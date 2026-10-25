# FacebookTool – quy ước cho mọi vai (Architect / Dev / Tester / Reviewer)

Quy trình làm việc: [docs/QUY_TRINH.md](docs/QUY_TRINH.md) – mỗi task chọn **cách chạy 1 / 2 / 3** (mặc định 3: phiên chính làm Dev + test, chỉ Reviewer là agent). Kế hoạch từng việc: `plans/NNN_ten_viec.md` (mẫu: [docs/PLAN_MAU.md](docs/PLAN_MAU.md)). Lộ trình sản phẩm: `../KE_HOACH_THUONG_MAI.md`.

## Kiến trúc (đọc trước khi sửa)
- `main.py`: cửa vào duy nhất (Task Scheduler, setup.ps1, giao diện). Chuyển lệnh sang `fb_upstt.py` (đăng bài, nhóm, chăm bài tự động, tin nhắn) hoặc `fb_monitor_v4.py` (quét nhóm theo dõi, bình luận). Kiểm bản quyền trước mỗi `--once`.
- `tool_store.py`: dữ liệu kịch bản (`scenarios`). Khi lưu, `materialize()` sinh lại `accounts[].campaigns[]` (id cố định). Script chạy đọc qua `upstt_store.py` / `monitor_store.py`.
- `fb_login.py`: mọi thao tác Facebook dùng chung (Chrome của nick, khóa nick, nghỉ nick, nhóm, kết quả, chăm bài, tin nhắn).
- `tool_gui.py` (PostKind / MonitorKind / ToolApp) dựng trên `gui_common.py` (TreeConfigApp, Tk + sv-ttk).
- Dữ liệu từng nick: `accounts/<id>/*.json`. Dữ liệu kịch bản theo dõi: `campaigns/<id>/`.

## Quy ước code
- Đầu file `.py`: 2 dòng bản quyền như các file hiện có.
- Comment, docstring, `print("[TAG] ...")`: **tiếng Việt KHÔNG dấu**. Chữ hiện cho người dùng (giao diện, `fb_login.note(...)`, Telegram): **tiếng Việt CÓ dấu**.
- Hằng số viết HOA ở đầu file, có comment đơn vị (giây / phút / ngày).
- Thêm field cho mục đăng bài / theo dõi: thêm vào `CAMPAIGN_DEFAULTS` (upstt_store / monitor_store) kèm comment. Không đổi tên hay xóa field cũ.
- **Config cũ của khách phải mở được**: dùng `setdefault` hoặc hàm chuyển dữ liệu (xem `migrate_to_scenarios`, `drop_library`), có backup trước khi chuyển.
- Python 3.12 (bản gửi khách là `.pyc`). Thư viện mới phải ghim version trong `requirements.txt` và được PM đồng ý.
- Sửa ít nhất có thể. Không định dạng lại hay đổi tên những chỗ không liên quan đến task (file lớn, dễ đụng nhau).

## An toàn nick + giới hạn sản phẩm
- Mọi thao tác lên Facebook phải có giới hạn số lần và khoảng nghỉ, và khi gặp `fb_login.is_rate_limited` phải gọi `pause_nick`.
- KHÔNG làm (xem kế hoạch): trộn nội dung chống spam, né phát hiện, úp tin, bình luận/nhắn tin hàng loạt cho người lạ, quét SĐT, buff tương tác.
- Agent **không chạy lệnh đăng / bình luận / xin vào / rời nhóm trên nick thật**. Test thật là việc của PM, làm trên nick test + nhóm test.

## Bí mật
Không đọc ra, không chép, không commit: `accounts/`, `config.json*`, `license.key`, `*.pem`, `../_NGUOI_BAN_khong_gui_khach/`. Cần dữ liệu mẫu thì tự tạo trong `tests/`.

## Lệnh
- Chạy test: `python -m pytest tests -q`   (cài: `python -m pip install -r tests/requirements.txt`)
- Mở giao diện: `MO_TOOL.bat`
