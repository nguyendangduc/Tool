# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
"""Giao dien sua cau hinh cho tool Facebook (mo tu MO_TOOL.bat, muc [1]).

File nay GIONG HET NHAU o ca 3 tool; tu nhan biet tool theo file .py trong thu muc.
- Doc/ghi dung file config hien tai: giu nguyen dong ghi chu (#) va cac muc khong co tren giao dien.
- Danh sach (nhom, tu khoa...) nhap moi dong 1 muc, luu thanh "a|b|c" nhu tool dang doc.
- Doi gio dang / chu ky quet thi tu cap nhat lich Task Scheduler khi bam Luu.
"""
import json
import re
import subprocess
import sys
import tkinter as tk
import urllib.parse
import urllib.request
from pathlib import Path
from tkinter import messagebox, ttk

BASE_DIR = Path(__file__).resolve().parent

if (BASE_DIR / "fb_monitor_v4.py").exists():
    TOOL_KIND = "monitor"
    CONFIG_FILE = BASE_DIR / "fb_monitor_config.txt"
    TITLE = "Cấu hình tool theo dõi nhóm Facebook"
else:
    TOOL_KIND = "upstt"
    CONFIG_FILE = BASE_DIR / "fb_upstt_config.txt"
    TITLE = "Cấu hình tool đăng bài vào nhóm Facebook"

# (tab, key, kieu, nhan, goi y, tuy chon)
# kieu: list | times | rules | text | secret | bool | int
FIELDS = {
    "monitor": [
        ("basic", "GROUP_URLS", "list", "Nhóm Facebook cần theo dõi", "Mỗi dòng 1 link nhóm", {"url": True}),
        ("basic", "KEYWORDS", "list", "Từ khóa cần tìm", "Mỗi dòng 1 từ / cụm từ", {}),
        ("basic", "EXCLUDE_KEYWORDS", "list", "Từ khóa loại trừ", "Bài có các từ này sẽ bị bỏ qua. Có thể để trống", {"optional": True}),
        ("basic", "TELEGRAM_TOKEN", "secret", "Telegram - Token của bot", "Lấy từ @BotFather", {}),
        ("basic", "TELEGRAM_CHAT_ID", "text", "Telegram - Chat ID", "Lấy từ @userinfobot", {}),
        ("basic", "AUTO_COMMENT", "bool", "Tự bình luận vào bài tìm được", "", {"default": "false"}),
        ("basic", "COMMENT_TEXT", "text", "Nội dung bình luận lần 1", "", {"optional": True}),
        ("basic", "COMMENT_TEXT_2", "text", "Nội dung bình luận lần 2", "Để trống nếu chỉ bình luận 1 lần", {"optional": True}),
        ("basic", "RUN_EVERY_MINUTES", "int", "Quét mỗi bao nhiêu phút", "", {"min": 5, "max": 1440, "default": "40", "schedule": True}),
        ("basic", "MAX_RUN_MINUTES", "int", "Mỗi lần quét tối đa bao nhiêu phút", "Phải nhỏ hơn số phút ở trên", {"min": 1, "max": 1440, "default": "20", "schedule": True}),
        ("advanced", "AD_PATTERNS", "list", "Dấu hiệu bài quảng cáo", "Mỗi dòng 1 cụm từ, mỗi cụm xuất hiện = +1 điểm", {"optional": True}),
        ("advanced", "AD_SCORE_RULES", "rules", "Dấu hiệu quảng cáo có điểm riêng", "Mỗi dòng dạng:  cụm từ=điểm   (vd: hotline=3)", {"optional": True}),
        ("advanced", "AD_SCORE_THRESHOLD", "int", "Đủ bao nhiêu điểm thì coi là quảng cáo", "", {"min": 1, "max": 100, "default": "6"}),
        ("advanced", "EXCLUDED_USERS", "list", "UID người đăng cần bỏ qua", "Mỗi dòng 1 UID. Có thể để trống", {"optional": True}),
        ("advanced", "SCROLL_COUNT", "int", "Số lần cuộn trang mỗi nhóm", "Nhiều hơn = quét sâu hơn nhưng lâu hơn", {"min": 1, "max": 200, "default": "10"}),
        ("advanced", "SCROLL_DISTANCE", "int", "Mỗi lần cuộn bao nhiêu px", "", {"min": 100, "max": 5000, "default": "600"}),
        ("advanced", "SCROLL_WAIT_MS", "int", "Chờ sau mỗi lần cuộn (mili giây)", "", {"min": 0, "max": 60000, "default": "6000"}),
        ("advanced", "SEE_MORE_WAIT_MS", "int", "Chờ sau khi bấm 'Xem thêm' (mili giây)", "", {"min": 0, "max": 60000, "default": "2000"}),
        ("advanced", "HEADLESS", "bool", "Chạy ẩn (không hiện trình duyệt)", "", {"default": "true"}),
    ],
    "upstt": [
        ("basic", "GROUP_URLS", "list", "Nhóm Facebook cần đăng", "Mỗi dòng 1 link nhóm", {"url": True}),
        ("basic", "SHARE_URL", "text", "Nội dung / link bài viết cần chia sẻ", "", {}),
        ("basic", "SCHEDULE_TIMES", "times", "Giờ đăng mỗi ngày", "Mỗi dòng 1 giờ, dạng GIỜ:PHÚT (24h), vd 06:30", {"schedule": True}),
        ("advanced", "LINK_LOAD_WAIT_SECONDS", "int", "Chờ sau khi dán link (giây)", "", {"min": 1, "max": 120, "default": "5"}),
        ("advanced", "POST_WAIT_SECONDS", "int", "Chờ sau khi bấm Đăng (giây)", "", {"min": 1, "max": 120, "default": "6"}),
        ("advanced", "GROUP_SWITCH_WAIT_SECONDS", "int", "Chờ giữa 2 nhóm (giây)", "", {"min": 0, "max": 600, "default": "6"}),
        ("advanced", "HEADLESS", "bool", "Chạy ẩn (không hiện trình duyệt)", "", {"default": "true"}),
    ],
}[TOOL_KIND]


# ------------------------------------------------------------------ doc / ghi config
def read_config():
    lines = CONFIG_FILE.read_text(encoding="utf-8-sig").splitlines() if CONFIG_FILE.exists() else []
    values = {}
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            key, value = s.split("=", 1)
            values[key.strip()] = value.strip()
    # Tuong thich cau hinh cu cua Monitor
    if TOOL_KIND == "monitor" and not values.get("GROUP_URLS") and values.get("GROUP_URL"):
        values["GROUP_URLS"] = values["GROUP_URL"]
    return lines, values


def write_config(new_values):
    lines, _ = read_config()
    if CONFIG_FILE.exists():
        CONFIG_FILE.with_name(CONFIG_FILE.name + ".bak").write_text("\n".join(lines) + "\n", encoding="utf-8")
    done = set()
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            key = s.split("=", 1)[0].strip()
            if key in new_values and key not in done:
                lines[i] = f"{key}={new_values[key]}"
                done.add(key)
    missing = [k for k in new_values if k not in done]
    if missing:
        lines += ["", "# Them boi giao dien cau hinh"]
        lines += [f"{k}={new_values[k]}" for k in missing]
    CONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def split_list(value):
    return [x.strip() for x in value.split("|") if x.strip()]


# ------------------------------------------------------------------ giao dien
class ScrollFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        canvas = tk.Canvas(self, highlightthickness=0, background="#ffffff")
        bar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = ttk.Frame(canvas, padding=(16, 12), style="Card.TFrame")
        window = canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))


class App:
    def __init__(self, root):
        self.root = root
        self.widgets = {}
        self.dirty = False
        _, self.values = read_config()
        self.original = dict(self.values)

        root.title(TITLE)
        # Vua man hinh (tru thanh taskbar), dat sat mep tren.
        height = min(760, root.winfo_screenheight() - 110)
        width = min(800, root.winfo_screenwidth() - 40)
        root.geometry(f"{width}x{height}+{(root.winfo_screenwidth() - width) // 2}+20")
        root.minsize(560, 420)
        root.configure(background="#ffffff")

        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("TLabel", background="#ffffff", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 10))
        style.configure("Hint.TLabel", foreground="#6b6b6b", font=("Segoe UI", 9))
        style.configure("TCheckbutton", background="#ffffff", font=("Segoe UI", 10))
        style.configure("Save.TButton", font=("Segoe UI Semibold", 10))

        header = ttk.Frame(root, padding=(16, 12, 16, 0), style="Card.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text=TITLE, font=("Segoe UI Semibold", 13)).pack(anchor="w")
        ttk.Label(header, text=f"File: {CONFIG_FILE}", style="Hint.TLabel").pack(anchor="w")

        # Nut dat truoc (side=bottom) de luon nhin thay, khong bi phan noi dung day xuong.
        footer = ttk.Frame(root, padding=(16, 0, 16, 12), style="Card.TFrame")
        footer.pack(side="bottom", fill="x")
        ttk.Button(footer, text="Lưu", style="Save.TButton", command=self.save).pack(side="right")
        ttk.Button(footer, text="Đóng", command=self.close).pack(side="right", padx=8)
        if TOOL_KIND == "monitor":
            ttk.Button(footer, text="Gửi thử Telegram", command=self.test_telegram).pack(side="left")

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=12, pady=10)
        tabs = {"basic": ScrollFrame(notebook), "advanced": ScrollFrame(notebook)}
        notebook.add(tabs["basic"], text="  Cơ bản  ")
        notebook.add(tabs["advanced"], text="  Nâng cao  ")

        for tab, key, kind, label, hint, opts in FIELDS:
            self.add_field(tabs[tab].inner, key, kind, label, hint, opts)

        root.protocol("WM_DELETE_WINDOW", self.close)
        self.dirty = False

        # Mo tu cua so den -> dua len tren cung de nguoi dung thay ngay.
        root.lift()
        root.attributes("-topmost", True)
        root.after(800, lambda: root.attributes("-topmost", False))
        root.focus_force()

    # ---------- tao o nhap
    def add_field(self, parent, key, kind, label, hint, opts):
        box = ttk.Frame(parent, style="Card.TFrame")
        box.pack(fill="x", pady=(0, 14))
        if kind != "bool":
            ttk.Label(box, text=label, style="Title.TLabel").pack(anchor="w")
            if hint:
                ttk.Label(box, text=hint, style="Hint.TLabel").pack(anchor="w")
        value = self.values.get(key, opts.get("default", ""))

        if kind in ("list", "times", "rules"):
            frame = ttk.Frame(box, style="Card.TFrame")
            frame.pack(fill="x", pady=(4, 0))
            text = tk.Text(frame, height=6, wrap="none", font=("Segoe UI", 10), relief="solid",
                           borderwidth=1, undo=True)
            bar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
            text.configure(yscrollcommand=bar.set)
            text.insert("1.0", "\n".join(split_list(value)))
            text.edit_modified(False)
            bar.pack(side="right", fill="y")
            text.pack(side="left", fill="x", expand=True)
            # Cuon chuot trong o danh sach chi cuon o do, khong cuon ca trang.
            text.bind("<MouseWheel>", lambda e, t=text: (t.yview_scroll(int(-e.delta / 120), "units"), "break")[1])
            text.bind("<<Modified>>", self.mark_dirty)
            widget = text
        elif kind == "bool":
            var = tk.BooleanVar(value=value.strip().lower() in ("1", "true", "yes", "on"))
            ttk.Checkbutton(box, text=label, variable=var, command=self.mark_dirty).pack(anchor="w")
            if hint:
                ttk.Label(box, text=hint, style="Hint.TLabel").pack(anchor="w")
            widget = var
        elif kind == "int":
            var = tk.StringVar(value=value)
            ttk.Spinbox(box, from_=opts.get("min", 0), to=opts.get("max", 100000), textvariable=var,
                        width=10, font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 0))
            var.trace_add("write", self.mark_dirty)
            widget = var
        else:  # text / secret
            var = tk.StringVar(value=value)
            row = ttk.Frame(box, style="Card.TFrame")
            row.pack(fill="x", pady=(4, 0))
            entry = ttk.Entry(row, textvariable=var, font=("Segoe UI", 10),
                              show="•" if kind == "secret" else "")
            entry.pack(side="left", fill="x", expand=True)
            if kind == "secret":
                ttk.Button(row, text="Hiện", width=6,
                           command=lambda e=entry: e.configure(show="" if e.cget("show") else "•")
                           ).pack(side="left", padx=(6, 0))
            var.trace_add("write", self.mark_dirty)
            widget = var
        self.widgets[key] = (kind, widget, label, opts)

    def mark_dirty(self, *args):
        self.dirty = True
        for kind, widget, _, _ in self.widgets.values():
            if isinstance(widget, tk.Text):
                widget.edit_modified(False)

    # ---------- lay gia tri + kiem tra
    def collect(self):
        values, errors = {}, []
        for key, (kind, widget, label, opts) in self.widgets.items():
            if kind in ("list", "times", "rules"):
                items = [x.strip() for x in widget.get("1.0", "end").splitlines() if x.strip()]
                items = [x.replace("|", " ") for x in items]
                if kind == "times":
                    fixed = []
                    for t in items:
                        m = re.fullmatch(r"(\d{1,2})[:h.](\d{2})", t)
                        if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
                            errors.append(f"{label}: '{t}' sai. Viết dạng GIỜ:PHÚT, vd 06:30")
                        else:
                            fixed.append(f"{int(m.group(1)):02d}:{m.group(2)}")
                    items = sorted(set(fixed))
                if kind == "rules":
                    for r in items:
                        if not re.fullmatch(r".+=\s*\d+", r):
                            errors.append(f"{label}: dòng '{r}' sai. Viết dạng  cụm từ=điểm")
                if opts.get("url"):
                    bad = [u for u in items if "facebook.com" not in u and "fb.com" not in u]
                    if bad:
                        errors.append(f"{label}: không phải link Facebook: {bad[0]}")
                if not items and not opts.get("optional"):
                    errors.append(f"{label}: chưa điền.")
                values[key] = "|".join(items)
            elif kind == "bool":
                values[key] = "true" if widget.get() else "false"
            elif kind == "int":
                raw = widget.get().strip()
                if not raw.isdigit() or not (opts.get("min", 0) <= int(raw) <= opts.get("max", 10**9)):
                    errors.append(f"{label}: phải là số từ {opts.get('min', 0)} đến {opts.get('max')}.")
                values[key] = raw
            else:
                v = " ".join(widget.get().split())  # 1 dong
                if not v and not opts.get("optional"):
                    errors.append(f"{label}: chưa điền.")
                values[key] = v

        if TOOL_KIND == "monitor":
            every, mx = values.get("RUN_EVERY_MINUTES", ""), values.get("MAX_RUN_MINUTES", "")
            if every.isdigit() and mx.isdigit() and int(mx) >= int(every):
                errors.append("Thời gian tối đa mỗi lần quét phải NHỎ HƠN số phút giữa 2 lần quét.")
            if values.get("AUTO_COMMENT") == "true" and not values.get("COMMENT_TEXT"):
                errors.append("Đã bật tự bình luận nhưng chưa điền nội dung bình luận lần 1.")
            tok = values.get("TELEGRAM_TOKEN", "")
            if tok and not re.fullmatch(r"\d+:[\w-]+", tok):
                errors.append("Telegram Token sai dạng (đúng dạng: 1234567890:AAH...).")
        return values, errors

    # ---------- nut
    def save(self):
        values, errors = self.collect()
        if errors:
            messagebox.showerror("Chưa lưu được", "Sửa các chỗ sau rồi bấm Lưu lại:\n\n• " + "\n• ".join(errors))
            return
        schedule_changed = any(
            opts.get("schedule") and values[key] != self.original.get(key, "")
            for key, (_, _, _, opts) in self.widgets.items()
        )
        write_config(values)
        self.original.update(values)
        self.dirty = False

        msg = "Đã lưu cấu hình. Lần chạy sau tool sẽ dùng thông tin mới."
        if schedule_changed:
            ok, detail = self.update_schedule()
            msg += ("\n\nĐã cập nhật lịch chạy tự động." if ok else
                    "\n\n⚠ Chưa cập nhật được lịch chạy:\n" + detail +
                    "\n\nMở MO_TOOL.bat và chọn [2] để cập nhật lịch.")
        messagebox.showinfo("Đã lưu", msg)

    def update_schedule(self):
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(BASE_DIR / "setup.ps1"), "-Action", "schedule"],
                capture_output=True, text=True, timeout=120,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as error:
            return False, str(error)
        out = (result.stdout + result.stderr).strip()
        errs = [l.strip() for l in out.splitlines() if "LOI" in l]
        return result.returncode == 0 and not errs, "\n".join(errs) or out[-400:]

    def test_telegram(self):
        values, _ = self.collect()
        token, chat = values.get("TELEGRAM_TOKEN", ""), values.get("TELEGRAM_CHAT_ID", "")
        if not token or not chat:
            messagebox.showwarning("Telegram", "Điền Token và Chat ID trước.")
            return
        data = urllib.parse.urlencode({"chat_id": chat, "text": "✅ Tool Facebook: gửi thử Telegram thành công."}).encode()
        try:
            with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=15) as r:
                ok = json.loads(r.read().decode()).get("ok")
        except Exception as error:
            ok, detail = False, str(error)
        else:
            detail = ""
        if ok:
            messagebox.showinfo("Telegram", "Đã gửi tin thử. Mở Telegram để kiểm tra.")
        else:
            messagebox.showerror("Telegram", "Gửi thử thất bại. Kiểm tra lại Token, Chat ID và đã bấm Start với bot chưa.\n\n" + detail)

    def close(self):
        if self.dirty and not messagebox.askyesno("Chưa lưu", "Bạn có thay đổi chưa lưu. Vẫn đóng?"):
            return
        self.root.destroy()


def main():
    # Tool gop (dang bai + theo doi trong 1 giao dien). .py hoac .pyc (ban gui khach).
    if (BASE_DIR / "tool_gui.py").exists() or (BASE_DIR / "tool_gui.pyc").exists():
        sys.path.insert(0, str(BASE_DIR))
        import tool_gui
        return tool_gui.main()
    # Tool dang bai ban moi (nhieu tai khoan / nhom noi dung) co giao dien rieng.
    if TOOL_KIND == "upstt" and (BASE_DIR / "upstt_gui.py").exists():
        sys.path.insert(0, str(BASE_DIR))
        import upstt_gui
        return upstt_gui.main()
    if TOOL_KIND == "monitor" and (BASE_DIR / "monitor_gui.py").exists():
        sys.path.insert(0, str(BASE_DIR))
        import monitor_gui
        return monitor_gui.main()
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # chu net tren man hinh do phan giai cao
        except Exception:
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
