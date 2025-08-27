import csv
from collections import defaultdict
from datetime import datetime, timedelta
from resources.config import DEFAULT_ENTRY, DEFAULT_EXIT, DEFAULT_FLOATING, DEFAULT_LATE_ALLOWED


class LogProcessor:
    def __init__(self):
        self.records = defaultdict(lambda: defaultdict(list))
        self.sessions = []
        self.unusual_days = set()
        self.work_schedules = {} 

    def load_file(self, txt_path: str):
        """Load and process TXT log file."""
        self.records.clear()
        self.sessions.clear()

        with open(txt_path, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) != 4:
                    continue
                person_id, date, time, _ = parts
                self.records[person_id][date].append(time)

        self._build_sessions()

    def _build_sessions(self):
        """Convert raw records into sessions."""
        for person_id, dates in self.records.items():
            for date, times in dates.items():
                sorted_times = sorted(times)
                if len(sorted_times) % 2 == 0:
                    for i in range(0, len(sorted_times), 2):
                        self.sessions.append([person_id, date, sorted_times[i], sorted_times[i + 1], "paired"])
                else:
                    self.sessions.append([person_id, date, sorted_times[0], sorted_times[-1], "fallback"])

    def export_csv(self, csv_path: str):
        """Export sessions to CSV."""
        with open(csv_path, mode="w", newline='', encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["ID", "Date", "Entry", "Exit", "Mode"])
            writer.writerows(self.sessions)

    def get_fallback_sessions(self, pid: str):
        """Return fallback sessions for a person ID."""
        return [(i, s) for i, s in enumerate(self.sessions) if s[0] == pid and s[4] == "fallback"]

    def edit_fallback_sessions(self, pid: str, updates: list[tuple[int, str, str]]):
        """
        Update fallback sessions.

        updates = [(index_in_sessions, new_entry, new_exit), ...]
        """
        for idx, entry, exit_ in updates:
            self.sessions[idx][2] = entry
            self.sessions[idx][3] = exit_

    def find_late_early(self, pid: str):
        """Return late/early sessions for a given ID using per-day work schedules."""
        late_sessions = []

        # Get all sessions for this person
        sessions = [s for s in self.sessions if s[0] == pid]

        for s in sessions:
            date, entry_str, exit_str = s[1], s[2], s[3]

            # Skip invalid times
            try:
                entry_dt = datetime.strptime(entry_str, "%H:%M")
                exit_dt = datetime.strptime(exit_str, "%H:%M")
            except ValueError:
                continue

            # Get the scheduled times for this date
            schedule = self.work_schedules.get(date, {})
            scheduled_entry_str = schedule.get("entry", DEFAULT_ENTRY)        # "07:30"
            scheduled_exit_str = schedule.get("exit", DEFAULT_EXIT)           # "16:30"
            floating = schedule.get("floating", DEFAULT_FLOATING)             # 1.0 hour
            late_allowed = schedule.get("late_allowed", DEFAULT_LATE_ALLOWED) # False


            scheduled_entry = datetime.strptime(scheduled_entry_str, "%H:%M")
            scheduled_exit = datetime.strptime(scheduled_exit_str, "%H:%M")
            float_minutes = int(floating * 60)

            # Allowed entry window
            if late_allowed:
                latest_allowed_entry = scheduled_entry + timedelta(minutes=10 + float_minutes)
            else:
                latest_allowed_entry = scheduled_entry + timedelta(minutes=float_minutes)
            
            # Check late entry
            if entry_dt > latest_allowed_entry:
                minutes_late = (entry_dt - latest_allowed_entry).seconds // 60
                late_sessions.append((pid, date, "Late Entry", entry_str, minutes_late))
                # Not allowed → end time is scheduled exit
                allowed_exit =  scheduled_exit + timedelta(minutes=float_minutes)
            else:
                # Allowed entry → allowed exit time is scheduled_exit + (entry_dt - scheduled_entry)
                delta_entry = entry_dt - scheduled_entry
                allowed_exit = scheduled_exit + delta_entry

            # Check early exit
            if exit_dt < allowed_exit:
                minutes_early = (allowed_exit - exit_dt).seconds // 60
                late_sessions.append((pid, date, "Early Exit", exit_str, minutes_early))

        return late_sessions