# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
"""Task 003 - luong mot luot theo danh tinh (plan 003 muc 3.5, 3.6). Viet TU SPEC bang monkeypatch:
khong mo Chrome, khong mang. Moi ham cham Facebook bi thay bang ham gia ghi lai lan goi.

- fb_upstt.run_campaign            -> Dev A
- fb_login.check_results_cli       -> Dev A
- fb_monitor_v4.run_account        -> Dev C
fb_login.ensure_identity / back_to_self / current_identity / identity_dir duoc thay bang ban gia THEO HOP DONG
(khong phu thuoc than ham cua Dev A).
"""
import contextlib
from pathlib import Path

import pytest

import account_status
import fb_login
import monitor_store
import upstt_store

HTX = ("61595395697904", "HTX chó mèo")
THU_TINH = ("61500000000002", "Thư Tình")
GROUP = "https://www.facebook.com/groups/abc/"


class Recorder:
    """Ghi thu tu su kien + gia lap trang thai danh tinh cua Chrome."""

    def __init__(self, start="self", fail_ids=(), back_ok=True):
        self.events = []
        self.state = start
        self.fail_ids = set(fail_ids)
        self.back_ok = back_ok
        self.notes = []
        self.ensure_calls = []
        self.inbox_states = []

    def ensure_identity(self, page, identity_id, name, shot_dir=None):
        self.ensure_calls.append((identity_id, name, shot_dir))
        self.events.append(("ensure", identity_id))
        if identity_id in self.fail_ids:
            raise fb_login.IdentitySwitchFailed(identity_id, name, "gia lap", "20261025_101010_danh_tinh.png")
        self.state = identity_id or "self"

    def back_to_self(self, page, self_name=""):
        self.events.append(("back", self.state))
        if self.back_ok:
            self.state = "self"
        return self.back_ok

    def current_identity(self, page):
        return self.state

    def note(self, _tool_dir, text, once=False):
        self.notes.append(text)


def fake_identity_dir(acc_dir, identity_id):
    if identity_id in ("self", "", None):
        return Path(acc_dir)
    if not str(identity_id).isdigit():
        raise ValueError(identity_id)
    path = Path(acc_dir) / "danh_tinh" / str(identity_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


class FakeContext:
    def __init__(self, rec):
        self.rec = rec

    def close(self):
        self.rec.events.append(("close", self.rec.state))


class FakePage:
    def __getattr__(self, name):
        return lambda *a, **k: None


@contextlib.contextmanager
def fake_playwright():
    yield object()


def common_patches(monkeypatch, tmp_path, rec):
    for mod in (upstt_store, monitor_store):
        monkeypatch.setattr(mod, "ACCOUNTS_DIR", tmp_path / "accounts")
        monkeypatch.setattr(mod, "BASE_DIR", tmp_path)
    monkeypatch.setattr(monitor_store, "CAMPAIGNS_DIR", tmp_path / "campaigns")
    monkeypatch.setattr(fb_login, "ensure_identity", rec.ensure_identity)
    monkeypatch.setattr(fb_login, "back_to_self", rec.back_to_self)
    monkeypatch.setattr(fb_login, "current_identity", rec.current_identity)
    monkeypatch.setattr(fb_login, "identity_dir", fake_identity_dir)
    monkeypatch.setattr(fb_login, "note", rec.note)
    monkeypatch.setattr(fb_login, "use_task_log", lambda *a, **k: None)
    monkeypatch.setattr(fb_login, "hold_nick", lambda *a, **k: True)
    monkeypatch.setattr(fb_login, "release_nick", lambda *a, **k: rec.events.append(("release", rec.state)))
    monkeypatch.setattr(fb_login, "nick_pause", lambda *a, **k: None)
    monkeypatch.setattr(fb_login, "recovering", lambda *a, **k: False)
    monkeypatch.setattr(fb_login, "disk_free_mb", lambda *a, **k: 10 ** 6)
    monkeypatch.setattr(fb_login, "get_page", lambda ctx: FakePage())
    monkeypatch.setattr(fb_login, "open_context", lambda *a, **k: FakeContext(rec))
    monkeypatch.setattr(fb_login, "verify_and_record", lambda *a, **k: None)
    monkeypatch.setattr(fb_login, "groups_due", lambda *a, **k: [])
    monkeypatch.setattr(fb_login, "check_results",
                        lambda page, acc_dir, *a, **k: rec.events.append(("check_results", Path(acc_dir))) or (0, []))

    def inbox(*a, **k):
        rec.inbox_states.append(rec.state)
        rec.events.append(("inbox", rec.state))
    monkeypatch.setattr(fb_login, "check_inbox_page", inbox)
    monkeypatch.setattr(account_status, "usable", lambda *a, **k: True)


def account_with(campaigns):
    return {"id": "a1", "name": "Tài khoản 1", "headless": True, "run_every_minutes": 40, "max_run_minutes": 20,
            "campaigns": campaigns,
            "identities": [{"id": "self", "name": "Nguyễn Văn Test", "kind": "self"},
                           {"id": HTX[0], "name": HTX[1], "kind": "page"},
                           {"id": THU_TINH[0], "name": THU_TINH[1], "kind": "page"}]}


def assert_back_before_close(rec):
    kinds = [e[0] for e in rec.events]
    assert "back" in kinds, rec.events
    assert "close" in kinds, rec.events
    assert kinds.index("back") < len(kinds) - 1 - kinds[::-1].index("close"), rec.events   # back truoc close
    if rec.inbox_states:
        assert set(rec.inbox_states) == {"self"}   # xem tin nhan ke chi khi dang o Ca nhan


# ------------------------------------------------------------------ fb_upstt.run_campaign (Dev A)
@pytest.fixture
def upstt(monkeypatch, tmp_path):
    import fb_upstt
    rec = Recorder()
    common_patches(monkeypatch, tmp_path, rec)
    monkeypatch.setattr(fb_upstt, "BASE_DIR", tmp_path)
    monkeypatch.setattr(fb_upstt, "sync_playwright", fake_playwright)
    monkeypatch.setattr(fb_upstt, "open_account_context", lambda *a, **k: FakeContext(rec))
    monkeypatch.setattr(fb_upstt, "recheck_waiting", lambda *a, **k: [])
    monkeypatch.setattr(fb_upstt, "post_to_all_groups",
                        lambda page, groups, *a, **k: rec.events.append(("post", rec.state)))
    return fb_upstt, rec


def post_campaign(post_as="self", post_as_name=""):
    return dict(upstt_store.CAMPAIGN_DEFAULTS, id="c1", name="Bài 1", kind="post", groups=[GROUP],
                share_text="xin chào", times=["06:30"], post_as=post_as, post_as_name=post_as_name)


def run_upstt(fb_upstt, campaign):
    account = account_with([campaign])
    try:
        fb_upstt.run_campaign(account, campaign)
    except SystemExit as error:
        assert not error.code, f"ma thoat {error.code}"


def test_upstt_page_chuyen_roi_dang_roi_ve(upstt, tmp_path):
    fb_upstt, rec = upstt
    run_upstt(fb_upstt, post_campaign(*HTX))
    assert rec.ensure_calls and rec.ensure_calls[0][:2] == HTX
    assert Path(rec.ensure_calls[0][2]) == tmp_path / "anh_loi"
    assert ("post", HTX[0]) in rec.events                    # dang khi dang o Page
    assert rec.events.index(("ensure", HTX[0])) < rec.events.index(("post", HTX[0]))
    assert fb_login.IDENTITY_NOTES["ok"].format(name=HTX[1]) in rec.notes
    assert_back_before_close(rec)
    assert rec.state == "self"


def test_upstt_chuyen_loi_khong_dang(upstt):
    fb_upstt, rec = upstt
    rec.fail_ids = {HTX[0]}
    run_upstt(fb_upstt, post_campaign(*HTX))                 # bo luot, khong raise (ma thoat 0)
    assert not [e for e in rec.events if e[0] == "post"], rec.events
    error = fb_login.IdentitySwitchFailed(HTX[0], HTX[1], "", "20261025_101010_danh_tinh.png")
    assert error.note_text in rec.notes
    assert_back_before_close(rec)


def test_upstt_ca_nhan_van_goi_ensure(upstt):
    """Nick chi Ca nhan: ensure_identity('self') van goi (luot truoc co the de Chrome o Page), khong ghi 'Dang dung'."""
    fb_upstt, rec = upstt
    run_upstt(fb_upstt, post_campaign())
    assert [c[0] for c in rec.ensure_calls] == ["self"]
    assert ("post", "self") in rec.events
    assert not any(n.startswith("👤") for n in rec.notes)
    assert_back_before_close(rec)


def test_upstt_page_khong_con_bo_luot(upstt):
    fb_upstt, rec = upstt
    run_upstt(fb_upstt, post_campaign("61599999999999", ""))
    assert not [e for e in rec.events if e[0] == "post"]
    assert not [c for c in rec.ensure_calls if c[0] == "61599999999999"]   # khong chuyen
    assert any(n.startswith("⛔ Danh tính") and "không còn trong tài khoản" in n for n in rec.notes), rec.notes


def test_upstt_loi_giua_chung_van_ve_ca_nhan(upstt, monkeypatch):
    fb_upstt, rec = upstt

    def boom(*a, **k):
        rec.events.append(("post", rec.state))
        raise RuntimeError("Chrome treo")
    monkeypatch.setattr(fb_upstt, "post_to_all_groups", boom)
    with contextlib.suppress(Exception):
        run_upstt(fb_upstt, post_campaign(*HTX))
    assert_back_before_close(rec)
    assert rec.state == "self"


def test_upstt_ve_ca_nhan_loi_ghi_back_fail(upstt):
    fb_upstt, rec = upstt
    rec.back_ok = False
    run_upstt(fb_upstt, post_campaign(*HTX))
    assert fb_login.IDENTITY_NOTES["back_fail"] in rec.notes
    assert "close" in [e[0] for e in rec.events]             # van dong Chrome


def test_upstt_tin_nhan_ke_khong_chay_khi_o_page(upstt):
    fb_upstt, rec = upstt
    run_upstt(fb_upstt, post_campaign(*HTX))
    assert HTX[0] not in rec.inbox_states


# ------------------------------------------------------------------ fb_login.check_results_cli (Dev A)
def test_check_results_cli_theo_danh_tinh(monkeypatch, tmp_path):
    rec = Recorder()
    common_patches(monkeypatch, tmp_path, rec)
    monkeypatch.setattr(fb_login, "identity_dir", fake_identity_dir)
    acc = tmp_path / "accounts" / "a1"
    acc.mkdir(parents=True)
    fb_login.check_results_cli(acc, ["abc"], lambda: FakeContext(rec), note=rec.notes.append,
                               identity={"id": HTX[0], "name": HTX[1]})
    assert rec.ensure_calls and rec.ensure_calls[0][:2] == HTX
    assert ("check_results", acc / "danh_tinh" / HTX[0]) in rec.events
    assert (acc / fb_login.PROGRESS_FILE).exists()           # tien do van o acc_dir
    assert_back_before_close(rec)


def test_check_results_cli_chuyen_loi_khong_doc(monkeypatch, tmp_path):
    rec = Recorder(fail_ids={HTX[0]})
    common_patches(monkeypatch, tmp_path, rec)
    acc = tmp_path / "accounts" / "a1"
    acc.mkdir(parents=True)
    with contextlib.suppress(fb_login.IdentitySwitchFailed):
        fb_login.check_results_cli(acc, ["abc"], lambda: FakeContext(rec), note=rec.notes.append,
                                   identity={"id": HTX[0], "name": HTX[1]})
    assert not [e for e in rec.events if e[0] == "check_results"]
    assert_back_before_close(rec)
    progress = fb_login.read_progress(acc)
    assert progress.get("done") is True and progress.get("ok") is False


def test_check_results_cli_ca_nhan_nhu_cu(monkeypatch, tmp_path):
    rec = Recorder()
    common_patches(monkeypatch, tmp_path, rec)
    acc = tmp_path / "accounts" / "a1"
    acc.mkdir(parents=True)
    fb_login.check_results_cli(acc, ["abc"], lambda: FakeContext(rec), note=rec.notes.append)
    assert ("check_results", acc) in rec.events


# ------------------------------------------------------------------ fb_monitor_v4.run_account (Dev C)
@pytest.fixture
def monitor(monkeypatch, tmp_path):
    import fb_monitor_v4
    rec = Recorder()
    common_patches(monkeypatch, tmp_path, rec)
    monkeypatch.setattr(fb_monitor_v4, "BASE_DIR", tmp_path)
    monkeypatch.setattr(fb_monitor_v4, "sync_playwright", fake_playwright)
    monkeypatch.setattr(fb_monitor_v4, "warn_not_joined", lambda *a, **k: None)
    monkeypatch.setattr(fb_monitor_v4, "COMMENTED_IDS_FILE", fb_monitor_v4.COMMENTED_IDS_FILE)
    monkeypatch.setattr(fb_monitor_v4, "SENT_IDS_FILE", fb_monitor_v4.SENT_IDS_FILE)
    monkeypatch.setattr(monitor_store, "scan_due", lambda *a, **k: True)
    monkeypatch.setattr(monitor_store, "mark_scanned", lambda *a, **k: None)
    monkeypatch.setattr(monitor_store, "hang_guard_minutes", lambda *a, **k: 30)
    monkeypatch.setattr(monitor_store, "to_legacy_config", lambda c, *a, **k: {"__id": c["id"]})

    def scan(config, page, *a, **k):
        rec.events.append(("scan", config.get("__id"), rec.state))
    monkeypatch.setattr(fb_monitor_v4, "scan_round", scan)
    return fb_monitor_v4, rec


def mon_campaign(cid, post_as="self", post_as_name=""):
    return dict(monitor_store.CAMPAIGN_DEFAULTS, id=cid, name=f"Theo dõi {cid}", kind="monitor", groups=[GROUP],
                keywords=["mèo"], post_as=post_as, post_as_name=post_as_name)


def test_monitor_chia_theo_danh_tinh(monitor):
    fb_monitor_v4, rec = monitor
    camps = [mon_campaign("m2", *HTX), mon_campaign("m1"), mon_campaign("m3", *THU_TINH), mon_campaign("m4", *HTX)]
    fb_monitor_v4.run_account(account_with(camps), {"accounts": []})
    scans = [(e[1], e[2]) for e in rec.events if e[0] == "scan"]
    # Ca nhan truoc, roi theo thu tu xuat hien; moi muc quet dung danh tinh cua no
    assert scans == [("m1", "self"), ("m2", HTX[0]), ("m4", HTX[0]), ("m3", THU_TINH[0])]
    # ensure 1 lan moi danh tinh
    assert [c[0] for c in rec.ensure_calls] == ["self", HTX[0], THU_TINH[0]]
    assert_back_before_close(rec)


def test_monitor_chuyen_loi_bo_muc_cua_danh_tinh_do(monitor):
    fb_monitor_v4, rec = monitor
    rec.fail_ids = {HTX[0]}
    camps = [mon_campaign("m2", *HTX), mon_campaign("m1"), mon_campaign("m3", *THU_TINH)]
    fb_monitor_v4.run_account(account_with(camps), {"accounts": []})
    scans = [e[1] for e in rec.events if e[0] == "scan"]
    assert scans == ["m1", "m3"]                              # m2 bi bo, danh tinh khac van chay
    assert not [e for e in rec.events if e[0] == "scan" and e[2] == HTX[0]]
    assert fb_login.IdentitySwitchFailed(HTX[0], HTX[1], "", "20261025_101010_danh_tinh.png").note_text in rec.notes
    assert_back_before_close(rec)
    assert ("release", "self") in rec.events


def test_monitor_page_khong_con_bo_muc(monitor):
    fb_monitor_v4, rec = monitor
    camps = [mon_campaign("m1"), mon_campaign("m9", "61599999999999", "")]
    fb_monitor_v4.run_account(account_with(camps), {"accounts": []})
    assert [e[1] for e in rec.events if e[0] == "scan"] == ["m1"]
    assert "61599999999999" not in [c[0] for c in rec.ensure_calls]
    assert any(n.startswith("⛔ Danh tính") for n in rec.notes), rec.notes


def test_monitor_commented_ids_theo_nick(monitor, tmp_path):
    fb_monitor_v4, rec = monitor
    fb_monitor_v4.run_account(account_with([mon_campaign("m2", *HTX)]), {"accounts": []})
    assert Path(fb_monitor_v4.COMMENTED_IDS_FILE) == tmp_path / "accounts" / "a1" / "commented_ids.txt"


def test_monitor_ca_nhan_khong_ghi_dang_dung(monitor):
    fb_monitor_v4, rec = monitor
    fb_monitor_v4.run_account(account_with([mon_campaign("m1")]), {"accounts": []})
    assert [c[0] for c in rec.ensure_calls] == ["self"]
    assert not any(n.startswith("👤") for n in rec.notes)
    assert_back_before_close(rec)


def test_monitor_loi_quet_van_ve_ca_nhan(monitor, monkeypatch):
    fb_monitor_v4, rec = monitor

    def boom(*a, **k):
        raise KeyboardInterrupt   # loi khong bi bat trong vong lap muc
    monkeypatch.setattr(fb_monitor_v4, "scan_round", boom)
    with contextlib.suppress(BaseException):
        fb_monitor_v4.run_account(account_with([mon_campaign("m2", *HTX)]), {"accounts": []})
    assert_back_before_close(rec)
