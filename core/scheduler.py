import tkinter as tk
from tkinter import Toplevel, Label, Frame, Button, Canvas, Scrollbar, VERTICAL, BooleanVar, Checkbutton
from tkinter.ttk import Combobox
from tkinter import messagebox
from resources.config import DEFAULT_ENTRY, DEFAULT_EXIT, DEFAULT_FLOATING, DEFAULT_LATE_ALLOWED

class WorkScheduleEditor:
    def __init__(self, app):
        self.app = app
        pid = self.app.selected_id.get()
        if not pid:
            messagebox.showinfo("Info", "Select an ID first.")
            return

        filtered_dates = sorted({s[1] for s in self.app.sessions if s[0] == pid})
        if not filtered_dates:
            messagebox.showinfo("Info", "No sessions found for selected ID.")
            return

        self.win = Toplevel()
        self.win.title("Work Schedule Editor")
        self.win.geometry("600x500")

        Label(self.win, text=f"Work schedules for ID: {pid}", font=("Segoe UI", 12, "bold")).pack(pady=10)

        canvas = Canvas(self.win)
        scrollbar = Scrollbar(self.win, orient=VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        content_frame = Frame(canvas)
        canvas.create_window((0, 0), window=content_frame, anchor="nw")
        content_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        self.combos = {}
        times_entry = [f"{h:02d}:{m:02d}" for h in range(7, 11) for m in (0, 30) if not (h == 10 and m > 30)]
        times_exit = [f"{h:02d}:{m:02d}" for h in range(16, 19) for m in (0, 30) if not (h == 18 and m > 30)]
        floating_opts = ["0.5", "1.0", "1.5"]

        for date in filtered_dates:
            frame = Frame(content_frame)
            frame.pack(pady=5, anchor='w')

            Label(frame, text=date, width=12).grid(row=0, column=0, padx=5)

            cb_entry = Combobox(frame, values=times_entry, width=7)
            cb_entry.set(self.app.work_schedules.get(date, {}).get("entry", DEFAULT_ENTRY))
            cb_entry.grid(row=0, column=1, padx=5)

            cb_exit = Combobox(frame, values=times_exit, width=7)
            cb_exit.set(self.app.work_schedules.get(date, {}).get("exit", DEFAULT_EXIT))
            cb_exit.grid(row=0, column=2, padx=5)

            cb_floating = Combobox(frame, values=floating_opts, width=5)
            cb_floating.set(str(self.app.work_schedules.get(date, {}).get("floating", DEFAULT_FLOATING)))
            cb_floating.grid(row=0, column=3, padx=5)

            late_var = BooleanVar(value=self.app.work_schedules.get(date, {}).get("late_allowed", DEFAULT_LATE_ALLOWED))
            chk = Checkbutton(frame, text="10min late OK", variable=late_var)
            chk.grid(row=0, column=4, padx=5)

            self.combos[date] = (cb_entry, cb_exit, cb_floating, late_var)

        Button(content_frame, text="Save All", command=self.save_schedules).pack(pady=10)

    def save_schedules(self):
        for d, (cb_e, cb_x, cb_f, late_v) in self.combos.items():
            self.app.work_schedules[d] = {
                "entry": cb_e.get(),
                "exit": cb_x.get(),
                "floating": float(cb_f.get()),
                "late_allowed": late_v.get()
            }
        messagebox.showinfo("Saved", "Work schedules updated.")
        self.win.destroy()