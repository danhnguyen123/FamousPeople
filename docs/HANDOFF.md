# Bàn giao: project mifune-v2 (cập nhật 15/10/2026)

File này ghi lại trạng thái công việc để làm tiếp ở phiên khác (Claude Code desktop hoặc cloud). Đọc `CLAUDE.md` và `docs/PIPELINE.md` trước.

## Đang làm gì

Video tài liệu tiếng Nhật về 三船敏郎 và vợ 吉峰幸子 (641 cue, 554 cảnh, 69 nhóm). Pipeline đã chạy tới bước **download**: mọi cảnh đều có ảnh. Chưa có audio, **chưa render** (chỉ render khi người dùng đồng ý).

Đang ở bước **duyệt ảnh**: 100 ảnh (153 cảnh) bị đánh dấu là ảnh xấu. Người dùng dán link ảnh thay thế trên trang audit, rồi Claude áp dụng vào project.

## Khôi phục project trên máy

```bash
cd pipeline && pip install -e . && cd ..
mkdir -p projects/mifune-v2 && cp -r examples/mifune-v2/. projects/mifune-v2/
rm projects/mifune-v2/images.json   # để bước download chạy lại và tải ảnh về
DOCUGEN_SEARCH='{"google": "serper", "brave": "brave"}' docugen run mifune-v2 --until download
```

- `examples/mifune-v2/` có đủ kết quả: `plan.json`, `search.json`, `select.json`, `images.json`, `plan.csv`, `candidates.csv`, `audit.json`, `translations.json` và `cache/select/` (câu trả lời của gpt-5.5 và gpt-6.1-sol). Bước plan, search và select được bỏ qua vì file đã có, không tốn API.
- Ảnh (`assets/`, 39 MB) và cache tìm kiếm thô không được commit. Lệnh trên chạy lại bước download: tải lại ảnh từ URL đã lưu, không tốn lượt API. Phải xóa `images.json` như trên, vì stage nào có output rồi sẽ bị bỏ qua. Vài ảnh có thể đã bị gỡ khỏi trang gốc; khi đó cảnh chuyển sang ảnh kế tiếp trong kho của nhóm.

## Lượt chạy hiện tại

- Search: Serper (Google) và Brave, keyword đầu của 69 nhóm. 18 nhóm có thêm keyword thứ 2, do lỗi đã sửa ở lượt gpt-5.5 bị hỏng (xem bên dưới). Không nhóm nào tìm keyword thứ 3.
- Select: OpenAI Batch, `gpt-6.1-sol`, effort medium. 271K token vào, 30K ra, khoảng $0,42.
- Kết quả: nhận 3.924 và loại 2.301 ảnh (nhận 63%). 344 ảnh khác nhau; 210 cảnh dùng lại ảnh, gần như toàn bộ là giữa các nhóm cùng nhân vật. 0 cảnh thiếu ảnh. Nhóm lớn nhất 15 cảnh, kho nhỏ nhất 22 ảnh.
- Lượt cũ để so sánh: plan 60 nhóm, nhóm lớn nhất 100 cảnh với 26 ảnh, 194 cảnh dùng lại, 362 ảnh khác nhau, Claude duyệt hết $0,73.

## Nhà cung cấp và credit

| Dịch vụ | Trạng thái |
|---|---|
| Claude (`DOCUGEN_ANTHROPIC_API_KEY`) | Hết credit (lỗi 400 credit balance too low) |
| OpenAI (`OPENAI_API_KEY`) | Đã nạp lại, đang dùng cho bước select |
| Serper | Chạy tốt, 100 ảnh mỗi lượt, 2 credit, không cần phân trang |
| Brave | Chạy tốt, 1 request mỗi giây. 2 truy vấn trả 0 ảnh do `safesearch=strict` |
| SearchAPI.io | Hết lượt tháng (429) |
| DataForSEO | Chưa xác minh tài khoản (40104) |
| Gemini | Chạy tốt, dùng cho bản dịch tiếng Việt |

Lệnh chạy select bằng OpenAI: `DOCUGEN_SELECT_PROVIDER=openai DOCUGEN_SELECT_BATCH=1 docugen run <slug> --until download`.

## Trang audit (claude.ai Artifact)

- Link: https://claude.ai/artifact/Jfh1o2YsdmRYg2zEefb3Jw (riêng tư, chỉ chủ sở hữu mở được).
- Tab 1 "Audit ảnh": mỗi ảnh xấu một thẻ, liệt kê các cảnh dùng ảnh đó, lọc theo loại lỗi, có ô dán link. Link dán ở thẻ được lưu cho mọi cảnh dùng ảnh đó.
- Tab 2 "Timeline từng cảnh": bảng giống `docugen review`, gồm lời thoại, bản dịch tiếng Việt, keyword (✓ là keyword tìm ra ảnh, viền đứt là chưa tìm), ảnh, ô dán link từng cảnh.
- Link được lưu vào kho dữ liệu của trang: collection `manual`, mỗi cảnh một document `{scene, url, at}`.
- Dựng lại trang: `python tools/audit/build_page.py projects/mifune-v2 <file>.html`, rồi publish lại cùng URL với Artifact tool (capabilities `{"db": {}}`, giữ nguyên khi publish lại).

### Áp dụng link người dùng đã dán

1. ArtifactData: `action "list"`, `collection "manual"`, `url` là link trang, `out_dir` là một thư mục tạm.
2. `python tools/audit/apply_links.py mifune-v2 <thư mục tạm>/manual`: tải ảnh vào `manual/scene_NNN.jpg`, ghi `manual/links.json`, cập nhật `images.json` và `plan.csv` (cùng code với `docugen review`).
3. Dựng lại và publish lại trang. Cảnh sẽ hiện "Đã áp dụng vào video".

Lưu ý: `set_manual` và `clear_manual` chạy lại toàn bộ bước phân ảnh. Ảnh từng tải lỗi có thể tải được ở lần này, làm đổi ảnh của vài cảnh khác. Đừng chạy hai hàm này khi HTTP đang bị giả lập.

## Audit ảnh

- `audit.json`: `{"scenes": {"186": {"issue": "placeholder", "note": "..."}}}`. Loại lỗi gồm `placeholder`, `screenshot`, `text`, `poster`, `watermark`, `unrelated`. Trang `docugen review` hiện badge và bộ lọc từ file này.
- Cách làm: `python tools/audit/contact_sheets.py projects/mifune-v2 projects/mifune-v2/sheets` ghép 10 tờ, mỗi tờ 56 ảnh. Claude mở từng tờ bằng Read tool để xem, đối chiếu lời thoại và trang nguồn trong `plan.csv`. Không nhận diện khuôn mặt.
- 149 cảnh được đánh dấu tay. Gộp theo ảnh thì còn 100 ảnh, phủ 153 cảnh, vì có 4 cảnh dùng chung ảnh bị sót.

## Phát hiện quan trọng

1. **Model ChatGPT không phải nguyên nhân chính.** Trên cùng 51 nhóm và 3.765 ứng viên: gpt-5.5 nhận 61%, gpt-6.1-sol nhận 65%. Trong 106 ảnh xấu, gpt-5.5 cũng nhận 95. Bước select chỉ đọc tiêu đề và tên trang, nên ảnh stock hay ảnh chụp màn hình trên một trang viết về 三船 vẫn qua. Chưa so với Claude vì hết credit; batch Claude trên 51 nhóm này tốn khoảng $0,5.
2. **gpt-5.5 tốn kém vì suy luận ẩn:** khoảng 3.300 token suy luận mỗi nhóm, tổng khoảng $3 cho 51 nhóm. gpt-6.1-sol chỉ cần khoảng 300 token.
3. **Prompt cache của OpenAI không kích hoạt** (`cached_tokens: 0`): phần chung, tức system prompt, chỉ khoảng 500 token, dưới ngưỡng 1.024.
4. **Thử cho model xem ảnh:** 1 tờ contact sheet 56 ảnh gửi gpt-6.1-sol ở chế độ `high` tốn 3.024 token vào và 169 ra, khoảng $0,008. Model bắt được 16 trên 18 ảnh xấu đã đánh dấu tay ở tờ 1; 2 ảnh sót cần biết danh tính người trong ảnh. Chế độ `low` kém hơn. Cả video khoảng $0,04 nếu chạy Batch.

## Việc tiếp theo (chờ người dùng chọn)

1. **Bước kiểm tra ảnh bằng hình** (đề xuất chính): sau download, ghép contact sheet, gửi batch cho model xem ảnh ở `detail: high`. Ảnh bị đánh dấu `screenshot`, `text`, `placeholder` hoặc stock thì cảnh tự lấy ảnh kế tiếp trong kho; poster chỉ đánh dấu, không tự loại. Ghi kết quả vào `audit.json`. Prompt đặt trong `pipeline/src/docugen/prompts/`.
2. **Giảm dùng lại ảnh giữa các nhóm:** khi xoay vòng kho, ưu tiên ảnh chưa xuất hiện ở cảnh nào (`assign_images` trong `download.py`).
3. **Siết prompt `image_selector.md`** nếu vẫn chỉ duyệt bằng chữ.
4. So sánh với Claude khi có credit.
5. Áp dụng link người dùng dán trên trang audit, rồi render khi người dùng đồng ý. Remotion trong cloud cần `--browser-executable=/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell`.

## Các commit của phiên này (nhánh `claude/celebrity-video-generator-impf6s`)

- Bước select chạy được bằng OpenAI (`openai_llm.py`, `DOCUGEN_SELECT_PROVIDER`), có Batch API, model mặc định `gpt-6.1-sol`.
- Câu trả lời của select được cache ở `cache/select/`. Nhóm bị lỗi API không còn bị coi là đã duyệt hết; chạy lại chỉ gửi các nhóm còn thiếu.
- Trang review đọc `audit.json`, có badge và bộ lọc.
- `plan.csv` thêm cột `Searched` và `Query`; trang review đánh dấu keyword theo hai cột này.
- Thêm `tools/audit/` và file này.
