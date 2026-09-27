import os
import sys
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from tkinter import font as tkfont

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_DIR, "monitoring_system"))
sys.path.insert(0, os.path.join(REPO_DIR, "goal_system"))

import goals
from Summary_Reader import DAY_ABBREVIATIONS, format_day_label, get_range_options, load_summary

'''
local tkinter GUI for the goal + monitoring systems (no Pi, no phone). Three screens, switched
from the top bar:
  - Goals (home):   add goals, check them off, delete typos. Done goals sink to the bottom
                    greyed out; overdue not-done goals turn red. See goal_system/goals.py for
                    when a goal moves to history.
  - Goal History:   past goals with their due date and whether they were done on time.
  - Monitoring Data: a dropdown (this week / this month / last 14 days); picking an option
                    jumps straight to a summary of apps + websites for that range, read from the
                    monitoring system's monthly summary CSVs.
Run via RUN_GUI.py at the repo root (or `python gui/app.py`).
'''

WINDOW_TITLE = "Activity Tracker"
DAY_CHECK_MS = 60_000  # how often to check whether the date rolled over while the window is open

COLOR_BG = "#ffffff"
COLOR_TEXT = "#1f1f1f"
COLOR_DONE = "#a0a0a0"
COLOR_OVERDUE = "#c62828"
COLOR_OVERDUE_BG = "#fdecea"
COLOR_ROW_BORDER = "#e6e6e6"
COLOR_MUTED = "#6b6b6b"


def parse_due_date(text, today):
    """Accepts 'YYYY-MM-DD', 'M/D/YYYY', 'M/D/YY', or 'M/D'. 'M/D' means the next time that
    date comes around (this year, or next year if it's already passed)."""
    text = text.strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    parts = text.replace("-", "/").split("/")
    try:
        if len(parts) == 2:
            month, day = int(parts[0]), int(parts[1])
            d = date(today.year, month, day)
            return d if d >= today else date(today.year + 1, month, day)
        if len(parts) == 3:
            month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
            if year < 100:
                year += 2000
            return date(year, month, day)
    except ValueError:
        pass
    raise ValueError(f"Couldn't read due date {text!r}. Use M/D, M/D/YYYY, or YYYY-MM-DD.")


def format_due(d, today):
    """'9/13 Sun' this year, '1/5/2027 Tue' otherwise."""
    if d.year == today.year:
        return format_day_label(d)
    return f"{d.month}/{d.day}/{d.year} {DAY_ABBREVIATIONS[d.weekday()]}"


def format_seconds(seconds):
    """3930 -> '1h 05m', 300 -> '5m', 20 -> '<1m'"""
    hours, remainder = divmod(int(seconds), 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m"
    return "<1m"


class ScrollableFrame(ttk.Frame):
    """A vertically scrollable area; put child widgets in self.inner. Mouse wheel scrolls it
    while the pointer is over it."""

    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg=COLOR_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=COLOR_BG)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._window, width=e.width))
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")

    def _on_mousewheel(self, event):
        # the wheel event goes to whatever widget is under the pointer (a row label, checkbox, ...),
        # so check that it's inside this frame rather than relying on <Enter>/<Leave>
        hovered = self.winfo_containing(event.x_root, event.y_root)
        if hovered is None or not str(hovered).startswith(str(self)):
            return
        # only scroll when the content is taller than the visible area
        if self.inner.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def clear(self):
        for child in self.inner.winfo_children():
            child.destroy()
        self.canvas.yview_moveto(0)


class HomeScreen(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._check_vars = []  # keep IntVars alive; tkinter drops the checkbox state if they're GC'd

        ttk.Label(self, text="Goals", style="Heading.TLabel").pack(anchor="w", padx=16, pady=(12, 6))

        add_row = ttk.Frame(self)
        add_row.pack(fill="x", padx=16, pady=(0, 4))
        ttk.Label(add_row, text="New goal").grid(row=0, column=0, sticky="w")
        self.name_entry = ttk.Entry(add_row)
        self.name_entry.grid(row=0, column=1, sticky="ew", padx=(6, 12))
        ttk.Label(add_row, text="Due").grid(row=0, column=2, sticky="w")
        self.due_entry = ttk.Entry(add_row, width=12)
        self.due_entry.grid(row=0, column=3, padx=(6, 12))
        ttk.Button(add_row, text="Add", command=self._add).grid(row=0, column=4)
        add_row.columnconfigure(1, weight=1)
        for entry in (self.name_entry, self.due_entry):
            entry.bind("<Return>", lambda e: self._add())

        self.message = ttk.Label(self, text="Due date: M/D, M/D/YYYY, or YYYY-MM-DD", style="Muted.TLabel")
        self.message.pack(anchor="w", padx=16, pady=(0, 8))

        self.list = ScrollableFrame(self)
        self.list.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    def _add(self):
        name = self.name_entry.get().strip()
        if not name:
            self._show_message("Type a goal name first.", error=True)
            return
        try:
            due = parse_due_date(self.due_entry.get(), self.app.today)
        except ValueError as e:
            self._show_message(str(e), error=True)
            return
        goals.add_goal(name, due)
        self.name_entry.delete(0, "end")
        self.due_entry.delete(0, "end")
        self.name_entry.focus_set()
        self._show_message(f"Added \"{name}\" (due {format_due(due, self.app.today)}).")
        self.refresh()

    def _show_message(self, text, error=False):
        self.message.configure(text=text, style="Error.TLabel" if error else "Muted.TLabel")

    def _toggle(self, goal_id, var):
        goals.set_done(goal_id, bool(var.get()), self.app.today)
        self.refresh()

    def _delete(self, goal):
        if messagebox.askyesno("Delete goal", f"Delete \"{goal['name']}\"? This can't be undone.", parent=self):
            goals.delete_goal(goal["id"])
            self.refresh()

    def refresh(self):
        today = self.app.today
        self.list.clear()
        self._check_vars = []
        active = goals.get_active_goals(today)

        if not active:
            tk.Label(self.list.inner, text="No goals yet. Add one above.", bg=COLOR_BG, fg=COLOR_MUTED,
                     font=self.app.body_font).pack(anchor="w", pady=12)
            return

        for goal in active:
            overdue = goals.is_overdue(goal, today)
            fg = COLOR_DONE if goal["done"] else COLOR_OVERDUE if overdue else COLOR_TEXT
            bg = COLOR_OVERDUE_BG if overdue else COLOR_BG

            border = tk.Frame(self.list.inner, bg=COLOR_ROW_BORDER)
            border.pack(fill="x", pady=(0, 1))
            row = tk.Frame(border, bg=bg, padx=6, pady=6)
            row.pack(fill="x")

            var = tk.IntVar(value=1 if goal["done"] else 0)
            self._check_vars.append(var)
            tk.Checkbutton(row, variable=var, bg=bg, activebackground=bg,
                           command=lambda gid=goal["id"], v=var: self._toggle(gid, v)).grid(row=0, column=0)

            tk.Label(row, text=goal["name"], bg=bg, fg=fg, font=self.app.body_font, anchor="w",
                     justify="left", wraplength=520).grid(row=0, column=1, sticky="ew", padx=(4, 12))

            due_text = format_due(goals.due_date_of(goal), today)
            if overdue:
                due_text += "  (overdue)"
            tk.Label(row, text=due_text, bg=bg, fg=fg, font=self.app.body_font).grid(row=0, column=2, padx=(0, 8))

            tk.Button(row, text="✕", relief="flat", bd=0, bg=bg, fg=COLOR_MUTED, activebackground=bg,
                      cursor="hand2", command=lambda g=goal: self._delete(g)).grid(row=0, column=3)
            row.columnconfigure(1, weight=1)


class HistoryScreen(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        ttk.Label(self, text="Goal History", style="Heading.TLabel").pack(anchor="w", padx=16, pady=(12, 6))
        self.summary = ttk.Label(self, style="Muted.TLabel")
        self.summary.pack(anchor="w", padx=16, pady=(0, 8))

        table = ttk.Frame(self)
        table.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.tree = ttk.Treeview(table, columns=("name", "due", "on_time"), show="headings")
        self.tree.heading("name", text="Goal", anchor="w")
        self.tree.heading("due", text="Due date", anchor="w")
        self.tree.heading("on_time", text="Done on time?", anchor="w")
        self.tree.column("name", width=420, anchor="w")
        self.tree.column("due", width=150, anchor="w", stretch=False)
        self.tree.column("on_time", width=150, anchor="w", stretch=False)
        self.tree.tag_configure("late", foreground=COLOR_OVERDUE)
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def refresh(self):
        today = self.app.today
        self.tree.delete(*self.tree.get_children())
        history = goals.get_history_goals(today)
        on_time_count = 0
        for goal in history:
            on_time = goals.was_on_time(goal)
            on_time_count += on_time
            self.tree.insert("", "end", values=(
                goal["name"],
                format_due(goals.due_date_of(goal), today),
                "Yes" if on_time else "No (late)",
            ), tags=() if on_time else ("late",))
        if history:
            self.summary.configure(text=f"{on_time_count} of {len(history)} done on time")
        else:
            self.summary.configure(text="No past goals yet. Done goals show up here once their due date passes.")


class MonitoringScreen(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        self.heading = ttk.Label(self, text="Monitoring Data", style="Heading.TLabel")
        self.heading.pack(anchor="w", padx=16, pady=(12, 6))
        self.summary = ttk.Label(self, style="Muted.TLabel")
        self.summary.pack(anchor="w", padx=16, pady=(0, 8))

        table = ttk.Frame(self)
        table.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.tree = ttk.Treeview(table, columns=("name", "kind", "time"), show="headings")
        self.tree.heading("name", text="App / Website", anchor="w")
        self.tree.heading("kind", text="Type", anchor="w")
        self.tree.heading("time", text="Time", anchor="e")
        self.tree.column("name", width=420, anchor="w")
        self.tree.column("kind", width=110, anchor="w", stretch=False)
        self.tree.column("time", width=120, anchor="e", stretch=False)
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def show_range(self, label, start, end):
        today = self.app.today
        if start == end:
            self.heading.configure(text=f"Monitoring Data: {format_due(start, today)}")
        else:
            self.heading.configure(text=f"Monitoring Data: {label} ({format_due(start, today)} – {format_due(end, today)})")

        entries, days_with_data = load_summary(start, end)
        self.tree.delete(*self.tree.get_children())
        for entry in entries:
            self.tree.insert("", "end", values=(entry["name"], entry["kind"], format_seconds(entry["seconds"])))

        if entries:
            total = sum(e["seconds"] for e in entries)
            day_word = "day" if len(days_with_data) == 1 else "days"
            self.summary.configure(text=f"Total {format_seconds(total)} across {len(days_with_data)} {day_word} "
                                        f"with data. Today isn't included until it's summarized after midnight.")
        else:
            self.summary.configure(text="No summarized data for this range. Days get summarized after they end "
                                        "(at midnight, or the next time the tracker starts).")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(WINDOW_TITLE)
        self.geometry("860x640")
        self.minsize(640, 420)
        self.today = date.today()

        self._setup_styles()

        top_bar = ttk.Frame(self, padding=(12, 10))
        top_bar.pack(fill="x")
        ttk.Button(top_bar, text="Goals", command=self.show_home).pack(side="left")
        ttk.Button(top_bar, text="Goal History", command=self.show_history).pack(side="left", padx=(8, 0))

        # clicking opens the dropdown; picking an option goes straight to that summary
        self.monitoring_menu = tk.Menu(self, tearoff=False, postcommand=self._build_monitoring_menu)
        ttk.Menubutton(top_bar, text="Monitoring Data", menu=self.monitoring_menu,
                       direction="below").pack(side="left", padx=(8, 0))
        ttk.Separator(self, orient="horizontal").pack(fill="x")

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        self.home = HomeScreen(container, self)
        self.history = HistoryScreen(container, self)
        self.monitoring = MonitoringScreen(container, self)
        for screen in (self.home, self.history, self.monitoring):
            screen.grid(row=0, column=0, sticky="nsew")

        self.current = None
        self.show_home()
        self.after(DAY_CHECK_MS, self._check_day)

    def _setup_styles(self):
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(name).configure(size=11)
        self.body_font = tkfont.nametofont("TkDefaultFont")
        style = ttk.Style(self)
        style.configure("Heading.TLabel", font=(self.body_font.actual("family"), 16, "bold"))
        style.configure("Muted.TLabel", foreground=COLOR_MUTED)
        style.configure("Error.TLabel", foreground=COLOR_OVERDUE)
        style.configure("Treeview", rowheight=28)
        style.configure("Treeview.Heading", font=(self.body_font.actual("family"), 11, "bold"))

    def _build_monitoring_menu(self):
        # rebuilt every time it opens so the date list stays current if the window is left open
        self.monitoring_menu.delete(0, "end")
        for i, (label, start, end) in enumerate(get_range_options(self.today)):
            if i == 2:
                self.monitoring_menu.add_separator()
            self.monitoring_menu.add_command(
                label=label, command=lambda l=label, s=start, e=end: self.show_monitoring(l, s, e))

    def _show(self, screen):
        self.current = screen
        screen.tkraise()

    def show_home(self):
        self.home.refresh()
        self._show(self.home)

    def show_history(self):
        self.history.refresh()
        self._show(self.history)

    def show_monitoring(self, label, start, end):
        self.monitoring.show_range(label, start, end)
        self._show(self.monitoring)

    def _check_day(self):
        """If the window stays open past midnight, re-sort goals (turn overdue ones red,
        move finished ones to history)."""
        if date.today() != self.today:
            self.today = date.today()
            if self.current in (self.home, self.history):
                self.current.refresh()
        self.after(DAY_CHECK_MS, self._check_day)


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
