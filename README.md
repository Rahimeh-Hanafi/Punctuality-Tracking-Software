# Punctuality Tracking Software

An application to process employee entry-exit logs, edit work schedules, and generate reports for late entries and early exits. 

## Features

- Load entry-exit data from TXT files.
- Display sessions for individual employees.
- Edit fallback sessions (paired/unpaired times).
- Customize daily work schedules:
  - Entry time (7:30–10:30 by 30 min steps)
  - Exit time (16:30–18:30 by 30 min steps)
  - Floating hours (0–1.5 h by 0.5 h steps)
  - Allow 10-minute late entry
- Detect late entries and early exits based on work schedules.
- Assign reasons for late/early records and save detailed reports.
- Export all processed data to CSV.


## Project Structure
Punctuality-Tracking-Software/

├── main.py 

├── requirements.txt # Python dependencies

├── sample_data/ # Sample TXT files for testing

├── ui/ # Tkinter UI components

│ ├── init.py

│ └── app.py

├── core/ # Core logic modules

│ ├── init.py

│ ├── processor.py # File processing & CSV export

│ ├── scheduler.py # Work schedule editor

│ └── reports.py # Late/Early report generation

└── resources/ # Constants and assets

│ ├── init.py

│ └── config.py # Default entry/exit times, floating, etc.

