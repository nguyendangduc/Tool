# 001 – Đóng gói chỉ chép đúng file cần gửi khách

Trạng thái: **Lập kế hoạch (bản nháp – chờ PM chốt)**
PM chốt ngày: …

## 1. Mục tiêu
`dong_goi.ps1` chỉ chép **danh sách file được phép** sang `FacebookTool_GuiKhach/`, thay vì chép mọi file trừ vài file bị loại. Khách không còn nhận nhật ký, cấu hình cũ hay file nội bộ của người bán.

Hiện tại (25/10/2026) bản gửi khách đang mang theo: `log.txt` (nhật ký thật, có tên nhóm / link bài), `config.truoc_kich_ban.json` (cấu hình cũ, có thể có token Telegram), `soan_tin_cu.json`, `giao_dien.json`, và từ nay cả `CLAUDE.md`, `.gitignore`.

## 2. Phạm vi
- Làm: đổi cách chọn file trong `dong_goi.ps1` sang danh sách cho phép. In ra danh sách file đã chép, cảnh báo nếu thiếu file bắt buộc.
- Không làm: đổi cách biên dịch `.pyc`, PyArmor / exe, đổi `setup.ps1`.

## 3. Hợp đồng
| Loại | Tên | Chi tiết |
|---|---|---|
| Danh sách cho phép | `$Allow` trong `dong_goi.ps1` | `*.pyc` (sinh từ `*.py` ở thư mục gốc) + `CAI_DAT.bat`, `MO_TOOL.bat`, `setup.ps1`, `requirements.txt`, `HUONG_DAN.md`, `BAN_QUYEN.txt` |
| Kết quả | thư mục `-Out` | Chỉ có file trong danh sách cho phép. Thiếu file bắt buộc → thoát mã 1 |

## 4. Chia việc
| Vai | Nhánh | File được sửa | Việc |
|---|---|---|---|
| Dev A | feat/001-dong-goi | `dong_goi.ps1` | danh sách cho phép + báo thiếu file |
| Tester | test/001-dong-goi | `tests/test_001_dong_goi.py` | chạy `dong_goi.ps1 -Out <tmp>` rồi kiểm tra nội dung thư mục |

(Việc nhỏ, chỉ 1 file → 1 Dev. Dùng để chạy thử nguyên vòng quy trình.)

## 5. Tiêu chí xong
- [ ] Thư mục kết quả không có: `*.py`, `log.txt`, `config*.json`, `soan_tin_cu.json`, `giao_dien.json`, `license.key`, `CLAUDE.md`, `.gitignore`, thư mục con nào.
- [ ] Có đủ: `.pyc` của mọi module (`main`, `fb_upstt`, `fb_monitor_v4`, `fb_login`, `tool_gui`, `gui_common`, `tool_store`, `upstt_store`, `monitor_store`, `ban_quyen`, `account_status`…) + các file trong danh sách cho phép.
- [ ] Thư mục gốc tool không còn `.pyc` sau khi đóng gói (giữ hành vi cũ).
- [ ] Bản đóng gói cài và mở được giao diện trên máy sạch (test tay).

## 6. Checklist test tay
| # | Bước | Mong đợi | Kết quả |
|---|---|---|---|
| 1 | Chạy `dong_goi.ps1` | In danh sách file đã chép, không cảnh báo | |
| 2 | Mở `FacebookTool_GuiKhach/` | Đúng danh sách ở mục 5 | |
| 3 | Chép sang máy / thư mục khác, chạy `CAI_DAT.bat` rồi `MO_TOOL.bat` | Giao diện mở, hiện màn bản quyền | |

## 7. Câu hỏi cho PM (cần trả lời trước khi chốt)
1. `CHUYEN_SANG_TOOL_GOP.bat`, `QUAY_LAI_TOOL_CU.bat`, `chuyen_sang.ps1`, `chuyen_du_lieu.py` (chuyển từ 2 tool cũ sang tool gộp): khách mới có cần không, hay chỉ khách cũ?
2. `cau_hinh.py` (giao diện cấu hình kiểu cũ): còn dùng không, có gửi khách không?
3. `account_status.py` và mọi module khác đều cần `.pyc`: lấy **tất cả** `*.py` ở thư mục gốc trừ `dong_goi`, hay liệt kê từng file?
