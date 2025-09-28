import csv
import tkinter as tk
from tkinter import messagebox, filedialog
import sqlite3


class ReportGenerator:
    def __init__(self, processor):
        self.processor = processor

    def save_report(self, file_path: str, late_sessions_with_reasons):
        """Save late/early report with reasons to CSV including total columns."""
        with open(file_path, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                "ID", "Date", "Entry", "Exit", "Status", "Duration (min)", "Mode", "Reason",
                "Total Impermissible", "Total Announced", "Total Other"
            ])
            writer.writerows(late_sessions_with_reasons)

    def open_late_early_report_window(self, root, pid: str):
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
