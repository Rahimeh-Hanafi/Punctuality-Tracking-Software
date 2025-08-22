import csv
from collections import defaultdict
from tkinter import Tk, Canvas, Button, Label, filedialog, messagebox, Frame, StringVar, OptionMenu, Text, Scrollbar, VERTICAL, RIGHT, Y, END, Entry, Toplevel, Checkbutton, BooleanVar

from tkinter.ttk import Style

records = defaultdict(lambda: defaultdict(list))
sessions = []
unusual_days = set()
def process_file():
    global records, sessions, selected_id

    txt_path = filedialog.askopenfilename(
        title="Select Entry-Exit TXT File",
        filetypes=[("Text files", "*.txt")]
    )
    if not txt_path:
        return

    records.clear()
    sessions.clear()

    try:
        with open(txt_path, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) != 4:
                    continue
                person_id, date, time, _ = parts
                records[person_id][date].append(time)
    except Exception as e:
        messagebox.showerror("Error", f"Could not read file:\n{e}")
        return

    for person_id, dates in records.items():
        for date, times in dates.items():
            sorted_times = sorted(times)
            if len(sorted_times) % 2 == 0:
                for i in range(0, len(sorted_times), 2):
                    sessions.append([person_id, date, sorted_times[i], sorted_times[i + 1], "paired"])
            else:
                sessions.append([person_id, date, sorted_times[0], sorted_times[-1], "fallback"])

    ids = sorted(records.keys())
    selected_id.set(ids[0] if ids else "")
    id_menu['menu'].delete(0, 'end')
    for pid in ids:
        id_menu['menu'].add_command(label=pid, command=lambda v=pid: selected_id.set(v))
    display_selected_id()


def display_selected_id():
    text_output.delete(1.0, END)
    pid = selected_id.get()
    if not pid or pid not in records:
        return

    filtered_sessions = [s for s in sessions if s[0] == pid]
    for idx, s in enumerate(filtered_sessions):
        text_output.insert(END, f"[{idx}] Date: {s[1]} | Entry: {s[2]} | Exit: {s[3]} | Mode: {s[4]}\n")


def edit_fallback():
    pid = selected_id.get()
    if not pid:
        messagebox.showinfo("Info", "Select an ID first.")
        return

    fallback_sessions = [(i, s) for i, s in enumerate(sessions) if s[0] == pid and s[4] == "fallback"]
    if not fallback_sessions:
        messagebox.showinfo("Info", "No fallback sessions for selected ID.")
        return

    win = Toplevel()
    win.title("Edit Fallback Entries")
    win.geometry("450x350")

    Label(win, text=f"Edit fallback sessions for ID: {pid}", font=("Segoe UI", 12, "bold")).pack(pady=10)

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
        for i, e1, e2 in entries:
            sessions[i][2] = e1.get()
            sessions[i][3] = e2.get()
        messagebox.showinfo("Updated", f"All fallback sessions updated for ID {pid}.")
        win.destroy()
        display_selected_id()

    Button(win, text="Save All Changes", command=save_all).pack(pady=10)


def filter_late_early():
    pid = selected_id.get()
    if not pid:
        messagebox.showinfo("Info", "Select an ID first.")
        return

    filtered_sessions = [s for s in sessions if s[0] == pid]
    late_sessions = []

    for s in filtered_sessions:
        entry = s[2]
        exit = s[3]
        try:
            entry_hour = int(entry.split(':')[0])
            exit_hour = int(exit.split(':')[0])
        except:
            continue
        if 10 <= entry_hour <= 18:
            if entry > "10:00":
                late_sessions.append((s[1], "Late Entry", entry))
            if exit < "18:00":
                late_sessions.append((s[1], "Early Exit", exit))

    if not late_sessions:
        messagebox.showinfo("Result", "No late entries or early exits found for the selected ID.")
        return

    result_win = Toplevel()
    result_win.title("Late/Early Report")
    result_win.geometry("400x300")
    Label(result_win, text=f"Late/Early records for ID: {pid}", font=("Segoe UI", 12, "bold")).pack(pady=10)

    output = Text(result_win, wrap='word', font=('Consolas', 11))
    output.pack(padx=10, pady=10, fill='both', expand=True)
    for r in late_sessions:
        output.insert(END, f"Date: {r[0]} | {r[1]} at {r[2]}\n")


def save_to_csv():
    if not sessions:
        messagebox.showinfo("Info", "Please process a file first.")
        return

    csv_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")],
        title="Save CSV File As"
    )
    if not csv_path:
        return

    try:
        with open(csv_path, mode="w", newline='', encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["ID", "Date", "Entry", "Exit", "Mode"])
            writer.writerows(sessions)
        messagebox.showinfo("Success", f"CSV file saved to:\n{csv_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Could not save CSV:\n{e}")

def process_file():
    global records, sessions, selected_id

    txt_path = filedialog.askopenfilename(
        title="Select Entry-Exit TXT File",
        filetypes=[("Text files", "*.txt")]
    )
    if not txt_path:
        return

    records.clear()
    sessions.clear()

    try:
        with open(txt_path, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) != 4:
                    continue
                person_id, date, time, _ = parts
                records[person_id][date].append(time)
    except Exception as e:
        messagebox.showerror("Error", f"Could not read file:\n{e}")
        return

    for person_id, dates in records.items():
        for date, times in dates.items():
            sorted_times = sorted(times)
            if len(sorted_times) % 2 == 0:
                for i in range(0, len(sorted_times), 2):
                    sessions.append([person_id, date, sorted_times[i], sorted_times[i + 1], "paired"])
            else:
                sessions.append([person_id, date, sorted_times[0], sorted_times[-1], "fallback"])

    ids = sorted(records.keys())
    selected_id.set(ids[0] if ids else "")
    id_menu['menu'].delete(0, 'end')
    for pid in ids:
        id_menu['menu'].add_command(label=pid, command=lambda v=pid: selected_id.set(v))


def select_unusual_days():
    global unusual_days

    pid = selected_id.get()
    if not pid:
        messagebox.showinfo("Info", "Select an ID first.")
        return

    filtered_dates = sorted({s[1] for s in sessions if s[0] == pid})
    if not filtered_dates:
        messagebox.showinfo("Info", "No sessions found for selected ID.")
        return

    win = Toplevel()
    win.title("Select Unusual Work Days")
    win.geometry("400x400")
    Label(win, text=f"Select 10:00–18:00 days for ID: {pid}", font=("Segoe UI", 12, "bold")).pack(pady=10)

    canvas = Canvas(win)
    scrollbar = Scrollbar(win, orient=VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    content_frame = Frame(canvas)
    canvas.create_window((0, 0), window=content_frame, anchor="nw")

    content_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    check_vars = {}
    for date in filtered_dates:
        var = BooleanVar(value=(date in unusual_days))
        chk = Checkbutton(content_frame, text=date, variable=var)
        chk.pack(anchor='w')
        check_vars[date] = var

    def save_selection():
        for d, v in check_vars.items():
            if v.get():
                unusual_days.add(d)
            elif d in unusual_days:
                unusual_days.remove(d)
        messagebox.showinfo("Saved", f"Saved 10–18 schedule for {pid}.")
        win.destroy()

    Button(content_frame, text="Save Selected Days", command=save_selection).pack(pady=10)
def filter_late_early():
    from datetime import datetime, timedelta
    import tkinter as tk
    from tkinter import messagebox, Toplevel, Label, Text, Button, StringVar, OptionMenu, Scrollbar, filedialog

    pid = selected_id.get()
    if not pid:
        messagebox.showinfo("Info", "Select an ID first.")
        return

    filtered_sessions = [s for s in sessions if s[0] == pid]
    late_sessions = []

    for s in filtered_sessions:
        date = s[1]
        entry = s[2]
        exit = s[3]

        try:
            entry_dt = datetime.strptime(entry, "%H:%M")
            exit_dt = datetime.strptime(exit, "%H:%M")
        except:
            continue

        if date in unusual_days:
            start_time = datetime.strptime("10:00", "%H:%M")
            latest_allowed_entry = start_time + timedelta(minutes=20)
            delta = entry_dt - start_time
            float_minutes = max(delta.total_seconds() // 60, 0)  # clamp to 0 if negative
            if entry_dt <= latest_allowed_entry:
                end_time = start_time + timedelta(minutes=60 * 8) + timedelta(minutes=float_minutes)
            else:
                end_time = datetime.strptime("18:20", "%H:%M")
                # Mark late entry
                late_by = entry_dt - latest_allowed_entry
                minutes_late = late_by.seconds // 60
                late_sessions.append((pid, date, "Late Entry", entry, minutes_late))
            if exit_dt < end_time:
                early_by = end_time - exit_dt
                minutes_early = early_by.seconds // 60
                late_sessions.append((pid, date, "Early Exit", exit, minutes_early))

        else:
            if int(pid) == 10: 
                start_time = datetime.strptime("07:00", "%H:%M")
            else:
                start_time = datetime.strptime("08:00", "%H:%M")
            latest_allowed_entry = start_time + timedelta(minutes=45)
            delta = entry_dt - start_time
            float_minutes = max(delta.total_seconds() // 60, 0)  # clamp to 0 if negative
            if entry_dt <= latest_allowed_entry:
                end_time = start_time + timedelta(minutes=60 * 9) + timedelta(minutes=float_minutes)
            else:
                if int(pid) == 10:
                    end_time = datetime.strptime("16:45", "%H:%M")
                else:
                    end_time = datetime.strptime("17:45", "%H:%M")
                # Mark late entry
                late_by = entry_dt - latest_allowed_entry
                minutes_late = late_by.seconds // 60
                late_sessions.append((pid, date, "Late Entry", entry, minutes_late))
            if exit_dt < end_time:
                early_by = end_time - exit_dt
                minutes_early = early_by.seconds // 60
                late_sessions.append((pid, date, "Early Exit", exit, minutes_early))

    if not late_sessions:
        messagebox.showinfo("Result", "No late entries or early exits found for the selected ID.")
        return

    result_win = Toplevel()
    result_win.title("Late/Early Report")
    result_win.geometry("600x500")

    Label(result_win, text=f"Late/Early records for ID: {pid}", font=("Segoe UI", 12, "bold")).pack(pady=10)

    container = tk.Frame(result_win)
    container.pack(fill='both', expand=True)

    # Canvas + scrollbar for scrolling
    canvas = tk.Canvas(container)
    scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")
        )
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    reason_vars = []

    for i, r in enumerate(late_sessions):
        pid_r, date, status, time, minutes = r
        row_frame = tk.Frame(scrollable_frame)
        row_frame.pack(anchor='w', pady=3, padx=5, fill='x')

        tk.Label(row_frame, text=f"{pid_r} | {date} | {status} at {time} | {minutes} min", width=55, anchor='w').pack(side='left')

        var = StringVar()
        var.set("Select Reason")
        dropdown = OptionMenu(row_frame, var, "Impermissible", "Announced", "Other")
        dropdown.pack(side='right')
        reason_vars.append((var, minutes, pid_r, date, status, time))

    def calculate_times():
        # Check if all reasons are selected
        for var, *_ in reason_vars:
            if var.get() == "Select Reason":
                messagebox.showerror("Error", "Please select a reason for all late/early records before calculating.")
                return

        total_impermissible = 0
        total_announced = 0
        for var, minutes, *_ in reason_vars:
            if var.get() == "Impermissible":
                total_impermissible += minutes
            elif var.get() == "Announced":
                total_announced += minutes
        messagebox.showinfo(
            "Totals",
            f"Total Impermissible time: {total_impermissible} minutes\n"
            f"Total Announced time: {total_announced} minutes"
        )

    def save_report():
        # Check if all reasons are selected
        for var, *_ in reason_vars:
            if var.get() == "Select Reason":
                messagebox.showerror("Error", "Please select a reason for all late/early records before saving.")
                return

        import csv
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save report as"
        )
        if not file_path:
            return

        with open(file_path, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["ID", "Date", "Type", "Time", "Duration (min)", "Reason"])
            for var, minutes, pid_r, date, status, time in reason_vars:
                writer.writerow([pid_r, date, status, time, minutes, var.get()])
        messagebox.showinfo("Saved", f"Report saved successfully to {file_path}")

    btn_frame = tk.Frame(result_win)
    btn_frame.pack(pady=10)

    Button(btn_frame, text="Calculate Times", command=calculate_times, bg="darkblue", fg="white").pack(side='left', padx=5)
    Button(btn_frame, text="Save Report", command=save_report, bg="green", fg="white").pack(side='left', padx=5)

app = Tk()
app.title("Entry-Exit Log Processor")
app.geometry("600x700")
app.configure(bg="#f0f2f5")

style = Style()
style.configure('TButton', font=('Segoe UI', 12), padding=6)

frame = Frame(app, bg="#f0f2f5")
frame.pack(expand=False, pady=10)

Label(frame, text="🕒 Entry-Exit Log Processor", font=("Segoe UI", 16, "bold"), bg="#f0f2f5").pack(pady=10)
Button(frame, text="Select TXT File", command=process_file).pack(pady=5)
Button(frame, text="Export All to CSV", command=save_to_csv).pack(pady=5)

selected_id = StringVar()
selected_id.set("Select ID")
Label(frame, text="Select ID to View Sessions:", bg="#f0f2f5", font=("Segoe UI", 11)).pack(pady=(15, 0))
id_menu = OptionMenu(frame, selected_id, ())
id_menu.pack()
Button(frame, text="Show Selected ID Sessions", command=display_selected_id).pack(pady=5)
Button(frame, text="Edit Fallback Rows", command=edit_fallback).pack(pady=5)
Button(frame, text="Mark 10–18 Days", command=select_unusual_days).pack(pady=5)
Button(frame, text="Check Late/Early Sessions", command=filter_late_early).pack(pady=5)

text_frame = Frame(app)
text_frame.pack(pady=10, padx=20, fill='both', expand=True)

scrollbar = Scrollbar(text_frame, orient=VERTICAL)
text_output = Text(text_frame, wrap='word', yscrollcommand=scrollbar.set, font=('Consolas', 11))
scrollbar.config(command=text_output.yview)
scrollbar.pack(side=RIGHT, fill=Y)
text_output.pack(fill='both', expand=True)

Label(app, text="Created by ChatGPT", font=("Segoe UI", 9), bg="#f0f2f5", fg="#888").pack(side="bottom", pady=10)

app.mainloop()
