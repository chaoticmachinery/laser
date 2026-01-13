#!/usr/bin/env python3

# Lightburn Grid Marker
#
# Written by: Keven Murphy
# Version: 3.0
#
# Mark out the interesting squares in your Lightburn material test.
# Supports CSV save/load and direct export to LightBurn .clb files.
# Frequency exported in Hz (×1000)
# Added global fields: Auto-Rotate, Scan Angle, Angle Increment, Bi-directional, Cross-hatch
# Fixed: bidir tag for LightBurn compatibility
# Layout: Two-column global parameters + checkboxes on one row with On/Off labels

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
import csv
import datetime
import xml.etree.ElementTree as ET
from pathlib import Path

# ====================== CONFIGURATION ======================
CONFIG = {
    # Visual settings
    "FONT_FAMILY": "Arial",
    "FONT_SIZE_LABEL": 10,
    "FONT_SIZE_BUTTON": 8,
    "FONT_SIZE_TOOLTIP": 8,
    "FONT_SIZE_TITLE": 10,

    "COLOR_BG_EMPTY": "white",
    "COLOR_BG_NOTE": "#c8f7c5",
    "COLOR_BG_EDITING": "#FF8C00",
    "COLOR_FG_TEXT": "black",

    "COLOR_HEADER_X": "#e8f4ff",
    "COLOR_HEADER_Y": "#f5f9ff",

    "COLOR_TOOLTIP_BG": "#ffffe0",
    "COLOR_TOOLTIP_BORDER": "black",

    # Behavior settings
    "MAX_NOTE_LENGTH": 512,
    "DISPLAY_NOTE_LENGTH": 40,
    "TOOLTIP_WRAP_LENGTH": 400,

    # Default grid counts
    "DEFAULT_X_COUNTS": 20,
    "DEFAULT_Y_COUNTS": 20,

    # Default global values
    "DEFAULT_SPEED": "3000",
    "DEFAULT_POWER": "20",
    "DEFAULT_FREQUENCY": "1000",
    "DEFAULT_LINE_INTERVAL": "0.0250",
    "DEFAULT_PASSES": "10",
    "DEFAULT_QPULSE": "200",

    # Extra global fields (hatch & scan settings)
    "EXTRA_GLOBAL_FIELDS": [
        "AutoRotate",
        "ScanAngle",
        "AngleIncrement",
        "BiDirectional",
        "CrossHatch"
    ],

    "EXTRA_GLOBAL_DEFAULTS": {
        "AutoRotate":     False,
        "ScanAngle":      "0",
        "AngleIncrement": "0",
        "BiDirectional":  False,
        "CrossHatch":     False
    }
}
# ===========================================================

PARAMETERS = [
    "Speed", "Power", "Frequency", "Line Interval", "Passes", "Q-Pulse"
]

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 25
        y = self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify="left",
                         background=CONFIG["COLOR_TOOLTIP_BG"],
                         relief="solid", borderwidth=1,
                         font=(CONFIG["FONT_FAMILY"], CONFIG["FONT_SIZE_TOOLTIP"]),
                         wraplength=CONFIG["TOOLTIP_WRAP_LENGTH"])
        label.pack(ipadx=6, ipady=4)

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

class LaserGridApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Laser Test Grid - Configurable X/Y Axes v3.0")
        self.geometry("1800x1050")

        # Subtle focus highlight for checkboxes
        style = ttk.Style()
        style.configure("TCheckbutton", focuscolor="gray92")

        self.notes = {}
        self.buttons = {}

        self.x_axis_var = tk.StringVar(value="Q-Pulse")
        self.y_axis_var = tk.StringVar(value="Frequency")
        self.qpulse_mode = tk.StringVar(value="Single")

        self.ranges = {}
        for param in PARAMETERS:
            self.ranges[param] = {
                "start": tk.StringVar(value=self._default_start(param)),
                "end": tk.StringVar(value=self._default_end(param)),
            }

        self.x_counts_var = tk.StringVar(value=str(CONFIG["DEFAULT_X_COUNTS"]))
        self.y_counts_var = tk.StringVar(value=str(CONFIG["DEFAULT_Y_COUNTS"]))

        self.current_values_x = []
        self.current_values_y = []
        self.current_x_param = ""
        self.current_y_param = ""
        self.tab_frames = {}

        self.global_entries = {}
        self.global_bools = {}

        self.create_ui()

        self.x_axis_var.trace_add("write", self._update_global_field_states)
        self.y_axis_var.trace_add("write", self._update_global_field_states)

        self.apply_ranges(silent=True)

    def _default_start(self, param):
        defaults = {
            "Speed": "4000", "Power": "90", "Frequency": "3800.0",
            "Line Interval": "0.0010", "Passes": "1", "Q-Pulse": "150"
        }
        return defaults.get(param, "1")

    def _default_end(self, param):
        defaults = {
            "Speed": "1000", "Power": "10", "Frequency": "100.0",
            "Line Interval": "0.020", "Passes": "10", "Q-Pulse": "200"
        }
        return defaults.get(param, "200")

    def _update_global_field_states(self, *args):
        active_axes = {self.x_axis_var.get(), self.y_axis_var.get()}
        for param, entry in self.global_entries.items():
            if param not in ["Title", "Material Name", "ScanAngle", "AngleIncrement"] and param in active_axes:
                entry.configure(state='disabled')
            else:
                entry.configure(state='normal')

    def show_all_notes(self):
        lines = [f"Title: {self.global_entries.get('Title', tk.StringVar(value='')).get() or '[No title]'}"]
        lines.append(f"Material Name: {self.global_entries.get('Material Name', tk.StringVar(value='')).get() or '[None]'}")
        lines.append(f"Auto-Rotate: {'On' if self.global_bools.get('AutoRotate', tk.BooleanVar(value=False)).get() else 'Off'}")
        lines.append(f"Scan Angle: {self.global_entries.get('ScanAngle', tk.StringVar(value='0')).get()} deg")
        lines.append(f"Angle Increment: {self.global_entries.get('AngleIncrement', tk.StringVar(value='0')).get()} deg")
        lines.append(f"Bi-directional: {'On' if self.global_bools.get('BiDirectional', tk.BooleanVar(value=False)).get() else 'Off'}")
        lines.append(f"Cross-hatch: {'On' if self.global_bools.get('CrossHatch', tk.BooleanVar(value=False)).get() else 'Off'}")
        lines.append("Global Parameters:")
        for param, entry in self.global_entries.items():
            if param not in ["Title", "Material Name", "ScanAngle", "AngleIncrement"]:
                lines.append(f"  {param}: {entry.get().strip() or '[empty]'}")
        lines.append("")
        lines.append(f"Grid: {self.current_y_param} (Y) vs {self.current_x_param} (X)")
        lines.append(f"  X counts: {self.x_counts_var.get()} → {len(self.current_values_x)} values")
        lines.append(f"  Y counts: {self.y_counts_var.get()} → {len(self.current_values_y)} values")

        if self.notes:
            lines.append(f"\n{len(self.notes)} Notes:")
            for (tab, r, c), text in sorted(self.notes.items()):
                x_val = self.current_values_x[c]
                y_val = self.current_values_y[r]
                prefix = f"Grid {tab}: " if tab > 0 else ""
                lines.append(f"  {prefix}{self.current_y_param} = {y_val} | {self.current_x_param} = {x_val} → {text}")
        else:
            lines.append("\nNo notes added yet.")

        messagebox.showinfo("Summary", "\n".join(lines))

    def export_to_csv(self):
        if not self.notes:
            messagebox.showinfo("Export", "No notes to export.")
            return

        globals_dict = {k: v.get().strip() for k, v in self.global_entries.items()}

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"laser_test_{globals_dict.get('Title','test').replace(' ', '_')[:30]}.csv"
        )
        if not file_path:
            return

        rows = []
        for (tab, r, c), note_text in sorted(self.notes.items()):
            x_value = self.current_values_x[c]
            y_value = self.current_values_y[r]

            cell_settings = globals_dict.copy()

            if self.current_x_param in cell_settings:
                cell_settings[self.current_x_param] = x_value
            if self.current_y_param in cell_settings:
                cell_settings[self.current_y_param] = y_value

            def fmt(val):
                if isinstance(val, str):
                    try:
                        f = float(val)
                        if f.is_integer():
                            return str(int(f))
                        elif abs(f) < 1:
                            return f"{f:.4f}"
                        else:
                            return f"{f:.1f}"
                    except:
                        return val
                return str(val)

            dynamic_title = (
                f"{note_text} "
                f"(S:{fmt(cell_settings.get('Speed', '?'))} "
                f"P:{fmt(cell_settings.get('Power', '?'))} "
                f"F:{fmt(cell_settings.get('Frequency', '?'))} "
                f"QP:{fmt(cell_settings.get('Q-Pulse', '?'))} "
                f"LI:{fmt(cell_settings.get('Line Interval', '?'))} "
                f"Pass:{fmt(cell_settings.get('Passes', '?'))})"
            ).strip()

            row = {
                "Note": note_text,
                "Tab": tab,
                "X_Param": self.current_x_param,
                "X_Value": x_value,
                "Y_Param": self.current_y_param,
                "Y_Value": y_value,
                "Title": dynamic_title,
                "Speed": cell_settings.get("Speed", ""),
                "Power": cell_settings.get("Power", ""),
                "Frequency": cell_settings.get("Frequency", ""),
                "Line Interval": cell_settings.get("Line Interval", ""),
                "Passes": cell_settings.get("Passes", ""),
                "Q-Pulse": cell_settings.get("Q-Pulse", "")
            }
            rows.append(row)

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                today = datetime.date.today().strftime("%Y-%m-%d")
                f.write("# Laser Test Grid Export - Metadata\n")
                f.write(f"# Date: {today}\n")
                f.write(f"# X_Axis: {self.current_x_param}\n")
                f.write(f"# Y_Axis: {self.current_y_param}\n")
                f.write(f"# Mode: {'Split' if self.qpulse_mode.get() == 'Split' else 'Single'}\n")
                f.write(f"# X_counts: {self.x_counts_var.get()}\n")
                f.write(f"# Y_counts: {self.y_counts_var.get()}\n")
                f.write("\n# Parameter Ranges:\n")
                for param in PARAMETERS:
                    start = self.ranges[param]["start"].get()
                    end = self.ranges[param]["end"].get()
                    f.write(f"#   {param}_start: {start}\n")
                    f.write(f"#   {param}_end: {end}\n")
                f.write("\n# Global Parameters:\n")
                for param, value in globals_dict.items():
                    f.write(f"#   {param}: {value}\n")
                f.write("\n# Global Extra Settings:\n")
                for field in CONFIG["EXTRA_GLOBAL_FIELDS"]:
                    if field in self.global_bools:
                        val = "1" if self.global_bools[field].get() else "0"
                    else:
                        val = self.global_entries.get(field, tk.StringVar(value="0")).get().strip()
                    f.write(f"#   {field}: {val}\n")
                f.write("\n")

                writer = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter='|')
                writer.writeheader()
                writer.writerows(rows)

            messagebox.showinfo("Success", f"Exported {len(rows)} rows + metadata (pipe delimited)")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def load_from_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return

        try:
            metadata = {}
            data_lines = []

            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('#') and ':' in line:
                        key, val = line[1:].split(':', 1)
                        key = key.strip()
                        val = val.strip()
                        metadata[key] = val
                    elif line and not line.startswith('#'):
                        data_lines.append(line)

            if "X_Axis" in metadata:
                self.x_axis_var.set(metadata["X_Axis"])
            if "Y_Axis" in metadata:
                self.y_axis_var.set(metadata["Y_Axis"])
            if "Mode" in metadata:
                self.qpulse_mode.set("Split" if metadata["Mode"] == "Split" else "Single")
            if "X_counts" in metadata:
                self.x_counts_var.set(metadata["X_counts"])
            if "Y_counts" in metadata:
                self.y_counts_var.set(metadata["Y_counts"])

            for param in PARAMETERS:
                start_key = f"{param}_start"
                end_key = f"{param}_end"
                if start_key in metadata:
                    self.ranges[param]["start"].set(metadata[start_key])
                if end_key in metadata:
                    self.ranges[param]["end"].set(metadata[end_key])

            self.apply_ranges(silent=True)

            for key in ["Title", "Material Name"] + PARAMETERS:
                if key in metadata and key in self.global_entries:
                    self.global_entries[key].delete(0, tk.END)
                    self.global_entries[key].insert(0, metadata.get(key, ""))

            for field in CONFIG["EXTRA_GLOBAL_FIELDS"]:
                if field in metadata:
                    val = metadata[field]
                    if field in self.global_bools:
                        self.global_bools[field].set(val == "1")
                    elif field in self.global_entries:
                        self.global_entries[field].delete(0, tk.END)
                        self.global_entries[field].insert(0, val)

            self._update_global_field_states()

            if not data_lines:
                messagebox.showinfo("Load", "No data rows found, but metadata restored.")
                return

            reader = csv.DictReader(data_lines, delimiter='|')
            rows = list(reader)

            loaded = 0
            self.clear_all(silent=True)

            for row in rows:
                try:
                    if row["X_Param"] != self.current_x_param or row["Y_Param"] != self.current_y_param:
                        continue
                    x_val = row["X_Value"]
                    y_val = row["Y_Value"]
                    note = row.get("Note", "").strip()
                    tab = int(row.get("Tab", "0"))

                    c = next((i for i, v in enumerate(self.current_values_x) if str(v) == str(x_val)), None)
                    r = next((i for i, v in enumerate(self.current_values_y) if str(v) == str(y_val)), None)

                    if r is not None and c is not None:
                        key = (tab, r, c)
                        if key in self.buttons:
                            self.notes[key] = note
                            display_text = (note[:CONFIG["DISPLAY_NOTE_LENGTH"]] + "...") if len(note) > CONFIG["DISPLAY_NOTE_LENGTH"] else note
                            self.buttons[key].config(text=display_text,
                                                     bg=CONFIG["COLOR_BG_NOTE"],
                                                     fg=CONFIG["COLOR_FG_TEXT"],
                                                     font=(CONFIG["FONT_FAMILY"], CONFIG["FONT_SIZE_BUTTON"], "bold"))
                            if len(note) > CONFIG["DISPLAY_NOTE_LENGTH"]:
                                ToolTip(self.buttons[key], note)
                            loaded += 1
                except:
                    continue

            messagebox.showinfo("Load Complete", f"Loaded {loaded} notes\nMetadata restored.")

        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def export_to_lightburn_clb(self):
        if not self.notes:
            messagebox.showinfo("Export", "No notes to export.")
            return

        material_name = self.global_entries.get("Material Name", tk.StringVar(value="")).get().strip()
        if not material_name:
            material_name = simpledialog.askstring(
                "Material Name Required",
                "No Material Name set in global fields.\nPlease enter one now:",
                initialvalue="Test Material"
            )
            if not material_name:
                return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".clb",
            filetypes=[("LightBurn Library", "*.clb")],
            initialfile=f"{material_name.replace(' ', '_')}_grid_test.clb",
            title="Save as LightBurn .clb file"
        )
        if not file_path:
            return

        globals_dict = {k: v.get().strip() for k, v in self.global_entries.items()}
        title_global = globals_dict.get("Title", "Untitled Test")

        root = ET.Element("LightBurnLibrary")
        root.set("DisplayName", f"{material_name} - {title_global} {datetime.date.today().strftime('%Y%m%d')}")

        material_elem = ET.SubElement(root, "Material")
        material_elem.set("name", material_name)

        added = 0

        for (tab, r, c), note_text in sorted(self.notes.items()):
            note_text = note_text.strip()
            if not note_text:
                continue

            x_value = self.current_values_x[c]
            y_value = self.current_values_y[r]

            cell_settings = globals_dict.copy()
            if self.current_x_param in cell_settings:
                cell_settings[self.current_x_param] = x_value
            if self.current_y_param in cell_settings:
                cell_settings[self.current_y_param] = y_value

            try:
                speed       = int(float(cell_settings.get("Speed", "1000")))
                power       = int(float(cell_settings.get("Power", "20")))
                freq        = int(float(cell_settings.get("Frequency", "1000")) * 1000)
                qpulse      = int(float(cell_settings.get("Q-Pulse", "200")))
                interval    = float(cell_settings.get("Line Interval", "0.025"))
                passes      = int(float(cell_settings.get("Passes", "1")))
                scan_angle  = int(float(self.global_entries.get("ScanAngle", tk.StringVar(value="0")).get() or 0))
                angle_inc   = int(float(self.global_entries.get("AngleIncrement", tk.StringVar(value="0")).get() or 0))
                auto_rotate = 1 if self.global_bools.get("AutoRotate", tk.BooleanVar(value=False)).get() else 0
                bi_dir      = 1 if self.global_bools.get("BiDirectional", tk.BooleanVar(value=False)).get() else 0
                cross_hatch = 1 if self.global_bools.get("CrossHatch", tk.BooleanVar(value=False)).get() else 0
            except (ValueError, TypeError):
                messagebox.showwarning("Warning", f"Skipping '{note_text[:30]}…' — invalid number(s)")
                continue

            def fmt(val):
                if isinstance(val, str):
                    try:
                        f = float(val)
                        if f.is_integer():
                            return str(int(f))
                        elif abs(f) < 1:
                            return f"{f:.4f}"
                        else:
                            return f"{f:.1f}"
                    except:
                        return val
                return str(val)

            dynamic_desc = (
                f"{note_text} "
                f"(S:{fmt(cell_settings.get('Speed', '?'))} "
                f"P:{fmt(cell_settings.get('Power', '?'))} "
                f"F:{fmt(cell_settings.get('Frequency', '?'))} "
                f"QP:{fmt(cell_settings.get('Q-Pulse', '?'))} "
                f"LI:{fmt(cell_settings.get('Line Interval', '?'))} "
                f"Pass:{fmt(cell_settings.get('Passes', '?'))})"
            ).strip()

            entry = ET.SubElement(material_elem, "Entry")
            entry.set("Thickness", "-1.0000")
            entry.set("Desc", dynamic_desc)
            entry.set("NoThickTitle", title_global)

            cut = ET.SubElement(entry, "CutSetting")
            cut.set("type", "Scan")

            ET.SubElement(cut, "index").set("Value", "0")
            ET.SubElement(cut, "name").set("Value", "")
            ET.SubElement(cut, "LinkPath").set("Value", f"{material_name}/{title_global}/{note_text[:50]}")
            ET.SubElement(cut, "maxPower").set("Value", str(power))
            ET.SubElement(cut, "maxPower2").set("Value", str(power))
            ET.SubElement(cut, "speed").set("Value", str(speed))
            ET.SubElement(cut, "frequency").set("Value", str(freq))
            ET.SubElement(cut, "PPI").set("Value", "0")
            ET.SubElement(cut, "QPulseWidth").set("Value", str(qpulse))
            ET.SubElement(cut, "JumpSpeed").set("Value", "4000")
            ET.SubElement(cut, "numPasses").set("Value", str(passes))

            ET.SubElement(cut, "bidir").set("Value", str(bi_dir))
            ET.SubElement(cut, "crossHatch").set("Value", str(cross_hatch))
            ET.SubElement(cut, "autoRotate").set("Value", str(auto_rotate))

            if scan_angle != 0:
                ET.SubElement(cut, "angle").set("Value", str(scan_angle))
            if angle_inc != 0:
                ET.SubElement(cut, "anglePerPass").set("Value", str(angle_inc))

            ET.SubElement(cut, "perfLen").set("Value", "0.01")
            ET.SubElement(cut, "perfSkip").set("Value", "0.01")
            ET.SubElement(cut, "dotTime").set("Value", "1")
            ET.SubElement(cut, "overscan").set("Value", "0")
            ET.SubElement(cut, "interval").set("Value", f"{interval:.4f}")
            ET.SubElement(cut, "subname").set("Value", "Grid Test")
            ET.SubElement(cut, "priority").set("Value", "0")
            ET.SubElement(cut, "tabCount").set("Value", "1")
            ET.SubElement(cut, "tabCountMax").set("Value", "1")

            added += 1

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)

        try:
            tree.write(file_path, encoding="utf-8", xml_declaration=True)
            messagebox.showinfo("Success", f"Exported {added} entries to\n{Path(file_path).name}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def clear_all(self, silent=False):
        if not silent and not messagebox.askyesno("Clear", "Remove all notes?"):
            return
        for key in list(self.notes):
            if key in self.buttons:
                self.buttons[key].config(text=" ", bg=CONFIG["COLOR_BG_EMPTY"])
        self.notes.clear()

    def create_ui(self):
        self.create_top_controls()

        params_container = ttk.Frame(self)
        params_container.pack(fill='x', padx=12, pady=(5, 10))
        params_container.columnconfigure(0, weight=1)
        params_container.columnconfigure(1, weight=1)

        ranges_frame = ttk.LabelFrame(params_container, text="Parameter Ranges", padding=10)
        ranges_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        self.create_range_inputs(ranges_frame)

        global_frame = ttk.LabelFrame(params_container, text="Global Test Parameters & Counts", padding=10)
        global_frame.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
        self.create_global_params(global_frame)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

    def create_top_controls(self):
        frame = ttk.LabelFrame(self, text="Controls & Axes", padding=10)
        frame.pack(fill='x', padx=10, pady=10)

        axis_frame = ttk.Frame(frame)
        axis_frame.pack(fill='x', pady=5)

        ttk.Label(axis_frame, text="X-Axis (Columns):").pack(side='left', padx=5)
        ttk.Combobox(axis_frame, textvariable=self.x_axis_var, values=PARAMETERS,
                     width=12, state="readonly").pack(side='left', padx=5)

        ttk.Label(axis_frame, text="  Y-Axis (Rows):").pack(side='left', padx=5)
        ttk.Combobox(axis_frame, textvariable=self.y_axis_var, values=PARAMETERS,
                     width=12, state="readonly").pack(side='left', padx=5)

        ttk.Button(axis_frame, text="Apply Axes & Ranges",
                   command=self.apply_ranges).pack(side='left', padx=20)

        ttk.Radiobutton(axis_frame, text="Single Grid",
                        variable=self.qpulse_mode, value="Single").pack(side='left', padx=10)
        ttk.Radiobutton(axis_frame, text="Split X into Two Grids",
                        variable=self.qpulse_mode, value="Split").pack(side='left', padx=5)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=8)

        ttk.Button(btn_frame, text="Show Summary", command=self.show_all_notes).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Export CSV", command=self.export_to_csv).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Load CSV", command=self.load_from_csv).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Export to LightBurn .clb", command=self.export_to_lightburn_clb).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Clear Notes", command=self.clear_all).pack(side='left', padx=5)

    def create_range_inputs(self, parent):
        for param in PARAMETERS:
            row = ttk.Frame(parent)
            row.pack(fill='x', pady=4)
            ttk.Label(row, text=f"{param.ljust(14)}:").pack(side='left', padx=(5,2))
            ttk.Entry(row, textvariable=self.ranges[param]["start"], width=12).pack(side='left', padx=3)
            ttk.Label(row, text="→").pack(side='left', padx=4)
            ttk.Entry(row, textvariable=self.ranges[param]["end"], width=12).pack(side='left', padx=3)

    def create_global_params(self, parent):
        today = datetime.date.today().strftime("%Y-%m-%d")

        defaults = {
            "Title": f"Laser Test - {today}",
            "Material Name": "Test Material",
            "Speed": CONFIG["DEFAULT_SPEED"],
            "Power": CONFIG["DEFAULT_POWER"],
            "Frequency": CONFIG["DEFAULT_FREQUENCY"],
            "Line Interval": CONFIG["DEFAULT_LINE_INTERVAL"],
            "Passes": CONFIG["DEFAULT_PASSES"],
            "Q-Pulse": CONFIG["DEFAULT_QPULSE"],
            **CONFIG["EXTRA_GLOBAL_DEFAULTS"]
        }

        row = 0

        # Title | Material Name
        ttk.Label(parent, text="Title:").grid(row=row, column=0, padx=8, pady=4, sticky='e')
        title_entry = ttk.Entry(parent, width=24)
        title_entry.insert(0, defaults["Title"])
        title_entry.grid(row=row, column=1, padx=5, pady=4, sticky='w')
        self.global_entries["Title"] = title_entry

        ttk.Label(parent, text="Material Name:").grid(row=row, column=3, padx=(30,8), pady=4, sticky='e')
        material_entry = ttk.Entry(parent, width=24)
        material_entry.insert(0, defaults["Material Name"])
        material_entry.grid(row=row, column=4, padx=5, pady=4, sticky='w')
        self.global_entries["Material Name"] = material_entry
        row += 1

        # Speed | Power
        ttk.Label(parent, text="Speed:").grid(row=row, column=0, padx=8, pady=4, sticky='e')
        speed_entry = ttk.Entry(parent, width=24)
        speed_entry.insert(0, defaults["Speed"])
        speed_entry.grid(row=row, column=1, padx=5, pady=4, sticky='w')
        self.global_entries["Speed"] = speed_entry

        ttk.Label(parent, text="Power:").grid(row=row, column=3, padx=(30,8), pady=4, sticky='e')
        power_entry = ttk.Entry(parent, width=24)
        power_entry.insert(0, defaults["Power"])
        power_entry.grid(row=row, column=4, padx=5, pady=4, sticky='w')
        self.global_entries["Power"] = power_entry
        row += 1

        # Frequency | Line Interval
        ttk.Label(parent, text="Frequency:").grid(row=row, column=0, padx=8, pady=4, sticky='e')
        freq_entry = ttk.Entry(parent, width=24)
        freq_entry.insert(0, defaults["Frequency"])
        freq_entry.grid(row=row, column=1, padx=5, pady=4, sticky='w')
        self.global_entries["Frequency"] = freq_entry

        ttk.Label(parent, text="Line Interval:").grid(row=row, column=3, padx=(30,8), pady=4, sticky='e')
        li_entry = ttk.Entry(parent, width=24)
        li_entry.insert(0, defaults["Line Interval"])
        li_entry.grid(row=row, column=4, padx=5, pady=4, sticky='w')
        self.global_entries["Line Interval"] = li_entry
        row += 1

        # Passes | Q-Pulse
        ttk.Label(parent, text="Passes:").grid(row=row, column=0, padx=8, pady=4, sticky='e')
        passes_entry = ttk.Entry(parent, width=24)
        passes_entry.insert(0, defaults["Passes"])
        passes_entry.grid(row=row, column=1, padx=5, pady=4, sticky='w')
        self.global_entries["Passes"] = passes_entry

        ttk.Label(parent, text="Q-Pulse:").grid(row=row, column=3, padx=(30,8), pady=4, sticky='e')
        qpulse_entry = ttk.Entry(parent, width=24)
        qpulse_entry.insert(0, defaults["Q-Pulse"])
        qpulse_entry.grid(row=row, column=4, padx=5, pady=4, sticky='w')
        self.global_entries["Q-Pulse"] = qpulse_entry
        row += 1

        # Scan Angle | Angle Increment
        ttk.Label(parent, text="Scan Angle (deg):").grid(row=row, column=0, padx=8, pady=4, sticky='e')
        scan_angle_entry = ttk.Entry(parent, width=24)
        scan_angle_entry.insert(0, defaults["ScanAngle"])
        scan_angle_entry.grid(row=row, column=1, padx=5, pady=4, sticky='w')
        self.global_entries["ScanAngle"] = scan_angle_entry

        ttk.Label(parent, text="Angle Increment (deg):").grid(row=row, column=3, padx=(30,8), pady=4, sticky='e')
        angle_inc_entry = ttk.Entry(parent, width=24)
        angle_inc_entry.insert(0, defaults["AngleIncrement"])
        angle_inc_entry.grid(row=row, column=4, padx=5, pady=4, sticky='w')
        self.global_entries["AngleIncrement"] = angle_inc_entry
        row += 1

        # Checkboxes on a single row – reduced vertical padding + text closer to box
# Auto-Rotate group: columns 0–2
        ttk.Label(parent, text="Auto-Rotate:").grid(row=row, column=0, padx=(10,4), pady=4, sticky='e')
        auto_var = tk.BooleanVar(value=defaults["AutoRotate"])
        ttk.Checkbutton(parent, variable=auto_var).grid(row=row, column=1, padx=2, pady=4, sticky='w')
        auto_status = ttk.Label(parent, text="On" if auto_var.get() else "Off", width=6,
                                foreground="green" if auto_var.get() else "gray")
        auto_status.grid(row=row, column=2, padx=(2, 30), pady=4, sticky='w')  # 2px left → text very close to box
        def update_auto(*args):
            auto_status.config(text="On" if auto_var.get() else "Off",
                               foreground="green" if auto_var.get() else "gray")
        auto_var.trace_add("write", update_auto)
        self.global_bools["AutoRotate"] = auto_var

        # Bi-directional group: columns 3–5
        ttk.Label(parent, text="Bi-directional:").grid(row=row, column=3, padx=(10,4), pady=4, sticky='e')
        bi_var = tk.BooleanVar(value=defaults["BiDirectional"])
        ttk.Checkbutton(parent, variable=bi_var).grid(row=row, column=4, padx=2, pady=4, sticky='w')
        bi_status = ttk.Label(parent, text="On" if bi_var.get() else "Off", width=6,
                              foreground="green" if bi_var.get() else "gray")
        bi_status.grid(row=row, column=5, padx=(2, 30), pady=4, sticky='w')
        def update_bi(*args):
            bi_status.config(text="On" if bi_var.get() else "Off",
                             foreground="green" if bi_var.get() else "gray")
        bi_var.trace_add("write", update_bi)
        self.global_bools["BiDirectional"] = bi_var

        # Cross-hatch group: columns 6–8
        ttk.Label(parent, text="Cross-hatch:").grid(row=row, column=6, padx=(10,4), pady=4, sticky='e')
        cross_var = tk.BooleanVar(value=defaults["CrossHatch"])
        ttk.Checkbutton(parent, variable=cross_var).grid(row=row, column=7, padx=2, pady=4, sticky='w')
        cross_status = ttk.Label(parent, text="On" if cross_var.get() else "Off", width=6,
                                 foreground="green" if cross_var.get() else "gray")
        cross_status.grid(row=row, column=8, padx=(2, 10), pady=4, sticky='w')
        def update_cross(*args):
            cross_status.config(text="On" if cross_var.get() else "Off",
                                foreground="green" if cross_var.get() else "gray")
        cross_var.trace_add("write", update_cross)
        self.global_bools["CrossHatch"] = cross_var

        row += 1  # move to X/Y counts

        # X counts | Y counts
        ttk.Label(parent, text="X counts:").grid(row=row, column=0, padx=8, pady=(12,4), sticky='e')
        ttk.Entry(parent, textvariable=self.x_counts_var, width=12).grid(row=row, column=1, padx=5, pady=(12,4), sticky='w')

        ttk.Label(parent, text="Y counts:").grid(row=row, column=3, padx=(30,8), pady=(12,4), sticky='e')
        ttk.Entry(parent, textvariable=self.y_counts_var, width=12).grid(row=row, column=4, padx=5, pady=(12,4), sticky='w')

    def apply_ranges(self, silent=False):
        if not silent and not messagebox.askyesno("Confirm", "Apply new axes/ranges? (Clears notes)"):
            return

        try:
            x_param = self.x_axis_var.get()
            y_param = self.y_axis_var.get()

            if x_param == y_param:
                raise ValueError("X and Y axes cannot be the same parameter!")

            x_counts = max(2, int(self.x_counts_var.get()))
            y_counts = max(2, int(self.y_counts_var.get()))

            self.current_values_x = self._generate_values(x_param, x_counts)
            self.current_values_y = self._generate_values(y_param, y_counts)
            self.current_x_param = x_param
            self.current_y_param = y_param

            for tab in self.notebook.tabs():
                self.notebook.forget(tab)
            self.tab_frames.clear()

            if self.qpulse_mode.get() == "Split":
                self._create_split_grids()
            else:
                self._create_single_grid()

            self.clear_all(silent=True)
            self._update_global_field_states()

        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _generate_values(self, param, counts):
        try:
            start = float(self.ranges[param]["start"].get())
            end = float(self.ranges[param]["end"].get())
        except:
            raise ValueError(f"Invalid range for {param}")

        if start == end:
            if param == "Frequency":
                return [f"{start:.1f}"] * counts
            return [str(start)] * counts

        step = (end - start) / (counts - 1)
        values = [start + i * step for i in range(counts)]

        if param in ["Speed", "Power", "Passes", "Q-Pulse"]:
            formatted = [f"{int(round(v))}" for v in values]
        elif param == "Line Interval":
            formatted = [f"{v:.4f}" for v in values]
        elif param == "Frequency":
            formatted = [f"{v:.1f}" for v in values]
        else:
            formatted = [f"{v:.2f}" for v in values]

        return formatted

    def _create_single_grid(self):
        frame = ttk.Frame(self.notebook)
        tab_text = f"{self.current_y_param} (Y) vs {self.current_x_param} (X)"
        self.notebook.add(frame, text=tab_text)
        self._build_grid(frame, 0, self.current_values_y, self.current_values_x)

    def _create_split_grids(self):
        total = len(self.current_values_x)
        if total < 4:
            messagebox.showwarning("Split Grids", "Too few values to split. Using single grid.")
            self._create_single_grid()
            return

        mid = (total + 1) // 2

        grid1_x = self.current_values_x[:mid]
        grid2_x = self.current_values_x[mid:]

        f1 = ttk.Frame(self.notebook)
        self.notebook.add(f1, text=f"Part 1 ({len(grid1_x)} {self.current_x_param})")
        self._build_grid(f1, 1, self.current_values_y, grid1_x)

        f2 = ttk.Frame(self.notebook)
        self.notebook.add(f2, text=f"Part 2 ({len(grid2_x)} {self.current_x_param})")
        self._build_grid(f2, 2, self.current_values_y, grid2_x)

    def _build_grid(self, parent, tab_id, y_values, x_values):
        frame = tk.Frame(parent, padx=10, pady=10)
        frame.pack(expand=True, fill='both')

        tk.Label(frame, text=f"{self.current_y_param} ↓",
                 font=(CONFIG["FONT_FAMILY"], CONFIG["FONT_SIZE_LABEL"], "bold")) \
          .grid(row=0, column=0, padx=8, pady=8, sticky='nsew')

        for col, val in enumerate(x_values, 1):
            tk.Label(frame, text=val, width=10, relief="ridge", bg=CONFIG["COLOR_HEADER_X"],
                     font=(CONFIG["FONT_FAMILY"], CONFIG["FONT_SIZE_LABEL"])) \
              .grid(row=0, column=col, sticky='nsew')

        for row, yval in enumerate(y_values, 1):
            tk.Label(frame, text=yval, width=12, relief="ridge", bg=CONFIG["COLOR_HEADER_Y"],
                     anchor="e", font=(CONFIG["FONT_FAMILY"], CONFIG["FONT_SIZE_LABEL"])) \
              .grid(row=row, column=0, sticky='nsew')

            for col, xval in enumerate(x_values, 1):
                key = (tab_id, row-1, col-1)
                btn = tk.Button(frame, text=" ", width=10, height=1, bg=CONFIG["COLOR_BG_EMPTY"],
                               relief="groove", command=lambda k=key: self.edit_note(k))
                btn.grid(row=row, column=col, padx=1, pady=1, sticky='nsew')
                self.buttons[key] = btn

        for i in range(len(x_values)+1):
            frame.columnconfigure(i, weight=1)
        for i in range(len(y_values)+1):
            frame.rowconfigure(i, weight=1)

    def edit_note(self, key):
        btn = self.buttons.get(key)
        if not btn:
            return

        current = self.notes.get(key, "")

        btn.config(bg=CONFIG["COLOR_BG_EDITING"], fg=CONFIG["COLOR_FG_TEXT"],
                   font=(CONFIG["FONT_FAMILY"], CONFIG["FONT_SIZE_BUTTON"], "bold"))

        new_text = simpledialog.askstring("Note", "Enter note/rating:",
                                         initialvalue=current, parent=self)

        if new_text is None:
            if current:
                btn.config(bg=CONFIG["COLOR_BG_NOTE"], fg=CONFIG["COLOR_FG_TEXT"],
                           font=(CONFIG["FONT_FAMILY"], CONFIG["FONT_SIZE_BUTTON"], "bold"))
            else:
                btn.config(bg=CONFIG["COLOR_BG_EMPTY"], fg=CONFIG["COLOR_FG_TEXT"],
                           font=(CONFIG["FONT_FAMILY"], CONFIG["FONT_SIZE_BUTTON"]))
            return

        new_text = new_text.strip()
        if len(new_text) > CONFIG["MAX_NOTE_LENGTH"]:
            new_text = new_text[:CONFIG["MAX_NOTE_LENGTH"]]

        if new_text:
            self.notes[key] = new_text
            display_text = (new_text[:CONFIG["DISPLAY_NOTE_LENGTH"]] + "...") \
                if len(new_text) > CONFIG["DISPLAY_NOTE_LENGTH"] else new_text
            btn.config(text=display_text, bg=CONFIG["COLOR_BG_NOTE"], fg=CONFIG["COLOR_FG_TEXT"],
                       font=(CONFIG["FONT_FAMILY"], CONFIG["FONT_SIZE_BUTTON"], "bold"))
            if len(new_text) > CONFIG["DISPLAY_NOTE_LENGTH"]:
                ToolTip(btn, new_text)
        else:
            self.notes.pop(key, None)
            btn.config(text=" ", bg=CONFIG["COLOR_BG_EMPTY"], fg=CONFIG["COLOR_FG_TEXT"],
                       font=(CONFIG["FONT_FAMILY"], CONFIG["FONT_SIZE_BUTTON"]))

if __name__ == "__main__":
    app = LaserGridApp()
    app.mainloop()
