# 002 – Bảo vệ nick: giới hạn và tạm nghỉ theo NICK FACEBOOK (uid), không theo "tài khoản" trong tool

Trạng thái: **Lập kế hoạch (bản nháp – chờ PM chốt)**
PM chốt ngày: …
Phụ thuộc: không. Khoá file: `fb_login.py`, `fb_upstt.py`, `upstt_store.py`, `tool_store.py`, `fb_monitor_v4.py`, `tool_gui.py`.

## 1. Mục tiêu
PM báo: "tool chạy chết rất nhiều acc; 1 tk tạo 3 page con cho cùng đăng; tưởng mỗi tk chỉ đăng 1–2 lần/ngày, 5–7 nhóm".
Làm xong: tool **tính giới hạn và tạm nghỉ theo nick Facebook thật (uid)**, cộng dồn mọi "tài khoản" trong tool dùng chung nick đó (cá nhân + các Page), có giờ nghỉ đêm, và báo rõ khi một nick bị đăng nhập ở nhiều cửa sổ.

## 2. Điều tra (dữ liệu thật 25/10/2026)

### 2.1 "Chết" là gì
`accounts/a3`, `a5`, `a6` cùng chuyển **expired lúc 13:03–13:04 hôm nay** – cả 3 là **cùng một nick** (uid …558). Facebook đã **đăng xuất mọi phiên** của nick này cùng lúc. (Nhật ký không ghi checkpoint / "giới hạn tần suất" – Facebook đá phiên, không báo lý do.)

### 2.2 Một nick = nhiều "tài khoản" trong tool
| uid | Tài khoản trong tool (mỗi cái 1 Chrome riêng, đăng nhập riêng) |
|---|---|
| …558 (Nguyễn Đức) | **a5** cá nhân · **a3** Page "Thư Tình" · **a6** Page "Vì Anh Là Gió" |
| …406 (Nguyễn Văn Thành Long) | **a4** cá nhân · **a2** Page "HTX chó mèo" |

Mỗi "tài khoản" là một thư mục Chrome riêng đăng nhập lại từ đầu → Facebook thấy **cùng một người đăng nhập trên 3 thiết bị**, thay nhau đăng bài tự động. Đây là nghi vấn mạnh nhất cho việc cả 3 phiên bị đá cùng lúc.

### 2.3 Lượng việc thật mỗi ngày (theo lịch đang bật)
**Nick …558** – không phải "1–2 lần, 5–7 nhóm":
| Giờ | Ai | Kịch bản | Nhóm |
|---|---|---|---|
| 02:20 | a5 | k1 TEST – Luồng đầy đủ (vẫn bật) | 2 |
| 06:45 | a5 | k14 Khách sạn thú cưng | 6 |
| 11:30 | a5 | k12 Tool | 8 |
| 19:00 | a3 (Page) | k10 Thiepcuoi4 | 7 |
| 19:15 | a5 | k14 Khách sạn thú cưng | 6 |
| 20:00 | a5 | k12 Tool | 8 |
| 20:35 | a6 (Page) | k10 Thiepcuoi4 – **cùng nội dung, cùng 7 nhóm** với a3 | 7 |
| mỗi 3 giờ (cả đêm) | a5 | Tự chăm bài: bình luận vào bài vừa duyệt (vd 01:54–02:00 bình luận liền 6 bài) | – |

→ **7 lượt đăng / ngày, ~44 lượt đăng vào nhóm**, chưa kể bình luận, xin vào nhóm, xác minh nhóm.

**Nick …406 (a4)**: quét 2 kịch bản theo dõi **mỗi 40 phút cả ngày đêm** (lượt 13:32 cuộn 18 phút → ~11 giờ/ngày lướt nhóm) + **tự bình luận vào bài người lạ** + đăng k10 11:30 (7), k14 12:00 & 21:00 (6+6), k1 02:20 (2) + tự chăm bài. Một nhóm Facebook đã ghi **37 bài** của nick này được duyệt.

### 2.4 Lỗ hổng trong code
| # | Chỗ | Vấn đề |
|---|---|---|
| a | `fb_login._pause_file` | Tạm nghỉ tính theo **uid + tên** → Page bị giới hạn thì cá nhân và Page khác **vẫn chạy tiếp** trên cùng nick |
| b | `upstt_store.validate` / `warnings` | Kiểm trùng giờ theo từng "tài khoản" → không thấy 3 "tài khoản" cùng nick cộng lại 7 lượt/ngày |
| c | không có | Không có **trần lượt đăng / ngày theo nick**, không có **giờ nghỉ đêm** |
| d | `max_posts_group_day` (=1) | Tính theo "tài khoản" → cùng nội dung vào cùng nhóm từ cá nhân + 2 Page của 1 người vẫn lọt |
| e | `account_status` | 1 phiên của nick bị đá → các phiên khác của cùng nick vẫn tiếp tục chạy / đăng nhập lại |
| f | theo dõi nhóm | Chu kỳ quét tối thiểu 5 phút, mặc định 40 phút, chạy 24/24 |

## 3. Phạm vi
- Làm (đề xuất – chờ PM chốt mục 7):
  1. **Ngân sách theo nick (uid)**, cộng mọi tài khoản trong tool cùng uid: tối đa N lượt đăng vào nhóm / ngày, tối đa M lượt chạy / ngày; vượt → bỏ lượt, ghi nhật ký rõ.
  2. **Giờ nghỉ đêm** theo nick (mặc định 23:00–06:00): không đăng, không bình luận, không quét, không tự chăm bài.
  3. **1 nhóm / 1 ngày / 1 nick**: cùng nhóm chỉ nhận 1 bài / ngày từ một nick, bất kể đăng bằng cá nhân hay Page nào.
  4. **Tạm nghỉ theo uid**: bị giới hạn hoặc **bị đá phiên** ở bất kỳ tài khoản nào → mọi tài khoản cùng uid dừng + báo Telegram (nếu có).
  5. **Cảnh báo trên giao diện**: 2+ tài khoản trong tool cùng uid → cảnh báo đỏ "1 nick đang đăng nhập ở N cửa sổ"; bảng "lượng việc theo nick / ngày" khi Lưu.
  6. **Theo dõi nhóm**: chu kỳ tối thiểu nâng lên (đề xuất 90 phút), chỉ quét trong giờ hoạt động.
- Không làm: né phát hiện (đổi vân tay trình duyệt, proxy xoay, gõ giả người…) – nằm trong danh sách KHÔNG làm. Đăng bằng Page trong **cùng một** cửa sổ Chrome (F9) là việc riêng (#003), làm sau.

## 4. Việc PM nên làm NGAY (không cần code)
1. **⏸ Tạm dừng toàn bộ** trong tool cho đến khi #002 xong.
2. **Tắt kịch bản k1 "TEST – Luồng đầy đủ"** (đăng 02:20 mỗi đêm).
3. Nick …558: **chỉ đăng nhập lại 1 tài khoản (a5)**, chưa đăng nhập a3/a6. Nghỉ 24–48 giờ trước khi chạy lại.
4. Bỏ k10 ở a3 hoặc a6 (cùng nội dung, cùng nhóm, cùng chủ).
5. Theo dõi nhóm (k2, k13 trên a4): tắt "tự bình luận" hoặc tăng chu kỳ quét lên ≥ 90 phút.

## 5. Chia việc (dự kiến, chốt ở bước Dựng khung)
| Vai | Nhánh | File được sửa | Việc |
|---|---|---|---|
| Dev A | feat/002-ngan-sach-nick | `fb_login.py`, `fb_upstt.py`, `upstt_store.py` | ngân sách + giờ nghỉ + 1 nhóm/ngày/nick + tạm nghỉ theo uid (đăng bài, chăm bài) |
| Dev B | feat/002-giao-dien | `tool_store.py`, `tool_gui.py` | cảnh báo trùng uid, bảng lượng việc theo nick, ô cài đặt ngân sách |
| Dev C (sau A) | feat/002-theo-doi | `fb_monitor_v4.py`, `monitor_store.py` | giờ nghỉ + tạm nghỉ theo uid + chu kỳ tối thiểu cho theo dõi nhóm |
| Tester | test/002-ngan-sach-nick | `tests/test_002_*.py` | test ngân sách / giờ nghỉ / gộp uid bằng dữ liệu giả, không mở Facebook |

## 6. Tiêu chí xong
- [ ] 3 tài khoản cùng uid: tổng lượt đăng / ngày không vượt N; lượt vượt bị bỏ + nhật ký ghi lý do.
- [ ] Trong giờ nghỉ đêm không có lượt đăng / bình luận / quét / chăm bài nào chạy.
- [ ] Cùng nhóm không nhận 2 bài / ngày từ cùng uid.
- [ ] 1 tài khoản bị đá phiên hoặc bị giới hạn → mọi tài khoản cùng uid dừng.
- [ ] Giao diện cảnh báo khi 2+ tài khoản cùng uid; hiện tổng lượng việc theo nick.
- [ ] Config cũ mở được; mặc định an toàn áp dụng ngay cho khách cũ.

## 7. Câu hỏi cho PM
| # | Câu hỏi | Đề xuất | PM quyết |
|---|---|---|---|
| 1 | Trần lượt đăng vào nhóm / ngày / nick | **10** (cá nhân + mọi Page cộng lại) | |
| 2 | Trần lượt chạy đăng bài / ngày / nick | **2** | |
| 3 | Giờ nghỉ đêm | **23:00–06:00** | |
| 4 | Chu kỳ quét theo dõi tối thiểu | **90 phút**, chỉ 07:00–22:00 | |
| 5 | Tự chăm bài: giữ hay tắt mặc định? | Giữ, nhưng tính vào ngân sách + không chạy đêm | |
| 6 | Bị đá phiên 1 tài khoản → các tài khoản cùng uid dừng bao lâu? | Dừng đến khi PM đăng nhập lại + thêm 24 giờ | |
| 7 | Cho phép khách tự nâng trần? | Có, nhưng tối đa 20 và hiện cảnh báo | |

## 8. Tiến độ (chỉ Điều phối ghi)
| Thời gian | Bước | Vai | Nhánh / commit | Kết quả |
|---|---|---|---|---|
| 25/10 | 1 Lập kế hoạch | Điều phối + Architect | main | Điều tra xong, chờ PM chốt mục 7 |
