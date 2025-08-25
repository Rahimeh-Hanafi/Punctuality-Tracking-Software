import tkinter as tk
from tkinter import Frame, Label, Button, Text, Scrollbar, StringVar, END, RIGHT, Y
from tkinter.ttk import Style

from core.processor import process_file, save_to_csv
from core.scheduler import WorkScheduleEditor
from core.reports import LateEarlyReport


class LogProcessorApp:
    def __init__(self, root):
        self.root = root
        self.records = {}
        self.sessions = []
        self.work_schedules = {}

        self.selected_id = StringVar()
        self.selected_id.set("Select ID")

        self.build_ui()

    def build_ui(self):
        self.root.title("Entry-Exit Log Processor")
        self.root.geometry("700x750")
        self.root.configure(bg="#f0f2f5")

        style = Style()
        style.configure('TButton', font=('Segoe UI', 12), padding=6)

        frame = Frame(self.root, bg="#f0f2f5")
        frame.pack(expand=False, pady=10)

        Label(
            frame,
            text="🕒 Entry-Exit Log Processor",
            font=("Segoe UI", 16, "bold"),
            bg="#f0f2f5"
        ).pack(pady=10)

        Button(frame, text="Select TXT File",
               command=lambda: process_file(self)).pack(pady=5)
        Button(frame, text="Export All to CSV",
               command=lambda: save_to_csv(self)).pack(pady=5)
        Button(frame, text="Edit Work Schedules",
               command=lambda: WorkScheduleEditor(self)).pack(pady=5)
        Button(frame, text="Check Late/Early Sessions",
               command=lambda: LateEarlyReport(self)).pack(pady=5)

        self.text_output = Text(self.root, wrap='word', font=('Consolas', 11))
        scrollbar = Scrollbar(self.root, command=self.text_output.yview)
        self.text_output.configure(yscrollcommand=scrollbar.set)

        self.text_output.pack(side="left", fill='both', expand=True, padx=20, pady=10)
        scrollbar.pack(side=RIGHT, fill=Y)

        Label(
            self.root,
            text="Created by ChatGPT",
            font=("Segoe UI", 9),
            bg="#f0f2f5",
            fg="#888"
        ).pack(side="bottom", pady=10)

    def display_selected_id(self):
        self.text_output.delete(1.0, END)
        pid = self.selected_id.get()
        if not pid or pid not in self.records:
            return

        filtered_sessions = [s for s in self.sessions if s[0] == pid]
        for idx, s in enumerate(filtered_sessions):
            self.text_output.insert(
                END,
                f"[{idx}] Date: {s[1]} | Entry: {s[2]} | Exit: {s[3]} | Mode: {s[4]}\n"
            )
