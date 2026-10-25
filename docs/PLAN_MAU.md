# NNN – Tên việc

Trạng thái: Lập kế hoạch | Dựng khung | Đang làm | Review (vòng N) | Chờ PM merge | Đã merge
PM chốt ngày: …
Phụ thuộc: (task phải merge trước, vd "002 – cùng sửa fb_login.py") hoặc "không"

## 1. Mục tiêu
Một hai câu: làm xong thì người dùng làm được gì mới. Vì sao cần (lỗi / yêu cầu khách / kế hoạch).

## 2. Phạm vi
- Làm: …
- Không làm: …

## 3. Hợp đồng (chốt ở bước Dựng khung)
| Loại | Tên | Chi tiết (kiểu, mặc định, vào/ra) |
|---|---|---|
| Field config | | |
| Hàm | | |
| CLI | | |
| File dữ liệu | | |
| Dòng nhật ký | | |
| Khi lỗi | | mã thoát, dọn dẹp gì, thông báo gì |
| Không đổi | | những gì phải giữ nguyên |

## 4. Chia việc + khoá file
| Vai | Nhánh | Worktree | File được sửa | Việc |
|---|---|---|---|---|
| Dev A | feat/NNN-… | .claude/worktrees/NNN-dev-a | | |
| Dev B | feat/NNN-… | .claude/worktrees/NNN-dev-b | | |
| Tester | test/NNN-… | .claude/worktrees/NNN-tester | tests/test_NNN_*.py | test tự động + checklist tay |

File khoá bởi task này (task khác không sửa trong lúc chạy): …
Đã đối chiếu task đang chạy: … (không trùng / trùng với NNN → đợi)

## 5. Tiêu chí xong
- [ ] …

## 6. Checklist test tay (nick test + nhóm test)
| # | Bước | Mong đợi | Kết quả |
|---|---|---|---|
| 1 | | | |

## 7. Câu hỏi / quyết định của PM
| # | Câu hỏi (ai nêu) | PM quyết | Ngày |
|---|---|---|---|
| 1 | | | |

## 8. Tiến độ (chỉ Điều phối ghi – agent không sửa mục này)
| Thời gian | Bước | Vai | Nhánh / commit | Kết quả |
|---|---|---|---|---|
| | 1 Lập kế hoạch | Architect + PM | main | |
| | 2 Dựng khung | Architect | main | |
| | 3 Dev A | Dev | feat/NNN-… | |
| | 3 Tester | Tester | test/NNN-… | |
| | 3 Gộp | Điều phối | int/NNN | pytest x/y |
| | 4 Review vòng 1 | Reviewer | int/NNN | ĐẠT / CẦN SỬA |
| | 5 Merge | PM | main | |

## 9. Bài học (ghi sau khi merge)
- …
