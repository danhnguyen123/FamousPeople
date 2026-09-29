# video/ (Remotion)

Dựng video từ `timeline.json` do pipeline Python tạo ra.

```bash
npm i
npm run dev          # Remotion Studio, xem trước với dữ liệu mẫu (src/sampleProps.ts)
npx remotion render Documentary out/video.mp4 --props=../projects/<slug>/timeline.json
```

- `src/schema.ts`: schema zod của props, phải khớp với `pipeline/src/docugen/timeline.py`.
- `src/Documentary.tsx`: đặt từng shot theo thời gian tuyệt đối lấy từ TTS (không lệch tiếng), crossfade giữa các shot.
- `src/components/KenBurnsShot.tsx`: hiệu ứng keyframe (zoom, pan) + nền mờ cho ảnh dọc hoặc ảnh nhỏ.
- `public/projects/<slug>/`: ảnh và audio pipeline chép vào (không commit).

Bộ skill Remotion nằm ở `../.claude/skills/` (từ `remotion-dev/skills`, bản 4.0.530).
