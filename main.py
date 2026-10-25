# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
"""Cua vao duy nhat cua tool gop (Task Scheduler, setup.ps1, giao dien deu goi file nay).

  --validate | --accounts | --schedule-json   : cho setup.ps1 (doc tool_store, chi in du lieu)
  --once --campaign c1                         : dang bai           -> fb_upstt.py
  --once --account a1                          : quet nhom theo doi -> fb_monitor_v4.py
  --check-results ... [--campaign mN]          : muc theo doi -> fb_monitor_v4.py, con lai -> fb_upstt.py
  --login | --check | --logout | --open-url    : fb_upstt.py (dung chung fb_login)

Script duoc chay nguyen ven nhu khi goi truc tiep (ghi log, ma thoat giu nguyen).
"""
import json
import runpy
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def script(name):
    """Duong dan file .py, hoac .pyc neu ban gui khach da bo .py (xem dong_goi.ps1)."""
    py = BASE_DIR / f"{name}.py"
    return py if py.exists() else BASE_DIR / f"{name}.pyc"


POST_SCRIPT = script("fb_upstt")
MONITOR_SCRIPT = script("fb_monitor_v4")


def get_arg(args, name):
    if name in args and args.index(name) + 1 < len(args):
        return args[args.index(name) + 1]
    return None


def setup_command(args):
    """Lenh cho setup.ps1: True neu da xu ly."""
    if not {"--validate", "--accounts", "--schedule-json"} & set(args):
        return False
    sys.path.insert(0, str(BASE_DIR))
    import tool_store
    data = tool_store.load()
    if "--validate" in args:
        errors = tool_store.validate(data)
        for error in errors:
            print(error)
        sys.exit(2 if errors else 0)
    if "--accounts" in args:
        for account in tool_store.accounts_with_enabled(data):
            print(f"{account['id']}\t{account['name']}")
    if "--schedule-json" in args:
        print(json.dumps(tool_store.schedule_entries(data), ensure_ascii=False))
    return True


def pick_script(args):
    if "--comment-posts" in args or "--verify-care" in args:
        return MONITOR_SCRIPT   # ham post_comment_on_facebook nam o fb_monitor_v4
    if "--once" in args:
        return POST_SCRIPT if "--campaign" in args else MONITOR_SCRIPT
    if "--check-results" in args and get_arg(args, "--campaign"):
        sys.path.insert(0, str(BASE_DIR))
        import tool_store
        _account, campaign = tool_store.find_campaign(tool_store.load(), get_arg(args, "--campaign"))
        if campaign and tool_store.kind_of(campaign) == tool_store.MONITOR:
            return MONITOR_SCRIPT
    return POST_SCRIPT


EXIT_NO_LICENSE = 5


def license_blocks(args):
    """Luot chay theo lich (--once): kiem ban quyen + tai khoan co nam trong so tai khoan duoc phep. Chan -> True."""
    if "--once" not in args:
        return False      # dang nhap / kiem tra / xem ket qua: van cho lam de khach cai dat truoc khi kich hoat
    sys.path.insert(0, str(BASE_DIR))
    import ban_quyen
    import fb_login
    import tool_store
    data = tool_store.load()
    campaign_id, account_id = get_arg(args, "--campaign"), get_arg(args, "--account")
    if campaign_id:
        account = tool_store.find_campaign(data, campaign_id)[0]
        account_id = account["id"] if account else None
    st = ban_quyen.trang_thai()
    if st["ok"] and account_id in tool_store.licensed_account_ids(data, st):
        return False
    reason = (st["ly_do"] if not st["ok"] else
              f"bản quyền chỉ cho {st['so_tai_khoan']} tài khoản đầu tiên – tài khoản này nằm ngoài giới hạn")
    fb_login.use_task_log(BASE_DIR, campaign_id or account_id or "ban_quyen")
    fb_login.note(BASE_DIR, f"⛔ Không chạy: {reason} Mở tool → 'ℹ Bản quyền' để kích hoạt / gia hạn.", once=True)
    print(f"[BAN QUYEN] {reason}")
    return True


def main():
    args = sys.argv[1:]
    if setup_command(args):
        return
    if license_blocks(args):
        sys.exit(EXIT_NO_LICENSE)
    script = pick_script(args)
    sys.argv = [str(script)] + args
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
