import csv
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from resources.config import DEFAULT_ENTRY, DEFAULT_EXIT, DEFAULT_FLOATING, DEFAULT_LATE_ALLOWED


class LogProcessor:
    def __init__(self, db_path="sessions.db"):
        self.records = defaultdict(lambda: defaultdict(list))
        self.sessions = []
        self.work_schedules = {} 
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize SQLite DB and sessions table."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT,
                    date TEXT,
                    entry TEXT,
                    exit TEXT,
                    status TEXT,       -- Paired / Fallback
                    duration INTEGER,
                    mode TEXT,         -- Late Entry / Early Exit / Leave
                    reason TEXT,       -- Impermissible / Announced / Other
                    total_impermissible INTEGER DEFAULT 0,
                    total_announced INTEGER DEFAULT 0,
                    total_other INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def load_file(self, txt_path: str):
        """Load and process TXT log file."""
        self.records.clear()
        self.sessions.clear()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM sessions")  # Clear old DB entries

        with open(txt_path, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) != 4:
                    continue
                person_id, date, time, _ = parts
                self.records[person_id][date].append(time)

        self._build_sessions()
        self._save_sessions_to_db()

    def _build_sessions(self):
        """Convert raw records into sessions."""
        self.sessions.clear()
        for person_id, dates in self.records.items():
            for date, times in dates.items():
                sorted_times = sorted(times)

                # If fewer than 2 times, skip
                if len(sorted_times) < 2:
                    continue

                # If odd count -> fallback
                if len(sorted_times) % 2 != 0:
                    self.sessions.append([
                        person_id,
                        date,
                        sorted_times[0],
                        sorted_times[-1],
                        "fallback"
                    ])
                    continue

                # First Entry and Last Exit
                first_entry = sorted_times[0]
                last_exit = sorted_times[-1]

                # Main paired session
                self.sessions.append([
                    person_id,
                    date,
                    first_entry,
                    last_exit,
                    "Paired"
                ])

                # Leave periods
                for i in range(1, len(sorted_times) - 1, 2):
                    first_exit = sorted_times[i]
                    second_entry = sorted_times[i + 1]

                    try:
                        t1 = datetime.strptime(first_exit, "%H:%M")
                        t2 = datetime.strptime(second_entry, "%H:%M")
                        duration_min = int((t2 - t1).total_seconds() // 60)
                    except ValueError:
                        duration_min = 0

                    self.sessions.append([
                        person_id,
                        date,
                        first_exit,
                        second_entry,
                        "Paired",
                        duration_min,
                        "Leave",
                        None
                    ])

    def _save_sessions_to_db(self):
        """Save sessions into SQLite database, replacing duplicates."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for s in self.sessions:
                # Handle variable length (leave sessions have more fields)
                if len(s) == 5:
                    pid, date, entry, exit_, status = s
                    duration = 0
                    mode = None
                    reason = None
                else:
                    pid, date, entry, exit_, status, duration, mode, reason = s

                cursor.execute("""
                    INSERT INTO sessions (id, date, entry, exit, status, duration, mode, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (pid, date, entry, exit_, status, duration, mode, reason))
            conn.commit()
    def get_fallback_sessions(self, pid: str):
        """Return fallback sessions for a person ID."""
        return [(i, s) for i, s in enumerate(self.sessions) if s[0] == pid and s[4] == "fallback"]

    def edit_fallback_sessions(self, pid: str, updates: list[tuple[int, str, str]]):
        for idx, entry, exit_ in updates:
            self.sessions[idx][2] = entry
            self.sessions[idx][3] = exit_
        # Update database as well
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for idx, entry, exit_ in updates:
                s = self.sessions[idx]
                cursor.execute("""
                    UPDATE sessions
                    SET entry=?, exit=?
                    WHERE id=? AND date=? AND status=?
                """, (entry, exit_, s[0], s[1], s[4]))
            conn.commit()

    def find_late_early(self, pid: str):
        """Return late/early sessions and save durations/reasons in DB."""
        results = []
        sessions = [s for s in self.sessions if s[0] == pid]

        for s in sessions:
            # Unpack depending on session length
            if len(s) == 5:
                pid_s, date, entry_str, exit_str, status = s
                duration = 0
                mode = None
                reason = None
            else:
                pid_s, date, entry_str, exit_str, status, duration, mode, reason = s


            # --- Handle Leave sessions separately ---
            if mode == "Leave":
                results.append((pid_s, date, entry_str, exit_str, status, duration, mode))
                continue

            # --- Handle Late/Early logic for Paired/Fallback sessions ---
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
                results.append((pid_s, date, entry_str, exit_str, status, minutes_late, "Late Entry"))
                allowed_exit = scheduled_exit + timedelta(minutes=float_minutes)
            else:
                # Allowed entry → allowed exit time is scheduled_exit + (entry_dt - scheduled_entry)
                delta_entry = entry_dt - scheduled_entry
                allowed_exit = scheduled_exit + delta_entry

            # Check early exit
            if exit_dt < allowed_exit:
                minutes_early = (allowed_exit - exit_dt).seconds // 60
                results.append((pid_s, date, entry_str, exit_str, status, minutes_early, "Early Exit"))


        return results

    
    def export_csv(self, csv_path: str):
        """Export all sessions from DB with per-ID totals."""

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, date, entry, exit, status, duration, mode, reason
                FROM sessions
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

        # Write to CSV
        import csv
        with open(csv_path, mode="w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "ID", "Date", "Entry", "Exit", "Status",
                "Duration (min)", "Mode", "Reason",
                "Total Impermissible", "Total Announced", "Total Other"
            ])
            writer.writerows(final_rows)

