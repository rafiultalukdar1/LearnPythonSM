
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime

# ==================================================
# PERSONAL KNOWLEDGE SEARCH ENGINE
# Built with Python + Tkinter + SQLite
# No external packages required
# ==================================================

DB_NAME = "knowledge.db"

COLORS = {
    "bg": "#0B1020",
    "sidebar": "#10182B",
    "panel": "#151F34",
    "card": "#1A2740",
    "input": "#0D1527",
    "border": "#293750",
    "text": "#F1F5F9",
    "muted": "#94A3B8",
    "purple": "#8B5CF6",
    "purple_hover": "#7C3AED",
    "green": "#34D399",
    "red": "#FB7185",
    "blue": "#60A5FA",
    "yellow": "#FBBF24",
}

CATEGORIES = [
    "Python",
    "Java",
    "Web Development",
    "Ideas",
    "Personal",
    "Other",
]


# ================= DATABASE =================

def db_connect():
    return sqlite3.connect(DB_NAME)


def initialize_database():
    with db_connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                content TEXT DEFAULT '',
                favorite INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                searched_at TEXT NOT NULL
            )
        """)


# ================= MAIN APP =================

class KnowledgeApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Knowledge Hub")
        self.root.geometry("1240x790")
        self.root.minsize(960, 650)
        self.root.configure(bg=COLORS["bg"])

        self.selected_id = None
        self.active_category = "All Notes"
        self.favorites_only = False
        self.search_after_id = None

        self.search_var = tk.StringVar()
        self.title_var = tk.StringVar()
        self.category_var = tk.StringVar(value="Python")
        self.sort_var = tk.StringVar(value="Recently Updated")
        self.status_var = tk.StringVar(value="Your workspace is ready")

        self.configure_styles()
        self.build_interface()
        self.refresh_notes()

        self.search_var.trace_add("write", self.on_search_changed)
        self.root.bind("<Control-n>", lambda e: self.new_note())
        self.root.bind("<Control-s>", lambda e: self.save_note())
        self.root.bind("<Escape>", lambda e: self.clear_editor())

    # ================= STYLES =================

    def configure_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Dark.TCombobox",
            fieldbackground=COLORS["input"],
            background=COLORS["panel"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["text"],
            bordercolor=COLORS["border"],
            padding=8
        )

        style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", COLORS["input"])],
            foreground=[("readonly", COLORS["text"])],
            selectbackground=[("readonly", COLORS["purple"])],
            selectforeground=[("readonly", COLORS["text"])]
        )

    # ================= UI HELPERS =================

    def label(
        self, parent, text, size=10, color=None,
        bold=False, **kwargs
    ):
        return tk.Label(
            parent,
            text=text,
            font=(
                "Segoe UI",
                size,
                "bold" if bold else "normal"
            ),
            bg=kwargs.pop("bg", parent.cget("bg")),
            fg=color or COLORS["text"],
            **kwargs
        )

    def button(
        self, parent, text, command,
        bg=None, fg=None, **kwargs
    ):
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI", 10, "bold"),
            bg=bg or COLORS["card"],
            fg=fg or COLORS["text"],
            activebackground=COLORS["purple_hover"],
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=9,
            **kwargs
        )

    def panel(self, parent, bg=None):
        return tk.Frame(
            parent,
            bg=bg or COLORS["panel"],
            highlightbackground=COLORS["border"],
            highlightthickness=1
        )

    # ================= BUILD INTERFACE =================

    def build_interface(self):
        self.main = tk.Frame(self.root, bg=COLORS["bg"])
        self.main.pack(fill="both", expand=True)

        self.build_sidebar()

        self.workspace = tk.Frame(
            self.main,
            bg=COLORS["bg"]
        )
        self.workspace.pack(
            side="left",
            fill="both",
            expand=True,
            padx=25,
            pady=22
        )

        self.build_header()
        self.build_statistics()
        self.build_search_bar()
        self.build_content_area()
        self.build_footer()

    def build_sidebar(self):
        self.sidebar = tk.Frame(
            self.main,
            bg=COLORS["sidebar"],
            width=225
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg=COLORS["sidebar"])
        brand.pack(fill="x", padx=20, pady=(28, 30))

        logo = tk.Frame(
            brand,
            bg=COLORS["purple"],
            width=42,
            height=42
        )
        logo.pack(side="left", padx=(0, 11))
        logo.pack_propagate(False)

        self.label(
            logo, "K", 22, "white", True
        ).place(relx=0.5, rely=0.5, anchor="center")

        brand_text = tk.Frame(brand, bg=COLORS["sidebar"])
        brand_text.pack(side="left")

        self.label(
            brand_text, "Knowledge", 15, COLORS["text"], True
        ).pack(anchor="w")

        self.label(
            brand_text, "PERSONAL WORKSPACE", 7, COLORS["muted"], True
        ).pack(anchor="w", pady=(3, 0))

        self.button(
            self.sidebar,
            "+   Create New Note",
            self.new_note,
            COLORS["purple"],
            "white"
        ).pack(fill="x", padx=15, pady=(0, 27))

        self.label(
            self.sidebar, "WORKSPACE", 9, COLORS["muted"], True
        ).pack(anchor="w", padx=21, pady=(0, 10))

        self.category_buttons = {}

        categories = ["All Notes"] + CATEGORIES

        for category in categories:
            btn = self.button(
                self.sidebar,
                "▦   " + category,
                lambda c=category: self.select_category(c),
                COLORS["sidebar"],
                COLORS["text"],
                anchor="w"
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.category_buttons[category] = btn

        self.favorites_btn = self.button(
            self.sidebar,
            "★   Favorites",
            self.toggle_favorites,
            COLORS["sidebar"],
            COLORS["yellow"],
            anchor="w"
        )
        self.favorites_btn.pack(
            fill="x", padx=10, pady=(16, 2)
        )

        self.button(
            self.sidebar,
            "◷   Recent Searches",
            self.show_recent_searches,
            COLORS["sidebar"],
            COLORS["muted"],
            anchor="w"
        ).pack(fill="x", padx=10, pady=2)

        bottom = tk.Frame(self.sidebar, bg=COLORS["sidebar"])
        bottom.pack(side="bottom", fill="x", padx=20, pady=20)

        tk.Frame(
            bottom, bg=COLORS["border"], height=1
        ).pack(fill="x", pady=(0, 15))

        self.label(
            bottom, "LOCAL & PRIVATE", 9, COLORS["green"], True
        ).pack(anchor="w")

        self.label(
            bottom, "Your notes stay on this computer.",
            9, COLORS["muted"], wraplength=180, justify="left"
        ).pack(anchor="w", pady=(5, 0))

    def build_header(self):
        header = tk.Frame(self.workspace, bg=COLORS["bg"])
        header.pack(fill="x", pady=(0, 21))

        left = tk.Frame(header, bg=COLORS["bg"])
        left.pack(side="left", fill="x", expand=True)

        self.label(
            left, "Your Knowledge Space", 24, COLORS["text"], True
        ).pack(anchor="w")

        self.label(
            left,
            "Organize your thoughts. Find what matters.",
            10,
            COLORS["muted"]
        ).pack(anchor="w", pady=(5, 0))

        self.button(
            header,
            "Save Note   Ctrl+S",
            self.save_note,
            COLORS["purple"],
            "white"
        ).pack(side="right", padx=(10, 0))

        self.button(
            header,
            "+ New",
            self.new_note,
            COLORS["card"]
        ).pack(side="right")

    def build_statistics(self):
        stats = tk.Frame(self.workspace, bg=COLORS["bg"])
        stats.pack(fill="x", pady=(0, 18))

        self.stat_total = self.stat_card(
            stats, "TOTAL NOTES", "0", "All your saved notes", COLORS["purple"]
        )
        self.stat_favorites = self.stat_card(
            stats, "FAVORITES", "0", "Your starred notes", COLORS["green"]
        )
        self.stat_categories = self.stat_card(
            stats, "CATEGORIES", "0", "Categories in use", COLORS["blue"]
        )

    def stat_card(self, parent, heading, value, description, accent):
        card = self.panel(parent)
        card.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.label(
            card, heading, 9, COLORS["muted"], True
        ).pack(anchor="w", padx=16, pady=(13, 2))

        number = self.label(
            card, value, 23, accent, True
        )
        number.pack(anchor="w", padx=16)

        self.label(
            card, description, 9, COLORS["muted"]
        ).pack(anchor="w", padx=16, pady=(1, 13))

        return number

    def build_search_bar(self):
        bar = tk.Frame(
            self.workspace,
            bg=COLORS["panel"],
            highlightbackground=COLORS["border"],
            highlightthickness=1
        )
        bar.pack(fill="x", pady=(0, 18))

        self.label(
            bar, "⌕", 22, COLORS["purple"], True
        ).pack(side="left", padx=(14, 8))

        self.search_entry = tk.Entry(
            bar,
            textvariable=self.search_var,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            font=("Segoe UI", 11),
            relief="flat",
            bd=0
        )
        self.search_entry.pack(
            side="left", fill="x", expand=True, pady=15
        )

        self.search_entry.insert(0, "")

        self.button(
            bar, "Clear", self.clear_search,
            COLORS["panel"], COLORS["muted"]
        ).pack(side="right", padx=7, pady=5)

        self.sort_combo = ttk.Combobox(
            bar,
            textvariable=self.sort_var,
            values=[
                "Recently Updated",
                "Oldest Updated",
                "Title A-Z",
                "Title Z-A"
            ],
            state="readonly",
            width=17,
            style="Dark.TCombobox"
        )
        self.sort_combo.pack(side="right", padx=7, pady=8)
        self.sort_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self.refresh_notes()
        )

    def build_content_area(self):
        area = tk.Frame(self.workspace, bg=COLORS["bg"])
        area.pack(fill="both", expand=True)

        # Notes panel
        self.list_panel = self.panel(area)
        self.list_panel.pack(
            side="left", fill="both", expand=True, padx=(0, 12)
        )

        list_header = tk.Frame(
            self.list_panel, bg=COLORS["panel"]
        )
        list_header.pack(fill="x", padx=15, pady=(15, 10))

        self.label(
            list_header, "Your Notes", 13, COLORS["text"], True
        ).pack(side="left")

        self.note_count = self.label(
            list_header, "0 notes", 9, COLORS["muted"]
        )
        self.note_count.pack(side="right")

        self.notes_canvas = tk.Canvas(
            self.list_panel,
            bg=COLORS["panel"],
            highlightthickness=0,
            bd=0
        )
        self.notes_canvas.pack(
            side="left", fill="both", expand=True,
            padx=(10, 0), pady=(0, 10)
        )

        scrollbar = tk.Scrollbar(
            self.list_panel,
            orient="vertical",
            command=self.notes_canvas.yview
        )
        scrollbar.pack(side="right", fill="y", pady=(0, 10))

        self.notes_canvas.configure(
            yscrollcommand=scrollbar.set
        )

        self.notes_container = tk.Frame(
            self.notes_canvas, bg=COLORS["panel"]
        )
        self.canvas_window = self.notes_canvas.create_window(
            (0, 0),
            window=self.notes_container,
            anchor="nw"
        )

        self.notes_container.bind(
            "<Configure>",
            lambda e: self.notes_canvas.configure(
                scrollregion=self.notes_canvas.bbox("all")
            )
        )

        self.notes_canvas.bind(
            "<Configure>",
            lambda e: self.notes_canvas.itemconfigure(
                self.canvas_window, width=e.width
            )
        )

        # Editor panel
        self.editor = self.panel(area)
        self.editor.pack(side="left", fill="both", expand=True)

        self.label(
            self.editor, "NOTE EDITOR", 9, COLORS["muted"], True
        ).pack(anchor="w", padx=20, pady=(20, 15))

        self.label(
            self.editor, "Title", 10, COLORS["text"], True
        ).pack(anchor="w", padx=20)

        self.title_entry = tk.Entry(
            self.editor,
            textvariable=self.title_var,
            font=("Segoe UI", 13, "bold"),
            bg=COLORS["input"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            bd=0
        )
        self.title_entry.pack(
            fill="x", padx=20, pady=(8, 17), ipady=11
        )

        self.label(
            self.editor, "Category", 10, COLORS["text"], True
        ).pack(anchor="w", padx=20)

        self.category_combo = ttk.Combobox(
            self.editor,
            textvariable=self.category_var,
            values=CATEGORIES,
            state="readonly",
            style="Dark.TCombobox"
        )
        self.category_combo.pack(
            fill="x", padx=20, pady=(8, 17)
        )

        self.label(
            self.editor, "Content", 10, COLORS["text"], True
        ).pack(anchor="w", padx=20)

        text_wrap = tk.Frame(self.editor, bg=COLORS["input"])
        text_wrap.pack(
            fill="both", expand=True,
            padx=20, pady=(8, 15)
        )

        self.content_text = tk.Text(
            text_wrap,
            bg=COLORS["input"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["purple"],
            font=("Segoe UI", 10),
            wrap="word",
            relief="flat",
            bd=0,
            padx=12,
            pady=12,
            undo=True
        )
        self.content_text.pack(
            side="left", fill="both", expand=True
        )

        text_scroll = tk.Scrollbar(
            text_wrap, command=self.content_text.yview
        )
        text_scroll.pack(side="right", fill="y")
        self.content_text.configure(
            yscrollcommand=text_scroll.set
        )

        actions = tk.Frame(self.editor, bg=COLORS["panel"])
        actions.pack(fill="x", padx=20, pady=(0, 18))

        self.button(
            actions, "★ Favorite", self.toggle_favorite,
            COLORS["card"], COLORS["yellow"]
        ).pack(side="left")

        self.button(
            actions, "Delete Note", self.delete_note,
            COLORS["card"], COLORS["red"]
        ).pack(side="right")

    def build_footer(self):
        footer = tk.Frame(self.workspace, bg=COLORS["bg"])
        footer.pack(fill="x", pady=(10, 0))

        self.label(
            footer,
            "Python  •  Tkinter  •  SQLite",
            9, COLORS["muted"]
        ).pack(side="left")

        self.label(
            footer,
            "● Local storage",
            9, COLORS["green"]
        ).pack(side="right")

        self.label(
            self.workspace, "", 9, COLORS["muted"]
        ).pack()

        self.status_label = tk.Label(
            self.workspace,
            textvariable=self.status_var,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.status_label.pack(fill="x", pady=(5, 0))

    # ================= SEARCH =================

    def on_search_changed(self, *_):
        if self.search_after_id:
            self.root.after_cancel(self.search_after_id)

        self.search_after_id = self.root.after(
            180, self.refresh_notes
        )

    def clear_search(self):
        self.search_var.set("")
        self.search_entry.focus_set()

    def save_search_history(self, query):
        query = query.strip()
        if not query:
            return

        with db_connect() as db:
            db.execute(
                "INSERT INTO searches (query, searched_at) VALUES (?, ?)",
                (
                    query,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            )

    def show_recent_searches(self):
        with db_connect() as db:
            rows = db.execute("""
                SELECT query, MAX(searched_at) AS latest
                FROM searches
                GROUP BY query
                ORDER BY latest DESC
                LIMIT 15
            """).fetchall()

        popup = tk.Toplevel(self.root)
        popup.title("Recent Searches")
        popup.geometry("420x460")
        popup.configure(bg=COLORS["bg"])
        popup.transient(self.root)

        self.label(
            popup, "Recent Searches", 18, COLORS["text"], True
        ).pack(anchor="w", padx=22, pady=(22, 5))

        self.label(
            popup, "Select a search to run it again.",
            10, COLORS["muted"]
        ).pack(anchor="w", padx=22, pady=(0, 15))

        if not rows:
            self.label(
                popup, "No search history yet.",
                11, COLORS["muted"]
            ).pack(pady=30)
            return

        for query, _ in rows:
            self.button(
                popup,
                "⌕   " + query,
                lambda q=query: self.apply_recent_search(q, popup),
                COLORS["panel"],
                COLORS["text"],
                anchor="w"
            ).pack(fill="x", padx=20, pady=4)

        self.button(
            popup, "Clear Search History",
            self.clear_search_history,
            COLORS["card"], COLORS["red"]
        ).pack(fill="x", padx=20, pady=(18, 5))

    def apply_recent_search(self, query, popup):
        self.search_var.set(query)
        popup.destroy()
        self.status_var.set(f'Searching for "{query}"')

    def clear_search_history(self):
        if not messagebox.askyesno(
            "Clear History",
            "Delete all recent search history?"
        ):
            return

        with db_connect() as db:
            db.execute("DELETE FROM searches")

        self.status_var.set("Search history cleared")

    # ================= FILTERS =================

    def select_category(self, category):
        self.active_category = category

        for name, btn in self.category_buttons.items():
            btn.configure(
                bg=COLORS["purple"] if name == category
                else COLORS["sidebar"],
                fg="white" if name == category
                else COLORS["text"]
            )

        self.status_var.set(f"Showing: {category}")
        self.refresh_notes()

    def toggle_favorites(self):
        self.favorites_only = not self.favorites_only

        self.favorites_btn.configure(
            bg=COLORS["purple"] if self.favorites_only
            else COLORS["sidebar"],
            fg="white" if self.favorites_only
            else COLORS["yellow"]
        )

        self.status_var.set(
            "Showing favorites" if self.favorites_only
            else "Showing all notes"
        )
        self.refresh_notes()

    # ================= REFRESH NOTES =================

    def refresh_notes(self):
        if not hasattr(self, "notes_container"):
            return

        for widget in self.notes_container.winfo_children():
            widget.destroy()

        sql = """
            SELECT id, title, category, content, favorite,
                   created_at, updated_at
            FROM notes
        """
        conditions = []
        params = []

        query = self.search_var.get().strip()

        if query:
            pattern = f"%{query}%"
            conditions.append(
                "(title LIKE ? OR content LIKE ? OR category LIKE ?)"
            )
            params.extend([pattern, pattern, pattern])

        if self.active_category != "All Notes":
            conditions.append("category = ?")
            params.append(self.active_category)

        if self.favorites_only:
            conditions.append("favorite = 1")

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sort_options = {
            "Recently Updated": "updated_at DESC, id DESC",
            "Oldest Updated": "updated_at ASC, id ASC",
            "Title A-Z": "title COLLATE NOCASE ASC",
            "Title Z-A": "title COLLATE NOCASE DESC",
        }

        sql += " ORDER BY " + sort_options.get(
            self.sort_var.get(),
            "updated_at DESC"
        )

        with db_connect() as db:
            notes = db.execute(sql, params).fetchall()

        self.note_count.configure(
            text=f"{len(notes)} note{'s' if len(notes) != 1 else ''}"
        )

        if query:
            self.save_search_history(query)

        if not notes:
            self.label(
                self.notes_container,
                "No notes found",
                14, COLORS["muted"], True
            ).pack(pady=(55, 8))

            self.label(
                self.notes_container,
                "Try another keyword or create a new note.",
                9, COLORS["muted"], justify="center"
            ).pack(pady=(0, 15))
        else:
            for note in notes:
                self.create_note_card(note)

        self.update_statistics()

    def create_note_card(self, note):
        note_id, title, category, content, favorite, created, updated = note
        selected = note_id == self.selected_id

        bg = "#292248" if selected else COLORS["card"]
        outline = COLORS["purple"] if selected else COLORS["border"]

        card = tk.Frame(
            self.notes_container,
            bg=bg,
            highlightbackground=outline,
            highlightthickness=1,
            cursor="hand2"
        )
        card.pack(fill="x", padx=3, pady=4)

        top = tk.Frame(card, bg=bg)
        top.pack(fill="x", padx=12, pady=(11, 5))

        self.label(
            top,
            ("★  " if favorite else "") + title,
            10,
            COLORS["yellow"] if favorite else COLORS["text"],
            True,
            anchor="w",
            wraplength=260,
            justify="left"
        ).pack(side="left", fill="x", expand=True)

        self.label(
            card, category.upper(), 8, COLORS["purple"], True
        ).pack(anchor="w", padx=12, pady=(0, 5))

        preview = content.strip().replace("\n", " ")
        if len(preview) > 88:
            preview = preview[:85] + "..."

        self.label(
            card,
            preview or "No content added yet.",
            9,
            COLORS["muted"],
            anchor="w",
            justify="left",
            wraplength=290
        ).pack(fill="x", padx=12, pady=(0, 8))

        self.label(
            card, "Updated " + updated,
            8, COLORS["muted"]
        ).pack(anchor="w", padx=12, pady=(0, 10))

        def open_note(event=None, item=note):
            self.select_note(item)

        widgets = [card, top]
        widgets.extend(top.winfo_children())

        for widget in widgets:
            widget.bind("<Button-1>", open_note)

    # ================= NOTE EDITOR =================

    def select_note(self, note):
        self.selected_id = note[0]
        self.title_var.set(note[1])
        self.category_var.set(note[2])

        self.content_text.delete("1.0", "end")
        self.content_text.insert("1.0", note[3])

        self.status_var.set("Editing: " + note[1])
        self.refresh_notes()

    def new_note(self):
        self.clear_editor()
        self.status_var.set("Create a new note")
        self.title_entry.focus_set()

    def clear_editor(self):
        self.selected_id = None
        self.title_var.set("")
        self.category_var.set("Python")
        self.content_text.delete("1.0", "end")
        self.status_var.set("Editor cleared")

        if hasattr(self, "notes_container"):
            self.refresh_notes()

    def save_note(self):
        title = self.title_var.get().strip()
        category = self.category_var.get().strip() or "Other"
        content = self.content_text.get("1.0", "end-1c").strip()

        if not title:
            messagebox.showwarning(
                "Missing Title",
                "Please enter a title for your note."
            )
            self.title_entry.focus_set()
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with db_connect() as db:
            if self.selected_id is None:
                cursor = db.execute("""
                    INSERT INTO notes
                    (title, category, content, favorite, created_at, updated_at)
                    VALUES (?, ?, ?, 0, ?, ?)
                """, (title, category, content, now, now))

                self.selected_id = cursor.lastrowid
                message = "Note created successfully."
            else:
                db.execute("""
                    UPDATE notes
                    SET title = ?, category = ?, content = ?, updated_at = ?
                    WHERE id = ?
                """, (title, category, content, now, self.selected_id))

                message = "Note updated successfully."

        self.status_var.set(message)
        self.refresh_notes()

    def delete_note(self):
        if self.selected_id is None:
            messagebox.showinfo(
                "Select a Note",
                "Please select a note to delete."
            )
            return

        if not messagebox.askyesno(
            "Delete Note",
            "This note will be permanently deleted. Continue?"
        ):
            return

        with db_connect() as db:
            db.execute(
                "DELETE FROM notes WHERE id = ?",
                (self.selected_id,)
            )

        self.clear_editor()
        self.status_var.set("Note deleted successfully.")

    def toggle_favorite(self):
        if self.selected_id is None:
            messagebox.showinfo(
                "Select a Note",
                "Select a note before changing favorites."
            )
            return

        with db_connect() as db:
            row = db.execute(
                "SELECT favorite FROM notes WHERE id = ?",
                (self.selected_id,)
            ).fetchone()

            if row is None:
                return

            new_value = 0 if row[0] else 1

            db.execute("""
                UPDATE notes
                SET favorite = ?, updated_at = ?
                WHERE id = ?
            """, (
                new_value,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                self.selected_id
            ))

        self.status_var.set(
            "Added to favorites." if new_value
            else "Removed from favorites."
        )
        self.refresh_notes()

    # ================= LIVE STATISTICS =================

    def update_statistics(self):
        with db_connect() as db:
            total = db.execute(
                "SELECT COUNT(*) FROM notes"
            ).fetchone()[0]

            favorites = db.execute(
                "SELECT COUNT(*) FROM notes WHERE favorite = 1"
            ).fetchone()[0]

            categories = db.execute(
                "SELECT COUNT(DISTINCT category) FROM notes"
            ).fetchone()[0]

        self.stat_total.configure(text=str(total))
        self.stat_favorites.configure(text=str(favorites))
        self.stat_categories.configure(text=str(categories))


# ================= START APP =================

if __name__ == "__main__":
    initialize_database()

    root = tk.Tk()
    app = KnowledgeApp(root)
    root.mainloop()
