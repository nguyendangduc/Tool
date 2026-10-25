# Quy trình làm việc

```
 1. Lập kế hoạch      PM + Architect viết plans/NNN_ten_viec.md
        │
 2. Dựng khung        chốt hợp đồng giữa các phần, làm TUẦN TỰ, commit lên main   ← bước quan trọng nhất
        │
        ├──────────────┬──────────────┐
 3. Dev A          Dev B          Tester          (song song, mỗi người 1 nhánh riêng)
    1 phần việc    1 phần việc    viết test TỪ SPEC (không đọc code của Dev)
        └──────────────┴──────────────┘
        │
 4. Reviewer          đúng spec · bảo mật · dễ bảo trì   ── lỗi → trả về Dev (bước 3)
        │
 5. PM duyệt + merge  chạy toàn bộ test + test tay trên nick test → merge → (đủ thì) gắn tag
```

## 1. Lập kế hoạch – PM + Architect
- Copy [PLAN_MAU.md](PLAN_MAU.md) thành `plans/NNN_ten_viec.md` (NNN = số thứ tự 001, 002…).
- Ghi: mục tiêu, phạm vi (làm / không làm), **chia phần việc theo file** để 2 Dev không sửa cùng một file, tiêu chí xong.
- PM đọc và chốt trước khi sang bước 2.

## 2. Dựng khung – Architect, làm tuần tự
"Hợp đồng" là những gì các phần dùng chung. Với tool này gồm:

| Loại hợp đồng | Ví dụ |
|---|---|
| Field config mới | `"like_rate": 0` trong `CAMPAIGN_DEFAULTS` – kiểu, mặc định, ý nghĩa |
| Chữ ký hàm | `fb_login.like_post(page, url) -> bool` + docstring vào/ra |
| Lệnh CLI | `--like-only`: ai gọi, script nào nhận |
| File dữ liệu | `accounts/<id>/xxx.json`: cấu trúc JSON |
| Chữ trong nhật ký | dòng `fb_login.note` mà giao diện `parse_log` đọc |

Architect commit khung lên `main`: field mặc định, hàm rỗng (`raise NotImplementedError`) có docstring đầy đủ. Từ đó Dev và Tester cùng bám một hợp đồng.

## 3. Làm song song
- **Dev**: nhánh `feat/NNN-ten-phan` tạo từ `main` sau bước 2. Chỉ sửa file của phần mình, không đổi hợp đồng (cần đổi → báo PM, quay lại bước 2).
- **Tester**: nhánh `test/NNN-ten-viec`. Viết test trong `tests/` **chỉ dựa vào plan + hợp đồng**, không đọc code Dev viết, để không "chấm bài theo đáp án". Soạn thêm **checklist test tay** cho phần bấm Facebook thật.

## 4. Review – 3 góc nhìn
| Góc | Câu hỏi |
|---|---|
| Đúng spec | Làm đủ tiêu chí xong? Đúng hợp đồng? Không làm thừa ngoài phạm vi? |
| Bảo mật / an toàn | Không lộ bí mật, không ghi cookie/token ra log? Có giới hạn + nghỉ nick khi Facebook chặn? Không thuộc danh sách KHÔNG làm? |
| Dễ bảo trì | Đúng quy ước CLAUDE.md? Config cũ của khách mở được? Không sửa lan sang chỗ không liên quan? |

Kết quả: **ĐẠT** hoặc **CẦN SỬA** (kèm danh sách lỗi, mỗi lỗi chỉ file:dòng) → trả về Dev.

## 5. PM duyệt + merge
1. Merge nhánh Tester + các nhánh Dev vào một nhánh tích hợp `int/NNN`.
2. `python -m pytest tests -q` → phải pass hết.
3. Test tay theo checklist trên **nick test + nhóm test**.
4. Đạt → merge vào `main`, cập nhật `HUONG_DAN.md`, `KE_HOACH_THUONG_MAI.md`, `CHANGELOG.md`.
5. Đủ để gửi khách → gắn tag `vX.Y.Z` → chạy `dong_goi.ps1` từ tag đó.

## Definition of Done (một việc chỉ "xong" khi)
- [ ] Tiêu chí xong trong plan đạt hết
- [ ] `pytest` pass, có test mới cho phần mới
- [ ] Checklist test tay đã chạy, ghi kết quả vào plan
- [ ] Reviewer ĐẠT cả 3 góc
- [ ] Config cũ mở được (thử với một `config.json` cũ)
- [ ] Đã cập nhật hướng dẫn + kế hoạch + changelog
