#!/usr/bin/env python3
"""
Dialog for configuring individual segment BPM settings.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict

from .models import Section

class BPMSegmentSettingsDialog(tk.Toplevel):
    """Dialog for configuring BPM settings for a segment."""

    def __init__(
        self,
        parent,
        section: Section,
        min_bpm: int = 40,
        max_bpm: int = 240,
    ):
        super().__init__(parent)
        self.title("分段BPM设置")
        self.geometry("350x200")
        self.resizable(False, False)

        self.section = section
        self.result = None

        # Center dialog
        self.transient(parent)
        self.grab_set()

        # UI
        padding = 10
        frame = ttk.Frame(self, padding=padding)
        frame.pack(fill=tk.BOTH, expand=True)

        # BPM input
        ttk.Label(frame, text="BPM:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.bpm_var = tk.IntVar(value=section.bpm)
        bpm_spin = ttk.Spinbox(
            frame,
            from_=min_bpm,
            to=max_bpm,
            textvariable=self.bpm_var,
            width=15,
        )
        bpm_spin.grid(row=0, column=1, sticky=tk.W, pady=5)

        # Description input
        ttk.Label(frame, text="描述:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.desc_var = tk.StringVar(value=section.description)
        desc_entry = ttk.Entry(frame, textvariable=self.desc_var, width=25)
        desc_entry.grid(row=1, column=1, sticky=tk.W, pady=5)

        # Info text
        info_text = "当前分段时长: {:.1f} 秒\n音符数量: {}".format(
            section.duration, section.note_count
        )
        ttk.Label(frame, text=info_text, foreground="#666666").grid(
            row=2, column=0, columnspan=2, pady=10, sticky=tk.W
        )

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="确定", command=self._on_ok).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(
            side=tk.LEFT, padx=5
        )

    def _on_ok(self):
        self.result = {
            "bpm": self.bpm_var.get(),
            "description": self.desc_var.get(),
        }
        self.destroy()
