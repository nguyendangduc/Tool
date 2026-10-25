# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
"""Du lieu cua tool gop: Tai khoan -> Muc dang bai ("post") + Muc theo doi ("monitor") trong 1 config.json.

Dung cho giao dien (tool_gui.py), main.py (--validate / --accounts / --schedule-json cho setup.ps1).
Hai script chay van doc qua store rieng (chi thay muc cua minh):
  fb_upstt.py      -> upstt_store.load()   (muc "post",    lich theo gio, moi muc 1 lich)
  fb_monitor_v4.py -> monitor_store.load() (muc "monitor", lich lap lai, moi tai khoan 1 lich)

Cau truc config.json:
{
  "accounts": [
    {"id": "a1", "name": "...", "run_every_minutes": 40, "max_run_minutes": 20, "headless": true,
     "campaigns": [{"id": "c1", "kind": "post", ...}, {"id": "m1", "kind": "monitor", ...}]}
  ],
  "rules": {...}, "paused": false
}
"""
import json
import shutil

import monitor_store
import upstt_store

BASE_DIR = upstt_store.BASE_DIR
CONFIG_JSON = BASE_DIR / "config.json"
ACCOUNTS_DIR = BASE_DIR / "accounts"
CAMPAIGNS_DIR = monitor_store.CAMPAIGNS_DIR
LOGS_DIR = BASE_DIR / "logs"

POST, MONITOR = upstt_store.KIND, monitor_store.KIND
STORES = {POST: upstt_store, MONITOR: monitor_store}
ID_PREFIX = {POST: "c", MONITOR: "m"}
ACCOUNT_DEFAULTS = monitor_store.ACCOUNT_DEFAULTS


def kind_of(campaign):
    return campaign.get("kind", POST)


def store_of(campaign):
    return STORES[kind_of(campaign)]


def defaults_of(kind):
    return STORES[kind].CAMPAIGN_DEFAULTS


def _fill(item, defaults):
    for key, value in defaults.items():
        item.setdefault(key, list(value) if isinstance(value, list) else value)


# ------------------------------------------------------------------ doc / ghi
def load():
    if CONFIG_JSON.exists():
        data = json.loads(CONFIG_JSON.read_text(encoding="utf-8"))
    else:
        data = {"accounts": []}
    for account in data.setdefault("accounts", []):
        _fill(account, ACCOUNT_DEFAULTS)
        # Task 003: [{"id": "self"|<id Page>, "name", "kind": "self"|"page", "missing"?: bool}].
        # [] (config cu / chua bam 'Doc danh sach Page') = chi co Ca nhan, xem account_identities().
        account.setdefault("identities", [])
        for campaign in account.setdefault("campaigns", []):
            campaign.setdefault("kind", POST)
            _fill(campaign, defaults_of(campaign["kind"]))
            if campaign["kind"] == MONITOR:
                monitor_store.merge_ad_lists(campaign)
        account.setdefault("group", "")
    data.setdefault("account_groups", [])
    global migrated
    migrated = "scenarios" not in data
    if migrated:
        migrate_to_scenarios(data)
    for s in data["scenarios"]:
        s.setdefault("enabled", True)
        s.setdefault("accounts", [])
        s.setdefault("members", {})
        s.setdefault("gap_minutes", DEFAULT_GAP)
        s.setdefault("member_times", {})   # {id tai khoan: [gio rieng]} - de trong = gio chung + gian cach
        s.setdefault("post_as", {})        # task 003: {id tai khoan: id danh tinh} - thieu = "self" (Ca nhan)
        if s["kind"] == MONITOR and "scan_minutes" not in s.setdefault("settings", {}):
            # Chu ky quet chuyen tu tai khoan sang kich ban (23/10/2026): lay chu ky dang dat o tai khoan chay no.
            olds = [a.get("run_every_minutes") for a in data["accounts"] if a["id"] in s["accounts"]]
            olds = [int(x) for x in olds if str(x).isdigit()]
            s["settings"]["scan_minutes"] = min(olds) if olds else monitor_store.SCAN_MINUTES[0]
        _fill(s.setdefault("settings", {}), settings_defaults(s["kind"]))
        s["settings"].pop("group_source", None)   # nguon 'nhom da tham gia' da bo (21/10/2026)
        if s["kind"] == MONITOR:
            monitor_store.merge_ad_lists(s["settings"])
    drop_library(data)
    data["rules"] = rules(data)
    apply_rules(data)
    return data


def save(data):
    materialize(data)
    sync_images(data)
    apply_rules(data)
    if CONFIG_JSON.exists():
        shutil.copy(CONFIG_JSON, CONFIG_JSON.with_suffix(".json.bak"))
    tmp = CONFIG_JSON.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_JSON)


def view(data, kind):
    """Ban sao chi co muc loai `kind` (dung de goi ham cua upstt_store / monitor_store)."""
    return dict(data, accounts=[dict(a, campaigns=[c for c in a["campaigns"] if kind_of(c) == kind])
                                for a in data["accounts"]])


def account_dir(account_id):
    path = ACCOUNTS_DIR / account_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def campaign_dir(campaign_id):
    return monitor_store.campaign_dir(campaign_id)


def new_id(data, prefix):
    used = {a["id"] for a in data["accounts"]} | {c["id"] for a in data["accounts"] for c in a["campaigns"]}
    used |= {s["id"] for s in data.get("scenarios", [])}
    used |= {cid for s in data.get("scenarios", []) for cid in s.get("members", {}).values()}
    used |= {p.name for d in (ACCOUNTS_DIR, CAMPAIGNS_DIR, LOGS_DIR) if d.exists() for p in d.iterdir()}
    n = 1
    while f"{prefix}{n}" in used:
        n += 1
    return f"{prefix}{n}"


def new_account(data, name):
    return dict(ACCOUNT_DEFAULTS, id=new_id(data, "a"), name=name, campaigns=[], identities=[])


def new_campaign(data, name, kind):
    item = {"id": new_id(data, ID_PREFIX[kind]), "name": name, "kind": kind}
    _fill(item, defaults_of(kind))
    return item


def shift_times(times, minutes):
    """['06:30'] lui 15 phut -> ['06:45'] (qua 24h thi vong lai dau ngay)."""
    shifted = [(upstt_store.to_minutes(t) + minutes) % 1440 for t in times]
    return sorted(f"{m // 60:02d}:{m % 60:02d}" for m in set(shifted))


# ------------------------------------------------------------------ kich ban (giong AutoNuoi)
# Kich ban = noi dung + nhom + gio, tick cac tai khoan chay. Khi luu, materialize() sinh lai
# accounts[].campaigns[] (moi kich ban x tai khoan = 1 muc, id giu co dinh trong "members") -> fb_upstt.py,
# fb_monitor_v4.py, setup.ps1 van doc accounts[].campaigns[] nhu cu.
SCENARIO_PREFIX = "k"
MEMBER_KEYS = ("id", "name", "kind", "enabled", "scenario")      # khong nam trong settings
PER_MEMBER_KEYS = ("post_as", "post_as_name")   # task 003: rieng tung tai khoan (kich ban["post_as"]), khong o settings
CONTENT_KEYS = ("share_text", "media_folder", "media_count", "media_count_max")
DEFAULT_GAP = 15
migrated = False   # load() vua chuyen du lieu cu sang kich ban (giao dien luu ngay de giu id kich ban)


def settings_defaults(kind):
    return {k: v for k, v in defaults_of(kind).items() if k != "enabled" and k not in PER_MEMBER_KEYS}


def drop_library(data):
    """Bo 'Soan tin' (22/10/2026 - moi kich ban tu co noi dung): kich ban dang dung tin -> chep noi dung + anh
    cua tin vao kich ban, roi bo kho tin."""
    old = data.pop("library", []) or []
    library = {t.get("id"): t for t in old}
    backup = BASE_DIR / "soan_tin_cu.json"
    if old and not backup.exists():   # giu lai noi dung cac tin cu (ke ca tin chua kich ban nao dung)
        try:
            backup.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass
    for s in data.get("scenarios", []):
        t = library.get(s["settings"].pop("content_id", "") or "")
        if t:
            for key in CONTENT_KEYS:
                if key in t:
                    s["settings"][key] = t[key]
    for a in data.get("accounts", []):
        for c in a.get("campaigns", []):
            c.pop("content_id", None)


def new_scenario(data, name, kind):
    settings = {}
    _fill(settings, settings_defaults(kind))
    return {"id": new_id(data, SCENARIO_PREFIX), "name": name, "kind": kind, "enabled": True,
            "accounts": [], "gap_minutes": DEFAULT_GAP, "members": {}, "post_as": {}, "settings": settings}


def find_scenario(data, scenario_id):
    return next((s for s in data["scenarios"] if s["id"] == scenario_id), None)


def scenario_of(data, campaign_id):
    """Muc (campaign id) -> (kich ban, id tai khoan)."""
    for s in data["scenarios"]:
        for aid, cid in s["members"].items():
            if cid == campaign_id:
                return s, aid
    return None, None


def member_campaign(data, scenario, account_id):
    """Muc da sinh cua kich ban o tai khoan (chua Luu / chua tick -> None)."""
    cid = scenario["members"].get(account_id)
    account = find_account(data, account_id)
    return next((c for c in account["campaigns"] if c["id"] == cid), None) if account and cid else None


def ticked_accounts(data, scenario):
    """Tai khoan duoc tick, theo thu tu tren giao dien (= thu tu gian cach gio)."""
    return [a for a in data["accounts"] if a["id"] in scenario["accounts"]]


def default_member_times(data, scenario, account_id):
    """Gio mac dinh cua tai khoan: gio chung + gian cach x thu tu tai khoan trong danh sach tick."""
    ids = [a["id"] for a in ticked_accounts(data, scenario)]
    i = ids.index(account_id) if account_id in ids else len(ids)
    return shift_times(scenario["settings"].get("times", []), int(scenario.get("gap_minutes") or 0) * i)


def custom_member_times(scenario, account_id):
    """Gio rieng cua tai khoan trong kich ban (sua o man tai khoan duoi kich ban) hoac None = dung mac dinh."""
    times = (scenario.get("member_times") or {}).get(account_id)
    return list(times) if times else None


def member_times(data, scenario, account_id):
    """Gio dang cua tai khoan: gio rieng neu co, khong thi gio chung + gian cach."""
    return custom_member_times(scenario, account_id) or default_member_times(data, scenario, account_id)


def resolved_settings(data, scenario):
    """Ban sao settings cua kich ban (de sinh muc cho tung tai khoan)."""
    return json.loads(json.dumps(scenario["settings"]))


def materialize(data):
    """Sinh lai accounts[].campaigns[] tu kich ban (goi truoc khi kiem tra / luu).

    Task 003 (Dev B): moi muc sinh ra them item["post_as"] = scenario["post_as"].get(id tai khoan, "self") va
    item["post_as_name"] = identity_name(tai khoan, post_as) ("" voi Ca nhan). Id khong con trong tai khoan van giu
    nguyen (luot chay se bao IDENTITY_NOTES["missing"] va bo luot, KHONG doi sang Ca nhan).
    """
    built = {a["id"]: [] for a in data["accounts"]}
    for s in data["scenarios"]:
        s["accounts"] = [aid for aid in s["accounts"] if aid in built]
        settings = resolved_settings(data, s)
        for i, account in enumerate(ticked_accounts(data, s)):
            cid = s["members"].get(account["id"])
            if not cid:
                cid = s["members"][account["id"]] = new_id(data, ID_PREFIX[s["kind"]])
            item = json.loads(json.dumps(settings))
            item.update(id=cid, name=s["name"], kind=s["kind"], enabled=bool(s["enabled"]), scenario=s["id"])
            if s["kind"] == POST:
                item["times"] = (custom_member_times(s, account["id"])
                                 or shift_times(item.get("times", []), int(s.get("gap_minutes") or 0) * i))
            built[account["id"]].append(item)
    for account in data["accounts"]:
        account["campaigns"] = built[account["id"]]
    return data


def migrate_to_scenarios(data):
    """Du lieu cu (muc nam trong tai khoan) -> moi muc thanh 1 kich ban chi tick tai khoan do (giu id, gio, bat/tat)."""
    backup = BASE_DIR / "config.truoc_kich_ban.json"
    if CONFIG_JSON.exists() and not backup.exists():
        shutil.copy(CONFIG_JSON, backup)
    data["scenarios"] = []
    for account in data["accounts"]:
        for c in account["campaigns"]:
            s = {"id": new_id(data, SCENARIO_PREFIX), "name": c.get("name", ""), "kind": kind_of(c),
                 "enabled": bool(c.get("enabled", True)), "accounts": [account["id"]], "gap_minutes": DEFAULT_GAP,
                 "members": {account["id"]: c["id"]},
                 "settings": {k: v for k, v in c.items() if k not in MEMBER_KEYS + PER_MEMBER_KEYS}}
            data["scenarios"].append(s)
            c["scenario"] = s["id"]


def duplicate_scenario(data, scenario):
    """Nhan ban kich ban: cung noi dung / nhom / gio, chua tick tai khoan nao."""
    item = json.loads(json.dumps(scenario))
    item.update(id=new_id(data, SCENARIO_PREFIX), name=f"{scenario['name']} (bản sao)", accounts=[], members={},
                member_times={}, post_as={})
    if scenario["kind"] == MONITOR:
        for f in scenario_images(data, scenario):
            shutil.copy2(f, campaign_dir(item["id"]) / f.name)
    return item


def delete_scenario(data, scenario, stamp):
    data["scenarios"].remove(scenario)
    if scenario["kind"] == MONITOR:
        for ident in [scenario["id"], *scenario["members"].values()]:
            old = CAMPAIGNS_DIR / ident
            if old.exists():
                old.rename(CAMPAIGNS_DIR / f"_da_xoa_{ident}_{stamp}")
    materialize(data)


def remove_account_everywhere(data, account_id):
    for s in data["scenarios"]:
        if account_id in s["accounts"]:
            s["accounts"].remove(account_id)


# ------------------------------------------------------------------ danh tinh + gop tai khoan (task 003)
# Hop dong: plans/003_mot_nick_nhieu_page.md muc 3. Du lieu theo danh tinh: fb_login.identity_dir().
MERGE_MARKER = "da_gop.json"                     # accounts/<id phu>/da_gop.json {"into", "identity", "time"}
MERGE_BACKUP = "config.truoc_gop_{stamp}.json"   # ban sao config.json truoc khi gop (o BASE_DIR)


def account_identities(account):
    """Danh tinh cua tai khoan, Ca nhan luon dung dau.

    Vao: account (dict trong config). Ra: list dict {"id", "name", "kind"[, "missing"]}.
    account["identities"] rong / thieu muc "self" -> them {"id": "self", "name": <ten ca nhan>, "kind": "self"} o dau
    (ten: muc self da luu, khong co thi fb_profile.json, khong co nua thi account["name"]). Khong sua account.
    Loi: khong raise.
    """
    raise NotImplementedError


def identity_name(account, identity_id):
    """Ten danh tinh `identity_id` cua tai khoan ("self" -> ten ca nhan). Khong co -> "" (khong raise)."""
    raise NotImplementedError


def update_identities(account, found):
    """Gop ket qua 'Doc danh sach Page' (fb_login.read_identities / load_identities_file) vao account["identities"].

    Vao: found = list nhu fb_login.read_identities. Lam: giu thu tu cu, cap nhat ten theo id, them Page moi o cuoi;
    Page cu khong con trong `found` -> GIU LAI + "missing": True (kich ban con tro toi); thay lai -> bo "missing".
    Ra: {"added": [ten], "renamed": [(cu, moi)], "missing": [ten]}. Loi: found rong / khong co "self" -> ValueError.
    """
    raise NotImplementedError


def same_uid_groups(data):
    """Cac nhom tai khoan trong tool CUNG 1 nick Facebook (cung uid trong accounts/<id>/fb_profile.json).

    Ra: [[id tai khoan, ...], ...] - moi nhom >= 2 tai khoan, theo thu tu tren giao dien (thu tu data["accounts"]);
    tai khoan chua biet uid -> khong tinh. Khong co -> []. Loi doc file -> bo qua tai khoan do.
    """
    raise NotImplementedError


def merge_plan(data, main_id, other_ids):
    """Xem truoc viec gop (KHONG sua gi) -> noi dung hop xac nhan.

    Vao: main_id = tai khoan chinh (giu Chrome); other_ids = tai khoan phu cung uid (se thanh danh tinh cua main).
    Ra: {"ok": bool, "errors": [chu co dau], "main": main_id,
         "mapping": {id phu: id danh tinh cua main},   # ten fb_profile cua tk phu khop ten danh tinh (khong phan
                                                        # biet hoa thuong / dau cach) - khop ten ca nhan -> "self"
         "scenarios": [{"id", "name", "action": "doi" | "tach" | "bo_trung", "account": id phu, "identity": id}],
         "copies": [[duong dan nguon, duong dan dich], ...],   # IDENTITY_FILES -> fb_login.identity_dir(main, id)
         "logout": [id phu], "backup": ten file MERGE_BACKUP, "lines": [chu co dau cho hop xac nhan]}
    errors (ok=False): khac uid; tk phu khong co ten; khong thay Page cung ten trong danh tinh cua main
    ("Không thấy Page '<tên>' trong danh sách của '<main>' – bấm 'Đọc danh sách Page' ở tài khoản chính trước.").
    Loi: main_id / id phu khong co trong data -> ValueError.
    """
    raise NotImplementedError


def merge_accounts(data, main_id, other_ids, stamp, plan=None):
    """Gop tai khoan phu vao tai khoan chinh (sau khi nguoi dung bam Gop trong hop xac nhan).

    Vao: plan = ket qua merge_plan (None -> tu tinh); stamp = chuoi thoi gian (vd '20261025_1530') cho ten backup.
    Lam (theo thu tu, plan["ok"] False -> khong lam gi):
      1. Chep config.json -> BASE_DIR / MERGE_BACKUP.format(stamp=stamp).
      2. Chep du lieu: moi file IDENTITY_FILES cua accounts/<phu>/ -> identity_dir(accounts/<main>, id) (dich da co
         -> gop: ket_qua.json dung chuyen_du_lieu.merge_results, json dang {khoa: ...} giu ban dich + them khoa
         thieu, file .txt gop dong); commented_ids.txt gop vao accounts/<main>/; tk phu dang tam nghi lau hon ->
         tai khoan chinh nghi toi cung luc. KHONG xoa / sua gi trong accounts/<phu>/ (ngoai MERGE_MARKER).
      3. Kich ban tick tk phu: "doi" = thay bang main o cung vi tri, members / member_times chuyen sang main,
         post_as[main] = id; "bo_trung" = main da tick cung danh tinh -> bo tk phu; "tach" = main da tick bang danh
         tinh khac -> tao kich ban moi '<ten> (<ten danh tinh>)' chi tick main, giu id muc cu cua tk phu.
      4. Xoa tk phu khoi data["accounts"]; ghi accounts/<phu>/MERGE_MARKER.
    Ra: plan + {"done": True}. Nguoi goi (giao dien): save(data) -> chay '--logout --account <phu>' tung tk phu
        (dang xuat Facebook + xoa browser_profile) -> cap nhat lich.
    Loi: OSError khi chep -> raise (config chua luu, backup con nguyen). ValueError nhu merge_plan.
    """
    raise NotImplementedError


def merged_leftovers(data):
    """Tai khoan da gop nhung Chrome chua dang xuat / xoa duoc: thu muc accounts/<id> co MERGE_MARKER + browser_profile,
    id khong con trong data["accounts"]. Ra: [id]. Giao dien hien canh bao + nut thu lai '--logout'."""
    raise NotImplementedError


# ---- anh binh luan cua kich ban theo doi: campaigns/<id kich ban>/ (co thu muc = chinh thuc),
# chua co thu muc thi lay anh cua muc dau tien co anh (du lieu cu). Khi luu chep sang campaigns/<id muc>/.
def _images_in(folder):
    return sorted(f for f in folder.glob("anh*.*") if f.is_file()) if folder.exists() else []


def scenario_images(data, scenario):
    own = CAMPAIGNS_DIR / scenario["id"]
    if own.exists():
        return _images_in(own)
    for cid in scenario["members"].values():
        found = _images_in(CAMPAIGNS_DIR / cid)
        if found:
            return found
    return []


def scenario_image_dir(data, scenario):
    """Thu muc anh chinh thuc cua kich ban (tao + chep anh cu vao neu chua co) - dung khi doi anh."""
    own = CAMPAIGNS_DIR / scenario["id"]
    if not own.exists():
        old = scenario_images(data, scenario)
        own.mkdir(parents=True, exist_ok=True)
        for f in old:
            shutil.copy2(f, own / f.name)
    return own


def sync_images(data):
    """Anh binh luan kich ban -> thu muc tung muc da sinh (fb_monitor_v4 doc theo id muc)."""
    for s in data["scenarios"]:
        own = CAMPAIGNS_DIR / s["id"]
        if s["kind"] != MONITOR or not own.exists():
            continue
        wanted = {f.name: f for f in _images_in(own)}
        for aid in s["accounts"]:
            dst = campaign_dir(s["members"][aid]) if aid in s["members"] else None
            if not dst:
                continue
            for f in _images_in(dst):
                if f.name not in wanted:
                    f.unlink()
            for name, f in wanted.items():
                target = dst / name
                if not target.exists() or target.stat().st_size != f.stat().st_size or \
                        target.stat().st_mtime < f.stat().st_mtime:
                    shutil.copy2(f, target)


def campaign_groups(account, campaign):
    """Nhom cua muc o tai khoan."""
    return campaign.get("groups", [])


def find_account(data, account_id):
    return next((a for a in data["accounts"] if a["id"] == account_id), None)


def find_campaign(data, campaign_id):
    for account in data["accounts"]:
        for campaign in account["campaigns"]:
            if campaign["id"] == campaign_id:
                return account, campaign
    return None, None


# ------------------------------------------------------------------ kiem tra / lich
def validate(data):
    materialize(data)
    errors = []
    for kind, store in STORES.items():
        for error in store.validate(view(data, kind)):
            if error not in errors:
                errors.append(error)
    return errors


def warnings(data):
    idle = [s["name"] for s in data["scenarios"] if s["enabled"] and not s["accounts"]]
    out = upstt_store.warnings(view(data, POST))
    if idle:
        out = out or ["Nên xem lại:"]
        out.append(f"{len(idle)} kịch bản đang bật nhưng chưa tick tài khoản nào (chưa chạy): " + ", ".join(idle[:5]))
    return out


def licensed_account_ids(data, st=None):
    """Tai khoan duoc chay theo ban quyen: N tai khoan dau tien (theo thu tu tren giao dien); chua co ban quyen -> rong."""
    import ban_quyen
    st = st or ban_quyen.trang_thai()
    return {a["id"] for a in data["accounts"][:st["so_tai_khoan"]]} if st["ok"] else set()


def schedule_entries(data):
    """Lich dang bai (moi muc 1 lich, task = id muc) + lich quet (moi tai khoan 1 lich, task = id tai khoan).

    Chi tao lich cho tai khoan nam trong ban quyen (het han / chua kich hoat -> khong co lich nao).
    """
    if data.get("paused"):
        return []
    allowed = licensed_account_ids(data)
    entries = upstt_store.schedule_entries(view(data, POST)) + monitor_store.schedule_entries(view(data, MONITOR))
    entries = [e for e in entries if e["account"] in allowed]
    if data.get("auto_care") and allowed:
        # 'Tu cham bai': 1 lich chung, 2 tieng/lan (fb_upstt.auto_care tu loc tai khoan theo ban quyen).
        every = auto_care_hours(data) * 60
        entries.append({"task": "tu_cham_bai", "account": sorted(allowed)[0], "args": "--auto-care",
                        "name": "Tự cập nhật trạng thái + chăm bài", "every": every, "max": every - 10, "offset": 15})
    inbox = inbox_settings(data)
    if inbox["enabled"] and allowed:
        # 'Kiem tra tin nhan': 1 lich chung (fb_upstt --check-inbox tu loc tai khoan theo ban quyen).
        every = inbox["minutes"]
        entries.append({"task": "tin_nhan", "account": sorted(allowed)[0], "args": "--check-inbox",
                        "name": "Kiểm tra tin nhắn mới", "every": every, "max": max(8, every - 2), "offset": 3})
    return entries


# Theo doi tin nhan khach nhan toi cac nick (Telegram rieng, khac kenh cua kich ban theo doi).
# Giong fb_login.INBOX_MINUTES: (mac dinh, nho nhat, lon nhat) phut giua 2 luot.
INBOX_DEFAULTS = {"enabled": False, "minutes": 15, "days": 7, "telegram_token": "", "telegram_chat_id": ""}
INBOX_MINUTES = (15, 10, 240)
INBOX_DAYS = (7, 1, 60)   # giong fb_login.INBOX_DAYS: chi lay tin chua doc trong N ngay gan nhat


def inbox_settings(data):
    saved = data.get("inbox") or {}
    s = dict(INBOX_DEFAULTS, **saved)
    default, low, high = INBOX_MINUTES
    try:   # ban dau luu 'hours' (mac dinh 2) -> bo, dung mac dinh moi
        value = int(saved.get("minutes") or default)
    except (TypeError, ValueError):
        value = default
    s["minutes"] = min(high, max(low, value))
    s.pop("hours", None)
    default, low, high = INBOX_DAYS
    try:
        s["days"] = min(high, max(low, int(saved.get("days") or default)))
    except (TypeError, ValueError):
        s["days"] = default
    return s


AUTO_CARE_HOURS = (2, 1, 24)   # mac dinh, nho nhat, lon nhat (gio giua 2 luot tu cham)


def auto_care_hours(data):
    default, low, high = AUTO_CARE_HOURS
    try:
        return min(high, max(low, int(data.get("auto_care_hours") or default)))
    except (TypeError, ValueError):
        return default


def accounts_with_enabled(data):
    return [a for a in data["accounts"] if any(c["enabled"] for c in a["campaigns"])]


# ------------------------------------------------------------------ tam nghi
def pause_notes(account, campaign):
    return store_of(campaign).pause_notes(account, campaign)


def reset_pause(account, kind, key, campaign=None):
    """kind cua ghi chu ('account' | 'group' | 'pending' | 'recovering'); campaign cho biet loai muc."""
    store = store_of(campaign) if campaign else upstt_store
    store.reset_pause(account, kind, key)


def image_path(campaign, n):
    return monitor_store.image_path(campaign, n)


# ------------------------------------------------------------------ rule khi loi (dung chung ca tool)
RULE_SPEC = [
    ("① Facebook báo \"bạn đăng quá nhiều\" (chống spam)", [
        ("text", "→ Tool nghỉ CẢ tài khoản: không đăng bài, không quét, không bình luận:"),
        ("grid", [("Bị lần đầu:", "nghỉ", ("pause_h1", 48, 1, 720), "giờ"),
                  ("Bị lần thứ 2:", "nghỉ", ("pause_h2", 72, 1, 720), "giờ"),
                  ("Bị lần thứ 3 trở đi:", "nghỉ", ("pause_h3", 168, 1, 2160), "giờ")]),
        ("line", "→ Nếu {} ngày liền không bị lại, lần sau được tính là \"lần đầu\".",
         [("strike_reset_days", 14, 1, 90)]),
        ("line", "→ Nghỉ xong, trong {} giờ đầu tool chỉ đăng một nửa số nhóm cho an toàn.",
         [("recovery_hours", 24, 0, 168)]),
        ("tip", "💡 Ví dụ: bị lần đầu lúc 8h sáng thứ 2 → tool chạy lại từ 8h sáng thứ 4."),
    ]),
] + upstt_store.RULE_SPEC[1:] + [
    ("⑤ Không bình luận được trong một nhóm theo dõi (tool vẫn quét và báo Telegram)",
     monitor_store.RULE_SPEC[1][1]),
]


def _rule_slots():
    for _title, parts in RULE_SPEC:
        for part in parts:
            if part[0] == "line":
                yield from part[2]
            elif part[0] == "grid":
                yield from (row[2] for row in part[1])


RULE_DEFAULTS = {k: d for k, d, _lo, _hi in _rule_slots()}


def rules(data):
    saved = data.get("rules") or {}
    return {k: int(saved.get(k, d)) for k, d in RULE_DEFAULTS.items()}


def apply_rules(data):
    data["rules"] = rules(data)
    upstt_store.apply_rules(data)
    monitor_store.apply_rules(data)
