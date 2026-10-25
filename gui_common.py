# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
"""Khung giao dien dung chung cho tool dang bai va Monitor.

File nay GIONG HET NHAU o ca cac tool. Moi tool chi khai bao "spec" (cac o can hien) trong
upstt_gui.py / monitor_gui.py va goi TreeConfigApp.

Cau truc: ben trai cay  Tai khoan > Muc (noi dung / nhom theo doi); ben phai chi tiet
muc dang chon, chia tab va khoi (section). Luu bang nut Luu hoac Ctrl+S.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

import account_status

try:
    import sv_ttk  # giao dien Windows 11 (Sun Valley); khong co thi dung giao dien mac dinh
except ImportError:
    sv_ttk = None

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
FONT = ("Segoe UI", 10)
FONT_SEMI = ("Segoe UI Semibold", 10)
COPYRIGHT = "© 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền."
# Mau / co chu lay dung theo CSS cua ban thiet ke 1 (mockup_he_thong.html)
MUTED = "#6b7380"
GREEN = "#15803d"
RED = "#b91c1c"
AMBER = "#b45309"
NAV_BG = "#162033"      # thanh dieu huong ben trai
NAV_FG = "#c7d0de"
NAV_HOVER = "#1e2b44"
NAV_ON = "#24314d"
PAGE_BG = "#ffffff"     # nen trang (khung phai, thanh tren)
SOFT = "#f7f8fa"        # nen cot danh sach, thanh tieu de khung, tieu de bang
TEXT = "#1d2330"
LINE = "#e1e5eb"        # vien khung / duong ke


# icon, kieu chu theo trang thai tai khoan
STATUS_UI = {
    account_status.OK: ("✅", "StatusOk.TLabel"),
    account_status.UNKNOWN: ("❔", "StatusWarn.TLabel"),
    account_status.EXPIRED: ("⚠️", "StatusBad.TLabel"),
    account_status.LOGGED_OUT: ("⛔", "StatusBad.TLabel"),
}


# ------------------------------------------------------------------ cua so
def setup_root(root, title, width, height):
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root.title(title)
    h = min(height, root.winfo_screenheight() - 100)
    w = min(width, root.winfo_screenwidth() - 40)
    root.geometry(f"{w}x{h}+{(root.winfo_screenwidth() - w) // 2}+16")
    root.minsize(880, 500)

    if sv_ttk:
        sv_ttk.set_theme("light")
    else:
        try:
            ttk.Style().theme_use("vista")
        except tk.TclError:
            pass
    style = ttk.Style()
    # Nen trang toan bo (ban thiet ke: khung phai / thanh tren / khung noi dung deu trang)
    for name in (".", "TFrame", "TLabel", "TCheckbutton", "TRadiobutton", "TLabelframe", "TLabelframe.Label",
                 "Switch.TCheckbutton", "TPanedwindow", "TNotebook"):
        style.configure(name, background=PAGE_BG)
    bg = PAGE_BG
    root.configure(background=bg)
    style.configure("TLabel", font=FONT, foreground=TEXT)
    style.configure("TCheckbutton", foreground=TEXT)
    style.configure("Switch.TCheckbutton", foreground=TEXT)
    style.configure("Soft.TFrame", background=SOFT)
    style.configure("Head.Switch.TCheckbutton", background=SOFT)
    style.configure("Soft.TLabel", background=SOFT)
    style.configure("SoftHint.TLabel", background=SOFT, foreground=MUTED, font=("Segoe UI", 10))
    style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"), foreground=TEXT)        # .h1 19px 700
    style.configure("Sub.TLabel", font=("Segoe UI", 10), foreground=MUTED)                 # .sub 13px
    style.configure("Field.TLabel", font=FONT_SEMI, foreground=TEXT)                       # .lbl 600
    style.configure("Hint.TLabel", font=("Segoe UI", 9), foreground=MUTED)                 # .hint 12px
    style.configure("Ok.TLabel", font=FONT_SEMI, foreground=GREEN)
    style.configure("Bad.TLabel", font=FONT_SEMI, foreground=RED)
    style.configure("Dirty.TLabel", font=("Segoe UI", 9), foreground=AMBER, background="#fff4e0")
    style.configure("Warn.TLabel", font=FONT_SEMI, foreground=AMBER)
    style.configure("StatusOk.TLabel", font=FONT_SEMI, foreground=GREEN)
    style.configure("StatusBad.TLabel", font=FONT_SEMI, foreground=RED)
    style.configure("StatusWarn.TLabel", font=FONT_SEMI, foreground=AMBER)
    # nut: chu 12.5px, nut chinh dam (.btn / .btn.p)
    style.configure("TButton", font=("Segoe UI", 9))
    style.configure("Accent.TButton", font=("Segoe UI Semibold", 9))
    style.configure("Small.TButton", font=("Segoe UI", 9), padding=(6, 0))
    style.configure("Danger.TButton", font=("Segoe UI", 9), foreground=RED)          # .btn.danger
    style.map("Danger.TButton", foreground=[("!disabled", RED)])
    style.configure("Treeview", font=("Segoe UI", 10), rowheight=31, foreground=TEXT, background=PAGE_BG,
                    fieldbackground=PAGE_BG)
    # Bang khong vien rieng (nam trong khung .box nhu ban thiet ke)
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    # Tieu de bang phang nen xam nhat chu #4b5363 dam (th) thay cho o noi co vien cua sv_ttk
    try:
        style.element_create("flat.Treeheading.cell", "from", "default")
    except tk.TclError:
        pass
    style.layout("Treeview.Heading", [
        ("flat.Treeheading.cell", {"sticky": "nswe"}),
        ("Treeheading.padding", {"sticky": "nswe", "children": [
            ("Treeheading.image", {"side": "right", "sticky": ""}),
            ("Treeheading.text", {"sticky": "we"})]})])
    style.configure("Treeview.Heading", font=("Segoe UI Semibold", 9), foreground="#4b5363", background=SOFT,
                    relief="flat", borderwidth=0, padding=(8, 6))
    style.map("Treeview.Heading", background=[("active", "#eef1f5"), ("!active", SOFT)],
              foreground=[("!disabled", "#4b5363")])
    # Cay co thu muc (📝 Dang bai / 🔎 Theo doi, nhom tai khoan...) -> giu mui ten gap / mo.
    style.layout("Treeview.Item", [("Treeitem.padding", {"sticky": "nswe", "children": [
        ("Treeitem.indicator", {"side": "left", "sticky": ""}),
        ("Treeitem.image", {"side": "left", "sticky": ""}),
        ("Treeitem.focus", {"side": "left", "sticky": "", "children": [
            ("Treeitem.text", {"side": "left", "sticky": ""})]})]})])
    style.configure("TLabelframe.Label", font=FONT_SEMI)
    return bg


def text_box(parent, height, wrap="none"):
    """O nhap nhieu dong co thanh cuon; cuon chuot chi cuon trong o."""
    frame = ttk.Frame(parent)
    # .ta: vien 1px xam nhat, chu #394150, dang go thi vien xanh
    text = tk.Text(frame, height=height, wrap=wrap, font=FONT, relief="flat", borderwidth=0, fg="#394150",
                   undo=True, padx=9, pady=6, highlightthickness=1, highlightbackground=LINE,
                   highlightcolor="#2563eb", insertbackground=TEXT)
    bar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    text.pack(side="left", fill="both", expand=True)
    text.bind("<MouseWheel>", lambda e: (text.yview_scroll(int(-e.delta / 120), "units"), "break")[1])
    return frame, text


class ScrollFrame(ttk.Frame):
    """Khung cuon doc cho noi dung dai."""

    def __init__(self, parent, bg):
        super().__init__(parent)
        canvas = tk.Canvas(self, highlightthickness=0, background=bg, borderwidth=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = ttk.Frame(canvas, padding=(4, 8, 16, 8))
        window = canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        wheel = lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))


# ------------------------------------------------------------------ thanh phan giao dien (ban thiet ke 1)
HEAD_BG = SOFT          # thanh tieu de khung (.box > .bh)
SEL_BG = "#e4ecff"      # dong / the dang chon (--sel)
ACCENT_BG = "#eaf1ff"   # nen nut loc / thu dang chon (--accent-bg)
ACCENT_LINE = "#bcd0ff"
ACCENT = "#2563eb"
LEVEL_COLOR = {"lv0": "#15803d", "lv2": "#b45309", "lv3": "#b91c1c", "off": "#9aa1ab", "bad": "#b91c1c"}
DOT_COLOR = {"#15803d": "#15803d", "#b45309": "#f59e0b", "#b91c1c": "#b91c1c", "#9aa1ab": "#b8bfca"}   # .d-ok/warn/bad/off
PILL_BG = {"#15803d": "#e7f6ec", "#b45309": "#fff4e0", "#b91c1c": "#fde8e8", "#9aa1ab": "#eef0f3"}   # .p-ok/warn/bad/off
PILL_FG = {"#9aa1ab": "#6b7380"}


def page_bg():
    return ttk.Style().lookup("TFrame", "background") or "#fafafa"


class Box(tk.Frame):
    """Khung co thanh tieu de nen xam nhat (thay ttk.Labelframe). Con cua khung pack thang vao khung (nam duoi
    thanh tieu de). Box.head: thanh tieu de (gan them nut ben phai neu can)."""
    HEAD_H = 38

    def __init__(self, parent, text="", padding=None, **_kw):
        bg = page_bg()
        super().__init__(parent, bg=bg, highlightbackground=LINE, highlightcolor=LINE, highlightthickness=1, bd=0,
                         padx=12, pady=10)
        self.head = tk.Frame(self, bg=HEAD_BG, height=self.HEAD_H)
        self.head.pack_propagate(False)
        self.head.place(x=-12, y=-10, relwidth=1, width=24)   # place tinh tu trong padx/pady -> keo ra sat vien
        tk.Frame(self.head, height=1, bg=LINE).pack(side="bottom", fill="x")
        tk.Label(self.head, text=str(text).strip(), bg=HEAD_BG, fg=TEXT, font=FONT_SEMI, anchor="w").pack(
            side="left", padx=(12, 0))
        tk.Frame(self, height=self.HEAD_H, bg=bg).pack(fill="x")   # cho cho thanh tieu de
        self.head.lift()   # khung dem tao sau se de len thanh tieu de neu khong nang len

    def add_pill(self, text, fg="#1d4ed8", bg=ACCENT_BG):
        """Vien thuoc canh tieu de (.pill, mac dinh .p-acc xanh), vd '2 nhóm'."""
        tk.Label(self.head, text=text, bg=bg, fg=fg, font=("Segoe UI Semibold", 9), padx=7).pack(
            side="left", padx=(8, 0))

    def add_switch(self, var, command=None):
        """Cong tac bat/tat ben phai thanh tieu de (.tog)."""
        sw = ttk.Checkbutton(self.head, variable=var, command=command, style="Head.Switch.TCheckbutton")
        sw.pack(side="right", padx=(0, 8))
        return sw

    def add_note(self, text):
        """Chu xam nho sau tieu de (vd '· kiểm tra lúc 09:49 · tự kiểm tra mỗi 15 phút'). Tra ve nhan de doi chu."""
        note = tk.Label(self.head, text=text, bg=HEAD_BG, fg=MUTED, font=("Segoe UI", 9), anchor="w")
        note.pack(side="left", padx=(8, 0))
        return note

    def add_link(self, text, command):
        """Nut chu xanh khong vien ben phai thanh tieu de (.btn.ghost), vd 'Xem tất cả →'."""
        link = tk.Label(self.head, text=text, bg=HEAD_BG, fg=ACCENT, font=("Segoe UI Semibold", 9), cursor="hand2")
        link.pack(side="right", padx=(0, 12))
        link.bind("<Button-1>", lambda _e: command())
        return link

    def add_button(self, text, command):
        b = ttk.Button(self.head, text=text, command=command, style="Small.TButton")   # .btn.sm
        b.pack(side="right", padx=(0, 8), pady=3)
        return b


class LineTabs(ttk.Frame):
    """Tab kieu chu + gach chan xanh (ban thiet ke 1). Giong ttk.Notebook o cac ham tool dang dung:
    add / select / index / tabs / tab / bind('<<NotebookTabChanged>>')."""

    def __init__(self, parent, show_bar=True, style="TFrame"):
        super().__init__(parent, style=style)
        bg = page_bg()
        self.bar = tk.Frame(self, bg=bg)
        self.gap = 8 if show_bar else 0
        if show_bar:   # show_bar=False: chi doi trang (cot danh sach trai - chuyen bang thanh dieu huong)
            self.bar.pack(fill="x")
            tk.Frame(self, height=1, bg=LINE).pack(fill="x")
        self.pages = []   # [(con, chu, nhan, gach)]
        self.current = None

    def add(self, child, text=""):
        bg = page_bg()
        cell = tk.Frame(self.bar, bg=bg)
        cell.pack(side="left", padx=(0, 6))
        label = tk.Label(cell, text=str(text).strip(), bg=bg, fg=MUTED, font=FONT, padx=14, pady=6,
                         cursor="hand2")
        label.pack()
        line = tk.Frame(cell, height=2, bg=bg)
        line.pack(fill="x")
        i = len(self.pages)
        label.bind("<Button-1>", lambda _e: self.select(i))
        self.pages.append((child, str(text).strip(), label, line))

    def tabs(self):
        return [str(i) for i in range(len(self.pages))]

    def tab(self, tab_id, option="text"):
        return self.pages[self.index(tab_id)][1] if option == "text" else None

    def index(self, tab_id):
        if tab_id == "end":
            return len(self.pages)
        return int(tab_id)

    def select(self, tab_id=None):
        if tab_id is None:
            return "" if self.current is None else str(self.current)
        i = self.index(tab_id)
        if not 0 <= i < len(self.pages) or i == self.current:
            return None
        if self.current is not None:
            self.pages[self.current][0].pack_forget()
        self.current = i
        for j, (_child, _text, label, line) in enumerate(self.pages):
            on = j == i
            label.configure(fg="#1d4ed8" if on else MUTED, font=FONT_SEMI if on else FONT)   # .tabs div.on
            line.configure(bg=ACCENT if on else page_bg())
        self.pages[i][0].pack(fill="both", expand=True, pady=(self.gap, 0))
        self.event_generate("<<NotebookTabChanged>>")
        return None


class CardList(tk.Frame):
    """Danh sach the (ban thiet ke 1) ve tu 1 Treeview an: thu muc -> tieu de nhom; kich ban / tai khoan -> the;
    tai khoan chay -> dong trong the. Bam the = chon dong tuong ung tren cay (giu nguyen logic cu)."""

    def __init__(self, parent, tree):
        bg = SOFT   # .list: nen xam nhat, the trang
        super().__init__(parent, bg=bg)
        self.tree = tree
        canvas = tk.Canvas(self, highlightthickness=0, background=bg, borderwidth=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = tk.Frame(canvas, bg=bg)
        window = canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        wheel = lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        self.canvas = canvas
        tree.bind("<<TreeviewSelect>>", lambda e: self.after_idle(self.render), add="+")

    def pick(self, iid):
        self.tree.selection_set(iid)
        self.tree.focus(iid)

    @staticmethod
    def color(tags):
        for t in tags:
            if t in LEVEL_COLOR:
                return LEVEL_COLOR[t]
        return TEXT

    def signature(self):
        """Noi dung dang ve (moi dong cay: id, chu, cot, mau + dong dang chon) -> giong lan truoc thi khong ve lai."""
        tree = self.tree
        out, stack = [(tree.selection() or [None])[0]], list(tree.get_children())
        while stack:
            iid = stack.pop(0)
            out.append((iid, tree.item(iid, "text"), tuple(tree.item(iid, "values")), tuple(tree.item(iid, "tags"))))
            stack[0:0] = tree.get_children(iid)
        return out

    def render(self):
        if not self.winfo_exists():
            return
        # Xoa + ve lai toan bo the lam danh sach nhap nhay (vd moi giay khi dang cap nhat) -> chi ve khi co thay doi
        sig = self.signature()
        if sig == getattr(self, "_drawn", None):
            return
        self._drawn = sig
        for w in self.inner.winfo_children():
            w.destroy()
        tree, bg = self.tree, SOFT
        sel = (tree.selection() or [None])[0]
        for top in tree.get_children():
            if "folder" in tree.item(top, "tags"):
                # .grp: 11.5px in hoa dam mau xam (icon loai giu o dau)
                tk.Label(self.inner, text=tree.item(top, "text").strip().upper(), bg=bg, fg=MUTED,
                         font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 3))
                children = tree.get_children(top)
                if not children:
                    tk.Label(self.inner, text="(trống)", bg=bg, fg="#9aa1ab", font=FONT, anchor="w").pack(
                        fill="x", padx=14)
                for iid in children:
                    self.card(iid, sel)
            else:
                self.card(top, sel)

    def card(self, iid, sel):
        tree = self.tree
        on = iid == sel or sel in tree.get_children(iid)
        white = "#ffffff"
        # .card / .card.sel: vien 1px, the dang chon vien xanh + quang xanh nhat 2px
        holder = tk.Frame(self.inner, bg=ACCENT_BG if iid == sel else SOFT)
        holder.pack(fill="x", padx=6, pady=2)
        card = tk.Frame(holder, bg=white, highlightthickness=1, bd=0,
                        highlightbackground=ACCENT if iid == sel else LINE, highlightcolor=ACCENT if iid == sel else LINE,
                        cursor="hand2")
        card.pack(fill="x", padx=2, pady=2)
        tags = tree.item(iid, "tags")
        values = list(tree.item(iid, "values")) + ["", ""]
        text = tree.item(iid, "text").strip()
        if text and not text[0].isalnum() and " " in text:
            text = text.split(" ", 1)[1].strip()   # bo icon dau dong: the da co cham mau
        row = tk.Frame(card, bg=white)
        row.pack(fill="x", padx=10, pady=(7, 0))
        color = self.color(tags)
        if color == TEXT:
            color = "#15803d"
        tk.Label(row, text="●", bg=white, fg=DOT_COLOR.get(color, color), font=("Segoe UI", 9)).pack(side="left")
        title = tk.Label(row, text=text, bg=white, fg="#9aa1ab" if "off" in tags else TEXT, font=FONT_SEMI,
                         anchor="w")
        title.pack(side="left", padx=(4, 0))
        right = str(values[1]).replace("●", "").replace("○", "").strip()
        meta = str(values[0]).strip()
        pill_fg, pill_bg = PILL_FG.get(color, color), PILL_BG.get(color, "#eef0f3")
        if str(iid).startswith("account:"):
            # the tai khoan (ban thiet ke 1): trang thai vao dong xam, o phai chi hien so tin nhan chua xem
            name, _sep, unseen = text.partition("💬")
            text = name.strip()
            meta = " · ".join(x for x in (meta, right) if x)
            right = f"💬 {unseen.strip()}" if unseen.strip() else ""
            pill_fg, pill_bg = "#b91c1c", "#fde8e8"
            title.configure(text=text)
        if right:
            tk.Label(row, text=right, bg=pill_bg, fg=pill_fg, padx=7,
                     font=("Segoe UI Semibold", 9)).pack(side="right")
        tk.Label(card, text=meta or " ", bg=white, fg=MUTED, font=("Segoe UI", 9), anchor="w").pack(
            fill="x", padx=10, pady=(1, 7))
        for w in (holder, card, row) + tuple(card.winfo_children()) + tuple(row.winfo_children()):
            w.bind("<Button-1>", lambda _e, i=iid: self.pick(i))
        for child in tree.get_children(iid):
            ctags = tree.item(child, "tags")
            cvals = list(tree.item(child, "values")) + ["", ""]
            cbg = SEL_BG if child == sel else SOFT   # .card .acc / .acc.sel
            line = tk.Frame(card, bg=cbg, cursor="hand2")
            line.pack(fill="x", padx=8, pady=(0, 5))
            ccolor = self.color(ctags)
            ccolor = "#15803d" if ccolor == TEXT else ccolor
            tk.Label(line, text="●", bg=cbg, fg=DOT_COLOR.get(ccolor, ccolor),
                     font=("Segoe UI", 8)).pack(side="left", padx=(6, 0))
            name = tree.item(child, "text").replace("👤", "").replace("⛔", "").strip().partition(" · ")[0]
            tk.Label(line, text=name, bg=cbg, fg="#9aa1ab" if "off" in ctags else TEXT, font=("Segoe UI", 9),
                     anchor="w").pack(side="left", padx=(4, 0), pady=3)
            tk.Label(line, text=str(cvals[0]), bg=cbg, fg=MUTED, font=("Segoe UI", 9)).pack(side="right",
                                                                                         padx=6)
            for w in (line,) + tuple(line.winfo_children()):
                w.bind("<Button-1>", lambda _e, i=child: self.pick(i))
        if on:
            self.after_idle(lambda c=card: self.see(c))

    def see(self, widget):
        """Cuon cho the dang chon hien trong khung."""
        try:
            self.update_idletasks()
            top, height = widget.winfo_y(), self.inner.winfo_height() or 1
            view_top, view_bottom = (x * height for x in self.canvas.yview())
            if top < view_top or top + widget.winfo_height() > view_bottom:
                self.canvas.yview_moveto(max(0, (top - 20) / height))
        except tk.TclError:
            pass


PILL_RULES = (   # (tu khoa trong o, chu, nen) - xet theo thu tu
    (("lỗi", "từ chối", "chưa đăng nhập", "ngoài bản quyền", "bị "), "#b91c1c", "#fde8e8"),
    (("chưa vào", "chưa tick", "đang tắt"), "#6b7380", "#eef0f3"),
    (("chờ", "đang", "cần xử lý", "câu hỏi", "chưa rõ", "tạm nghỉ"), "#b45309", "#fff4e0"),
    (("đã xác minh", "đã vào", "quản trị viên", "hoạt động", "đã duyệt"), "#15803d", "#e7f6ec"),
)


def pill_style(text):
    t = str(text).casefold()
    for words, fg, bg in PILL_RULES:
        if any(w in t for w in words):
            return fg, bg
    return None


def pill_cells(tree, columns, style_of=None):
    """Ve o trang thai thanh 'vien thuoc' mau (ban thiet ke 1): Treeview khong to mau tung o nen dat nhan mau
    de len o. Tu ve lai khi cuon / doi co / bam; bam vao nhan = bam vao bang. Tra ve ham ve lai (goi sau khi doi
    du lieu)."""
    pills, pending, retries = [], [], []

    def draw():
        pending.clear()
        for p in pills:
            p.destroy()
        pills.clear()
        if not tree.winfo_exists() or not tree.winfo_ismapped():
            return
        rows = tree.get_children()
        if rows and not any(tree.bbox(r) for r in rows) and len(retries) < 30:   # vua hien lai, chua xep dong
            retries.append(1)
            tree.after(60, later)
            return
        retries.clear()
        for iid in rows:
            for col in columns:
                box = tree.bbox(iid, col)
                style = box and (style_of or pill_style)(tree.set(iid, col))
                if not style:
                    continue
                x, y, w, h = box
                # nen o = nen dong (che chu goc cua o), roi dat vien thuoc len tren
                cover = tk.Frame(tree, bg=row_bg(iid), bd=0)
                cover.place(x=x + 1, y=y + 1, width=max(1, w - 2), height=max(1, h - 2))
                label = tk.Label(cover, text=tree.set(iid, col).strip(), fg=style[0], bg=style[1], padx=6, pady=0,
                                 font=("Segoe UI Semibold", 9), bd=0)
                if tree.column(col, "anchor") == "center":
                    label.place(relx=0.5, rely=0.5, anchor="center")
                else:
                    label.place(x=2, rely=0.5, anchor="w")
                for widget in (cover, label):
                    for seq in ("<ButtonPress-1>", "<ButtonRelease-1>"):
                        widget.bind(seq, lambda e, s=seq, wd=widget: tree.event_generate(
                            s, x=wd.winfo_rootx() - tree.winfo_rootx() + e.x,
                            y=wd.winfo_rooty() - tree.winfo_rooty() + e.y))
                    widget.bind("<MouseWheel>", lambda e: tree.yview_scroll(int(-e.delta / 120), "units"))
                pills.append(cover)

    def row_bg(iid):
        style = ttk.Style()
        if iid in tree.selection():
            return style.lookup("Treeview", "background", ["selected"]) or SEL_BG
        for tag in tree.item(iid, "tags"):
            bg = tree.tag_configure(tag, "background")
            if bg:
                return bg
        return style.lookup("Treeview", "background") or "#ffffff"

    def later(*_a):
        if not pending and tree.winfo_exists():
            pending.append(tree.after_idle(draw))

    old = tree.cget("yscrollcommand")
    if old:
        tree.configure(yscrollcommand=lambda first, last: (tree.tk.eval(f"{old} {first} {last}"), later()))
    for seq in ("<Configure>", "<Map>", "<ButtonRelease-1>", "<<TreeviewSelect>>", "<KeyRelease>", "<MouseWheel>"):
        tree.bind(seq, later, add="+")
    return later


def stat_card(parent, col, value, label, color, font, padx=(0, 0)):
    """O so lieu trang, vien manh xam nhat (ban thiet ke 1)."""
    white = "#ffffff"
    cell = tk.Frame(parent, bg=white, highlightthickness=1, highlightbackground=LINE, highlightcolor=LINE,
                    padx=12, pady=10)
    cell.grid(row=0, column=col, sticky="nsew", padx=padx)
    tk.Label(cell, text=str(value), bg=white, fg=color or TEXT, font=font, anchor="w").pack(anchor="w")
    tk.Label(cell, text=label, bg=white, fg="#6b7380", font=("Segoe UI", 9), anchor="w").pack(anchor="w")
    return cell


def fit_wrap(label, box, pad=0):
    """Dong huong dan tu xuong dong theo do rong that cua khung (cot hep / cua so nho khong bi cat chu)."""
    label.pack(anchor="w", padx=(pad, 0))
    try:
        inner = 2 * int(str(box.cget("padx")))   # Box (tk.Frame) co le trong 2 ben
    except (tk.TclError, ValueError):
        inner = 0
    box.bind("<Configure>", lambda e: label.winfo_exists() and e.width > 60
             and label.configure(wraplength=max(120, e.width - inner - pad - 8)), add="+")
    return label


CHIP_ON_BG = ACCENT_BG    # nut loc dang chon (.chip.on)
CHIP_ON_FG = "#1d4ed8"


def chip_paint(widget, on):
    """.chip / .days span: vien manh xam, nen trang, chu xam 12px; dang chon: nen xanh nhat, vien xanh, chu xanh dam."""
    widget.configure(fg=CHIP_ON_FG if on else MUTED, font=("Segoe UI Semibold", 9) if on else ("Segoe UI", 9))
    widget.master.configure(bg=ACCENT_LINE if on else LINE)   # vien 1px = khung boc ngoai


def chip_button(parent, kind, **kw):
    """Nut kieu .chip (kind = tk.Radiobutton / tk.Checkbutton, indicatoron=0) nam trong khung vien 1px
    (Tk tren Windows khong ve vien highlight cho nut nay). Pack / grid khung: nut.master."""
    holder = tk.Frame(parent, bg=LINE, padx=1, pady=1)
    btn = kind(holder, indicatoron=0, relief="flat", bd=0, offrelief="flat", padx=9, pady=1, cursor="hand2",
               highlightthickness=0, bg="#ffffff", activebackground="#f1f4f8", selectcolor=CHIP_ON_BG,
               font=("Segoe UI", 9), fg=MUTED, **kw)
    btn.pack()
    return btn


def chip_widgets(bar, kind=tk.Radiobutton):
    """Cac nut .chip trong 1 hang (nam trong khung vien)."""
    return [w for holder in bar.winfo_children() for w in holder.winfo_children() if isinstance(w, kind)]


def chips(parent, var, options, command=None, padx=(0, 5)):
    """Hang nut loc nhanh: options = [(gia tri, nhan)]. Nut dang chon to xanh. Tra ve khung chua."""
    bar = parent if isinstance(parent, (ttk.Frame, tk.Frame)) else ttk.Frame(parent)
    for value, label in options:
        chip_button(bar, tk.Radiobutton, text=label, value=value, variable=var, command=command).master.pack(
            side="left", padx=(0, 5))
    def recolor(*_a):
        if not bar.winfo_exists():
            return
        for w in chip_widgets(bar):
            chip_paint(w, str(w.cget("value")) == var.get())
    var.trace_add("write", recolor)
    recolor()
    return bar


class NumBox(ttk.Entry):
    """O so gon (.inp cua ban thiet ke 1) thay ttk.Spinbox co mui ten to: go so, phim ↑ / ↓ tang giam.
    Nhan cung tham so voi Spinbox (from_, to, increment, command, width, textvariable)."""

    def __init__(self, parent, from_=0, to=100, increment=1, command=None, width=5, **kw):
        kw.pop("format", None)
        super().__init__(parent, width=max(4, int(width)), justify="center", **kw)
        self.low, self.high, self.step, self.command = from_, to, increment, command
        self.bind("<Up>", lambda _e: self.bump(1))
        self.bind("<Down>", lambda _e: self.bump(-1))

    def bump(self, sign):
        try:
            value = float(self.get().strip() or 0)
        except ValueError:
            return "break"
        value = min(self.high, max(self.low, value + sign * self.step))
        self.delete(0, "end")
        self.insert(0, str(int(value)) if float(value).is_integer() else str(value))
        if self.command:
            self.command()
        return "break"


def no_wheel(spinbox):
    """Lan chuot tren o so: cuon trang (KHONG doi so) - tranh vo tinh sua gia tri khi cuon."""
    def on_wheel(e):
        p = spinbox.master
        while p is not None and not isinstance(p, tk.Canvas):
            p = p.master
        if p is not None:
            p.yview_scroll(int(-e.delta / 120), "units")
        return "break"
    spinbox.bind("<MouseWheel>", on_wheel)
    return spinbox


# ------------------------------------------------------------------ o nhap theo spec
class Form:
    """Tao o nhap tu spec, doc lai gia tri, bao thay doi.

    spec: (key, kieu, nhan, goi y, tuy chon). kieu: list | times | text | multiline | secret | bool | int
    """

    def __init__(self, on_change):
        self.widgets = {}
        self.on_change = on_change

    def add(self, parent, item, key, kind, label, hint="", opts=None):
        opts = opts or {}
        box = ttk.Frame(parent)
        box.pack(fill="x", pady=(0, 10))
        value = (opts.get("target") or item).get(key, "")
        if kind == "bool":
            var = tk.BooleanVar(value=bool(value))
            ttk.Checkbutton(box, text=label, variable=var, command=self.on_change,
                            style="Switch.TCheckbutton" if sv_ttk else "TCheckbutton").pack(anchor="w")
            if hint:
                pad = 46 if sv_ttk else 20
                fit_wrap(ttk.Label(box, text=hint, style="Hint.TLabel", wraplength=620, justify="left"), box, pad)
            self.widgets[key] = (kind, var, opts)
            return box
        # (ban thiet ke 1) .lbl dam → o nhap → .hint xam ben duoi; o so nam cung dong voi nhan
        head = ttk.Frame(box)
        counter = None
        if str(label).strip() or kind in ("list", "times", "int"):   # o khong nhan (ten o tren khung) -> khong de dong trong
            head.pack(fill="x")
            ttk.Label(head, text=label, style="Field.TLabel", wraplength=360 if kind == "int" else 0,
                      justify="left").pack(side="left")
        if kind in ("list", "times"):
            counter = ttk.Label(head, text="", style="Hint.TLabel")
            counter.pack(side="right")

        if kind in ("list", "times", "multiline"):
            height = opts.get("height", 3 if kind == "multiline" else 5)
            frame, text = text_box(box, height, wrap="word" if kind == "multiline" else "none")
            frame.pack(fill="x", pady=(4, 0))
            text.insert("1.0", "\n".join(value) if isinstance(value, list) else value)
            text.edit_modified(False)

            def changed(_e=None, t=text, c=counter):
                if t.edit_modified():
                    t.edit_modified(False)
                    self.on_change()
                if c is not None:
                    n = len([x for x in t.get("1.0", "end").splitlines() if x.strip()])
                    c.configure(text=f"{n} mục")
            text.bind("<<Modified>>", changed)
            changed()
            self.widgets[key] = (kind, text, opts)
        elif kind == "int":
            var = tk.StringVar(value=str(value))
            no_wheel(NumBox(head, from_=opts.get("min", 0), to=opts.get("max", 100000), textvariable=var,
                            width=6, font=FONT)).pack(side="left", padx=(10, 0))
            var.trace_add("write", lambda *a: self.on_change())
            self.widgets[key] = (kind, var, opts)
        else:
            var = tk.StringVar(value=value)
            row = ttk.Frame(box)
            row.pack(fill="x", pady=(4, 0))
            entry = ttk.Entry(row, textvariable=var, font=FONT, show="•" if kind == "secret" else "")
            entry.pack(side="left", fill="x", expand=True)
            if kind == "secret":
                ttk.Button(row, text="Hiện", width=6,
                           command=lambda: entry.configure(show="" if entry.cget("show") else "•")
                           ).pack(side="left", padx=(6, 0))
            var.trace_add("write", lambda *a: self.on_change())
            self.widgets[key] = (kind, var, opts)
        if hint:
            fit_wrap(ttk.Label(box, text=hint, style="Hint.TLabel", wraplength=620, justify="left"),
                     box).pack_configure(pady=(3, 0))
        return box

    def lines(self, key):
        return [x.strip().replace("|", " ") for x in self.widgets[key][1].get("1.0", "end").splitlines() if x.strip()]

    def commit(self, item):
        """Ghi gia tri vao item. So khong hop le thi giu gia tri cu va bao loi."""
        errors = []
        for key, (kind, widget, opts) in self.widgets.items():
            dest = opts.get("target") or item  # vd cong tac Chay an cua Monitor ghi vao tai khoan
            if kind in ("list", "times"):
                dest[key] = self.lines(key)
            elif kind == "multiline":
                # Giu nguyen xuong dong; chi bo khoang trang thua cuoi moi dong va dau/cuoi.
                # Chi ghi khi nguoi dung SUA that (mo xem khong lam noi dung cu bi coi la 'chua luu').
                norm = lambda t: "\n".join(x.rstrip() for x in str(t or "").splitlines()).strip()
                if norm(widget.get("1.0", "end")) != norm(dest.get(key, "")):
                    dest[key] = norm(widget.get("1.0", "end"))
            elif kind == "bool":
                dest[key] = bool(widget.get())
            elif kind == "int":
                raw = widget.get().strip()
                if raw.isdigit() and opts.get("min", 0) <= int(raw) <= opts.get("max", 10**9):
                    dest[key] = int(raw)
                else:
                    errors.append(f"'{raw}' không hợp lệ (cần số từ {opts.get('min', 0)} đến {opts.get('max')}).")
            else:
                dest[key] = widget.get().strip()
        return errors


class PausePanel(ttk.Frame):
    """Ghi chu 'dang tam nghi' (tai khoan / nhom nao, vi sao, den khi nao) + nut Reset tung dong.

    get_notes() -> [{'text', 'kind', 'key', 'reset'}]; on_reset(kind, key) bo nghi. Khong co gi -> an han.
    """

    def __init__(self, parent, title, get_notes, on_reset):
        super().__init__(parent)
        self.title, self.get_notes, self.on_reset = title, get_notes, on_reset
        self.refresh()

    def refresh(self):
        for child in self.winfo_children():
            child.destroy()
        try:
            notes = self.get_notes()
        except Exception as error:
            notes = [{"text": f"Không đọc được trạng thái tạm nghỉ: {error}", "reset": False}]
        if not notes:
            self.pack_forget()
            return
        self.pack(fill="x", pady=(0, 12))
        fit(ttk.Label(self, text=self.title, style="Warn.TLabel", justify="left")).pack(fill="x")
        for note in notes:
            row = ttk.Frame(self)
            row.pack(fill="x", pady=(4, 0))
            if note.get("reset"):
                ttk.Button(row, text="Reset", width=7,
                           command=lambda n=note: self.reset(n)).pack(side="right", padx=(8, 0), anchor="n")
            fit(ttk.Label(row, text="⏸ " + note["text"], style="Hint.TLabel",
                          justify="left")).pack(side="left", fill="x", expand=True, anchor="w")

    def reset(self, note):
        if not messagebox.askyesno("Bỏ tạm nghỉ", "Bỏ tạm nghỉ ngay?\n\n" + note["text"] +
                                   "\n\nLần chạy tới tool sẽ đăng / bình luận lại bình thường."):
            return
        self.on_reset(note.get("kind"), note.get("key"))
        self.refresh()


# ------------------------------------------------------------------ tong hop duyet bai (tab Tong hop)
def _link_key(url):
    return re.sub(r"[?#].*$", "", (url or "").strip()).rstrip("/").lower().split("facebook.com/")[-1]


def result_rows(acc_dir, group_urls, kind):
    """Moi nhom 1 dong: so lieu doc tu ket_qua.json (fb_login.check_results ghi). kind: 'posts' | 'comments'."""
    import fb_login
    st = fb_login.load_results(acc_dir)
    now, rows = time.time(), []
    for url in group_urls:
        slug = fb_login.group_slug(url) or st["alias"].get(_link_key(url), "")
        info = st["groups"].get(slug) or {}
        want = "comment" if kind == "comments" else "post"
        sent7 = sum(1 for e in st["sent"].get(slug, []) if e[1] == want and now - e[0] < 7 * 86400)
        rows.append({"url": url, "slug": slug, "name": info.get("name") or slug or url, "sent7": sent7,
                     "info": info, "status": result_status(info, kind)})
    return rows


def result_status(info, kind):
    """(muc do: -1 chua xem, 0 tot .. 3 xau, chu hien thi)."""
    if not info:
        return -1, "⚪ Chưa có số liệu"
    if info.get("admin"):
        return 0, "🟢 Bạn là quản trị viên"
    get = lambda tab: (info.get(tab) or {}).get(kind, 0)
    ok, wait, bad = get("posted"), get("pending"), get("declined") + get("removed")
    word = "bài" if kind == "posts" else "bình luận"
    if bad >= 2 and bad >= ok:
        return 3, "🔴 Hay bị từ chối / gỡ"
    if info.get("member_review") and not ok:
        return 2, "🟠 Đang duyệt thành viên mới"
    if wait >= 2:
        return 2, f"🟠 Còn {wait} {word} chờ duyệt"
    if ok:
        return 0, "🟢 Tốt"
    return 1, f"⚪ Chưa có {word} được đăng"


# ------------------------------------------------------------------ nhat ky -> bang (tab Chi tiet)
LOG_LINE = re.compile(r"^(\d\d)/(\d\d) (\d\d):(\d\d)\s+(.*)$")
EVENT_KIND = {   # bieu tuong dau dong nhat ky -> nhom ket qua (loc + to mau)
    "✅": "ok", "💬": "ok", "📨": "ok", "✔": "info",   # ✔ = dong tom tat 1 lan quet (thong tin)
    "⏳": "wait",
    "⏭": "skip", "⏸": "skip", "🚪": "skip", "🐢": "skip", "🔁": "skip",
    "❌": "error", "⚠️": "error", "⚠": "error", "⛔": "error", "⏰": "error", "🗑": "error",
}
EVENT_DAYS = [("Hôm nay", 1), ("7 ngày gần nhất", 7), ("30 ngày gần nhất", 30)]


def _log_time(day, month, hour, minute):
    from datetime import datetime
    now = datetime.now()
    try:
        t = datetime(now.year, int(month), int(day), int(hour), int(minute))
    except ValueError:
        return None
    return t.replace(year=now.year - 1) if (t - now).days > 1 else t   # dong cuoi nam truoc


def _parse_event(text):
    """'❌ Lỗi – Nhóm A – lý do (ảnh: anh_loi/x.png)' -> {icon, kind, label, group, detail, image, url}."""
    text = text.strip()
    icon = next((i for i in sorted(EVENT_KIND, key=len, reverse=True) if text.startswith(i)), "")
    rest = text[len(icon):].strip() if icon else text
    image = url = ""
    m = re.search(r"\s*\(ảnh: (anh_loi/[^)]+)\)", rest)
    if m:
        image, rest = m.group(1), rest[:m.start()] + rest[m.end():]
    if " | " in rest:
        rest, url = rest.rsplit(" | ", 1)
        url = url.strip()
    parts = [p.strip() for p in rest.split(" – ")]
    if url and len(parts) == 2 and re.search(r"/posts/|post_id=|/permalink/", url):
        label, group, detail = parts[0], "", parts[1]   # vd '💬 Đã bình luận – đã hiện dưới bài | link bai' 
    elif len(parts) >= 2:
        label, group, detail = parts[0], parts[1], " – ".join(parts[2:])
    elif ": " in rest:
        (label, detail), group = rest.split(": ", 1), ""
    else:
        label, group, detail = rest, "", ""
    g = re.search(r"/groups/([^/?#]+)", url) if url else None
    if not group and g:
        group = g.group(1)
    # tail = phan sau nhan, de tach lai dung khi ten nhom co chua ' – ' (xem split_group_name)
    return {"icon": icon, "kind": EVENT_KIND.get(icon, "info"), "label": label.strip(), "group": group,
            "detail": detail.strip(), "image": image, "url": url if url.startswith("http") else "",
            "slug": g.group(1) if g else "", "tail": " – ".join(parts[1:]) if len(parts) >= 2 else ""}


def split_group_name(e, names):
    """(ten nhom, chi tiet) de hien: ten nhom lay theo ma nhom trong link neu biet -> khong bi cat o dau ' – '."""
    name = names.get(e.get("slug", ""))
    if name and e.get("tail", "").startswith(name):
        return name, e["tail"][len(name):].lstrip(" –")
    return names.get(e["group"], e["group"]), e["detail"]


def day_start(days):
    """Moc 'Xem: N ngay' theo NGAY LICH: 1 = tu 0 gio hom nay, 7 = tu 0 gio cua 6 ngay truoc (khong phai 24h)."""
    from datetime import datetime, timedelta
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)


def parse_log(paths, days=7, campaign=None):
    """Cac file nhat_ky.txt (cu -> moi) -> danh sach LUOT CHAY, moi nhat truoc.

    Luot: {'time', 'title', 'summary', 'events': [...]}. campaign: chi lay dong cua nhom theo doi nay
    (nhat ky tool theo doi co dong '📂 Nhóm theo dõi: <ten>'; nhat ky cu chua co dong nay -> lay het).
    """
    since = day_start(days)
    runs, run, current = [], None, None
    for path in paths:
        try:
            lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            m = LOG_LINE.match(line)
            if not m:
                continue
            t = _log_time(*m.groups()[:4])
            text = m.group(5).strip()
            if text.startswith("▶"):
                run = {"time": t, "title": text[1:].strip(), "summary": "", "events": []}
                runs.append(run)
                current = None
                continue
            if text.startswith("📂 Nhóm theo dõi:"):
                current = text.split(":", 1)[1].strip()
                continue
            if run is None:
                run = {"time": t, "title": "(nhật ký cũ)", "summary": "", "events": []}
                runs.append(run)
            if text.startswith("■"):
                run["summary"] = text[1:].strip()
                continue
            if campaign and current and current != campaign:
                continue
            ev = _parse_event(text)
            ev["time"] = t
            run["events"].append(ev)
    runs = [r for r in runs if r["time"] and r["time"] >= since and (r["events"] or r["summary"])]
    return sorted(runs, key=lambda r: r["time"], reverse=True)


def fit(label, pad=8):
    """Nhan tu xuong dong vua khung (wraplength theo do rong that) -> khong bi tran mep phai."""
    label.bind("<Configure>", lambda e: e.widget.configure(wraplength=max(200, e.width - pad)), add="+")
    return label


class GridTable(ttk.Frame):
    """Bang co ke o (nhu Excel), GIAN HET KHUNG: cot tu gian theo do rong, bang cao theo so dong.

    columns: [(key, tieu de, rong toi thieu px, 'w'|'center')]. add(values, bg, bold, span, data, wrap).
    max_rows_visible: qua so dong nay moi cuon doc trong bang (None = hien het, trang tu cuon).
    Cua so hep hon tong cot toi thieu -> hien thanh cuon ngang.
    """
    ROW_H = 30
    HEAD_H = 32
    LINE = "#c9ced6"
    HEAD_BG = "#eef1f5"
    SEL_BG = "#cfe3ff"

    EMPTY = "(trống)"

    def __init__(self, parent, columns, rows_visible=None, max_rows_visible=None, filterable=()):
        super().__init__(parent)
        import tkinter.font as tkfont
        self.columns = columns
        self.min_w = [c[2] for c in columns]
        self.widths = list(self.min_w)
        self.items, self.rows, self.sel = [], [], None
        self.max_rows = max_rows_visible
        self.on_select = self.on_double = None
        # Loc theo cot (bam tieu de cot co ▾): {key: gia tri dang loc}. Giu nguyen khi do lai du lieu (clear + add).
        self.filterable, self.filters, self.on_filter = set(filterable), {}, None
        self.font = tkfont.Font(font=FONT)
        self.bold = tkfont.Font(font=FONT_SEMI)
        self.head = tk.Canvas(self, height=self.HEAD_H, highlightthickness=0, background=self.HEAD_BG)
        self.body = tk.Canvas(self, height=self.ROW_H * (rows_visible or 3), highlightthickness=0,
                              background="#ffffff")
        self.ys = ttk.Scrollbar(self, orient="vertical", command=self.body.yview)
        self.xs = ttk.Scrollbar(self, orient="horizontal", command=self._xview)
        self.body.configure(yscrollcommand=self.ys.set, xscrollcommand=self.xs.set)
        self.head.grid(row=0, column=0, sticky="ew")
        self.body.grid(row=1, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.body.bind("<Button-1>", self._click)
        self.body.bind("<Double-1>", self._double)
        self.head.bind("<Button-1>", self._head_click)
        self.body.bind("<Configure>", self._resize)
        self._wheel_inside = False
        wheel = lambda e: (self.body.yview_scroll(int(-e.delta / 120), "units"), "break")[1] \
            if self._wheel_inside else None
        hwheel = lambda e: (self._xview("scroll", int(-e.delta / 120), "units"), "break")[1]
        for w in (self.body, self.head):
            w.bind("<MouseWheel>", wheel)
            w.bind("<Shift-MouseWheel>", hwheel)
        self._view_w = 0

    # ---- bo cuc
    @property
    def total_w(self):
        return sum(self.widths)

    def _xview(self, *args):
        self.body.xview(*args)
        self.head.xview(*args)

    def _resize(self, event):
        if abs(event.width - self._view_w) < 2:
            return
        self._view_w = event.width
        need = sum(self.min_w)
        if event.width > need:   # du cho -> gian deu cac cot cho het khung
            extra = event.width - need
            self.widths = [w + extra * w / need for w in self.min_w]
        else:
            self.widths = list(self.min_w)
        self._render()

    def _clip(self, text, width, font):
        text = str(text)
        if font.measure(text) <= width:
            return text
        while text and font.measure(text + "…") > width:
            text = text[:-1]
        return text + "…"

    # ---- ve
    def _render(self):
        self.head.delete("all")
        x = 0
        for (key, title, _w, anchor), width in zip(self.columns, self.widths):
            on = key in self.filters
            self.head.create_rectangle(x, 0, x + width, self.HEAD_H - 1, outline=self.LINE,
                                       fill="#dbe7fb" if on else self.HEAD_BG)
            if key in self.filterable:
                title = f"{title} ▾" + (f" {self.filters[key] or self.EMPTY}" if on else "")
            self.head.create_text(x + width / 2, self.HEAD_H / 2, text=self._clip(title, width - 8, self.bold),
                                  font=self.bold, anchor="center", fill="#1d4ed8" if on else "#1f2328")
            x += width
        self.head.configure(scrollregion=(0, 0, self.total_w, self.HEAD_H))
        self.body.delete("all")
        self.rows = []
        for i in self.visible():
            self._draw_row(*self.items[i])
        height = self.rows[-1]["y1"] if self.rows else self.ROW_H
        self.body.configure(scrollregion=(0, 0, self.total_w, height))
        # Cao theo noi dung; qua max_rows moi cuon doc trong bang
        limit = self.max_rows * self.ROW_H if self.max_rows else None
        self.body.configure(height=min(height, limit) if limit else height)
        self._wheel_inside = bool(limit and height > limit)
        if self._wheel_inside:
            self.ys.grid(row=1, column=1, sticky="ns")
        else:
            self.ys.grid_remove()
        if self._view_w and self.total_w > self._view_w + 1:
            self.xs.grid(row=2, column=0, sticky="ew")
        else:
            self.xs.grid_remove()
        if self.sel is not None and self.sel < len(self.rows):
            self._paint(self.sel, self.SEL_BG)

    def _draw_row(self, values, bg, bold, span, data, wrap):
        y = self.rows[-1]["y1"] if self.rows else 0
        font = self.bold if bold else self.font
        tag = f"r{len(self.rows)}"
        cells = [(0, self.total_w, "w", values[0])] if span else []
        if not span:
            x = 0
            for (key, title, _w, anchor), width, value in zip(self.columns, self.widths, values):
                cells.append((x, width, anchor, value))
                x += width
        texts, height = [], self.ROW_H
        for x, width, anchor, value in cells:
            if wrap and not span:
                t = self.body.create_text(x + width / 2 if anchor == "center" else x + 8, y + 7,
                                          anchor="n" if anchor == "center" else "nw", font=font,
                                          text=str(value), width=width - 14,
                                          justify="center" if anchor == "center" else "left", tags=tag)
                bx = self.body.bbox(t)
                height = max(height, (bx[3] - bx[1]) + 14 if bx else height)
            else:
                t = self.body.create_text(x + width / 2 if anchor == "center" else x + 8, y + self.ROW_H / 2,
                                          anchor="center" if anchor == "center" else "w", font=font,
                                          text=self._clip(value, width - 14, font), tags=tag)
            texts.append(t)
        for (x, width, anchor, value), t in zip(cells, texts):
            r = self.body.create_rectangle(x, y, x + width, y + height, outline=self.LINE, fill=bg, tags=tag)
            self.body.tag_lower(r, t)
            if not (wrap and not span):
                self.body.coords(t, x + width / 2 if anchor == "center" else x + 8, y + height / 2)
        self.rows.append({"data": data, "bg": bg, "tag": tag, "y0": y, "y1": y + height})

    # ---- du lieu
    def clear(self):
        self.items, self.rows, self.sel = [], [], None
        self.body.delete("all")
        self.body.yview_moveto(0)

    def add(self, values, bg="#ffffff", bold=False, span=False, data=None, wrap=False):
        self.items.append((values, bg, bold, span, data, wrap))
        if not self.filters:   # dang loc -> doi ve lai 1 lan (dong tieu de luot chi hien khi con dong khop)
            self._draw_row(values, bg, bold, span, data, wrap)
        self.after_idle(self._render_once)
        return len(self.items) - 1

    # ---- loc theo cot
    def _passes(self, values):
        for key, want in self.filters.items():
            i = next(n for n, c in enumerate(self.columns) if c[0] == key)
            if (str(values[i]) if i < len(values) else "") != want:
                return False
        return True

    def visible(self):
        """Chi so cac dong dang hien: dong khop bo loc; dong tieu de luot (span) chi hien khi co dong con khop."""
        if not self.filters:
            return list(range(len(self.items)))
        out, head = [], None
        for i, it in enumerate(self.items):
            if it[3]:
                head = i
            elif self._passes(it[0]):
                if head is not None:
                    out.append(head)
                    head = None
                out.append(i)
        return out

    def visible_data(self):
        """data cua cac dong du lieu dang hien (sau khi loc)."""
        return [self.items[i][4] for i in self.visible() if self.items[i][4] is not None and not self.items[i][3]]

    def set_filter(self, key, value=None):
        """value None -> bo loc cot do."""
        if value is None:
            self.filters.pop(key, None)
        else:
            self.filters[key] = value
        self.sel = None
        self._render()
        if self.on_filter:
            self.on_filter()

    def _head_click(self, event):
        cx, x = self.head.canvasx(event.x), 0
        for (key, title, _w, _a), width in zip(self.columns, self.widths):
            if x <= cx < x + width:
                break
            x += width
        else:
            return
        if key not in self.filterable:
            return
        i = next(n for n, c in enumerate(self.columns) if c[0] == key)
        values = list(dict.fromkeys(str(it[0][i]) if i < len(it[0]) else "" for it in self.items if not it[3]))
        if key in self.filters and self.filters[key] not in values:
            values.append(self.filters[key])
        menu = tk.Menu(self, tearoff=0)
        var = self._menu_var = tk.StringVar(value=self.filters.get(key, "\0all"))   # giu tham chieu (Tk xoa bien)
        menu.add_radiobutton(label="Tất cả", variable=var, value="\0all", command=lambda: self.set_filter(key))
        menu.add_separator()
        for v in values:
            menu.add_radiobutton(label=v or self.EMPTY, variable=var, value=v,
                                 command=lambda v=v: self.set_filter(key, v))
        menu.tk_popup(event.x_root, event.y_root)

    def update_row(self, index, values=None, bg=None):
        """Doi chu / mau 1 dong (vd o tick chon bai, trang thai cham bai) roi ve lai."""
        old = self.items[index]
        self.items[index] = (values if values is not None else old[0], bg if bg is not None else old[1], *old[2:])
        self._render_once()

    def data_rows(self):
        """[(chi so dong, data)] cua cac dong co du lieu (khong phai dong tieu de luot chay)."""
        return [(i, it[4]) for i, it in enumerate(self.items) if it[4] is not None and not it[3]]

    def _render_once(self):
        if not getattr(self, "_pending", False):
            self._pending = True
            self.after_idle(self._do_render)

    def _do_render(self):
        self._pending = False
        if self.winfo_exists():
            self._render()

    # ---- chon dong
    def _row_at(self, event):
        cy = self.body.canvasy(event.y)
        for i, row in enumerate(self.rows):
            if row["y0"] <= cy < row["y1"]:
                return i
        return None

    def _paint(self, i, color):
        for item in self.body.find_withtag(self.rows[i]["tag"]):
            if self.body.type(item) == "rectangle":
                self.body.itemconfigure(item, fill=color)

    def _click(self, event):
        i = self._row_at(event)
        if i is None:
            return
        if self.sel is not None and self.sel < len(self.rows):
            self._paint(self.sel, self.rows[self.sel]["bg"])
        self.sel = i
        self._paint(i, self.SEL_BG)
        if self.on_select:
            self.on_select(self.rows[i]["data"])

    def _double(self, event):
        self._click(event)
        if self.sel is not None and self.on_double:
            self.on_double(self.rows[self.sel]["data"])

    def selected(self):
        return self.rows[self.sel]["data"] if self.sel is not None and self.sel < len(self.rows) else None


def fb_login_post_id(url):
    """Khoa cua bai trong trang thai cham bai: ma bai (post id) hoac chinh link."""
    import fb_login
    return (fb_login.post_id_of(url) or url) if url else ""


CHECK_ERROR_FILE = "kiem_tra_loi.txt"


def fb_login_progress(acc_dir, finished=False):
    """Tien do 'Cap nhat'. finished: tien trinh da thoat -> chua ghi xong (chet som) thi tra ve loi tu stderr."""
    import fb_login
    p = fb_login.read_progress(acc_dir)
    if finished and not p.get("done"):
        try:
            lines = [x.strip() for x in (Path(acc_dir) / CHECK_ERROR_FILE).read_text(encoding="utf-8").splitlines()
                     if x.strip()]
        except OSError:
            lines = []
        reason = (lines[-1] if lines else "tiến trình dừng giữa chừng")[:150]
        p = {"step": "done", "text": f"Cập nhật lỗi: {reason}", "done": True, "ok": False}
    return p


def section(parent, title):
    frame = Box(parent, text=title)
    frame.pack(fill="x", pady=(0, 12))
    return frame


# ------------------------------------------------------------------ tien ich
def send_telegram_test(token, chat_id, text):
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=15) as r:
            return bool(json.loads(r.read().decode()).get("ok")), ""
    except Exception as error:
        return False, str(error)


def run_setup_schedule(base_dir):
    """Goi setup.ps1 -Action schedule (can quyen Admin - co khi mo tu MO_TOOL.bat)."""
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                 "-File", str(base_dir / "setup.ps1"), "-Action", "schedule"],
                                capture_output=True, text=True, timeout=180, creationflags=NO_WINDOW)
    except Exception as error:
        return False, str(error)
    out = (result.stdout + result.stderr).strip()
    errs = [line.strip() for line in out.splitlines() if "LOI" in line]
    return result.returncode == 0 and not errs, "\n".join(errs) or out[-400:]


def _profile_chrome_ps(profile_dir, action):
    script = (
        "$ids = Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | "
        f"Where-Object {{ $_.CommandLine -like '*{profile_dir}*' }} | ForEach-Object {{ $_.ProcessId }}; "
        "if ($ids) { Get-Process -Id $ids -ErrorAction SilentlyContinue | "
        "Where-Object { $_.MainWindowHandle -ne 0 } | ForEach-Object { " + action + " } }"
    )
    try:
        return subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                              timeout=30, creationflags=NO_WINDOW).stdout
    except Exception:
        return ""


def account_process_alive(account_dir):
    """Co tien trinh tool nao dang giu tai khoan (dang nhap / chay theo lich)? Kiem tra nhanh qua PID da luu."""
    try:
        pid = int((Path(account_dir) / "browser_profile.pid").read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return False
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259   # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def login_window_open(profile_dir):
    """Cua so Chrome dang nhap cua tai khoan nay con dang mo (co the bi che sau cua so khac)."""
    return bool(_profile_chrome_ps(profile_dir, "$_.Id").strip())


def close_login_window(profile_dir):
    """Dong cua so Chrome dang nhap DUNG CACH (nhu bam X) de Chrome kip luu dang nhap."""
    _profile_chrome_ps(profile_dir, "$_.CloseMainWindow() | Out-Null")


# ------------------------------------------------------------------ ung dung chung
class _ChainProc:
    """Chay noi tiep nhieu lenh (task 003: moi danh tinh 1 lan '--check-results'), gia lap Popen.poll().
    Lenh truoc loi (ma != 0) -> dung, tra ma do. stderr ghi chung 1 file (lenh dau ghi de, lenh sau ghi them)."""

    def __init__(self, cmds, cwd, err_path):
        self.cmds, self.cwd, self.err_path = list(cmds), cwd, err_path
        self.returncode = None
        self.first = True
        self.proc = self._start()

    def _start(self):
        cmd = self.cmds.pop(0)
        err_file = open(self.err_path, "w" if self.first else "a", encoding="utf-8")
        self.first = False
        try:
            return subprocess.Popen(cmd, cwd=self.cwd, creationflags=NO_WINDOW,
                                    stdout=subprocess.DEVNULL, stderr=err_file)
        finally:
            err_file.close()

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        code = self.proc.poll()
        if code is None:
            return None
        if code == 0 and self.cmds:
            self.proc = self._start()
            return None
        self.returncode = code
        return code


class TreeConfigApp:
    """Ung dung cau hinh dang cay. Lop con khai bao:

    STORE, SCRIPT, TITLE, ITEM_NOUN ("nội dung"/"nhóm theo dõi"), ITEM_ICON,
    account_extra(parent, account), item_tabs(): [(ten tab, [(ten khoi, [spec...])])],
    item_extra(tab_name, parent, item), tree_item_text(item), tree_account_text(account),
    schedule_key(entries), validate_extra(), new_item(account)
    """

    STORE = None
    SCRIPT = None
    TITLE = ""
    ITEM_NOUN = "mục"
    ITEM_ICON = "📝"
    # Nhat ky tach theo task (logs/<id>/): "account" = moi tai khoan 1 lich (Monitor),
    # "item" = moi muc 1 lich (dang bai).
    LOG_TASK_LEVEL = "account"
    ACCOUNT_FIELDS = []
    ACCOUNT_FIELDS_TITLE = "Lịch quét"
    ENABLED_TITLE = "Bật mục này"
    ENABLED_HINT = "Tắt = tạm ngừng, không mất dữ liệu."
    # Tool gop nhieu loai muc: lop con dat self.KINDS = {loai: doi tuong co ITEM_NOUN, ITEM_ICON, RESULT_KIND,
    # LOG_TASK_LEVEL, ENABLED_TITLE/HINT, ADD_LABEL, item_tabs(), section_extra(), tree_item_text(),
    # account_item_summary(), on_delete_item()} TRUOC khi goi __init__. Khong dat -> 1 loai, lay tu chinh lop.
    KINDS = None

    def kind(self, item):
        """Doi tuong mo ta loai cua muc (tool 1 loai: chinh app)."""
        return self.KINDS[item.get("kind")] if self.KINDS else self

    def all_kinds(self):
        return list(self.KINDS.items()) if self.KINDS else [(None, self)]

    @property
    def has_results(self):
        return any(k.RESULT_KIND for _key, k in self.all_kinds())

    def __init__(self, root):
        self.root = root
        self.store = self.STORE
        self.base_dir = Path(self.SCRIPT).parent
        self.python = str(Path(sys.executable).with_name("python.exe"))
        self.data = self.store.load()
        self.store.materialize(self.data)
        if getattr(self.store, "migrated", False):
            self.store.save(self.data)   # lan dau chuyen sang kich ban: ghi ngay de id kich ban co dinh
        self.saved_schedule = self.schedule_key(self.store.schedule_entries(self.data))
        self._schedule_thread = None
        self._schedule_again = False
        self.pending_login = set()     # tai khoan dang mo cua so Chrome dang nhap (tu giao dien nay)
        self.busy_accounts = set()     # tai khoan dang co lenh Dang nhap / Kiem tra / Dang xuat chay
        self.login_done_button = None
        self.saved_snapshot = self.snapshot()
        self.current = None
        self.form = None
        self.login_status = None
        self.dirty = False

        self.bg = setup_root(root, self.TITLE, 1280, 820)
        style = ttk.Style()
        # Tab ben trai (Kich ban / Tai khoan) chuyen qua thanh dieu huong -> an dau tab cua Notebook.
        style.layout("Plain.TNotebook.Tab", [])
        style.configure("Plain.TNotebook", borderwidth=0)
        style.configure("Page.TLabel", font=("Segoe UI", 11, "bold"), foreground=TEXT)    # .crumb b 15px
        style.configure("Crumb.TLabel", font=("Segoe UI", 9), foreground=MUTED)          # .crumb 12.5px
        style.configure("Kpi.TLabel", font=("Segoe UI", 18, "bold"))                     # .kpi .n 24px 700
        style.configure("Running.TLabel", font=("Segoe UI", 9), foreground=GREEN)
        style.configure("Paused.TLabel", font=FONT_SEMI, foreground="#9d5d00")

        # ---- thanh dieu huong (trai, nen toi) - giong ban thiet ke 1
        nav = tk.Frame(root, background=NAV_BG, width=168)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        self.nav = nav
        # .brand 14px dam trang + small 11px #8fa0bb; nut « / » thu gon thanh dieu huong (chi con bieu tuong)
        brand = tk.Frame(nav, bg=NAV_BG)
        brand.pack(fill="x", padx=(16, 6), pady=(12, 0))
        self.nav_toggle = tk.Label(brand, text="«", bg=NAV_BG, fg="#8fa0bb", font=("Segoe UI", 12, "bold"),
                                   cursor="hand2", padx=6)
        self.nav_toggle.pack(side="right")
        self.nav_toggle.bind("<Button-1>", lambda _e: self.set_nav_small(not self.nav_small))
        self.nav_brand = [tk.Label(brand, text="BánhBaoChiên", bg=NAV_BG, fg="#ffffff", font=("Segoe UI", 11, "bold"),
                                   anchor="w"),
                          tk.Label(nav, text="Tool Facebook", bg=NAV_BG, fg="#8fa0bb", font=("Segoe UI", 8),
                                   anchor="w")]
        self.nav_brand[0].pack(side="left", fill="x", pady=(4, 0))
        self.nav_brand[1].pack(fill="x", padx=16, pady=(0, 0))
        sep = lambda: tk.Frame(nav, height=1, bg="#26324a").pack(fill="x", padx=14, pady=10)   # .nav .sep
        sep()
        self.nav_items = {}
        for key, text in self.NAV:
            if key == "settings":
                sep()
            item = tk.Frame(nav, bg=NAV_BG, cursor="hand2")
            item.pack(fill="x", padx=8, pady=1)
            label = tk.Label(item, text=text, bg=NAV_BG, fg=NAV_FG, font=FONT, anchor="w", padx=10, pady=7,
                             cursor="hand2")
            label.pack(side="left", fill="x", expand=True)
            badge = tk.Label(item, text="", bg="#ef4444", fg="#ffffff", font=("Segoe UI Semibold", 8), padx=6)
            for w in (item, label, badge):
                w.bind("<Button-1>", lambda _e, k=key: self.show_page(k))
                w.bind("<Enter>", lambda _e, k=key: self.page != k and self.paint_nav(k, NAV_HOVER))
                w.bind("<Leave>", lambda _e, k=key: self.page != k and self.paint_nav(k, NAV_BG))
            self.nav_items[key] = (item, label, badge)
        # .nav .foot: o ban quyen (.lic) + ban quyen tac gia
        foot = tk.Frame(nav, bg=NAV_BG)
        foot.pack(side="bottom", fill="x", padx=8, pady=(0, 12))
        self.nav_foot = foot
        self.nav_license = tk.Label(foot, text="", bg="#1f2b43", fg="#cfe0ff", font=("Segoe UI", 8), anchor="w",
                                    justify="left", wraplength=140, cursor="hand2", padx=8, pady=6)
        self.nav_license.pack(fill="x")
        self.nav_license.bind("<Button-1>", lambda _e: self.show_page("settings"))
        tk.Label(foot, text="© 2026 BánhBaoChiên\nAutoTool", bg=NAV_BG, fg="#8fa0bb", font=("Segoe UI", 8),
                 anchor="w", justify="left").pack(fill="x", padx=2, pady=(8, 0))

        # ---- dai trang thai (duoi): viec chay ngam, thay doi chua luu
        footer = ttk.Frame(root, padding=(16, 3, 16, 4))
        footer.pack(side="bottom", fill="x")
        self.status = ttk.Label(footer, text="", style="Hint.TLabel")
        self.status.pack(side="left")
        tk.Frame(root, height=1, bg=LINE).pack(side="bottom", fill="x")

        # ---- thanh tren (.top): duong dan + trang thai tool + nut chung, vien duoi xam nhat
        header = ttk.Frame(root, padding=(16, 9, 16, 9))
        header.pack(fill="x")
        # Nut an / hien cot danh sach (Kich ban / Tai khoan) -> nhuong cho cho phan chi tiet ben phai
        self.list_toggle = ttk.Button(header, text="☰", width=3, command=lambda: self.set_list_hidden(not self.list_hidden))
        self.list_toggle.pack(side="left", padx=(0, 10))
        # Duong dan (Kich ban › TEST › 👤 Tai khoan 5) + nhan '● chua luu' - giong ban thiet ke 1
        self.page_title = ttk.Label(header, text="", style="Page.TLabel")
        self.page_title.pack(side="left")
        self.crumb = ttk.Label(header, text="", style="Sub.TLabel")
        self.crumb.pack(side="left", padx=(4, 0))
        self.crumb_last = ttk.Label(header, text="", style="Page.TLabel")
        self.crumb_last.pack(side="left")
        style.configure("Saved.TLabel", font=("Segoe UI", 9), foreground=GREEN)
        self.dirty_label = ttk.Label(header, text="", style="Saved.TLabel")
        self.dirty_label.pack(side="left", padx=(12, 0))
        tools = ttk.Frame(header)
        tools.pack(side="right")
        self.run_state = ttk.Label(tools, text="", style="Running.TLabel")
        self.run_state.pack(side="left", padx=(0, 10))
        if self.has_results:
            self.refresh_all_btn = ttk.Button(tools, text="🔄 Cập nhật toàn bộ", command=self.refresh_all)
            self.refresh_all_btn.pack(side="left")
        self.pause_button = ttk.Button(tools, text="", command=self.toggle_pause)
        self.pause_button.pack(side="left", padx=8)
        ttk.Button(tools, text="💾 Lưu  Ctrl+S", command=self.save,
                   style="Accent.TButton" if sv_ttk else "TButton").pack(side="left")
        tk.Frame(root, height=1, bg=LINE).pack(fill="x")
        self.pause_banner = ttk.Label(root, text="", style="Warn.TLabel", padding=(18, 4, 18, 0))
        self.pause_banner.pack(fill="x")

        # ---- vung noi dung: Kich ban / Tai khoan (danh sach + chi tiet) hoac 1 trang (Tong quan, Tin nhan, Cai dat)
        self.content = ttk.Frame(root)
        self.content.pack(fill="both", expand=True)
        self.page_box = ttk.Frame(self.content)
        self.page = None
        body = ttk.Panedwindow(self.content, orient="horizontal")
        body.pack(fill="both", expand=True)
        self.body = body

        # ---- ben trai (.list): nen xam nhat, vien phai
        style.configure("Plain.TNotebook", background=SOFT)
        left = ttk.Frame(body, style="Soft.TFrame")
        body.add(left, weight=1)
        self.left_pane = left
        tk.Frame(left, width=1, bg=LINE).pack(side="right", fill="y")
        self.left_tabs = LineTabs(left, show_bar=False, style="Soft.TFrame")
        self.left_tabs.pack(fill="both", expand=True)
        self.trees = {}

        # Cay dang bang: cot #0 = ten (kich ban / tai khoan / tin), cac cot sau = thong tin can nhin nhanh.
        tree_cols = {
            "scenario": ("Kịch bản  ›  tài khoản chạy", [("info", "Giờ / nhóm", 96), ("result", "Kết quả", 78)]),
            "account": ("Tài khoản", [("fb", "Tên Facebook", 150), ("state", "Trạng thái", 110)]),
        }

        # Loc danh sach (giong ban thiet ke 1): o tim + nut loc nhanh. Doi ten / Nhan ban / Xoa: o dau tung man.
        self.list_search = {}
        self.list_filter = {}
        self.cards = {}
        self.chip_bars = {}

        def tab(key, title, buttons, chip_list, placeholder):
            frame = ttk.Frame(self.left_tabs, style="Soft.TFrame")
            self.left_tabs.add(frame, text=f"  {title}  ")
            # .list .tools: o tim + nut them, vien duoi
            bar = ttk.Frame(frame, style="Soft.TFrame", padding=(10, 10, 10, 10))
            bar.pack(fill="x")
            tk.Frame(frame, height=1, bg=LINE).pack(fill="x")
            search = tk.StringVar()
            self.list_search[key] = search
            entry = ttk.Entry(bar, textvariable=search)
            entry.pack(side="left", fill="x", expand=True)
            hint = ttk.Label(bar, text=placeholder, style="Hint.TLabel", background="#ffffff")
            hint.place(in_=entry, x=10, rely=0.5, anchor="w")
            hint.bind("<Button-1>", lambda _e: entry.focus_set())
            search.trace_add("write", lambda *_a, k=key, h=hint: (h.place_forget() if search.get() else
                                                                   h.place(in_=entry, x=10, rely=0.5, anchor="w"),
                                                                   self.refresh_tree_keep()))
            for i, (text, command) in enumerate(buttons):
                if isinstance(command, list):   # "＋ Kịch bản ▾": menu chon loai
                    btn = ttk.Button(bar, text=text, style="Accent.TButton" if sv_ttk else "TButton")
                    menu = tk.Menu(btn, tearoff=0, font=FONT)
                    for label, cmd in command:
                        menu.add_command(label=label, command=cmd)
                    btn.configure(command=lambda b=btn, m=menu: m.tk_popup(b.winfo_rootx(),
                                                                           b.winfo_rooty() + b.winfo_height()))
                else:
                    btn = ttk.Button(bar, text=text, command=command,
                                     style="Accent.TButton" if sv_ttk and i == 0 else "TButton")
                btn.pack(side="left", padx=(6, 0))
            chip_bar = tk.Frame(frame, bg=SOFT, padx=10, pady=8)   # .chips
            chip_bar.pack(fill="x")
            var = tk.StringVar(value=chip_list[0][0])
            self.list_filter[key] = var
            self.chip_bars[key] = chips(chip_bar, var, chip_list, command=self.refresh_tree_keep)
            head, cols = tree_cols[key]
            box = ttk.Frame(frame, style="Soft.TFrame")
            box.pack(fill="both", expand=True)
            tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="tree", selectmode="browse")
            tree.heading("#0", text=head, anchor="w")
            tree.column("#0", width=230, minwidth=160, stretch=True)
            for cid, title2, width in cols:
                tree.heading(cid, text=title2, anchor="w")
                tree.column(cid, width=width, minwidth=60, stretch=False, anchor="w")
            tree.tag_configure("folder", font=FONT_SEMI)
            tree.tag_configure("lv0", foreground="#1a7f37")
            tree.tag_configure("lv2", foreground="#b45309")
            tree.tag_configure("lv3", foreground="#b42318")
            tree.tag_configure("off", foreground="#8a8f98")
            tree.tag_configure("bad", foreground="#b42318")
            # Cay an (giu du lieu + logic chon); nguoi dung thay danh sach THE ve tu cay (ban thiet ke 1).
            cards = CardList(box, tree)
            cards.pack(fill="both", expand=True)
            self.cards[key] = cards
            tree.bind("<<TreeviewSelect>>", self.on_select)
            tree.bind("<<TreeviewOpen>>", lambda e: self.remember_open(e, True))
            tree.bind("<<TreeviewClose>>", lambda e: self.remember_open(e, False))
            self.trees[key] = tree
            if key == "account":   # trang thai da co bieu tuong o dau dong (✅ / ⛔) -> chi hien ten Facebook
                tree.configure(displaycolumns=("fb",))
                tree.column("fb", width=170)

        adds = [(f"{k.ITEM_ICON}  {getattr(k, 'ADD_LABEL', k.ITEM_NOUN.capitalize())}".replace("📝 ", "")
                 .replace("🔎 ", ""), lambda key=key: self.add_scenario(key)) for key, k in self.all_kinds()]
        kind_chips = [(key, f"{k.ITEM_ICON} {getattr(k, 'CHIP_LABEL', k.ITEM_NOUN)}") for key, k in self.all_kinds()]
        tab("scenario", "📋 Kịch bản", [("＋ Kịch bản ▾", adds)] if len(adds) > 1 else
            [(f"＋ {label.split('  ', 1)[-1]}", cmd) for label, cmd in adds],
            [("all", "Tất cả")] + (kind_chips if self.KINDS else []) + [("err", "Có lỗi"), ("off", "Đang tắt")],
            "🔍 Tìm kịch bản…")
        tab("account", "👤 Tài khoản", [("＋ Tài khoản", self.add_account), ("＋ Nhóm", self.add_account_group)],
            [("all", "Tất cả"), ("msg", "Có tin nhắn"), ("err", "Có lỗi")], "🔍 Tìm tài khoản…")
        self.tree = self.trees["scenario"]
        self.left_tabs.select(0)
        self.left_tabs.bind("<<NotebookTabChanged>>", lambda e: self.on_select())

        # ---- ben phai
        self.right = ttk.Frame(body, padding=(18, 14, 18, 0))   # .right: padding 14px 18px
        body.add(self.right, weight=3)
        # Cot trai du rong cho ten tai khoan + ten Facebook + gio / ket qua.
        self._sash_set = False
        self.nav_small = self.list_hidden = False
        if self.ui_state().get("nav_small"):
            self.set_nav_small(True)
        if self.ui_state().get("list_hidden"):
            self.set_list_hidden(True)

        self.refresh_header()
        self.refresh_tree()
        if self.data["scenarios"]:
            self.select(f"scenario:{self.data['scenarios'][0]['id']}")
        elif self.data["accounts"]:
            self.select(f"account:{self.data['accounts'][0]['id']}")
        else:
            self.show_empty()
        # Mo tool: trang Tong quan (co du lieu) / Tai khoan (may moi - bat dau tu them tai khoan).
        self.show_page("home" if self.data["accounts"] else "account")

        root.bind("<Control-s>", lambda e: self.save())
        root.bind("<Control-S>", lambda e: self.save())
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.lift()
        root.attributes("-topmost", True)
        root.after(800, lambda: root.attributes("-topmost", False))
        root.focus_force()

    # ------------------------------------------------------------ du lieu
    def snapshot(self):
        return json.dumps(self.data, sort_keys=True, ensure_ascii=False)

    def mark_dirty(self):
        if not self.dirty:
            self.dirty = True
            self.dirty_label.configure(text="● chưa lưu", style="Dirty.TLabel", padding=(8, 1))   # .dirty

    def mark_clean(self):
        from datetime import datetime
        self.dirty = False
        self.dirty_label.configure(text=f"✓ Đã lưu {datetime.now():%H:%M}", style="Saved.TLabel", padding=0)

    # Node tren cay: sgroup:post|monitor / scenario:k1 / member:k1|a3 (kich ban x tai khoan = 1 muc da sinh)
    # / account:a1 / agroup:<ten>. "campaign:c1" (code cu) duoc doi sang member tuong ung.
    TREE_OF = {"sgroup": "scenario", "scenario": "scenario", "member": "scenario", "account": "account",
               "agroup": "account"}

    # Trang thai giao dien (thu muc / kich ban dang gap) - file rieng, khong lam config.json bi coi la "chua luu".
    def ui_state(self):
        if not hasattr(self, "_ui_state"):
            try:
                self._ui_state = json.loads((self.base_dir / "giao_dien.json").read_text(encoding="utf-8"))
            except Exception:
                self._ui_state = {}
        return self._ui_state

    def remember_open(self, event, is_open):
        tree = event.widget
        iid = tree.focus()
        if not iid or iid.split(":", 1)[0] not in ("sgroup", "scenario", "agroup"):
            return
        self.ui_state().setdefault("open", {})[iid] = is_open
        self.save_ui_state()

    # ---- thu gon thanh dieu huong / an cot danh sach (nho lai trong giao_dien.json)
    def set_nav_small(self, small):
        self.nav_small = small
        self.nav.configure(width=56 if small else 168)
        self.nav_toggle.configure(text="»" if small else "«")
        for w in self.nav_brand:
            if small:
                w.pack_forget()
            else:
                w.pack(**({"side": "left", "fill": "x", "pady": (4, 0)} if w is self.nav_brand[0]
                          else {"fill": "x", "padx": 16, "after": self.nav_toggle.master}))
        if small:
            self.nav_foot.pack_forget()
        else:
            self.nav_foot.pack(side="bottom", fill="x", padx=8, pady=(0, 12))
        for key, text in self.NAV:
            _item, label, _badge = self.nav_items[key]
            label.configure(text=text.split()[0] if small else text, anchor="center" if small else "w")
        self.ui_state()["nav_small"] = small
        self.save_ui_state()

    def set_list_hidden(self, hidden):
        self.list_hidden = hidden
        try:
            if hidden:
                self.body.forget(self.left_pane)
            elif str(self.left_pane) not in self.body.panes():
                self.body.insert(0, self.left_pane, weight=1)
                self.root.after(80, self.place_sash)
        except tk.TclError:
            pass
        self.list_toggle.configure(text="☰  Hiện danh sách" if hidden else "☰", width=0 if hidden else 3)
        self.ui_state()["list_hidden"] = hidden
        self.save_ui_state()

    def save_ui_state(self):
        try:
            (self.base_dir / "giao_dien.json").write_text(json.dumps(self._ui_state, ensure_ascii=False),
                                                         encoding="utf-8")
        except OSError:
            pass

    def active_tree(self):
        keys = list(self.trees)
        try:
            return self.trees[keys[self.left_tabs.index(self.left_tabs.select())]]
        except Exception:
            return self.trees["scenario"]

    def selected(self):
        sel = self.active_tree().selection()
        return tuple(sel[0].split(":", 1)) if sel else (None, None)

    def find(self, kind, ident):
        if kind == "account":
            return self.store.find_account(self.data, ident)
        if kind == "scenario":
            s = self.store.find_scenario(self.data, ident)
            return s and s["settings"]
        if kind == "member":
            sid, aid = ident.split("|", 1)
            s = self.store.find_scenario(self.data, sid)
            return s and self.store.member_campaign(self.data, s, aid)
        if kind == "campaign":
            return self.store.find_campaign(self.data, ident)[1]
        return None

    def member_iid(self, campaign_id):
        s, aid = self.store.scenario_of(self.data, campaign_id)
        return f"member:{s['id']}|{aid}" if s else None

    def select(self, iid, clear_filters=True):
        """Chon node (tu chuyen sang dung tab ben trai)."""
        if iid and iid.startswith("campaign:"):
            iid = self.member_iid(iid.split(":", 1)[1])
        if not iid:
            return False
        key = self.TREE_OF.get(iid.split(":", 1)[0])
        tree = self.trees.get(key)
        if clear_filters and tree and not tree.exists(iid) and any(self.list_query(k) != ("", "all") for k in self.trees):
            # Dang loc danh sach nen muc bi an -> bo loc roi chon (vd bam 'Xem' o Tong quan).
            self.clear_list_filters()
            self.refresh_tree()
        if not tree or not tree.exists(iid):
            return False
        if self.page != key:
            self.show_page(key)
        self.left_tabs.select(list(self.trees).index(key))
        tree.selection_set(iid)
        tree.see(iid)
        return True

    # ------------------------------------------------------------ dieu huong (thanh trai)
    NAV = [("home", "🏠  Tổng quan"), ("scenario", "📋  Kịch bản"), ("account", "👤  Tài khoản"),
           ("inbox", "💬  Tin nhắn"), ("settings", "🛠  Cài đặt")]
    PAGE_TITLES = {"home": "Tổng quan", "scenario": "Kịch bản", "account": "Tài khoản",
                   "inbox": "Tin nhắn khách", "settings": "Cài đặt"}

    def show_page(self, key):
        """Chuyen trang. Kich ban / Tai khoan: danh sach + chi tiet (giu nguyen noi dung dang sua);
        Tong quan / Tin nhan / Cai dat: dung lai moi lan mo (so lieu moi nhat)."""
        if key in ("scenario", "account") and key not in self.trees:
            return
        self.commit_form()
        if key in ("scenario", "account"):
            self.page_box.pack_forget()
            if not self.body.winfo_ismapped():
                self.body.pack(fill="both", expand=True)   # cot danh sach sat mep (ban thiet ke 1)
            # Moi lan hien lai danh sach (Tk xep lai cot theo do rong noi dung): dat lai vach ngan - cot trai ~36%
            # (toi da 460px) hoac dung cho nguoi dung da tu keo.
            self.root.after(80, self.place_sash)
            self.page = key
            idx = list(self.trees).index(key)
            if self.left_tabs.index(self.left_tabs.select()) != idx:
                self.left_tabs.select(idx)   # -> <<NotebookTabChanged>> -> on_select
        else:
            self.body.pack_forget()
            for child in self.page_box.winfo_children():
                child.destroy()
            self.page_box.pack(fill="both", expand=True)
            self.page = key
            scroll = ScrollFrame(self.page_box, self.bg)
            scroll.pack(fill="both", expand=True, padx=(14, 4), pady=(6, 4))
            builder = {"home": self.build_home, "inbox": self.build_inbox_page,
                       "settings": self.build_settings_page}[key]
            try:
                builder(scroll.inner)
            except Exception as error:   # 1 trang loi khong lam treo ca tool
                ttk.Label(scroll.inner, text=f"Không dựng được trang này: {error}", style="Bad.TLabel",
                          wraplength=800).pack(anchor="w", pady=20)
        if key in ("home", "inbox", "settings"):
            from datetime import datetime
            self.show_crumb([], f"·  hôm nay {datetime.now():%d/%m}" if key == "home" else
                            ("·  mọi tài khoản" if key == "inbox" else ""))
        elif self.current:
            self.set_crumb()
        else:
            self.show_crumb([])
        self.update_nav()

    def show_crumb(self, parts, note=""):
        """.crumb: 'Kịch bản › TEST › ' chu xam 12.5px, muc cuoi dam 15px; khong co muc con thi ten trang dam."""
        title = self.PAGE_TITLES.get(self.page, "")
        if parts:
            self.page_title.configure(text=title + "  ›", style="Crumb.TLabel")
            self.crumb.configure(text="".join(f"{p}  ›  " for p in parts[:-1]), style="Crumb.TLabel")
            self.crumb_last.configure(text=parts[-1])
        else:
            self.page_title.configure(text=title, style="Page.TLabel")
            self.crumb.configure(text=note, style="Sub.TLabel")
            self.crumb_last.configure(text="")

    def set_crumb(self):
        """Duong dan sau ten trang: '› TEST – Luong day du › 👤 Tai khoan 5'."""
        if not hasattr(self, "crumb") or self.page not in ("scenario", "account"):
            return   # trang Tong quan / Tin nhan / Cai dat dang mo: khong doi duong dan
        kind, ident = self.current or (None, None)
        parts = []
        if kind == "scenario":
            s = self.store.find_scenario(self.data, ident)
            parts = [s["name"]] if s else []
        elif kind == "member":
            sid, aid = ident.split("|", 1)
            s, a = self.store.find_scenario(self.data, sid), self.store.find_account(self.data, aid)
            parts = [x for x in ((s or {}).get("name"), f"👤 {a['name']}" if a else None) if x]
        elif kind == "account":
            a = self.store.find_account(self.data, ident)
            parts = [a["name"]] if a else []
        self.show_crumb(parts)

    def place_sash(self):
        if not self.body.winfo_exists() or self.page not in ("scenario", "account") or self.list_hidden:
            return
        width = self.body.winfo_width()
        if not self.body.winfo_ismapped() or width < 200:   # chua ve xong -> thu lai
            self.root.after(80, self.place_sash)
            return
        if not self._sash_set:
            self._sash_set = True
            # Nguoi dung keo vach ngan -> nho vi tri (dung lai khi quay ve trang danh sach)
            self.body.bind("<ButtonRelease-1>", lambda _e: setattr(self, "_sash_user", self.body.sashpos(0)), add="+")
        pos = getattr(self, "_sash_user", None) or min(460, int(width * 0.36))
        self.body.sashpos(0, min(pos, width - 360))

    def update_nav(self):
        unseen = self.total_unseen() if hasattr(self.store, "INBOX_DEFAULTS") else 0
        for key, text in self.NAV:
            parts = self.nav_items.get(key)
            if not parts:
                continue
            _item, label, badge = parts
            on = key == self.page
            label.configure(fg="#ffffff" if on else NAV_FG, font=FONT_SEMI if on else FONT)
            if key == "inbox" and unseen:   # .nav .it .b: so do tron
                badge.configure(text=str(unseen))
                badge.pack(side="right", padx=(0, 8))
            else:
                badge.pack_forget()
            self.paint_nav(key, NAV_ON if on else NAV_BG)

    def paint_nav(self, key, bg):
        item, label, _badge = self.nav_items[key]
        item.configure(bg=bg)
        label.configure(bg=bg)

    def total_unseen(self):
        import fb_login
        return sum(len(fb_login.unseen_inbox(self.account_dir(a))) for a in self.data["accounts"])

    def refresh_page(self):
        """Ve lai trang dang mo (Tong quan / Tin nhan / Cai dat) sau khi co so lieu moi."""
        if self.page in ("home", "inbox", "settings"):
            self.show_page(self.page)
        else:
            self.update_nav()

    # ------------------------------------------------------------ trang Tong quan
    def kpi(self, parent, col, number, label, color=None):
        stat_card(parent, col, number, label, color, ("Segoe UI", 18, "bold"), padx=(0 if col == 0 else 10, 0))

    def today_stats(self):
        """So lieu hom nay cho Tong quan: bai da dang, khach tim duoc, tin nhan chua xem."""
        import fb_login
        from datetime import datetime
        start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        today = datetime.now().strftime("%Y-%m-%d")
        posts = leads = 0
        for a in self.data["accounts"]:
            for folder in self.identity_dirs(a):   # task 003: cong moi danh tinh cua tai khoan
                sent = fb_login.load_results(folder).get("sent", {})
                posts += sum(1 for entries in sent.values() for e in entries if e[1] == "post" and e[0] >= start)
            for c in a["campaigns"]:
                if c.get("kind") != "monitor":
                    continue
                path = self.base_dir / "campaigns" / c["id"] / "bai_thu_thap.jsonl"
                try:
                    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError:
                    continue
                leads += sum(1 for line in lines if f'"time": "{today}' in line and '"gui_telegram"' in line)
        return posts, leads

    def week_stats(self, account):
        """(bai da dang 7 ngay, bai duoc duyet 7 ngay, khach tim duoc hom nay) cua 1 tai khoan."""
        import fb_login
        from datetime import datetime
        since = time.time() - 7 * 86400
        posts = approved = 0
        for folder in self.identity_dirs(account):   # task 003: cong moi danh tinh cua tai khoan
            st = fb_login.load_results(folder)
            for slug, entries in st.get("sent", {}).items():
                mine = [e for e in entries if e[1] == "post" and e[0] >= since]
                if not mine:
                    continue
                posts += len(mine)
                group = st.get("groups", {}).get(slug)
                if group:
                    statuses = fb_login.item_statuses(group, [{"time": e[0], "kind": e[1],
                                                               "post_id": e[2] if len(e) > 2 else "",
                                                               "snippet": e[3] if len(e) > 3 else ""} for e in mine])
                    approved += statuses.count("approved")
        today, leads = datetime.now().strftime("%Y-%m-%d"), 0
        for c in account["campaigns"]:
            if c.get("kind") != "monitor":
                continue
            try:
                lines = (self.base_dir / "campaigns" / c["id"] / "bai_thu_thap.jsonl").read_text(
                    encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            leads += sum(1 for line in lines if f'"time": "{today}' in line and '"gui_telegram"' in line)
        return posts, approved, leads

    def alerts(self):
        """Viec can nguoi dung xu ly: [(muc do 'bad'|'warn', tieu de, giai thich, nhan nut, ham)]."""
        import fb_login
        out = []
        for a in self.data["accounts"]:
            acc_dir = self.account_dir(a)
            go = lambda a=a: self.select(f"account:{a['id']}")
            if not self.account_usable(a):
                st = account_status.LABELS[self.account_state(a)["status"]]
                running = sum(1 for s in self.data["scenarios"] if a["id"] in s["accounts"])
                out.append(("bad", f"{a['name']}: {st}", (f"{running} kịch bản đang dừng · " if running else "")
                            + "bấm Đăng nhập → Chrome mở ra → đăng nhập Facebook", "Đăng nhập", go))
                continue
            pause = fb_login.nick_pause(acc_dir)
            if pause:
                out.append(("warn", f"{a['name']}: tạm nghỉ đến {fb_login.pause_text(pause)}",
                            f"{pause.get('reason', '')} · hết giờ nghỉ tool tự chạy lại", "Xem", go))
            try:
                import upstt_store
                ids = self.store.account_identity_ids(a) if hasattr(self.store, "account_identity_ids") else ["self"]
                waiting = 0
                for ident in ids:   # task 003: cong moi danh tinh
                    st = upstt_store.join_state(a["id"]) if ident == "self" else upstt_store.join_state(a["id"], identity=ident)
                    waiting += sum(1 for g in st.values() if g.get("status") in upstt_store.JOIN_WAITING)
            except Exception:
                waiting = 0
            if waiting:
                out.append(("warn", f"{a['name']}: đang chờ duyệt vào {waiting} nhóm",
                            "chưa vào thì chưa đăng / quét được nhóm riêng tư", "Xem", go))
        for s in self.data["scenarios"]:
            if not s["enabled"]:
                continue
            for a in self.store.ticked_accounts(self.data, s):
                c = self.store.member_campaign(self.data, s, a["id"])
                if c and self.account_usable(a) and self.result_level(a, c) == 3:
                    out.append(("bad", f"{self.KINDS[s['kind']].ITEM_ICON if self.KINDS else ''} {s['name']} – "
                                       f"{a['name']}: có nhóm hay bị từ chối / gỡ",
                                "xem tab Kết quả tổng hợp để biết nhóm nào, nên bỏ hay đăng thưa", "Xem",
                                lambda s=s, a=a: self.select(f"member:{s['id']}|{a['id']}")))
        return out + self.extra_alerts()

    def extra_alerts(self):
        return []

    def upcoming(self, limit=8):
        """Lich sap chay trong 24h: [(datetime, viec, tai khoan)]."""
        from datetime import datetime, timedelta
        now = datetime.now()
        out = []
        for a in self.data["accounts"]:
            if not self.account_usable(a) or self.data.get("paused"):
                continue
            for c in a["campaigns"]:
                if not c.get("enabled", True):
                    continue
                if c.get("kind") == "monitor":
                    try:
                        import monitor_store
                        last = datetime.fromtimestamp(monitor_store.last_scan(c["id"]) or now.timestamp())
                        every = monitor_store.scan_minutes(c)
                    except Exception:
                        continue
                    nxt = max(now, last + timedelta(minutes=every))
                    out.append((nxt, f"🔎 Quét “{c['name']}” (mỗi {every} phút)", a["name"]))
                    continue
                days = set(c.get("weekdays") or [])
                for t in c.get("times", []):
                    try:
                        hh, mm = (int(x) for x in t.split(":"))
                    except ValueError:
                        continue
                    for add in (0, 1):
                        when = (now + timedelta(days=add)).replace(hour=hh, minute=mm, second=0, microsecond=0)
                        if when > now and (not days or when.weekday() in days):
                            out.append((when, f"📝 {c['name']}", a["name"]))
                            break
        return sorted(out, key=lambda x: x[0])[:limit]

    def build_home(self, parent):
        from datetime import datetime
        if not self.data["accounts"]:
            ttk.Label(parent, text="Bắt đầu trong 3 bước", style="Title.TLabel").pack(anchor="w", pady=(10, 6))
            for n, text in enumerate(("Thêm tài khoản Facebook (trang 👤 Tài khoản → ＋ Tài khoản).",
                                      "Đăng nhập tài khoản đó (Chrome mở ra → đăng nhập → bấm ✔ Đăng nhập xong).",
                                      "Tạo kịch bản (trang 📋 Kịch bản → ＋ Đăng bài / ＋ Theo dõi) và tick tài khoản."), 1):
                ttk.Label(parent, text=f"{n}.  {text}").pack(anchor="w", pady=2)
            ttk.Button(parent, text="＋ Thêm tài khoản", style="Accent.TButton" if sv_ttk else "TButton",
                       command=lambda: (self.show_page("account"), self.add_account())).pack(anchor="w", pady=12)
            return
        import fb_login
        stats = {a["id"]: self.week_stats(a) for a in self.data["accounts"]}
        posts_today, _leads_today = self.today_stats()
        approved = sum(v[1] for v in stats.values())
        leads = sum(v[2] for v in stats.values())
        unseen = self.total_unseen() if hasattr(self.store, "INBOX_DEFAULTS") else 0
        alerts = self.alerts()
        running = sum(1 for s in self.data["scenarios"] if s["enabled"] and s["accounts"])
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(4, 12))
        for i in range(4):
            row.columnconfigure(i, weight=1, uniform="k")
        self.kpi(row, 0, posts_today, f"bài đăng hôm nay · {running} kịch bản đang chạy", "#1d4ed8")
        self.kpi(row, 1, approved, "bài được duyệt (7 ngày)", GREEN)
        self.kpi(row, 2, leads, "khách mới tìm được hôm nay (theo dõi)", AMBER)
        self.kpi(row, 3, unseen, "tin nhắn khách chưa xem", RED if unseen else None)

        cols = ttk.Frame(parent)
        cols.pack(fill="x")
        cols.columnconfigure(0, weight=1, uniform="h")
        cols.columnconfigure(1, weight=1, uniform="h")
        left = ttk.Frame(cols)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = ttk.Frame(cols)
        right.grid(row=0, column=1, sticky="nsew")

        box = section(left, "⚠ Cần bạn xử lý")
        if alerts:
            box.add_pill(str(len(alerts)), AMBER, "#fff4e0")
        if not alerts:
            ttk.Label(box, text="✅ Không có việc gì cần xử lý.", style="Ok.TLabel").pack(anchor="w", pady=(0, 8))
        # .todo: o bieu tuong 26px nen mau · tieu de chu dam mau thuong · goi y xam · nut nho · ke ngang giua cac dong
        icons = {"bad": ("!", RED, "#fde8e8"), "warn": ("!", AMBER, "#fff4e0")}
        shown = alerts[:10]
        for n, (level, title, hint, btn, cmd) in enumerate(shown):
            line = ttk.Frame(box)
            line.pack(fill="x", pady=8)
            mark, fg, bg = icons.get(level, ("i", "#1d4ed8", ACCENT_BG))
            tk.Label(line, text=mark, fg=fg, bg=bg, font=("Segoe UI", 10, "bold"), width=2).pack(
                side="left", anchor="n", ipady=1, padx=(0, 10))
            text = ttk.Frame(line)
            text.pack(side="left", fill="x", expand=True)
            fit_wrap(ttk.Label(text, text=title, justify="left"), text)
            if hint:
                fit_wrap(ttk.Label(text, text=hint, style="Hint.TLabel", justify="left"), text)
            ttk.Button(line, text=btn, command=cmd, style="Small.TButton").pack(side="right", anchor="n",
                                                                                 padx=(10, 0))
            if n < len(shown) - 1 or unseen:
                tk.Frame(box, height=1, bg=LINE).pack(fill="x")
        if unseen:
            ttk.Button(box, text=f"💬 Xem {unseen} tin nhắn khách →", command=lambda: self.show_page("inbox"),
                       style="Small.TButton").pack(anchor="w", pady=(8, 4))

        box = section(right, "🕒 Sắp chạy")
        items = self.upcoming()
        if not items:
            ttk.Label(box, text="Không có lịch nào sắp chạy" + (" (đang tạm dừng toàn bộ)." if self.data.get("paused")
                                                                else "."), style="Hint.TLabel").pack(anchor="w", pady=4)
        else:
            up = ttk.Treeview(box, columns=("when", "what", "who"), show="headings", height=len(items))
            for cid, title, width in (("when", "Giờ", 80), ("what", "Việc", 260), ("who", "Tài khoản", 120)):
                up.heading(cid, text=title, anchor="w")
                up.column(cid, width=width, anchor="w", stretch=cid == "what")
            for when, what, who in items:
                day = "" if when.date() == datetime.now().date() else " (mai)"
                up.insert("", "end", values=(f"{when:%H:%M}{day}", what, who))
            up.pack(fill="x", pady=(0, 8))

        box = section(parent, "👤 Tài khoản")
        tree = ttk.Treeview(box, columns=("name", "state", "scripts", "week", "leads", "msg"), show="headings",
                            height=min(8, max(2, len(self.data["accounts"]))))
        for cid, title, width in (("name", "Tài khoản", 250), ("state", "Trạng thái", 180),
                                  ("scripts", "Kịch bản", 110), ("week", "Đăng / duyệt 7 ngày", 140),
                                  ("leads", "Khách mới", 90), ("msg", "Tin nhắn", 80)):
            tree.heading(cid, text=title, anchor="w")
            tree.column(cid, width=width, anchor="w", stretch=cid == "name")
        tree.tag_configure("bad", foreground=RED)
        tree.tag_configure("warn", foreground=AMBER)
        for a in self.data["accounts"]:
            pause = fb_login.nick_pause(self.account_dir(a)) if self.account_usable(a) else None
            state = (account_status.LABELS[self.account_state(a)["status"]] if not self.account_usable(a) else
                     f"tạm nghỉ đến {fb_login.pause_text(pause)}" if pause else "hoạt động")
            mine = [s for s in self.data["scenarios"] if a["id"] in s["accounts"] and s["enabled"]]
            kinds = {}
            for s in mine:
                icon = self.KINDS[s["kind"]].ITEM_ICON if self.KINDS else "•"
                kinds[icon] = kinds.get(icon, 0) + 1
            n = len(fb_login.unseen_inbox(self.account_dir(a))) if hasattr(self.store, "INBOX_DEFAULTS") else 0
            p7, ok7, lead = stats[a["id"]]
            tree.insert("", "end", iid=a["id"], values=(self.account_label(a), state,
                                                        "  ".join(f"{k} {v}" for k, v in kinds.items()) or "—",
                                                        f"{p7} / {ok7}", lead or "—", n or "—"),
                        tags=["bad"] if not self.account_usable(a) else (["warn"] if pause else []))
        tree.pack(fill="x", pady=(0, 8))
        pill_cells(tree, ["state"])
        pill_cells(tree, ["msg"], lambda t: (RED, "#fde8e8") if str(t).strip().isdigit() else None)   # so tin do
        box.add_link("Xem tất cả →", lambda: self.show_page("account"))
        tree.bind("<Double-1>", lambda e: tree.focus() and self.select(f"account:{tree.focus()}"))
        ttk.Label(box, text="Bấm đúp 1 tài khoản để mở.", style="Hint.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Label(parent, text=f"Số liệu lúc {datetime.now():%H:%M}. Kết quả duyệt bài đúng tới lần "
                               "'🔄 Cập nhật toàn bộ' gần nhất.", style="Hint.TLabel").pack(anchor="w")

    # ------------------------------------------------------------ trang Tin nhan (moi tai khoan)
    def build_inbox_page(self, parent):
        import fb_login
        from datetime import datetime
        if not hasattr(self.store, "INBOX_DEFAULTS"):
            return
        settings = self.store.inbox_settings(self.data)
        # (ban thiet ke 1) hang loc: nut loc · Tai khoan ▾ · ben phai trang thai tu kiem tra + Kiem tra ngay
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(4, 8))
        names = ["Mọi tài khoản"] + [a["name"] for a in self.data["accounts"]]
        who = tk.StringVar(value=names[0])
        view = tk.StringVar(value="unseen")
        unseen_n = self.total_unseen()
        chips(bar, view, [("unseen", f"Chưa xem {unseen_n}" if unseen_n else "Chưa xem"), ("all", "Tất cả 7 ngày"),
                          ("inbox", "Hộp thư"), ("requests", "Tin nhắn chờ"), ("spam", "Spam")],
              command=lambda: fill())
        combo = ttk.Combobox(bar, values=names, textvariable=who, state="readonly", width=18)
        combo.pack(side="left", padx=(4, 12))
        ttk.Button(bar, text="⚙", command=lambda: self.show_page("settings"), style="Small.TButton",
                   width=3).pack(side="right")
        check_btn = ttk.Button(bar, text="🔄 Kiểm tra ngay", style="Small.TButton")
        check_btn.pack(side="right", padx=6)
        ttk.Label(bar, text=(f"Tự kiểm tra mỗi {settings['minutes']} phút" if settings["enabled"] else
                             "Tự kiểm tra đang TẮT")
                  + (" · Telegram: ✓ đã kết nối" if settings["telegram_token"] else " · chưa có Telegram"),
                  style="Hint.TLabel").pack(side="right", padx=(0, 4))
        cols = ("pick", "name", "acc", "folder", "snippet", "time", "reply")
        box = tk.Frame(parent, bg=PAGE_BG, highlightthickness=1, highlightbackground=LINE, highlightcolor=LINE)
        box.pack(fill="x")
        tree = ttk.Treeview(box, columns=cols, show="headings", height=3, selectmode="extended")
        for cid, title, width in (("pick", "", 36), ("name", "Người nhắn", 170), ("acc", "Tài khoản", 120),
                                  ("folder", "Mục", 100), ("snippet", "Tin nhắn", 400), ("time", "Lúc", 90),
                                  ("reply", "", 100)):
            tree.heading(cid, text=title, anchor="w")
            tree.column(cid, width=width, anchor="center" if cid in ("pick", "reply") else "w",
                        stretch=cid == "snippet")
        sb = ttk.Scrollbar(box, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        folder_style = lambda t: ((RED, "#fde8e8") if "spam" in str(t).casefold() else
                                  (MUTED, "#eef0f3") if str(t).strip() else None)
        redraw = [pill_cells(tree, ["folder"], folder_style),
                  pill_cells(tree, ["reply"], lambda t: ("#ffffff", ACCENT) if str(t).strip() else None)]
        rows = {}
        act = ttk.Frame(parent)
        act.pack(fill="x", pady=(8, 0))
        empty = ttk.Label(act, text="", style="Hint.TLabel")

        def ticks(*_a):   # o tick = dong dang chon
            for iid in rows:
                tree.set(iid, "pick", "☑" if iid in tree.selection() else "☐")

        def fill(*_a):
            tree.delete(*tree.get_children())
            rows.clear()
            want, mode = who.get(), view.get()
            since = time.time() - 7 * 86400
            for a in self.data["accounts"]:
                if want != names[0] and a["name"] != want:
                    continue
                if mode == "all":   # ca tin da xem (7 ngay), moi nhat truoc
                    threads = fb_login.load_inbox(self.account_dir(a))["threads"]
                    items = sorted((dict(v, id=k) for k, v in threads.items() if v.get("time", 0) >= since),
                                   key=lambda v: -v.get("time", 0))
                else:
                    items = [t for t in fb_login.unseen_inbox(self.account_dir(a))
                             if mode == "unseen" or t.get("folder") == mode]
                for t in items:
                    iid = tree.insert("", "end", values=(
                        "☐", t.get("name", ""), a["name"], fb_login.INBOX_FOLDER_LABEL.get(t.get("folder"), ""),
                        t.get("snippet", ""), f"{datetime.fromtimestamp(t.get('time', 0)):%H:%M %d/%m}",
                        "↗ Trả lời"))
                    rows[iid] = (a, t)
            if not rows:
                tree.insert("", "end", values=("", "", "", "", "✅ Không có tin nhắn chưa xem.", "", ""))
            tree.configure(height=max(1, min(14, len(rows))))
            empty.configure(text="“↗ Trả lời” mở Chrome của đúng tài khoản tại cuộc trò chuyện. Trả lời xong đóng "
                                 "Chrome. Tool chỉ thấy câu cuối của mỗi cuộc trò chuyện.")
            for r in redraw:
                r()

        def picked():
            return [rows[i] for i in tree.selection() if i in rows]

        def reply(_e=None):
            items = picked()
            if not items:
                messagebox.showinfo("Tin nhắn", "Chọn 1 dòng trong bảng trước.")
                return
            a, t = items[0]
            self.open_in_account(a, t["url"])
            fb_login.mark_inbox_seen(self.account_dir(a), [t["id"]])
            fill()
            self.update_nav()

        def seen():
            for a, t in picked():
                fb_login.mark_inbox_seen(self.account_dir(a), [t["id"]])
            fill()
            self.update_nav()

        def check_now():
            accounts = [a for a in self.data["accounts"] if self.account_usable(a)
                        and (who.get() == names[0] or a["name"] == who.get())]
            runner = next((k for _key, k in self.all_kinds() if hasattr(k, "run_accounts")), None)
            if not accounts or not runner:
                messagebox.showinfo("Tin nhắn", "Chưa có tài khoản nào đã đăng nhập.")
                return
            runner.run_accounts([(a, ["--check-inbox"]) for a in accounts], "Kiểm tra tin nhắn",
                                done=lambda: self.page == "inbox" and self.show_page("inbox"))
            self.flash(f"Đang kiểm tra tin nhắn {len(accounts)} tài khoản (chạy ngầm, xem tiến độ ở dưới cùng).")

        def on_click(e):   # bam o "↗ Tra loi" cua dong
            iid = tree.identify_row(e.y)
            if iid in rows and tree.identify_column(e.x) == "#7":
                tree.selection_set(iid)
                reply()

        ttk.Button(act, text="✔ Đánh dấu đã xem", command=seen, style="Small.TButton").pack(side="left")
        empty.pack(side="left", padx=(10, 0))
        check_btn.configure(command=check_now)
        tree.bind("<Double-1>", reply)
        tree.bind("<ButtonRelease-1>", on_click, add="+")
        tree.bind("<<TreeviewSelect>>", ticks, add="+")
        combo.bind("<<ComboboxSelected>>", fill)
        fill()

    # ------------------------------------------------------------ trang Cai dat
    def build_settings_page(self, parent):
        # Luoi 2 cot (ban thiet ke 1): Tin nhan khach | Tu cham bai · Ban quyen · Toan bo tool; duoi: Rule, Nhat ky.
        grid = ttk.Frame(parent)
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=1, uniform="s")
        grid.columnconfigure(1, weight=1, uniform="s")
        left = ttk.Frame(grid)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = ttk.Frame(grid)
        right.grid(row=0, column=1, sticky="nsew")
        if hasattr(self.store, "INBOX_DEFAULTS"):
            self.inbox_settings_form(section(left, "💬 Theo dõi tin nhắn khách"))
        if hasattr(self.store, "AUTO_CARE_HOURS"):
            box = section(right, "🔄 Tự cập nhật trạng thái")
            _default, low, high = self.store.AUTO_CARE_HOURS
            self.auto_care_var = tk.BooleanVar(value=bool(self.data.get("auto_care")))
            box.add_switch(self.auto_care_var, self.toggle_auto_care)
            row = ttk.Frame(box)
            row.pack(anchor="w")
            ttk.Label(row, text="Mỗi").pack(side="left")
            self.auto_care_hours_var = tk.StringVar(value=str(self.store.auto_care_hours(self.data)))
            hours = no_wheel(NumBox(row, from_=low, to=high, width=3, textvariable=self.auto_care_hours_var,
                                         command=self.change_auto_care_hours))
            hours.pack(side="left", padx=6)
            hours.bind("<Return>", lambda _e: self.change_auto_care_hours())
            hours.bind("<FocusOut>", lambda _e: self.change_auto_care_hours())
            ttk.Label(row, text="giờ cập nhật 1 lần").pack(side="left")
            fit_wrap(ttk.Label(box, text="Tool tự vào Facebook xem lại trạng thái bài / bình luận ở mọi nhóm của các "
                                         "kịch bản đang bật – cả Đăng bài lẫn Theo dõi (chờ duyệt / đã duyệt / bị từ "
                                         "chối / bị gỡ). Cập nhật xong: bài của bạn mới được duyệt thì tự chăm theo "
                                         "nội dung 'Chăm bài' của kịch bản (mỗi bài 1 lần, tối đa "
                                         f"{getattr(self.store, 'AUTO_CARE_MAX', 5)} bài / tài khoản / lượt). "
                                         "Bật / tắt / đổi giờ là lưu luôn.", style="Hint.TLabel", justify="left"),
                     box).pack_configure(pady=(6, 0))
        self.license_section(right)
        self.tool_section(right)
        if getattr(self.store, "RULE_SPEC", None):
            box = section(parent, "⚙ Rule khi lỗi")
            box.add_pill("dùng chung cho mọi kịch bản Đăng bài & Theo dõi, mọi tài khoản")
            self.rules_box(box)
            ttk.Label(box, text="Sửa xong bấm 💾 Lưu ở góc trên.", style="Hint.TLabel").pack(anchor="w", pady=(0, 4))
        self.log_section(parent)

    def tool_section(self, parent):
        """Khung 'Toan bo tool': dang chay / tam dung + so lich Windows dang co."""
        box = section(parent, "⏸ Toàn bộ tool")
        paused = bool(self.data.get("paused"))
        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Label(row, text="Đang TẠM DỪNG toàn bộ  ·" if paused else "Đang chạy theo lịch  ·",
                  foreground=AMBER if paused else TEXT).pack(side="left")
        ttk.Button(row, text="▶ Chạy lại toàn bộ" if paused else "⏸ Tạm dừng toàn bộ", style="Small.TButton",
                   command=lambda: (self.toggle_pause(), self.refresh_page())).pack(side="left", padx=(8, 0))
        try:
            entries = self.store.schedule_entries(self.data)
        except Exception:
            entries = []
        fresh = self.schedule_key(entries) == self.saved_schedule
        line = ttk.Frame(box)
        line.pack(fill="x", pady=(8, 0))
        ttk.Label(line, text="Lịch Windows:").pack(side="left")
        tk.Label(line, text=f"✓ đã cập nhật · {len(entries)} lịch" if fresh else "chưa cập nhật – bấm 💾 Lưu",
                 fg=GREEN if fresh else AMBER, bg="#e7f6ec" if fresh else "#fff4e0",
                 font=("Segoe UI Semibold", 9), padx=7).pack(side="left", padx=(8, 0))

    def license_section(self, parent):
        pass

    def log_section(self, parent):
        """Nhat ky (thay nut 'Xem nhat ky' cu): moi viec 1 nhat ky - tai khoan, noi dung dang, tin nhan, tu cham."""
        box = section(parent, "📄 Nhật ký")
        logs = self.base_dir / "logs"
        names = {}
        for a in self.data["accounts"]:
            names[a["id"]] = f"👤 {a['name']} (quét theo dõi, đăng nhập, nhóm)"
            for c in a["campaigns"]:
                icon = self.KINDS[c["kind"]].ITEM_ICON if self.KINDS and c.get("kind") in self.KINDS else "•"
                names[c["id"]] = f"{icon} {c['name']} – {a['name']}"
        names.update({"tin_nhan": "💬 Kiểm tra tin nhắn", "tu_cham_bai": "🔄 Tự cập nhật + chăm bài", "ket_qua": "🔄 Cập nhật kết quả"})
        found = []
        if logs.exists():
            for d in logs.iterdir():
                f = d / "nhat_ky.txt"
                if d.is_dir() and f.exists():
                    found.append((f.stat().st_mtime, names.get(d.name, f"• {d.name}"), f))
        found.sort(reverse=True)
        if not found:
            ttk.Label(box, text="Chưa có nhật ký nào.", style="Hint.TLabel").pack(anchor="w", pady=(0, 8))
            return
        labels = [x[1] for x in found]
        var = tk.StringVar(value=labels[0])
        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Label(row, text="Xem nhật ký:").pack(side="left")
        combo = ttk.Combobox(row, values=labels, textvariable=var, state="readonly", width=48)
        combo.pack(side="left", padx=6)
        tf, text = text_box(box, 14, wrap="word")
        tf.pack(fill="x", pady=(6, 4))

        def show(*_a):
            path = found[labels.index(var.get())][2]
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                lines = []
            text.configure(state="normal")
            text.delete("1.0", "end")
            text.insert("1.0", "\n".join(reversed(lines[-400:])) or "(trống)")
            text.configure(state="disabled")

        ttk.Button(row, text="🔄 Làm mới", command=show).pack(side="left")
        ttk.Button(row, text="Mở file", command=lambda: os.startfile(str(found[labels.index(var.get())][2]))).pack(
            side="left", padx=6)
        ttk.Label(box, text="Mới nhất ở trên cùng (400 dòng gần nhất).", style="Hint.TLabel").pack(anchor="w", pady=(0, 8))
        combo.bind("<<ComboboxSelected>>", show)
        show()

    # ------------------------------------------------------------ cay
    # Tk tren Windows khong ve emoji mau (🔴🟠🟢 thanh vong gach cheo) -> cham ● + mau chu theo tag lv0..lv3.
    LEVEL_TEXT = {-1: "", 0: "● tốt", 1: "○ chưa rõ", 2: "● cần xem", 3: "● lỗi"}

    def account_label(self, account, maxlen=None):
        """'Tài khoản 4 · Nguyễn Văn A' (ten trong tool + ten Facebook) -> biet ngay tai khoan nao la ai."""
        fb = self.fb_name(account)
        text = account["name"] + (f" · {fb}" if fb and fb.lower() not in account["name"].lower() else "")
        return text if not maxlen or len(text) <= maxlen else text[:maxlen - 1] + "…"

    def refresh_tree_keep(self):
        """Ve lai cay, giu dong dang chon (sau khi chay ngam xong)."""
        try:
            kind, ident = self.selected()
            self.refresh_tree(f"{kind}:{ident}" if kind else None)
        except tk.TclError:
            pass

    def list_query(self, key):
        """(chu dang tim, nut loc dang chon) cua danh sach ben trai."""
        search = getattr(self, "list_search", {}).get(key)
        chip = getattr(self, "list_filter", {}).get(key)
        return (search.get().strip().casefold() if search else ""), (chip.get() if chip else "all")

    def chip_counts(self, key, counts):
        """Ghi so luong canh nhan nut loc (vd 'Tất cả 9')."""
        bar = getattr(self, "chip_bars", {}).get(key)
        if not bar or not bar.winfo_exists():
            return
        for w in chip_widgets(bar):
            if True:
                base = getattr(w, "base_text", None) or w.cget("text")
                w.base_text = base
                n = counts.get(str(w.cget("value")))
                w.configure(text=base if n is None else f"{base} {n}")

    def clear_list_filters(self):
        for var in getattr(self, "list_search", {}).values():
            var.set("")
        for var in getattr(self, "list_filter", {}).values():
            var.set("all")

    def account_paused(self, account):
        import fb_login
        try:
            return bool(fb_login.nick_pause(self.account_dir(account)))
        except Exception:
            return False

    def refresh_tree(self, select=None):
        self.store.materialize(self.data)
        for tree in self.trees.values():
            tree.delete(*tree.get_children())
        paused = bool(self.data.get("paused"))
        usable = {a["id"]: self.account_usable(a) for a in self.data["accounts"]}

        # ---- Kich ban: thu muc theo loai (📝 Dang bai / 🔎 Theo doi) > kich ban > tai khoan chay.
        # Cot: Gio / nhom · Ket qua. Kich ban loi xep len dau, kich ban tat xuong cuoi; gap / mo duoc va nho lai.
        tree = self.trees["scenario"]
        opened = self.ui_state().get("open", {})
        text, chip = self.list_query("scenario")
        counts = {"all": 0, "off": 0, "err": 0}
        for kind_key, k in self.all_kinds():
            items = []
            for s in (x for x in self.data["scenarios"] if x["kind"] == kind_key):
                members = []
                for a in self.store.ticked_accounts(self.data, s):
                    c = self.store.member_campaign(self.data, s, a["id"])
                    members.append((a, c, self.result_level(a, c) if c else -1))
                level = max((m[2] for m in members), default=-1)
                for key in ("all", kind_key, "off" if not s["enabled"] else "", "err" if s["enabled"] and level >= 2 else ""):
                    counts[key] = counts.get(key, 0) + 1
                if text and text not in s["name"].casefold() and not any(text in a["name"].casefold()
                                                                         for a, _c, _l in members):
                    continue
                if (chip in dict(self.all_kinds()) and chip != kind_key) or (chip == "off" and s["enabled"]) or \
                        (chip == "err" and not (s["enabled"] and level >= 2)):
                    continue
                items.append((level, s, members))
            if (text or chip != "all") and not items:
                continue
            items.sort(key=lambda x: (not x[1]["enabled"], -x[0] if x[0] >= 2 else 0))
            reds = sum(1 for lv, s, _m in items if lv == 3 and s["enabled"])
            oranges = sum(1 for lv, s, _m in items if lv == 2 and s["enabled"])
            folder = f"sgroup:{kind_key}"
            label = getattr(k, "FOLDER_LABEL", k.ITEM_NOUN.capitalize())
            summary = " · ".join(x for x in (f"{reds} lỗi" if reds else "", f"{oranges} cần xem" if oranges else "") if x)
            tree.insert("", "end", iid=folder, open=opened.get(folder, True),
                        tags=["folder"] + (["lv3"] if reds else (["lv2"] if oranges else [])),
                        text=f"{k.ITEM_ICON}  {label}  ({len(items)})", values=["", summary])
            for level, s, members in items:
                n = len(s["accounts"])
                tree.insert(folder, "end", iid=f"scenario:{s['id']}", open=opened.get(f"scenario:{s['id']}", True),
                            text=f"{k.ITEM_ICON if s['enabled'] else '⏸'}  {s['name']}"
                                 + ("" if n else "   (chưa tick tài khoản)"),
                            values=[k.tree_scenario_info(s),
                                    "đang tắt" if not s["enabled"] else self.LEVEL_TEXT[level]],
                            tags=[f"lv{level}"] if s["enabled"] else ["off"])
                for a, c, lv in members:
                    stopped = paused or not usable[a["id"]]
                    tree.insert(f"scenario:{s['id']}", "end", iid=f"member:{s['id']}|{a['id']}",
                                text=f"{'⛔' if stopped else '👤'}  {self.account_label(a)}",
                                values=[k.tree_member_info(a, c) if c else "",
                                        "chưa đăng nhập" if not usable[a["id"]] else
                                        ("tạm dừng" if stopped else self.LEVEL_TEXT[lv])],
                                tags=["bad"] if not usable[a["id"]] else ([f"lv{lv}"] if s["enabled"] else ["off"]))
        self.chip_counts("scenario", counts)

        # ---- Tai khoan (theo nhom tai khoan): ten trong tool · ten Facebook · trang thai dang nhap
        tree = self.trees["account"]
        groups = self.data.get("account_groups", [])
        text, chip = self.list_query("account")
        shown = []
        counts = {"all": 0, "msg": 0, "err": 0}
        for a in self.data["accounts"]:
            unseen = self.inbox_unseen_count(a) if hasattr(self.store, "INBOX_DEFAULTS") else 0
            counts["all"] += 1
            counts["msg"] += bool(unseen)
            counts["err"] += not usable[a["id"]] or self.account_paused(a)
            if text and text not in a["name"].casefold() and text not in (self.fb_name(a) or "").casefold():
                continue
            if (chip == "msg" and not unseen) or (chip == "err" and usable[a["id"]] and not self.account_paused(a)):
                continue
            shown.append((a, unseen))
        self.chip_counts("account", counts)
        for g in groups:
            members = [a for a, _u in shown if a.get("group") == g]
            if (text or chip != "all") and not members:
                continue
            tree.insert("", "end", iid=f"agroup:{g}", open=opened.get(f"agroup:{g}", True), tags=["folder"],
                        text=f"📁  {g}  ({len(members)})", values=["", ""])
        for a, unseen in shown:
            parent = f"agroup:{a['group']}" if a.get("group") in groups and tree.exists(f"agroup:{a['group']}") else ""
            state = self.account_state(a)["status"]
            icon = STATUS_UI[state][0]
            running = [s for s in self.data["scenarios"] if a["id"] in s["accounts"]]
            tree.insert(parent, "end", iid=f"account:{a['id']}",
                        text=f"{icon}  {a['name']}" + (f"   💬 {unseen}" if unseen else ""),
                        values=[self.fb_name(a) or "(chưa kiểm tra)",
                                account_status.LABELS[state] + (f" · {len(running)} kịch bản" if running else "")],
                        tags=[] if usable[a["id"]] else ["bad"])

        self._tree_base = {}
        for tree in self.trees.values():
            stack = list(tree.get_children())
            while stack:
                iid = stack.pop()
                self._tree_base[iid] = tree.item(iid, "text")
                stack.extend(tree.get_children(iid))
        if not self.update_tree_status():
            self.render_cards()
        if select:
            self.select(select, clear_filters=False)   # ve lai cay: giu bo loc dang dung

    def render_cards(self):
        for cards in getattr(self, "cards", {}).values():
            cards.render()

    # ------------------------------------------------------------ cap nhat ket qua: toan bo + icon tren cay
    _check_done = {}   # tai khoan -> (ok, thoi diem xong)

    def check_state(self, account_id):
        """'running' | ('ok', gio) | ('error', gio) | None."""
        proc = self._checks.get(account_id)
        if proc is not None and proc.poll() is None:
            return "running"
        if proc is not None:   # vua xong -> doc ket qua tu file tien do
            p = fb_login_progress(self.store.ACCOUNTS_DIR / account_id, finished=True)
            self._check_done[account_id] = (bool(p.get("ok")) and p.get("done", False), time.time())
            self._checks.pop(account_id, None)
        done = self._check_done.get(account_id)
        if done:
            from datetime import datetime
            return ("ok" if done[0] else "error", f"{datetime.fromtimestamp(done[1]):%H:%M}")
        return None

    def update_tree_status(self):
        """Gan icon sau ten tai khoan / noi dung: ⏳ dang cap nhat, ✅ da cap nhat (gio), ⚠ loi."""
        if not self.has_results or not hasattr(self, "_tree_base"):
            return False
        running = False
        for a in self.data["accounts"]:
            st = self.check_state(a["id"])
            running = running or st == "running"
            mark = "" if not st else ("   ⏳" if st == "running" else
                                      (f"   ✅ {st[1]}" if st[0] == "ok" else f"   ⚠ lỗi {st[1]}"))
            small = "" if not st else ("  ⏳" if st == "running" else ("  ✅" if st[0] == "ok" else "  ⚠"))
            for iid, suffix in [(f"account:{a['id']}", mark)] + [(self.member_iid(c["id"]), small)
                                                                for c in a["campaigns"]]:
                tree = self.trees[self.TREE_OF["member" if iid and iid.startswith("member") else "account"]]
                if iid and tree.exists(iid) and iid in self._tree_base:
                    tree.item(iid, text=self._tree_base[iid] + suffix)
        if hasattr(self, "refresh_all_btn"):
            self.refresh_all_btn.configure(text="⏳ Đang cập nhật…" if running else "🔄 Cập nhật toàn bộ")
            self.refresh_all_btn.state(["disabled"] if running else ["!disabled"])
        if running or not getattr(self, "_cards_after_check", False):
            self.render_cards()   # the hien ⏳ / ✅ khi dang / vua cap nhat
        self._cards_after_check = running
        return running

    def watch_checks(self):
        """Theo doi cac luot cap nhat dang chay -> doi icon tren cay; xong het thi ve lai cham mau."""
        if self.update_tree_status():
            self.root.after(1000, self.watch_checks)
        else:
            kind, ident = self.selected()
            self.refresh_tree(f"{kind}:{ident}" if kind else None)
            if self.page == "home":
                self.refresh_page()

    def refresh_all(self):
        """Nut 'Cap nhat toan bo': moi tai khoan xem lai trang 'Noi dung cua ban' cua tat ca nhom (chi xem)."""
        started = 0
        for a in self.data["accounts"]:
            if a["id"] not in self._checks and self.account_usable(a) and self.start_check(a):
                started += 1
        if not started:
            messagebox.showinfo("Cập nhật kết quả duyệt", "Không có tài khoản nào cần cập nhật (đang cập nhật dở, "
                                                    "chưa đăng nhập hoặc chưa có nhóm).")
            return
        self.flash(f"Đang cập nhật {started} tài khoản (chạy ngầm, chỉ xem) – xem icon ⏳ / ✅ ở cây bên trái.")
        self.watch_checks()

    def on_select(self, _event=None, force=False):
        kind, ident = self.selected()
        # Chon lai dung muc dang mo (vd sau khi Luu ve lai cay) -> giu nguyen tab / vi tri cuon.
        if not force and self.current == (kind, ident) and self.form:
            return
        if not kind:
            # Vua chuyen sang tab chua chon dong nao: mo dong dau tien; tab trong -> man huong dan cua tab do.
            tree = self.active_tree()
            first = tree.get_children()
            if first:
                leaf = first[0]
                while tree.get_children(leaf) and leaf.split(":", 1)[0] in ("sgroup", "agroup"):
                    leaf = tree.get_children(leaf)[0]
                tree.selection_set(leaf)
                tree.see(leaf)
                return
            self.commit_form()
            self.show_tab_intro()
            return
        self.commit_form()
        if kind == "account":
            self.show_account(self.store.find_account(self.data, ident))
        elif kind == "scenario":
            self.show_scenario(self.store.find_scenario(self.data, ident))
        elif kind == "member":
            sid, aid = ident.split("|", 1)
            s = self.store.find_scenario(self.data, sid)
            self.show_member(s, self.store.find_account(self.data, aid), self.store.member_campaign(self.data, s, aid))
        elif kind in ("agroup", "sgroup"):
            self.show_folder(kind, ident)
        elif kind == "campaign":
            self.show_item(*self.store.find_campaign(self.data, ident))

    def commit_form(self):
        if not self.current or not self.form:
            return []
        item = self.find(*self.current)
        if not item:
            return []
        errors = self.form.commit(item)
        if self.snapshot() != self.saved_snapshot:
            self.mark_dirty()
        return errors

    # ------------------------------------------------------------ ben phai
    def clear_right(self):
        for child in self.right.winfo_children():
            child.destroy()
        self.form = Form(self.mark_dirty)
        self.current = None
        self.login_status = None
        if hasattr(self, "crumb") and self.page in ("scenario", "account"):
            self.show_crumb([])

    def show_empty(self):
        self.clear_right()
        ttk.Label(self.right, text="Chưa có tài khoản nào.", style="Title.TLabel").pack(anchor="w", pady=(20, 4))
        ttk.Label(self.right, text="Bấm '＋ Tài khoản' ở bên trái để bắt đầu.", style="Sub.TLabel").pack(anchor="w")

    def show_account(self, account):
        """Trang tai khoan (giong ban thiet ke 1): dau trang = ten + trang thai + nut; noi dung chia 4 tab."""
        import fb_login
        self.clear_right()
        self.current = ("account", account["id"])
        self.set_crumb()
        state = self.account_state(account)
        usable = self.account_usable(account)
        acc_dir = self.account_dir(account)
        accent = "Accent.TButton" if sv_ttk else "TButton"

        # ---- dau trang: ten · trang thai · nut dang nhap / doi ten / xoa
        # (ban thiet ke 1: ten dam ben trai · vien thuoc trang thai + nut dang nhap ben phai; dong xam ben duoi)
        head = ttk.Frame(self.right)
        head.pack(fill="x")
        ttk.Label(head, text=account["name"], style="Title.TLabel").pack(side="left")
        pause = fb_login.nick_pause(acc_dir) if usable else None
        if usable:
            ttk.Button(head, text="Đăng xuất", style="Danger.TButton",
                       command=lambda: self.account_action(account, "logout")).pack(side="right")
            ttk.Button(head, text="Đổi tài khoản", command=lambda: self.account_action(account, "switch")).pack(
                side="right", padx=6)
            ttk.Button(head, text="Kiểm tra đăng nhập", command=lambda: self.account_action(account, "check")).pack(
                side="right")
        else:
            label = "Đăng nhập lại" if state["status"] == account_status.EXPIRED else "Đăng nhập"
            ttk.Button(head, text=label, style=accent, command=lambda: self.account_action(account, "login")).pack(
                side="right")
        pill = (f"⏸ tạm nghỉ đến {fb_login.pause_text(pause)}" if pause else
                account_status.LABELS[state["status"]].lower() if not usable else "hoạt động")
        fg, bg = ((AMBER, "#fff4e0") if pause else (GREEN, "#e7f6ec") if usable else (RED, "#fde8e8"))
        tk.Label(head, text=pill, fg=fg, bg=bg, font=("Segoe UI Semibold", 9), padx=8).pack(side="right", padx=10)
        fb_name = self.fb_name(account)
        sub_row = ttk.Frame(self.right)
        sub_row.pack(fill="x", pady=(2, 0))
        sub = [f"Facebook: {fb_name}" if fb_name else ("Bấm 'Kiểm tra đăng nhập' để hiện tên Facebook"
                                                      if usable else "Chưa đăng nhập Facebook")]
        if account.get("group"):
            sub.append(f"📁 {account['group']}")
        if state.get("time"):
            sub.append(f"kiểm tra lúc {state['time']}")
        ttk.Label(sub_row, text="  ·  ".join(sub), style="Sub.TLabel").pack(side="left")
        for text, cmd, color in (("🗑 Xóa", self.delete, RED), ("✎ Đổi tên", self.rename, ACCENT)):   # .btn.ghost
            link = tk.Label(sub_row, text=text, fg=color, bg=PAGE_BG, font=("Segoe UI", 9), cursor="hand2")
            link.pack(side="right", padx=(10, 0))
            link.bind("<Button-1>", lambda _e, c=cmd: c())
        if state.get("message") and state["status"] != account_status.OK:
            ttk.Label(self.right, text=state["message"], style="Hint.TLabel", wraplength=760).pack(anchor="w")
        if pause:
            row = ttk.Frame(self.right)
            row.pack(fill="x", pady=(8, 0))
            ttk.Label(row, text=f"⏸  Đang tạm nghỉ đến {fb_login.pause_text(pause)} – {pause.get('reason', '')}",
                      style="Warn.TLabel").pack(side="left")

            def resume():
                fb_login.clear_nick_pause(acc_dir)
                self.flash(f"'{account['name']}' chạy lại ngay từ lượt sau.")
                self.refresh_tree(f"account:{account['id']}")
                self.on_select(force=True)
            ttk.Button(row, text="Cho chạy lại ngay", command=resume).pack(side="right")

        # ---- dang nhap tung buoc: chi hien khi chua dang nhap / dang mo Chrome dang nhap
        login = ttk.Frame(self.right)
        login.pack(fill="x")
        self.login_status = ttk.Label(login, text="", style="Hint.TLabel", wraplength=760)   # pack khi co chu
        self.login_done_button = ttk.Button(login, text="✔  Đăng nhập xong – đóng Chrome",
                                            style=accent, command=lambda: self.finish_login(account))
        waiting = account["id"] in self.pending_login or (
            not usable and account_process_alive(acc_dir) and login_window_open(acc_dir / "browser_profile"))
        if not usable:
            ttk.Label(login, text=f"→ Các {self.ITEM_NOUN} của tài khoản này đang TẠM DỪNG cho đến khi đăng nhập.\n"
                                  "① Bấm Đăng nhập  ② Chrome mở ra → đăng nhập Facebook (điện thoại hỏi thì chọn "
                                  "'Đúng, là tôi')  ③ Thấy trang chủ thì bấm '✔ Đăng nhập xong'. Đăng nhập bằng CÁ "
                                  "NHÂN – Page của nick chọn ở 'Đăng bằng' trong kịch bản (không cần tài khoản riêng "
                                  "cho Page).", style="Warn.TLabel", wraplength=760,
                      justify="left").pack(anchor="w", pady=(4, 0))
        if waiting:
            self.show_login_waiting()
        same = getattr(self, "same_nick_banner", None)   # task 003: canh bao chung 1 nick + nut Gop
        if same:
            same(self.right, account)

        # ---- 4 tab
        mine = [s for s in self.data["scenarios"] if account["id"] in s["accounts"]]
        joined = fb_login.load_joined_groups(acc_dir)
        unseen = self.inbox_unseen_count(account) if hasattr(self.store, "INBOX_DEFAULTS") else 0
        tabs = LineTabs(self.right)
        tabs.pack(fill="both", expand=True, pady=(10, 0))
        entries = []
        if hasattr(self.store, "INBOX_DEFAULTS"):
            entries.append((f"💬 Tin nhắn ({unseen})", lambda p: self.inbox_section(p, account) if usable else
                            ttk.Label(p, text="Đăng nhập tài khoản trước để đọc tin nhắn.", style="Hint.TLabel").pack(
                                anchor="w", pady=10)))
        if hasattr(self, "identities_tab"):
            n_id = len(self.store.account_identities(account))
            entries.append((f"🎭 Cá nhân & Page ({n_id})", lambda p: self.identities_tab(p, account)))
        entries.append((f"📋 Kịch bản ({len(mine)})", lambda p: self.account_scenarios(p, account, mine)))
        entries.append((f"👥 Nhóm đã vào ({len(joined['groups'])})", lambda p: self.joined_groups_tab(p, account)))
        entries.append(("⚙ Thiết lập", lambda p: self.account_settings_tab(p, account)))
        self.lazy_tabs(tabs, entries, "account")

    def account_scenarios(self, parent, account, mine):
        usable = self.account_usable(account)
        if not mine:
            ttk.Label(parent, text="Chưa chạy kịch bản nào. Vào 📋 Kịch bản → chọn kịch bản → tab '👥 Tài khoản chạy' "
                                   "→ tick tài khoản này.", style="Hint.TLabel", wraplength=700).pack(anchor="w", pady=8)
            return
        for s in mine:
            c = self.store.member_campaign(self.data, s, account["id"])
            mark = "⛔  " if (s["enabled"] and not usable) else ("●  " if s["enabled"] else "⏸  ")
            k = self.KINDS[s["kind"]]
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=(0, 6))
            ttk.Label(row, text=mark + k.ITEM_ICON + " " + (k.account_item_summary(c) if c else s["name"]),
                      wraplength=640, justify="left").pack(side="left")
            ttk.Button(row, text="Mở ›", command=lambda s=s: self.select(f"member:{s['id']}|{account['id']}")).pack(
                side="right")

    def joined_groups_tab(self, parent, account):
        """Nhom tai khoan dang o (doc tu Facebook - nut 'Cap nhat trang thai' / lenh --joined-groups)."""
        import fb_login
        from datetime import datetime
        acc_dir = self.account_dir(account)
        data = fb_login.load_joined_groups(acc_dir)
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text=(f"{len(data['groups'])} nhóm · đọc lúc {datetime.fromtimestamp(data['time']):%H:%M %d/%m}"
                             if data["time"] else "Chưa đọc danh sách nhóm lần nào."), style="Hint.TLabel").pack(side="left")
        runner = next((k for _key, k in self.all_kinds() if hasattr(k, "run_accounts")), None)
        if runner and self.account_usable(account):
            ttk.Button(bar, text="🔄 Đọc lại từ Facebook", command=lambda: runner.run_accounts(
                [(account, ["--joined-groups"])], "Đọc nhóm đã tham gia",
                done=lambda: self.current == ("account", account["id"]) and self.on_select(force=True))).pack(side="right")
        box = ttk.Frame(parent)
        box.pack(fill="both", expand=True)
        tree = ttk.Treeview(box, columns=("name", "url"), show="headings", height=14)
        tree.heading("name", text="Nhóm", anchor="w")
        tree.heading("url", text="Link", anchor="w")
        tree.column("name", width=360, anchor="w")
        tree.column("url", width=360, anchor="w", stretch=True)
        sb = ttk.Scrollbar(box, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for g in data["groups"]:
            tree.insert("", "end", values=(g.get("name") or g.get("slug"), g.get("url", "")))
        tree.bind("<Double-1>", lambda e: tree.focus() and self.open_in_account(
            account, tree.item(tree.focus(), "values")[1]))
        ttk.Label(parent, text="Bấm đúp 1 nhóm để mở bằng Chrome của tài khoản.", style="Hint.TLabel").pack(
            anchor="w", pady=(6, 0))

    def account_settings_tab(self, parent, account):
        if self.ACCOUNT_FIELDS:
            box = section(parent, self.ACCOUNT_FIELDS_TITLE)
            for spec in self.ACCOUNT_FIELDS:
                self.form.add(box, account, *spec)
        self.account_extra(parent, account)

    def show_item(self, account, item):
        self.clear_right()
        self.current = ("campaign", item["id"])
        k = self.kind(item)
        top = ttk.Frame(self.right)
        top.pack(fill="x")
        ttk.Label(top, text=f"{k.ITEM_ICON}  {item['name']}", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text=f"   {k.ITEM_NOUN}  ·  👤 {account['name']}", style="Sub.TLabel").pack(side="left", pady=(6, 0))
        if self.data.get("paused"):
            self.banner("⏸  Tool đang TẠM DỪNG TOÀN BỘ - không có lịch nào chạy.", "▶ Chạy lại", self.toggle_pause)
        elif not self.account_usable(account):
            st = account_status.LABELS[self.account_state(account)["status"]]
            self.banner(f"⛔  Tài khoản '{account['name']}': {st} → {k.ITEM_NOUN} này đang TẠM DỪNG.",
                        "Đăng nhập lại", lambda: self.goto_account_login(account))
        self.form.add(self.right, item, "enabled", "bool", k.ENABLED_TITLE, k.ENABLED_HINT)
        tabs = LineTabs(self.right)
        tabs.pack(fill="both", expand=True)
        for tab_name, sections in k.item_tabs():
            scroll = ScrollFrame(tabs, self.bg)
            tabs.add(scroll, text=f"   {tab_name}   ")
            if sections is None:   # tab tu dung (vd man Dang tuong 2 cot giong AutoNuoi)
                k.build_tab(self, scroll.inner, tab_name, account, item)
                continue
            for title, specs in sections:
                box = section(scroll.inner, title)
                for spec in specs:
                    self.form.add(box, item, *spec)
                k.section_extra(title, box, item)

    # ------------------------------------------------------------ them / sua / xoa
    def add_account(self):
        self.commit_form()
        name = simpledialog.askstring("Thêm tài khoản", "Tên tài khoản (để bạn dễ nhận biết):",
                                      initialvalue=f"Tài khoản {len(self.data['accounts']) + 1}", parent=self.root)
        if not name or not name.strip():
            return
        account = self.new_account(name.strip())
        kind, ident = self.selected()
        if kind == "agroup":
            account["group"] = ident
        elif kind == "account":
            account["group"] = (self.store.find_account(self.data, ident) or {}).get("group", "")
        self.data["accounts"].append(account)
        self.mark_dirty()
        self.refresh_tree(f"account:{account['id']}")
        self.flash("Đã thêm tài khoản. Đăng nhập Facebook, rồi tick tài khoản này trong kịch bản muốn chạy.")

    def add_account_group(self):
        self.commit_form()
        name = simpledialog.askstring("Thêm nhóm tài khoản", "Tên nhóm (vd: Nick mới, Nick lâu năm, Thời trang):",
                                      parent=self.root)
        name = (name or "").strip()
        if not name or name in self.data["account_groups"]:
            return
        self.data["account_groups"].append(name)
        self.mark_dirty()
        self.refresh_tree(f"agroup:{name}")
        self.flash("Đã thêm nhóm. Chọn từng tài khoản → ô 'Nhóm tài khoản' để xếp vào nhóm.")

    def add_scenario(self, item_kind):
        self.commit_form()
        noun = self.KINDS[item_kind].ITEM_NOUN
        name = simpledialog.askstring(f"Thêm kịch bản {noun}", "Tên kịch bản (vd: Thiệp cưới, Khách sạn thú cưng):",
                                      parent=self.root)
        if not name or not name.strip():
            return
        s = self.new_scenario(name.strip(), item_kind)
        kind, ident = self.selected()
        if kind == "account":   # dang chon tai khoan -> tick san tai khoan do
            s["accounts"].append(ident)
        self.data["scenarios"].append(s)
        self.mark_dirty()
        self.refresh_tree(f"scenario:{s['id']}")
        self.flash("Đã thêm kịch bản. Soạn nội dung / nhóm / giờ, rồi tab '👥 Tài khoản chạy' tick các tài khoản.")

    def new_scenario(self, name, kind):
        return self.store.new_scenario(self.data, name, kind)

    def duplicate(self):
        self.commit_form()
        kind, ident = self.selected()
        if kind not in ("scenario", "member"):
            messagebox.showinfo("Nhân bản", "Chọn một kịch bản ở tab '📋 Kịch bản' trước.")
            return
        s = self.store.find_scenario(self.data, ident.split("|", 1)[0])
        copy = self.store.duplicate_scenario(self.data, s)
        self.data["scenarios"].insert(self.data["scenarios"].index(s) + 1, copy)
        self.mark_dirty()
        self.refresh_tree(f"scenario:{copy['id']}")
        self.flash("Đã nhân bản (chưa tick tài khoản nào). Sửa nội dung rồi tick tài khoản ở '👥 Tài khoản chạy'.")

    def rename(self):
        self.commit_form()
        kind, ident = self.selected()
        if kind == "member":
            kind, ident = "scenario", ident.split("|", 1)[0]
        if kind == "agroup":
            name = simpledialog.askstring("Đổi tên", "Tên mới:", initialvalue=ident, parent=self.root)
            name = (name or "").strip()
            if not name or name == ident:
                return
            groups = self.data["account_groups"]
            groups[groups.index(ident)] = name
            for a in self.data["accounts"]:
                if a.get("group") == ident:
                    a["group"] = name
            self.mark_dirty()
            self.refresh_tree(f"{kind}:{name}")
            return
        target = {"scenario": lambda: self.store.find_scenario(self.data, ident),
                  "account": lambda: self.store.find_account(self.data, ident)}.get(kind)
        item = target() if target else None
        if not item:
            return
        name = simpledialog.askstring("Đổi tên", "Tên mới:", initialvalue=item["name"], parent=self.root)
        if name and name.strip():
            item["name"] = name.strip()
            self.mark_dirty()
            self.refresh_tree(f"{kind}:{ident}")
            self.on_select(force=True)

    def delete(self):
        self.commit_form()
        kind, ident = self.selected()
        if not kind:
            return
        stamp = time.strftime("%Y%m%d_%H%M%S")
        if kind == "member":
            sid, aid = ident.split("|", 1)
            s = self.store.find_scenario(self.data, sid)
            account = self.store.find_account(self.data, aid)
            if not messagebox.askyesno("Bỏ tài khoản khỏi kịch bản",
                                       f"Bỏ tick '{account['name']}' khỏi kịch bản '{s['name']}'?\n\n"
                                       "Tài khoản này thôi chạy kịch bản; kết quả cũ vẫn giữ, tick lại là chạy tiếp."):
                return
            s["accounts"].remove(aid)
            self.current = None
            self.mark_dirty()
            self.refresh_tree(f"scenario:{sid}")
            self.on_select(force=True)
            self.flash("Đã bỏ tài khoản khỏi kịch bản. Bấm Lưu để cập nhật lịch.")
            return
        if kind == "scenario":
            s = self.store.find_scenario(self.data, ident)
            if not messagebox.askyesno("Xóa kịch bản", f"Xóa kịch bản '{s['name']}'?\n\n"
                                       f"{len(s['accounts'])} tài khoản đang chạy kịch bản này sẽ thôi chạy."):
                return
            self.store.delete_scenario(self.data, s, stamp)
        elif kind == "agroup":
            if not messagebox.askyesno("Xóa nhóm tài khoản", f"Xóa nhóm '{ident}'?\n\n"
                                       "Chỉ xóa nhóm, các tài khoản trong nhóm vẫn giữ nguyên."):
                return
            self.data["account_groups"].remove(ident)
            for a in self.data["accounts"]:
                if a.get("group") == ident:
                    a["group"] = ""
        elif kind == "account":
            account = self.store.find_account(self.data, ident)
            used = [s["name"] for s in self.data["scenarios"] if ident in s["accounts"]]
            if not messagebox.askyesno("Xóa tài khoản", f"Xóa '{account['name']}'?"
                                       + (f"\nTài khoản đang chạy {len(used)} kịch bản: {', '.join(used[:5])}."
                                          if used else "")
                                       + "\nPhiên đăng nhập của tài khoản này cũng bị bỏ."):
                return
            self.data["accounts"].remove(account)
            self.store.remove_account_everywhere(self.data, ident)
            old = self.store.ACCOUNTS_DIR / ident
            if old.exists():
                # Xoa du lieu dang nhap (token), doi ten thu muc de id moi khong dung lai.
                import shutil
                shutil.rmtree(old / "browser_profile", ignore_errors=True)
                try:
                    old.rename(self.store.ACCOUNTS_DIR / f"_da_xoa_{ident}_{stamp}")
                except OSError:
                    pass
        else:
            return
        self.current = None
        self.mark_dirty()
        self.refresh_tree()
        tree = self.active_tree()
        if tree.get_children():
            tree.selection_set(tree.get_children()[0])
        else:
            self.show_empty()
        self.flash("Đã xóa. Bấm Lưu để cập nhật lịch.")

    def on_delete_item(self, ident, stamp):
        pass

    # ------------------------------------------------------------ kich ban / thanh vien / Soan tin
    def show_scenario(self, s):
        """Kich ban: noi dung + nhom + gio (sua chung) va tab '👥 Tai khoan chay' (tick tai khoan, gian cach)."""
        self.clear_right()
        self.current = ("scenario", s["id"])
        self.set_crumb()
        k = self.KINDS[s["kind"]]
        # ---- dau trang (giong ban thiet ke 1): ten · cong tac Bat · Doi ten / Nhan ban / Xoa + 1 dong tom tat
        top = ttk.Frame(self.right)
        top.pack(fill="x")
        ttk.Label(top, text=f"{k.ITEM_ICON}  {s['name']}", style="Title.TLabel").pack(side="left")
        on = tk.BooleanVar(value=bool(s["enabled"]))

        def toggle():
            s["enabled"] = on.get()
            self.mark_dirty()
            self.refresh_tree(f"scenario:{s['id']}")
            switch.configure(text="Đang bật" if on.get() else "Đang tắt")
        switch = ttk.Checkbutton(top, text="Đang bật" if s["enabled"] else "Đang tắt", variable=on, command=toggle,
                                 style="Switch.TCheckbutton" if sv_ttk else "TCheckbutton")
        switch.pack(side="left", padx=(14, 0), pady=(4, 0))
        ttk.Button(top, text="🗑 Xóa", command=self.delete).pack(side="right")
        ttk.Button(top, text="⧉ Nhân bản", command=self.duplicate).pack(side="right", padx=6)
        ttk.Button(top, text="✎ Đổi tên", command=self.rename).pack(side="right")
        summary = getattr(k, "scenario_summary", None)
        ttk.Label(self.right, text=summary(s) if summary else f"{len(s['accounts'])} tài khoản chạy",
                  style="Sub.TLabel").pack(anchor="w", pady=(2, 4))
        if self.data.get("paused"):
            self.banner("⏸  Tool đang TẠM DỪNG TOÀN BỘ - không có lịch nào chạy.", "▶ Chạy lại", self.toggle_pause)
        elif not s["accounts"]:
            self.banner("Kịch bản chưa có tài khoản nào chạy. Mở tab '👥 Tài khoản chạy' để tick.",
                        "👥 Tick tài khoản",
                        lambda: tabs.select(next(i for i, (_n, x) in enumerate(k_tabs) if x == "accounts")))
        tabs = LineTabs(self.right)
        tabs.pack(fill="both", expand=True)
        k_tabs = k.scenario_tabs()
        def builder(tab_name, sections):
            def build(inner):
                if sections == "accounts":
                    self.members_tab(inner, s)
                elif sections is None:
                    k.build_scenario_tab(self, inner, tab_name, s)
                else:
                    for title, specs in sections:
                        box = section(inner, title)
                        for spec in specs:
                            self.form.add(box, s["settings"], *spec)
                        k.scenario_section_extra(title, box, s)
            return build
        self.lazy_tabs(tabs, [(f"{name} ({len(s['accounts'])})" if sec == "accounts" else name, builder(name, sec))
                              for name, sec in k_tabs], f"scenario:{s['kind']}")

    def lazy_tabs(self, tabs, entries, key):
        """Chi dung noi dung tab dang xem (tab khac dung khi bam vao) -> mo man nhanh; nho tab dang xem theo loai man."""
        pages = []
        for name, build in entries:
            scroll = ScrollFrame(tabs, self.bg)
            tabs.add(scroll, text=f"   {name}   ")
            pages.append([scroll, build, False, name])
        self._lazy_pages = (tabs, pages)
        if not hasattr(self, "_tab_pref"):
            self._tab_pref = {}

        def show(_e=None):
            try:
                i = tabs.index(tabs.select())
            except tk.TclError:
                return
            self._tab_pref[key] = i
            page = pages[i]
            if not page[2]:
                page[2] = True
                page[1](page[0].inner)
        tabs.bind("<<NotebookTabChanged>>", show)
        start = self._tab_pref.get(key, 0)
        tabs.select(start if start < len(pages) else 0)
        show()

    def stale_result_tabs(self):
        """Vua 'Cap nhat' xong o 1 tab ket qua -> cac tab 'Ket qua ...' khac da dung thi dung lai khi bam vao."""
        tabs, pages = getattr(self, "_lazy_pages", (None, []))
        try:
            current = tabs.index(tabs.select()) if tabs is not None else -1
        except tk.TclError:
            return
        for i, page in enumerate(pages):
            if i != current and page[2] and page[3].startswith("Kết quả"):
                for child in page[0].inner.winfo_children():
                    child.destroy()
                page[2] = False

    def members_tab(self, parent, s):
        """Giong AutoNuoi: danh sach tai khoan co o tick + gian cach gio giua 2 tai khoan."""
        is_post = s["kind"] == "post"
        k = self.KINDS[s["kind"]]
        # ---- thanh tren: loc nhom tai khoan · tick het / bo tick · gian cach (dang bai)
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 8))
        groups = ["Tất cả"] + self.data.get("account_groups", [])
        flt = tk.StringVar(value="Tất cả")
        chips(bar, flt, [(g, g) for g in groups], padx=(0, 2))   # loc nhanh theo nhom tai khoan
        ttk.Button(bar, text="Tick hết", command=lambda: tick_all(True)).pack(side="left", padx=(10, 0))
        ttk.Button(bar, text="Bỏ tick", command=lambda: tick_all(False)).pack(side="left", padx=(6, 0))
        gap_var = tk.StringVar(value=str(s.get("gap_minutes", 15)))
        if is_post:
            ttk.Label(bar, text="phút").pack(side="right")
            no_wheel(NumBox(bar, from_=0, to=240, increment=5, width=5, textvariable=gap_var)).pack(side="right",
                                                                                                        padx=6)
            ttk.Label(bar, text="Giãn cách giữa 2 tài khoản").pack(side="right")
        # ---- bang: Chay · Tai khoan · Trang thai · Gio dang / Quet · Nhom da vao
        try:
            licensed = self.store.licensed_account_ids(self.data)
        except Exception:
            licensed = {a["id"] for a in self.data["accounts"]}
        has_identity = hasattr(self.store, "account_identities")   # task 003: o 'Dang bang' tung tai khoan
        cols = [("run", "Chạy", 48, "center"), ("name", "Tài khoản", 200, "w"), ("state", "Trạng thái", 130, "w"),
                ("time", "Giờ đăng" if is_post else "Quét", 110, "w"), ("groups", "Nhóm", 130, "w"),
                ("open", "", 90, "center")]
        if has_identity:
            cols.insert(2, ("as", "Đăng bằng ▾", 150, "w"))
        col_open = f"#{len(cols)}"
        col_as = "#3" if has_identity else None
        # bang trong khung vien (ban thiet ke 1), cao vua so tai khoan
        box = tk.Frame(parent, bg=PAGE_BG, highlightthickness=1, highlightbackground=LINE, highlightcolor=LINE)
        box.pack(fill="x")
        tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings", selectmode="browse",
                            height=max(1, min(12, len(self.data["accounts"]))))
        for cid, title, width, anchor in cols:
            tree.heading(cid, text=title, anchor="center" if cid == "run" else "w")
            tree.column(cid, width=width, minwidth=40, anchor=anchor, stretch=cid == "name")
        tree.tag_configure("off", foreground="#8a8f98")
        tree.tag_configure("bad", foreground=RED)
        tree.tag_configure("on", background="#eef4ff")
        sb = ttk.Scrollbar(box, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        state_pills = pill_cells(tree, ["state"])
        # "Mở ›" / "🔑 Đăng nhập": nut nho nen xam nhat (.btn.sm)
        open_pills = pill_cells(tree, ["open"], lambda t: (TEXT, "#eef1f5") if str(t).strip() else None)
        redraw_pills = lambda: (state_pills(), open_pills())
        fit_wrap(ttk.Label(parent, text="Bấm ô 'Chạy' để tick / bỏ tick (bỏ tick = thôi chạy, kết quả cũ vẫn giữ). "
                                        "Bấm 'Mở ›' (hoặc bấm đúp) để mở màn riêng của tài khoản (Đăng ngay / Quét ngay, "
                                        "kết quả" + (", giờ đăng riêng" if is_post else "") + ")."
                                        + (" Tài khoản thứ 2, 3… tự lùi theo giãn cách để không đăng cùng lúc."
                                           if is_post else " Thời gian quét đặt ở tab 🔎 Theo dõi, mọi tài khoản "
                                                           "dùng chung.")
                                        + (" Bấm ô 'Đăng bằng' để chọn Cá nhân hay 1 Page của nick đó (Page lấy bằng "
                                           "nút '🔄 Đọc danh sách Page' ở trang tài khoản)." if has_identity else ""),
                           style="Hint.TLabel", justify="left"), parent).pack_configure(pady=(8, 0))

        def visible():
            g = flt.get()
            return [a for a in self.data["accounts"] if g == "Tất cả" or a.get("group") == g]

        def changed():
            self.mark_dirty()
            self.store.materialize(self.data)
            self.refresh_tree(f"scenario:{s['id']}")
            render()

        def toggle(aid):
            if aid in s["accounts"]:
                s["accounts"].remove(aid)
            else:
                s["accounts"].append(aid)
            changed()

        def tick_all(value):
            for a in visible():
                if value and a["id"] not in s["accounts"]:
                    s["accounts"].append(a["id"])
                elif not value and a["id"] in s["accounts"]:
                    s["accounts"].remove(a["id"])
            changed()

        def render():
            tree.delete(*tree.get_children())
            accounts = visible()
            if not accounts:
                tree.insert("", "end", values=("", "Chưa có tài khoản – thêm ở trang 👤 Tài khoản") + ("",) * (len(cols) - 2),
                            tags=["off"])
            for a in accounts:
                ticked = a["id"] in s["accounts"]
                usable = self.account_usable(a)
                out = a["id"] not in licensed
                state = ("ngoài bản quyền" if out else
                         account_status.LABELS[self.account_state(a)["status"]] if not usable else "hoạt động")
                when, joined = k.member_columns(self, s, a) if ticked and hasattr(k, "member_columns") else ("—", "—")
                action = "" if out else ("🔑 Đăng nhập" if not usable else ("Mở ›" if ticked else ""))
                values = ["☑" if ticked else "☐", self.account_label(a, 40), state, when, joined, action]
                if has_identity:
                    values.insert(2, as_text(a) if ticked else "—")
                tree.insert("", "end", iid=a["id"], values=values,
                            tags=["off"] if out else (["bad"] if not usable else (["on"] if ticked else [])))
            redraw_pills()

        def as_text(a):
            ident = str((s.get("post_as") or {}).get(a["id"]) or "self")
            if ident == "self":
                return "👤 Cá nhân"
            hit = next((x for x in self.store.account_identities(a) if x["id"] == ident), None)
            if hit is None or hit.get("missing"):
                return f"⚠ Page không còn ({hit['name'] if hit else ident})"
            return f"📄 {hit['name']}"

        def pick_identity(a, event):
            """Menu chon danh tinh 'Dang bang' cho tai khoan a trong kich ban nay."""
            menu = tk.Menu(tree, tearoff=0)
            cur = str((s.get("post_as") or {}).get(a["id"]) or "self")

            def choose(ident):
                post_as = s.setdefault("post_as", {})
                if ident == "self":
                    post_as.pop(a["id"], None)
                else:
                    post_as[a["id"]] = ident
                changed()
            for x in self.store.account_identities(a):
                label = ("👤 Cá nhân: " if x["id"] == "self" else "📄 ") + (x.get("name") or x["id"]) + \
                        ("   (không còn thấy)" if x.get("missing") else "")
                menu.add_command(label=("✓  " if x["id"] == cur else "     ") + label,
                                 command=lambda i=x["id"]: choose(i))
            menu.add_separator()
            menu.add_command(label="🔄 Đọc danh sách Page… (trang tài khoản)",
                             command=lambda: self.select(f"account:{a['id']}"))
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        def on_click(e):
            iid = tree.identify_row(e.y)
            if not iid or iid not in {a["id"] for a in self.data["accounts"]}:
                return
            col = tree.identify_column(e.x)
            if col == "#1":
                toggle(iid)
            elif col_as and col == col_as and iid in s["accounts"]:
                pick_identity(self.store.find_account(self.data, iid), e)
            elif col == col_open:   # cot hanh dong: Mo › (da tick) / Dang nhap (chua dang nhap)
                action = tree.item(iid, "values")[len(cols) - 1]
                if action.startswith("🔑"):
                    self.select(f"account:{iid}")
                elif action:
                    self.select(f"member:{s['id']}|{iid}")

        def on_double(e):
            iid = tree.identify_row(e.y)
            if iid and iid in s["accounts"]:
                self.select(f"member:{s['id']}|{iid}")

        def gap_changed(*_a):
            raw = gap_var.get().strip()
            if raw.isdigit() and int(raw) != s.get("gap_minutes") and 0 <= int(raw) <= 240:
                s["gap_minutes"] = int(raw)
                changed()

        tree.bind("<ButtonRelease-1>", on_click)
        tree.bind("<Double-1>", on_double)
        gap_var.trace_add("write", gap_changed)
        flt.trace_add("write", lambda *_a: render())
        render()

    def show_member(self, s, account, item):
        """Kich ban x tai khoan: ket qua, Dang ngay... cua rieng tai khoan (noi dung sua o kich ban)."""
        self.clear_right()
        self.current = ("member", f"{s['id']}|{account['id']}")
        self.set_crumb()
        k = self.KINDS[s["kind"]]
        top = ttk.Frame(self.right)
        top.pack(fill="x")
        ttk.Label(top, text=f"👤  {self.account_label(account)}", style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="✎ Sửa kịch bản", command=lambda: self.select(f"scenario:{s['id']}")).pack(side="right")
        as_name = self.identity_label(account, item)
        ttk.Label(self.right, text=f"chạy {k.ITEM_ICON} {s['name']}" + (f"   ·   đăng bằng Page '{as_name}'" if as_name
                                                                       else ""), style="Sub.TLabel").pack(anchor="w")
        if item is None:
            ttk.Label(self.right, text="Chưa có dữ liệu – bấm Lưu.", style="Hint.TLabel").pack(anchor="w")
            return
        if self.data.get("paused"):
            self.banner("⏸  Tool đang TẠM DỪNG TOÀN BỘ - không có lịch nào chạy.", "▶ Chạy lại", self.toggle_pause)
        elif not self.account_usable(account):
            st = account_status.LABELS[self.account_state(account)["status"]]
            self.banner(f"⛔  Tài khoản '{account['name']}': {st} → kịch bản này đang TẠM DỪNG ở tài khoản này.",
                        "Đăng nhập lại", lambda: self.goto_account_login(account))
        # ---- 4 o so (giong ban thiet ke 1)
        kpis = k.member_kpis(self, s, account, item) if hasattr(k, "member_kpis") else []
        if kpis:
            row = ttk.Frame(self.right)
            row.pack(fill="x", pady=(8, 6))
            for i, (value, label, color) in enumerate(kpis):
                row.columnconfigure(i, weight=1, uniform="m")
                stat_card(row, i, value, label, color, ("Segoe UI Semibold", 15 if len(str(value)) < 9 else 11),
                          padx=(0 if i == 0 else 8, 0))
        else:
            ttk.Label(self.right, text=k.member_summary(self, s, account, item), style="Hint.TLabel",
                      wraplength=680, justify="left").pack(anchor="w", pady=(4, 6))
        if s["kind"] == "post" and hasattr(self.store, "custom_member_times"):
            self.member_times_row(self.right, s, account)
        tabs = LineTabs(self.right)
        tabs.pack(fill="both", expand=True)
        def builder(tab_name, sections):
            def build(inner):
                if sections is None:
                    k.build_member_tab(self, inner, tab_name, account, item)
                    return
                for title, _specs in sections:
                    k.section_extra(title, section(inner, title), item)
            return build
        self.lazy_tabs(tabs, [(name, builder(name, sec)) for name, sec in k.member_tabs()], f"member:{s['kind']}")

    def member_times_row(self, parent, s, account):
        """Gio dang RIENG cua tai khoan trong kich ban. Gio o kich ban (+ gian cach) chi la mac dinh."""
        import upstt_store
        default = self.store.default_member_times(self.data, s, account["id"])
        own = self.store.custom_member_times(s, account["id"])
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 8))
        ttk.Label(row, text="🕒 Giờ đăng của tài khoản này:").pack(side="left")
        var = tk.StringVar(value=", ".join(own or default))
        entry = ttk.Entry(row, textvariable=var, width=28)
        entry.pack(side="left", padx=6)
        reset = ttk.Button(row, text="↺ Dùng giờ chung")
        reset.pack(side="left")
        hint = ttk.Label(parent, text="", style="Hint.TLabel", wraplength=680)
        hint.pack(anchor="w", pady=(0, 6))

        def show_hint():
            mine = self.store.custom_member_times(s, account["id"])
            hint.configure(text=(f"Đang dùng GIỜ RIÊNG. Giờ chung của kịch bản cho tài khoản này: {', '.join(default) or 'chưa có'}."
                                 if mine else "Đang dùng giờ chung của kịch bản (đã cộng giãn cách). Sửa ô trên "
                                              "(vd: 7:00, 20:30) rồi Enter để đặt giờ riêng; bấm Lưu để áp dụng."))
            reset.state(["!disabled"] if mine else ["disabled"])

        def apply(times):
            current = self.store.custom_member_times(s, account["id"]) or default
            if times == current:
                return
            mt = s.setdefault("member_times", {})
            if not times or times == default:
                mt.pop(account["id"], None)
            else:
                mt[account["id"]] = times
            self.mark_dirty()
            self.store.materialize(self.data)
            self.refresh_tree(f"member:{s['id']}|{account['id']}")
            self.flash("Đã đổi giờ đăng của tài khoản – bấm Lưu để áp dụng lịch.")
            show_hint()

        def commit(_e=None):
            times, bad = upstt_store.normalize_times(re.split(r"[,;\s]+", var.get()))
            if bad:
                # Tra o ve gio dang dung truoc khi hien canh bao (roi o -> FocusOut khong bao lan 2).
                var.set(", ".join(self.store.custom_member_times(s, account["id"]) or default))
                messagebox.showwarning("Giờ đăng", "Giờ không đúng dạng: " + ", ".join(bad) +
                                       "\n\nViết dạng 7:00 hoặc 19:30, cách nhau dấu phẩy.")
                return
            var.set(", ".join(times or default))
            apply(times)

        def use_default():
            var.set(", ".join(default))
            apply([])

        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)
        reset.configure(command=use_default)
        show_hint()

    def show_tab_intro(self):
        """Man huong dan khi tab ben trai chua co gi."""
        self.clear_right()
        key = list(self.trees)[self.left_tabs.index(self.left_tabs.select())]
        text = {
            "account": ("👤  Tài khoản", "Chưa có tài khoản nào. Thêm tài khoản rồi đăng nhập Facebook.",
                        "＋ Thêm tài khoản", self.add_account),
            "scenario": ("📋  Kịch bản", "Chưa có kịch bản nào. Thêm kịch bản đăng bài, rồi tick các tài khoản chạy.",
                         "＋ Thêm kịch bản đăng bài", lambda: self.add_scenario("post")),
        }[key]
        ttk.Label(self.right, text=text[0], style="Title.TLabel").pack(anchor="w", pady=(10, 6))
        ttk.Label(self.right, text=text[1], style="Sub.TLabel", wraplength=640, justify="left").pack(anchor="w")
        ttk.Button(self.right, text=text[2], style="Accent.TButton" if sv_ttk else "TButton",
                   command=text[3]).pack(anchor="w", pady=(14, 0))

    def show_folder(self, kind, name):
        self.clear_right()
        if kind == "sgroup":
            k = self.KINDS[name]
            items = [s for s in self.data["scenarios"] if s["kind"] == name]
            ttk.Label(self.right, text=f"{k.ITEM_ICON}  {getattr(k, 'FOLDER_LABEL', k.ITEM_NOUN)}",
                      style="Title.TLabel").pack(anchor="w")
            ttk.Label(self.right, text=f"{len(items)} kịch bản · {sum(1 for s in items if s['enabled'])} đang bật. "
                                       "Kịch bản có lỗi tự xếp lên đầu. Bấm ▸ để gập thư mục.",
                      style="Sub.TLabel", wraplength=680).pack(anchor="w", pady=(0, 10))
            ttk.Button(self.right, text=f"＋ {getattr(k, 'ADD_LABEL', k.ITEM_NOUN)}",
                       command=lambda: self.add_scenario(name)).pack(anchor="w", pady=(0, 10))
            for s in items:
                row = ttk.Frame(self.right)
                row.pack(fill="x", pady=2)
                ttk.Label(row, text=f"{k.ITEM_ICON if s['enabled'] else '⏸'}  {k.tree_scenario_text(s)}   ·   "
                                    f"{len(s['accounts'])} tài khoản").pack(side="left")
                ttk.Button(row, text="Mở", width=5, command=lambda s=s: self.select(f"scenario:{s['id']}")).pack(side="right")
            return
        accounts = [a for a in self.data["accounts"] if a.get("group") == name]
        head = ttk.Frame(self.right)
        head.pack(fill="x")
        ttk.Label(head, text=f"📁  {name}", style="Title.TLabel").pack(side="left")
        ttk.Button(head, text="🗑 Xóa nhóm", command=self.delete).pack(side="right")
        ttk.Button(head, text="✎ Đổi tên", command=self.rename).pack(side="right", padx=6)
        ttk.Label(self.right, text=f"Nhóm tài khoản · {len(accounts)} tài khoản. Trong kịch bản → '👥 Tài khoản "
                                   "chạy' chọn nhóm này để tick nhanh cả nhóm.", style="Sub.TLabel",
                  wraplength=680).pack(anchor="w", pady=(0, 10))
        for a in accounts:
            ttk.Label(self.right, text=f"👤  {self.account_label(a)}").pack(anchor="w")

    def account_extra(self, parent, account):
        pass

    # ------------------------------------------------------------ tin nhan moi (tab Tai khoan)
    _inbox_checks = {}   # tai khoan -> tien trinh 'Kiem tra tin nhan ngay'

    def inbox_section(self, parent, account):
        """Khung 'Tin nhan moi': cuoc tro chuyen co tin chua doc (hop thu / tin nhan cho / spam).
        Bam dup -> mo Chrome cua tai khoan dung cuoc tro chuyen de TU tra loi."""
        import fb_login
        from datetime import datetime
        acc_dir = self.account_dir(account)
        settings = self.store.inbox_settings(self.data)
        # .box "Tin nhắn chưa xem · kiểm tra lúc … · tự kiểm tra mỗi …" + nut Kiem tra ngay tren thanh tieu de
        box = Box(parent, text="Tin nhắn chưa xem")
        box.pack(fill="x")
        info = box.add_note("")
        check_btn = box.add_button("🔄 Kiểm tra ngay", lambda: None)
        cols = ("name", "folder", "snippet", "time", "reply")
        tree = ttk.Treeview(box, columns=cols, show="headings", height=3, selectmode="extended")
        for col, title, width in (("name", "Người nhắn", 150), ("folder", "Mục", 100),
                                  ("snippet", "Tin nhắn", 300), ("time", "Lúc", 90), ("reply", "", 100)):
            tree.heading(col, text=title, anchor="w")
            tree.column(col, width=width, anchor="center" if col == "reply" else "w", stretch=col == "snippet")
        tree.pack(fill="x", pady=(0, 4))
        folder_style = lambda t: ((RED, "#fde8e8") if "spam" in str(t).casefold() else
                                  (MUTED, "#eef0f3") if str(t).strip() else None)
        redraw = [pill_cells(tree, ["folder"], folder_style),
                  pill_cells(tree, ["reply"], lambda t: ("#ffffff", ACCENT) if str(t).strip() else None)]
        bottom = ttk.Frame(parent)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Label(bottom, text="Bấm ↗ Trả lời (hoặc bấm đúp dòng) → mở Chrome của tài khoản đúng cuộc trò chuyện.",
                  style="Hint.TLabel").pack(side="left")
        ttk.Button(bottom, text="⚙ Cài đặt", command=self.inbox_settings_dialog, style="Small.TButton").pack(
            side="right")
        seen_btn = ttk.Button(bottom, text="✔ Đánh dấu đã xem", style="Small.TButton")
        seen_btn.pack(side="right", padx=6)
        rows = {}

        def fill():
            if not tree.winfo_exists():
                return
            tree.delete(*tree.get_children())
            rows.clear()
            for t in fb_login.unseen_inbox(acc_dir):
                iid = tree.insert("", "end", values=(
                    t.get("name", ""), fb_login.INBOX_FOLDER_LABEL.get(t.get("folder"), t.get("folder", "")),
                    t.get("snippet", ""), f"{datetime.fromtimestamp(t.get('time', 0)):%H:%M %d/%m}", "↗ Trả lời"))
                rows[iid] = t
            if not rows:
                tree.insert("", "end", values=("", "", "Không có tin nhắn mới.", "", ""))
            tree.configure(height=max(1, min(10, len(rows))))
            checked = fb_login.load_inbox(acc_dir)["checked"]
            auto = (f"tự kiểm tra mỗi {settings['minutes']} phút" if settings["enabled"]
                    else "tự kiểm tra đang TẮT (bật ở ⚙ Cài đặt)")
            info.configure(text="·  " + (f"kiểm tra lúc {datetime.fromtimestamp(checked):%H:%M %d/%m}" if checked
                                          else "chưa kiểm tra lần nào") + f"  ·  {auto}")
            for r in redraw:
                r()

        def picked():
            return [rows[i] for i in tree.selection() if i in rows]

        def open_selected(_e=None):
            items = picked()
            if not items:
                messagebox.showinfo("Tin nhắn", "Chọn 1 dòng trong bảng trước.")
                return
            self.open_in_account(account, items[0]["url"])
            fb_login.mark_inbox_seen(acc_dir, [items[0]["id"]])
            fill()
            self.refresh_tree_keep()

        def mark_seen():
            items = picked()
            if items:
                fb_login.mark_inbox_seen(acc_dir, [t["id"] for t in items])
                fill()
                self.refresh_tree_keep()

        def poll():
            proc = self._inbox_checks.get(account["id"])
            if not check_btn.winfo_exists():
                return
            if proc is not None and proc.poll() is None:
                check_btn.state(["disabled"])
                check_btn.configure(text="⏳ Đang đọc tin nhắn…")
                self.root.after(1000, poll)
                return
            self._inbox_checks.pop(account["id"], None)
            check_btn.state(["!disabled"])
            check_btn.configure(text="🔄 Kiểm tra ngay")
            if proc is not None:
                if proc.returncode == fb_login.EXIT_PROFILE_BUSY:
                    self.flash(f"'{account['name']}' đang bận (tool khác dùng) → thử lại sau vài phút.")
                elif proc.returncode:
                    self.flash("Kiểm tra tin nhắn bị lỗi – xem 📄 Xem nhật ký.")
                fill()
                self.refresh_tree_keep()

        def check_now():
            if account["id"] in self._inbox_checks:
                return
            self._inbox_checks[account["id"]] = subprocess.Popen(
                [self.python, str(self.SCRIPT), "--check-inbox", "--account", account["id"]], cwd=self.base_dir,
                creationflags=NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            poll()

        def on_click(e):   # bam o "↗ Tra loi" cua dong
            iid = tree.identify_row(e.y)
            if iid in rows and tree.identify_column(e.x) == "#5":
                tree.selection_set(iid)
                open_selected()

        check_btn.configure(command=check_now)
        seen_btn.configure(command=mark_seen)
        tree.bind("<Double-1>", open_selected)
        tree.bind("<ButtonRelease-1>", on_click, add="+")
        fill()
        if account["id"] in self._inbox_checks:
            poll()

    def inbox_unseen_count(self, account):
        import fb_login
        return len(fb_login.unseen_inbox(self.account_dir(account)))

    def inbox_settings_dialog(self):
        """Nut '⚙ Cai dat theo doi tin nhan' (o tai khoan) -> trang Cai dat."""
        self.show_page("settings")

    def inbox_settings_form(self, frame):
        """Cai dat chung (moi tai khoan): tu kiem tra moi N phut + Telegram RIENG cho tin nhan (trang Cai dat)."""
        s = self.store.inbox_settings(self.data)
        win = frame.winfo_toplevel()
        enabled = tk.BooleanVar(value=s["enabled"])
        minutes = tk.StringVar(value=str(s["minutes"]))
        days = tk.StringVar(value=str(s["days"]))
        token = tk.StringVar(value=s["telegram_token"])
        chat = tk.StringVar(value=s["telegram_chat_id"])
        _default, low, high = self.store.INBOX_MINUTES
        d_default, d_low, d_high = self.store.INBOX_DAYS
        # (ban thiet ke 1) cong tac bat/tat tren thanh tieu de · 1 dong "Kiem tra moi … phut · lay tin chua doc trong … ngay"
        if isinstance(frame, Box):
            frame.add_switch(enabled)
        else:
            ttk.Checkbutton(frame, text="Tự kiểm tra mọi tài khoản", variable=enabled).pack(anchor="w")
        row = ttk.Frame(frame)
        row.pack(anchor="w")
        ttk.Label(row, text="Kiểm tra mỗi").pack(side="left")
        no_wheel(NumBox(row, from_=low, to=high, increment=5, width=4, textvariable=minutes)).pack(
            side="left", padx=6)
        ttk.Label(row, text="phút  ·  lấy tin chưa đọc trong").pack(side="left")
        no_wheel(NumBox(row, from_=d_low, to=d_high, width=4, textvariable=days)).pack(side="left", padx=6)
        ttk.Label(row, text="ngày").pack(side="left")
        grid = ttk.Frame(frame)
        grid.pack(fill="x", pady=(8, 0))
        grid.columnconfigure(1, weight=1)
        ttk.Label(grid, text="Telegram Token").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        token_entry = ttk.Entry(grid, textvariable=token, show="•")   # an ma bot (ban thiet ke: ••••)
        token_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=3)
        token_entry.bind("<FocusIn>", lambda _e: token_entry.configure(show=""))
        token_entry.bind("<FocusOut>", lambda _e: token_entry.configure(show="•"))
        ttk.Label(grid, text="Chat ID").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(grid, textvariable=chat).grid(row=1, column=1, sticky="ew", pady=3)
        test_btn = ttk.Button(grid, text="✈ Gửi thử")
        test_btn.grid(row=1, column=2, sticky="e", padx=(6, 0), pady=3)
        fit_wrap(ttk.Label(frame, text="Kênh Telegram riêng cho tin nhắn (khác kênh của kịch bản theo dõi). Token lấy từ "
                                       "@BotFather, Chat ID từ @userinfobot. Tool chỉ đọc danh sách tin nhắn – khách "
                                       f"không thấy 'đã xem'. Tối thiểu {low} phút, mặc định {d_default} ngày.",
                           style="Hint.TLabel", justify="left"), frame).pack_configure(pady=(6, 0))

        def test():
            if not token.get().strip() or not chat.get().strip():
                messagebox.showwarning("Telegram", "Điền Token và Chat ID trước.", parent=win)
                return
            ok, detail = send_telegram_test(token.get().strip(), chat.get().strip(),
                                            "✅ Tool Facebook: kênh báo TIN NHẮN MỚI hoạt động.")
            if ok:
                messagebox.showinfo("Telegram", "Đã gửi tin thử. Mở Telegram để kiểm tra.", parent=win)
            else:
                messagebox.showerror("Telegram", "Gửi thử thất bại. Kiểm tra Token, Chat ID và đã bấm Start với "
                                                 "bot chưa.\n\n" + detail, parent=win)

        def update(*_a):
            """Moi thay doi ghi thang vao cau hinh (cham '● chua luu'), bam 💾 Luu o goc tren de luu + cap nhat lich."""
            try:
                m = min(high, max(low, int(minutes.get().strip())))
            except ValueError:
                m = s["minutes"]
            try:
                n_days = min(d_high, max(d_low, int(days.get().strip())))
            except ValueError:
                n_days = s["days"]
            new = {"enabled": enabled.get(), "minutes": m, "days": n_days,
                   "telegram_token": token.get().strip(), "telegram_chat_id": chat.get().strip()}
            if new != self.store.inbox_settings(self.data):
                self.data["inbox"] = new
                self.mark_dirty()

        def switched(*_a):
            if enabled.get() and not (token.get().strip() and chat.get().strip()) and not messagebox.askyesno(
                    "Theo dõi tin nhắn", "Chưa có Telegram → tool chỉ ghi tin mới vào tab Tài khoản, không báo "
                                         "điện thoại. Vẫn bật?", parent=win):
                enabled.set(False)
                return
            update()

        test_btn.configure(command=test)
        for var in (minutes, days, token, chat):
            var.trace_add("write", update)
        enabled.trace_add("write", switched)

    # ------------------------------------------------------------ dang nhap / trang thai
    def account_dir(self, account):
        return self.store.ACCOUNTS_DIR / account["id"]

    def item_dir(self, account, item):
        """Task 003: thu muc du lieu cua muc theo danh tinh 'Dang bang' (Ca nhan = account_dir nhu cu).
        Loi (id la) -> thu muc khong co that (bang trong, KHONG lan so lieu Ca nhan)."""
        get = getattr(self.store, "campaign_data_dir", None)
        if not get or not item or (item.get("post_as") or "self") == "self":
            return self.account_dir(account)
        try:
            return get(account, item)
        except Exception:
            return self.account_dir(account) / "danh_tinh" / "_"

    def identity_dirs(self, account):
        """Moi thu muc danh tinh cua tai khoan (so lieu ca tai khoan = cong lai)."""
        ids = getattr(self.store, "account_identity_ids", None)
        out = [self.account_dir(account)]
        for ident in (ids(account) if ids else []):
            if ident != "self":
                try:
                    out.append(self.store.identity_data_dir(account["id"], ident))
                except Exception:
                    pass
        return out

    def identity_label(self, account, item):
        """Ten Page cua muc ('' = Ca nhan)."""
        if not item or (item.get("post_as") or "self") == "self":
            return ""
        return item.get("post_as_name") or item.get("post_as", "")

    def page_open_hint(self, account, item):
        """Cau PM 8: Chrome that mo o Ca nhan -> nhac tu chuyen sang Page."""
        name = self.identity_label(account, item)
        if name:
            messagebox.showinfo("Mở bằng Page", f"Chrome của '{account['name']}' mở ở CÁ NHÂN (tool không tự chuyển "
                                                f"trong Chrome bạn tự dùng).\n\nMuốn xem bằng Page '{name}': bấm ảnh đại "
                                                f"diện góc phải trên → 'Chuyển sang {name}'.\nXem xong nhớ chuyển về Cá "
                                                "nhân rồi đóng Chrome (tool cũng tự chuyển lại ở lượt sau).")

    def account_state(self, account):
        return account_status.read(self.account_dir(account))

    def fb_name(self, account):
        """Ten Facebook that (lay luc Dang nhap / Kiem tra). Chi hien khi dang dang nhap."""
        if self.account_state(account)["status"] not in (account_status.OK, account_status.UNKNOWN):
            return ""
        return account_status.read_profile(self.account_dir(account)).get("name", "")

    def account_usable(self, account):
        return account_status.usable(self.account_dir(account))

    def banner(self, text, button_text, command):
        bar = ttk.Frame(self.right, padding=(10, 6))
        bar.pack(fill="x", pady=(4, 6))
        ttk.Label(bar, text=text, style="Warn.TLabel", wraplength=560).pack(side="left")
        ttk.Button(bar, text=button_text, command=command,
                   style="Accent.TButton" if sv_ttk else "TButton").pack(side="right")

    def goto_account_login(self, account):
        self.select(f"account:{account['id']}")
        self.root.update_idletasks()
        self.account_action(account, "login")

    def set_login_status(self, text, style="Hint.TLabel"):
        if self.login_status is not None and self.login_status.winfo_exists():
            self.login_status.configure(text=text, style=style)
            if text and not self.login_status.winfo_manager():   # o trong thi khong chiem cho (ban thiet ke 1)
                self.login_status.pack(anchor="w")

    def show_login_waiting(self):
        if self.login_done_button is not None and self.login_done_button.winfo_exists():
            if self.login_status is not None and self.login_status.winfo_manager():
                self.login_done_button.pack(anchor="w", pady=(0, 8), before=self.login_status)
            else:
                self.login_done_button.pack(anchor="w", pady=(0, 8))
        self.set_login_status("Cửa sổ Chrome đăng nhập đang mở. Đăng nhập Facebook xong (thấy trang chủ) "
                              "thì bấm nút trên, hoặc tự đóng cửa sổ Chrome.", "Warn.TLabel")

    def finish_login(self, account):
        """Nguoi dung bao da dang nhap xong -> dong Chrome dung cach, tool tu kiem tra roi cap nhat."""
        profile = self.account_dir(account) / "browser_profile"
        self.set_login_status("Đang đóng Chrome và kiểm tra đăng nhập...")
        self.root.update_idletasks()
        close_login_window(profile)
        if account["id"] not in self.pending_login:
            # Cua so mo tu lan truoc (giao dien cu da dong) -> theo doi trang thai den khi cap nhat.
            self.watch_status(account, account_status.read(self.account_dir(account)).get("time"), time.time() + 90)

    def watch_status(self, account, old_time, deadline):
        state = account_status.read(self.account_dir(account))
        if state.get("time") != old_time or time.time() > deadline:
            self.after_account_change(account)
            return
        self.root.after(1000, lambda: self.watch_status(account, old_time, deadline))

    def account_action(self, account, action):
        """login | check | logout | switch (= dang xuat roi dang nhap tai khoan khac)."""
        if action in ("logout", "switch"):
            ask = ("Đăng xuất" if action == "logout" else "Đổi tài khoản") + f" '{account['name']}'?\n\n" \
                  "Tool sẽ đăng xuất Facebook và XÓA dữ liệu đăng nhập đã lưu của tài khoản này.\n" \
                  f"Các {self.ITEM_NOUN} của tài khoản sẽ tạm dừng cho đến khi đăng nhập lại."
            if not messagebox.askyesno("Xác nhận", ask):
                return
        if account["id"] in self.busy_accounts:
            # Lenh truoc chua xong -> khong chay chong (truoc day bam nhieu lan lam cac lenh dung nhau).
            msg = "⏳  Đang xử lý lệnh trước của tài khoản này, đợi vài giây..."
            self.set_login_status(msg, "Warn.TLabel")
            self.flash(msg)
            return
        if self.has_changes() and not self.save(quiet=True):
            return
        steps = {"login": ["login"], "check": ["check"], "logout": ["logout"], "switch": ["logout", "login"]}[action]
        self.run_steps(account, steps)

    def run_steps(self, account, steps, force=False):
        if not steps:
            self.busy_accounts.discard(account["id"])
            self.after_account_change(account)
            return
        step, rest = steps[0], steps[1:]
        if step == "check" and not (self.account_dir(account) / "browser_profile").exists():
            account_status.write(self.account_dir(account), account_status.LOGGED_OUT)
            self.after_account_change(account)
            return
        text = {"login": "Đang mở Chrome... Đăng nhập xong thì ĐÓNG Chrome.",
                "check": "Đang kiểm tra đăng nhập (khoảng 15 giây)...",
                "logout": "Đang đăng xuất và xóa dữ liệu đăng nhập..."}[step]
        self.set_login_status(text)
        self.flash(text)
        self.busy_accounts.add(account["id"])
        cmd = [self.python, str(self.SCRIPT), f"--{step}", "--account", account["id"]]
        if force:
            cmd.append("--force")
        if step == "login":
            proc = subprocess.Popen(cmd, cwd=self.base_dir, creationflags=NEW_CONSOLE)
            self.pending_login.add(account["id"])
            self.root.after(3000, lambda: proc.poll() is None and self.current == ("account", account["id"])
                            and self.show_login_waiting())
        else:
            proc = subprocess.Popen(cmd, cwd=self.base_dir, creationflags=NO_WINDOW,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.wait_step(proc, account, step, rest, force)

    def wait_step(self, proc, account, step, rest, force=False):
        code = proc.poll()
        if code is None:
            self.root.after(250, lambda: self.wait_step(proc, account, step, rest, force))
            return
        self.busy_accounts.discard(account["id"])   # lenh nay da xong (buoc tiep theo se dat lai neu co)
        if step == "login":
            self.pending_login.discard(account["id"])
        if code == 4 and step == "login" and login_window_open(self.account_dir(account) / "browser_profile"):
            # Khong phai lich chay: cua so dang nhap lan truoc van mo (thuong bi che sau cua so khac).
            if messagebox.askyesno(
                    "Cửa sổ đăng nhập vẫn đang mở",
                    f"Cửa sổ Chrome đăng nhập của '{account['name']}' vẫn đang mở "
                    "(có thể bị che sau cửa sổ khác, xem trên thanh taskbar).\n\n"
                    "Nếu bạn ĐÃ đăng nhập xong: bấm Yes, tool sẽ đóng Chrome và lưu đăng nhập.\n"
                    "Nếu CHƯA: bấm No, mở lại cửa sổ Chrome đó để đăng nhập tiếp."):
                self.finish_login(account)
            else:
                self.on_select(force=True)
            return
        if code == 4:
            if step == "check":
                # Da co ten tai khoan -> chi can hien trang thai tu luot dang chay, khong dung luot do.
                # Chua co ten -> hoi dung luot dang chay de kiem tra + lay ten ngay.
                if not force and not self.fb_name(account) and messagebox.askyesno(
                        "Tài khoản đang chạy",
                        f"Tài khoản '{account['name']}' đang chạy theo lịch nên chưa kiểm tra được ngay.\n\n"
                        "Dừng lượt đang chạy để kiểm tra đăng nhập và lấy tên tài khoản Facebook ngay?\n"
                        "(Lượt sau vẫn chạy đúng lịch.)"):
                    self.run_steps(account, [step] + rest, force=True)
                    return
                self.after_account_change(account, note="đang chạy theo lịch, trạng thái lấy từ lượt chạy này")
                return
            if not force and messagebox.askyesno(
                    "Tài khoản đang chạy",
                    f"Tài khoản '{account['name']}' đang chạy theo lịch.\n\n"
                    "Dừng lượt đang chạy để tiếp tục? (Lượt sau vẫn chạy đúng lịch.)"):
                self.run_steps(account, [step] + rest, force=True)
                return
            self.after_account_change(account, note="chưa thực hiện vì tài khoản đang chạy theo lịch")
            return
        if code != 0 and step in ("login", "logout"):
            self.after_account_change(account)
            log = self.account_dir(account) / "dang_nhap.log"
            if step == "login" and code == 3:
                messagebox.showwarning(
                    "Chưa đăng nhập được",
                    f"Tool chưa thấy tài khoản '{account['name']}' đăng nhập Facebook.\n\n"
                    "Bấm 'Đăng nhập' lại, đăng nhập trong cửa sổ Chrome cho đến khi THẤY TRANG CHỦ "
                    "Facebook (nếu Facebook hỏi xác nhận trên điện thoại thì chọn 'Đúng, là tôi'), "
                    "rồi mới đóng Chrome.\n\nKhông đóng cửa sổ màu đen trong lúc đăng nhập.")
            else:
                what = "Đăng nhập" if step == "login" else "Đăng xuất"
                messagebox.showwarning(
                    f"{what} chưa xong",
                    f"{what} bị dừng giữa chừng (mã {code}).\n"
                    "Có thể cửa sổ màu đen đã bị đóng hoặc có lỗi.\n\n"
                    f"Thử lại. Nếu vẫn lỗi, gửi file này cho người hỗ trợ:\n{log}")
            return
        self.run_steps(account, rest, force)

    def after_account_change(self, account, note=""):
        """Trang thai doi -> ve lai cay / trang, bat hoac tat lich cua tai khoan."""
        kind, ident = self.selected()
        self.refresh_tree(f"{kind}:{ident}" if kind else None)
        if self.current and self.current[0] == "account" and self.current[1] == account["id"]:
            self.on_select(force=True)
        state = self.account_state(account)
        icon, style = STATUS_UI[state["status"]]
        msg = f"{icon}  {account['name']}: {account_status.LABELS[state['status']]}"
        if note:
            msg += f"  ({note})"
        self.set_login_status(msg, style)
        self.flash(msg)
        self.sync_schedule_async(lambda sched: sched and self.set_login_status(msg + "  ·  " + sched, style))

    def sync_schedule_async(self, done=None):
        """Cap nhat lich chay (setup.ps1, vai giay) o luong nen -> giao dien khong bi do.

        Dang cap nhat ma trang thai lai doi -> xong luot nay se cap nhat tiep theo trang thai moi nhat.
        """
        new = self.schedule_key(self.store.schedule_entries(self.data))
        if new == self.saved_schedule:
            return
        if self._schedule_thread is not None and self._schedule_thread.is_alive():
            self._schedule_again = True
            return
        result = {}
        self._schedule_again = False
        self._schedule_thread = threading.Thread(
            target=lambda: result.update(zip(("ok", "detail"), self.update_schedule())), daemon=True)
        self._schedule_thread.start()
        self.flash("Đang cập nhật lịch chạy...")

        def finished():
            if self._schedule_thread.is_alive():
                self.root.after(200, finished)
                return
            if result.get("ok"):
                self.saved_schedule = new
                text = "đã cập nhật lịch chạy"
            else:
                text = "CHƯA cập nhật được lịch"
                messagebox.showwarning("Lịch chạy", "Chưa cập nhật được lịch chạy:\n" + result.get("detail", "") +
                                       "\n\nĐóng giao diện rồi mở lại bằng MO_TOOL.bat (bấm Yes khi Windows hỏi quyền).")
            self.flash(text)
            if done:
                done(text)
            if self._schedule_again:
                self.sync_schedule_async(done)

        self.root.after(200, finished)

    def wait_schedule(self):
        """Cho luot cap nhat lich nen (neu co) xong truoc khi cap nhat lich lan nua."""
        if self._schedule_thread is not None:
            self._schedule_thread.join()

    # ------------------------------------------------------------ dau trang
    def refresh_header(self):
        paused = bool(self.data.get("paused"))
        self.pause_button.configure(text="▶ Chạy lại toàn bộ" if paused else "⏸ Tạm dừng toàn bộ")
        self.run_state.configure(text="⏸ Đang tạm dừng" if paused else "● Đang tự chạy theo lịch",
                                 foreground=AMBER if paused else GREEN, font=FONT_SEMI)
        self.pause_banner.configure(text="⏸  Tool đang TẠM DỪNG TOÀN BỘ: không có lịch nào chạy. "
                                         "Bấm '▶ Chạy lại toàn bộ' để tiếp tục." if paused else "")

    def toggle_pause(self):
        paused = not self.data.get("paused")
        if paused and not messagebox.askyesno("Tạm dừng toàn bộ", "Tạm dừng toàn bộ tool?\n\n"
                                              "Gỡ hết lịch chạy tự động. Không mất cấu hình, không đăng xuất."):
            return
        self.commit_form()
        self.data["paused"] = paused
        if not self.save(quiet=True):
            self.data["paused"] = not paused
            return
        self.refresh_header()
        kind, ident = self.selected()
        self.refresh_tree(f"{kind}:{ident}" if kind else None)
        self.on_select(force=True)

    def toggle_auto_care(self):
        """Bat/tat lich 'Tu cap nhat trang thai' (trang Cai dat): moi N gio cap nhat ket qua moi kich ban dang bat
        (dang bai + theo doi), xong thi bai CUA MINH moi duoc duyet -> binh luan noi dung cham 1 lan / bai."""
        on = self.auto_care_var.get()
        if on and not messagebox.askyesno(
                "Tự cập nhật trạng thái", f"Bật tự cập nhật trạng thái?\n\nCứ {self.store.auto_care_hours(self.data)} "
                "giờ tool vào Facebook cập nhật trạng thái mọi kịch bản đang bật (Đăng bài + Theo dõi). Cập nhật xong, "
                "bài của bạn mới được duyệt thì tự bình luận nội dung 'Chăm bài' của kịch bản – mỗi bài 1 lần, "
                "tối đa 5 bài / tài khoản / lượt. Kịch bản chưa có nội dung chăm bài thì chỉ cập nhật."):
            self.auto_care_var.set(False)
            return
        self.commit_form()
        self.data["auto_care"] = on
        if not self.save(quiet=True):
            self.data["auto_care"] = not on
            self.auto_care_var.set(not on)

    def change_auto_care_hours(self):
        """O 'moi N gio' cua Tu cham bai: sua xong (Enter / bam ra ngoai / mui ten) -> luu + cap nhat lich."""
        _default, low, high = self.store.AUTO_CARE_HOURS
        old = self.store.auto_care_hours(self.data)
        try:
            hours = min(high, max(low, int(self.auto_care_hours_var.get().strip())))
        except ValueError:
            hours = old
        self.auto_care_hours_var.set(str(hours))
        if hours == old:
            return
        self.commit_form()
        self.data["auto_care_hours"] = hours
        if not self.save(quiet=True):
            self.data["auto_care_hours"] = old
            self.auto_care_hours_var.set(str(old))

    def show_license(self):
        path = self.base_dir / "BAN_QUYEN.txt"
        text = path.read_text(encoding="utf-8") if path.exists() else COPYRIGHT
        messagebox.showinfo("Bản quyền", text)

    def log_task(self):
        """(id, ten) cua task co nhat ky ung voi muc dang chon, hoac (None, None)."""
        kind, ident = self.selected()
        if not kind or kind not in ("campaign", "member", "account"):
            return None, None
        if kind == "member":
            kind, ident = "campaign", (self.find("member", ident) or {}).get("id")
        if kind == "campaign":
            account, item = self.store.find_campaign(self.data, ident)
            if not item:
                return None, None
            target = account if self.kind(item).LOG_TASK_LEVEL == "account" else item
            return target["id"], target["name"]
        account = self.store.find_account(self.data, ident)
        # Tai khoan co nhat ky rieng khi co loai muc chay theo tai khoan (vd quet nhom theo doi).
        if account and any(k.LOG_TASK_LEVEL == "account" for _key, k in self.all_kinds()):
            return account["id"], account["name"]
        return None, None

    def open_log(self):
        # Nhat ky ngan gon cho nguoi dung, RIENG tung task: logs/<id>/nhat_ky.txt
        # (log.txt chi tiet cung nam o do, de go loi).
        task, name = self.log_task()
        if not task:
            messagebox.showinfo("Nhật ký", "Chọn một tài khoản bên dưới kịch bản (👤) ở bên trái rồi bấm lại để xem "
                                           "nhật ký của nó.\n\n"
                                           "(Nhật ký cũ – trước khi tách riêng – vẫn ở nhat_ky.txt trong thư mục tool.)")
            return
        log = self.base_dir / "logs" / task / "nhat_ky.txt"
        if log.exists():
            os.startfile(str(log))
        else:
            messagebox.showinfo("Nhật ký", f"'{name}' chưa có nhật ký – chưa chạy lượt nào kể từ khi cập nhật.\n"
                                           f"(Nhật ký kỹ thuật chi tiết: logs\\{task}\\log.txt trong thư mục tool.)")

    # ------------------------------------------------------------ tab Tong hop + Chi tiet
    # Lop con dat RESULT_KIND = "posts" (dang bai) / "comments" (theo doi) va them 2 tab
    # ("Tổng hợp", [("Tổng hợp", [])]), ("Chi tiết", [("Chi tiết", [])]) -> section_extra goi results_tab / details_tab.
    RESULT_KIND = None
    _checks = {}   # tai khoan -> tien trinh 'Cap nhat ngay' dang chay

    def _word(self, k):
        return "bài" if k == "posts" else "bình luận"

    def reset_note_pause(self, account, note, item):
        """Nut 'Cho ... lai ngay': tool gop can biet loai muc de bo dung loai tam nghi."""
        if self.KINDS:
            self.store.reset_pause(account, note.get("kind"), note.get("key"), item)
        else:
            self.store.reset_pause(account, note.get("kind"), note.get("key"))

    def item_groups(self, account, item):
        """Nhom cua muc o tai khoan (muc dang bai co the lay nhom nick da tham gia)."""
        if hasattr(self.store, "campaign_groups"):
            return self.store.campaign_groups(account, item)
        return item.get("groups", [])

    DOTS = {-1: "", 0: "  🟢", 1: "  ⚪", 2: "  🟠", 3: "  🔴"}

    def result_level(self, account, item):
        """Muc ket qua xau nhat cua muc: -1 chua co, 0 tot, 1 chua ro, 2 can xem, 3 loi."""
        k = self.kind(item).RESULT_KIND
        if not k:
            return -1
        rows = result_rows(self.account_dir(account), self.item_groups(account, item), k)
        if k == "comments":
            notes, cstats = self.store.pause_notes(account, item), self.comment_stats(account, item)
            levels = [self.group_report(r, notes, cstats, k)[0] for r in rows]
        else:
            levels = [r["status"][0] for r in rows]
        return max(levels, default=-1)

    def result_dot(self, account, item):
        return self.DOTS[self.result_level(account, item)]

    def results_summary(self, parent, account, item):
        """1 dong tom tat duoi o danh sach nhom."""
        k = self.kind(item).RESULT_KIND
        rows = result_rows(self.account_dir(account), self.item_groups(account, item), k)
        total = lambda tab: sum((r["info"].get(tab) or {}).get(k, 0) for r in rows)
        if not any(r["info"] for r in rows) and not any(r["sent7"] for r in rows):
            return
        w = self._word(k)
        fit(ttk.Label(parent, style="Hint.TLabel", justify="left",
                  text=f"📊 Trên Facebook: {total('posted')} {w} đã đăng · {total('pending')} chờ duyệt · "
                       f"{total('declined') + total('removed')} bị từ chối / gỡ.  Tool đã gửi "
                       f"{sum(r['sent7'] for r in rows)} {w} trong 7 ngày.  "
                  )).pack(fill="x", pady=(0, 12))

    # ---- tab Tong hop: moi nhom 1 dong, tra loi 3 cau: bai co len khong / tool dang lam gi / minh can lam gi
    STATUS_TEXT = {"approved": "✅ Đã duyệt", "pending": "⏳ Chờ duyệt", "declined": "❌ Bị từ chối",
                   "removed": "🗑 Bị gỡ", "unchecked": "⚪ Chưa kiểm tra"}

    def is_sent_event(self, e, k):
        if k == "comments":
            return e["label"].startswith(("Đã bình luận", "Đã gửi bình luận"))
        return e["label"] in ("Đã đăng", "Chờ duyệt")

    def current_statuses(self, account, item, events):
        """Trang thai hien tai (theo lan 'Cap nhat' gan nhat) cua cac dong 'da gui' -> {id(dong): (trang thai, gio kiem)}."""
        import fb_login
        k = self.kind(item).RESULT_KIND
        st = fb_login.load_results(self.item_dir(account, item))
        names = {g.get("name"): slug for slug, g in st["groups"].items() if g.get("name")}
        snip = fb_login.text_snippet(item.get("share_text" if k == "posts" else "comment_text", ""))
        groups, out = {}, {}
        for e in events:
            if not self.is_sent_event(e, k):
                # Tool ghi 'chua binh luan duoc' nhung ma bai lai nam trong muc Dang cho -> thuc ra DA GUI, dang cho duyet
                g = st["groups"].get(fb_login.group_slug(e["url"]), {})
                if e["label"].startswith("Chưa bình luận") and fb_login.post_id_of(e["url"]) in g.get("pending_ids", []):
                    out[id(e)] = ("pending", g.get("items_checked", 0))
                continue
            slug = fb_login.group_slug(e["url"]) or names.get(e["group"], "")
            if slug in st["groups"]:
                groups.setdefault(slug, []).append(e)
        for slug, evs in groups.items():
            # 1 bai binh luan nhieu lan (thu lai / dong trung) -> tinh 1 lan
            uniq = {}
            for e in sorted(evs, key=lambda x: x["time"]):
                uniq.setdefault(fb_login.post_id_of(e["url"]) or id(e), e)
            entries = [{"time": e["time"].timestamp(), "post_id": fb_login.post_id_of(e["url"]), "snippet": snip}
                       for e in uniq.values()]
            result = dict(zip(uniq.keys(), fb_login.item_statuses(st["groups"][slug], entries)))
            g = st["groups"][slug]
            checked = g.get("items_checked") or (g.get("checked", 0) if g.get("admin") else 0)
            for e in evs:
                out[id(e)] = (result[fb_login.post_id_of(e["url"]) or id(e)], checked)
        return out

    def comment_stats(self, account, item, days=7):
        """Tool theo doi: {ma nhom: {'approved','pending','declined','removed','unchecked','fail'}} trong `days` ngay.

        Trang thai lay tu lan 'Cap nhat' gan nhat (muc Dang cho / Bi tu choi / Da go tren Facebook);
        'fail' = bai tool khong binh luan duoc lan nao.
        """
        import fb_login
        events = [e for run in parse_log(self.log_paths(account, item), days=days, campaign=item["name"])
                  for e in run["events"] if e["url"]]
        status = self.current_statuses(account, item, events)
        best, rank = {}, {"fail": 0, "unchecked": 1, "removed": 2, "declined": 2, "pending": 3, "approved": 4}
        for e in events:
            if not ("bình luận" in e["label"]):
                continue
            key = (fb_login.group_slug(e["url"]), fb_login.post_id_of(e["url"]) or e["url"])
            res = status.get(id(e), ("unchecked",))[0] if self.is_sent_event(e, "comments") else status.get(id(e), ("fail",))[0]
            if rank[res] > rank.get(best.get(key), -1):
                best[key] = res
        stats = {}
        for (slug, _post), res in best.items():
            c = stats.setdefault(slug, dict.fromkeys(("approved", "pending", "declined", "removed", "unchecked", "fail"), 0))
            c[res] += 1
        return stats

    def comment_report(self, r, note, c):
        """Tool theo doi: 1 dong bang (moi binh luan tinh 1 lan, theo trang thai hien tai)."""
        from datetime import datetime
        ok, wait, unchecked, fail = c.get("approved", 0), c.get("pending", 0), c.get("unchecked", 0), c.get("fail", 0)
        bad = c.get("declined", 0) + c.get("removed", 0)
        parts = [f"✅ {ok} đã duyệt" if ok else "", f"⏳ {wait} chờ duyệt" if wait else "",
                 f"❌ {bad} bị từ chối / gỡ" if bad else "", f"⚪ {unchecked} chưa kiểm tra" if unchecked else "",
                 f"{fail} không bình luận được" if fail else ""]
        text = "\n".join(x for x in parts if x) or "chưa bình luận"
        if note:
            until = f"{datetime.fromtimestamp(note['until']):%H:%M ngày %d/%m}" if note.get("until") else "?"
            return (2, text, f"🟡 Tool tạm ngừng bình luận đến {until}\n(nhóm không cho bình luận)",
                    "Mở bài xem thử (tab Kết quả chi tiết) – hoặc bấm 'Cho bình luận lại ngay'", note)
        if bad >= 2 and bad >= ok:
            return 3, text, "🔴 Nhóm hay từ chối / gỡ bình luận", "Cân nhắc bỏ nhóm khỏi danh sách", None
        if fail >= 2 and fail > ok + wait + unchecked:
            return 2, text, "🟡 Hay không bình luận được", "Mở bài xem thử (tab Kết quả chi tiết)", None
        if wait:
            return 2, text, "🟡 Có bình luận đang chờ duyệt", "Đợi quản trị viên duyệt", None
        if ok:
            return 0, text, "🟢 Bình luận được duyệt", "Không cần làm gì", None
        if unchecked:
            return 1, text, "⚪ Chưa kiểm tra trạng thái", "Bấm 'Cập nhật ngay'", None
        if fail:
            return 1, text, "⚪ Lần trước không bình luận được", "Mở bài xem thử (tab Kết quả chi tiết)", None
        return 1, text, "⚪ Chưa có khách phù hợp", "Không cần làm gì", None

    def group_report(self, r, notes, cstats=None, k="posts"):
        """1 dong bang: (muc do 0 tot..3 xau, bai cua ban, tinh trang, ban nen lam, ghi chu tam dung hoac None)."""
        from datetime import datetime
        if k == "comments":
            keys = {_link_key(r["url"]), r["slug"], f"groups/{r['slug']}"}
            note = next((n for n in notes if n.get("kind") == "group" and n.get("key") in keys), None)
            return self.comment_report(r, note, (cstats or {}).get(r["slug"], {}))
        w = self._word(k)
        act = "đăng" if k == "posts" else "bình luận"
        info = r["info"]
        get = lambda tab: (info.get(tab) or {}).get(k, 0)
        ok, wait, bad = get("posted"), get("pending"), get("declined") + get("removed")
        parts = [f"{bad} bị từ chối / gỡ" if bad else "", f"{wait} đang chờ duyệt" if wait else "",
                 f"{ok} đã lên" if ok else ""]
        posts = "\n".join(p for p in parts if p) or (f"chưa có {w} nào" if info else "–")
        keys = {_link_key(r["url"]), r["slug"], f"groups/{r['slug']}"}
        note = next((n for n in notes if n.get("kind") in ("group", "pending") and n.get("key") in keys), None)
        when = lambda t: f"{datetime.fromtimestamp(t):%H:%M ngày %d/%m}"
        if note and note["kind"] == "pending":
            return (2, posts, f"🟡 Tool tạm ngừng {act}\n(còn {note.get('count', '?')} bài cũ chưa được duyệt)",
                    "Đợi quản trị viên duyệt – hoặc bấm 'Cho đăng lại ngay'", note)
        if note and note.get("fault") == "chua_vao":
            return (2, posts, f"🟡 Tool tạm ngừng {act} đến {when(note['until'])}\n(chưa được duyệt vào nhóm)",
                    "Vào nhóm trả lời câu hỏi tham gia, đợi duyệt", note)
        if note and note.get("fault") == "chan_han":
            return (3, posts, f"🔴 Tool tạm ngừng {act} đến {when(note['until'])}\n(nhóm không cho đăng)",
                    "Xoá nhóm này khỏi danh sách", note)
        if note:
            return (2, posts, f"🟡 Tool tạm ngừng {act} đến {when(note['until'])}\n(nhóm không cho {act})",
                    f"Vào nhóm xem có cho {act} không – hoặc bấm 'Cho {act} lại ngay'", note)
        if info.get("admin"):
            # Facebook khong cho quan tri vien xem 'Noi dung cua ban' -> khong dem duoc, nhung bai len ngay.
            return (0, f"{r['sent7']} {w} đã gửi (7 ngày)" if r["sent7"] else "–",
                    f"🟢 Bạn là quản trị viên nhóm\n({w} lên ngay, không cần duyệt)", "Không cần làm gì", None)
        if bad >= 2 and bad >= ok:
            return 3, posts, f"🔴 Nhóm hay từ chối {w}", f"Xoá nhóm khỏi danh sách\n(hoặc đăng thưa: 1 {w} / 3 ngày)", None
        if info.get("member_review") and not ok:
            return 2, posts, "🟡 Nhóm đang duyệt thành viên mới", "Vào nhóm tương tác tay vài ngày trước", None
        if wait >= 2:
            return 2, posts, f"🟡 Nhiều {w} đang chờ duyệt", "Đợi quản trị viên duyệt", None
        if ok:
            return 0, posts, f"🟢 {act.capitalize()} bình thường", "Không cần làm gì", None
        if not info and not r["sent7"]:
            return 1, posts, "⚪ Chưa có số liệu", "Bấm 'Cập nhật ngay' để xem", None
        if not r["sent7"]:
            # Chua gui gi vao nhom nay (tool theo doi: chua co khach phu hop) -> khong co gi de danh gia.
            return 1, posts, f"⚪ Chưa {act} ở nhóm này", "Không cần làm gì", None
        return (1, posts, f"⚪ Đã gửi {r['sent7']} {w}, Facebook chưa ghi nhận",
                "Đợi vài giờ rồi bấm 'Cập nhật ngay'", None)

    def results_tab(self, parent, account, item):
        k = self.kind(item).RESULT_KIND
        w = self._word(k)
        act = "đăng" if k == "posts" else "bình luận"
        acc_dir = self.account_dir(account)
        get_notes = lambda: self.store.pause_notes(account, item)

        # Ca tai khoan bi Facebook han che -> khung do tren cung (anh huong moi nhom)
        banner = ttk.Frame(parent)
        banner_txt = fit(ttk.Label(banner, text="", style="Bad.TLabel", justify="left"))
        banner_btn = ttk.Button(banner, text=f"Cho {act} lại ngay")
        banner_btn.pack(side="right", padx=(8, 0), anchor="n")
        banner_txt.pack(side="left", fill="x", expand=True)

        bar = ttk.Frame(parent)
        bar.pack(fill="x")
        last_lbl = ttk.Label(bar, text="", style="Hint.TLabel")
        last_lbl.pack(side="left")
        btn = ttk.Button(bar, text="🔄  Cập nhật ngay")
        btn.pack(side="right")
        prog_box = ttk.Frame(parent, padding=(10, 8))
        prog_bar = ttk.Progressbar(prog_box, mode="determinate", maximum=100)
        prog_bar.pack(fill="x")
        prog_txt = fit(ttk.Label(prog_box, text="", style="Field.TLabel", justify="left"))
        prog_txt.pack(fill="x", pady=(6, 0))
        fit(ttk.Label(prog_box, style="Hint.TLabel", justify="left",
                      text="Tool đang chạy ngầm và CHỈ XEM (không đăng, không bình luận). Bạn cứ làm việc khác hoặc "
                           "chuyển sang mục khác – kiểm tra xong bảng tự cập nhật.")).pack(fill="x", pady=(2, 0))

        table = GridTable(parent, [("name", "Nhóm", 138, "w"), ("posts", "Bài đăng" if k == "posts" else "Bình luận (7 ngày)", 112, "w"),
                                   ("status", "Tình trạng", 168, "w"), ("todo", "Bạn nên làm", 158, "w")])
        table.pack(fill="x", pady=(10, 0))
        fit(ttk.Label(parent, style="Hint.TLabel", justify="left",
                      text="Nhóm có vấn đề tự xếp lên đầu. Bấm 1 dòng để xem số liệu đầy đủ.")).pack(fill="x", pady=(4, 0))
        detail = fit(ttk.Label(parent, text="", justify="left"))
        detail.pack(fill="x", pady=(6, 0))
        bottom = ttk.Frame(parent)
        bottom.pack(fill="x", pady=(8, 0))
        btn_open = ttk.Button(bottom, text="🌐  Xem nhóm trên Facebook")
        btn_open.pack(side="left")
        btn_reset = ttk.Button(bottom, text=f"▶  Cho {act} lại ngay")
        btn_reset.pack(side="left", padx=(8, 0))
        colors = {3: "#fde2e1", 2: "#fff1d6", 1: "#ffffff", 0: "#e3f5e6"}

        def fill():
            from datetime import datetime
            notes = get_notes()
            acc_note = next((n for n in notes if n.get("kind") in ("account", "recovering")), None)
            if acc_note and acc_note["kind"] == "account":
                banner_txt.configure(text=f"⛔ CẢ tài khoản đang bị Facebook hạn chế → tool nghỉ {act} đến "
                                          f"{datetime.fromtimestamp(acc_note['until']):%H:%M ngày %d/%m}.\n"
                                          f"{acc_note.get('reason', '')}", style="Bad.TLabel")
            elif acc_note:
                banner_txt.configure(text=f"🐢 Tài khoản vừa hết tạm nghỉ → hôm nay tool chỉ {act} nửa số nhóm "
                                          "cho an toàn.", style="Warn.TLabel")
            if acc_note:
                banner_btn.configure(command=lambda: reset_note(acc_note))
                banner.pack(fill="x", pady=(0, 10), before=bar)
            else:
                banner.pack_forget()
            table.clear()
            rows = result_rows(acc_dir, self.item_groups(account, item), k)
            # Xau truoc (do, vang), roi tot (xanh), cuoi cung la nhom chua co gi (trang)
            order = {3: 0, 2: 1, 0: 2, 1: 3}
            cstats = self.comment_stats(account, item) if k == "comments" else None
            reports = sorted(((self.group_report(r, notes, cstats, k), r) for r in rows),
                             key=lambda x: order.get(x[0][0], 4))
            for (level, posts, status, todo, note), r in reports:
                table.add((r["name"], posts, status, todo), bg=colors.get(level, "#ffffff"), wrap=True,
                          data={"row": r, "note": note, "status": status, "todo": todo})
            last = max((r["info"].get("checked", 0) for r in rows), default=0)
            last_lbl.configure(text=f"Cập nhật lần cuối: {datetime.fromtimestamp(last):%H:%M ngày %d/%m}" if last
                               else "Chưa có số liệu – bấm 'Cập nhật ngay' hoặc đợi lượt chạy tới.")
            detail.configure(text="")
            btn_reset.state(["disabled"])

        def on_select(d):
            r, note = d["row"], d["note"]
            info = r["info"]
            g = lambda tab: (info.get(tab) or {}).get(k, 0)
            lines = [f"{r['name']}"]
            if info:
                lines.append(f"Trên Facebook (tổng từ trước tới nay): {g('posted')} đã lên · {g('pending')} chờ duyệt · "
                             f"{g('declined')} bị từ chối · {g('removed')} bị gỡ.")
            lines.append(f"Tool đã gửi {r['sent7']} {w} trong 7 ngày qua.")
            if note:
                lines.append("Vì sao tạm ngừng: " + note["text"].split(": ", 1)[-1])
            detail.configure(text="\n".join(lines))
            btn_reset.state(["!disabled"] if note and note.get("reset") else ["disabled"])

        def reset_note(note):
            if not messagebox.askyesno(f"Cho {act} lại ngay", f"Bỏ tạm ngừng và cho tool {act} lại ở lần chạy tới?"
                                       f"\n\n{note['text']}"):
                return
            self.reset_note_pause(account, note, item)
            fill()
            self.flash(f"Đã bỏ tạm ngừng – lần chạy tới tool sẽ {act} lại.")

        def reset_selected():
            d = table.selected()
            if d and d["note"]:
                reset_note(d["note"])

        def open_selected(_d=None):
            d = table.selected()
            r = d["row"] if d else None
            if not r or not r["slug"]:
                messagebox.showinfo("Xem trên Facebook", "Chọn 1 nhóm trong bảng trước.")
                return
            import fb_login
            proc = subprocess.Popen([self.python, str(self.SCRIPT), "--open-url", fb_login.content_url(r["slug"]),
                                     "--account", account["id"]], cwd=self.base_dir, creationflags=NO_WINDOW,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.flash(f"Đang mở Chrome của '{account['name']}' ở trang 'Nội dung của bạn'… Xem xong thì ĐÓNG Chrome.")
            self.page_open_hint(account, item)
            self.root.after(4000, lambda: proc.poll() == 4 and messagebox.showwarning(
                "Tài khoản đang bận", f"'{account['name']}' đang chạy theo lịch (đăng bài / quét) → mở lại sau vài phút."))

        def show_progress(p):
            if not prog_box.winfo_ismapped():
                prog_box.pack(fill="x", pady=(8, 0), after=bar)
            step = p.get("step", "")
            if step == "wait":
                if str(prog_bar.cget("mode")) != "indeterminate":
                    prog_bar.configure(mode="indeterminate")
                    prog_bar.start(15)
            else:
                prog_bar.stop()
                prog_bar.configure(mode="determinate")
                n = max(1, p.get("n", 0))
                done = {"start": 0, "login": 0.03, "group": (p.get("i", 0) + 0.5) / (n + 1),
                        "notify": n / (n + 1), "done": 1}.get(step, 0)
                prog_bar["value"] = done * 100
            order = {"start": 1, "wait": 1, "login": 2, "group": 3, "notify": 4, "done": 4}
            prog_txt.configure(text=(f"Bước {order.get(step, 1)}/4 · " if step != "done" else "") + p.get("text", ""))

        def poll():
            proc = self._checks.get(account["id"])
            if not prog_box.winfo_exists():
                return
            if proc is not None and proc.poll() is None:
                p = fb_login_progress(acc_dir)
                btn.state(["disabled"])
                btn.configure(text="⏳  Đang cập nhật…")
                if p:
                    show_progress(p)
                self.root.after(500, poll)
                return
            p = fb_login_progress(acc_dir, finished=True)   # doc SAU khi tien trinh xong (tranh doc tien do cu)
            self.check_state(account["id"])   # ghi nhan ket qua (icon ✅ / ⚠ tren cay)
            btn.state(["!disabled"])
            btn.configure(text="🔄  Cập nhật ngay")
            if p and p.get("done"):
                show_progress(p)
                if p.get("ok"):
                    fill()
                    self.stale_result_tabs()
                    self.refresh_tree(f"campaign:{item['id']}")
                    self.root.after(6000, lambda: prog_box.winfo_exists() and prog_box.pack_forget())
            else:
                prog_box.pack_forget()

        def check_now():
            if not self.start_check(account, item):
                messagebox.showinfo("Cập nhật", "Chưa có nhóm nào để xem (link nhóm chưa đúng dạng "
                                                "facebook.com/groups/...).")
                return
            n = len(self.item_groups(account, item))
            show_progress({"step": "start", "text": f"Đang chuẩn bị xem {n} nhóm (khoảng {max(1, n // 2)} phút)…"})
            poll()

        btn.configure(command=check_now)
        btn_open.configure(command=open_selected)
        btn_reset.configure(command=reset_selected)
        table.on_select = on_select
        table.on_double = open_selected
        fill()
        if account["id"] in self._checks:   # dang cap nhat tu truoc (chuyen muc roi quay lai)
            poll()

    # ------------------------------------------------------------ rule khi loi (Setting nang cao)
    def rules_box(self, parent):
        """Khung 'Rule khi loi': 1 bo chung cho ca tool, sua o noi dung nao cung la bo do."""
        spec = getattr(self.store, "RULE_SPEC", None)
        if not spec:
            return
        rules = self.data.setdefault("rules", self.store.rules(self.data))
        defaults = self.store.RULE_DEFAULTS
        variables = {}

        def reset_all():
            for key, var in variables.items():
                var.set(str(defaults[key]))
            self.flash("Đã đưa rule về mặc định – bấm Lưu để áp dụng.")

        if isinstance(parent, Box):   # nut tren thanh tieu de (ban thiet ke 1)
            parent.add_button("↺ Đưa về mặc định", reset_all)
        else:
            head = ttk.Frame(parent)
            head.pack(fill="x")
            ttk.Button(head, text="↺ Về mặc định", command=reset_all).pack(side="right", anchor="n", padx=(8, 0))

        def spin(box, slot, rv):
            key, default, lo, hi = slot
            var = tk.StringVar(value=str(rules.get(key, default)))
            no_wheel(NumBox(box, from_=lo, to=hi, textvariable=var, width=5, font=FONT))
            variables[key] = var
            rv.append((key, var))
            self.form.widgets[key] = ("int", var, {"target": rules, "min": lo, "max": hi})
            return box.winfo_children()[-1]

        def watch(rv, lbl):
            def show(*_a):
                changed = any(v.get().strip() != str(defaults[k]) for k, v in rv)
                lbl.configure(text="(mặc định: " + " · ".join(str(defaults[k]) for k, _v in rv) + ")" if changed else "")
            for _k, var in rv:
                var.trace_add("write", lambda *_a: self.mark_dirty())
                var.trace_add("write", show)
            show()

        # moi rule 1 khung nho, xep luoi 2 cot (ban thiet ke 1)
        board = ttk.Frame(parent)
        board.pack(fill="x")
        board.columnconfigure(0, weight=1, uniform="r")
        board.columnconfigure(1, weight=1, uniform="r")
        for n, (title, parts) in enumerate(spec):
            sub = Box(board, text=title.lstrip("①②③④⑤⑥⑦⑧⑨ ").strip())
            sub.grid(row=n // 2, column=n % 2, sticky="nsew", padx=(0, 10) if n % 2 == 0 else 0, pady=(0, 10))
            for part in parts:
                if part[0] == "text":
                    fit_wrap(ttk.Label(sub, text=part[1].lstrip("→ "), justify="left"), sub).pack_configure(pady=2)
                elif part[0] == "tip":
                    fit_wrap(ttk.Label(sub, text=part[1], style="Hint.TLabel", justify="left"),
                             sub).pack_configure(pady=(4, 0))
                elif part[0] == "grid":
                    grid = ttk.Frame(sub)
                    grid.pack(anchor="w", pady=2)
                    for r, (label, verb, slot, unit) in enumerate(part[1]):
                        rv = []
                        ttk.Label(grid, text=label).grid(row=r, column=0, sticky="w", pady=2)
                        ttk.Label(grid, text=verb).grid(row=r, column=1, sticky="e", padx=(14, 6))
                        spin(grid, slot, rv).grid(row=r, column=2, sticky="w")
                        ttk.Label(grid, text=unit).grid(row=r, column=3, sticky="w", padx=(6, 0))
                        note = ttk.Label(grid, text="", style="Warn.TLabel")
                        note.grid(row=r, column=4, sticky="w", padx=(10, 0))
                        watch(rv, note)
                else:   # line: chu co o so chen giua (o hep: phan chu sau o so tu xuong dong)
                    row = ttk.Frame(sub)
                    row.pack(fill="x", pady=3)
                    rv = []
                    pieces = part[1].lstrip("→ ").split("{}")
                    for i, piece in enumerate(pieces):
                        if piece.strip():
                            label = ttk.Label(row, text=piece.strip(), justify="left")
                            label.pack(side="left", padx=(0 if i == 0 else 6, 0))
                            if i == len(pieces) - 1:
                                label.configure(wraplength=220)
                        if i < len(part[2]):
                            spin(row, part[2][i], rv).pack(side="left", padx=(6, 0))
                    note = ttk.Label(row, text="", style="Warn.TLabel")
                    note.pack(side="left", padx=(10, 0))
                    watch(rv, note)

    # ---- tab Chi tiet
    def start_check(self, account, item=None):
        """Chay ngam 'Cap nhat': vao Facebook xem lai cac nhom (Dang cho / Bi tu choi / Da go). False neu khong co nhom."""
        import fb_login
        campaigns = [item] if item else [c for c in account["campaigns"] if c.get("enabled", True)]
        # Task 003: moi danh tinh 1 lan doc ket qua (Ca nhan truoc), chay noi tiep trong 1 Chrome moi lan.
        by_identity = {}
        for c in campaigns:
            for g in self.item_groups(account, c):
                if fb_login.group_slug(g):
                    by_identity.setdefault(c.get("post_as") or "self", []).append(fb_login.group_slug(g))
        slugs = [s for v in by_identity.values() for s in v]
        if not slugs or account["id"] in self._checks:
            return bool(slugs)
        acc_dir = self.account_dir(account)
        try:
            (acc_dir / "kiem_tra_tien_do.json").unlink()
        except OSError:
            pass
        cmds = []
        for ident in sorted(by_identity, key=lambda i: i != "self"):
            cmd = [self.python, str(self.SCRIPT), "--check-results", "--account", account["id"], "--groups",
                   ",".join(dict.fromkeys(by_identity[ident]))]
            if item:
                cmd += ["--campaign", item["id"]]
            elif ident != "self":
                cmd += ["--identity", ident]
            cmds.append(cmd)
        # Loi khi chay (vd thoat ngay, chua kip ghi tien do) -> ghi ra file de giao dien bao lai.
        err_path = acc_dir / CHECK_ERROR_FILE
        self._checks[account["id"]] = _ChainProc(cmds, self.base_dir, err_path)
        self._check_done.pop(account["id"], None)
        self.watch_checks()
        return True

    def approved_posts(self, account, item, days=30):
        """Bai da duoc duyet CUA MINH -> [{time, group, url, detail}] (link bai that de binh luan/mo dung bai).

        Uu tien lay tu muc 'Da dang' (posted_items, co link bai that) ma lan 'Cap nhat' da doc; neu chua co
        thi suy ra tu nhat ky (chi co link nhom - mo duoc nhom nhung khong tro dung bai).
        """
        import fb_login
        from datetime import datetime
        st = fb_login.load_results(self.item_dir(account, item))
        out, seen = [], set()
        # 1) Link bai that tu muc 'Da dang' cua tung nhom trong noi dung nay.
        for url in self.item_groups(account, item):
            slug = fb_login.group_slug(url) or url
            g = st["groups"].get(slug, {})
            # Gio dang tung bai: muc 'Da dang' xep MOI NHAT truoc, nhat ky gui cung vay -> bai thu k cung doan dau
            # noi dung = lan gui thu k (cung noi dung dang nhieu lan thi khong khop theo chu duoc). Bai cu hon moi lan
            # gui con ghi -> khong ro ngay dang (time None: chi dem, khong hien khi loc theo thoi gian).
            sent = sorted((e for e in st["sent"].get(slug, []) if e[1] == "post" and len(e) > 3 and e[3]),
                          key=lambda e: -e[0])
            used = set()
            for it in g.get("posted_items", []):
                if it.get("id") in seen or not it.get("url"):
                    continue
                seen.add(it.get("id"))
                body = fb_login.text_key(it.get("text", ""))
                k = next((n for n, e in enumerate(sent) if n not in used and e[3] in body), None)
                if k is not None:
                    used.add(k)
                out.append({"time": datetime.fromtimestamp(sent[k][0]) if k is not None else None,
                            "group": g.get("name") or slug, "url": it["url"], "detail": it.get("text", "")})
        out.sort(key=lambda p: p["time"] or datetime.min, reverse=True)
        if out or self.kind(item).RESULT_KIND == "posts":
            return out
        # 2) Du phong cho tool theo doi (binh luan): lay tu nhat ky (co post_id).
        runs = parse_log(self.log_paths(account, item), days=days,
                         campaign=item["name"] if self.kind(item).LOG_TASK_LEVEL == "account" else None)
        events = [e for r in runs for e in r["events"] if e.get("url")]
        status = self.current_statuses(account, item, events)
        names = {slug: g.get("name") for slug, g in st["groups"].items() if g.get("name")}
        for e in sorted(events, key=lambda x: x["time"], reverse=True):
            if (status.get(id(e)) or ("",))[0] != "approved":
                continue
            key = fb_login.post_id_of(e["url"]) or e["url"]
            if key in seen:
                continue
            seen.add(key)
            out.append({"time": e["time"], "group": names.get(e["group"], e["group"]) or "nhóm",
                        "url": e["url"], "detail": e.get("detail", "")})
        return out

    # ---- Cham bai: binh luan mo ta shop vao cac bai DA DUYET (moi bai 1 lan). Trang thai: accounts/<id>/cham_bai.json
    CARE_TEXT = {"queued": "⏳ chờ gửi", "sending": "⏳ đang gửi", "sent": "💬 đã bình luận", "visible": "✅ đã lên",
                 "failed": "❌ lỗi"}
    CARE_BG = {"visible": "#e3f5e6", "sent": "#eef3fb", "failed": "#fde2e1"}

    def care_state(self, account, item=None):
        import fb_login
        return fb_login.load_care_state(self.item_dir(account, item))

    def care_cell(self, care, url):
        import fb_login
        st = care.get(fb_login.post_id_of(url) or url, {}).get("status", "") if url else ""
        return self.CARE_TEXT.get(st, "")

    def care_text_owner(self, item):
        """Noi luu noi dung cham bai: settings cua kich ban (muc cua tai khoan duoc sinh lai khi Luu)."""
        find = getattr(self.store, "scenario_of", None)
        s = find(self.data, item["id"])[0] if find else None
        return s["settings"] if s else item

    def care_dialog(self, account, item, posts, started=None):
        """Hop thoai chan bai: CHI noi dung binh luan (bai da chon o bang Ket qua chi tiet)."""
        if not self.account_usable(account):
            messagebox.showwarning("Chăm bài", f"Tài khoản '{account['name']}' chưa đăng nhập.")
            return
        owner = self.care_text_owner(item)
        win = tk.Toplevel(self.root)
        win.title(f"Chăm {len(posts)} bài đã duyệt – {self.account_label(account)}")
        win.geometry("640x420")
        win.minsize(520, 360)
        win.transient(self.root)
        frame = ttk.Frame(win, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"💬  Chăm {len(posts)} bài đã chọn", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Nội dung bình luận (mô tả thêm shop / dịch vụ, trả lời khách…). Tool bình luận vào "
                              "từng bài đã chọn – mỗi bài chỉ MỘT lần, các bài cách nhau 30–70 giây.",
                  style="Hint.TLabel", wraplength=600, justify="left").pack(anchor="w", pady=(2, 8))
        note_frame, note = text_box(frame, 8, wrap="word")
        note_frame.pack(fill="both", expand=True)
        note.insert("1.0", owner.get("care_text", "") or item.get("care_text", ""))
        note.focus_set()
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x", pady=(12, 0))

        def text_now():
            return note.get("1.0", "end").strip()

        def keep_text():
            text = text_now()
            if text != owner.get("care_text", ""):
                owner["care_text"] = item["care_text"] = text
                self.mark_dirty()
                self.save(quiet=True)

        def copy_text():
            if not text_now():
                messagebox.showinfo("Copy", "Ô nội dung đang trống.", parent=win)
                return
            self.root.clipboard_clear()
            self.root.clipboard_append(text_now())
            keep_text()
            self.flash("Đã copy nội dung – dán (Ctrl+V) vào ô bình luận.")

        def open_self():
            keep_text()
            subprocess.Popen([self.python, str(self.SCRIPT), "--open-tabs", "--account", account["id"],
                              "--urls", "|".join(p["url"] for p in posts)], cwd=self.base_dir,
                             creationflags=NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.flash(f"Đang mở {len(posts)} bài bằng Chrome của '{account['name']}' để bạn tự chăm (xong thì đóng "
                       "Chrome).")
            win.destroy()
            self.page_open_hint(account, item)

        def comment():
            text = text_now()
            if not text:
                messagebox.showinfo("Chăm bài", "Điền nội dung bình luận trước.", parent=win)
                return
            keep_text()
            proc = subprocess.Popen([self.python, str(self.SCRIPT), "--comment-posts", "--account", account["id"],
                                     "--urls", "|".join(p["url"] for p in posts), "--text", text]
                                    + self.identity_args(item),
                                    cwd=self.base_dir, creationflags=NO_WINDOW,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.flash(f"💬 Đang bình luận vào {len(posts)} bài (chạy ngầm) – cột 'Chăm bài' tự cập nhật.")
            win.destroy()
            if started:
                started(proc)

        ttk.Button(bottom, text="📋  Copy", command=copy_text).pack(side="left")
        ttk.Button(bottom, text="🌐  Mở để tự chăm", command=open_self).pack(side="left", padx=(8, 0))
        ttk.Button(bottom, text=f"💬  Bình luận vào {len(posts)} bài", style="Accent.TButton" if sv_ttk else "TButton",
                   command=comment).pack(side="right")
        ttk.Button(bottom, text="Hủy", command=win.destroy).pack(side="right", padx=(0, 8))
        win.grab_set()

    def identity_args(self, item):
        """['--identity', id Page] cho lenh chay tu 1 muc dang bang Page (Ca nhan -> [] nhu cu)."""
        ident = (item or {}).get("post_as") or "self"
        return [] if ident == "self" else ["--identity", ident]

    def open_in_account(self, account, url, item=None):
        """Mo link bang Chrome cua tai khoan (dang nhap san -> thay ca bai / binh luan dang cho duyet)."""
        proc = subprocess.Popen([self.python, str(self.SCRIPT), "--open-url", url, "--account", account["id"]],
                                cwd=self.base_dir, creationflags=NO_WINDOW,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.flash(f"Đang mở bài bằng Chrome của '{account['name']}'… Xem xong thì ĐÓNG Chrome để tool chạy tiếp.")
        self.page_open_hint(account, item)

        def busy():
            if proc.poll() == 4 and messagebox.askyesno(
                    "Tài khoản đang bận", f"'{account['name']}' đang chạy (đăng bài / quét) nên chưa mở Chrome của tài "
                    "khoản được.\n\nMở bằng trình duyệt thường? (có thể không thấy bình luận chờ duyệt nếu trình "
                    "duyệt đó không đăng nhập đúng tài khoản)"):
                import webbrowser
                webbrowser.open(url)
        self.root.after(4000, busy)

    def log_paths(self, account, item):
        folder = self.base_dir / "logs" / (account["id"] if self.kind(item).LOG_TASK_LEVEL == "account" else item["id"])
        return [folder / "nhat_ky.1.txt", folder / "nhat_ky.txt"]

    def details_tab(self, parent, account, item):
        """Ket qua chi tiet: nhat ky tung luot + cot 'Cham bai'.

        Che do 'Chi bai da duyet': bang liet ke cac bai DA DUYET (co link bai that). Nut '💬 Cham bai':
        bam lan 1 -> cac dong co o chon; chon bai; bam lan 2 -> hop thoai noi dung -> tool binh luan,
        cot 'Cham bai' tu cap nhat: cho gui -> dang gui -> da binh luan -> da len (thay tren bai) / loi.
        """
        import os
        import webbrowser
        # Theo doi (binh luan vao bai nguoi khac): khong co cham bai -> chi loc thoi gian + loc theo cot.
        monitor = self.kind(item).RESULT_KIND == "comments"
        top = ttk.Frame(parent)
        top.pack(fill="x")
        ttk.Label(top, text="Xem:").pack(side="left")
        days_var = tk.StringVar(value=EVENT_DAYS[1][0])
        days_box = ttk.Combobox(top, textvariable=days_var, values=[d for d, _ in EVENT_DAYS], state="readonly",
                                width=12)
        days_box.pack(side="left", padx=(4, 8))
        refresh_btn = ttk.Button(top, text="🔄  Cập nhật ngay")
        refresh_btn.pack(side="right")
        care_var = tk.BooleanVar(value=False)
        care_btn = ttk.Button(top, text="💬  Chăm bài")
        cancel_btn = ttk.Button(top, text="✕  Thôi chọn")
        if not monitor:
            # Hang 2: Chi bai da duyet + Cham bai (rieng 1 hang -> khong bi cat chu khi cua so hep)
            top2 = ttk.Frame(parent)
            top2.pack(fill="x", pady=(8, 0))
            ttk.Checkbutton(top2, text="Chỉ bài đã duyệt", variable=care_var, command=lambda: set_view(),
                            style="Switch.TCheckbutton" if sv_ttk else "TCheckbutton").pack(side="left")
            care_btn = ttk.Button(top2, text="💬  Chăm bài")
            care_btn.pack(side="left", padx=(10, 0))
            cancel_btn = ttk.Button(top2, text="✕  Thôi chọn")
        refresh_txt = ttk.Label(parent, text="", style="Field.TLabel")
        stats = fit(ttk.Label(parent, text="", style="Hint.TLabel", justify="left"))
        stats.pack(fill="x", pady=(8, 6))
        mode_bar = ttk.Label(parent, text="", style="Warn.TLabel")

        # cot Cham bai dat ngay sau Nhom de khong bi khuat khi cua so hep. Bam tieu de 'Ket qua luc gui' /
        # 'Trang thai hien tai' -> loc theo gia tri trong cot.
        cols = [("time", "Giờ", 78, "center"), ("group", "Nhóm", 200, "w"),
                ("care", "Chăm bài", 120, "center"), ("result", "Kết quả lúc gửi", 170, "w"),
                ("now", "Trạng thái hiện tại", 170, "w"), ("detail", "Chi tiết", 480, "w")]
        if monitor:
            cols.pop(2)
        table = GridTable(parent, cols, rows_visible=14, max_rows_visible=18, filterable=("result", "now"))
        table.pack(fill="both", expand=True)
        APPROVED = self.STATUS_TEXT["approved"]

        def row(time_, group, care, result, now, detail):
            return (time_, group, result, now, detail) if monitor else (time_, group, care, result, now, detail)
        colors = {"ok": "#e3f5e6", "wait": "#eef3fb", "skip": "#f3f3f3", "error": "#fde2e1"}
        full = fit(ttk.Label(parent, text="", justify="left"))
        full.pack(fill="x", pady=(8, 0))
        hint = fit(ttk.Label(parent, style="Hint.TLabel", justify="left", text=""))
        hint.pack(fill="x")
        st = {"select": False, "picked": set(), "proc": None, "verify": None}

        def set_hint():
            hint.configure(text=(
                "Bấm vào dòng bài để chọn / bỏ chọn, xong bấm '💬 Chăm … bài đã chọn' để soạn bình luận. Bài đã bình "
                "luận rồi (💬 / ✅) không chọn lại được – mỗi bài chỉ chăm 1 lần." if st["select"] else
                "Chọn 1 dòng có 🔗 rồi bấm 'Mở bài này' (hoặc bấm đúp) để xem bài bằng Chrome của tài khoản – thấy cả "
                "bài / bình luận đang CHỜ DUYỆT. Cột 'Chăm bài': 💬 đã bình luận · ✅ đã lên (thấy trên bài) · ❌ lỗi."))

        # ---- bang
        def fill():
            import fb_login
            names = {slug: g.get("name") for slug, g in fb_login.load_results(self.account_dir(account))["groups"].items()
                     if g.get("name")}   # ma nhom (tu link bai) -> ten nhom
            care = self.care_state(account)
            table.clear()
            if care_var.get():
                fill_approved(names, care)
            else:
                fill_log(names, care)
            table.after_idle(update_stats)
            full.configure(text="")
            update_buttons(None)
            update_care_btn()

        def fill_approved(names, care):
            days = dict(EVENT_DAYS)[days_var.get()]
            since = day_start(days)
            every = self.approved_posts(account, item)
            posts = [p for p in every if p["time"] and p["time"] >= since]
            old = sum(1 for p in every if not p["time"])
            st["old"] = (f" · {old} bài đã duyệt cũ hơn (đăng trước khi tool ghi nhật ký) không hiện" if old else "")
            st["note"] = "" if posts else (
                f"Chưa có bài nào được duyệt trong {days_var.get().lower()} – bấm '🔄 Cập nhật ngay' để tool vào "
                "Facebook xem bài nào đã được duyệt (chạy ngầm ~1–2 phút).")
            for p in posts:
                cell = self.care_cell(care, p["url"])
                pickable = st["select"] and not cell.startswith(("💬", "✅", "⏳"))
                mark = ("☑ " if p["url"] in st["picked"] else "☐ ") if pickable else ("   " if st["select"] else "")
                state = care.get(fb_login_post_id(p["url"]), {}).get("status", "")
                table.add(row(f"{mark}{p['time']:%d/%m %H:%M}", p["group"], cell, "✅ Đăng thành công", APPROVED,
                              (p.get("detail") or "").replace("\n", " ") + " 🔗"),
                          bg="#cfe3ff" if p["url"] in st["picked"] else self.CARE_BG.get(state, "#ffffff"),
                          data=dict(p, kind="approved", pickable=pickable, label="Đã duyệt", icon="✅", image="",
                                    group=p["group"]))

        def fill_log(names, care):
            days = dict(EVENT_DAYS)[days_var.get()]
            runs = parse_log(self.log_paths(account, item), days=days,
                             campaign=item["name"] if self.kind(item).LOG_TASK_LEVEL == "account" else None)
            now_status = self.current_statuses(account, item, [e for r in runs for e in r["events"]])
            last_check = max((c for _s, c in now_status.values()), default=0)
            for run in runs:
                head = f"{run['time']:%d/%m  %H:%M}   ·   {run['title']}" + \
                    (f"   ·   {run['summary']}" if run["summary"] else "")
                table.add((head,), bg="#f4f5f7", bold=True, span=True,
                          data={"detail": f"{run['title']}\n{run['summary']}", "image": "", "url": ""})
                for e in run["events"]:
                    mark = (" 🖼" if e["image"] else "") + (" 🔗" if e["url"] else "")
                    cur = now_status.get(id(e))
                    gname, detail = split_group_name(e, names)
                    table.add(row(f"{e['time']:%H:%M}", gname,
                                  self.care_cell(care, e["url"]) if fb_login_post_id(e["url"]) else "",
                                  f"{e['icon']} {e['label']}".strip(), self.STATUS_TEXT[cur[0]] if cur else "",
                                  detail + mark), bg=colors.get(e["kind"], "#ffffff"), data=e)
            from datetime import datetime
            st["note"] = "" if runs else "Chưa có nhật ký trong khoảng thời gian này."
            st["checked"] = ("\nCột 'Trạng thái hiện tại': " + (
                f"theo lần cập nhật lúc {datetime.fromtimestamp(last_check):%H:%M ngày %d/%m}" if last_check
                else "chưa cập nhật lần nào – bấm 'Cập nhật ngay'") + " (tool vào Facebook xem mục Đang chờ / "
                "Bị từ chối / Đã gỡ của từng nhóm).") if runs else ""

        def update_stats():
            """Dong so lieu tren bang: dem theo cac dong DANG HIEN (sau loc thoi gian + loc theo cot)."""
            rows = table.visible_data()
            where = " (đang lọc theo cột)" if table.filters and not (care_var.get() and list(table.filters) == ["now"]) \
                else ""
            if st.get("note") and not rows:
                stats.configure(text=st["note"])
            elif care_var.get():
                care = self.care_state(account)
                state = [care.get(fb_login_post_id(p["url"]), {}).get("status", "") for p in rows]
                done = sum(s in ("sent", "visible") for s in state)   # cung cach dem voi o 'bai da cham' o tren
                wait = sum(s in ("queued", "sending") for s in state)
                bad = state.count("failed")
                stats.configure(text=f"{len(rows)} bài đã được duyệt ({days_var.get().lower()}){where} · "
                                     f"đã chăm {done} bài" + (f" · {wait} đang chăm" if wait else "")
                                     + (f" · {bad} lỗi" if bad else "") + f"{st.get('old', '')}.")
            elif not rows:
                stats.configure(text="Không có dòng nào khớp bộ lọc." + st.get("checked", ""))
            else:
                count = {"ok": 0, "wait": 0, "skip": 0, "error": 0}
                for e in rows:
                    count[e.get("kind")] = count.get(e.get("kind"), 0) + 1
                runs = sum(1 for i in table.visible() if table.items[i][3])
                stats.configure(text=f"{runs} lượt chạy{where} · ✅ {count['ok']} thành công · ⏳ {count['wait']} chờ "
                                     f"duyệt · ⏭ {count['skip']} bỏ qua / tạm nghỉ · ❌ {count['error']} lỗi / cảnh báo"
                                     + st.get("checked", ""))

        # ---- che do cham bai
        def set_view():
            # 'Chi bai da duyet' = loc cot 'Trang thai hien tai' = Da duyet (tieu de cot hien bo loc dang bat)
            if care_var.get():
                table.filters["now"] = APPROVED
            else:
                if table.filters.get("now") == APPROVED:
                    table.filters.pop("now")
                if st["select"]:
                    st["select"] = False
                    st["picked"].clear()
                    show_mode()
            fill()

        def on_filter():
            # Bo / doi loc 'Trang thai hien tai' khi dang o 'Chi bai da duyet' -> tat che do do (bang nhat ky)
            if care_var.get() and table.filters.get("now") != APPROVED:
                now = table.filters.get("now")
                care_var.set(False)
                set_view()
                if now is not None:
                    table.set_filter("now", now)
                return
            if not care_var.get() and table.filters.get("now") == APPROVED and not monitor:
                care_var.set(True)   # loc 'Da duyet' tren bang nhat ky = bat 'Chi bai da duyet' (de cham)
                set_view()
                return
            update_stats()

        def show_mode():
            if st["select"]:
                cancel_btn.pack(side="left", padx=(6, 0), after=care_btn)
                mode_bar.configure(text="✏ Đang chọn bài để chăm – bấm vào dòng bài để chọn.")
                mode_bar.pack(fill="x", before=stats, pady=(8, 0))
            else:
                cancel_btn.pack_forget()
                mode_bar.pack_forget()
            set_hint()

        def update_care_btn():
            if st["proc"] is not None and st["proc"].poll() is None:
                care_btn.configure(text="⏳  Đang chăm bài…")
                care_btn.state(["disabled"])
                return
            care_btn.state(["!disabled"])
            n = len(st["picked"])
            care_btn.configure(text=f"💬  Chăm {n} bài đã chọn" if st["select"] and n else
                               ("💬  Chọn bài để chăm…" if st["select"] else "💬  Chăm bài"))

        def care_click():
            if not st["select"]:
                st["select"] = True
                st["picked"].clear()
                if not care_var.get():
                    care_var.set(True)
                    table.filters["now"] = APPROVED
                show_mode()
                fill()
                return
            posts = [d for _i, d in table.data_rows() if d.get("kind") == "approved" and d["url"] in st["picked"]]
            if not posts:
                messagebox.showinfo("Chăm bài", "Bấm vào các dòng bài để chọn ít nhất 1 bài.")
                return
            self.care_dialog(account, item, posts, started=started)

        def cancel_click():
            st["select"] = False
            st["picked"].clear()
            show_mode()
            fill()

        def started(proc):
            st["proc"] = proc
            st["select"] = False
            st["picked"].clear()
            show_mode()
            watch_care()

        def watch_care():
            if not table.winfo_exists():
                return
            fill()
            proc = st["proc"]
            if proc is not None and proc.poll() is None:
                p = fb_login_progress(self.account_dir(account))
                refresh_txt.configure(text="💬 " + (p.get("text") or "Đang chăm bài…"))
                if not refresh_txt.winfo_ismapped():
                    refresh_txt.pack(fill="x", before=stats, pady=(8, 0))
                self.root.after(2000, watch_care)
                return
            if proc is not None:
                p = fb_login_progress(self.account_dir(account))
                refresh_txt.configure(text=("✅ " if p.get("ok") else "⚠ ") + (p.get("text") or "Xong."))
                st["proc"] = None
                fill()

        def verify_care():
            """Sau 'Cap nhat ngay': mo lai cac bai 'da binh luan' xem binh luan da hien chua."""
            care = self.care_state(account)
            urls = [p["url"] for p in self.approved_posts(account, item)
                    if care.get(fb_login_post_id(p["url"]), {}).get("status") == "sent"]
            if not urls or not self.account_usable(account):
                return
            st["proc"] = subprocess.Popen([self.python, str(self.SCRIPT), "--verify-care", "--account", account["id"],
                                           "--urls", "|".join(urls)] + self.identity_args(item), cwd=self.base_dir, creationflags=NO_WINDOW,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            watch_care()

        care_btn.configure(command=care_click)
        cancel_btn.configure(command=cancel_click)

        # ---- cap nhat trang thai duyet (vao Facebook xem)
        def poll_refresh():
            proc = self._checks.get(account["id"])
            if not refresh_btn.winfo_exists():
                return
            if proc is not None and proc.poll() is None:
                p = fb_login_progress(self.account_dir(account))
                refresh_txt.configure(text="⏳ " + (p.get("text") or "Đang cập nhật…"))
                self.root.after(800, poll_refresh)
                return
            self.check_state(account["id"])
            p = fb_login_progress(self.account_dir(account), finished=True)
            refresh_btn.state(["!disabled"])
            refresh_txt.configure(text=("✅ " if p.get("ok") else "⚠ ") + (p.get("text") or "Xong."))
            fill()
            if p.get("ok"):
                self.stale_result_tabs()
                verify_care()

        def refresh_now():
            if not self.start_check(account, item):
                messagebox.showinfo("Cập nhật", "Chưa có nhóm nào để xem.")
                return
            refresh_btn.state(["disabled"])
            refresh_txt.pack(fill="x", before=stats, pady=(8, 0))
            poll_refresh()

        refresh_btn.configure(command=refresh_now)

        # ---- chon dong / mo bai
        def on_select(e):
            if not e:
                return
            if st["select"] and e.get("kind") == "approved":
                if e.get("pickable"):
                    st["picked"].symmetric_difference_update({e["url"]})
                    fill()
                return
            if "label" in e:
                full.configure(text=" – ".join(x for x in (f"{e['icon']} {e['label']}".strip(), e["group"],
                                                           e.get("detail", "")) if x)
                               + (f"\n🔗 {e['url']}" if e["url"] else ""))
            else:
                full.configure(text=e["detail"])

        def open_image(e):
            path = self.base_dir / e["image"]
            if path.exists():
                os.startfile(path)
            else:
                messagebox.showinfo("Ảnh lỗi", "Ảnh này đã bị xoá (tool chỉ giữ ảnh lỗi 2 ngày).")

        def on_open(e):
            if not e or st["select"]:
                return
            if e.get("url"):
                import fb_login
                slug = fb_login.group_slug(e["url"])
                target = e["url"] if fb_login.post_id_of(e["url"]) or not slug else fb_login.content_url(slug)
                self.open_in_account(account, target, item)
            elif e.get("image"):
                open_image(e)

        bottom = ttk.Frame(parent)
        bottom.pack(fill="x", pady=(8, 0))
        btn_post = ttk.Button(bottom, text="🌐  Mở bài này (Chrome của tài khoản)",
                              command=lambda: on_open(table.selected()))
        btn_post.pack(side="left")
        btn_img = ttk.Button(bottom, text="🖼  Xem ảnh lỗi", command=lambda: open_image(table.selected()))
        btn_img.pack(side="left", padx=(8, 0))
        btn_web = ttk.Button(bottom, text="Mở bằng trình duyệt thường",
                             command=lambda: webbrowser.open(table.selected()["url"]))
        btn_web.pack(side="left", padx=(8, 0))

        def update_buttons(e):
            btn_post.state(["!disabled"] if e and e.get("url") else ["disabled"])
            btn_web.state(["!disabled"] if e and e.get("url") else ["disabled"])
            btn_img.state(["!disabled"] if e and e.get("image") else ["disabled"])

        days_box.bind("<<ComboboxSelected>>", lambda _e: fill())
        table.on_filter = on_filter
        table.on_select = lambda e: (on_select(e), update_buttons(e))
        table.on_double = on_open
        set_hint()
        fill()
        if account["id"] in self._checks:   # dang cap nhat tu truoc
            refresh_btn.state(["disabled"])
            refresh_txt.pack(fill="x", before=stats, pady=(8, 0))
            poll_refresh()

    # ------------------------------------------------------------ luu
    def has_changes(self):
        self.commit_form()
        return self.snapshot() != self.saved_snapshot

    def save(self, quiet=False):
        errors = self.commit_form()
        errors += self.validate_extra()
        errors += self.store.validate(self.data)
        if errors:
            messagebox.showerror("Chưa lưu được", "Sửa các chỗ sau rồi bấm Lưu lại:\n\n• " + "\n• ".join(errors))
            return False
        self.store.save(self.data)
        self.saved_snapshot = self.snapshot()
        self.mark_clean()
        new_schedule = self.schedule_key(self.store.schedule_entries(self.data))
        msg = "Đã lưu. Lần chạy sau tool sẽ dùng thông tin mới."
        self.wait_schedule()
        if new_schedule != self.saved_schedule:
            ok, detail = self.update_schedule()
            if ok:
                self.saved_schedule = new_schedule
                msg += "\nĐã cập nhật lịch chạy tự động."
            else:
                msg += "\n\n⚠ Chưa cập nhật được lịch:\n" + detail + "\n\nĐóng giao diện rồi mở lại bằng MO_TOOL.bat (bấm Yes khi Windows hỏi quyền)."
        kind, ident = self.selected()
        self.refresh_tree(f"{kind}:{ident}" if kind else None)
        warns = getattr(self.store, "warnings", lambda data: [])(self.data)
        if quiet:
            self.flash(msg.split("\n")[0])
        elif warns:
            messagebox.showwarning("Đã lưu – nên xem lại", msg + "\n\n⚠ " + warns[0] + "\n\n• " + "\n• ".join(warns[1:]))
        else:
            messagebox.showinfo("Đã lưu", msg)
        return True

    def update_schedule(self):
        return run_setup_schedule(self.base_dir)

    def flash(self, text):
        self.status.configure(text=text)
        self.root.after(8000, lambda: self.status.winfo_exists() and self.status.configure(text=""))

    def close(self):
        if self.has_changes() and not messagebox.askyesno("Chưa lưu", "Bạn có thay đổi chưa lưu. Vẫn đóng?"):
            return
        self.root.destroy()

    # ------------------------------------------------------------ mac dinh cho lop con
    def tree_account_text(self, account):
        return account["name"]

    def tree_item_text(self, item):
        return item["name"]

    def account_item_summary(self, item):
        return item["name"]

    def item_tabs(self):
        return []

    def section_extra(self, title, parent, item):
        pass

    def validate_extra(self):
        return []

    def schedule_key(self, entries):
        return json.dumps(entries, sort_keys=True, ensure_ascii=False)

    def new_account(self, name):
        return {"id": self.store.new_id(self.data, "a"), "name": name, "campaigns": []}

    def new_item(self, name):
        item = {"id": self.store.new_id(self.data, "c"), "name": name}
        for key, value in self.store.CAMPAIGN_DEFAULTS.items():
            item[key] = list(value) if isinstance(value, list) else value
        return item


def run(app_class):
    root = tk.Tk()
    app_class(root)
    root.mainloop()
