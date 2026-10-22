import tkinter as tk
import ast
import operator

# ==================== WINDOW ====================

root = tk.Tk()
root.title("Smart Calculator")
root.geometry("360x560")
root.resizable(False, False)
root.configure(bg="#0B0F19")

# ==================== COLORS ====================

BG = "#0B0F19"
CARD = "#151B2B"
DISPLAY_BG = "#101625"
TEXT = "#F1F5F9"
MUTED = "#8B95AA"

PURPLE = "#8B5CF6"
PURPLE_HOVER = "#A78BFA"

BTN = "#20283A"
BTN_HOVER = "#303B52"

OPERATOR = "#30234D"
OPERATOR_HOVER = "#49346F"

DANGER = "#4A2435"
DANGER_HOVER = "#713047"

# ==================== HEADER ====================

header = tk.Frame(root, bg=BG)
header.pack(fill="x", padx=24, pady=(18, 10))

tk.Label(
    header,
    text="SMART",
    font=("Segoe UI", 11, "bold"),
    fg=PURPLE_HOVER,
    bg=BG
).pack(anchor="w")

tk.Label(
    header,
    text="Calculator",
    font=("Segoe UI", 22, "bold"),
    fg=TEXT,
    bg=BG
).pack(anchor="w")

# ==================== MAIN CARD ====================

card = tk.Frame(root, bg=CARD)
card.pack(fill="both", expand=True, padx=16, pady=(4, 16))

# ==================== DISPLAY ====================

display_frame = tk.Frame(card, bg=DISPLAY_BG)
display_frame.pack(fill="x", padx=12, pady=12)

history_label = tk.Label(
    display_frame,
    text="Ready to calculate",
    font=("Segoe UI", 10),
    fg=MUTED,
    bg=DISPLAY_BG,
    anchor="e"
)
history_label.pack(fill="x", padx=14, pady=(12, 2))

display_var = tk.StringVar(value="0")

display = tk.Entry(
    display_frame,
    textvariable=display_var,
    font=("Segoe UI", 28, "bold"),
    bg=DISPLAY_BG,
    fg=TEXT,
    disabledbackground=DISPLAY_BG,
    disabledforeground=TEXT,
    insertbackground=TEXT,
    selectbackground=PURPLE,
    selectforeground=TEXT,
    readonlybackground=DISPLAY_BG,
    justify="right",
    relief="flat",
    bd=0,
    highlightthickness=0,
    state="readonly"
)
display.pack(fill="x", padx=14, pady=(2, 16), ipady=5)

# ==================== SAFE CALCULATION ====================

allowed_operators = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg
}

def safe_calculate(expression):
    tree = ast.parse(expression, mode="eval")

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)

        if isinstance(node, ast.Constant):
            if type(node.value) in (int, float):
                return node.value
            raise ValueError("Invalid value")

        if isinstance(node, ast.BinOp):
            op_type = type(node.op)

            if op_type not in allowed_operators:
                raise ValueError("Invalid operator")

            left = evaluate(node.left)
            right = evaluate(node.right)

            return allowed_operators[op_type](left, right)

        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)

            if op_type not in allowed_operators:
                raise ValueError("Invalid operator")

            return allowed_operators[op_type](evaluate(node.operand))

        raise ValueError("Invalid expression")

    return evaluate(tree)

# ==================== BUTTON LOGIC ====================

expression = ""
just_calculated = False

def update_display():
    display_var.set(expression if expression else "0")

def press(value):
    global expression, just_calculated

    if value == "C":
        expression = ""
        just_calculated = False
        history_label.config(text="Cleared")

    elif value == "DEL":
        if just_calculated:
            expression = ""
            just_calculated = False
        else:
            expression = expression[:-1]

        history_label.config(text="")

    elif value == "=":
        if not expression:
            return

        try:
            original = expression
            result = safe_calculate(expression)

            if isinstance(result, float):
                if not (float("-inf") < result < float("inf")):
                    raise ValueError("Invalid result")

                if result.is_integer():
                    result = int(result)

            expression = str(result)
            history_label.config(text=f"{original} =")
            just_calculated = True

        except Exception:
            expression = ""
            just_calculated = False
            history_label.config(text="Invalid calculation")
            display_var.set("Error")
            return

    else:
        if display_var.get() == "Error":
            expression = ""

        if just_calculated:
            if value in ["+", "-", "*", "/", "%"]:
                pass
            else:
                expression = ""

            just_calculated = False

        if value in ["+", "-", "*", "/", "%"]:
            if not expression:
                if value != "-":
                    return
            elif expression[-1] in ["+", "-", "*", "/", "%"]:
                expression = expression[:-1]

            history_label.config(text="")

        expression += value

    update_display()

# ==================== BUTTON DESIGN ====================

buttons = [
    [("C", DANGER, DANGER_HOVER),
     ("DEL", OPERATOR, OPERATOR_HOVER),
     ("%", OPERATOR, OPERATOR_HOVER),
     ("/", OPERATOR, OPERATOR_HOVER)],

    [("7", BTN, BTN_HOVER),
     ("8", BTN, BTN_HOVER),
     ("9", BTN, BTN_HOVER),
     ("*", OPERATOR, OPERATOR_HOVER)],

    [("4", BTN, BTN_HOVER),
     ("5", BTN, BTN_HOVER),
     ("6", BTN, BTN_HOVER),
     ("-", OPERATOR, OPERATOR_HOVER)],

    [("1", BTN, BTN_HOVER),
     ("2", BTN, BTN_HOVER),
     ("3", BTN, BTN_HOVER),
     ("+", OPERATOR, OPERATOR_HOVER)],

    [("00", BTN, BTN_HOVER),
     ("0", BTN, BTN_HOVER),
     (".", BTN, BTN_HOVER),
     ("=", PURPLE, PURPLE_HOVER)]
]

button_frame = tk.Frame(card, bg=CARD)
button_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

for r in range(5):
    button_frame.grid_rowconfigure(r, weight=1)

for c in range(4):
    button_frame.grid_columnconfigure(c, weight=1)

def create_button(text, color, hover_color, row, col):
    button = tk.Button(
        button_frame,
        text=text,
        font=("Segoe UI", 15, "bold"),

        # Normal and click-state colors
        bg=color,
        fg=TEXT,
        activebackground=hover_color,
        activeforeground=TEXT,

        # Prevent default border/focus colors
        relief="flat",
        overrelief="flat",
        bd=0,
        highlightthickness=0,
        highlightbackground=color,
        highlightcolor=color,
        takefocus=False,

        # Prevent system theme from overriding colors
        cursor="hand2",
        command=lambda v=text: press(v)
    )

    button.grid(
        row=row,
        column=col,
        sticky="nsew",
        padx=4,
        pady=4,
        ipadx=2,
        ipady=8
    )

    button.bind(
        "<Enter>",
        lambda event, b=button, h=hover_color:
        b.configure(bg=h, activebackground=h)
    )

    button.bind(
        "<Leave>",
        lambda event, b=button, c=color:
        b.configure(bg=c, activebackground=hover_color)
    )

    return button

for r, row in enumerate(buttons):
    for c, (text, color, hover_color) in enumerate(row):
        create_button(text, color, hover_color, r, c)

# ==================== KEYBOARD SUPPORT ====================

def keyboard_input(event):
    key = event.char

    if key in "0123456789.+-%":
        press(key)

    elif key in "*/":
        press(key)

    elif event.keysym in ("Return", "KP_Enter"):
        press("=")

    elif event.keysym == "BackSpace":
        press("DEL")

    elif event.keysym == "Escape":
        press("C")

root.bind("<Key>", keyboard_input)

# ==================== RUN ====================

root.mainloop()