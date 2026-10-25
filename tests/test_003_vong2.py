# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
"""Task 003 vong 2 (plan muc 3.10): tai khoan Page kieu cu, kiem i_user moi thao tac, Page missing, gop theo page_id.

Khong mo Chrome: page gia chi co cookie i_user; ham bam Facebook (ensure_identity / back_to_self) thay bang ham ghi lai.
"""
import json
import time

import pytest

import fb_login
import fb_upstt
import tool_store

PAGE = "61595395697904"


class FakeContext:
    def __init__(self, i_user=""):
        self.i_user = i_user

    def cookies(self, _url=None):
        out = [{"name": "c_user", "value": "100000000000001"}]
        if self.i_user:
            out.append({"name": "i_user", "value": self.i_user})
        return out


class FakePage:
    def __init__(self, i_user=""):
        self.context = FakeContext(i_user)


@pytest.fixture
def rec(monkeypatch, tmp_path):
    """Ghi lai nhat ky + moi lan chuyen / ve Ca nhan (khong bam Facebook)."""
    calls = {"notes": [], "ensure": [], "back": []}
    monkeypatch.setattr(fb_login, "note", lambda _d, text, once=False: calls["notes"].append(text))

    def ensure(page, ident, name, shot_dir=None):
        calls["ensure"].append(ident)
        page.context.i_user = "" if ident == "self" else ident

    def back(page, name=""):
        calls["back"].append(name)
        page.context.i_user = ""
        return True
    monkeypatch.setattr(fb_login, "ensure_identity", ensure)
    monkeypatch.setattr(fb_login, "back_to_self", back)
    fb_login._RUN_LEGACY.clear()
    return calls


def acc(tmp_path, pages=(), profile=None):
    d = tmp_path / "accounts" / "a1"
    d.mkdir(parents=True)
    if pages is not None:
        ids = [{"id": "self", "name": "Nguyễn Văn A", "kind": "self"}] + [
            {"id": p, "name": f"Page {p}", "kind": "page"} for p in pages]
        if pages:
            (d / fb_login.IDENTITIES_FILE).write_text(json.dumps({"time": 1, "identities": ids}), encoding="utf-8")
    if profile is not None:
        (d / "fb_profile.json").write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
    return d


# ------------------------------------------------------------------ legacy_page_id / self_name_of
def test_legacy_page_id_kieu_cu(tmp_path):
    d = acc(tmp_path)
    assert fb_login.legacy_page_id(FakePage(PAGE), d) == PAGE        # khong danh sach Page + i_user -> kieu cu
    assert fb_login.legacy_page_id(FakePage(""), d) == ""            # dang o Ca nhan


def test_legacy_page_id_da_co_danh_sach_page(tmp_path):
    d = acc(tmp_path, pages=[PAGE])
    assert fb_login.legacy_page_id(FakePage(PAGE), d) == ""          # luot truoc bi ngat, khong phai kieu cu


def test_self_name_of_thu_tu_nguon(tmp_path):
    d = acc(tmp_path, pages=[PAGE], profile={"name": "Tên cũ", "uid": "1"})
    assert fb_login.self_name_of(d) == "Nguyễn Văn A"                # danh_tinh.json truoc
    d2 = acc(tmp_path / "x", profile={"name": "HTX chó mèo", "uid": "1", "page_id": PAGE})
    assert fb_login.self_name_of(d2) == ""                           # ten Page kieu cu -> khong dung
    d3 = acc(tmp_path / "y", profile={"name": "Nguyễn Văn B", "uid": "1", "page_id": ""})
    assert fb_login.self_name_of(d3) == "Nguyễn Văn B"


# ------------------------------------------------------------------ begin / end identity
def test_begin_missing_khong_thao_tac(tmp_path, rec):
    d = acc(tmp_path, pages=[PAGE])
    assert fb_login.begin_identity(FakePage(), d, PAGE, "", tmp_path, "TK1") is None
    assert rec["ensure"] == [] and "không còn trong tài khoản" in rec["notes"][0]


def test_begin_kieu_cu_khong_chuyen_ve_ca_nhan(tmp_path, rec):
    d = acc(tmp_path, profile={"name": "HTX chó mèo", "uid": "1", "page_id": PAGE})
    page = FakePage(PAGE)
    run = fb_login.begin_identity(page, d, "self", "", tmp_path, "TK3")
    assert run == {"id": "self", "expect": PAGE, "name": "HTX chó mèo", "legacy": True}
    assert rec["ensure"] == [] and "tài khoản Page kiểu cũ" in rec["notes"][0]
    assert fb_login.end_identity(page, d, tmp_path) is True
    assert rec["back"] == [] and page.context.i_user == PAGE          # khong bao gio tu ve Ca nhan


def test_kieu_cu_hai_luot_lien_khong_dang_bang_ca_nhan(tmp_path, rec):
    """Loi review vong 1: luot 1 bo + finally keo ve Ca nhan -> luot 2 dang bang Ca nhan. Nay: 2 luot deu o Page."""
    d = acc(tmp_path, profile={"name": "HTX chó mèo", "uid": "1", "page_id": PAGE})
    page = FakePage(PAGE)
    for _ in range(2):
        run = fb_login.begin_identity(page, d, "self", "", tmp_path, "TK3")
        assert run and run["legacy"] and run["expect"] == PAGE
        fb_login.assert_identity(page, run["expect"], run["name"])     # khong raise
        fb_login.end_identity(page, d, tmp_path)
    assert rec["ensure"] == [] and rec["back"] == [] and page.context.i_user == PAGE


def test_begin_page_roi_end_ve_ca_nhan_du_thieu_danh_sach(tmp_path, rec):
    """Luot chuyen sang Page: end_identity theo quyet dinh dau luot (khong doan lai la kieu cu tu cookie)."""
    d = acc(tmp_path)                                                  # khong co danh_tinh.json
    page = FakePage("")
    run = fb_login.begin_identity(page, d, PAGE, "HTX chó mèo", tmp_path, "TK4")
    assert run["expect"] == PAGE and page.context.i_user == PAGE
    assert fb_login.end_identity(page, d, tmp_path) is True and rec["back"] and page.context.i_user == ""


def test_begin_chuyen_loi_bo_luot(tmp_path, rec, monkeypatch):
    def fail(page, ident, name, shot_dir=None):
        raise fb_login.IdentitySwitchFailed(ident, name, "test")
    monkeypatch.setattr(fb_login, "ensure_identity", fail)
    d = acc(tmp_path, pages=[PAGE])
    assert fb_login.begin_identity(FakePage(), d, PAGE, "HTX", tmp_path) is None
    assert rec["notes"] and rec["notes"][0].startswith("⛔ Không chuyển được")


def test_assert_identity_lech_raise(tmp_path):
    with pytest.raises(fb_login.IdentityChanged) as err:
        fb_login.assert_identity(FakePage(""), PAGE, "HTX chó mèo")
    assert "HTX chó mèo" in err.value.note_text
    fb_login.assert_identity(FakePage(PAGE), PAGE, "HTX")              # khop -> khong raise
    fb_login.assert_identity(FakePage(""), "self")


# ------------------------------------------------------------------ dung luot khi danh tinh doi giua chung
def test_post_to_all_groups_dung_khi_danh_tinh_doi(tmp_path, monkeypatch):
    page = FakePage(PAGE)
    posted = []

    def post(_page, url, *_a, **_k):
        posted.append(url)
        page.context.i_user = ""                                       # Facebook tu doi danh tinh sau bai dau
        return fb_upstt.POSTED
    monkeypatch.setattr(fb_upstt, "post_to_group", post)
    monkeypatch.setattr(fb_login, "note", lambda *_a, **_k: None)
    monkeypatch.setattr(fb_login, "record_sent", lambda *_a, **_k: None)
    monkeypatch.setattr(fb_login, "set_verified", lambda *_a, **_k: None)
    monkeypatch.setattr(fb_upstt, "cleanup_error_shots", lambda: None)
    page.wait_for_timeout = lambda _ms: None
    with pytest.raises(fb_login.IdentityChanged):
        fb_upstt.post_to_all_groups(page, ["https://www.facebook.com/groups/1/", "https://www.facebook.com/groups/2/"],
                                    "noi dung", 0, 0, 0, acc_dir=tmp_path, expect_identity=(PAGE, "HTX"))
    assert posted == ["https://www.facebook.com/groups/1/"]           # nhom 2 KHONG dang


# ------------------------------------------------------------------ chon danh tinh trong hop 'Tham gia voi tu cach'
@pytest.mark.parametrize("labels, want, expect", [
    (["Nguyễn A", "HTX chó mèo", "HTX"], "HTX", 2),             # review vong 2 loi C: trung khop hoan toan truoc
    (["Lan Anh Shop", "Lan Anh"], "Lan Anh", 1),                # khong chon nham Ca nhan co ten bat dau giong Page
    (["Nguyễn A", "HTX chó mèo"], "htx  CHÓ mèo", 1),           # bo dau cach thua, khong phan biet hoa thuong
    (["Nguyễn A", "HTX chó mèo (Trang)"], "HTX chó mèo", 1),    # 'bat dau bang' khi chi 1 lua chon khop
    (["HTX chó mèo 1", "HTX chó mèo 2"], "HTX chó mèo", None),  # 2 lua chon cung 'bat dau bang' -> khong doan
    (["Nguyễn A"], "HTX", None),
    (["Nguyễn A", "HTX"], "", None),
])
def test_pick_join_as(labels, want, expect):
    assert fb_login._pick_join_as(labels, want) == expect


# ------------------------------------------------------------------ gioi han xin vao ca nick
def test_nick_join_usage_cong_moi_danh_tinh(tmp_path):
    d = acc(tmp_path)
    now = time.time()
    fb_login.save_join_state(d, {"g1": {"status": "pending", "requested": now - 100}})
    page_dir = fb_login.identity_dir(d, PAGE)
    fb_login.save_join_state(page_dir, {"g2": {"status": "joined", "requested": now - 10},
                                        "g3": {"status": "joined", "requested": now - 3 * 86400}})
    usage = fb_login.nick_join_usage(d)
    assert usage["today"] == 2 and abs(usage["last"] - (now - 10)) < 1


# ------------------------------------------------------------------ materialize + gop theo page_id
def test_materialize_page_missing_ten_rong():
    data = {"accounts": [{"id": "a1", "name": "TK1", "campaigns": [],
                          "identities": [{"id": "self", "name": "A", "kind": "self"},
                                         {"id": PAGE, "name": "HTX", "kind": "page", "missing": True}]}],
            "scenarios": [{"id": "k1", "name": "Bài", "kind": "post", "enabled": True, "accounts": ["a1"],
                           "members": {"a1": "c1"}, "gap_minutes": 0, "post_as": {"a1": PAGE},
                           "settings": {"times": ["08:00"]}}]}
    tool_store.materialize(data)
    item = data["accounts"][0]["campaigns"][0]
    assert item["post_as"] == PAGE and item["post_as_name"] == ""


@pytest.fixture
def gop(tmp_path, monkeypatch):
    acc_root = tmp_path / "accounts"
    monkeypatch.setattr(tool_store, "ACCOUNTS_DIR", acc_root)

    def profile(aid, name, page_id=""):
        (acc_root / aid).mkdir(parents=True, exist_ok=True)
        (acc_root / aid / "fb_profile.json").write_text(json.dumps(
            {"name": name, "uid": "222", "page_id": page_id}, ensure_ascii=False), encoding="utf-8")
    profile("a5", "Nguyễn Đức")
    data = {"accounts": [{"id": "a5", "name": "Tài khoản 5", "campaigns": [],
                          "identities": [{"id": "self", "name": "Nguyễn Đức", "kind": "self"},
                                         {"id": PAGE, "name": "Thư Tình", "kind": "page"}]},
                         {"id": "a3", "name": "Tai khoan 2", "campaigns": []}],
            "scenarios": []}
    return data, profile


def test_merge_plan_ghep_theo_page_id_khi_ten_da_doi(gop):
    data, profile = gop
    profile("a3", "Nguyễn Đức", page_id=PAGE)                          # ten bi ghi de bang ten Ca nhan, id con
    plan = tool_store.merge_plan(data, "a5", ["a3"])
    assert plan["ok"] is True and plan["mapping"] == {"a3": PAGE}


def test_merge_plan_tai_khoan_chinh_kieu_cu_loi(gop):
    data, profile = gop
    profile("a5", "Thư Tình", page_id=PAGE)
    profile("a3", "Nguyễn Đức")
    plan = tool_store.merge_plan(data, "a5", ["a3"])
    assert plan["ok"] is False and any("tài khoản Page kiểu cũ" in e for e in plan["errors"])


def test_default_merge_main_bo_tai_khoan_kieu_cu(gop):
    data, profile = gop
    profile("a5", "Thư Tình", page_id=PAGE)
    profile("a3", "Nguyễn Đức")
    assert tool_store.default_merge_main(data, ["a5", "a3"]) == "a3"
