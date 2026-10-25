# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
"""Chuyen du lieu tu 2 tool cu (FacebookUpStt + FacebookMonitor) sang tool gop. CHI CHEP, khong sua tool cu.

  python chuyen_du_lieu.py <thu muc tool dang bai> <thu muc tool theo doi> [--force]

- Tai khoan tool dang bai giu nguyen id; noi dung dang bai giu nguyen id (lich, nhat ky logs/cN giu nguyen).
- Tai khoan tool theo doi: CUNG uid + CUNG ten hien thi (cung 1 danh tinh: ca nhan / Page) voi 1 tai khoan
  tool dang bai -> gop vao tai khoan do; khac -> them tai khoan moi. Tai khoan trong (khong muc, chua dang nhap) -> bo.
- Nhom theo doi doi id sang mN (tranh trung cN cua noi dung dang bai).
- Gop ket_qua.json (bai / binh luan da gui, trang thai duyet). Trinh duyet: lay ban dang nhap gan nhat.
Truoc khi chay: tat lich 2 tool cu va dong moi cua so Chrome cua tool (tool kiem tra va bao loi neu dang chay).
"""
import json
import msvcrt
import shutil
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent
sys.path.insert(0, str(TARGET))

PROFILE_IGNORE = shutil.ignore_patterns("Cache", "Code Cache", "GPUCache", "GrShaderCache", "ShaderCache",
                                        "DawnCache", "DawnGraphiteCache", "DawnWebGPUCache", "Singleton*", "lockfile")
SKIP_FILES = {"browser_profile.lock", "browser_profile.pid", "kiem_tra_tien_do.json"}
ACCOUNT_KEYS = ("run_every_minutes", "max_run_minutes", "headless")


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def profile_of(acc_dir):
    p = read_json(acc_dir / "fb_profile.json", {}) or {}
    return p.get("uid", ""), p.get("name", "")


def login_rank(acc_dir):
    """De chon trinh duyet: (dang dang nhap?, thoi diem kiem tra gan nhat)."""
    st = read_json(acc_dir / "status.json", {}) or {}
    return (st.get("status") == "ok", st.get("time", ""))


def busy(acc_dir):
    """Co tien trinh tool dang giu tai khoan nay (khoa browser_profile.lock)?"""
    lock = acc_dir / "browser_profile.lock"
    if not lock.exists():
        return False
    try:
        with open(lock, "a+") as f:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        return False
    except OSError:
        return True


def copy_account(src, dst):
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name in SKIP_FILES:
            continue
        if item.is_dir():
            shutil.copytree(item, dst / item.name, ignore=PROFILE_IGNORE if item.name == "browser_profile" else None,
                            dirs_exist_ok=True)
        else:
            shutil.copy2(item, dst / item.name)


def merge_results(a, b):
    """Gop 2 ket_qua.json (fb_login): nhom -> lay ban kiem tra moi hon; lan gui -> gop, bo trung."""
    a, b = a or {}, b or {}
    groups = dict(a.get("groups", {}))
    for slug, g in b.get("groups", {}).items():
        if g.get("checked", 0) > groups.get(slug, {}).get("checked", 0):
            groups[slug] = g
    sent = {}
    for src in (a.get("sent", {}), b.get("sent", {})):
        for slug, entries in src.items():
            seen = {json.dumps(e, ensure_ascii=False) for e in sent.get(slug, [])}
            sent.setdefault(slug, []).extend(e for e in entries if json.dumps(e, ensure_ascii=False) not in seen)
    for slug in sent:
        sent[slug].sort(key=lambda e: e[0])
    notes = list(dict.fromkeys(a.get("notes_seen", []) + b.get("notes_seen", [])))[-200:]
    return {"groups": groups, "sent": sent, "alias": {**a.get("alias", {}), **b.get("alias", {})}, "notes_seen": notes}


def copy_tree_into(src, dst):
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    if len(args) != 2:
        print(__doc__)
        sys.exit(1)
    post_dir, mon_dir = Path(args[0]).resolve(), Path(args[1]).resolve()
    if (TARGET / "config.json").exists() and not force:
        sys.exit("Tool gop da co config.json -> khong chuyen de tranh ghi de. Them --force neu chac chan.")

    post_cfg = read_json(post_dir / "config.json")
    mon_cfg = read_json(mon_dir / "config.json")
    if not post_cfg or not mon_cfg:
        sys.exit("Khong doc duoc config.json cua tool cu.")

    running = [str(d) for root in (post_dir, mon_dir) for d in (root / "accounts").glob("*") if d.is_dir() and busy(d)]
    if running:
        sys.exit("Tool cu dang chay o: " + ", ".join(running) + " -> tat lich / doi chay xong roi chay lai.")

    import tool_store

    accounts, report = [], []
    used = {a["id"] for a in post_cfg["accounts"]}

    # ---- tai khoan + noi dung dang bai: giu nguyen id
    for a in post_cfg["accounts"]:
        acc = {k: v for k, v in a.items() if k != "campaigns"}
        acc.update({k: v for k, v in tool_store.ACCOUNT_DEFAULTS.items() if k not in acc})
        acc["campaigns"] = [dict(c, kind="post") for c in a.get("campaigns", [])]
        accounts.append(acc)
        copy_account(post_dir / "accounts" / a["id"], TARGET / "accounts" / a["id"])
        report.append(f"Tài khoản {a['id']} '{a['name']}': {len(acc['campaigns'])} nội dung đăng")
    copy_tree_into(post_dir / "logs", TARGET / "logs")
    copy_tree_into(post_dir / "anh_loi", TARGET / "anh_loi")

    # ---- tai khoan + nhom theo doi
    used_campaign = {c["id"] for a in accounts for c in a["campaigns"]}
    n = 0
    for a in mon_cfg["accounts"]:
        src = mon_dir / "accounts" / a["id"]
        uid, name = profile_of(src)
        campaigns = a.get("campaigns", [])
        if not campaigns and not uid:
            report.append(f"Bỏ tài khoản theo dõi {a['id']} '{a['name']}' (không có nhóm theo dõi, chưa đăng nhập)")
            continue
        match = next((acc for acc in accounts
                      if uid and profile_of(TARGET / "accounts" / acc["id"]) == (uid, name)), None)
        if match:
            dst = TARGET / "accounts" / match["id"]
            for f in ("commented_ids.txt", "binh_luan_loi.json"):
                if (src / f).exists():
                    shutil.copy2(src / f, dst / f)
            write_json(dst / "ket_qua.json", merge_results(read_json(dst / "ket_qua.json"), read_json(src / "ket_qua.json")))
            if login_rank(src) > login_rank(dst) and (src / "browser_profile").exists():
                shutil.rmtree(dst / "browser_profile", ignore_errors=True)
                shutil.copytree(src / "browser_profile", dst / "browser_profile", ignore=PROFILE_IGNORE)
                for f in ("status.json", "fb_profile.json"):
                    if (src / f).exists():
                        shutil.copy2(src / f, dst / f)
                picked = "trình duyệt của tool theo dõi"
            else:
                picked = "trình duyệt của tool đăng bài"
            acc = match
            report.append(f"Gộp tài khoản theo dõi {a['id']} vào {acc['id']} '{acc['name']}' ({name}) – dùng {picked}")
        else:
            new = a["id"] if a["id"] not in used else next(f"a{i}" for i in range(1, 999) if f"a{i}" not in used)
            acc = {k: v for k, v in a.items() if k != "campaigns"}
            acc["id"], acc["campaigns"] = new, []
            accounts.append(acc)
            copy_account(src, TARGET / "accounts" / new)
            report.append(f"Thêm tài khoản theo dõi {a['id']} thành {new} '{acc['name']}'")
        used.add(acc["id"])
        for key in ACCOUNT_KEYS:
            if key in a:
                acc[key] = a[key]
        copy_tree_into(mon_dir / "logs" / a["id"], TARGET / "logs" / acc["id"])
        for c in campaigns:
            n += 1
            while f"m{n}" in used_campaign:
                n += 1
            new_c = dict(c, id=f"m{n}", kind="monitor")
            used_campaign.add(new_c["id"])
            acc["campaigns"].append(new_c)
            copy_tree_into(mon_dir / "campaigns" / c["id"], TARGET / "campaigns" / new_c["id"])
            report.append(f"   🔎 Nhóm theo dõi '{c['name']}': {c['id']} → {new_c['id']} (tài khoản {acc['id']})")
    copy_tree_into(mon_dir / "anh_loi", TARGET / "anh_loi")

    rules = dict(mon_cfg.get("rules") or {})
    rules.update(post_cfg.get("rules") or {})
    data = {"accounts": accounts, "rules": rules,
            "paused": bool(post_cfg.get("paused")) and bool(mon_cfg.get("paused"))}
    tool_store.save(data)
    data = tool_store.load()      # dien mac dinh + kiem tra doc lai duoc
    tool_store.save(data)

    print("CHUYEN DU LIEU XONG:")
    for line in report:
        print(" - " + line)
    errors = tool_store.validate(data)
    if errors:
        print("\nCan xem lai trong giao dien:")
        for e in errors:
            print(" ! " + e)


if __name__ == "__main__":
    main()
