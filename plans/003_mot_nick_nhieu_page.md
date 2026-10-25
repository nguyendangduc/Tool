# 003 – Một nick nhiều Page trong MỘT Chrome (F9)

Trạng thái: **Vòng 2 – sửa sau review** (hợp đồng bổ sung ở mục 3.10, khung vòng 2 đã commit trên `main`; chờ Dev A / B / C + Tester)
PM chốt ngày: 25/10/2026
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

## 3. Hợp đồng (CHỐT ở bước Dựng khung 25/10/2026 – khung đã commit trên `main`)
Khung: field mặc định + hàm rỗng (`raise NotImplementedError`, docstring đủ vào / ra / lỗi) trong `fb_login.py`, `tool_store.py`; field mặc định trong `upstt_store.py`, `monitor_store.py`; tham số mới `identity=` (chưa dùng) ở `upstt_store.join_state`, `upstt_store.reset_pause`, `monitor_store.reset_pause`, `fb_login.check_results_cli`. Khung không đổi hành vi (đã kiểm: `materialize()` trên config thật sinh ra đúng như cũ). Docstring trong code là bản chi tiết; bảng dưới là bản tóm tắt – lệch nhau thì báo Architect.

### 3.1 Dữ liệu config
| Loại | Tên | Chi tiết |
|---|---|---|
| Field tài khoản | `account["identities"]` | `[{"id": "self", "name": "<tên cá nhân>", "kind": "self"}, {"id": "61595395697904", "name": "HTX chó mèo", "kind": "page"}]`, lưu trong `config.json` (mục tài khoản). Id Page = cookie `i_user`; Cá nhân luôn `"self"`. Tuỳ chọn `"missing": true` = lần đọc gần nhất không thấy Page này (vẫn giữ vì kịch bản còn trỏ tới). **Mặc định `[]`** (config cũ / chưa bấm Đọc danh sách Page) = chỉ có Cá nhân. Đọc qua `tool_store.account_identities(account)` (Cá nhân luôn đứng đầu). |
| Field kịch bản | `scenario["post_as"]` | `{account_id: identity_id}` – giống `member_times`; thiếu khoá = `"self"`. Mặc định `{}`. Có ở cả kịch bản đăng bài lẫn theo dõi (PM câu 4). Nhân bản kịch bản → `{}`. |
| Field mục (sinh ra) | `campaign["post_as"]`, `campaign["post_as_name"]` | `materialize()` ghi id + tên danh tính cho từng mục (tài khoản × kịch bản). Mặc định trong `CAMPAIGN_DEFAULTS` của `upstt_store` + `monitor_store`: `"self"`, `""`. KHÔNG nằm trong `scenario["settings"]` (`tool_store.PER_MEMBER_KEYS`). Id không còn trong tài khoản → **giữ nguyên id** (lượt chạy báo `missing` + bỏ lượt, không tự đổi sang Cá nhân). **Vòng 2 (PM câu 13): Page có `"missing": true` hoặc không còn → `post_as_name = ""`** (xem 3.10d). `fb_upstt` / `fb_monitor_v4` chỉ đọc 2 field này, không đọc `identities` (lệnh `--identity` không kèm mục: tra `identities`, **bỏ qua mục `missing`**). |
| File | `accounts/<id>/danh_tinh.json` | `{"time": epoch, "identities": [như read_identities]}` – lệnh `--read-identities` ghi (`fb_login.save_identities_file`), giao diện đọc (`fb_login.load_identities_file`) → `tool_store.update_identities(account, found)` → Lưu config. Lệnh chạy không tự sửa config (giao diện có thể đang có thay đổi chưa lưu). |

### 3.2 Dữ liệu theo danh tính
**Cách tách: Cá nhân giữ nguyên file cũ ở `accounts/<id>/`; mỗi Page có thư mục con `accounts/<id>/danh_tinh/<id Page>/` với đúng các tên file cũ.** `fb_login.identity_dir(acc_dir, identity_id) -> Path` ("self" / "" / None → `acc_dir`; id Page → thư mục con, tự tạo; id không phải số → `ValueError`).

Lý do chọn (thay vì thêm khoá danh tính vào từng JSON): (1) mọi hàm hiện có đều nhận `acc_dir` (`load_results`, `record_sent`, `check_results`, `groups_due`, `load_join_state`, `set_join_status`, `set_verified`, `mark_joined`, `save_joined_groups`, `load_care_state`, `set_care_status`, `care_candidates`, `load_group_state`…) → chỉ cần truyền `identity_dir(...)` thay `acc_dir`, **không đổi chữ ký, không đổi cấu trúc JSON**; (2) config cũ / nick chỉ có Cá nhân: không chuyển dữ liệu, không cần backup, chạy y như cũ; (3) gộp tài khoản = chép file của tài khoản phụ vào 1 thư mục; (4) khoá trong JSON buộc sửa mọi hàm đọc/ghi + giao diện của cả 3 Dev cùng lúc → dễ lệch.

| Theo DANH TÍNH (`identity_dir`) – `fb_login.IDENTITY_FILES` | Theo NICK (`acc_dir`, như cũ) |
|---|---|
| `xin_vao_nhom.json`, `nhom_da_vao.json`, `ket_qua.json`, `cham_bai.json` (+ file cũ `da_binh_luan_cham.txt`), `nhom_tam_nghi.json`, `binh_luan_loi.json` | `browser_profile/`, `status.json`, `fb_profile.json`, khoá (`browser_profile.lock/.pid`, `hold_nick`), **tạm nghỉ nick** (`pause_nick` / `nick_pause` / `recovering` / `clear_nick_pause` – xem câu PM 5), `commented_ids.txt` (1 bài chỉ được 1 bình luận của cả nick, dù danh tính nào), `tin_nhan.json` (chỉ Cá nhân), `tim_nhom.json`, `kiem_tra_tien_do.json` (giao diện luôn đọc tiến độ ở `acc_dir`), `dang_nhap.log` |

Hàm store: `upstt_store.join_state(account_id, identity="self")`; `upstt_store.reset_pause(account, kind, key, identity="self")`; `monitor_store.reset_pause(account, kind, key, identity="self")` (nhóm → `identity_dir`, `kind` "account"/"recovering" → `acc_dir`); `pause_notes(account, campaign)` tự lấy `campaign["post_as"]`; `tool_store.reset_pause` truyền `identity=campaign.get("post_as", "self")`. `logs/<id mục>/`, `campaigns/<id>/` không đổi.

### 3.3 Hàm `fb_login` (Dev A viết thân)
| Hàm | Vào → Ra | Hành vi / lỗi |
|---|---|---|
| `identity_dir(acc_dir, identity_id) -> Path` | xem 3.2 | `ValueError` nếu id lạ |
| `current_identity(page) -> str` | cookie `i_user` → id Page; không có → `"self"` | không mở trang, không raise, không in cookie |
| `read_identities(page) -> list[dict]` | `[{"id":"self","name","kind":"self"}, {"id":<i_user>,"name","kind":"page"}…]`, Cá nhân đầu, tối đa `READ_IDENTITIES_MAX`=10 Page | menu `ACCOUNT_MENU_LABELS` → (≥2 Page) "Xem tất cả trang cá nhân". Id Page đọc được trên trang thì lấy, không thì chuyển sang Page đó đọc `i_user`. Luôn kết thúc ở Cá nhân (finally). Lỗi → `RuntimeError` (Facebook giới hạn: chữ `rate_limited` trong lỗi, người gọi `pause_nick`) |
| `switch_identity(page, identity_id, name) -> bool` | True nếu cuối cùng `current_identity == identity_id` | Đã đúng → không bấm gì. Bấm `role=button` "Chuyển sang <name>" (không có → hộp "Chọn trang cá nhân" → nút "<name>, …"), chờ `IDENTITY_SWITCH_WAIT`=8 s, kiểm `i_user` tối đa `IDENTITY_SWITCH_TIMEOUT`=30 s. Không raise |
| `ensure_identity(page, identity_id, name, shot_dir=None) -> None` | | Gọi `switch_identity`; False → chụp `<yyyymmdd_HHMMSS>_danh_tinh.png` vào `shot_dir` rồi raise `IdentitySwitchFailed`. `"self"` + không có `i_user` → không thao tác gì |
| `back_to_self(page, self_name="") -> bool` | True nếu đang ở Cá nhân | Không có `i_user` → True ngay. **Không bao giờ raise** (dùng trong finally). ~~`self_name` = `account_status.read_profile(acc_dir)["name"]`~~ → **vòng 2: `self_name` = `fb_login.self_name_of(acc_dir)`** (3.10h); script không gọi thẳng nữa mà qua `end_identity` |
| `load_identities_file(acc_dir)` / `save_identities_file(acc_dir, identities)` | `danh_tinh.json` | lỗi đọc → mặc định `{"time": 0, "identities": []}`; lỗi ghi → bỏ qua |
| `class IdentitySwitchFailed(RuntimeError)` | thuộc tính `identity_id, name, reason, shot`; `note_text` = dòng nhật ký nguyên văn | đã viết đủ trong khung |
| `check_results_cli(..., identity=None)` | `identity` = `{"id","name"}` | ≠ Cá nhân → `ensure_identity` sau `verify_and_record`, kết quả ghi `identity_dir`, `back_to_self` trong finally; tiến độ vẫn `acc_dir` |
| Sửa `fetch_profile_name`, `_logout_on_facebook` | | Dùng `ACCOUNT_MENU_LABELS` (nhãn mới "Account, your profile" trước, nhãn cũ dự phòng) + hộp `div[role=dialog]:not([aria-label='Messenger']):visible` (mục 3b). ~~`fetch_profile_name`: đang ở Page (`i_user`) → `back_to_self` trước khi đọc `/me` (tên lưu luôn là tên Cá nhân).~~ **ĐỔI vòng 2 (3.10b): `fetch_profile_name` KHÔNG BAO GIỜ chuyển danh tính; ghi thêm `page_id`.** **Thuộc Dev A.** |

### 3.4 Lệnh CLI (qua `main.py`, không cần sửa `main.py` – lệnh lạ mặc định sang `fb_upstt`)
| Lệnh | Script | Hành vi | Mã thoát |
|---|---|---|---|
| `--read-identities --account aN` | fb_upstt | `hold_nick` → Chrome ngầm → `verify_and_record` → `read_identities` → `save_identities_file` → note `IDENTITY_NOTES["read"]`; tiến độ `write_progress(acc_dir)` | 0 xong · 3 chưa đăng nhập · 4 bận · 1 lỗi khác (không ghi file) |
| `--identity <id>` (tuỳ chọn) | fb_upstt: `--check-results`, `--joined-groups` · fb_monitor_v4: `--check-results`, `--comment-posts`, `--verify-care` | Danh tính dùng = `--identity` › `post_as` của mục `--campaign` / `--item` › `"self"`; tên lấy từ `post_as_name` của mục (hoặc `identities` của tài khoản). Luồng như 3.5 | như cũ |
| ~~`--join-groups` / `--leave-groups` với danh tính ≠ Cá nhân~~ | fb_upstt | ~~Không làm; chữ `IDENTITY_NOTES["page_join"]`~~ → **ĐỔI vòng 2 (câu 7 đổi): nhận `--identity` / `--campaign`, xin vào / rời bằng Page – xem 3.10e.** Khoá `page_join` giữ trong `IDENTITY_NOTES` (không dùng nữa) | 0 |
| `--read-identities` ở tài khoản Page kiểu cũ | fb_upstt | **Vòng 2:** không đọc, không bấm gì; tiến độ `done, ok=False` chữ `IDENTITY_NOTES["legacy_read"]` (3.10a) | 1 |
| `--logout --account <id phụ>` | fb_upstt | Chấp nhận cả id **không còn trong config** nếu có `accounts/<id>/da_gop.json` (để đăng xuất Chrome tài khoản đã gộp) | như cũ |
| `--once …` | cả 2 | Danh tính lấy từ `campaign["post_as"]` | như cũ |
| `--open-url`, `--open-tabs`, `--open-groups`, `--find-groups`, `--check-inbox` | | Không theo danh tính (Chrome thật / việc của nick) – xem câu PM 8 | |

### 3.5 Luồng một lượt (mọi lệnh mở Chrome làm việc theo danh tính)
> **Vòng 2:** bước 2–3 gói vào `fb_login.begin_identity`, bước 5 vào `fb_login.end_identity`; thêm `assert_identity` trước mỗi bài / bình luận / xin vào / rời; tài khoản Page kiểu cũ KHÔNG gọi `ensure_identity` / `back_to_self` – xem 3.10. Bảng dưới vẫn đúng với nick đã có danh sách Page.
1. `hold_nick` → `open_context` → `verify_and_record` (như cũ).
2. `post_as ≠ "self"` mà `post_as_name == ""` (Page không còn trong tài khoản) → note `missing`, bỏ lượt.
3. `fb_login.ensure_identity(page, post_as, post_as_name, shot_dir=BASE_DIR / "anh_loi")` – **gọi cả khi là "self"** (lượt trước bị `os._exit` có thể để Chrome ở Page). Nick chỉ dùng Cá nhân: không có `i_user` → không bấm gì → chạy y như cũ. Danh tính ≠ Cá nhân → note `ok`.
4. Làm việc; mọi file danh tính dùng `identity_dir(acc_dir, post_as)`; tạm nghỉ / khoá / tiến độ / `commented_ids` dùng `acc_dir`.
5. `finally`: `back_to_self(page, self_name)` (False → note `back_fail`) → `context.close()` → `release_nick`.
- **fb_monitor_v4 `run_account`**: chia các mục đến hạn theo `post_as` (Cá nhân trước, giữ thứ tự), `ensure_identity` 1 lần mỗi danh tính; lỗi → bỏ các mục của danh tính đó, chạy tiếp danh tính khác. `groups_due` / `check_results` / `warn_not_joined` theo từng danh tính.
- **Xem tin nhắn ké** (`check_inbox_page(..., piggyback=True)`) chỉ chạy khi `current_identity(page) == "self"`.
- **`auto_care`**: mỗi tài khoản 1 Chrome; lần lượt từng danh tính có mục đang bật (`post_as`): ensure → `check_results(identity_dir)`; cuối `back_to_self`. **`care_new_approved`**: nhóm mục theo `post_as`, `care_candidates(identity_dir, …)`, gọi `--comment-posts --account aN --identity <id>`.
- **`run_campaign`**: `join_state(..., identity=post_as)`, `recheck_waiting` / `groups_due` / `check_results` / ghi kết quả / nhóm tạm nghỉ theo `identity_dir`; `pause_nick` theo `acc_dir`.

### 3.6 Khi lỗi
| Tình huống | Hành vi | Nhật ký (`fb_login.note`) | Mã thoát |
|---|---|---|---|
| Không chuyển được danh tính | KHÔNG đăng / bình luận / đọc kết quả bằng danh tính đó; ảnh lỗi `anh_loi/<thời gian>_danh_tinh.png`; bỏ lượt (monitor: bỏ mục của danh tính đó); `back_to_self` trong finally | `error.note_text` | 0 |
| Page không còn trong tài khoản | không chuyển, bỏ lượt | `missing` | 0 |
| Không về được Cá nhân | vẫn đóng Chrome; lượt sau `ensure_identity` tự sửa | `back_fail` | giữ mã của lượt |
| Page chưa vào nhóm (đăng bằng Page, lỗi "chưa vào") | bỏ nhóm đó, trạng thái + đếm lỗi nhóm ghi ở `identity_dir` (luật `GROUP_STREAK` cũ); KHÔNG đăng bằng Cá nhân thay | `not_member` (+ dòng lỗi cũ) | 0 |
| Facebook giới hạn khi đang là Page | `pause_nick(acc_dir)` → nghỉ cả nick (câu PM 5) | dòng cũ | như cũ |
| Lượt bị watchdog `os._exit(2)` | finally không chạy → Chrome có thể còn ở Page; lượt sau bước 3 sửa | dòng cũ | 2 |
| `--read-identities` lỗi | không ghi `danh_tinh.json`; tiến độ `done, ok=False` | – | 1 / 3 / 4 |
| Gộp: `merge_plan` có lỗi | không làm gì; hộp báo `errors` | – | – |
| Gộp: chép file lỗi (`OSError`) | raise; config CHƯA lưu; backup còn | – | – |
| Gộp: đăng xuất tài khoản phụ lỗi | gộp đã lưu; `merged_leftovers` → cảnh báo + nút thử lại `--logout` | – | – |
| **(V2)** Danh tính bị đổi giữa lượt (`assert_identity` → `IdentityChanged`) | dừng CẢ lượt (không làm nhóm / bài / mục còn lại, kể cả danh tính khác trong `run_account`); không ghi trạng thái nhóm / bài đang làm; bài chăm `queued`/`sending` → `failed`; `end_identity` trong finally | `error.note_text` (`changed`) | 0 |
| **(V2)** Tài khoản Page kiểu cũ | chạy bằng Page đang mở, không chuyển, không về Cá nhân | `legacy` (once=True) | như cũ |
| **(V2)** `--read-identities` ở tài khoản kiểu cũ | không đọc; không ghi `danh_tinh.json` | tiến độ `legacy_read` | 1 |
| **(V2)** Xin vào bằng Page: hộp "Tham gia với tư cách" không có tên danh tính đang dùng | `Escape`, không xin; tính 1 lượt bấm (an toàn giới hạn); nhóm ghi trạng thái `join_as_missing` | dòng nhóm `   <slug>: ` + `join_as_missing` | 0 |
| **(V2)** Xin vào: Facebook giới hạn khi đang là Page | `pause_nick(acc_dir)` cả nick, dừng | dòng cũ | 0 |
| **(V2)** Gộp: `merge_plan` thấy tài khoản phụ ghép ra Cá nhân / tài khoản chính là kiểu cũ | `ok=False`, không làm gì; hộp báo `errors` (chữ ở 3.10b) | – | – |
| **(V2)** Gộp: `save()` trả False sau `merge_accounts` | DỪNG: không `--logout`, không xoá Chrome phụ; hộp lỗi (chữ ở 3.10g); dữ liệu gộp còn trong bộ nhớ (đánh dấu chưa lưu) | – | – |

### 3.7 Gộp tài khoản (Dev B; PM câu 3)
| Hàm (`tool_store`) | Hành vi |
|---|---|
| `same_uid_groups(data) -> list[list[id]]` | nhóm ≥2 tài khoản cùng `uid` trong `fb_profile.json`, theo thứ tự giao diện; chưa biết uid → bỏ |
| `merge_plan(data, main_id, other_ids) -> dict` | xem trước, KHÔNG sửa gì: `ok, errors, main, mapping {phụ: id danh tính}, scenarios [{id, name, action: doi/tach/bo_trung, account, identity}], copies, logout, backup, lines` (chữ có dấu cho hộp xác nhận). Ghép: tên `fb_profile.json` của tài khoản phụ = tên danh tính của tài khoản chính (không phân biệt hoa thường / khoảng trắng); trùng tên Cá nhân → `"self"`. Không thấy → lỗi "Không thấy Page '<tên>' trong danh sách của '<chính>' – bấm 'Đọc danh sách Page' ở tài khoản chính trước." |
| `merge_accounts(data, main_id, other_ids, stamp, plan=None) -> dict` | (1) backup `config.json` → ~~`config.truoc_gop_<stamp>.json`~~ **vòng 2: `sao_luu/config.truoc_gop_<stamp>.json`** (3.10g); (2) chép `IDENTITY_FILES` của phụ → `identity_dir(chính, id)` (đích có sẵn → gộp, `ket_qua.json` dùng `chuyen_du_lieu.merge_results`), `commented_ids.txt` gộp vào `accounts/<chính>/`, phụ đang tạm nghỉ lâu hơn → chính nghỉ tới cùng lúc; KHÔNG xoá gì ở `accounts/<phụ>/`; (3) kịch bản: `doi` = thay phụ bằng chính tại chỗ, chuyển `members` / `member_times`, `post_as[chính] = id` · `bo_trung` = chính đã tick cùng danh tính → bỏ phụ · `tach` = chính đã tick bằng danh tính khác → kịch bản mới "<tên> (<tên danh tính>)" chỉ tick chính, giữ id mục cũ của phụ (câu PM 6); (4) bỏ phụ khỏi `data["accounts"]`, ghi `accounts/<phụ>/da_gop.json` `{"into", "identity", "time"}`. Trả plan + `"done": True` |
| `merged_leftovers(data) -> list[id]` | thư mục có `da_gop.json` + `browser_profile`, id không còn trong config |
| `account_identities`, `identity_name`, `update_identities(account, found) -> {"added", "renamed", "missing"}` | xem docstring; Page không còn thấy → giữ + `"missing": true` |

Luồng giao diện: cảnh báo "N tài khoản chung 1 nick" (từ `same_uid_groups`, cả khi thêm tài khoản mới sau này) + nút **Gộp vào …** (chọn tài khoản chính, câu PM 10) → (nếu thiếu Page) chạy `--read-identities` cho tài khoản chính → `merge_plan` → hộp xác nhận in `lines` → bấm Gộp: kiểm không tài khoản nào đang chạy → `merge_accounts` → `save(data)` → `--logout --account <phụ>` từng cái (đăng xuất Facebook + xoá `browser_profile` – hàm cũ `fb_login.logout`) → cập nhật lịch. Đăng xuất lỗi → `merged_leftovers` hiện cảnh báo + nút thử lại.

### 3.8 Dòng nhật ký mới – `fb_login.IDENTITY_NOTES` (không đổi chữ; giao diện / test dựa vào)
| Khoá | Chữ |
|---|---|
| `ok` | `👤 Đang dùng: {name}` (chỉ ghi khi danh tính ≠ Cá nhân) |
| `fail` | `⛔ Không chuyển được sang "{name}": bỏ lượt, không đăng / bình luận gì để tránh dùng nhầm danh tính{shot}` – `{shot}` = `shot` bên dưới hoặc "" (dùng `IdentitySwitchFailed.note_text`) |
| `shot` | ` (ảnh: anh_loi/{file})` (khớp `gui_common._parse_event`) |
| `missing` | `⛔ Danh tính "{name}" không còn trong tài khoản {account}: bỏ lượt. Mở kịch bản chọn lại "Đăng bằng".` |
| `back_fail` | `⚠️ Chưa chuyển về Cá nhân được: lượt sau tool tự chuyển lại.` |
| `not_member` | `   ⏭ {name} chưa vào nhóm {group}: bỏ nhóm này, không đăng bằng Cá nhân thay.` |
| `read` | `👤 {account}: đọc được Cá nhân + {pages} Page.` |
| `page_join` | `Xin vào / rời nhóm bằng Page: chưa hỗ trợ – tool chỉ xin vào / rời bằng Cá nhân.` (chữ tiến độ, không phải nhật ký) – **vòng 2: không dùng nữa** (câu 7 đổi), giữ khoá |
| **(V2)** `legacy` | `⚠️ {account}: Chrome đang ở Page "{name}" (tài khoản Page kiểu cũ) → vẫn chạy bằng Page này như trước, không tự chuyển về Cá nhân. Nên Gộp tài khoản này vào tài khoản Cá nhân của nick (màn tài khoản → nút Gộp) để chỉ dùng 1 Chrome.` – ghi `once=True` |
| **(V2)** `changed` | `⛔ Danh tính đang dùng bị đổi giữa chừng (cần "{name}"): dừng lượt, không đăng / bình luận tiếp để tránh dùng nhầm danh tính.` (= `IdentityChanged.note_text`) |
| **(V2)** `legacy_read` | `Chrome của tài khoản này đang ở Page "{name}" (tài khoản Page kiểu cũ) → không đọc danh sách Page ở đây (đọc sẽ đổi danh tính đang đăng). Hãy Gộp tài khoản này vào tài khoản Cá nhân của nick rồi đọc danh sách Page ở tài khoản Cá nhân.` (chữ tiến độ) |
| **(V2)** `join_as_missing` | `không thấy "{name}" trong hộp "Tham gia với tư cách" → không xin, để tránh xin nhầm danh tính` (nhãn kết quả 1 nhóm trong `--join-groups`) |

Chữ đầy đủ nằm trong `fb_login.IDENTITY_NOTES` (khung vòng 2 thêm bằng `IDENTITY_NOTES.update(...)` ở cuối `fb_login.py`).

### 3.9 Không đổi
Cách đăng / xác minh / đọc kết quả / khoá nick; cấu trúc từng file JSON; nick chỉ có Cá nhân chạy y như cũ (không bấm thêm gì trên Facebook, nhật ký giống cũ); `main.py`, `account_status.py`.

### 3.10 Vòng 2 – sửa sau review vòng 1 (CHỐT 25/10/2026; khung ở cuối `fb_login.py` trên `main`)
PM đã quyết: câu 12 = A1, câu 13, câu 14, câu 7 đổi. Mục này **thắng** các dòng cũ của 3.1–3.8 khi lệch (các dòng cũ đã gạch / ghi "vòng 2").

Hàm dùng chung mới (`fb_login`, khung `NotImplementedError` + docstring – Dev A viết thân, Dev C dùng):
| Hàm | Vào → Ra | Ghi chú |
|---|---|---|
| `legacy_page_id(page, acc_dir) -> str` | id Page nếu tài khoản Page kiểu cũ, không thì `""` | chỉ đọc cookie + `danh_tinh.json`, không raise |
| `self_name_of(acc_dir) -> str` | tên Cá nhân cho `back_to_self` / `ensure_identity("self")` | thứ tự: mục "self" của `danh_tinh.json` › tên `fb_profile.json` nếu file KHÔNG có `page_id` › `""` |
| `begin_identity(page, acc_dir, identity_id, name, tool_dir, account_name="", shot_dir=None) -> dict \| None` | `None` = bỏ lượt (đã ghi nhật ký); `run = {"id", "expect", "name", "legacy"}` | thay `fb_upstt.enter_identity`, đoạn `ensure_identity` trong `fb_monitor_v4`, `check_results_cli` |
| `end_identity(page, acc_dir, tool_dir) -> bool` | finally; kiểu cũ → không bấm gì; còn lại `back_to_self(self_name_of)` + note `back_fail` | không bao giờ raise; thay `leave_identity` của cả 2 script |
| `assert_identity(page, expect_id, name="") -> None` | lệch → `IdentityChanged` | chỉ đọc cookie (PM câu 14) |
| `class IdentityChanged(IdentitySwitchFailed)` | `note_text` = `IDENTITY_NOTES["changed"]` | đã viết đủ trong khung |
| `nick_join_usage(acc_dir) -> {"today", "last"}` | đếm xin vào cả nick | 3.10e |
| `PROFILE_PAGE_ID_KEY = "page_id"` | khoá mới trong `fb_profile.json` | 3.10b |

**a) Tài khoản Page kiểu cũ** (PM câu 12 = A1)
- Định nghĩa (khi Chrome đang mở): `danh_tinh.json` của nick **không có Page nào** (chưa từng "Đọc danh sách Page") **và** lúc mở Chrome có cookie `i_user` = P → `legacy_page_id` trả P. Khi không mở Chrome (giao diện, Gộp): `fb_profile.json` có `page_id` ≠ "" (do 3.10b ghi).
- Nick đã có danh sách Page mà Chrome còn ở Page (lượt trước bị `os._exit`) → KHÔNG phải kiểu cũ → `ensure_identity` tự sửa như 3.5.
- Hành vi = **chạy y như bản cũ bằng Page P, KHÔNG BAO GIỜ tự chuyển về Cá nhân**; dữ liệu ở `acc_dir` (danh tính "self" về mặt file, như bản cũ); nhật ký `legacy` (once=True) mỗi lượt.

| Chỗ | Hành vi tài khoản kiểu cũ (`run["legacy"]`) |
|---|---|
| Đầu lượt (`begin_identity`) – fb_upstt `run_campaign`, `auto_care`, `--joined-groups`, `--join/leave-groups`, `check_results_cli`; fb_monitor_v4 `run_account`, `--comment-posts`, `--verify-care` | không `ensure_identity`; `run = {"id": "self", "expect": P, "name": <tên Page trong fb_profile.json nếu page_id == P, không thì P>, "legacy": True}`; note `legacy` |
| finally (`end_identity`) | không bấm gì (không `back_to_self`) |
| `verify_and_record` / `fetch_profile_name` | ghi `page_id = P`, tên = tên Page đang mở (không ghi đè bằng tên Cá nhân) – 3.10b |
| Tin nhắn ké (`check_inbox_page(..., piggyback=True)`) + lệnh `--check-inbox` | như bản cũ: đọc ở danh tính đang mở, KHÔNG chuyển. Nick đã có danh sách Page: ké chỉ khi `current_identity == "self"` (không chuyển chỉ để xem tin); `--check-inbox` riêng: `back_to_self(self_name_of)` rồi đọc như 3.5 |
| Theo dõi (`run_account`) | 1 nhóm danh tính "self" → chạy bằng P, `assert_identity(P)` trước mỗi bình luận, `IDENTITY_DATA_DIR = acc_dir` |
| Chăm bài (`care_new_approved` → `--comment-posts` không `--identity`; `auto_care`) | như trên, bình luận bằng P, `cham_bai.json` ở `acc_dir` |
| Xin vào / rời nhóm | bằng P (như Page – 3.10e), `as_name` = `run["name"]`; tên không rõ (chỉ có id) → hộp "Tham gia với tư cách" ra thì `join_as_missing` |
| `--read-identities` | KHÔNG đọc (đọc sẽ đưa Chrome về Cá nhân + làm tài khoản hết là kiểu cũ → đăng bằng Cá nhân); tiến độ `legacy_read`, mã 1. Muốn dùng nhiều Page: Gộp vào tài khoản Cá nhân (HUONG_DAN) |

**b) `page_id` trong `fb_profile.json` + Gộp ghép theo id** (Dev A ghi, Dev B đọc)
- `fb_profile.json` = `{"name", "uid", "time", "page_id"}` (`page_id` = `legacy_page_id(...)` lúc ghi, `""` = Cá nhân; file cũ thiếu khoá = `""`). Ghi bằng hàm riêng trong `fb_login` (gọi `account_status.write_profile` rồi thêm khoá – `account_status.py` KHÔNG sửa).
- `verify_and_record(page, base_dir, fetch_name=False)`: sau khi đăng nhập OK, `pid = legacy_page_id(page, base_dir)` (chỉ cookie); gọi `fetch_profile_name` khi `fetch_name` **hoặc** chưa có file **hoặc** `read_profile()["page_id"] != pid` (Chrome vừa đổi giữa Page kiểu cũ / Cá nhân).
- `fetch_profile_name(page, base_dir)`: **không bao giờ chuyển danh tính** (bỏ `back_to_self` của vòng 1). `current_identity ≠ "self"` mà `legacy_page_id == ""` (nick có danh sách Page, Chrome còn ở Page do lượt trước bị ngắt) → KHÔNG ghi gì (giữ tên Cá nhân cũ), in log, return. Còn lại đọc tên như cũ (đang ở Page kiểu cũ → tên Page) → ghi `name, uid, page_id`.
- `tool_store.merge_plan` (Dev B): với mỗi tài khoản phụ: (1) `page_id` có → ghép vào danh tính có `id == page_id` của tài khoản chính; không có → lỗi cũ "Không thấy Page '<tên>' …". (2) không có `page_id` (file cũ) → ghép theo tên như vòng 1. (3) **ghép ra `"self"` → lỗi** (thêm vào `errors`, `ok=False` – KHÔNG raise: hộp Gộp đã hiện `errors`; `ValueError` vẫn chỉ dành cho id sai): `"'<phụ>' đang là Cá nhân của nick (trùng '<chính>'), không phải Page → không gộp được. Nếu tài khoản này vốn đăng bằng Page: mở Chrome của nó, chuyển sang Page đó rồi bấm 'Kiểm tra đăng nhập'; nếu chỉ là tài khoản trùng thì xoá tài khoản này."` (4) tài khoản chính có `page_id` → lỗi `"'<chính>' đang ở Page '<tên>' (tài khoản Page kiểu cũ) – chọn tài khoản Cá nhân của nick làm tài khoản chính."` `default_merge_main` bỏ qua tài khoản có `page_id`.

**c) Kiểm `i_user` trước mỗi thao tác** (PM câu 14) – `fb_login.assert_identity(page, run["expect"], run["name"])`, chỉ đọc cookie. **Gọi NGOÀI mọi khối `except RuntimeError / Exception` đang nuốt lỗi** (`IdentityChanged` là `RuntimeError`); chỗ có `except` rộng bao ngoài phải thêm `except fb_login.IdentityChanged: raise` trước.
| Nơi gọi | Dev | Khi lệch |
|---|---|---|
| `fb_upstt.post_to_all_groups` – mỗi nhóm, trước `post_to_group` (trước khối `try`); tham số mới `expect_identity=None` (None = không kiểm, giữ cách gọi cũ) | A | note `note_text`, dừng vòng nhóm (không đếm, không ghi trạng thái nhóm đó), `run_campaign` bỏ tin nhắn ké |
| `fb_upstt` `--join-groups` / `--leave-groups` – trước mỗi `join_group` / `leave_group` | A | dừng, tiến độ `ok=False` |
| `fb_monitor_v4.post_comment_on_article` + `post_comment_on_facebook` – đầu hàm, khi biến module mới `IDENTITY_EXPECT` (tuple `(expect, name)` hoặc None, đặt cạnh `IDENTITY_DATA_DIR` trong `run_account` / `--comment-posts`) | C | `scan_round` + `try` từng mục trong `run_account` phải re-raise; `run_account` bắt ở vòng danh tính → note, **dừng cả lượt** (không sang danh tính khác), bỏ ké |
| `--comment-posts` – vòng bài (qua `post_comment_on_facebook`) | C | bắt `IdentityChanged` trước `except Exception`; bài `queued`/`sending` → `failed`; tiến độ `done, ok=False` chữ `note_text` |
`check_results` / `verify_one` / quét chỉ đọc → không cần kiểm.

**d) Page missing** (PM câu 13): `tool_store.materialize` ghi `post_as_name = ""` khi id Page không còn trong `account_identities` **hoặc** mục đó có `"missing": true` (vẫn giữ `post_as` = id). Luồng chạy: `post_as ≠ "self"` + `post_as_name == ""` → `begin_identity` note `missing`, trả None **trước khi mở menu** (không chuyển, không ảnh lỗi). `fb_monitor_v4.identity_name_of` / `cli_identity` + `fb_upstt.item_identity` khi tra `identities` (lệnh `--identity` không kèm mục): bỏ qua mục `missing: true`. `care_new_approved` / `auto_care` bỏ danh tính missing như hiện tại.

**e) Xin vào / Rời nhóm bằng Page** (câu 7 đổi; Dev A, giao diện Dev B)
- CLI `--join-groups` / `--leave-groups --account aN [--identity <id> | --campaign <id mục>]`: danh tính = `item_identity(...)` như 3.4. Missing → note `missing` + tiến độ `ok=False`, return. Nick tạm nghỉ → như cũ. `hold_nick` → mở Chrome → `verify_and_record` → `run = begin_identity(...)` (None → tiến độ `"Không chuyển được sang \"<tên>\" → không <xin vào / rời> nhóm."`, `ok=False`) → làm → finally `end_identity`.
- Dữ liệu: `id_dir = identity_dir(acc_dir, run["id"])`; `join_state(account, identity=run["id"])`, `set_join_status(id_dir, …)`, `forget_joined(id_dir, …)`, `verify_one(page, id_dir, …)` (câu 11).
- Giới hạn **cả nick**: `usage = fb_login.nick_join_usage(acc_dir)`; dừng khi `usage["today"]` (đọc lại sau mỗi lần bấm, hoặc cộng dồn trong lượt) ≥ `per_day` (`JOIN_PER_DAY`); trước lần bấm xin ĐẦU TIÊN của lượt chờ thêm `JOIN_WAIT_SECONDS - (now - usage["last"])` nếu > 0; giữa 2 nhóm chờ như cũ. Rời nhóm: giới hạn trong lượt như cũ.
- `fb_login.join_group(page, url, answer=None, as_name=None)` (thêm tham số cuối, gọi cũ không đổi) và `_join_as_profile(page, dialog, as_name=None)`: `None` = Cá nhân (chọn lựa chọn đầu như cũ); chuỗi khác rỗng = chọn lựa chọn có nhãn (bỏ dấu cách thừa, NFC, không phân biệt hoa thường) bằng / bắt đầu bằng `as_name`; chuỗi rỗng hoặc không thấy → `Escape`, trả `("join_as_missing", True)` (đã bấm "Tham gia" → tính vào giới hạn). Người gọi: `as_name = None` nếu `run["expect"] == "self"`, ngược lại `run["name"]`. Nhãn kết quả: `IDENTITY_NOTES["join_as_missing"].format(name=...)`.
- `assert_identity` trước mỗi nhóm (3.10c). Facebook giới hạn → `pause_nick(acc_dir)` (cả nick).
- Giao diện (`tool_gui.scope_action`): bỏ loại `as_page`; `todo(a)` đọc `join_state(a["id"], post_as(s, a["id"]))`; job thêm `["--identity", post_as]` khi ≠ "self"; xem trước ghi danh tính: `• <tài khoản> (bằng <tên Page>): xin vào N nhóm`; câu luật: "Mỗi nick tối đa {JOIN_PER_DAY} nhóm/ngày (tính chung Cá nhân + mọi Page), cách nhau {JOIN_WAIT_SECONDS} giây." Nút 🙋 / 🚪 ở mục bằng Page bật lại.

**f) Giao diện đọc theo danh tính** (sửa lỗi, KHÔNG đổi hợp đồng; Dev B). Quy tắc: mọi thứ của 1 mục / 1 ô (tài khoản × kịch bản) đọc `app.item_dir(account, item)` (ket_qua, cham_bai, nhom_tam_nghi…) và `join_state(account_id, post_as(s, account_id))`; tiến độ, tạm nghỉ nick, `commented_ids.txt`, tin nhắn vẫn `account_dir`.
| File | Chỗ (int/003) | Sửa |
|---|---|---|
| `gui_common.py` | `result_level` (`result_rows(self.account_dir…)`), `results_summary`, `results_tab` (`rows = result_rows(acc_dir, …)` – giữ `acc_dir` cho `fb_login_progress` / `kiem_tra_tien_do.json`) | `result_rows(self.item_dir(account, item), …)` |
| `gui_common.py` | `care_state(account, item=None)` – 3 chỗ gọi không truyền `item` (~4713, 4779, 4896) + `names = load_results(self.account_dir…)` (~4711) | truyền `item`; tên nhóm đọc `item_dir` |
| `tool_gui.py` | `join_status`, `membership_text`, `joined_count` (gọi `upstt_store.join_state(account_id)`) | thêm tham số `identity` – người gọi truyền `post_as(s, aid)` / `item["post_as"]` |
| `tool_gui.py` | `sent_7days`, `member_kpis` (ô số liệu: `load_results` / `load_care_state(app.account_dir…)`) | `app.item_dir(account, item)` |
| `tool_gui.py` | bảng nhóm kịch bản `render()` (`states = {a: join_state(a)}`) | `join_state(a["id"], post_as(s, a["id"]))` |
| `tool_gui.py` | `build_member_tab` (`states = upstt_store.join_state(account)`, `result_rows(app.account_dir…)`) | theo `item["post_as"]` / `item_dir` |
| `tool_gui.py` | `group_names` | cộng tên từ `app.identity_dirs(a)` |
| `tool_gui.py` | màn tài khoản "Đang xin vào N nhóm" (~1859), tab "Nhóm đã vào" (`gui_common.joined_groups_tab`) | mức tài khoản: cộng mọi danh tính (`identity_dirs`) hoặc ghi rõ "(Cá nhân)" – không để số Cá nhân giả làm số cả nick |

**g) Sao lưu + an toàn khi Gộp** (Dev B)
- `tool_store`: `MERGE_BACKUP_DIR = "sao_luu"`; sao lưu ở `BASE_DIR / "sao_luu" / "config.truoc_gop_<stamp>.json"` (tạo thư mục; `dong_goi.ps1` chỉ chép file ở gốc tool → thư mục con không bao giờ vào bản gửi khách, không cần sửa `dong_goi.ps1`). `merge_accounts` trả `backup = "sao_luu/config.truoc_gop_<stamp>.json"`; dòng xem trước trong `lines` đổi theo.
- `tool_gui.merge_dialog.run`: `if not self.save(quiet=True)` → DỪNG: không `logout_merged`, không xoá Chrome phụ; hộp lỗi `"Đã gộp trong tool nhưng LƯU cấu hình bị lỗi → CHƯA đăng xuất / xoá Chrome của tài khoản phụ.\n\nBấm Lưu (Ctrl+S) thử lại. Lưu được thì tool hiện cảnh báo 'Chrome tài khoản đã gộp chưa xoá' kèm nút thử lại. Cấu hình trước khi gộp: sao_luu/<file>."`; dữ liệu trong bộ nhớ giữ trạng thái chưa lưu (`mark_dirty`). Sau khi lưu được: `merged_leftovers` hiện cảnh báo + nút thử lại như 3.7.

**h) Tên Cá nhân dùng chung**: mọi chỗ cần tên Cá nhân (`back_to_self`, `ensure_identity("self")`) dùng `fb_login.self_name_of(acc_dir)` – qua `begin_identity` / `end_identity`. Xoá các chỗ tự đọc `account_status.read_profile(acc_dir)["name"]` trong `fb_upstt` (`enter_identity`, `leave_identity`, `check_inbox`), `fb_login.check_results_cli`, `fb_monitor_v4.self_name_of` / `leave_identity` (thay bằng hàm của `fb_login`). `run_account` không truyền tên rỗng / tên Page cho `ensure_identity("self")` nữa.

`check_results_cli(acc_dir, slugs, open_ctx, note=print, identity=None)`: `identity = {"id", "name", "account_name"?}`; bên trong dùng `begin_identity(page, acc_dir, id, name, tool_dir=Path(acc_dir).parent.parent, account_name=...)` (None → không đọc, tiến độ `ok=False`) + `end_identity` trong finally; `identity=None` = "self" (vẫn qua `begin_identity` để tài khoản kiểu cũ không bị kéo về Cá nhân). Chữ ký không đổi.

### 3b. Kết quả thử thật (25/10/2026, Tài khoản 4, cách B – chỉ chuyển, không đăng)
Chuyển Cá nhân → Page "HTX chó mèo" → về Cá nhân: **thành công**. Ảnh + dữ liệu: `scratchpad/f9_probe/` (không đưa vào repo).

| Việc | Cách làm đã kiểm chứng |
|---|---|
| Mở menu tài khoản | nút `role=button`, `aria-label="Account, your profile"` (trong `role=banner`). ⚠ Nhãn cũ "Trang cá nhân của bạn" giờ chỉ còn trên `svg` – **`fb_login.fetch_profile_name` và `_logout_on_facebook` đang dùng nhãn cũ, cần sửa trong task này** |
| Hộp menu | `div[role=dialog]:not([aria-label='Messenger']):visible` (luôn có 1 hộp Messenger ẩn) |
| Chuyển sang danh tính X | trong menu có sẵn nút `role=button` tên **"Chuyển sang X"** (cả khi đang ở Page: "Chuyển sang <tên cá nhân>"). Bấm → chờ ~8 giây, trang tải lại |
| Danh sách đủ (khi có ≥2 Page) | nút "Xem tất cả trang cá nhân" → hộp "Chọn trang cá nhân", mỗi danh tính 1 nút `"<tên>, N thông báo"`, danh tính đang dùng có thêm **", đang chọn"** |
| Biết đang ở danh tính nào | cookie **`i_user`** = id Page khi đang là Page (`61595395697904` cho HTX chó mèo), **không có** khi là Cá nhân; `c_user` luôn là id cá nhân. Dòng đầu menu = tên danh tính đang dùng |
| Id danh tính (cho `identities[].id`) | Page: giá trị `i_user` sau khi chuyển; Cá nhân: `"self"` |

## 4. Chia việc (CHỐT – không trùng file giữa các vai; cả 3 Dev làm song song trên khung đã commit)
| Vai | Nhánh | File được sửa (chỉ những file này) | Việc |
|---|---|---|---|
| Dev A | feat/003-danh-tinh | `fb_login.py`, `fb_upstt.py`, `upstt_store.py` | Thân 8 hàm mới của `fb_login` (3.3) + `check_results_cli(identity=)`; sửa nhãn menu trong `fetch_profile_name` / `_logout_on_facebook` (+ về Cá nhân trước khi đọc tên). `fb_upstt`: `run_campaign`, `care_new_approved`, `auto_care` theo 3.5; CLI `--read-identities`, `--identity` cho `--check-results` / `--joined-groups`, chặn `--join-groups` / `--leave-groups` bằng Page, `--logout` cho tài khoản đã gộp (3.4); xem tin nhắn ké chỉ khi ở Cá nhân. `upstt_store`: `join_state(identity=)`, `pause_notes` / `reset_pause(identity=)` đọc `identity_dir` |
| Dev B | feat/003-giao-dien | `tool_store.py`, `tool_gui.py`, `gui_common.py`, `HUONG_DAN.md` | `tool_store`: `materialize` ghi `post_as` + `post_as_name`; thân 7 hàm mới (3.7); `reset_pause` truyền `identity`; `warnings` báo mục đăng bằng Page không còn. Giao diện: ô **Đăng bằng** cho từng tài khoản tick trong tab "Tài khoản chạy" (kịch bản đăng bài + theo dõi; mặc định Cá nhân); nút **Đọc danh sách Page** + danh sách danh tính ở màn tài khoản (chạy `--read-identities`, đọc `danh_tinh.json`, `update_identities`, Lưu); cảnh báo trùng uid + nút **Gộp vào …** + hộp xác nhận + chạy `--logout` + cảnh báo `merged_leftovers`; mọi bảng của 1 mục (kết quả, trạng thái nhóm, chăm bài, ghi chú tạm nghỉ) đọc `identity_dir` theo `post_as` của mục, lệnh gọi từ mục truyền `--campaign` / `--identity`; số liệu cả tài khoản cộng mọi danh tính; nút Xin vào / Rời nhóm và "Mở" Chrome thật với mục bằng Page theo câu PM 7, 8. `HUONG_DAN.md` mục "Dùng Page" |
| Dev C | feat/003-theo-doi | `fb_monitor_v4.py`, `monitor_store.py` | `run_account` theo 3.5 (chia mục theo danh tính); `warn_not_joined`, `groups_due` / `check_results`, `record_sent`, `binh_luan_loi.json` theo `identity_dir`; `pause_nick`, `commented_ids.txt` theo `acc_dir`; `--comment-posts` / `--verify-care` / `--check-results` nhận danh tính (3.4); tin nhắn ké chỉ ở Cá nhân. `monitor_store`: `pause_notes` / `reset_pause(identity=)` |
| Tester | test/003-danh-tinh | `tests/test_003_*.py`, `tests/trang_gia/` | Trang HTML giả: banner có nút `aria-label="Account, your profile"`, hộp menu có nút "Chuyển sang <tên>" / "Xem tất cả trang cá nhân" / hộp "Chọn trang cá nhân" (có ", đang chọn"); giả cookie `i_user` (Playwright `context.add_cookies`). Test: `identity_dir`, `current_identity`, `switch_identity` / `ensure_identity` / `back_to_self` (đúng / sai / đã đúng thì không bấm), `IdentitySwitchFailed.note_text`; `materialize` sinh `post_as`; `update_identities`; `same_uid_groups`, `merge_plan`, `merge_accounts` với config + `accounts/` giả trong `tmp_path` (đủ 3 trường hợp doi / bo_trung / tach, backup, marker); config cũ mở được |

Không vai nào sửa: `main.py`, `account_status.py`, `dong_goi.ps1` (task 001 đang sửa), mục 8 của plan. Không có file mới ở gốc tool (không ảnh hưởng `dong_goi.ps1`). `tests/test_khung_003.py` là test khung của Architect (Tester không cần sửa).

**Phụ thuộc giữa các Dev** (đều gọi qua chữ ký trong khung → làm song song; tự chạy thử bằng `monkeypatch` hàm còn `NotImplementedError`, chạy thật ở `int/003`):
| Ai dùng | Dùng của ai | Cái gì |
|---|---|---|
| Dev B | Dev A | `fb_login.identity_dir`, `IDENTITY_FILES`, `load_identities_file`, lệnh `--read-identities` / `--identity` / `--logout` tài khoản đã gộp; `upstt_store.join_state(identity=)` |
| Dev C | Dev A | `fb_login.identity_dir`, `ensure_identity`, `back_to_self`, `current_identity`, `IdentitySwitchFailed`, `IDENTITY_NOTES`, `check_results_cli(identity=)`; `upstt_store.join_state(identity=)` |
| Dev A, Dev C | Dev B | `campaign["post_as"]`, `campaign["post_as_name"]` do `materialize` ghi (khung đã có mặc định "self" → chưa có Dev B vẫn chạy như cũ) |
| Dev A | Dev C | `--comment-posts --identity` (chăm bài) |
| Dev B | Dev C | `monitor_store.reset_pause(identity=)` (chữ ký đã có trong khung) |

Đối chiếu plan khác: #001 (Đang làm) chỉ sửa `dong_goi.ps1` + `tests/test_001_*` → không trùng. #002 PM gác lại → không chạy song song.

### 4.2 Chia việc VÒNG 2 (sau review vòng 1 – hợp đồng 3.10). Cùng nhánh, cùng file như bảng trên; merge `main` (khung vòng 2) vào nhánh trước khi làm.
| Vai | File | Việc |
|---|---|---|
| Dev A | `fb_login.py`, `fb_upstt.py`, `upstt_store.py` | **fb_login:** thân 6 hàm khung cuối file (`legacy_page_id`, `self_name_of`, `begin_identity`, `end_identity`, `assert_identity`, `nick_join_usage`); `verify_and_record` + `fetch_profile_name` theo 3.10b (bỏ `back_to_self`, ghi `page_id`); `join_group(..., as_name=None)` + `_join_as_profile(..., as_name=None)` (3.10e); `check_results_cli` qua `begin_identity` / `end_identity` (3.10h). **fb_upstt:** thay `enter_identity` / `leave_identity` bằng hàm `fb_login` ở `run_campaign`, `auto_care`, `--joined-groups`; `post_to_all_groups(expect_identity=)` + `assert_identity` mỗi nhóm (3.10c); tin nhắn ké + `check_inbox` theo 3.10a; `--join-groups` / `--leave-groups` bằng danh tính (3.10e – bỏ chặn `page_join`, bỏ `enter_identity(SELF)`); `--read-identities` chặn tài khoản kiểu cũ (`legacy_read`, mã 1); `item_identity` bỏ qua `missing`; truyền `account_name` cho `check_results_cli`. **upstt_store:** không đổi hợp đồng (chỉ sửa nếu cần cho `join_state(identity=)` với id kiểu cũ = "self") |
| Dev B | `tool_store.py`, `tool_gui.py`, `gui_common.py`, `HUONG_DAN.md` | **tool_store:** `materialize` → `post_as_name=""` khi Page missing / không còn (3.10d); `merge_plan` ghép theo `page_id` trước, tên sau, lỗi "ra Cá nhân" + "tài khoản chính kiểu cũ" (3.10b); `default_merge_main` bỏ tài khoản có `page_id`; sao lưu `sao_luu/` (3.10g). **tool_gui / gui_common:** đọc theo danh tính mọi chỗ ở 3.10f; Gộp: `save()` False → dừng, không logout, hộp lỗi (3.10g); bật lại 🙋 Xin vào / 🚪 Rời cho mục bằng Page, truyền `--identity`, đọc `join_state` theo danh tính, câu luật "tính chung cả nick" (3.10e). **HUONG_DAN.md:** đoạn "Tài khoản Page kiểu cũ" (chạy như cũ + nên Gộp; muốn đọc danh sách Page thì Gộp vào tài khoản Cá nhân), xin vào nhóm bằng Page (giới hạn chung cả nick), file sao lưu ở `sao_luu/` |
| Dev C | `fb_monitor_v4.py`, `monitor_store.py` | `run_account`: mỗi nhóm danh tính `run = fb_login.begin_identity(...)` (None → bỏ mục của danh tính đó), `IDENTITY_DATA_DIR = identity_dir(acc_dir, run["id"])`, biến mới `IDENTITY_EXPECT`; `assert_identity` đầu `post_comment_on_article` / `post_comment_on_facebook`; `IdentityChanged` re-raise qua `scan_round` + `try` từng mục → dừng cả lượt (3.10c); finally `fb_login.end_identity`; tin nhắn ké theo 3.10a (KHÔNG `back_to_self` trước ké); `--comment-posts` / `--verify-care` qua `begin_identity` / `end_identity`, bắt `IdentityChanged`; `--check-results` truyền `account_name`; `identity_name_of` / `cli_identity` bỏ qua `missing`; xoá `self_name_of` / `leave_identity` riêng (dùng `fb_login`). `monitor_store`: không đổi hợp đồng |
| Tester | `tests/test_003_*.py`, `tests/trang_gia/` | Test mới: `legacy_page_id` (không danh_tinh + i_user → P; có Page trong danh_tinh → ""; không i_user → ""); `self_name_of` (thứ tự nguồn, bỏ tên khi có `page_id`); `begin_identity` (missing → None + không gọi `ensure_identity`; kiểu cũ → không gọi `ensure_identity`, `run.legacy`, note `legacy`; Page lỗi → None + `note_text`); `end_identity` (kiểu cũ → không gọi `back_to_self`; không raise); `assert_identity` / `IdentityChanged.note_text`; `fetch_profile_name` ở Page kiểu cũ không chuyển + ghi `page_id` + tên Page (trang giả); `join_group(as_name=)` chọn đúng Page / `join_as_missing` (trang giả hộp "Tham gia với tư cách"); `nick_join_usage` cộng nhiều thư mục; `merge_plan` ghép theo `page_id`, lỗi khi ra "self", lỗi khi chính có `page_id`; `merge_accounts` sao lưu vào `sao_luu/`; `materialize` → `post_as_name=""` khi `missing`; luồng chạy (giả `fb_login` như `test_003_luong_chay.py`): tài khoản kiểu cũ chạy 2 lượt liền không gọi `ensure_identity` / `back_to_self`, `IdentityChanged` giữa vòng nhóm dừng lượt |

Phụ thuộc vòng 2: Dev C dùng 6 hàm khung của Dev A (chữ ký đã có trên `main` → tự `monkeypatch` khi Dev A chưa xong). Dev B dùng khoá `page_id` (Dev A ghi) – đọc thẳng `fb_profile.json`, thiếu khoá = "". Không thêm file mới ở gốc tool (`sao_luu/` là thư mục do tool tạo lúc Gộp).

## 5. Tiêu chí xong
- [ ] Mỗi nick chỉ còn 1 thư mục Chrome; không còn 2 tài khoản trong tool cùng uid.
- [ ] Kịch bản "Đăng bằng Thư Tình" → bài lên nhóm dưới tên Thư Tình; xong lượt Chrome đang ở Cá nhân.
- [ ] Không chuyển được danh tính → không đăng gì.
- [ ] Gộp a3, a6 vào a5 không mất kịch bản / kết quả; có backup.
- [ ] Config cũ (chưa có `identities`) mở được, mặc định Cá nhân.
- [ ] Nick chỉ dùng Cá nhân: lượt chạy không bấm thêm gì trên Facebook, nhật ký giống bản cũ.
- [ ] Mọi lượt dùng danh tính kết thúc ở Cá nhân (`back_to_self` trong finally), kể cả khi lỗi giữa chừng.
- [ ] Dữ liệu Page nằm ở `accounts/<id>/danh_tinh/<id Page>/`; dữ liệu Cá nhân giữ file cũ.
- [ ] Theo dõi + bình luận (quét, chăm bài) bằng đúng danh tính kịch bản chọn; 1 bài không bị cả nick bình luận 2 lần.
- [ ] Page bị xoá khỏi tài khoản / không còn → mục đó không đăng, không đổi sang Cá nhân.
- [ ] Chrome của tài khoản phụ đã đăng xuất + xoá; lỗi thì có cảnh báo + nút thử lại.
- [ ] Bảng kết quả / trạng thái nhóm / chăm bài của mục bằng Page hiện số liệu của Page, không lẫn Cá nhân.
- [ ] (V2) Tài khoản Page kiểu cũ (chưa Gộp) chạy đăng bài / theo dõi / chăm bài nhiều lượt: luôn bằng Page đó, không lượt nào chuyển về Cá nhân; nhật ký có dòng nhắc Gộp.
- [ ] (V2) "Kiểm tra đăng nhập" ở tài khoản Page kiểu cũ giữ tên Page + ghi `page_id`; Gộp sau đó ghép đúng Page (không ra Cá nhân); ghép ra Cá nhân → báo lỗi, không gộp.
- [ ] (V2) Page `missing` → bỏ lượt ngay, không mở menu, không ảnh lỗi.
- [ ] (V2) Danh tính bị đổi giữa lượt → dừng ngay trước bài / bình luận kế tiếp.
- [ ] (V2) Xin vào / rời nhóm bằng Page được; giới hạn 10 nhóm/ngày tính chung cả nick.
- [ ] (V2) Gộp: lưu cấu hình lỗi → không đăng xuất / xoá Chrome phụ; sao lưu nằm ở `sao_luu/`.

## 6. Checklist test tay (nick test + Page test + nhóm test)
| # | Bước | Mong đợi | Kết quả |
|---|---|---|---|
| 1 | Đọc danh sách Page | Hiện đủ Page nick quản lý | |
| 2 | Đăng ngay bằng Page vào nhóm test | Bài hiện tên Page | |
| 3 | Đăng ngay bằng Cá nhân sau đó | Bài hiện tên cá nhân | |
| 4 | Mở Chrome nick sau lượt chạy | Đang ở Cá nhân | |
| 5 | Page chưa vào nhóm | Tool báo, không đăng bằng cá nhân thay | |
| 6 | Đổi tên Page trên Facebook → Đọc danh sách Page lần nữa | Tên mới hiện, kịch bản vẫn chọn đúng Page (id giữ) | |
| 7 | Kịch bản theo dõi "Đăng bằng" Page, Quét ngay nhóm test có bài khớp từ khoá | Bình luận hiện tên Page; xong lượt Chrome ở Cá nhân | |
| 8 | Bài đăng bằng Page được duyệt → Cập nhật kết quả + tự chăm | Kết quả hiện ở mục bằng Page; bình luận chăm hiện tên Page | |
| 9 | Đang chạy lượt bằng Page thì đóng cửa sổ đen / tắt máy giữa chừng; chạy lại | Lượt sau tự chuyển đúng danh tính trước khi làm | |
| 10 | Bấm Gộp (a3, a6 → a5; a2 → a4) | Hộp xác nhận liệt kê đủ; sau Gộp: có `config.truoc_gop_*.json`, tài khoản phụ biến mất, kịch bản tick tài khoản chính + "Đăng bằng" đúng Page, Kết quả cũ còn; Facebook › "Nơi bạn đã đăng nhập" không còn phiên của Chrome phụ | |
| 11 | Mục đăng bằng Page: tab Kết quả / Trạng thái nhóm | Chỉ số liệu của Page | |
| 12 | (V2, TRƯỚC khi Gộp) Tài khoản Page kiểu cũ (vd a3: Chrome đang ở Page): Đăng ngay vào nhóm test 2 lượt liền; Quét ngay 1 lượt | Cả 2 bài + bình luận hiện tên **Page**, không bài nào tên Cá nhân; nhật ký có dòng "⚠️ … tài khoản Page kiểu cũ … Nên Gộp"; mở Chrome sau lượt vẫn ở Page | |
| 13 | (V2) Ở tài khoản kiểu cũ bấm "Kiểm tra đăng nhập", rồi Gộp vào tài khoản Cá nhân | Tên Facebook vẫn là tên Page; hộp Gộp ghi "→ thành danh tính Page '<tên>'" (không phải Cá nhân); sau Gộp kịch bản "Đăng bằng" đúng Page | |
| 14 | (V2) Xin vào nhóm test bằng Page (mục đăng bằng Page → 🙋 Xin vào) | Nhóm nhận yêu cầu / thành viên là **Page**; trạng thái nhóm hiện ở mục bằng Page, không ở mục Cá nhân; xong lượt Chrome ở Cá nhân | |
| 15 | (V2) Gộp với `config.json` đang bị khoá ghi (vd mở bằng Notepad++ khoá / thuộc tính chỉ đọc) | Hộp lỗi lưu; Chrome phụ CHƯA bị đăng xuất / xoá; file sao lưu ở `sao_luu/` | |

## 7. Câu hỏi cho PM
| # | Câu hỏi | Đề xuất | PM quyết |
|---|---|---|---|
| 1 | Cách chuyển: (A) chọn "Đăng với tư cách" trong hộp đăng của nhóm, hay (B) chuyển cả trang sang Page rồi chuyển về? | Cho thử trên nick test | **B** – chuyển cả trang sang Page (như người thật), xong việc chuyển về Cá nhân |
| 2 | Page chưa vào nhóm thì: bỏ nhóm đó, hay tự xin vào bằng Page? | Bỏ + báo, xin vào làm sau | **Theo đề xuất**: bỏ nhóm đó + báo trong nhật ký, KHÔNG đăng bằng Cá nhân thay; xin vào bằng Page làm việc sau |
| 3 | Gộp "Tai khoan 2", "tai khoan 1" → "Tài khoản 5" và "Tài khoản 3" → "Tài khoản 4" ngay khi cập nhật, hay để bạn bấm nút "Gộp"? | Bạn bấm nút, có hộp xác nhận | **Bấm nút**: tool chỉ hiện cảnh báo "N tài khoản chung 1 nick" + nút **Gộp vào …**; bấm → hộp xác nhận liệt kê việc sẽ làm (Page nào vào đâu, kịch bản đổi ra sao, có backup, Chrome nào bị đăng xuất + xoá) → bấm Gộp mới làm |
| 4 | Theo dõi nhóm + bình luận khách: dùng danh tính nào? | Chọn được như đăng bài | **Như đăng bài**: kịch bản theo dõi chọn danh tính; là Page thì vừa mở Chrome là chuyển sang Page luôn rồi mới quét / bình luận |
| 5 | (Dựng khung) Facebook báo "đăng quá nhiều" khi đang là Page: trước đây Cá nhân và mỗi Page **nghỉ riêng** (mỗi cái 1 tài khoản tool). Giờ chung 1 Chrome – nghỉ riêng từng danh tính hay nghỉ **cả nick**? | Nghỉ cả nick (an toàn hơn, cùng 1 thiết bị; ít sửa) – hợp đồng 3.2 đang theo đề xuất này | **Theo đề xuất** (PM 25/10) |
| 6 | (Dựng khung) Kịch bản đang tick CẢ tài khoản chính lẫn tài khoản phụ (vd a5 Cá nhân + a3 Page cùng đăng 1 nội dung): khi gộp, 1 tài khoản chỉ chọn được 1 "Đăng bằng" mỗi kịch bản | Tách thành kịch bản bản sao "<tên> (<tên Page>)" chỉ tick tài khoản chính bằng Page (hợp đồng 3.7 `tach`). Cách khác: cho 1 kịch bản chọn nhiều danh tính / tài khoản (đổi cấu trúc, lớn hơn) | **Theo đề xuất** (PM 25/10) |
| 7 | (Dựng khung) Mục đăng bằng Page: nút 🙋 Xin vào / 🚪 Rời nhóm làm gì? | Tắt nút + chú thích "Xin vào bằng Page: làm sau" (theo câu 2) | ~~Theo đề xuất~~ → **ĐỔI (PM 25/10, sau câu 11): Page được Xin vào / Rời nhóm như Cá nhân.** Hợp đồng bổ sung: `--join-groups` / `--leave-groups` nhận `--identity` (ensure_identity trước, back_to_self sau); hộp "Tham gia với tư cách" chọn đúng Page đang dùng (không chọn Cá nhân); trạng thái xin vào ghi ở `identity_dir`; giới hạn 10 nhóm/ngày và chờ 45 giây tính chung **cả nick** (như tạm nghỉ – câu 5); Facebook giới hạn → `pause_nick` cả nick. Giao diện bật lại nút, truyền `--identity`. Câu 2 (Page chưa vào nhóm khi **đăng** → bỏ qua + báo) giữ nguyên |
| 8 | (Dựng khung) Nút "Mở" (mở Chrome THẬT xem "Nội dung của bạn", mở bài để chăm tay): Chrome thật không do tool điều khiển → tool không tự chuyển sang Page được | Vẫn mở (ở Cá nhân) + hiện nhắc "Bấm ảnh đại diện góc phải → Chuyển sang <Page>" | **Theo đề xuất** (PM 25/10) |
| 9 | (Dựng khung) Đọc danh sách Page: nếu trang không cho đọc id Page, tool phải chuyển lần lượt sang từng Page (~8 giây/Page, tối đa 10) rồi về Cá nhân | Chấp nhận (chỉ khi bạn bấm nút, không chạy theo lịch) | **Theo đề xuất** (PM 25/10) |
| 10 | (Dựng khung) Gộp: tài khoản nào là tài khoản chính (giữ Chrome)? | Nút "Gộp vào …" có ô chọn; mặc định tài khoản có tên Facebook là tên Cá nhân, không có thì tài khoản đứng đầu | **Theo đề xuất** (PM 25/10) |

Ghi chú: đăng bài, theo dõi, chăm bài, kiểm kết quả của cùng một tài khoản **dùng chung 1 thư mục Chrome** (`accounts/<mã>/browser_profile`, cả `fb_upstt.open_account_context` lẫn `fb_monitor_v4` đều gọi `fb_login.open_context(account_dir)`), và không bao giờ mở cùng lúc (khoá thư mục + `hold_nick`). Vì vậy mỗi lượt phải **tự chuyển đúng danh tính lúc bắt đầu** và **chuyển về Cá nhân lúc kết thúc** – lượt trước để Chrome ở Page nào thì lượt sau không được tin là vẫn ở đó.

| 11 | (Dev A) Xác minh nhóm khi đang là Page (`verify_one`: xem lại nhóm chờ duyệt, `--joined-groups`): có tự trả lời câu hỏi tham gia + bấm "Vẫy tay chào" bằng Page không? | Chặn (theo câu 2) | **(a) Cho Page làm như Cá nhân** – PM 25/10: "page vẫn làm như trang cá nhân bình thường" |

| 12 | (Review vòng 1, lỗi 1) Tài khoản Page kiểu cũ (chưa Gộp, `identities` trống, Chrome đang ở Page – có `i_user`): bản mới làm gì? | A1: chạy như cũ bằng Page đó + nhật ký nhắc Gộp; KHÔNG BAO GIỜ tự chuyển về Cá nhân | **A1 – theo đề xuất** (PM 25/10) |
| 13 | (Review vòng 1) Page `missing`: bỏ lượt ngay hay vẫn thử chuyển (~40 giây + ảnh lỗi)? | Bỏ lượt ngay, `post_as_name=""`, không thao tác Facebook | **Theo đề xuất** (PM 25/10) |
| 14 | (Review vòng 1) Đọc lại cookie `i_user` trước MỖI bài đăng / bình luận, lệch thì dừng lượt | Làm | **Theo đề xuất** (PM 25/10) |

## 8. Tiến độ (chỉ Điều phối ghi)
| Thời gian | Bước | Vai | Nhánh / commit | Kết quả |
|---|---|---|---|---|
| 25/10 | 1 Lập kế hoạch | Điều phối | main | Bản nháp, chờ PM trả lời mục 7 |
| 25/10 | 1 Lập kế hoạch | Điều phối + PM | main | PM trả lời đủ 4 câu (B, bỏ nhóm, nút Gộp, theo dõi theo danh tính) |
| 25/10 | 1 Thử thật | Điều phối | – | TK4: chuyển sang HTX chó mèo + về Cá nhân thành công; cách nhận biết = cookie `i_user` (mục 3b) |
