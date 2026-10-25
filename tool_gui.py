# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
"""Giao dien tool gop: Tai khoan > 📝 Noi dung dang (dang bai) / 🔎 Nhom theo doi (quet + binh luan).

Khung chung: gui_common.TreeConfigApp. Moi loai muc mo ta bang 1 lop Kind (tab, o nhap, chu hien thi).
"""
import shutil
import sys
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ban_quyen
import gui_common as ui
import tool_store as store
import upstt_store

LICENSE_WARN_DAYS = 7   # con <= 7 ngay -> canh bao o Tong quan + thanh trai


def post_as(s, account_id):
    """Task 003: danh tinh 'Dang bang' cua tai khoan trong kich ban ("self" = Ca nhan)."""
    return str((s.get("post_as") or {}).get(account_id) or "self")


def join_state(account_id, identity="self"):
    """Trang thai vao nhom theo danh tinh (Ca nhan: goi y nhu cu)."""
    if identity in ("", None, "self"):
        return upstt_store.join_state(account_id)
    try:
        return upstt_store.join_state(account_id, identity=identity)
    except Exception:
        return {}


class PostKind:
    """Noi dung dang bai vao nhom (fb_upstt.py), moi muc 1 lich theo gio."""
    KEY = store.POST
    ITEM_NOUN = "nội dung đăng"
    ADD_LABEL = "📝 Đăng bài"
    FOLDER_LABEL = "Đăng bài"
    CHIP_LABEL = "Đăng bài"
    ITEM_ICON = "📝"
    RESULT_KIND = "posts"          # tab Tong hop: bai dang duoc duyet / bi tu choi
    LOG_TASK_LEVEL = "item"        # moi noi dung 1 lich -> nhat ky rieng tung noi dung
    ENABLED_TITLE = "Bật đăng nội dung này"
    ENABLED_HINT = ("Bật: đến giờ đã đặt, tool tự đăng nội dung này vào các nhóm bên dưới.\n"
                    "Tắt: tạm ngừng đăng, vẫn giữ nguyên nhóm, nội dung và giờ – bật lại là chạy tiếp.")

    def __init__(self, app):
        self.app = app
        self.estimate = None
        self._grp = None   # trang thai bang nhom (cot trai man Dang bai)

    def item_tabs(self):
        # Tab dau tu dung (sections=None): man "Dang bai" 2 cot giong AutoNuoi.
        return [
            ("📝 Đăng bài", None),
            ("Kết quả tổng hợp", [("Bài của bạn ở từng nhóm", [])]),
            ("Kết quả chi tiết", [("Nhật ký từng lần đăng", [])]),
        ]

    def section_extra(self, title, parent, item):
        app = self.app
        if title == "Bài của bạn ở từng nhóm":
            app.results_tab(parent, store.find_campaign(app.data, item["id"])[0], item)
        if title == "Nhật ký từng lần đăng":
            app.details_tab(parent, store.find_campaign(app.data, item["id"])[0], item)
        if title == "Rule khi lỗi":
            app.rules_box(parent)

    # ------------------------------------------------------------ kich ban / tai khoan chay
    def scenario_tabs(self):
        # Rule khi loi dung chung ca tool -> man Cai dat (khong lap lai o tung kich ban).
        return [("📝 Đăng bài", None), ("👥 Tài khoản chạy", "accounts")]

    def scenario_section_extra(self, title, parent, s):
        if title == "Rule khi lỗi":
            self.app.rules_box(parent)

    def member_tabs(self):
        return [("🚀 Đăng ngay", None),
                ("Kết quả tổng hợp", [("Bài của bạn ở từng nhóm", [])]),
                ("Kết quả chi tiết", [("Nhật ký từng lần đăng", [])])]

    def tree_scenario_text(self, s):
        st = s["settings"]
        days = upstt_store.weekdays_text(st.get("weekdays"))
        return (f"{s['name']}   ·   {', '.join(st.get('times', [])) or 'chưa có giờ'}"
                + ("" if days == "hằng ngày" else f" ({days})"))

    def tree_member_text(self, account, item):
        return f"   ·   {', '.join(item['times']) or 'chưa có giờ'}"

    def tree_scenario_info(self, s):
        st = s["settings"]
        days = upstt_store.weekdays_text(st.get("weekdays"))
        times = ", ".join(st.get("times", [])) or "chưa có giờ"
        # the kich ban (ban thiet ke 1): "02:20 hằng ngày · 2 nhóm"
        return f"{times} {days.replace('Thứ: ', '')} · {len(st.get('groups', []))} nhóm"

    def tree_member_info(self, account, item):
        return ", ".join(item["times"]) or "chưa có giờ"

    # ================================================================ trang thai vao nhom
    # accounts/<id>/xin_vao_nhom.json (+ nhom da doc duoc) - ghi boi --join-groups / --leave-groups / --joined-groups
    STATUS_CELL = {"joined": "✓ đã vào", "pending": "⏳ chờ duyệt", "questions": "❓ câu hỏi",
                   "no_button": "⚠ chưa rõ", "unknown": "⚠ chưa rõ", "": "– chưa vào"}
    FILTERS = ["Tất cả nhóm", "Có tài khoản chưa vào", "Đã vào – chưa xác minh xong", "Đang chờ duyệt / câu hỏi",
               "Có lỗi / tạm nghỉ"]
    FILTER_CHIPS = ["Tất cả", "Có TK chưa vào", "Chưa xác minh", "Chờ duyệt", "Có lỗi"]   # nut loc (ngan)

    def join_status(self, account_id, url):
        import fb_login
        st = upstt_store.join_state(account_id)
        return st.get(fb_login.group_slug(url) or url, {}).get("status", "")

    def status_cell(self, g):
        """O trang thai 1 nhom x 1 tai khoan. Da vao = tool xac minh ngay: da xac minh (vao 1 phat dang duoc) /
        can xu ly (xac minh thay vuong: chi QTV dang, bat tra loi cau hoi...) / dang xac minh (vua vao, chua chay xong
        - vd du lieu cu truoc khi co xac minh: lan Cap nhat trang thai / luot dang toi se xac minh)."""
        st = g.get("status", "")
        if st != "joined":
            return self.STATUS_CELL.get(st, "⚠ chưa rõ")
        if g.get("verified"):
            return "✅ đã xác minh"
        return "⚠ vào – cần xử lý" if g.get("verify_note") else "⏳ đang xác minh"

    @staticmethod
    def verify_kind(g):
        """'' (chua vao) / 'ok' / 'todo' (chua xac minh) / 'bad' (can xu ly)."""
        if g.get("status") != "joined":
            return ""
        return "ok" if g.get("verified") else ("bad" if g.get("verify_note") else "todo")

    def membership_text(self, account_id, groups):
        """'7 nhóm · đã vào 5 · chờ 1' - nhom tai khoan da vao / dang xin."""
        import fb_login
        st = upstt_store.join_state(account_id)
        counts = {}
        verified = 0
        for g in groups:
            entry = st.get(fb_login.group_slug(g) or g, {})
            k = entry.get("status", "")
            counts[k] = counts.get(k, 0) + 1
            verified += self.verify_kind(entry) == "ok"
        parts = [f"đã vào {counts['joined']}" + (f" (xác minh {verified})" if counts["joined"] != verified else "")
                 if counts.get("joined") else "",
                 f"chờ {counts.get('pending', 0) + counts.get('questions', 0)}"
                 if counts.get("pending") or counts.get("questions") else "",
                 f"chưa vào {counts['']}" if counts.get("") else ""]
        return f"{len(groups)} nhóm" + "".join(f" · {p}" for p in parts if p)

    def scenario_summary(self, s):
        st = s["settings"]
        ticked = store.ticked_accounts(self.app.data, s)
        est = upstt_store.estimate_minutes(st, ticked[0]["id"]) if ticked else upstt_store.estimate_minutes(st)
        return (f"{len(s['accounts'])} tài khoản  ·  {len(st.get('groups', []))} nhóm  ·  giờ chung "
                f"{', '.join(st.get('times', [])) or 'chưa có'} ({upstt_store.weekdays_text(st.get('weekdays'))})"
                f"  ·  ~{est} phút/lượt")

    def joined_count(self, account_id, groups):
        import fb_login
        st = upstt_store.join_state(account_id)
        return sum(1 for g in groups if (st.get(fb_login.group_slug(g) or g) or {}).get("status") == "joined")

    @staticmethod
    def sent_7days(app, account, groups, kind):
        import time
        import fb_login
        sent = fb_login.load_results(app.account_dir(account)).get("sent", {})
        slugs = {fb_login.group_slug(g) or g for g in groups}
        since = time.time() - 7 * 86400
        return sum(1 for slug, entries in sent.items() if slug in slugs
                   for e in entries if e[1] == kind and e[0] >= since)

    def member_kpis(self, app, s, account, item):
        """4 o so dau man tai khoan trong kich ban: (gia tri, nhan, mau)."""
        import fb_login
        groups = item.get("groups", [])
        own = store.custom_member_times(s, account["id"])
        care = fb_login.load_care_state(app.account_dir(account))
        slugs = {fb_login.group_slug(g) or g for g in groups}
        cared = sum(1 for v in care.values() if v.get("status") in ("sent", "visible")
                    and fb_login.group_slug(v.get("url", "")) in slugs)
        joined = self.joined_count(account["id"], groups)
        return [(", ".join(item.get("times", [])) or "chưa có", "giờ đăng " + ("(riêng)" if own else "(chung)"), None),
                (f"{joined}/{len(groups)}", "nhóm đã vào", ui.GREEN if joined == len(groups) and groups else ui.AMBER),
                (self.sent_7days(app, account, groups, "post"), "bài đã đăng (7 ngày)", "#1d4ed8"),
                (cared, "bài đã chăm", None)]

    def member_columns(self, app, s, account):
        """Cot 'Gio dang' + 'Nhom da vao' trong bang Tai khoan chay."""
        times = store.member_times(app.data, s, account["id"])
        own = "  (riêng)" if store.custom_member_times(s, account["id"]) else ""
        return (", ".join(times) or "chưa có") + own, self.membership_text(account["id"], s["settings"].get("groups", []))

    def member_info(self, app, s, account):
        times = store.member_times(app.data, s, account["id"])
        own = " (giờ riêng)" if store.custom_member_times(s, account["id"]) else ""
        return (f"giờ: {', '.join(times) or 'chưa có'}{own}  ·  "
                f"{self.membership_text(account['id'], s['settings'].get('groups', []))}")

    def member_summary(self, app, s, account, item):
        return (f"Giờ đăng: {', '.join(item['times']) or 'chưa có'} "
                f"({upstt_store.weekdays_text(item.get('weekdays'))})  ·  "
                f"{self.membership_text(account['id'], item['groups'])}  ·  ~{upstt_store.estimate_minutes(item)} "
                "phút/lần.\nKhi chạy theo lịch, tool chỉ đăng vào nhóm tài khoản ĐÃ VÀO. Nội dung, nhóm, giờ chung: "
                "sửa ở kịch bản (nút ✎ bên phải); giờ riêng của tài khoản này: sửa ngay dưới đây.")

    def group_names(self, s):
        """Ten nhom (slug -> ten): luu khi them tu Tim nhom + ten tool doc duoc khi dang / cap nhat ket qua."""
        import fb_login
        names = {}
        for a in store.ticked_accounts(self.app.data, s):
            for slug, g in fb_login.load_results(self.app.account_dir(a)).get("groups", {}).items():
                if g.get("name"):
                    names[slug] = g["name"]
        for url, name in (s["settings"].get("group_names") or {}).items():
            names[fb_login.group_slug(url) or url] = name
        return names

    def usable_accounts(self, s=None):
        """Tai khoan da dang nhap: cua kich ban (neu co) truoc, roi cac tai khoan khac."""
        app = self.app
        mine = store.ticked_accounts(app.data, s) if s else []
        rest = [a for a in app.data["accounts"] if a not in mine]
        return [a for a in mine + rest if app.account_usable(a)]

    def pick_account(self, s, title):
        """Tai khoan dung Chrome de TIM nhom (chi xem): uu tien tai khoan cua kich ban; nhieu tai khoan -> hoi."""
        import tkinter as tk
        app = self.app
        choices = self.usable_accounts(s)
        if not choices:
            messagebox.showinfo(title, "Cần ít nhất 1 tài khoản ĐÃ ĐĂNG NHẬP (tab '👤 Tài khoản') – tool dùng Chrome "
                                       "của tài khoản đó để tìm.")
            return None
        if len(choices) == 1:
            return choices[0]
        win = tk.Toplevel(app.root)
        win.title(title)
        win.transient(app.root)
        win.resizable(False, False)
        frame = ttk.Frame(win, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Tìm bằng Chrome của tài khoản nào? (chỉ xem, không bấm gì)",
                  style="Field.TLabel").pack(anchor="w", pady=(0, 8))
        var = tk.StringVar(value=choices[0]["id"])
        for a in choices:
            ttk.Radiobutton(frame, text=app.account_label(a), value=a["id"], variable=var).pack(anchor="w", pady=1)
        chosen = {}
        bar = ttk.Frame(frame)
        bar.pack(fill="x", pady=(12, 0))
        ttk.Button(bar, text="Tiếp tục", style="Accent.TButton" if ui.sv_ttk else "TButton",
                   command=lambda: (chosen.update(id=var.get()), win.destroy())).pack(side="right")
        ttk.Button(bar, text="Hủy", command=win.destroy).pack(side="right", padx=(0, 8))
        win.grab_set()
        app.root.wait_window(win)
        return store.find_account(app.data, chosen["id"]) if chosen else None

    @staticmethod
    def make_table(parent, columns, height=10, pills=()):
        """Bang (Treeview) co thanh cuon. columns: [(key, tieu de, rong, gian?, canh)]. pills: cot trang thai ve
        thanh vien thuoc mau (goi tree.redraw_pills() sau khi doi du lieu)."""
        box = ttk.Frame(parent)
        tree = ttk.Treeview(box, columns=[c[0] for c in columns], show="headings", height=height,
                            selectmode="browse")
        for key, title, width, stretch, anchor in columns:
            tree.heading(key, text=title, anchor=anchor)
            tree.column(key, width=width, minwidth=min(width, 40), stretch=stretch, anchor=anchor)
        sb = ttk.Scrollbar(box, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        tree.tag_configure("warn", foreground="#b45309")
        tree.tag_configure("muted", foreground="#8a8f98")
        tree.tag_configure("picked", background="#e8f0fe")
        tree.redraw_pills = ui.pill_cells(tree, pills) if pills else (lambda: None)
        return box, tree

    # ================================================================ man "Dang bai" cua kich ban
    def build_scenario_tab(self, app, parent, tab_name, s):
        import tkinter as tk
        item = s["settings"]

        def rebuild():
            app.commit_form()
            app.mark_dirty()
            app.refresh_tree(f"scenario:{s['id']}")
            app.on_select(force=True)

        # ---- 1. NHOM SE DANG (rong het khung): danh sach chung + trang thai tung tai khoan
        gbox = ui.Box(parent, text="Nhóm sẽ đăng")   # .bh: ten + vien thuoc so nhom + nut ben phai
        gbox.add_pill(f"{len(item.get('groups', []))} nhóm")
        gbox.pack(fill="x")
        self.groups_panel(gbox, s)

        # ---- 2. Trai: Noi dung · Anh · Cham bai  |  Phai: Lich dang · Tuy chon · Khi xin vao nhom (ban thiet ke 1)
        grid = ttk.Frame(parent)
        grid.pack(fill="both", expand=True, pady=(10, 0))
        grid.columnconfigure(0, weight=1, uniform="c")
        grid.columnconfigure(1, weight=1, uniform="c")
        left = ttk.Frame(grid)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right = ttk.Frame(grid)
        right.grid(row=0, column=1, sticky="nsew")

        box = ui.Box(left, text="  ✍ Nội dung bài đăng  ", padding=(10, 6))
        box.pack(fill="x")
        app.form.add(box, item, "share_text", "multiline", "",
                     "Viết như đăng tay. Có link thì Facebook tự hiện ô xem trước. Có thể để trống nếu chỉ đăng "
                     "ảnh/video. Cùng nội dung muốn đăng nhiều giờ: thêm giờ ở 'Lịch đăng' (không cần tạo "
                     "thêm kịch bản).", {"height": 6})
        mbox = ui.Box(left, text="  🖼 Ảnh / video  ", padding=(10, 6))
        mbox.pack(fill="x", pady=(8, 0))
        self.media_box(mbox, item)
        cbox = ui.Box(left, text="  💬 Chăm bài đã duyệt  ", padding=(10, 6))
        cbox.pack(fill="x", pady=(8, 0))
        item.setdefault("care_text", "")
        app.form.add(cbox, item, "care_text", "multiline", "",
                     "Bình luận 1 lần dưới bài CỦA BẠN khi bài được duyệt (vd thông tin liên hệ). TỰ CHĂM: mỗi lần "
                     "trạng thái bài được cập nhật – bấm 🔄 Cập nhật ngay / Cập nhật toàn bộ, hoặc theo lịch 'Tự cập "
                     "nhật trạng thái' ở 🛠 Cài đặt – tool tìm bài mới được duyệt và tự chăm (mỗi bài 1 lần, bài tool "
                     "đăng trong 7 ngày). Để trống = không tự chăm. Chăm tay: nút 💬 Chăm bài ở tab Kết quả chi tiết.",
                     {"height": 2})

        lbox = ui.Box(right, text="  🕒 Lịch đăng  ", padding=(10, 6))
        lbox.pack(fill="x")
        app.form.add(lbox, item, "times", "times", "Giờ đăng mỗi ngày (giờ chung)",
                     "Mỗi dòng 1 giờ (06:30). Tài khoản thứ 2, 3… tự lùi theo 'Giãn cách' ở tab '👥 Tài khoản chạy', "
                     "hoặc đặt giờ riêng ở từng tài khoản.", {"height": 3})
        self.weekday_box(lbox, item)
        obox = ui.Box(right, text="  ⚙ Tùy chọn  ", padding=(10, 6))
        obox.pack(fill="x", pady=(8, 0))
        app.form.add(obox, item, "max_groups_per_run", "int", "Mỗi lượt đăng tối đa … nhóm (0 = hết)",
                     "Đặt số nhỏ (vd 20) để an toàn: mỗi lượt chỉ đăng một phần nhóm (ưu tiên nhóm lâu chưa đăng), "
                     "xoay vòng.", {"min": 0, "max": 1000})
        app.form.add(obox, item, "headless", "bool", "Chạy ngầm (không hiện cửa sổ Chrome)",
                     "Bật (nên bật): chạy ngầm. Tắt: hiện Chrome để xem/tìm lỗi.", {})
        self.estimate = ttk.Label(obox, text="", style="Hint.TLabel")
        self.estimate.pack(anchor="w", pady=(6, 0))
        import fb_login
        jbox = ui.Box(right, text="  Khi xin vào nhóm  ", padding=(10, 6))
        jbox.pack(fill="x", pady=(8, 0))
        item.setdefault("join_answer", "")
        item.setdefault("join_wave", True)
        app.form.add(jbox, item, "join_answer", "multiline", "Câu trả lời mẫu cho câu hỏi tham gia",
                     "Nhóm hỏi câu hỏi khi xin vào: ô chữ điền câu này (để trống = \"" + fb_login.DEFAULT_JOIN_ANSWER +
                     "\"); câu chọn 1 / chọn nhiều: tool chọn đáp án đồng ý / có, không có thì chọn đáp án đầu. "
                     "Câu hỏi xin email, số điện thoại, link… tool để trống.", {"height": 2})
        app.form.add(jbox, item, "join_wave", "bool", "Vào nhóm xong bấm 'Vẫy tay chào'",
                     "Nhóm có nút Vẫy tay chào / Xin chào (Facebook soạn sẵn) thì bấm 1 lần khi vừa vào.", {})
        self._est = (s, item)
        self.update_estimate()
        ttk.Label(right, text="🚀 Đăng ngay / xem kết quả: chọn từng tài khoản (👤) bên dưới kịch bản ở cây bên trái.",
                  style="Hint.TLabel", wraplength=420, justify="left").pack(anchor="w", pady=(8, 0))

    # ---------------------------------------------------------------- bang nhom cua kich ban
    def groups_panel(self, parent, s):
        """Thanh cong cu + bang nhom (o tick + trang thai tung tai khoan) + nut Xin vao / Roi nhom / Xoa."""
        import tkinter as tk
        app = self.app
        if isinstance(parent, ui.Box):   # nut nam tren thanh tieu de khung (ban thiet ke 1)
            parent.add_button("🔄 Cập nhật trạng thái", lambda: self.check_approved(s))
            parent.add_button("＋ Dán link", lambda: self.paste_links_dialog(s))
            parent.add_button("🔍 Tìm nhóm", lambda: self.find_groups_dialog(s))
        else:
            top = ttk.Frame(parent)
            top.pack(fill="x")
            ttk.Button(top, text="🔍  Tìm nhóm", command=lambda: self.find_groups_dialog(s)).pack(side="left")
            ttk.Button(top, text="＋  Dán link", command=lambda: self.paste_links_dialog(s)).pack(side="left",
                                                                                                padx=(6, 0))
            ttk.Button(top, text="🔄  Cập nhật trạng thái", command=lambda: self.check_approved(s)).pack(side="right")
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 4))
        all_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Tick hết (đang hiện)", variable=all_var,
                        command=lambda: tick_all(all_var.get())).pack(side="left")
        flt = tk.StringVar(value=self.FILTERS[0])
        ttk.Frame(bar, width=10).pack(side="left")
        ui.chips(bar, flt, list(zip(self.FILTERS, self.FILTER_CHIPS)), command=lambda: render(), padx=(0, 2))
        summary = ttk.Label(bar, text="", style="Hint.TLabel")
        summary.pack(side="right")

        accounts = store.ticked_accounts(app.data, s)
        cols = [("pick", "", 34, False, "center"), ("name", "Nhóm", 260, True, "w")]
        cols += [(f"a{i}", app.account_label(a, 16), 150, False, "center") for i, a in enumerate(accounts)]
        if not accounts:
            cols.append(("none", "Tài khoản", 200, False, "center"))
        # bang vua so nhom (ban thiet ke 1): khong de khoang trong lon khi it nhom
        box, tree = self.make_table(parent, cols, height=max(3, min(10, len(s["settings"].get("groups", [])))),
                                    pills=[f"a{i}" for i in range(len(accounts))])
        box.pack(fill="x")
        act = ttk.Frame(parent)
        act.pack(fill="x", pady=(8, 0))
        count = ttk.Label(act, text="", style="Field.TLabel")
        count.pack(side="left")
        ttk.Button(act, text="🗑  Xóa khỏi kịch bản", command=lambda: self.remove_groups(s, picked_urls())).pack(
            side="right")
        leave_btn = ttk.Button(act, text="🚪  Rời nhóm", command=lambda: self.scope_action(s, "leave", picked_urls()))
        leave_btn.pack(side="right", padx=(0, 6))
        join_btn = ttk.Button(act, text="🙋  Xin vào", command=lambda: self.scope_action(s, "join", picked_urls()))
        join_btn.pack(side="right", padx=(0, 6))
        accounts = store.ticked_accounts(app.data, s)
        if accounts and all(post_as(s, a["id"]) != "self" for a in accounts):   # cau PM 7
            join_btn.state(["disabled"])
            leave_btn.state(["disabled"])
            ttk.Label(act, text="Xin vào / rời nhóm bằng Page: làm sau", style="Hint.TLabel").pack(side="right",
                                                                                                padx=(0, 8))
        issues = ui.fit_wrap(ttk.Label(parent, text="", style="Warn.TLabel", justify="left"), parent)
        issues.pack_configure(pady=(6, 0))
        rule = ("Đăng theo lịch: mỗi tài khoản chỉ đăng nhóm nó ĐÃ VÀO." if s["kind"] == "post" else
                "Nhóm riêng tư chưa vào thì quét không thấy bài.")
        ui.fit_wrap(ttk.Label(parent, text=f"Bấm dòng để tick · {rule} Xóa khỏi kịch bản không rời nhóm trên "
                                           "Facebook. ✅ đã xác minh = dùng được ngay · ⚠ cần xử lý · ⏳ đang xác minh.",
                              style="Hint.TLabel", justify="left"), parent).pack_configure(pady=(6, 0))
        picked, rows, why = set(), {}, []
        if not hasattr(self, "_picked"):
            self._picked = {}
        picked |= self._picked.get(s["id"], set())   # giu o tick khi ve lai (vd sau Cap nhat trang thai)
        self._picked[s["id"]] = picked

        def picked_urls():
            return [u for u in s["settings"].get("groups", []) if u in picked]

        def cells(url, notes, names, states):
            import fb_login
            slug = fb_login.group_slug(url) or url
            name = names.get(slug) or slug
            vals, problem, kinds = [], False, set()
            for a in accounts:
                entry = states[a["id"]].get(slug, {})
                st = entry.get("status", "")
                kinds.add(st)
                kinds.add("v_" + self.verify_kind(entry))
                text = self.status_cell(entry)
                if entry.get("verify_note") and not entry.get("verified"):
                    why.append(f"{name} – {a['name']}: {entry['verify_note']}")
                if notes[a["id"]].get(slug):
                    text = "⚠ tạm nghỉ"   # nhom dang loi o tai khoan nay (chi tiet: Ket qua tong hop)
                    problem = True
                vals.append(text)
            if not accounts:
                vals.append("chưa tick tài khoản")
            return name, vals, problem, kinds

        def render():
            import fb_login
            tree.delete(*tree.get_children())
            rows.clear()
            groups = s["settings"].get("groups", [])
            names = self.group_names(s)
            states = {a["id"]: upstt_store.join_state(a["id"]) for a in accounts}
            notes = {}
            for a in accounts:
                c = store.member_campaign(app.data, s, a["id"])
                try:
                    ns = store.pause_notes(a, c) if c else []
                except Exception:
                    ns = []
                notes[a["id"]] = {str(n["key"]).split("groups/")[-1]: n.get("text", "") for n in ns if n.get("key")}
            want = flt.get()
            shown = 0
            why.clear()
            for url in groups:
                name, vals, problem, kinds = cells(url, notes, names, states)
                st_kinds = {k for k in kinds if not k.startswith("v_")}
                if want == self.FILTERS[1] and not (st_kinds - {"joined"}):
                    continue
                if want == self.FILTERS[2] and not kinds & {"v_todo", "v_bad"}:
                    continue
                if want == self.FILTERS[3] and not kinds & {"pending", "questions"}:
                    continue
                if want == self.FILTERS[4] and not (problem or kinds & {"no_button", "unknown", "v_bad"}):
                    continue
                tags = (["picked"] if url in picked else []) + (["warn"] if problem else [])
                iid = tree.insert("", "end", values=["☑" if url in picked else "☐", name, *vals], tags=tags)
                rows[iid] = url
                shown += 1
            picked.intersection_update(groups)
            issues.configure(text=("⚠ Cần xử lý:\n" + "\n".join(f"  • {w}" for w in why[:6])
                                   + (f"\n  … và {len(why) - 6} mục khác" if len(why) > 6 else "")) if why else "")
            total = len(groups)
            summary.configure(text=f"Đang hiện {shown}/{total} nhóm" if shown != total else f"{total} nhóm")
            if not groups:
                tree.insert("", "end", values=["", "Chưa có nhóm – bấm 🔍 Tìm nhóm hoặc ＋ Dán link", *[""] * (len(cols) - 2)],
                            tags=["muted"])
            update_count()
            tree.redraw_pills()

        def update_count():
            n = len(picked)
            count.configure(text=f"Đã tick {n} nhóm" if n else "Chưa tick nhóm nào")

        def toggle(iid):
            url = rows.get(iid)
            if not url:
                return
            if url in picked:
                picked.discard(url)
            else:
                picked.add(url)
            on = url in picked
            vals = list(tree.item(iid, "values"))
            vals[0] = "☑" if on else "☐"
            tags = [t for t in tree.item(iid, "tags") if t != "picked"] + (["picked"] if on else [])
            tree.item(iid, values=vals, tags=tags)
            update_count()

        def tick_all(value):
            for iid, url in rows.items():
                if (url in picked) != value:
                    toggle(iid)

        def on_click(event):
            iid = tree.identify_row(event.y)
            if iid and tree.identify_region(event.x, event.y) == "cell":
                toggle(iid)

        def on_double(event):
            import webbrowser
            url = rows.get(tree.identify_row(event.y))
            if url:
                webbrowser.open(url)
        tree.bind("<ButtonRelease-1>", on_click)
        tree.bind("<Double-1>", on_double)
        self._groups_render = render
        render()

    def refresh_groups(self):
        render = getattr(self, "_groups_render", None)
        try:
            if render:
                render()
        except Exception:
            pass

    # ---------------------------------------------------------------- xin vao / roi nhom: chon tai khoan
    def scope_action(self, s, action, urls):
        """Man 'Xin vao N nhom' / 'Roi N nhom': tat ca tai khoan cua kich ban hoac chi tai khoan chi dinh."""
        import tkinter as tk
        import fb_login
        app = self.app
        joining = action == "join"
        verb, title = ("xin vào", "Xin vào") if joining else ("rời", "Rời")
        if not urls:
            messagebox.showinfo(f"{title} nhóm", "Tick ít nhất 1 nhóm trong bảng (bấm vào dòng nhóm).")
            return
        accounts = store.ticked_accounts(app.data, s)
        if not accounts:
            messagebox.showinfo(f"{title} nhóm", "Kịch bản chưa tick tài khoản nào (tab '👥 Tài khoản chạy').")
            return
        # Cau PM 7: tai khoan dang bang Page -> khong xin vao / roi bang Page (lam sau)
        as_page = [a for a in accounts if post_as(s, a["id"]) != "self"]
        accounts = [a for a in accounts if a not in as_page]
        if not accounts:
            messagebox.showinfo(f"{title} nhóm", "Các tài khoản của kịch bản đều ĐĂNG BẰNG PAGE.\n\n"
                                                 f"{title} nhóm bằng Page: làm sau – hiện tool chỉ xin vào / rời "
                                                 "bằng Cá nhân. Vào nhóm bằng Page: tự làm tay trên Facebook.")
            return

        def todo(a):
            want = ("joined", "pending") if not joining else None
            out = []
            for u in urls:
                st = self.join_status(a["id"], u)
                if joining and st != "joined":   # dang cho duyet: mo lai, con cau hoi chua tra loi thi tra loi
                    out.append(u)
                elif not joining and st in want:
                    out.append(u)
            return out

        win = tk.Toplevel(app.root)
        win.title(f"{title} {len(urls)} nhóm")
        win.transient(app.root)
        win.resizable(False, False)
        frame = ttk.Frame(win, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"{'🙋' if joining else '🚪'}  {title} {len(urls)} nhóm đã tick",
                  style="Title.TLabel").pack(anchor="w", pady=(0, 10))
        mode = tk.StringVar(value="all")
        names = ", ".join(a["name"] for a in accounts)
        ttk.Radiobutton(frame, text="Tất cả tài khoản của kịch bản", value="all", variable=mode,
                        command=lambda: refresh()).pack(anchor="w")
        ttk.Label(frame, text=names, style="Hint.TLabel", wraplength=440).pack(anchor="w", padx=(24, 0))
        ttk.Radiobutton(frame, text="Chỉ tài khoản chỉ định", value="some", variable=mode,
                        command=lambda: refresh()).pack(anchor="w", pady=(8, 0))
        checks = []
        cbox = ttk.Frame(frame)
        cbox.pack(anchor="w", padx=(24, 0), pady=(2, 0))
        for a in accounts:
            usable = app.account_usable(a)
            var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(cbox, text=app.account_label(a) + ("" if usable else "   (chưa đăng nhập)"),
                                 variable=var, command=lambda: refresh())
            cb.pack(anchor="w", pady=1)
            checks.append((var, a, cb, usable))
        preview = ttk.Label(frame, text="", wraplength=440, justify="left")
        preview.pack(anchor="w", fill="x", pady=(12, 4))
        rule = (f"Mỗi tài khoản tối đa {fb_login.JOIN_PER_DAY} nhóm/ngày, cách nhau {fb_login.JOIN_WAIT_SECONDS} giây. "
                "Nhóm có câu hỏi: tool tự trả lời theo 'Câu trả lời mẫu' của kịch bản (câu hỏi xin email / số điện "
                "thoại… để trống). Nhóm đang chờ duyệt mà chưa trả lời câu hỏi: tool mở lại trả lời." if joining else
                f"Cách nhau {fb_login.LEAVE_WAIT_SECONDS} giây. Nhóm đang chờ duyệt: tool hủy yêu cầu. Tài khoản là "
                "quản trị viên nhóm: tool KHÔNG tự rời. Nhóm vẫn nằm trong danh sách của kịch bản.")
        ttk.Label(frame, text=rule, style="Hint.TLabel", wraplength=440, justify="left").pack(anchor="w")
        bar = ttk.Frame(frame)
        bar.pack(fill="x", pady=(14, 0))
        go = ttk.Button(bar, text=title, style="Accent.TButton" if ui.sv_ttk else "TButton")
        go.pack(side="right")
        ttk.Button(bar, text="Hủy", command=win.destroy).pack(side="right", padx=(0, 8))

        def chosen():
            if mode.get() == "all":
                return [a for _v, a, _c, usable in checks if usable]
            return [a for v, a, _c, usable in checks if v.get() and usable]

        def refresh():
            for var, a, cb, usable in checks:
                cb.state(["!disabled"] if mode.get() == "some" and usable else ["disabled"])
            picked = chosen()
            lines = []
            for a in picked:
                n = len(todo(a))
                lines.append(f"• {a['name']}: " + (f"{verb} {n} nhóm" if n else
                                                   ("đã vào / đã xin hết" if joining else "không ở nhóm nào trong số này")))
            skipped = [a["name"] for _v, a, _c, usable in checks if not usable]
            preview.configure(text=("Sẽ làm:\n" + "\n".join(lines)) if lines else "Chưa chọn tài khoản nào.")
            if as_page:
                preview.configure(text=preview.cget("text") + "\nBỏ qua (đăng bằng Page – xin vào / rời bằng Page: làm "
                                  "sau): " + ", ".join(a["name"] for a in as_page))
            if skipped and mode.get() == "all":
                preview.configure(text=preview.cget("text") + "\nBỏ qua (chưa đăng nhập): " + ", ".join(skipped))

        def run():
            jobs = []
            for a in chosen():
                work = todo(a)
                if work:
                    jobs.append((a, ["--join-groups" if joining else "--leave-groups", "--urls", "|".join(work)]))
            if not jobs:
                messagebox.showinfo(f"{title} nhóm", "Không có việc gì để làm với lựa chọn này.", parent=win)
                return
            win.destroy()
            self.run_accounts(jobs, f"{title} nhóm", done=self.refresh_groups)
            app.flash(f"{'🙋' if joining else '🚪'} Bắt đầu {verb} nhóm bằng {len(jobs)} tài khoản (chạy ngầm, xem tiến "
                      "độ ở thanh dưới cùng).")
        go.configure(command=run)
        refresh()
        win.grab_set()

    def remove_groups(self, s, urls):
        """Xoa khoi kich ban: chi bo nhom khoi danh sach (khong roi nhom tren Facebook)."""
        app = self.app
        if not urls:
            messagebox.showinfo("Xóa khỏi kịch bản", "Tick ít nhất 1 nhóm trong bảng (bấm vào dòng nhóm).")
            return
        if not messagebox.askyesno(
                "Xóa khỏi kịch bản",
                f"Xóa {len(urls)} nhóm khỏi kịch bản '{s['name']}'?\n\nCác tài khoản sẽ thôi đăng vào các nhóm này "
                "nhưng VẪN Ở TRONG NHÓM trên Facebook. Muốn rời hẳn thì bấm 'Rời nhóm' trước rồi mới xóa."):
            return
        app.commit_form()
        gone = set(urls)
        s["settings"]["groups"] = [u for u in s["settings"].get("groups", []) if u not in gone]
        for u in gone:
            (s["settings"].get("group_names") or {}).pop(u, None)
        self._picked.get(s["id"], set()).difference_update(gone)
        app.mark_dirty()
        if app.save(quiet=True):
            app.flash(f"Đã xóa {len(urls)} nhóm khỏi kịch bản.")
        self.refresh_groups()
        self.update_estimate()

    def check_approved(self, s):
        """'Cap nhat trang thai': doc nhom tung tai khoan dang o (chi xem) -> cho duyet thanh da vao, nhom da roi."""
        accounts = [a for a in store.ticked_accounts(self.app.data, s) if self.app.account_usable(a)]
        if not accounts:
            messagebox.showinfo("Cập nhật trạng thái", "Kịch bản chưa có tài khoản nào đã đăng nhập.")
            return
        urls = "|".join(s["settings"].get("groups", []))   # nhom kich ban da vao ma chua xac minh -> xac minh luon
        self.run_accounts([(a, ["--joined-groups"] + (["--urls", urls] if urls else [])
                            + ([] if post_as(s, a["id"]) == "self" else ["--identity", post_as(s, a["id"])]))
                           for a in accounts], "Cập nhật trạng thái", done=self.refresh_groups)

    # ---------------------------------------------------------------- chay lan luot tung tai khoan
    def run_accounts(self, jobs, title, done=None):
        """Chay lan luot (moi tai khoan 1 Chrome, khong mo nhieu Chrome cung luc): jobs = [(tai khoan, [tham so])].

        Tien do doc tu file tien do cua tai khoan dang chay, hien o thanh trang thai.
        """
        import subprocess
        app = self.app
        jobs = list(jobs)
        results = []

        def start_next():
            if not jobs:
                text = " · ".join(results)
                app.flash(f"✅ {title} xong: {text}" if text else f"✅ {title} xong.")
                if done:
                    done()
                app.refresh_tree_keep()
                return
            account, extra = jobs.pop(0)
            acc_dir = app.account_dir(account)
            try:
                (acc_dir / "kiem_tra_tien_do.json").unlink()
            except OSError:
                pass
            proc = subprocess.Popen([app.python, str(app.SCRIPT), *extra, "--account", account["id"]],
                                    cwd=app.base_dir, creationflags=ui.NO_WINDOW,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            def poll():
                if proc.poll() is None:
                    p = ui.fb_login_progress(acc_dir)
                    left = f" (còn {len(jobs)} tài khoản)" if jobs else ""
                    app.status.configure(text=f"⏳ {title} – {account['name']}: {p.get('text') or 'đang chạy…'}{left}")
                    app.root.after(1500, poll)
                    return
                p = ui.fb_login_progress(acc_dir)   # doc SAU khi tien trinh xong (tranh doc tien do cu)
                results.append(f"{account['name']}: {p.get('text') or ('xong' if proc.returncode == 0 else 'lỗi')}")
                start_next()
            poll()
        start_next()

    # ================================================================ man tai khoan trong kich ban: Dang ngay
    def build_member_tab(self, app, parent, tab_name, account, item, action=None,
                         preselect=lambda st: st == "joined"):
        """Bang nhom cua kich ban + trang thai cua tai khoan nay + nut chay ngay. action = (nhan nut, ham(urls), loi
        nhac) - mac dinh 'Dang ngay' (theo doi nhom dung 'Quet ngay'). preselect(trang thai) -> tick san."""
        import tkinter as tk
        import fb_login
        label, run_now, hint = action or (
            "🚀  Đăng ngay", lambda urls: self.post_now(account, item, urls),
            f"“Đăng ngay” đăng liền vào các nhóm ĐÃ TICK bằng tài khoản '{account['name']}'. "
            "Lịch tự động vẫn chạy theo giờ đăng của kịch bản. Thêm / bớt nhóm: sửa ở kịch bản.")
        box = ui.Box(parent, text=f"  Nhóm của kịch bản – trạng thái của '{account['name']}'  ",
                             padding=(12, 8))
        box.pack(fill="x")
        bar = ttk.Frame(box)
        bar.pack(fill="x", pady=(0, 6))
        all_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Tick hết", variable=all_var, command=lambda: tick_all(all_var.get())).pack(side="left")
        ttk.Label(bar, text="Nhóm chờ duyệt / câu hỏi" + (" / chưa vào" if not preselect("") else "") +
                  " mặc định không tick.", style="Hint.TLabel").pack(side="left", padx=(12, 0))
        rk = app.kind(item).RESULT_KIND or "posts"
        tbox, tree = self.make_table(box, [("pick", "", 34, False, "center"), ("name", "Nhóm", 250, True, "w"),
                                           ("state", "Trạng thái", 140, False, "center"),
                                           ("mine", "Bài của bạn" if rk == "posts" else "Bình luận của bạn", 140,
                                            False, "w"),
                                           ("todo", "Bạn nên làm", 160, False, "w")],
                                     height=max(3, min(12, len(item.get("groups", [])))), pills=["state"])
        tbox.pack(fill="x")
        s, _aid = store.scenario_of(app.data, item["id"])
        names = self.group_names(s) if s else {}
        states = upstt_store.join_state(account["id"])
        # Ket qua tung nhom (giong tab Ket qua tong hop): bai / binh luan cua ban + viec nen lam
        reports = {}
        try:
            notes = store.pause_notes(account, item)
            cstats = app.comment_stats(account, item) if rk == "comments" else None
            for r in ui.result_rows(app.account_dir(account), item.get("groups", []), rk):
                _lv, mine, _status, todo, _note = app.group_report(r, notes, cstats, rk)
                reports[r["url"]] = (" · ".join(x for x in str(mine).splitlines() if x), str(todo).replace("\n", " "))
        except Exception:
            reports = {}
        picked, rows = set(), {}
        for url in item.get("groups", []):
            slug = fb_login.group_slug(url) or url
            st = states.get(slug, {}).get("status", "")
            on = preselect(st)
            if on:
                picked.add(url)
            mine, todo = reports.get(url, ("–", ""))
            iid = tree.insert("", "end", values=["☑" if on else "☐", names.get(slug) or slug,
                                                 self.status_cell(states.get(slug, {})), mine, todo],
                              tags=(["picked"] if on else []) + ([] if st in ("joined", "") else ["warn"]))
            rows[iid] = url
        if not rows:
            tree.insert("", "end", values=["", "Kịch bản chưa có nhóm", "", "", ""], tags=["muted"])
        run = ttk.Frame(parent)
        run.pack(fill="x", pady=(10, 0))
        count = ttk.Label(run, text="", style="Field.TLabel")
        count.pack(side="left")
        ttk.Button(run, text=label, style="Accent.TButton" if ui.sv_ttk else "TButton",
                   command=lambda: run_now([u for u in item.get("groups", []) if u in picked])).pack(side="right")
        ttk.Label(parent, text=hint, style="Hint.TLabel", wraplength=700, justify="left").pack(anchor="w", pady=(6, 0))

        def update_count():
            count.configure(text=f"Đã tick {len(picked)} nhóm")

        def toggle(iid):
            url = rows.get(iid)
            if not url:
                return
            picked.symmetric_difference_update({url})
            on = url in picked
            vals = list(tree.item(iid, "values"))
            vals[0] = "☑" if on else "☐"
            tree.item(iid, values=vals, tags=[t for t in tree.item(iid, "tags") if t != "picked"] +
                      (["picked"] if on else []))
            update_count()

        def tick_all(value):
            for iid, url in rows.items():
                if (url in picked) != value:
                    toggle(iid)

        tree.bind("<ButtonRelease-1>", lambda e: toggle(tree.identify_row(e.y))
                  if tree.identify_region(e.x, e.y) == "cell" else None)
        update_count()

    def paste_links_dialog(self, s):
        import tkinter as tk
        app = self.app
        item = s["settings"]
        win = tk.Toplevel(app.root)
        win.title("Dán link nhóm")
        win.geometry("600x380")
        win.transient(app.root)
        frame = ttk.Frame(win, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Dán link nhóm, mỗi dòng 1 nhóm:", style="Field.TLabel").pack(anchor="w")
        bf, box = ui.text_box(frame, 12, wrap="none")
        bf.pack(fill="both", expand=True, pady=(4, 8))

        def add():
            urls = [x.strip() for x in box.get("1.0", "end").splitlines()
                    if x.strip() and ("facebook.com" in x or "fb.com" in x)]
            have = set(item.get("groups", []))
            added = [u for u in dict.fromkeys(urls) if u not in have]
            item.setdefault("groups", []).extend(added)
            win.destroy()
            if added:
                app.mark_dirty()
                app.save(quiet=True)
            self.refresh_groups()
            self.update_estimate()
            app.flash(f"Đã thêm {len(added)} nhóm vào kịch bản. Tick nhóm → 🙋 Xin vào để các tài khoản vào nhóm.")
        ttk.Button(frame, text="Thêm vào kịch bản", style="Accent.TButton" if ui.sv_ttk else "TButton",
                   command=add).pack(side="right")
        ttk.Button(frame, text="Đóng", command=win.destroy).pack(side="right", padx=8)
        win.grab_set()

    def post_now(self, account, item, urls):
        import subprocess
        app = self.app
        app.commit_form()
        if not urls:
            messagebox.showinfo("Đăng ngay", "Tick chọn ít nhất 1 nhóm.")
            return
        if not app.account_usable(account):
            messagebox.showwarning("Đăng ngay", f"Tài khoản '{account['name']}' chưa đăng nhập.")
            return
        if not (item.get("share_text") or "").strip() and not upstt_store.media_all(item):
            messagebox.showwarning("Đăng ngay", "Kịch bản chưa có nội dung và cũng chưa có ảnh/video để đăng.")
            return
        if app.has_changes() and not app.save(quiet=True):
            return
        if not messagebox.askyesno("Đăng ngay",
                                   f"Đăng liền nội dung '{item['name']}' vào {len(urls)} nhóm đã tick, "
                                   f"bằng tài khoản '{account['name']}'?\n\nXem tiến trình ở tab 'Kết quả chi tiết'."):
            return
        cmd = [app.python, str(app.SCRIPT), "--once", "--campaign", item["id"], "--now", "--only", "|".join(urls)]
        subprocess.Popen(cmd, cwd=app.base_dir, creationflags=ui.NO_WINDOW,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        app.flash(f"🚀 Đang đăng vào {len(urls)} nhóm… xem tab 'Kết quả chi tiết'.")

    def weekday_box(self, parent, item, verb="đăng"):
        """Chon thu trong tuan duoc dang / quet (bo chon het = hang ngay)."""
        import tkinter as tk
        ttk.Label(parent, text=f"{verb.capitalize()} vào các thứ", style="Field.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Label(parent, text=f"Bỏ chọn hết = {verb} hằng ngày.", style="Hint.TLabel").pack(anchor="w")
        row = ttk.Frame(parent)
        row.pack(anchor="w", pady=(4, 8))
        chosen = set(item.get("weekdays") or [])
        variables = []

        def update(*_a):
            item["weekdays"] = sorted(i for i, v in variables if v.get())
            self.app.mark_dirty()

        for i, name in enumerate(upstt_store.WEEKDAY_NAMES):   # nut nho (.days span): T2 … CN, chon = to xanh
            var = tk.BooleanVar(value=i in chosen)
            variables.append((i, var))
            btn = ui.chip_button(row, tk.Checkbutton, text=name, variable=var)
            btn.configure(padx=8, pady=2, command=lambda b=btn, v=var: (ui.chip_paint(b, v.get()), update()))
            btn.master.pack(side="left", padx=(0, 4))
            ui.chip_paint(btn, var.get())

    # ================================================================ Tim nhom: chi tim va THEM vao kich ban
    def find_groups_dialog(self, s):
        import json
        import subprocess
        import tkinter as tk
        import fb_login
        app = self.app
        account = self.pick_account(s, "Tìm nhóm")
        if not account:
            return
        acc_dir = app.account_dir(account)
        item = s["settings"]
        win = tk.Toplevel(app.root)
        win.title(f"Tìm nhóm cho kịch bản '{s['name']}'  ·  tìm bằng '{account['name']}'")
        win.geometry("980x760")
        win.minsize(820, 560)
        win.transient(app.root)
        frame = ttk.Frame(win, padding=14)
        frame.pack(fill="both", expand=True)

        # ---- bo loc
        filt = ui.Box(frame, text="  Tìm theo  ", padding=(10, 6))
        filt.pack(fill="x")
        r1 = ttk.Frame(filt)
        r1.pack(fill="x")
        ttk.Label(r1, text="Từ khoá:", width=12).pack(side="left")
        kw_var = tk.StringVar(value=s.get("name", ""))
        ttk.Entry(r1, textvariable=kw_var).pack(side="left", fill="x", expand=True)
        ttk.Label(r1, text="nhiều từ khoá cách nhau bằng |", style="Hint.TLabel").pack(side="left", padx=(8, 0))
        r2 = ttk.Frame(filt)
        r2.pack(fill="x", pady=(6, 0))
        ttk.Label(r2, text="Thành viên từ:", width=12).pack(side="left")
        min_var = tk.StringVar(value="1000")
        ui.no_wheel(ui.NumBox(r2, from_=0, to=5_000_000, increment=1000, textvariable=min_var, width=9)).pack(side="left")
        ttk.Label(r2, text="đến:").pack(side="left", padx=(6, 4))
        max_var = tk.StringVar(value="0")
        ui.no_wheel(ui.NumBox(r2, from_=0, to=9_000_000, increment=1000, textvariable=max_var, width=9)).pack(side="left")
        ttk.Label(r2, text="(0 = không giới hạn)", style="Hint.TLabel").pack(side="left", padx=(4, 16))
        ttk.Label(r2, text="Tối thiểu:").pack(side="left")
        act_var = tk.StringVar(value="0")
        ui.no_wheel(ui.NumBox(r2, from_=0, to=1000, textvariable=act_var, width=5)).pack(side="left", padx=(4, 2))
        ttk.Label(r2, text="bài/ngày").pack(side="left")
        r3 = ttk.Frame(filt)
        r3.pack(fill="x", pady=(6, 0))
        ttk.Label(r3, text="Loại nhóm:", width=12).pack(side="left")
        type_var = tk.StringVar(value="all")
        for val, lbl in (("all", "Tất cả"), ("public", "Công khai"), ("private", "Riêng tư")):
            ttk.Radiobutton(r3, text=lbl, value=val, variable=type_var).pack(side="left", padx=(0, 8))
        ttk.Label(r3, text="   Mỗi từ khoá tối đa:").pack(side="left")
        per_var = tk.StringVar(value="30")
        ui.no_wheel(ui.NumBox(r3, from_=1, to=100, textvariable=per_var, width=5)).pack(side="left", padx=(4, 2))
        ttk.Label(r3, text="nhóm").pack(side="left")
        r4 = ttk.Frame(filt)
        r4.pack(fill="x", pady=(6, 0))
        ttk.Label(r4, text="Bỏ nhóm có tên:", width=12).pack(side="left")
        excl_var = tk.StringVar(value="")
        ttk.Entry(r4, textvariable=excl_var, width=30).pack(side="left")
        ttk.Label(r4, text="vd: mua bán|thanh lý", style="Hint.TLabel").pack(side="left", padx=(8, 16))
        ttk.Label(r4, text="Sắp xếp:").pack(side="left")
        sorts = [("activity", "Nhiều bài/ngày"), ("lively", "Sôi nổi"), ("members", "Nhiều thành viên")]
        sort_var = tk.StringVar(value=sorts[0][1])
        ttk.Combobox(r4, values=[x[1] for x in sorts], textvariable=sort_var, state="readonly", width=16).pack(
            side="left", padx=(4, 12))
        find_btn = ttk.Button(r4, text="🔍  Tìm", style="Accent.TButton" if ui.sv_ttk else "TButton")
        find_btn.pack(side="right")
        ttk.Label(filt, text="Nhiều bài/ngày = đông người đăng (bài dễ trôi) · Sôi nổi = bài/ngày so với số thành viên "
                             "(nhóm vừa phải mà nhiều bài, người đọc thật nhiều) · Nhóm từ 1.000 thành viên và ≥ 3 "
                             "bài/ngày thường đáng đăng.", style="Hint.TLabel", wraplength=900).pack(anchor="w",
                                                                                                   pady=(6, 0))
        status = ttk.Label(frame, text="Nhập từ khoá rồi bấm 🔍 Tìm (tool mở Facebook chạy ngầm, chỉ xem).",
                           style="Hint.TLabel")
        status.pack(anchor="w", pady=(8, 4))

        # ---- thanh duoi (ghim day cua so)
        bottom = ttk.Frame(frame)
        bottom.pack(side="bottom", fill="x", pady=(8, 0))
        count = ttk.Label(bottom, text="", style="Field.TLabel")
        count.pack(side="left")
        ttk.Button(bottom, text="Tick 10 nhóm đầu", command=lambda: tick_first(10)).pack(side="left", padx=(12, 0))
        ttk.Button(bottom, text="Bỏ tick", command=lambda: tick_first(0)).pack(side="left", padx=(6, 0))
        add_btn = ttk.Button(bottom, text="", style="Accent.TButton" if ui.sv_ttk else "TButton")
        add_btn.pack(side="right")
        ttk.Button(bottom, text="Đóng", command=win.destroy).pack(side="right", padx=(0, 8))

        # ---- ket qua
        cols = [("pick", "", 34, False, "center"), ("name", "Nhóm", 300, True, "w"),
                ("members", "Thành viên", 90, False, "center"), ("privacy", "Loại", 80, False, "center"),
                ("activity", "Bài/ngày", 70, False, "center"), ("lively", "Sôi nổi", 70, False, "center"),
                ("keyword", "Từ khoá", 120, False, "w")]
        tbox, tree = self.make_table(frame, cols, height=14)
        tbox.pack(fill="both", expand=True)
        state = {"groups": [], "rows": {}, "picked": set(), "sort": None}

        def have():
            return {fb_login.group_slug(u) or u for u in item.get("groups", [])}

        def update_count():
            n = len(state["picked"])
            count.configure(text=f"Đã tick {n} nhóm")
            add_btn.configure(text=f"➕  Thêm {n} nhóm vào kịch bản" if n else "➕  Thêm vào kịch bản")

        def render():
            tree.delete(*tree.get_children())
            state["rows"].clear()
            already = have()
            for g in state["groups"]:
                inside = g["slug"] in already
                on = g["url"] in state["picked"] and not inside
                iid = tree.insert("", "end", values=[
                    "✓" if inside else ("☑" if on else "☐"),
                    g["name"] + ("   (đã có trong kịch bản)" if inside else "")
                    + ("   · bạn đã tham gia" if g.get("joined") and not inside else ""),
                    g.get("members", "?"), g.get("privacy", "?"), g.get("activity") or "–",
                    g.get("lively", "") or "–", g.get("keyword", "")],
                    tags=["muted"] if inside else (["picked"] if on else []))
                state["rows"][iid] = g
            update_count()

        def toggle(iid):
            g = state["rows"].get(iid)
            if not g or g["slug"] in have():
                return
            state["picked"].symmetric_difference_update({g["url"]})
            render_keep(iid)

        def render_keep(iid):
            g = state["rows"][iid]
            on = g["url"] in state["picked"]
            vals = list(tree.item(iid, "values"))
            vals[0] = "☑" if on else "☐"
            tree.item(iid, values=vals, tags=["picked"] if on else [])
            update_count()

        def tick_first(n):
            already = have()
            state["picked"] = {g["url"] for g in [x for x in state["groups"] if x["slug"] not in already][:n]}
            render()

        def sort_by(key):
            num = {"members": "members_num", "activity": "activity_num", "lively": "lively"}.get(key)
            rev = state["sort"] != key
            state["sort"] = key if rev else None
            state["groups"].sort(key=lambda g: (g.get(num) or 0) if num else str(g.get(key, "")).lower(), reverse=rev)
            render()
        for key, *_r in cols[1:]:
            tree.heading(key, command=lambda k=key: sort_by(k))

        def poll(proc):
            if not win.winfo_exists():
                return
            if proc.poll() is None:
                p = ui.fb_login_progress(acc_dir)
                status.configure(text="⏳ " + (p.get("text") or "Đang tìm…"))
                win.after(700, lambda: poll(proc))
                return
            p = ui.fb_login_progress(acc_dir)   # doc SAU khi tien trinh xong (tranh doc tien do cu)
            find_btn.state(["!disabled"])
            if p.get("ok", True) and p.get("done"):
                try:
                    state["groups"] = json.loads((acc_dir / "tim_nhom.json").read_text(encoding="utf-8"))
                except Exception:
                    state["groups"] = []
                state["picked"].clear()
                already = have()
                new = sum(1 for g in state["groups"] if g["slug"] not in already)
                status.configure(text=f"Tìm được {len(state['groups'])} nhóm ({new} nhóm chưa có trong kịch bản). "
                                      "Bấm vào dòng để tick, bấm tiêu đề cột để sắp xếp.")
                render()
            else:
                status.configure(text="⚠ " + (p.get("text") or "Tìm nhóm lỗi."))

        def do_find():
            kws = [x.strip() for x in kw_var.get().split("|") if x.strip()]
            if not kws:
                messagebox.showinfo("Tìm nhóm", "Nhập ít nhất 1 từ khoá.", parent=win)
                return
            find_btn.state(["disabled"])
            status.configure(text="⏳ Đang mở Facebook để tìm nhóm…")
            sort_key = next(k for k, label in sorts if label == sort_var.get())
            try:
                (acc_dir / "kiem_tra_tien_do.json").unlink()
            except OSError:
                pass
            cmd = [app.python, str(app.SCRIPT), "--find-groups", "--account", account["id"],
                   "--keywords", "|".join(kws), "--min-members", (min_var.get().strip() or "0"),
                   "--max-members", (max_var.get().strip() or "0"),
                   "--min-activity", (act_var.get().strip() or "0"),
                   "--per-keyword", (per_var.get().strip() or "30"),
                   "--group-type", type_var.get(), "--sort", sort_key, "--exclude", excl_var.get().strip()]
            proc = subprocess.Popen(cmd, cwd=app.base_dir, creationflags=ui.NO_WINDOW,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            poll(proc)

        def do_add():
            picked = [g for g in state["groups"] if g["url"] in state["picked"]]
            if not picked:
                messagebox.showinfo("Thêm vào kịch bản", "Tick ít nhất 1 nhóm (bấm vào dòng nhóm).", parent=win)
                return
            app.commit_form()
            groups = item.setdefault("groups", [])
            names = item.setdefault("group_names", {})
            added = 0
            for g in picked:
                if g["url"] not in groups:
                    groups.append(g["url"])
                    added += 1
                names[g["url"]] = g["name"]
            state["picked"].clear()
            app.mark_dirty()
            app.save(quiet=True)
            render()
            self.refresh_groups()
            self.update_estimate()
            status.configure(text=f"✅ Đã thêm {added} nhóm vào kịch bản. Ở bảng nhóm của kịch bản: tick nhóm → "
                                  "🙋 Xin vào để các tài khoản vào nhóm.")

        find_btn.configure(command=do_find)
        add_btn.configure(command=do_add)
        tree.bind("<ButtonRelease-1>", lambda e: toggle(tree.identify_row(e.y))
                  if tree.identify_region(e.x, e.y) == "cell" else None)
        update_count()
        win.grab_set()

    def media_box(self, parent, item):
        """Thu muc anh / video dinh kem + so file moi bai."""
        ttk.Label(parent, text="Ảnh / video đính kèm", style="Field.TLabel").pack(anchor="w")
        ui.fit_wrap(ttk.Label(parent, text="Chọn 1 thư mục chứa ảnh (jpg, png, webp, gif) hoặc video (mp4, mov…). Mỗi "
                                           "bài đính kèm các file ĐẦU TIÊN theo tên file (đặt tên 01.jpg, 02.jpg… để "
                                           "chọn thứ tự). Để trống = chỉ đăng chữ.", style="Hint.TLabel",
                              wraplength=620, justify="left"), parent)
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(4, 0))
        label = ttk.Label(row, text="", wraplength=420, justify="left")
        label.pack(side="left", fill="x", expand=True)

        def show():
            folder = (item.get("media_folder") or "").strip()
            files = upstt_store.media_files(item)
            if not folder:
                text = "Chưa chọn – chỉ đăng chữ"
            elif not Path(folder).is_dir():
                text = f"⚠ Không thấy thư mục: {folder}"
            elif not files:
                text = f"⚠ Thư mục không có ảnh / video: {folder}"
            else:
                text = f"🖼 {folder}\n   Mỗi bài kèm: " + ", ".join(f.name for f in files)
            label.configure(text=text)

        def pick():
            folder = filedialog.askdirectory(title="Chọn thư mục ảnh / video", initialdir=item.get("media_folder") or None)
            if folder:
                item["media_folder"] = str(Path(folder))
                self.app.mark_dirty()
                show()
                self.update_estimate()

        def clear():
            item["media_folder"] = ""
            self.app.mark_dirty()
            show()
            self.update_estimate()

        def open_folder():
            folder = item.get("media_folder") or ""
            if folder and Path(folder).is_dir():
                import os
                os.startfile(folder)

        ttk.Button(row, text="Chọn thư mục...", command=pick).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="Mở", width=5, command=open_folder).pack(side="left", padx=(6, 0))
        ttk.Button(row, text="Bỏ", width=5, command=clear).pack(side="left", padx=(6, 0))
        show()
        ttk.Frame(parent, height=8).pack()
        self.app.form.add(parent, item, "media_count", "int", "Số ảnh / video mỗi bài (tối thiểu)",
                          f"Từ 1 đến {upstt_store.MEDIA_MAX}. Nhiều file thì đăng lâu hơn.",
                          {"min": 1, "max": upstt_store.MEDIA_MAX})
        var = self.app.form.widgets["media_count"][1]
        var.trace_add("write", lambda *_a: (item.update(media_count=int(var.get()))
                                             if var.get().strip().isdigit() else None, show()))
        self.app.form.add(parent, item, "media_count_max", "int", "Số ảnh / video tối đa (để lấy ngẫu nhiên)",
                          "Để 0 = luôn lấy đúng số tối thiểu. Lớn hơn số tối thiểu = mỗi bài lấy ngẫu nhiên "
                          "từ tối thiểu đến số này (ảnh vẫn lấy theo thứ tự tên file).",
                          {"min": 0, "max": upstt_store.MEDIA_MAX})

    def update_estimate(self):
        app = self.app
        if not (app.current and app.current[0] == "scenario" and self.estimate is not None
                and self.estimate.winfo_exists() and getattr(self, "_est", None)):
            return
        s, item = self._est
        ticked = store.ticked_accounts(app.data, s)
        aid = ticked[0]["id"] if ticked else None
        n = upstt_store.run_group_count(item, aid) if aid else len(item.get("groups", []))
        self.estimate.configure(text=f"⏱  Mỗi lần đăng hết khoảng {upstt_store.estimate_minutes(item, aid)} phút "
                                     f"· {n} nhóm/lượt" + (f" (tài khoản '{ticked[0]['name']}')" if ticked else "") + ".")

    def commit_extra(self, item, errors):
        """Gio: chuan hoa '6:30', '19h00' -> '06:30', '19:00'; sai thi bao loi khi Luu."""
        if "times" in self.app.form.widgets:
            item["times"], bad = upstt_store.normalize_times(self.app.form.lines("times"))
            if bad:
                errors.append(f"[{item.get('name') or 'Kịch bản'}] Giờ sai: {', '.join(bad)} (viết dạng 06:30).")

    def tree_item_text(self, item):
        days = upstt_store.weekdays_text(item.get("weekdays"))
        extra = "" if days == "hằng ngày" else f" ({days})"
        return f"{item['name']}   ·   {', '.join(item['times']) or 'chưa có giờ'}{extra}"

    def account_item_summary(self, item):
        return (f"{item['name']}  —  {len(item['groups'])} nhóm  —  giờ: {', '.join(item['times']) or 'chưa có'} "
                f"({upstt_store.weekdays_text(item.get('weekdays'))})"
                f"  —  ~{upstt_store.estimate_minutes(item)} phút/lần" + ("" if item["enabled"] else "  (đang tắt)"))

    def on_delete_item(self, ident, stamp):
        pass


class MonitorKind:
    """Nhom theo doi (fb_monitor_v4.py): quet tu khoa, bao Telegram, tu binh luan; lich quet theo tai khoan."""
    KEY = store.MONITOR
    ITEM_NOUN = "nhóm theo dõi"
    ADD_LABEL = "🔎 Theo dõi"
    FOLDER_LABEL = "Theo dõi nhóm"
    CHIP_LABEL = "Theo dõi"
    ITEM_ICON = "🔎"
    RESULT_KIND = "comments"       # tab Tong hop: binh luan duoc duyet / bi go
    LOG_TASK_LEVEL = "account"     # moi tai khoan 1 lich quet -> nhat ky theo tai khoan
    ENABLED_TITLE = "Bật theo dõi nhóm này"
    ENABLED_HINT = ("Bật: mỗi lần quét, tool tìm bài trong các nhóm bên dưới, báo về Telegram và tự bình luận "
                    "(nếu bật).\nTắt: tạm bỏ qua nhóm theo dõi này, vẫn giữ nguyên cài đặt – bật lại là chạy tiếp.")

    def __init__(self, app):
        self.app = app
        # Dung chung bang nhom / Tim nhom / Xin vao - Roi nhom / bang 'chay ngay' voi ben dang bai (giong nhau).
        self.g = PostKind(app)

    def item_tabs(self):
        return [
            ("Kết quả tổng hợp", [("Bình luận của bạn ở từng nhóm", [])]),
            ("Kết quả chi tiết", [("Nhật ký từng lần quét", [])]),
            ("Setting cơ bản", [
                ("Theo dõi nhóm nào", [
                    ("groups", "list", "Danh sách nhóm",
                     "Dán link nhóm, mỗi dòng 1 nhóm (vd: https://www.facebook.com/groups/abc).", {"height": 6}),
                ]),
                ("Tìm bài nào", [
                    ("keywords", "list", "Từ khóa cần tìm",
                     "Mỗi dòng 1 từ hoặc cụm từ. Bài có ít nhất 1 từ khóa sẽ được báo về.", {}),
                    ("exclude_keywords", "list", "Từ khóa loại trừ",
                     "Bài có 1 trong các từ này sẽ bị bỏ qua. Có thể để trống.", {}),
                ]),
                ("Báo về Telegram", [
                    ("telegram_token", "secret", "Mã bot (Token)", "Lấy từ @BotFather trên Telegram.", {}),
                    ("telegram_chat_id", "text", "Chat ID",
                     "Lấy từ @userinfobot (ID của bạn hoặc của nhóm Telegram nhận tin).", {}),
                ]),
                ("Tự bình luận", [
                    ("auto_comment", "bool", "Tự bình luận vào bài tìm được",
                     "Bật: sau khi báo Telegram, tool tự bình luận vào bài (nội dung + ảnh bên dưới).\n"
                     "Tắt: chỉ báo về Telegram, không bình luận.", {}),
                    ("comment_text", "multiline", "Bình luận lần 1", "Viết như bình luận tay, xuống dòng thoải mái.", {}),
                    ("comment_text_2", "multiline", "Bình luận lần 2",
                     "Để trống nếu chỉ bình luận 1 lần. Lần 2 chỉ chạy khi lần 1 thành công.", {}),
                ]),
            ]),
            ("Setting nâng cao", [
                ("Lọc bài quảng cáo", [
                    ("ad_filter", "bool", "Bật lọc bài quảng cáo",
                     "Bật: tự bỏ qua bài có dấu hiệu quảng cáo (chấm điểm theo các danh sách bên dưới).\n"
                     "Tắt: không lọc - mọi bài khớp từ khóa đều được gửi Telegram / bình luận "
                     "(các danh sách bên dưới tạm không dùng, vẫn giữ nguyên).", {}),
                    ("ad_score_rules", "list", "Dấu hiệu quảng cáo (cụm từ=điểm)",
                     "Mỗi dòng 1 cụm, dạng  cụm từ=điểm  (vd: hotline=6). Không ghi điểm = 3 điểm.\n"
                     "Bài gặp cụm nào thì CỘNG DỒN điểm cụm đó (cùng với điểm tool tự chấm: số điện thoại, "
                     "giá, địa chỉ, hashtag, inbox...).\n"
                     "Cụm có điểm ≥ vạch chặn = gặp là chặn ngay. Cụm điểm thấp = cần thêm dấu hiệu khác.", {}),
                    ("ad_score_threshold", "int", "Vạch chặn: tổng điểm từ bao nhiêu thì coi là quảng cáo",
                     "Đây là vạch chặn, KHÔNG phải điểm tối đa (1 bài quảng cáo có thể được 20-40 điểm).\n"
                     "Bài viết kiểu người đi tìm ('mình cần', 'có ai biết'...) vẫn được giữ lại dù đủ điểm, "
                     "trừ khi có giá / số điện thoại / tự xưng bên bán.", {"min": 1, "max": 100}),
                ]),
                ("Trình duyệt", []),
            ]),
        ]

    # ------------------------------------------------------------ kich ban / tai khoan chay
    def scenario_tabs(self):
        # Giong ben Dang bai: 1 tab chinh (bang nhom + toan bo thiet lap) + Tai khoan chay. Rule khi loi: Cai dat.
        return [("🔎 Theo dõi", None), ("👥 Tài khoản chạy", "accounts")]

    def spec(self, key):
        """Dong mo ta o nhap (key, kieu, tieu de, goi y, tuy chon) lay tu item_tabs - 1 noi dinh nghia."""
        for _name, sections in self.item_tabs():
            for _title, specs in sections:
                for sp in specs:
                    if sp[0] == key:
                        return sp
        raise KeyError(key)

    def build_scenario_tab(self, app, parent, tab_name, s):
        """Man chinh kich ban theo doi: bang nhom (rong het) + 2 cot: Tim bai nao | Khi tim thay + Lich quet."""
        item = s["settings"]
        gbox = ui.Box(parent, text="Nhóm theo dõi")
        gbox.add_pill(f"{len(item.get('groups', []))} nhóm")
        gbox.pack(fill="x")
        self.g.groups_panel(gbox, s)
        grid = ttk.Frame(parent)
        grid.pack(fill="both", expand=True, pady=(10, 0))
        grid.columnconfigure(0, weight=1, uniform="c")
        grid.columnconfigure(1, weight=1, uniform="c")
        left = ttk.Frame(grid)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right = ttk.Frame(grid)
        right.grid(row=0, column=1, sticky="nsew")

        box = ui.Box(left, text="  🔍 Tìm bài nào  ", padding=(10, 6))
        box.pack(fill="x")
        for key in ("keywords", "exclude_keywords"):
            app.form.add(box, item, *self.spec(key))
        cbox = ui.Box(left, text="  💬 Tự bình luận  ", padding=(10, 6))
        cbox.pack(fill="x", pady=(8, 0))
        for key in ("auto_comment", "comment_text", "comment_text_2"):
            app.form.add(cbox, item, *self.spec(key))
        self.scenario_section_extra("Tự bình luận", cbox, s)

        tbox = ui.Box(right, text="  ✈ Báo về Telegram  ", padding=(10, 6))
        tbox.pack(fill="x")
        for key in ("telegram_token", "telegram_chat_id"):
            app.form.add(tbox, item, *self.spec(key))
        ttk.Button(tbox, text="✈  Gửi thử Telegram", command=self.test_telegram).pack(anchor="w", pady=(0, 6))
        sbox = ui.Box(right, text="  🕒 Lịch quét  ", padding=(10, 6))
        sbox.pack(fill="x", pady=(8, 0))
        _default, low, high = store.monitor_store.SCAN_MINUTES
        app.form.add(sbox, item, "scan_minutes", "int", "Quét mỗi bao nhiêu phút",
                     "Áp dụng cho TẤT CẢ tài khoản trong kịch bản này. Lần trước chưa xong thì lần sau tự đợi. "
                     "Chạy ngầm / hiện Chrome: đặt ở từng tài khoản (⚙ Thiết lập).", {"min": low, "max": high})
        self.g.weekday_box(sbox, item, verb="quét")
        abox = ui.Box(right, text="  🚫 Lọc bài quảng cáo  ", padding=(10, 6))
        abox.pack(fill="x", pady=(8, 0))
        for key in ("ad_filter", "ad_score_rules", "ad_score_threshold"):
            app.form.add(abox, item, *self.spec(key))
        ttk.Label(parent, text="🔎 Quét ngay / xem kết quả / khách tìm được: chọn từng tài khoản (👤) bên dưới kịch bản "
                               "ở cây bên trái.", style="Hint.TLabel", wraplength=700,
                  justify="left").pack(anchor="w", pady=(8, 0))

    def member_tabs(self):
        return ([("🔎 Quét ngay", None), ("🎯 Khách tìm được", None)]
                + [t for t in self.item_tabs() if t[0].startswith("Kết quả")])

    def leads(self, item, days):
        """Bai khach (khop tu khoa, khong phai quang cao, da bao Telegram) trong `days` ngay + dem bai bi loc."""
        import json
        from datetime import datetime, timedelta
        since = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        path = store.CAMPAIGNS_DIR / item["id"] / "bai_thu_thap.jsonl"
        out, skipped = [], {"quang_cao": 0, "tu_loai": 0}
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return out, skipped
        for line in lines:
            try:
                j = json.loads(line)
            except ValueError:
                continue
            if str(j.get("time", ""))[:10] < since:
                continue
            if j.get("decision") == "gui_telegram":
                out.append(j)
            elif j.get("decision") in skipped:
                skipped[j["decision"]] += 1
        return list(reversed(out)), skipped

    def leads_tab(self, app, parent, account, item):
        import tkinter as tk
        import fb_login
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 6))
        ranges = {"Hôm nay": 1, "7 ngày": 7, "30 ngày": 30}
        rng = tk.StringVar(value="7 ngày")
        ttk.Label(bar, text="Xem:").pack(side="left")
        combo = ttk.Combobox(bar, values=list(ranges), textvariable=rng, state="readonly", width=10)
        combo.pack(side="left", padx=6)
        info = ttk.Label(bar, text="", style="Hint.TLabel")
        info.pack(side="left", padx=8)
        tbox, tree = self.g.make_table(parent, [("time", "Lúc", 110, False, "w"), ("group", "Nhóm", 200, False, "w"),
                                                ("kw", "Từ khóa khớp", 140, False, "w"),
                                                ("text", "Nội dung bài", 380, True, "w"),
                                                ("cmt", "Bình luận", 90, False, "center")], height=12)
        tbox.pack(fill="both", expand=True)
        rows = {}
        acc_dir = app.account_dir(account)
        try:
            commented = set((acc_dir / "commented_ids.txt").read_text(encoding="utf-8").split())
        except OSError:
            commented = set()
        s, _aid = store.scenario_of(app.data, item["id"])
        names = self.g.group_names(s) if s else {}

        def fill(*_a):
            tree.delete(*tree.get_children())
            rows.clear()
            found, skipped = self.leads(item, ranges[rng.get()])
            for j in found:
                slug = fb_login.group_slug(j.get("url", "")) or ""
                iid = tree.insert("", "end", values=(str(j.get("time", ""))[5:16], names.get(slug) or slug,
                                                     ", ".join(j.get("keywords", [])[:3]),
                                                     " ".join(str(j.get("text", "")).split())[:160],
                                                     "✓ đã" if str(j.get("id")) in commented else "—"))
                rows[iid] = j
            if not found:
                tree.insert("", "end", values=("", "Chưa có khách trong khoảng này", "", "", ""), tags=["muted"])
            info.configure(text=f"{len(found)} khách · bỏ qua {skipped['quang_cao']} bài quảng cáo, "
                                f"{skipped['tu_loai']} bài có từ loại trừ")

        def open_post(_e=None):
            j = rows.get(tree.focus())
            if j and j.get("url"):
                app.open_in_account(account, j["url"])

        def copy_link():
            j = rows.get(tree.focus())
            if j and j.get("url"):
                app.root.clipboard_clear()
                app.root.clipboard_append(j["url"])
                app.flash("Đã sao chép link bài.")

        act = ttk.Frame(parent)
        act.pack(fill="x", pady=(8, 0))
        ttk.Button(act, text="↗ Mở bài (Chrome của tài khoản)", command=open_post).pack(side="left")
        ttk.Button(act, text="📋 Sao chép link", command=copy_link).pack(side="left", padx=8)
        ttk.Label(parent, text="Khách = bài khớp từ khóa, không phải quảng cáo, đã báo Telegram. Nhiều bài quảng cáo bị "
                               "bỏ qua nhầm → giảm bớt 'Dấu hiệu quảng cáo' / tăng 'Vạch chặn' ở kịch bản.",
                  style="Hint.TLabel", wraplength=760, justify="left").pack(anchor="w", pady=(6, 0))
        tree.bind("<Double-1>", open_post)
        combo.bind("<<ComboboxSelected>>", fill)
        fill()

    def build_member_tab(self, app, parent, tab_name, account, item):
        if tab_name.startswith("🎯"):
            self.leads_tab(app, parent, account, item)
            return
        hint = (f"“Quét ngay” quét liền các nhóm ĐÃ TICK bằng tài khoản '{account['name']}' (tìm bài theo từ khóa, báo "
                "Telegram, tự bình luận nếu bật). Lịch tự động vẫn quét theo chu kỳ của kịch bản. Thêm / bớt nhóm: "
                "sửa ở kịch bản.")
        # Nhom cong khai khong can vao van quet duoc -> tick san moi nhom tru nhom dang cho duyet / cau hoi.
        self.g.build_member_tab(app, parent, tab_name, account, item,
                                action=("🔎  Quét ngay", lambda urls: self.scan_now(account, item, urls), hint),
                                preselect=lambda st: st not in ("pending", "questions"))

    def scan_now(self, account, item, urls):
        import subprocess
        app = self.app
        app.commit_form()
        if not urls:
            messagebox.showinfo("Quét ngay", "Tick chọn ít nhất 1 nhóm.")
            return
        if not app.account_usable(account):
            messagebox.showwarning("Quét ngay", f"Tài khoản '{account['name']}' chưa đăng nhập.")
            return
        if not item.get("keywords"):
            messagebox.showwarning("Quét ngay", "Kịch bản chưa có từ khóa (sửa ở kịch bản → khung 'Tìm bài nào').")
            return
        if app.has_changes() and not app.save(quiet=True):
            return
        if not messagebox.askyesno("Quét ngay", f"Quét liền {len(urls)} nhóm đã tick bằng tài khoản "
                                                f"'{account['name']}'?\n\nXem tiến trình ở tab 'Kết quả chi tiết'."):
            return
        cmd = [app.python, str(app.SCRIPT), "--once", "--account", account["id"], "--item", item["id"],
               "--only", "|".join(urls)]
        subprocess.Popen(cmd, cwd=app.base_dir, creationflags=ui.NO_WINDOW,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        app.flash(f"🔎 Đang quét {len(urls)} nhóm… xem tab 'Kết quả chi tiết'.")

    def media_folder_box(self, parent, item):
        """Thu muc anh binh luan (giong ben dang bai): moi binh luan lay ngau nhien 1 anh."""
        ttk.Label(parent, text="Hoặc thư mục ảnh (ngẫu nhiên 1 ảnh / bình luận)",
                  style="Field.TLabel").pack(anchor="w", pady=(8, 0))
        label = ttk.Label(parent, text="", wraplength=420, justify="left", style="Hint.TLabel")
        ui.fit_wrap(label, parent)
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(4, 0))

        def show():
            folder = (item.get("comment_media_folder") or "").strip()
            pics = [f for f in Path(folder).iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif")
                    ] if folder and Path(folder).is_dir() else []
            label.configure(text="Chưa chọn – dùng ảnh lần 1 / lần 2 ở trên" if not folder else
                            f"⚠ Không thấy thư mục / không có ảnh: {folder}" if not pics else
                            f"🖼 {folder} ({len(pics)} ảnh)")

        def pick():
            folder = filedialog.askdirectory(title="Chọn thư mục ảnh bình luận",
                                             initialdir=item.get("comment_media_folder") or None)
            if folder:
                item["comment_media_folder"] = str(Path(folder))
                self.app.mark_dirty()
                show()

        def clear():
            item["comment_media_folder"] = ""
            self.app.mark_dirty()
            show()

        ttk.Button(row, text="Chọn thư mục...", command=pick).pack(side="left")
        ttk.Button(row, text="Bỏ", width=5, command=clear).pack(side="left", padx=(6, 0))
        show()
        ttk.Frame(parent, height=10).pack()

    @staticmethod
    def days_suffix(item):
        days = upstt_store.weekdays_text(item.get("weekdays"))
        return "" if days == "hằng ngày" else f" ({days.replace('Thứ: ', '')})"

    def tree_scenario_text(self, s):
        return f"{s['name']}   ·   {len(s['settings'].get('groups', []))} nhóm" + self.days_suffix(s["settings"])

    def tree_member_text(self, account, item):
        return ""

    def tree_scenario_info(self, s):
        st = s["settings"]
        return (f"{len(st.get('groups', []))} nhóm · mỗi {store.monitor_store.scan_minutes(st)} phút"
                + self.days_suffix(st))

    def tree_member_info(self, account, item):
        return f"quét {store.monitor_store.scan_minutes(item)} ph"

    def scenario_summary(self, s):
        st = s["settings"]
        return (f"{len(s['accounts'])} tài khoản  ·  {len(st.get('groups', []))} nhóm  ·  quét mỗi "
                f"{store.monitor_store.scan_minutes(st)} phút ({upstt_store.weekdays_text(st.get('weekdays'))})  ·  "
                f"{len(st.get('keywords', []))} từ khóa  ·  tự bình luận: {'bật' if st.get('auto_comment') else 'tắt'}")

    def member_kpis(self, app, s, account, item):
        groups = item.get("groups", [])
        joined = self.g.joined_count(account["id"], groups)
        found, _skipped = self.leads(item, 7)
        return [(f"{store.monitor_store.scan_minutes(item)} phút", "quét mỗi (đặt ở kịch bản)", None),
                (f"{joined}/{len(groups)}", "nhóm đã vào", ui.GREEN if joined == len(groups) and groups else ui.AMBER),
                (len(found), "khách tìm được (7 ngày)", ui.AMBER),
                (self.g.sent_7days(app, account, groups, "comment"), "bình luận đã gửi (7 ngày)", "#1d4ed8")]

    def member_columns(self, app, s, account):
        return (f"mỗi {store.monitor_store.scan_minutes(s['settings'])} phút",
                self.g.membership_text(account["id"], s["settings"].get("groups", [])))

    def member_info(self, app, s, account):
        return (f"quét mỗi {store.monitor_store.scan_minutes(s['settings'])} phút (đặt ở kịch bản)  ·  "
                f"{self.g.membership_text(account['id'], s['settings'].get('groups', []))}")

    def member_summary(self, app, s, account, item):
        return (f"Tài khoản này quét {self.g.membership_text(account['id'], item['groups'])} mỗi "
                f"{store.monitor_store.scan_minutes(item)} phút ({upstt_store.weekdays_text(item.get('weekdays'))}). "
                "Nhóm, từ khoá, bình luận, chu kỳ quét: sửa ở kịch bản (nút ✎ bên phải).")

    def scenario_section_extra(self, title, parent, s):
        app = self.app
        if title == "Rule khi lỗi":
            app.rules_box(parent)
        if title == "Báo về Telegram":
            ttk.Button(parent, text="✈  Gửi thử Telegram", command=self.test_telegram).pack(anchor="w", pady=(0, 12))
        if title == "Tự bình luận":
            ttk.Label(parent, text="Ảnh kèm bình luận",
                      style="Field.TLabel").pack(anchor="w")
            for n in (1, 2):
                row = ttk.Frame(parent)
                row.pack(fill="x", pady=(4, 0))
                path = self.scenario_image(s, n)
                label = ttk.Label(row, text=self.image_text(n, path), width=18)
                label.pack(side="left")
                ttk.Button(row, text="Chọn ảnh...", command=lambda n=n, l=label: self.pick_image(s, n, l)).pack(side="left")
                ttk.Button(row, text="Bỏ ảnh", command=lambda n=n, l=label: self.remove_image(s, n, l)).pack(side="left", padx=6)
            self.media_folder_box(parent, s["settings"])

    def scenario_image(self, s, n):
        return next((f for f in store.scenario_images(self.app.data, s) if f.stem == f"anh{n}"), None)

    def section_extra(self, title, parent, item):
        app = self.app
        account = store.find_campaign(app.data, item["id"])[0]
        if title == "Bình luận của bạn ở từng nhóm":
            app.results_tab(parent, account, item)
        if title == "Nhật ký từng lần quét":
            app.details_tab(parent, account, item)
        if title == "Rule khi lỗi":
            app.rules_box(parent)
        if title == "Trình duyệt":
            # Moi lan quet, tai khoan mo 1 trinh duyet chung cho moi nhom theo doi -> ap dung ca tai khoan.
            app.form.add(parent, item, "headless", "bool", "Chạy ngầm (không hiện cửa sổ Chrome)",
                         "Bật (nên để bật): tool chạy ngầm, không hiện cửa sổ.\n"
                         "Tắt: hiện cửa sổ Chrome để xem tool đang làm gì – dùng khi cần tìm lỗi.\n"
                         f"Áp dụng cho việc QUÉT của CẢ tài khoản '{account['name']}' (mọi nhóm theo dõi dùng chung "
                         "1 cửa sổ).", {"target": account})
        if title == "Báo về Telegram":
            ttk.Button(parent, text="✈  Gửi thử Telegram", command=self.test_telegram).pack(anchor="w", pady=(0, 12))
        if title == "Tự bình luận":
            ttk.Label(parent, text="Ảnh kèm bình luận", style="Field.TLabel").pack(anchor="w")
            for n in (1, 2):
                row = ttk.Frame(parent)
                row.pack(fill="x", pady=(4, 0))
                path = store.image_path(item, n)
                label = ttk.Label(row, text=self.image_text(n, path), width=18)
                label.pack(side="left")
                ttk.Button(row, text="Chọn ảnh...", command=lambda n=n, l=label: self.pick_image(item, n, l)).pack(side="left")
                ttk.Button(row, text="Bỏ ảnh", command=lambda n=n, l=label: self.remove_image(item, n, l)).pack(side="left", padx=6)
            ttk.Frame(parent, height=10).pack()

    @staticmethod
    def image_text(n, path):
        return f"Lần {n}:  " + (f"🖼 {path.name}" if path else "chưa có ảnh")

    def pick_image(self, s, n, label):
        src = filedialog.askopenfilename(title=f"Chọn ảnh bình luận lần {n}",
                                         filetypes=[("Ảnh", "*.jpg *.jpeg *.png *.webp"), ("Tất cả", "*.*")])
        if not src:
            return
        self.remove_image(s, n, label)
        dst = store.scenario_image_dir(self.app.data, s) / f"anh{n}{Path(src).suffix.lower()}"
        shutil.copy(src, dst)
        label.configure(text=self.image_text(n, dst))
        store.sync_images(self.app.data)
        self.app.flash("Đã chọn ảnh (áp dụng ngay cho các tài khoản chạy kịch bản, không cần bấm Lưu).")

    def remove_image(self, s, n, label):
        for old in store.scenario_image_dir(self.app.data, s).glob(f"anh{n}.*"):
            old.unlink()
        label.configure(text=self.image_text(n, None))
        store.sync_images(self.app.data)

    def test_telegram(self):
        app = self.app
        app.commit_form()
        item = app.find(*app.current)
        if not item["telegram_token"] or not item["telegram_chat_id"]:
            messagebox.showwarning("Telegram", "Điền Token và Chat ID trước.")
            return
        s = store.find_scenario(app.data, app.current[1])
        name = s["name"] if s else item.get("name", "")
        ok, detail = ui.send_telegram_test(item["telegram_token"], item["telegram_chat_id"],
                                           f"✅ Tool Facebook ({name}): gửi thử Telegram thành công.")
        if ok:
            messagebox.showinfo("Telegram", "Đã gửi tin thử. Mở Telegram để kiểm tra.")
        else:
            messagebox.showerror("Telegram", "Gửi thử thất bại. Kiểm tra Token, Chat ID và đã bấm Start với bot chưa.\n\n" + detail)

    def commit_extra(self, item, errors):
        pass

    def tree_item_text(self, item):
        return f"{item['name']}   ·   {len(item['groups'])} nhóm"

    def account_item_summary(self, item):
        return (f"{item['name']}  —  {len(item['groups'])} nhóm  —  {len(item['keywords'])} từ khóa  —  "
                f"bình luận: {'có' if item['auto_comment'] else 'không'}" + ("" if item["enabled"] else "  (đang tắt)"))

    def on_delete_item(self, ident, stamp):
        old = store.CAMPAIGNS_DIR / ident
        if old.exists():
            old.rename(store.CAMPAIGNS_DIR / f"_da_xoa_{ident}_{stamp}")


class ToolApp(ui.TreeConfigApp):
    STORE = store
    SCRIPT = Path(__file__).resolve().parent / "main.py"
    TITLE = "Tool Facebook – Đăng bài & Theo dõi nhóm"
    ITEM_NOUN = "mục"
    ACCOUNT_FIELDS_TITLE = "Thiết lập"
    # Chu ky quet dat o kich ban theo doi (23/10/2026). Chay ngam de o tai khoan: moi lan quet, tai khoan mo
    # 1 Chrome chung cho moi kich ban theo doi cua no.
    ACCOUNT_FIELDS = [
        ("headless", "bool", "Quét theo dõi chạy ngầm (không hiện cửa sổ Chrome)",
         "Bật (nên để bật): tool quét ngầm, không hiện cửa sổ.\n"
         "Tắt: hiện cửa sổ Chrome để xem tool đang làm gì – dùng khi cần tìm lỗi. Chu kỳ quét: đặt ở kịch bản.", {}),
    ]

    def __init__(self, root):
        self.KINDS = {store.POST: PostKind(self), store.MONITOR: MonitorKind(self)}
        super().__init__(root)
        self.refresh_license()
        if not ban_quyen.trang_thai()["ok"]:
            root.after(600, self.show_license)

    # ------------------------------------------------------------ ban quyen
    def refresh_license(self):
        st = ban_quyen.trang_thai()
        self.root.title(f"{self.TITLE}   –   {ban_quyen.mo_ta(st)}")
        self.refresh_header()
        return st

    def refresh_header(self):
        super().refresh_header()
        # 1 dong ngan (dong dai / nhieu dong lam giao dien ve lai lien tuc). Chi tiet nam trong cua so Ban quyen.
        st = ban_quyen.trang_thai()
        self.nav_license.configure(
            text=(f"🔑 Bản quyền đến {st['het_han']:%d/%m/%Y}\n{st['so_tai_khoan']} tài khoản"
                  + (f"\n⚠ còn {st['con_ngay']} ngày" if st["con_ngay"] <= LICENSE_WARN_DAYS else ""))
            if st["ok"] else "⛔ Chưa có bản quyền\n(bấm để nhập key)",
            fg="#fbbf24" if not st["ok"] or st["con_ngay"] <= LICENSE_WARN_DAYS else "#cfe0ff")
        extra = ""
        if not st["ok"]:
            extra = "⛔  Chưa có bản quyền hợp lệ → tool KHÔNG chạy theo lịch. Vào 🛠 Cài đặt → Bản quyền để nhập key."
        elif len(self.data["accounts"]) > st["so_tai_khoan"]:
            extra = (f"⚠  Bản quyền cho {st['so_tai_khoan']} tài khoản đầu tiên – "
                     f"{len(self.data['accounts']) - st['so_tai_khoan']} tài khoản cuối danh sách KHÔNG chạy.")
        if extra and not self.data.get("paused"):
            self.pause_banner.configure(text=extra)

    def license_section(self, parent):
        """Trang Cai dat: tinh trang ban quyen + nut nhap key (cua so cu)."""
        st = ban_quyen.trang_thai()
        import tkinter as tk
        box = ui.section(parent, "🔑 Bản quyền")
        # (ban thiet ke 1) vien thuoc "còn hạn đến …" · so tai khoan; dong Ma may [ma] [Sao chép] [Nhập key mới]
        top = ttk.Frame(box)
        top.pack(anchor="w")
        if st["ok"]:
            pill, fg, bg = f"✓ còn hạn đến {st['het_han']:%d/%m/%Y}", ui.GREEN, "#e7f6ec"
            if st["con_ngay"] <= LICENSE_WARN_DAYS:
                pill, fg, bg = f"⚠ còn {st['con_ngay']} ngày (đến {st['het_han']:%d/%m/%Y})", ui.AMBER, "#fff4e0"
            rest = f"·  {st['so_tai_khoan']} tài khoản" + (f"  ·  {st['khach']}" if st.get("khach") else "")
        else:
            pill, fg, bg, rest = "⛔ chưa có bản quyền", ui.RED, "#fde8e8", ban_quyen.mo_ta(st)
        tk.Label(top, text=pill, fg=fg, bg=bg, font=("Segoe UI Semibold", 9), padx=7).pack(side="left")
        ttk.Label(top, text=rest, style="Sub.TLabel").pack(side="left", padx=(8, 0))
        row = ttk.Frame(box)
        row.pack(anchor="w", pady=(8, 0))
        code = ban_quyen.ma_may()
        ttk.Label(row, text="Mã máy").pack(side="left")
        tk.Label(row, text=code, bg="#ffffff", fg=ui.TEXT, font=ui.FONT, padx=9, pady=2, highlightthickness=1,
                 highlightbackground=ui.LINE).pack(side="left", padx=(8, 6))

        def copy():
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            self.flash("Đã chép mã máy – gửi cho người bán để nhận key.")
        ttk.Button(row, text="Sao chép", command=copy, style="Small.TButton").pack(side="left")
        ttk.Button(row, text="Nhập key mới", command=self.show_license, style="Small.TButton").pack(side="left",
                                                                                                padx=(6, 0))

    def _license_alerts(self):
        st = ban_quyen.trang_thai()
        go = lambda: self.show_page("settings")
        if not st["ok"]:
            return [("bad", "Chưa có bản quyền hợp lệ", "tool KHÔNG chạy theo lịch · gửi mã máy cho người bán để nhận key",
                     "Nhập key", go)]
        if st["con_ngay"] <= LICENSE_WARN_DAYS:
            return [("warn", f"Bản quyền còn {st['con_ngay']} ngày (đến {st['het_han']:%d/%m/%Y})",
                     "liên hệ người bán gia hạn để tool không dừng", "Gia hạn", go)]
        return []

    def show_license(self):
        import tkinter as tk
        win = tk.Toplevel(self.root)
        win.title("Bản quyền")
        win.transient(self.root)
        win.resizable(False, False)
        frame = ttk.Frame(win, padding=18)
        frame.pack(fill="both", expand=True)
        status = ttk.Label(frame, text="", style="Field.TLabel", wraplength=520, justify="left")
        status.pack(anchor="w")
        ttk.Label(frame, text="Mã máy (gửi cho người bán để nhận key):", style="Hint.TLabel").pack(anchor="w", pady=(14, 2))
        row = ttk.Frame(frame)
        row.pack(fill="x")
        code = ban_quyen.ma_may()
        entry = ttk.Entry(row, font=("Consolas", 12), width=30)
        entry.insert(0, code)
        entry.configure(state="readonly")
        entry.pack(side="left")

        def copy_code():
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            self.flash("Đã sao chép mã máy.")
        ttk.Button(row, text="📋 Sao chép mã máy", command=copy_code).pack(side="left", padx=(8, 0))
        ttk.Label(frame, text="Dán key nhận được vào đây rồi bấm Kích hoạt:", style="Hint.TLabel").pack(anchor="w", pady=(14, 2))
        box_frame, box = ui.text_box(frame, 4, wrap="char")
        box_frame.pack(fill="x")
        result = ttk.Label(frame, text="", wraplength=520, justify="left")
        result.pack(anchor="w", pady=(8, 0))

        def show():
            st = ban_quyen.trang_thai()
            extra = f"\nKhách: {st['khach']}" if st.get("khach") else ""
            status.configure(text=ban_quyen.mo_ta(st) + extra, style="Ok.TLabel" if st["ok"] else "Bad.TLabel")

        def activate():
            ok, info = ban_quyen.kich_hoat(box.get("1.0", "end"))
            if not ok:
                result.configure(text="❌ " + info, style="Bad.TLabel")
                return
            result.configure(text="✅ Đã kích hoạt. Đang cập nhật lịch chạy…", style="Ok.TLabel")
            show()
            self.refresh_license()
            kind, ident = self.selected()
            self.refresh_tree(f"{kind}:{ident}" if kind else None)
            self.sync_schedule_async(lambda text: result.winfo_exists() and result.configure(
                text=f"✅ Đã kích hoạt – {text}."))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="Kích hoạt", style="Accent.TButton" if ui.sv_ttk else "TButton",
                   command=activate).pack(side="right")
        ttk.Button(buttons, text="Đóng", command=win.destroy).pack(side="right", padx=8)

        def terms():
            path = self.base_dir / "BAN_QUYEN.txt"
            messagebox.showinfo("Điều khoản", path.read_text(encoding="utf-8") if path.exists() else ui.COPYRIGHT,
                                parent=win)
        ttk.Button(buttons, text="Điều khoản sử dụng", command=terms).pack(side="left")
        show()
        win.grab_set()

    def add_account(self):
        st = ban_quyen.trang_thai()
        if st["ok"] and len(self.data["accounts"]) >= st["so_tai_khoan"]:
            messagebox.showwarning("Bản quyền", f"Bản quyền hiện tại cho tối đa {st['so_tai_khoan']} tài khoản.\n\n"
                                                "Liên hệ người bán để nâng gói, hoặc xoá bớt tài khoản không dùng.")
            return
        super().add_account()

    def commit_form(self):
        errors = super().commit_form()
        if self.current and self.current[0] == "scenario" and self.form:
            s = store.find_scenario(self.data, self.current[1])
            if s:
                self.KINDS[s["kind"]].commit_extra(s["settings"], errors)
        return errors

    def tree_account_text(self, account):
        return account["name"]

    def new_account(self, name):
        return store.new_account(self.data, name)

    def new_scenario(self, name, kind):
        s = store.new_scenario(self.data, name, kind)
        if kind == store.MONITOR:
            # Lay san Telegram cua kich ban theo doi khac de khoi nhap lai.
            others = [x["settings"] for x in self.data["scenarios"]
                      if x["kind"] == store.MONITOR and x["settings"].get("telegram_token")]
            if others:
                s["settings"]["telegram_token"] = others[0]["telegram_token"]
                s["settings"]["telegram_chat_id"] = others[0]["telegram_chat_id"]
        return s

    def account_extra(self, parent, account):
        """Tab Tai khoan: nhom tai khoan (loc / tick nhanh trong kich ban) + nhom da tham gia."""
        import tkinter as tk
        from datetime import datetime
        box = ui.section(parent, "Phân loại & nhóm Facebook")
        row = ttk.Frame(box)
        row.pack(anchor="w", pady=(0, 6))
        ttk.Label(row, text="Nhóm tài khoản:").pack(side="left")
        values = ["(chưa phân loại)"] + self.data["account_groups"]
        var = tk.StringVar(value=account.get("group") or values[0])
        combo = ttk.Combobox(row, values=values, textvariable=var, state="readonly", width=24)
        combo.pack(side="left", padx=(6, 0))

        def set_group(_e=None):
            account["group"] = "" if var.get() == values[0] else var.get()
            self.mark_dirty()
            self.refresh_tree(f"account:{account['id']}")
        combo.bind("<<ComboboxSelected>>", set_group)
        ttk.Label(box, text="Thêm nhóm bằng nút '＋ Nhóm tài khoản'. Trong kịch bản → '👥 Tài khoản chạy' lọc theo "
                            "nhóm để tick nhanh.", style="Hint.TLabel", wraplength=640).pack(anchor="w", pady=(0, 8))
        st = upstt_store.join_state(account["id"])
        waiting = [k for k, g in st.items() if g.get("status") in upstt_store.JOIN_WAITING]
        if waiting:
            ttk.Label(box, text=f"Đang xin vào {len(waiting)} nhóm (⏳ chờ duyệt / ❓ cần trả lời câu hỏi) – các nhóm này "
                                "được bỏ qua khi đăng cho đến khi được duyệt. Kiểm tra ở kịch bản → '🔄 Kiểm tra duyệt'.",
                      style="Hint.TLabel", wraplength=640).pack(anchor="w")

    def schedule_key(self, entries):
        return [(e["task"], e.get("every"), e.get("max"), e.get("times"), e.get("weekdays")) for e in entries]

    # ================================================================ task 003: Ca nhan & Page, gop tai khoan
    def identities_tab(self, parent, account):
        """Tab tai khoan: danh tinh cua nick (Ca nhan + Page) + nut 'Doc danh sach Page'."""
        from datetime import datetime
        box = ui.Box(parent, text="Cá nhân & Page của nick")
        box.pack(fill="x")
        if self.account_usable(account):
            box.add_button("🔄 Đọc danh sách Page", lambda: self.read_identities(account))
        try:
            import fb_login
            read_at = fb_login.load_identities_file(self.account_dir(account)).get("time") or 0
        except Exception:
            read_at = 0
        ttk.Label(box, text=(f"Đọc từ Facebook lúc {datetime.fromtimestamp(read_at):%H:%M %d/%m}" if read_at else
                             "Chưa đọc danh sách Page – bấm '🔄 Đọc danh sách Page' (tool mở Facebook chạy ngầm, chỉ "
                             "xem; nick có nhiều Page có thể mất vài phút)."), style="Hint.TLabel").pack(anchor="w")
        identities = store.account_identities(account)
        tbox, tree = PostKind.make_table(box, [("name", "Danh tính", 260, True, "w"), ("kind", "Loại", 90, False, "w"),
                                               ("used", "Kịch bản đăng bằng", 140, False, "w"),
                                               ("note", "Ghi chú", 220, False, "w")],
                                         height=max(2, min(8, len(identities))))
        tbox.pack(fill="x", pady=(6, 0))
        for x in identities:
            used = sum(1 for s in self.data["scenarios"] if account["id"] in s["accounts"]
                       and post_as(s, account["id"]) == x["id"])
            tree.insert("", "end", values=(x.get("name") or x["id"], "👤 Cá nhân" if x["id"] == "self" else "📄 Page",
                                           used or "—", "⚠ lần đọc gần nhất không thấy" if x.get("missing") else ""),
                        tags=["warn"] if x.get("missing") else [])
        ui.fit_wrap(ttk.Label(box, text="1 nick = 1 tài khoản trong tool (1 Chrome, đăng nhập 1 lần). Muốn đăng bằng Page: "
                                        "mở kịch bản → '👥 Tài khoản chạy' → bấm ô 'Đăng bằng' của tài khoản này. Tool "
                                        "tự chuyển sang Page khi chạy và chuyển về Cá nhân khi xong. Page không còn "
                                        "thấy vẫn giữ (kịch bản đang trỏ tới) – chọn lại 'Đăng bằng' nếu cần.",
                              style="Hint.TLabel", justify="left"), box).pack_configure(pady=(6, 0))

    def read_identities(self, account, then=None):
        """Chay '--read-identities --account aN' -> doc danh_tinh.json -> update_identities -> Luu."""
        import fb_login
        acc_dir = self.account_dir(account)

        def handle(_acc, code):
            if code == 3:
                messagebox.showwarning("Đọc danh sách Page", f"'{account['name']}' chưa đăng nhập Facebook.")
                return
            if code == 4:
                messagebox.showwarning("Đọc danh sách Page", f"'{account['name']}' đang chạy (đăng bài / quét) – "
                                                             "đợi vài phút rồi bấm lại.")
                return
            try:
                found = fb_login.load_identities_file(acc_dir).get("identities") or []
                res = store.update_identities(account, found) if code == 0 else None
            except Exception:
                res = None
            if res is None:
                p = ui.fb_login_progress(acc_dir)
                messagebox.showwarning("Đọc danh sách Page", "Chưa đọc được danh sách Page"
                                       + (f": {p['text']}" if p.get("text") else ".") + "\nThử lại sau ít phút.")
                return
            self.mark_dirty()
            self.save(quiet=True)
            pages = len(store.account_identities(account)) - 1
            parts = [f"{pages} Page"] + ([f"mới: {', '.join(res['added'])}"] if res["added"] else []) \
                + ([f"đổi tên: {', '.join(f'{a} → {b}' for a, b in res['renamed'])}"] if res["renamed"] else []) \
                + ([f"không còn thấy: {', '.join(res['missing'])}"] if res["missing"] else [])
            self.flash(f"👤 {account['name']}: Cá nhân + " + " · ".join(parts))
            if self.current == ("account", account["id"]):
                self.on_select(force=True)
            if then:
                then()
        if self.has_changes() and not self.save(quiet=True):
            return
        self.KINDS[store.POST].run_accounts([(account, ["--read-identities"])], "Đọc danh sách Page", on_each=handle)
        self.flash(f"⏳ Đang đọc danh sách Page của '{account['name']}' (chạy ngầm, chỉ xem)…")

    def same_nick_banner(self, parent, account):
        """Canh bao 'N tai khoan chung 1 nick' o trang tai khoan + nut Gop vao …"""
        group = next((g for g in store.same_uid_groups(self.data) if account["id"] in g), None)
        if not group:
            return
        bar = ttk.Frame(parent, padding=(10, 6))
        bar.pack(fill="x", pady=(6, 0))
        names = ", ".join(f"'{store.find_account(self.data, i)['name']}'" for i in group)
        ui.fit_wrap(ttk.Label(bar, text=f"⚠ {len(group)} tài khoản chung 1 nick Facebook: {names}. Facebook thấy 1 người "
                                        "đăng nhập trên nhiều Chrome → dễ bị đá cả các phiên. Nên gộp thành 1 tài khoản "
                                        "(Page thành 'Đăng bằng').", style="Warn.TLabel", justify="left"), bar)
        ttk.Button(bar, text="Gộp vào …", style="Accent.TButton" if ui.sv_ttk else "TButton",
                   command=lambda: self.merge_dialog(group)).pack(anchor="e", pady=(4, 0))

    def extra_alerts(self):
        out = self._license_alerts()
        for group in store.same_uid_groups(self.data):
            names = ", ".join(store.find_account(self.data, i)["name"] for i in group)
            out.append(("warn", f"{len(group)} tài khoản chung 1 nick: {names}",
                        "1 nick nên là 1 tài khoản (Page chọn ở 'Đăng bằng') – bấm Gộp, có hộp xác nhận",
                        "Gộp vào …", lambda g=group: self.merge_dialog(g)))
        left = store.merged_leftovers(self.data)
        if left:
            out.append(("warn", f"Chrome của {len(left)} tài khoản đã gộp chưa đăng xuất / xoá được: {', '.join(left)}",
                        "đăng xuất Facebook + xoá Chrome thừa để Facebook không thấy nhiều thiết bị", "Thử lại",
                        self.retry_merged_logout))
        return out

    def merge_dialog(self, group):
        """Hop 'Gop vao …': chon tai khoan chinh (cau PM 10) -> xem truoc (merge_plan) -> Gop."""
        import tkinter as tk
        names = {i: store.find_account(self.data, i)["name"] for i in group}
        win = tk.Toplevel(self.root)
        win.title("Gộp tài khoản chung 1 nick")
        win.geometry("720x520")
        win.transient(self.root)
        frame = ttk.Frame(win, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"🔄  Gộp {len(group)} tài khoản chung 1 nick Facebook", style="Title.TLabel").pack(anchor="w")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(8, 6))
        ttk.Label(row, text="Tài khoản chính (giữ Chrome + đăng nhập):").pack(side="left")
        labels = [f"{names[i]}  ({i})" for i in group]
        main_var = tk.StringVar(value=labels[group.index(store.default_merge_main(self.data, group))])
        combo = ttk.Combobox(row, values=labels, textvariable=main_var, state="readonly", width=30)
        combo.pack(side="left", padx=(8, 0))
        bf, text = ui.text_box(frame, 14, wrap="word")
        bf.pack(fill="both", expand=True)
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x", pady=(10, 0))
        go = ttk.Button(bottom, text="Gộp", style="Accent.TButton" if ui.sv_ttk else "TButton")
        go.pack(side="right")
        ttk.Button(bottom, text="Hủy", command=win.destroy).pack(side="right", padx=(0, 8))
        read_btn = ttk.Button(bottom, text="🔄 Đọc danh sách Page của tài khoản chính")
        read_btn.pack(side="left")
        state = {}

        def main_id():
            return group[labels.index(main_var.get())]

        def show():
            mid = main_id()
            plan = store.merge_plan(self.data, mid, [i for i in group if i != mid])
            state["plan"] = plan
            body = plan["lines"] if plan["ok"] else (["⛔ Chưa gộp được:"] + [f"  • {e}" for e in plan["errors"]])
            text.configure(state="normal")
            text.delete("1.0", "end")
            text.insert("1.0", "\n".join(body))
            text.configure(state="disabled")
            go.state(["!disabled"] if plan["ok"] else ["disabled"])
            read_btn.state(["!disabled"] if self.account_usable(store.find_account(self.data, mid)) else ["disabled"])

        def read():
            win.destroy()
            self.read_identities(store.find_account(self.data, main_id()), then=lambda: self.merge_dialog(group))

        def run():
            mid = main_id()
            running = [names[i] for i in group if i in self.busy_accounts or i in self._checks
                       or ui.account_process_alive(self.account_dir({"id": i}))]
            if running:
                messagebox.showwarning("Gộp", "Đang chạy: " + ", ".join(running) + ".\n\nĐợi chạy xong (hoặc bấm ⏸ Tạm "
                                       "dừng toàn bộ) rồi gộp lại.", parent=win)
                return
            self.commit_form()
            from datetime import datetime
            try:
                res = store.merge_accounts(self.data, mid, [i for i in group if i != mid],
                                           datetime.now().strftime("%Y%m%d_%H%M%S"), state["plan"])
            except OSError as e:
                messagebox.showerror("Gộp", f"Chép dữ liệu lỗi – CHƯA gộp, cấu hình chưa đổi.\n\n{e}", parent=win)
                return
            win.destroy()
            if not res.get("done"):
                return
            self.mark_dirty()
            self.save(quiet=True)
            self.refresh_tree(f"account:{mid}")
            self.select(f"account:{mid}")
            self.logout_merged([(i, names[i]) for i in res["logout"]], f"Đã gộp vào '{names[mid]}' (sao lưu: "
                                                                          f"{res['backup']}).")
        combo.bind("<<ComboboxSelected>>", lambda _e: show())
        read_btn.configure(command=read)
        go.configure(command=run)
        show()
        win.grab_set()

    def logout_merged(self, items, head=""):
        """'--logout --account <phu>' tung tai khoan da gop; loi -> canh bao (merged_leftovers + nut Thu lai)."""
        failed = []
        jobs = [({"id": i, "name": n}, ["--logout"]) for i, n in items]
        if not jobs:
            return

        def each(acc, code):
            if code != 0:
                failed.append(acc["name"])

        def done():
            if failed:
                messagebox.showwarning("Đăng xuất tài khoản đã gộp", (head + "\n\n" if head else "") +
                                       "Chưa đăng xuất / xoá được Chrome của: " + ", ".join(failed) +
                                       ".\n\nTrang Tổng quan sẽ hiện cảnh báo + nút 'Thử lại'.")
            else:
                self.flash((head + " " if head else "") + "Đã đăng xuất + xoá Chrome của tài khoản phụ.")
            if self.page == "home":
                self.refresh_page()
        self.KINDS[store.POST].run_accounts(jobs, "Đăng xuất tài khoản đã gộp", done=done, on_each=each)

    def retry_merged_logout(self):
        self.logout_merged([(i, i) for i in store.merged_leftovers(self.data)])


def main():
    ui.run(ToolApp)


if __name__ == "__main__":
    main()
