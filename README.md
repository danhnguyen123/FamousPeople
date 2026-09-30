# FamousPeople: tạo video documentary từ SRT

Công cụ kiểu VidRush: đưa vào file phụ đề SRT kèm audio lời đọc, nhận ra video MP4 gồm ảnh tư liệu chạy hiệu ứng keyframe (Ken Burns), lời đọc và phụ đề. Chủ đề đầu tiên: documentary về người nổi tiếng, hỗ trợ **tiếng Anh, Pháp, Đức, Ý, Ba Lan, Hà Lan**.

```
SRT + audio ──► Claude Scene Analyzer ──► Google Images (SerpApi) ──► timeline.json ──► Remotion ──► MP4
                3 đến 5 truy vấn/cảnh      chấm điểm, tải, chống trùng
```

| Thư mục | Nội dung |
|---|---|
| `pipeline/` | Gói Python `docugen`: đọc SRT, Scene Analyzer, tìm ảnh, xuất timeline |
| `video/` | Dự án Remotion 4 dựng video từ timeline |
| `.claude/skills/` | Bộ skill Remotion chính thức (`remotion-dev/skills`) cho Claude Code |
| `docs/FOOTAGE_AGENT.md` | Kiến trúc, so sánh SerpApi / DataForSEO / Gemini, chi phí, chấm điểm |
| `docs/SCRIPT_GUIDE.md` | Cách viết lời thoại để tìm đúng ảnh |
| `projects/<slug>/` | Kết quả từng dự án (không commit) |

## Cài đặt

```bash
cp .env.example .env            # điền ANTHROPIC_API_KEY, SERPAPI_API_KEY
cd pipeline && pip install -e ".[dev]"     # thêm ".[clip]" nếu muốn xếp hạng bằng CLIP
cd ../video && npm i
```

## Chạy

```bash
docugen new --srt voice.srt --audio voice.mp3 --lang de --slug marlene
docugen run marlene --until select      # dừng lại để duyệt ảnh
# mở projects/marlene/review.html, thay ảnh sai bằng manual/scene_007.jpg
docugen run marlene --force select      # chọn lại ảnh, dựng timeline, render
```

Mỗi bước lưu JSON trong thư mục dự án và được bỏ qua ở lần chạy sau; `--force <bước>` làm lại bước đó và mọi bước sau. Các bước: `segment, subject, briefs, search, narrate, select, timeline, render`. Kết quả tìm kiếm SerpApi được cache nên chạy lại không tốn thêm lượt. Xem trước trong Remotion Studio: `cd video && npm run dev`.

Vẫn có thể bắt đầu từ kịch bản `.txt` (`docugen new examples/chaplin_en.txt --lang en`); khi đó audio được tạo bằng ElevenLabs.

## Cách tìm ảnh (tóm tắt)

- **Entity first:** Claude xác định người, sự kiện, năm của từng cảnh và viết 3 đến 5 truy vấn neo sự kiện ("Charlie Chaplin The Kid 1921"), cộng truy vấn dự phòng.
- **Danh tính bằng tiêu đề ảnh, không bằng khuôn mặt:** ảnh có tên người trong tiêu đề hoặc trang nguồn được xếp trên hẳn ảnh không có tên. CLIP (tùy chọn) chỉ xếp hạng lại theo độ khớp với cảnh.
- **Nguồn:** Google Images qua SerpApi. Wikimedia, Openverse, Pexels, Brave vẫn còn trong code, bật lại bằng `DOCUGEN_PROVIDERS`.

Chi tiết: [docs/FOOTAGE_AGENT.md](docs/FOOTAGE_AGENT.md).

## Kiểm thử

```bash
cd pipeline && python -m pytest       # chạy offline, mọi API đều được giả lập
cd video && npm run lint
```
