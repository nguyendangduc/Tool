# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
"""Task 003 - fb_login: danh tinh (Ca nhan / Page). Viet TU SPEC (plan 003 muc 3.2, 3.3, 3b) - cho Dev A.

Phan Playwright dung trang gia tests/trang_gia/fb_danh_tinh.html phuc vu tai https://www.facebook.com/ qua
context.route: MOI request bi chan / tra trang gia, KHONG ra mang, khong dung Facebook that.
Chromium khong chay duoc -> skip (co ly do).
"""
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import pytest

import fb_login

FAKE_HTML = Path(__file__).resolve().parent / "trang_gia" / "fb_danh_tinh.html"
FB = "https://www.facebook.com/"
SELF_NAME = "Nguyễn Văn Test"
HTX = ("61595395697904", "HTX chó mèo")
THU_TINH = ("61500000000002", "Thư Tình")
SHOT_RE = re.compile(r"^\d{8}_\d{6}_danh_tinh\.png$")


# ------------------------------------------------------------------ khong can trinh duyet
def test_identity_dir_ca_nhan_la_acc_dir(tmp_path):
    for ident in ("self", "", None):
        assert Path(fb_login.identity_dir(tmp_path, ident)) == tmp_path
    assert not (tmp_path / "danh_tinh").exists()   # Ca nhan: khong tao gi, giu file cu


def test_identity_dir_page_la_thu_muc_con_tu_tao(tmp_path):
    path = Path(fb_login.identity_dir(tmp_path, HTX[0]))
    assert path == tmp_path / "danh_tinh" / HTX[0]
    assert path.is_dir()
    # goi lai khong loi (thu muc da co)
    assert Path(fb_login.identity_dir(tmp_path, HTX[0])) == path


@pytest.mark.parametrize("bad", ["../a2", "abc", "12/34", "12\\34", "..", " 123", "123abc", "self/.."])
def test_identity_dir_id_la_bi_chan(tmp_path, bad):
    with pytest.raises(ValueError):
        fb_login.identity_dir(tmp_path, bad)


def test_identity_files_dung_hop_dong():
    assert set(fb_login.IDENTITY_FILES) == {"xin_vao_nhom.json", "nhom_da_vao.json", "ket_qua.json", "cham_bai.json",
                                            "da_binh_luan_cham.txt", "nhom_tam_nghi.json", "binh_luan_loi.json"}
    # Theo NICK (khong duoc tach theo danh tinh)
    for name in ("commented_ids.txt", "tin_nhan.json", "status.json", "fb_profile.json", "kiem_tra_tien_do.json"):
        assert name not in fb_login.IDENTITY_FILES
    assert fb_login.ACCOUNT_MENU_LABELS[0] == "Account, your profile"


def test_note_text_khong_anh():
    error = fb_login.IdentitySwitchFailed(HTX[0], HTX[1], "khong thay nut", "")
    assert error.note_text == fb_login.IDENTITY_NOTES["fail"].format(name=HTX[1], shot="")
    assert "ảnh:" not in error.note_text
    # khong co ten -> dung id
    assert HTX[0] in fb_login.IdentitySwitchFailed(HTX[0], "", "x").note_text


def test_load_identities_file_chua_co_hoac_hong(tmp_path):
    assert fb_login.load_identities_file(tmp_path) == {"time": 0, "identities": []}
    (tmp_path / fb_login.IDENTITIES_FILE).write_text("{hong", encoding="utf-8")
    assert fb_login.load_identities_file(tmp_path) == {"time": 0, "identities": []}


def test_save_load_identities_file(tmp_path):
    ids = [{"id": "self", "name": SELF_NAME, "kind": "self"}, {"id": HTX[0], "name": HTX[1], "kind": "page"}]
    before = time.time()
    fb_login.save_identities_file(tmp_path, ids)
    raw = json.loads((tmp_path / "danh_tinh.json").read_text(encoding="utf-8"))
    assert raw["identities"] == ids
    assert before - 1 <= raw["time"] <= time.time() + 1
    got = fb_login.load_identities_file(tmp_path)
    assert got["identities"] == ids and got["time"] == raw["time"]


def test_save_identities_file_loi_ghi_bo_qua(tmp_path):
    not_dir = tmp_path / "la_file"
    not_dir.write_text("x", encoding="utf-8")
    fb_login.save_identities_file(not_dir, [{"id": "self", "name": "A", "kind": "self"}])   # khong raise


class _BrokenPage:
    """page gia: moi thao tac deu loi (Chrome da dong / treo)."""

    def __getattr__(self, name):
        raise RuntimeError("Target page, context or browser has been closed")


def test_current_identity_loi_cookie_tra_self():
    assert fb_login.current_identity(_BrokenPage()) == "self"


def test_back_to_self_khong_bao_gio_raise():
    assert fb_login.back_to_self(_BrokenPage(), SELF_NAME) in (True, False)


def test_switch_identity_khong_raise():
    assert fb_login.switch_identity(_BrokenPage(), HTX[0], HTX[1]) is False


# ------------------------------------------------------------------ trang gia (Playwright)
@pytest.fixture(scope="module")
def browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        pytest.skip(f"khong co playwright: {error}")
    pw = sync_playwright().start()
    try:
        b = pw.chromium.launch(headless=True)
    except Exception as error:
        pw.stop()
        pytest.skip(f"khong mo duoc chromium cua playwright: {str(error).splitlines()[0]}")
    yield b
    b.close()
    pw.stop()


@pytest.fixture(autouse=True)
def _nhanh(monkeypatch):
    # Trang gia tai lai sau 300 ms -> khong can cho 8 / 30 giay nhu Facebook that.
    monkeypatch.setattr(fb_login, "IDENTITY_SWITCH_WAIT", 1)
    monkeypatch.setattr(fb_login, "IDENTITY_SWITCH_TIMEOUT", 3)


class FakeFb:
    def __init__(self, browser, i_user=None, mode=""):
        self.counts = {"menu": 0, "chuyen": 0, "xem_tat_ca": 0}
        self.hits = []
        self.context = browser.new_context(locale="vi-VN")
        html = FAKE_HTML.read_text(encoding="utf-8")

        def route(r):
            host = urlparse(r.request.url).hostname or ""
            if host == "facebook.com" or host.endswith(".facebook.com"):
                if r.request.resource_type == "document":
                    self.hits.append(r.request.url)
                    r.fulfill(status=200, content_type="text/html; charset=utf-8", body=html)
                else:
                    r.fulfill(status=204, body="")
            else:
                r.abort()

        self.context.route("**/*", route)
        self.context.expose_binding("giaDem", lambda _src, key: self.counts.__setitem__(key, self.counts[key] + 1))
        cookies = [{"name": "c_user", "value": "100000000000001", "domain": ".facebook.com", "path": "/"},
                   {"name": "xs", "value": "gia", "domain": ".facebook.com", "path": "/"}]
        if i_user:
            cookies.append({"name": "i_user", "value": i_user, "domain": ".facebook.com", "path": "/"})
        if mode:
            cookies.append({"name": "gia_mode", "value": mode, "domain": ".facebook.com", "path": "/"})
        self.context.add_cookies(cookies)
        self.page = self.context.new_page()
        self.page.goto(FB)

    def i_user(self):
        return next((c["value"] for c in self.context.cookies(FB) if c["name"] == "i_user"), None)

    def clicks(self):
        return self.counts["menu"] + self.counts["chuyen"] + self.counts["xem_tat_ca"]

    def close(self):
        self.context.close()


@pytest.fixture
def fake(browser):
    made = []

    def make(i_user=None, mode=""):
        f = FakeFb(browser, i_user, mode)
        made.append(f)
        return f

    yield make
    for f in made:
        f.close()


def test_trang_gia_hoat_dong(fake):
    """Tu kiem trang gia (khong phu thuoc Dev): chuyen bang nut -> cookie i_user doi."""
    f = fake()
    f.page.get_by_role("button", name="Account, your profile").click()
    f.page.get_by_role("button", name=f"Chuyển sang {HTX[1]}").click()
    f.page.wait_for_timeout(1200)
    assert f.i_user() == HTX[0]
    assert f.counts["menu"] == 1 and f.counts["chuyen"] == 1


def test_current_identity_ca_nhan(fake):
    f = fake()
    hits = len(f.hits)
    assert fb_login.current_identity(f.page) == "self"
    assert len(f.hits) == hits and f.clicks() == 0   # khong mo trang, khong bam


def test_current_identity_page(fake):
    f = fake(i_user=HTX[0])
    hits = len(f.hits)
    assert fb_login.current_identity(f.page) == HTX[0]
    assert len(f.hits) == hits and f.clicks() == 0


def test_switch_da_dung_ca_nhan_khong_bam(fake):
    f = fake()
    assert fb_login.switch_identity(f.page, "self", SELF_NAME) is True
    assert f.clicks() == 0


def test_switch_da_dung_page_khong_bam(fake):
    f = fake(i_user=HTX[0])
    assert fb_login.switch_identity(f.page, HTX[0], HTX[1]) is True
    assert f.clicks() == 0


def test_switch_sang_page_bang_nut_chuyen_sang(fake):
    f = fake()
    assert fb_login.switch_identity(f.page, HTX[0], HTX[1]) is True
    assert f.i_user() == HTX[0]
    assert fb_login.current_identity(f.page) == HTX[0]


def test_switch_sang_page_qua_hop_chon_trang_ca_nhan(fake):
    """Menu khong co 'Chuyen sang Thu Tinh' -> phai qua 'Xem tat ca trang ca nhan'."""
    f = fake()
    assert fb_login.switch_identity(f.page, THU_TINH[0], THU_TINH[1]) is True
    assert f.i_user() == THU_TINH[0]
    assert f.counts["xem_tat_ca"] >= 1


def test_switch_page_sang_page(fake):
    f = fake(i_user=HTX[0])
    assert fb_login.switch_identity(f.page, THU_TINH[0], THU_TINH[1]) is True
    assert f.i_user() == THU_TINH[0]


def test_switch_ve_ca_nhan(fake):
    f = fake(i_user=HTX[0])
    assert fb_login.switch_identity(f.page, "self", SELF_NAME) is True
    assert f.i_user() is None


def test_switch_that_bai_tra_false(fake):
    f = fake(mode="hong")
    assert fb_login.switch_identity(f.page, HTX[0], HTX[1]) is False
    assert f.i_user() is None


def test_switch_ten_khong_co_tra_false(fake):
    f = fake()
    assert fb_login.switch_identity(f.page, "61599999999999", "Page Không Có") is False
    assert f.i_user() is None


def test_ensure_self_khong_i_user_khong_thao_tac(fake, tmp_path):
    f = fake()
    assert fb_login.ensure_identity(f.page, "self", SELF_NAME, shot_dir=tmp_path) is None
    assert f.clicks() == 0
    assert list(tmp_path.iterdir()) == []


def test_ensure_page_thanh_cong(fake, tmp_path):
    f = fake()
    assert fb_login.ensure_identity(f.page, HTX[0], HTX[1], shot_dir=tmp_path) is None
    assert f.i_user() == HTX[0]
    assert list(tmp_path.glob("*.png")) == []


def test_ensure_self_khi_chrome_dang_o_page(fake, tmp_path):
    """Luot truoc bi os._exit de Chrome o Page -> luot Ca nhan phai tu chuyen ve (3.5 buoc 3)."""
    f = fake(i_user=HTX[0])
    fb_login.ensure_identity(f.page, "self", SELF_NAME, shot_dir=tmp_path)
    assert f.i_user() is None


def test_ensure_that_bai_raise_va_chup_anh(fake, tmp_path):
    f = fake(mode="hong")
    shots = tmp_path / "anh_loi"
    shots.mkdir()
    with pytest.raises(fb_login.IdentitySwitchFailed) as info:
        fb_login.ensure_identity(f.page, HTX[0], HTX[1], shot_dir=shots)
    error = info.value
    assert error.identity_id == HTX[0] and error.name == HTX[1]
    files = [p.name for p in shots.iterdir()]
    assert len(files) == 1 and SHOT_RE.match(files[0]), files
    assert error.shot == files[0]
    assert error.note_text.endswith(f"(ảnh: anh_loi/{files[0]})")


def test_ensure_that_bai_khong_shot_dir(fake):
    f = fake(mode="hong")
    with pytest.raises(fb_login.IdentitySwitchFailed) as info:
        fb_login.ensure_identity(f.page, HTX[0], HTX[1])
    assert info.value.shot == ""


def test_back_to_self_dang_ca_nhan_tra_true_ngay(fake):
    f = fake()
    assert fb_login.back_to_self(f.page, SELF_NAME) is True
    assert f.clicks() == 0


def test_back_to_self_tu_page(fake):
    f = fake(i_user=THU_TINH[0])
    assert fb_login.back_to_self(f.page, SELF_NAME) is True
    assert f.i_user() is None


def test_back_to_self_khong_biet_ten(fake):
    f = fake(i_user=HTX[0])
    assert fb_login.back_to_self(f.page, "") is True
    assert f.i_user() is None


def test_back_to_self_that_bai_tra_false_khong_raise(fake):
    f = fake(i_user=HTX[0], mode="hong")
    assert fb_login.back_to_self(f.page, SELF_NAME) is False


def _brief(items):
    return [{k: x.get(k) for k in ("id", "name", "kind")} for x in items]


EXPECTED = [{"id": "self", "name": SELF_NAME, "kind": "self"},
            {"id": HTX[0], "name": HTX[1], "kind": "page"},
            {"id": THU_TINH[0], "name": THU_TINH[1], "kind": "page"}]


def test_read_identities_tu_ca_nhan(fake):
    f = fake()
    got = fb_login.read_identities(f.page)
    assert _brief(got) == EXPECTED
    assert f.i_user() is None   # luon ket thuc o Ca nhan


def test_read_identities_tu_page(fake):
    f = fake(i_user=HTX[0])
    got = fb_login.read_identities(f.page)
    assert got[0]["id"] == "self" and got[0]["kind"] == "self" and got[0]["name"] == SELF_NAME
    assert sorted(_brief(got)[1:], key=lambda x: x["id"]) == sorted(EXPECTED[1:], key=lambda x: x["id"])
    assert f.i_user() is None


def test_read_identities_mot_page(fake):
    f = fake(mode="mot_page")
    assert _brief(fb_login.read_identities(f.page)) == EXPECTED[:2]
    assert f.i_user() is None


def test_read_identities_loi_raise_runtime(browser):
    """Khong mo duoc menu (trang trong) -> RuntimeError."""
    context = browser.new_context()
    context.route("**/*", lambda r: r.fulfill(status=200, content_type="text/html", body="<html><body></body></html>")
                  if (urlparse(r.request.url).hostname or "").endswith("facebook.com") else r.abort())
    try:
        page = context.new_page()
        page.goto(FB)
        with pytest.raises(RuntimeError) as info:
            fb_login.read_identities(page)
        assert not isinstance(info.value, NotImplementedError)   # NotImplementedError cung la RuntimeError
    finally:
        context.close()
