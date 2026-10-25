# © 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền.
# Nghiêm cấm sao chép, chia sẻ, chỉnh sửa hoặc bán lại khi chưa có sự đồng ý bằng văn bản.
"""Khung task 003 (Architect): config cu (chua co danh tinh) van mo duoc, mac dinh = Ca nhan.

Chi kiem phan khung + tuong thich nguoc. Test tinh nang viet o tests/test_003_*.py (Tester).
"""
import json

import fb_login
import monitor_store
import tool_store
import upstt_store

OLD_CONFIG = {
    "accounts": [{"id": "a1", "name": "Tài khoản 1", "campaigns": []}],
    "scenarios": [{"id": "k1", "name": "Bài 1", "kind": "post", "enabled": True, "accounts": ["a1"],
                   "members": {"a1": "c1"}, "settings": {"groups": [], "share_text": "x", "times": ["06:30"]}}],
}


def test_mac_dinh_danh_tinh_la_ca_nhan():
    assert upstt_store.CAMPAIGN_DEFAULTS["post_as"] == "self"
    assert monitor_store.CAMPAIGN_DEFAULTS["post_as"] == "self"
    assert fb_login.IDENTITY_SELF == "self"
    assert issubclass(fb_login.IdentitySwitchFailed, RuntimeError)


def test_config_cu_mo_duoc(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(OLD_CONFIG, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(tool_store, "CONFIG_JSON", path)
    data = tool_store.load()
    assert data["accounts"][0]["identities"] == []
    s = data["scenarios"][0]
    assert s["post_as"] == {}
    assert "post_as" not in s["settings"] and "post_as_name" not in s["settings"]


def test_loi_chuyen_danh_tinh_co_dong_nhat_ky():
    error = fb_login.IdentitySwitchFailed("61595395697904", "HTX chó mèo", "khong thay nut", "x_danh_tinh.png")
    assert error.note_text.startswith("⛔ Không chuyển được sang \"HTX chó mèo\"")
    assert error.note_text.endswith("(ảnh: anh_loi/x_danh_tinh.png)")
