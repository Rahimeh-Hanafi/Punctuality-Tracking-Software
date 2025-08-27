import tkinter as tk
from ui.app import LogApp


def main():
    root = tk.Tk()
    app = LogApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
