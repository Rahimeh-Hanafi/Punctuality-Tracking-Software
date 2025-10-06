import tkinter as tk
from tkinter import filedialog, messagebox, END, Entry, Label, Frame, Button

from tkinter.ttk import Style, OptionMenu

from core.processor import LogProcessor
from core.reports import ReportGenerator
from core.scheduler import WorkScheduleEditor
from resources.config import APP_TITLE, APP_SIZE, CREATOR


class LogApp:
    def __init__(self, root):
        self.root = root
        self.processor = LogProcessor()
        self.processor.app = self
        self.reporter = ReportGenerator(self.processor, app=self)
        self.work_schedules = self.processor.work_schedules
        self.selected_id = tk.StringVar(value="Select ID")
        self.sessions = []
        self.holidays = []
        self._setup_ui()

    def _setup_ui(self):
        self.root.title(APP_TITLE)
        self.root.geometry(APP_SIZE)
        self.root.configure(bg="#f0f2f5")

        style = Style()
        style.configure('TButton', font=('Segoe UI', 12), padding=6)

        frame = tk.Frame(self.root, bg="#f0f2f5")
        frame.pack(expand=False, pady=10)

        tk.Label(frame, text="🕒 Entry-Exit Log Processor", font=("Segoe UI", 16, "bold"), bg="#f0f2f5").pack(pady=10)
        tk.Button(frame, text="Select TXT File", command=self.load_file).pack(pady=5)
        tk.Button(frame, text="Export All to CSV", command=self.export_csv).pack(pady=5)

        tk.Label(frame, text="Select ID to View Sessions:", bg="#f0f2f5", font=("Segoe UI", 11)).pack(pady=(15, 0))
        self.id_menu = OptionMenu(frame, self.selected_id, ())
        self.id_menu.pack()
        tk.Button(frame, text="Show Selected ID Sessions", command=self.display_selected_id).pack(pady=5)
        tk.Button(frame, text="Edit Fallback Rows", command=self.edit_fallback).pack(pady=5)
        tk.Button(frame, text="Edit Work Schedules", command=self.open_schedule_editor).pack(pady=5)
        tk.Button(frame, text="Check Late/Early Sessions", command=self.check_late_early).pack(pady=5)

        # Text area
        text_frame = tk.Frame(self.root)
        text_frame.pack(pady=10, padx=20, fill='both', expand=True)

        scrollbar = tk.Scrollbar(text_frame)
        self.text_output = tk.Text(text_frame, wrap='word', yscrollcommand=scrollbar.set, font=('Consolas', 11))
        scrollbar.config(command=self.text_output.yview)
        scrollbar.pack(side="right", fill="y")
        self.text_output.pack(fill='both', expand=True)

        tk.Label(self.root, text=CREATOR, font=("Segoe UI", 9), bg="#f0f2f5", fg="#888").pack(side="bottom", pady=10)

    # ==== Button Actions ====
    def load_file(self):
        path = filedialog.askopenfilename(title="Select Entry-Exit TXT File", filetypes=[("Text files", "*.txt")])
        if not path:
            return
        try:
            self.processor.load_file(path)
            self.sessions = self.processor.sessions
            self._refresh_id_menu()
        except Exception as e:
            messagebox.showerror("Error", f"Could not process file:\n{e}")
    def _refresh_id_menu(self):
        menu = self.id_menu['menu']
        menu.delete(0, 'end')

        # ✅ Use sessions instead of records, works for DB and TXT
        ids = sorted({s[0] for s in self.processor.sessions})

        if ids:
            self.selected_id.set(ids[0])
            for pid in ids:
                menu.add_command(label=pid, command=lambda v=pid: self.selected_id.set(v))

        # 🔹 Force UI redraw
        self.root.update_idletasks()

    def export_csv(self):
        if not self.processor.sessions:
            messagebox.showinfo("Info", "Please process a file first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        self.processor.export_csv(path)
        messagebox.showinfo("Success", f"CSV file saved to:\n{path}")

    def display_selected_id(self):
        self.text_output.delete(1.0, END)
        pid = self.selected_id.get()
        if not pid:
            return

        # ✅ Filter directly from sessions 
        filtered = [s for s in self.processor.sessions if s[0] == pid]

        if not filtered:
            self.text_output.insert(END, f"No sessions found for ID {pid}\n")
            return
        # 🔹 Sort by date, then entry, then exit
        filtered_sorted = sorted(filtered, key=lambda s: (s[1], s[2], s[3]))
        for idx, s in enumerate(filtered_sorted):
            self.text_output.insert(END, f"[{idx}] Date: {s[1]} | Entry: {s[2]} | Exit: {s[3]} | Mode: {s[4]}\n")

    def edit_fallback(self):
        pid = self.selected_id.get()
        if not pid:
            messagebox.showinfo("Info", "Select an ID first.")
            return

        fallback_sessions = self.processor.get_fallback_sessions(pid)
        if not fallback_sessions:
            messagebox.showinfo("Info", "No fallback sessions for selected ID.")
            return

        win = tk.Toplevel(self.root)
        win.title("Edit Fallback Entries")
        win.geometry("450x350")

        tk.Label(win, text=f"Edit fallback sessions for ID: {pid}", font=("Segoe UI", 12, "bold")).pack(pady=10)

        entries = []

        for i, session in fallback_sessions:
            frame = Frame(win)
            frame.pack(pady=5)
            Label(frame, text=f"{session[1]}").grid(row=0, column=0, padx=5)
            e_entry = Entry(frame, width=10)
            e_entry.insert(0, session[2])
            e_entry.grid(row=0, column=1, padx=5)
            e_exit = Entry(frame, width=10)
            e_exit.insert(0, session[3])
            e_exit.grid(row=0, column=2, padx=5)
            entries.append((i, e_entry, e_exit))

        def save_all():
            updates = [(i, e1.get(), e2.get()) for i, e1, e2 in entries]
            self.processor.edit_fallback_sessions(pid, updates)
            messagebox.showinfo("Updated", f"All fallback sessions updated for ID {pid}.")
            win.destroy()
            self.display_selected_id()

        Button(win, text="Save All Changes", command=save_all).pack(pady=10)

    def open_schedule_editor(self):
        if not hasattr(self, "sessions") or not self.sessions:
            messagebox.showinfo("Info", "Please load a log file first.")
            return
        WorkScheduleEditor(self)

    def check_late_early(self):
        pid = self.selected_id.get()
        if not pid:
            messagebox.showinfo("Info", "Select an ID first.")
            return
        self.reporter.open_late_early_report_window(self.root, pid, holidays=self.holidays)
