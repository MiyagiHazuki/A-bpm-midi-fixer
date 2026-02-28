#!/usr/bin/env python3
"""
Canvas component for BPM visualization and segment manipulation.

Features:
- Display BPM change curve
- Display note density histogram
- Drag segment boundaries
- Click to add/delete segments
- Right-click context menu
"""

import tkinter as tk
from typing import List, Optional, Callable
import copy
import mido
import numpy as np

from .models import Section, BPMChangePoint


class BPMVisualizationCanvas(tk.Canvas):
    """Canvas for BPM visualization and segment manipulation."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.sections: List[Section] = []
        self.total_duration: float = 0.0

        # MIDI data for visualization
        self.midi_file: Optional[mido.MidiFile] = None
        self.note_density: Optional[np.ndarray] = None  # Density array
        self.bpm_changes: List[BPMChangePoint] = []  # BPM change points

        # Display mode
        self.show_segments: bool = False

        # Zoom and pan state
        self.zoom_level: float = 1.0
        self.pan_offset: float = 0.0
        self.dragging: bool = False
        self.drag_start_x: int = 0
        self.selected_segment: Optional[Section] = None
        self.drag_action: Optional[str] = None  # 'start', 'end', or None

        # Visual constants
        self.width = 900
        self.height = 300
        self.configure(width=self.width, height=self.height)

        # Bind events
        self.bind("<Configure>", self._on_resize)
        self.bind("<ButtonPress-1>", self._on_mouse_down)
        self.bind("<B1-Motion>", self._on_mouse_drag)
        self.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.bind("<Button-3>", self._on_right_click)
        self.bind("<Motion>", self._on_mouse_move)

        # Undo/Redo stacks
        self.undo_stack: List[List[Section]] = []
        self.redo_stack: List[List[Section]] = []

        # Callbacks
        self.on_segments_changed: Optional[Callable] = None
        self.on_edit_segment: Optional[Callable] = None

        # Tooltip state
        self.tooltip_text = None
        self.tooltip_rect = None
        self.hovered_section = None

    def _on_resize(self, event):
        """Handle canvas resize."""
        if self.width != event.width or self.height != event.height:
            self.width = event.width
            self.height = event.height
            self.redraw()

    def set_midi_data(self, midi_file: mido.MidiFile):
        """
        Set MIDI data for visualization.

        Args:
            midi_file: Mido MidiFile object
        """
        self.midi_file = midi_file
        self.total_duration = midi_file.length
        self.show_segments = False  # Don't show segments initially

        # Extract BPM changes
        self._extract_bpm_changes()

        # Calculate note density
        self._calculate_note_density()

        # Redraw with raw data
        self.redraw()

    def set_sections(self, sections: List[Section]):
        """
        Update sections to display.

        Args:
            sections: List of Section objects
        """
        # Save to undo stack
        if self.sections and self.sections != sections:
            self.undo_stack.append(copy.deepcopy(self.sections))
            self.redo_stack.clear()

        self.sections = sections
        self.show_segments = True
        self.redraw()

    def _extract_bpm_changes(self):
        """Extract BPM change events from MIDI file."""
        self.bpm_changes = []

        if not self.midi_file:
            return

        # Time tracking
        current_time = 0.0

        for track in self.midi_file.tracks:
            for msg in track:
                current_time += msg.time

                if msg.type == "set_tempo":
                    bpm = int(mido.tempo2bpm(msg.tempo) + 0.5)
                    self.bpm_changes.append(BPMChangePoint(time=current_time, bpm=bpm))

        # Sort by time
        self.bpm_changes.sort(key=lambda x: x.time)

    def _calculate_note_density(self):
        """Calculate note density histogram from MIDI data."""
        if self.midi_file is None:
            return

        # Calculate bins (0.1 second per bin)
        bin_size = 0.1
        num_bins = int(self.total_duration / bin_size) + 1
        self.note_density = np.zeros(num_bins, dtype=int)

        # Collect notes
        current_time = 0.0
        for track in self.midi_file.tracks:
            for msg in track:
                current_time += msg.time
                if msg.type == "note_on":
                    bin_idx = int(current_time / bin_size)
                    if 0 <= bin_idx < num_bins:
                        self.note_density[bin_idx] += 1

    def _draw_bpm_curve(self):
        """Draw BPM change curve."""
        if not self.bpm_changes:
            return

        # Find BPM range for scaling
        min_bpm = min(p.bpm for p in self.bpm_changes)
        max_bpm = max(p.bpm for p in self.bpm_changes)
        bpm_range = max_bpm - min_bpm if max_bpm != min_bpm else 1

        # Draw curve
        points = []
        for i, change in enumerate(self.bpm_changes):
            x = self._time_to_x(change.time)
            # Scale BPM to canvas height (leave padding)
            y = (
                self.height
                - 50
                - ((change.bpm - min_bpm) / bpm_range) * (self.height - 100)
            )
            points.append((x, y))

        # Draw line segments
        if len(points) >= 2:
            for i in range(len(points) - 1):
                self.create_line(
                    points[i][0],
                    points[i][1],
                    points[i + 1][0],
                    points[i + 1][1],
                    fill="#0066cc",
                    width=2,
                    tags="bpm_curve",
                )

        # Draw BPM labels at key points
        for change in self.bpm_changes:
            if i % 2 == 0:  # Show every other point to avoid clutter
                x = self._time_to_x(change.time)
                y = (
                    self.height
                    - 50
                    - ((change.bpm - min_bpm) / bpm_range) * (self.height - 100)
                )

                # Draw label background
                self.create_rectangle(
                    x - 25,
                    y - 20,
                    x + 25,
                    y,
                    fill="#ffffcc",
                    outline="#cccccc",
                    tags="bpm_label_bg",
                )
                self.create_text(
                    x,
                    y - 10,
                    text=f"{change.bpm}",
                    fill="#333333",
                    font=("Arial", 9, "bold"),
                    tags="bpm_label",
                )

    def _draw_note_density(self):
        """Draw note density as semi-transparent bars."""
        if self.note_density is None:
            return

        max_density = np.max(self.note_density)
        if max_density == 0:
            return

        # Draw density at bottom (lower half)
        base_y = self.height - 30
        max_height = self.height * 0.3

        bar_width = self.width / len(self.note_density)

        for i, density in enumerate(self.note_density):
            if density == 0:
                continue

            bar_height = (density / max_density) * max_height

            x1 = i * bar_width
            x2 = x1 + bar_width - 1
            y1 = base_y - bar_height
            y2 = base_y

            # Color based on density
            intensity = min(255, 100 + int((density / max_density) * 155))
            color = f"#2020{intensity:02x}"

            self.create_rectangle(x1, y1, x2, y2, fill=color, outline="")

    def redraw(self):
        """Redraw canvas with current data."""
        self.delete("all")

        # Draw background
        self.create_rectangle(0, 0, self.width, self.height, fill="#f8f9fa", outline="")

        # If no MIDI data loaded, show empty state
        if self.midi_file is None:
            self.create_text(
                self.width / 2,
                self.height / 2,
                text="请先选择 MIDI 文件",
                fill="#999999",
                font=("Arial", 14),
            )
            return

        # Draw BPM curve (top layer)
        self._draw_bpm_curve()

        # Draw note density (bottom layer)
        self._draw_note_density()

        # Draw segments (if enabled)
        if self.show_segments and self.sections:
            self._draw_segments()

        # Draw time grid
        self._draw_time_grid()

        # Draw status message
        if not self.show_segments:
            self.create_text(
                self.width / 2,
                15,
                text="BPM 曲线与音符密度 - 右键点击添加分段",
                fill="#666666",
                font=("Arial", 10),
            )

    def _draw_segments(self):
        """Draw segment overlays."""
        for i, section in enumerate(self.sections):
            x1 = self._time_to_x(section.start)
            x2 = self._time_to_x(section.end)

            # Color based on BPM value
            bpm = section.bpm
            if bpm == 120:
                color = "#e0e0e0"  # Grey - default BPM
            elif bpm > 120:
                # Light green for faster
                intensity = int(max(0, 240 - (bpm - 120) * 2))
                color = f"#{intensity:02x}ff{intensity:02x}"
            else:
                # Light red for slower
                intensity = int(max(0, 240 - (120 - bpm) * 2))
                color = f"#ff{intensity:02x}{intensity:02x}"

            # Highlight selected segment
            if section == self.selected_segment:
                outline = "#ff0000"
                width = 2
                bg_stipple = "gray50"
            else:
                outline = ""
                width = 0
                bg_stipple = "gray25"

            # Draw segment background (top half)
            self.create_rectangle(
                x1,
                0,
                x2,
                self.height - 50,
                fill=color,
                outline=outline,
                width=width,
                tags=f"segment_{i}",
                stipple=bg_stipple,
            )

            # Draw BPM value in center
            mid_x = (x1 + x2) / 2
            mid_y = self.height * 0.25

            self.create_rectangle(
                mid_x - 20,
                mid_y - 15,
                mid_x + 20,
                mid_y + 15,
                fill="white",
                outline="#dddddd",
            )
            self.create_text(
                mid_x,
                mid_y,
                text=f"BPM: {section.bpm}",
                fill="#333333",
                font=("Arial", 11, "bold"),
            )

            # Draw boundary line
            line_width = 2
            line_color = "#d9534f"

            # Left boundary
            self.create_line(
                x1,
                0,
                x1,
                self.height - 50,
                fill=line_color,
                width=line_width,
                dash=(4, 2),
                tags=f"boundary_{section.start}",
            )

            # Right boundary (only for last segment)
            if i == len(self.sections) - 1:
                self.create_line(
                    x2,
                    0,
                    x2,
                    self.height - 50,
                    fill=line_color,
                    width=line_width,
                    dash=(4, 2),
                    tags=f"boundary_{section.end}",
                )

    def _draw_time_grid(self):
        """Draw time grid lines and labels."""
        # Calculate appropriate tick spacing
        duration = self.total_duration * self.zoom_level
        if duration <= 30:
            tick_interval = 5
        elif duration <= 120:
            tick_interval = 15
        else:
            tick_interval = 30

        for t in np.arange(0, self.total_duration, tick_interval):
            x = self._time_to_x(float(t))
            self.create_line(
                x, self.height - 30, x, self.height, fill="#cccccc", dash=(2, 2)
            )

            minutes = int(t // 60)
            seconds = int(t % 60)
            label = f"{minutes:02d}:{seconds:02d}"
            self.create_text(
                x + 2,
                self.height - 5,
                text=label,
                anchor="sw",
                fill="#666666",
                font=("Arial", 8),
            )

    def _time_to_x(self, time: float) -> float:
        """Convert time in seconds to x coordinate."""
        if self.total_duration == 0:
            return 0

        pixels_per_second = self.width / self.total_duration
        x = time * pixels_per_second * self.zoom_level + self.pan_offset
        return max(0, min(self.width, x))

    def _x_to_time(self, x: float) -> float:
        """Convert x coordinate to time in seconds."""
        pixels_per_second = self.width / self.total_duration
        time = (x - self.pan_offset) / (pixels_per_second * self.zoom_level)
        return max(0, min(self.total_duration, time))

    def _on_mouse_down(self, event):
        """Handle mouse click."""
        self.dragging = True
        self.drag_start_x = event.x
        self.drag_action = None

        # Check if clicking near a start boundary
        for section in self.sections:
            boundary_x = self._time_to_x(section.start)
            if abs(event.x - boundary_x) < 8:
                self.selected_segment = section
                self.drag_action = "start"
                return

        # Check if clicking near an end boundary
        for section in self.sections:
            boundary_x = self._time_to_x(section.end)
            if abs(event.x - boundary_x) < 8:
                self.selected_segment = section
                self.drag_action = "end"
                return

        # Check if clicking inside a segment
        for section in self.sections:
            x1 = self._time_to_x(section.start)
            x2 = self._time_to_x(section.end)
            if x1 <= event.x <= x2:
                self.selected_segment = section
                self.redraw()
                return

        # Clicked in empty space
        self.selected_segment = None
        self.redraw()

    def _on_mouse_drag(self, event):
        """Handle mouse drag."""
        if not self.dragging or self.selected_segment is None or not self.drag_action:
            return

        new_time = self._x_to_time(event.x)

        try:
            idx = self.sections.index(self.selected_segment)
        except ValueError:
            return

        if self.drag_action == "start":
            min_t = 0.0
            if idx > 0:
                min_t = self.sections[idx - 1].start + 0.1

            max_t = self.selected_segment.end - 0.1
            new_time = max(min_t, min(new_time, max_t))

            old_start = self.selected_segment.start
            self.selected_segment.start = new_time

            if idx > 0 and abs(self.sections[idx - 1].end - old_start) < 0.001:
                self.sections[idx - 1].end = new_time

        elif self.drag_action == "end":
            min_t = self.selected_segment.start + 0.1
            max_t = self.total_duration

            if idx < len(self.sections) - 1:
                max_t = self.sections[idx + 1].end - 0.1

            new_time = max(min_t, min(new_time, max_t))

            old_end = self.selected_segment.end
            self.selected_segment.end = new_time

            if (
                idx < len(self.sections) - 1
                and abs(self.sections[idx + 1].start - old_end) < 0.001
            ):
                self.sections[idx + 1].start = new_time

        self.redraw()

    def _on_mouse_up(self, event):
        """Handle mouse release."""
        if self.dragging:
            self.dragging = False

            if self.on_segments_changed:
                self.on_segments_changed(self.sections)

    def _on_right_click(self, event):
        """Handle right-click to show context menu."""
        click_time = self._x_to_time(event.x)

        # Check if clicking on a segment
        clicked_section = None
        for section in self.sections:
            if section.start <= click_time <= section.end:
                clicked_section = section
                break

        # Create popup menu
        menu = tk.Menu(self, tearoff=0)

        # Check if clicking on a boundary
        boundary_clicked = False
        for i, section in enumerate(self.sections):
            boundary_x = self._time_to_x(section.start)
            if abs(event.x - boundary_x) < 8:
                if 0 < i < len(self.sections) - 1:
                    boundary_clicked = True
                    menu.add_command(
                        label="删除此分界线",
                        command=lambda: self._delete_boundary(i),
                    )
                    break

        if not boundary_clicked and clicked_section:
            # Segment context menu
            menu.add_command(
                label="编辑分段设置",
                command=lambda: self.on_edit_segment(clicked_section)
                if self.on_edit_segment
                else None,
            )
            menu.add_separator()

            # Add split option
            menu.add_command(
                label="在此处分割",
                command=lambda: self._split_segment(click_time),
            )

        if not boundary_clicked and not clicked_section:
            # Empty space - add boundary
            if 0 < click_time < self.total_duration:
                menu.add_command(
                    label="在此处添加分界线",
                    command=lambda: self._add_boundary(click_time),
                )

        # Show menu
        if menu.index("end") is not None:
            menu.post(event.x_root, event.y_root)

    def _delete_boundary(self, index):
        """Delete boundary at index."""
        if not (0 < index < len(self.sections)):
            return

        self.undo_stack.append(copy.deepcopy(self.sections))
        self.redo_stack.clear()

        # Merge with neighboring segment
        prev_section = self.sections[index - 1]
        next_section = self.sections[index]

        prev_section.end = next_section.end
        self.sections.pop(index)

        self.redraw()
        if self.on_segments_changed:
            self.on_segments_changed(self.sections)

    def _split_segment(self, split_time):
        """Split segment at given time."""
        if not (0 < split_time < self.total_duration):
            return

        self.undo_stack.append(copy.deepcopy(self.sections))
        self.redo_stack.clear()

        for i, section in enumerate(self.sections):
            if section.start <= split_time <= section.end:
                new_section = Section(
                    start=split_time,
                    end=section.end,
                    bpm=section.bpm,
                    description=section.description + " (分割)",
                )
                section.end = split_time
                self.sections.insert(i + 1, new_section)
                break

        self.redraw()
        if self.on_segments_changed:
            self.on_segments_changed(self.sections)

    def _add_boundary(self, time):
        """Add a new boundary at the given time."""
        if not (0 < time < self.total_duration):
            return

        # Find which segment to split
        for i, section in enumerate(self.sections):
            if section.start <= time <= section.end:
                # Only split if not at exact boundary
                if abs(time - section.start) > 0.1 and abs(time - section.end) > 0.1:
                    new_section = Section(
                        start=time,
                        end=section.end,
                        bpm=section.bpm,
                        description="用户添加",
                    )
                    section.end = time
                    self.sections.insert(i + 1, new_section)

                    self.undo_stack.append(copy.deepcopy(self.sections))
                    self.redo_stack.clear()

                    self.redraw()
                    if self.on_segments_changed:
                        self.on_segments_changed(self.sections)
                break

    def undo(self):
        """Undo last action."""
        if self.undo_stack:
            self.redo_stack.append(copy.deepcopy(self.sections))
            self.sections = self.undo_stack.pop()
            self.redraw()
            if self.on_segments_changed:
                self.on_segments_changed(self.sections)

    def redo(self):
        """Redo last undone action."""
        if self.redo_stack:
            self.undo_stack.append(copy.deepcopy(self.sections))
            self.sections = self.redo_stack.pop()
            self.redraw()
            if self.on_segments_changed:
                self.on_segments_changed(self.sections)

    def _on_mouse_move(self, event):
        """Handle mouse movement for tooltips."""
        if not self.sections or self.dragging:
            self._hide_tooltip()
            return

        time = self._x_to_time(event.x)
        hovered = None

        for section in self.sections:
            if section.start <= time <= section.end:
                hovered = section
                break

        if hovered != self.hovered_section:
            self.hovered_section = hovered
            self.redraw()

        if hovered:
            self._show_tooltip(event.x, event.y, hovered)
        else:
            self._hide_tooltip()

    def _show_tooltip(self, x, y, section):
        """Show tooltip for section."""
        self._hide_tooltip()

        duration = section.duration
        text = (
            f"BPM: {section.bpm}\n时长: {duration:.1f}秒\n音符数: {section.note_count}"
        )

        text_id = self.create_text(
            x + 15,
            y + 15,
            text=text,
            anchor="nw",
            font=("Arial", 9),
            fill="#333",
            tags="tooltip",
        )
        bbox = self.bbox(text_id)

        pad = 5
        rect_id = self.create_rectangle(
            bbox[0] - pad,
            bbox[1] - pad,
            bbox[2] + pad,
            bbox[3] + pad,
            fill="#ffffe0",
            outline="#333",
            tags="tooltip_bg",
        )

        self.tag_raise("tooltip")
        self.tooltip_text = text_id
        self.tooltip_rect = rect_id

    def _hide_tooltip(self):
        """Hide tooltip."""
        self.delete("tooltip")
        self.delete("tooltip_bg")
        self.tooltip_text = None
        self.tooltip_rect = None
