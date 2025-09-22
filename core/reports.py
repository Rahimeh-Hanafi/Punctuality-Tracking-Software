import csv
import tkinter as tk
from tkinter import messagebox, filedialog


class ReportGenerator:
    def __init__(self, processor):
        self.processor = processor

    def save_report(self, file_path: str, late_sessions_with_reasons):
        """Save late/early report with reasons to CSV including total columns."""
        with open(file_path, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                "ID", "Date", "Type", "Time", "Duration (min)", "Reason",
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
            pid_r, date, status, time, minutes = r
            row_frame = tk.Frame(scrollable_frame)
            row_frame.pack(anchor='w', pady=3, padx=5, fill='x')

            tk.Label(row_frame, text=f"{pid_r} | {date} | {status} at {time} | {minutes} min",
                     width=55, anchor='w').pack(side='left')

            var = tk.StringVar()
            var.set("Select Reason")
            dropdown = tk.OptionMenu(row_frame, var, "Impermissible", "Announced", "Other")
            dropdown.pack(side='right')
            reason_vars.append((var, minutes, pid_r, date, status, time))

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

            rows = [(pid_r, date, status, time, minutes, var.get())
                    for var, minutes, pid_r, date, status, time in reason_vars]
            
            # Calculate totals for each reason
            total_impermissible = sum(minutes for var, minutes, *_ in reason_vars if var.get() == "Impermissible")
            total_announced = sum(minutes for var, minutes, *_ in reason_vars if var.get() == "Announced")
            total_other = sum(minutes for var, minutes, *_ in reason_vars if var.get() == "Other")
            # Prepare rows with extra columns for totals
            rows = [
                (pid_r, date, status, time, minutes, var.get(),
                total_impermissible, total_announced, total_other)
                for var, minutes, pid_r, date, status, time in reason_vars
            ]

            self.save_report(file_path, rows)
            messagebox.showinfo("Saved", f"Report saved successfully to {file_path}")

        btn_frame = tk.Frame(result_win)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Calculate Times", command=calculate_times,
                  bg="darkblue", fg="white").pack(side='left', padx=5)
        tk.Button(btn_frame, text="Save Report", command=save_report_ui,
                  bg="green", fg="white").pack(side='left', padx=5)
