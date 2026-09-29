# Footage Agent: cách tìm ảnh cho kịch bản người nổi tiếng

## Pipeline

```
script.txt
  │ 1 segment   tách câu (pysbd, hỗ trợ 6 ngôn ngữ), gộp câu ngắn thành cảnh, bỏ chỉ dẫn [..]
  │ 2 subject   Claude xác định nhân vật chính → Wikidata: QID, tên ở 6 ngôn ngữ, bí danh,
  │             năm sinh/mất, category Commons, danh sách tác phẩm kèm năm (SPARQL)
  │ 3 briefs    Claude viết "visual brief" cho từng cảnh: loại cảnh, thực thể, khoảng năm,
  │             sự kiện neo, địa điểm, truy vấn cụ thể → rộng, câu mô tả cho CLIP
  │ 4 search    Wikimedia Commons (category theo năm + tìm kiếm), Openverse, Pexels (cảnh
  │             chung), Brave Images (web, tùy chọn) → chấm điểm → xếp hạng
  │ 5 narrate   ElevenLabs with-timestamps → thời điểm bắt đầu/kết thúc từng cảnh
  │             (--no-tts: ước lượng theo tốc độ đọc của ngôn ngữ, để xem trước)
  │ 6 select    số ảnh mỗi cảnh = thời lượng / max-shot; tải ảnh, loại trùng bằng
  │             perceptual hash; ưu tiên file trong manual/; xuất review.html + credits.txt
  │ 7 timeline  props cho Remotion (video/src/schema.ts), chép ảnh + audio vào video/public
  │ 8 render    npx remotion render
  ▼
out/<slug>-<lang>.mp4
```

## Vì sao "entity first" chứ không "face first"

CLIP rất giỏi trả lời "ảnh này có giống *một nữ diễn viên thập niên 90 ở buổi công chiếu* không", nhưng không phân biệt được Winona Ryder với Jennifer Connelly, nhất là ảnh trắng đen, ảnh scan tạp chí, góc nghiêng. Vì vậy:

- **Danh tính được chứng minh bằng metadata.** Với cảnh có người (`person_portrait`, `person_event`, `person_with_other`), ảnh bị loại nếu tên hoặc bí danh Wikidata không xuất hiện trong tiêu đề, mô tả, category hoặc URL trang.
- **CLIP chỉ xếp hạng lại** các ứng viên đã qua bộ lọc danh tính, theo độ khớp với cảnh.

## Công thức điểm (`pipeline/src/docugen/scoring.py`)

| Thành phần | Cảnh có thực thể | Cảnh chung (generic) |
|---|---|---|
| entity: tên / bí danh có trong metadata | 40% | 0% |
| source: độ tin cậy của chú thích nguồn | 25% | 25% |
| context: năm trong khoảng + từ khóa sự kiện/địa điểm | 20% | 15% |
| clip: độ khớp hình ảnh (0.5 khi tắt CLIP) | 10% | 40% |
| quality: độ phân giải, tỉ lệ ngang | 5% | 20% |

Loại cứng: domain agency có watermark (Getty, Alamy, Shutterstock...), domain trong blacklist, cạnh ngắn dưới 400px, ảnh stock cho người có tên. Pipeline không lọc theo bản quyền.

## Mẹo quan trọng nhất: category theo năm trên Commons

Người nổi tiếng thường có category kiểu `Category:Winona Ryder in 1994`, `Category:Charlie Chaplin in 1915`. Ảnh trong đó đã được người thật phân loại đúng người, đúng năm. Pipeline luôn thử các category này trước khi tìm kiếm bằng từ khóa.

## Nguồn

| Nguồn | Dùng cho |
|---|---|
| Wikimedia Commons | người, sự kiện, địa điểm, poster cũ |
| Openverse (Flickr, bảo tàng...) | như trên |
| Pexels (cần API key) | cảnh chung |
| Brave Image Search (cần `BRAVE_API_KEY`) | web: scan tạp chí, fan archive, trang Pinterest |

- Không có bước kiểm tra bản quyền: mọi ảnh qua bộ lọc danh tính và chất lượng đều được dùng, kể cả ảnh web không rõ license. Loại license chỉ hiển thị trong `review.html` để tham khảo.
- Ảnh CC BY / BY-SA vẫn được ghi tên tác giả trên hình (tắt bằng `showCredits: false` trong timeline) và trong `credits.txt`.
- Pinterest chỉ xuất hiện gián tiếp qua API tìm kiếm Brave; pipeline không scrape Pinterest hay Google Images (điều khoản của họ cấm thu thập tự động).

## Duyệt và sửa tay

1. Mở `projects/<slug>/review.html`: mỗi cảnh hiện ảnh đã chọn (viền vàng), các lựa chọn thay thế, điểm từng thành phần và license (tham khảo).
2. Muốn thay ảnh cảnh 7: lưu file thành `projects/<slug>/manual/scene_007.jpg` (nhiều ảnh: `scene_007_a.jpg`, `scene_007_b.jpg`).
3. Chạy lại `docugen run <slug> --force select`.

## Lộ trình nâng cấp

- **Xác minh khuôn mặt tùy chọn:** lấy ảnh chân dung tham chiếu từ Wikidata (P18), so embedding khuôn mặt (InsightFace/ArcFace) để loại ảnh chú thích sai. Dùng làm bộ lọc phụ, không thay thế metadata.
- **Điểm lấy nét (focusX/focusY):** phát hiện khuôn mặt để Ken Burns zoom vào mặt thay vì giữa ảnh (schema đã có sẵn trường).
- **Video B-roll:** Pexels Videos / Storyblocks / Internet Archive (newsreel public domain) cho cảnh chung.
- **Hiệu ứng:** parallax 2.5D, tiêu đề chương, bản đồ, dòng thời gian (bộ skill Remotion có sẵn hướng dẫn).
- **Web editor:** giao diện thay ảnh kiểu "Replace media" dựa trên `footage.json` (đã lưu sẵn 30 ứng viên mỗi cảnh).
