import tkinter as tk
from tkinter import messagebox, filedialog
from datetime import datetime
import math

# ===================== THEME =====================

BG = "#080B14"
SIDEBAR = "#0D1221"
CARD = "#111827"
CARD2 = "#151D30"
BORDER = "#253149"

WHITE = "#F4F7FF"
MUTED = "#8794AD"
PURPLE = "#8B5CF6"
PURPLE_HOVER = "#A78BFA"
GREEN = "#22D3A6"
RED = "#FB7185"
BLUE = "#60A5FA"
YELLOW = "#FBBF24"

FONT = "Segoe UI"

root = tk.Tk()
root.title("Freelancer | Profit Analyzer")
root.geometry("1220x850")
root.minsize(980, 720)
root.configure(bg=BG)

# ===================== HELPERS =====================

def make_label(parent, text, size=10, color=WHITE, bold=False, bg=None, **kwargs):

    return tk.Label(
        parent,
        text=text,
        font=(FONT, size, "bold" if bold else "normal"),
        fg=color,
        bg=bg or parent.cget("bg"),
        **kwargs
    )


def make_card(parent, bg=CARD):
    return tk.Frame(
        parent,
        bg=bg,
        highlightbackground=BORDER,
        highlightthickness=1
    )


def money(value):
    return f"৳ {value:,.2f}".replace(".00", "")


def style_button(parent, text, command, bg=PURPLE, fg=WHITE, hover=None):

    hover = hover or PURPLE_HOVER

    button = tk.Button(
        parent,
        text=text,
        command=command,
        font=(FONT, 10, "bold"),
        bg=bg,
        fg=fg,
        activebackground=hover,
        activeforeground=WHITE,
        relief="flat",
        bd=0,
        cursor="hand2",
        highlightthickness=0,
        padx=15,
        pady=10
    )

    button.bind(
        "<Enter>",
        lambda event: button.configure(bg=hover)
    )
    button.bind(
        "<Leave>",
        lambda event: button.configure(bg=bg)
    )

    return button


# ===================== MAIN LAYOUT =====================

app = tk.Frame(root, bg=BG)
app.pack(fill="both", expand=True)

sidebar = tk.Frame(app, bg=SIDEBAR, width=205)
sidebar.pack(side="left", fill="y")
sidebar.pack_propagate(False)

main = tk.Frame(app, bg=BG)
main.pack(side="left", fill="both", expand=True)

# ===================== SIDEBAR =====================

brand = tk.Frame(sidebar, bg=SIDEBAR)
brand.pack(fill="x", padx=20, pady=(27, 32))

logo = tk.Frame(brand, bg=PURPLE, width=43, height=43)
logo.pack(anchor="w")
logo.pack_propagate(False)

make_label(
    logo, "F", 23, WHITE, True, PURPLE
).place(relx=0.5, rely=0.5, anchor="center")

make_label(
    brand, "Freelancer", 18, WHITE, True, SIDEBAR
).pack(anchor="w", pady=(12, 0))

make_label(
    brand, "PROFIT ANALYZER", 8, PURPLE_HOVER, True, SIDEBAR
).pack(anchor="w", pady=(3, 0))

make_label(
    sidebar, "WORKSPACE", 8, MUTED, True, SIDEBAR
).pack(anchor="w", padx=22, pady=(0, 10))

nav_buttons = {}

def set_active_nav(name):
    for item, button in nav_buttons.items():
        if item == name:
            button.config(bg="#292044", fg=PURPLE_HOVER)
        else:
            button.config(bg=SIDEBAR, fg=MUTED)


def create_nav(text, icon, command, active=False):
    button = tk.Button(
        sidebar,
        text=f"  {icon}    {text}",
        font=(FONT, 10, "bold" if active else "normal"),
        anchor="w",
        bg="#292044" if active else SIDEBAR,
        fg=PURPLE_HOVER if active else MUTED,
        activebackground="#292044",
        activeforeground=WHITE,
        relief="flat",
        bd=0,
        cursor="hand2",
        padx=14,
        pady=13,
        command=command
    )
    button.pack(fill="x", padx=10, pady=3)
    nav_buttons[text] = button
    return button


# ===================== HEADER =====================

content = tk.Frame(main, bg=BG)
content.pack(fill="both", expand=True, padx=24, pady=(20, 14))

header = tk.Frame(content, bg=BG)
header.pack(fill="x", pady=(0, 18))

header_left = tk.Frame(header, bg=BG)
header_left.pack(side="left", fill="x", expand=True)

make_label(
    header_left, "Good to see you 👋", 10, PURPLE_HOVER, True, BG
).pack(anchor="w")

make_label(
    header_left, "Freelancer Dashboard", 23, WHITE, True, BG
).pack(anchor="w", pady=(3, 2))

make_label(
    header_left,
    "Track your earnings. Understand your growth.",
    10, MUTED, False, BG
).pack(anchor="w")

date_card = make_card(header, CARD2)
date_card.pack(side="right", anchor="center")

make_label(
    date_card, "TODAY", 8, MUTED, True, CARD2
).pack(anchor="w", padx=14, pady=(9, 1))

make_label(
    date_card,
    datetime.now().strftime("%d %b %Y"),
    10, WHITE, True, CARD2
).pack(anchor="w", padx=14, pady=(0, 9))

# ===================== TOP GRID =====================

top = tk.Frame(content, bg=BG)
top.pack(fill="x")

top.grid_columnconfigure(0, weight=6)
top.grid_columnconfigure(1, weight=4)

# ===================== INPUT CARD =====================

form_card = make_card(top)
form_card.grid(
    row=0, column=0,
    sticky="nsew",
    padx=(0, 8)
)

form_header = tk.Frame(form_card, bg=CARD)
form_header.pack(fill="x", padx=18, pady=(16, 14))

make_label(
    form_header, "01", 9, PURPLE_HOVER, True, CARD
).pack(side="left")

make_label(
    form_header, "  Project Overview", 13, WHITE, True, CARD
).pack(side="left")

make_label(
    form_header, "EDIT DETAILS", 8, MUTED, True, CARD
).pack(side="right")

form = tk.Frame(form_card, bg=CARD)
form.pack(fill="x", padx=18)

form.grid_columnconfigure(0, weight=1)
form.grid_columnconfigure(1, weight=1)


def create_input(parent, title, default, row, column):
    wrapper = tk.Frame(parent, bg=CARD)

    make_label(
        wrapper, title, 9, MUTED, True, CARD
    ).pack(anchor="w", pady=(0, 6))

    variable = tk.StringVar(value=default)

    entry = tk.Entry(
        wrapper,
        textvariable=variable,
        font=(FONT, 11),
        bg=CARD2,
        fg=WHITE,
        insertbackground=WHITE,
        selectbackground=PURPLE,
        selectforeground=WHITE,
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=PURPLE
    )

    entry.pack(fill="x", ipady=10)

    wrapper.grid(
        row=row,
        column=column,
        sticky="ew",
        padx=(0, 9) if column == 0 else (9, 0),
        pady=(0, 12)
    )

    return variable, entry


name_var, name_entry = create_input(
    form, "Freelancer Name", "Rafiul Talukdar", 0, 0
)

projects_var, projects_entry = create_input(
    form, "Completed Projects", "10", 0, 1
)

income_var, income_entry = create_input(
    form, "Total Income (BDT)", "50000", 1, 0
)

expenses_var, expenses_entry = create_input(
    form, "Total Expenses (BDT)", "12000", 1, 1
)

button_row = tk.Frame(form_card, bg=CARD)
button_row.pack(fill="x", padx=18, pady=(0, 17))

# ===================== PROGRESS CARD =====================

progress_card = make_card(top, CARD2)
progress_card.grid(
    row=0, column=1,
    sticky="nsew",
    padx=(8, 0)
)

make_label(
    progress_card, "02  /  PROFIT MARGIN",
    9, MUTED, True, CARD2
).pack(anchor="w", padx=18, pady=(17, 0))

ring = tk.Canvas(
    progress_card,
    width=190,
    height=170,
    bg=CARD2,
    highlightthickness=0
)
ring.pack(pady=(0, 0))

ring.create_oval(
    27, 10, 163, 146,
    outline="#28344D",
    width=12
)

progress_arc = ring.create_arc(
    27, 10, 163, 146,
    start=90,
    extent=-273.6,
    style="arc",
    outline=GREEN,
    width=12
)

ring_percent = ring.create_text(
    95, 69,
    text="76%",
    fill=WHITE,
    font=(FONT, 25, "bold")
)

ring.create_text(
    95, 97,
    text="PROFIT MARGIN",
    fill=MUTED,
    font=(FONT, 8, "bold")
)

ring_status = make_label(
    progress_card,
    "●  Profitable",
    9, GREEN, True, "#10352F"
)
ring_status.pack(pady=(0, 16), ipadx=13, ipady=8)

# ===================== METRIC CARDS =====================

metrics = tk.Frame(content, bg=BG)
metrics.pack(fill="x", pady=16)

for column in range(4):
    metrics.grid_columnconfigure(column, weight=1)

metric_specs = [
    ("TOTAL INCOME", "৳ 50,000", GREEN, "#102D2C", "↗"),
    ("TOTAL EXPENSES", "৳ 12,000", RED, "#321D2A", "↘"),
    ("NET PROFIT", "৳ 38,000", BLUE, "#162748", "✦"),
    ("PROFIT MARGIN", "76%", PURPLE_HOVER, "#251D43", "%")
]

metric_values = []

for i, (title, value, accent, card_bg, icon) in enumerate(metric_specs):
    card = make_card(metrics, card_bg)
    card.grid(
        row=0, column=i, sticky="nsew",
        padx=(0 if i == 0 else 5, 5 if i < 3 else 0)
    )

    top_line = tk.Frame(card, bg=card_bg)
    top_line.pack(fill="x", padx=13, pady=(13, 5))

    make_label(
        top_line, title, 8, MUTED, True, card_bg
    ).pack(side="left")

    make_label(
        top_line, icon, 13, accent, True, card_bg
    ).pack(side="right")

    value_label = make_label(
        card, value, 13, WHITE, True, card_bg
    )
    value_label.pack(anchor="w", padx=13, pady=(5, 14))

    metric_values.append(value_label)

# ===================== BOTTOM GRID =====================

bottom = tk.Frame(content, bg=BG)
bottom.pack(fill="both", expand=True)

bottom.grid_columnconfigure(0, weight=6)
bottom.grid_columnconfigure(1, weight=4)
bottom.grid_rowconfigure(0, weight=1)

# ===================== CHART =====================

chart_card = make_card(bottom)
chart_card.grid(
    row=0, column=0,
    sticky="nsew",
    padx=(0, 8)
)

chart_header = tk.Frame(chart_card, bg=CARD)
chart_header.pack(fill="x", padx=16, pady=(15, 0))

make_label(
    chart_header, "Income vs Expenses", 12, WHITE, True, CARD
).pack(side="left")

make_label(
    chart_header, "LIVE OVERVIEW", 8, GREEN, True, CARD
).pack(side="right")

chart = tk.Canvas(
    chart_card,
    bg=CARD,
    highlightthickness=0
)
chart.pack(fill="both", expand=True, padx=10, pady=10)

# ===================== RIGHT PANELS =====================

right = tk.Frame(bottom, bg=BG)
right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

right.grid_columnconfigure(0, weight=1)
right.grid_rowconfigure(0, weight=1)
right.grid_rowconfigure(1, weight=1)

# Status panel
status_card = make_card(right)
status_card.grid(
    row=0, column=0,
    sticky="nsew",
    pady=(0, 6)
)

make_label(
    status_card, "Profit Status", 12, WHITE, True, CARD
).pack(anchor="w", padx=15, pady=(13, 10))

status_box = tk.Frame(
    status_card,
    bg="#10352F",
    highlightbackground="#176C59",
    highlightthickness=1
)
status_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

status_title = make_label(
    status_box, "Looking good!", 13, GREEN, True, "#10352F"
)
status_title.pack(anchor="w", padx=12, pady=(11, 4))

status_desc = make_label(
    status_box,
    "Your income is higher than your expenses.",
    9, "#B6F4E5", False, "#10352F",
    wraplength=300,
    justify="left"
)
status_desc.pack(anchor="w", padx=12, pady=(0, 11))

# Quick summary panel
quick_card = make_card(right)
quick_card.grid(
    row=1, column=0,
    sticky="nsew",
    pady=(6, 0)
)

make_label(
    quick_card, "Quick Summary", 12, WHITE, True, CARD
).pack(anchor="w", padx=15, pady=(12, 5))

quick_values = []

for title in [
    "Freelancer",
    "Completed Projects",
    "Total Income",
    "Total Expenses",
    "Net Profit"
]:
    row = tk.Frame(quick_card, bg=CARD)
    row.pack(fill="x", padx=15, pady=3)

    make_label(
        row, title, 9, MUTED, False, CARD
    ).pack(side="left")

    value = make_label(
        row, "-", 9, WHITE, True, CARD
    )
    value.pack(side="right")

    quick_values.append(value)

# ===================== CHART DRAWING =====================

def draw_chart(income, expenses):
    chart.delete("all")

    width = max(chart.winfo_width(), 320)
    height = max(chart.winfo_height(), 200)

    left = 48
    right_edge = width - 18
    top_edge = 22
    bottom_edge = height - 35

    plot_height = bottom_edge - top_edge
    plot_width = right_edge - left

    maximum = max(income, expenses, 1) * 1.2

    # Horizontal grid
    for i in range(6):
        value = maximum * i / 5
        y = bottom_edge - plot_height * i / 5

        chart.create_line(
            left, y, right_edge, y,
            fill=BORDER,
            width=1
        )

        tick = (
            f"{value / 1000:.0f}k"
            if value >= 1000
            else f"{value:.0f}"
        )

        chart.create_text(
            left - 8, y,
            text=tick,
            fill=MUTED,
            font=(FONT, 8),
            anchor="e"
        )

    # Bar positions
    
    centers = [
        left + plot_width * 0.32,
        left + plot_width * 0.72
    ]

    bar_width = min(62, plot_width * 0.22)

    for center, value, color, title in [
        (centers[0], income, GREEN, "Income"),
        (centers[1], expenses, RED, "Expenses")
    ]:
        bar_height = (value / maximum) * plot_height
        x1 = center - bar_width / 2
        x2 = center + bar_width / 2
        y1 = bottom_edge - bar_height

        chart.create_rectangle(
            x1, y1, x2, bottom_edge,
            fill=color,
            outline=""
        )

        chart.create_text(
            center,
            max(top_edge + 9, y1 - 12),
            text=f"{value:,.0f}",
            fill=WHITE,
            font=(FONT, 9, "bold")
        )

        chart.create_text(
            center, bottom_edge + 17,
            text=title,
            fill=MUTED,
            font=(FONT, 9)
        )

# ===================== DYNAMIC CALCULATIONS =====================

def analyze_profit():
    try:
        name = name_var.get().strip() or "Freelancer"
        projects_text = projects_var.get().strip()
        income_text = income_var.get().strip()
        expenses_text = expenses_var.get().strip()

        if not projects_text or not income_text or not expenses_text:
            raise ValueError("Please fill in all numeric fields.")

        projects = int(projects_text)
        income = float(income_text)
        expenses = float(expenses_text)

        if not all(map(math.isfinite, [income, expenses])):
            raise ValueError("Please enter finite numbers.")

        if projects < 0 or income < 0 or expenses < 0:
            raise ValueError("Negative values are not allowed.")

        profit = income - expenses

        margin = (
            profit / income * 100
            if income > 0
            else 0
        )

        # Update metric cards
        metric_values[0].config(text=money(income))
        metric_values[1].config(text=money(expenses))
        metric_values[2].config(
            text=money(profit),
            fg=GREEN if profit >= 0 else RED
        )
        metric_values[3].config(text=f"{margin:.1f}%")

        # Update circular progress
        visible_margin = max(0, min(100, margin))

        ring.itemconfigure(
            progress_arc,
            extent=-360 * visible_margin / 100,
            outline=GREEN if profit >= 0 else RED
        )

        ring.itemconfigure(
            ring_percent,
            text=f"{margin:.1f}%"
        )

        # Update status
        if profit > 0:
            color_bg = "#10352F"
            accent = GREEN

            status_title.config(
                text="✓  Profitable",
                fg=GREEN
            )
            status_desc.config(
                text=f"Great work, {name}! Income exceeds expenses."
            )
            ring_status.config(
                text="●  Profitable",
                fg=GREEN,
                bg=color_bg
            )

        elif profit < 0:
            color_bg = "#321D2A"
            accent = RED

            status_title.config(
                text="!  Loss detected",
                fg=RED
            )
            status_desc.config(
                text=f"{name}, your expenses exceed your income."
            )
            ring_status.config(
                text="●  Needs attention",
                fg=RED,
                bg=color_bg
            )

        else:
            color_bg = "#251D43"
            accent = PURPLE_HOVER

            status_title.config(
                text="=  Break-even",
                fg=PURPLE_HOVER
            )
            status_desc.config(
                text=f"{name}, income equals expenses."
            )
            ring_status.config(
                text="●  Break-even",
                fg=PURPLE_HOVER,
                bg=color_bg
            )

        status_box.config(
            bg=color_bg,
            highlightbackground=accent
        )
        status_title.config(bg=color_bg)
        status_desc.config(bg=color_bg)

        # Update quick summary
        values = [
            name,
            str(projects),
            money(income),
            money(expenses),
            money(profit)
        ]

        for widget, value in zip(quick_values, values):
            widget.config(text=value)

        # Redraw chart
        draw_chart(income, expenses)

        make_label_text = (
            f"Last analyzed: {datetime.now().strftime('%I:%M %p')}"
        )
        footer_status.config(text=make_label_text)

    except (ValueError, OverflowError) as error:
        messagebox.showerror(
            "Check your input",
            str(error) or "Please enter valid numbers."
        )


# ===================== RESET =====================

def reset_form():
    name_var.set("")
    projects_var.set("0")
    income_var.set("0")
    expenses_var.set("0")

    analyze_profit()
    name_entry.focus_set()


# ===================== EXPORT REPORT =====================

def export_report():
    try:
        name = name_var.get().strip() or "Freelancer"
        projects = int(projects_var.get())
        income = float(income_var.get())
        expenses = float(expenses_var.get())

        if projects < 0 or income < 0 or expenses < 0:
            raise ValueError

        profit = income - expenses
        margin = profit / income * 100 if income else 0

        if profit > 0:
            status = "Profitable"
        elif profit < 0:
            status = "Loss"
        else:
            status = "Break-even"

        report = (
            "FREELANCER PROFIT ANALYZER\n"
            "==========================\n\n"
            f"Generated: {datetime.now():%d %b %Y, %I:%M %p}\n"
            f"Freelancer: {name}\n"
            f"Completed Projects: {projects}\n\n"
            f"Total Income: {money(income)}\n"
            f"Total Expenses: {money(expenses)}\n"
            f"Net Profit/Loss: {money(profit)}\n"
            f"Profit Margin: {margin:.2f}%\n"
            f"Status: {status}\n"
        )

        path = filedialog.asksaveasfilename(
            title="Export Profit Report",
            defaultextension=".txt",
            filetypes=[("Text Report", "*.txt")],
            initialfile="freelancer_profit_report.txt"
        )

        if path:
            with open(path, "w", encoding="utf-8") as file:
                file.write(report)

            messagebox.showinfo(
                "Report Saved",
                "Your report was exported successfully."
            )

    except (ValueError, OverflowError):
        messagebox.showerror(
            "Invalid Input",
            "Please enter valid project, income and expense values."
        )


# ===================== BUTTONS =====================

style_button(
    button_row,
    "✦  Analyze Profit",
    analyze_profit
).pack(side="left", fill="x", expand=True, padx=(0, 5))

style_button(
    button_row,
    "↻  Reset",
    reset_form,
    bg=CARD2,
    hover="#303B52"
).pack(side="left", padx=5)

style_button(
    button_row,
    "↓  Export",
    export_report,
    bg="#183A35",
    hover="#23584D"
).pack(side="left", padx=(5, 0))


# ===================== FOOTER =====================

footer = tk.Frame(
    content,
    bg="#17152C",
    highlightbackground="#342B55",
    highlightthickness=1
)
footer.pack(fill="x", pady=(13, 0))

footer_status = make_label(
    footer,
    "Ready to analyze your earnings",
    9, PURPLE_HOVER, False, "#17152C"
)
footer_status.pack(side="left", padx=13, pady=10)

make_label(
    footer,
    "PLAN  •  TRACK  •  GROW",
    8, MUTED, True, "#17152C"
).pack(side="right", padx=13)


# ===================== NAVIGATION =====================

def go_dashboard():
    set_active_nav("Dashboard")
    name_entry.focus_set()


def go_reports():
    set_active_nav("Reports")
    export_report()


def go_settings():
    set_active_nav("Settings")

    settings = tk.Toplevel(root)
    settings.title("Settings")
    settings.geometry("330x200")
    settings.resizable(False, False)
    settings.configure(bg=BG)
    settings.transient(root)

    make_label(
        settings, "Dashboard Settings", 16, WHITE, True, BG
    ).pack(anchor="w", padx=22, pady=(22, 10))

    make_label(
        settings,
        "Currency: BDT (Bangladeshi Taka)\n"
        "Theme: Dark / Purple\n"
        "Reports: Export as TXT",
        10, MUTED, False, BG,
        justify="left"
    ).pack(anchor="w", padx=22, pady=5)

    style_button(
        settings,
        "Close",
        settings.destroy
    ).pack(anchor="e", padx=22, pady=12)


create_nav("Dashboard", "▦", go_dashboard, active=True)
create_nav("Reports", "▤", go_reports)
create_nav("Settings", "⚙", go_settings)

# ===================== INITIALIZE =====================

chart.bind(
    "<Configure>",
    lambda event: draw_chart(
        float(income_var.get() or 0),
        float(expenses_var.get() or 0)
    )
)

root.bind("<Return>", lambda event: analyze_profit())

root.after(150, analyze_profit)

root.mainloop()