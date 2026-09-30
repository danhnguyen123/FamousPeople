# FamousPeople: tạo video documentary từ SRT

Đưa vào file phụ đề SRT kèm audio lời đọc, nhận ra video MP4 gồm ảnh tư liệu chạy hiệu ứng Ken Burns, lời đọc và phụ đề. Chủ đề: documentary về người nổi tiếng, hỗ trợ **tiếng Anh, Pháp, Đức, Ý, Ba Lan, Hà Lan**.

```
SRT + audio ─► plan (Claude) ─► search (Google, Bing, Brave) ─► select (Claude) ─► download ─► timeline ─► render (Remotion)
```

| Thư mục | Nội dung |
|---|---|
| `pipeline/` | Gói Python `docugen` |
| `pipeline/src/docugen/prompts/` | Prompt của Claude (`keyword_planner.md`, `image_selector.md`) |
| `video/` | Dự án Remotion 4 dựng video từ `timeline.json` |
| `docs/PIPELINE.md` | Chi tiết từng bước, định dạng `plan.json`, chi phí, so sánh nhà cung cấp |
| `projects/<slug>/` | Kết quả từng dự án (không commit) |

## Cài đặt

```bash
cp .env.example .env     # điền ANTHROPIC_API_KEY, DATAFORSEO_*, SEARCHAPI_API_KEY, BRAVE_API_KEY
cd pipeline && pip install -e .
cd ../video && npm i
```

## Chạy

```bash
docugen new --srt voice.srt --audio voice.mp3 --lang de --slug marlene
docugen run marlene --until download    # dừng lại để duyệt ảnh
# mở projects/marlene/plan.csv (và candidates.csv), thay ảnh sai bằng manual/scene_007.jpg
docugen run marlene --force download    # gán lại ảnh, dựng timeline, render
docugen status marlene
```

Mỗi bước lưu kết quả trong thư mục dự án và được bỏ qua ở lần chạy sau. `--force <bước>` làm lại bước đó và mọi bước sau. Kết quả tìm kiếm được cache nên chạy lại không tốn thêm lượt. Xem trước trong Remotion Studio: `cd video && npm run dev`.

Muốn đổi cách chia cảnh, chọn keyword hay duyệt ảnh thì sửa prompt trong `pipeline/src/docugen/prompts/`, không cần sửa code.
