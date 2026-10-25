# 001 – Đóng gói chỉ chép đúng file cần gửi khách

Trạng thái: **Đang làm** (plan + hợp đồng đã chốt)
PM chốt ngày: 25/10/2026 – "chỉ dùng các file trong FacebookTool"

## 1. Mục tiêu
`dong_goi.ps1` chỉ chép **danh sách file được phép** sang `FacebookTool_GuiKhach/`, thay vì chép mọi file trừ vài file bị loại. Khách không còn nhận nhật ký, cấu hình cũ hay file nội bộ của người bán.

Hiện tại (25/10/2026) bản gửi khách đang mang theo: `log.txt` (nhật ký thật, có tên nhóm / link bài), `config.truoc_kich_ban.json` (cấu hình cũ, có thể có token Telegram), `soan_tin_cu.json`, `giao_dien.json`, và từ nay cả `CLAUDE.md`, `.gitignore`.

## 2. Phạm vi
- Làm: đổi cách chọn file trong `dong_goi.ps1` sang danh sách cho phép. In ra danh sách file đã chép, cảnh báo nếu thiếu file bắt buộc.
- Không làm: đổi cách biên dịch `.pyc`, PyArmor / exe, đổi `setup.ps1`.

## 3. Hợp đồng
| Loại | Tên | Chi tiết |
|---|---|---|
| File không phải mã nguồn | `$Allow` trong `dong_goi.ps1` (mẫu tên) | `*.bat`, `*.ps1` (trừ `dong_goi.ps1`), `requirements.txt`, `HUONG_DAN.md`, `BAN_QUYEN.txt`. Hiện tại = `CAI_DAT.bat`, `MO_TOOL.bat`, `CHUYEN_SANG_TOOL_GOP.bat`, `QUAY_LAI_TOOL_CU.bat`, `setup.ps1`, `chuyen_sang.ps1` + 3 file kia |
| Mã nguồn | `.pyc` | Biên dịch **mọi `*.py` ở thư mục gốc**, không bỏ file nào. Bắt buộc phải có `main.pyc`, `cau_hinh.pyc`, `tool_gui.pyc` (cửa vào) |
| Không bao giờ gửi | (mọi file không khớp `$Allow`) | `log.txt`, `config*.json`, `license.key`, `soan_tin_cu.json`, `giao_dien.json`, `CLAUDE.md`, `.gitignore`, `dong_goi.ps1`, mọi thư mục con |
| Kết quả | thư mục `-Out` | Chỉ có các file trên, không có thư mục con. Thiếu file bắt buộc → in lỗi, thoát mã 1 |
| Không đổi | tham số, đường dẫn mặc định | `-Out` như cũ, mặc định `../FacebookTool_GuiKhach`; thư mục gốc tool không còn `.pyc` sau khi chạy |

## 4. Chia việc
| Vai | Nhánh | File được sửa | Việc |
|---|---|---|---|
| Dev A | feat/001-dong-goi | `dong_goi.ps1` | danh sách cho phép + báo thiếu file |
| Tester | test/001-dong-goi | `tests/test_001_dong_goi.py` | chạy `dong_goi.ps1 -Out <tmp>` rồi kiểm tra nội dung thư mục |

(Việc nhỏ, chỉ 1 file → 1 Dev. Dùng để chạy thử nguyên vòng quy trình.)

## 5. Tiêu chí xong
- [ ] Thư mục kết quả không có: `*.py`, `log.txt`, `config*.json`, `soan_tin_cu.json`, `giao_dien.json`, `license.key`, `CLAUDE.md`, `.gitignore`, thư mục con nào.
- [ ] Có đủ: `.pyc` của **mọi** `.py` ở thư mục gốc (hiện 13 file: `main`, `cau_hinh`, `chuyen_du_lieu`, `fb_upstt`, `fb_monitor_v4`, `fb_login`, `tool_gui`, `gui_common`, `tool_store`, `upstt_store`, `monitor_store`, `ban_quyen`, `account_status`) + mọi file khớp `$Allow` (hiện 9 file).
- [ ] Thư mục gốc tool không còn `.pyc` sau khi đóng gói (giữ hành vi cũ).
- [ ] Bản đóng gói cài và mở được giao diện trên máy sạch (test tay).

## 6. Checklist test tay
| # | Bước | Mong đợi | Kết quả |
|---|---|---|---|
| 1 | Chạy `dong_goi.ps1` | In danh sách file đã chép, không cảnh báo | |
| 2 | Mở `FacebookTool_GuiKhach/` | Đúng danh sách ở mục 5 | |
| 3 | Chép sang máy / thư mục khác, chạy `CAI_DAT.bat` rồi `MO_TOOL.bat` | Giao diện mở, hiện màn bản quyền | |

## 7. Quyết định của PM (25/10/2026)
PM: "gửi hết, không bỏ file nào" (của tool).
1. File chuyển từ 2 tool cũ (`CHUYEN_SANG_TOOL_GOP.bat`, `QUAY_LAI_TOOL_CU.bat`, `chuyen_sang.ps1`, `chuyen_du_lieu.py`): **gửi**.
2. `cau_hinh.py`: **gửi** (bắt buộc – cửa mở giao diện: `MO_TOOL.bat` → `setup.ps1 -Action gui` → `cau_hinh.py` → `tool_gui.main()`).
3. Mã nguồn: **mọi `*.py` ở thư mục gốc**, không bỏ file nào. Module mới thêm sau này tự được gửi.
4. File khác: theo **mẫu tên** (`*.bat`, `*.ps1` trừ `dong_goi.ps1`, + 3 file tài liệu), nên `.bat` / `.ps1` mới cũng tự được gửi.
5. Dữ liệu / bí mật / file nội bộ vẫn KHÔNG gửi (xem bảng Hợp đồng) – đây là mục tiêu của việc 001.

## 8. Tiến độ
| Thời gian | Bước | Vai | Nhánh / commit | Kết quả |
|---|---|---|---|---|
| 25/10 | 1 Lập kế hoạch | Architect + PM | main | PM chốt: gửi hết file của tool, không gửi dữ liệu / bí mật |
| 25/10 | 2 Dựng khung | Architect | main | Hợp đồng nằm ở mục 3 (chỉ 1 file `.ps1`, không cần hàm rỗng). Chờ commit |
| | 3 Dev A | Dev | feat/001-dong-goi | |
| | 3 Tester | Tester | test/001-dong-goi | |
| | 4 Review | Reviewer | | |
| | 5 Merge | PM | main | |
