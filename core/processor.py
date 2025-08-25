import csv
from collections import defaultdict
from tkinter import filedialog, messagebox

def process_file(app):
    txt_path = filedialog.askopenfilename(
        title="Select Entry-Exit TXT File",
        filetypes=[("Text files", "*.txt")]
    )
    if not txt_path:
        return

    app.records = defaultdict(lambda: defaultdict(list))
    app.sessions.clear()

    try:
        with open(txt_path, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) != 4:
                    continue
                person_id, date, time, _ = parts
                app.records[person_id][date].append(time)
    except Exception as e:
        messagebox.showerror("Error", f"Could not read file:\n{e}")
        return

    for person_id, dates in app.records.items():
        for date, times in dates.items():
            sorted_times = sorted(times)
            if len(sorted_times) % 2 == 0:
                for i in range(0, len(sorted_times), 2):
                    app.sessions.append([person_id, date, sorted_times[i], sorted_times[i+1], "paired"])
            else:
                app.sessions.append([person_id, date, sorted_times[0], sorted_times[-1], "fallback"])

    ids = sorted(app.records.keys())
    app.selected_id.set(ids[0] if ids else "")
    app.id_menu = None  # can be wired to OptionMenu if needed
    app.display_selected_id()

def save_to_csv(app):
    if not app.sessions:
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
        with open(csv_path, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Date", "Entry", "Exit", "Mode"])
            writer.writerows(app.sessions)
        messagebox.showinfo("Success", f"CSV file saved to: {csv_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Could not save CSV:\n{e}")