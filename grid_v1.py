#!/usr/bin/env python

#Lightburn Grid Marker
#
#Written by: Keven Murphy
#Version: 1.0
#
#Purpose
#This is a Python desktop tool (built with Tkinter) designed to help users of MOPA fiber lasers (or similar galvo lasers) systematically test and document optimal engraving parameters, especially for materials like stainless steel where frequency (kHz) and Q-pulse width (ns) dramatically affect color, depth, contrast, and finish.
#Main Features
#
#Interactive Parameter Grid
#Two tabs (grids) showing combinations of:
#Frequency (kHz) – vertical axis (highest at top, lowest at bottom)
#Q-pulse width (ns) – horizontal axis
#
#Grid 1: pulses (default 1–200 ns)
#Grid 2: pulses (default 200–500 ns)
#You can freely change the start/end values for frequency and each Q-pulse range → grids regenerate instantly when you click "Apply Ranges"
#
#Cell Annotation
#Click any cell → popup asks for a short note/rating (e.g. "gold", "deep", "8/10", "skip")
#Annotated cells turn light green and display the text
#Notes are the main way to mark "good" or promising settings
#
#Global Test Parameters
#Editable fields for:
#Title / Test Name
#Speed (mm/s)
#Max Power (%)
#Line interval (mm)
#Number of passes

#New scan settings:
#Mode (dropdown: Fill, Line, Cross, Hatch, etc.)
#Angle increment (°)
#Auto-rotate (°)
#Bi-directional (checkbox)
#Cross-hatch (checkbox)

#Export to CSV
#Saves all annotated cells as rows
#Each row contains:
#Desc.: note + all key parameters including Q-pulse (e.g. "gold (Spd: 3000 - Pwr: 20 - LI: 0.0020 - Qp: 15)")
#Sub-layer name (the note itself)
#Freq.
#Max power
#Q-pulse
#LI
#
#All global parameters + scan settings + ranges are saved as # comment lines at the top of the file (metadata)
#
#Import / Load from CSV
#Restores:
#All range start/end values (grids regenerate automatically)
#Title
#Speed, Power, LI, Passes
#Mode, Angle increment, Auto-rotate, Bi-directional, Cross-hatch
#All previously annotated cells (notes reappear on the correct grid positions)
#
#Uses tolerant matching (rounds frequency to 1 decimal) so small floating-point differences don't break loading
#
#Summary View
#Quick popup showing current title, all parameters, scan settings, current ranges, and list of all notes with their freq/Q-pulse coordinates
#
#
#Overall Workflow
#
#Set desired frequency and Q-pulse ranges → Apply
#Engrave your test plate using the grid parameters
#Visually inspect the real plate → click corresponding cells in the app → add notes ("best color", "too deep", "skip", etc.)
#Export CSV → keeps a perfect digital record of what worked
#Later reload the same CSV → everything (ranges, settings, notes) comes back exactly as you left it
#

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
import csv
import os

class LaserGridApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Laser Test Grid - Range Selector & CSV")
        self.geometry("1500x1200")

        self.notes = {}
        self.buttons = {}
        self.current_freq_labels = []
        self.current_qpulse1 = []
        self.current_qpulse2 = []

        # Range variables
        self.freq_start_var = tk.StringVar(value="3800.0")
        self.freq_end_var   = tk.StringVar(value="100.0")
        self.q1_start_var   = tk.StringVar(value="1")
        self.q1_end_var     = tk.StringVar(value="200")
        self.q2_start_var   = tk.StringVar(value="201")
        self.q2_end_var     = tk.StringVar(value="500")

        # New scan settings
        self.mode_var = tk.StringVar(value="Fill")
        self.angle_inc_var = tk.StringVar(value="0")
        self.auto_rotate_var = tk.StringVar(value="0")
        self.bi_dir_var = tk.BooleanVar(value=False)
        self.cross_hatch_var = tk.BooleanVar(value=False)

        self.create_notebook_and_grids()
        self.create_controls_and_params()
        self.create_range_inputs()

        self.apply_ranges(silent=True)

    def create_notebook_and_grids(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        self.tab1_frame = None
        self.tab2_frame = None

    def create_controls_and_params(self):
        frame = ttk.LabelFrame(self, text="Controls & Global Parameters", padding=10)
        frame.pack(fill='x', padx=10, pady=(0, 5))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(0, 10))

        ttk.Button(btn_frame, text="Show Summary", command=self.show_all_notes).pack(side='left', padx=6)
        ttk.Button(btn_frame, text="Export CSV", command=self.export_to_csv).pack(side='left', padx=6)
        ttk.Button(btn_frame, text="Load CSV", command=self.load_from_csv).pack(side='left', padx=6)
        ttk.Button(btn_frame, text="Clear Notes", command=self.clear_all).pack(side='left', padx=6)

        params_frame = ttk.Frame(frame)
        params_frame.pack(fill='x', pady=5)

        # Title
        ttk.Label(params_frame, text="Title:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.title_entry = ttk.Entry(params_frame, width=50)
        self.title_entry.insert(0, "Laser Test - 2025-12-28")
        self.title_entry.grid(row=0, column=1, padx=5, pady=5, columnspan=5, sticky="ew")

        # Basic params
        defaults = [
            ("Speed (mm/s)", "3000"),
            ("Max Power (%)", "20"),
            ("Line interval (mm)", "0.0020"),
            ("Number of passes", "10")
        ]
        self.param_entries = {}
        for i, (label, default) in enumerate(defaults):
            row = 1 + i // 2
            col = (i % 2) * 3
            ttk.Label(params_frame, text=label + ":").grid(row=row, column=col, padx=5, pady=3, sticky="e")
            entry = ttk.Entry(params_frame, width=12)
            entry.insert(0, default)
            entry.grid(row=row, column=col + 1, padx=5, pady=3)
            self.param_entries[label] = entry

        # New scan settings
        ttk.Label(params_frame, text="Mode:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        ttk.Combobox(params_frame, textvariable=self.mode_var,
                     values=["Fill", "Line", "Cross", "Hatch", "Contour", "Engrave", "Other"],
                     width=15).grid(row=3, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(params_frame, text="Angle increment (°):").grid(row=3, column=2, padx=5, pady=5, sticky="e")
        ttk.Entry(params_frame, textvariable=self.angle_inc_var, width=8).grid(row=3, column=3, padx=5, pady=5)

        ttk.Label(params_frame, text="Auto-rotate (°):").grid(row=4, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(params_frame, textvariable=self.auto_rotate_var, width=8).grid(row=4, column=1, padx=5, pady=5)

        ttk.Checkbutton(params_frame, text="Bi-directional", variable=self.bi_dir_var).grid(row=4, column=2, columnspan=2, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(params_frame, text="Cross-hatch", variable=self.cross_hatch_var).grid(row=4, column=4, columnspan=2, padx=5, pady=5, sticky="w")

    def create_range_inputs(self):
        frame = ttk.LabelFrame(self, text="Define Ranges", padding=10)
        frame.pack(fill='x', padx=10, pady=10)

        row = ttk.Frame(frame)
        row.pack(fill='x', pady=5)
        ttk.Label(row, text="Frequency (kHz) Start:").pack(side='left', padx=5)
        ttk.Entry(row, textvariable=self.freq_start_var, width=12).pack(side='left', padx=5)
        ttk.Label(row, text="End:").pack(side='left', padx=5)
        ttk.Entry(row, textvariable=self.freq_end_var, width=12).pack(side='left', padx=5)

        row = ttk.Frame(frame)
        row.pack(fill='x', pady=5)
        ttk.Label(row, text="Q-Pulse Grid 1 (ns) Start:").pack(side='left', padx=5)
        ttk.Entry(row, textvariable=self.q1_start_var, width=12).pack(side='left', padx=5)
        ttk.Label(row, text="End:").pack(side='left', padx=5)
        ttk.Entry(row, textvariable=self.q1_end_var, width=12).pack(side='left', padx=5)

        row = ttk.Frame(frame)
        row.pack(fill='x', pady=5)
        ttk.Label(row, text="Q-Pulse Grid 2 (ns) Start:").pack(side='left', padx=5)
        ttk.Entry(row, textvariable=self.q2_start_var, width=12).pack(side='left', padx=5)
        ttk.Label(row, text="End:").pack(side='left', padx=5)
        ttk.Entry(row, textvariable=self.q2_end_var, width=12).pack(side='left', padx=5)

        ttk.Button(frame, text="Apply Ranges (clears notes)", command=self.apply_ranges).pack(pady=10)

    def apply_ranges(self, silent=False):
        if not silent and not messagebox.askyesno("Confirm", "Apply new ranges? This will clear all current notes."):
            return

        try:
            f_start = float(self.freq_start_var.get())
            f_end   = float(self.freq_end_var.get())
            q1_start = int(self.q1_start_var.get())
            q1_end   = int(self.q1_end_var.get())
            q2_start = int(self.q2_start_var.get())
            q2_end   = int(self.q2_end_var.get())

            num_steps = 20
            f_step = (f_start - f_end) / (num_steps - 1) if num_steps > 1 else 0
            self.current_freq_labels = [f"{f_start - i * f_step:.1f}" for i in range(num_steps)]

            q1_step = max(1, (q1_end - q1_start) // (num_steps - 1)) if num_steps > 1 else 1
            q2_step = max(1, (q2_end - q2_start) // (num_steps - 1)) if num_steps > 1 else 1

            self.current_qpulse1 = list(range(q1_start, q1_end + 1, q1_step))
            self.current_qpulse2 = list(range(q2_start, q2_end + 1, q2_step))

        except Exception as e:
            messagebox.showerror("Invalid Range", f"Error: {str(e)}\nUsing defaults.")
            self.current_freq_labels = [f"{3800.0 - i*190:.1f}" for i in range(20)]
            self.current_qpulse1 = list(range(1,21))
            self.current_qpulse2 = list(range(21,41))
            return

        if self.tab1_frame: self.tab1_frame.destroy()
        if self.tab2_frame: self.tab2_frame.destroy()

        self.tab1_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tab1_frame, text=f'Grid 1: {q1_start}–{q1_end} ns')
        self.create_grid(self.tab1_frame, 1, self.current_freq_labels, self.current_qpulse1)

        self.tab2_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tab2_frame, text=f'Grid 2: {q2_start}–{q2_end} ns')
        self.create_grid(self.tab2_frame, 2, self.current_freq_labels, self.current_qpulse2)

        self.clear_all(silent=True)
        if not silent:
            messagebox.showinfo("Success", "Ranges applied.")

    def create_grid(self, parent, tab_id, freq_labels, qpulse):
        frame = tk.Frame(parent, padx=10, pady=10)
        frame.pack(expand=True, fill='both')

        tk.Label(frame, text="Freq ↓\nQ-Pulse →", font=("Arial", 10, "bold")).grid(row=0, column=0, padx=5, pady=5)

        for col, val in enumerate(qpulse, 1):
            tk.Label(frame, text=str(val), width=6, relief="ridge", bg="#e0e0e0").grid(row=0, column=col)

        for row, freq in enumerate(freq_labels, 1):
            tk.Label(frame, text=freq, width=10, anchor="e", relief="ridge", bg="#f0f0f0").grid(row=row, column=0)

            for col, qval in enumerate(qpulse, 1):
                key = (tab_id, row-1, col-1)
                btn = tk.Button(frame, text=" ", width=8, height=1, bg="white", relief="groove", bd=1,
                                font=("Arial", 8), command=lambda k=key: self.edit_note(k))
                btn.grid(row=row, column=col, padx=1, pady=1)
                self.buttons[key] = btn

        for i in range(len(qpulse) + 1):
            frame.columnconfigure(i, weight=1)
        for i in range(len(freq_labels) + 1):
            frame.rowconfigure(i, weight=1)

    def edit_note(self, key):
        current = self.notes.get(key, "")
        new_text = simpledialog.askstring("Note", "Enter note/rating:", initialvalue=current, parent=self)
        if new_text is None:
            return
        new_text = new_text.strip()[:12]
        if new_text:
            self.notes[key] = new_text
            self.buttons[key].config(text=new_text, bg="#90EE90", fg="black", font=("Arial", 8, "bold"))
        else:
            self.notes.pop(key, None)
            self.buttons[key].config(text=" ", bg="white", fg="black", font=("Arial", 8))

    def get_params_dict(self):
        return {
            "title": self.title_entry.get().strip(),
            "speed": self.param_entries["Speed (mm/s)"].get().strip(),
            "power": self.param_entries["Max Power (%)"].get().strip(),
            "li": self.param_entries["Line interval (mm)"].get().strip(),
            "passes": self.param_entries["Number of passes"].get().strip(),
        }

    def export_to_csv(self):
        if not self.notes:
            messagebox.showinfo("Export", "No selections to export.")
            return

        params = self.get_params_dict()
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"laser_{params['title'].replace(' ', '_')[:30]}.csv"
        )
        if not file_path:
            return

        rows = []
        for (tab, r, c), text in sorted(self.notes.items()):
            freq = self.current_freq_labels[r]
            ns = self.current_qpulse1[c] if tab == 1 else self.current_qpulse2[c]

            # Updated Desc. now includes Q-pulse (Qp)
            desc = f"{text} (Spd: {params['speed']} - Pwr: {params['power']} - LI: {params['li']} - Qp: {ns})"

            rows.append({
                "Desc.": desc,
                "Sub-layer name": text,
                "Freq.": freq,
                "Max power": params["power"],
                "Q-pulse": str(ns),
                "LI": params["li"]
            })

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                # Metadata at top (unchanged)
                f.write(f"# Title: {params['title']}\n")
                f.write(f"# Freq Start: {self.freq_start_var.get()}\n")
                f.write(f"# Freq End: {self.freq_end_var.get()}\n")
                f.write(f"# Q1 Start: {self.q1_start_var.get()}\n")
                f.write(f"# Q1 End: {self.q1_end_var.get()}\n")
                f.write(f"# Q2 Start: {self.q2_start_var.get()}\n")
                f.write(f"# Q2 End: {self.q2_end_var.get()}\n")
                f.write(f"# Mode: {self.mode_var.get()}\n")
                f.write(f"# Angle Increment: {self.angle_inc_var.get()}\n")
                f.write(f"# Auto Rotate: {self.auto_rotate_var.get()}\n")
                f.write(f"# Bi-directional: {'Yes' if self.bi_dir_var.get() else 'No'}\n")
                f.write(f"# Cross-hatch: {'Yes' if self.cross_hatch_var.get() else 'No'}\n")
                f.write("\n")

                writer = csv.DictWriter(f, fieldnames=[
                    "Desc.", "Sub-layer name", "Freq.", "Max power", "Q-pulse", "LI"
                ])
                writer.writeheader()
                writer.writerows(rows)

            messagebox.showinfo("Success", f"Exported {len(rows)} rows to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save:\n{str(e)}")

    def load_from_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Parse metadata
            metadata = {}
            for line in lines:
                if line.startswith("#") and ":" in line:
                    key, val = line[1:].strip().split(":", 1)
                    metadata[key.strip()] = val.strip()

            # Restore ranges
            for key, var in [
                ("Freq Start", self.freq_start_var),
                ("Freq End", self.freq_end_var),
                ("Q1 Start", self.q1_start_var),
                ("Q1 End", self.q1_end_var),
                ("Q2 Start", self.q2_start_var),
                ("Q2 End", self.q2_end_var)
            ]:
                if key in metadata:
                    var.set(metadata[key])

            # Restore new scan settings
            if "Mode" in metadata:
                self.mode_var.set(metadata["Mode"])
            if "Angle Increment" in metadata:
                self.angle_inc_var.set(metadata["Angle Increment"])
            if "Auto Rotate" in metadata:
                self.auto_rotate_var.set(metadata["Auto Rotate"])
            if "Bi-directional" in metadata:
                self.bi_dir_var.set(metadata["Bi-directional"] == "Yes")
            if "Cross-hatch" in metadata:
                self.cross_hatch_var.set(metadata["Cross-hatch"] == "Yes")

            self.apply_ranges(silent=True)

            # Parse data
            data_lines = [line for line in lines if not line.startswith("#") and line.strip()]
            reader = csv.DictReader(data_lines)
            loaded_rows = list(reader)

            if not loaded_rows:
                messagebox.showinfo("Load", "No data rows found.")
                return

            self.clear_all(silent=True)

            # Restore basic params from Desc.
            if loaded_rows:
                first = loaded_rows[0]
                if "Desc." in first and " (Spd: " in first["Desc."]:
                    try:
                        parts = first["Desc."].split(" (Spd: ")[1].split(" - ")
                        self.param_entries["Speed (mm/s)"].delete(0, tk.END)
                        self.param_entries["Speed (mm/s)"].insert(0, parts[0])
                        self.param_entries["Max Power (%)"].delete(0, tk.END)
                        self.param_entries["Max Power (%)"].insert(0, parts[1].split(": ")[1])
                        self.param_entries["Line interval (mm)"].delete(0, tk.END)
                        self.param_entries["Line interval (mm)"].insert(0, parts[2].split(": ")[1].rstrip(")"))
                    except:
                        pass

            # Restore selections
            loaded_count = 0
            for row in loaded_rows:
                text = row.get("Sub-layer name", "").strip()
                if not text:
                    continue

                freq_str = row.get("Freq.", "").strip()
                q_str = row.get("Q-pulse", "").strip()

                try:
                    saved_freq = round(float(freq_str), 1)
                    r = next((i for i, f in enumerate(self.current_freq_labels) if round(float(f), 1) == saved_freq), None)
                    if r is None:
                        continue
                except:
                    continue

                try:
                    ns = round(float(q_str))
                    if ns in self.current_qpulse1:
                        tab = 1
                        c = self.current_qpulse1.index(ns)
                    elif ns in self.current_qpulse2:
                        tab = 2
                        c = self.current_qpulse2.index(ns)
                    else:
                        continue
                except:
                    continue

                key = (tab, r, c)
                if key in self.buttons:
                    self.notes[key] = text
                    self.buttons[key].config(text=text, bg="#90EE90", fg="black", font=("Arial", 8, "bold"))
                    loaded_count += 1

            msg = f"Loaded {loaded_count} selections.\nRanges + scan settings restored."
            if "Title" in metadata:
                self.title_entry.delete(0, tk.END)
                self.title_entry.insert(0, metadata["Title"])
                msg += f"\nTitle restored: {metadata['Title']}"

            messagebox.showinfo("Load Complete", msg)

        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load:\n{str(e)}")

    def show_all_notes(self):
        lines = []
        params = {
            "title": self.title_entry.get().strip(),
            "speed": self.param_entries["Speed (mm/s)"].get().strip(),
            "power": self.param_entries["Max Power (%)"].get().strip(),
            "li": self.param_entries["Line interval (mm)"].get().strip(),
            "passes": self.param_entries["Number of passes"].get().strip(),
        }

        lines.append(f"Title: {params['title'] or '[empty]'}")
        lines.append("Parameters:")
        for k, v in params.items():
            if k != "title":
                lines.append(f"  {k}: {v or '[empty]'}")

        lines.append("\nScan Settings:")
        lines.append(f"  Mode: {self.mode_var.get()}")
        lines.append(f"  Angle increment: {self.angle_inc_var.get()}°")
        lines.append(f"  Auto-rotate: {self.auto_rotate_var.get()}°")
        lines.append(f"  Bi-directional: {'Yes' if self.bi_dir_var.get() else 'No'}")
        lines.append(f"  Cross-hatch: {'Yes' if self.cross_hatch_var.get() else 'No'}")

        lines.append(f"\nRanges:")
        lines.append(f"  Freq: {self.freq_start_var.get()} → {self.freq_end_var.get()}")
        lines.append(f"  Q1: {self.q1_start_var.get()} → {self.q1_end_var.get()}")
        lines.append(f"  Q2: {self.q2_start_var.get()} → {self.q2_end_var.get()}")

        if self.notes:
            lines.append("\nNotes:")
            for (tab, r, c), text in sorted(self.notes.items()):
                freq = self.current_freq_labels[r]
                ns = self.current_qpulse1[c] if tab == 1 else self.current_qpulse2[c]
                lines.append(f"  Grid {tab} | {freq} kHz | {ns} ns → {text}")
        else:
            lines.append("\nNo notes added yet.")

        messagebox.showinfo("Summary", "\n".join(lines))

    def clear_all(self, silent=False):
        if silent or messagebox.askyesno("Clear", "Remove all notes?"):
            for key in list(self.notes.keys()):
                if key in self.buttons:
                    self.buttons[key].config(text=" ", bg="white", fg="black", font=("Arial", 8))
            self.notes.clear()

if __name__ == "__main__":
    app = LaserGridApp()
    app.mainloop()
