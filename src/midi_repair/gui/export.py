#!/usr/bin/env python3
"""
Segment export functionality for BPM-based MIDI repair.
"""

import mido
from mido import MetaMessage, MidiTrack
from typing import List, Tuple
import os

from .models import Section


def _seconds_to_ticks(seconds: float, bpm: int, ticks_per_beat: int) -> int:
    """Convert seconds to MIDI ticks based on BPM.

    Args:
        seconds: Time in seconds
        bpm: Beats per minute
        ticks_per_beat: Ticks per beat from MIDI file

    Returns:
        Time in ticks
    """
    ticks_per_second = (ticks_per_beat * bpm) / 60.0
    return int(seconds * ticks_per_second)


def _get_original_tempo_map(mid: mido.MidiFile) -> List[Tuple[int, int]]:
    """Extract tempo events from the original MIDI file.

    Args:
        mid: Mido MidiFile object

    Returns:
        List of (tick_position, tempo_microseconds) sorted by tick_position
    """
    tempo_map = []

    # Look for tempo events in track 0 (tempo track)
    # For type 1 MIDI, track 0 is tempo track
    # For type 0 MIDI, all events are in track 0
    if not mid.tracks:
        return tempo_map

    tempo_track = mid.tracks[0]

    cumulative_ticks = 0
    for msg in tempo_track:
        cumulative_ticks += msg.time
        if hasattr(msg, "type") and msg.type == "set_tempo":
            tempo_map.append((cumulative_ticks, msg.tempo))

    # Sort by tick position (should already be sorted but ensure)
    tempo_map.sort(key=lambda x: x[0])

    return tempo_map


def _seconds_to_ticks_using_original_tempo(
    seconds: float, tempo_map: List[Tuple[int, int]], ticks_per_beat: int
) -> int:
    """Convert seconds to MIDI ticks using original tempo map.

    This function properly handles multiple tempo changes by calculating
    cumulative time through each tempo segment.

    Args:
        seconds: Time position in seconds
        tempo_map: List of (tick_position, tempo_microseconds) from original MIDI
        ticks_per_beat: Ticks per beat from MIDI file

    Returns:
        Time in ticks
    """
    if not tempo_map:
        # Default to 120 BPM if no tempo found
        default_tempo = 500000  # 120 BPM in microseconds per beat
        ticks_per_second = (ticks_per_beat * mido.tempo2bpm(default_tempo)) / 60.0
        return int(seconds * ticks_per_second)

    # Calculate cumulative time up to each tempo event
    cumulative_time = 0.0
    cumulative_ticks = 0

    for i, (tick_pos, tempo) in enumerate(tempo_map):
        # Calculate ticks from previous tempo to this tempo
        if i == 0:
            ticks_to_this = tick_pos
        else:
            prev_tick = tempo_map[i - 1][0]
            ticks_to_this = tick_pos - prev_tick

        # Convert these ticks to seconds using the tempo at this segment
        prev_tempo = tempo_map[i - 1][1] if i > 0 else tempo_map[0][1]
        ticks_per_second = (ticks_per_beat * mido.tempo2bpm(prev_tempo)) / 60.0
        segment_seconds = (
            ticks_to_this / ticks_per_second if ticks_per_second > 0 else 0
        )

        # Check if target time is before this tempo event
        if seconds < cumulative_time + segment_seconds:
            # Target is in this segment
            remaining_seconds = seconds - cumulative_time
            return cumulative_ticks + int(remaining_seconds * ticks_per_second)

        cumulative_time += segment_seconds
        cumulative_ticks += ticks_to_this

    # After all known tempo events, use the last tempo
    remaining_seconds = seconds - cumulative_time
    last_tempo = tempo_map[-1][1]
    ticks_per_second = (ticks_per_beat * mido.tempo2bpm(last_tempo)) / 60.0
    return cumulative_ticks + int(remaining_seconds * ticks_per_second)


def export_segments_to_midi(
    input_file: str,
    output_file: str,
    sections: List[Section],
    verbose: bool = True,
) -> tuple[bool, str]:
    """
    Export MIDI with segment-based BPM changes.

    Args:
        input_file: Path to input MIDI file
        output_file: Path to output MIDI file
        sections: List of sections with BPM settings
        verbose: Whether to print progress

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        if verbose:
            print(f"Loading: {input_file}")

        # Load original MIDI
        mid = mido.MidiFile(input_file)

        # Extract original tempo map for accurate time conversion
        original_tempo_map = _get_original_tempo_map(mid)

        if verbose:
            print(f"Original file:")
            print(f"  Type: {mid.type}")
            print(f"  Ticks per beat: {mid.ticks_per_beat}")
            print(f"  Tracks: {len(mid.tracks)}")
            if original_tempo_map:
                print(f"  Original tempo events: {len(original_tempo_map)}")

        # Sort sections by start time
        sorted_sections = sorted(sections, key=lambda s: s.start)

        # Create new tempo track
        new_tempo_track = MidiTrack()

        # Add time signature at start
        new_tempo_track.append(
            MetaMessage("time_signature", numerator=4, denominator=4, time=0)
        )

        # Add tempo changes for each segment
        last_ticks = 0
        for i, section in enumerate(sorted_sections):
            # Calculate tick position using ORIGINAL tempo (not target BPM)
            # This ensures time positions match what the GUI displays
            current_ticks = _seconds_to_ticks_using_original_tempo(
                section.start, original_tempo_map, mid.ticks_per_beat
            )
            delta_ticks = current_ticks - last_ticks

            # Add tempo change at segment start (always add for first segment)
            # The tempo VALUE is the target BPM, but position is calculated using original tempo
            tempo_value = mido.bpm2tempo(section.bpm)
            new_tempo_track.append(
                MetaMessage(
                    "set_tempo",
                    tempo=tempo_value,
                    time=delta_ticks,
                )
            )

            if verbose:
                print(
                    f"  [{section.start:.1f}s - {section.end:.1f}s]: {section.bpm} BPM "
                    f"(tick_pos={current_ticks}, delta_ticks={delta_ticks})"
                )

            last_ticks = current_ticks

        # Copy other tracks (skip original tempo events from track 0)
        new_tracks = [new_tempo_track]

        for track in mid.tracks[1:]:
            new_track = MidiTrack()

            # Copy events, but skip tempo messages
            for msg in track:
                if hasattr(msg, "type") and msg.type == "set_tempo":
                    continue
                new_track.append(msg)

            new_tracks.append(new_track)

        # Create new MIDI file
        new_mid = mido.MidiFile(type=mid.type, ticks_per_beat=mid.ticks_per_beat)
        new_mid.tracks = new_tracks

        # Ensure output directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Save
        if verbose:
            print(f"\nSaving: {output_file}")

        new_mid.save(output_file)

        if verbose:
            print("\n=== Export Complete ===")
            print(f"  - Segments: {len(sections)}")
            print(f"  - Output: {output_file}")

        return True, f"成功导出分段BPM MIDI文件，共 {len(sections)} 个分段"

    except Exception as e:
        error_msg = f"导出分段MIDI失败: {str(e)}"
        if verbose:
            print(f"ERROR: {error_msg}")
        return False, error_msg
