#!/usr/bin/env python3
"""
MIDI Repair Tool - GUI Application with BPM Visualization

A tkinter-based GUI for repairing and customizing MIDI files:
- Load and analyze MIDI files
- Visualize BPM changes and note density
- Segment-based BPM customization
- Export modified MIDI with segment BPM changes
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sys
import os
import mido
import shutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .core.repair import repair_midi, detect_original_bpm
from .gui.visualization import BPMVisualizationCanvas
from .gui.dialogs import BPMSegmentSettingsDialog
from .gui.export import export_segments_to_midi
from .gui.models import Section


class MidiRepairGUI:
    """Main GUI Application for MIDI Repair Tool"""

    def __init__(self, root):
        self.root = root
        self.root.title("MIDI Repair Tool - BPM分段可视化")
        self.root.geometry("1100x850")
        self.root.resizable(True, True)

        # State variables
        self.input_file = None
        self.output_file = None
        self.midi_data = None
        self.sections: list[Section] = []

        # 分段模式开关（与一键修复互斥）
        self.segment_mode_enabled = tk.BooleanVar(value=False)

        # Configure style
        self.setup_styles()

        # Create GUI
        self.create_widgets()

        # Center window
        self.center_window()

    def setup_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        style.theme_use("clam")

        # Configure button styles
        style.configure("Primary.TButton", font=("Arial", 11, "bold"), padding=10)
        style.configure("Secondary.TButton", font=("Arial", 10), padding=8)
        style.configure("Success.TButton", font=("Arial", 11, "bold"), padding=10)

        # Configure label styles
        style.configure("Title.TLabel", font=("Arial", 16, "bold"))
        style.configure("Subtitle.TLabel", font=("Arial", 12, "bold"))
        style.configure("Normal.TLabel", font=("Arial", 10))
        style.configure("Info.TLabel", font=("Arial", 9), foreground="#666")

    def center_window(self):
        """Center window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def create_widgets(self):
        """Create all GUI widgets"""

        # Main container
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(
            main_frame, text="MIDI Repair Tool - BPM分段可视化", style="Title.TLabel"
        )
        title_label.pack(pady=(0, 20))

        # === SECTION 1: Import MIDI ===
        self.create_import_section(main_frame)

        # === SECTION 2: Visualization Canvas ===
        self.create_visualization_section(main_frame)

        # === SECTION 3: Quick Repair ===
        self.create_quick_repair_section(main_frame)

        # === SECTION 4: Status/Log Area ===
        self.create_status_section(main_frame)

    def create_import_section(self, parent):
        """Create import section"""
        import_frame = ttk.LabelFrame(parent, text="1. 导入MIDI文件", padding="15")
        import_frame.pack(fill=tk.X, pady=(0, 15))

        # File path display
        self.file_path_var = tk.StringVar(value="未选择文件")
        file_path_label = ttk.Label(
            import_frame,
            textvariable=self.file_path_var,
            style="Normal.TLabel",
            wraplength=600,
        )
        file_path_label.pack(side=tk.LEFT, padx=(0, 10))

        # Import button
        import_btn = ttk.Button(
            import_frame,
            text="📂 浏览...",
            style="Secondary.TButton",
            command=self.import_midi,
        )
        import_btn.pack(side=tk.RIGHT)

    def create_visualization_section(self, parent):
        """Create visualization canvas section"""
        viz_frame = ttk.LabelFrame(parent, text="2. BPM可视化与分段", padding="15")
        viz_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Create canvas
        self.canvas = BPMVisualizationCanvas(viz_frame, bg="white", height=400)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Set up callbacks
        self.canvas.on_segments_changed = self._on_segments_changed
        self.canvas.on_edit_segment = self._edit_segment

        # Control buttons below canvas
        control_frame = ttk.Frame(viz_frame)
        control_frame.pack(fill=tk.X, pady=(10, 0))

        # Info label
        self.info_label = ttk.Label(
            control_frame, text="分段: 0 | 点击右键添加/编辑分段", style="Info.TLabel"
        )
        self.info_label.pack(side=tk.LEFT)

        # Undo/Redo buttons
        ttk.Button(
            control_frame,
            text="撤销 (Ctrl+Z)",
            style="Secondary.TButton",
            command=self.canvas.undo,
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            control_frame,
            text="重做 (Ctrl+Y)",
            style="Secondary.TButton",
            command=self.canvas.redo,
        ).pack(side=tk.RIGHT, padx=5)

        # Export segments button
        # Export MIDI button (智能导出)
        self.export_btn = ttk.Button(
            control_frame,
            text="↗ 导出 MIDI",
            style="Success.TButton",
            command=self.smart_export,
            state=tk.DISABLED,
        )
        self.export_btn.pack(side=tk.RIGHT, padx=5)

        # Enable export button if we have segments OR fix result
        export_enabled = bool(self.sections) or (
            self.output_file and os.path.exists(self.output_file)
        )
        self.export_btn.config(state=tk.NORMAL if export_enabled else tk.DISABLED)

    def create_quick_repair_section(self, parent):
        """Create quick repair section"""
        repair_frame = ttk.LabelFrame(parent, text="3. 一键修复", padding="15")
        repair_frame.pack(fill=tk.X, pady=(0, 15))

        # BPM input row
        bpm_frame = ttk.Frame(repair_frame)
        bpm_frame.pack(fill=tk.X)

        ttk.Label(bpm_frame, text="目标BPM:", style="Normal.TLabel").pack(
            side=tk.LEFT, padx=(0, 10)
        )

        self.bpm_var = tk.StringVar(value="120")
        bpm_entry = ttk.Entry(
            bpm_frame, textvariable=self.bpm_var, width=10, font=("Arial", 11)
        )
        bpm_entry.pack(side=tk.LEFT, padx=(0, 10))

        # Fix button
        self.fix_btn = ttk.Button(
            bpm_frame,
            text="⚡ 一键修复",
            style="Success.TButton",
            command=self.fix_midi,
        )
        self.fix_btn.pack(side=tk.LEFT, padx=10)

        # 分段模式开关（与一键修复互斥）
        self.segment_mode_checkbox = ttk.Checkbutton(
            bpm_frame,
            text="启用分段BPM模式",
            variable=self.segment_mode_enabled,
            command=self._on_segment_mode_changed,
        )
        self.segment_mode_checkbox.pack(side=tk.LEFT, padx=(30, 0))

        # 分段模式提示
        self.segment_mode_label = ttk.Label(
            bpm_frame,
            text="(启用后将禁用一键修复)",
            style="Info.TLabel",
        )
        self.segment_mode_label.pack(side=tk.LEFT, padx=(5, 0))

    def create_status_section(self, parent):
        """Create status/log area"""
        status_frame = ttk.LabelFrame(parent, text="状态 / 日志", padding="15")
        status_frame.pack(fill=tk.BOTH, expand=True)

        self.status_text = scrolledtext.ScrolledText(
            status_frame, height=8, wrap=tk.WORD, font=("Courier", 9)
        )
        self.status_text.pack(fill=tk.BOTH, expand=True)

        self.status_text.tag_config("info", foreground="#0066cc")
        self.status_text.tag_config("success", foreground="#00aa00")
        self.status_text.tag_config("error", foreground="#cc0000")
        self.status_text.tag_config("warning", foreground="#cc6600")

        self.log("欢迎使用 MIDI Repair Tool - BPM分段可视化！", "info")
        self.log("请导入MIDI文件开始。", "info")

    def log(self, message, tag="normal"):
        """Add a message to the status log"""
        self.status_text.insert(tk.END, message + "\n", tag)
        self.status_text.see(tk.END)
        self.root.update_idletasks()

    def import_midi(self):
        """Handle MIDI file import"""
        filename = filedialog.askopenfilename(
            title="选择MIDI文件",
            filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")],
        )

        if filename:
            self.input_file = filename
            self.file_path_var.set(os.path.basename(filename))
            self.log(f"\n--- 文件已导入 ---", "info")
            self.log(f"文件: {filename}", "info")

            # Load MIDI for visualization
            try:
                self.midi_data = mido.MidiFile(filename)
                self.canvas.set_midi_data(self.midi_data)
                self.log(f"MIDI文件时长: {self.midi_data.length:.1f}秒", "info")
            except Exception as e:
                self.log(f"加载MIDI错误: {e}", "error")

            # Initialize sections
            if self.midi_data:
                self.sections = [Section(start=0, end=self.midi_data.length, bpm=120)]
                self.canvas.set_sections(self.sections)

            # Enable fix button
            self.fix_btn.config(state=tk.NORMAL)
            self._update_button_states()

    def _update_button_states(self):
        """根据分段模式状态更新按钮可用性"""
        if self.segment_mode_enabled.get():
            # 分段模式：禁用一键修复
            self.fix_btn.config(state=tk.DISABLED)
            self.segment_mode_label.config(text="(一键修复已禁用)")
        else:
            # 非分段模式：启用一键修复
            self.fix_btn.config(state=tk.NORMAL if self.input_file else tk.DISABLED)
            self.segment_mode_label.config(text="(启用后将禁用一键修复)")

    def _on_segment_mode_changed(self):
        """分段模式切换时的处理"""
        if self.segment_mode_enabled.get():
            # 切换到分段模式
            self._update_button_states()
            self.log("\n--- 分段BPM模式已启用 ---", "info")
            self.log("请在可视化区域右键创建分段。", "info")
        else:
            # 切换回普通模式
            self._update_button_states()
            self.log("\n--- 分段BPM模式已禁用 ---", "info")
            self.log("可使用一键修复功能。", "info")

    def _on_segments_changed(self, sections):
        """Handle segments changed event"""
        self.sections = sections

        if sections:
            total_notes = sum(s.note_count for s in sections)
            self.info_label.config(
                text=f"分段: {len(sections)} | 总音符数: {total_notes}"
            )
        else:
            self.info_label.config(text="点击右键添加/编辑分段")

        # Enable export button if we have segments OR fix result
        export_enabled = bool(self.sections) or (
            self.output_file and os.path.exists(self.output_file)
        )
        self.export_btn.config(state=tk.NORMAL if export_enabled else tk.DISABLED)

    def _edit_segment(self, section):
        """Edit segment BPM settings"""
        dialog = BPMSegmentSettingsDialog(self.root, section, min_bpm=40, max_bpm=240)
        self.root.wait_window(dialog)

        if dialog.result:
            # Update section
            section.bpm = dialog.result["bpm"]
            section.description = dialog.result["description"]

            # Redraw
            self.canvas.redraw()
            self._on_segments_changed(self.sections)

            self.log(f"更新分段BPM: {section.bpm}", "info")

    def fix_midi(self):
        """One-click fix MIDI file"""
        if not self.input_file:
            messagebox.showwarning("未选择文件", "请先导入MIDI文件。")
            return

        # Get original BPM
        detected = detect_original_bpm(self.input_file)
        target_bpm = detected if detected else 120

        self.log(f"\n--- 一键修复 ---", "info")
        self.log(f"检测到的原始BPM: {detected}", "info")
        self.log(f"使用目标BPM: {target_bpm}", "info")

        # Generate output filename
        base, ext = os.path.splitext(self.input_file)
        output_file = f"{base}_fixed{ext}"

        try:
            success, message, details = repair_midi(
                input_file=self.input_file,
                output_file=output_file,
                target_bpm=target_bpm,
                verbose=True,
            )

            if success:
                self.output_file = output_file
                self.log(f"\n✓ {message}", "success")
                self.log(f"输出: {output_file}", "success")

                # Enable export button (handled by _on_segments_changed)
                self._on_segments_changed(self.sections)
                messagebox.showinfo(
                    "修复成功",
                    f"MIDI文件已修复！\n\n输出: {output_file}",
                )
            else:
                self.log(f"✗ {message}", "error")
                messagebox.showerror("修复失败", message)

        except Exception as e:
            self.log(f"✗ 错误: {e}", "error")
            messagebox.showerror("错误", f"修复MIDI文件失败:\n{e}")

    def smart_export(self):
        """智能导出MIDI文件：根据用户操作自动选择导出内容。"""
        # Case 1: 有分段 - 导出分段BPM
        if self.sections:
            if not self.input_file:
                messagebox.showwarning("无法导出", "请先导入MIDI文件。")
                return
            # Ask for save location
            filename = filedialog.asksaveasfilename(
                title="保存分段BPM MIDI",
                defaultextension=".mid",
                filetypes=[("MIDI files", "*.mid"), ("All files", "*.*")],
                initialfile=os.path.basename(self.input_file).replace(
                    ".mid", "_segments.mid"
                ),
            )
            if not filename:
                return
            self.log(f"\n--- 导出分段BPM ---", "info")
            try:
                success, message = export_segments_to_midi(
                    input_file=self.input_file,
                    output_file=filename,
                    sections=self.sections,
                    verbose=True,
                )
                if success:
                    self.log(f"\n{message}", "success")
                    self.log(f"输出: {filename}", "success")
                    messagebox.showinfo(
                        "导出成功",
                        f"分段BPM MIDI已保存到:\n{filename}",
                    )
                else:
                    self.log(f"\n{message}", "error")
                    messagebox.showerror("导出失败", message)
            except Exception as e:
                self.log(f"\n错误: {e}", "error")
                messagebox.showerror("错误", f"导出文件失败:\n{e}")

        # Case 2: 没有分段但有修复结果 - 导出固定BPM
        elif self.output_file and os.path.exists(self.output_file):
            if not self.output_file or not os.path.exists(self.output_file):
                messagebox.showwarning("无文件", "没有可导出的修复后MIDI文件。")
                return
            # Ask for save location
            filename = filedialog.asksaveasfilename(
                title="保存修复后的MIDI",
                defaultextension=".mid",
                filetypes=[("MIDI files", "*.mid"), ("All files", "*.*")],
                initialfile=os.path.basename(self.output_file),
            )
            if not filename:
                return
            try:
                shutil.copy2(self.output_file, filename)
                self.log(f"\n已导出: {filename}", "success")
                messagebox.showinfo(
                    "已导出",
                    f"修复后的MIDI已保存到:\n{filename}",
                )
            except Exception as e:
                self.log(f"\n错误: {e}", "error")
                messagebox.showerror("错误", f"导出失败:\n{e}")

        # Case 3: 没有可导出的内容
        else:
            messagebox.showwarning("无法导出", "请先创建分段或使用一键修复功能。")


def main():
    """Main entry point"""
    root = tk.Tk()
    app = MidiRepairGUI(root)

    # Bind keyboard shortcuts
    root.bind("<Control-z>", lambda e: app.canvas.undo())
    root.bind("<Control-y>", lambda e: app.canvas.redo())

    root.mainloop()


if __name__ == "__main__":
    main()
