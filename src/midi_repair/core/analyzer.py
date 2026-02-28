#!/usr/bin/env python3
"""
MIDI File Analyzer Module

This module provides analysis functionality for MIDI files:
- Analyze BPM information
- Detect empty event sections
- Provide diagnosis summary
- Return structured results
"""

import mido
from mido import Message, MetaMessage, MidiTrack
from collections import Counter
from typing import Dict, Any, List, Optional
import os


def analyze_midi(filepath: str, verbose: bool = True) -> Dict[str, Any]:
    """
    Analyze MIDI file for BPM and empty event issues.

    Args:
        filepath: Path to the MIDI file
        verbose: Whether to print analysis results

    Returns:
        Dictionary with analysis results
    """
    result = {
        "file_path": filepath,
        "file_exists": False,
        "file_type": None,
        "ticks_per_beat": None,
        "track_count": None,
        "tracks": [],
        "issues": [],
        "has_tempo": False,
        "original_bpm": None,
        "is_valid": False,
    }

    # Check if file exists
    if not os.path.exists(filepath):
        result["issues"].append(f"File not found: {filepath}")
        if verbose:
            print(f"ERROR: File not found: {filepath}")
        return result

    result["file_exists"] = True

    try:
        # Load MIDI file
        mid = mido.MidiFile(filepath)

        result["file_type"] = mid.type
        result["ticks_per_beat"] = mid.ticks_per_beat
        result["track_count"] = len(mid.tracks)

        if verbose:
            print("=" * 60)
            print(f"Analyzing MIDI file: {filepath}")
            print("=" * 60)
            print("\n[FILE OVERVIEW]")
            print(f"  - Type: {mid.type}")
            print(f"  - Ticks per beat (tpb): {mid.ticks_per_beat}")
            print(f"  - Number of tracks: {len(mid.tracks)}")

        # Analyze each track
        tempo_tracks = []

        for i, track in enumerate(mid.tracks):
            if verbose:
                print("\n" + "=" * 60)
                print(f"TRACK {i}: {track.name if track.name else 'Unnamed'}")
                print(f"  - Number of events: {len(track)}")

            track_info = {
                "index": i,
                "name": track.name if track.name else "Unnamed",
                "event_count": len(track),
                "msg_types": {},
                "has_tempo": False,
                "note_count": 0,
                "empty_count": 0,
                "bpm_values": [],
            }

            # Analyze events
            msg_types = Counter()
            has_tempo = False
            has_time_signature = False
            empty_count = 0
            note_events = []
            bpm_values = []
            last_tick = 0

            for j, msg in enumerate(track):
                msg_types[type(msg).__name__] += 1

                # Check for tempo (BPM)
                if isinstance(msg, MetaMessage):
                    if msg.type == "set_tempo":
                        has_tempo = True
                        tempo = msg.tempo
                        bpm = mido.tempo2bpm(tempo)
                        bpm_values.append(bpm)
                        track_info["bpm_values"].append(bpm)

                        if verbose:
                            print(f"\n  [TEMPO FOUND] at event {j}:")
                            print(f"     - Tempo: {tempo} microseconds/beat")
                            print(f"     - BPM: {bpm:.2f}")

                    elif msg.type == "time_signature":
                        has_time_signature = True
                        if verbose:
                            print(
                                f"\n  [TIME SIGNATURE] at event {j}: {msg.numerator}/{msg.denominator}"
                            )

                # Track empty/meta events
                if msg.type == "empty":
                    empty_count += 1
                    if empty_count <= 5 and verbose:
                        print(f"  [EMPTY EVENT] at tick {msg.time} (delta)")

                # Collect note events
                if msg.type in ("note_on", "note_off"):
                    note_events.append(msg)
                    last_tick = msg.time if hasattr(msg, "time") else 0

            track_info["msg_types"] = dict(msg_types)
            track_info["has_tempo"] = has_tempo
            track_info["note_count"] = len(note_events)
            track_info["empty_count"] = empty_count

            if has_tempo:
                tempo_tracks.append(i)

            if verbose:
                print(f"\n  [EVENT BREAKDOWN]")
                for msg_type, count in sorted(msg_types.items(), key=lambda x: -x[1]):
                    print(f"     {msg_type}: {count}")

                # BPM analysis
                print(f"\n  [BPM ANALYSIS]")
                if not has_tempo:
                    print(f"     MISSING: No tempo/set_tempo message found!")
                    print(
                        f"     -> Default MIDI tempo is 120 BPM (500000 microseconds/beat)"
                    )
                else:
                    print(f"     OK: Tempo message present")
                    if bpm_values:
                        print(
                            f"     BPM range: {min(bpm_values):.2f} - {max(bpm_values):.2f}"
                        )

                if not has_time_signature:
                    print(f"     WARNING: No time signature found, using default 4/4")

                # Empty event analysis
                print(f"\n  [EMPTY EVENT ANALYSIS]")
                print(f"     - Total empty events: {empty_count}")
                if empty_count > 0:
                    print(
                        f"     - Empty event ratio: {empty_count / len(track) * 100:.1f}%"
                    )

                # Note event analysis
                if note_events:
                    print(f"\n  [NOTE EVENTS]")
                    print(f"     - Total note events: {len(note_events)}")

            result["tracks"].append(track_info)

        # Overall diagnosis
        result["has_tempo"] = len(tempo_tracks) > 0
        result["original_bpm"] = (
            result["tracks"][0]["bpm_values"][0]
            if result["tracks"] and result["tracks"][0]["bpm_values"]
            else None
        )

        # Check for issues
        if not tempo_tracks:
            result["issues"].append(
                "NO TEMPO: No tempo meta message found in any track"
            )
        else:
            if verbose:
                print(f"\nOK: Tempo found in track(s): {tempo_tracks}")

        # Check for sparse tracks
        for track_info in result["tracks"]:
            if track_info["empty_count"] > track_info["event_count"] * 0.5:
                result["issues"].append(
                    f"TRACK {track_info['index']}: {track_info['empty_count']}/{track_info['event_count']} "
                    f"empty events ({track_info['empty_count'] / track_info['event_count'] * 100:.1f}%)"
                )

        # Check for tempo ramp (multiple tempo values)
        all_bpm_values = []
        for track_info in result["tracks"]:
            all_bpm_values.extend(track_info["bpm_values"])

        if len(set(all_bpm_values)) > 10:
            result["issues"].append(
                f"TEMPO RAMP: Multiple tempo values detected ({len(set(all_bpm_values))} unique BPM values). "
                "This can cause 'missing BPM' issues in some software."
            )

        result["is_valid"] = result["has_tempo"] and len(result["issues"]) == 0

        # Print diagnosis summary
        if verbose:
            print("\n" + "=" * 60)
            print("DIAGNOSIS SUMMARY")
            print("=" * 60)

            if result["issues"]:
                print("\nIssues detected:")
                for issue in result["issues"]:
                    print(f"  {issue}")
            else:
                print("OK: No major issues detected")

        return result

    except Exception as e:
        error_msg = f"Error analyzing MIDI: {str(e)}"
        result["issues"].append(error_msg)
        if verbose:
            print(f"ERROR: {error_msg}")
        return result


def get_diagnosis_summary(result: Dict[str, Any]) -> str:
    """
    Get a text summary of the diagnosis.

    Args:
        result: Analysis result from analyze_midi()

    Returns:
        Formatted summary string
    """
    lines = []
    lines.append("=" * 50)
    lines.append("MIDI FILE DIAGNOSIS")
    lines.append("=" * 50)
    lines.append(f"File: {result.get('file_path', 'Unknown')}")
    lines.append(f"Type: {result.get('file_type', 'Unknown')}")
    lines.append(f"Tracks: {result.get('track_count', 0)}")
    lines.append(f"Ticks/Beat: {result.get('ticks_per_beat', 0)}")
    lines.append("")

    if result.get("original_bpm"):
        lines.append(f"Detected BPM: {result['original_bpm']:.1f}")

    lines.append("")

    if result.get("issues"):
        lines.append("ISSUES FOUND:")
        for issue in result["issues"]:
            lines.append(f"  - {issue}")
    else:
        lines.append("STATUS: No issues detected")

    lines.append("=" * 50)

    return "\n".join(lines)
