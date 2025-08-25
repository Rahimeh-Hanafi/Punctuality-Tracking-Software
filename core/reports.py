from tkinter import Toplevel, Label, Text, END, messagebox
from datetime import datetime, timedelta
from resources.config import DEFAULT_ENTRY, DEFAULT_EXIT, DEFAULT_FLOATING, DEFAULT_LATE_ALLOWED

class LateEarlyReport:
    def __init__(self, app):
        self.app = app
        pid = self.app.selected_id.get()
        if not pid:
            messagebox.showinfo("Info", "Select an ID first.")
            return

        filtered_sessions = [s for s in self.app.sessions if s[0] == pid]
        late_sessions = []

        for s in filtered_sessions:
            date, entry, exit = s[1], s[2], s[3]
            try:
                entry_dt = datetime.strptime(entry, "%H:%M")
                exit_dt = datetime.strptime(exit, "%H:%M")
            except:
                continue

            sched = self.app.work_schedules.get(date, {
                "entry": DEFAULT_ENTRY,
                "exit": DEFAULT_EXIT,
                "floating": DEFAULT_FLOATING,
                "late_allowed": DEFAULT_LATE_ALLOWED            
            })
            start_time = datetime.strptime(sched["entry"], "%H:%M")
            end_time = datetime.strptime(sched["exit"], "%H:%M")

            if sched["late_allowed"]:
                latest_entry = start_time + timedelta(minutes=10)
            else:
                latest_entry = start_time

            expected_end = end_time + timedelta(minutes=int(sched["floating"] * 60))

            if entry_dt > latest_entry:
                minutes_late = (entry_dt - latest_entry).seconds // 60
                late_sessions.append((pid, date, "Late Entry", entry, minutes_late))

            if exit_dt < expected_end:
                minutes_early = (expected_end - exit_dt).seconds // 60
                late_sessions.append((pid, date, "Early Exit", exit, minutes_early))

        if not late_sessions:
            messagebox.showinfo("Result", "No late entries or early exits found for the selected ID.")
            return

        result_win = Toplevel()
        result_win.title("Late/Early Report")
        result_win.geometry("600x400")

        Label(result_win, text=f"Late/Early records for ID: {pid}", font=("Segoe UI", 12, "bold")).pack(pady=10)

        output = Text(result_win, wrap='word', font=('Consolas', 11))
        output.pack(padx=10, pady=10, fill='both', expand=True)
        for r in late_sessions:
            output.insert(END, f"Date: {r[1]} | {r[2]} at {r[3]} | {r[4]} min\n")