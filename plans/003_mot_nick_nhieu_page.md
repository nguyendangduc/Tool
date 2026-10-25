# 003 – Một nick nhiều Page trong MỘT Chrome (F9)

Trạng thái: **Lập kế hoạch (bản nháp – chờ PM chốt)**
PM chốt ngày: …
Phụ thuộc: không (#002 PM gác lại 25/10/2026). Khoá file: `fb_login.py`, `fb_upstt.py`, `upstt_store.py`, `tool_store.py`, `tool_gui.py`, `gui_common.py`, `fb_monitor_v4.py`.

## 1. Mục tiêu
Một nick Facebook = **một** tài khoản trong tool = **một** thư mục Chrome, đăng nhập **một** lần. Bên trong có các danh tính: Cá nhân + các Page nick đó quản lý. Mỗi kịch bản chọn "Đăng bằng" danh tính nào; tool tự chuyển như người thật.

Vì sao: hiện mỗi Page là một tài khoản riêng trong tool (HUONG_DAN.md hướng dẫn vậy) → mỗi Page một Chrome, đăng nhập riêng → Facebook thấy 1 người trên 3 thiết bị. 25/10 13:03 nick …558 bị đá cả 3 phiên (a5, a3, a6) cùng lúc.

## 2. Phạm vi
- Làm:
  1. Tài khoản trong tool có danh sách **danh tính** `[{id, name, kind: "self"|"page"}]`; nút **Đọc danh sách Page** lấy từ Facebook.
  2. Kịch bản đăng bài (và chăm bài) có ô **Đăng bằng** (mặc định: Cá nhân). Tick tài khoản + chọn danh tính cho từng tài khoản.
  3. Lượt chạy: mở Chrome của nick → bảo đảm đang là đúng danh tính → làm việc → **chuyển về Cá nhân** → đóng Chrome.
  4. Trạng thái nhóm (đã vào / chờ duyệt / xác minh), kết quả duyệt bài, chăm bài **tách theo danh tính**.
  5. **Gộp dữ liệu cũ**: tài khoản trùng uid (a3, a6 → a5; a2 → a4) thành danh tính của tài khoản chính; kịch bản đổi theo; kết quả cũ giữ; backup trước khi gộp; đăng xuất + xoá thư mục Chrome thừa (PM bấm xác nhận).
  6. Cảnh báo nếu sau này lại thêm tài khoản trùng uid; sửa HUONG_DAN.md mục "Dùng Page".
- Không làm: giới hạn lượt / giờ đêm (#002, gác lại); giả vân tay, proxy; tự tạo Page.

## 3. Hợp đồng (chốt ở bước Dựng khung – cần PM test tay trước, xem mục 7 câu 1)
| Loại | Tên | Chi tiết |
|---|---|---|
| Field tài khoản | `identities` | `[{"id": "self", "name": "...", "kind": "self"}, {"id": "<page id>", "name": "Thư Tình", "kind": "page"}]` |
| Field kịch bản | `post_as` | `{account_id: identity_id}`, thiếu = `"self"` |
| Hàm | `fb_login.read_identities(page) -> list` | đọc cá nhân + các Page từ menu tài khoản |
| Hàm | `fb_login.switch_identity(page, identity) -> bool` | chuyển sang danh tính; đã đúng thì không làm gì |
| Hàm | `fb_login.current_identity(page) -> str` | danh tính đang dùng |
| File dữ liệu | `accounts/<id>/<identity>/…` hoặc khoá theo identity trong json hiện có | chốt ở Dựng khung |
| Khi lỗi | không chuyển được danh tính | KHÔNG đăng (tránh đăng nhầm cá nhân), ghi nhật ký, ảnh lỗi, bỏ lượt |
| Không đổi | | Cách đăng / xác minh / đọc kết quả / khoá nick hiện có |

## 4. Chia việc (dự kiến)
| Vai | Nhánh | File được sửa | Việc |
|---|---|---|---|
| Dev A | feat/003-danh-tinh | `fb_login.py`, `fb_upstt.py`, `upstt_store.py` | đọc / chuyển danh tính, lượt đăng + chăm bài theo danh tính, trạng thái nhóm theo danh tính |
| Dev B | feat/003-giao-dien | `tool_store.py`, `tool_gui.py`, `gui_common.py` | field mới, gộp dữ liệu cũ, ô Đăng bằng, nút Đọc danh sách Page, cảnh báo trùng uid |
| Dev C (sau A) | feat/003-theo-doi | `fb_monitor_v4.py` | bình luận (chăm bài / theo dõi) bằng đúng danh tính |
| Tester | test/003-danh-tinh | `tests/test_003_*.py`, `tests/trang_gia/` | trang HTML giả menu chuyển Page + hộp "Đăng với tư cách"; test gộp dữ liệu với config giả |

## 5. Tiêu chí xong
- [ ] Mỗi nick chỉ còn 1 thư mục Chrome; không còn 2 tài khoản trong tool cùng uid.
- [ ] Kịch bản "Đăng bằng Thư Tình" → bài lên nhóm dưới tên Thư Tình; xong lượt Chrome đang ở Cá nhân.
- [ ] Không chuyển được danh tính → không đăng gì.
- [ ] Gộp a3, a6 vào a5 không mất kịch bản / kết quả; có backup.
- [ ] Config cũ (chưa có `identities`) mở được, mặc định Cá nhân.

## 6. Checklist test tay (nick test + Page test + nhóm test)
| # | Bước | Mong đợi | Kết quả |
|---|---|---|---|
| 1 | Đọc danh sách Page | Hiện đủ Page nick quản lý | |
| 2 | Đăng ngay bằng Page vào nhóm test | Bài hiện tên Page | |
| 3 | Đăng ngay bằng Cá nhân sau đó | Bài hiện tên cá nhân | |
| 4 | Mở Chrome nick sau lượt chạy | Đang ở Cá nhân | |
| 5 | Page chưa vào nhóm | Tool báo, không đăng bằng cá nhân thay | |

## 7. Câu hỏi cho PM
| # | Câu hỏi | Đề xuất | PM quyết |
|---|---|---|---|
| 1 | Cách chuyển: (A) chọn "Đăng với tư cách" trong hộp đăng của nhóm, hay (B) chuyển cả trang sang Page rồi chuyển về? | Cho thử trên nick test | **B** – chuyển cả trang sang Page (như người thật), xong việc chuyển về Cá nhân |
| 2 | Page chưa vào nhóm thì: bỏ nhóm đó, hay tự xin vào bằng Page? | Bỏ + báo, xin vào làm sau | (chưa trả lời – tạm theo đề xuất) |
| 3 | Gộp "Tai khoan 2", "tai khoan 1" → "Tài khoản 5" và "Tài khoản 3" → "Tài khoản 4" ngay khi cập nhật, hay để bạn bấm nút "Gộp"? | Bạn bấm nút, có hộp xác nhận | **Bấm nút**: tool chỉ hiện cảnh báo "N tài khoản chung 1 nick" + nút **Gộp vào …**; bấm → hộp xác nhận liệt kê việc sẽ làm (Page nào vào đâu, kịch bản đổi ra sao, có backup, Chrome nào bị đăng xuất + xoá) → bấm Gộp mới làm |
| 4 | Theo dõi nhóm + bình luận khách: dùng danh tính nào? | Chọn được như đăng bài | **Như đăng bài**: kịch bản theo dõi chọn danh tính; là Page thì vừa mở Chrome là chuyển sang Page luôn rồi mới quét / bình luận |

Ghi chú: đăng bài, theo dõi, chăm bài, kiểm kết quả của cùng một tài khoản **dùng chung 1 thư mục Chrome** (`accounts/<mã>/browser_profile`, cả `fb_upstt.open_account_context` lẫn `fb_monitor_v4` đều gọi `fb_login.open_context(account_dir)`), và không bao giờ mở cùng lúc (khoá thư mục + `hold_nick`). Vì vậy mỗi lượt phải **tự chuyển đúng danh tính lúc bắt đầu** và **chuyển về Cá nhân lúc kết thúc** – lượt trước để Chrome ở Page nào thì lượt sau không được tin là vẫn ở đó.

## 8. Tiến độ (chỉ Điều phối ghi)
| Thời gian | Bước | Vai | Nhánh / commit | Kết quả |
|---|---|---|---|---|
| 25/10 | 1 Lập kế hoạch | Điều phối | main | Bản nháp, chờ PM trả lời mục 7 |
