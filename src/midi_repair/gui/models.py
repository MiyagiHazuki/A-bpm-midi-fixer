#!/usr/bin/env python3
"""
Data models for MIDI segment visualization.
"""

from dataclasses import dataclass


@dataclass
class Section:
    """Represents a time segment with BPM settings.

    Attributes:
        start: Start time in seconds
        end: End time in seconds
        bpm: BPM value for this segment
        note_count: Number of notes in this segment
    """

    start: float
    end: float
    bpm: int = 120
    note_count: int = 0
    description: str = ""

    @property
    def duration(self) -> float:
        """Get segment duration in seconds."""
        return self.end - self.start


@dataclass
class BPMChangePoint:
    """Represents a BPM change event in the MIDI file.

    Attributes:
        time: Time in seconds
        bpm: BPM value
    """

    time: float
    bpm: int
