import csv
import tkinter as tk
from tkinter import messagebox, filedialog
import sqlite3


class ReportGenerator:
    def __init__(self, processor, app=None):
        self.processor = processor
        self.app = app

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
        holidays = holidays or []
        
        try:
            with sqlite3.connect(self.processor.db_path) as conn:
                cursor = conn.cursor()

                # Find all distinct months for this ID
                cursor.execute("SELECT DISTINCT substr(date,1,6) FROM sessions WHERE id = ?", (pid,))
                months = [row[0] for row in cursor.fetchall()]

                for ym in months:  # e.g. "140406"               
                    m = int(ym[4:6]) 

                    if 7 <= m <= 12:
                        days_in_month = 30
                    else:  # months 1–6
                        days_in_month = 31

                    # Days except holidays
                    usual_days = [d for d in range(1, days_in_month + 1) if d not in holidays]

                    # Get existing days
                    cursor.execute("""
                        SELECT substr(date,7,2)
                        FROM sessions
                        WHERE id = ? AND substr(date,1,6) = ?
                    """, (pid, ym))
                    existing_days = {int(row[0]) for row in cursor.fetchall()}

                    # Insert missing days as "Leave"
                    for day in usual_days:
                        if day not in existing_days:
                            date_str = f"{ym}{day:02d}"  # e.g. 14040605

                            # ✅ Try to get work schedule for this day
                            cursor.execute("SELECT entry, exit FROM work_schedules WHERE date = ?", (date_str,))
                            row = cursor.fetchone()

                            if row:
                                entry_time, exit_time = row
                            else:
                                entry_time = getattr(self.app, "DEFAULT_ENTRY", "07:30")
                                exit_time = getattr(self.app, "DEFAULT_EXIT", "16:30")

                            # ✅ Check for ID-based exception
                            cursor.execute("SELECT entry, exit FROM exceptions WHERE id = ?", (pid,))
                            ex_row = cursor.fetchone()
                            if ex_row:
                                entry_time, exit_time = ex_row

                            # ✅ Insert missing record
                            cursor.execute("""
                                INSERT INTO sessions (id, date, entry, exit, status, duration, mode, reason)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (pid, date_str, entry_time, exit_time, "paired", 540, "Leave", None))

                conn.commit()
                messagebox.showinfo("Completed", f"Missing days for ID {pid} have been added as 'Leave'.")
        
        except Exception as e:
            messagebox.showerror("Database Error", f"Error while updating missing days:\n{e}")


        # Then, clean duplicates only for this ID (Necessary for reprocess a specific ID)
        with sqlite3.connect(self.processor.db_path) as conn:
            cursor = conn.cursor()
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
            conn.commit()
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
            def on_reason_selected(*args, var=var, pid_r=pid_r, date=date, entry=entry, exit=exit, status=status, mode=mode):
                selected_reason = var.get()
                if selected_reason == "Select Reason":
                    return
                with sqlite3.connect(self.processor.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE sessions
                        SET reason = ?
                        WHERE id = ? AND date = ? AND entry = ? AND exit = ? AND status = ? AND mode = ?
                    """, (
                        selected_reason,
                        pid_r,
                        date,
                        entry,
                        exit,
                        status,
                        mode
                    ))
                    conn.commit()

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
            total_impermissible = sum(minutes for var, minutes, *_ in reason_vars if var.get() == "Impermissible")
            total_announced = sum(minutes for var, minutes, *_ in reason_vars if var.get() == "Announced")
            total_other = sum(minutes for var, minutes, *_ in reason_vars if var.get() == "Other")
           
            # Prepare rows with extra columns for totals
            rows = [
                (pid_r, date, entry, exit, status, minutes, mode, var.get(),
                total_impermissible, total_announced, total_other)
                for var, minutes, pid_r, date, entry, exit, status, mode in reason_vars
            ]

            self.save_report(file_path, rows)
            # --- Save reasons to database ---
            with sqlite3.connect(self.processor.db_path) as conn:
                cursor = conn.cursor()

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

        tk.Button(btn_frame, text="Calculate Times", command=calculate_times,
                  bg="darkblue", fg="white").pack(side='left', padx=5)
        tk.Button(btn_frame, text="Save Report", command=save_report_ui,
                  bg="green", fg="white").pack(side='left', padx=5)
