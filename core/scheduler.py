import sqlite3
from tkinter import Toplevel, Label, Frame, Button, Canvas, Scrollbar, VERTICAL, BooleanVar, Checkbutton, messagebox
from tkinter.ttk import Combobox
from resources.config import DEFAULT_ENTRY, DEFAULT_EXIT, DEFAULT_FLOATING, DEFAULT_LATE_ALLOWED
from datetime import datetime, timedelta

class WorkScheduleEditor:
    def __init__(self, app):
        self.app = app
        pid = self.app.selected_id.get()
        if not pid:
            messagebox.showinfo("Info", "Select an ID first.")
            return

        # --- Get all work schedules from DB (already has defaults) ---
        try:
            with sqlite3.connect(self.app.processor.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT date, entry, exit, floating, late_allowed FROM work_schedules")
                schedules = {row[0]: {
                    "entry": row[1],
                    "exit": row[2],
                    "floating": row[3],
                    "late_allowed": bool(row[4])
                } for row in cursor.fetchall()}
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load schedules:\n{e}")
            return

        filtered_dates = sorted({s[1] for s in self.app.sessions if s[0] == pid})
        if not filtered_dates:
            messagebox.showinfo("Info", "No sessions found for selected ID.")
            return

        # --- Load all work schedules from database ---
        try:
            with sqlite3.connect(self.app.processor.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT date, entry, exit, floating, late_allowed FROM work_schedules")
                schedules = {
                    row[0]: {
                        "entry": row[1],
                        "exit": row[2],
                        "floating": row[3],
                        "late_allowed": bool(row[4]),
                    }
                    for row in cursor.fetchall()
                }

                # --- Load per-ID exceptions from the 'exceptions' table ---
                cursor.execute("SELECT id, entry, exit FROM exceptions")
                rows = cursor.fetchall()
                exceptions = {str(r[0]): {"entry": r[1], "exit": r[2]} for r in rows}

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load schedules or exceptions:\n{e}")
            return

        # --- Apply exception if exists for this pid ---
        if pid in exceptions:
            for d in schedules.keys():
                schedules[d]["entry"] = exceptions[pid]["entry"]
                schedules[d]["exit"] = exceptions[pid]["exit"]
        # --- Build window ---
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
        times_entry = [f"{h:02d}:{m:02d}" for h in range(7, 11) for m in (0, 30)]
        times_exit = [f"{h:02d}:{m:02d}" for h in range(13, 18) for m in (0, 30)]
        floating_opts = ["0.0", "0.5", "1.0"]

        for date in filtered_dates:
            frame = Frame(content_frame)
            frame.pack(pady=5, anchor='w')

            Label(frame, text=date, width=12).grid(row=0, column=0, padx=5)

            cb_entry = Combobox(frame, values=times_entry, width=7)
            cb_entry.set(schedules[date]["entry"])
            cb_entry.grid(row=0, column=1, padx=5)

            cb_exit = Combobox(frame, values=times_exit, width=7)
            cb_exit.set(schedules[date]["exit"])
            cb_exit.grid(row=0, column=2, padx=5)

            cb_floating = Combobox(frame, values=floating_opts, width=5)
            cb_floating.set(str(schedules[date]["floating"]))
            cb_floating.grid(row=0, column=3, padx=5)

            late_var = BooleanVar(value=schedules[date]["late_allowed"])
            chk = Checkbutton(frame, text="10 min late OK", variable=late_var)
            chk.grid(row=0, column=4, padx=5)

            self.combos[date] = (cb_entry, cb_exit, cb_floating, late_var)

        Button(content_frame, text="Save All", command=self.save_schedules).pack(pady=10)

    def save_schedules(self):
        """Save edited work schedules to memory and database."""
        # 1️⃣ Update in-memory dictionary
        for d, (cb_e, cb_x, cb_f, late_v) in self.combos.items():
            self.app.work_schedules[d] = {
                "entry": cb_e.get(),
                "exit": cb_x.get(),
                "floating": float(cb_f.get()),
                "late_allowed": late_v.get()
            }

        # 2️⃣ Save all schedules to the database
        try:
            with sqlite3.connect(self.app.processor.db_path) as conn:
                cursor = conn.cursor()

                for d, schedule in self.app.work_schedules.items():
                    cursor.execute("""
                        UPDATE work_schedules
                        SET entry = ?, 
                            exit = ?, 
                            floating = ?, 
                            late_allowed = ?
                        WHERE date = ?
                    """, (
                        schedule["entry"],
                        schedule["exit"],
                        schedule["floating"],
                        int(schedule["late_allowed"]),
                        d
                    ))
                conn.commit()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to save schedules:\n{e}")
            return

        # 3️⃣ Confirm success to user
        messagebox.showinfo("Saved", "✅ Work schedules updated successfully.")
        self.win.destroy()
class HolidaySelector:
    def __init__(self, app):
        self.app = app
        self.holidays = {}

        self.win = Toplevel()
        self.win.title("Select Holidays")
        self.win.geometry("400x500")

        # --- Get month and year from database (first record just as example) ---
        with sqlite3.connect(self.app.processor.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT date FROM sessions LIMIT 1")
            row = cursor.fetchone()
            if row:
                date = row[0]  # yyyymmdd               
                month = int(date[4:6])                
            else:
                month = 1                  

        if 7 <= month <= 12:
            days_in_month = 30
        else:  # months 1–6
            days_in_month = 31

        Label(self.win, text=f"Select holidays (1–{days_in_month}):",
            font=("Segoe UI", 12, "bold")).pack(pady=10)

        # --- Frame for main scrollable area ---
        main_frame = Frame(self.win)
        main_frame.pack(fill="both", expand=True)

        canvas = Canvas(main_frame)
        scrollbar = Scrollbar(main_frame, orient=VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        content_frame = Frame(canvas)
        canvas.create_window((0, 0), window=content_frame, anchor="nw")
        content_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # --- Correct number of checkboxes based on month ---
        for day in range(1, days_in_month + 1):
            var = BooleanVar(value=False)  # default: not holiday
            chk = Checkbutton(content_frame, text=f"Day {day}", variable=var)
            chk.pack(anchor="w", padx=10)
            self.holidays[day] = var

        # --- Bottom frame for Save button ---
        bottom_frame = Frame(self.win)
        bottom_frame.pack(side="bottom", fill="x", pady=10)

        Button(bottom_frame, text="Save & Edit Work Schedule",
               command=self.save_and_open_schedules).pack()

    def save_and_open_schedules(self):
        # Collect holidays
        self.app.holidays = [day for day, var in self.holidays.items() if var.get()]

        # Close holiday selector window
        self.win.destroy()

        # Open WorkScheduleEditor
        WorkScheduleEditor(self.app)