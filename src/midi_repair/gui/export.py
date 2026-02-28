#!/usr/bin/env python3
"""
Segment export functionality for BPM-based MIDI repair.
"""

import mido
from mido import MetaMessage, MidiTrack
from typing import List
import os

from .models import Section


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

        if verbose:
            print(f"Original file:")
            print(f"  Type: {mid.type}")
            print(f"  Ticks per beat: {mid.ticks_per_beat}")
            print(f"  Tracks: {len(mid.tracks)}")

        # Sort sections by start time
        sorted_sections = sorted(sections, key=lambda s: s.start)

        # Create new tempo track
        new_tempo_track = MidiTrack()

        # Add time signature at start
        new_tempo_track.append(
            MetaMessage("time_signature", numerator=4, denominator=4, time=0)
        )

        # Add tempo changes for each segment
        last_time = 0.0
        for section in sorted_sections:
            if section.start > last_time:
                # Add tempo change at segment start
                tempo_value = mido.bpm2tempo(section.bpm)
                new_tempo_track.append(
                    MetaMessage(
                        "set_tempo",
                        tempo=tempo_value,
                        time=int(section.start * mid.ticks_per_beat),
                    )
                )

                if verbose:
                    print(
                        f"  [{section.start:.1f}s - {section.end:.1f}s]: {section.bpm} BPM"
                    )

            last_time = section.end

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
