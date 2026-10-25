# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
import time
import re
import sys
import json
import html
import hashlib
import threading
import unicodedata
import requests
from datetime import datetime
from pathlib import Path
import os
from collections import OrderedDict

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError
)

import fb_login
import account_status
import monitor_store


# ============================================================
# PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

CONFIG_FILE = BASE_DIR / "fb_monitor_config.txt"

# DEBUG_IMAGE removed

# file to persist commented post IDs
COMMENTED_IDS_FILE = BASE_DIR / "commented_ids.txt"

# file lưu ID bài đã bắn Telegram (để chạy --once không gửi trùng)
SENT_IDS_FILE = BASE_DIR / "sent_ids.txt"

LOG_FILE = BASE_DIR / "log.txt"


# ============================================================
# GLOBAL
# ============================================================

CURRENT_CONFIG = {}

TOTAL_DETECTED_POSTS = 0

# Tối đa số ID được giữ trong RAM / file
MAX_STORED_IDS = 100

COMMENTED_IDS = OrderedDict()



# ============================================================
# CONFIG
# ============================================================

def load_config():

    if not CONFIG_FILE.exists():

        raise FileNotFoundError(
            f"\nKhông tìm thấy:\n{CONFIG_FILE}\n\n"
            "Hãy đặt fb_monitor_config.txt "
            "cùng thư mục với file PY."
        )

    config = {}

    with CONFIG_FILE.open(
        "r",
        encoding="utf-8-sig"
    ) as f:

        for raw in f:

            line = raw.strip()

            if (
                not line
                or line.startswith("#")
                or "=" not in line
            ):
                continue

            key, value = line.split(
                "=",
                1
            )

            config[key.strip()] = value.strip()

    return config


# ============================================================
# CONFIG REQUIRED
# ============================================================

def required(config, key):

    value = config.get(
        key,
        ""
    ).strip()

    if (
        not value
        or value.startswith("YOUR_")
        or value.startswith("DAN_")
    ):

        raise ValueError(
            f"❌ Chưa điền {key} "
            "trong fb_monitor_config.txt"
        )

    return value


# ============================================================
# ĐỌC LIST
# ============================================================

def get_list(config, key):

    value = config.get(
        key,
        ""
    ).strip()

    if not value:
        return []

    return [
        x.strip()
        for x in value.split("|")
        if x.strip()
    ]



# ============================================================
# ĐỌC DANH SÁCH GROUP
#
# Ưu tiên GROUP_URLS.
# Nếu GROUP_URLS trống thì dùng GROUP_URL cũ.
# Các group ngăn cách bằng dấu |
# ============================================================

def get_group_urls(config):

    group_urls = get_list(
        config,
        "GROUP_URLS"
    )

    if group_urls:
        return group_urls

    old_group_url = config.get(
        "GROUP_URL",
        ""
    ).strip()

    if old_group_url:
        return [old_group_url]

    return []

# ============================================================
# ĐỌC SỐ
# ============================================================

def get_int(config, key, default):

    try:

        return int(
            config.get(
                key,
                default
            )
        )

    except:

        return default


# ============================================================
# ĐỌC LUẬT ĐIỂM QUẢNG CÁO
# ============================================================

def get_score_rules(config, key):

    value = config.get(
        key,
        ""
    ).strip()

    if not value:
        return []

    rules = []

    for item in value.split("|"):

        item = item.strip()

        if not item:
            continue

        if "=" not in item:
            item = f"{item}=3"     # khong ghi diem = 3 diem

        pattern, score = item.rsplit(
            "=",
            1
        )

        pattern = pattern.strip()

        try:

            score = int(
                score.strip()
            )

        except:

            continue

        if pattern:

            rules.append(
                (
                    pattern,
                    score
                )
            )

    return rules


# ============================================================
# SO SÁNH KHÔNG PHÂN BIỆT HOA THƯỜNG
#
# Dùng NFKD (Compatibility Decomposition) thay vì NFC vì 2 lý do:
#
# 1. Gộp chữ tiếng Việt có dấu về cùng 1 dạng, tránh trường hợp
#    cùng một chữ nhưng được lưu ở 2 dạng Unicode khác nhau
#    (dựng sẵn vs tổ hợp) khiến so khớp bị sai lệch.
#
# 2. QUAN TRỌNG: giải mã các ký tự "in đậm/in nghiêng cách điệu"
#    (Unicode Mathematical Alphanumeric Symbols, VD: 𝐙𝐚𝐥𝐨, 𝟖𝟎𝐤)
#    mà nhiều bài quảng cáo cố tình dùng để né bộ lọc từ khóa.
#    NFC KHÔNG xử lý được các ký tự này vì chúng không phải là
#    dấu tổ hợp, mà là ký tự hoàn toàn khác thuộc khối Unicode
#    riêng (U+1D400–U+1D7FF). NFKD có sẵn compatibility mapping
#    để chuyển các ký tự này về đúng chữ Latin/số gốc.
# ============================================================

def normalize_text_for_match(value):

    if not value:
        return ""

    return unicodedata.normalize(
        "NFKD",
        value
    ).casefold()


# Ky tu chu / so / dau tieng Viet (sau NFKD dau tach thanh ky tu rieng U+0300-U+036F).
_WORD_CHAR = r"[\w\u0300-\u036f]"


def contains_keyword(text, keyword):

    if not text or not keyword:
        return False

    needle = normalize_text_for_match(keyword.strip())
    haystack = normalize_text_for_match(text)

    # Tu ngan 1 chu (ib, sg, hcm, q8, spa, ks...) -> phai dung rieng thanh 1 tu,
    # tranh khop nham vao giua tu khac hoac giua duong link (vd "ib" trong "mibextid").
    if len(keyword.strip()) <= 3 and " " not in keyword.strip():
        return re.search(
            f"(?<!{_WORD_CHAR}){re.escape(needle)}(?!{_WORD_CHAR})",
            haystack
        ) is not None

    return needle in haystack


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(
    text,
    token,
    chat_id
):

    url = (
        "https://api.telegram.org/"
        f"bot{token}/sendMessage"
    )

    try:

        response = requests.post(

            url,

            json={

                "chat_id":
                    chat_id,

                "text":
                    text,

                "parse_mode":
                    "HTML",

                "disable_web_page_preview":
                    False

            },

            timeout=20
        )

        if response.ok:
            return True

        print(
            "❌ Telegram lỗi:",
            response.text
        )

        return False

    except Exception as e:

        print(
            "❌ Telegram exception:",
            e
        )

        return False


# ============================================================
# PERSISTENT COMMENTED IDS
# ============================================================


def add_limited_id(id_store, post_id, max_count=MAX_STORED_IDS):
    """
    Thêm ID vào bộ nhớ RAM và chỉ giữ tối đa max_count ID.

    ID mới nhất nằm cuối. Khi vượt giới hạn, ID cũ nhất
    sẽ bị xóa trước (FIFO).
    """

    if not post_id:
        return

    # Nếu ID đã tồn tại thì đưa nó thành ID mới nhất.
    if post_id in id_store:
        del id_store[post_id]

    id_store[post_id] = None

    while len(id_store) > max_count:

        old_id, _ = id_store.popitem(last=False)

        print(
            f"   🗑️ RAM: Xóa ID cũ nhất do vượt {max_count}: {old_id}"
        )


# Bai da binh luan: nho nhieu hon (chong binh luan lap = chong spam).
MAX_COMMENTED_IDS = 2000


def comment_fingerprint(text):
    """Dau van tay noi dung bai: cung 1 bai nhung ID doi (ID that / CONTENT_..., sua bai o cuoi) van nhan ra.
    Bai ngan (< 50 chu cai) khong dung: nhieu khach viet y het nhau ("Minh can lam thiep online a")."""
    import hashlib
    norm = re.sub(r"[^0-9a-zà-ỹđ]+", "", unicodedata.normalize("NFC", text or "").lower())
    if len(norm) < 50:
        return ""
    return "TXT_" + hashlib.md5(norm[:60].encode("utf-8")).hexdigest()[:24]


def post_keys(post_id, post_url, text):
    """Moi khoa nhan dien 1 bai: ID tool dung, ID THAT trong link, dau van tay noi dung.

    Cung 1 bai co the ra ID khac nhau giua cac lan quet (CONTENT_... / ID that) -> so tat ca khoa.
    Bai ngan: dau van tay gan voi NHOM (cung cau ngan y het trong cung nhom = cung bai).
    """
    import hashlib
    keys = [k for k in (post_id, get_post_id(post_url or "")) if k]
    fp = comment_fingerprint(text)
    if fp:
        keys.append(fp)
    else:
        g = re.search(r"/groups/([^/?#]+)", post_url or "")
        norm = re.sub(r"[^0-9a-zà-ỹđ]+", "", unicodedata.normalize("NFC", text or "").lower())
        if g and len(norm) >= 15:
            keys.append("TXS_" + hashlib.md5((g.group(1) + "|" + norm[:60]).encode("utf-8")).hexdigest()[:24])
    return list(dict.fromkeys(keys))


def load_commented_ids(path, max_count=None):
    """
    Đọc ID đã comment từ file TXT.
    Chỉ giữ tối đa 100 ID mới nhất.
    """

    result = OrderedDict()

    try:

        if not path.exists():
            return result

        with path.open(
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:

                post_id = line.strip()

                if not post_id:
                    continue

                # Nếu file có ID trùng thì chỉ giữ một record,
                # đồng thời coi nó là ID mới nhất.
                if post_id in result:
                    del result[post_id]

                result[post_id] = None

        # Đảm bảo RAM không bao giờ quá 100 ID.
        while len(result) > (max_count or MAX_STORED_IDS):

            old_id, _ = result.popitem(
                last=False
            )

            print(
                f"   🗑️ FILE: Bỏ ID cũ khi load do vượt {MAX_STORED_IDS}: {old_id}"
            )

        # Nếu file cũ có hơn 100 dòng thì ghi lại file sạch ngay.
        try:

            with path.open(
                "w",
                encoding="utf-8"
            ) as f:

                for post_id in result:
                    f.write(f"{post_id}\n")

        except Exception as e:

            print(
                "   ⚠️ Không thể chuẩn hóa file commented_ids.txt:",
                e
            )

        return result

    except Exception as e:

        print(
            "   ⚠️ Không load được commented IDs:",
            e
        )

        return OrderedDict()


def save_limited_commented_id(
    path,
    id_store,
    post_id,
    max_count=MAX_STORED_IDS
):
    """
    Lưu ID bài đã hoàn tất comment vào RAM + file TXT.

    File luôn được ghi lại theo thứ tự cũ -> mới và không bao giờ
    vượt quá max_count record. Khi vượt giới hạn, record cũ nhất
    bị xóa trước.
    """

    if not post_id:
        return False

    # --------------------------------------------------------
    # 1. CẬP NHẬT RAM
    # --------------------------------------------------------

    add_limited_id(
        id_store,
        post_id,
        max_count
    )

    # --------------------------------------------------------
    # 2. ĐỌC FILE HIỆN TẠI
    # --------------------------------------------------------

    ids = []

    try:

        if path.exists():

            with path.open(
                "r",
                encoding="utf-8"
            ) as f:

                for line in f:

                    value = line.strip()

                    if value:
                        ids.append(value)

    except Exception as e:

        print(
            "   ⚠️ Không đọc được file comment ID:",
            e
        )

    # --------------------------------------------------------
    # 3. BỎ RECORD TRÙNG VỚI ID MỚI
    # --------------------------------------------------------

    ids = [
        value
        for value in ids
        if value != post_id
    ]

    # --------------------------------------------------------
    # 4. ID MỚI NHẤT ĐƯA XUỐNG CUỐI
    # --------------------------------------------------------

    ids.append(post_id)

    # --------------------------------------------------------
    # 5. CHỈ GIỮ 100 RECORD CUỐI
    # --------------------------------------------------------

    if len(ids) > max_count:

        removed_count = len(ids) - max_count
        old_ids = ids[:removed_count]
        ids = ids[removed_count:]

        for old_id in old_ids:

            print(
                f"   🗑️ FILE: Xóa ID comment cũ do vượt {max_count}: {old_id}"
            )

    # --------------------------------------------------------
    # 6. ĐỒNG BỘ LẠI RAM THEO FILE
    # --------------------------------------------------------

    id_store.clear()

    for value in ids:
        id_store[value] = None

    # --------------------------------------------------------
    # 7. GHI LẠI FILE
    # --------------------------------------------------------

    try:

        with path.open(
            "w",
            encoding="utf-8"
        ) as f:

            for value in ids:
                f.write(f"{value}\n")

        print(
            f"   💾 Đã cập nhật {path}: {len(ids)}/{max_count} ID"
        )

        return True

    except Exception as e:

        print(
            "   ⚠️ Không ghi được file comment ID:",
            e
        )

        return False


# ============================================================
# COMMENT HELPERS
# ============================================================


def find_comment_image(file_name):
    """Ảnh comment: CHỈ dùng ảnh riêng đã chọn cho nhóm theo dõi (giao diện → Chọn ảnh...).

    Không lấy ảnh chung (thư mục tool / Downloads) nữa: nhóm thiệp cưới từng bị gửi nhầm ảnh
    quảng cáo thú cưng. Chưa chọn ảnh → chỉ bình luận chữ.
    """

    # Thu muc anh (giong ben dang bai): moi binh luan lay NGAU NHIEN 1 anh trong thu muc.
    folder = CURRENT_CONFIG.get("COMMENT_MEDIA_FOLDER", "")
    if folder and Path(folder).is_dir():
        import random
        pics = [f for f in Path(folder).iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif")]
        if pics:
            return random.choice(pics)

    key = "COMMENT_IMAGE_2" if file_name == "facebook2.jpg" else "COMMENT_IMAGE_1"
    own = CURRENT_CONFIG.get(key, "")

    if own and Path(own).exists():
        return Path(own)

    return Path(own or f"(chua chon anh {file_name})")


def prepare_comment_text(config, matched_keywords):

    fixed = config.get("COMMENT_TEXT", "").strip()

    if fixed:

        return fixed

    # fallback default
    keywords_text = ", ".join(matched_keywords) if matched_keywords else ""

    text = "Bên mình nhận trông giữ chó mèo, hỗ trợ đưa đón, thực đơn pate tươi xuyên suốt"

    if keywords_text:

        text = f"[{keywords_text}] " + text

    return text



def paste_or_upload_comment_image(page, form, image_path):
    """Chọn ảnh comment qua nút ảnh Facebook, không dùng Ctrl+V."""
    if not image_path:
        print("      ⚠️ Chưa có đường dẫn ảnh.")
        return False

    image_path = Path(image_path)
    if not image_path.exists():
        print(f"      ❌ Không tìm thấy ảnh: {image_path}")
        return False

    print("      🖼️ Chọn ảnh bằng nút ảnh Facebook...")
    print(f"      ➤ File ảnh: {image_path}")

    # Cach 1: o chon file AN trong chinh khung binh luan -> dua anh thang vao (khong can bam nut).
    if form is not None:
        try:
            inputs = form.locator("input[type='file']")
            if inputs.count() == 0:
                # o file co the nam ngay cap cha cua form binh luan
                inputs = form.locator("xpath=..").locator("input[type='file']")
            if inputs.count() > 0:
                inputs.first.set_input_files(str(image_path))
                print("      ✅ Đã đưa ảnh vào ô chọn file của khung bình luận.")
                page.wait_for_timeout(10000)
                return True
        except Exception as e:
            print(f"      ⚠️ Ô chọn file của khung bình luận không dùng được: {str(e)[:80]}")

    # Cach 2 (cu): bam the li thu 3 trong hang bieu tuong duoi o binh luan.
    try:
        action_lists = None
        list_count = 0
        if form is not None:
            try:
                action_lists = form.locator(
                    "[data-id='unfocused-state-actions-list']"
                )
                list_count = action_lists.count()
            except:
                list_count = 0

        if list_count == 0:
            action_lists = page.locator(
                "[data-id='unfocused-state-actions-list']"
            )
            try:
                list_count = action_lists.count()
            except:
                list_count = 0

        print(f"      🔎 unfocused-state-actions-list: {list_count} kết quả")
        if list_count == 0:
            print("      ❌ Không tìm thấy unfocused-state-actions-list.")
            return False

        action_list = None
        for i in range(list_count):
            candidate = action_lists.nth(i)
            try:
                if candidate.is_visible():
                    action_list = candidate
                    break
            except Exception:
                pass
        if action_list is None:
            action_list = action_lists.nth(0)

        lis = action_list.locator("li")
        li_count = lis.count()
        print(f"      🔎 Số thẻ li: {li_count}")
        if li_count < 3:
            print("      ❌ Không đủ 3 thẻ li.")
            return False

        # Tim nut anh theo TEN (thu tu cac nut doi theo nick: co / khong co "nhan dan avatar").
        third_li = None
        for k in range(li_count):
            try:
                label = lis.nth(k).locator("[aria-label]").first.get_attribute("aria-label", timeout=1000) or ""
            except Exception:
                label = ""
            if re.search(r"ảnh|photo|image", label, re.IGNORECASE):
                third_li = lis.nth(k)
                print(f"      ➤ Nút ảnh: '{label}' (vị trí {k + 1})")
                break
        if third_li is None:
            third_li = lis.nth(2)
        try:
            third_li.scroll_into_view_if_needed(timeout=2000)
        except Exception:
            pass

        print("      ➤ Click thẻ li thứ 3...")
        try:
            with page.expect_file_chooser(timeout=7000) as fc_info:
                third_li.click(timeout=4000)
            file_chooser = fc_info.value
            print("      ➤ Windows Open đã được kích hoạt.")
            print(f"      ➤ Chọn ảnh: {image_path.name}")
            file_chooser.set_files(str(image_path))
            print("      ✅ Đã chọn ảnh.")
        except PlaywrightTimeoutError:
            print("      ❌ Click li thứ 3 nhưng không bắt được file chooser.")
            return False
        except Exception as e:
            print(f"      ❌ Lỗi file chooser: {e}")
            return False

        print("      ⏳ Chờ Facebook load ảnh...")
        page.wait_for_timeout(10000)
        print("      ✅ Ảnh đã được đưa vào comment.")
        return True
    except Exception as e:
        print(f"      ❌ Lỗi chọn ảnh Facebook: {e}")
        return False


# Ket qua lan binh luan gan nhat -> ghi nhat ky cu the (da hien / cho duyet / loi vi sao).
COMMENT_RESULT = {"status": "", "detail": "", "no_image": False}

COMMENT_PENDING_HINTS = ["chờ phê duyệt", "chờ quản trị viên", "chờ duyệt", "đang chờ xét duyệt",
                         "sẽ hiển thị sau khi", "awaiting approval"]
COMMENT_ERROR_HINTS = ["không thể đăng bình luận", "không thể bình luận", "bình luận không được đăng",
                       "tạm thời bị chặn", "bạn bị chặn", "đã xảy ra lỗi", "thử lại sau", "không gửi được",
                       "giới hạn tần suất", "couldn't post", "try again later", "temporarily blocked"]


def comment_fail(detail):
    COMMENT_RESULT.update(status="loi", detail=detail)
    return False


# ------------------------------------------------------------------ chong binh luan lap lai khi hong
# Bai binh luan hong 2 lan -> bo qua bai do. Nhom hong "khong thay khung binh luan" lien tiep 3 bai khac nhau
# -> ngung tu binh luan nhom do 3 / 7 / 14 ngay (tai pham lau hon; van bao Telegram).
# Facebook bao gioi han -> ca tai khoan nghi 48h / 72h / 7 ngay (fb_login.pause_nick).
# Giao dien doc cung file nay de hien nhom dang nghi + nut Reset (monitor_store.pause_notes).
COMMENT_FAIL_FILE_NAME = "binh_luan_loi.json"
MAX_COMMENT_TRIES = 2
# GROUP_FAIL_LIMIT / GROUP_PAUSE_DAYS: monitor_store (nguoi dung sua o tab Setting nang cao > Rule khi loi)
LOW_DISK_MB = 2048


def _account_dir():
    return Path(COMMENTED_IDS_FILE).parent


def _load_fail_state():
    try:
        st = json.loads((_account_dir() / COMMENT_FAIL_FILE_NAME).read_text(encoding="utf-8"))
    except Exception:
        st = {}
    st.setdefault("posts", {})
    st.setdefault("groups", {})
    return st


def _save_fail_state(st):
    posts = st["posts"]
    if len(posts) > 500:   # giu 500 bai gan nhat
        st["posts"] = dict(list(posts.items())[-500:])
    try:
        (_account_dir() / COMMENT_FAIL_FILE_NAME).write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        print(f"   ⚠️ Không ghi được {COMMENT_FAIL_FILE_NAME}: {e}")


def _group_of(post_url):
    m = re.search(r"/groups/([^/?#]+)", post_url or "")
    return m.group(1) if m else ""


def comment_skip_reason(keys, post_url):
    """Ly do KHONG binh luan bai nay (rong = duoc binh luan)."""
    pause = fb_login.nick_pause(_account_dir())
    if pause:
        return f"tài khoản đang tạm nghỉ đến {fb_login.pause_text(pause)} ({pause.get('reason', '')})"
    st = _load_fail_state()
    g = st["groups"].get(_group_of(post_url)) or {}
    if g.get("until", 0) > time.time():
        return (f"nhóm {_group_of(post_url)} đang ngừng tự bình luận đến "
                f"{datetime.fromtimestamp(g['until']):%H:%M %d/%m} ({g.get('reason', '')})")
    if max((st["posts"].get(k, 0) for k in keys), default=0) >= MAX_COMMENT_TRIES:
        return f"đã thử bình luận {MAX_COMMENT_TRIES} lần không được"
    return ""


def record_comment_fail(page, keys, post_url, detail, telegram_token, telegram_chat_id):
    st = _load_fail_state()
    first_time = max((st["posts"].get(k, 0) for k in keys), default=0) == 0
    for k in keys:
        st["posts"][k] = st["posts"].get(k, 0) + 1
    group = _group_of(post_url)
    if group and first_time and "không thấy khung bình luận" in (detail or ""):
        g = st["groups"].setdefault(group, {"fails": 0, "until": 0, "level": 0})
        g["fails"] = g.get("fails", 0) + 1
        if g["fails"] >= monitor_store.GROUP_FAIL_LIMIT:
            g["level"] = g.get("level", 0) + 1
            days = monitor_store.GROUP_PAUSE_DAYS[min(g["level"], len(monitor_store.GROUP_PAUSE_DAYS)) - 1]
            g["until"], g["fails"], g["days"] = time.time() + days * 86400, 0, days
            g["reason"] = (f"{monitor_store.GROUP_FAIL_LIMIT} bài liền không thấy khung bình luận – nhóm chặn thành viên mới "
                           f"bình luận / tài khoản chưa đủ quyền (lần {g['level']}, nghỉ {days} ngày)")
            msg = (f"⏸ Nhóm {group}: ngừng tự bình luận {days} ngày – {g['reason']}. "
                   f"Vẫn quét và báo Telegram khách mới.")
            fb_login.note(BASE_DIR, msg)
            send_telegram(html.escape(msg), telegram_token, telegram_chat_id)
    _save_fail_state(st)

    try:
        page_text = page.evaluate("() => document.body.innerText")
    except Exception:
        page_text = ""
    if fb_login.is_rate_limited(detail) or fb_login.is_rate_limited(page_text):
        info = fb_login.pause_nick(_account_dir(), f"Facebook giới hạn tần suất khi bình luận ở nhóm {group or '?'}")
        msg = (f"⛔ Facebook đang giới hạn tần suất bình luận của tài khoản này (lần {info['strikes']}) → tạm nghỉ "
               f"bình luận + đăng bài {info['hours']} giờ, đến {fb_login.pause_text(info)}. "
               f"Tool vẫn quét và báo Telegram khách mới.")
        fb_login.note(BASE_DIR, msg)
        send_telegram(html.escape(msg), telegram_token, telegram_chat_id)


def record_comment_ok(post_url):
    """Binh luan duoc -> nhom het bi tinh loi (lan nghi sau lai tu 3 ngay) + ghi de ~2 tieng sau xem da duyet chua."""
    if _group_of(post_url):
        fb_login.record_sent(_account_dir(), post_url, link=_group_of(post_url), kind="comment",
                             text=CURRENT_CONFIG.get("COMMENT_TEXT", ""), post_url=post_url)
    st = _load_fail_state()
    g = st["groups"].get(_group_of(post_url))
    if g and (g.get("fails") or g.get("level")):
        g["fails"] = g["level"] = 0
        _save_fail_state(st)


def warn_low_disk(telegram_token, telegram_chat_id):
    """O dia sap day -> khong luu duoc bai da bao -> bao trung Telegram, Chrome loi. Bao toi da 6 tieng/lan."""
    free = fb_login.disk_free_mb(BASE_DIR)
    if free < 0 or free >= LOW_DISK_MB:
        return
    mark = Path(os.environ.get("TEMP") or BASE_DIR) / "fb_monitor_disk_warn.txt"
    try:
        if time.time() - mark.stat().st_mtime < 6 * 3600:
            return
    except OSError:
        pass
    msg = (f"⚠️ Ổ đĩa máy chạy tool sắp ĐẦY (còn {free} MB). Tool không lưu được bài đã báo → "
           f"sẽ báo TRÙNG khách cũ, bình luận lặp lại, Chrome dễ lỗi. Hãy dọn ổ đĩa ngay.")
    print(msg)
    fb_login.note(BASE_DIR, msg, once=True)
    send_telegram(html.escape(msg), telegram_token, telegram_chat_id)
    try:
        mark.write_text("1", encoding="utf-8")
    except OSError:
        pass


def count_text_on_page(page, needle):
    try:
        return page.evaluate("n => (document.body.innerText.split(n).length - 1)", needle)
    except Exception:
        return -1


def comment_snippet(comment_text):
    """Doan CHU THUAN dai nhat trong binh luan (bo bieu tuong 💌🔥: Facebook ve thanh anh, khong co trong chu trang)."""
    runs = re.findall(r"[0-9A-Za-zÀ-ỹĐđ][0-9A-Za-zÀ-ỹĐđ ,.!?:()%-]{10,}", comment_text or "")
    best = max(runs, key=len, default="").strip()
    return best[:25] if len(best) >= 10 else ""


def check_comment_outcome(page, snippet, count_before, text_before=""):
    """Sau khi Enter: binh luan da hien / Facebook bao cho duyet / bao loi / chua thay.

    count_before: so lan doan binh luan co tren trang LUC CON nam trong o nhap.
    Gui xong o nhap trong -> binh luan hien ra thi so lan >= truoc, chua hien thi it hon 1.
    """
    try:
        text = page.evaluate("() => document.body.innerText.toLowerCase()")
    except Exception:
        text = ""
    for kind, hints in (("loi", COMMENT_ERROR_HINTS), ("cho_duyet", COMMENT_PENDING_HINTS)):
        for hint in hints:
            # Chi tinh thong bao MOI hien ra sau khi gui (khong tinh chu co san trong bai khac).
            if text.count(hint) > text_before.count(hint):
                i = text.rfind(hint)
                return kind, " ".join(text[max(0, i - 40): i + 80].split())
    if snippet and count_before > 0 and count_text_on_page(page, snippet) >= count_before:
        return "da_hien", ""
    return "chua_thay", ""


def type_comment_text(page, target_loc, text, slow=False):
    """Nhap noi dung (co the nhieu dong). Xuong dong = Shift+Enter: Enter tron se GUI binh luan ngay."""
    lines = (text or "").replace("\r\n", "\n").split("\n")
    if slow:
        target_loc.click()
        target_loc.type(lines[0], delay=20)
    else:
        target_loc.fill(lines[0])
    for line in lines[1:]:
        page.keyboard.press("Shift+Enter")
        if line:
            if slow:
                page.keyboard.type(line, delay=20)
            else:
                page.keyboard.insert_text(line)


def verify_comment_sent(page, textbox, original_text, timeout_ms=5000):

    try:

        end = time.time() + (timeout_ms / 1000.0)

        while time.time() < end:

            cur = ""

            try:
                cur = textbox.input_value()
            except:
                try:
                    cur = textbox.evaluate("el => (el.innerText || el.value || '')")
                except:
                    cur = ""

            if not cur:
                return True

            # So bo qua khoang trang / xuong dong (o nhap co the hien xuong dong khac chu goc).
            if " ".join(original_text.split()) not in " ".join(cur.split()):
                return True

            page.wait_for_timeout(500)

    except Exception:

        return False

    return False


def close_post_dialog(page, timeout_ms=15000):
    """
    Đóng sạch toàn bộ dialog sau khi comment.

    Facebook có thể xuất hiện 2 lớp dialog:
      1. Dialog bài viết -> nút aria-label="Đóng".
      2. Nếu comment chưa hoàn tất, Facebook mở dialog xác nhận
         "Rời khỏi trang?" -> phải click nút aria-label="Rời khỏi Trang"
         (nút xác nhận ở phía dưới), KHÔNG click nút "Đóng" của dialog này.

    Hàm chỉ trả True khi KHÔNG còn dialog modal nào trên DOM/hiển thị.
    Vì vậy vòng scroll chỉ được chạy sau khi hàm này hoàn tất.
    """

    deadline = time.time() + (timeout_ms / 1000.0)
    last_state = None

    def visible_enabled(locator):
        try:
            return locator.is_visible() and locator.is_enabled()
        except Exception:
            try:
                return locator.is_visible()
            except Exception:
                return False

    def dialog_count():
        try:
            return page.locator('div[role="dialog"][aria-modal="true"]').count()
        except Exception:
            return 0

    while time.time() < deadline:
        try:
            dialogs = page.locator('div[role="dialog"][aria-modal="true"]')
            count = dialogs.count()
        except Exception:
            count = 0

        if count == 0:
            # Chờ thêm một nhịp ngắn để chắc chắn Facebook không vừa tạo lại
            # dialog confirmation sau animation của nút Close.
            page.wait_for_timeout(300)
            if dialog_count() == 0:
                print("      ✅ Đã đóng hoàn toàn tất cả dialog.")
                return True
            continue

        # ------------------------------------------------------------
        # 1. ƯU TIÊN XỬ LÝ DIALOG XÁC NHẬN "Rời khỏi Trang"
        # ------------------------------------------------------------
        # Không dùng class x... vì class Facebook thay đổi liên tục.
        # Dùng aria-label ổn định hơn.
        leave_selectors = [
            'div[aria-label="Rời khỏi Trang"][role="button"]',
            '[role="button"][aria-label="Rời khỏi Trang"]',
            'div[aria-label="Leave Page"][role="button"]',
            '[role="button"][aria-label="Leave Page"]',
        ]

        leave_clicked = False
        for selector in leave_selectors:
            try:
                buttons = page.locator(selector)
                n = buttons.count()
            except Exception:
                n = 0

            # Đi từ cuối lên vì Facebook thường render button thật sau các
            # bản aria-hidden/disabled dùng cho accessibility.
            for i in range(n - 1, -1, -1):
                try:
                    btn = buttons.nth(i)
                    if not visible_enabled(btn):
                        continue

                    print(
                        "      ⚠️ Facebook hiện dialog 'Rời khỏi trang?' "
                        "→ click 'Rời khỏi Trang' để đóng hẳn..."
                    )
                    btn.scroll_into_view_if_needed(timeout=1500)
                    btn.click(timeout=3000)
                    leave_clicked = True
                    break
                except Exception:
                    continue

            if leave_clicked:
                break

        if leave_clicked:
            # Quan trọng: KHÔNG scroll ngay. Chờ confirmation dialog biến mất
            # hoàn toàn và chờ animation của Facebook kết thúc.
            for _ in range(30):
                page.wait_for_timeout(250)
                if dialog_count() == 0:
                    page.wait_for_timeout(300)
                    if dialog_count() == 0:
                        print(
                            "      ✅ Đã click 'Rời khỏi Trang' "
                            "và dialog xác nhận đã biến mất hoàn toàn."
                        )
                        return True
            continue

        # ------------------------------------------------------------
        # 2. CHƯA CÓ CONFIRMATION -> ĐÓNG DIALOG BÀI VIẾT
        # ------------------------------------------------------------
        try:
            dialog = dialogs.nth(count - 1)
        except Exception:
            dialog = None

        close_selectors = [
            'div[aria-label="Đóng"][role="button"]',
            '[role="button"][aria-label="Đóng"]',
            'div[aria-label="Close"][role="button"]',
            '[role="button"][aria-label="Close"]',
        ]

        close_clicked = False
        if dialog is not None:
            for selector in close_selectors:
                try:
                    buttons = dialog.locator(selector)
                    n = buttons.count()
                except Exception:
                    n = 0

                for i in range(n - 1, -1, -1):
                    try:
                        btn = buttons.nth(i)
                        if not visible_enabled(btn):
                            continue

                        print("      ➤ Click nút Đóng dialog bài viết...")
                        btn.click(timeout=3000)
                        close_clicked = True
                        break
                    except Exception:
                        continue

                if close_clicked:
                    break

        if close_clicked:
            # Chờ sau click Close. Nếu comment thất bại, Facebook có thể
            # tạo confirmation dialog trong khoảng thời gian này.
            page.wait_for_timeout(400)
            continue

        # ------------------------------------------------------------
        # 3. FALLBACK ESCAPE
        # ------------------------------------------------------------
        state = f"{count}:{last_state}"
        if state != last_state:
            print("      ⚠️ Không tìm thấy nút đóng phù hợp → thử Escape...")
            last_state = state

        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

        page.wait_for_timeout(400)

    # ------------------------------------------------------------
    # KIỂM TRA CUỐI: tuyệt đối không cho scroll nếu dialog còn tồn tại.
    # ------------------------------------------------------------
    remaining = dialog_count()
    if remaining == 0:
        print("      ✅ Dialog đã đóng hoàn toàn.")
        return True

    print(
        f"      ❌ Vẫn còn {remaining} dialog sau "
        f"{timeout_ms / 1000:.1f}s → KHÔNG được scroll."
    )
    return False


def post_comment_on_facebook(page, post_url, comment_text, image_path=None):
    """Comment theo permalink.

    Luồng bắt buộc:
    1. Mở permalink.
    2. Tìm FORM có textbox con.
    3. Nhập TEXT trước.
    4. Từ chính FORM đó tìm unfocused-state-actions-list.
    5. Click LI thứ 3 để chọn ảnh.
    6. Chờ ảnh load đủ lâu.
    7. ENTER để gửi.
    """

    try:

        if not post_url:
            return False

        print(f"   ↪️ Mở bài để comment: {post_url}")
        page.goto(
            post_url,
            wait_until="domcontentloaded",
            timeout=30000
        )
        page.wait_for_timeout(1500)

        # Bài có ảnh: ô bình luận hiện chậm → chờ tối đa 10s cho ô hiện ra
        try:
            page.locator(
                "form [contenteditable='true']:visible"
            ).first.wait_for(state="visible", timeout=10000)
        except Exception:
            pass

        # --------------------------------------------------------
        # TÌM FORM CÓ TEXTBOX CON
        # --------------------------------------------------------
        form_loc = None
        target_loc = None

        forms = page.locator("form")
        form_count = 0

        try:
            form_count = forms.count()
        except:
            form_count = 0

        print(f"      🔎 Tổng số FORM trên trang: {form_count}")

        for i in range(form_count):

            try:
                candidate = forms.nth(i)

                if not candidate.is_visible():
                    continue

                target = candidate.locator(
                    "[contenteditable='true'], textarea, input[type='text']"
                ).first

                try:
                    target_count = target.count()
                except:
                    target_count = 0

                if target_count <= 0:
                    continue

                if not target.is_visible():
                    continue

                form_loc = candidate
                target_loc = target
                print(
                    f"      ✅ Tìm được FORM chứa textbox tại vị trí {i + 1}."
                )
                break

            except Exception as e:
                print(
                    f"      ⚠️ Lỗi kiểm tra FORM {i + 1}: {e}"
                )

        # --------------------------------------------------------
        # FALLBACK SELECTOR CŨ
        # --------------------------------------------------------
        if form_loc is None or target_loc is None:

            print(
                "      ⚠️ Không tìm được FORM chứa textbox → thử selector textbox cũ."
            )

            selectors = [
                "div[aria-label='Viết bình luận']",
                "div[aria-label='Write a comment']",
                "div[role='textbox']",
                "textarea",
                "div[contenteditable='true']"
            ]

            for sel in selectors:

                try:
                    loc = page.locator(sel)
                    count = loc.count()

                    print(
                        f"      ➤ Kiểm tra selector '{sel}': {count} kết quả"
                    )

                    for i in range(count):
                        candidate = loc.nth(i)

                        try:
                            if not candidate.is_visible():
                                continue

                            target_loc = candidate
                            form_loc = candidate.locator(
                                "xpath=ancestor::form[1]"
                            )

                            if form_loc.count() == 0:
                                form_loc = None

                            break

                        except:
                            pass

                    if target_loc is not None:
                        break

                except Exception as e:
                    print(
                        f"      ⚠️ Lỗi selector '{sel}': {e}"
                    )

        if target_loc is None:

            print(
                "   ⚠️ Không tìm thấy khung bình luận."
            )

            return False

        try:
            target_loc.click(timeout=3000)
        except:
            pass

        page.wait_for_timeout(500)

        # --------------------------------------------------------
        # 1. NHẬP TEXT TRƯỚC
        # --------------------------------------------------------
        print(
            "      ➤ BƯỚC 1: Nhập text comment trước..."
        )

        text_ok = False

        try:
            type_comment_text(page, target_loc, comment_text)
            text_ok = True
        except:
            try:
                type_comment_text(page, target_loc, comment_text, slow=True)
                text_ok = True
            except Exception as e:
                print(
                    "      ⚠️ Không nhập được text:",
                    e
                )

        if not text_ok:
            return False

        page.wait_for_timeout(1000)
        print("      ✅ Đã nhập text.")

        # --------------------------------------------------------
        # 2. TÌM FORM → unfocused-state-actions-list → LI THỨ 3
        # --------------------------------------------------------
        if image_path and os.path.exists(image_path):

            print(
                "      ➤ BƯỚC 2: Tìm unfocused-state-actions-list trong FORM..."
            )

            if form_loc is None:
                print(
                    "      ❌ Không có FORM để tìm nút ảnh."
                )
                return False

            image_ok = paste_or_upload_comment_image(
                page,
                form_loc,
                image_path
            )

            if not image_ok:
                print(
                    "      ❌ Không thể đưa ảnh vào comment."
                )
                return False

            print(
                "      ✅ Đã chọn ảnh."
            )

            # Chờ lâu hơn để Facebook render thumbnail/attachment.
            print(
                "      ⏳ Chờ Facebook load ảnh trước khi Enter... 8 giây"
            )
            page.wait_for_timeout(8000)

        else:
            print(
                "      ℹ️ Không có ảnh comment → bỏ qua bước ảnh."
            )

        # --------------------------------------------------------
        # 3. ENTER SAU KHI TEXT + ẢNH ĐÃ SẴN SÀNG
        # --------------------------------------------------------
        print(
            "      ➤ BƯỚC 3: Press Enter để gửi..."
        )

        try:
            target_loc.press("Enter")
            print(
                "      ✅ Đã press Enter."
            )
        except Exception as e:
            print(
                "      ⚠️ Press Enter thất bại:",
                e
            )
            return False

        print(
            "      ➤ Chờ Facebook render comment... (10 giây)"
        )
        page.wait_for_timeout(10000)

        try:
            if verify_comment_sent(
                page,
                target_loc,
                comment_text,
                timeout_ms=5000
            ):
                print(
                    "      ✅ Comment đã gửi thành công (ảnh + text)."
                )
                return True

            print(
                "      ⚠️ Không xác nhận được comment đã gửi."
            )
            return False

        except Exception as e:
            print(
                "      ⚠️ Lỗi khi kiểm tra comment:",
                e
            )
            return False

    except Exception as e:

        print(
            "   ❌ Lỗi khi comment theo permalink:",
            e
        )

        return False

    finally:

        print(
            "      ➤ Kiểm tra/đóng dialog sau comment permalink..."
        )
        close_post_dialog(
            page,
            timeout_ms=10000
        )

def post_comment_on_article(page, post_id, comment_text, image_path=None, post_text=None):
    """Comment trực tiếp trong story_message.

    Luồng chính:
    1. Định vị story_message (theo data-bot-post-id hoặc so khớp nội dung text).
    2. Từ story_message đi lên 3 cấp cha để lấy container bao trùm bài viết.
    3. Tìm nút có aria-label="Viết bình luận" (hoặc data-ad-rendering-role="comment_button") và click để mở khung comment.
    4. Tìm textbox và form bên trong container.
    5. Nhập text -> Đính ảnh (nếu có) -> Enter gửi comment.
    """

    try:

        fb_login.close_group_popup(page)   # bang chao mung nhom che nut 'Viet binh luan'

        selector = f"[data-bot-post-id='{post_id}']"
        loc = page.locator(selector)

        try:
            count = loc.count()
        except:
            count = 0

        print(
            f"   ↪️ Tìm bài trên DOM bằng selector {selector}: {count} kết quả"
        )

        article = None
        if count > 0:
            article = loc.nth(0)
        else:
            # Fallback: duyệt qua tất cả story_message trên trang để tìm đúng bài
            print(
                f"   🔎 data-bot-post-id={post_id} không thấy trên DOM, fallback tìm theo nội dung bài..."
            )
            try:
                stories = page.locator('div[data-ad-rendering-role="story_message"]').all()
                for st in stories:
                    try:
                        st_text = st.inner_text().strip()
                        if not st_text:
                            continue
                        if post_text and (post_text[:30] in st_text or st_text[:30] in post_text):
                            article = st
                            st.evaluate("(el, id) => el.setAttribute('data-bot-post-id', id)", post_id)
                            print("      ✅ Tìm thấy bài qua so khớp nội dung text!")
                            break
                        elif post_id.startswith("CONTENT_") and hashlib.sha1(st_text[:1500].encode("utf-8", errors="ignore")).hexdigest()[:24] in post_id:
                            article = st
                            st.evaluate("(el, id) => el.setAttribute('data-bot-post-id', id)", post_id)
                            print("      ✅ Tìm thấy bài qua SHA1 hash!")
                            break
                    except:
                        pass
            except Exception as e:
                print(f"      ⚠️ Lỗi quét fallback story_message: {e}")

        if article is None and post_text:
            # Facebook go bai da cuon qua khoi trang -> cuon nguoc len tim lai.
            for step in range(12):
                page.mouse.wheel(0, -1400)
                page.wait_for_timeout(1200)
                try:
                    for st in page.locator('div[data-ad-rendering-role="story_message"]').all():
                        st_text = (st.inner_text() or "").strip()
                        if st_text and (post_text[:30] in st_text or st_text[:30] in post_text):
                            article = st
                            st.evaluate("(el, id) => el.setAttribute('data-bot-post-id', id)", post_id)
                            print(f"      ✅ Cuộn ngược {step + 1} lần thì tìm lại được bài.")
                            break
                except Exception:
                    pass
                if article is not None:
                    break

        if article is None:
            print(
                "   ⚠️ Không tìm thấy bài trên trang để comment (in-article)."
            )
            return comment_fail("không tìm thấy bài trên trang (bài đã trôi khỏi màn hình / bị ẩn)")

        # --------------------------------------------------------
        # BƯỚC 1: ĐI LÊN 3 CẤP VÀ CLICK NÚT "Viết bình luận"
        # --------------------------------------------------------
        print(
            "      ➤ Từ story_message đi lên 3 cấp cha để tìm nút 'Viết bình luận'..."
        )

        btn_clicked = False
        try:
            btn_clicked = article.evaluate(
                """(el) => {
                    try {
                        let node = el;
                        for (let i = 0; i < 3 && node.parentElement; i++) {
                            node = node.parentElement;
                        }
                        if (!node) return false;

                        // Đánh dấu container bài viết
                        node.setAttribute('data-bot-post-container', '1');

                        // Tìm nút "Viết bình luận"
                        const btn = node.querySelector(
                            'div[aria-label="Viết bình luận"], ' +
                            'div[aria-label="Write a comment"], ' +
                            'div[data-ad-rendering-role="comment_button"], ' +
                            '[role="button"][aria-label*="bình luận"], ' +
                            '[role="button"][aria-label*="comment"]'
                        );

                        if (btn) {
                            btn.click();
                            return true;
                        }
                        return false;
                    } catch (e) {
                        return false;
                    }
                }"""
            )
        except Exception as e:
            print(
                f"      ⚠️ Lỗi khi click nút Viết bình luận: {e}"
            )

        if btn_clicked:
            print(
                "      ✅ Đã click nút 'Viết bình luận'. Đang chờ khung comment mở ra..."
            )
            page.wait_for_timeout(1500)
        else:
            print(
                "      ℹ️ Không tìm thấy nút 'Viết bình luận' (có thể khung comment đã mở sẵn)."
            )

        # --------------------------------------------------------
        # BƯỚC 2: TÌM FORM VÀ TEXTBOX (CÓ RETRY CHỜ KHUNG LOAD XONG)
        # --------------------------------------------------------
        form_loc = None
        target_loc = None

        print("      🔎 Đang dò tìm ô nhập bình luận (textbox) và FORM...")

        # Thử trong tối đa 10 lần (10 x 500ms = 5 giây) để chờ DOM Facebook render xong
        for attempt in range(10):
            try:
                res = article.evaluate(
                    """(el) => {
                        try {
                            // 1. Kiểm tra phần tử đang được active (Facebook thường tự focus vào textbox)
                            let active = document.activeElement;
                            let target = null;
                            let form = null;

                            if (active && (active.isContentEditable || active.getAttribute('role') === 'textbox' || active.tagName === 'TEXTAREA')) {
                                target = active;
                            }

                            // 2. Đi ngược lên các cấp cha để bao quát toàn bộ khu vực bình luận của bài
                            let root = el;
                            for (let i = 0; i < 8 && root.parentElement; i++) {
                                root = root.parentElement;
                                if (!target) {
                                    const tb = root.querySelector(
                                        'div[role="textbox"][contenteditable="true"], ' +
                                        'div[contenteditable="true"], ' +
                                        'div[role="textbox"], ' +
                                        'div[aria-label*="bình luận"][role="textbox"], ' +
                                        'div[aria-label*="câu trả lời"][role="textbox"], ' +
                                        'textarea'
                                    );
                                    if (tb && (tb.offsetWidth > 0 || tb.offsetHeight > 0)) {
                                        target = tb;
                                    }
                                }
                                if (target) {
                                    form = target.closest('form') || 
                                           root.querySelector('form') || 
                                           target.closest('[data-id="unfocused-state-actions-list"]')?.parentElement;
                                    if (form) break;
                                }
                            }

                            if (target) {
                                target.setAttribute('data-bot-comment-target', '1');
                                if (form) {
                                    form.setAttribute('data-bot-comment-form', '1');
                                } else if (target.parentElement) {
                                    target.parentElement.setAttribute('data-bot-comment-form', '1');
                                }
                                return { found: true, has_form: !!form };
                            }

                            return { found: false };
                        } catch (e) {
                            return { found: false, error: String(e) };
                        }
                    }"""
                )

                if res and res.get("found"):
                    target_loc = page.locator("[data-bot-comment-target='1']").first
                    form_loc = page.locator("[data-bot-comment-form='1']").first
                    print(f"      ✅ Đã tìm thấy khung bình luận sau {(attempt + 1) * 0.5:.1f}s!")
                    break

            except Exception as e:
                pass

            page.wait_for_timeout(500)

        # --------------------------------------------------------
        # FALLBACK NẾU CHƯA TÌM THẤY
        # --------------------------------------------------------
        if target_loc is None or target_loc.count() == 0:
            fallbacks = [
                "div[role='textbox'][contenteditable='true']",
                "div[aria-label*='Viết bình luận'][role='textbox']",
                "div[contenteditable='true']",
                "div[role='textbox']",
                "textarea"
            ]
            for sel in fallbacks:
                candidates = page.locator(sel)
                c_count = 0
                try:
                    c_count = candidates.count()
                except:
                    c_count = 0
                for i in range(c_count):
                    c = candidates.nth(i)
                    try:
                        if c.is_visible():
                            target_loc = c
                            f = c.locator("xpath=ancestor::form[1]")
                            if f.count() > 0:
                                form_loc = f.first
                            print(f"      ✅ Fallback tìm thấy textbox qua selector: {sel}")
                            break
                    except:
                        pass
                if target_loc is not None:
                    break

        if target_loc is None:
            print(
                "   ⚠️ Không tìm thấy khung bình luận bên trong bài."
            )
            return comment_fail("không thấy khung bình luận (nhóm tắt bình luận / chưa đủ quyền / bài bị khóa)")

        try:
            target_loc.scroll_into_view_if_needed(timeout=2500)
        except:
            pass

        try:
            target_loc.click(timeout=2500)
        except:
            pass

        page.wait_for_timeout(500)

        # --------------------------------------------------------
        # 1. NHẬP TEXT TRƯỚC
        # --------------------------------------------------------
        print(
            "      ➤ BƯỚC 1: Nhập text comment trước..."
        )

        text_ok = False

        try:
            type_comment_text(page, target_loc, comment_text)
            text_ok = True
        except:
            try:
                type_comment_text(page, target_loc, comment_text, slow=True)
                text_ok = True
            except:
                try:
                    lines = comment_text.split("\n")
                    page.keyboard.type(lines[0], delay=15)
                    for line in lines[1:]:
                        page.keyboard.press("Shift+Enter")
                        page.keyboard.type(line, delay=15)
                    text_ok = True
                except Exception as e:
                    print(
                        "      ⚠️ Không nhập được text vào target:",
                        e
                    )

        if not text_ok:
            print("      ❌ Nhập text thất bại.")
            return comment_fail("không nhập được chữ vào ô bình luận")

        page.wait_for_timeout(1000)
        print(
            "      ✅ Đã nhập text."
        )

        # --------------------------------------------------------
        # 2. SAU ĐÓ MỚI TÌM ACTION LIST VÀ ẢNH
        # --------------------------------------------------------
        if image_path and os.path.exists(image_path):

            if form_loc is None or form_loc.count() == 0:
                try:
                    f = target_loc.locator("xpath=ancestor::form[1]")
                    if f.count() > 0:
                        form_loc = f.first
                except:
                    pass

            print(
                "      ➤ BƯỚC 2: Tìm unfocused-state-actions-list trong FORM..."
            )

            image_ok = paste_or_upload_comment_image(
                page,
                form_loc,
                image_path
            )

            if not image_ok:
                # Khong kem duoc anh -> van binh luan bang chu (khong bo khach).
                print(
                    "      ⚠️ Không đính kèm được ảnh → vẫn gửi bình luận chỉ có chữ."
                )
                COMMENT_RESULT["no_image"] = True
                try:
                    target_loc.click(timeout=3000)
                except Exception:
                    pass
            else:
                print(
                    "      ✅ Ảnh đã được đưa vào comment."
                )

                print(
                    "      ⏳ Chờ Facebook load ảnh trước khi Enter... 8 giây"
                )
                page.wait_for_timeout(8000)

        else:
            print(
                "      ℹ️ Không có ảnh comment."
            )

        # --------------------------------------------------------
        # 3. ENTER
        # --------------------------------------------------------
        print(
            "      ➤ BƯỚC 3: Press Enter để gửi..."
        )
        snippet = comment_snippet(comment_text)
        count_before = count_text_on_page(page, snippet) if snippet else -1
        try:
            text_before = page.evaluate("() => document.body.innerText.toLowerCase()")
        except Exception:
            text_before = ""

        try:
            target_loc.press("Enter")
            print(
                "      ✅ Đã press Enter."
            )
        except Exception:
            try:
                page.keyboard.press("Enter")
                print(
                    "      ✅ Đã press Enter (qua keyboard)."
                )
            except Exception as e:
                print(
                    "      ⚠️ Press Enter thất bại:",
                    e
                )
                return comment_fail("không bấm được Enter để gửi")

        print(
            "      ➤ Chờ Facebook render comment... (10 giây)"
        )
        page.wait_for_timeout(10000)

        try:
            if verify_comment_sent(
                page,
                target_loc,
                comment_text,
                timeout_ms=5000
            ):
                print(
                    "      ✅ Comment đã gửi thành công (ảnh + text)."
                )
                status, msg = check_comment_outcome(page, snippet, count_before, text_before)
                print(f"      🔎 Kết quả sau khi gửi: {status} {msg}")
                if status == "loi":
                    return comment_fail(f"Facebook báo: {msg}")
                COMMENT_RESULT.update(status=status, detail=msg)

                # --------------------------------------------------------
                # BƯỚC 4: TẮT DIALOG BÀI VIẾT NẾU ĐANG MỞ
                # --------------------------------------------------------
                print(
                    "      ➤ Đang đóng dialog bài viết..."
                )
                dialog_closed = False
                try:
                    # Thử tìm và click nút Đóng trên dialog
                    dialog_closed = page.evaluate(
                        """() => {
                            try {
                                // 1. Tìm nút Đóng chính xác theo selector
                                const closeSelectors = [
                                    'div[aria-label="Đóng"][role="button"]',
                                    'div[aria-label="Close"][role="button"]',
                                    'div[role="dialog"] div[aria-label="Đóng"]',
                                    'div[role="dialog"] div[aria-label="Close"]',
                                    'div[aria-label="Đóng"]',
                                    'div[aria-label="Close"]'
                                ];

                                for (const sel of closeSelectors) {
                                    const btns = document.querySelectorAll(sel);
                                    for (let i = btns.length - 1; i >= 0; i--) {
                                        const btn = btns[i];
                                        if (btn && (btn.offsetWidth > 0 || btn.offsetHeight > 0)) {
                                            btn.click();
                                            return true;
                                        }
                                    }
                                }
                                return false;
                            } catch (e) {
                                return false;
                            }
                        }"""
                    )
                except Exception as e:
                    print(f"      ⚠️ Lỗi khi tìm nút đóng dialog: {e}")

                if dialog_closed:
                    print("      ✅ Đã click nút Đóng dialog.")
                else:
                    # Fallback dùng Escape
                    try:
                        page.keyboard.press("Escape")
                        print("      ✅ Đã bấm phím Escape để đóng dialog.")
                    except Exception as e:
                        print(f"      ⚠️ Lỗi khi bấm Escape: {e}")

                # Chờ một chút để dialog biến mất hoàn toàn
                page.wait_for_timeout(1000)

                return True

            print(
                "      ⚠️ Không xác nhận được comment đã gửi."
            )
            status, msg = check_comment_outcome(page, snippet, count_before, text_before)
            return comment_fail(f"Facebook báo: {msg}" if status == "loi" and msg else
                                "đã bấm Enter nhưng chữ vẫn nằm trong ô (Facebook không nhận)")

        except Exception as e:
            print(
                "      ⚠️ Lỗi khi kiểm tra comment:",
                e
            )
            return comment_fail(f"lỗi khi kiểm tra đã gửi chưa: {str(e)[:80]}")

    except Exception as e:

        print(
            "   ❌ Lỗi khi comment in-article:",
            e
        )

        return comment_fail(f"lỗi bất ngờ: {str(e)[:80]}")

    finally:

        # LUÔN đóng dialog, kể cả comment thành công hay lỗi.
        print(
            "      ➤ Đảm bảo dialog bài viết đã được đóng..."
        )

        dialog_closed = close_post_dialog(
            page,
            timeout_ms=10000
        )

        if dialog_closed:
            print(
                "      ✅ Dialog đã đóng thành công → trả quyền cho vòng scroll."
            )
        else:
            print(
                "      ⛔ Dialog chưa đóng được → chưa được phép scroll."
            )

# ============================================================
# URL
# ============================================================

def normalize_url(href):

    if not href:
        return ""

    href = html.unescape(href.strip())

    href = href.replace("\\/", "/")

    if href.startswith("/"):

        href = "https://www.facebook.com" + href

    return href.split("?", 1)[0]


# ============================================================
# KIỂM TRA POST URL
# ============================================================

def is_post_url(url):

    if not url:
        return False

    low = url.lower()

    post_patterns = [

        "/posts/",
        "/permalink/",
        "story_fbid",
        "pfbid",
        "/share/p/"

    ]

    return any(x in low for x in post_patterns)


# ============================================================
# LẤY POST ID
# ============================================================

def get_post_id(url):

    if not url:
        return ""

    # --------------------------------------------------------
    # pfbid
    # --------------------------------------------------------

    match = re.search(
        r"(pfbid[A-Za-z0-9_-]+)",
        url,
        re.I
    )

    if match:
        return match.group(1)

    # --------------------------------------------------------
    # ID số
    # --------------------------------------------------------

    numbers = re.findall(
        r"\d{5,}",
        url
    )

    if numbers:
        return numbers[-1]

    return ""


# ============================================================
# LẤY LINK BÀI VIẾT
# ============================================================

def extract_post_url(article):

    # --------------------------------------------------------
    # BƯỚC 1 (ƯU TIÊN):
    #
    # Từ thẻ story_message, đi lên 3 cấp cha (parentElement),
    # sau đó tìm TẤT CẢ thẻ <a> nằm bên trong node đó.
    # Thẻ <a> nào có href chứa "/posts" thì lấy href đó
    # làm link bài viết.
    # --------------------------------------------------------

    try:

        href = article.evaluate(
            """(el) => {
                try {
                    let node = el;

                    for (let i = 0; i < 3 && node.parentElement; i++) {
                        node = node.parentElement;
                    }

                    const links = Array.from(node.querySelectorAll('a'));

                    for (const link of links) {
                        const href = link.getAttribute('href');
                        if (href && href.includes('/posts')) {
                            return href;
                        }
                    }

                    return null;
                } catch (e) {
                    return null;
                }
            }"""
        )

        if href:

            url = normalize_url(
                href
            )

            if url:
                return url

    except Exception as e:

        print(
            "      ⚠️ Lỗi khi tìm link theo 'đi lên 3 cấp':",
            e
        )

    # --------------------------------------------------------
    # BƯỚC 2 (FALLBACK):
    #
    # Nếu bước 1 không tìm được link, quay lại cách cũ:
    # tìm trực tiếp trong article bằng nhiều selector khác nhau.
    # --------------------------------------------------------

    selectors = [

        "a[href*='/posts/']",
        "a[href*='/permalink/']",
        "a[href*='story_fbid']",
        "a[href*='pfbid']",
        "a[href*='/share/p/']"

    ]

    # --------------------------------------------------------
    # SELECTOR
    # --------------------------------------------------------

    for selector in selectors:

        try:

            links = article.locator(
                selector
            ).all()

            for link in links:

                href = link.get_attribute(
                    "href"
                )

                if not href:
                    continue

                url = normalize_url(
                    href
                )

                if is_post_url(url):
                    return url

        except:
            pass

    # --------------------------------------------------------
    # FALLBACK HTML
    # --------------------------------------------------------

    try:

        article_html = article.evaluate(
            "(el) => el.outerHTML"
        )

        patterns = [

            r'href="([^"]*/posts/[^"]*)"',
            r'href="([^"]*/permalink/[^"]*)"',
            r'href="([^"]*story_fbid[^"]*)"',
            r'href="([^"]*pfbid[^"]*)"',
            r'href="([^"]*/share/p/[^"]*)"'

        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                article_html,
                re.I
            )

            if not match:
                continue

            url = normalize_url(
                match.group(1)
            )

            if is_post_url(url):
                return url

    except:
        pass

    return ""


# ============================================================
# LẤY LINK BẰNG CÁCH RÊ CHUỘT
#
# Facebook không để sẵn link bài: thẻ thời gian ("2 giờ", "11 tháng 10")
# chỉ có href giả "?__cft__..." và CHỈ đổi thành link thật
# (.../groups/<nhóm>/posts/<id>/) khi rê chuột vào.
# → Rê chuột vào các thẻ <a> href giả ở đầu bài rồi đọc lại href.
# Dự phòng: link ảnh trong bài có "set=pcb.<id bài>" → ghép thành link bài.
# ============================================================

def extract_post_url_by_hover(article):

    # JS: link bài đầu tiên trong khung bài, KHÔNG nằm trong nội dung bài viết.
    find_js = """(box, st) => {
        for (const a of box.querySelectorAll('a[href]')) {
            if (st && st.contains(a)) continue;
            const h = a.getAttribute('href') || '';
            if (/\\/posts\\/|\\/permalink\\/|story_fbid|pfbid/.test(h)) return h;
        }
        return '';
    }"""

    try:

        box = article.locator(
            "xpath=ancestor::div[@aria-posinset][1]"
        )

        if box.count() == 0:

            box = article.locator(
                "xpath=ancestor::*[@role='article'][1]"
            )

        if box.count() == 0:
            return ""

        box = box.first
        story = article.element_handle(timeout=2000)
        fake = box.locator("a[href^='?'], a[href='#']")

        for index in range(min(fake.count(), 4)):

            anchor = fake.nth(index)

            try:

                # Thẻ ẩn: rê chuột không được, bỏ qua (tránh chờ lâu).
                if not anchor.is_visible():
                    continue

                anchor.hover(timeout=1500)

            except Exception:
                continue

            # Facebook vẽ lại thẻ sau khi rê chuột → tìm lại trong cả khung bài.
            for _ in range(6):

                article.page.wait_for_timeout(150)

                href = box.evaluate(find_js, story, timeout=2000)
                url = normalize_url(href or "")

                if is_post_url(url):
                    return url

        # Dự phòng: ảnh trong bài → set=pcb.<id bài>
        hrefs = box.evaluate(
            "(el) => Array.from(el.querySelectorAll('a[href*=\"pcb.\"]')).map(a => a.getAttribute('href'))",
            timeout=2000
        )

        group = re.search(
            r"/groups/([^/?#]+)",
            article.page.url
        )

        for href in hrefs or []:

            match = re.search(
                r"pcb\.(\d{5,})",
                href or ""
            )

            if match and group:
                return (
                    f"https://www.facebook.com/groups/"
                    f"{group.group(1)}/posts/{match.group(1)}/"
                )

    except Exception as e:

        print(
            "      ⚠️ Lỗi khi lấy link bằng rê chuột:",
            str(e).splitlines()[0][:120]
        )

    return ""


# ============================================================
# XEM THÊM
# ============================================================

def click_see_more(article):

    clicked = 0

    selectors = [

        "div[role='button']",
        "span",
        "a"

    ]

    for selector in selectors:

        try:

            elements = article.locator(
                selector
            ).all()

        except:

            continue

        for element in elements:

            try:

                if not element.is_visible():
                    continue

                text = (
                    element.inner_text(
                        timeout=1000
                    )
                    .strip()
                    .casefold()
                )

                if text not in [
                    "xem thêm",
                    "see more"
                ]:
                    continue

                print(
                    "   ↳ 🔽 Click Xem thêm"
                )

                element.click(
                    timeout=2000
                )

                clicked += 1

                break

            except:
                pass

        if clicked:
            break

    return clicked

# ============================================================
# LẤY NỘI DUNG BÀI
# ============================================================

def extract_post_text(article):

    try:

        text = article.inner_text(
            timeout=5000
        ).strip()

        if text:
            return text

    except:
        pass

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    try:

        elements = article.locator(
            "div[dir='auto']"
        ).all()

        result = []

        for element in elements:

            try:

                text = (
                    element.inner_text()
                    .strip()
                )

                if (
                    text
                    and text not in result
                ):

                    result.append(
                        text
                    )

            except:
                pass

        return "\n".join(
            result
        ).strip()

    except:

        return ""


# ============================================================
# LẤY DATA BÀI
# ============================================================

def extract_post_data(article):

    try:

        # ----------------------------------------------------
        # XEM THÊM
        # ----------------------------------------------------

        clicked = click_see_more(
            article
        )

        if clicked:

            see_more_wait_ms = (
                CURRENT_CONFIG.get(
                    "SEE_MORE_WAIT_MS",
                    2000
                )
            )

            try:

                wait_ms = int(
                    see_more_wait_ms
                )

            except:

                wait_ms = 2000

            print(
                f"   ⏳ Chờ Xem thêm "
                f"{wait_ms / 1000:.1f}s..."
            )

            article.page.wait_for_timeout(
                wait_ms
            )

        # ----------------------------------------------------
        # CONTENT
        # ----------------------------------------------------

        text = extract_post_text(
            article
        )

        # Bam roi ma bai van con "… Xem thêm" (Facebook mo cham / bam truot) -> bam lai, cho lau hon.
        # Bai bi cat thi bo loc chi thay tieu de -> quang cao de lot.
        for retry in range(2):
            if not text or not re.search(r"(Xem thêm|See more)\s*$", text):
                break
            print(f"   ↻ Bài vẫn bị cắt '… Xem thêm' → bấm lại lần {retry + 2}")
            if not click_see_more(article):
                break
            article.page.wait_for_timeout(2000 + retry * 1500)
            text = extract_post_text(article)
        if text and re.search(r"(Xem thêm|See more)\s*$", text):
            print("   ⚠️ Không mở được 'Xem thêm' → chấm điểm trên phần nội dung bị cắt.")

        if not text:
            return None

        # ----------------------------------------------------
        # URL
        # ----------------------------------------------------

        post_url = extract_post_url(
            article
        )

        # ----------------------------------------------------
        # ID
        # ----------------------------------------------------

        post_id = get_post_id(
            post_url
        )

        # ----------------------------------------------------
        # FALLBACK ID
        # ----------------------------------------------------

        if not post_id:

            base = text[:1500]

            post_id = (
                "CONTENT_"
                + hashlib.sha1(
                    base.encode(
                        "utf-8",
                        errors="ignore"
                    )
                ).hexdigest()[:24]
            )

        # Cách cũ không thấy link → rê chuột vào thẻ thời gian để Facebook gắn link thật.
        # (ID vẫn giữ theo cách cũ để không gửi trùng các bài đã gửi trước đây.)
        if not post_url:

            post_url = extract_post_url_by_hover(
                article
            )

        # tag the article element with our post_id so we can find it later
        try:
            article.evaluate("(el, id) => el.setAttribute('data-bot-post-id', id)", post_id)
        except:
            pass

        return {

            "id":
                post_id,

            "url":
                post_url,

            "text":
                text

        }

    except:

        return None


# ============================================================
# ĐẾM STORY_MESSAGE
#
# QUAN TRỌNG:
# Dùng selector giống code cũ.
# Không đổi selector.
# ============================================================

def get_story_count(page):

    try:

        return page.locator(
            'div[data-ad-rendering-role="story_message"]'
        ).count()

    except:

        return 0


# ============================================================
# CHỜ STORY_MESSAGE
#
# Nếu Facebook render chậm:
# kiểm tra nhiều lần thay vì chỉ check 1 lần.
# ============================================================

def wait_for_story_message(
    page,
    retry_count=3,
    wait_ms=3000
):

    count = 0

    for i in range(
        retry_count
    ):

        count = get_story_count(
            page
        )

        print(
            f"   🔎 Kiểm tra "
            f"story_message "
            f"lần {i + 1}/{retry_count}: "
            f"{count}"
        )

        if count > 0:
            return count

        if i < retry_count - 1:

            print(
                f"   ⏳ Chưa thấy "
                f"story_message → "
                f"chờ {wait_ms / 1000:.1f}s..."
            )

            page.wait_for_timeout(
                wait_ms
            )

    return count


# ============================================================
# ĐỌC TẤT CẢ STORY_MESSAGE
# ============================================================

def read_articles(
    page,
    collected
):

    new_count = 0

    try:

        articles = page.locator(
            'div[data-ad-rendering-role="story_message"]'
        ).all()

    except Exception:

        return 0

    print(
        f"   📦 story_message đang có trên DOM: "
        f"{len(articles)}"
    )

    skipped = 0

    for index, article in enumerate(
        articles,
        1
    ):

        # Bài đã đọc ở lần cuộn trước (dấu vân tay = 300 ký tự đầu còn khớp)
        # → bỏ qua, khỏi bấm "Xem thêm" và bóc lại (trước đây tốn ~0.8s/bài/lần cuộn).
        # Facebook dùng lại khung cho bài khác thì nội dung khác → vẫn được đọc.
        try:

            if article.evaluate(
                "el => el.dataset.fbmonKey === (el.innerText || '').slice(0, 300)",
                timeout=2000
            ):
                skipped += 1
                continue

        except Exception:

            pass

        try:

            data = extract_post_data(
                article
            )

            try:

                article.evaluate(
                    "el => { el.dataset.fbmonKey = (el.innerText || '').slice(0, 300); }",
                    timeout=2000
                )

            except Exception:

                pass

            if not data:
                continue

            post_id = data["id"]

            if post_id not in collected:

                collected[post_id] = data

                new_count += 1

                print(
                    f"\n   📝 Đọc bài "
                    f"{index}/{len(articles)}"
                )

                log_detected_post(
                    data,
                    new_count
                )

        except:

            pass

    if skipped:

        print(
            f"   ⏭️ Bỏ qua {skipped} bài đã đọc ở lần cuộn trước."
        )

    return new_count


# ============================================================
# LOG BÀI
# ============================================================

def log_detected_post(
    data,
    index=None
):

    post_id = (
        data.get("id")
        or
        "Không có ID"
    )

    post_url = (
        data.get("url")
        or
        "Không lấy được link"
    )

    post_text = (
        data.get("text")
        or
        ""
    )

    print()

    print(
        "╔══════════════════════════════════════════════════════"
    )

    print(
        "║ 🔎 PHÁT HIỆN BÀI VIẾT"
    )

    print(
        "╠══════════════════════════════════════════════════════"
    )

    if index is not None:

        print(
            f"║ 📌 STT: {index}"
        )

    print(
        f"║ 🆔 ID: {post_id}"
    )

    print(
        f"║ 🔗 LINK: {post_url}"
    )

    print(
        "║ 📝 NỘI DUNG:"
    )

    display_text = post_text[:3000]

    if display_text:

        for line in display_text.splitlines():

            print(
                f"║ {line}"
            )

    else:

        print(
            "║ [Không có nội dung]"
        )

    if len(post_text) > 3000:

        print(
            "║ ... [Nội dung dài hơn 3000 ký tự]"
        )

    print(
        "╚══════════════════════════════════════════════════════"
    )

    print()


# ============================================================
# KIỂM TRA AD PATTERN
# ============================================================

def check_advertisement(
    text,
    ad_patterns
):

    if not text:
        return []

    matched = []

    for pattern in ad_patterns:

        if contains_keyword(
            text,
            pattern
        ):

            matched.append(
                pattern
            )

    return matched


# ============================================================
# ĐÁNH GIÁ ĐIỂM QUẢNG CÁO
# ============================================================

# Cách viết của NGƯỜI ĐI TÌM dịch vụ (ngôi thứ nhất, đang hỏi / nhờ).
SEEKER_PHRASES = [
    "cần tìm", "đang tìm", "muốn tìm", "tìm giúp", "tìm hộ",
    "ai biết", "có ai biết", "có ai nhận", "ai nhận", "bên nào nhận", "chỗ nào nhận", "nơi nào nhận",
    "shop nào nhận", "có chỗ nào", "có nơi nào", "ở đâu nhận",
    "cho mình hỏi", "cho em hỏi", "cho e hỏi", "cho mình xin", "cho em xin", "cho e xin",
    "nhờ mọi người", "nhờ cả nhà", "nhờ mn", "mọi người ơi", "cả nhà ơi", "mn ơi",
    "xin review", "xin địa chỉ", "giới thiệu giúp", "recommend giúp", "gợi ý giúp",
    "mình cần gửi", "em cần gửi", "e cần gửi", "mình muốn gửi", "em muốn gửi",
    "mình muốn", "em muốn", "e muốn", "mk muốn", "m muốn", "mình đang muốn", "nhà em muốn",
    "anh chị nào", "a/c nào", "ac nào", "đơn vị nào", "có đơn vị nào", "tôi muốn", "tôi cần",
    "cần gửi bé", "cần gửi chó", "cần gửi mèo", "cần người giữ", "cần chỗ",
    "mình cần", "em cần", "m cần", "e cần", "mk cần", "nhà mình cần", "cần gấp",
    "cần dịch vụ", "cần khách sạn", "cần ksan", "cần ks", "cần hotel", "cần người trông", "cần người chăm",
    "bên nào", "chỗ nào", "nhà nào nhận", "home nào", "ksan nào", "hotel nào", "khách sạn nào",
    "bạn nào nhận", "có bạn nào", "ai có chỗ", "ai giữ", "ai trông",
    "xin bảng giá", "xin giá", "review giúp", "chỉ em với", "chỉ mình với",
]

# Câu TỰ XƯNG của bên bán (khách không bao giờ viết) -> bài có câu này không được bảo vệ như người đi tìm.
# Cố định trong code, KHÔNG phụ thuộc danh sách dấu hiệu quảng cáo (danh sách đó có cả "zalo", "ib"... khách cũng dùng).
SELLER_SELF_WORDS = [
    "bên em", "shop em", "bên mình nhận", "bên em nhận", "chuyên nhận", "shop mình nhận",
    "em nhận giữ", "em nhận trông", "em nhận chăm", "mình nhận giữ", "mình nhận trông", "mình nhận chăm",
    "nhận trông giữ", "nhận lưu trú", "nhận in thiệp", "nhận thiết kế thiệp",
]

# Quảng cáo hay mượn giọng người đi tìm ("Bạn đang tìm...?") → không tính là người đi tìm.
SEEKER_AD_COPY = [
    "bạn đang tìm", "bạn có đang tìm", "bạn cần tìm", "bạn đang cần", "bạn có đang cần", "ba mẹ đang tìm", "sen đang tìm",
    "bạn muốn tìm", "anh chị đang tìm", "ac đang tìm",
    "bạn nào đang tìm", "bạn nào cần", "ai đang tìm", "ai đang cần", "ai có nhu cầu", "khách nào cần",
    "dâu rể nào đang", "dâu rể đang tìm", "cặp đôi nào đang",
]

# Dấu hiệu quảng cáo RẤT MẠNH: có giá tiền hoặc khuyến mãi.
# ("bảng giá" KHÔNG tính: người đi tìm rất hay xin bảng giá.)
STRONG_AD_WORDS = ["khuyến mãi", "giảm giá", "voucher", "ưu đãi", "giá chỉ", "chỉ từ"]
# Giá tiền: >= 2 chữ số + k/đ (60k, 100.000đ, 150k/ngày) hoặc dạng triệu (1tr5, 2tr, 3 triệu).
# Không bắt "7,8,9 k ạ" (k = "không").
PRICE_PATTERN = re.compile(
    r"\b\d{2,}(?:[.,]\d{3})*\s?(?:k|đ|đồng|vnđ|vnd)(?![a-zà-ỹ])"
    r"|\b\d+\s?(?:tr|triệu)(?:\d+)?\b",
    re.IGNORECASE
)


# So dien thoai VN: 0 + 9-10 chu so, cho phep cach / cham / gach giua cac nhom; hoac 84 / +84.
PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:0|\+?84[\s.]?)\d(?:[\s.\-]?\d){8,9}(?!\d)"
)

# Dia chi cu the -> +3. Chi nhac khu vuc -> +1.
ADDRESS_EXACT_WORDS = ["địa chỉ", "số nhà", "ngõ", "ngách", "hẻm"]
ADDRESS_AREA_WORDS = ["phường", "quận", "huyện", "thành phố", "tp.", "đường"]
# So nha + ten duong viet hoa: "80 Văn Hội", "57B Mai Văn Vĩnh", "C7/13B23 Phạm Hùng", "724 đường lê đức anh".
HOUSE_NUMBER_PATTERN = re.compile(
    r"(?<![\w/.,:-])[A-Z]?\d{1,4}[A-Za-z]?(?:/\d+[A-Za-z]?\d*)*\s+"
    r"(?:đường\s+|phố\s+|Đường\s+|Phố\s+)?"
    r"(?:[A-ZĐÀ-Ỹ][a-zà-ỹ]+\s+[A-ZĐÀ-Ỹ][a-zà-ỹ]+|(?<=đường\s)[a-zà-ỹ]+\s+[a-zà-ỹ]+)"
)


def find_seeker_phrase(text):
    """Câu kiểu người đi tìm dịch vụ đầu tiên tìm thấy, hoặc '' nếu không có."""

    if any(contains_keyword(text, p) for p in SEEKER_AD_COPY):
        return ""

    for phrase in SEEKER_PHRASES:
        if contains_keyword(text, phrase):
            return phrase

    return ""


def has_strong_ad_signal(text):
    """Có giá tiền (60k, 100.000đ, 1tr...) hoặc từ khuyến mãi rõ ràng."""

    if PRICE_PATTERN.search(text or ""):
        return True

    # So dien thoai / hotline: nguoi di tim gan nhu khong de so, ben ban thi luon de.
    if PHONE_PATTERN.search(unicodedata.normalize("NFKD", text or "")) or contains_keyword(text, "hotline"):
        return True

    return any(contains_keyword(text, w) for w in STRONG_AD_WORDS)


def evaluate_advertisement(
    text,
    ad_patterns,
    ad_score_rules,
    ad_score_threshold
):

    if not text:

        return {

            "is_ad":
                False,

            "score":
                0,

            "reasons":
                [],

            "hard_matches":
                []

        }

    score = 0

    reasons = []

    hard_matches = []

    # ========================================================
    # 1. AD_PATTERNS (không phân biệt hoa/thường, chuẩn hóa Unicode)
    # ========================================================

    for pattern in ad_patterns:

        if contains_keyword(
            text,
            pattern
        ):

            hard_matches.append(
                pattern
            )

    if hard_matches:

        hard_score = min(
            len(hard_matches) * 3,
            6
        )

        score += hard_score

        for pattern in hard_matches:

            reasons.append(
                f"{pattern} (+3)"
            )

    # ========================================================
    # 2. SCORE RULES (không phân biệt hoa/thường, chuẩn hóa Unicode)
    # ========================================================

    for pattern, rule_score in ad_score_rules:

        if contains_keyword(
            text,
            pattern
        ):

            score += rule_score

            reasons.append(
                f"{pattern} (+{rule_score})"
            )

    # ========================================================
    # 3. SỐ ĐIỆN THOẠI
    # ========================================================

    has_phone = bool(PHONE_PATTERN.search(
        unicodedata.normalize("NFKD", text)
    ))

    if has_phone:

        score += 3

        reasons.append(
            "số điện thoại (+3)"
        )

    # ========================================================
    # 4. ĐỊA CHỈ
    # ========================================================

    exact_address = (
        any(contains_keyword(text, w) for w in ADDRESS_EXACT_WORDS)
        or HOUSE_NUMBER_PATTERN.search(text or "")
    )

    if exact_address:

        score += 3

        reasons.append(
            "địa chỉ cụ thể (+3)"
        )

    elif any(contains_keyword(text, w) for w in ADDRESS_AREA_WORDS):

        score += 1

        reasons.append(
            "nhắc khu vực (+1)"
        )

    # Nhieu hashtag (#hotelchomeo #xuhuong ...) -> kieu bai quang cao.
    hashtags = re.findall(r"#\w", unicodedata.normalize("NFKD", text))

    if len(hashtags) >= 3:

        score += 2

        reasons.append(
            f"{len(hashtags)} hashtag (+2)"
        )

    # ========================================================
    # 5. CTA
    # ========================================================

    cta_patterns = [

        "inbox",
        "ib",
        "liên hệ",
        "đặt lịch",
        "đặt phòng",
        "đặt chỗ",
        "đăng ký",
        "gọi ngay",
        "nhắn tin",
        "ghé ngay"

    ]

    cta_found = []

    for pattern in cta_patterns:

        if contains_keyword(
            text,
            pattern
        ):

            cta_found.append(
                pattern
            )

    if cta_found:

        cta_score = min(
            len(cta_found) * 2,
            4
        )

        score += cta_score

        reasons.append(
            f"CTA ({', '.join(cta_found)}) "
            f"(+{cta_score})"
        )

    # ========================================================
    # 6. GIÁ / KHUYẾN MÃI
    # ========================================================

    promotion_patterns = [

        "giảm",
        "ưu đãi",
        "khuyến mãi",
        "không phụ thu",
        "miễn phí",
        "free",
        "voucher",
        "sale",
        "giá chỉ",
        "chỉ từ",
        "đồng/ngày",
        "đồng/giờ"

    ]

    promotion_found = []

    for pattern in promotion_patterns:

        if contains_keyword(
            text,
            pattern
        ):

            promotion_found.append(
                pattern
            )

    if promotion_found:

        promotion_score = min(
            len(promotion_found) * 2,
            5
        )

        score += promotion_score

        reasons.append(
            f"khuyến mãi/giá "
            f"({', '.join(promotion_found)}) "
            f"(+{promotion_score})"
        )

    # ========================================================
    # 7. MÔ HÌNH KINH DOANH
    # ========================================================

    business_patterns = [

        "spa",
        "hotel",
        "homestay",
        "shop",
        "store",
        "tiệm",
        "cửa hàng",
        "studio",
        "salon",
        "nhà hàng",
        "quán",
        "dịch vụ"

    ]

    business_found = []

    for pattern in business_patterns:

        if contains_keyword(
            text,
            pattern
        ):

            business_found.append(
                pattern
            )

    if business_found:

        business_score = min(
            len(business_found) * 2,
            4
        )

        score += business_score

        reasons.append(
            f"mô hình kinh doanh "
            f"({', '.join(business_found)}) "
            f"(+{business_score})"
        )

    # ========================================================
    # KẾT QUẢ
    # ========================================================

    is_ad = (
        score >= ad_score_threshold
    )

    # ========================================================
    # NGƯỜI ĐI TÌM DỊCH VỤ → KHÔNG PHẢI QUẢNG CÁO
    #
    # Người tìm dịch vụ cũng hay viết "dịch vụ", "hotel", "inbox",
    # để số điện thoại, nhắc quận/đường... nên dễ bị chấm nhầm.
    # Bài viết theo kiểu người đi tìm thì giữ lại, TRỪ KHI có
    # dấu hiệu quảng cáo rất mạnh (giá tiền, khuyến mãi).
    # ========================================================
    if is_ad:

        seeker = find_seeker_phrase(text)

        # Diem quang cao qua cao (>= 15 hoac >= 3 lan nguong) -> chac chan quang cao du co cau "can gap"...
        very_high = score >= max(15, ad_score_threshold * 3)
        # Bai da TU XUNG ben ban (khop dau hieu +3 nhu "em nhận", "bên em") -> khong bao ve nhu nguoi di tim.
        seller = any(contains_keyword(text, w) for w in SELLER_SELF_WORDS)
        if seeker and not very_high and not seller and not has_strong_ad_signal(text):

            is_ad = False

            reasons.append(
                f"người đi tìm dịch vụ ('{seeker}') → không coi là quảng cáo"
            )

    return {

        "is_ad":
            is_ad,

        "score":
            score,

        "reasons":
            reasons,

        "hard_matches":
            hard_matches

    }


# ============================================================
# XỬ LÝ BÀI MỚI
# ============================================================

# ============================================================
# THU THẬP DỮ LIỆU BÀI VIẾT
#
# Mỗi bài quét được ghi 1 dòng JSON vào campaigns/<id>/bai_thu_thap.jsonl
# (cạnh sent_ids.txt) kèm quyết định của tool → dùng để đánh giá lại
# từ khóa / điểm quảng cáo. Mỗi bài chỉ ghi 1 lần. Quá 10MB → đổi tên
# thành bai_thu_thap.1.jsonl (giữ 2 file).
# ============================================================

COLLECT_FILE_NAME = "bai_thu_thap.jsonl"
_collected_keys = {}


def record_post(post_id, data, decision, ad_result=None, keywords=None, excludes=None):

    try:

        path = SENT_IDS_FILE.parent / COLLECT_FILE_NAME

        keys = _collected_keys.get(path)

        if keys is None:

            keys = set()

            if path.exists():

                for line in path.read_text(encoding="utf-8", errors="replace").splitlines():

                    try:
                        keys.add(json.loads(line)["id"])
                    except (ValueError, KeyError, TypeError):
                        pass

            _collected_keys[path] = keys

        if post_id in keys:
            return

        fb_login.rotate_log(path, 10_000_000, keep=2)

        row = {
            "time": f"{datetime.now():%Y-%m-%d %H:%M:%S}",
            "id": post_id,
            "decision": decision,
            "url": data.get("url", ""),
            "author": data.get("author", ""),
            "ad_score": (ad_result or {}).get("score"),
            "ad_reasons": (ad_result or {}).get("reasons", []),
            "keywords": keywords or [],
            "excludes": excludes or [],
            "text": data.get("text", ""),
        }

        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

        keys.add(post_id)

    except Exception as error:

        print(f"   ⚠️ Không ghi được dữ liệu thu thập: {error}")


def process_new_posts(

    new_post_ids,

    collected,

    sent_posts,

    keywords,

    exclude_keywords,

    ad_patterns,

    ad_score_rules,

    ad_score_threshold,

    page,

    config,

    COMMENTED_IDS,

    commented_file,

    telegram_token,

    telegram_chat_id

):
    telegram_success = 0
    telegram_failed = 0
    no_keyword = 0
    excluded_keyword_count = 0
    advertisement_count = 0
    empty_text = 0
    duplicate_count = 0

    for post_id in new_post_ids:

        try:

            data = collected.get(post_id)

            if not data:
                continue

            text = data.get("text", "")
            post_url = data.get("url", "")

            # ====================================================
            # 1. TEXT TRỐNG
            # ====================================================
            if not text:
                empty_text += 1
                print(
                    "   ⚠️ Bài phát hiện nhưng không có nội dung."
                )
                continue

            # ====================================================
            # 2. ĐÁNH GIÁ QUẢNG CÁO
            # ====================================================
            # Người dùng có thể TẮT lọc quảng cáo (AD_FILTER=false) → bỏ qua bước chấm điểm.
            ad_filter_on = CURRENT_CONFIG.get(
                "AD_FILTER",
                "true"
            ).strip().lower() in ("1", "true", "yes", "on")

            if ad_filter_on:
                ad_result = evaluate_advertisement(
                    text,
                    ad_patterns,
                    ad_score_rules,
                    ad_score_threshold
                )
            else:
                print("   ⏭️ Lọc quảng cáo đang TẮT → không kiểm tra quảng cáo.")
                ad_result = {"is_ad": False, "score": 0, "reasons": []}

            if ad_result["is_ad"]:

                advertisement_count += 1

                print()
                print("   🚫 BÀI QUẢNG CÁO → BỎ QUA")
                print("   🆔 ID:", post_id)
                print(
                    "   📊 Điểm quảng cáo:",
                    ad_result["score"],
                    "/",
                    ad_score_threshold
                )
                print("   🚫 Lý do:")

                for reason in ad_result["reasons"]:
                    print("      •", reason)

                record_post(post_id, data, "quang_cao", ad_result)
                continue

            if ad_filter_on:
                print()
                print("   🟢 BÀI CHƯA ĐỦ ĐIỂM QUẢNG CÁO")
                print(
                    "   📊 Điểm:",
                    ad_result["score"],
                    "/",
                    ad_score_threshold
                )

            if ad_result["reasons"]:
                print("   🔎 Dấu hiệu:")
                for reason in ad_result["reasons"]:
                    print("      •", reason)

            # ====================================================
            # 3. CHECK ĐÃ GỬI
            # ====================================================
            # Cung 1 bai co the ra ID khac nhau giua cac lan quet -> so them dau van tay noi dung.
            keys = post_keys(post_id, post_url, text)
            if any(k in sent_posts for k in keys):

                duplicate_count += 1

                print(
                    f"   🔁 Đã gửi trước đó, bỏ qua: {post_id}"
                )
                continue

            # ====================================================
            # 4. EXCLUDE KEYWORDS
            # ====================================================
            matched_exclude = [
                keyword
                for keyword in exclude_keywords
                if contains_keyword(text, keyword)
            ]

            if matched_exclude:

                excluded_keyword_count += 1

                print("   🚫 BÀI BỊ LOẠI")
                print(
                    "   🚫 Keyword loại:",
                    ", ".join(matched_exclude)
                )
                record_post(post_id, data, "tu_loai", ad_result, excludes=matched_exclude)
                continue

            # ====================================================
            # 5. KEYWORDS
            # ====================================================
            matched_keywords = [
                keyword
                for keyword in keywords
                if contains_keyword(text, keyword)
            ]

            if not matched_keywords:

                no_keyword += 1
                print("   ⏭️ Không khớp keyword.")
                record_post(post_id, data, "khong_tu_khoa", ad_result)
                continue

            # ====================================================
            # 6. THỎA MÃN
            # ====================================================
            message = (
                "🔔 <b>PHÁT HIỆN BÀI VIẾT</b>\n\n"
                f"🔑 <b>Từ khóa:</b> "
                f"{html.escape(', '.join(matched_keywords))}"
                "\n\n"
                f"📊 <b>Điểm quảng cáo:</b> "
                f"{ad_result['score']}/{ad_score_threshold}"
                "\n\n"
                f"🔗 <b>Link bài viết:</b>\n"
                f"{html.escape(post_url or 'Không lấy được link')}"
                "\n\n"
                f"📝 <b>Nội dung:</b>\n"
                f"{html.escape(text[:700])}"
            )

            print()
            print("📨 BÀI THỎA MÃN → GỬI TELEGRAM")
            print("   🆔 ID:", post_id)
            print("   🔑 Keyword:", matched_keywords)
            print("   📊 Điểm quảng cáo:", ad_result["score"])
            print("   🔗 Link:", post_url)

            # ====================================================
            # 7. GỬI TELEGRAM
            # ====================================================
            sent = send_telegram(
                message,
                telegram_token,
                telegram_chat_id
            )

            record_post(post_id, data, "gui_telegram" if sent else "telegram_loi",
                        ad_result, keywords=matched_keywords)

            if not sent:

                telegram_failed += 1
                print(
                    "   ❌ Telegram lỗi → KHÔNG lưu ID."
                )
                continue

            telegram_success += 1

            # Lưu ID bài đã bắn Telegram (RAM + sent_ids.txt), tối đa 100 ID.
            # Ghi file ngay để lần chạy sau / bị dừng giữa chừng không gửi trùng.
            save_limited_commented_id(
                SENT_IDS_FILE,
                sent_posts,
                post_id,
                MAX_COMMENTED_IDS
            )
            for k in keys[1:]:
                save_limited_commented_id(SENT_IDS_FILE, sent_posts, k, MAX_COMMENTED_IDS)

            print(
                f"   ✅ Đã bắn Telegram → lưu ID "
                f"({len(sent_posts)}/{MAX_STORED_IDS})."
            )
            short = re.sub(r"\s+", " ", text)[:70]
            fb_login.note(BASE_DIR, f"   📨 Khách mới: \"{short}…\" → đã báo Telegram"
                          + (f" | {post_url}" if post_url else ""))

            # ====================================================
            # 8. AUTO COMMENT
            #
            # COMMENT LẦN 1:
            # COMMENT_TEXT + Downloads/facebook.png
            #
            # COMMENT LẦN 2:
            # COMMENT_TEXT_2 + Downloads/facebook2.png
            #
            # Chỉ khi comment 1 thành công mới chạy comment 2.
            # Chỉ khi cả 2 thành công mới ghi COMMENTED_IDS.
            # Lỗi comment không được làm dừng vòng scan.
            # ====================================================
            try:

                auto = config.get(
                    "AUTO_COMMENT",
                    "false"
                ).strip().lower()

                print(
                    f"   🔍 DEBUG: AUTO_COMMENT = '{auto}'"
                )

                if auto not in ("1", "true", "yes"):

                    print(
                        f"   ⏭️ Auto-comment DISABLED (AUTO_COMMENT='{auto}')"
                    )
                    continue

                print(
                    "   🔍 DEBUG: Auto-comment được ENABLE"
                )

                if any(k in COMMENTED_IDS for k in keys):

                    print(
                        "   ℹ️ Bài đã hoàn tất 2 comment trước đó, bỏ qua."
                    )
                    continue

                skip_reason = comment_skip_reason(keys, post_url)
                if skip_reason:
                    print(f"   ⏭️ Không bình luận: {skip_reason}")
                    continue

                # ----------------------------------------------------
                # COMMENT 1
                # ----------------------------------------------------
                comment_text_1 = prepare_comment_text(
                    config,
                    matched_keywords
                )

                image_path_1 = find_comment_image("facebook.jpg")

                if not image_path_1.exists():
                    print(
                        f"      ⚠️ Không tìm thấy ảnh comment 1: {image_path_1}"
                    )
                    image_path_1 = ""
                else:
                    image_path_1 = str(image_path_1)

                print()
                print(
                    "   💬 ================= COMMENT LẦN 1 ================="
                )
                print(
                    f"      ➤ Nội dung: {comment_text_1}"
                )
                print(
                    f"      ➤ Ảnh: {image_path_1 or 'Không có'}"
                )

                comment_1_ok = False
                COMMENT_RESULT.update(status="", detail="", no_image=False)

                # GIỮ NGUYÊN TOÀN BỘ LUỒNG AUTO-COMMENT CŨ,
                # nhưng không mở permalink bằng page.goto().
                # Comment trực tiếp trên article đang hiển thị trong Group
                # để tránh Facebook điều hướng ra khỏi Group/Home.
                try:
                    print(
                        "      🔍 Comment lần 1 trực tiếp trên article trong Group..."
                    )
                    comment_1_ok = post_comment_on_article(
                        page,
                        post_id,
                        comment_text_1,
                        image_path_1 or None,
                        post_text=text
                    )
                except Exception as e:
                    print(
                        "      ⚠️ Lỗi in-article comment 1:",
                        e
                    )
                    comment_1_ok = False

                if not comment_1_ok:

                    fb_login.note(BASE_DIR, "      ⚠️ Chưa bình luận được: "
                                  + (COMMENT_RESULT["detail"] or "không rõ lý do") + f" | {post_url or post_id}")
                    record_comment_fail(page, keys, post_url, COMMENT_RESULT["detail"],
                                        telegram_token, telegram_chat_id)
                    print(
                        "   ⚠️ Comment lần 1 thất bại → KHÔNG chạy comment lần 2."
                    )
                    print(
                        "   ➡️ Không dừng monitor, tiếp tục scroll/bài tiếp theo."
                    )
                    continue

                print(
                    "   ✅ COMMENT LẦN 1 THÀNH CÔNG"
                )
                record_comment_ok(post_url)
                fb_login.note(BASE_DIR, "      💬 " + {
                    "da_hien": "Đã bình luận – đã hiện dưới bài",
                    "cho_duyet": "Đã gửi bình luận – Facebook báo đang CHỜ DUYỆT: " + COMMENT_RESULT["detail"][:80],
                    "chua_thay": "Đã gửi bình luận (ô nhập đã trống) – chưa thấy hiện dưới bài, có thể đang chờ duyệt",
                }.get(COMMENT_RESULT["status"], "Đã bình luận vào bài")
                    + (" (KHÔNG kèm được ảnh, chỉ có chữ)" if COMMENT_RESULT.get("no_image") else "")
                    + f" | {post_url or post_id}")

                # ----------------------------------------------------
                # COMMENT 2
                # ----------------------------------------------------
                comment_text_2 = config.get(
                    "COMMENT_TEXT_2",
                    ""
                ).strip()

                if not comment_text_2:

                    print(
                        "   ⚠️ COMMENT_TEXT_2 đang trống → không thể hoàn tất comment lần 2."
                    )
                        # ----------------------------------------------------
                    #  LƯU ID CẤU HÌNH CHỈ CÓ COMMENT LẦN MỘT VÀ COMMENT LẦN MỘT ĐÃ THÀNH CÔNG
                    # ----------------------------------------------------
                    saved = save_limited_commented_id(
                        Path(commented_file),
                        COMMENTED_IDS,
                        post_id,
                        MAX_COMMENTED_IDS
                    )
                    for k in keys[1:]:
                        save_limited_commented_id(Path(commented_file), COMMENTED_IDS, k, MAX_COMMENTED_IDS)
                    if saved:
                        print(
                            "   ✅ Đã hoàn tất 1 comment và lưu ID."
                        )
                    else:
                        print(
                            "   ⚠️ Đã hoàn tất 1 comment nhưng không lưu được ID."
                        )
                    continue

                image_path_2 = find_comment_image("facebook2.jpg")

                if not image_path_2.exists():
                    print(
                        f"      ⚠️ Không tìm thấy ảnh comment 2: {image_path_2}"
                    )
                    image_path_2 = ""
                else:
                    image_path_2 = str(image_path_2)

                print()
                print(
                    "   💬 ================= COMMENT LẦN 2 ================="
                )
                print(
                    f"      ➤ Nội dung: {comment_text_2}"
                )
                print(
                    f"      ➤ Ảnh: {image_path_2 or 'Không có'}"
                )

                comment_2_ok = False

                # GIỮ NGUYÊN TOÀN BỘ LUỒNG AUTO-COMMENT CŨ,
                # nhưng không mở permalink bằng page.goto().
                # Comment trực tiếp trên article đang hiển thị trong Group.
                try:
                    print(
                        "      🔍 Comment lần 2 trực tiếp trên article trong Group..."
                    )
                    comment_2_ok = post_comment_on_article(
                        page,
                        post_id,
                        comment_text_2,
                        image_path_2 or None,
                        post_text=text
                    )
                except Exception as e:
                    print(
                        "      ⚠️ Lỗi in-article comment 2:",
                        e
                    )
                    comment_2_ok = False

                if not comment_2_ok:

                    print(
                        "   ⚠️ Comment lần 2 thất bại."
                    )
                    print(
                        "   ➡️ Không dừng monitor, tiếp tục scroll/bài tiếp theo."
                    )
                    continue

                print(
                    "   ✅ COMMENT LẦN 2 THÀNH CÔNG"
                )

                # ----------------------------------------------------
                # CHỈ LƯU ID KHI CẢ 2 COMMENT THÀNH CÔNG
                # ----------------------------------------------------
                saved = save_limited_commented_id(
                    Path(commented_file),
                    COMMENTED_IDS,
                    post_id,
                    MAX_COMMENTED_IDS
                )
                for k in keys[1:]:
                    save_limited_commented_id(Path(commented_file), COMMENTED_IDS, k, MAX_COMMENTED_IDS)

                if saved:
                    print(
                        "   ✅ Đã hoàn tất 2 comment và lưu ID."
                    )
                else:
                    print(
                        "   ⚠️ Đã hoàn tất 2 comment nhưng không lưu được ID."
                    )

            except Exception as e:

                # TUYỆT ĐỐI KHÔNG ĐỂ LỖI COMMENT LÀM TREO MONITOR.
                print(
                    "   ⚠️ Lỗi auto-comment:"
                )
                print(
                    repr(e)
                )

                try:
                    import traceback
                    traceback.print_exc()
                except:
                    pass

                print(
                    "   ➡️ Tiếp tục xử lý bài/scroll tiếp theo."
                )

        except Exception as e:

            # Bảo vệ từng bài: một bài lỗi không được làm dừng cả vòng.
            print(
                f"   ⚠️ Lỗi xử lý bài {post_id}: {e}"
            )
            continue

    return {
        "telegram_success": telegram_success,
        "telegram_failed": telegram_failed,
        "no_keyword": no_keyword,
        "excluded_keyword_count": excluded_keyword_count,
        "advertisement_count": advertisement_count,
        "empty_text": empty_text,
        "duplicate_count": duplicate_count
    }

# ============================================================
# SCROLL
# ============================================================

def scroll_page(
    page,
    distance
):

    try:

        page.mouse.wheel(
            0,
            distance
        )

    except:

        try:

            page.evaluate(
                f"""
                window.scrollBy(
                    0,
                    {distance}
                )
                """
            )

        except:

            pass


# ============================================================
# CHỜ ĐỦ THỜI GIAN
# ============================================================

def wait_full_time(
    page,
    wait_ms
):

    seconds = wait_ms / 1000

    print(
        f"   ⏳ Chờ Facebook load đủ "
        f"{seconds:.1f}s..."
    )

    start = time.time()

    while True:

        elapsed = (
            time.time()
            - start
        )

        if elapsed >= seconds:
            break

        remaining = (
            seconds
            - elapsed
        )

        print(
            f"      ... còn "
            f"{remaining:.1f}s",
            end="\r",
            flush=True
        )

        sleep_time = min(
            0.5,
            remaining
        )

        page.wait_for_timeout(
            int(
                sleep_time * 1000
            )
        )

    print(
        "      ✅ Đã đủ thời gian chờ.       "
    )


# ============================================================
# DIAGNOSTIC
# ============================================================

# diagnose_page removed


# ============================================================
# XỬ LÝ BÀI MỚI
# ============================================================

def handle_new_posts(

    page,

    collected,

    sent_posts,

    keywords,

    exclude_keywords,

    ad_patterns,

    ad_score_rules,

    ad_score_threshold,

    telegram_token,

    telegram_chat_id

):

    before_ids = set(
        collected
    )

    new_count = read_articles(
        page,
        collected
    )

    global TOTAL_DETECTED_POSTS

    TOTAL_DETECTED_POSTS += new_count

    new_post_ids = [

        post_id

        for post_id in collected

        if post_id not in before_ids

    ]

    if not new_post_ids:

        return None

    print(
        f"\n📨 Có {len(new_post_ids)} bài mới"
    )

    result = process_new_posts(
        new_post_ids,

        collected,

        sent_posts,

        keywords,

        exclude_keywords,

        ad_patterns,

        ad_score_rules,

        ad_score_threshold,

        page,

        CURRENT_CONFIG,

        COMMENTED_IDS,

        COMMENTED_IDS_FILE,

        telegram_token,

        telegram_chat_id

    )

    return result


# ============================================================
# MAIN
# ============================================================

def scan_round(config, page, run_deadline=None, max_run_minutes=20):
    """1 vong quet cho 1 nhom theo doi. config: dict KEY=chuoi (xem monitor_store.to_legacy_config)."""

    global CURRENT_CONFIG
    global TOTAL_DETECTED_POSTS
    global COMMENTED_IDS

    CURRENT_CONFIG = config
    run_once = True
    loop_wait_seconds = 0

    # load persisted commented IDs
    COMMENTED_IDS = load_commented_ids(
        COMMENTED_IDS_FILE,
        MAX_COMMENTED_IDS
    )

    # HỖ TRỢ NHIỀU GROUP.
    # GROUP_URLS=group1|group2|group3
    # Nếu không có GROUP_URLS thì dùng GROUP_URL cũ.
    group_urls = get_group_urls(config)

    if not group_urls:
        raise ValueError(
            "❌ Chưa có GROUP_URLS hoặc GROUP_URL trong fb_monitor_config.txt"
        )

    # ========================================================
    # TELEGRAM
    # ========================================================
    telegram_token = required(
        config,
        "TELEGRAM_TOKEN"
    )

    telegram_chat_id = required(
        config,
        "TELEGRAM_CHAT_ID"
    )

    warn_low_disk(telegram_token, telegram_chat_id)

    # ========================================================
    # KEYWORDS
    # ========================================================
    keywords = get_list(
        config,
        "KEYWORDS"
    )

    exclude_keywords = get_list(
        config,
        "EXCLUDE_KEYWORDS"
    )

    ad_patterns = get_list(
        config,
        "AD_PATTERNS"
    )

    # ========================================================
    # AD SCORE
    # ========================================================
    ad_score_rules = get_score_rules(
        config,
        "AD_SCORE_RULES"
    )

    ad_score_threshold = max(
        1,
        get_int(
            config,
            "AD_SCORE_THRESHOLD",
            6
        )
    )

    # ========================================================
    # SCROLL
    # ========================================================
    scroll_count = max(
        1,
        get_int(
            config,
            "SCROLL_COUNT",
            10
        )
    )

    scroll_distance = max(
        100,
        get_int(
            config,
            "SCROLL_DISTANCE",
            600
        )
    )

    scroll_wait_ms = max(
        1000,
        get_int(
            config,
            "SCROLL_WAIT_MS",
            6000
        )
    )

    see_more_wait_ms = max(
        500,
        get_int(
            config,
            "SEE_MORE_WAIT_MS",
            2000
        )
    )

    # ========================================================
    # STATE
    # ========================================================
    # Các bài đã bắn Telegram, tối đa 100 ID.
    # Đọc từ sent_ids.txt để chạy lại (--once) không gửi trùng.
    sent_posts = load_commented_ids(
        SENT_IDS_FILE,
        MAX_COMMENTED_IDS
    )

    telegram_success = 0
    telegram_failed = 0
    no_keyword = 0
    excluded_keyword_count = 0
    advertisement_count = 0
    empty_text = 0
    duplicate_count = 0

    # ========================================================
    # START
    # ========================================================
    print()
    print("================================================")
    print(" FACEBOOK GROUP → TELEGRAM MONITOR")
    print("================================================")
    print(
        "📌 Số group:",
        len(group_urls)
    )

    for index, group_url in enumerate(group_urls, 1):
        print(
            f"   {index}. {group_url}"
        )

    print(
        "🔑 Keyword:",
        keywords
    )
    print(
        "🚫 Keyword loại:",
        exclude_keywords
    )
    print(
        "📢 AD_PATTERNS:",
        len(ad_patterns)
    )
    print(
        "📊 AD SCORE RULES:",
        len(ad_score_rules)
    )
    print(
        "🎯 AD SCORE THRESHOLD:",
        ad_score_threshold
    )
    print(
        "📜 Scroll:",
        scroll_count
    )
    print(
        "📏 Scroll distance:",
        scroll_distance,
        "px"
    )
    print(
        "⏱ Scroll wait:",
        scroll_wait_ms,
        "ms"
    )
    print(
        "🔽 Xem thêm wait:",
        see_more_wait_ms,
        "ms"
    )
    print(
        f"💬 Comment lần 1: COMMENT_TEXT + {find_comment_image('facebook.jpg')}"
    )
    print(
        f"💬 Comment lần 2: COMMENT_TEXT_2 + {find_comment_image('facebook2.jpg')}"
    )
    print("================================================")

    # ====================================================
    # VÒNG QUÉT VĨNH VIỄN
    # ====================================================
    while True:

        try:

            # =================================================
            # QUÉT LẦN LƯỢT TỪNG GROUP
            # =================================================
            for group_index, group_url in enumerate(
                group_urls,
                1
            ):

                if run_deadline and time.time() > run_deadline:
                    print()
                    print(
                        f"⏰ Quá MAX_RUN_MINUTES = {max_run_minutes} phút "
                        f"→ dừng vòng này, bỏ qua "
                        f"{len(group_urls) - group_index + 1} group còn lại."
                    )
                    break

                # Mỗi group có collected riêng để không trộn DOM.
                collected = {}

                print()
                print(
                    "================================================"
                )
                print(
                    f"🌐 GROUP {group_index}/{len(group_urls)}"
                )
                print(
                    f"🔗 {group_url}"
                )
                print(
                    "================================================"
                )

                try:

                    page.goto(
                        group_url,
                        wait_until="domcontentloaded",
                        timeout=60000
                    )

                    # =================================================
                    # CHỜ FACEBOOK
                    # =================================================
                    print(
                        "⏳ Chờ Facebook render ban đầu 8 giây..."
                    )

                    wait_full_time(
                        page,
                        4000
                    )
                    fb_login.close_group_popup(page)   # bang 'Chao mung ban den voi nhom' che bai

                    # =================================================
                    # KIỂM TRA STORY
                    # =================================================
                    print(
                        "\n🔎 Kiểm tra story_message..."
                    )

                    article_count = wait_for_story_message(
                        page,
                        retry_count=3,
                        wait_ms=3000
                    )

                    print(
                        f"📦 Story_message ban đầu: {article_count}"
                    )

                    # =================================================
                    # NẾU CÓ BÀI → ĐỌC
                    # NẾU KHÔNG CÓ → VẪN TIẾP TỤC SCROLL
                    # =================================================
                    if article_count > 0:

                        print(
                            "\n📝 Đọc bài viết hiện tại..."
                        )

                        result = handle_new_posts(
                            page,
                            collected,
                            sent_posts,
                            keywords,
                            exclude_keywords,
                            ad_patterns,
                            ad_score_rules,
                            ad_score_threshold,
                            telegram_token,
                            telegram_chat_id
                        )

                        if result:
                            telegram_success += result[
                                "telegram_success"
                            ]
                            telegram_failed += result[
                                "telegram_failed"
                            ]
                            no_keyword += result[
                                "no_keyword"
                            ]
                            excluded_keyword_count += result[
                                "excluded_keyword_count"
                            ]
                            advertisement_count += result[
                                "advertisement_count"
                            ]
                            empty_text += result[
                                "empty_text"
                            ]
                            duplicate_count += result[
                                "duplicate_count"
                            ]

                    else:

                        print(
                            "⚠️ Chưa thấy story_message."
                        )
                        print(
                            "➡️ KHÔNG DỪNG."
                        )
                        print(
                            "➡️ Sẽ tiếp tục scroll để Facebook render bài."
                        )

                    # =================================================
                    # SCROLL
                    # =================================================
                    print()
                    print(
                        "================================================"
                    )
                    print(
                        "📜 BẮT ĐẦU SCROLL"
                    )
                    print(
                        "================================================"
                    )

                    for i in range(
                        scroll_count
                    ):

                        # Hết giờ giữa chừng 1 group → dừng cuộn để thoát đúng cách
                        # (đóng trình duyệt, lưu cookie), không đợi bị buộc thoát.
                        if run_deadline and time.time() > run_deadline:
                            print(
                                f"\n⏰ Hết {max_run_minutes} phút → dừng cuộn group này."
                            )
                            break

                        print()
                        print(
                            f"========== VÒNG {i + 1}/{scroll_count} =========="
                        )

                        try:

                            # ------------------------------------------------
                            # ĐẢM BẢO DIALOG ĐÃ ĐÓNG TRƯỚC KHI SCROLL
                            # ------------------------------------------------
                            dialog_ready = close_post_dialog(
                                page,
                                timeout_ms=5000
                            )

                            if not dialog_ready:
                                print(
                                    "   ⛔ Dialog chưa đóng → KHÔNG scroll vòng này."
                                )
                                print(
                                    "   ➡️ Giữ nguyên vị trí hiện tại và thử đóng lại ở vòng kế tiếp."
                                )
                                continue

                            # ------------------------------------------------
                            # SCROLL
                            # ------------------------------------------------
                            print(
                                f"⬇️ Scroll {scroll_distance}px..."
                            )

                            scroll_page(
                                page,
                                scroll_distance
                            )

                            # ------------------------------------------------
                            # WAIT
                            # ------------------------------------------------
                            wait_full_time(
                                page,
                                scroll_wait_ms
                            )

                            # ------------------------------------------------
                            # KIỂM TRA STORY
                            # ------------------------------------------------
                            print(
                                "🔎 Tìm story_message..."
                            )

                            article_count = wait_for_story_message(
                                page,
                                retry_count=2,
                                wait_ms=1500
                            )

                            print(
                                f"📦 Story_message hiện tại: {article_count}"
                            )

                            # ------------------------------------------------
                            # KHÔNG CÓ BÀI → TIẾP TỤC
                            # ------------------------------------------------
                            if article_count == 0:

                                print(
                                    "   ⚠️ Chưa có story_message sau scroll."
                                )
                                print(
                                    "   ➡️ Vẫn tiếp tục vòng tiếp theo."
                                )
                                continue

                            # ------------------------------------------------
                            # ĐỌC ARTICLE
                            # ------------------------------------------------
                            before_ids = set(
                                collected
                            )

                            new_count = read_articles(
                                page,
                                collected
                            )

                            TOTAL_DETECTED_POSTS += (
                                new_count
                            )

                            new_post_ids = [
                                post_id
                                for post_id in collected
                                if post_id not in before_ids
                            ]

                            print(
                                f"\n📊 Vòng {i + 1}: "
                                f"thêm {new_count} bài | "
                                f"tổng {len(collected)} bài"
                            )

                            print(
                                f"🔎 Tổng bài phát hiện toàn phiên: "
                                f"{TOTAL_DETECTED_POSTS}"
                            )

                            # =================================================
                            # XỬ LÝ
                            # =================================================
                            if new_post_ids:

                                print(
                                    f"\n📨 Có {len(new_post_ids)} bài mới"
                                )

                                result = process_new_posts(
                                    new_post_ids,
                                    collected,
                                    sent_posts,
                                    keywords,
                                    exclude_keywords,
                                    ad_patterns,
                                    ad_score_rules,
                                    ad_score_threshold,
                                    page,
                                    CURRENT_CONFIG,
                                    COMMENTED_IDS,
                                    COMMENTED_IDS_FILE,
                                    telegram_token,
                                    telegram_chat_id
                                )

                                telegram_success += result[
                                    "telegram_success"
                                ]
                                telegram_failed += result[
                                    "telegram_failed"
                                ]
                                no_keyword += result[
                                    "no_keyword"
                                ]
                                excluded_keyword_count += result[
                                    "excluded_keyword_count"
                                ]
                                advertisement_count += result[
                                    "advertisement_count"
                                ]
                                empty_text += result[
                                    "empty_text"
                                ]
                                duplicate_count += result[
                                    "duplicate_count"
                                ]

                                print(
                                    "\n   📊 Kết quả vòng:"
                                )
                                print(
                                    "      Telegram +",
                                    result["telegram_success"]
                                )
                                print(
                                    "      Quảng cáo +",
                                    result["advertisement_count"]
                                )
                                print(
                                    "      Keyword loại +",
                                    result["excluded_keyword_count"]
                                )
                                print(
                                    "      Không keyword +",
                                    result["no_keyword"]
                                )

                            else:

                                print(
                                    "   ℹ️ Không có bài mới."
                                )

                        except PlaywrightTimeoutError as e:

                            # Một vòng scroll lỗi timeout không được làm dừng group.
                            print(
                                "   ⚠️ TIMEOUT trong vòng scroll → bỏ qua vòng này."
                            )
                            print(
                                repr(e)
                            )
                            continue

                        except Exception as e:

                            # Một lỗi bất kỳ của một vòng cũng không làm treo monitor.
                            print(
                                "   ⚠️ Lỗi trong vòng scroll → bỏ qua vòng này."
                            )
                            print(
                                repr(e)
                            )
                            continue

                    # =================================================
                    # KẾT THÚC GROUP
                    # =================================================
                    print()
                    print(
                        "================================================"
                    )
                    print(
                        f"🏁 GROUP {group_index}/{len(group_urls)} HOÀN TẤT"
                    )
                    print(
                        f"📦 Tổng bài trong group: {len(collected)}"
                    )
                    print(
                        "================================================"
                    )

                except PlaywrightTimeoutError as e:

                    # Lỗi load group: bỏ group hiện tại, sang group kế tiếp.
                    print()
                    print(
                        f"⚠️ PLAYWRIGHT TIMEOUT GROUP {group_index}:"
                    )
                    print(
                        repr(e)
                    )
                    print(
                        "➡️ Bỏ qua group này, tiếp tục group kế tiếp."
                    )
                    continue

                except Exception as e:

                    # Lỗi group: không được dừng monitor nhiều group.
                    print()
                    print(
                        f"⚠️ LỖI GROUP {group_index}:"
                    )
                    print(
                        repr(e)
                    )
                    print(
                        "➡️ Bỏ qua group này, tiếp tục group kế tiếp."
                    )
                    continue

            # =================================================
            # ĐÃ QUÉT HẾT TOÀN BỘ GROUP
            # =================================================
            print()
            print(
                "================================================"
            )
            print(
                "🏁 ĐÃ QUÉT HẾT TOÀN BỘ GROUP"
            )
            print(
                f"📦 Số group: {len(group_urls)}"
            )
            print(
                "================================================"
            )

            # Theo yêu cầu: sau khi quét hết group thì nghỉ SCROLL_WAIT_MS.
            print(
                f"⏳ Đã quét hết group → nghỉ SCROLL_WAIT_MS = "
                f"{scroll_wait_ms} ms..."
            )
            time.sleep(
                scroll_wait_ms / 1000.0
            )

            # =================================================
            # TỔNG KẾT
            # =================================================
            print()
            print(
                "📊 TỔNG KẾT VÒNG QUÉT"
            )
            print(
                "================================================"
            )
            print(
                "Tổng bài phát hiện:",
                TOTAL_DETECTED_POSTS
            )
            print(
                "Quảng cáo bị loại:",
                advertisement_count
            )
            print(
                "Không khớp keyword:",
                no_keyword
            )
            print(
                "Bị loại bởi EXCLUDE:",
                excluded_keyword_count
            )
            print(
                "Telegram thành công:",
                telegram_success
            )
            print(
                "Telegram thất bại:",
                telegram_failed
            )
            print(
                "Đã gửi trùng:",
                duplicate_count
            )
            print(
                "Text trống:",
                empty_text
            )
            fb_login.note(
                BASE_DIR,
                f"   ✔ Đã xem {TOTAL_DETECTED_POSTS} bài: {telegram_success} khách mới · "
                f"{advertisement_count} quảng cáo bỏ qua · {excluded_keyword_count + no_keyword} bài không phù hợp"
                + (f" · ⚠️ {telegram_failed} lỗi gửi Telegram" if telegram_failed else "")
            )
            print(
                "================================================"
            )

        except KeyboardInterrupt:
            print(
                "\n🛑 Đã dừng chương trình."
            )
            break

        except Exception as e:

            # Bảo vệ toàn bộ vòng monitor.
            print(
                "\n⚠️ LỖI VÒNG MONITOR:"
            )
            print(
                repr(e)
            )
            print(
                "➡️ Không thoát chương trình, chuyển sang thời gian chờ."
            )

        if run_once:
            print(
                "\n✅ Chế độ --once: xong 1 vòng, thoát."
            )
            break

        # ====================================================
        # CHỜ VÒNG MONITOR TIẾP THEO
        # ====================================================
        print()
        print(
            f"⏳ Chờ {loop_wait_seconds} giây "
            "trước vòng quét tiếp theo..."
        )

        try:
            time.sleep(
                loop_wait_seconds
            )
        except KeyboardInterrupt:
            print(
                "\n🛑 Đã dừng chương trình."
            )
            break


def warn_not_joined(account, campaigns):
    """Nhom theo doi ma tai khoan CHUA VAO / dang cho duyet (theo trang thai xin vao nhom ben Dang bai):
    nhom rieng tu se khong thay bai -> ghi 1 dong canh bao (khong lap lai neu khong doi)."""
    try:
        import upstt_store
        states = upstt_store.join_state(account["id"])
    except Exception:
        return
    if not states:
        return   # chua tung kiem tra trang thai nhom -> khong biet, khong bao
    waiting, missing = [], []
    for c in campaigns:
        for url in c["groups"]:
            slug = fb_login.group_slug(url) or url
            st = (states.get(slug) or {}).get("status", "")
            if st in ("pending", "questions"):
                waiting.append(slug)
            elif st != "joined":
                missing.append(slug)
    waiting, missing = list(dict.fromkeys(waiting)), list(dict.fromkeys(missing))
    if waiting or missing:
        parts = ([f"{len(waiting)} nhóm đang chờ duyệt"] if waiting else []) + (
            [f"{len(missing)} nhóm chưa vào / chưa kiểm tra"] if missing else [])
        fb_login.note(BASE_DIR, f"⚠️ {account['name']}: " + ", ".join(parts) + " → nhóm riêng tư sẽ không thấy bài "
                                "(xin vào nhóm ở kịch bản, nút 🙋 Xin vào): " + ", ".join((waiting + missing)[:8]),
                      once=True)


def weekday_ok(campaign):
    """Thu trong tuan duoc quet (de trong = hang ngay). 0 = Thu 2 ... 6 = Chu nhat (giong ben dang bai)."""
    days = campaign.get("weekdays") or []
    return not days or datetime.now().weekday() in days


def run_account(account, data, only_campaign=None, only_urls=None):
    """Quet lan luot cac nhom theo doi dang bat cua 1 tai khoan, trong 1 trinh duyet.

    only_campaign / only_urls: nut 'Quet ngay' (man tai khoan duoi kich ban) -> chi quet muc do, chi cac nhom da
    tick, ke ca muc dang tat / ngoai thu da chon."""

    global COMMENTED_IDS_FILE
    global SENT_IDS_FILE

    # Nhat ky cua tai khoan nay ghi rieng: logs/<id>/nhat_ky.txt
    fb_login.use_task_log(BASE_DIR, account["id"])

    acc_dir = monitor_store.account_dir(account["id"])
    if not account_status.usable(acc_dir):
        st = account_status.read(acc_dir)
        print(f"[SKIP] {account['name']}: {account_status.LABELS[st['status']]} -> tạm dừng, "
              "cần đăng nhập lại trong giao diện (MO_TOOL.bat).")
        fb_login.note(BASE_DIR, f"⏸ {account['name']}: {account_status.LABELS[st['status']]} → tạm dừng quét, "
                                "cần đăng nhập lại.", once=True)
        return

    if only_campaign:
        campaigns = [dict(c, groups=[g for g in c["groups"] if not only_urls or g in only_urls])
                     for c in account["campaigns"] if c["id"] == only_campaign]
        campaigns = [c for c in campaigns if c["groups"]]
    else:
        campaigns = [c for c in account["campaigns"] if c["enabled"]]
        off = [c["name"] for c in campaigns if not weekday_ok(c)]
        if off:
            print(f"[SKIP] Hom nay khong quet: {', '.join(off)} (ngoai cac thu da chon).")
        campaigns = [c for c in campaigns if weekday_ok(c)]
        # Chu ky quet dat theo kich ban: lich tai khoan chay theo chu ky ngan nhat -> kich ban chua den han thi de.
        later = [c["name"] for c in campaigns if not monitor_store.scan_due(c)]
        if later:
            print(f"[SKIP] Chua den han quet: {', '.join(later)}.")
        campaigns = [c for c in campaigns if monitor_store.scan_due(c)]
    if not campaigns:
        print(f"[SKIP] {account['name']}: khong co nhom theo doi nao can quet luc nay.")
        return
    warn_not_joined(account, campaigns)

    # Cung nick Facebook dang dang bai o tool khac -> doi xong roi moi quet (khong bo luot).
    # Goi TRUOC dong ho tu ngat de thoi gian doi khong bi tinh vao gioi han chay.
    if not fb_login.hold_nick(acc_dir, wait_minutes=30):
        fb_login.note(BASE_DIR, f"⚠️ {account['name']}: tài khoản bận quá 30 phút (tool khác đang dùng) → vẫn quét.")

    # Khong gioi han thoi gian quet: quet het cac nhom (cuon du so lan) roi tu xong.
    # Chi giu chot chong treo (Chrome / Facebook dung han) de luot sau con chay duoc.
    max_run_minutes = monitor_store.hang_guard_minutes(account)
    run_deadline = None

    watchdog = threading.Timer(
        max_run_minutes * 60,
        lambda: (
            print(f"\n⛔ Treo quá {max_run_minutes} phút → buộc thoát.", flush=True),
            fb_login.note(BASE_DIR, f"⛔ {account['name']}: lượt quét bị treo quá {max_run_minutes} phút → tự dừng."),
            os._exit(2)
        )
    )
    watchdog.daemon = True
    watchdog.start()

    print(f"[START] {account['name']}: {len(campaigns)} nhóm theo dõi (không giới hạn thời gian, chống treo {max_run_minutes} phút).")
    fb_login.note(BASE_DIR, f"▶ Bắt đầu quét – {account['name']}")
    started = time.time()

    with sync_playwright() as p:

        context = fb_login.open_context(
            p,
            monitor_store.account_dir(account["id"]),
            headless=account["headless"]
        )

        try:
            page = fb_login.get_page(context)
            try:
                fb_login.verify_and_record(page, acc_dir)
            except fb_login.NotLoggedIn:
                fb_login.note(BASE_DIR, f"⚠️ {account['name']}: Facebook đã đăng xuất tài khoản → tạm dừng, "
                                        "cần đăng nhập lại.")
                raise

            due = fb_login.groups_due(acc_dir, known=[fb_login.group_slug(g) for c in campaigns for g in c["groups"]])
            if due:
                # Binh luan da gui >= 2 tieng: xem quan tri vien da duyet / go chua (1 trang / nhom).
                print(f"📊 Kiểm tra kết quả bình luận ở {len(due)} nhóm.")
                fb_login.check_results(page, acc_dir, due, note=lambda t: fb_login.note(BASE_DIR, t))

            # Bai da binh luan: theo tai khoan (khong binh luan 2 lan cung 1 bai).
            COMMENTED_IDS_FILE = monitor_store.account_dir(account["id"]) / "commented_ids.txt"

            for index, campaign in enumerate(campaigns, 1):

                if run_deadline and time.time() > run_deadline:
                    print(
                        f"\n⏰ Hết {max_run_minutes} phút → bỏ qua "
                        f"{len(campaigns) - index + 1} nhóm theo dõi còn lại."
                    )
                    break

                print()
                print("################################################")
                print(f"📂 NHÓM THEO DÕI {index}/{len(campaigns)}: {campaign['name']}")
                print("################################################")
                # Danh dau trong nhat ky -> tab 'Chi tiet' tach dung dong cua tung nhom theo doi.
                fb_login.note(BASE_DIR, f"📂 Nhóm theo dõi: {campaign['name']}")

                # Bai da gui Telegram: theo nhom theo doi.
                SENT_IDS_FILE = monitor_store.campaign_dir(campaign["id"]) / "sent_ids.txt"

                try:
                    scan_round(
                        monitor_store.to_legacy_config(campaign),
                        page,
                        run_deadline,
                        max_run_minutes
                    )
                    if not only_campaign:   # 'Quet ngay' khong doi lich quet tu dong
                        monitor_store.mark_scanned(campaign["id"])
                except Exception as e:
                    print(f"\n⚠️ Lỗi nhóm theo dõi '{campaign['name']}': {e!r} → sang nhóm tiếp theo.")
                    fb_login.note(BASE_DIR, f"   ⚠️ {campaign['name']}: gặp lỗi, bỏ qua lượt này.")

            fb_login.note(BASE_DIR, f"■ Xong lượt quét ({round((time.time() - started) / 60)} phút)")

            # Trinh duyet dang mo san -> xem tin nhan giup lich 'Kiem tra tin nhan' (nick hay ban quet nen lich
            # do hay bo luot). Loi o day khong anh huong luot quet.
            try:
                fb_login.check_inbox_page(page, acc_dir, account["name"], note=lambda t: fb_login.note(BASE_DIR, t),
                                          piggyback=True)
            except Exception as error:
                print(f"[TIN NHAN] Loi xem tin nhan: {str(error).splitlines()[0][:100]}")

        finally:
            try:
                context.close()
            except Exception:
                pass
            fb_login.release_nick(acc_dir)


def main():

    # --once --account a1 : Task Scheduler goi theo lich cua tai khoan
    # --login / --check --account a1 : dang nhap / kiem tra dang nhap
    # --validate | --accounts | --schedule-json : cho setup.ps1
    args = sys.argv[1:]
    data = monitor_store.load()

    def get_arg(name):
        if name in args and args.index(name) + 1 < len(args):
            return args[args.index(name) + 1]
        return None

    if "--validate" in args:
        errors = monitor_store.validate(data)
        for error in errors:
            print(error)
        sys.exit(2 if errors else 0)

    if "--accounts" in args:
        for account in data["accounts"]:
            if any(c["enabled"] for c in account["campaigns"]):
                print(f"{account['id']}\t{account['name']}")
        return

    if "--schedule-json" in args:
        print(json.dumps(monitor_store.schedule_entries(data), ensure_ascii=False))
        return

    account = monitor_store.find_account(data, get_arg("--account") or "")

    # Giao dien: nut 'Kiem tra ngay' (tab Ket qua) / nut 'Mo' trang Noi dung cua ban cua 1 nhom.
    if "--check-results" in args or "--open-url" in args:
        if not account:
            raise ValueError("Thieu hoac sai --account.")
        acc_dir = monitor_store.account_dir(account["id"])
        with sync_playwright() as p:
            if "--open-url" in args:
                fb_login.open_url_window(p, acc_dir, get_arg("--open-url"))
                return
            slugs = [s for s in (get_arg("--groups") or "").split(",") if s]
            fb_login.use_task_log(BASE_DIR, account["id"])
            fb_login.check_results_cli(acc_dir, slugs, lambda: fb_login.open_context(p, acc_dir, headless=True),
                                       note=lambda t: fb_login.note(BASE_DIR, t))
        return

    # Giao dien: 'Cham bai' (tab Ket qua chi tiet) -> binh luan mo ta shop vao cac bai DA DUYET da chon.
    # Moi bai toi da 1 lan (khong up tin). Trang thai tung bai ghi vao accounts/<id>/cham_bai.json de bang hien:
    #   queued -> sending -> sent (da gui) -> visible (mo lai bai thay binh luan) | failed.
    # --verify-care: mo lai cac bai 'sent' xem binh luan da hien chua (vd nhom duyet binh luan) -> visible.
    if "--comment-posts" in args or "--verify-care" in args:
        if not account:
            raise ValueError("Thieu hoac sai --account.")
        import random
        verify_only = "--verify-care" in args
        acc_dir = monitor_store.account_dir(account["id"])
        urls = [u for u in (get_arg("--urls") or "").split("|") if u.strip()]
        text = (get_arg("--text") or "").strip()
        fb_login.use_task_log(BASE_DIR, account["id"])
        care = fb_login.load_care_state(acc_dir)
        n = len(urls)
        fb_login.write_progress(acc_dir, "start", "Đang chuẩn bị…", 0, n)
        if not urls or (not verify_only and not text):
            fb_login.write_progress(acc_dir, "done", "Thiếu nội dung hoặc chưa chọn bài.", 0, n, done=True, ok=False)
            return
        if not verify_only:
            for url in urls:
                if care.get(fb_login.post_id_of(url) or url, {}).get("status") not in ("sent", "visible"):
                    fb_login.set_care_status(acc_dir, url, "queued", text)
        try:
            with sync_playwright() as p:
                context = fb_login.open_context(p, acc_dir, headless=True)
                try:
                    page = fb_login.get_page(context)
                    fb_login.verify_and_record(page, acc_dir)
                    ok_count = skip = fail = streak = seen = 0
                    for i, url in enumerate(urls):
                        pid = fb_login.post_id_of(url) or url
                        old = care.get(pid, {})
                        if verify_only:
                            if old.get("status") != "sent":
                                continue
                            fb_login.write_progress(acc_dir, "group", f"Đang xem bình luận bài {i + 1}/{n}…", i, n)
                            try:
                                if fb_login.comment_visible(page, url, old.get("text") or text):
                                    fb_login.set_care_status(acc_dir, url, "visible")
                                    seen += 1
                            except Exception as error:
                                print(f"[CHAM] Loi xem bai: {error}")
                            continue
                        if old.get("status") in ("sent", "visible"):   # moi bai toi da 1 lan -> khong thanh up tin
                            skip += 1
                            fb_login.note(BASE_DIR, f"   ⏭ Bỏ qua (đã bình luận trước đó): {url}")
                            continue
                        fb_login.write_progress(acc_dir, "group", f"Đang bình luận bài {i + 1}/{n}…", i, n)
                        fb_login.set_care_status(acc_dir, url, "sending", text)
                        try:
                            ok = post_comment_on_facebook(page, url, text)
                        except Exception as error:
                            print(f"[CMT] Loi: {error}")
                            ok = False
                        if ok:
                            ok_count += 1
                            streak = 0
                            fb_login.set_care_status(acc_dir, url, "sent", text)
                            fb_login.record_sent(acc_dir, fb_login.group_slug(url) or url, kind="comment",
                                                 text=text, post_url=url)
                            try:   # mo lai bai: thay binh luan cua minh -> 'da len'
                                if fb_login.comment_visible(page, url, text):
                                    fb_login.set_care_status(acc_dir, url, "visible", text)
                                    seen += 1
                            except Exception as error:
                                print(f"[CHAM] Loi xem lai bai: {error}")
                            fb_login.note(BASE_DIR, f"   💬 Đã bình luận mô tả shop vào bài | {url}")
                        else:
                            fail += 1
                            streak += 1
                            fb_login.set_care_status(acc_dir, url, "failed", text)
                            fb_login.note(BASE_DIR, f"   ⚠️ Chưa bình luận được bài này | {url}")
                            try:
                                if fb_login.is_rate_limited(page.evaluate("() => document.body.innerText")):
                                    info = fb_login.pause_nick(acc_dir, "Facebook giới hạn khi bình luận chăm bài")
                                    fb_login.note(BASE_DIR, f"⛔ Facebook giới hạn tần suất → dừng, tạm nghỉ "
                                                            f"{info['hours']} giờ.")
                                    break
                            except Exception:
                                pass
                            if streak >= 2:
                                fb_login.note(BASE_DIR, "⛔ Lỗi 2 bài liền → dừng cho an toàn.")
                                break
                        if i < n - 1:
                            page.wait_for_timeout(random.randint(30_000, 70_000))   # giãn cách như người
                    # Bai con 'queued' (dung giua chung) -> tra ve chua lam de lan sau chon lai duoc.
                    for url in urls:
                        if fb_login.load_care_state(acc_dir).get(fb_login.post_id_of(url) or url, {}).get(
                                "status") in ("queued", "sending"):
                            fb_login.set_care_status(acc_dir, url, "failed")
                    if verify_only:
                        msg = f"Xong: {seen} bình luận đã hiện trên bài."
                    else:
                        msg = (f"Xong: {ok_count} đã bình luận ({seen} đã thấy hiện) · {skip} bỏ qua (đã làm) · "
                               f"{fail} lỗi.")
                    fb_login.write_progress(acc_dir, "done", msg, n, n, done=True, ok=(verify_only or ok_count > 0
                                                                                     or fail == 0))
                finally:
                    context.close()
        except fb_login.NotLoggedIn:
            fb_login.write_progress(acc_dir, "done", "Facebook đã đăng xuất tài khoản → đăng nhập lại.", 0, n,
                                    done=True, ok=False)
            raise
        except Exception as error:
            fb_login.write_progress(acc_dir, "done", f"Lỗi: {str(error).splitlines()[0][:120]}", 0, n,
                                    done=True, ok=False)
            raise
        return

    if "--login" in args or "--check" in args or "--logout" in args:

        if not account:
            raise ValueError("Thieu hoac sai --account.")

        acc_dir = monitor_store.account_dir(account["id"])
        fb_login.start_account_log(acc_dir, args)
        if "--check" in args and "--force" in args:
            fb_login.acquire(acc_dir, force=True)   # nguoi dung chon dung luot dang chay de kiem tra ngay
        print(f"[ACCOUNT] {account['name']}")

        with sync_playwright() as p:

            if "--logout" in args:
                fb_login.logout(p, acc_dir, force="--force" in args)
                return

            if "--login" in args:
                fb_login.interactive_login(p, acc_dir, force="--force" in args)

            context = fb_login.open_context(p, acc_dir, headless=True)

            try:
                fb_login.verify_and_record(fb_login.get_page(context), acc_dir, fetch_name=True)
            finally:
                context.close()

        return

    if "--once" in args:

        if account:
            # 'Quet ngay': --item mX --only nhom|nhom (khong dung --campaign: main.py chuyen --once --campaign sang
            # tool dang bai).
            only = get_arg("--only")
            run_account(account, data, only_campaign=get_arg("--item"),
                        only_urls={u.strip() for u in only.split("|") if u.strip()} if only else None)
        else:
            # Lich kieu cu (khong kem --account): quet moi tai khoan.
            for item in data["accounts"]:
                run_account(item, data)

        print("\n✅ Chế độ --once: xong, thoát.")
        return

    print("Cach dung: fb_monitor_v4.py --once --account a1 | --login --account a1 | --check --account a1")


# ============================================================
# START
# ============================================================

def redirect_output_to_log():
    """pythonw (Task Scheduler) không có cửa sổ → ghi ra log.txt để xem lỗi."""

    if sys.stdout is not None:
        return

    # Luot quet cua 1 tai khoan (--once --account a1) -> log RIENG: logs/a1/log.txt.
    # Lenh khac (setup.ps1 goi --validate, --schedule-json...) -> log.txt chung.
    args = sys.argv[1:]
    log_file = LOG_FILE
    if "--once" in args and "--account" in args and args.index("--account") + 1 < len(args):
        try:
            log_file = fb_login.task_log_dir(BASE_DIR, args[args.index("--account") + 1]) / "log.txt"
        except OSError:
            pass

    # Log đầy 5MB → đổi thành log.1.txt (cũ hơn: log.2.txt), giữ 3 file, không mất dữ liệu mới.
    fb_login.rotate_log(log_file, 5_000_000, keep=3)

    # Ghi an toan: o day / file bi khoa -> bo qua dong nhat ky, KHONG lam chet luot quet.
    stream = fb_login.open_log_stream(log_file)
    sys.stdout = sys.stderr = stream

    print(
        f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} | "
        f"{' '.join(sys.argv[1:])} ====="
    )


if __name__ == "__main__":

    redirect_output_to_log()

    try:

        main()

    except fb_login.NotLoggedIn as e:

        print(
            f"\n❌ {e}"
        )
        sys.exit(fb_login.EXIT_NOT_LOGGED_IN)

    except fb_login.ProfileBusy as e:

        print(
            f"\n[LOGIN] {e}"
        )
        sys.exit(fb_login.EXIT_PROFILE_BUSY)

    except KeyboardInterrupt:

        print(
            "\n🛑 Đã dừng chương trình."
        )

    except Exception as e:

        print(
            "\n❌ CHƯƠNG TRÌNH DỪNG DO LỖI:"
        )

        print(
            repr(e)
        )

        sys.exit(1)
