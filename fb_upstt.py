# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
import json
import os
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

import fb_login
import account_status
import upstt_store


BASE_DIR = Path(__file__).resolve().parent

def disable_windows_quick_edit_mode():
    """Tat 'Quick Edit Mode' cua console Windows.

    Khi Quick Edit Mode dang bat, chi can nguoi dung click chuot (hoac vo tinh
    bam) vao cua so terminal la toan bo tien trinh dang chay se bi 'dong bang'
    cho toi khi bam Enter/Esc. Day la nguyen nhan pho bien khien script chay
    theo lich (schedule) bi 'treo' hang gio dong ho ma khong co loi gi ca.
    Ham nay chi co tac dung tren Windows; cac he dieu hanh khac se bo qua.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        STD_INPUT_HANDLE = -10
        ENABLE_QUICK_EDIT_MODE = 0x0040
        ENABLE_EXTENDED_FLAGS = 0x0080

        handle = kernel32.GetStdHandle(STD_INPUT_HANDLE)
        mode = ctypes.c_ulong()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return

        new_mode = (mode.value & ~ENABLE_QUICK_EDIT_MODE) | ENABLE_EXTENDED_FLAGS
        if kernel32.SetConsoleMode(handle, new_mode):
            print("[SESSION] Da tat Quick Edit Mode de tranh bi treo khi click vao terminal.")
    except Exception as error:
        print(f"[SESSION] Khong the tat Quick Edit Mode tu dong: {error}")


def find_create_post_trigger(page):
    trigger = page.locator("div[role='button']").filter(
        has_text=re.compile(r"B\u1ea1n vi\u1ebft g\u00ec \u0111i|Ban viet gi di", re.IGNORECASE)
    )
    trigger.first.wait_for(state="visible", timeout=15_000)
    return trigger.first


def find_composer_dialog(page):
    dialog = page.locator("div[role='dialog']").filter(
        has_text=re.compile(r"T\u1ea1o b\u00e0i vi\u1ebft|Tao bai viet", re.IGNORECASE)
    )
    dialog.first.wait_for(state="visible", timeout=10_000)
    return dialog.first


# Ket qua sau khi bam Dang (doc tu thong bao Facebook hien ra).
POSTED, PENDING, BLOCKED, FAILED = "da_dang", "cho_duyet", "bi_chan", "loi"
NOT_MEMBER = "chua_vao_nhom"
SKIP_PENDING = "bo_qua_cho_duyet"   # nhom dang co nhieu bai cho duyet -> khong dang them luot nay
SKIP_PAUSED = "nhom_tam_nghi"       # nhom dang tam ngung (loi do nhom nhieu luot)
RESULT_LABELS = {POSTED: "Đã đăng", PENDING: "Chờ duyệt", BLOCKED: "BỊ CHẶN", FAILED: "Lỗi",
                 NOT_MEMBER: "Chưa vào nhóm", SKIP_PENDING: "Bỏ qua (nhiều bài chờ duyệt)",
                 SKIP_PAUSED: "Nhóm tạm nghỉ"}
PENDING_SEEN = {"count": 0}


def pending_count(page):
    """So bai cua minh dang cho duyet trong nhom (dai 'Dang cho quan tri vien phe duyet - N bai viet')."""
    import unicodedata
    try:
        text = unicodedata.normalize("NFC", page.evaluate("() => document.body.innerText") or "").lower()
    except Exception:
        return 0
    m = re.search(r"đang chờ quản trị viên phê duyệt\s*(\d+)\s*bài viết", text) or \
        re.search(r"pending admin approval\s*(\d+)\s*posts?", text)
    return int(m.group(1)) if m else 0

# Tai khoan chua duoc duyet thanh vien / chua tra loi cau hoi tham gia nhom.
NOT_MEMBER_WORDS = ["xem xét quyền tham gia", "trả lời những câu hỏi", "câu hỏi tham gia", "tham gia nhóm để",
                    "chưa phải là thành viên", "membership", "answer questions", "join group to", "join this group"]

BLOCKED_WORDS = ["tạm thời bị chặn", "bị chặn", "temporarily blocked", "you're blocked", "you are blocked",
                 "bị hạn chế", "restricted", "đi ngược lại tiêu chuẩn", "against our community standards",
                 "goes against"]
PENDING_WORDS = ["chờ phê duyệt", "chờ duyệt", "chờ quản trị viên", "quản trị viên phê duyệt",
                 "quản trị viên nhóm phê duyệt", "gửi bài viết cho quản trị viên",
                 "quản trị viên xem xét", "đang chờ", "pending", "admin approval", "submitted for", "will be reviewed",
                 "awaiting approval"]
ERROR_WORDS = ["không thể đăng", "không đăng được", "couldn't post", "can't post", "could not post",
               "đã xảy ra lỗi", "something went wrong", "thử lại", "try again"]


def classify_post_result(messages, composer_open):
    """messages: chu trong cac thong bao / hop thoai Facebook hien ra sau khi bam Dang."""
    import unicodedata
    text = unicodedata.normalize("NFC", " | ".join(m for m in messages if m)).lower()
    for status, words in ((BLOCKED, BLOCKED_WORDS), (NOT_MEMBER, NOT_MEMBER_WORDS), (PENDING, PENDING_WORDS),
                          (FAILED, ERROR_WORDS)):
        if any(w in text for w in words):
            return status
    return FAILED if composer_open else POSTED


# Buoc dang lam -> khi loi biet hong o dau. FAIL_REASON: ly do da biet (vd Facebook bao gi sau khi bam Dang).
STEP = {"now": ""}
FAIL_REASON = {"text": ""}

STEP_FAIL_TEXT = {
    "mo_nhom": "trang nhóm tải quá lâu (mạng / Facebook chậm, hoặc tài khoản đang mở ở nơi khác)",
    "tim_o_dang": "không thấy ô 'Bạn viết gì đi…' để đăng bài",
    "cho_hop_thoai": "bấm vào ô đăng bài nhưng hộp 'Tạo bài viết' không mở ra",
    "dan_link": "không dán được link vào ô soạn bài (ô soạn bị che / chưa sẵn sàng)",
    "dinh_kem": "không đính kèm được ảnh/video (không thấy nút 'Ảnh/video' trong hộp soạn bài)",
    "cho_tai_anh": "ảnh/video tải lên quá lâu (mạng chậm / file quá nặng)",
    "bam_dang": "không bấm được nút 'Đăng'",
}

# Doc trang nhom luc loi -> doan nguyen nhan cu the hon.
PAGE_HINTS = [
    (["đăng nhập vào facebook", "quên mật khẩu", "log in to facebook"], "Facebook đã đăng xuất tài khoản này"),
    (["trả lời những câu hỏi", "câu hỏi tham gia", "xem xét quyền tham gia"],
     "nhóm bắt trả lời câu hỏi tham gia trước khi đăng"),
    (["chỉ quản trị viên", "only admins"], "nhóm chỉ cho quản trị viên đăng bài"),
    (["nội dung này hiện không hiển thị", "trang này không hiển thị", "this content isn't available"],
     "nhóm không mở được (bị xóa / tài khoản bị chặn khỏi nhóm / link sai)"),
    (["tạm thời bị chặn", "temporarily blocked", "bạn bị hạn chế"], "Facebook đang chặn / hạn chế tài khoản này"),
    (["tham gia nhóm", "join group"], "tài khoản chưa là thành viên nhóm (thấy nút 'Tham gia nhóm')"),
]


def diagnose_page(page):
    try:
        text = page.evaluate("() => document.body.innerText.toLowerCase()")
    except Exception:
        return ""
    has_composer = "bạn viết gì đi" in text
    for words, why in PAGE_HINTS:
        if any(w in text for w in words):
            if why.startswith("tài khoản chưa là thành viên") and has_composer:
                continue
            return why
    return ""


def explain_failure(error, page):
    """Ly do loi de ghi nhat ky: buoc hong + dau hieu tren trang + loi ky thuat rut gon."""
    if FAIL_REASON["text"]:
        return FAIL_REASON["text"]
    parts = [STEP_FAIL_TEXT.get(STEP["now"], "lỗi không rõ bước")]
    hint = diagnose_page(page)
    if hint:
        parts.append("trang đang hiện: " + hint)
    if error is not None:
        if "interrupted by another navigation" in str(error):
            parts.append("Facebook chuyển trang giữa chừng")
        elif "Timeout" in type(error).__name__ or "Timeout" in str(error):
            parts.append("hết thời gian chờ")
        elif str(error):
            parts.append(str(error).splitlines()[0][:80])
    return " – ".join(parts)


def visible_messages(page):
    """Chu trong cac hop thoai / thong bao dang hien (tru hop soan bai cua minh)."""
    found = []
    for el in page.locator("div[role='dialog'], div[role='alert'], div[role='status']").all()[:15]:
        try:
            txt = (el.inner_text(timeout=1_000) or "").strip()
        except Exception:
            continue
        if txt and not re.search(r"T\u1ea1o b\u00e0i vi\u1ebft|Tao bai viet", txt, re.IGNORECASE):
            found.append(re.sub(r"\s+", " ", txt)[:300])
    return found


def read_post_feedback(page, wait_ms, before=()):
    """Cho hop soan bai dong / thong bao MOI hien ra; tra ve (ket qua, cac thong bao moi).

    before: cac thong bao da co TRUOC khi bam Dang (bang Thong bao, chat...) -> bo qua.
    """
    old = {m[:120] for m in before}
    messages, composer_open = [], True
    deadline = time.time() + max(wait_ms, 12_000) / 1000
    hard_end = deadline + POSTING_EXTRA_SECONDS
    POSTING_SEEN["yes"] = False
    while time.time() < deadline:
        page.wait_for_timeout(1_000)
        try:
            composer = page.locator("div[role='dialog']").filter(
                has_text=re.compile(r"T\u1ea1o b\u00e0i vi\u1ebft|Tao bai viet", re.IGNORECASE))
            composer_open = composer.count() > 0
            found = [m for m in visible_messages(page) if m[:120] not in old]
            # 'Dang dang...' = Facebook VAN DANG xu ly bai (khong phai loi) -> doi them, khong tinh la thong bao.
            busy = [m for m in found if is_posting_toast(m)]
            if busy:
                POSTING_SEEN["yes"] = True
                deadline = min(max(deadline, time.time() + 5), hard_end)
            found = [m for m in found if not is_posting_toast(m)]
            messages = found or messages
            # Facebook bao gioi han tan suat bang chu do NGAY TRONG hop soan bai.
            if composer_open and fb_login.is_rate_limited(composer.first.inner_text(timeout=1_000)):
                return BLOCKED, ["Facebook giới hạn tần suất đăng bài / bình luận của tài khoản này (chống spam)"]
        except Exception:
            continue
        status = classify_post_result(messages, composer_open)
        if status in (BLOCKED, PENDING) or (not composer_open and time.time() > deadline - 4):
            break
    return classify_post_result(messages, composer_open), messages


POSTING_EXTRA_SECONDS = 30          # Facebook con 'Dang dang...' -> doi them toi da bay nhieu giay
POSTING_SEEN = {"yes": False}


def is_posting_toast(message):
    low = (message or "").strip().lower()
    return len(low) < 40 and (low.startswith("đang đăng") or low.startswith("posting"))


MEDIA_BUTTON_RE = re.compile(r"^(Ảnh/video|Ảnh/Video|Photo/video|Photo/Video)$", re.IGNORECASE)
ADD_MEDIA_RE = re.compile(r"Thêm ảnh/video|Add photos/videos|kéo và thả|drag and drop", re.IGNORECASE)


def _file_input(page, dialog):
    """O chon file anh/video cua hop soan bai (Facebook co the dat ngoai hop thoai)."""
    for scope in (dialog, page):
        inputs = scope.locator("input[type='file']")
        for i in range(inputs.count()):
            accept = (inputs.nth(i).get_attribute("accept") or "").lower()
            if not accept or "image" in accept or "video" in accept:
                return inputs.nth(i)
    return None


def attach_media(page, dialog, files):
    """Dinh kem anh / video vao hop 'Tao bai viet' roi doi Facebook tai xong."""
    STEP["now"] = "dinh_kem"
    paths = [str(f) for f in files]
    target = _file_input(page, dialog)
    if target is None:
        # Chua co o chon file -> bam nut 'Anh/video' trong hop soan bai.
        clicked = False
        for el in dialog.locator("[aria-label]").all():
            label = (el.get_attribute("aria-label") or "").strip()
            if MEDIA_BUTTON_RE.match(label):
                el.click()
                clicked = True
                break
        if not clicked:
            raise RuntimeError("Khong thay nut Anh/video trong hop soan bai.")
        page.wait_for_timeout(1_500)
        target = _file_input(page, dialog)
    if target is not None:
        target.set_input_files(paths)
    else:
        # Facebook chi mo hop chon file khi bam vung 'Them anh/video'.
        with page.expect_file_chooser(timeout=10_000) as chooser:
            dialog.get_by_text(ADD_MEDIA_RE).first.click()
        chooser.value.set_files(paths)

    STEP["now"] = "cho_tai_anh"
    has_video = any(f.suffix.lower() in upstt_store.VIDEO_EXT for f in files)
    deadline = time.time() + (300 if has_video else 30 + 10 * len(files))
    page.wait_for_timeout(2_000)
    while time.time() < deadline:
        busy = dialog.locator("[role='progressbar']").count()
        post_button = dialog.locator("div[role='button'][aria-label='Đăng'], "
                                     "div[role='button'][aria-label='Dang']").first
        ready = post_button.count() and post_button.get_attribute("aria-disabled") != "true"
        if not busy and ready:
            print(f"[MEDIA] Da tai xong {len(files)} file.")
            return
        page.wait_for_timeout(1_000)
    FAIL_REASON["text"] = STEP_FAIL_TEXT["cho_tai_anh"] + f" – {len(files)} file"
    raise RuntimeError("Anh/video tai len qua lau.")


def post_to_group(page, group_url, share_url, load_wait_ms, submit_wait_ms, skip_pending_check=False, media=()):
    print(f"[GROUP] Mo: {group_url}")
    STEP["now"], FAIL_REASON["text"] = "mo_nhom", ""
    try:
        page.goto(group_url, wait_until="domcontentloaded", timeout=45_000)
    except PlaywrightTimeoutError:
        print("[RETRY] Trang nhom tai qua lau -> thu lai 1 lan.")
        page.goto(group_url, wait_until="domcontentloaded", timeout=60_000)
    try:
        title = re.sub(r"^\(\d+\+?\)\s*", "", page.title() or "")
        title = re.sub(r"\s*[|\-–]\s*Facebook\s*$", "", title).strip()
        if title and title.lower() != "facebook":
            GROUP_NAMES[group_url] = title[:60]
    except Exception:
        pass
    if fb_login.group_slug(page.url):
        GROUP_SLUGS[group_url] = fb_login.group_slug(page.url)   # link share/g/... -> ten nhom that
    page.wait_for_timeout(3_000)
    fb_login.close_group_popup(page)   # nhom moi vao: bang 'Chao mung...' che o dang bai

    # Quan tri vien chua duyet cac bai truoc -> dang them chi lam hang cho dai ra, de bi chan.
    PENDING_SEEN["count"] = pending_count(page)
    if PENDING_SEEN["count"] >= upstt_store.PENDING_LIMIT and not skip_pending_check:
        FAIL_REASON["text"] = (f"nhóm đang có {PENDING_SEEN['count']} bài của bạn chờ quản trị viên duyệt "
                               f"(từ {upstt_store.PENDING_LIMIT} bài trở lên thì không đăng thêm)")
        print(f"[SKIP] {FAIL_REASON['text']}")
        return SKIP_PENDING

    print("[STEP 1/4] Tim o 'Ban viet gi di...'")
    STEP["now"] = "tim_o_dang"
    try:
        trigger = find_create_post_trigger(page)
    except PlaywrightTimeoutError:
        if not fb_login.close_group_popup(page):   # bang chao hien muon
            raise
        trigger = find_create_post_trigger(page)
    trigger.click()

    print("[STEP 2/4] Cho hop thoai 'Tao bai viet'")
    STEP["now"] = "cho_hop_thoai"
    try:
        dialog = find_composer_dialog(page)
    except PlaywrightTimeoutError:
        # Facebook cham / bang chao che -> dong bang, bam lai 1 lan.
        print("[RETRY] Hop 'Tao bai viet' chua mo -> bam lai 1 lan.")
        fb_login.agree_rules(page)   # lan dau dang: hop 'Quy tac nhom' bat bam Dong y
        fb_login.close_group_popup(page)
        find_create_post_trigger(page).click()
        dialog = find_composer_dialog(page)
    textbox = dialog.locator("div[role='textbox'][contenteditable='true']").first
    textbox.wait_for(state="visible", timeout=10_000)

    print(f"[STEP 3/4] Dan link bai viet va cho {load_wait_ms // 1000}s")
    STEP["now"] = "dan_link"
    # Xuong dong: Shift+Enter (an toan trong moi o nhap cua Facebook).
    lines = share_url.replace("\r\n", "\n").split("\n")
    textbox.fill(lines[0])
    for line in lines[1:]:
        page.keyboard.press("Shift+Enter")
        if line:
            page.keyboard.insert_text(line)
    page.wait_for_timeout(load_wait_ms)

    if media:
        print(f"[STEP 3b] Dinh kem {len(media)} anh/video: {', '.join(f.name for f in media)}")
        attach_media(page, dialog, media)

    print("[STEP 4/4] Bam nut 'Dang'")
    STEP["now"] = "bam_dang"
    post_button = dialog.locator(
        "div[role='button'][aria-label='\u0110\u0103ng'], "
        "div[role='button'][aria-label='Dang']"
    ).first
    post_button.wait_for(state="visible", timeout=10_000)
    if post_button.get_attribute("aria-disabled") == "true":
        FAIL_REASON["text"] = "nút 'Đăng' vẫn bị mờ sau khi dán link (link chưa tải xong phần xem trước / link lỗi)"
        raise RuntimeError("Nut Dang van bi vo hieu hoa sau khi da cho tai link.")
    before = visible_messages(page)
    post_button.click()
    print("[WAIT] Cho Facebook phan hoi...")
    status, messages = read_post_feedback(page, submit_wait_ms, before)
    for msg in messages[:3]:
        print(f"[FACEBOOK] {msg}")
    print(f"[KET QUA] {RESULT_LABELS[status]}")
    if status == FAILED:
        if messages:
            FAIL_REASON["text"] = "Facebook báo: " + messages[0][:120]
        elif POSTING_SEEN["yes"]:
            FAIL_REASON["text"] = ("Facebook xử lý bài quá lâu (vẫn hiện 'Đang đăng' sau "
                                   f"{POSTING_EXTRA_SECONDS + submit_wait_ms // 1000} giây) – có thể bài VẪN LÊN, "
                                   "xem lại ở tab Kết quả tổng hợp")
        else:
            FAIL_REASON["text"] = "đã bấm 'Đăng' nhưng hộp soạn bài vẫn mở, Facebook không xác nhận đã đăng"
    return status


LOW_DISK_MB = 2048  # o dia con it hon -> canh bao

GROUP_NAMES = {}   # link nhom -> ten nhom that (lay tu tieu de trang khi mo nhom)
GROUP_SLUGS = {}   # link nhom -> ma nhom that trong link (groups/<ma>) sau khi mo

# Anh chup man hinh moi lan dang loi -> xem Facebook dang hien gi. Tu xoa anh cu hon 2 ngay.
ERROR_SHOT_DIR = BASE_DIR / "anh_loi"
ERROR_SHOT_KEEP_DAYS = 2


def cleanup_error_shots(keep_days=ERROR_SHOT_KEEP_DAYS):
    if not ERROR_SHOT_DIR.exists():
        return
    limit = time.time() - keep_days * 86400
    for f in ERROR_SHOT_DIR.glob("*.png"):
        try:
            if f.stat().st_mtime < limit:
                f.unlink()
        except OSError:
            pass


def save_error_shot(page, group_url):
    try:
        ERROR_SHOT_DIR.mkdir(exist_ok=True)
        name = re.sub(r"[^\w-]+", "_", group_label(group_url))[:40].strip("_") or "nhom"
        path = ERROR_SHOT_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{name}.png"
        page.screenshot(path=str(path), timeout=10_000)
        print(f"[ANH LOI] {path}")
        return path.name
    except Exception as error:
        print(f"[ANH LOI] Khong chup duoc: {error}")
        return ""


def group_label(url):
    """Ten nhom de ghi nhat ky: ten that neu da mo duoc nhom, khong thi rut gon tu link."""
    if GROUP_NAMES.get(url):
        return GROUP_NAMES[url]
    m = re.search(r"/groups/([^/?#]+)|/share/g/([^/?#]+)", url or "")
    return (m.group(1) or f"nhóm {m.group(2)}") if m else (url or "")[:40]


def group_fault(status, reason):
    """Loi do CHINH NHOM (dang lai van hong) -> loai: 'chua_vao' / 'chan_han'; loi khac (mang, popup...) -> ''."""
    if status == NOT_MEMBER or any(w in reason for w in ("trả lời câu hỏi tham gia", "tài khoản chưa là thành viên")):
        return "chua_vao"
    if any(w in reason for w in ("chỉ cho quản trị viên đăng", "nhóm không mở được")):
        return "chan_han"
    return ""


VERIFY_WAIT_SECONDS = 8      # cho giua 2 nhom khi xac minh
WAITING_RECHECK_HOURS = 3    # luot dang theo lich: nhom dang cho duyet cu 3 tieng xem lai 1 lan


def join_options(account, url=None, campaign=None):
    """(cau tra loi mau, co vay tay) cua muc dang dung nhom nay (muc dau tien cua tai khoan co nhom do)."""
    if campaign is None and url:
        slug = (fb_login.group_slug(url) or url).lower()
        campaign = next((c for c in account.get("campaigns", [])
                         if any((fb_login.group_slug(g) or g).lower() == slug for g in c.get("groups", []))), None)
    campaign = campaign or {}
    return campaign.get("join_answer") or None, campaign.get("join_wave", True)


def verify_one(page, acc_dir, url, answer=None, wave=True):
    """Xac minh 1 nhom (fb_login.verify_group), ghi ket qua + nhat ky. -> trang thai."""
    slug = fb_login.group_slug(url) or url
    try:
        status, why, done = fb_login.verify_group(page, url, answer=answer, wave=wave)
    except Exception as error:
        status, why, done = "joined", f"lỗi khi xác minh: {str(error).splitlines()[0][:80]}", []
    fixed = f" (tool đã {', '.join(done)})" if done else ""
    if status == "ready":
        fb_login.set_verified(acc_dir, url, True)
        fb_login.note(BASE_DIR, f"   ✅ {slug}: đã xác minh – vào nhóm là đăng được{fixed}")
    elif status == "joined":
        fb_login.set_verified(acc_dir, url, False, why)
        fb_login.note(BASE_DIR, f"   ⚠️ {slug}: đã vào nhưng chưa xác minh được – {why}{fixed}")
    elif status == "pending":
        fb_login.set_join_status(acc_dir, url, "pending")
        if done:
            fb_login.note(BASE_DIR, f"   ✍️ {slug}: đang chờ duyệt – tool đã tự trả lời câu hỏi tham gia")
        elif why:
            fb_login.note(BASE_DIR, f"   ❓ {slug}: đang chờ duyệt – chưa trả lời được câu hỏi: {why}")
    elif status == "not_member":
        before = fb_login.load_join_state(acc_dir).get(slug, {}).get("status")
        if before in upstt_store.JOIN_WAITING:   # van dang xin (vd nhom hoi cau hoi) -> giu trang thai, ghi gio xem
            fb_login.set_join_status(acc_dir, url, before)
        else:
            fb_login.forget_joined(acc_dir, url)
            fb_login.note(BASE_DIR, f"   {slug}: không còn ở trong nhóm")
    return status


def recheck_waiting(page, acc_dir, urls, campaign=None, every_hours=WAITING_RECHECK_HOURS):
    """Nhom dang xin (cho duyet / cau hoi) da lau chua xem -> mo lai: con cau hoi chua tra loi thi tra loi;
    duoc duyet thi XAC MINH NGAY. -> danh sach nhom vua vao + xac minh xong (dang duoc luon)."""
    state = fb_login.load_join_state(acc_dir)
    answer, wave = join_options({}, campaign=campaign)
    ready = []
    for url in urls:
        g = state.get(fb_login.group_slug(url) or url, {})
        if time.time() - g.get("time", 0) < every_hours * 3600:
            continue
        if verify_one(page, acc_dir, url, answer, wave) == "ready":
            ready.append(url)
        page.wait_for_timeout(VERIFY_WAIT_SECONDS * 1000)
    return ready


def post_to_all_groups(
    page,
    group_urls,
    share_url,
    load_wait_ms,
    submit_wait_ms,
    group_switch_wait_ms=6000,
    acc_dir=None,
    media_pick=None,
):
    counts = {POSTED: 0, PENDING: 0, NOT_MEMBER: 0, SKIP_PENDING: 0, SKIP_PAUSED: 0, BLOCKED: 0, FAILED: 0}
    cleanup_error_shots()
    state = upstt_store.load_group_state(acc_dir) if acc_dir else {"groups": {}, "pending": {}}
    print(f"[BATCH] Bat dau dang vao {len(group_urls)} nhom.")
    for index, group_url in enumerate(group_urls, start=1):
        print(f"\n[PROGRESS] Nhom {index}/{len(group_urls)}")
        key = upstt_store.group_key(group_url)
        g = state["groups"].get(key) or {}
        if g.get("until", 0) > time.time():
            # Nhom dang tam nghi (xem / Reset tren giao dien) -> khong mo nhom, khong cho.
            counts[SKIP_PAUSED] += 1
            fb_login.note(BASE_DIR, f"   ⏸ {RESULT_LABELS[SKIP_PAUSED]} – {group_label(group_url)} – đến "
                                    f"{upstt_store._when(g['until'])}: {g.get('reason', '')}")
            continue
        reason = ""
        try:
            # Nguoi dung bam Reset (nhom nhieu bai cho duyet) -> lan nay van dang 1 lan.
            forced = state.setdefault("force", {}).pop(key, None) is not None
            media = media_pick() if media_pick else ()
            status = post_to_group(page, group_url, share_url, load_wait_ms, submit_wait_ms,
                                   skip_pending_check=forced, media=media)
            if status == FAILED:
                reason = explain_failure(None, page)
        except (PlaywrightTimeoutError, RuntimeError) as error:
            print(f"[ERROR] Khong the dang vao nhom nay: {error}")
            status, reason = FAILED, explain_failure(error, page)
        except Exception as error:
            print(f"[ERROR] Loi khong mong doi: {error}")
            status, reason = FAILED, explain_failure(error, page)
        detail = ""
        if status == FAILED:
            print(f"[LY DO] {reason}")
            shot = save_error_shot(page, group_url)
            detail = f" – {reason}" + (f" (ảnh: anh_loi/{shot})" if shot else "")
        if status == SKIP_PENDING:
            detail = f" – {FAIL_REASON['text']}"
        counts[status] += 1
        icon = {POSTED: "✅", PENDING: "⏳", NOT_MEMBER: "🚪", SKIP_PENDING: "⏭", BLOCKED: "⛔", FAILED: "❌"}[status]
        # Bai da gui: kem link nhom -> tab Ket qua chi tiet biet dung nhom de hien trang thai hien tai.
        fb_login.note(BASE_DIR, f"   {icon} {RESULT_LABELS[status]} – {group_label(group_url)}{detail}"
                      + (f" | {group_url}" if status in (POSTED, PENDING) else ""))

        # ---- ghi trang thai nhom (giao dien hien ghi chu + nut Reset)
        now = time.time()
        if status == SKIP_PENDING:
            p = state["pending"].setdefault(key, {"since": now})
            p["count"] = PENDING_SEEN["count"]
            if now - p["since"] >= upstt_store.PENDING_WARN_DAYS * 86400:
                fb_login.note(BASE_DIR, f"   ⚠️ Nhóm {group_label(group_url)}: {int((now - p['since']) // 86400)} ngày "
                                        "quản trị viên không duyệt bài → nên cân nhắc bỏ nhóm này.", once=True)
        elif status in (POSTED, PENDING):
            state["pending"].pop(key, None)
            state["groups"].pop(key, None)
            if acc_dir:   # ~2 tieng sau tool xem bai nay duoc duyet / bi tu choi chua (tab Ket qua)
                fb_login.record_sent(acc_dir, GROUP_SLUGS.get(group_url) or group_url, link=key, text=share_url)
        fault = group_fault(status, reason)
        if acc_dir and (status in (POSTED, PENDING) or fault == "chua_vao"):
            # Dang duoc = nhom da xac minh; bao chua vao / phai tra loi cau hoi = chua xac minh
            real = f"https://www.facebook.com/groups/{GROUP_SLUGS[group_url]}/" if GROUP_SLUGS.get(group_url) \
                else group_url
            fb_login.set_verified(acc_dir, real, status in (POSTED, PENDING),
                                  reason or "Facebook báo tài khoản chưa vào nhóm")
        if fault:
            g = state["groups"].setdefault(key, {})
            g["streak"] = g.get("streak", 0) + 1
            if g["streak"] >= upstt_store.GROUP_STREAK:
                days, why = upstt_store.GROUP_PAUSE[fault]
                g.update(until=now + days * 86400, streak=0, kind=fault,
                         reason=f"{upstt_store.GROUP_STREAK} lượt liền lỗi: {why} (nghỉ {days} ngày)")
                fb_login.note(BASE_DIR, f"   ⏸ Ngừng đăng nhóm {group_label(group_url)} {days} ngày – {g['reason']}")
        if acc_dir:
            upstt_store.save_group_state(acc_dir, state)

        if status == BLOCKED:
            # Facebook dang chan / gioi han -> dung ngay + nghi ca tai khoan (moi noi dung, ca tool theo doi).
            print("[STOP] Facebook dang chan dang bai -> DUNG cac nhom con lai de bao ve tai khoan.")
            if acc_dir:
                info = fb_login.pause_nick(acc_dir, f"Facebook giới hạn tần suất khi đăng vào nhóm "
                                                    f"{group_label(group_url)}")
                fb_login.note(BASE_DIR, f"⛔ Facebook đang chặn / giới hạn tài khoản này (lần {info['strikes']}) → "
                                        f"dừng các nhóm còn lại, TẠM NGHỈ đăng bài + bình luận {info['hours']} giờ, "
                                        f"đến {fb_login.pause_text(info)}.")
            else:
                fb_login.note(BASE_DIR, "⛔ Facebook đang chặn đăng bài → dừng các nhóm còn lại. Nên nghỉ vài ngày.")
            break

        if index < len(group_urls):
            print(f"[WAIT] Doi {group_switch_wait_ms // 1000}s truoc khi sang nhom tiep theo.")
            page.wait_for_timeout(group_switch_wait_ms)

    summary = " · ".join(f"{RESULT_LABELS[k]}: {v}" for k, v in counts.items() if v)
    print(f"[BATCH] Ket thuc {len(group_urls)} nhom. {summary}")
    fb_login.note(BASE_DIR, f"■ Xong: {summary}")


def get_arg(name):
    """--name gia_tri -> gia_tri (khong co thi None)."""
    args = sys.argv[1:]
    if name in args and args.index(name) + 1 < len(args):
        return args[args.index(name) + 1]
    return None


def open_account_context(playwright, account_id, headless, wait_minutes=0):
    """Mo trinh duyet cua tai khoan. wait_minutes>0: dang ban thi xep hang doi."""
    deadline = time.time() + wait_minutes * 60
    while True:
        try:
            return fb_login.open_context(playwright, upstt_store.account_dir(account_id), headless=headless)
        except fb_login.ProfileBusy:
            if time.time() >= deadline:
                raise
            print("[QUEUE] Tai khoan dang dang noi dung khac -> doi 30s roi thu lai.")
            time.sleep(30)


def run_campaign(account, campaign):
    # Nhat ky cua noi dung nay ghi rieng: logs/<id>/nhat_ky.txt
    fb_login.use_task_log(BASE_DIR, campaign["id"])
    acc_dir = upstt_store.account_dir(account["id"])
    if not account_status.usable(acc_dir):
        st = account_status.read(acc_dir)
        print(f"[SKIP] {account['name']}: {account_status.LABELS[st['status']]} -> tam dung, "
              "can dang nhap lai trong giao dien (MO_TOOL.bat).")
        fb_login.note(BASE_DIR, f"⏸ Bỏ lượt đăng \"{campaign['name']}\" – {account['name']}: "
                                f"{account_status.LABELS[st['status']]}, cần đăng nhập lại.")
        return
    pause = fb_login.nick_pause(acc_dir)
    if pause:
        print(f"[SKIP] Nick dang tam nghi den {fb_login.pause_text(pause)} ({pause.get('reason', '')}).")
        fb_login.note(BASE_DIR, f"⏸ Bỏ lượt đăng '{campaign['name']}' – tài khoản đang tạm nghỉ đến "
                                f"{fb_login.pause_text(pause)} ({pause.get('reason', '')}).", once=True)
        return
    if 0 <= fb_login.disk_free_mb(BASE_DIR) < LOW_DISK_MB:
        fb_login.note(BASE_DIR, f"⚠️ Ổ đĩa sắp đầy (còn {fb_login.disk_free_mb(BASE_DIR)} MB) → Chrome dễ lỗi, "
                                "trang trắng. Hãy dọn ổ đĩa.", once=True)
    print(f"[START] {account['name']} > {campaign['name']}: dang vao {len(campaign['groups'])} nhom.")
    fb_login.note(BASE_DIR, f"▶ Đăng \"{campaign['name']}\" – {account['name']} ({len(campaign['groups'])} nhóm)")
    # Cung nick Facebook dang mo o tool/tai khoan khac (vd tool theo doi) -> doi xong roi moi dang.
    if not fb_login.hold_nick(acc_dir, wait_minutes=30):
        fb_login.note(BASE_DIR, "⚠️ Nick Facebook bận quá 30 phút (tool khác đang dùng) → vẫn đăng.")
    with sync_playwright() as playwright:
        # Cung tai khoan dang chay noi dung khac -> doi toi da 40 phut thay vi bo luot.
        context = open_account_context(playwright, account["id"], campaign["headless"], wait_minutes=40)
        page = fb_login.get_page(context)
        # Dong ho tu ngat: Facebook / Chrome dung -> khong treo toi 3 tieng (chan cac gio dang sau).
        limit = max(30, upstt_store.estimate_minutes(campaign) * 3)
        watchdog = threading.Timer(limit * 60, lambda: (
            print(f"\n[STOP] Luot dang qua {limit} phut (bat thuong) -> tu dung. Luot sau van chay dung gio."),
            fb_login.note(BASE_DIR, f"⏰ Lượt đăng chạy quá {limit} phút (bất thường) → tự dừng."),
            os._exit(2)))
        watchdog.daemon = True
        watchdog.start()
        try:
            try:
                fb_login.verify_and_record(page, acc_dir)
            except fb_login.NotLoggedIn:
                fb_login.note(BASE_DIR, f"⚠️ {account['name']}: Facebook đã đăng xuất tài khoản → tạm dừng, "
                                        "cần đăng nhập lại.")
                raise
            groups = campaign["groups"]
            # Nhom tai khoan nay moi XIN vao (cho duyet / can tra loi cau hoi) -> chua la thanh vien, bo qua.
            joins = upstt_store.join_state(account["id"])
            waiting = [g for g in groups if joins.get(fb_login.group_slug(g) or g, {}).get("status")
                       in upstt_store.JOIN_WAITING]
            if waiting:
                # Xem lai nhom dang xin: da duoc duyet -> xac minh ngay roi dang luon trong luot nay.
                approved = recheck_waiting(page, acc_dir, waiting, campaign=campaign)
                waiting = [g for g in waiting if g not in approved]
                groups = [g for g in groups if g not in waiting]
                if approved:
                    fb_login.note(BASE_DIR, f"   🎉 {len(approved)} nhóm vừa được duyệt → đã xác minh, đăng luôn lượt này.")
            if waiting:
                fb_login.note(BASE_DIR, f"   ⏳ Bỏ qua {len(waiting)} nhóm tài khoản đang xin vào (chờ duyệt / cần "
                                        "trả lời câu hỏi).")
                if not groups:
                    fb_login.note(BASE_DIR, "   ⏸ Không còn nhóm nào tài khoản đã vào → lượt này không đăng.")
                    return
            known = [fb_login.group_slug(g) for c in account["campaigns"] if c["enabled"] for g in c.get("groups", [])]
            due = fb_login.groups_due(acc_dir, known=known)
            if due:
                # Bai da gui >= 2 tieng: xem quan tri vien da duyet / tu choi chua (1 trang / nhom).
                print(f"[KET QUA] Kiem tra {len(due)} nhom da dang truoc do.")
                fb_login.check_results(page, acc_dir, due, note=lambda t: fb_login.note(BASE_DIR, t))
            total = len(groups)
            if fb_login.recovering(acc_dir) and len(groups) > 1:
                # Vua het nghi do Facebook gioi han -> ngay dau chi dang nua so nhom (doi nhom theo ngay).
                import random
                keep = set(random.Random(f"{datetime.now():%Y%m%d}{campaign['id']}").sample(
                    range(len(groups)), (len(groups) + 1) // 2))
                groups = [g for i, g in enumerate(groups) if i in keep]
                fb_login.note(BASE_DIR, f"   🐢 Tài khoản vừa hết tạm nghỉ → hôm nay chỉ đăng {len(groups)}/"
                                        f"{total} nhóm cho an toàn.")
            # Gioi han so nhom moi luot (bao ve nick: dang it moi luot, do bi coi la spam). Uu tien nhom lau
            # chua dang nhat -> xoay vong het danh sach qua cac luot.
            cap = int(campaign.get("max_groups_per_run") or 0)
            if cap and len(groups) > cap:
                sent = fb_login.load_results(acc_dir).get("sent", {})
                last = lambda g: max((e[0] for e in sent.get(fb_login.group_slug(g) or g, [])), default=0)
                groups = sorted(groups, key=last)[:cap]
                fb_login.note(BASE_DIR, f"   ⏳ Giới hạn an toàn: lượt này chỉ đăng {len(groups)}/"
                                        f"{total} nhóm (ưu tiên nhóm lâu chưa đăng).")
            has_media = bool(campaign.get("media_folder"))
            if has_media and not upstt_store.media_all(campaign):
                has_media = False
                fb_login.note(BASE_DIR, f"   ⚠️ Không thấy ảnh/video trong thư mục {campaign['media_folder']} → "
                                        "lượt này chỉ đăng chữ.")
            post_to_all_groups(
                page,
                groups,
                campaign["share_text"],
                upstt_store.LINK_LOAD_WAIT * 1000,
                upstt_store.POST_WAIT * 1000,
                upstt_store.GROUP_SWITCH_WAIT * 1000,
                acc_dir=acc_dir,
                media_pick=(lambda: upstt_store.media_pick(campaign)) if has_media else None,
            )
            # Trinh duyet dang mo san -> xem tin nhan giup lich 'Kiem tra tin nhan' (nick ban dang bai thi lich do
            # bo luot). Loi o day khong anh huong luot dang.
            try:
                fb_login.check_inbox_page(page, acc_dir, account["name"], note=lambda t: fb_login.note(BASE_DIR, t),
                                          piggyback=True)
            except Exception as error:
                print(f"[TIN NHAN] Loi xem tin nhan: {str(error).splitlines()[0][:100]}")
        finally:
            watchdog.cancel()
            context.close()


AUTO_CARE_MAX = 5   # moi tai khoan toi da 5 bai / luot tu cham


def care_new_approved(account, show_progress=False):
    """Sau moi lan cap nhat ket qua (bam tay hoac lich Tu cap nhat): binh luan noi dung 'Cham bai' cua muc
    (1 lan / bai) vao bai CUA MINH vua duoc duyet. Muc chua co noi dung cham -> bo qua. Binh luan chay qua
    --comment-posts (giu chot an toan san co: gian cach 30-70s, loi 2 bai lien thi dung, Facebook gioi han thi
    nick tam nghi). -> so bai da dua di cham."""
    import subprocess
    acc_dir = upstt_store.account_dir(account["id"])
    campaigns = [c for c in account["campaigns"] if c["enabled"] and (c.get("care_text") or "").strip()]
    if not campaigns or fb_login.nick_pause(acc_dir):
        return 0
    # Moi muc 1 noi dung cham; nhom trung giua cac muc -> muc dau tien.
    picks, taken = [], set()
    for c in campaigns:
        urls = [u for u in fb_login.care_candidates(acc_dir, c["groups"]) if u not in taken]
        urls = urls[:AUTO_CARE_MAX - sum(len(u) for _t, u in picks)]
        if urls:
            taken.update(urls)
            picks.append((c["care_text"].strip(), urls))
    if not picks:
        print(f"[CHAM] {account['name']}: khong co bai moi duoc duyet can cham.")
        return 0
    total = sum(len(u) for _t, u in picks)
    fb_login.note(BASE_DIR, f"💬 Tự chăm bài – {account['name']}: {total} bài mới được duyệt.")
    if show_progress:   # bam 'Cap nhat' tren giao dien: thanh tien do hien dang cham
        done = fb_login.read_progress(acc_dir).get("text", "")
        fb_login.write_progress(acc_dir, "care", f"Đang tự chăm {total} bài mới được duyệt…", 0, total)
    for text, urls in picks:
        try:
            subprocess.run([sys.executable, str(BASE_DIR / "main.py"), "--comment-posts", "--account",
                            account["id"], "--urls", "|".join(urls), "--text", text], cwd=BASE_DIR,
                           timeout=40 * 60)
        except subprocess.TimeoutExpired:
            fb_login.note(BASE_DIR, f"⏰ Tự chăm bài – {account['name']}: chạy quá 40 phút → dừng.")
            break
        if fb_login.nick_pause(acc_dir):   # vua bi Facebook gioi han -> dung nick nay
            break
    if show_progress:
        fb_login.write_progress(acc_dir, "done", f"{done} Đã tự chăm {total} bài mới được duyệt (xem cột Chăm bài)."
                                .strip(), total, total, done=True)
    return total


def auto_care(data):
    """Lich 'Tu cap nhat trang thai' (N gio/lan, bat o Cai dat): moi tai khoan cap nhat ket qua MOI nhom cua cac
    muc dang bat (ca dang bai lan theo doi) roi tu cham bai moi duoc duyet (care_new_approved)."""
    import tool_store
    full = tool_store.load()
    fb_login.use_task_log(BASE_DIR, "tu_cham_bai")
    if full.get("paused") or not full.get("auto_care"):
        print("[CAP NHAT] Tu cap nhat trang thai dang tat.")
        return
    allowed = tool_store.licensed_account_ids(full)
    every = {a["id"]: a for a in full["accounts"]}   # du ca muc theo doi (data chi co muc dang bai)
    for account in data["accounts"]:
        if account["id"] not in allowed:
            continue
        acc_dir = upstt_store.account_dir(account["id"])
        if not account_status.usable(acc_dir) or fb_login.nick_pause(acc_dir):
            print(f"[CAP NHAT] {account['name']}: chua dang nhap / dang tam nghi -> bo qua.")
            continue
        campaigns = [c for c in every.get(account["id"], account)["campaigns"] if c.get("enabled", True)]
        slugs = list(dict.fromkeys(fb_login.group_slug(g) for c in campaigns for g in c.get("groups", [])
                                   if fb_login.group_slug(g)))
        if not slugs:
            continue
        # Nick dang dang bai / quet o luot khac -> bo qua, luot sau lam (khong chen ngang).
        if not fb_login.hold_nick(acc_dir, wait_minutes=0):
            fb_login.note(BASE_DIR, f"⏭ {account['name']}: đang bận (tool khác dùng) → để lượt cập nhật sau.")
            continue
        try:
            with sync_playwright() as playwright:
                context = open_account_context(playwright, account["id"], headless=True)
                try:
                    page = fb_login.get_page(context)
                    fb_login.verify_and_record(page, acc_dir)
                    fb_login.note(BASE_DIR, f"🔄 Tự cập nhật – {account['name']}: {len(slugs)} nhóm "
                                            f"({len(campaigns)} mục đăng bài / theo dõi).")
                    fb_login.check_results(page, acc_dir, slugs, note=lambda t: fb_login.note(BASE_DIR, t))
                finally:
                    context.close()
        except (fb_login.NotLoggedIn, fb_login.ProfileBusy) as error:
            fb_login.note(BASE_DIR, f"⏭ {account['name']}: {str(error).splitlines()[0][:100]} → bỏ qua lượt này.")
            continue
        finally:
            fb_login.release_nick(acc_dir)
        care_new_approved(account)


def check_inbox(data, account_id=None):
    """Lich 'Kiem tra tin nhan' (hoac nut 'Kiem tra ngay' 1 tai khoan): doc danh sach tin nhan CHUA DOC
    (hop thu / tin nhan cho / spam) cua tung nick -> luu accounts/<id>/tin_nhan.json + bao Telegram tin moi.
    Chi doc danh sach, khong mo cuoc tro chuyen (khach khong thay 'da xem'), khong tra loi."""
    import tool_store
    full = tool_store.load()
    settings = tool_store.inbox_settings(full)
    fb_login.use_task_log(BASE_DIR, "tin_nhan")
    if not account_id and (full.get("paused") or not settings["enabled"]):
        print("[TIN NHAN] Kiem tra tin nhan dang tat.")
        return
    allowed = tool_store.licensed_account_ids(full)
    accounts = [a for a in data["accounts"] if a["id"] in allowed and (not account_id or a["id"] == account_id)]
    for account in accounts:
        acc_dir = upstt_store.account_dir(account["id"])
        if not account_status.usable(acc_dir):
            continue
        # Luot dang bai / quet nhom vua xem tin giup (cung trinh duyet) -> khong mo Chrome them lan nua.
        checked = fb_login.load_inbox(acc_dir)["checked"]
        if not account_id and time.time() - checked < settings["minutes"] * 60 * 0.6:
            print(f"[TIN NHAN] {account['name']}: vua xem luc {datetime.fromtimestamp(checked):%H:%M} -> bo qua.")
            continue
        # Lich: nick dang ban -> de luot sau. Nut bam tay: doi toi da 10 phut.
        if not fb_login.hold_nick(acc_dir, wait_minutes=10 if account_id else 0):
            print(f"[TIN NHAN] {account['name']}: dang ban -> bo qua luot nay.")
            continue
        try:
            with sync_playwright() as playwright:
                context = open_account_context(playwright, account["id"], headless=True,
                                               wait_minutes=10 if account_id else 0)
                try:
                    page = fb_login.get_page(context)
                    fb_login.verify_and_record(page, acc_dir)
                    # Nut bam tay -> doc du 3 muc; lich -> luot nhanh (Hop thu), du 3 muc moi 2 tieng / khi co tin.
                    fb_login.check_inbox_page(page, acc_dir, account["name"],
                                              note=lambda t: fb_login.note(BASE_DIR, t), force_full=bool(account_id))
                finally:
                    context.close()
        except (fb_login.NotLoggedIn, fb_login.ProfileBusy) as error:
            print(f"[TIN NHAN] {account['name']}: {str(error).splitlines()[0][:100]}")
            if account_id:
                raise
            continue
        finally:
            fb_login.release_nick(acc_dir)
        print(f"[TIN NHAN] {account['name']}: {len(fb_login.unseen_inbox(acc_dir))} cuoc tro chuyen co tin chua xem.")


def campaigns_due_now(data, window_minutes=10):
    """Lich cu goi --once khong kem --campaign: chay noi dung co gio trong 10 phut vua qua."""
    now = datetime.now()
    now_min = now.hour * 60 + now.minute
    due = []
    for account in data["accounts"]:
        for campaign in account["campaigns"]:
            if campaign["enabled"] and any(
                0 <= (now_min - upstt_store.to_minutes(t)) % 1440 <= window_minutes for t in campaign["times"]
            ):
                due.append((account, campaign))
    return due


def main():
    args = sys.argv[1:]
    data = upstt_store.load()

    # Cho setup.ps1: kiem tra cau hinh / liet ke tai khoan / lich can tao.
    # Cac lenh nay CHI in du lieu (setup.ps1 doc ket qua) -> khong in them dong nao khac.
    if "--validate" in args:
        errors = upstt_store.validate(data)
        for error in errors:
            print(error)
        sys.exit(2 if errors else 0)
    if "--accounts" in args:
        for account in data["accounts"]:
            if any(c["enabled"] for c in account["campaigns"]):
                print(f"{account['id']}\t{account['name']}")
        return
    if "--schedule-json" in args:
        print(json.dumps(upstt_store.schedule_entries(data), ensure_ascii=False))
        return

    disable_windows_quick_edit_mode()

    # Giao dien: 'Tim nhom' (A1), 'Mo cac nhom da chon' (phu 1), 'Mo cac bai da chon de vao cham' (B1).
    if "--find-groups" in args or "--open-groups" in args or "--open-tabs" in args:
        account = upstt_store.find_account(data, get_arg("--account") or "")
        if not account:
            raise ValueError("Thieu hoac sai --account.")
        acc_dir = upstt_store.account_dir(account["id"])
        with sync_playwright() as playwright:
            if "--open-tabs" in args:
                # Mo nhieu URL (bai viet) thanh tab, de nguoi dung TU doc / tra loi tung bai.
                urls = [u for u in (get_arg("--urls") or "").split("|") if u.strip()]
                if urls:
                    fb_login.open_group_tabs(playwright, acc_dir, urls)
                return
            if "--open-groups" in args:
                slugs = [s for s in (get_arg("--slugs") or "").split(",") if s]
                urls = [fb_login.content_url(s).replace("/my_pending_content", "") for s in slugs]
                if urls:
                    fb_login.open_group_tabs(playwright, acc_dir, urls)
                return
            keywords = [k.strip() for k in (get_arg("--keywords") or "").split("|") if k.strip()]
            min_members = int(get_arg("--min-members") or 0)
            max_members = int(get_arg("--max-members") or 0)
            min_activity = int(get_arg("--min-activity") or 0)   # toi thieu bai viet/ngay
            per_keyword = int(get_arg("--per-keyword") or 30)
            group_type = (get_arg("--group-type") or "all").lower()   # all | public | private
            sort_by = (get_arg("--sort") or "members").lower()        # members | activity | lively
            exclude = [w.strip().lower() for w in (get_arg("--exclude") or "").split("|") if w.strip()]
            out_file = acc_dir / "tim_nhom.json"
            fb_login.write_progress(acc_dir, "start", "Đang chuẩn bị tìm nhóm…", 0, len(keywords) or 1)
            try:
                context = open_account_context(playwright, account["id"], headless=True, wait_minutes=25)
                page = fb_login.get_page(context)
                try:
                    fb_login.verify_and_record(page, acc_dir)
                    seen, results = set(), []
                    for i, kw in enumerate(keywords):
                        fb_login.write_progress(acc_dir, "group", f"Đang tìm: {kw}", i, len(keywords))
                        taken = 0
                        for g in fb_login.find_groups(page, kw):
                            if g["slug"] in seen:
                                continue
                            if min_members and g["members_num"] < min_members:
                                continue
                            if max_members and g["members_num"] > max_members:
                                continue
                            if min_activity and g.get("activity_num", 0) < min_activity:
                                continue
                            if group_type == "public" and g["privacy"] != "công khai":
                                continue
                            if group_type == "private" and g["privacy"] != "riêng tư":
                                continue
                            if exclude and any(w in g["name"].lower() for w in exclude):
                                continue
                            # Do soi noi: so bai/ngay tren 1.000 thanh vien (nhom nho ma nhieu bai = tuong tac that).
                            g["lively"] = round(g.get("activity_num", 0) * 1000 / max(g["members_num"], 1), 2)
                            seen.add(g["slug"])
                            g["keyword"] = kw
                            results.append(g)
                            taken += 1
                            if taken >= per_keyword:
                                break
                    key = {"activity": "activity_num", "lively": "lively"}.get(sort_by, "members_num")
                    results.sort(key=lambda g: -g.get(key, 0))
                    out_file.write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
                    fb_login.write_progress(acc_dir, "done", f"Tìm được {len(results)} nhóm.", len(keywords),
                                            len(keywords), done=True)
                finally:
                    context.close()
            except Exception as error:
                fb_login.write_progress(acc_dir, "done", f"Tìm nhóm lỗi: {str(error).splitlines()[0][:120]}", 0, 1,
                                        done=True, ok=False)
                raise
        return

    # Giao dien (danh sach nhom cua kich ban): 'Xin vao' / 'Roi nhom' cho 1 tai khoan, lan luot tung nhom.
    #   Xin vao: chi bam 'Tham gia nhom'; nhom co cau hoi -> KHONG tu tra loi (danh dau de nguoi dung tu mo).
    #   Roi nhom: bam 'Da tham gia -> Roi nhom' (hoac huy yeu cau dang cho); la quan tri vien -> KHONG tu roi.
    # Gioi han --per-day nhom / tai khoan / ngay, cho giua 2 nhom; Facebook bao chan -> dung + nghi nick.
    if "--join-groups" in args or "--leave-groups" in args:
        joining = "--join-groups" in args
        account = upstt_store.find_account(data, get_arg("--account") or "")
        if not account:
            raise ValueError("Thieu hoac sai --account.")
        acc_dir = upstt_store.account_dir(account["id"])
        fb_login.use_task_log(BASE_DIR, account["id"])
        urls = [u.strip() for u in (get_arg("--urls") or "").split("|") if u.strip()]
        per_day = int(get_arg("--per-day") or (fb_login.JOIN_PER_DAY if joining else fb_login.LEAVE_PER_DAY))
        verb = "xin vào" if joining else "rời"
        fb_login.write_progress(acc_dir, "start", f"Đang chuẩn bị {verb} nhóm…", 0, len(urls) or 1)
        pause = fb_login.nick_pause(acc_dir)
        if pause:
            fb_login.write_progress(acc_dir, "done", f"Tài khoản đang tạm nghỉ đến {fb_login.pause_text(pause)} – "
                                    f"không {verb} nhóm.", 0, 1, done=True, ok=False)
            return
        fb_login.hold_nick(acc_dir, wait_minutes=30)
        labels = {"joined": "đã vào nhóm", "pending": "đã gửi yêu cầu, chờ duyệt",
                  "questions": "nhóm hỏi câu hỏi – tool chưa trả lời được, bạn mở nhóm trả lời",
                  "no_button": "không thấy nút trên Facebook",
                  "unknown": "đã bấm, chưa rõ kết quả", "left": "đã rời", "not_member": "không ở trong nhóm",
                  "admin": "bạn là quản trị viên – tool không tự rời", "skip": "đã xử lý trước đó",
                  "later": "để hôm sau (đủ giới hạn ngày)", "limited": "Facebook chặn"}
        count, done_today = {}, 0
        with sync_playwright() as playwright:
            try:
                context = open_account_context(playwright, account["id"], headless=True, wait_minutes=25)
                page = fb_login.get_page(context)
                try:
                    fb_login.verify_and_record(page, acc_dir)
                    state = upstt_store.join_state(account["id"])
                    fb_login.note(BASE_DIR, f"{'🙋' if joining else '🚪'} {account['name']}: {verb} {len(urls)} nhóm "
                                            f"(tối đa {per_day}/ngày)")
                    for i, url in enumerate(urls):
                        slug = fb_login.group_slug(url) or url
                        status_now = state.get(slug, {}).get("status")
                        # Dang cho duyet van mo lai (khong tinh luot xin): con cau hoi chua tra loi thi tra loi
                        if joining and status_now == "joined":
                            count["skip"] = count.get("skip", 0) + 1
                            continue
                        used = fb_login.joins_today(acc_dir) if joining else done_today
                        if used >= per_day:
                            fb_login.note(BASE_DIR, f"   ⏸ Đủ {per_day} nhóm hôm nay → dừng, hôm sau làm tiếp phần còn lại.")
                            count["later"] = len(urls) - i
                            break
                        fb_login.write_progress(acc_dir, "group", f"Đang {verb} nhóm {slug} ({i + 1}/{len(urls)})",
                                                i, len(urls))
                        answer, wave = join_options(account, url)
                        answer = get_arg("--answer") or answer
                        wave = wave if get_arg("--wave") is None else get_arg("--wave") == "1"
                        if joining:
                            status, clicked = fb_login.join_group(page, url, answer=answer)
                        else:
                            status, clicked = fb_login.leave_group(page, url)
                        if status == "limited":
                            info = fb_login.pause_nick(acc_dir, f"Facebook chặn {verb} nhóm")
                            fb_login.note(BASE_DIR, f"   ⛔ Facebook báo giới hạn → dừng, tài khoản nghỉ đến "
                                                    f"{fb_login.pause_text(info)}.")
                            count["limited"] = 1
                            break
                        if joining:
                            fb_login.set_join_status(acc_dir, url, status, requested=clicked)
                        elif status in ("left", "not_member"):
                            fb_login.forget_joined(acc_dir, url)
                        if clicked:
                            done_today += 1
                        count[status] = count.get(status, 0) + 1
                        extra = fb_login.LAST_JOIN_NOTE["text"] if joining else ""
                        fb_login.note(BASE_DIR, f"   {slug}: {labels.get(status, status)}" + (f" ({extra})" if extra else ""))
                        if joining and status == "joined":   # vao duoc ngay -> xac minh luon (dang duoc chua)
                            page.wait_for_timeout(3_000)
                            verify_one(page, acc_dir, url, answer, wave)
                        if clicked and i < len(urls) - 1:
                            page.wait_for_timeout((fb_login.JOIN_WAIT_SECONDS if joining
                                                   else fb_login.LEAVE_WAIT_SECONDS) * 1000)
                finally:
                    context.close()
            except Exception as error:
                fb_login.write_progress(acc_dir, "done", f"{verb.capitalize()} nhóm lỗi: "
                                        f"{str(error).splitlines()[0][:120]}", 0, 1, done=True, ok=False)
                raise
            finally:
                fb_login.release_nick(acc_dir)
        summary = ", ".join(f"{n} {labels.get(k, k)}" for k, n in count.items())
        fb_login.write_progress(acc_dir, "done", f"Xong: {summary or 'không có nhóm nào'}.", len(urls), len(urls),
                                done=True, ok="limited" not in count)
        print(f"[{'XIN' if joining else 'ROI'} NHOM] {account['name']}: {summary}")
        return

    # Giao dien: 'Cap nhat trang thai' -> doc nhom da tham gia (accounts/<id>/nhom_da_vao.json):
    # nhom dang xin (cho duyet / cau hoi) ma da vao -> 'joined'; doc HET ma nhom 'joined' khong con -> da roi.
    if "--joined-groups" in args:
        account = upstt_store.find_account(data, get_arg("--account") or "")
        if not account:
            raise ValueError("Thieu hoac sai --account.")
        acc_dir = upstt_store.account_dir(account["id"])
        fb_login.use_task_log(BASE_DIR, account["id"])
        fb_login.write_progress(acc_dir, "start", "Đang chuẩn bị đọc nhóm đã tham gia…", 0, 1)
        with sync_playwright() as playwright:
            try:
                context = open_account_context(playwright, account["id"], headless=True, wait_minutes=25)
                page = fb_login.get_page(context)
                try:
                    fb_login.verify_and_record(page, acc_dir)
                    fb_login.write_progress(acc_dir, "group", "Đang đọc danh sách nhóm đã tham gia…", 0, 1)
                    groups, complete = fb_login.read_joined_groups(page, with_complete=True)
                    cache = fb_login.save_joined_groups(acc_dir, groups)
                    approved, gone = fb_login.mark_joined(acc_dir, cache["groups"], complete=complete)
                    text = (f"Đang ở {len(cache['groups'])} nhóm · {approved} nhóm mới được duyệt"
                            + (f" · {gone} nhóm đã rời / bị mời ra" if gone else ""))
                    # Da vao la phai xac minh: moi nhom tai khoan nay se dang (moi muc cua no + --urls) da vao ma
                    # chua xac minh (vd vua duoc duyet) -> xac minh ngay.
                    state = fb_login.load_join_state(acc_dir)
                    urls = [u.strip() for u in (get_arg("--urls") or "").split("|") if u.strip()]
                    urls += [g for c in account.get("campaigns", []) for g in c.get("groups", [])]
                    todo, seen = [], set()
                    for u in urls:
                        slug = fb_login.group_slug(u) or u
                        g = state.get(slug, {})
                        if slug not in seen and g.get("status") == "joined" and not g.get("verified"):
                            todo.append(u)
                        seen.add(slug)
                    ready = 0
                    for i, url in enumerate(todo):
                        fb_login.write_progress(acc_dir, "group", f"Đang xác minh nhóm {i + 1}/{len(todo)}…", i,
                                                len(todo))
                        ready += verify_one(page, acc_dir, url, *join_options(account, url)) == "ready"
                        page.wait_for_timeout(VERIFY_WAIT_SECONDS * 1000)
                    if todo:
                        text += f" · xác minh {ready}/{len(todo)} nhóm sẵn sàng đăng"
                    print(f"[NHOM] {account['name']}: {text}")
                    fb_login.note(BASE_DIR, f"🔄 {account['name']}: {text}")
                    fb_login.write_progress(acc_dir, "done", text + ".", 1, 1, done=True)
                finally:
                    context.close()
            except Exception as error:
                fb_login.write_progress(acc_dir, "done", f"Đọc nhóm lỗi: {str(error).splitlines()[0][:120]}", 0, 1,
                                        done=True, ok=False)
                raise
        return

    # Lich 'Tu cham bai' (moi 2 tieng, bat/tat o dau giao dien).
    if "--auto-care" in args:
        auto_care(data)
        return

    # Lich 'Kiem tra tin nhan' / nut 'Kiem tra tin nhan ngay' (--account a1).
    if "--check-inbox" in args:
        check_inbox(data, get_arg("--account"))
        return

    # Giao dien: nut 'Kiem tra ngay' (tab Ket qua) / nut 'Mo' trang Noi dung cua ban cua 1 nhom.
    if "--check-results" in args or "--open-url" in args:
        account = upstt_store.find_account(data, get_arg("--account") or "")
        if not account:
            raise ValueError("Thieu hoac sai --account.")
        acc_dir = upstt_store.account_dir(account["id"])
        with sync_playwright() as playwright:
            if "--open-url" in args:
                fb_login.open_url_window(playwright, acc_dir, get_arg("--open-url"))
                return
            slugs = [s for s in (get_arg("--groups") or "").split(",") if s]
            # Ghi nhat ky vao noi dung dang xem (tab Chi tiet hien duoc).
            fb_login.use_task_log(BASE_DIR, get_arg("--campaign") or "ket_qua")
            fb_login.check_results_cli(
                acc_dir, slugs,
                lambda: open_account_context(playwright, account["id"], headless=True, wait_minutes=25),
                note=lambda t: fb_login.note(BASE_DIR, t))
        # Cap nhat bang tay xong -> tu cham bai moi duoc duyet (muc co noi dung 'Cham bai').
        fb_login.release_nick(acc_dir)
        campaign = get_arg("--campaign")
        if campaign:
            account = dict(account, campaigns=[c for c in account["campaigns"] if c["id"] == campaign])
        care_new_approved(account, show_progress=True)
        return

    # --login / --check / --logout: theo tung tai khoan (--account a1).
    if "--login" in args or "--check" in args or "--logout" in args:
        account = upstt_store.find_account(data, get_arg("--account") or "")
        if not account:
            raise ValueError("Thieu hoac sai --account.")
        acc_dir = upstt_store.account_dir(account["id"])
        fb_login.start_account_log(acc_dir, args)
        if "--check" in args and "--force" in args:
            fb_login.acquire(acc_dir, force=True)   # nguoi dung chon dung luot dang chay de kiem tra ngay
        print(f"[ACCOUNT] {account['name']}")
        with sync_playwright() as playwright:
            if "--logout" in args:
                fb_login.logout(playwright, acc_dir, force="--force" in args)
                return
            if "--login" in args:
                fb_login.interactive_login(playwright, acc_dir, force="--force" in args)
            context = open_account_context(playwright, account["id"], headless=True)
            try:
                fb_login.verify_and_record(fb_login.get_page(context), acc_dir, fetch_name=True)
            finally:
                context.close()
        return

    # --once --campaign c1: Task Scheduler goi dung gio cua tung nhom noi dung.
    if "--once" in args:
        campaign_id = get_arg("--campaign")
        if campaign_id:
            account, campaign = upstt_store.find_campaign(data, campaign_id)
            if not campaign:
                raise ValueError(f"Khong tim thay nhom noi dung {campaign_id} (da bi xoa?).")
            now = "--now" in args   # nguoi dung bam 'Dang ngay' -> chay du dang tat / ngoai gio
            if not campaign["enabled"] and not now:
                print(f"[SKIP] '{campaign['name']}' dang tat.")
                return
            only = get_arg("--only")   # 'Dang ngay' vao cac nhom da tick (ngan cach bang |)
            if only:
                keep = {u.strip() for u in only.split("|") if u.strip()}
                campaign = dict(campaign, groups=[g for g in campaign["groups"] if g in keep])
                if not campaign["groups"]:
                    print("[SKIP] Khong co nhom nao (da tick) de dang.")
                    return
            run_campaign(account, campaign)
        else:
            due = campaigns_due_now(data)
            if not due:
                print("[SKIP] Khong co noi dung nao den gio.")
            for account, campaign in due:
                run_campaign(account, campaign)
        return

    print("Cach dung: fb_upstt.py --once --campaign c1 | --login --account a1 | --check --account a1")


def redirect_output_to_log():
    """pythonw (Task Scheduler) khong co cua so -> ghi ra log.txt de xem loi."""
    if sys.stdout is not None:
        return
    # Luot dang cua 1 noi dung (--once --campaign c1) -> log RIENG: logs/c1/log.txt.
    # Lenh khac (setup.ps1 goi --validate, --schedule-json...) -> log.txt chung.
    args = sys.argv[1:]
    log_file = BASE_DIR / "log.txt"
    if "--once" in args and "--campaign" in args and args.index("--campaign") + 1 < len(args):
        try:
            log_file = fb_login.task_log_dir(BASE_DIR, args[args.index("--campaign") + 1]) / "log.txt"
        except OSError:
            pass
    # Log day 1MB -> doi thanh log.1.txt (cu hon: log.2.txt), giu 3 file.
    fb_login.rotate_log(log_file, 1_000_000, keep=3)
    stream = fb_login.open_log_stream(log_file)   # o day / file khoa -> bo qua nhat ky, tool van chay
    sys.stdout = sys.stderr = stream
    print(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} | {' '.join(sys.argv[1:])} =====")


if __name__ == "__main__":
    redirect_output_to_log()
    try:
        main()
    except fb_login.NotLoggedIn as error:
        print(f"[LOGIN] LOI: {error}")
        sys.exit(fb_login.EXIT_NOT_LOGGED_IN)
    except fb_login.ProfileBusy as error:
        print(f"[LOGIN] {error}")
        sys.exit(fb_login.EXIT_PROFILE_BUSY)
    except KeyboardInterrupt:
        print("\n[STOP] Da dung theo yeu cau nguoi dung.")
    except Exception as error:
        print(f"[FATAL] {error}")
        sys.exit(1)