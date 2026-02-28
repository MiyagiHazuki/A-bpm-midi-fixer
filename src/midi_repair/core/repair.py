#!/usr/bin/env python3
"""
MIDI File Repair Module

This module provides core functionality for repairing MIDI files:
- Sets a single stable tempo (removes continuous tempo changes)
- Removes large gaps in tempo track
- Supports custom BPM setting
- Auto-detects original BPM from file
"""

import mido
from mido import Message, MetaMessage, MidiTrack
from typing import Optional, Tuple, Dict, Any
import os


def detect_original_bpm(input_file: str) -> Optional[int]:
    """
    Detect the original BPM from a MIDI file.

    Args:
        input_file: Path to the MIDI file

    Returns:
        Integer BPM value if found, None otherwise
    """
    try:
        mid = mido.MidiFile(input_file)
        if mid.tracks:
            for msg in mid.tracks[0]:
                if hasattr(msg, "type") and msg.type == "set_tempo":
                    original_bpm = mido.tempo2bpm(msg.tempo)
                    return int(original_bpm + 0.5)
    except Exception:
        pass
    return None


def repair_midi(
    input_file: str,
    output_file: str,
    target_bpm: Optional[int] = None,
    verbose: bool = True,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Repair the MIDI file:
    - Set a single stable tempo (removes tempo ramp)
    - Remove large gaps in tempo track
    - Optionally detect and use original BPM

    Args:
        input_file: Path to input MIDI file
        output_file: Path to output MIDI file
        target_bpm: Target BPM (if None, auto-detects from original)
        verbose: Whether to print progress messages

    Returns:
        Tuple of (success: bool, message: str, details: dict)
    """
    details = {
        "original_bpm": None,
        "target_bpm": None,
        "tracks_processed": 0,
        "notes_copied": 0,
    }

    try:
        if verbose:
            print(f"Loading: {input_file}")

        # Check if input file exists
        if not os.path.exists(input_file):
            return False, f"Input file not found: {input_file}", details

        mid = mido.MidiFile(input_file)

        if verbose:
            print(f"Original file:")
            print(f"  Type: {mid.type}")
            print(f"  Ticks per beat: {mid.ticks_per_beat}")
            print(f"  Tracks: {len(mid.tracks)}")

        # Detect original BPM
        detected_bpm = detect_original_bpm(input_file)
        details["original_bpm"] = detected_bpm

        # Determine target BPM
        if target_bpm is None:
            target_bpm = detected_bpm if detected_bpm else 80

        details["target_bpm"] = target_bpm

        if verbose:
            if detected_bpm:
                print(f"Detected original BPM: {detected_bpm}")
            print(f"Using target BPM: {target_bpm}")

        # Create new tempo track (Track 0)
        new_tempo_track = MidiTrack()

        # Add single tempo event at the start
        # target_bpm BPM = 60000000/target_bpm microseconds per beat
        tempo_value = mido.bpm2tempo(target_bpm)
        new_tempo_track.append(MetaMessage("set_tempo", tempo=tempo_value, time=0))

        # Add time signature (4/4)
        new_tempo_track.append(
            MetaMessage("time_signature", numerator=4, denominator=4, time=0)
        )

        # Copy other tracks but skip their tempo data to avoid conflicts
        new_tracks = [new_tempo_track]

        for i, track in enumerate(mid.tracks[1:], 1):
            new_track = MidiTrack()

            # Copy events, but skip meta tempo messages from original track 0
            for msg in track:
                if hasattr(msg, "type") and msg.type == "set_tempo":
                    continue  # Skip tempo in non-tempo tracks
                new_track.append(msg)

            new_tracks.append(new_track)

            # Report note counts
            note_events = [m for m in track if m.type in ("note_on", "note_off")]
            details["notes_copied"] += len(note_events)

            if verbose:
                print(f"  Track {i}: {len(note_events)} note events copied")

        details["tracks_processed"] = len(mid.tracks)

        # Create new MIDI file
        new_mid = mido.MidiFile(type=mid.type, ticks_per_beat=mid.ticks_per_beat)
        new_mid.tracks = new_tracks

        # Save
        if verbose:
            print(f"\nSaving: {output_file}")

        # Ensure output directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        new_mid.save(output_file)

        if verbose:
            print("\n=== Repair Complete ===")
            print(f"  - Single tempo: {target_bpm} BPM")
            print(f"  - Removed continuous tempo changes")
            print(f"  - Output: {output_file}")

        return (
            True,
            f"Successfully repaired MIDI file. BPM set to {target_bpm}",
            details,
        )

    except Exception as e:
        error_msg = f"Error repairing MIDI: {str(e)}"
        if verbose:
            print(f"ERROR: {error_msg}")
        return False, error_msg, details


def verify_midi(filepath: str) -> Dict[str, Any]:
    """
    Verify a MIDI file after repair.

    Args:
        filepath: Path to the MIDI file to verify

    Returns:
        Dictionary with verification results
    """
    result = {
        "valid": False,
        "tracks": 0,
        "tempo_events": 0,
        "note_events": 0,
        "has_tempo": False,
        "errors": [],
    }

    try:
        mid = mido.MidiFile(filepath)
        result["tracks"] = len(mid.tracks)

        for i, track in enumerate(mid.tracks):
            tempos = [m for m in track if hasattr(m, "type") and m.type == "set_tempo"]
            notes = [m for m in track if m.type in ("note_on", "note_off")]

            result["tempo_events"] += len(tempos)
            result["note_events"] += len(notes)

            if tempos:
                result["has_tempo"] = True

        result["valid"] = result["has_tempo"] and result["note_events"] > 0

        if not result["has_tempo"]:
            result["errors"].append("No tempo event found")
        if result["note_events"] == 0:
            result["errors"].append("No note events found")

    except Exception as e:
        result["errors"].append(str(e))

    return result
