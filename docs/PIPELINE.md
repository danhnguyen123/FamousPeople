# Pipeline

```
input.srt ─┐
           ├─► 1. plan      Claude đọc toàn bộ SRT ──────────────► plan.json
audio ─────┘                 cảnh (1 đến 2 cue), nhóm, keyword
               2. search    keyword đầu của mỗi nhóm × 3 nguồn ─► search.json
                             DataForSEO (Google), SearchAPI (Bing), Brave
               3. select    Claude duyệt kết quả từng nhóm ─────► select.json, (search.json)
                             nhóm thiếu ảnh: tìm keyword kế tiếp
               4. download  ảnh cho từng cảnh ──────────────────► images.json, assets/,
                                                                    plan.csv, candidates.csv
               5. timeline  props cho Remotion ─────────────────► timeline.json
               6. render    npx remotion render ────────────────► out/<slug>-<lang>.mp4
```

## 1. plan

Claude (`DOCUGEN_MODEL`, mặc định `claude-opus-5-5`, effort `high`) nhận toàn bộ SRT, mỗi cue một dòng có số thứ tự, thời gian và độ dài. Prompt nằm ở `pipeline/src/docugen/prompts/keyword_planner.md` và được gửi làm system prompt có cache. Kết quả là structured output:

```json
{
  "main_subject": "Marlene Dietrich",
  "title": "Marlene Dietrich: Der blaue Engel",
  "groups": [
    {"group": 1, "subject": "Marlene Dietrich", "context": "young, 1920s Berlin",
     "keywords": ["Marlene Dietrich jung Berlin 1920er", "Marlene Dietrich young 1920s"]},
    {"group": 2, "subject": "Der blaue Engel", "context": "1930 film",
     "keywords": ["Der blaue Engel 1930 Film", "The Blue Angel 1930 film still"]}
  ],
  "scenes": [{"cues": [1, 2], "group": 1}, {"cues": [3], "group": 2}]
}
```

- Cảnh gồm 1 hoặc 2 cue liền nhau cùng chủ thể, không quá khoảng 7 giây. Mỗi cảnh là một ảnh.
- Nhóm gom các cảnh cùng chủ thể và cùng bối cảnh. Mỗi nhóm chỉ tìm ảnh một lần.
- Keyword gồm 2 đến 3 truy vấn. Truy vấn đầu viết bằng ngôn ngữ kịch bản, có ít nhất một truy vấn tiếng Anh, tên riêng giữ nguyên.

Code kiểm tra lại: mọi cue phải thuộc đúng một cảnh theo thứ tự. Cảnh quá 2 cue thì bị tách. Cue bị bỏ sót thành một cảnh riêng, dùng nhóm của cảnh trước. Nhóm không tồn tại thì dùng nhóm của cảnh trước. Mọi chỉnh sửa đều được ghi cảnh báo.

## 2. search

Keyword đầu của mỗi nhóm được tìm trên mọi nguồn trong `DOCUGEN_SEARCH`. Ảnh thumbnail YouTube (youtube.com, ytimg.com) và ảnh bìa video TikTok (tiktok.com, tiktokcdn.com) luôn bị bỏ khi gộp kết quả:

| Nguồn | API | Tham số |
|---|---|---|
| `dataforseo` | Google Images, `POST /v3/serp/google/images/task_post` rồi `GET task_get/advanced/{id}` | `language_code` và `location_code` theo `--lang` (en 2840, fr 2250, de 2276, it 2380, pl 2616, nl 2528, ja 2392), `depth=100`. Tất cả task gửi một lần, chờ khoảng 1 đến 5 phút. Đặt `DOCUGEN_DATAFORSEO_LIVE=1` để lấy kết quả ngay qua `live/advanced` |
| `google` | SearchAPI.io, `engine=google_images` | `gl` và `hl` theo ngôn ngữ (jp/ja, de/de...), 100 kết quả mỗi lượt, $0,004 mỗi lượt. Không nằm trong mặc định, bật bằng `DOCUGEN_SEARCH`, ví dụ `google,bing,brave` khi chưa dùng được DataForSEO |
| `bing` | SearchAPI.io, `engine=bing_images` | `market_code` theo ngôn ngữ (de-DE, fr-FR...), trang 1 |
| `brave` | `GET https://api.search.brave.com/res/v1/images/search` | `count=200` (tối đa, không phân trang), `search_lang` theo ngôn ngữ, `safesearch=strict`. Gọi tuần tự, cách nhau `DOCUGEN_BRAVE_INTERVAL` giây (mặc định 1,1, vì gói miễn phí chỉ cho 1 lượt mỗi giây) |

- **Gộp kết quả:** lấy tối đa `DOCUGEN_CANDIDATES_PER_SOURCE` (40) kết quả mỗi nguồn, xếp xen kẽ (Google 1, Bing 1, Brave 1, Google 2...), bỏ URL trùng và bỏ các site trong `DOCUGEN_BLOCKED_DOMAINS`.
- **Cache:** mỗi phản hồi thô được cache ở `cache/<nguồn>/`. Task DataForSEO đang chờ được lưu vào file `.task`, nên chạy lại sau khi bị ngắt sẽ không gửi task lần nữa.

## 3. select

Mỗi nhóm gọi Claude một lần (`DOCUGEN_SELECT_MODEL`, effort `medium`, 6 nhóm chạy song song). Prompt nằm ở `prompts/image_selector.md`.

- **Claude nhận:** chủ thể, bối cảnh và các keyword tìm kiếm của nhóm, và danh sách ứng viên. Mỗi ứng viên chỉ gồm: id, tiêu đề, tên site.
- **Claude kiểm tra:** tiêu đề hoặc tên site có liên quan đến keyword tìm kiếm không. Có thì nhận và xếp hạng, không thì loại. Các ảnh được nhận là kho ảnh của nhóm.
- **Claude trả về:**
  - `accepted` (tốt nhất trước), mỗi ảnh mức `subject_and_context` hoặc `subject_only`
  - `rejected` kèm lý do
- **Nhóm thiếu ảnh:** nếu nhóm có ít hơn `DOCUGEN_MIN_POOL` (3) ảnh được chấp nhận, code tìm keyword kế tiếp trên cả 3 nguồn và chỉ gửi kết quả mới cho Claude. Lặp lại cho đến khi hết keyword.
- **Batch:** `DOCUGEN_SELECT_BATCH=1` dùng Batches API, rẻ bằng một nửa nhưng phải chờ vài phút. Batch không có server-side fallback.

Claude chỉ đọc chữ, không xem ảnh và không nhận diện khuôn mặt. Danh tính dựa vào tên trong tiêu đề hoặc tên site.

## 4. download

Các cảnh được xử lý theo thứ tự.

1. **Ảnh thủ công:** nếu có `manual/scene_007.jpg` (hoặc .png, .webp) thì cảnh 7 dùng ảnh đó. Cảnh này vẫn tính một lượt trong kho ảnh của nhóm, nên thay ảnh một cảnh không làm đổi ảnh của các cảnh khác.
2. **Xoay vòng kho ảnh:** các cảnh của một nhóm lần lượt lấy ảnh trong kho của nhóm theo thứ tự Claude xếp hạng, hết kho thì quay lại ảnh đầu. Không lấy cùng một ảnh cho hai cảnh liền nhau khi kho còn ảnh khác.
3. **Tải ảnh:** ảnh được tải với `Referer` là trang nguồn. Chỉ bỏ ảnh tải lỗi hoặc `content-type` không phải ảnh. Ảnh nhỏ và ảnh trùng vẫn được giữ. Ảnh lỗi rời khỏi kho và cảnh chuyển sang ảnh kế.
4. **Nhóm không có ảnh nào:** lấy ảnh của nhóm nhân vật chính. Nếu vẫn không có thì giữ ảnh của cảnh trước.

Bước này còn ghi 2 file để duyệt:
- `plan.csv` (UTF-8 BOM, mở được bằng Excel): mỗi cảnh một dòng gồm cue, lời thoại, nhóm, chủ thể, keyword, file ảnh, nguồn, có dùng lại không, ghi chú của Claude, trang nguồn.
- `candidates.csv`: toàn bộ kết quả tìm kiếm kèm quyết định của Claude.

### Trang duyệt ảnh: `docugen review <slug>`

Mở trang web local (mặc định http://127.0.0.1:8765/, đổi bằng `--port`) đọc `plan.csv`. Mỗi cảnh một dòng gồm: số cảnh, cue và thời điểm, lời thoại, 3 keyword của nhóm, ảnh preview cuối cùng, và ô dán link ảnh thủ công. Có ô tìm kiếm và bộ lọc (đã thay thủ công, thiếu ảnh, ảnh dùng lại).

- **Dán link rồi bấm Lưu (hoặc Enter):** server tải ảnh về `manual/scene_NNN.jpg`, ghi link vào `manual/links.json`, cập nhật ngay `images.json` và `plan.csv`, rồi hiện ảnh bên cạnh ô nhập. Link phải trỏ trực tiếp tới file ảnh.
- **Xóa:** bỏ ảnh thủ công, cảnh lấy lại ảnh của kho.
- Mỗi lần đổi ảnh, `timeline.json` bị xóa vì không còn khớp. Chạy lại `docugen run <slug>` để dựng lại timeline và render với ảnh mới.

## 5. timeline và 6. render

- **Thời lượng ảnh:** ảnh của mỗi cảnh chạy từ đầu cue đầu tiên đến đầu cảnh kế tiếp. Ảnh đầu bắt đầu từ 0 giây, ảnh cuối chạy tới 0,5 giây sau cue cuối.
- **Phụ đề:** theo đúng từng cue.
- **Schema:** `video/src/schema.ts` và `pipeline/src/docugen/timeline.py` mô tả cùng một JSON.

## Key API trong môi trường cloud của Claude Code

Biến môi trường của môi trường cloud hiển thị với mọi người dùng môi trường đó, nên không dùng cho key bí mật. Với 3 nguồn tìm ảnh, thêm key vào mục **API credentials**. Proxy của Anthropic sẽ gắn key vào request khi request rời khỏi máy ảo, và code không cần biến môi trường nào.

| Tên | Allowed websites | Header | Prefix | Value |
|---|---|---|---|---|
| DataForSEO | `api.dataforseo.com` | `Authorization` | `Basic` | base64 của `login:api_password` |
| SearchAPI | `www.searchapi.io` | `Authorization` | `Bearer` | API key |
| Brave | `api.search.brave.com` | `X-Subscription-Token` | (để trống) | API key |

`api.anthropic.com` không bao giờ nhận API credentials, và biến `ANTHROPIC_API_KEY` được dành cho chính Claude Code. Để chạy bước plan và select trong phiên cloud, đặt key Claude vào `DOCUGEN_ANTHROPIC_API_KEY` (lưu ý key này sẽ hiển thị với người dùng môi trường), hoặc chạy hai bước đó trên máy của bạn.

## Chi phí cho video 10 phút

Giả định khoảng 150 cue, 50 nhóm.

| Bước | Cách tính | Chi phí |
|---|---|---|
| plan (Opus 5.5, $4 vào / $20 ra mỗi 1M token) | khoảng 10K token vào, 10 đến 20K ra | khoảng $0,3 đến $0,5 |
| search DataForSEO Standard | 50 × $0,0006 | khoảng $0,03 |
| search SearchAPI Bing | 50 × $0,004 (gói $40/tháng, 10.000 lượt) | khoảng $0,20 |
| search Brave | 50 × $0,005 ($5 miễn phí mỗi tháng) | khoảng $0,25 |
| select (Opus 5.5) | khoảng 200K token vào, 25K ra | khoảng $1,3 (Batch: khoảng $0,65) |
| **Tổng** | | **khoảng $2 đến $2,3** |

Keyword dự phòng chỉ tốn thêm khi một nhóm thiếu ảnh. Chạy lại một bước không tốn lượt search nhờ cache.

## So sánh nhà cung cấp tìm ảnh

| Nhà cung cấp | Nguồn | Giá mỗi lượt (khoảng 100 ảnh) | Ghi chú |
|---|---|---|---|
| **DataForSEO** (đang dùng) | Google Images | $0,0006 queue, $0,002 live | Rẻ nhất. Bất đồng bộ. Không có kích thước ảnh. Toán tử `site:` làm giá nhân 5. Có cả Google Lens (`search_by_image`, chỉ chạy queue) |
| **SearchAPI.io** (đang dùng) | Bing Images | $0,004 (gói $40/tháng) | JSON có kích thước ảnh, có bộ lọc `size`, `min_size` |
| **Brave** (đang dùng) | Chỉ mục riêng | $0,005, tặng $5/tháng | 200 kết quả một lượt, không phân trang. Gói thường không cho quyền lưu kết quả lâu dài |
| Serper | Google Images | khoảng $0,002 (2 credit) | Trả kết quả ngay, tặng 2.500 credit |
| SerpApi | Google Images | $0,015 đến $0,025 | Đắt nhất, lượt đọc cache không tính phí |
| Bright Data | Bing, Google | khoảng $0,0015 | Trả theo lượt dùng, cấu hình kiểu proxy |
| Gemini (grounding) | Google Search | | Không trả danh sách ảnh, không hợp để tìm ảnh |

Không tự viết scraper cho Google, Bing, Pinterest hay YouTube.
