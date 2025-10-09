import sqlite3
from datetime import datetime, timedelta
from tkinter import (
    Toplevel, Label, Frame, Button, Canvas, Scrollbar, VERTICAL,
    BooleanVar, Checkbutton, messagebox
)
from tkinter.ttk import Combobox
from resources.config import DEFAULT_ENTRY, DEFAULT_EXIT, DEFAULT_FLOATING, DEFAULT_LATE_ALLOWED

TIME_FMT = "%H:%M"

class WorkScheduleEditor:
    def __init__(self, app):
        self.app = app
        pid = self.app.selected_id.get()
        if not pid:
            messagebox.showinfo("Info", "Select an ID first.")
            return

        # --- Get month and year from database or today ---
        with sqlite3.connect(self.app.processor.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT date FROM sessions LIMIT 1")
            row = cursor.fetchone()
            if row:
                date = row[0]  # yyyymmdd
                month = int(date[4:6])
                year = int(date[:4])
            else:
                year, month = 1404, 1  # Default to 1404/01

        # --- Determine days in month (Persian calendar style) ---
        days_in_month = 30 if 7 <= month <= 12 else 31

        # --- Ensure defaults exist in DB ---
        self.ensure_default_schedules(self.app.processor.db_path, year, month, days_in_month)

        # --- Load all schedules + exceptions ---
        try:
            with sqlite3.connect(self.app.processor.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT date, entry, exit, floating, late_allowed, is_holiday FROM work_schedules")
                schedules = {
                    row[0]: {
                        "entry": row[1],
                        "exit": row[2],
                        "floating": row[3],
                        "late_allowed": bool(row[4]),
                        "is_holiday": bool(row[5])
                    } for row in cursor.fetchall()
                }

                cursor.execute("SELECT id, date, entry, exit FROM exceptions")
                exceptions = {(str(r[0]), r[1]): {"entry": r[2], "exit": r[3]} for r in cursor.fetchall()}

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load schedules or exceptions:\n{e}")
            return

        # --- Adaptive Exception Logic ---
        if any(key[0] == pid for key in exceptions):

            default_entry_dt = datetime.strptime(DEFAULT_ENTRY, TIME_FMT)
            default_exit_dt = datetime.strptime(DEFAULT_EXIT, TIME_FMT)
            default_work_duration = default_exit_dt - default_entry_dt


            for date_key, sched in schedules.items():       
                ex_key = (pid, date_key)
                if ex_key not in exceptions:
                    continue  # no exception for this date

                ex_entry = datetime.strptime(exceptions[ex_key]["entry"], TIME_FMT)
                ex_exit = datetime.strptime(exceptions[ex_key]["exit"], TIME_FMT)
                ex_work_duration = ex_exit - ex_entry
                normal_entry = datetime.strptime(sched["entry"], TIME_FMT)
                normal_exit = datetime.strptime(sched["exit"], TIME_FMT)

                # Case 1: Exit differs from default
                if sched["exit"] != DEFAULT_EXIT:
                    if ex_exit >= normal_exit:
                        # If overlapping → align exception with normal
                        exceptions[ex_key]["entry"] = sched["entry"]
                        exceptions[ex_key]["exit"] = sched["exit"]
                    # else: no overlap → do nothing

                # Case 2: Entry differs from default
                elif sched["entry"] != DEFAULT_ENTRY:
                    # Compute working durations
                    normal_work_duration = normal_exit - normal_entry
                    # If exception range fits inside new normal range → do nothing
                    if ex_entry >= normal_entry and ex_exit <= normal_exit:
                        continue
                    else:
                        # Otherwise, adjust exception schedule proportionally
                        ratio = normal_work_duration.total_seconds() / default_work_duration.total_seconds()
                        new_exit = normal_entry + timedelta(seconds=ex_work_duration.total_seconds() * ratio)
                        exceptions[ex_key]["entry"] = normal_entry.strftime(TIME_FMT)
                        exceptions[ex_key]["exit"] = self.round_to_half_hour(new_exit.strftime(TIME_FMT))

            # Apply modified exception times to schedules
            for (eid, date_key), ex_vals in exceptions.items():
                if eid == pid and date_key in schedules:
                    schedules[date_key]["entry"] = ex_vals["entry"]
                    schedules[date_key]["exit"] = ex_vals["exit"]
        # --- Build UI ---
        self.win = Toplevel()
        self.win.title("Work Schedule Editor")
        self.win.geometry("700x550")

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
        times_entry = [f"{h:02d}:{m:02d}" for h in range(7, 12) for m in (0, 30)]
        times_exit = [f"{h:02d}:{m:02d}" for h in range(13, 20) for m in (0, 30)]
        floating_opts = ["0.0", "0.5", "1.0"]

        # --- Create rows for each day ---
        for day in range(1, days_in_month + 1):
            date_str = f"{year:04d}{month:02d}{day:02d}"
            schedule = schedules.get(date_str, {
                "entry": DEFAULT_ENTRY,
                "exit": DEFAULT_EXIT,
                "floating": DEFAULT_FLOATING,
                "late_allowed": DEFAULT_LATE_ALLOWED,
                "is_holiday": False
            })

            frame = Frame(content_frame)
            frame.pack(pady=4, anchor='w')

            Label(frame, text=date_str, width=12).grid(row=0, column=0, padx=5)

            cb_entry = Combobox(frame, values=times_entry, width=7)
            cb_entry.set(schedule["entry"])
            cb_entry.grid(row=0, column=1, padx=5)

            cb_exit = Combobox(frame, values=times_exit, width=7)
            cb_exit.set(schedule["exit"])
            cb_exit.grid(row=0, column=2, padx=5)

            cb_floating = Combobox(frame, values=floating_opts, width=5)
            cb_floating.set(str(schedule["floating"]))
            cb_floating.grid(row=0, column=3, padx=5)

            late_var = BooleanVar(value=schedule["late_allowed"])
            Checkbutton(frame, text="10 min late OK", variable=late_var).grid(row=0, column=4, padx=5)

            holiday_var = BooleanVar(value=schedule["is_holiday"])
            Checkbutton(frame, text="Holiday", variable=holiday_var).grid(row=0, column=5, padx=5)

            self.combos[date_str] = (cb_entry, cb_exit, cb_floating, late_var, holiday_var)

        Button(content_frame, text="Save All", command=self.save_schedules).pack(pady=10)

    # -------------------------------------------------------------------------
    def round_to_half_hour(self, time_str):
        """Round a 'HH:MM' time string to nearest :00 or :30."""
        t = datetime.strptime(time_str, "%H:%M")
        minutes = t.minute
        if minutes < 15:
            t = t.replace(minute=0)
        elif minutes < 45:
            t = t.replace(minute=30)
        else:
            t = (t + timedelta(hours=1)).replace(minute=0)
        return t.strftime("%H:%M")
    # -------------------------------------------------------------------------

    def ensure_default_schedules(self, db_path, year, month, days_in_month):
        """Ensure work_schedules table has default entries for given month."""
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT date FROM work_schedules")
                existing_dates = {row[0] for row in cursor.fetchall()}

                for day in range(1, days_in_month + 1):
                    date_str = f"{year:04d}{month:02d}{day:02d}"
                    if date_str not in existing_dates:
                        cursor.execute("""
                            INSERT INTO work_schedules (date, is_holiday, entry, exit, floating, late_allowed)
                            VALUES (?, 0, ?, ?, ?, ?)
                        """, (date_str, DEFAULT_ENTRY, DEFAULT_EXIT, DEFAULT_FLOATING, DEFAULT_LATE_ALLOWED))
                conn.commit()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to ensure default schedules:\n{e}")

    # -------------------------------------------------------------------------
    def save_schedules(self):
        """Save all edited work schedules including holidays."""
        try:
            with sqlite3.connect(self.app.processor.db_path) as conn:
                cursor = conn.cursor()

                for d, (cb_e, cb_x, cb_f, late_v, hol_v) in self.combos.items():
                    entry = cb_e.get()
                    exit = cb_x.get()
                    floating = float(cb_f.get())
                    late_allowed = int(late_v.get())
                    is_holiday = int(hol_v.get())

                    # --- Insert default row if date does not exist ---
                    cursor.execute("SELECT COUNT(*) FROM work_schedules WHERE date = ?", (d,))
                    if cursor.fetchone()[0] == 0:
                        cursor.execute("""
                            INSERT INTO work_schedules (date, entry, exit, floating, late_allowed, is_holiday)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (d, entry, exit, floating, late_allowed, is_holiday))
                    else:
                        cursor.execute("""
                            UPDATE work_schedules
                            SET entry = ?, exit = ?, floating = ?, late_allowed = ?, is_holiday = ?
                            WHERE date = ?
                        """, (entry, exit, floating, late_allowed, is_holiday, d))

                    # --- Update in-memory dictionary ---
                    self.app.work_schedules[d] = {
                        "entry": entry,
                        "exit": exit,
                        "floating": floating,
                        "late_allowed": bool(late_allowed),
                        "is_holiday": bool(is_holiday)
                    }

                # --- Update global holidays list ---
                self.app.holidays = [int(d[6:8]) for d, vals in self.app.work_schedules.items() if vals["is_holiday"]]

                conn.commit()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to save schedules:\n{e}")
            return

        messagebox.showinfo("Saved", "✅ Work schedules updated successfully.")
        self.win.destroy()
