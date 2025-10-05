import csv
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from resources.config import DEFAULT_ENTRY, DEFAULT_EXIT, DEFAULT_FLOATING, DEFAULT_LATE_ALLOWED, EXCEPTIONS
from tkinter import messagebox


class LogProcessor:
    def __init__(self, db_path="sessions.db"):
        self.records = defaultdict(lambda: defaultdict(list))
        self.sessions = []
        self.work_schedules = {} 
        self.exceptions = {}
        self.db_path = db_path
        self._init_db()                       
        self.load_exceptions_from_config()    # Always constant        

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

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS work_schedules (
                    date TEXT PRIMARY KEY,
                    is_holiday INTEGER DEFAULT 0,
                    entry TEXT DEFAULT ?,
                    exit TEXT DEFAULT ?,
                    floating REAL DEFAULT ?,
                    late_allowed INTEGER DEFAULT ?
                )
            ''', (DEFAULT_ENTRY, DEFAULT_EXIT, DEFAULT_FLOATING, int(DEFAULT_LATE_ALLOWED)))

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS exceptions (
                    id TEXT PRIMARY KEY,
                    entry TEXT,
                    exit TEXT
                )
            """)
            conn.commit()
    def load_exceptions_from_config(self):
        """Read constant exceptions from config.py and insert into DB."""
        self.exceptions.clear()

        # Convert to dictionary in memory
        self.exceptions = {e["id"]: (e["entry"], e["exit"]) for e in EXCEPTIONS}

        # 🔹 Insert into database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for pid, (entry, exit_) in self.exceptions.items():
                cursor.execute("""
                    INSERT OR REPLACE INTO exceptions (id, entry, exit)
                    VALUES (?, ?, ?)
                """, (pid, entry, exit_))
            conn.commit()

    def _build_and_save_schedules_to_db(self, month_in_file: str):
        """
        Completely rebuild the work_schedules table for a single month.
        Deletes all existing data and inserts fresh daily records
        for the given month (month_in_file, e.g. "140406").
        Uses Jalali calendar rules:
        - Months 1–6 → 31 days
        - Months 7–12 → 30 days
        """

        y = int(month_in_file[:4])
        m = int(month_in_file[4:6])

        # Jalali month length
        if 7 <= m <= 12:
            days_in_month = 30
        else:
            days_in_month = 31

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 🔹 1. Wipe the table clean
            cursor.execute("DELETE FROM work_schedules")
            conn.commit()
            print("Cleared all existing work_schedules data.")

            # 🔹 2. Insert all days for this month
            for d in range(1, days_in_month + 1):
                date_str = f"{y:04d}{m:02d}{d:02d}"

                cursor.execute("""
                    INSERT INTO work_schedules (date, is_holiday, entry, exit, floating, late_allowed)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    date_str,
                    0,  # not holiday by default
                    DEFAULT_ENTRY,
                    DEFAULT_EXIT,
                    DEFAULT_FLOATING,
                    int(DEFAULT_LATE_ALLOWED),
                ))

            conn.commit()       
    def _load_schedules_from_db(self, month_in_file: str):
        """Load all work schedules from the database into self.work_schedules."""

        self.work_schedules.clear()

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT date, is_holiday, entry, exit, floating, late_allowed
                    FROM work_schedules
                    ORDER BY date
                """)
                rows = cursor.fetchall()

        except sqlite3.Error as e:
            messagebox.showerror(
                "Database Error",
                f"Failed to load schedules from the database:\n{e}\n\n"
                f"Rebuilding schedules for month {month_in_file}..."
            )
            self._build_and_save_schedules_to_db(month_in_file)
            return

        # Build dictionary
        for date, is_holiday, entry, exit_, floating, late_allowed in rows:
            self.work_schedules[date] = {
                "is_holiday": bool(is_holiday),
                "entry": entry,
                "exit": exit_,
                "floating": float(floating),
                "late_allowed": bool(late_allowed),
            }

        messagebox.showinfo(
            "Work Schedules Loaded",
            f"✅ Loaded {len(rows)} work schedule records from DB."
        )        
    def _load_sessions_from_db(self):
        """Load all sessions from SQLite database into self.sessions."""
        self.sessions.clear()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, date, entry, exit, status, duration, mode, reason
                FROM sessions
                ORDER BY id, date
            """)
            rows = cursor.fetchall()

            for row in rows:
                pid, date, entry, exit_, status, duration, mode, reason = row

                # 🔹 Convert ID back to 8-digit padded string for UI display
                pid_str = str(pid).zfill(8)

                self.sessions.append([
                    pid_str, date, entry, exit_, status, duration, mode, reason
                ])

    def load_file(self, txt_path: str):
        """Load and process TXT log file."""
        self.records.clear()
        self.sessions.clear()
        # --- Step 0: Validate file content for proper format ---
        with open(txt_path, encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                parts = line.strip().split()

                # Check 4 columns
                if len(parts) != 4:
                    messagebox.showerror(
                        "Invalid File",
                        f"Line {line_no} does not have exactly 4 columns: '{line.strip()}'"
                        "Expected format: ID(8 chars) DATE(YYYYMMDD) TIME(HH:MM) CODE\n"
                        "Example: 00000010 14040603 16:38 05"
                    )
                    return

                person_id, date_str, time_str, code = parts

                # Check date: exactly 8 numeric characters
                if len(date_str) != 8 or not date_str.isdigit():
                    messagebox.showerror(
                        "Invalid File",
                        f"Line {line_no} has invalid date (must be 8 digits): '{date_str}'"
                        "Expected format: ID(8 chars) DATE(YYYYMMDD) TIME(HH:MM) CODE\n"
                        "Example: 00000010 14040603 16:38 05"
                    )
                    return
                
                # Check ID: exactly 8 numeric characters
                if len(person_id) != 8 or not person_id.isdigit():
                    messagebox.showerror(
                        "Invalid File",
                        f"Line {line_no} has invalid ID (must be 8 digits): '{person_id}'\n"
                        "Expected format: ID(8 chars) DATE(YYYYMMDD) TIME(HH:MM) CODE\n"
                        "Example: 00000010 14040603 16:38 05"
                    )
                    return

                # Check time: format HH:MM
                try:                    
                    datetime.strptime(time_str, "%H:%M")
                except ValueError:
                    messagebox.showerror(
                        "Invalid File",
                        f"Line {line_no} has invalid time format (should be HH:MM): '{time_str}'"
                        "Expected format: ID(8 chars) DATE(YYYYMMDD) TIME(HH:MM) CODE\n"
                        "Example: 00000010 14040603 16:38 05"
                    )
                    return
        # --- Step 1: Peek into file and find the first month (first 6 digits) ---
        month_in_file = None
        with open(txt_path, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) != 4:
                    continue
                _, date_str, _, _ = parts
                if len(date_str) < 6:
                    continue
                year_month = date_str[:6]  # first 6 digits, e.g., '140406'
                if month_in_file is None:
                    month_in_file = year_month

        # --- Step 1b: Show message if no valid date found ---
        if not month_in_file:
            messagebox.showwarning(
                "Invalid File",
                "No valid dates found in the file. Please check the file format."
            )
            return

        # --- Step 2: Check DB for existing sessions in this month ---
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM sessions
                WHERE substr(date,1,6) = ?
            """, (month_in_file,))
            (count_existing,) = cursor.fetchone()

        # --- Step 3: If found, just load from DB ---
        if count_existing > 0:
            messagebox.showinfo(
                "Data Loaded",
                f"Sessions for month {month_in_file} already exist in the database. Loading existing data."
            )
            self._load_sessions_from_db()
            self._load_schedules_from_db(month_in_file)
            self.app._refresh_id_menu()
            return
        # --- Step 4: Otherwise, parse TXT normally and save to DB ---
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM sessions")  # Clear old DB entries

        with open(txt_path, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) != 4:
                    continue
                person_id, date, time, _ = parts
                self.records[person_id][date].append(time)

        # --- Step 5: Build sessions and save ---
        self._build_sessions()
        self._save_sessions_to_db()
        self._build_and_save_schedules_to_db(month_in_file)

    def _build_sessions(self):
        """Convert raw records into sessions."""
        self.sessions.clear()
        for person_id, dates in self.records.items():
            for date, times in dates.items():
                sorted_times = sorted(times)

                # If fewer than 1 times, skip
                if len(sorted_times) < 1:
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
        """Save sessions into SQLite database, sorted by ID and date."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # 🔹 Sort by ID (pid) and then by date
            sorted_sessions = sorted(self.sessions, key=lambda s: (s[0], s[1]))
            for s in sorted_sessions:
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
        # 🔹 Refresh the ID menu in UI after saving
        if hasattr(self, "app"):
            self.app._refresh_id_menu()
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
        # 🔹 Sort sessions by ID and then by date
        self.sessions.sort(key=lambda s: (s[0], s[1]))

    def find_late_early(self, pid: str):
        """Return late/early sessions with minutes and reasons, using DB schedules and exceptions."""
        results = []

        # --- Step 1: Fetch all sessions for this ID from the DB ---
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, date, entry, exit, status, duration, mode, reason
                FROM sessions
                WHERE id = ?
                ORDER BY date
            """, (pid,))
            sessions = cursor.fetchall()

        # 🔹 Sort by ID then date (extra safety)
        sessions.sort(key=lambda s: (s[0], s[1]))
        for s in sessions:
            # --- Step 2: Unpack session depending on tuple length ---
            if len(s) == 5:
                pid_s, date, entry_str, exit_str, status = s
                duration, mode, reason = 0, None, None
            else:
                pid_s, date, entry_str, exit_str, status, duration, mode, reason = s

            # --- Step 3: Skip Leave sessions (they are reported as-is) ---
            if mode == "Leave":
                results.append((pid_s, date, entry_str, exit_str, status, duration, mode))
                continue

            # --- Step 4: Convert actual entry/exit strings to datetime objects ---
            try:
                entry_dt = datetime.strptime(entry_str, "%H:%M")
                exit_dt = datetime.strptime(exit_str, "%H:%M")
            except ValueError:
                continue  # Skip invalid entries

            # --- Step 5: Fetch scheduled times from work_schedules table ---
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT entry, exit, floating, late_allowed
                    FROM work_schedules
                    WHERE date = ?
                """, (date,))
                sched = cursor.fetchone()

            if sched:
                scheduled_entry_str, scheduled_exit_str, floating, late_allowed = sched
            else:
                # Fallback to defaults if schedule missing
                scheduled_entry_str = DEFAULT_ENTRY
                scheduled_exit_str = DEFAULT_EXIT
                floating = DEFAULT_FLOATING
                late_allowed = DEFAULT_LATE_ALLOWED

            # --- Step 6: Check for ID-specific exceptions ---
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT entry, exit FROM exceptions WHERE id = ?", (pid,))
                ex = cursor.fetchone()
            if ex:
                scheduled_entry_str, scheduled_exit_str = ex

            # --- Step 7: Convert schedule strings to datetime objects ---
            scheduled_entry = datetime.strptime(scheduled_entry_str, "%H:%M")
            scheduled_exit = datetime.strptime(scheduled_exit_str, "%H:%M")
            float_minutes = int(float(floating) * 60)

            # --- Step 8: Calculate allowed entry window ---
            if late_allowed:
                latest_allowed_entry = scheduled_entry + timedelta(minutes=10 + float_minutes)
            else:
                latest_allowed_entry = scheduled_entry + timedelta(minutes=float_minutes)

            # --- Step 9: Check Late Entry ---
            if entry_dt > latest_allowed_entry:
                minutes_late = (entry_dt - latest_allowed_entry).seconds // 60
                results.append((pid_s, date, entry_str, exit_str, status, minutes_late, "Late Entry"))
                allowed_exit = scheduled_exit + timedelta(minutes=float_minutes)
            else:
                # Allowed entry → allowed exit is extended by difference between actual and scheduled entry
                delta_entry = entry_dt - scheduled_entry
                allowed_exit = scheduled_exit + delta_entry

            # --- Step 10: Check Early Exit ---
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

