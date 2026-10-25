# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
"""Du lieu cua tool theo doi nhom: Tai khoan -> Nhom theo doi (config.json).

Dung chung cho fb_monitor_v4.py (chay quet), monitor_gui.py (giao dien) va setup.ps1 (qua fb_monitor_v4.py).

- Lich quet dat THEO TAI KHOAN (moi N phut, toi da M phut/lan); moi lan quet lan luot
  tat ca nhom theo doi dang bat cua tai khoan trong cung 1 trinh duyet -> khong bao gio trung gio.
- accounts/<id>/browser_profile : dang nhap rieng cua tai khoan
- accounts/<id>/commented_ids.txt : bai da binh luan (theo tai khoan, tranh binh luan 2 lan)
- campaigns/<id>/sent_ids.txt     : bai da gui Telegram (theo nhom theo doi)
- campaigns/<id>/anh1.jpg, anh2.jpg : anh kem binh luan

Ban gop (FacebookTool): config.json dung chung voi tool dang bai; moi muc co "kind" ("post" | "monitor").
load() chi tra ve cac muc "monitor" (fb_monitor_v4.py khong thay muc dang bai). Giao dien doc/ghi qua tool_store.py.
"""
import json
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_JSON = BASE_DIR / "config.json"
LEGACY_TXT = BASE_DIR / "fb_monitor_config.txt"
ACCOUNTS_DIR = BASE_DIR / "accounts"
CAMPAIGNS_DIR = BASE_DIR / "campaigns"
KIND = "monitor"

ACCOUNT_DEFAULTS = {"run_every_minutes": 40, "max_run_minutes": 20, "headless": True}
CAMPAIGN_DEFAULTS = {
    "enabled": True,
    "groups": [],
    "keywords": [],
    "exclude_keywords": [],
    "telegram_token": "",
    "telegram_chat_id": "",
    "auto_comment": False,
    "comment_text": "",
    "comment_text_2": "",
    "ad_filter": True,
    "ad_patterns": [],
    "ad_score_rules": [],
    "ad_score_threshold": 6,
    "excluded_users": [],
    "scroll_count": 10,
    "scroll_distance": 600,
    "scroll_wait_ms": 6000,
    "see_more_wait_ms": 2000,
    "care_text": "",        # noi dung luu san de copy khi vao cham bai (B1); nguoi dung tu dan tay
    "weekdays": [],         # thu duoc quet (0 = Thu 2 ... 6 = CN); de trong = hang ngay (giong ben dang bai)
    "scan_minutes": 40,     # quet moi N phut - dat o kich ban, moi tai khoan cua kich ban dung chung
    "comment_media_folder": "",   # thu muc anh: moi binh luan lay ngau nhien 1 anh (thay anh1 / anh2 co dinh)
    # Task 003: danh tinh quet + binh luan cua muc nay - tool_store.materialize() ghi tu kich ban["post_as"].
    "post_as": "self",      # "self" = Ca nhan; chuoi so = id Page (cookie i_user), xem fb_login.ensure_identity
    "post_as_name": "",     # ten danh tinh (de bam 'Chuyen sang <ten>'); "" voi Ca nhan
}

# Cach quet - co dinh, khong cho sua tren giao dien.
SCROLL_COUNT = 15        # so lan cuon moi nhom
SCROLL_DISTANCE = 500    # px moi lan cuon
SCROLL_WAIT_MS = 1000    # cho sau moi lan cuon
SEE_MORE_WAIT_MS = 1000  # cho sau khi bam 'Xem them'

# campaign key -> key trong config kieu cu ma fb_monitor_v4.py dang doc
LEGACY_KEYS = {
    "groups": "GROUP_URLS", "keywords": "KEYWORDS", "exclude_keywords": "EXCLUDE_KEYWORDS",
    "telegram_token": "TELEGRAM_TOKEN", "telegram_chat_id": "TELEGRAM_CHAT_ID",
    "auto_comment": "AUTO_COMMENT", "comment_text": "COMMENT_TEXT", "comment_text_2": "COMMENT_TEXT_2",
    "ad_filter": "AD_FILTER", "ad_patterns": "AD_PATTERNS", "ad_score_rules": "AD_SCORE_RULES", "ad_score_threshold": "AD_SCORE_THRESHOLD",
    "excluded_users": "EXCLUDED_USERS", "scroll_count": "SCROLL_COUNT", "scroll_distance": "SCROLL_DISTANCE",
    "scroll_wait_ms": "SCROLL_WAIT_MS", "see_more_wait_ms": "SEE_MORE_WAIT_MS",
    "comment_media_folder": "COMMENT_MEDIA_FOLDER",
}


def _fill(item, defaults):
    for key, value in defaults.items():
        item.setdefault(key, list(value) if isinstance(value, list) else value)


# ------------------------------------------------------------------ doc / ghi
def account_dir(account_id):
    path = ACCOUNTS_DIR / account_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def campaign_dir(campaign_id):
    path = CAMPAIGNS_DIR / campaign_id
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
        _fill(account, ACCOUNT_DEFAULTS)
        account["campaigns"] = [c for c in account.setdefault("campaigns", []) if c.get("kind", KIND) == KIND]
        for campaign in account["campaigns"]:
            _fill(campaign, CAMPAIGN_DEFAULTS)
            merge_ad_lists(campaign)
    return data


DEFAULT_AD_POINTS = 3


def merge_ad_lists(campaign):
    """Gop 2 danh sach dau hieu quang cao cu thanh 1: 'cum tu=diem' (khong ghi diem = 3).

    Truoc day: 'Dau hieu quang cao' (+3 moi cum) va 'Dau hieu co diem rieng' (cum=diem) - cung 1 viec.
    """
    rules, seen = [], set()
    for raw in list(campaign.get("ad_score_rules", [])) + list(campaign.get("ad_patterns", [])):
        raw = raw.strip()
        if not raw:
            continue
        if "=" in raw and raw.rsplit("=", 1)[1].strip().isdigit():
            phrase, pts = raw.rsplit("=", 1)[0].strip(), raw.rsplit("=", 1)[1].strip()
        else:
            phrase, pts = raw, str(DEFAULT_AD_POINTS)
        key = phrase.lower()
        if key and key not in seen:
            seen.add(key)
            rules.append(f"{phrase}={pts}")
    campaign["ad_score_rules"] = rules
    campaign["ad_patterns"] = []


def save(data):
    apply_rules(data)
    if CONFIG_JSON.exists():
        shutil.copy(CONFIG_JSON, CONFIG_JSON.with_suffix(".json.bak"))
    tmp = CONFIG_JSON.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_JSON)


def new_id(data, prefix):
    used = {a["id"] for a in data["accounts"]} | {c["id"] for a in data["accounts"] for c in a["campaigns"]}
    used |= {p.name for d in (ACCOUNTS_DIR, CAMPAIGNS_DIR) if d.exists() for p in d.iterdir()}
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


def pause_notes(account, campaign):
    """Ghi chu cho giao dien: [{'kind': 'account'|'group', 'key', 'text', 'reset': bool}].

    Doc file do fb_monitor_v4.py ghi (binh_luan_loi.json) va fb_login (tai khoan tam nghi).
    """
    import re
    import time
    from datetime import datetime
    import fb_login
    folder = ACCOUNTS_DIR / account["id"]
    notes = []
    pause = fb_login.nick_pause(folder)
    if pause:
        notes.append({"kind": "account", "key": "", "reset": True, "until": pause["until"],
                      "reason": pause.get("reason", ""),
                      "text": f"Tài khoản '{account['name']}' nghỉ CẢ bình luận + đăng bài đến "
                              f"{fb_login.pause_text(pause)} – {pause.get('reason', '')}"})
    try:
        groups = json.loads((folder / "binh_luan_loi.json").read_text(encoding="utf-8")).get("groups", {})
    except Exception:
        groups = {}
    mine = {m.group(1) for g in campaign.get("groups", []) for m in [re.search(r"/groups/([^/?#]+)", g)] if m}
    for slug, info in groups.items():
        if slug in mine and info.get("until", 0) > time.time():
            notes.append({"kind": "group", "key": slug, "reset": True, "until": info["until"], "fault": "comment",
                          "text": f"Nhóm {slug}: ngừng tự bình luận đến "
                                  f"{datetime.fromtimestamp(info['until']):%H:%M %d/%m} – "
                                  + info.get("reason", "nhiều bài liền không thấy khung bình luận")})
    return notes


def reset_pause(account, kind, key, identity="self"):
    """Nut Reset: bo nghi thu cong (nhom: tinh lai tu dau, lan nghi sau lai tu 3 ngay).

    identity (task 003): binh_luan_loi.json nam o fb_login.identity_dir(acc_dir, identity); tam nghi CA nick
    ('account') van o acc_dir. (Khung: chua dung.)
    """
    import fb_login
    folder = ACCOUNTS_DIR / account["id"]
    if kind == "account":
        fb_login.clear_nick_pause(folder)
        return
    path = folder / "binh_luan_loi.json"
    try:
        st = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    st.get("groups", {}).pop(key, None)
    path.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")


def image_path(campaign, n):
    """Anh kem binh luan lan n (1/2) cua nhom theo doi (anh1.jpg / anh1.png...), khong co thi None."""
    folder = CAMPAIGNS_DIR / campaign["id"]
    found = sorted(folder.glob(f"anh{n}.*")) if folder.exists() else []
    return found[0] if found else None


# ------------------------------------------------------------------ doi sang config kieu cu
def to_legacy_config(campaign):
    """Nhom theo doi -> dict KEY=chuoi ma code quet hien tai dang doc."""
    config = {}
    for key, legacy in LEGACY_KEYS.items():
        value = campaign[key]
        if isinstance(value, bool):
            value = "true" if value else "false"
        elif isinstance(value, list):
            value = "|".join(str(x) for x in value)
        config[legacy] = str(value)
    config.update(SCROLL_COUNT=str(SCROLL_COUNT), SCROLL_DISTANCE=str(SCROLL_DISTANCE),
                  SCROLL_WAIT_MS=str(SCROLL_WAIT_MS), SEE_MORE_WAIT_MS=str(SEE_MORE_WAIT_MS))
    for n in (1, 2):
        path = image_path(campaign, n)
        config[f"COMMENT_IMAGE_{n}"] = str(path) if path else ""
    return config


# ------------------------------------------------------------------ chuyen tu ban cu
def _split(value):
    return [x.strip() for x in value.split("|") if x.strip()]


def migrate_legacy():
    """Ban cu (fb_monitor_config.txt, 1 tai khoan) -> config.json; giu dang nhap + lich su."""
    values = {}
    for line in LEGACY_TXT.read_text(encoding="utf-8-sig").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            key, value = s.split("=", 1)
            values[key.strip()] = value.strip()

    def as_int(key, default):
        try:
            return int(values.get(key, default))
        except ValueError:
            return default

    campaign = {"id": "c1", "name": "Nhóm theo dõi 1"}
    _fill(campaign, CAMPAIGN_DEFAULTS)
    for key, legacy in LEGACY_KEYS.items():
        if legacy not in values:
            continue
        default = CAMPAIGN_DEFAULTS[key]
        if isinstance(default, bool):
            campaign[key] = values[legacy].lower() in ("1", "true", "yes", "on")
        elif isinstance(default, list):
            campaign[key] = _split(values[legacy])
        elif isinstance(default, int):
            campaign[key] = as_int(legacy, default)
        else:
            campaign[key] = values[legacy]
    if not campaign["groups"] and values.get("GROUP_URL"):
        campaign["groups"] = [values["GROUP_URL"]]

    account = {"id": "a1", "name": "Tài khoản 1", "campaigns": [campaign],
               "run_every_minutes": as_int("RUN_EVERY_MINUTES", 40),
               "max_run_minutes": as_int("MAX_RUN_MINUTES", 20),
               "headless": values.get("HEADLESS", "true").lower() in ("1", "true", "yes", "on")}

    acc = account_dir("a1")
    camp = campaign_dir("c1")
    moves = [(BASE_DIR / "browser_profile", acc / "browser_profile"),
             (BASE_DIR / "commented_ids.txt", acc / "commented_ids.txt"),
             (BASE_DIR / "sent_ids.txt", camp / "sent_ids.txt"),
             (BASE_DIR / "facebook.jpg", camp / "anh1.jpg"),
             (BASE_DIR / "facebook2.jpg", camp / "anh2.jpg")]
    for src, dst in moves:
        if src.exists() and not dst.exists():
            shutil.move(str(src), str(dst))
    for n, name in ((1, "facebook.jpg"), (2, "facebook2.jpg")):
        downloads = Path.home() / "Downloads" / name
        if downloads.exists() and not (camp / f"anh{n}.jpg").exists():
            shutil.copy(downloads, camp / f"anh{n}.jpg")
    lock = BASE_DIR / "browser_profile.lock"
    if lock.exists():
        try:
            lock.unlink()
        except OSError:
            pass
    LEGACY_TXT.rename(LEGACY_TXT.with_name(LEGACY_TXT.name + ".da_chuyen"))
    return {"accounts": [account]}


SCAN_MINUTES = (40, 5, 1440)   # mac dinh, nho nhat, lon nhat (phut giua 2 lan quet 1 kich ban)


def scan_minutes(campaign):
    default, low, high = SCAN_MINUTES
    try:
        return min(high, max(low, int(campaign.get("scan_minutes") or default)))
    except (TypeError, ValueError):
        return default


def account_every(account):
    """Lich cua tai khoan chay theo kich ban theo doi co chu ky NGAN NHAT; moi luot chi quet kich ban da den han."""
    times = [scan_minutes(c) for c in account["campaigns"] if c.get("enabled", True)]
    return min(times) if times else account.get("run_every_minutes", SCAN_MINUTES[0])


def hang_guard_minutes(account):
    """Chot AN TOAN chong treo (khong phai gioi han quet): luot quet binh thuong tu xong khi cuon du so lan.
    Chi khi Chrome / Facebook treo moi bi ngat, de luot sau con chay duoc."""
    return max(120, account_every(account) * 3)


LAST_SCAN_FILE = "lan_quet_cuoi.txt"


def last_scan(campaign_id):
    try:
        return float((CAMPAIGNS_DIR / campaign_id / LAST_SCAN_FILE).read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return 0.0


def mark_scanned(campaign_id):
    import time
    try:
        (campaign_dir(campaign_id) / LAST_SCAN_FILE).write_text(str(time.time()), encoding="ascii")
    except OSError:
        pass


def scan_due(campaign, now=None):
    """Kich ban da den han quet chua (chua quet lan nao = den han). Lech 2 phut van tinh (lich Windows lech giay)."""
    import time
    now = now or time.time()
    return now - last_scan(campaign["id"]) >= scan_minutes(campaign) * 60 - 120


# ------------------------------------------------------------------ kiem tra
def validate(data):
    errors = []
    if not data["accounts"]:
        errors.append("Chưa có tài khoản nào.")
    for account in data["accounts"]:
        for c in account["campaigns"]:
            if not c["enabled"]:
                continue
            where = f"[{account['name']} › {c['name']}]"
            if not c["groups"]:
                errors.append(f"{where} Chưa có nhóm Facebook.")
            bad = [g for g in c["groups"] if "facebook.com" not in g and "fb.com" not in g]
            if bad:
                errors.append(f"{where} Không phải link Facebook: {bad[0]}")
            if not c["keywords"]:
                errors.append(f"{where} Chưa có từ khóa cần tìm.")
            if not c["telegram_token"] or not c["telegram_chat_id"]:
                errors.append(f"{where} Chưa điền Telegram Token / Chat ID.")
            if c["auto_comment"] and not c["comment_text"].strip():
                errors.append(f"{where} Đã bật tự bình luận nhưng chưa có nội dung bình luận lần 1.")
            for rule in c["ad_score_rules"]:
                if "=" in rule and not rule.rsplit("=", 1)[1].strip().isdigit():
                    errors.append(f"{where} Dấu hiệu quảng cáo sai dạng: '{rule}' (đúng: cụm từ=điểm, "
                                  f"hoặc chỉ cụm từ = {DEFAULT_AD_POINTS} điểm).")
    return errors


def account_usable(account):
    """Tai khoan dang dang nhap hop le (xem account_status)."""
    import account_status
    return account_status.usable(ACCOUNTS_DIR / account["id"])


def schedule_entries(data):
    """Moi tai khoan hop le co nhom theo doi dang bat -> 1 lich quet lap lai.

    Tool dang 'Tam dung toan bo' hoac tai khoan het han / chua dang nhap -> khong tao lich.
    """
    if data.get("paused"):
        return []
    entries = []
    active = [x for x in data["accounts"] if account_usable(x) and any(c["enabled"] for c in x["campaigns"])]
    for index, a in enumerate(active):
        entries.append({
            "task": a["id"], "account": a["id"], "args": f"--once --account {a['id']}",
            "name": f"{a['name']} ({sum(c['enabled'] for c in a['campaigns'])} nhóm theo dõi)",
            "every": account_every(a), "max": hang_guard_minutes(a),
            # Lech gio bat dau giua cac tai khoan de khong cung mo trinh duyet 1 luc.
            "offset": 1 + index * 3,
        })
    return entries


# ------------------------------------------------------------------ rule khi loi (tab Setting nang cao)
# (tieu de, [phan]). phan: ('text', chu) | ('line', chu co {}, [o so]) | ('grid', [(nhan, dong tu, o so, don vi)])
# | ('tip', chu). o so: (khoa, mac dinh, nho nhat, lon nhat). Ap dung cho CA tool.
GROUP_FAIL_LIMIT = 3          # fb_monitor_v4 doc: khong thay khung binh luan bay nhieu bai lien -> ngung nhom
GROUP_PAUSE_DAYS = [3, 7, 14]  # ngung tu binh luan nhom lan 1 / 2 / 3+
RULE_SPEC = [
    ("① Facebook báo \"bạn đăng quá nhiều\" (chống spam)", [
        ("text", "→ Tool nghỉ CẢ tài khoản, không quét, không bình luận gì:"),
        ("grid", [("Bị lần đầu:", "nghỉ", ("pause_h1", 48, 1, 720), "giờ"),
                  ("Bị lần thứ 2:", "nghỉ", ("pause_h2", 72, 1, 720), "giờ"),
                  ("Bị lần thứ 3 trở đi:", "nghỉ", ("pause_h3", 168, 1, 2160), "giờ")]),
        ("line", "→ Nếu {} ngày liền không bị lại, lần sau được tính là \"lần đầu\".",
         [("strike_reset_days", 14, 1, 90)]),
        ("tip", "💡 Ví dụ: bị lần đầu lúc 8h sáng thứ 2 → tool chạy lại từ 8h sáng thứ 4."),
    ]),
    ("② Không bình luận được trong một nhóm (tool vẫn quét và báo Telegram)", [
        ("line", "→ Gặp {} bài liền không có ô bình luận thì tool tạm ngừng bình luận nhóm đó:",
         [("comment_fail_limit", 3, 1, 20)]),
        ("grid", [("Bị lần đầu:", "ngừng", ("comment_pause_d1", 3, 1, 60), "ngày"),
                  ("Bị lần thứ 2:", "ngừng", ("comment_pause_d2", 7, 1, 90), "ngày"),
                  ("Bị lần thứ 3 trở đi:", "ngừng", ("comment_pause_d3", 14, 1, 180), "ngày")]),
        ("tip", "💡 Thường do nhóm chặn thành viên mới bình luận."),
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
    global GROUP_FAIL_LIMIT, GROUP_PAUSE_DAYS
    GROUP_FAIL_LIMIT = r["comment_fail_limit"]
    GROUP_PAUSE_DAYS = [r["comment_pause_d1"], r["comment_pause_d2"], r["comment_pause_d3"]]
