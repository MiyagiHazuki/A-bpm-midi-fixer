#!/usr/bin/env python3
"""
Command-line interface for MIDI Repair Tool

Usage:
    python -m midi_repair.cli input.mid [options]
    python -m midi_repair.cli input.mid --output output.mid --bpm 120
    python -m midi_repair.cli input.mid --analyze-only
"""

import argparse
import sys
import os

# Add src to path for imports
# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from midi_repair.core.repair import repair_midi, verify_midi, detect_original_bpm
from midi_repair.core.analyzer import analyze_midi, get_diagnosis_summary


def main():
    parser = argparse.ArgumentParser(
        description="MIDI Repair Tool - Fix problematic MIDI files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  midi-repair input.mid                      # Fix with auto-detected BPM
  midi-repair input.mid --bpm 120            # Fix with specific BPM
  midi-repair input.mid --output fixed.mid   # Specify output file
  midi-repair input.mid --analyze-only      # Analyze without fixing
        """,
    )

    parser.add_argument("input", nargs="?", help="Input MIDI file path")

    parser.add_argument(
        "-o", "--output", help="Output MIDI file path (default: input_fixed.mid)"
    )

    parser.add_argument(
        "-b",
        "--bpm",
        type=int,
        help="Target BPM for repair (default: auto-detect from original, or 80)",
    )

    parser.add_argument(
        "-a", "--analyze-only", action="store_true", help="Analyze file without fixing"
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    parser.add_argument(
        "--version", action="version", version="MIDI Repair Tool v1.0.0"
    )

    args = parser.parse_args()

    # Handle no arguments
    if args.input is None:
        parser.print_help()
        return 1

    input_file = args.input

    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        return 1

    # Analyze first
    print("\n" + "=" * 60)
    print("MIDI REPAIR TOOL")
    print("=" * 60 + "\n")

    result = analyze_midi(input_file, verbose=True)

    print("\n" + get_diagnosis_summary(result))

    # Exit if analyze-only mode
    if args.analyze_only:
        return 0

    # Determine output file
    if args.output:
        output_file = args.output
    else:
        # Auto-generate output filename
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}_fixed{ext}"

    # Determine BPM
    target_bpm = args.bpm

    print("\n" + "=" * 60)
    print("REPAIRING MIDI FILE")
    print("=" * 60)

    # Run repair
    success, message, details = repair_midi(
        input_file=input_file,
        output_file=output_file,
        target_bpm=target_bpm,
        verbose=True,
    )

    if success:
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)

        verify_result = verify_midi(output_file)
        print(f"Valid: {verify_result['valid']}")
        print(f"Tracks: {verify_result['tracks']}")
        print(f"Tempo events: {verify_result['tempo_events']}")
        print(f"Note events: {verify_result['note_events']}")

        if verify_result["errors"]:
            print("Errors:")
            for error in verify_result["errors"]:
                print(f"  - {error}")

        print(f"\n✓ Output saved to: {output_file}")
        return 0
    else:
        print(f"\n✗ Error: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
