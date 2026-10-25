# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
"""Ban quyen offline: key do nguoi ban ky (Ed25519), gan voi ma may, co han dung va so tai khoan toi da.

- ma_may(): ma cua may nay (khach gui cho nguoi ban de lay key).
- trang_thai(): {'ok', 'ly_do', 'het_han', 'so_tai_khoan', 'con_ngay', 'khach'} doc tu file license.key.
- kich_hoat(key): kiem tra roi luu key. Key sai / sai may / het han -> tra ve ly do, khong luu.
Key chi tao duoc bang khoa bi mat cua nguoi ban (tao_key.py), tool chi chua khoa cong khai de kiem tra.
"""
import base64
import ctypes
import hashlib
import json
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
KEY_FILE = BASE_DIR / "license.key"
PUBLIC_KEY = "c3QJyCP-gpUvbirWmYORZVh_JcWnKwdpu6cbMP8xv2Q"
WARN_DAYS = 3


def _b64d(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _machine_guid():
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                             winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        return str(winreg.QueryValueEx(key, "MachineGuid")[0])
    except OSError:
        return ""


def _volume_serial():
    serial = ctypes.c_ulong(0)
    try:
        ctypes.windll.kernel32.GetVolumeInformationW("C:\\", None, 0, ctypes.byref(serial), None, None, None, 0)
    except Exception:
        return ""
    return f"{serial.value:08X}"


def ma_may():
    """BBC-XXXX-XXXX-XXXX-XXXX: bam tu MachineGuid cua Windows + serial o C (cai lai Windows thi doi ma)."""
    digest = hashlib.sha256(f"bbc|{_machine_guid()}|{_volume_serial()}".encode()).hexdigest()[:16].upper()
    return "BBC-" + "-".join(digest[i:i + 4] for i in range(0, 16, 4))


def doc_key(key):
    """Kiem tra 1 key -> (payload, None) hoac (None, ly do)."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    key = (key or "").strip().replace("\n", "").replace(" ", "")
    if key.count(".") != 1:
        return None, "Key sai định dạng (copy thiếu / thừa ký tự)."
    body_b64, sig_b64 = key.split(".")
    try:
        body, sig = _b64d(body_b64), _b64d(sig_b64)
        Ed25519PublicKey.from_public_bytes(_b64d(PUBLIC_KEY)).verify(sig, body)
        payload = json.loads(body.decode("utf-8"))
    except (InvalidSignature, ValueError):
        return None, "Key không hợp lệ (không phải key do BánhBaoChiên AutoTool cấp, hoặc đã bị sửa)."
    if payload.get("m") != ma_may():
        return None, f"Key này cấp cho máy khác ({payload.get('m')}). Mã máy này: {ma_may()}."
    try:
        expires = date.fromisoformat(payload["exp"])
    except (KeyError, ValueError):
        return None, "Key không hợp lệ (thiếu hạn dùng)."
    if expires < date.today():
        return None, f"Key đã hết hạn ngày {expires:%d/%m/%Y} – liên hệ để gia hạn."
    return payload, None


def trang_thai():
    if not KEY_FILE.exists():
        return {"ok": False, "ly_do": "Chưa kích hoạt bản quyền.", "so_tai_khoan": 0}
    try:
        payload, error = doc_key(KEY_FILE.read_text(encoding="ascii"))
    except Exception as e:
        payload, error = None, f"Không đọc được file bản quyền ({e})."
    if error:
        return {"ok": False, "ly_do": error, "so_tai_khoan": 0}
    expires = date.fromisoformat(payload["exp"])
    days = (expires - date.today()).days
    return {"ok": True, "ly_do": "", "het_han": expires, "con_ngay": days, "so_tai_khoan": int(payload.get("n", 1)),
            "khach": payload.get("c", "")}


def kich_hoat(key):
    """Luu key neu hop le. -> (True, trang thai) | (False, ly do)."""
    payload, error = doc_key(key)
    if error:
        return False, error
    KEY_FILE.write_text(key.strip().replace("\n", "").replace(" ", ""), encoding="ascii")
    return True, trang_thai()


def mo_ta(st=None):
    """1 dong cho giao dien / nhat ky."""
    st = st or trang_thai()
    if not st["ok"]:
        return "⛔ " + st["ly_do"]
    warn = f"  ⚠ còn {st['con_ngay']} ngày" if st["con_ngay"] <= WARN_DAYS else ""
    return f"✅ Bản quyền đến {st['het_han']:%d/%m/%Y} · tối đa {st['so_tai_khoan']} tài khoản{warn}"
