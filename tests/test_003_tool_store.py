# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
"""Task 003 - tool_store: danh tinh cua tai khoan + materialize post_as. Viet TU SPEC (plan 003 muc 3.1, 3.7).

Cho Dev B (account_identities, identity_name, update_identities, materialize, reset_pause) va Dev A
(upstt_store.join_state(identity=) dung fb_login.identity_dir). Moi duong dan tro vao tmp_path.
"""
import copy
import json

import pytest

import fb_login
import monitor_store
import tool_store
import upstt_store

HTX = ("61595395697904", "HTX chó mèo")
THU_TINH = ("61500000000002", "Thư Tình")


@pytest.fixture
def tool_dir(tmp_path, monkeypatch):
    """Thu muc tool gia: config.json, accounts/, campaigns/, logs/ deu trong tmp_path."""
    for mod in (tool_store, upstt_store, monitor_store):
        monkeypatch.setattr(mod, "BASE_DIR", tmp_path, raising=False)
        monkeypatch.setattr(mod, "CONFIG_JSON", tmp_path / "config.json", raising=False)
        monkeypatch.setattr(mod, "ACCOUNTS_DIR", tmp_path / "accounts", raising=False)
    monkeypatch.setattr(tool_store, "CAMPAIGNS_DIR", tmp_path / "campaigns")
    monkeypatch.setattr(monitor_store, "CAMPAIGNS_DIR", tmp_path / "campaigns")
    monkeypatch.setattr(tool_store, "LOGS_DIR", tmp_path / "logs")
    (tmp_path / "accounts").mkdir()
    return tmp_path


def write_profile(tool_dir, account_id, name, uid):
    d = tool_dir / "accounts" / account_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "fb_profile.json").write_text(json.dumps({"name": name, "uid": uid, "time": "2026-10-25 10:00"},
                                                  ensure_ascii=False), encoding="utf-8")
    return d


def account(account_id="a1", name="Tài khoản 1", identities=None):
    return dict(monitor_store.ACCOUNT_DEFAULTS, id=account_id, name=name, campaigns=[], group="",
                identities=identities if identities is not None else [])


IDS = [{"id": "self", "name": "Nguyễn Văn Test", "kind": "self"},
       {"id": HTX[0], "name": HTX[1], "kind": "page"},
       {"id": THU_TINH[0], "name": THU_TINH[1], "kind": "page"}]


# ------------------------------------------------------------------ account_identities / identity_name
def test_account_identities_rong_la_ca_nhan(tool_dir):
    write_profile(tool_dir, "a1", "Nguyễn Văn Test", "111")
    acc = account()
    got = tool_store.account_identities(acc)
    assert [(x["id"], x["kind"]) for x in got] == [("self", "self")]
    assert got[0]["name"] == "Nguyễn Văn Test"   # ten tu fb_profile.json
    assert acc["identities"] == []                # khong sua account


def test_account_identities_khong_fb_profile_dung_ten_tai_khoan(tool_dir):
    got = tool_store.account_identities(account(name="Tài khoản 9"))
    assert got == [{"id": "self", "name": "Tài khoản 9", "kind": "self"}]


def test_account_identities_thieu_self_them_o_dau(tool_dir):
    acc = account(identities=[IDS[2], IDS[1]])
    before = copy.deepcopy(acc)
    got = tool_store.account_identities(acc)
    assert got[0]["id"] == "self" and got[0]["kind"] == "self"
    assert [x["id"] for x in got[1:]] == [THU_TINH[0], HTX[0]]
    assert acc == before


def test_account_identities_self_luon_dau(tool_dir):
    acc = account(identities=[IDS[1], IDS[0], IDS[2]])
    got = tool_store.account_identities(acc)
    assert got[0]["id"] == "self" and got[0]["name"] == "Nguyễn Văn Test"
    assert sorted(x["id"] for x in got) == sorted(x["id"] for x in IDS)


def test_account_identities_thieu_field_khong_raise(tool_dir):
    acc = {"id": "a1", "name": "Tài khoản 1"}   # config rat cu: khong co ca "identities"
    got = tool_store.account_identities(acc)
    assert got[0]["id"] == "self"


def test_identity_name(tool_dir):
    acc = account(identities=list(IDS))
    assert tool_store.identity_name(acc, "self") == "Nguyễn Văn Test"
    assert tool_store.identity_name(acc, HTX[0]) == HTX[1]
    assert tool_store.identity_name(acc, "61599999999999") == ""
    assert tool_store.identity_name(account(identities=[]), HTX[0]) == ""


# ------------------------------------------------------------------ update_identities
def test_update_identities_lan_dau(tool_dir):
    acc = account()
    out = tool_store.update_identities(acc, copy.deepcopy(IDS))
    assert [x["id"] for x in acc["identities"]] == ["self", HTX[0], THU_TINH[0]]
    assert sorted(out["added"]) == sorted([HTX[1], THU_TINH[1]])
    assert out["renamed"] == [] and out["missing"] == []


def test_update_identities_doi_ten_giu_id_va_thu_tu(tool_dir):
    acc = account(identities=copy.deepcopy(IDS))
    found = [IDS[0], {"id": THU_TINH[0], "name": "Thư Tình Mới", "kind": "page"}, IDS[1]]
    out = tool_store.update_identities(acc, found)
    assert [x["id"] for x in acc["identities"]] == ["self", HTX[0], THU_TINH[0]]   # giu thu tu cu
    assert acc["identities"][2]["name"] == "Thư Tình Mới"
    assert [tuple(x) for x in out["renamed"]] == [(THU_TINH[1], "Thư Tình Mới")]
    assert out["added"] == []


def test_update_identities_page_moi_o_cuoi(tool_dir):
    acc = account(identities=copy.deepcopy(IDS[:2]))
    new = {"id": "61500000000003", "name": "Shop Mèo", "kind": "page"}
    out = tool_store.update_identities(acc, [IDS[0], new, IDS[1]])
    assert [x["id"] for x in acc["identities"]] == ["self", HTX[0], "61500000000003"]
    assert out["added"] == ["Shop Mèo"]


def test_update_identities_page_mat_giu_lai_missing(tool_dir):
    acc = account(identities=copy.deepcopy(IDS))
    out = tool_store.update_identities(acc, [IDS[0], IDS[1]])
    gone = next(x for x in acc["identities"] if x["id"] == THU_TINH[0])
    assert gone.get("missing") is True
    assert out["missing"] == [THU_TINH[1]]
    assert not next(x for x in acc["identities"] if x["id"] == HTX[0]).get("missing")
    # thay lai -> bo "missing"
    tool_store.update_identities(acc, copy.deepcopy(IDS))
    assert not next(x for x in acc["identities"] if x["id"] == THU_TINH[0]).get("missing")


@pytest.mark.parametrize("found", [[], [IDS[1]]])
def test_update_identities_found_rong_hoac_thieu_self(tool_dir, found):
    acc = account(identities=copy.deepcopy(IDS))
    before = copy.deepcopy(acc)
    with pytest.raises(ValueError):
        tool_store.update_identities(acc, found)
    assert acc == before


# ------------------------------------------------------------------ materialize post_as / post_as_name
def config(post_as=None, kind="post"):
    settings = {}
    tool_store._fill(settings, tool_store.settings_defaults(kind))
    if kind == "post":
        settings.update(groups=["https://www.facebook.com/groups/abc/"], share_text="x", times=["06:30"])
    s = {"id": "k1", "name": "Bài 1", "kind": kind, "enabled": True, "accounts": ["a1", "a2"],
         "gap_minutes": 15, "members": {"a1": "c1", "a2": "c2"}, "member_times": {}, "settings": settings}
    if post_as is not None:
        s["post_as"] = post_as
    return {"accounts": [account("a1", "Tài khoản 1", copy.deepcopy(IDS)), account("a2", "Tài khoản 2")],
            "scenarios": [s]}


def items(data):
    return {a["id"]: a["campaigns"][0] for a in data["accounts"] if a["campaigns"]}


@pytest.mark.parametrize("kind", ["post", "monitor"])
def test_materialize_ghi_post_as(tool_dir, kind):
    data = config({"a1": HTX[0]}, kind=kind)
    tool_store.materialize(data)
    got = items(data)
    assert got["a1"]["post_as"] == HTX[0] and got["a1"]["post_as_name"] == HTX[1]
    assert got["a2"]["post_as"] == "self" and got["a2"]["post_as_name"] == ""   # thieu khoa = Ca nhan
    for key in tool_store.PER_MEMBER_KEYS:
        assert key not in data["scenarios"][0]["settings"]


def test_materialize_ca_nhan_ten_rong(tool_dir):
    data = config({"a1": "self"})
    tool_store.materialize(data)
    assert items(data)["a1"]["post_as"] == "self" and items(data)["a1"]["post_as_name"] == ""


def test_materialize_page_khong_con_giu_id(tool_dir):
    """Page khong con trong tai khoan -> giu nguyen id (luot chay bao missing), KHONG doi sang Ca nhan."""
    data = config({"a1": "61599999999999"})
    tool_store.materialize(data)
    assert items(data)["a1"]["post_as"] == "61599999999999"
    assert items(data)["a1"]["post_as_name"] == ""


def test_materialize_page_missing_van_co_ten(tool_dir):
    data = config({"a1": THU_TINH[0]})
    data["accounts"][0]["identities"][2]["missing"] = True
    tool_store.materialize(data)
    assert items(data)["a1"]["post_as"] == THU_TINH[0]


def test_config_cu_chay_nhu_cu(tool_dir):
    """Config cu (khong identities / post_as) -> load + materialize: moi muc la Ca nhan."""
    old = config()
    for a in old["accounts"]:
        a.pop("identities")
    old["scenarios"][0].pop("post_as", None)
    (tool_dir / "config.json").write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    data = tool_store.load()
    tool_store.materialize(data)
    for item in items(data).values():
        assert item["post_as"] == "self" and item["post_as_name"] == ""
    assert tool_store.account_identities(data["accounts"][1])[0]["id"] == "self"


def test_upstt_store_load_muc_cu_mac_dinh_self(tool_dir):
    data = config()
    tool_store.materialize(data)
    for a in data["accounts"]:
        for c in a["campaigns"]:
            c.pop("post_as", None)
            c.pop("post_as_name", None)
    (tool_dir / "config.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    loaded = upstt_store.load()
    c = loaded["accounts"][0]["campaigns"][0]
    assert c["post_as"] == "self" and c["post_as_name"] == ""


def test_duplicate_scenario_bo_post_as(tool_dir):
    data = config({"a1": HTX[0]})
    dup = tool_store.duplicate_scenario(data, data["scenarios"][0])
    assert dup["post_as"] == {}


# ------------------------------------------------------------------ du lieu theo danh tinh
def test_reset_pause_truyen_identity_cua_muc(tool_dir, monkeypatch):
    calls = []
    for store in (upstt_store, monitor_store):
        monkeypatch.setattr(store, "reset_pause",
                            lambda acc, kind, key, identity="self", _s=store: calls.append((_s.KIND, kind, key, identity)))
    acc = account()
    tool_store.reset_pause(acc, "group", "abc", campaign={"kind": "post", "post_as": HTX[0]})
    tool_store.reset_pause(acc, "group", "xyz", campaign={"kind": "monitor", "post_as": THU_TINH[0]})
    tool_store.reset_pause(acc, "group", "def", campaign={"kind": "post"})
    assert calls == [("post", "group", "abc", HTX[0]), ("monitor", "group", "xyz", THU_TINH[0]),
                     ("post", "group", "def", "self")]


def test_join_state_theo_danh_tinh(tool_dir):
    """Dev A: join_state(identity=<Page>) doc xin_vao_nhom.json o identity_dir, khong lan voi Ca nhan."""
    acc_dir = tool_dir / "accounts" / "a1"
    acc_dir.mkdir()
    (acc_dir / "xin_vao_nhom.json").write_text(json.dumps({"nhom_a": {"status": "joined"}}), encoding="utf-8")
    page_dir = acc_dir / "danh_tinh" / HTX[0]
    page_dir.mkdir(parents=True)
    (page_dir / "xin_vao_nhom.json").write_text(json.dumps({"nhom_b": {"status": "pending"}}), encoding="utf-8")
    assert set(upstt_store.join_state("a1")) == {"nhom_a"}
    assert set(upstt_store.join_state("a1", identity="self")) == {"nhom_a"}
    assert set(upstt_store.join_state("a1", identity=HTX[0])) == {"nhom_b"}
    # Page chua co du lieu -> rong (khong lay cua Ca nhan)
    assert upstt_store.join_state("a1", identity=THU_TINH[0]) == {}


def test_pause_notes_doc_nhom_tam_nghi_cua_danh_tinh(tool_dir, monkeypatch):
    """Dev A: pause_notes(account, campaign) tu lay campaign["post_as"] -> nhom tam nghi cua Page."""
    import time
    monkeypatch.setattr(fb_login, "nick_pause", lambda d: None)
    monkeypatch.setattr(fb_login, "recovering", lambda d: False)
    acc_dir = tool_dir / "accounts" / "a1"
    page_dir = acc_dir / "danh_tinh" / HTX[0]
    page_dir.mkdir(parents=True)
    key = upstt_store.group_key("https://www.facebook.com/groups/abc/")
    st = {"groups": {key: {"until": time.time() + 86400, "reason": "Page lỗi"}}, "pending": {}}
    (page_dir / "nhom_tam_nghi.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    camp = dict(upstt_store.CAMPAIGN_DEFAULTS, id="c1", name="Bài 1", kind="post",
                groups=["https://www.facebook.com/groups/abc/"])
    acc = account()
    assert [n for n in upstt_store.pause_notes(acc, dict(camp, post_as="self")) if n["kind"] == "group"] == []
    page_notes = upstt_store.pause_notes(acc, dict(camp, post_as=HTX[0], post_as_name=HTX[1]))
    assert any(n["kind"] == "group" for n in page_notes)
