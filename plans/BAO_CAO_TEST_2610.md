# Báo cáo test 26/10/2026 – 10 mục PM tự test

> File tạm để theo dõi. **Làm xong hết thì xoá file này** (ghi tóm tắt vào plan của task tương ứng).
> Môi trường lúc test: thư mục `FacebookTool` đang chạy nhánh **`test/003`** (code #003 chưa merge), lịch tự động ĐANG BẬT.

Trạng thái: 🔍 đã phân tích · 🛠 đang sửa · ✅ xong · ❓ cần PM trả lời · 🧪 cần thử trên Facebook thật

| # | Mục | Loại | Nguyên nhân (đã đọc code / dữ liệu) | Cách sửa đề xuất | Task | Trạng thái |
|---|---|---|---|---|---|---|
| 1 | Tắt tool thì lịch có chạy không | Hỏi | **Lịch (đăng bài, quét, tự cập nhật + chăm bài 3 giờ/lần, tin nhắn) chạy bằng Windows Task Scheduler → KHÔNG cần mở tool.** Riêng việc bấm tay trong tool: lệnh đang chạy vẫn chạy tiếp khi đóng tool (`subprocess.Popen` không bị giết), nhưng **việc xếp hàng chưa tới lượt bị mất** (`tool_gui.run_accounts` chỉ chạy việc kế tiếp khi cửa sổ còn mở) và **đóng tool không cảnh báo** (`gui_common.close`) | Đóng tool khi còn việc xếp hàng → hỏi "Còn N việc chưa chạy – vẫn đóng?" | #006 | 🔍 |
| 2 | Chăm bài không chăm, bảng không cập nhật | Lỗi | Dữ liệu thật TK4: `cham_bai.json` có **110/113 bài kẹt "⏳ chờ gửi" (queued)**. `--comment-posts` ghi "queued" trước khi chạy; nếu lệnh bị ngắt / lỗi giữa chừng (đóng tool, nick bận, mất đăng nhập, lỗi Chrome) thì không trả về "lỗi" → `care_candidates` thấy bài đã có trạng thái → **không bao giờ chăm lại**, bảng mãi "chờ gửi" | (a) mọi đường thoát của `--comment-posts` (finally) trả "queued/sending" về "chưa làm"; (b) bài "queued" quá 1 giờ coi như chưa làm; (c) dọn 110 bài kẹt hiện có | #006 | 🔍 |
| 3 | Giới hạn 5 tài khoản → vô hạn | Bản quyền | Không phải code: con số nằm trong **key bản quyền** (trường `n`). ⚠ Key máy này **hết hạn 29/10/2026** | ❓ PM chọn: (A) tạo key mới bằng `tao_key.py` với số lớn (vd 999) + gia hạn – không sửa code; (B) sửa code: `n = 0` nghĩa là không giới hạn, hiện "không giới hạn" | – / #006 | ❓ |
| 4 | Nhóm kịch bản (select box) để lọc | Tính năng | Chưa có. Đã có "Nhóm tài khoản" (`account["group"]`) – làm tương tự cho kịch bản | Field `scenario["group"]` + ô chọn ở kịch bản + ô lọc trên cây "📋 Kịch bản" | #007 | 🔍 |
| 4b | Tiến trình (chăm, cập nhật) có chạy khi tắt tool / chuyển màn khác | Hỏi | Chuyển màn khác: **vẫn chạy**. Tắt tool: xem mục 1 (đang chạy thì chạy tiếp; xếp hàng thì mất) | Như mục 1 + mục 10 (nút tin nhắn bị "kẹt" khi chuyển màn) | #006 | 🔍 |
| 5 | Kết quả chi tiết của tài khoản trong kịch bản liệt kê cả bài của kịch bản khác | Lỗi | Nhật ký lọc đúng theo kịch bản (logs/<id mục>), nhưng chế độ **"Chỉ bài đã duyệt"** (`gui_common.approved_posts`) lấy **mọi bài đã đăng trong các nhóm của kịch bản**, không lọc theo nội dung. Các kịch bản Thiệp cưới (c4, c6, c7) dùng chung nhóm → thấy bài của nhau | Chỉ giữ bài có đoạn đầu khớp nội dung (`share_text`) của kịch bản này (giống `care_candidates`) | #006 | 🔍 |
| 6 | Theo dõi: Facebook ghi bình luận bị từ chối, tool ghi đã duyệt | Lỗi | `fb_login.item_statuses`: không tìm thấy trong mục Chờ / Từ chối / Gỡ thì **mặc định "đã duyệt"**. Khớp bằng đoạn đầu `comment_text`, nhưng bình luận thật có thể dùng `comment_text_2` / chữ đã thay từ khoá → không khớp → bị coi là đã duyệt | Khớp theo **chữ thật đã gửi** (ghi vào `record_sent`), không theo mẫu; không khớp được thì "chưa rõ" thay vì "đã duyệt" | #006 | 🧪 cần xem 1 nhóm thật |
| 7 | Bộ lọc bảng Kết quả chi tiết quá nhiều giá trị | Giao diện | Lọc theo cột "Kết quả" / "Hiện tại" lấy **nguyên chữ từng dòng** (vd "Bị từ chối – thêm 1 bài (Facebook đang ghi tổng 4)") → mỗi dòng 1 giá trị | Gom về nhóm cố định: Đã đăng · Chờ duyệt · Bị từ chối · Bị gỡ · Lỗi · Bỏ qua (đăng bài); Đã bình luận · Chưa bình luận được · Khách mới (theo dõi) | #007 | ❓ PM chốt danh sách |
| 8 | Cây Kịch bản: mục đang chọn phải bôi đậm | Giao diện | Treeview mất màu chọn khi bấm sang khung bên phải (mất focus) | Style màu chọn cả khi không focus | #007 | 🔍 |
| 9 | Chrome của tài khoản đang chạy → thêm nút tắt Chrome / tiến trình | Tính năng | Đã có hàm `close_login_window`, `account_process_alive` nhưng chỉ dùng cho cửa sổ đăng nhập | Khi báo "tài khoản đang bận": thêm nút **"⏹ Dừng việc đang chạy"** (giết tiến trình tool + Chrome của đúng tài khoản đó, nhả khoá nick) | #007 | 🔍 |
| 10 | Kiểm tra tin nhắn không thấy tin mới | Lỗi | `tin_nhan.json` TK4: lần đọc cuối **24/10 20:47** – từ đó không lần nào đọc xong. (a) Nút "Kiểm tra ngay": chuyển màn khác khi đang chạy → id tài khoản kẹt trong `_inbox_checks` → **bấm lại không làm gì** cho tới khi mở lại tool (`gui_common.py` ~3494); (b) lỗi của lệnh bị bỏ (`stdout=DEVNULL`) → không biết vì sao không đọc được; (c) lịch tự động: `inbox.enabled = False` | Sửa (a); ghi lỗi ra nhật ký; 🧪 chạy thử `--check-inbox --account a4` để xem lỗi thật (có thể Facebook đổi giao diện hộp thư như đã đổi nút tài khoản) | #006 | 🧪 |

## Chia task (đề xuất)
- **#006 – Sửa lỗi** (2, 5, 6, 10 + cảnh báo đóng tool 1/4b): `fb_monitor_v4.py`, `fb_login.py`, `gui_common.py`.
- **#007 – Giao diện** (4, 7, 8, 9): `tool_store.py`, `tool_gui.py`, `gui_common.py`.
- **Mục 3**: theo lựa chọn PM (A không cần task).
- Làm **sau khi merge #003** (cùng sửa `gui_common.py`, `tool_gui.py`, `fb_login.py`).

## Nhật ký xử lý
| Ngày | Mục | Việc | Kết quả |
|---|---|---|---|
| 26/10 | tất cả | Phân tích code + dữ liệu thật TK4 | Bảng trên |
