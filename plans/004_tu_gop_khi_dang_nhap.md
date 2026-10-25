# 004 – Một nick một Chrome tự động (bỏ nút Gộp) + Page không chọn được khi xin vào nhóm

Trạng thái: **Lập kế hoạch (bản nháp – chờ PM chốt)**
PM chốt ngày: …
Phụ thuộc: #003 (đã merge), **#006 + #007 (chưa merge – cùng sửa `gui_common.py`, `tool_gui.py`, `fb_login.py`)** → làm trên nhánh `feat/007-giao-dien`, merge sau #006/#007.
Cách chạy: **2** – đụng đăng nhập / xoá Chrome / xin vào nhóm (an toàn nick) → Tester agent (Sonnet) viết test mù + Reviewer agent (Opus).

## 1. Mục tiêu
PM 25/10: "bỏ hẳn nút gộp … lần sau có đăng nhập các page khác nhau cùng 1 tk thì cứ tự động cho vào 1 chrome".
Làm xong: người dùng **không bao giờ phải biết "gộp"**. Đăng nhập một nick đã có trong tool → tool tự dùng Chrome sẵn có của nick đó, không giữ Chrome thứ 2.

## 2. Phạm vi
- Làm:
  1. **Đăng nhập trùng nick**: bấm ＋ Tài khoản → Đăng nhập. Xong đăng nhập, tool đọc uid (`fb_profile.json`). uid **đã có** ở tài khoản khác → báo *"Nick này đã có ở '<tài khoản>' → dùng chung Chrome đó"*, **đăng xuất + xoá Chrome vừa tạo**, bỏ tài khoản vừa thêm khỏi danh sách, tự chạy **Đọc danh sách Page** ở tài khoản sẵn có (Page mới hiện ngay trong ô Đăng bằng).
  2. Cũng áp dụng khi bấm **Đăng nhập lại / Đổi tài khoản** ở một tài khoản mà đăng nhập vào nick đang thuộc tài khoản khác.
  3. **Bỏ nút Gộp** (hộp Gộp, nút "Gộp vào …" trên cảnh báo).
  4. **Page không chọn được khi xin vào nhóm** (review #003, PM chọn b): nhóm gặp `join_as_missing` ghi trạng thái riêng **"❓ không chọn được Page"** – bảng nhóm hiện trạng thái này, lần xin sau **bỏ qua nhóm đó** (không tốn lượt), có nút / lọc để xin lại khi người dùng muốn.
- Không làm: đổi cách chuyển Page, giới hạn lượt / ngày (#005).

## 3. Hợp đồng (chốt ở bước Dựng khung)
| Loại | Tên | Chi tiết |
|---|---|---|
| Hàm | `tool_store.owner_of_uid(data, uid, except_id) -> account_id \| None` | tài khoản khác đang dùng uid |
| Luồng GUI | sau `--login` xong | uid trùng → hộp báo + `--logout --account <mới>` + xoá khỏi config + `--read-identities --account <sẵn có>` |
| Trạng thái nhóm | `xin_vao_nhom.json` status `"join_as_missing"` | nằm trong `upstt_store.JOIN_WAITING`? → **không** (không phải chờ duyệt); lượt xin bỏ qua; giao diện nhãn "❓ không chọn được Page" |
| Khi lỗi | đăng xuất Chrome mới lỗi | vẫn bỏ tài khoản mới, cảnh báo + nút thử lại (dùng lại `merged_leftovers`) |
| Không đổi | `merge_accounts` / `merge_plan` | giữ lại trong `tool_store` (dùng cho mục 7 câu 1 nếu PM chọn) |

## 4. Chia việc (cách 2)
| Vai | Ai | File | Việc |
|---|---|---|---|
| Dev | Phiên chính | `gui_common.py`, `tool_gui.py`, `tool_store.py`, `fb_upstt.py`, `upstt_store.py` | mục 2.1–2.4 |
| Tester | Agent (Sonnet), test mù | `tests/test_004_*.py` | test từ plan + chữ ký hàm, không xem code |
| Reviewer | Agent (Opus) | – | 3 góc |

## 5. Tiêu chí xong
- [ ] Đăng nhập nick đã có → không còn 2 thư mục Chrome cùng uid; tài khoản mới biến mất; Page mới hiện ở tài khoản sẵn có.
- [ ] Không còn nút / hộp Gộp nào trên giao diện.
- [ ] Nhóm "không chọn được Page" hiện đúng nhãn, lượt xin sau bỏ qua, không trừ giới hạn 10 nhóm/ngày.
- [ ] Config cũ mở được.

## 6. Checklist test tay
| # | Bước | Mong đợi | Kết quả |
|---|---|---|---|
| 1 | ＋ Tài khoản → đăng nhập nick của Tài khoản 4 | Báo trùng nick, Chrome mới bị xoá, Tài khoản 4 đọc lại danh sách Page | |
| 2 | Tạo Page mới trên Facebook → Tài khoản 4 → Đọc danh sách Page | Page mới hiện trong ô Đăng bằng | |
| 3 | Xin vào nhóm bằng Page, hộp "Tham gia với tư cách" không có Page đó | Nhóm hiện "❓ không chọn được Page"; xin lần 2 bỏ qua | |

## 7. Câu hỏi cho PM
| # | Câu hỏi | Đề xuất | PM quyết |
|---|---|---|---|
| 1 | Khách cũ cập nhật lên mà **đang có sẵn nhiều tài khoản cùng nick** (kiểu cũ): bỏ nút Gộp rồi thì xử lý sao? (a) tool **tự gộp** lúc mở (có sao lưu, đăng xuất + xoá Chrome thừa) (b) chỉ cảnh báo + hướng dẫn tự xoá tay (c) giữ nút Gộp riêng cho trường hợp này | (a) tự gộp, nhưng **hỏi xác nhận 1 lần** trước khi xoá Chrome | |
| 2 | Đăng nhập trùng nick: có cần hỏi trước khi xoá Chrome vừa tạo không? | Không hỏi – chỉ báo (Chrome vừa tạo chưa có gì) | |
| 3 | Nhóm "❓ không chọn được Page": xin lại bằng cách nào? | Tick nhóm → 🙋 Xin vào như thường (bấm tay thì luôn thử lại); chỉ lượt **tự động** mới bỏ qua | |

## 8. Tiến độ (chỉ Điều phối ghi)
| Thời gian | Bước | Vai | Nhánh / commit | Kết quả |
|---|---|---|---|---|
| 26/10 | 1 Lập kế hoạch | Điều phối | main | Bản nháp, chờ PM |
