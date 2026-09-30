# Footage Agent: cách tìm ảnh cho kịch bản người nổi tiếng

## Pipeline

```
input.srt + audio (hoặc script.txt)
  │ 1 segment   SRT: gộp cue thành cảnh, cắt ở cuối câu, tối đa 12 giây mỗi cảnh
  │             (script.txt: tách câu bằng pysbd, bỏ chỉ dẫn [..])
  │ 2 subject   Claude xác định nhân vật chính và tối đa 8 người khác: bí danh,
  │             năm sinh/mất, tác phẩm kèm năm (từ kiến thức của Claude)
  │ 3 briefs    Claude (Scene Analyzer) cho từng cảnh: loại cảnh, thực thể, khoảng năm,
  │             sự kiện neo, 3 đến 5 truy vấn Google Images, truy vấn dự phòng, câu mô tả CLIP
  │ 4 search    Google Images qua SerpApi (cache trên đĩa) → chấm điểm → xếp hạng
  │ 5 narrate   SRT: thời gian lấy từ cue, audio là file của bạn
  │             (script.txt: ElevenLabs with-timestamps)
  │ 6 select    số ảnh mỗi cảnh = thời lượng / max-shot; tải ảnh, loại trùng bằng
  │             perceptual hash; ưu tiên manual/; xuất review.html + credits.txt
  │ 7 timeline  props cho Remotion, phụ đề đúng thời gian cue
  │ 8 render    npx remotion render
  ▼
out/<slug>-<lang>.mp4
```

## So sánh công cụ tìm ảnh Google

| | SerpApi (đang dùng) | DataForSEO | Gemini Grounding with Google Search |
|---|---|---|---|
| Trả về gì | ~100 ảnh mỗi lượt: link ảnh gốc, kích thước, tiêu đề, trang nguồn | Top 100 ảnh: link ảnh, trang nguồn, tiêu đề/alt | Câu trả lời văn bản + danh sách link trang web (groundingMetadata). **Không trả ảnh** |
| Giá | Miễn phí 250 lượt/tháng; $25/1.000, $75/5.000, $150/15.000, $275/30.000 lượt mỗi tháng | Trả theo dùng: $0.002/lượt (live), rẻ hơn khi chạy hàng đợi; nạp tối thiểu $50 | Gemini 3: $14/1.000 truy vấn sau 5.000 lượt miễn phí mỗi tháng |
| Tích hợp | Đơn giản nhất, 1 lệnh GET | Nhiều endpoint hơn (live hoặc task_post/task_get) | Không dùng được làm công cụ tìm ảnh |
| Khi nào dùng | Bắt đầu, sản lượng vừa | Khi làm nhiều video, cần giảm chi phí | Tra cứu dữ kiện, không phải tìm ảnh |

DataForSEO có thể thêm sau như một provider mới trong `pipeline/src/docugen/providers/`, cùng interface `search(query) -> list[Candidate]`.

### Ước tính chi phí SerpApi
Số lượt ≈ số cảnh × `DOCUGEN_MAX_QUERIES` (mặc định 4), cộng truy vấn dự phòng cho cảnh chưa đủ 8 ảnh đúng tên. Video 10 phút có khoảng 80 đến 100 cảnh, tức khoảng 350 đến 450 lượt. Chạy lại bước `search` không tốn thêm lượt nhờ cache ở `projects/<slug>/cache/serpapi/`.

## Vì sao "entity first" chứ không "face first"

CLIP rất giỏi trả lời "ảnh này có giống *một nữ diễn viên thập niên 90 ở buổi công chiếu* không", nhưng không phân biệt được Winona Ryder với Jennifer Connelly. Vì vậy:

- **Danh tính được chấm bằng tiêu đề ảnh và trang nguồn.** Với cảnh có người, ảnh có tên hoặc bí danh trong tiêu đề, nguồn hoặc URL trang được cộng 40% điểm, nên luôn xếp trên ảnh không có tên. Ảnh không tên vẫn được giữ làm dự phòng.
- **CLIP chỉ xếp hạng lại** theo độ khớp với cảnh.

## Công thức điểm (`pipeline/src/docugen/scoring.py`)

| Thành phần | Cảnh có thực thể | Cảnh chung (generic) |
|---|---|---|
| entity: tên / bí danh có trong tiêu đề, nguồn, URL | 40% | 0% |
| source: độ tin cậy của trang nguồn (Wikipedia 0.8, IMDb 0.6, Pinterest 0.35...) | 25% | 25% |
| context: năm trong khoảng + từ khóa sự kiện/địa điểm | 20% | 15% |
| clip: độ khớp hình ảnh (0.5 khi tắt CLIP) | 10% | 40% |
| quality: độ phân giải, tỉ lệ ngang | 5% | 20% |

Không có bộ lọc cứng nào ngoài các domain bạn tự chặn trong `DOCUGEN_BLOCKED_DOMAINS`. Không lọc theo bản quyền; loại license chỉ hiển thị trong `review.html`.

## Tải ảnh

Link ảnh gốc từ Google Images trỏ thẳng về website chứa ảnh, nên có trang chặn tải hoặc trả về HTML. Pipeline gửi kèm `Referer` là trang nguồn, bỏ qua phản hồi không phải ảnh, và tự chuyển sang ứng viên kế tiếp khi lỗi. Thumbnail của Google (~200px) không được dùng vì quá nhỏ cho video 1080p.

## Duyệt và sửa tay

1. Mở `projects/<slug>/review.html`: mỗi cảnh hiện ảnh đã chọn (viền vàng), các lựa chọn thay thế và điểm từng thành phần.
2. Muốn thay ảnh cảnh 7: lưu file thành `projects/<slug>/manual/scene_007.jpg` (nhiều ảnh: `scene_007_a.jpg`, `scene_007_b.jpg`).
3. Chạy lại `docugen run <slug> --force select`.

## Nguồn tùy chọn (đang tắt)

Code của Wikimedia Commons (có category theo năm), Openverse, Pexels và Brave vẫn còn. Bật lại bằng `DOCUGEN_PROVIDERS=google,wikimedia,openverse,pexels,web`.

## Lộ trình nâng cấp

- **Provider DataForSEO** khi sản lượng tăng.
- **Xác minh khuôn mặt tùy chọn:** so embedding khuôn mặt (InsightFace/ArcFace) với một ảnh chân dung tham chiếu để loại ảnh chú thích sai.
- **Điểm lấy nét (focusX/focusY):** phát hiện khuôn mặt để Ken Burns zoom vào mặt (schema đã có sẵn trường).
- **Hiệu ứng:** parallax 2.5D, tiêu đề chương, bản đồ, dòng thời gian.
- **Web editor** thay ảnh dựa trên `footage.json` (đã lưu 30 ứng viên mỗi cảnh).
