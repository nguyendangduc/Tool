# Hướng dẫn Tool Facebook – Đăng bài & Theo dõi nhóm

*© 2026 BánhBaoChiên AutoTool. Bảo lưu mọi quyền. Nghiêm cấm sao chép, chia sẻ, bán lại khi chưa có sự đồng ý bằng văn bản. Xem `BAN_QUYEN.txt`.*

Một tool làm 2 việc, dùng chung tài khoản Facebook:

- **📝 Đăng bài**: tự đăng bài vào các nhóm Facebook **đúng giờ bạn chọn mỗi ngày**.
- **🔎 Theo dõi nhóm**: tự quét các nhóm theo chu kỳ (mặc định **40 phút**), tìm bài có **từ khóa** của bạn, gửi về **Telegram** và tự **bình luận** (nếu bật).

Một tool chạy được **nhiều tài khoản**. Mỗi tài khoản có nhiều **nội dung đăng** và nhiều **nhóm theo dõi**, mỗi mục có cài đặt riêng.

**Yêu cầu:** Windows 10 hoặc 11, có Internet. **Không cần cài gì trước**, tool tự cài.

| File | Dùng khi |
|---|---|
| **`CAI_DAT.bat`** | Cài đặt: lần đầu dùng tool, hoặc khi tool bị lỗi (tự cài phần còn thiếu, cập nhật lịch chạy) |
| **`MO_TOOL.bat`** | Mở **giao diện**: cấu hình, **đăng nhập** / đổi / đăng xuất tài khoản Facebook, xem kết quả, nhật ký, tạm dừng |

---

## Cài đặt (làm 1 lần)

**Bước 1. Cài đặt:** bấm đúp **`CAI_DAT.bat`** → bấm **Yes**.
- Nếu hiện màn hình "Windows protected your PC" thì bấm **More info** → **Run anyway**.
- Lần đầu tool **tự tải và cài** phần mềm cần thiết, mất **5–10 phút**. Cứ để yên đến khi thấy **CAI DAT XONG**.

**Bước 2. Cấu hình và đăng nhập:** bấm đúp **`MO_TOOL.bat`** → bấm **Yes** → giao diện mở ra:
1. Bấm **＋ Tài khoản** → bấm **Đăng nhập** → Chrome mở ra: đăng nhập Facebook, thấy trang chủ thì **đóng Chrome**. Điện thoại hỏi xác nhận thì chọn **"Đúng, là tôi"** (không chọn Chặn).
2. Chọn tài khoản rồi bấm:
   - **＋ 📝 Đăng bài** → điền **nhóm Facebook**, **nội dung bài**, **giờ đăng**.
   - **＋ 🔎 Theo dõi** → điền **nhóm Facebook**, **từ khóa**, **Telegram** (bấm *Gửi thử Telegram*), bình luận.
3. Bấm **Lưu**. Xong: tool tự chạy theo lịch.

---

## Giao diện (`MO_TOOL.bat`)

Giống AutoNuoi, cột trái có **2 tab** (Kịch bản · Tài khoản), mỗi tab là một bảng có cột:

```
📋 Kịch bản  › tài khoản chạy            Giờ / nhóm      Kết quả
  📝 Đăng bài (12)                                        🔴 2 🟠 2      ← thư mục theo loại, gập/mở được (tool nhớ)
     📝 Thiệp cưới                       06:30           🔴 lỗi       ← kịch bản lỗi lên đầu, kịch bản tắt (⏸) xuống cuối
        👤 Tài khoản 4 · Mạnh Quân       06:30           🔴 lỗi       ← tên trong tool · tên Facebook
        👤 Tài khoản 5 · Ngọc Anh        06:45           🟢 tốt       ← giờ tự lùi theo giãn cách
  🔎 Theo dõi nhóm (3)
👤 Tài khoản                Tên Facebook      Trạng thái              ← đăng nhập, nhóm tài khoản (Nick mới / Nick lâu năm…)
```

**Kịch bản** (chọn dòng 📝 / 🔎) – tab **📝 Đăng bài**, soạn chung cho mọi tài khoản chạy kịch bản:

1. **Nhóm sẽ đăng** – bảng nhóm của kịch bản, mỗi tài khoản 1 cột trạng thái. **Khi đăng theo lịch, mỗi tài khoản chỉ đăng vào nhóm nó ĐÃ VÀO.**
   - **Vào được nhóm là tool xác minh ngay**: mở nhóm, đóng bảng "Chào mừng", bấm đồng ý nội quy (nếu có), bấm thử ô "Bạn viết gì đi" và mở được hộp "Tạo bài viết" (đóng lại, không đăng gì).
   - Kết quả xác minh có 3 mức:
     - **✅ đã xác minh**: nhóm này đăng / theo dõi được ngay. Đăng thành công 1 lần cũng tính là đã xác minh.
     - **⚠ vào – cần xử lý**: xác minh thấy vướng, ví dụ nhóm chỉ cho quản trị viên đăng hoặc bắt trả lời câu hỏi. Lý do hiện ngay dưới bảng.
     - **⏳ đang xác minh**: vừa vào, tool chưa chạy xong.
   - Xác minh chạy vào các lúc:
     - **Xin vào** mà vào được luôn (nhóm công khai).
     - Nhóm **được quản trị viên duyệt**: lượt đăng theo lịch cứ 3 tiếng mở lại nhóm đang chờ 1 lần, thấy đã duyệt thì xác minh rồi **đăng luôn trong lượt đó**. Bấm **🔄 Cập nhật trạng thái** thì cũng xác minh luôn.
   - Trạng thái khác: **⏳ chờ duyệt** · **❓ câu hỏi** (nhóm hỏi câu hỏi tham gia – bạn tự mở nhóm trả lời) · **– chưa vào** · ⚠ chưa rõ · "tạm nghỉ" (nhóm đang lỗi).
   - Phía trên: **🔍 Tìm nhóm** · **＋ Dán link** · **🔄 Cập nhật trạng thái**. Nút này đọc nhóm từng tài khoản đang ở, chuyển ⏳/❓ thành đã vào khi được duyệt, nhóm đã rời thành "chưa vào", rồi xác minh **mọi** nhóm tài khoản sẽ đăng mà chưa xác minh xong (cách nhau 8 giây).
   - **Bấm vào dòng nhóm để tick** (☐ → ☑), "Tick hết", ô **Lọc**: Có tài khoản chưa vào / Đã vào nhưng chưa xác minh / Đang chờ duyệt / Có lỗi. Bấm đúp = mở nhóm.
   - Tick nhóm rồi chọn việc:
     - **🙋 Xin vào** → hộp chọn **Tất cả tài khoản của kịch bản** hoặc **Chỉ tài khoản chỉ định**, xem trước mỗi tài khoản xin mấy nhóm → tài khoản lần lượt bấm "Tham gia nhóm" (chạy ngầm, tiến độ ở thanh dưới cùng). Tối đa 10 nhóm/tài khoản/ngày, cách nhau 45 giây; tài khoản đã vào thì bỏ qua; Facebook báo giới hạn → dừng + cho tài khoản nghỉ.
       - **Nhóm có câu hỏi: tool tự trả lời** theo mục **"Khi xin vào nhóm"** của kịch bản (khung bên phải): ô chữ điền **Câu trả lời mẫu**; câu chọn 1 / chọn nhiều chọn đáp án *đồng ý / có*, không có thì chọn đáp án đầu. Câu hỏi xin **email, số điện thoại, Zalo, link, mật khẩu…** tool **để trống** – nếu vì thế không gửi được thì đánh dấu ❓ để bạn tự trả lời.
       - Nhóm **đang chờ duyệt mà chưa trả lời câu hỏi** (trên trang nhóm còn nút "Trả lời câu hỏi"): bấm Xin vào lại, hoặc để lượt đăng theo lịch tự mở ra trả lời.
       - Hộp **"Tham gia với tư cách"** (tài khoản quản lý Trang): tool chọn trang cá nhân. Hộp **Quy tắc nhóm**: tool bấm Tôi đồng ý.
       - **Vẫy tay chào**: vào nhóm xong, nếu Facebook có nút *Vẫy tay chào / Xin chào* (soạn sẵn) thì tool bấm 1 lần. Tắt được ở mục "Khi xin vào nhóm". Tool không tự viết bài chào.
     - **🚪 Rời nhóm** → cùng hộp chọn tài khoản → tài khoản đang ở nhóm bấm "Đã tham gia → Rời nhóm" (đang chờ duyệt thì hủy yêu cầu). Tài khoản là **quản trị viên** nhóm: tool **không tự rời**. Nhóm vẫn nằm trong danh sách kịch bản.
     - **🗑 Xóa khỏi kịch bản** → chỉ bỏ nhóm khỏi danh sách (thôi đăng), **không rời nhóm trên Facebook**. Muốn bỏ hẳn: Rời nhóm trước rồi mới Xóa.
2. **🔍 Tìm nhóm** – chỉ tìm và **thêm vào kịch bản** (không xin vào ở đây): từ khoá (nhiều từ cách nhau |), thành viên từ–đến, tối thiểu bài/ngày, loại nhóm, số nhóm mỗi từ khoá, **bỏ nhóm có tên chứa…**, sắp xếp **Nhiều bài/ngày** · **Sôi nổi** (bài/ngày so với số thành viên – nhóm vừa phải mà nhiều bài) · **Nhiều thành viên**. Kết quả là bảng (bấm tiêu đề cột để sắp xếp, bấm dòng để tick, "Tick 10 nhóm đầu"); nhóm đã có trong kịch bản hiện ✓ mờ. Bấm **➕ Thêm N nhóm vào kịch bản** → nhóm vào bảng ở bước 1 → tick → 🙋 Xin vào.
3. **Nội dung bài đăng** + ảnh/video của kịch bản. **Tùy chọn**: giờ đăng chung (cùng nội dung đăng nhiều giờ → thêm giờ, không cần tạo thêm kịch bản), thứ, giới hạn nhóm/lượt, chạy ngầm.

- Tab **👥 Tài khoản chạy**: tick tài khoản nào thì tài khoản đó chạy kịch bản (lọc theo nhóm tài khoản, **Tick hết / Bỏ tick**). **Giãn cách giờ đăng giữa 2 tài khoản** (mặc định 15 phút): tài khoản thứ 1 đăng đúng giờ chung, thứ 2 lùi 15 phút, thứ 3 lùi 30 phút… Bỏ tick = thôi chạy, kết quả cũ vẫn giữ.
- Nút **⧉ Nhân bản**: tạo kịch bản giống hệt (chưa tick tài khoản) để sửa thành nội dung khác.

**Tài khoản trong kịch bản** (chọn dòng 👤 dưới kịch bản) – chỉ xem và đăng ngay, không thêm/bớt nhóm ở đây:
- Tab **🚀 Đăng ngay**: bảng nhóm kèm trạng thái của riêng tài khoản này, bấm dòng để tick (mặc định tick các nhóm ĐÃ VÀO) → **🚀 Đăng ngay**.
- Tab **Kết quả tổng hợp**, **Kết quả chi tiết** (có **chăm bài**, xem dưới), 📄 Xem nhật ký. Nút 🗑 Xóa ở đây = bỏ tài khoản khỏi kịch bản.

**Chăm bài (👤 → Kết quả chi tiết):**
1. Bấm **💬 Chăm bài** (cạnh "✅ Chỉ bài đã duyệt") → bảng chỉ còn **bài đã được duyệt**, mỗi dòng có ô ☐.
2. Bấm vào các dòng để chọn → nút đổi thành **💬 Chăm N bài đã chọn** → bấm.
3. Hộp **chỉ có nội dung bình luận** (lưu sẵn cho lần sau) + Copy / 🌐 Mở để tự chăm / **💬 Bình luận vào N bài**.
4. Cột **Chăm bài** tự cập nhật: ⏳ chờ gửi → ⏳ đang gửi → **💬 đã bình luận** → **✅ đã lên** (tool mở lại bài thấy bình luận của bạn) · ❌ lỗi. Bình luận chưa hiện (nhóm duyệt bình luận) → bấm **🔄 Cập nhật ngay** sau, tool xem lại.
- **Mỗi bài chỉ chăm 1 lần** (bài 💬/✅ không chọn lại được – không phải úp tin). Các bài cách nhau 30–70 giây.

**Tab 👤 Tài khoản**: đăng nhập / đổi / đăng xuất, quét mỗi bao nhiêu phút, **Nhóm tài khoản** (＋ Nhóm tài khoản → chọn nhóm cho từng tài khoản), các kịch bản tài khoản đang chạy.


- **Đăng ngay** = chạy liền ngay lúc bấm. Để tool tự chạy theo lịch thì đặt **Giờ đăng** rồi bấm **Lưu**.
- Dữ liệu cũ tự chuyển: mỗi mục cũ thành 1 kịch bản chỉ tick đúng tài khoản cũ (giữ nguyên giờ, kết quả). Bản sao cấu hình cũ: `config.truoc_kich_ban.json`.

Kết quả của từng tài khoản trong kịch bản:
- **Kết quả tổng hợp**: mỗi nhóm 1 dòng – bài / bình luận của bạn được duyệt, chờ duyệt hay bị gỡ, và **bạn nên làm gì**. Nhóm có vấn đề tự xếp lên đầu.
- **Kết quả chi tiết**: nhật ký từng lần đăng / quét + cột Chăm bài. Bấm đúp 1 dòng có 🔗 để mở bài bằng Chrome của tài khoản.
- Kịch bản 🔎 theo dõi: **Setting cơ bản** (nhóm, từ khóa, Telegram, bình luận), **Setting nâng cao** (Rule khi lỗi, lọc bài quảng cáo).

Các nút khác:
- **Bật / tắt** từng kịch bản: tắt là tạm ngừng, không mất dữ liệu.
- **🔄 Cập nhật toàn bộ**: tool vào Facebook xem lại trạng thái duyệt bài / bình luận ở mọi nhóm (chỉ xem, không đăng).
- Bấm **Lưu** (hoặc `Ctrl+S`). Lịch tự cập nhật.

**Ảnh / video đính kèm:** chọn 1 thư mục; mỗi bài tool đính kèm các file đầu tiên theo tên (đặt 01.jpg, 02.jpg… để sắp thứ tự). Đặt **Số tối thiểu** và **Số tối đa** khác nhau → mỗi bài lấy ngẫu nhiên số ảnh trong khoảng đó.

**Giới hạn an toàn (📝 → Đăng vào nhóm nào → "mỗi lượt chỉ đăng tối đa … nhóm"):** để 0 = đăng hết. Đặt số nhỏ (vd 20) để mỗi lượt chỉ đăng một phần nhóm (ưu tiên nhóm lâu chưa đăng), xoay vòng qua các lượt — đăng ít mỗi lượt đỡ bị coi là spam, an toàn cho nick.

⚠️ **Giờ đăng của các nội dung trong cùng một tài khoản Facebook không được trùng hoặc quá sát nhau.** Cửa sổ sẽ báo nếu bị trùng, kèm số phút cần cách nhau. Lượt đăng bài và lượt quét của cùng tài khoản tự **xếp hàng**, không chạy chồng nhau.

**Dùng Page:** **1 nick Facebook = 1 tài khoản trong tool** (1 Chrome, đăng nhập 1 lần bằng **Cá nhân**). **Không** tạo thêm tài khoản riêng cho Page — Facebook sẽ thấy 1 người đăng nhập trên nhiều Chrome và dễ đá cả các phiên.

1. **Đọc danh sách Page:** chọn tài khoản → tab **🎭 Cá nhân & Page** → bấm **🔄 Đọc danh sách Page**. Tool mở Facebook chạy ngầm (chỉ xem), đọc Cá nhân + các Page nick quản lý (tối đa 10 Page; nhiều Page có thể mất vài phút). Đổi tên Page / thêm Page trên Facebook thì bấm đọc lại — kịch bản vẫn giữ đúng Page. Page không còn thấy được giữ lại, ghi "⚠ không thấy".
2. **Đăng bằng:** mở kịch bản (đăng bài hoặc theo dõi) → tab **👥 Tài khoản chạy** → bấm ô **Đăng bằng** của tài khoản → chọn **Cá nhân** hoặc 1 Page → **Lưu**. Mặc định là Cá nhân. Khi chạy, tool tự chuyển sang Page như người thật, làm xong **tự chuyển về Cá nhân**. Không chuyển được → lượt đó **không đăng / bình luận gì** (không đăng nhầm bằng Cá nhân). Kết quả, trạng thái nhóm, chăm bài của Page tách riêng với Cá nhân.
   - Muốn cùng 1 nội dung đăng cả bằng Cá nhân lẫn Page: **⧉ Nhân bản** kịch bản, bản sao chọn Đăng bằng Page.
   - Page chưa vào nhóm: tool bỏ nhóm đó và ghi nhật ký. **🙋 Xin vào / 🚪 Rời nhóm bằng Page chưa hỗ trợ** (nút tắt khi kịch bản chỉ có tài khoản đăng bằng Page) — vào nhóm bằng Page thì làm tay trên Facebook.
   - Nút **Mở** (Chrome của tài khoản) luôn mở ở Cá nhân: muốn xem bằng Page thì bấm ảnh đại diện góc phải → **Chuyển sang <tên Page>**.
3. **Gộp tài khoản cũ:** trước đây mỗi Page là 1 tài khoản riêng → tool hiện cảnh báo **"N tài khoản chung 1 nick"** (Tổng quan và trang tài khoản) + nút **Gộp vào …**. Bấm → chọn **tài khoản chính** (giữ Chrome, nên là tài khoản đăng nhập Cá nhân) → hộp xác nhận liệt kê: tài khoản nào thành Page nào, kịch bản đổi ra sao (kịch bản đang chạy cả tài khoản chính lẫn phụ thì tách thành bản sao "<tên> (<tên Page>)"), có sao lưu `config.truoc_gop_<ngày giờ>.json`, Chrome nào bị đăng xuất + xoá → bấm **Gộp**. Báo "Không thấy Page …" thì bấm **🔄 Đọc danh sách Page của tài khoản chính** trong hộp rồi gộp lại. Kết quả cũ được giữ. Đăng xuất Chrome phụ lỗi → Tổng quan hiện cảnh báo + nút **Thử lại**.

---

## Sử dụng hằng ngày

**Không cần làm gì.** Chỉ cần máy **bật** và đã **đăng nhập Windows**. Nếu máy tắt đúng giờ đăng, bật máy lên tool sẽ đăng bù.

- Tắt màn hình, khóa màn hình: tool **vẫn chạy**.
- Máy **ngủ (Sleep)**: tool tự đánh thức máy để chạy. Chắc nhất là tắt chế độ ngủ: **Settings → System → Power & sleep → Sleep → Never**.
- Máy **tắt hẳn** hoặc **đăng xuất Windows**: tool không chạy.

---

## Tài khoản: đăng nhập, đổi, đăng xuất

| Trạng thái | Ý nghĩa | Các mục của tài khoản |
|---|---|---|
| ✅ **Đang hoạt động** | Đã đăng nhập, chạy bình thường | Chạy theo lịch |
| ⚠️ **Hết hạn / bị Facebook đăng xuất** | Facebook đã đá tài khoản ra | **Tự tạm dừng** → bấm **Đăng nhập lại** |
| ⛔ **Chưa đăng nhập** | Chưa đăng nhập hoặc đã bấm Đăng xuất | **Tạm dừng** → bấm **Đăng nhập** |

- **Đổi tài khoản**: đăng xuất tài khoản cũ rồi mở Chrome để đăng nhập tài khoản mới.
- **Đăng xuất**: đăng xuất Facebook, **xóa dữ liệu đăng nhập đã lưu** và **tạm dừng** các mục của tài khoản.
- Góc trên: **📄 Xem nhật ký** · **⏸ Tạm dừng toàn bộ** / **▶ Chạy lại toàn bộ**.

> 💡 **Tool có vấn đề thì chạy lại `CAI_DAT.bat`** (chạy bao nhiêu lần cũng an toàn).

---

## Lưu ý

- Facebook báo **"bạn đăng quá nhiều"**: tool tự **nghỉ cả tài khoản** (đăng bài, quét, bình luận) theo Rule khi lỗi, rồi tự chạy lại.
- Một vài nhóm báo **"Không thể đăng"**: kiểm tra tài khoản còn trong nhóm và nhóm có cho đăng bài không. Tool tự tạm bỏ nhóm lỗi liên tiếp.
- ❌ Không xóa và không gửi cho người khác thư mục `accounts` (chứa đăng nhập) và file `config.json`.
- ❌ Không di chuyển hoặc đổi tên thư mục tool sau khi cài.
- ❌ Không đặt quá nhiều giờ đăng hay quá nhiều nhóm, vì Facebook có thể coi là spam.

---

## Lấy thông tin Telegram

- **TOKEN:** trên Telegram, nhắn **@BotFather** → gõ `/newbot` → đặt tên → copy mã `1234567890:AAH...`. Sau đó mở bot vừa tạo và bấm **Start**.
- **CHAT_ID:** nhắn **@userinfobot** → copy dãy số sau chữ `Id:`.
