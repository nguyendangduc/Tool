# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
"""Trang thai dang nhap cua tung tai khoan (accounts/<id>/status.json).

File nay GIONG HET NHAU o cac tool.
- ok          : da dang nhap, lan kiem tra gan nhat binh thuong -> cac muc ben duoi chay.
- expired     : dang dung thi Facebook da dang xuat / phien het han -> tam dung, can dang nhap lai.
- logged_out  : chua dang nhap hoac da bam Dang xuat -> tam dung, can dang nhap.
- unknown     : co du lieu dang nhap nhung chua kiem tra lan nao -> van cho chay (lan chay se tu kiem tra).

Ghi boi: --login / --check / --logout / lan chay theo lich. Doc boi: giao dien va lich (schedule_entries).
"""
import json
import time
from pathlib import Path

OK = "ok"
EXPIRED = "expired"
LOGGED_OUT = "logged_out"
UNKNOWN = "unknown"

LABELS = {
    OK: "Đang hoạt động",
    EXPIRED: "Hết hạn / bị Facebook đăng xuất",
    LOGGED_OUT: "Chưa đăng nhập",
    UNKNOWN: "Chưa kiểm tra",
}


def _file(account_dir):
    return Path(account_dir) / "status.json"


def read(account_dir):
    """{'status', 'time', 'message'}. Khong co file: co du lieu dang nhap -> unknown, khong -> logged_out."""
    path = _file(account_dir)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("status") in LABELS:
                return data
        except Exception:
            pass
    has_profile = (Path(account_dir) / "browser_profile").exists()
    return {"status": UNKNOWN if has_profile else LOGGED_OUT, "time": "", "message": ""}


def write(account_dir, status, message=""):
    Path(account_dir).mkdir(parents=True, exist_ok=True)
    data = {"status": status, "time": time.strftime("%Y-%m-%d %H:%M"), "message": message}
    tmp = _file(account_dir).with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_file(account_dir))
    return data


PROFILE_FILE = "fb_profile.json"


def read_profile(account_dir):
    """{'name', 'uid', 'time'} cua tai khoan Facebook dang dang nhap (rong neu chua biet)."""
    try:
        return json.loads((Path(account_dir) / PROFILE_FILE).read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_profile(account_dir, name, uid=""):
    Path(account_dir).mkdir(parents=True, exist_ok=True)
    data = {"name": name, "uid": uid, "time": time.strftime("%Y-%m-%d %H:%M")}
    (Path(account_dir) / PROFILE_FILE).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def clear_profile(account_dir):
    try:
        (Path(account_dir) / PROFILE_FILE).unlink()
    except OSError:
        pass


def usable(account_dir):
    """Tai khoan duoc phep chay (tao lich / chay theo lich)."""
    return read(account_dir)["status"] in (OK, UNKNOWN)
