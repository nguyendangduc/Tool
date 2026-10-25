# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
"""Dang nhap Facebook bang trinh duyet rieng cua tool (thu muc browser_profile/).

File nay GIONG HET NHAU o ca 2 tool (FacebookMonitor, FacebookUpStt).
Sua o mot noi thi copy sang 2 noi con lai.

- Nguoi dung dang nhap 1 lan trong cua so mo boi `--login` (MO_TOOL.bat -> chon tai khoan -> Dang nhap).
  Cua so nay la Google Chrome that, KHONG bi Playwright dieu khien, de Facebook
  khong nghi la bot va chan dang nhap.
- Khi chay theo lich, Playwright mo lai dung profile do bang chinh Chrome tren may,
  tat dau hieu tu dong hoa va khai dung phien ban trinh duyet.
- Trinh duyet tu luu cookie (ke ca xs moi khi Facebook doi) vao browser_profile/,
  cac lan chay sau mo lai dung profile do nen khong bi vang.
- May khong co Chrome: dung Chromium cai kem Playwright (cung cach tren).
- FB_COOKIE trong config chi con la du phong: neu profile chua dang nhap thi
  nap cookie do vao profile mot lan.
"""
import hashlib
import json
import msvcrt
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError

PROFILE_DIR_NAME = "browser_profile"
SEED_FILE_NAME = ".cookie_seed"
LOCK_FILE_NAME = "browser_profile.lock"
PID_FILE_NAME = "browser_profile.pid"
FACEBOOK_URL = "https://www.facebook.com/"

# Ma thoat de setup.ps1 biet ly do.
EXIT_NOT_LOGGED_IN = 3
EXIT_PROFILE_BUSY = 4

# Tat dau hieu "trinh duyet dang bi dieu khien tu dong" (navigator.webdriver).
STEALTH_ARGS = ["--disable-blink-features=AutomationControlled"]
STEALTH_IGNORE_DEFAULT_ARGS = ["--enable-automation"]

CHROME_PATHS = [
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
]


class NotLoggedIn(RuntimeError):
    pass


class ProfileBusy(RuntimeError):
    pass


_lock_handles = {}  # moi profile (tai khoan) 1 khoa rieng


def _acquire_lock(base_dir):
    """Chi 1 tien trinh duoc mo profile. Windows tu nha khoa khi tien trinh thoat."""
    key = str(Path(base_dir).resolve())
    if key in _lock_handles:
        return
    handle = open(Path(base_dir) / LOCK_FILE_NAME, "a+")
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        raise ProfileBusy(
            "Tool dang chay (theo lich hoac cua so dang nhap dang mo). "
            "Doi vai phut roi thu lai."
        )
    _lock_handles[key] = handle
    # Ghi PID de giao dien co the dung dung luot nay khi nguoi dung bam Dang xuat / Doi tai khoan.
    try:
        (Path(base_dir) / PID_FILE_NAME).write_text(str(os.getpid()), encoding="ascii")
    except OSError:
        pass


_nick_handles = {}  # uid Facebook -> file khoa dang giu


def _nick_lock_dir():
    """fb_tools/ o THU MUC CHA cua cac tool (copy ca bo sang may khac la xong); khong ghi duoc -> LOCALAPPDATA."""
    for root in (Path(__file__).resolve().parent.parent, Path(os.environ.get("LOCALAPPDATA") or Path.home())):
        path = root / "fb_tools"
        try:
            path.mkdir(parents=True, exist_ok=True)
            return path
        except OSError:
            continue
    return Path(os.environ.get("TEMP") or ".")


def hold_nick(base_dir, wait_minutes=30):
    """1 nick Facebook chi mo o 1 trinh duyet tai 1 thoi diem, du la tool nao (dang bai / theo doi).

    Khoa file chung trong <thu muc cha cua tool>/fb_tools theo uid -> cac tool khong can biet nhau;
    may chi cai 1 tool thi khong ai tranh khoa. Windows tu nha khoa khi tien trinh thoat.
    Nick dang ban -> doi toi da `wait_minutes`; qua han van chay tiep (nhu truoc day). Tra ve True neu giu duoc.
    """
    try:
        uid = json.loads((Path(base_dir) / "fb_profile.json").read_text(encoding="utf-8")).get("uid", "")
    except Exception:
        uid = ""
    if not re.fullmatch(r"\d+", uid or ""):
        return True
    if uid in _nick_handles:
        return True
    try:
        handle = open(_nick_lock_dir() / f"nick_{uid}.lock", "a+")
    except OSError:
        return True
    handle.seek(0)
    deadline = time.time() + wait_minutes * 60
    waited = False
    while True:
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            _nick_handles[uid] = handle
            if waited:
                print("[NICK] Nick da ranh -> chay tiep.", flush=True)
            return True
        except OSError:
            if time.time() >= deadline:
                handle.close()
                print(f"[NICK] Doi qua {wait_minutes} phut nick van ban -> van chay.", flush=True)
                return False
            if not waited:
                print("[NICK] Nick Facebook nay dang duoc dung o tool/luot khac -> doi xong roi moi chay.", flush=True)
                waited = True
            time.sleep(15)


def release_nick(base_dir):
    """Tra nick cho tool khac ngay khi xong (khong doi tien trinh thoat)."""
    try:
        uid = json.loads((Path(base_dir) / "fb_profile.json").read_text(encoding="utf-8")).get("uid", "")
    except Exception:
        return
    handle = _nick_handles.pop(uid, None)
    if handle:
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        handle.close()


# ------------------------------------------------------------------ tam dung nick (dung chung moi tool)
# Facebook bao "gioi han tan suat" -> dung dang bai / binh luan cua nick do mot thoi gian.
# Ghi theo uid trong fb_tools/ -> tool dang bai va tool theo doi cung biet nick dang nghi.
RATE_LIMIT_WORDS = ["giới hạn tần suất", "bảo vệ cộng đồng khỏi spam", "limit how often",
                    "protect our community from spam", "tạm thời bị chặn", "temporarily blocked"]


def is_rate_limited(text):
    import unicodedata
    text = unicodedata.normalize("NFC", text or "").lower()
    return any(w in text for w in RATE_LIMIT_WORDS)


def _nick_uid(base_dir):
    try:
        uid = json.loads((Path(base_dir) / "fb_profile.json").read_text(encoding="utf-8")).get("uid", "")
    except Exception:
        uid = ""
    return uid if re.fullmatch(r"\d+", uid or "") else ""


def _pause_file(base_dir):
    """Theo DANH TINH dang bai (uid + ten): ca nhan va cac Page cua cung nick bi Facebook gioi han rieng."""
    uid = _nick_uid(base_dir)
    try:
        name = json.loads((Path(base_dir) / "fb_profile.json").read_text(encoding="utf-8")).get("name", "")
    except Exception:
        name = ""
    if not uid:
        return Path(base_dir) / "tam_dung.json"
    tag = hashlib.md5(name.strip().lower().encode("utf-8")).hexdigest()[:8]
    return _nick_lock_dir() / f"nick_{uid}_{tag}.pause.json"


# Tai pham thi nghi lau hon: lan 1 / 2 / 3+ (gio). Qua STRIKE_RESET_DAYS ngay khong bi lai -> tinh lai tu lan 1.
ACCOUNT_PAUSE_HOURS = [48, 72, 168]
STRIKE_RESET_DAYS = 14
RECOVERY_HOURS = 24   # ngay dau sau khi het nghi: tool dang bai chi chay nua so nhom


def _read_pause(base_dir):
    try:
        return json.loads(_pause_file(base_dir).read_text(encoding="utf-8"))
    except Exception:
        return {}


def pause_nick(base_dir, reason, hours=None):
    """Tam dung dang bai + binh luan cua danh tinh nay. hours=None -> theo so lan tai pham. Tra ve thong tin nghi."""
    now = time.time()
    old = _read_pause(base_dir)
    strikes = int(old.get("strikes", 1 if old.get("until") else 0))
    if now - float(old.get("last", old.get("until", 0))) > STRIKE_RESET_DAYS * 86400:
        strikes = 0
    strikes += 1
    if hours is None:
        hours = ACCOUNT_PAUSE_HOURS[min(strikes, len(ACCOUNT_PAUSE_HOURS)) - 1]
    info = {"until": now + hours * 3600, "reason": reason, "strikes": strikes, "hours": hours, "last": now}
    try:
        _pause_file(base_dir).write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return info


def nick_pause(base_dir):
    """Nick dang tam dung -> {'until', 'reason', 'strikes', 'hours'}; khong thi None."""
    info = _read_pause(base_dir)
    try:
        return info if float(info.get("until", 0)) > time.time() else None
    except (TypeError, ValueError):
        return None


def recovering(base_dir):
    """Vua het nghi (trong RECOVERY_HOURS) -> nen chay nhe tay."""
    info = _read_pause(base_dir)
    try:
        until = float(info.get("until", 0))
    except (TypeError, ValueError):
        return False
    return until > 0 and until <= time.time() < until + RECOVERY_HOURS * 3600


def clear_nick_pause(base_dir):
    """Nut Reset tren giao dien: bo nghi ngay + xoa so lan tai pham."""
    try:
        _pause_file(base_dir).unlink()
    except OSError:
        pass


def pause_text(info):
    from datetime import datetime
    return f"{datetime.fromtimestamp(info['until']):%H:%M %d/%m}"


# ------------------------------------------------------------------ bang chao mung cua nhom
WELCOME_WORDS = ["chào mừng bạn đến với", "welcome to"]


def close_group_popup(page):
    """Nhom moi vao hien bang 'Chao mung ban den voi ...' che trang -> bam X (khong duoc thi Esc). True neu da dong."""
    import unicodedata
    closed = False
    try:
        for dialog in page.locator("div[role='dialog']").all()[:5]:
            try:
                text = unicodedata.normalize("NFC", dialog.inner_text(timeout=1_000) or "").lower()
            except Exception:
                continue
            if not any(w in text for w in WELCOME_WORDS) or "tạo bài viết" in text:
                continue
            button = dialog.locator("[aria-label='Đóng'], [aria-label='Close']").first
            try:
                button.click(timeout=3_000)
            except Exception:
                page.keyboard.press("Escape")
            page.wait_for_timeout(1_000)
            closed = True
            print("[POPUP] Da dong bang chao mung cua nhom.", flush=True)
    except Exception:
        pass
    return closed


# ------------------------------------------------------------------ o dia
def disk_free_mb(path):
    import shutil
    try:
        return shutil.disk_usage(str(path)).free // (1024 * 1024)
    except OSError:
        return -1


# ------------------------------------------------------------------ ket qua duyet bai / binh luan
# Trang 'Noi dung cua ban' cua nhom (groups/<nhom>/my_pending_content): thanh ben ghi so bai / binh luan
# Dang cho / Da dang / Bi tu choi / Da go (so van con sau khi xem -> 1 trang / nhom la du).
# Tool dang bai + tool theo doi cung dung; moi tai khoan 1 file ket_qua.json.
RESULTS_FILE = "ket_qua.json"
CONTENT_TABS = {"đang chờ": "pending", "đã đăng": "posted", "bị từ chối": "declined", "đã gỡ": "removed",
                "pending": "pending", "published": "posted", "posted": "posted", "declined": "declined",
                "removed": "removed"}
CHECK_AFTER_HOURS = 2      # gui xong bao lau thi kiem tra
RECHECK_HOURS = 24         # nhom con bai cho duyet -> kiem tra lai sau bay lau
SENT_KEEP_DAYS = 30


def group_slug(url):
    m = re.search(r"/groups/([^/?#]+)", url or "")
    return m.group(1) if m else ""


def content_url(slug):
    return f"https://www.facebook.com/groups/{slug}/my_pending_content"


def parse_group_content(text):
    """Chu trang 'Noi dung cua ban' -> {'name', 'pending': {'posts', 'comments'}, ..., 'member_review'}; None neu khong doc duoc."""
    import unicodedata
    text = unicodedata.normalize("NFC", text or "")
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    result = {k: {"posts": 0, "comments": 0} for k in ("pending", "posted", "declined", "removed")}
    name, start = "", None
    for i, line in enumerate(lines):
        if line.endswith("› Nội dung của bạn") or line.endswith("› Your content"):
            name = line.rsplit("›", 1)[0].strip()
        if start is None and line.lower() in CONTENT_TABS:
            start = i
    if start is None:
        return None
    seen, current = [], None
    for line in lines[start:]:
        low = line.lower()
        if low in CONTENT_TABS:
            key = CONTENT_TABS[low]
            if key in seen:      # ten muc lap lai = tieu de danh sach ben phai -> het thanh ben
                break
            seen.append(key)
            current = key
            continue
        counts = re.findall(r"(\d+)\s*(bài viết|bình luận|posts?|comments?)", low)
        if counts and current:
            for n, kind in counts:
                result[current]["comments" if kind.startswith(("bình", "comment")) else "posts"] += int(n)
            continue
        if low in ("chỉ báo nội dung mới", "new content indicator"):
            continue
        if current == "removed":
            break
    if len(seen) < 2:
        return None
    result["name"] = name
    result["member_review"] = "xét duyệt người mới tham gia" in text.lower()
    return result


def text_key(text):
    """Chu de so khop: bo bieu tuong (Facebook ve thanh anh), chu thuong, gop khoang trang."""
    import unicodedata
    text = unicodedata.normalize("NFC", text or "").lower()
    return " ".join(re.sub(r"[^\w\s,.!?:;()%/'\"&+-]", " ", text).split())


def text_snippet(text, size=20):
    """Doan dau noi dung (sau khi bo bieu tuong) -> nhan ra bai / binh luan trong danh sach 'Noi dung cua ban'."""
    key = text_key(text)
    return key[:size] if len(key) >= 8 else ""


POST_ID_RE = re.compile(r"/posts/(\d+)|[?&]post_id=(\d+)|/permalink/(\d+)")


def post_id_of(url):
    m = POST_ID_RE.search(url or "")
    return next((g for g in m.groups() if g), "") if m else ""


def _read_tab(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(5_000)
    close_group_popup(page)
    for _ in range(4):   # danh sach dai -> cuon cho Facebook tai them
        page.mouse.wheel(0, 2500)
        page.wait_for_timeout(1_200)
    text = page.evaluate("() => document.body.innerText")
    links = page.evaluate("() => [...document.querySelectorAll('a[href]')].map(a => a.href)")
    return text, links


# Facebook khong cho xem trang nhom (chua duoc duyet vao / bi han che / nhom da an).
NO_ACCESS_TEXTS = ("không xem được nội dung này", "content isn't available", "this content isn't available")
ADMIN_TEXTS = ("công cụ quản trị", "admin tools")


def read_group_content(page, slug):
    """Doc trang 'Noi dung cua ban': so dem (muc ben trai) + tung muc trong Dang cho / Bi tu choi / Da go.

    Dang cho co link tung bai / binh luan (khop chinh xac theo ma bai); Bi tu choi / Da go chi co noi dung
    (khop theo doan chu). Ket qua dung de tinh trang thai hien tai cua tung bai / binh luan tool da gui.
    """
    base = f"https://www.facebook.com/groups/{slug}/"
    text, links = _read_tab(page, content_url(slug))
    info = parse_group_content(text)
    if not info:
        low = (text or "").lower()
        if any(w in low for w in NO_ACCESS_TEXTS):
            # Quan tri vien nhom: Facebook khong mo 'Noi dung cua ban' (bai cua admin len ngay, khong qua duyet).
            page.goto(base, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(5_000)
            home = (page.evaluate("() => document.body.innerText") or "").lower()
            if any(w in home for w in ADMIN_TEXTS):
                title = re.sub(r"^\(\d+\)\s*", "", page.title() or "").rsplit(" | ", 1)[0].strip()
                return {"admin": True, "name": title}
            return {"no_access": True}
        return None
    # Link thong bao (notif_id) o thanh tren cung khong phai cua nhom nay.
    info["pending_ids"] = sorted({post_id_of(h) for h in links if "notif_id" not in h and post_id_of(h)})
    info["pending_text"] = text_key(text)[:40000]
    for key, tab in (("declined", "my_declined_content"), ("removed", "my_removed_content")):
        try:
            tab_text, _ = _read_tab(page, base + tab + "/")
            info[f"{key}_text"] = text_key(tab_text)[:40000]
        except Exception as error:
            print(f"[KET QUA] {slug}: khong mo duoc muc {tab} ({str(error).splitlines()[0][:60]})")
            info[f"{key}_text"] = ""
    info["items_checked"] = time.time()
    return info


def _members_num(text):
    """'30K' / '2,3K' / '183K' / '573' / '1,2 triệu' -> so nguyen (xap xi)."""
    m = re.search(r"([\d.,]+)\s*(K|N|nghìn|tr|triệu|M)?", text or "", re.I)
    if not m:
        return 0
    num = float(m.group(1).replace(".", "").replace(",", "."))
    unit = (m.group(2) or "").lower()
    mult = {"k": 1e3, "n": 1e3, "nghìn": 1e3, "tr": 1e6, "triệu": 1e6, "m": 1e6}.get(unit, 1)
    return int(num * mult)


def find_groups(page, keyword, max_results=30):
    """Tim nhom tren Facebook theo tu khoa (CHI DOC, khong tham gia).

    -> [{'slug','url','name','privacy','members','members_num','activity','joined'}] (joined: da la thanh vien).
    """
    from urllib.parse import quote
    page.goto(f"https://www.facebook.com/search/groups/?q={quote(keyword)}", wait_until="domcontentloaded",
              timeout=45_000)
    page.wait_for_timeout(5_000)
    for _ in range(4):
        page.mouse.wheel(0, 2800)
        page.wait_for_timeout(1_500)
    cards = page.evaluate(r"""() => {
        const out = []; const seen = new Set();
        for (const a of document.querySelectorAll('a[href*="/groups/"]')) {
            const m = a.href.match(/facebook\.com\/groups\/([^/?#]+)/);
            if (!m || m[1] === 'search' || seen.has(m[1])) continue;
            let box = a;
            for (let i = 0; i < 6 && box.parentElement; i++) box = box.parentElement;
            const text = (box.innerText || '').trim();
            if (!text || !text.includes('\n')) continue;
            seen.add(m[1]);
            out.push({slug: m[1], url: a.href.split('?')[0], block: text});
        }
        return out;
    }""")
    import unicodedata
    groups = []
    for c in cards:
        lines = [x.strip() for x in unicodedata.normalize("NFC", c["block"]).splitlines() if x.strip()]
        if not lines:
            continue
        info_line = next((x for x in lines if "thành viên" in x.lower() or "member" in x.lower()), "")
        low = info_line.lower()
        privacy = "riêng tư" if ("riêng tư" in low or "private" in low) else (
            "công khai" if ("công khai" in low or "public" in low) else "?")
        mem = re.search(r"([\d.,]+\s*(?:K|N|nghìn|tr|triệu|M)?)\s*(?:thành viên|member)", info_line, re.I)
        act = re.search(r"(\d+)(\+?)\s*(?:bài viết|bài đăng|posts?)(?:\s*(?:mỗi ngày|một ngày|/\s*ngày|a day|per day|/\s*day|hôm nay|today))?",
                        info_line, re.I)
        act_num = int(act.group(1)) if act else 0
        joined = any(w in " ".join(lines).lower() for w in ("đã tham gia", "joined", "truy cập nhóm", "vào nhóm"))
        groups.append({"slug": c["slug"], "url": c["url"], "name": lines[0][:80],
                       "privacy": privacy, "members": (mem.group(1).strip() if mem else "?"),
                       "members_num": _members_num(mem.group(1)) if mem else 0,
                       "activity": (act.group(1) + act.group(2)) if act else "", "activity_num": act_num,
                       "joined": joined})
        if len(groups) >= max_results:
            break
    return groups


JOINED_GROUPS_FILE = "nhom_da_vao.json"
JOINED_GROUPS_URL = "https://www.facebook.com/groups/joins/"
JOINED_MAX_AGE_DAYS = 3
# Link /groups/<x> khong phai nhom (menu, trang chuc nang cua Facebook).
NOT_GROUP_SLUGS = {"feed", "discover", "joins", "search", "create", "notifications", "your_groups", "browse",
                   "category", "categories", "requests", "invites", "suggested", "pending", "manage", "settings",
                   "groups"}

_JOINED_JS = r"""(skip) => {
    const out = []; const seen = new Set(skip);
    for (const a of document.querySelectorAll('a[href*="/groups/"]')) {
        const m = a.href.match(/facebook\.com\/groups\/([^/?#]+)/);
        if (!m || seen.has(m[1].toLowerCase())) continue;
        const name = (a.innerText || a.getAttribute('aria-label') || '').trim().split('\n')[0];
        if (!name) continue;   // link anh dai dien -> lay ten o link chu cung nhom
        seen.add(m[1].toLowerCase());
        out.push({slug: m[1], name: name});
    }
    return out;
}"""


def parse_joined_links(items):
    """[{'slug','name'}] tu trang -> [{'slug','url','name'}] (bo slug khong phai nhom, bo trung)."""
    groups, seen = [], set()
    for it in items:
        slug = (it.get("slug") or "").strip()
        if not slug or slug.lower() in NOT_GROUP_SLUGS or slug.lower() in seen:
            continue
        seen.add(slug.lower())
        groups.append({"slug": slug, "url": f"https://www.facebook.com/groups/{slug}/",
                       "name": ((it.get("name") or "").strip().split("\n")[0] or slug)[:80]})
    return groups


def read_joined_groups(page, max_scrolls=40, with_complete=False):
    """Doc danh sach nhom NICK NAY da tham gia (trang Nhom cua ban). CHI DOC, khong bam gi.

    -> [{'slug','url','name'}] (with_complete=True -> (danh sach, da doc HET hay chua)).
    Cuon toi khi 3 lan lien khong them nhom nao (= het danh sach) hoac du max_scrolls lan (= chua chac het).
    """
    page.goto(JOINED_GROUPS_URL, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(5_000)
    skip = sorted(NOT_GROUP_SLUGS)
    found, still, complete = {}, 0, False
    for _ in range(max_scrolls + 1):
        before = len(found)
        for g in parse_joined_links(page.evaluate(_JOINED_JS, skip)):
            found.setdefault(g["slug"].lower(), g)
        still = still + 1 if len(found) == before else 0
        if still >= 3:   # 3 lan cuon khong them nhom nao -> het danh sach
            complete = True
            break
        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(1_500)
    groups = list(found.values())
    return (groups, complete) if with_complete else groups


def load_joined_groups(acc_dir):
    """Cache nhom da tham gia -> {'time': epoch, 'groups': [{'slug','url','name'}]}."""
    try:
        data = json.loads((Path(acc_dir) / JOINED_GROUPS_FILE).read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("groups"), list):
            return {"time": float(data.get("time") or 0), "groups": data["groups"]}
    except Exception:
        pass
    return {"time": 0, "groups": []}


def save_joined_groups(acc_dir, groups):
    data = {"time": time.time(), "groups": list(groups)}
    try:
        (Path(acc_dir) / JOINED_GROUPS_FILE).write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                                        encoding="utf-8")
    except OSError:
        pass
    return data


def joined_groups_stale(cache, max_age_days=JOINED_MAX_AGE_DAYS):
    return not cache["groups"] or time.time() - cache["time"] > max_age_days * 86400


# ------------------------------------------------------------------ xin vao nhom
# Tool CHI bam "Tham gia nhom". Nhom co cau hoi -> KHONG tu tra loi (danh dau 'questions' de nguoi dung tu mo).
# Trang thai theo tai khoan: accounts/<id>/xin_vao_nhom.json {slug: {status, time, url, requested}}
#   joined = da la thanh vien · pending = da gui yeu cau, cho duyet · questions = can tra loi cau hoi
#   no_button = khong thay nut Tham gia · unknown = da bam nhung khong ro ket qua
JOIN_STATE_FILE = "xin_vao_nhom.json"
JOIN_PER_DAY = 10        # moi tai khoan xin toi da bay nhieu nhom / ngay (mac dinh)
JOIN_WAIT_SECONDS = 45   # cho giua 2 lan xin
LEAVE_PER_DAY = 20       # moi tai khoan roi toi da bay nhieu nhom / lan chay
LEAVE_WAIT_SECONDS = 20  # cho giua 2 lan roi
# So KHOP NGUYEN VAN chu tren nut (khong khop 1 phan): trang co nhieu nut khac chua chu 'dang cho' / 'tham gia'
# (vd nut an 'Tin nhan dang cho moi...' cua Messenger) -> khop 1 phan se doan sai trang thai.
_JOIN_BTN = re.compile(r"^\s*(Tham gia nhóm|Tham gia|Join group|Join)\s*$", re.I)
_JOINED_TXT = re.compile(r"^\s*(Đã tham gia|Joined)\s*$", re.I)
_PENDING_TXT = re.compile(r"^\s*(Hủy yêu cầu|Huỷ yêu cầu|Đã gửi yêu cầu|Cancel request|Request sent)\s*$", re.I)
# Nhom minh LA QUAN TRI VIEN: khong co nut 'Da tham gia' ma co 'Chinh sua' / 'Cong cu quan tri'.
_ADMIN_BTN = re.compile(r"^\s*(Chỉnh sửa|Edit|Công cụ quản trị|Admin tools|Quản lý|Manage)\s*$", re.I)
# Dau hieu phu DA LA THANH VIEN (khi dau trang khong co nut nao o tren): nut Moi. (O 'Ban viet gi di' KHONG dung
# duoc: nhom cong khai nguoi chua vao cung thay.)
_MEMBER_HINT = re.compile(r"^\s*(\+?\s*Mời|Invite)\s*$", re.I)
_QUESTION_TXT = re.compile(r"(câu hỏi|Trả lời|Answer|question|Gửi|Submit)", re.I)

# Chi lay nut DANG HIEN trong vung noi dung chinh cua trang nhom (bo thanh tren, thong bao, Messenger an...),
# kem vi tri doc (y) de biet nut nao o DAU TRANG.
_BUTTON_TEXTS_JS = r"""() => {
    const root = document.querySelector('[role="main"]') || document.body;
    return [...root.querySelectorAll('[role="button"],button')].map(b => {
        const r = b.getBoundingClientRect();
        return {t: (b.innerText || b.getAttribute('aria-label') || '').trim(), y: r.top + window.scrollY,
                v: r.width > 0 && r.height > 0};
    }).filter(x => x.v && x.t).slice(0, 300);
}"""


def _visible_button(page, pattern):
    """Nut DANG HIEN, nam TREN CUNG trong vung chinh co chu khop pattern (None neu khong co).

    Tren cung = nut o dau trang cua CHINH nhom; nut cung chu o duoi (vd dai 'Nhom lien quan' toan nut
    'Tham gia nhom' cua nhom khac) khong duoc bam.
    """
    main = page.locator('[role="main"]')
    scope = main.first if main.count() else page
    buttons = scope.get_by_role("button", name=pattern)
    best, best_y = None, None
    for i in range(min(buttons.count(), 30)):
        b = buttons.nth(i)
        try:
            box = b.bounding_box() if b.is_visible() else None
        except Exception:
            box = None
        if box and (best_y is None or box["y"] < best_y):
            best, best_y = b, box["y"]
    return best


def _visible_dialog(page):
    """Hop thoai DANG HIEN vua mo ra (bo hop an co san cua Messenger / Thong bao)."""
    dialogs = page.locator('[role="dialog"]')
    for i in range(dialogs.count() - 1, -1, -1):
        d = dialogs.nth(i)
        try:
            label = (d.get_attribute("aria-label") or "").lower()
            if label in ("messenger", "thông báo", "notifications", "chats", "đoạn chat"):
                continue
            if d.is_visible():
                return d
        except Exception:
            continue
    return None


def load_join_state(acc_dir):
    try:
        st = json.loads((Path(acc_dir) / JOIN_STATE_FILE).read_text(encoding="utf-8"))
        return st if isinstance(st, dict) else {}
    except Exception:
        return {}


def save_join_state(acc_dir, st):
    try:
        (Path(acc_dir) / JOIN_STATE_FILE).write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def set_join_status(acc_dir, url, status, requested=False):
    st = load_join_state(acc_dir)
    slug = group_slug(url) or url
    old = st.get(slug, {})
    st[slug] = {"status": status, "time": time.time(), "url": url,
                "requested": old.get("requested", 0) if not requested else time.time()}
    if status == "joined" and old.get("status") == "joined":   # van o nhom -> giu ket qua xac minh
        st[slug].update({k: old[k] for k in ("verified", "verify_note") if k in old})
    save_join_state(acc_dir, st)


def set_verified(acc_dir, url, ok, note=""):
    """Ghi ket qua xac minh nhom (da vao + dang bai duoc ngay). ok=False -> note = viec con vuong."""
    st = load_join_state(acc_dir)
    slug = group_slug(url) or url
    g = st.setdefault(slug, {"status": "joined", "time": time.time(), "url": url, "requested": 0})
    g["status"] = "joined"
    g["verified"] = time.time() if ok else 0
    g["verify_note"] = "" if ok else note
    save_join_state(acc_dir, st)


def joins_today(acc_dir):
    """So lan tool da BAM xin vao nhom hom nay (tinh gioi han moi ngay)."""
    from datetime import datetime
    today = datetime.now().date()
    return sum(1 for g in load_join_state(acc_dir).values()
               if g.get("requested") and datetime.fromtimestamp(g["requested"]).date() == today)


def mark_joined(acc_dir, joined_groups, complete=False):
    """Sau khi doc danh sach nhom da tham gia: nhom dang cho duyet / can tra loi ma da vao -> 'joined'.

    complete (doc HET danh sach): nhom dang ghi 'joined' ma khong con trong danh sach -> da roi / bi moi ra -> xoa.
    -> (so nhom moi duoc duyet, so nhom khong con la thanh vien).
    """
    st = load_join_state(acc_dir)
    have = {g["slug"].lower() for g in joined_groups}
    approved = gone = 0
    for slug, g in list(st.items()):
        if slug.lower() in have and g.get("status") != "joined":
            g.update(status="joined", time=time.time())
            approved += 1
        elif complete and slug.lower() not in have and g.get("status") == "joined":
            del st[slug]
            gone += 1
    known = {s.lower() for s in st}
    for g in joined_groups:   # nhom da vao tu truoc -> ghi nhan luon
        if g["slug"].lower() not in known:
            st[g["slug"]] = {"status": "joined", "time": time.time(), "url": g["url"], "requested": 0}
    save_join_state(acc_dir, st)
    return approved, gone


def forget_joined(acc_dir, url):
    """Da roi nhom: bo khoi trang thai xin vao nhom + khoi danh sach nhom da tham gia da doc."""
    slug = (group_slug(url) or url).lower()
    st = load_join_state(acc_dir)
    for key in [k for k in st if k.lower() == slug]:
        del st[key]
    save_join_state(acc_dir, st)
    cache = load_joined_groups(acc_dir)
    left = [g for g in cache["groups"] if g.get("slug", "").lower() != slug]
    if len(left) != len(cache["groups"]):
        try:
            (Path(acc_dir) / JOINED_GROUPS_FILE).write_text(json.dumps(
                {"time": cache["time"], "groups": left}, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass


_LEAVE_TXT = re.compile(r"^\s*(Rời nhóm|Rời khỏi nhóm|Leave group|Leave)\s*$", re.I)
_CANCEL_REQ_TXT = re.compile(r"^\s*(Hủy yêu cầu|Huỷ yêu cầu|Cancel request)\s*$", re.I)
_ADMIN_TXT = re.compile(r"(quản trị viên|admin|người kiểm duyệt|moderator|lưu trữ nhóm|archive)", re.I)


def _click_dialog_button(page, pattern):
    """Bam nut co chu khop pattern trong hop thoai dang mo (nut xac nhan). -> True neu bam duoc."""
    dialog = _visible_dialog(page)
    if dialog is None:
        return False
    button = dialog.get_by_role("button", name=pattern).first
    if not button.count():
        return False
    button.click()
    page.wait_for_timeout(3_000)
    return True


def leave_group(page, url):
    """Roi nhom (dang la thanh vien) hoac huy yeu cau (dang cho duyet). -> (trang thai, da_bam).

    Trang thai: 'left' da roi / huy yeu cau · 'not_member' khong o trong nhom · 'admin' tai khoan la quan tri
    vien (KHONG tu roi: Facebook se hoi chon quan tri vien moi / luu tru nhom) · 'no_button' · 'limited'.
    """
    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(5_000)
    if is_rate_limited(page.inner_text("body")[:6000]):
        return "limited", False
    state, admin = _membership_on_page(page, with_admin=True)
    if admin:
        return "admin", False   # nhom minh quan tri -> KHONG tu roi (Facebook se hoi chon quan tri vien moi / luu tru)
    if state is None:
        return "not_member", False
    if state == "pending":
        button = _visible_button(page, _CANCEL_REQ_TXT)
        if button is None:
            return "no_button", False
        button.click()
        page.wait_for_timeout(3_000)
        _click_dialog_button(page, _CANCEL_REQ_TXT)
        return ("left" if _membership_on_page(page) is None else "no_button"), True
    button = _visible_button(page, _JOINED_TXT)
    if button is None:
        return "no_button", False
    button.click()
    page.wait_for_timeout(2_500)
    items = page.get_by_role("menuitem", name=re.compile(r"(Rời nhóm|Rời khỏi nhóm|Leave group)", re.I))
    item = next((items.nth(i) for i in range(min(items.count(), 5)) if items.nth(i).is_visible()), None)
    if item is None:
        page.keyboard.press("Escape")
        return "no_button", True
    item.click()
    page.wait_for_timeout(3_000)
    dialog = _visible_dialog(page)
    text = dialog.inner_text()[:3000] if dialog is not None else ""
    if _ADMIN_TXT.search(text):
        page.keyboard.press("Escape")   # la quan tri vien -> de nguoi dung tu quyet
        return "admin", True
    if not _click_dialog_button(page, _LEAVE_TXT):
        page.keyboard.press("Escape")
        return "no_button", True
    if is_rate_limited(page.inner_text("body")[:6000]):
        return "limited", True
    page.wait_for_timeout(2_000)
    try:   # tai lai trang de chac chan da roi (o dang bai / nut cu co the con hien vai giay)
        page.reload(wait_until="domcontentloaded", timeout=45_000)
        page.wait_for_timeout(4_000)
    except Exception:
        pass
    return ("left" if _membership_on_page(page) is None else "no_button"), True


# ------------------------------------------------------------------ cham bai (binh luan mo ta vao bai da duyet)
# accounts/<id>/cham_bai.json {post_id: {status, time, url, text}}
#   queued = cho gui · sent = da bam gui (chua thay hien tren bai) · visible = da thay binh luan hien tren bai
#   failed = khong binh luan duoc. File cu da_binh_luan_cham.txt (danh sach post_id) = 'sent'.
CARE_FILE = "cham_bai.json"


def load_care_state(acc_dir):
    try:
        st = json.loads((Path(acc_dir) / CARE_FILE).read_text(encoding="utf-8"))
        st = st if isinstance(st, dict) else {}
    except Exception:
        st = {}
    try:
        for pid in (Path(acc_dir) / "da_binh_luan_cham.txt").read_text(encoding="utf-8").split():
            st.setdefault(pid, {"status": "sent", "time": 0, "url": "", "text": ""})
    except OSError:
        pass
    return st


def set_care_status(acc_dir, url, status, text=None):
    st = load_care_state(acc_dir)
    pid = post_id_of(url) or url
    old = st.get(pid, {})
    st[pid] = {"status": status, "time": time.time(), "url": url or old.get("url", ""),
               "text": text if text is not None else old.get("text", "")}
    try:
        (Path(acc_dir) / CARE_FILE).write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


# ------------------------------------------------------------------ tin nhan moi (Messenger cua nick)
# accounts/<id>/tin_nhan.json {"checked": epoch, "threads": {thread_id: {name, snippet, folder, url, time, seen,
#   notified}}}. Chi DOC danh sach cuoc tro chuyen (khong mo tung cuoc -> khach khong thay 'da xem').
INBOX_FILE = "tin_nhan.json"
INBOX_FOLDERS = [("inbox", "Hộp thư", "https://www.facebook.com/messages/"),
                 ("requests", "Tin nhắn chờ", "https://www.facebook.com/messages/requests/"),
                 ("spam", "Spam", "https://www.facebook.com/messages/requests/")]   # tab 'Spam' trong Tin nhan cho
INBOX_FOLDER_LABEL = {k: label for k, label, _url in INBOX_FOLDERS}


INBOX_UNREAD_MARK = ("tin nhắn chưa đọc:", "unread message:")
INBOX_E2EE_TEXTS = ("mã hóa đầu cuối", "end-to-end encrypted", "không khôi phục được tin nhắn",
                    "tin nhắn không hiển thị")
INBOX_DAYS = (7, 1, 60)   # chi lay tin chua doc trong N ngay gan nhat: mac dinh, nho nhat, lon nhat
_AGE_UNITS = {"phút": 1 / 60, "giờ": 1, "ngày": 24, "tuần": 168, "tháng": 720, "năm": 8760,
              "m": 1 / 60, "min": 1 / 60, "h": 1, "d": 24, "w": 168, "y": 8760}

_INBOX_ROWS_JS = r"""() => {
    const out = [];
    for (const a of document.querySelectorAll('a[href*="/messages/"]')) {
        const m = a.href.match(/\/messages\/(?:e2ee\/)?(?:requests\/)?t\/(\d+)/);
        if (!m) continue;
        out.push({id: m[1], url: a.href.split('?')[0], text: a.innerText || '',
                  group: /^(Nhóm chat|Group chat)/i.test(a.getAttribute('aria-label') || '')});
    }
    return out;
}"""


def _age_hours(text):
    """'16 giờ' / '1 ngày' / '21 tuần' / 'Vừa xong' -> so gio (khong doc duoc -> 0 = coi la moi)."""
    m = re.search(r"(\d+)\s*(phút|giờ|ngày|tuần|tháng|năm|min|m|h|d|w|y)\b", text or "", re.I)
    return int(m.group(1)) * _AGE_UNITS[m.group(2).lower()] if m else 0


def parse_inbox_row(text):
    """Chu 1 dong cuoc tro chuyen -> {name, snippet, unread, age_hours}.
    Mau: 'Ten\\nTin nhắn chưa đọc:\\nNoi dung\\n \\n·\\n16 giờ'."""
    import unicodedata
    lines = [x.strip() for x in unicodedata.normalize("NFC", text or "").splitlines() if x.strip() and x.strip() != "·"]
    if not lines:
        return None
    unread = any(x.lower() in INBOX_UNREAD_MARK for x in lines)
    body = [x for x in lines[1:] if x.lower() not in INBOX_UNREAD_MARK]
    snippet = body[0] if body else ""
    age = _age_hours(body[1] if len(body) > 1 else "")
    if any(w in snippet.lower() for w in INBOX_E2EE_TEXTS):
        snippet = "(tin mã hoá – mở Messenger để xem nội dung)"
    return {"name": lines[0][:80], "snippet": snippet[:500], "unread": unread, "age_hours": age}


def read_inbox(page, full=True, days=INBOX_DAYS[0]):
    """Doc tin nhan CHUA DOC cua nick o Hop thu (+ Tin nhan cho / Spam neu full). CHI DOC danh sach, khong mo
    cuoc nao. -> [{id, name, snippet, folder, url}]. Bo nhom chat va tin chua doc cu hon `days` ngay."""
    # Trang Tin nhan cho / Spam van hien danh sach Hop thu ben trai -> cuoc da gap o muc truoc thi bo qua,
    # phan con lai moi la cua muc dang doc.
    found, seen = {}, set()
    for folder, _label, url in (INBOX_FOLDERS if full else INBOX_FOLDERS[:1]):
        try:
            rows = _read_inbox_folder(page, folder, url)
        except Exception as error:
            print(f"[TIN NHAN] {folder}: khong doc duoc ({str(error).splitlines()[0][:80]})")
            continue
        for r in rows:
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            info = parse_inbox_row(r["text"])
            if not info or not info["unread"] or r.get("group") or info["age_hours"] > days * 24:
                continue
            found[r["id"]] = {"id": r["id"], "name": info["name"], "snippet": info["snippet"], "folder": folder,
                              "url": r["url"]}
    return list(found.values())


_CLICK_TAB_JS = r"""(name) => {
    const t = [...document.querySelectorAll('[role=tab]')].find(x => (x.innerText || '').trim() === name);
    if (!t) return false;
    t.click();
    return true;
}"""


def _read_inbox_folder(page, folder, url):
    """Hop thu: mo trang. Tin nhan cho: mo trang (tab 'Co the ban biet' chon san). Spam: bam tab 'Spam'
    (chi doi danh sach, khong mo cuoc tro chuyen nao)."""
    if folder != "spam" or "/messages/requests" not in (page.url or ""):
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        page.wait_for_timeout(7_000)
    if folder == "spam":
        if not page.evaluate(_CLICK_TAB_JS, "Spam"):
            print("[TIN NHAN] Khong thay tab Spam.")
            return []
        page.wait_for_timeout(5_000)
    for _ in range(2):   # cuon danh sach de tai them cuoc tro chuyen
        page.mouse.wheel(0, 2500)
        page.wait_for_timeout(1_200)
    return page.evaluate(_INBOX_ROWS_JS)


def load_inbox(acc_dir):
    try:
        st = json.loads((Path(acc_dir) / INBOX_FILE).read_text(encoding="utf-8"))
        st = st if isinstance(st, dict) else {}
    except Exception:
        st = {}
    st.setdefault("checked", 0)
    st.setdefault("threads", {})
    return st


def save_inbox(acc_dir, st):
    try:
        (Path(acc_dir) / INBOX_FILE).write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def merge_inbox(acc_dir, found, full=True):
    """found: [{id, name, snippet, folder, url}] cuoc tro chuyen CHUA DOC vua doc duoc -> luu; tra ve cac muc
    can bao (cuoc moi, hoac khach nhan them cau khac). Cuoc nguoi dung da mo / tra loi tren Facebook (khong con
    'chua doc') -> tu danh dau da xem. full=False (chi doc Hop thu): khong dong vao cuoc o Tin nhan cho / Spam."""
    st, now, new = load_inbox(acc_dir), time.time(), []
    unread = {t["id"] for t in found}
    for tid, t in st["threads"].items():
        if tid not in unread and not t.get("seen") and (full or t.get("folder") == "inbox"):
            t["seen"] = True
    for t in found:
        old = st["threads"].get(t["id"], {})
        # Cung cau cu (nguoi dung da bam 'da xem' trong tool) -> giu nguyen, khong bao lai.
        changed = t["snippet"] != old.get("notified")
        item = dict(old, **t, seen=bool(old.get("seen")) and not changed)
        if changed:
            item["time"] = now
            item["notified"] = t["snippet"]
            new.append(item)
        st["threads"][t["id"]] = item
    # Gioi han file: bo cuoc da xem cu hon 30 ngay.
    st["threads"] = {k: v for k, v in st["threads"].items()
                     if not v.get("seen") or now - v.get("time", 0) < 30 * 86400}
    st["checked"] = now
    if full:
        st["full_checked"] = now
    save_inbox(acc_dir, st)
    return new


# Cai dat 'Theo doi tin nhan' (config.json -> "inbox"), doc thang tu file de tool dang bai / theo doi dung chung.
INBOX_MINUTES = (15, 10, 240)      # mac dinh, nho nhat, lon nhat (phut giua 2 luot)
INBOX_FULL_EVERY = 120             # phut: doc du 3 muc (Tin nhan cho / Spam khong co so dem) it nhat moi 2 tieng


def inbox_minutes(s):
    default, low, high = INBOX_MINUTES
    try:
        value = int(s.get("minutes") or default)
    except (TypeError, ValueError):
        value = default
    return min(high, max(low, value))


def inbox_config(acc_dir):
    try:
        data = json.loads((Path(acc_dir).parent.parent / "config.json").read_text(encoding="utf-8"))
    except Exception:
        data = {}
    s = dict({"enabled": False, "telegram_token": "", "telegram_chat_id": ""}, **(data.get("inbox") or {}))
    s["minutes"] = inbox_minutes(s)
    default, low, high = INBOX_DAYS
    try:
        s["days"] = min(high, max(low, int(s.get("days") or default)))
    except (TypeError, ValueError):
        s["days"] = default
    s["paused"] = bool(data.get("paused"))
    return s


def send_inbox_telegram(settings, account_name, items):
    """Bao Telegram (kenh rieng cho tin nhan): moi cuoc tro chuyen co tin moi 1 dong."""
    import html
    import urllib.parse
    import urllib.request
    token, chat = settings.get("telegram_token", ""), settings.get("telegram_chat_id", "")
    if not token or not chat or not items:
        return
    lines = [f"💬 <b>Tin nhắn mới – {html.escape(account_name)}</b>"]
    for t in items[:15]:
        where = INBOX_FOLDER_LABEL.get(t["folder"], t["folder"])
        lines.append(f"\n• <b>{html.escape(t['name'])}</b> ({where}): {html.escape(t['snippet'][:300])}")
    if len(items) > 15:
        lines.append(f"\n… và {len(items) - 15} cuộc trò chuyện khác.")
    body = urllib.parse.urlencode({"chat_id": chat, "text": "\n".join(lines), "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=body, timeout=20):
            pass
    except Exception as error:
        print(f"[TIN NHAN] Telegram loi: {error}")


def check_inbox_page(page, acc_dir, account_name, note=print, force_full=False, piggyback=False):
    """Xem tin nhan bang trinh duyet DANG MO cua nick. Luot nhanh: chi Hop thu (~15s); luot du (Hop thu + Tin nhan
    cho + Spam) khi da >= 2 tieng chua doc du, hoac luot nhanh vua thay tin moi. Tin moi -> nhat ky + Telegram.
    piggyback=True (cuoi luot dang bai / quet nhom): chi chay khi da bat theo doi va da den han (>= N phut)."""
    settings = inbox_config(acc_dir)
    st = load_inbox(acc_dir)
    now = time.time()
    if piggyback and (not settings["enabled"] or settings["paused"]
                      or now - st["checked"] < settings["minutes"] * 60 * 0.6):
        return []
    full = force_full or now - st.get("full_checked", 0) >= INBOX_FULL_EVERY * 60
    found = read_inbox(page, full=full, days=settings["days"])
    new = merge_inbox(acc_dir, found, full=full)
    if new and not full:
        # Hop thu co tin moi -> xem luon Tin nhan cho / Spam (khach la hay roi vao do).
        found = read_inbox(page, full=True, days=settings["days"])
        new += [t for t in merge_inbox(acc_dir, found, full=True) if t["id"] not in {x["id"] for x in new}]
        full = True
    print(f"[TIN NHAN] {account_name}: {'du 3 muc' if full else 'nhanh (Hop thu)'} – {len(found)} cuoc chua doc, "
          f"{len(new)} tin moi.")
    if new:
        note(f"💬 {account_name}: {len(new)} tin nhắn mới – " + ", ".join(t["name"] for t in new[:5]))
        send_inbox_telegram(settings, account_name, new)
    return new


def mark_inbox_seen(acc_dir, thread_ids):
    st = load_inbox(acc_dir)
    for tid in thread_ids:
        if tid in st["threads"]:
            st["threads"][tid]["seen"] = True
    save_inbox(acc_dir, st)


def unseen_inbox(acc_dir):
    """Cuoc tro chuyen co tin moi chua xem, moi nhat truoc."""
    st = load_inbox(acc_dir)
    items = [dict(v, id=k) for k, v in st["threads"].items() if not v.get("seen")]
    return sorted(items, key=lambda v: -v.get("time", 0))


AUTO_CARE_DAYS = 7   # tu cham: chi bai tool dang trong 7 ngay qua


def care_candidates(acc_dir, groups, days=AUTO_CARE_DAYS):
    """Tu cham: bai CUA MINH da duoc duyet (muc 'Da dang') ma tool da dang va CHUA cham lan nao -> [url].

    groups: link / ma nhom cua cac muc co noi dung cham. Chi lay bai khop doan dau noi dung tool da gui vao nhom
    do trong `days` ngay (khong dong vao bai cu / bai tu dang tay). Bai da co trang thai cham bat ky (ke ca loi)
    -> bo qua: moi bai toi da 1 lan, khong thu lai tu dong.
    """
    st, care = load_results(acc_dir), load_care_state(acc_dir)
    since, out = time.time() - days * 86400, []
    for slug in dict.fromkeys(group_slug(g) or g for g in groups):
        info = st["groups"].get(slug) or {}
        if info.get("admin"):
            continue
        sent = st["sent"].get(slug, [])
        snippets = {e[3] for e in sent if e[1] == "post" and e[0] >= since and len(e) > 3 and e[3]}
        commented = {e[2] for e in sent if e[1] == "comment" and len(e) > 2 and e[2]}
        for it in info.get("posted_items", []):
            pid, url = it.get("id"), it.get("url")
            if not pid or not url or pid in care or pid in commented:
                continue
            body = text_key(it.get("text", ""))
            if any(s in body for s in snippets):
                out.append(url)
    return list(dict.fromkeys(out))


def comment_visible(page, url, text):
    """Mo bai, tim doan dau noi dung binh luan cua minh tren trang -> True neu thay (binh luan da len)."""
    key = text_snippet(text, 30)
    if not key:
        return False
    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(5_000)
    return key in text_key(page.inner_text("body"))


def _membership_on_page(page, with_admin=False):
    """'joined' / 'pending' / None (chua vao) - theo nut dang hien o dau trang nhom.

    with_admin=True -> (trang thai, la quan tri vien?).
    """
    buttons = page.evaluate(_BUTTON_TEXTS_JS)
    # Nut TREN CUNG trong cac nut trang thai = nut cua CHINH nhom o dau trang. Nut cung chu o duoi (vd dai
    # 'Nhom lien quan' toan 'Tham gia nhom' cua nhom khac, hien ra sau khi vao nhom) khong tinh.
    kinds = [(_JOIN_BTN, None), (_JOINED_TXT, "joined"), (_PENDING_TXT, "pending"), (_ADMIN_BTN, "admin")]
    found = [(b["y"], kind) for b in buttons for pattern, kind in kinds if pattern.match(b["t"])]
    top = min(found, key=lambda x: x[0])[1] if found else (
        "joined" if any(_MEMBER_HINT.match(b["t"]) for b in buttons) else None)
    admin = top == "admin"
    state = "joined" if admin else top
    return (state, admin) if with_admin else state


# ------------------------------------------------------------------ tu tra loi cau hoi tham gia
# Hop 'Tra loi cau hoi' (hien khi bam Tham gia, hoac nut 'Tra loi cau hoi' tren trang nhom khi dang cho duyet).
# 3 loai: o chu (tra loi = cau mau cua kich ban) · chon 1 (uu tien dap an dong y / co) · chon nhieu (tick dap an
# dong y; khong co thi tick dap an dau). Cau hoi xin email / so dien thoai / mat khau / link -> de trong.
LAST_JOIN_NOTE = {"text": ""}   # ghi chu lan xin vao vua roi (vd 'da tu tra loi cau hoi') -> ghi nhat ky
DEFAULT_JOIN_ANSWER ="Mình biết nhóm qua tìm kiếm trên Facebook, mình đã đọc và đồng ý với nội quy nhóm ạ."
_ANSWER_BTN = re.compile(r"^\s*(Trả lời câu hỏi|Answer questions)\s*$", re.I)
_SUBMIT_BTN = re.compile(r"^\s*(Gửi|Submit)\s*$", re.I)
_POSITIVE = re.compile(r"(đồng ý|chấp nhận|có|rồi|đã đọc|yes|agree|accept|ok)", re.I)
_NEGATIVE = re.compile(r"(không|chưa|no\b|disagree|decline)", re.I)
_SENSITIVE = re.compile(r"(email|e-mail|gmail|số điện thoại|sđt|sdt|điện thoại|phone|zalo|mật khẩu|password|"
                        r"link|đường dẫn|url|mã giới thiệu|cmnd|cccd)", re.I)
_QUESTIONS_JS = r"""() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const d = [...document.querySelectorAll('[role=dialog]')].filter(vis).pop();
  if (!d) return [];
  const inputs = [...d.querySelectorAll('textarea, input[type=radio], input[type=checkbox], input[type=text]')];
  const text = e => {
    const lab = e.closest('label'); if (lab && lab.innerText.trim()) return lab.innerText.trim();
    const by = e.getAttribute('aria-labelledby');
    if (by) return by.split(' ').map(i => (document.getElementById(i) || {}).innerText || '').join(' ').trim();
    return e.getAttribute('aria-label') || e.getAttribute('placeholder') || '';
  };
  // Khoi cau hoi: di len tu o nhap toi khi cha chua o nhap KHAC LOAI hoac co nut 'Lua chon khac cho cau hoi'
  const blockOf = e => {
    let b = e;
    while (b.parentElement && b.parentElement !== d) {
      const p = b.parentElement;
      const kinds = new Set([...p.querySelectorAll('textarea, input[type=radio], input[type=checkbox], input[type=text]')]
                             .map(x => x.tagName + x.type));
      if (kinds.size > 1) break;
      b = p;
      if (p.querySelector('[aria-label*="câu hỏi"], [aria-label*="question"]')) break;
    }
    return b;
  };
  const blocks = [];
  inputs.forEach((e, i) => {
    e.setAttribute('data-fbq', String(i));
    const b = blockOf(e);
    let blk = blocks.find(x => x.el === b);
    if (!blk) { blk = {el: b, q: (b.innerText || '').split('\n')[0].trim(), type: e.type, options: []}; blocks.push(blk); }
    blk.options.push({i, text: text(e), checked: !!e.checked, value: e.value || ''});
  });
  return blocks.map(b => ({q: b.q, type: b.type, options: b.options}));
}"""


def answer_questions(page, answer=None):
    """Tra loi hop cau hoi tham gia DANG MO roi bam Gui. -> (da gui?, ghi chu)."""
    answer = (answer or DEFAULT_JOIN_ANSWER).strip()
    dialog = _visible_dialog(page)
    if dialog is None:
        return False, "không thấy hộp câu hỏi"
    blocks = page.evaluate(_QUESTIONS_JS)
    skipped = []
    for b in blocks:
        opts = b["options"]
        box = lambda o: page.locator(f"[data-fbq='{o['i']}']")
        if b["type"] in ("textarea", "text"):
            if _SENSITIVE.search(b["q"]):
                skipped.append(b["q"][:50])
                continue
            for o in opts:
                if not o["value"]:
                    box(o).click()
                    page.keyboard.type(answer, delay=15)
                    page.wait_for_timeout(500)
            continue
        if any(o["checked"] for o in opts):
            continue
        good = [o for o in opts if _POSITIVE.search(o["text"]) and not _NEGATIVE.search(o["text"])]
        pick = good if b["type"] == "checkbox" and good else [(good or opts)[0]]
        for o in pick:
            try:
                box(o).click(force=True)
            except Exception:
                box(o).evaluate("e => e.click()")
            page.wait_for_timeout(400)
    print(f"[CAU HOI] Da tra loi {len(blocks) - len(skipped)}/{len(blocks)} cau.", flush=True)
    button = dialog.get_by_role("button", name=_SUBMIT_BTN).first
    if not button.count() or button.get_attribute("aria-disabled") == "true":
        page.keyboard.press("Escape")
        return False, ("nhóm hỏi thông tin riêng (" + "; ".join(skipped) + ")") if skipped else \
            "chưa gửi được câu trả lời (nút Gửi chưa bấm được)"
    button.click()
    page.wait_for_timeout(3_500)
    return True, ("bỏ trống: " + "; ".join(skipped)) if skipped else ""


def answer_pending_questions(page, answer=None):
    """Dang cho duyet ma trang nhom con nut 'Tra loi cau hoi' -> mo ra tra loi. -> (da gui?, ghi chu) / None."""
    button = _visible_button(page, _ANSWER_BTN)
    if button is None:
        return None
    button.click()
    page.wait_for_timeout(2_500)
    return answer_questions(page, answer)


def join_group(page, url, answer=None):
    """Mo nhom, bam 'Tham gia nhom' (1 lan). -> (trang thai, da_bam). Trang thai them: 'limited' = Facebook chan."""
    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(5_000)
    if is_rate_limited(page.inner_text("body")[:6000]):
        return "limited", False
    LAST_JOIN_NOTE["text"] = ""
    before = _membership_on_page(page)
    if before == "pending":   # da xin tu truoc ma chua tra loi cau hoi -> tra loi luon
        res = answer_pending_questions(page, answer)
        if res:
            LAST_JOIN_NOTE["text"] = "đã tự trả lời câu hỏi" if res[0] else res[1]
    if before:
        return before, False
    button = _visible_button(page, _JOIN_BTN)
    if button is None:
        return "no_button", False
    button.click()
    page.wait_for_timeout(5_000)
    notes = []
    # Sau khi bam co the hien lan luot: 'Tham gia voi tu cach' (nick quan ly Trang) / 'Quy tac nhom' (Dong y) /
    # 'Tra loi cau hoi' -> xu ly tung hop (toi da 3).
    for _ in range(3):
        dialog = _visible_dialog(page)
        if dialog is None:
            break
        text = dialog.inner_text()[:3000]
        if is_rate_limited(text):
            page.keyboard.press("Escape")
            return "limited", True
        if _JOIN_AS_TXT.search(text):
            if not _join_as_profile(page, dialog):
                break
            notes.append("chọn tham gia bằng trang cá nhân")
            continue
        if _QUESTION_TXT.search(text) and dialog.locator("textarea, input[type=radio], input[type=checkbox]").count():
            # Tu tra loi (cau mau cua kich ban) roi Gui. Khong gui duoc (vd hoi thong tin rieng) -> dong hop:
            # Facebook van gui yeu cau thi 'pending', chua gui duoc thi 'questions' (nguoi dung tu mo).
            sent, why = answer_questions(page, answer)
            notes.append("đã tự trả lời câu hỏi" + (f" ({why})" if why and sent else "") if sent else why)
            break
        if agree_rules(page):
            notes.append("đồng ý nội quy")
            continue
        break
    LAST_JOIN_NOTE["text"] = ", ".join(n for n in notes if n)
    page.wait_for_timeout(2_500)
    if is_rate_limited(page.inner_text("body")[:6000]):
        return "limited", True
    after = _membership_on_page(page)
    if after is None and any("trả lời" in n or "thông tin" in n for n in notes):
        return "questions", True
    return after or "unknown", True


_JOIN_AS_TXT = re.compile(r"(tham gia với tư cách|tham gia bằng|join as)", re.I)
_CONTINUE_BTN = re.compile(r"^\s*(Tiếp tục|Tham gia nhóm|Tham gia|Continue|Join group|Join)\s*$", re.I)


def _join_as_profile(page, dialog):
    """Hop 'Tham gia voi tu cach' (nick quan ly Trang): chon lua chon DAU (trang ca nhan) -> Tiep tuc."""
    try:
        radios = dialog.locator("[role=radio], input[type=radio]")
        if radios.count():
            radios.first.click(force=True)
            page.wait_for_timeout(600)
        button = dialog.get_by_role("button", name=_CONTINUE_BTN).last
        if not button.count():
            return False
        button.click()
        page.wait_for_timeout(4_000)
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ xac minh nhom (vao 1 phat la dang duoc)
# Da vao nhom chua chac dang duoc: bang 'Chao mung' che o dang, hop 'Quy tac nhom' bat bam Dong y, nhom chi cho
# quan tri vien dang... Xac minh = mo nhom, xu ly cac buoc do, bam o 'Ban viet gi di' thay hop 'Tao bai viet' mo
# duoc thi dong lai (KHONG dang gi). Dang bai thanh cong cung tinh la da xac minh.
_RULES_TXT = re.compile(r"(quy tắc|nội quy|group rules|\brules\b)", re.I)
_AGREE_BTN = re.compile(r"^\s*(Tôi đồng ý|Đồng ý|I agree|Agree|Tôi hiểu|Đã hiểu|Got it)\s*$", re.I)
_COMPOSER_TXT = re.compile(r"Bạn viết gì đi|Ban viet gi di|Write something", re.I)
_DISCARD_BTN = re.compile(r"^\s*(Bỏ|Bỏ bài viết|Discard)\s*$", re.I)   # hop 'Bo bai viet?' (neu co)


def agree_rules(page):
    """Hop 'Quy tac nhom' dang hien -> bam 'Toi dong y'. True neu da bam."""
    dialog = _visible_dialog(page)
    if dialog is None:
        return False
    try:
        if not _RULES_TXT.search(dialog.inner_text(timeout=2_000)[:4000]):
            return False
        buttons = dialog.get_by_role("button", name=_AGREE_BTN)
        for i in range(min(buttons.count(), 5)):
            b = buttons.nth(i)
            if b.is_visible() and b.get_attribute("aria-disabled") != "true":
                b.click()
                page.wait_for_timeout(2_500)
                print("[NOI QUY] Da bam dong y quy tac nhom.", flush=True)
                return True
    except Exception:
        pass
    return False


def _composer_trigger(page, timeout=8_000):
    main = page.locator('[role="main"]')
    scope = main.first if main.count() else page
    trigger = scope.locator("div[role='button']").filter(has_text=_COMPOSER_TXT).first
    try:
        trigger.wait_for(state="visible", timeout=timeout)
        return trigger
    except Exception:
        return None


def _composer_open(page, timeout=8_000):
    dialog = page.locator("div[role='dialog']").filter(has_text=re.compile(r"Tạo bài viết|Create post", re.I)).filter(
        has=page.locator("div[role='textbox'][contenteditable='true']"))
    try:
        dialog.first.wait_for(state="visible", timeout=timeout)
        return dialog.first
    except Exception:
        return None


# (khong dat emoji trong regex: Playwright chuyen sang regex JS khong co co 'u' -> emoji thanh 2 ky tu, khop sai)
_WAVE_BTN = re.compile(r"^\W*(Vẫy tay chào|Vẫy tay|Chào mọi người|Xin chào|Wave|Say hi|Say hello)\W*$", re.I)


def wave_hello(page):
    """Nut 'Vay tay chao' / 'Xin chao' (bang chao mung hoac dau trang nhom, Facebook tu soan san) -> bam 1 lan.
    True neu da bam. Khong tu viet bai chao."""
    dialog = _visible_dialog(page)
    scopes = ([dialog] if dialog is not None else []) + [page.locator('[role="main"]').first]
    for scope in scopes:
        try:
            buttons = scope.get_by_role("button", name=_WAVE_BTN)
            for i in range(min(buttons.count(), 5)):
                b = buttons.nth(i)
                if b.is_visible() and b.get_attribute("aria-disabled") != "true":
                    b.click()
                    page.wait_for_timeout(2_500)
                    print("[VAY TAY] Da bam vay tay chao nhom.", flush=True)
                    return True
        except Exception:
            continue
    return False


def verify_group(page, url, answer=None, wave=True):
    """Mo nhom, xu ly bang chao / quy tac, thu mo hop 'Tao bai viet' (khong dang). -> (trang thai, ghi chu, da lam).

    Trang thai: 'ready' = san sang dang · 'joined' = da vao nhung con vuong (ghi chu) · 'pending' / 'not_member' /
    'limited'. da lam: danh sach viec tool vua xu ly (tra loi cau hoi, vay tay, dong bang chao, dong y noi quy).
    Dang cho duyet ma con nut 'Tra loi cau hoi' -> tu tra loi (answer = cau mau cua kich ban).
    """
    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(5_000)
    if is_rate_limited(page.inner_text("body")[:6000]):
        return "limited", "", []
    state = _membership_on_page(page)
    if state == "pending":
        res = answer_pending_questions(page, answer)
        if res is None:
            return "pending", "", []
        return "pending", ("" if res[0] else res[1]), (["tự trả lời câu hỏi"] if res[0] else [])
    if state != "joined":
        return state or "not_member", "", []
    done = []
    if wave and wave_hello(page):
        done.append("vẫy tay chào nhóm")
    if close_group_popup(page):
        done.append("đóng bảng chào mừng")
    if agree_rules(page):
        done.append("đồng ý nội quy")
    trigger = _composer_trigger(page)
    if trigger is None:
        body = page.inner_text("body")[:8000].lower()
        if any(w in body for w in ("trả lời những câu hỏi", "câu hỏi tham gia", "answer questions")):
            return "joined", "nhóm bắt trả lời câu hỏi tham gia trước khi đăng", done
        return "joined", "không thấy ô 'Bạn viết gì đi' (nhóm có thể chỉ cho quản trị viên đăng)", done
    ok = None
    for _ in range(2):
        trigger.click()
        page.wait_for_timeout(2_500)
        ok = _composer_open(page)
        if ok is not None:
            break
        if agree_rules(page):   # hop quy tac hien khi bam o dang lan dau
            done.append("đồng ý nội quy")
        elif close_group_popup(page):
            done.append("đóng bảng chào mừng")
        else:
            break
    if ok is None:
        dialog = _visible_dialog(page)
        why = (dialog.inner_text()[:80].replace("\n", " ") if dialog is not None else "")
        page.keyboard.press("Escape")
        return "joined", "bấm ô đăng bài nhưng không mở được hộp 'Tạo bài viết'" + (f" ({why})" if why else ""), done
    page.keyboard.press("Escape")   # chua go gi -> dong hop, khong dang
    page.wait_for_timeout(1_500)
    _click_dialog_button(page, _DISCARD_BTN)
    return "ready", "", done


def open_group_tabs(playwright, base_dir, urls):
    """Mo Chrome THAT cua tai khoan, moi nhom 1 tab, de nguoi dung TU bam 'Tham gia'. Cho dong cua so."""
    acquire(base_dir)
    exe_path, _ = _browser_exe(playwright)
    profile_dir = base_dir / PROFILE_DIR_NAME
    if _profile_pids(profile_dir):
        _kill_profile_chrome(profile_dir)
        _wait_no_profile_process(profile_dir, timeout=15)
    urls = list(urls)
    args = [str(exe_path), f"--user-data-dir={profile_dir}", "--no-first-run", "--no-default-browser-check",
            "--new-window", urls[0]] + urls[1:]
    subprocess.Popen(args)
    _wait_login_window_closed(profile_dir)
    _wait_profile_released(profile_dir)


_POSTED_JS = r"""(slug) => {
    const out = []; const seen = new Set();
    for (const root of document.querySelectorAll('[role="main"]')) {
        for (const a of root.querySelectorAll('a[href*="multi_permalinks="], a[href*="/posts/"], a[href*="/permalink/"]')) {
            if (a.closest('[role="dialog"], [role="banner"], [role="navigation"], [role="complementary"]')) continue;
            const m = a.href.match(/multi_permalinks=(\d+)/) || a.href.match(/\/(?:posts|permalink)\/(\d+)/);
            if (!m || seen.has(m[1])) continue;
            if (!a.href.includes('/groups/' + slug)) continue;
            let box = a.closest('[role="article"]') || a;
            if (box === a) for (let i = 0; i < 12 && box.parentElement; i++) box = box.parentElement;
            seen.add(m[1]);
            // Dong noi dung: dong DAI NHAT cua bai (ten nguoi dang / ten nhom / ngay gio - Facebook tach tung chu
            // thanh nhieu dong - deu ngan hon).
            const lines = (box.innerText || '').split('\n').map(s => s.trim()).slice(0, 80);
            const text = lines.reduce((a, b) => b.length > a.length ? b : a, '');
            out.push({id: m[1], url: 'https://www.facebook.com/groups/' + slug + '/posts/' + m[1] + '/',
                      text: text.slice(0, 120)});
        }
    }
    return out;
}"""


def read_posted_content(page, slug, limit=40):
    """Doc muc 'Da dang' trong 'Noi dung cua ban' cua nhom -> [{'id','url','text'}] cac BAI CUA MINH da duoc duyet.

    Trang nay Facebook chi liet ke bai cua chinh minh -> dung de 'cham bai' binh luan DUNG bai cua minh.
    - Link bai lay tu nut 'Xem trong nhom' (...?multi_permalinks=<ma bai>): dong ngay gio chi co link khi re chuot.
    - CHI lay trong vung noi dung chinh: bang Thong bao / Messenger (an, luon co tren trang) chua link bai cua
      NGUOI KHAC -> lay nham thi binh luan vao bai khong phai cua minh.
    - Gom SAU MOI LAN CUON: Facebook bo bai da cuon qua khoi trang (bai moi nhat o dau se mat neu chi doc cuoi).
    """
    base = f"https://www.facebook.com/groups/{slug}/"
    try:
        page.goto(base + "my_posted_content", wait_until="domcontentloaded", timeout=45_000)
        page.wait_for_timeout(4_000)
        close_group_popup(page)
        found = {}
        for step in range(8):
            for it in page.evaluate(_POSTED_JS, slug):
                found.setdefault(it["id"], it)
            if len(found) >= limit:
                break
            page.mouse.wheel(0, 1800)
            page.wait_for_timeout(1_200)
        return list(found.values())[:limit]
    except Exception as error:
        print(f"[DA DANG] {slug}: khong doc duoc ({str(error).splitlines()[0][:60]})")
        return []
def item_statuses(group, entries):
    """Trang thai hien tai cua tung bai / binh luan da gui vao 1 nhom.

    group: so lieu nhom (read_group_content). entries: [{'time', 'kind', 'post_id', 'snippet'}].
    -> danh sach 'approved' | 'pending' | 'declined' | 'removed' | 'unchecked' (cung thu tu).
    Binh luan co ma bai: cho duyet = ma bai nam trong muc Dang cho (chinh xac). Con lai khop theo doan chu:
    doan chu xuat hien k lan trong muc nao thi k bai / binh luan CU NHAT cung doan chu do thuoc muc do.
    """
    if (group or {}).get("admin"):
        # Nick la quan tri vien nhom: bai / binh luan len ngay, khong qua duyet (Facebook khong mo 'Noi dung cua ban').
        return ["approved"] * len(entries)
    checked = (group or {}).get("items_checked", 0)
    out = ["unchecked" if not checked or checked < e["time"] else None for e in entries]
    pending_ids = set((group or {}).get("pending_ids", []))
    for i, e in enumerate(entries):
        if out[i] is None and e.get("post_id") and e["post_id"] in pending_ids:
            out[i] = "pending"
    for cat in ("pending", "declined", "removed"):
        text = (group or {}).get(f"{cat}_text", "")
        if not text:
            continue
        open_items = [i for i, e in enumerate(entries) if out[i] is None and e.get("snippet")
                      and not (cat == "pending" and e.get("post_id"))]
        for snip in {entries[i]["snippet"] for i in open_items}:
            k = text.count(snip)
            same = sorted((i for i in open_items if entries[i]["snippet"] == snip), key=lambda i: entries[i]["time"])
            for i in same[:k]:
                out[i] = cat
    return [s or "approved" for s in out]


ADMIN_NOTE_RE = re.compile(r"Quản trị viên đã (phê duyệt|gỡ|từ chối) (bài viết|bình luận) của bạn (?:trong|khỏi) "
                           r"(.+?)\s*\.", re.IGNORECASE)


def read_admin_notifications(page):
    """Thong bao 'Quan tri vien da phe duyet / go ... cua ban trong <nhom>' -> [(hanh dong, loai, ten nhom)]."""
    import unicodedata
    try:
        page.goto("https://www.facebook.com/notifications", wait_until="domcontentloaded", timeout=45_000)
        page.wait_for_timeout(4_000)
        text = unicodedata.normalize("NFC", page.evaluate("() => document.body.innerText") or "")
    except Exception:
        return []
    flat = re.sub(r"\s+", " ", text)
    return [(m.group(1).lower(), m.group(2).lower(), m.group(3).strip()) for m in ADMIN_NOTE_RE.finditer(flat)]


def load_results(acc_dir):
    try:
        st = json.loads((Path(acc_dir) / RESULTS_FILE).read_text(encoding="utf-8"))
    except Exception:
        st = {}
    for key in ("groups", "sent", "alias"):
        st.setdefault(key, {})
    st.setdefault("notes_seen", [])
    return st


def save_results(acc_dir, st):
    try:
        (Path(acc_dir) / RESULTS_FILE).write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def record_sent(acc_dir, url_or_slug, link="", kind="post", text="", post_url=""):
    """Ghi 1 lan gui (bai / binh luan) vao nhom -> lam so 'Gui 7 ngay' + biet nhom nao can kiem tra.

    Moi lan gui: [thoi diem, loai, ma bai, doan chu] -> sau nay tinh duoc trang thai tung bai (item_statuses).
    """
    slug = group_slug(url_or_slug) or url_or_slug
    if not slug:
        return
    st = load_results(acc_dir)
    now = time.time()
    sent = [t for t in st["sent"].get(slug, []) if now - t[0] < SENT_KEEP_DAYS * 86400]
    sent.append([now, kind, post_id_of(post_url), text_snippet(text)])
    st["sent"][slug] = sent
    if link:
        st["alias"][link] = slug
    save_results(acc_dir, st)


def groups_due(acc_dir, limit=8, known=()):
    """Nhom da gui >= CHECK_AFTER_HOURS ma chua kiem tra tu do; hoac con bai cho duyet va lau chua xem lai.

    known: ma nhom trong cau hinh -> nhom CHUA KIEM TRA LAN NAO cung duoc xem (lay so lieu cu, khong can doi gui moi).
    """
    st = load_results(acc_dir)
    now, due = time.time(), []
    for slug in dict.fromkeys(s for s in known if s):
        if slug not in st["groups"] and slug not in st["sent"]:
            due.append((0, slug))
    for slug, sent in st["sent"].items():
        ready = [e[0] for e in sent if now - e[0] >= CHECK_AFTER_HOURS * 3600]
        if not ready:
            continue
        g = st["groups"].get(slug, {})
        checked = g.get("checked", 0)
        waiting = (g.get("pending") or {}).get("posts", 0) + (g.get("pending") or {}).get("comments", 0)
        if checked < max(ready) or (waiting and now - checked >= RECHECK_HOURS * 3600):
            due.append((checked, slug))
    return [slug for _, slug in sorted(due)][:limit]


PROGRESS_FILE = "kiem_tra_tien_do.json"


def write_progress(acc_dir, step, text, i=0, n=0, done=False, ok=True):
    """Nut 'Kiem tra ngay': ghi buoc dang lam -> giao dien doc va hien cho nguoi dung."""
    try:
        (Path(acc_dir) / PROGRESS_FILE).write_text(json.dumps(
            {"step": step, "text": text, "i": i, "n": n, "done": done, "ok": ok, "t": time.time()},
            ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def read_progress(acc_dir):
    try:
        return json.loads((Path(acc_dir) / PROGRESS_FILE).read_text(encoding="utf-8"))
    except Exception:
        return {}


def check_results(page, acc_dir, slugs, note=print, notifications=True, progress=None):
    """Doc 'Noi dung cua ban' cua cac nhom -> luu so lieu + ghi thay doi (duoc duyet / bi tu choi / bi go).

    progress(i, n, ten): bao tien do (nut Kiem tra ngay); i = 0..n, i == n la dang doc thong bao.
    -> (so nhom doc duoc, [ten nhom Facebook khong cho xem]).
    """
    st = load_results(acc_dir)
    read_ok, no_access = 0, []
    # Mau dong nhat ky: '<icon> <Ket qua> – <Nhom> – <chi tiet>' (tab Chi tiet tach thanh cot).
    labels = {"posted": ("✅", "Được duyệt"), "declined": ("❌", "Bị từ chối"), "removed": ("🗑", "Bị gỡ")}
    for index, slug in enumerate(slugs):
        if progress:
            progress(index, len(slugs), (st["groups"].get(slug) or {}).get("name") or slug)
        try:
            info = read_group_content(page, slug)
        except Exception as error:
            print(f"[KET QUA] {slug}: khong mo duoc ({str(error).splitlines()[0][:80]})")
            continue
        if info and info.get("admin"):
            name = info["name"] or (st["groups"].get(slug) or {}).get("name") or slug
            print(f"[KET QUA] {name}: nick la quan tri vien -> bai len ngay, khong qua duyet")
            now = time.time()
            st["groups"][slug] = {"admin": True, "name": name, "checked": now, "items_checked": now}
            read_ok += 1
            continue
        if info and info.get("no_access"):
            print(f"[KET QUA] {slug}: Facebook bao khong xem duoc noi dung (chua duoc duyet vao / bi han che)")
            no_access.append((st["groups"].get(slug) or {}).get("name") or slug)
            continue
        if not info:
            print(f"[KET QUA] {slug}: khong doc duoc trang 'Noi dung cua ban'")
            continue
        read_ok += 1
        old = st["groups"].get(slug, {})
        name = info["name"] or old.get("name") or slug
        for key, (icon, label) in labels.items():
            for kind, word in (("posts", "bài"), ("comments", "bình luận")):
                diff = info[key][kind] - (old.get(key) or {}).get(kind, 0)
                if old and diff > 0:
                    note(f"   {icon} {label} – {name} – thêm {diff} {word} (Facebook đang ghi tổng {info[key][kind]})")
        # Lay link cac bai cua minh da duoc duyet (de man 'Vao cham bai' tro dung bai).
        try:
            posted = read_posted_content(page, slug)
            if posted:
                info["posted_items"] = posted
            elif old.get("posted_items"):
                info["posted_items"] = old["posted_items"]
        except Exception:
            if old.get("posted_items"):
                info["posted_items"] = old["posted_items"]
        info["checked"] = time.time()
        info["name"] = name
        st["groups"][slug] = info
        print(f"[KET QUA] {name}: cho {info['pending']} · dang {info['posted']} · tu choi {info['declined']} "
              f"· go {info['removed']}{' · xet duyet nguoi moi' if info['member_review'] else ''}")
    if notifications:
        if progress:
            progress(len(slugs), len(slugs), "")
        for action, kind, group in read_admin_notifications(page):
            key = f"{action}|{kind}|{group}"
            if key in st["notes_seen"]:
                continue
            st["notes_seen"] = (st["notes_seen"] + [key])[-200:]
            icon = {"phê duyệt": "✅", "gỡ": "🗑", "từ chối": "❌"}.get(action, "ℹ️")
            note(f"   {icon} Quản trị viên đã {action} – {group} – {kind} của bạn (theo thông báo Facebook)")
    save_results(acc_dir, st)
    return read_ok, no_access


def check_results_cli(acc_dir, slugs, open_ctx, note=print, identity=None):
    """Lenh --check-results (nut 'Kiem tra ngay'): doi tai khoan ranh -> xem tung nhom -> doc thong bao.

    Moi buoc ghi vao kiem_tra_tien_do.json de giao dien hien 'dang lam gi'. open_ctx() -> BrowserContext.
    identity (task 003): None | {"id", "name"} - khac Ca nhan -> ensure_identity truoc khi doc, ket qua ghi vao
    identity_dir(acc_dir, id), back_to_self trong finally; progress van ghi o acc_dir. (Khung: chua dung.)
    """
    n = len(slugs)
    write_progress(acc_dir, "start", "Đang chuẩn bị…", 0, n)
    try:
        if not hold_nick(acc_dir, wait_minutes=0):
            write_progress(acc_dir, "wait", "Đang chờ tài khoản rảnh: tool khác (đăng bài / theo dõi) đang dùng "
                                            "tài khoản này. Tool tự đợi tối đa 25 phút rồi kiểm tra.", 0, n)
            if not hold_nick(acc_dir, wait_minutes=25):
                raise ProfileBusy("Tai khoan ban qua 25 phut.")
        write_progress(acc_dir, "login", "Đang mở Facebook (chạy ngầm) và kiểm tra đăng nhập…", 0, n)
        context = open_ctx()
        try:
            page = get_page(context)
            verify_and_record(page, acc_dir)

            def progress(i, total, name):
                if i < total:
                    write_progress(acc_dir, "group", f"Đang xem nhóm {i + 1}/{total}: {name}", i, total)
                else:
                    write_progress(acc_dir, "notify", "Đang đọc thông báo Facebook (bài được duyệt / bị gỡ)…",
                                   total, total)
            read_ok, no_access = check_results(page, acc_dir, slugs, note=note, progress=progress)
        finally:
            context.close()
        from datetime import datetime
        if read_ok == n:
            text = f"Xong lúc {datetime.now():%H:%M} – bảng bên dưới đã được cập nhật."
        else:
            text = f"Xong lúc {datetime.now():%H:%M} – chỉ đọc được {read_ok}/{n} nhóm."
            if no_access:
                text += (f" Facebook không cho xem {len(no_access)} nhóm (có thể chưa được duyệt vào): "
                         + ", ".join(no_access[:3]) + ("…" if len(no_access) > 3 else ""))
        # 0 nhom doc duoc -> bao loi (tranh tuong da cap nhat); doc duoc 1 phan van tinh la xong.
        write_progress(acc_dir, "done", text, n, n, done=True, ok=read_ok > 0 or n == 0)
    except ProfileBusy:
        write_progress(acc_dir, "done", "Tài khoản bận quá 25 phút (tool khác đang dùng) → thử lại sau.", 0, n,
                       done=True, ok=False)
        raise
    except NotLoggedIn:
        write_progress(acc_dir, "done", "Facebook đã đăng xuất tài khoản này → vào trang tài khoản bấm Đăng nhập.",
                       0, n, done=True, ok=False)
        raise
    except Exception as error:
        write_progress(acc_dir, "done", f"Kiểm tra bị lỗi: {str(error).splitlines()[0][:120]}", 0, n,
                       done=True, ok=False)
        raise


def open_url_window(playwright, base_dir, url):
    """Nut 'Mo' tren giao dien: mo Chrome THAT cua tai khoan o trang `url`, cho nguoi dung dong cua so."""
    acquire(base_dir)
    exe_path, _ = _browser_exe(playwright)
    profile_dir = base_dir / PROFILE_DIR_NAME
    if _profile_pids(profile_dir):
        _kill_profile_chrome(profile_dir)
        _wait_no_profile_process(profile_dir, timeout=15)
    subprocess.Popen([str(exe_path), f"--user-data-dir={profile_dir}", "--no-first-run",
                      "--no-default-browser-check", "--new-window", url])
    _wait_login_window_closed(profile_dir)
    _wait_profile_released(profile_dir)


def rotate_log(log_file, max_bytes, keep=3):
    """log.txt day (> max_bytes) -> doi ten thanh log.1.txt, log.1 -> log.2 ...; giu toi da `keep` file.

    Khong xoa du lieu moi: chi file cu nhat (log.<keep-1>.txt) bi bo khi xoay vong.
    """
    log_file = Path(log_file)
    try:
        if not log_file.exists() or log_file.stat().st_size <= max_bytes:
            return
        old = lambda n: log_file.with_name(f"{log_file.stem}.{n}{log_file.suffix}")
        if old(keep - 1).exists():
            old(keep - 1).unlink()
        for n in range(keep - 2, 0, -1):
            if old(n).exists():
                old(n).replace(old(n + 1))
        log_file.replace(old(1))
    except OSError:
        # File dang mo o noi khac (vd Notepad) -> lan sau xoay vong.
        pass


USER_LOG_NAME = "nhat_ky.txt"
LOGS_DIR_NAME = "logs"
_task_log_dir = None    # dat boi use_task_log(): nhat ky cua luot dang chay ghi rieng theo task


def task_log_dir(tool_dir, task_id):
    """logs/<task>/ : log.txt + nhat_ky.txt RIENG cua tung task (Monitor: tai khoan a1, dang bai: noi dung c1).

    Nam ngoai accounts/ nen dang xuat / xoa tai khoan khong mat nhat ky.
    """
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", str(task_id)) or "_"
    path = Path(tool_dir) / LOGS_DIR_NAME / safe
    path.mkdir(parents=True, exist_ok=True)
    return path


def use_task_log(tool_dir, task_id):
    """Tu day, note() ghi vao logs/<task>/nhat_ky.txt thay vi nhat_ky.txt chung."""
    global _task_log_dir
    try:
        _task_log_dir = task_log_dir(tool_dir, task_id)
    except OSError:
        _task_log_dir = None


def note(tool_dir, text, once=False):
    """Ghi 1 dong NGAN GON cho nguoi dung vao nhat_ky.txt (kem gio). once=True: bo qua neu trung dong cuoi.

    Dang chay 1 task (use_task_log) -> ghi vao logs/<task>/nhat_ky.txt.
    Khong bao gio lam chet tool (loi ghi file -> bo qua).
    """
    from datetime import datetime
    path = Path(_task_log_dir or tool_dir) / USER_LOG_NAME
    try:
        if once and path.exists():
            with path.open("rb") as f:
                f.seek(max(0, path.stat().st_size - 600))
                last = f.read().decode("utf-8", errors="ignore").strip().splitlines()[-1:]
            if last and last[0][13:] == text:
                return
        rotate_log(path, 300_000, keep=2)
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%d/%m %H:%M}  {text}\n")
    except Exception:
        pass


ACCOUNT_LOG_NAME = "dang_nhap.log"


class SafeStream:
    """Ghi nhat ky KHONG BAO GIO lam chet tool: o day / file bi khoa -> bo qua dong do."""

    def __init__(self, stream):
        self.stream = stream

    def write(self, text):
        try:
            self.stream.write(text)
        except (OSError, ValueError):
            pass
        return len(text)

    def flush(self):
        try:
            self.stream.flush()
        except (OSError, ValueError):
            pass


def open_log_stream(log_file):
    """Mo log.txt de ghi (an toan). Khong mo duoc (o day, khong co quyen) -> bo qua nhat ky, tool van chay."""
    try:
        return SafeStream(open(log_file, "a", encoding="utf-8", buffering=1))
    except OSError:
        return SafeStream(open(os.devnull, "w", encoding="utf-8"))


class _Tee:
    def __init__(self, *streams):
        self.streams = [s for s in streams if s is not None]

    def write(self, text):
        for stream in self.streams:
            try:
                stream.write(text)
                stream.flush()
            except (OSError, ValueError):
                pass
        return len(text)

    def flush(self):
        pass


def start_account_log(base_dir, argv):
    """Ghi moi dong in ra cua lenh dang nhap / kiem tra / dang xuat vao accounts/<id>/dang_nhap.log
    (van hien tren console neu co) de biet ly do khi khong thanh cong."""
    import sys
    from datetime import datetime
    log_file = Path(base_dir) / ACCOUNT_LOG_NAME
    rotate_log(log_file, 200_000, keep=2)
    stream = open(log_file, "a", encoding="utf-8", buffering=1)
    console = sys.stdout if sys.stdout is not None and getattr(sys.stdout, "name", "") != str(log_file) else None
    sys.stdout = sys.stderr = _Tee(console, stream)
    print(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} | {' '.join(argv)} =====")


def force_release(base_dir, timeout=30):
    """Dung luot dang chay cua tai khoan (tien trinh giu khoa + Chrome cua profile) roi lay khoa.

    Chi dung khi nguoi dung chu dong bam Dang nhap / Dang xuat / Doi tai khoan.
    """
    base_dir = Path(base_dir)
    pid_file = base_dir / PID_FILE_NAME
    try:
        pid = int(pid_file.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        pid = 0
    if pid and pid != os.getpid():
        print(f"[LOGIN] Dung luot dang chay theo lich (PID {pid}) de tiep tuc.")
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
    _kill_profile_chrome(base_dir / PROFILE_DIR_NAME)
    deadline = time.time() + timeout
    while True:
        try:
            _acquire_lock(base_dir)
            return
        except ProfileBusy:
            if time.time() > deadline:
                raise
            time.sleep(1)


def acquire(base_dir, force=False):
    """Lay khoa tai khoan; force=True thi dung luot dang chay neu co."""
    try:
        _acquire_lock(base_dir)
    except ProfileBusy:
        if not force:
            raise
        force_release(base_dir)


# ------------------------------------------------------------------ trinh duyet
def find_chrome():
    """Duong dan Google Chrome that tren may, khong co thi None."""
    for path in CHROME_PATHS:
        if path.is_file():
            return path
    return None


def _browser_exe(playwright):
    chrome = find_chrome()
    if chrome:
        return chrome, "chrome"
    return Path(playwright.chromium.executable_path), None


def _user_agent(exe_path):
    """User-Agent khop phien ban that cua trinh duyet (khong co chu 'Headless').

    Chrome dat thu muc/ file manifest ten theo phien ban (vd 154.0.8037.98) canh chrome.exe.
    """
    major = None
    for item in exe_path.parent.iterdir():
        match = re.match(r"^(\d+)\.\d+\.\d+\.\d+", item.name)
        if match:
            major = max(major or 0, int(match.group(1)))
    if major is None:
        return None
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.0.0 Safari/537.36"
    )


def _has_login_cookie(context):
    return any(
        c["name"] == "c_user" for c in context.cookies(FACEBOOK_URL)
    )


def _cookie_hash(cookie_text):
    return hashlib.sha256(cookie_text.strip().encode("utf-8")).hexdigest()


def _cookies_from_text(cookie_text):
    cookies = []
    for item in cookie_text.split(";"):
        item = item.strip()
        if "=" not in item:
            continue
        name, value = item.split("=", 1)
        if name.strip():
            cookies.append({
                "name": name.strip(),
                "value": value.strip(),
                "domain": ".facebook.com",
                "path": "/",
            })
    return cookies


def _seed_from_cookie(context, base_dir, cookie_text):
    """Profile chua dang nhap + co FB_COOKIE moi -> nap vao profile 1 lan."""
    cookie_text = (cookie_text or "").strip()
    if not cookie_text or cookie_text.startswith("YOUR_") or _has_login_cookie(context):
        return

    seed_file = base_dir / PROFILE_DIR_NAME / SEED_FILE_NAME
    digest = _cookie_hash(cookie_text)
    if seed_file.exists() and seed_file.read_text(encoding="utf-8").strip() == digest:
        return  # Cookie nay da thu roi (va da het han) -> khong nap lai.

    cookies = _cookies_from_text(cookie_text)

    # Chuyen tu ban cu: fb_session.json giu xs moi nhat cua FB_COOKIE nay.
    session_file = base_dir / "fb_session.json"
    if session_file.exists():
        try:
            data = json.loads(session_file.read_text(encoding="utf-8"))
            if data.get("source_hash") == digest and data.get("cookies"):
                cookies = data["cookies"]
                print("[LOGIN] Chuyen phien tu fb_session.json sang browser_profile.")
        except Exception:
            pass

    if cookies:
        context.add_cookies(cookies)
        print(f"[LOGIN] Nap {len(cookies)} cookie vao browser_profile.")
    seed_file.write_text(digest, encoding="utf-8")


# Thu muc BO NHO DEM cua Chrome (xoa an toan, Chrome tu tao lai). KHONG gom cookie / dang nhap / du lieu trang.
CACHE_DIRS = [
    "Default/Cache", "Default/Code Cache", "Default/GPUCache",
    "GrShaderCache", "GraphiteDawnCache", "ShaderCache",
    "optimization_guide_model_store", "Crashpad/reports",
]


def _dir_size(path):
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def trim_profile_cache(profile_dir, max_mb=300):
    """browser_profile qua `max_mb` -> xoa bo nho dem cua Chrome (chi goi khi Chrome cua profile da tat)."""
    import shutil
    profile_dir = Path(profile_dir)
    if not profile_dir.exists():
        return
    size = _dir_size(profile_dir)
    if size <= max_mb * 1024 * 1024:
        return
    for rel in CACHE_DIRS:
        shutil.rmtree(profile_dir / rel, ignore_errors=True)
    after = _dir_size(profile_dir)
    print(f"[LOGIN] Don bo nho dem Chrome: {size // 1048576} MB -> {after // 1048576} MB")


def open_context(playwright, base_dir, headless=True, cookie_text=""):
    """Mo trinh duyet bang profile rieng cua tool. Tra ve BrowserContext."""
    _acquire_lock(base_dir)
    profile_dir = base_dir / PROFILE_DIR_NAME
    _wait_profile_released(profile_dir)
    trim_profile_cache(profile_dir)
    exe_path, channel = _browser_exe(playwright)
    options = dict(
        headless=headless,
        viewport={"width": 1280, "height": 900},
        locale="vi-VN",
        args=STEALTH_ARGS,
        ignore_default_args=STEALTH_IGNORE_DEFAULT_ARGS,
    )
    if channel:
        options["channel"] = channel
    user_agent = _user_agent(exe_path)
    if user_agent:
        options["user_agent"] = user_agent
    try:
        try:
            context = playwright.chromium.launch_persistent_context(str(profile_dir), **options)
        except PlaywrightError as error:
            if "existing browser session" not in str(error):
                raise
            # Da giu khoa tai khoan -> Chrome nao con dung profile nay chi la ban sot lai: tat roi thu lai.
            print("[LOGIN] Chrome cu con giu profile -> tat roi mo lai.")
            _kill_profile_chrome(profile_dir)
            _wait_no_profile_process(profile_dir, 15)
            context = playwright.chromium.launch_persistent_context(str(profile_dir), **options)
    except PlaywrightError as error:
        if "has been closed" in str(error) or "existing browser session" in str(error):
            raise ProfileBusy(
                "Khong mo duoc browser_profile (co the dang bi trinh duyet khac dung). "
                "Doi vai phut roi thu lai."
            ) from error
        raise
    _seed_from_cookie(context, base_dir, cookie_text)
    return context


def get_page(context):
    return context.pages[0] if context.pages else context.new_page()


def verify_logged_in(page):
    """Mo Facebook va kiem tra con dang nhap. Loi -> NotLoggedIn."""
    print("[LOGIN] Kiem tra dang nhap Facebook...")
    if not _has_login_cookie(page.context):
        raise NotLoggedIn(
            "Chua dang nhap hoac phien da het han. Mo MO_TOOL.bat, chon tai khoan, bam 'Dang nhap lai'."
        )
    page.goto(FACEBOOK_URL, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(2_000)

    url = page.url.lower()
    if "checkpoint" in url:
        raise NotLoggedIn(
            "Facebook dang yeu cau xac minh tai khoan. "
            "Mo MO_TOOL.bat, chon tai khoan, bam 'Dang nhap lai' va lam theo huong dan cua Facebook."
        )
    login_form = page.locator("input[name='email'], input[name='pass']").count() > 0
    if "login" in url or login_form or not _has_login_cookie(page.context):
        raise NotLoggedIn(
            "Chua dang nhap hoac phien da het han. Mo MO_TOOL.bat, chon tai khoan, bam 'Dang nhap lai'."
        )
    print("[LOGIN] OK: dang dang nhap Facebook.")


def interactive_login(playwright, base_dir, cookie_text="", force=False):
    """Mo trinh duyet THAT (khong tu dong hoa) de nguoi dung tu dang nhap.

    Cho den khi nguoi dung dong cua so. Sau do goi verify_logged_in de kiem tra.
    """
    acquire(base_dir, force)
    exe_path, _ = _browser_exe(playwright)
    profile_dir = base_dir / PROFILE_DIR_NAME
    profile_dir.mkdir(exist_ok=True)

    print()
    print("==============================================================")
    print("  Cua so trinh duyet dang mo.")
    print("  1. Dang nhap Facebook nhu binh thuong.")
    print("     Facebook hoi xac nhan tren dien thoai -> chon 'Dung, la toi'")
    print("     (KHONG chon 'Chan'), roi chon dung so hien tren may tinh.")
    print("  2. Thay trang chu Facebook thi DONG cua so trinh duyet.")
    print("  KHONG bam 'Dang xuat' trong cua so do.")
    print("==============================================================")

    # Chrome cu cua profile nay con chay (cua so cu / chay ngam) -> tat truoc, neu khong Chrome moi
    # se "nhap" vao phien cu va thoat ngay, tool tuong nguoi dung da dong cua so.
    if _profile_pids(profile_dir):
        print("[LOGIN] Tat Chrome cu cua tool con dang mo.")
        _kill_profile_chrome(profile_dir)
        _wait_no_profile_process(profile_dir, timeout=15)

    subprocess.Popen([
        str(exe_path),
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--new-window",
        FACEBOOK_URL,
    ])
    _wait_login_window_closed(profile_dir)
    print("[LOGIN] Da dong cua so dang nhap.")
    _wait_profile_released(profile_dir)


def _profile_pids(profile_dir):
    """PID cac tien trinh chrome.exe dang dung dung profile nay (theo --user-data-dir)."""
    script = (
        "Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | "
        f"Where-Object {{ $_.CommandLine -like '*{profile_dir}*' }} | "
        "ForEach-Object { $_.ProcessId }"
    )
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True,
                             text=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except Exception:
        return set()
    return {int(x) for x in out.split() if x.strip().isdigit()}


def _visible_window_pids():
    """PID cua moi tien trinh dang co cua so hien tren man hinh."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    pids = set()

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            pids.add(pid.value)
        return True

    user32.EnumWindows(each, 0)
    return pids


def _wait_login_window_closed(profile_dir, max_hours=3):
    """Cho nguoi dung dang nhap xong va dong Chrome.

    Xong khi: khong con tien trinh Chrome nao cua profile, HOAC con chay ngam nhung khong con cua so nao
    (Chrome hay chay ngam sau khi dong cua so) -> tat phan chay ngam.
    """
    start = time.time()
    no_window = 0
    while time.time() - start < max_hours * 3600:
        time.sleep(2)
        pids = _profile_pids(profile_dir)
        if not pids:
            return
        if time.time() - start < 10:
            continue                      # Chrome dang khoi dong, cua so chua kip hien
        if pids & _visible_window_pids():
            no_window = 0
        else:
            no_window += 1
            if no_window >= 3:            # ~6 giay khong con cua so nao -> nguoi dung da dong
                _kill_profile_chrome(profile_dir)
                return


def _wait_no_profile_process(profile_dir, timeout=20):
    deadline = time.time() + timeout
    while _profile_pids(profile_dir):
        if time.time() > deadline:
            return False
        time.sleep(1)
    return True


def _kill_profile_chrome(profile_dir):
    """Tat CHI cac tien trinh Chrome dung profile cua tool (khong dung Chrome cua nguoi dung)."""
    script = (
        "Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | "
        f"Where-Object {{ $_.CommandLine -like '*{profile_dir}*' }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _wait_profile_released(profile_dir, timeout=20):
    """Dong cua so xong Chrome can vai giay de tat han (co khi chay ngam) -> doi, qua lau thi tat."""
    if _wait_no_profile_process(profile_dir, timeout):
        return
    print("[LOGIN] Chrome cua tool van chay ngam -> tat no.")
    _kill_profile_chrome(profile_dir)
    _wait_no_profile_process(profile_dir, 15)


# ------------------------------------------------------------------ danh tinh: Ca nhan / Page (task 003)
# 1 nick Facebook = 1 tai khoan trong tool = 1 Chrome. Ben trong co cac danh tinh: Ca nhan ("self") + cac Page
# nick quan ly (id = gia tri cookie i_user khi dang la Page; c_user luon la id ca nhan).
# Moi luot: ensure_identity() luc dau -> lam viec -> back_to_self() trong finally -> dong Chrome.
# Hop dong day du: plans/003_mot_nick_nhieu_page.md muc 3.
IDENTITY_SELF = "self"
IDENTITY_DIR_NAME = "danh_tinh"      # du lieu theo Page: accounts/<id>/danh_tinh/<id Page>/
IDENTITIES_FILE = "danh_tinh.json"   # ket qua --read-identities: {"time": epoch, "identities": [...]}
IDENTITY_SWITCH_WAIT = 8             # giay: cho trang tai lai sau khi bam 'Chuyen sang ...'
IDENTITY_SWITCH_TIMEOUT = 30         # giay: toi da cho cookie i_user doi dung sau khi bam
READ_IDENTITIES_MAX = 10             # toi da bay nhieu Page moi lan doc danh sach (moi Page ~ IDENTITY_SWITCH_WAIT)
# File du lieu TACH THEO DANH TINH (Ca nhan: accounts/<id>/; Page: accounts/<id>/danh_tinh/<id Page>/).
# Cac file khac (browser_profile, status.json, fb_profile.json, commented_ids.txt, tin_nhan.json, tim_nhom.json,
# kiem_tra_tien_do.json, dang_nhap.log, khoa, tam nghi) giu theo NICK o accounts/<id>/.
IDENTITY_FILES = ("xin_vao_nhom.json", "nhom_da_vao.json", "ket_qua.json", "cham_bai.json", "da_binh_luan_cham.txt",
                  "nhom_tam_nghi.json", "binh_luan_loi.json")
# Nut mo menu tai khoan (goc tren phai, trong role=banner). Nhan moi truoc, nhan cu de du phong (plan 003 muc 3b).
ACCOUNT_MENU_LABELS = ("Account, your profile", "Trang cá nhân của bạn", "Your profile")
# Chu nhat ky (hien cho nguoi dung) - giao dien / test dua vao: KHONG doi chu.
IDENTITY_NOTES = {
    "ok": "👤 Đang dùng: {name}",
    "fail": "⛔ Không chuyển được sang \"{name}\": bỏ lượt, không đăng / bình luận gì để tránh dùng nhầm danh tính{shot}",
    "shot": " (ảnh: anh_loi/{file})",
    "missing": "⛔ Danh tính \"{name}\" không còn trong tài khoản {account}: bỏ lượt. Mở kịch bản chọn lại \"Đăng bằng\".",
    "back_fail": "⚠️ Chưa chuyển về Cá nhân được: lượt sau tool tự chuyển lại.",
    "not_member": "   ⏭ {name} chưa vào nhóm {group}: bỏ nhóm này, không đăng bằng Cá nhân thay.",
    "read": "👤 {account}: đọc được Cá nhân + {pages} Page.",
    "page_join": "Xin vào / rời nhóm bằng Page: chưa hỗ trợ – tool chỉ xin vào / rời bằng Cá nhân.",
}


class IdentitySwitchFailed(RuntimeError):
    """Khong chuyen duoc sang danh tinh can dung -> luot do KHONG dang / binh luan gi.

    identity_id: "self" | id Page; name: ten danh tinh; reason: ly do (khong dau, de in log);
    shot: ten file anh loi trong anh_loi/ ("" neu khong chup duoc).
    note_text: dong nhat ky dung nguyen van -> fb_login.note(BASE_DIR, error.note_text).
    """

    def __init__(self, identity_id, name, reason="", shot=""):
        super().__init__(f"Khong chuyen duoc sang danh tinh {identity_id} ({reason})")
        self.identity_id, self.name, self.reason, self.shot = identity_id, name, reason, shot

    @property
    def note_text(self):
        shot = IDENTITY_NOTES["shot"].format(file=self.shot) if self.shot else ""
        return IDENTITY_NOTES["fail"].format(name=self.name or self.identity_id, shot=shot)


def identity_dir(acc_dir, identity_id):
    """Thu muc du lieu cua danh tinh (cac file IDENTITY_FILES nam o day).

    Vao: acc_dir = accounts/<id> cua nick; identity_id = "self" | "" | None | id Page (chi chu so).
    Ra: Path. "self" / "" / None -> chinh acc_dir (giu nguyen file cu, khong chuyen du lieu);
        id Page -> acc_dir / "danh_tinh" / <id Page> (tao thu muc neu chua co).
    Loi: ValueError neu identity_id khong phai "self" va khong phai toan chu so (chan duong dan la).
    Ghi chu: progress (kiem_tra_tien_do.json), khoa, tam nghi, status, fb_profile van dung acc_dir.
    """
    raise NotImplementedError


def current_identity(page):
    """Danh tinh Chrome dang dung, doc cookie (KHONG mo trang, khong bam gi).

    Vao: page Playwright da mo facebook.com.
    Ra: gia tri cookie i_user (id Page, chuoi so) neu co; khong co i_user -> "self".
    Loi: khong raise (doc cookie loi -> "self"). Khong in gia tri cookie nao khac ra log.
    """
    raise NotImplementedError


def read_identities(page):
    """Doc danh sach danh tinh cua nick tu menu tai khoan (plan 003 muc 3b).

    Vao: page da dang nhap (dang o danh tinh nao cung duoc).
    Ra: [{"id": "self", "name": <ten ca nhan>, "kind": "self"},
         {"id": <i_user>, "name": <ten Page>, "kind": "page"}, ...] - Ca nhan luon dung dau, toi da
         READ_IDENTITIES_MAX Page. Id Page lay tu trang neu doc duoc, khong thi chuyen sang Page do de doc cookie
         i_user (moi Page ~IDENTITY_SWITCH_WAIT giay). Luon ket thuc o Ca nhan (back_to_self trong finally).
    Loi: khong mo duoc menu / khong doc duoc ten ca nhan -> RuntimeError. Facebook bao gioi han -> RuntimeError
         co chu "rate_limited" (nguoi goi pause_nick).
    """
    raise NotImplementedError


def switch_identity(page, identity_id, name):
    """Chuyen ca trang sang danh tinh `identity_id` (ten `name`) nhu nguoi that.

    Vao: identity_id "self" | id Page; name = ten hien tren nut "Chuyen sang <name>".
    Lam: current_identity(page) == identity_id -> KHONG bam gi, tra True. Khong thi mo menu tai khoan
         (ACCOUNT_MENU_LABELS), bam nut role=button "Chuyển sang <name>" (khong co -> "Xem tất cả trang cá nhân" ->
         hop "Chọn trang cá nhân" -> nut "<name>, ..."), cho IDENTITY_SWITCH_WAIT giay, kiem lai bang
         current_identity() toi da IDENTITY_SWITCH_TIMEOUT giay.
    Ra: True neu sau cung current_identity(page) == identity_id; False neu khong.
    Loi: khong raise (moi loi Playwright -> False).
    """
    raise NotImplementedError


def ensure_identity(page, identity_id, name, shot_dir=None):
    """Bao dam Chrome dang o dung danh tinh truoc khi dang / quet / binh luan / doc ket qua.

    Vao: nhu switch_identity; shot_dir = thu muc anh loi (vd BASE_DIR / "anh_loi") hoac None (khong chup).
    Ra: None khi da dung danh tinh (ke ca "self" luc khong co i_user -> khong thao tac gi tren Facebook).
    Loi: IdentitySwitchFailed(identity_id, name, reason, shot) neu switch_identity tra False; chup anh
         <yyyymmdd_HHMMSS>_danh_tinh.png vao shot_dir truoc khi raise. Nguoi goi: ghi error.note_text,
         KHONG dang / binh luan, bo luot (ma thoat 0), back_to_self trong finally.
    """
    raise NotImplementedError


def back_to_self(page, self_name=""):
    """Chuyen ve Ca nhan (goi trong finally cua MOI luot, truoc context.close()).

    Vao: self_name = ten ca nhan (account_status.read_profile(acc_dir)["name"]) - "" thi tu tim nut
         "Chuyển sang ..." tro ve ca nhan.
    Ra: True neu da o Ca nhan (khong co i_user: tra True ngay, khong thao tac); False neu chuyen khong duoc
        (nguoi goi ghi IDENTITY_NOTES["back_fail"]; luot sau ensure_identity tu sua).
    Loi: KHONG BAO GIO raise (dung trong finally).
    """
    raise NotImplementedError


def load_identities_file(acc_dir):
    """Ket qua lan --read-identities gan nhat cua nick (accounts/<id>/danh_tinh.json).

    Ra: {"time": epoch (0 neu chua doc), "identities": [... nhu read_identities ...]}. Loi doc file -> mac dinh.
    """
    raise NotImplementedError


def save_identities_file(acc_dir, identities):
    """Ghi accounts/<id>/danh_tinh.json = {"time": now, "identities": identities}. Loi ghi -> bo qua."""
    raise NotImplementedError


# ------------------------------------------------------------------ trang thai + dang xuat
def fetch_profile_name(page, base_dir):
    """Lay ten Facebook dang dung (mo facebook.com/me, doc tieu de trang) -> luu de giao dien hien.

    Dang dung duoi danh nghia Page -> la ten Page. Loi thi bo qua (khong anh huong dang nhap).
    """
    import account_status
    try:
        uid = next((c["value"] for c in page.context.cookies(FACEBOOK_URL) if c["name"] == "c_user"), "")
        page.goto("https://www.facebook.com/me", wait_until="domcontentloaded", timeout=30_000)
        # Ten nam o nhan anh dai dien dau trang ca nhan (ca nick lan Page); tieu de trang chi la du phong.
        generic = {"trang cá nhân của bạn", "your profile", "hành động với ảnh đại diện",
                   "profile picture actions", "ảnh đại diện", "profile picture", "facebook"}
        name = ""
        for _ in range(8):
            page.wait_for_timeout(1_000)
            labels = page.locator("div[role='main'] svg[aria-label]").evaluate_all(
                "els => els.map(e => e.getAttribute('aria-label'))")
            name = next((x.strip() for x in labels if x and x.strip().lower() not in generic), "")
            if name:
                break
        if not name:
            # Page chua co anh dai dien: nhan anh khong co ten -> doc menu tai khoan (goc tren phai),
            # dong dau tien la ten tai khoan / Page dang dung.
            try:
                page.locator("[aria-label='Trang cá nhân của bạn'], [aria-label='Your profile']").first.click(timeout=5_000)
                menu = page.locator("div[role='dialog']").last
                menu.wait_for(state="visible", timeout=5_000)
                page.wait_for_timeout(1_000)
                lines = [x.strip() for x in menu.inner_text(timeout=3_000).splitlines() if x.strip()]
                if lines and lines[0].lower() not in generic:
                    name = lines[0]
                page.keyboard.press("Escape")
            except Exception:
                pass
        if not name:
            title = page.title() or ""
            name = re.sub(r"^\(\d+\+?\)\s*", "", title)
            name = re.sub(r"\s*[|\-–]\s*Facebook\s*$", "", name).strip()
        if name and name.lower() != "facebook":
            account_status.write_profile(base_dir, name, uid)
            print(f"[LOGIN] Tai khoan Facebook: {name}")
        else:
            account_status.write_profile(base_dir, "", uid)   # khong lay duoc -> khong thu lai moi lan chay
    except Exception as error:
        print(f"[LOGIN] Khong lay duoc ten tai khoan: {str(error).splitlines()[0][:120]}")


def verify_and_record(page, base_dir, fetch_name=False):
    """verify_logged_in + ghi trang thai tai khoan (account_status) de giao dien / lich biet."""
    import account_status
    before = account_status.read(base_dir)["status"]
    try:
        verify_logged_in(page)
    except NotLoggedIn as error:
        # Dang hoat dong ma bi mat dang nhap -> het han; con lai -> chua dang nhap.
        status = account_status.EXPIRED if before in (account_status.OK, account_status.UNKNOWN) else account_status.LOGGED_OUT
        account_status.write(base_dir, status, str(error))
        raise
    account_status.write(base_dir, account_status.OK)
    # Ten tai khoan: lay khi Dang nhap / Kiem tra, hoac 1 lan duy nhat khi chua co (lan chay theo lich dau tien).
    if fetch_name or not (Path(base_dir) / account_status.PROFILE_FILE).exists():
        fetch_profile_name(page, base_dir)


def _logout_on_facebook(page):
    """Bam Dang xuat tren Facebook (huy phien tren may chu). Thanh cong -> True."""
    if not _has_login_cookie(page.context):
        return True
    deadline = time.time() + 20
    page.goto(FACEBOOK_URL, wait_until="domcontentloaded", timeout=30_000)
    if not _has_login_cookie(page.context):
        return True
    menus = [
        "div[role='button'][aria-label='Trang cá nhân của bạn']",
        "div[role='button'][aria-label='Your profile']",
        "[aria-label='Trang cá nhân của bạn']",
        "[aria-label='Your profile']",
        "div[role='banner'] div[role='button'] image",
    ]
    try:
        page.locator(", ".join(menus)).first.wait_for(timeout=8_000)
    except Exception:
        pass
    for selector in menus:
        if time.time() > deadline:
            break
        try:
            menu = page.locator(selector).first
            if menu.count() == 0:
                continue
            menu.click(timeout=3_000)
            item = page.get_by_role("button", name=re.compile(r"^(Đăng xuất|Log out)$")).first
            try:
                item.wait_for(timeout=3_000)
            except Exception:
                item = page.get_by_text(re.compile(r"^(Đăng xuất|Log out)$")).first
            item.click(timeout=3_000)
            for _ in range(20):
                page.wait_for_timeout(500)
                if not _has_login_cookie(page.context):
                    return True
        except Exception:
            continue
    return not _has_login_cookie(page.context)


def remove_profile(profile_dir, timeout=10):
    """Xoa browser_profile. Dung tien to \\\\?\\ de xoa duoc ca duong dan dai hon 260 ky tu
    (Chrome tao thu muc con rat sau) va bo thuoc tinh chi doc neu co."""
    import shutil
    import stat
    long_path = "\\\\?\\" + str(Path(profile_dir).resolve())

    def force_writable(func, path, *_):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except OSError:
            pass

    deadline = time.time() + timeout
    while os.path.exists(long_path):
        try:
            if sys.version_info >= (3, 12):
                shutil.rmtree(long_path, onexc=force_writable)
            else:
                shutil.rmtree(long_path, onerror=force_writable)
        except OSError:
            pass
        if not os.path.exists(long_path) or time.time() > deadline:
            break
        time.sleep(0.3)
    return not os.path.exists(long_path)


def logout(playwright, base_dir, force=False):
    """Dang xuat tai khoan cua tool: dang xuat tren Facebook (neu duoc) + XOA du lieu dang nhap da luu.

    Tra ve True neu da dang xuat duoc tren Facebook; False neu chi xoa duoc du lieu tren may
    (phien cu tren Facebook khong con cookie nao dung duoc, co the go them trong 'Noi ban da dang nhap').
    """
    import account_status
    base_dir = Path(base_dir)
    profile_dir = base_dir / PROFILE_DIR_NAME
    on_facebook = False
    acquire(base_dir, force)
    if profile_dir.exists():
        try:
            context = open_context(playwright, base_dir, headless=True)
            try:
                on_facebook = _logout_on_facebook(get_page(context))
            finally:
                context.close()
        except ProfileBusy:
            raise
        except Exception as error:
            print(f"[LOGOUT] Khong dang xuat duoc tren Facebook: {error}")
        _wait_profile_released(profile_dir)
        remove_profile(profile_dir)
    account_status.write(base_dir, account_status.LOGGED_OUT,
                         "Đã đăng xuất." if on_facebook else "Đã xóa dữ liệu đăng nhập trên máy.")
    account_status.clear_profile(base_dir)
    print("[LOGOUT] " + ("Da dang xuat tren Facebook va xoa du lieu dang nhap."
                         if on_facebook else "Da xoa du lieu dang nhap tren may."))
    return on_facebook


# ------------------------------------------------------------------ danh tinh vong 2 (task 003, plan muc 3.10)
# Khung (Architect): chu ky + docstring; than do Dev A viet. Dat cuoi file de khong dung khoi Dev A da sua.
# Moi luot / lenh dung Chrome lam viec theo danh tinh goi: begin_identity() (dau luot) -> assert_identity()
# truoc MOI bai dang / binh luan / xin vao / roi nhom -> end_identity() trong finally.
PROFILE_PAGE_ID_KEY = "page_id"   # khoa them trong accounts/<id>/fb_profile.json: i_user luc ghi ten ("" = Ca nhan)
IDENTITY_NOTES.update({
    "legacy": "⚠️ {account}: Chrome đang ở Page \"{name}\" (tài khoản Page kiểu cũ) → vẫn chạy bằng Page này như "
              "trước, không tự chuyển về Cá nhân. Nên Gộp tài khoản này vào tài khoản Cá nhân của nick (màn tài khoản "
              "→ nút Gộp) để chỉ dùng 1 Chrome.",
    "changed": "⛔ Danh tính đang dùng bị đổi giữa chừng (cần \"{name}\"): dừng lượt, không đăng / bình luận tiếp để "
               "tránh dùng nhầm danh tính.",
    "legacy_read": "Chrome của tài khoản này đang ở Page \"{name}\" (tài khoản Page kiểu cũ) → không đọc danh sách Page "
                   "ở đây (đọc sẽ đổi danh tính đang đăng). Hãy Gộp tài khoản này vào tài khoản Cá nhân của nick rồi "
                   "đọc danh sách Page ở tài khoản Cá nhân.",
    "join_as_missing": "không thấy \"{name}\" trong hộp \"Tham gia với tư cách\" → không xin, để tránh xin nhầm danh tính",
})


class IdentityChanged(IdentitySwitchFailed):
    """Truoc 1 bai dang / binh luan / xin vao / roi nhom: cookie i_user khong con dung danh tinh cua luot
    (Facebook tu chuyen, nguoi dung bam tay trong Chrome...). Nguoi goi: ghi note_text, DUNG ca luot (khong lam
    nhom / bai con lai), end_identity trong finally, ma thoat 0. La IdentitySwitchFailed -> cac cho da bat loi chuyen
    danh tinh cung bat duoc; nhung PHAI goi assert_identity NGOAI cac khoi `except RuntimeError / Exception` nuot loi.
    """

    @property
    def note_text(self):
        return IDENTITY_NOTES["changed"].format(name=self.name or self.identity_id)


def legacy_page_id(page, acc_dir):
    """Tai khoan Page kieu cu? (plan 003 muc 3.10a) - CHI doc cookie + file, khong mo trang, khong bam gi.

    Kieu cu = danh_tinh.json cua nick (load_identities_file(acc_dir)) KHONG co Page nao (chua tung bam 'Doc danh
    sach Page') VA Chrome dang co cookie i_user (dang o 1 Page - kieu cu: moi Page 1 tai khoan tool, tu chuyen Chrome
    sang Page bang tay).
    Ra: id Page (i_user) neu la kieu cu; "" neu khong (dang o Ca nhan, hoac nick da co danh sach Page -> i_user la do
        luot truoc bi ngat, begin_identity tu sua). Loi: khong raise (loi doc -> "").
    """
    raise NotImplementedError


def self_name_of(acc_dir):
    """Ten Ca nhan dung cho back_to_self / ensure_identity("self") - MOI script dung ham nay (khong tu doc file).

    Thu tu: muc "self" trong danh_tinh.json (load_identities_file) > ten trong fb_profile.json NEU file do khong co
    page_id (khong co thi do la ten Page kieu cu, khong dung) > "". Loi: khong raise -> "".
    """
    raise NotImplementedError


def begin_identity(page, acc_dir, identity_id, name, tool_dir, account_name="", shot_dir=None):
    """Buoc 2-3 cua luot (plan 003 muc 3.5 + 3.10), goi ngay SAU verify_and_record, ca khi la Ca nhan.

    Vao: identity_id = post_as cua muc / --identity ("self" | id Page); name = post_as_name ("" voi Page = Page khong
         con / missing); tool_dir = BASE_DIR (ghi note); account_name = ten tai khoan (cho dong nhat ky);
         shot_dir None -> tool_dir / "anh_loi".
    Lam (dung thu tu):
      1. Page ma name == "" -> note IDENTITY_NOTES["missing"], tra None. KHONG thao tac Facebook (PM cau 13).
      2. "self" va legacy_page_id(page, acc_dir) = P -> KHONG bam gi; note IDENTITY_NOTES["legacy"] (once=True;
         name = ten trong fb_profile.json neu page_id == P, khong thi P). Tra run kieu cu (PM cau 12 = A1).
      3. Con lai: ensure_identity(page, id, name hoac self_name_of(acc_dir), shot_dir). IdentitySwitchFailed -> note
         error.note_text, tra None. Page -> note IDENTITY_NOTES["ok"].
    Ra: None = bo luot (da ghi nhat ky). Hoac run = {"id": id danh tinh cho identity_dir / join_state ("self" voi kieu
        cu - du lieu kieu cu o acc_dir nhu truoc), "expect": id phai thay o cookie truoc moi bai (kieu cu: P),
        "name": ten danh tinh dang dung ("" = Ca nhan), "legacy": bool}.
    Loi: khong raise (tru loi Playwright khong lien quan danh tinh - nguoi goi xu ly nhu cu).
    """
    raise NotImplementedError


def end_identity(page, acc_dir, tool_dir):
    """Buoc 5 (finally cua MOI luot, truoc context.close()). page None -> True.

    Kieu cu (legacy_page_id(page, acc_dir) khac "") -> KHONG bam gi, tra True (khong bao gio tu ve Ca nhan - PM cau
    12). Con lai -> back_to_self(page, self_name_of(acc_dir)); False -> note IDENTITY_NOTES["back_fail"].
    Ra: True neu dang o danh tinh dung de dong Chrome. Loi: KHONG BAO GIO raise.
    """
    raise NotImplementedError


def assert_identity(page, expect_id, name=""):
    """Kiem cookie i_user truoc MOI bai dang / binh luan / xin vao / roi nhom (PM cau 14). CHI doc cookie.

    Vao: expect_id = run["expect"] cua begin_identity ("self" | id Page); name = run["name"] (cho dong nhat ky).
    Ra: None neu current_identity(page) == expect_id.
    Loi: lech -> raise IdentityChanged(expect_id, name, "i_user khong khop"). Khong chup anh, khong bam gi.
    """
    raise NotImplementedError


def nick_join_usage(acc_dir):
    """Gioi han xin vao nhom tinh chung CA NICK (Ca nhan + moi Page - cau PM 7 doi).

    Doc xin_vao_nhom.json o acc_dir va moi acc_dir/danh_tinh/<id so>/ (khong tao thu muc).
    Ra: {"today": so lan da BAM xin vao hom nay (cong moi danh tinh, nhu joins_today), "last": epoch lan bam xin gan
        nhat (0 neu chua)}. Nguoi goi: today >= per_day -> dung; truoc lan bam dau tien cho them
        JOIN_WAIT_SECONDS - (now - last) neu > 0. Loi doc file -> bo qua file do, khong raise.
    """
    raise NotImplementedError
