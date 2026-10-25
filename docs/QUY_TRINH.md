# Quy trình làm việc

```
 1. Lập kế hoạch      PM + Architect viết plans/NNN_ten_viec.md                    ── CỔNG: PM chốt plan
        │
 2. Dựng khung        chốt hợp đồng giữa các phần, làm TUẦN TỰ, commit lên main   ← bước quan trọng nhất
        │
        ├──────────────┬──────────────┐
 3. Dev A          Dev B          Tester          (song song, mỗi vai 1 nhánh + 1 worktree riêng)
    1 phần việc    1 phần việc    viết test TỪ SPEC (không đọc code của Dev)
        └──────────────┴──────────────┘
        │  Điều phối gộp vào int/NNN, chạy toàn bộ test
 4. Reviewer          đúng spec · bảo mật · dễ bảo trì   ── CẦN SỬA → vòng sửa (xem 4b) → quay lại 3
        │
 5. PM duyệt + merge  test tay trên nick test → merge int/NNN vào main             ── CỔNG: chỉ PM merge
```

**Cách chạy mặc định (PM chọn 25/10/2026 – tiết kiệm token):** Architect, Dev, Tester do **phiên Claude chính** làm (đã có sẵn bối cảnh, không đọc lại file lớn). **Chỉ Reviewer là agent riêng** (cặp mắt mới – giá trị lớn nhất của quy trình). Việc rủi ro cao (đụng đăng bài / nick) có thể thêm 1 Tester agent model rẻ để giữ "test mù". Không agent nào sửa file ngoài worktree của mình; Điều phối kiểm `git status` trên `main` sau mỗi lượt agent.

Các vai: **PM** = bạn. **Điều phối** = phiên Claude chính (giao việc cho agent, gộp nhánh, cập nhật bảng tiến độ). **Architect / Dev / Tester / Reviewer** = agent trong `.claude/agents/`, mỗi agent bắt đầu trống, chỉ biết những gì ghi trong file vai + plan.

## 1. Lập kế hoạch – PM + Architect
- Copy [PLAN_MAU.md](PLAN_MAU.md) thành `plans/NNN_ten_viec.md` (NNN = 001, 002…).
- Ghi: mục tiêu, phạm vi (làm / không làm), **chia phần việc theo file** để 2 Dev không sửa cùng một file, tiêu chí xong.
- Đối chiếu **bảng khoá file** (mục "Nhiều task cùng lúc") với các task đang chạy.
- Architect liệt kê câu hỏi ở mục 7. **PM trả lời và chốt** trước khi sang bước 2.

## 2. Dựng khung – Architect, làm tuần tự
"Hợp đồng" là những gì các phần dùng chung. Với tool này gồm:

| Loại hợp đồng | Ví dụ |
|---|---|
| Field config mới | `"like_rate": 0` trong `CAMPAIGN_DEFAULTS` – kiểu, mặc định, ý nghĩa |
| Chữ ký hàm | `fb_login.like_post(page, url) -> bool` + docstring vào/ra |
| Lệnh CLI | `--like-only`: ai gọi, script nào nhận |
| File dữ liệu | `accounts/<id>/xxx.json`: cấu trúc JSON |
| Chữ trong nhật ký | dòng `fb_login.note` mà giao diện `parse_log` đọc |
| Hành vi khi lỗi | mã thoát, dọn file tạm, thông báo (bài học #001: phải ghi rõ trong hợp đồng) |

Architect commit khung lên `main`: field mặc định, hàm rỗng (`raise NotImplementedError`) có docstring đầy đủ. Việc chỉ 1 file / không có hàm chung thì hợp đồng nằm trong plan là đủ.

## 3. Làm song song
| Vai | Nhánh | Worktree |
|---|---|---|
| Dev A / Dev B | `feat/NNN-ten-phan` | `.claude/worktrees/NNN-dev-a`, `NNN-dev-b` |
| Tester | `test/NNN-ten-viec` | `.claude/worktrees/NNN-tester` |
| Gộp | `int/NNN` | `.claude/worktrees/NNN-int` |

- **Dev**: chỉ sửa file của phần mình, không đổi hợp đồng (cần đổi → báo PM, quay lại bước 2). Tự chạy thử, báo kết quả cho Điều phối.
- **Tester**: viết test trong `tests/test_NNN_*.py` **chỉ dựa vào plan + hợp đồng**, không đọc code Dev. Trên khung / bản cũ test phải FAIL – đó là bằng chứng test có tác dụng. Liệt kê **chỗ spec mơ hồ** để PM quyết.
- **Không agent nào sửa mục "8. Tiến độ" của plan.** Agent báo kết quả về, Điều phối ghi một chỗ (tránh xung đột khi gộp – bài học #001).
- **Điều phối gộp**: tạo `int/NNN` từ `main`, merge các nhánh `feat/*` + `test/*`, chạy `python -m pytest tests -q`. Test hỏng → trả về vai liên quan, chưa sang Reviewer.

## 4. Review – 3 góc nhìn (trên `int/NNN`)
| Góc | Câu hỏi |
|---|---|
| Đúng spec | Làm đủ tiêu chí xong? Đúng hợp đồng? Không làm thừa ngoài phạm vi? |
| Bảo mật / an toàn | Không lộ bí mật, không ghi cookie/token ra log? Có giới hạn + nghỉ nick khi Facebook chặn? Không thuộc danh sách KHÔNG làm? File mới ở gốc có bị `dong_goi.ps1` gửi khách ngoài ý muốn? |
| Dễ bảo trì | Đúng quy ước CLAUDE.md? Config cũ của khách mở được? Không sửa lan sang chỗ không liên quan? |

Reviewer **tự kiểm chứng** từng lỗi (chạy thử trên bản sao trong `%TEMP%`), xếp mỗi điểm vào: **lỗi chặn** · **PM quyết** · **ghi chú không chặn**. Kết quả: **ĐẠT** hoặc **CẦN SỬA**.

### 4b. Vòng sửa (khi CẦN SỬA)
1. **Tester viết test cho đúng lỗi Reviewer tìm ra trước** (test phải FAIL trên bản hiện tại) – lỗi đã lọt qua test thì phải có test chặn nó quay lại.
2. Dev sửa song song, chỉ sửa lỗi chặn, không làm thêm.
3. Điều phối gộp lại vào `int/NNN`, chạy toàn bộ test (test mới phải chuyển sang ĐẠT).
4. Reviewer **soát lại chỉ phần sửa** + kiểm không sinh lỗi mới; không nêu lại điểm đã xếp "không chặn / PM quyết".
5. Quá **3 vòng** vẫn CẦN SỬA → dừng, PM xem lại plan / hợp đồng (thường là spec sai, không phải code).

## 5. PM duyệt + merge
1. Đọc kết luận Reviewer + trả lời các câu "PM quyết" (ghi vào mục 7 plan). Câu nào đổi hợp đồng → mở task mới hoặc thêm vòng sửa.
2. Test tay theo mục 6 của plan trên **nick test + nhóm test** (đóng gói / giao diện / Facebook thật).
3. Merge: `git switch main` → `git merge --no-ff int/NNN -m "[pm] merge NNN: <tên việc>"` → `python -m pytest tests -q`.
4. Cập nhật `HUONG_DAN.md`, `KE_HOACH_THUONG_MAI.md`, `CHANGELOG.md` nếu cần. Xoá worktree + nhánh của task.
5. Đủ để gửi khách → làm theo mục "Phát hành".

## Phát hành (gửi bản mới cho khách)
**Số phiên bản `vX.Y.Z`:**
| Tăng | Khi nào | Ví dụ |
|---|---|---|
| Z (vá) | Chỉ sửa lỗi, không thêm tính năng, config không đổi | Facebook đổi nút Đăng → `v1.0.1` |
| Y (tính năng) | Thêm tính năng; config cũ vẫn mở được | Thêm F11 thích bài → `v1.1.0` |
| X (lớn) | Đổi cấu trúc config / cách cài, khách phải làm thêm bước | Chuyển sang .exe → `v2.0.0` |

**Các bước (PM làm, Điều phối hỗ trợ):**
1. Trên `main`: `python -m pytest tests -q` phải pass hết.
2. Thêm mục mới ở đầu `CHANGELOG.md`:
   ```
   ## v1.1.0 – 30/10/2026
   - Thêm: … (task NNN)
   - Sửa: … (task NNN)
   - Lưu ý cho khách: … (nếu phải làm gì sau khi cập nhật)
   ```
   Viết cho khách đọc, có dấu, không ghi tên hàm. Commit `[pm] release: v1.1.0`.
3. Gắn tag: `git tag -a v1.1.0 -m "v1.1.0"`.
4. Đóng gói từ đúng tag: `git worktree add .claude/worktrees/release v1.1.0` → chạy `dong_goi.ps1` trong đó → kiểm thư mục `FacebookTool_GuiKhach` (đúng danh sách file, không có log / config / `.py`) → `git worktree remove .claude/worktrees/release`.
5. Đổi tên gói thành `FacebookTool_v1.1.0`, cài thử trên máy / thư mục sạch (`CAI_DAT.bat` → `MO_TOOL.bat` mở được).
6. Gửi khách, ghi vào sổ khách (giữ riêng, KHÔNG để trong repo – cùng chỗ `_NGUOI_BAN_khong_gui_khach/da_cap.csv`): khách · mã máy · phiên bản · ngày gửi.

## Sửa gấp (hotfix – khách đang bị lỗi)
Dùng khi tool **đang bán bị hỏng** (Facebook đổi giao diện, lỗi làm tool không chạy). Việc khác – kể cả lỗi nhỏ – đi quy trình thường.

```
tag đang bán (vd v1.1.0) ─► hotfix/NNN-ten-loi ─► sửa + test ─► Reviewer (nhanh) ─► PM test tay ─► merge main ─► tag v1.1.1 ─► gửi khách
```

| Bước | Rút gọn so với quy trình thường |
|---|---|
| Plan | Plan ngắn: lỗi gì, ảnh lỗi / nhật ký, nguyên nhân, cách sửa, tiêu chí xong. PM chốt luôn trong chat |
| Dựng khung | Bỏ (không đổi hợp đồng – đổi hợp đồng thì không phải hotfix) |
| Dev + Tester | 1 Dev. Tester viết **1 test tái hiện lỗi** (trang HTML giả lập giống giao diện Facebook mới), FAIL trước khi sửa |
| Reviewer | **Vẫn bắt buộc**, chỉ soát diff sửa + an toàn nick |
| PM | **Vẫn bắt buộc** test tay trên nick test + merge |

- Nhánh tạo từ **tag đang bán**, không từ `main` (main có thể có tính năng chưa phát hành): `git switch -c hotfix/NNN-ten-loi v1.1.0`.
- Xong: merge vào `main`, gắn tag vá (`v1.1.1`) lên commit hotfix, phát hành như mục trên. Task đang chạy gộp `main` mới vào `int/NNN` của mình.
- Ghi vào `CHANGELOG.md` mục `Sửa:` + ảnh lỗi gốc lưu ở `plans/NNN_*.md`.

## Nhiều task cùng lúc
Số agent tăng theo **số task** và **số nhóm file rời nhau**, không theo cảm giác "việc to":

| Vai | Bao nhiêu |
|---|---|
| Architect | 1, làm lần lượt từng plan (plan sau phải xem bảng khoá file của plan trước) |
| Dev | mỗi task: **1 Dev cho mỗi nhóm file rời nhau** (thường 1–2). 3 task × 1–2 Dev = 3–6 Dev chạy cùng lúc |
| Tester | **1 / task** |
| Reviewer | **1 / task**, chạy khi `int/NNN` của task đó xanh |
| Điều phối | 1 (phiên chính) |
| PM | 1 (bạn) – **nút cổ chai thật**: 2 cổng / task + test tay |

**Bảng khoá file.** Mỗi plan ghi file sẽ sửa (mục 4). Hai task **sửa cùng một file thì không chạy bước 3 cùng lúc** – task sau đợi task trước merge xong. Các file dễ đụng nhau: `gui_common.py`, `tool_gui.py`, `fb_login.py`, `fb_upstt.py`, `fb_monitor_v4.py`, `tool_store.py`, `upstt_store.py`, `monitor_store.py`, `setup.ps1`.

**Merge từng task một vào `main`.** Task A merge xong → các task đang chạy gộp `main` mới vào `int/NNN` của mình, chạy lại toàn bộ test, Reviewer soát lại nếu có thay đổi.

**Giới hạn khuyên dùng:** tối đa **3 task** đang ở bước 3–4 cùng lúc. Nhiều hơn thì PM không kịp chốt plan / test tay, và nick test chỉ có 1 – test tay Facebook thật phải xếp hàng.

## Theo dõi (PM xem Claude có làm đúng quy trình không)
| Ở đâu | Thấy gì | Ai cập nhật |
|---|---|---|
| **Bảng tiến độ** (trang web) | Mỗi task 1 sơ đồ 5 bước, bước đang chạy sáng lên, ô vàng = đang chờ PM, nhật ký từng vai | Điều phối, mỗi lần chuyển bước |
| Mục **"8. Tiến độ"** trong `plans/NNN_*.md` | Từng bước: vai, nhánh, commit, kết quả | Điều phối (agent không sửa) |
| `git log --oneline --graph --all` | Commit có tiền tố vai, nhánh tách / gộp đúng sơ đồ | Tự có khi commit |

**Tiền tố commit theo vai:** `[architect]`, `[dev-A]`, `[dev-B]`, `[tester]`, `[reviewer]`, `[pm]`. Ví dụ `[dev-A] feat(001): dong_goi chi chep file cho phep`.

**Cổng chờ PM** – Điều phối DỪNG lại và báo bạn, không tự đi tiếp:
1. Sau bước 1: plan xong → **bạn chốt** thì mới dựng khung.
2. Sau bước 4: Reviewer ĐẠT → **bạn test tay + merge**. Claude không tự merge vào `main`.

**Mỗi lần chuyển bước, Điều phối báo trong chat đúng mẫu:**
```
[#001] Bước 3 → 4 · Dev A xong (feat/001-dong-goi, 2 commit), Tester xong (6 test, 6 pass)
Tiếp theo: Reviewer · Đang chờ bạn: không
```

## Lưu ý kỹ thuật
- Git cài qua winget có thể chưa vào PATH của phiên đang mở: dùng `& "C:\Program Files\Git\cmd\git.exe"`, hoặc mở lại VSCode / terminal.
- Python dùng cho test: `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`.
- Worktree nằm trong `.claude/worktrees/` (đã `.gitignore`). Task xong: `git worktree remove <đường dẫn>` + `git branch -d <nhánh>`.

## Definition of Done (một việc chỉ "xong" khi)
- [ ] Tiêu chí xong trong plan đạt hết
- [ ] `pytest` pass trên `int/NNN` và sau khi merge vào `main`, có test mới cho phần mới + cho mọi lỗi Reviewer tìm ra
- [ ] Checklist test tay đã chạy, ghi kết quả vào plan
- [ ] Reviewer ĐẠT cả 3 góc; mọi câu "PM quyết" đã có câu trả lời ở mục 7
- [ ] Config cũ mở được (thử với một `config.json` cũ)
- [ ] Đã cập nhật hướng dẫn + kế hoạch + changelog; xoá worktree + nhánh của task

Một **bản phát hành** chỉ "xong" khi: pytest pass trên `main` · CHANGELOG có mục phiên bản · đã gắn tag · gói đóng từ đúng tag và cài thử được · đã ghi sổ khách.
