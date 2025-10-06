import sqlite3
from tkinter import (
    Toplevel, Label, Frame, Button, Canvas, Scrollbar, VERTICAL,
    BooleanVar, Checkbutton, messagebox
)
from tkinter.ttk import Combobox
from resources.config import DEFAULT_ENTRY, DEFAULT_EXIT, DEFAULT_FLOATING, DEFAULT_LATE_ALLOWED

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

                cursor.execute("SELECT id, entry, exit FROM exceptions")
                exceptions = {str(r[0]): {"entry": r[1], "exit": r[2]} for r in cursor.fetchall()}

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load schedules or exceptions:\n{e}")
            return

        # --- Apply per-ID exception ---
        if pid in exceptions:
            for d in schedules:
                schedules[d]["entry"] = exceptions[pid]["entry"]
                schedules[d]["exit"] = exceptions[pid]["exit"]

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
        times_entry = [f"{h:02d}:{m:02d}" for h in range(7, 11) for m in (0, 30)]
        times_exit = [f"{h:02d}:{m:02d}" for h in range(13, 18) for m in (0, 30)]
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
