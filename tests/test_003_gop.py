# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
"""Task 003 - gop tai khoan trung uid (tool_store.same_uid_groups / merge_plan / merge_accounts / merged_leftovers).
Viet TU SPEC (plan 003 muc 2.5, 3.6, 3.7, PM cau 3, 5, 6) - cho Dev B (+ fb_login.identity_dir cua Dev A).

Config gia (giong may PM): a4 + a2 cung uid 111 (a2 = Page "HTX chó mèo" cua a4);
a5 + a3 + a6 cung uid 222 (a3 = Page "Thư Tình", a6 = Page "Shop Mèo" cua a5); a7 nick khac chua biet uid.
Moi file nam trong tmp_path (khong dung config.json / accounts that).
"""
import copy
import json
import time

import pytest

import fb_login
import monitor_store
import tool_store
import upstt_store

STAMP = "20261025_1530"
HTX = "61595395697904"
THU_TINH = "61500000000002"
SHOP = "61500000000003"


@pytest.fixture
def tool_dir(tmp_path, monkeypatch):
    for mod in (tool_store, upstt_store, monitor_store):
        monkeypatch.setattr(mod, "BASE_DIR", tmp_path, raising=False)
        monkeypatch.setattr(mod, "CONFIG_JSON", tmp_path / "config.json", raising=False)
        monkeypatch.setattr(mod, "ACCOUNTS_DIR", tmp_path / "accounts", raising=False)
    monkeypatch.setattr(tool_store, "CAMPAIGNS_DIR", tmp_path / "campaigns")
    monkeypatch.setattr(monitor_store, "CAMPAIGNS_DIR", tmp_path / "campaigns")
    monkeypatch.setattr(tool_store, "LOGS_DIR", tmp_path / "logs")
    lock_dir = tmp_path / "fb_tools"
    lock_dir.mkdir()
    monkeypatch.setattr(fb_login, "_nick_lock_dir", lambda: lock_dir)   # file tam nghi nick -> tmp
    (tmp_path / "accounts").mkdir()
    return tmp_path


def acc_dir(tool_dir, account_id):
    d = tool_dir / "accounts" / account_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def profile(tool_dir, account_id, name, uid):
    (acc_dir(tool_dir, account_id) / "fb_profile.json").write_text(
        json.dumps({"name": name, "uid": uid, "time": "2026-10-25 10:00"}, ensure_ascii=False), encoding="utf-8")


def account(account_id, name, identities=()):
    return dict(monitor_store.ACCOUNT_DEFAULTS, id=account_id, name=name, campaigns=[], group="",
                identities=list(identities))


def scenario(sid, name, kind, accounts, members, post_as=None, member_times=None):
    settings = {}
    tool_store._fill(settings, tool_store.settings_defaults(kind))
    settings.update(groups=["https://www.facebook.com/groups/abc/"])
    if kind == "post":
        settings.update(share_text=f"nội dung {sid}", times=["06:30"])
    return {"id": sid, "name": name, "kind": kind, "enabled": True, "accounts": list(accounts), "gap_minutes": 15,
            "members": dict(members), "member_times": dict(member_times or {}), "post_as": dict(post_as or {}),
            "settings": settings}


@pytest.fixture
def data(tool_dir):
    profile(tool_dir, "a2", "HTX chó mèo", "111")
    profile(tool_dir, "a3", "  thư TÌNH ", "222")       # khac hoa thuong + dau cach van khop
    profile(tool_dir, "a4", "Nguyễn Văn Bốn", "111")
    profile(tool_dir, "a5", "Trần Thị Năm", "222")
    profile(tool_dir, "a6", "Shop Mèo", "222")
    acc_dir(tool_dir, "a7")                               # chua biet uid
    d = {
        "accounts": [
            account("a4", "Tài khoản 4", [{"id": "self", "name": "Nguyễn Văn Bốn", "kind": "self"},
                                          {"id": HTX, "name": "HTX chó mèo", "kind": "page"}]),
            account("a2", "Tai khoan 2"),
            account("a5", "Tài khoản 5", [{"id": "self", "name": "Trần Thị Năm", "kind": "self"},
                                          {"id": THU_TINH, "name": "Thư Tình", "kind": "page"},
                                          {"id": SHOP, "name": "Shop Mèo", "kind": "page"}]),
            account("a3", "Tài khoản 3"),
            account("a6", "Tài khoản 6"),
            account("a7", "Tài khoản 7"),
        ],
        "scenarios": [
            # k1: a5 (Ca nhan) + a3 (Thu Tinh) cung dang -> 'tach' (PM cau 6)
            scenario("k1", "Bài 1", "post", ["a5", "a3"], {"a5": "c1", "a3": "c2"}),
            # k2: a7 + a6 -> 'doi' a6 thanh a5 bang Shop Meo, tai cho, giu gio rieng
            scenario("k2", "Bài 2", "post", ["a7", "a6"], {"a7": "c3", "a6": "c4"},
                     member_times={"a6": ["09:00"]}),
            # k3 (theo doi): a5 da tick bang Thu Tinh + a3 -> 'bo_trung'
            scenario("k3", "Theo dõi 3", "monitor", ["a5", "a3"], {"a5": "m1", "a3": "m2"},
                     post_as={"a5": THU_TINH}),
            # k4: chi a2 -> 'doi' sang a4 bang HTX
            scenario("k4", "Bài 4", "post", ["a2"], {"a2": "c5"}),
        ],
    }
    tool_store.materialize(d)
    (tool_dir / "config.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def find(d, sid):
    return next(s for s in d["scenarios"] if s["id"] == sid)


def results(sent_slug, t):
    return {"groups": {}, "sent": {sent_slug: [[t, "groups/abc", "x"]]}, "alias": {}, "notes_seen": []}


# ------------------------------------------------------------------ same_uid_groups
def test_same_uid_groups(data):
    groups = tool_store.same_uid_groups(data)
    assert sorted(groups) == sorted([["a4", "a2"], ["a5", "a3", "a6"]])   # theo thu tu giao dien
    assert all("a7" not in g for g in groups)


def test_same_uid_groups_khong_trung(tool_dir):
    profile(tool_dir, "a1", "A", "1")
    profile(tool_dir, "a2", "B", "2")
    d = {"accounts": [account("a1", "1"), account("a2", "2"), account("a3", "3")], "scenarios": []}
    assert tool_store.same_uid_groups(d) == []


def test_same_uid_groups_file_hong_bo_qua(data, tool_dir):
    (tool_dir / "accounts" / "a6" / "fb_profile.json").write_text("{hong", encoding="utf-8")
    assert sorted(tool_store.same_uid_groups(data)) == sorted([["a4", "a2"], ["a5", "a3"]])


# ------------------------------------------------------------------ merge_plan
def test_merge_plan_khong_sua_gi(data, tool_dir):
    before = copy.deepcopy(data)
    cfg_before = (tool_dir / "config.json").read_text(encoding="utf-8")
    plan = tool_store.merge_plan(data, "a5", ["a3", "a6"])
    assert data == before
    assert (tool_dir / "config.json").read_text(encoding="utf-8") == cfg_before
    assert not list(tool_dir.glob("**/config.truoc_gop_*.json"))
    assert not (tool_dir / "accounts" / "a3" / tool_store.MERGE_MARKER).exists()
    assert not list((tool_dir / "accounts" / "a5").rglob("ket_qua.json"))
    assert plan["ok"] is True and plan["errors"] == []


def test_merge_plan_noi_dung(data):
    plan = tool_store.merge_plan(data, "a5", ["a3", "a6"])
    assert plan["main"] == "a5"
    assert plan["mapping"] == {"a3": THU_TINH, "a6": SHOP}
    actions = {(s["id"], s["account"]): (s["action"], s["identity"]) for s in plan["scenarios"]}
    assert actions == {("k1", "a3"): ("tach", THU_TINH), ("k2", "a6"): ("doi", SHOP),
                       ("k3", "a3"): ("bo_trung", THU_TINH)}
    assert sorted(plan["logout"]) == ["a3", "a6"]
    assert plan["backup"].startswith("sao_luu/config.truoc_gop_") and plan["backup"].endswith(".json")   # vong 2 (3.10g)
    assert plan["lines"] and all(isinstance(x, str) and x.strip() for x in plan["lines"])
    text = "\n".join(plan["lines"])
    assert "Thư Tình" in text and "Shop Mèo" in text


def test_merge_plan_copies_tro_vao_identity_dir(data, tool_dir):
    (acc_dir(tool_dir, "a3") / "ket_qua.json").write_text(json.dumps(results("abc", 1)), encoding="utf-8")
    plan = tool_store.merge_plan(data, "a5", ["a3", "a6"])
    pairs = [(str(a), str(b)) for a, b in plan["copies"]]
    want_src = str(tool_dir / "accounts" / "a3" / "ket_qua.json")
    want_dst = str(tool_dir / "accounts" / "a5" / "danh_tinh" / THU_TINH / "ket_qua.json")
    assert (want_src, want_dst) in pairs
    for _src, dst in pairs:
        assert "danh_tinh" in dst   # tk phu la Page -> dich la thu muc Page


def test_merge_plan_khac_uid_loi(data):
    plan = tool_store.merge_plan(data, "a5", ["a2"])
    assert plan["ok"] is False and plan["errors"]


def test_merge_plan_khong_thay_page(data, tool_dir):
    profile(tool_dir, "a6", "Page Lạ", "222")
    plan = tool_store.merge_plan(data, "a5", ["a3", "a6"])
    assert plan["ok"] is False
    assert any("Không thấy Page 'Page Lạ'" in e and "Đọc danh sách Page" in e for e in plan["errors"])


def test_merge_plan_tk_phu_khong_ten(data, tool_dir):
    profile(tool_dir, "a6", "", "222")
    plan = tool_store.merge_plan(data, "a5", ["a6"])
    assert plan["ok"] is False and plan["errors"]


def test_merge_plan_ten_ca_nhan_la_self(data, tool_dir):
    """Vong 2 (3.10b): tk phu ghep ra Ca nhan cua main (2 tai khoan tool cung la Ca nhan) -> LOI, khong gop im lang."""
    profile(tool_dir, "a6", "trần thị năm", "222")
    plan = tool_store.merge_plan(data, "a5", ["a6"])
    assert plan["ok"] is False and plan["mapping"] == {}
    assert any("đang là Cá nhân của nick" in e for e in plan["errors"])


@pytest.mark.parametrize("main, others", [("a99", ["a3"]), ("a5", ["a99"])])
def test_merge_plan_id_khong_co_valueerror(data, main, others):
    with pytest.raises(ValueError):
        tool_store.merge_plan(data, main, others)


# ------------------------------------------------------------------ merge_accounts
def test_merge_accounts_day_du(data, tool_dir):
    a3, a5, a6 = (acc_dir(tool_dir, x) for x in ("a3", "a5", "a6"))
    (a3 / "ket_qua.json").write_text(json.dumps(results("abc", 100)), encoding="utf-8")
    (a3 / "xin_vao_nhom.json").write_text(json.dumps({"abc": {"status": "joined"}}), encoding="utf-8")
    (a3 / "da_binh_luan_cham.txt").write_text("bai1\n", encoding="utf-8")
    (a3 / "commented_ids.txt").write_text("p1\np2\n", encoding="utf-8")
    (a5 / "commented_ids.txt").write_text("p2\np3\n", encoding="utf-8")
    (a5 / "ket_qua.json").write_text(json.dumps(results("xyz", 5)), encoding="utf-8")   # cua Ca nhan a5
    # dich da co du lieu (Shop Meo da tung chay o a5) -> gop
    shop_dir = a5 / "danh_tinh" / SHOP
    shop_dir.mkdir(parents=True)
    (shop_dir / "ket_qua.json").write_text(json.dumps(results("abc", 200)), encoding="utf-8")
    (a6 / "ket_qua.json").write_text(json.dumps(results("abc", 300)), encoding="utf-8")
    a3_before = {p.name: p.read_bytes() for p in a3.iterdir()}
    cfg_before = (tool_dir / "config.json").read_text(encoding="utf-8")

    out = tool_store.merge_accounts(data, "a5", ["a3", "a6"], STAMP)
    assert out.get("done") is True and out["ok"] is True

    # (1) backup = config.json truoc khi gop
    backup = tool_dir / "sao_luu" / f"config.truoc_gop_{STAMP}.json"
    assert backup.exists() and backup.read_text(encoding="utf-8") == cfg_before

    # (2) du lieu chep sang thu muc danh tinh; Ca nhan a5 giu nguyen
    tt = a5 / "danh_tinh" / THU_TINH
    assert json.loads((tt / "ket_qua.json").read_text(encoding="utf-8"))["sent"]["abc"][0][0] == 100
    assert json.loads((tt / "xin_vao_nhom.json").read_text(encoding="utf-8")) == {"abc": {"status": "joined"}}
    assert "bai1" in (tt / "da_binh_luan_cham.txt").read_text(encoding="utf-8")
    merged = json.loads((shop_dir / "ket_qua.json").read_text(encoding="utf-8"))
    assert sorted(e[0] for e in merged["sent"]["abc"]) == [200, 300]
    assert json.loads((a5 / "ket_qua.json").read_text(encoding="utf-8")) == results("xyz", 5)
    ids = set((a5 / "commented_ids.txt").read_text(encoding="utf-8").split())
    assert ids == {"p1", "p2", "p3"}            # commented_ids theo NICK, gop vao accounts/<chinh>/
    assert not (tt / "commented_ids.txt").exists()

    # tk phu: khong xoa / sua gi (ngoai da_gop.json)
    assert {p.name: p.read_bytes() for p in a3.iterdir() if p.name != tool_store.MERGE_MARKER} == a3_before
    marker = json.loads((a3 / tool_store.MERGE_MARKER).read_text(encoding="utf-8"))
    assert marker["into"] == "a5" and marker["identity"] == THU_TINH and marker["time"]
    assert json.loads((a6 / tool_store.MERGE_MARKER).read_text(encoding="utf-8"))["identity"] == SHOP

    # (4) tk phu bien mat
    ids_left = [a["id"] for a in data["accounts"]]
    assert "a3" not in ids_left and "a6" not in ids_left
    assert ids_left == ["a4", "a2", "a5", "a7"]
    for s in data["scenarios"]:
        assert "a3" not in s["accounts"] and "a6" not in s["accounts"]
        assert "a3" not in s["members"] and "a6" not in s["members"]


def test_merge_accounts_kich_ban(data):
    tool_store.merge_accounts(data, "a5", ["a3", "a6"], STAMP)
    # doi: a6 -> a5 tai cho, giu id muc + gio rieng, Dang bang Shop Meo
    k2 = find(data, "k2")
    assert k2["accounts"] == ["a7", "a5"]
    assert k2["members"]["a5"] == "c4" and k2["members"]["a7"] == "c3"
    assert k2["member_times"].get("a5") == ["09:00"] and "a6" not in k2["member_times"]
    assert k2["post_as"]["a5"] == SHOP
    # bo_trung: k3 chi con a5 bang Thu Tinh, muc cu cua a5 giu
    k3 = find(data, "k3")
    assert k3["accounts"] == ["a5"] and k3["members"] == {"a5": "m1"} and k3["post_as"] == {"a5": THU_TINH}
    # tach: k1 giu a5 Ca nhan; kich ban moi 'Bài 1 (Thư Tình)' chi tick a5 bang Thu Tinh, giu id muc c2 cua a3
    k1 = find(data, "k1")
    assert k1["accounts"] == ["a5"] and k1["members"] == {"a5": "c1"}
    assert k1["post_as"].get("a5", "self") == "self"
    new = [s for s in data["scenarios"] if s["name"] == "Bài 1 (Thư Tình)"]
    assert len(new) == 1
    s = new[0]
    assert s["id"] not in ("k1", "k2", "k3", "k4") and s["kind"] == "post"
    assert s["accounts"] == ["a5"] and s["members"] == {"a5": "c2"} and s["post_as"] == {"a5": THU_TINH}
    assert s["settings"]["share_text"] == find(data, "k1")["settings"]["share_text"]
    # k4 khong lien quan
    assert find(data, "k4")["accounts"] == ["a2"]
    # materialize sau gop: muc ra dung danh tinh
    tool_store.materialize(data)
    a5 = next(a for a in data["accounts"] if a["id"] == "a5")
    by_id = {c["id"]: c for c in a5["campaigns"]}
    assert by_id["c2"]["post_as"] == THU_TINH and by_id["c2"]["post_as_name"] == "Thư Tình"
    assert by_id["c4"]["post_as"] == SHOP and by_id["c1"]["post_as"] == "self"
    assert by_id["m1"]["post_as"] == THU_TINH


def test_merge_accounts_a2_vao_a4(data, tool_dir):
    out = tool_store.merge_accounts(data, "a4", ["a2"], STAMP)
    assert out["done"] is True and out["mapping"] == {"a2": HTX}
    k4 = find(data, "k4")
    assert k4["accounts"] == ["a4"] and k4["members"] == {"a4": "c5"} and k4["post_as"] == {"a4": HTX}
    assert "a2" not in [a["id"] for a in data["accounts"]]
    assert (tool_dir / "accounts" / "a2" / tool_store.MERGE_MARKER).exists()


def test_merge_accounts_plan_loi_khong_lam_gi(data, tool_dir):
    before = copy.deepcopy(data)
    plan = tool_store.merge_plan(data, "a5", ["a2"])
    assert plan["ok"] is False
    try:
        tool_store.merge_accounts(data, "a5", ["a2"], STAMP, plan=plan)
    except ValueError:
        pass
    assert data == before
    assert not (tool_dir / "sao_luu" / f"config.truoc_gop_{STAMP}.json").exists()
    assert not (tool_dir / "accounts" / "a2" / tool_store.MERGE_MARKER).exists()


def test_merge_accounts_chep_loi_raise_oserror(data, tool_dir):
    (acc_dir(tool_dir, "a3") / "ket_qua.json").write_text(json.dumps(results("abc", 1)), encoding="utf-8")
    plan = tool_store.merge_plan(data, "a5", ["a3"])
    assert plan["ok"] is True
    # dich bi chan: accounts/a5/danh_tinh la FILE -> khong tao duoc thu muc Page
    block = tool_dir / "accounts" / "a5" / "danh_tinh"
    if block.is_dir():
        import shutil
        shutil.rmtree(block)
    block.write_text("chan", encoding="utf-8")
    cfg_before = (tool_dir / "config.json").read_text(encoding="utf-8")
    with pytest.raises(OSError):
        tool_store.merge_accounts(data, "a5", ["a3"], STAMP, plan=plan)
    assert (tool_dir / "config.json").read_text(encoding="utf-8") == cfg_before   # config chua luu
    assert (tool_dir / "sao_luu" / f"config.truoc_gop_{STAMP}.json").exists()                  # backup con


def test_merge_accounts_tam_nghi_lau_hon(data, tool_dir):
    """Tk phu dang tam nghi lau hon -> tai khoan chinh nghi toi cung luc (PM cau 5: nghi ca nick)."""
    a5, a6 = acc_dir(tool_dir, "a5"), acc_dir(tool_dir, "a6")
    assert fb_login.nick_pause(a5) is None
    info = fb_login.pause_nick(a6, "Facebook giới hạn", hours=100)
    tool_store.merge_accounts(data, "a5", ["a6"], STAMP)
    got = fb_login.nick_pause(a5)
    assert got is not None and float(got["until"]) >= info["until"] - 1


def test_merge_accounts_tam_nghi_ngan_hon_khong_rut(data, tool_dir):
    a5, a6 = acc_dir(tool_dir, "a5"), acc_dir(tool_dir, "a6")
    main = fb_login.pause_nick(a5, "Facebook giới hạn", hours=100)
    fb_login.pause_nick(a6, "Facebook giới hạn", hours=1)
    tool_store.merge_accounts(data, "a5", ["a6"], STAMP)
    assert float(fb_login.nick_pause(a5)["until"]) >= main["until"] - 1


# ------------------------------------------------------------------ merged_leftovers
def test_merged_leftovers(data, tool_dir):
    tool_store.merge_accounts(data, "a5", ["a3", "a6"], STAMP)
    assert tool_store.merged_leftovers(data) == []         # chua co browser_profile
    (tool_dir / "accounts" / "a3" / "browser_profile").mkdir()
    assert tool_store.merged_leftovers(data) == ["a3"]
    # id con trong config (vd marker sot lai) -> khong tinh
    (tool_dir / "accounts" / "a5" / tool_store.MERGE_MARKER).write_text(
        json.dumps({"into": "a9", "identity": "self", "time": time.time()}), encoding="utf-8")
    (tool_dir / "accounts" / "a5" / "browser_profile").mkdir()
    assert tool_store.merged_leftovers(data) == ["a3"]


def test_merged_leftovers_khong_co_gi(tool_dir):
    assert tool_store.merged_leftovers({"accounts": [], "scenarios": []}) == []
