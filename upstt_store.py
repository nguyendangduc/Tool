# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
"""Du lieu cua tool dang bai: Tai khoan -> Nhom noi dung (config.json).

Dung chung cho fb_upstt.py (chay dang bai), upstt_gui.py (giao dien) va setup.ps1 (qua fb_upstt.py).

Cau truc config.json:
{
  "accounts": [
    {"id": "a1", "name": "Tai khoan 1", "campaigns": [
        {"id": "c1", "name": "Khach san thu cung", "enabled": true,
         "groups": ["https://www.facebook.com/groups/..."], "share_text": "...",
         "times": ["06:30", "19:00"],
         "link_load_wait": 5, "post_wait": 6, "group_switch_wait": 6, "headless": true}
    ]}
  ]
}
Moi tai khoan co trinh duyet rieng: accounts/<id>/browser_profile.

Ban gop (FacebookTool): config.json dung chung voi tool theo doi; moi muc co "kind" ("post" | "monitor").
load() chi tra ve cac muc "post" (fb_upstt.py khong thay muc theo doi). Giao dien doc/ghi qua tool_store.py.
"""
import json
import math
import re
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_JSON = BASE_DIR / "config.json"
LEGACY_TXT = BASE_DIR / "fb_upstt_config.txt"
ACCOUNTS_DIR = BASE_DIR / "accounts"
KIND = "post"

CAMPAIGN_DEFAULTS = {
    "enabled": True,
    "groups": [],
    "share_text": "",
    "media_folder": "",     # thu muc anh / video dinh kem ("" = chi dang chu), xem media_files()
    "media_count": 1,       # so file dinh kem moi bai (toi thieu neu co media_count_max)
    "media_count_max": 0,   # >0 va > media_count: moi bai lay ngau nhien tu media_count den media_count_max file
    "max_groups_per_run": 0,  # >0: moi luot chi dang toi da bay nhieu nhom (uu tien nhom lau chua dang); 0 = tat ca
    "times": [],
    "weekdays": [],         # thu trong tuan duoc dang (0=T2 .. 6=CN); [] = tat ca cac ngay
    "care_text": "",        # noi dung luu san de copy khi vao cham bai (B1); nguoi dung tu dan tay
    "join_answer": "",      # cau tra loi mau cho cau hoi tham gia nhom ("" = cau mac dinh fb_login.DEFAULT_JOIN_ANSWER)
    "join_wave": True,      # vao nhom xong bam 'Vay tay chao' / 'Xin chao' (neu Facebook co nut)
    "link_load_wait": 5,
    "post_wait": 6,
    "group_switch_wait": 6,
    "headless": True,
}
# Thoi gian cho khi dang bai (giay) - co dinh, khong cho sua tren giao dien.
LINK_LOAD_WAIT = 5      # cho sau khi dan link
POST_WAIT = 6           # cho sau khi bam Dang
GROUP_SWITCH_WAIT = 6   # cho giua 2 nhom
TIME_RE = re.compile(r"(\d{1,2})[:h.](\d{2})")
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
MEDIA_MAX = 10              # Facebook cho nhieu hon, nhung nhieu file -> tai lau, de loi
MEDIA_UPLOAD_SECONDS = 8    # uoc tinh thoi gian tai 1 anh (video tinh 60s)


def media_all(campaign):
    """Tat ca file anh / video trong thu muc (theo ten); khong co thu muc -> []."""
    folder = (campaign.get("media_folder") or "").strip()
    if not folder or not Path(folder).is_dir():
        return []
    return sorted((f for f in Path(folder).iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXT | VIDEO_EXT),
                  key=lambda f: f.name.lower())


def media_count_range(campaign):
    """(min, max) so file dinh kem moi bai."""
    lo = max(1, min(MEDIA_MAX, int(campaign.get("media_count") or 1)))
    hi = int(campaign.get("media_count_max") or 0)
    hi = lo if hi < lo else min(MEDIA_MAX, hi)
    return lo, hi


def media_files(campaign):
    """File dinh kem CO DINH (lo file dau theo ten) - dung de uoc tinh / hien thi."""
    lo, _hi = media_count_range(campaign)
    return media_all(campaign)[:lo]


def media_pick(campaign):
    """Chon file dinh kem cho MOT bai: ngau nhien tu `min` den `max` file (neu max>min), lay theo thu tu ten."""
    import random
    files = media_all(campaign)
    if not files:
        return []
    lo, hi = media_count_range(campaign)
    n = random.randint(lo, hi) if hi > lo else lo
    return files[:min(n, len(files))]


# ------------------------------------------------------------------ doc / ghi
def account_dir(account_id):
    """Thu muc rieng cua tai khoan (chua browser_profile/)."""
    path = ACCOUNTS_DIR / account_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def load():
    if not CONFIG_JSON.exists():
        data = migrate_legacy() if LEGACY_TXT.exists() else {"accounts": []}
        data["rules"] = rules(data)
        save(data)
        return data
    data = json.loads(CONFIG_JSON.read_text(encoding="utf-8"))
    data["rules"] = rules(data)
    apply_rules(data)
    for account in data.setdefault("accounts", []):
        account["campaigns"] = [c for c in account.setdefault("campaigns", []) if c.get("kind", KIND) == KIND]
        for campaign in account["campaigns"]:
            for key, value in CAMPAIGN_DEFAULTS.items():
                campaign.setdefault(key, value if not isinstance(value, list) else list(value))
    return data


def save(data):
    apply_rules(data)
    if CONFIG_JSON.exists():
        shutil.copy(CONFIG_JSON, CONFIG_JSON.with_suffix(".json.bak"))
    tmp = CONFIG_JSON.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_JSON)


def new_id(data, prefix):
    used = {a["id"] for a in data["accounts"]}
    used |= {c["id"] for a in data["accounts"] for c in a["campaigns"]}
    n = 1
    while f"{prefix}{n}" in used:
        n += 1
    return f"{prefix}{n}"


def find_account(data, account_id):
    return next((a for a in data["accounts"] if a["id"] == account_id), None)


def find_campaign(data, campaign_id):
    for account in data["accounts"]:
        for campaign in account["campaigns"]:
            if campaign["id"] == campaign_id:
                return account, campaign
    return None, None


# ------------------------------------------------------------------ chuyen tu ban cu
def read_legacy_txt(path):
    values = {}
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            key, value = s.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def campaign_from_legacy(values, campaign_id, name):
    def as_int(key, default):
        try:
            return int(values.get(key, default))
        except ValueError:
            return default

    return {
        "id": campaign_id,
        "name": name,
        "enabled": True,
        "groups": [x.strip() for x in values.get("GROUP_URLS", "").split("|") if x.strip()],
        "share_text": values.get("SHARE_URL", ""),
        "times": normalize_times(values.get("SCHEDULE_TIMES", "").split("|"))[0],
        "link_load_wait": as_int("LINK_LOAD_WAIT_SECONDS", 5),
        "post_wait": as_int("POST_WAIT_SECONDS", 6),
        "group_switch_wait": as_int("GROUP_SWITCH_WAIT_SECONDS", 6),
        "headless": values.get("HEADLESS", "true").strip().lower() in ("1", "true", "yes", "on"),
    }


def migrate_legacy():
    """Ban cu (1 tai khoan, fb_upstt_config.txt) -> config.json, giu nguyen dang nhap."""
    values = read_legacy_txt(LEGACY_TXT)
    data = {"accounts": [{"id": "a1", "name": "Tài khoản 1",
                          "campaigns": [campaign_from_legacy(values, "c1", "Nội dung 1")]}]}
    old_profile = BASE_DIR / "browser_profile"
    if old_profile.exists():
        target = ACCOUNTS_DIR / "a1"
        target.mkdir(parents=True, exist_ok=True)
        if not (target / "browser_profile").exists():
            shutil.move(str(old_profile), str(target / "browser_profile"))
        old_lock = BASE_DIR / "browser_profile.lock"
        if old_lock.exists():
            try:
                old_lock.unlink()
            except OSError:
                pass
    LEGACY_TXT.rename(LEGACY_TXT.with_name(LEGACY_TXT.name + ".da_chuyen"))
    return data


# ------------------------------------------------------------------ kiem tra
def normalize_times(raw_times):
    """['6:30', '19h00'] -> (['06:30', '19:00'], loi)."""
    good, errors = [], []
    for t in raw_times:
        t = t.strip()
        if not t:
            continue
        m = TIME_RE.fullmatch(t)
        if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
            errors.append(t)
        else:
            good.append(f"{int(m.group(1)):02d}:{m.group(2)}")
    return sorted(set(good)), errors


JOIN_FILE = "xin_vao_nhom.json"   # trang thai xin vao nhom cua tai khoan: {slug: {status, time, url}}
JOIN_WAITING = ("pending", "questions")   # chua la thanh vien -> luot dang bo qua nhom nay


def join_state(account_id):
    """{slug: {status, ...}}: trang thai xin vao nhom + cac nhom da doc duoc la 'da tham gia' (nhom_da_vao.json)."""
    try:
        st = json.loads((ACCOUNTS_DIR / account_id / JOIN_FILE).read_text(encoding="utf-8"))
    except Exception:
        st = {}
    try:
        joined = json.loads((ACCOUNTS_DIR / account_id / "nhom_da_vao.json").read_text(encoding="utf-8"))["groups"]
    except Exception:
        joined = []
    for g in joined:
        if g.get("slug") and st.get(g["slug"], {}).get("status") != "joined":
            st[g["slug"]] = {"status": "joined", "url": g.get("url", "")}
    return st


def campaign_groups(account_id, campaign):
    """Nhom cua muc (dung chung moi tai khoan chay kich ban)."""
    return campaign["groups"]


def run_group_count(campaign, account_id=None):
    """So nhom 1 luot dang (sau gioi han max_groups_per_run)."""
    n = len(campaign["groups"])
    cap = int(campaign.get("max_groups_per_run") or 0)
    return min(n, cap) if cap else n


def estimate_minutes(campaign, account_id=None):
    """Uoc tinh thoi gian dang xong 1 luot (phut): moi nhom ~ cho + 20s thao tac."""
    per_group = LINK_LOAD_WAIT + POST_WAIT + GROUP_SWITCH_WAIT + 20
    per_group += sum(60 if f.suffix.lower() in VIDEO_EXT else MEDIA_UPLOAD_SECONDS for f in media_files(campaign))
    return max(3, math.ceil(run_group_count(campaign, account_id) * per_group / 60) + 1)


def safe_gap_minutes(campaign, account_id=None):
    """Khoang cach NEN de giua 2 luot cung nick: do thuc te luot co loi ~2 phut/nhom (cho het han tai trang)."""
    return run_group_count(campaign, account_id) * 2 + 2


def to_minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def validate(data):
    """Tra ve danh sach loi (rong = hop le)."""
    errors = []
    if not data["accounts"]:
        errors.append("Chưa có tài khoản nào.")
    for account in data["accounts"]:
        enabled = [c for c in account["campaigns"] if c["enabled"]]
        for c in enabled:
            where = f"[{account['name']} › {c['name']}]"
            if not c["groups"]:
                errors.append(f"{where} Chưa có nhóm Facebook.")
            bad = [g for g in c["groups"] if "facebook.com" not in g and "fb.com" not in g]
            if bad:
                errors.append(f"{where} Không phải link Facebook: {bad[0]}")
            folder = (c.get("media_folder") or "").strip()
            if folder and not Path(folder).is_dir():
                errors.append(f"{where} Không thấy thư mục ảnh/video: {folder}")
            elif folder and not media_files(c):
                errors.append(f"{where} Thư mục ảnh/video không có file ảnh / video nào: {folder}")
            if not c["share_text"].strip() and not media_files(c):
                errors.append(f"{where} Chưa có nội dung / link bài cần chia sẻ.")
            if not c["times"]:
                errors.append(f"{where} Chưa có giờ đăng.")

    # Cung 1 nick Facebook (cung tai khoan, hoac nhieu tai khoan la cac Page cua cung 1 nick)
    # -> chi 1 trinh duyet mo nick do tai 1 thoi diem -> cac luot dang khong duoc chong nhau.
    pools = {}
    for account in data["accounts"]:
        pools.setdefault(nick_key(account), []).append(account)
    for accounts in pools.values():
        names = {a["name"] for a in accounts}
        slots = sorted(
            (to_minutes(t), f"{a['name']} › {c['name']}" if len(names) > 1 else c["name"],
             estimate_minutes(c, a["id"]), t, safe_gap_minutes(c, a["id"]))
            for a in accounts for c in a["campaigns"] if c["enabled"] for t in c["times"]
        )
        label = accounts[0]["name"] if len(names) == 1 else "Cùng 1 tài khoản Facebook: " + ", ".join(sorted(names))
        for i, (start, name, need, t, safe) in enumerate(slots):
            if len(slots) < 2:
                break
            nxt_start, nxt_name, _, nxt_t, _ = slots[(i + 1) % len(slots)]
            gap = (nxt_start - start) % 1440
            if (i + 1) % len(slots) == i:
                continue
            if gap < need:
                why = ("Cùng 1 tài khoản Facebook mà đăng chồng giờ thì dễ LỖI (Facebook tải trang không kịp, "
                       "không mở được ô đăng bài).")
                if gap == 0:
                    errors.append(f"[{label}] Trùng giờ {t}: '{name}' và '{nxt_name}'. {why} "
                                  f"Nên để cách nhau khoảng {safe} phút.")
                else:
                    errors.append(f"[{label}] '{name}' lúc {t} cần ít nhất {need} phút để đăng xong "
                                  f"(Facebook chậm có thể tới {safe} phút), nhưng '{nxt_name}' bắt đầu lúc {nxt_t} "
                                  f"(chỉ cách {gap} phút). {why} Nên để cách nhau khoảng {safe} phút.")
    return errors


# ------------------------------------------------------------------ nhom tam nghi (theo tung tai khoan)
# fb_upstt.py ghi, giao dien doc de hien ghi chu + nut Reset.
GROUP_STATE_FILE = "nhom_tam_nghi.json"
GROUP_STREAK = 2             # bao nhieu luot LIEN TIEP gap loi do nhom thi ngung nhom
GROUP_PAUSE = {              # loai loi -> (so ngay nghi, giai thich)
    "chua_vao": (1, "tài khoản chưa được duyệt vào nhóm / nhóm bắt trả lời câu hỏi tham gia"),
    "chan_han": (7, "nhóm chỉ cho quản trị viên đăng bài / nhóm không mở được (bị xoá, tài khoản bị mời ra khỏi nhóm) "
                    "– nên xoá nhóm này khỏi danh sách"),
}
PENDING_LIMIT = 2            # nhom dang co tu bay nhieu bai cho duyet -> bo qua luot nay
PENDING_WARN_DAYS = 7        # bo qua lien tuc bay nhieu ngay -> canh bao nen bo nhom


def load_group_state(acc_dir):
    try:
        st = json.loads((Path(acc_dir) / GROUP_STATE_FILE).read_text(encoding="utf-8"))
    except Exception:
        st = {}
    st.setdefault("groups", {})
    st.setdefault("pending", {})
    return st


def save_group_state(acc_dir, st):
    try:
        (Path(acc_dir) / GROUP_STATE_FILE).write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def _when(ts):
    from datetime import datetime
    return f"{datetime.fromtimestamp(ts):%H:%M %d/%m}"


def pause_notes(account, campaign):
    """Ghi chu cho giao dien: [{'kind': 'account'|'group'|'pending', 'key', 'text', 'reset': bool}]."""
    import time
    import fb_login
    acc_dir = ACCOUNTS_DIR / account["id"]
    notes = []
    pause = fb_login.nick_pause(acc_dir)
    if pause:
        notes.append({"kind": "account", "key": "", "reset": True, "until": pause["until"],
                      "reason": pause.get("reason", ""),
                      "text": f"Tài khoản '{account['name']}' nghỉ CẢ đăng bài + bình luận đến "
                              f"{fb_login.pause_text(pause)} – {pause.get('reason', '')}"})
    elif fb_login.recovering(acc_dir):
        notes.append({"kind": "recovering", "key": "", "reset": True,
                      "text": f"Tài khoản '{account['name']}' vừa hết nghỉ → hôm nay chỉ đăng nửa số nhóm cho an toàn"})
    st = load_group_state(acc_dir)
    mine = {group_key(g) for g in campaign_groups(account["id"], campaign)}
    now = time.time()
    for key, g in st["groups"].items():
        if key in mine and g.get("until", 0) > now:
            notes.append({"kind": "group", "key": key, "reset": True, "until": g["until"], "fault": g.get("kind", ""),
                          "text": f"Nhóm {key}: ngừng đăng đến {_when(g['until'])} – {g.get('reason', '')}"})
    for key, p in st["pending"].items():
        if key in mine:
            days = int((now - p.get("since", now)) // 86400)
            extra = (f" – đã {days} ngày quản trị viên không duyệt, nên cân nhắc bỏ nhóm"
                     if days >= PENDING_WARN_DAYS else "")
            notes.append({"kind": "pending", "key": key, "reset": True, "count": p.get("count", 0), "days": days,
                          "text": f"Nhóm {key}: đang có {p.get('count', '?')} bài chờ duyệt → tạm bỏ qua, "
                                  f"tự đăng lại khi quản trị viên duyệt / xoá bớt (Reset = lần tới vẫn đăng){extra}"})
    return notes


def reset_pause(account, kind, key):
    """Nut Reset: bo nghi thu cong."""
    import fb_login
    acc_dir = ACCOUNTS_DIR / account["id"]
    if kind in ("account", "recovering"):
        fb_login.clear_nick_pause(acc_dir)
        return
    st = load_group_state(acc_dir)
    if kind == "pending":
        # Lan dang toi van dang vao nhom nay 1 lan, bo qua kiem tra so bai cho duyet.
        import time
        st["pending"].pop(key, None)
        st.setdefault("force", {})[key] = time.time()
    st["groups"].pop(key, None)
    save_group_state(acc_dir, st)


MAX_POSTS_PER_GROUP_DAY = 1   # quan tri vien thay 1 nhom nhan > 1 bai/ngay cung noi dung -> de chan


def group_key(url):
    """Link nhom -> khoa so sanh (bo ?query, /, chu hoa)."""
    return re.sub(r"[?#].*$", "", (url or "").strip()).rstrip("/").lower().split("facebook.com/")[-1]


def warnings(data):
    """Canh bao (KHONG chan luu): nhom nhan qua nhieu bai/ngay, hoac nhieu nick cung dang 1 nhom."""
    per_group = {}
    for account in data["accounts"]:
        for c in account["campaigns"]:
            if not c["enabled"]:
                continue
            for g in campaign_groups(account["id"], c):
                info = per_group.setdefault(group_key(g), {"posts": 0, "nicks": set(), "names": set()})
                info["posts"] += len(c["times"])
                info["nicks"].add(nick_key(account))
                info["names"].add(account["name"])
    lines = []
    for key, info in sorted(per_group.items(), key=lambda x: -x[1]["posts"]):
        problems = []
        if info["posts"] > MAX_POSTS_PER_GROUP_DAY:
            problems.append(f"{info['posts']} bài/ngày")
        if len(info["nicks"]) > 1:
            problems.append(f"{len(info['nicks'])} tài khoản cùng đăng ({', '.join(sorted(info['names']))})")
        if problems:
            lines.append(f"{key}: " + " · ".join(problems))
    if not lines:
        return []
    shown = lines[:8] + ([f"… và {len(lines) - 8} nhóm khác"] if len(lines) > 8 else [])
    return [f"{len(lines)} nhóm đang nhận quá nhiều bài – quản trị viên dễ để chờ duyệt / gỡ bài / chặn tài khoản. "
            f"Nên: mỗi nhóm chỉ 1 tài khoản đăng, tối đa {MAX_POSTS_PER_GROUP_DAY} bài/ngày."] + shown


def nick_key(account):
    """uid Facebook cua tai khoan (cac Page cua cung 1 nick co chung uid); chua biet -> theo tai khoan."""
    try:
        uid = json.loads((ACCOUNTS_DIR / account["id"] / "fb_profile.json").read_text(encoding="utf-8")).get("uid", "")
    except Exception:
        uid = ""
    return f"uid:{uid}" if uid else f"acc:{account['id']}"


def account_usable(account):
    """Tai khoan dang dang nhap hop le (xem account_status)."""
    import account_status
    return account_status.usable(ACCOUNTS_DIR / account["id"])


def schedule_entries(data):
    """Cac nhom noi dung dang bat cua tai khoan hop le, de setup.ps1 tao lich.

    Tool dang 'Tam dung toan bo' hoac tai khoan het han / chua dang nhap -> khong tao lich.
    """
    if data.get("paused"):
        return []
    return [
        {"task": c["id"], "account": a["id"], "args": f"--once --campaign {c['id']}",
         "name": f"{a['name']} › {c['name']}", "times": c["times"],
         "weekdays": sorted(set(c.get("weekdays") or []))}
        for a in data["accounts"] if account_usable(a)
        for c in a["campaigns"] if c["enabled"] and c["times"]
    ]


WEEKDAY_NAMES = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
WEEKDAY_PS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def weekdays_text(weekdays):
    days = sorted(set(weekdays or []))
    if not days or len(days) == 7:
        return "hằng ngày"
    return "Thứ: " + ", ".join(WEEKDAY_NAMES[d] for d in days)


# ------------------------------------------------------------------ rule khi loi (tab Setting nang cao)
# (tieu de, [phan]). phan: ('text', chu) | ('line', chu co {}, [o so]) | ('grid', [(nhan, dong tu, o so, don vi)])
# | ('tip', chu). o so: (khoa, mac dinh, nho nhat, lon nhat). Ap dung cho CA tool.
RULE_SPEC = [
    ("① Facebook báo \"bạn đăng quá nhiều\" (chống spam)", [
        ("text", "→ Tool nghỉ CẢ tài khoản, không đăng gì:"),
        ("grid", [("Bị lần đầu:", "nghỉ", ("pause_h1", 48, 1, 720), "giờ"),
                  ("Bị lần thứ 2:", "nghỉ", ("pause_h2", 72, 1, 720), "giờ"),
                  ("Bị lần thứ 3 trở đi:", "nghỉ", ("pause_h3", 168, 1, 2160), "giờ")]),
        ("line", "→ Nếu {} ngày liền không bị lại, lần sau được tính là \"lần đầu\".",
         [("strike_reset_days", 14, 1, 90)]),
        ("line", "→ Nghỉ xong, trong {} giờ đầu tool chỉ đăng một nửa số nhóm cho an toàn.",
         [("recovery_hours", 24, 0, 168)]),
        ("tip", "💡 Ví dụ: bị lần đầu lúc 8h sáng thứ 2 → tool đăng lại từ 8h sáng thứ 4."),
    ]),
    ("② Không đăng được vào một nhóm", [
        ("line", "→ Phải lỗi {} lần liền ở nhóm đó thì tool mới tạm bỏ nhóm.", [("group_streak", 2, 1, 10)]),
        ("grid", [("Do chưa được duyệt vào nhóm:", "bỏ", ("pause_not_member_days", 1, 1, 60), "ngày"),
                  ("Do nhóm chỉ cho quản trị viên đăng / bị xoá:", "bỏ", ("pause_blocked_days", 7, 1, 90), "ngày")]),
        ("tip", "💡 Ví dụ: 2 lần đăng liền bị báo \"chưa vào nhóm\" → 1 ngày sau tool mới thử lại."),
    ]),
    ("③ Bài cũ của bạn trong nhóm còn chờ duyệt", [
        ("line", "→ Nhóm đang có từ {} bài chờ duyệt trở lên thì tool không đăng thêm.",
         [("pending_limit", 2, 1, 50)]),
        ("line", "→ Nếu cứ như vậy {} ngày liền, tool nhắc bạn nên bỏ nhóm.", [("pending_warn_days", 7, 1, 90)]),
        ("tip", "💡 Đăng chồng lên bài chưa duyệt dễ bị quản trị viên chặn."),
    ]),
    ("④ Đăng quá dày vào một nhóm", [
        ("line", "→ Nếu 1 nhóm nhận quá {} bài/ngày (cộng mọi nội dung, mọi tài khoản), tool cảnh báo khi bạn bấm Lưu.",
         [("max_posts_group_day", 1, 1, 20)]),
        ("tip", "💡 Chỉ cảnh báo, không tự chặn."),
    ]),
]

def _rule_slots():
    """(khoa, mac dinh, nho nhat, lon nhat) cua moi o so trong RULE_SPEC."""
    for _title, parts in RULE_SPEC:
        for part in parts:
            if part[0] == "line":
                yield from part[2]
            elif part[0] == "grid":
                yield from (row[2] for row in part[1])


RULE_DEFAULTS = {k: d for k, d, _lo, _hi in _rule_slots()}

def rules(data):
    """Bo rule khi loi cua ca tool (gia tri nguoi dung sua, thieu thi lay mac dinh)."""
    saved = data.get("rules") or {}
    return {k: int(saved.get(k, d)) for k, d in RULE_DEFAULTS.items()}


def apply_rules(data):
    """Dat rule vao cac bien tool dung khi chay (goi moi lan load / save cau hinh)."""
    r = rules(data)
    try:
        import fb_login
    except ImportError:   # chi chep rieng file cau hinh (vd khi chuyen du lieu cu)
        fb_login = None
    if fb_login:
        fb_login.ACCOUNT_PAUSE_HOURS = [r["pause_h1"], r["pause_h2"], r["pause_h3"]]
        fb_login.STRIKE_RESET_DAYS = r["strike_reset_days"]
    if fb_login:
        fb_login.RECOVERY_HOURS = r["recovery_hours"]
    global GROUP_STREAK, PENDING_LIMIT, PENDING_WARN_DAYS, MAX_POSTS_PER_GROUP_DAY
    GROUP_STREAK, PENDING_LIMIT = r["group_streak"], r["pending_limit"]
    PENDING_WARN_DAYS, MAX_POSTS_PER_GROUP_DAY = r["pending_warn_days"], r["max_posts_group_day"]
    GROUP_PAUSE["chua_vao"] = (r["pause_not_member_days"], GROUP_PAUSE["chua_vao"][1])
    GROUP_PAUSE["chan_han"] = (r["pause_blocked_days"], GROUP_PAUSE["chan_han"][1])
