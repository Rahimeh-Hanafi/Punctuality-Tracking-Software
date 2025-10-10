import csv
import tkinter as tk
from tkinter import messagebox, filedialog
import sqlite3
from datetime import datetime


class ReportGenerator:
    def __init__(self, processor, app=None):
        self.processor = processor
        self.app = app
        self.db_path = processor.db_path

    def save_report(self, file_path: str, late_sessions_with_reasons):
        """Save late/early report with reasons to CSV including total columns."""        
        # 🔹 Sort by ID, then by Date, then Entry and Exit if needed
        sorted_late_sessions = sorted(late_sessions_with_reasons, key=lambda r: (r[0], r[1], r[2], r[3]))

        with open(file_path, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                "ID", "Date", "Entry", "Exit", "Status", "Duration (min)", "Mode", "Reason",
                "Total Impermissible", "Total Announced", "Total Other"
            ])
            writer.writerows(sorted_late_sessions)

    def open_late_early_report_window(self, root, pid: str, holidays=None):      
        try:
            with sqlite3.connect(self.processor.db_path) as conn:
                cursor = conn.cursor()

                # Find all distinct months for this ID
                cursor.execute("SELECT DISTINCT substr(date,1,6) FROM sessions WHERE id = ?", (pid,))
                months = [row[0] for row in cursor.fetchall()]

                for ym in months:  # e.g. "140406"  
                    # Read holidays directly from in-memory schedules
                    holidays = [
                        int(date_key[6:8])
                        for date_key, info in self.app.work_schedules.items()
                        if info.get("is_holiday") and date_key.startswith(ym)
                    ]                                            
                    m = int(ym[4:6]) 

                    if 7 <= m <= 12:
                        days_in_month = 30
                    else:  # months 1–6
                        days_in_month = 31

                    # Days except holidays
                    usual_days = [d for d in range(1, days_in_month + 1) if d not in holidays]

                    # Before inserting new Leave record, remove any Leave rows for holidays
                    # that may have been created by pressing "Check Late/Early Sessions"
                    # before setting the work schedule (to avoid incorrect inserts from button actions)
                    for h in holidays:
                        date_str = f"{ym}{h:02d}"
                        cursor.execute("""
                            DELETE FROM sessions
                            WHERE id = ? AND date = ? AND mode = 'Leave'
                        """, (pid, date_str))

                    # Get existing days
                    cursor.execute("""
                        SELECT substr(date,7,2)
                        FROM sessions
                        WHERE id = ? AND substr(date,1,6) = ?
                    """, (pid, ym))
                    existing_days = {int(row[0]) for row in cursor.fetchall()}

                    # Insert missing non-holiday Leave rows
                    for day in usual_days:
                        if day not in existing_days:
                            date_str = f"{ym}{day:02d}"  # e.g. 14040605

                            # ✅ Try to get work schedule from in-memory schedules
                            schedule = self.app.work_schedules.get(date_str)

                            if schedule:
                                entry_time = schedule.get("entry", getattr(self.app, "DEFAULT_ENTRY", "07:30"))
                                exit_time = schedule.get("exit", getattr(self.app, "DEFAULT_EXIT", "16:30"))
                            else:
                                # Check for ID-based exception in the database
                                cursor.execute(
                                    "SELECT entry, exit FROM exceptions WHERE id = ? AND date = ?",
                                    (pid, date_str)
                                )
                                ex_row = cursor.fetchone()
                                if ex_row:
                                    entry_time, exit_time = ex_row
                                else:
                                    # Fall back to defaults
                                    entry_time = getattr(self.app, "DEFAULT_ENTRY", "07:30")
                                    exit_time = getattr(self.app, "DEFAULT_EXIT", "16:30")

                            entry_dt = datetime.strptime(entry_time, "%H:%M")
                            exit_dt = datetime.strptime(exit_time, "%H:%M")
                            duration_minutes = int((exit_dt - entry_dt).total_seconds() // 60)

                            # ✅ Insert missing record
                            cursor.execute("""
                                INSERT INTO sessions (id, date, entry, exit, status, duration, mode, reason)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (pid, date_str, entry_time, exit_time, "paired", duration_minutes, "Leave", None))

                conn.commit()
                messagebox.showinfo("Completed", f"Missing days for ID {pid} have been added as 'Leave'.")
        
        except Exception as e:
            messagebox.showerror("Database Error", f"Error while updating missing days:\n{e}")


        """Tkinter window for late/early analysis with reason selection & export."""
        late_sessions = self.processor.find_late_early(pid)
        if not late_sessions:
            messagebox.showinfo("Result", "No late/early entries found.")
            return

        result_win = tk.Toplevel(root)
        result_win.title("Late/Early Report")
        result_win.geometry("600x500")

        tk.Label(result_win, text=f"Late/Early records for ID: {pid}", font=("Segoe UI", 12, "bold")).pack(pady=10)

        container = tk.Frame(result_win)
        container.pack(fill='both', expand=True)

        canvas = tk.Canvas(container)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        reason_vars = []
        for r in late_sessions:
            pid_r, date, entry, exit, status, minutes, mode = r
            row_frame = tk.Frame(scrollable_frame)
            row_frame.pack(anchor='w', pady=3, padx=5, fill='x')

            tk.Label(
                row_frame,
                text=f"{pid_r} | {date} | {entry} → {exit} | {status} | {minutes} min | {mode}",
                width=65,
                anchor='w'
            ).pack(side='left')

            var = tk.StringVar()
            var.set("Select Reason")
            
            # Callback to save immediately
            def on_reason_selected(*args, var=var):
                # Just store selection in memory, no DB change
                selected_reason = var.get()
                if selected_reason == "Select Reason":
                    return
            # Attach trace to trigger DB update on selection
            var.trace_add("write", on_reason_selected)
            dropdown = tk.OptionMenu(row_frame, var, "Impermissible", "Announced", "Other")
            dropdown.pack(side='right')

            # Now include mode too
            reason_vars.append((var, minutes, pid_r, date, entry, exit, status, mode))

        def calculate_times():
            for var, *_ in reason_vars:
                if var.get() == "Select Reason":
                    messagebox.showerror("Error", "Please select a reason for all records before calculating.")
                    return

            total_impermissible = sum(minutes for var, minutes, *_ in reason_vars if var.get() == "Impermissible")
            total_announced = sum(minutes for var, minutes, *_ in reason_vars if var.get() == "Announced")

            messagebox.showinfo("Totals",
                                f"Total Impermissible time: {total_impermissible} minutes\n"
                                f"Total Announced time: {total_announced} minutes")

        def save_report_ui():
            for var, *_ in reason_vars:
                if var.get() == "Select Reason":
                    messagebox.showerror("Error", "Please select a reason for all records before saving.")
                    return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Save report as"
            )
            if not file_path:
                return
            
            # Calculate totals for each reason
            total_impermissible = sum(minutes or 0 for var, minutes, *_ in reason_vars if var.get() == "Impermissible")
            total_announced = sum(minutes or 0 for var, minutes, *_ in reason_vars if var.get() == "Announced")
            total_other = sum(minutes or 0 for var, minutes, *_ in reason_vars if var.get() == "Other")
           
            # Prepare rows with extra columns for totals
            rows = [
                (pid_r, date, entry, exit, status, minutes, mode, var.get(),
                total_impermissible, total_announced, total_other)
                for var, minutes, pid_r, date, entry, exit, status, mode in reason_vars
            ]

            self.save_report(file_path, rows)
            # --- Database updates ---             
            with sqlite3.connect(self.processor.db_path) as conn:
                cursor = conn.cursor()

                # Remove duplicates for this ID (Necessary for reprocessed IDs)
                cursor.execute("""
                    DELETE FROM sessions
                    WHERE rowid NOT IN (
                        SELECT MIN(rowid)
                        FROM sessions
                        WHERE id = ?
                        GROUP BY date, entry, exit
                    )
                    AND id = ?
                """, (pid, pid))      

                # 2️⃣ Clear old duration, mode, reason for this ID (Necessary for reprocessed IDs)
                cursor.execute("""
                    UPDATE sessions
                    SET duration = NULL,
                        mode = NULL,
                        reason = NULL
                    WHERE id = ?
                """, (pid,))       

                # Get all unique (id, date, entry, exit) tuples from reason_vars
                unique_keys = {(pid_r, date, entry, exit) for _, _, pid_r, date, entry, exit, *_ in reason_vars}

                # Delete existing rows for those id+date+entry+exit combos
                for pid_r, date, entry, exit in unique_keys:
                    cursor.execute(
                        "DELETE FROM sessions WHERE id = ? AND date = ? AND entry = ? AND exit = ?",
                        (pid_r, date, entry, exit)
                    )

                # Insert fresh rows
                for var, minutes, pid_r, date, entry, exit, status, mode in reason_vars:
                    cursor.execute("""
                        INSERT INTO sessions (
                            id, date, entry, exit, status, duration, mode, reason,
                            total_impermissible, total_announced, total_other
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        pid_r, date, entry, exit, status, minutes, mode, var.get(),
                        total_impermissible, total_announced, total_other
                    ))

                conn.commit()

            # -------------------------------
            messagebox.showinfo("Saved", f"Report saved successfully to {file_path}")

        btn_frame = tk.Frame(result_win)
        btn_frame.pack(pady=10)

        # tk.Button(btn_frame, text="Calculate Times", command=calculate_times,
        #           bg="darkblue", fg="white").pack(side='left', padx=5)
        tk.Button(btn_frame, text="Save Report", command=save_report_ui,
                  bg="green", fg="white").pack(side='left', padx=5)

    def export_csv(self, csv_path: str):
        """Export all sessions from DB with per-ID totals."""

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, date, entry, exit, status, duration, mode, reason
                FROM sessions
                ORDER BY id, date
            """)
            rows = cursor.fetchall()

        # Group rows by ID
        from collections import defaultdict
        rows_by_id = defaultdict(list)
        for r in rows:
            pid = r[0]  # first column = ID
            rows_by_id[pid].append(r)

        final_rows = []
        for pid, session_rows in rows_by_id.items():
            total_impermissible = sum(r[5] for r in session_rows if r[7] == "Impermissible")
            total_announced = sum(r[5] for r in session_rows if r[7] == "Announced")
            total_other = sum(r[5] for r in session_rows if r[7] not in ("Impermissible", "Announced", None))

            for r in session_rows:
                final_rows.append((
                    r[0],  # ID
                    r[1],  # Date
                    r[2],  # Entry
                    r[3],  # Exit
                    r[4],  # Status
                    r[5],  # Duration
                    r[6],  # Mode
                    r[7],  # Reason
                    total_impermissible,
                    total_announced,
                    total_other
                ))

        # Sort rows by ID and then by date and time
        sorted_rows = sorted(final_rows, key=lambda r: (r[0], r[1], r[2], r[3]))

        # Write to CSV        
        with open(csv_path, mode="w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "ID", "Date", "Entry", "Exit", "Status",
                "Duration (min)", "Mode", "Reason",
                "Total Impermissible", "Total Announced", "Total Other"
            ])
            writer.writerows(sorted_rows)

