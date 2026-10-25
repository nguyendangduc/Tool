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
from pathlib import Path

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
            post_as = str((s.get("post_as") or {}).get(account["id"]) or SELF)
            item["post_as"] = post_as
            # Page khong con / 'missing' -> ten "" -> luot chay bo ngay, khong thao tac Facebook (muc 3.10d).
            hit = next((x for x in account_identities(account) if str(x.get("id")) == post_as), None)
            item["post_as_name"] = "" if post_as == SELF or not hit or hit.get("missing") else hit.get("name", "")
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
MERGE_BACKUP_DIR = "sao_luu"   # thu muc con (dong_goi.ps1 chi chep file o goc -> khong bao gio vao ban gui khach)
MERGE_BACKUP = MERGE_BACKUP_DIR + "/config.truoc_gop_{stamp}.json"   # ban sao config.json truoc khi gop
SELF = "self"                                    # = fb_login.IDENTITY_SELF (khong import fb_login o dau file)
IDENTITY_DIR_NAME = "danh_tinh"                  # = fb_login.IDENTITY_DIR_NAME (chi de xem truoc duong dan)


def _profile(account_id):
    """fb_profile.json cua tai khoan ({} neu chua co / loi)."""
    try:
        data = json.loads((ACCOUNTS_DIR / account_id / "fb_profile.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _norm_name(text):
    return " ".join(str(text or "").split()).casefold()


def identity_data_dir(account_id, identity_id=SELF):
    """Thu muc du lieu cua danh tinh (ket qua, trang thai nhom, cham bai...) - giao dien doc theo post_as cua muc.

    Ca nhan -> accounts/<id>/ (nhu cu, khong goi fb_login); Page -> fb_login.identity_dir (Dev A).
    """
    acc_dir = ACCOUNTS_DIR / account_id
    if identity_id in (None, "", SELF):
        return acc_dir
    import fb_login
    return fb_login.identity_dir(acc_dir, str(identity_id))


def campaign_data_dir(account, campaign):
    """Thu muc du lieu cua 1 muc (theo campaign["post_as"])."""
    return identity_data_dir(account["id"], (campaign or {}).get("post_as") or SELF)


def account_identity_ids(account):
    """Id moi danh tinh co du lieu cua tai khoan: Ca nhan + Page trong danh sach + thu muc danh_tinh/<id> tren dia
    (so lieu ca tai khoan = cong moi danh tinh)."""
    ids = [x["id"] for x in account_identities(account)]
    folder = ACCOUNTS_DIR / account["id"] / IDENTITY_DIR_NAME
    try:
        ids += sorted(p.name for p in folder.iterdir() if p.is_dir() and p.name.isdigit() and p.name not in ids)
    except OSError:
        pass
    return ids


def account_identities(account):
    """Danh tinh cua tai khoan, Ca nhan luon dung dau.

    Vao: account (dict trong config). Ra: list dict {"id", "name", "kind"[, "missing"]}.
    account["identities"] rong / thieu muc "self" -> them {"id": "self", "name": <ten ca nhan>, "kind": "self"} o dau
    (ten: muc self da luu, khong co thi fb_profile.json, khong co nua thi account["name"]). Khong sua account.
    Loi: khong raise.
    """
    saved = [dict(x) for x in (account.get("identities") or []) if isinstance(x, dict) and x.get("id")]
    me = next((x for x in saved if str(x["id"]) == SELF), None)
    pages = [dict(x, id=str(x["id"]), kind="page") for x in saved if str(x["id"]) != SELF]
    if me is None:
        me = {"id": SELF, "name": "", "kind": "self"}
    me = dict(me, id=SELF, kind="self")
    if not me.get("name"):
        me["name"] = _profile(account.get("id", "")).get("name") or account.get("name", "")
    return [me] + pages


def identity_name(account, identity_id):
    """Ten danh tinh `identity_id` cua tai khoan ("self" -> ten ca nhan). Khong co -> "" (khong raise)."""
    want = SELF if identity_id in (None, "") else str(identity_id)
    try:
        return next((x.get("name", "") for x in account_identities(account) if x["id"] == want), "")
    except Exception:
        return ""


def update_identities(account, found):
    """Gop ket qua 'Doc danh sach Page' (fb_login.read_identities / load_identities_file) vao account["identities"].

    Vao: found = list nhu fb_login.read_identities. Lam: giu thu tu cu, cap nhat ten theo id, them Page moi o cuoi;
    Page cu khong con trong `found` -> GIU LAI + "missing": True (kich ban con tro toi); thay lai -> bo "missing".
    Ra: {"added": [ten], "renamed": [(cu, moi)], "missing": [ten]}. Loi: found rong / khong co "self" -> ValueError.
    """
    found = [x for x in (found or []) if isinstance(x, dict) and x.get("id")]
    if not found or not any(str(x["id"]) == SELF for x in found):
        raise ValueError("danh sach danh tinh rong hoac thieu Ca nhan")
    current = [dict(x) for x in (account.get("identities") or []) if isinstance(x, dict) and x.get("id")]
    by_id = {str(x["id"]): x for x in current}
    out = {"added": [], "renamed": [], "missing": []}
    seen = set()
    for f in found:
        fid = str(f["id"])
        name = str(f.get("name") or "").strip()
        kind = "self" if fid == SELF else "page"
        seen.add(fid)
        old = by_id.get(fid)
        if old is None:
            old = by_id[fid] = {"id": fid, "name": name, "kind": kind}
            current.append(old)
            if kind == "page":
                out["added"].append(name)
            continue
        if name and old.get("name") != name:
            if old.get("name"):
                out["renamed"].append((old["name"], name))
            old["name"] = name
        old.update(id=fid, kind=kind)
        old.pop("missing", None)
    for x in current:
        if str(x["id"]) not in seen:
            x["missing"] = True
            out["missing"].append(x.get("name", ""))
    account["identities"] = ([x for x in current if str(x["id"]) == SELF]
                             + [x for x in current if str(x["id"]) != SELF])
    return out


def same_uid_groups(data):
    """Cac nhom tai khoan trong tool CUNG 1 nick Facebook (cung uid trong accounts/<id>/fb_profile.json).

    Ra: [[id tai khoan, ...], ...] - moi nhom >= 2 tai khoan, theo thu tu tren giao dien (thu tu data["accounts"]);
    tai khoan chua biet uid -> khong tinh. Khong co -> []. Loi doc file -> bo qua tai khoan do.
    """
    groups = {}
    for a in data.get("accounts", []):
        uid = str(_profile(a["id"]).get("uid") or "")
        if uid.isdigit():
            groups.setdefault(uid, []).append(a["id"])
    return [ids for ids in groups.values() if len(ids) >= 2]


def default_merge_main(data, ids):
    """Tai khoan chinh mac dinh khi gop (PM cau 10): tai khoan co ten Facebook = ten Ca nhan (theo danh sach danh
    tinh da doc cua bat ky tai khoan nao trong nhom), khong co thi tai khoan dung dau."""
    accounts = [find_account(data, i) for i in ids]
    selves = {_norm_name(x.get("name")) for a in accounts if a for x in (a.get("identities") or [])
              if isinstance(x, dict) and str(x.get("id")) == SELF and x.get("name")}
    # Tai khoan Page kieu cu (fb_profile.json co page_id) khong bao gio la tai khoan chinh (muc 3.10b).
    personal = [a for a in accounts if a and not _profile(a["id"]).get("page_id")]
    for a in personal:
        if _norm_name(_profile(a["id"]).get("name")) in selves:
            return a["id"]
    if personal:
        return personal[0]["id"]
    return ids[0] if ids else None


def _identity_path_preview(main_id, identity_id):
    """Duong dan danh tinh de HIEN (khong tao thu muc) - viec chep that dung fb_login.identity_dir."""
    acc_dir = ACCOUNTS_DIR / main_id
    return acc_dir if identity_id == SELF else acc_dir / IDENTITY_DIR_NAME / str(identity_id)


def _identity_files():
    import fb_login
    return tuple(fb_login.IDENTITY_FILES)


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
    main = find_account(data, main_id)
    if main is None:
        raise ValueError(f"khong co tai khoan {main_id}")
    others = []
    for oid in other_ids:
        if find_account(data, oid) is None:
            raise ValueError(f"khong co tai khoan {oid}")
        if oid != main_id and oid not in others:
            others.append(oid)
    errors, mapping = [], {}
    main_uid = str(_profile(main_id).get("uid") or "")
    identities = account_identities(main)
    names = {x["id"]: x.get("name", "") for x in identities}
    if _profile(main_id).get("page_id"):
        errors.append(f"'{main['name']}' đang ở Page '{_profile(main_id).get('name', '')}' (tài khoản Page kiểu cũ) – "
                      "chọn tài khoản Cá nhân của nick làm tài khoản chính.")
    for oid in others:
        other = find_account(data, oid)
        if not main_uid.isdigit() or str(_profile(oid).get("uid") or "") != main_uid:
            errors.append(f"'{other['name']}' không cùng nick Facebook với '{main['name']}' – không gộp được.")
            continue
        fb_name = _profile(oid).get("name", "")
        page_id = str(_profile(oid).get("page_id") or "")
        if page_id:
            # Muc 3.10b: ghep theo id Page truoc (ten co the da doi / trung ten Ca nhan).
            hit = next((x["id"] for x in identities if str(x.get("id")) == page_id), None)
        else:
            if not _norm_name(fb_name):
                errors.append(f"'{other['name']}' chưa có tên Facebook – bấm 'Kiểm tra đăng nhập' ở tài khoản đó trước.")
                continue
            hit = next((x["id"] for x in identities if _norm_name(x.get("name")) == _norm_name(fb_name)), None)
        if hit is None:
            errors.append(f"Không thấy Page '{fb_name or page_id}' trong danh sách của '{main['name']}' – bấm 'Đọc danh "
                          "sách Page' ở tài khoản chính trước.")
            continue
        if hit == SELF:
            errors.append(f"'{other['name']}' đang là Cá nhân của nick (trùng '{main['name']}'), không phải Page → không "
                          "gộp được. Nếu tài khoản này vốn đăng bằng Page: mở Chrome của nó, chuyển sang Page đó rồi bấm "
                          "'Kiểm tra đăng nhập'; nếu chỉ là tài khoản trùng thì xoá tài khoản này.")
            continue
        mapping[oid] = hit

    # Kich ban: mo phong theo thu tu tick (tk phu dau tien thay cho chinh, cac tk sau tach / bo trung).
    scenarios = []
    for s in data.get("scenarios", []):
        cur = (str((s.get("post_as") or {}).get(main_id) or SELF)) if main_id in s["accounts"] else None
        split = set()
        for aid in s["accounts"]:
            if aid not in mapping:
                continue
            ident = mapping[aid]
            if cur is None:
                action, cur = "doi", ident
            elif ident == cur or ident in split:
                action = "bo_trung"
            else:
                action = "tach"
                split.add(ident)
            scenarios.append({"id": s["id"], "name": s["name"], "action": action, "account": aid, "identity": ident})

    copies = []
    try:
        files = _identity_files()
    except Exception:
        files = ()
    for oid, ident in mapping.items():
        dst = _identity_path_preview(main_id, ident)
        for name in files:
            src = ACCOUNTS_DIR / oid / name
            if src.exists():
                copies.append([str(src), str(dst / name)])
    backup = MERGE_BACKUP.format(stamp="<giờ gộp>")
    label = lambda i: "Cá nhân" if i == SELF else f"Page '{names.get(i, i)}'"
    acc_name = lambda i: find_account(data, i)["name"]
    lines = [f"Gộp vào '{main['name']}' (giữ Chrome + đăng nhập của tài khoản này):"]
    lines += [f"  • '{acc_name(o)}' → thành danh tính {label(i)} của '{main['name']}'" for o, i in mapping.items()]
    if scenarios:
        lines.append("Kịch bản:")
    for x in scenarios:
        who = names.get(x["identity"], x["identity"])
        if x["action"] == "doi":
            lines.append(f"  • '{x['name']}': '{acc_name(x['account'])}' → '{main['name']}' đăng bằng {label(x['identity'])}")
        elif x["action"] == "bo_trung":
            lines.append(f"  • '{x['name']}': bỏ '{acc_name(x['account'])}' ('{main['name']}' đã chạy bằng "
                         f"{label(x['identity'])})")
        else:
            lines.append(f"  • '{x['name']}': '{main['name']}' đang chạy bằng danh tính khác → tách thành kịch bản mới "
                         f"'{x['name']} ({who})' cho '{main['name']}' đăng bằng {label(x['identity'])}")
    lines.append(f"Dữ liệu: chép {len(copies)} file (kết quả, trạng thái nhóm, chăm bài…) sang danh tính tương ứng của "
                 f"'{main['name']}'. Thư mục cũ của tài khoản phụ giữ nguyên.")
    lines.append(f"Sao lưu cấu hình trước khi gộp: {MERGE_BACKUP.format(stamp='<ngày giờ>')}")
    if mapping:
        lines.append("Sau khi gộp: đăng xuất Facebook + xoá Chrome của " + ", ".join(f"'{acc_name(o)}'" for o in mapping)
                     + "; các tài khoản này biến mất khỏi danh sách.")
    if not others:
        errors.append("Chưa chọn tài khoản phụ nào để gộp.")
    return {"ok": not errors, "errors": errors, "main": main_id, "mapping": mapping, "scenarios": scenarios,
            "copies": copies, "logout": list(mapping), "backup": backup, "lines": lines}


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def _merge_file(src, dst):
    """Chep src -> dst; dst da co -> gop (ket_qua.json: merge_results; json dict: giu dich + them khoa thieu;
    .txt: gop dong). OSError -> raise."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(src, dst)
        return
    if src.suffix == ".txt":
        old = dst.read_text(encoding="utf-8", errors="replace").splitlines()
        new = src.read_text(encoding="utf-8", errors="replace").splitlines()
        have = set(old)
        extra = [x for x in new if x.strip() and x not in have]
        if extra:
            dst.write_text("\n".join(old + extra) + "\n", encoding="utf-8")
        return
    a, b = _read_json(dst), _read_json(src)
    if src.name == "ket_qua.json":
        import chuyen_du_lieu
        merged = chuyen_du_lieu.merge_results(a if isinstance(a, dict) else {}, b if isinstance(b, dict) else {})
    elif isinstance(a, dict) and isinstance(b, dict):
        merged = dict(a)
        for key, value in b.items():
            merged.setdefault(key, value)
    elif a is None and b is not None:
        merged = b
    else:
        return
    dst.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")


def _merge_pause(main_dir, other_dir):
    """Tk phu dang tam nghi lau hon -> tai khoan chinh nghi toi cung luc (tam nghi theo nick, cau PM 5)."""
    import fb_login
    other, mine = fb_login.nick_pause(other_dir), fb_login.nick_pause(main_dir)
    if not other or (mine and float(mine.get("until", 0)) >= float(other.get("until", 0))):
        return
    path = fb_login._pause_file(main_dir)
    info = dict(other, strikes=max(int(other.get("strikes", 1) or 1), int((mine or {}).get("strikes", 0) or 0)))
    path.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")


def _move_member(s, old, new, identity):
    """Chuyen o tick / id muc / gio rieng cua `old` sang `new` trong kich ban s (tai cho)."""
    s["accounts"] = [new if a == old else a for a in s["accounts"]]
    for key in ("members", "member_times"):
        d = s.setdefault(key, {})
        if old in d:
            d[new] = d.pop(old)
    post_as = s.setdefault("post_as", {})
    post_as.pop(old, None)
    if identity == SELF:
        post_as.pop(new, None)
    else:
        post_as[new] = identity


def _drop_member(s, aid):
    s["accounts"] = [a for a in s["accounts"] if a != aid]
    for key in ("members", "member_times", "post_as"):
        (s.get(key) or {}).pop(aid, None)


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
    import time
    import fb_login
    plan = plan or merge_plan(data, main_id, other_ids)
    if not plan.get("ok"):
        return dict(plan, done=False)
    mapping = plan["mapping"]
    main = find_account(data, main_id)
    main_dir = ACCOUNTS_DIR / main_id
    # 1. backup (config.json that; chua co file -> ghi ban dang mo)
    backup = BASE_DIR / MERGE_BACKUP.format(stamp=stamp)
    backup.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_JSON.exists():
        shutil.copy2(CONFIG_JSON, backup)
    else:
        backup.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # 2. chep du lieu (chua dong vao data -> loi o day thi du lieu trong bo nho van nguyen)
    files = _identity_files()
    for oid, ident in mapping.items():
        src_dir = ACCOUNTS_DIR / oid
        dst_dir = Path(fb_login.identity_dir(main_dir, ident))
        for name in files:
            if (src_dir / name).exists():
                _merge_file(src_dir / name, dst_dir / name)
        if (src_dir / "commented_ids.txt").exists():
            _merge_file(src_dir / "commented_ids.txt", main_dir / "commented_ids.txt")
        try:
            _merge_pause(main_dir, src_dir)
        except Exception as e:
            print(f"[GOP] khong chep duoc tam nghi cua {oid}: {e}")
    for oid, ident in mapping.items():
        (ACCOUNTS_DIR / oid / MERGE_MARKER).write_text(
            json.dumps({"into": main_id, "identity": ident, "time": time.time()}, ensure_ascii=False), encoding="utf-8")
    # 3. kich ban
    for x in plan["scenarios"]:
        s = find_scenario(data, x["id"])
        if s is None or x["account"] not in s["accounts"]:
            continue
        if x["action"] == "doi":
            _move_member(s, x["account"], main_id, x["identity"])
        elif x["action"] == "bo_trung":
            _drop_member(s, x["account"])
        else:   # tach (cau PM 6): ban sao chi tick tai khoan chinh, giu id muc cu cua tk phu
            item = json.loads(json.dumps(s))
            label = identity_name(main, x["identity"]) or x["identity"]
            item.update(id=new_id(data, SCENARIO_PREFIX), name=f"{s['name']} ({label})", accounts=[x["account"]],
                        members={k: v for k, v in s.get("members", {}).items() if k == x["account"]},
                        member_times={k: v for k, v in (s.get("member_times") or {}).items() if k == x["account"]},
                        post_as={})
            if s["kind"] == POST and not item["member_times"]:   # giu gio dang cu cua tk phu (khong lui lai gio)
                item["member_times"] = {x["account"]: default_member_times(data, s, x["account"])}
            _move_member(item, x["account"], main_id, x["identity"])
            data["scenarios"].insert(data["scenarios"].index(s) + 1, item)
            _drop_member(s, x["account"])
    # 4. bo tk phu
    gone = set(mapping)
    data["accounts"] = [a for a in data["accounts"] if a["id"] not in gone]
    for oid in gone:
        remove_account_everywhere(data, oid)
    return dict(plan, done=True, backup=f"{MERGE_BACKUP_DIR}/{backup.name}")


def merged_leftovers(data):
    """Tai khoan da gop nhung Chrome chua dang xuat / xoa duoc: thu muc accounts/<id> co MERGE_MARKER + browser_profile,
    id khong con trong data["accounts"]. Ra: [id]. Giao dien hien canh bao + nut thu lai '--logout'."""
    ids = {a["id"] for a in data.get("accounts", [])}
    try:
        dirs = sorted(p for p in ACCOUNTS_DIR.iterdir() if p.is_dir())
    except OSError:
        return []
    return [p.name for p in dirs if p.name not in ids and (p / MERGE_MARKER).exists()
            and (p / "browser_profile").exists()]


def merge_marker(account_id):
    """Noi dung da_gop.json cua tai khoan da gop ({} neu khong co)."""
    return _read_json(ACCOUNTS_DIR / account_id / MERGE_MARKER) or {}


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
    lost = lost_identities(data)
    if lost:
        out = out or ["Nên xem lại:"]
        out.append(f"{len(lost)} mục 'Đăng bằng' Page không còn trong tài khoản (lượt chạy sẽ BỎ, không đăng bằng Cá "
                   "nhân thay) – mở kịch bản → '👥 Tài khoản chạy' chọn lại: "
                   + ", ".join(f"{s} – {a}" for s, a in lost[:5]))
    return out


def lost_identities(data):
    """[(ten kich ban, ten tai khoan)] co post_as la Page khong con (khong co trong danh sach / 'missing')."""
    out = []
    for s in data.get("scenarios", []):
        for aid, pid in (s.get("post_as") or {}).items():
            account = find_account(data, aid)
            if not account or aid not in s["accounts"] or str(pid or SELF) == SELF:
                continue
            hit = next((x for x in account_identities(account) if x["id"] == str(pid)), None)
            if hit is None or hit.get("missing"):
                out.append((s["name"], account["name"]))
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
    store.reset_pause(account, kind, key, identity=(campaign or {}).get("post_as") or SELF)


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
