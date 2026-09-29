# FamousPeople: tạo video documentary từ kịch bản

Công cụ kiểu VidRush: đưa vào một kịch bản, nhận ra video MP4 gồm lời đọc, ảnh tư liệu chạy hiệu ứng keyframe (Ken Burns) và phụ đề. Chủ đề đầu tiên: documentary về người nổi tiếng, hỗ trợ **tiếng Anh, Pháp, Đức, Ý, Ba Lan, Hà Lan**.

```
kịch bản ──► Footage Agent (Python) ──► timeline.json ──► Remotion ──► MP4
             Claude + Wikidata + Commons/Openverse/Pexels
             + ElevenLabs (timestamps)
```

| Thư mục | Nội dung |
|---|---|
| `pipeline/` | Gói Python `docugen`: tách cảnh, Footage Agent, TTS, xuất timeline |
| `video/` | Dự án Remotion 4 dựng video từ timeline |
| `.claude/skills/` | Bộ skill Remotion chính thức (`remotion-dev/skills`) cho Claude Code |
| `docs/FOOTAGE_AGENT.md` | Kiến trúc tìm ảnh, công thức chấm điểm, bản quyền |
| `docs/SCRIPT_GUIDE.md` | Cách viết kịch bản để tìm đúng ảnh |
| `examples/` | Kịch bản mẫu (Charlie Chaplin, EN và FR) |
| `projects/<slug>/` | Kết quả từng dự án (không commit) |

## Cài đặt

```bash
cp .env.example .env            # điền ANTHROPIC_API_KEY, ELEVENLABS_*, DOCUGEN_USER_AGENT
cd pipeline && pip install -e ".[dev]"     # thêm ".[clip]" nếu muốn xếp hạng bằng CLIP
cd ../video && npm i
```

## Chạy

```bash
docugen new examples/chaplin_en.txt --lang en        # tạo projects/chaplin-en/
docugen run chaplin-en --no-tts --until select       # xem trước, chưa tốn tiền TTS
# mở projects/chaplin-en/review.html, thay ảnh sai bằng manual/scene_007.jpg
docugen run chaplin-en --force narrate               # TTS thật + timeline + render
```

Mỗi bước lưu JSON trong thư mục dự án và được bỏ qua ở lần chạy sau; `--force <bước>` làm lại bước đó và mọi bước sau. Các bước: `segment, subject, briefs, search, narrate, select, timeline, render`. Xem trước trong Remotion Studio: `cd video && npm run dev`.

## Cách tìm ảnh (tóm tắt)

- **Entity first:** Claude đọc kịch bản, xác định người/sự kiện/năm của từng cảnh; Wikidata cho tên ở 6 ngôn ngữ, bí danh, năm sinh và danh sách tác phẩm để tạo truy vấn neo sự kiện ("Charlie Chaplin The Kid 1921").
- **Danh tính bằng metadata, không bằng khuôn mặt:** ảnh cảnh có người bị loại nếu tên không nằm trong chú thích/category. CLIP chỉ xếp hạng lại theo độ khớp với cảnh.
- **Category theo năm của Commons** (`Charlie Chaplin in 1915`) được thử trước tiên.
- **Bản quyền:** mặc định chỉ dùng public domain, Creative Commons, stock free; ảnh CC BY được ghi công trên hình và trong `credits.txt`. Không scrape Pinterest/Google; web discovery chỉ qua API và luôn cần duyệt tay.

Chi tiết: [docs/FOOTAGE_AGENT.md](docs/FOOTAGE_AGENT.md).

## Kiểm thử

```bash
cd pipeline && python -m pytest       # chạy offline, mọi API đều được giả lập
cd video && npm run lint
```
