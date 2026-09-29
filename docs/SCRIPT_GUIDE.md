# Viết kịch bản để Footage Agent tìm đúng ảnh

Footage Agent chỉ đọc lời thoại. Nó không hiểu chỉ dẫn kiểu `[SHOW BANK]` hay `(CUT TO ...)`; pipeline xóa các dòng này trước khi xử lý.

## Nguyên tắc: viết bằng hình ảnh, không đạo diễn bằng hình ảnh

| Yếu | Mạnh |
|---|---|
| "Rồi mọi thứ thay đổi." | "Năm 1994, tại buổi công chiếu Little Women ở Los Angeles, mọi thứ thay đổi." |
| "Cô ấy nổi tiếng hơn bao giờ hết." | "Cô xuất hiện trên thảm đỏ lễ trao giải Oscar lần thứ 66." |
| "Anh ấy bắt đầu sự nghiệp." | "Năm 1913, Chaplin ký hợp đồng đầu tiên với hãng Keystone ở Los Angeles." |

Mỗi đoạn nên chứa ít nhất một trong các "neo" sau:

1. **Tên đầy đủ** của người đang được nói tới (ít nhất ở câu đầu của mỗi đoạn; đại từ "cô ấy", "anh ta" vẫn được, Claude sẽ tự suy ra).
2. **Năm** hoặc mốc tuổi ("năm 22 tuổi" cũng được, pipeline cộng với năm sinh từ Wikidata).
3. **Sự kiện cụ thể**: phim, album, lễ trao giải, phiên tòa, buổi phỏng vấn, chương trình TV.
4. **Địa điểm có tên**: thành phố, nhà hát, trường học, studio.

Sự kiện là neo mạnh nhất: một buổi công chiếu sinh ra hàng trăm ảnh có chú thích ghi đủ tên, năm và địa điểm, nên xác suất tìm đúng người rất cao.

## Tránh "sa mạc nội dung"

- Chủ đề quá hẹp (một vụ việc địa phương năm 1990) sẽ buộc video lặp lại vài tấm ảnh ít ỏi. Hãy mở rộng bối cảnh: thành phố, thời đại, những người liên quan.
- Đoạn cảm xúc thuần túy ("nỗi cô đơn gặm nhấm anh") sẽ được tính là cảnh `generic` và dùng ảnh stock (mưa, phố đêm). Đừng để quá 1 trên 4 cảnh là loại này.
- Người càng nổi tiếng trước năm 1990 càng có nhiều ảnh public domain trên Wikimedia Commons. Người nổi tiếng hiện đại có ít ảnh tự do hơn: xem mục bản quyền trong `FOOTAGE_AGENT.md`.

## Đa ngôn ngữ

Kịch bản có thể viết bằng tiếng Anh, Pháp, Đức, Ý, Ba Lan hoặc Hà Lan. Truy vấn tìm ảnh luôn được sinh bằng tiếng Anh (metadata lưu trữ phần lớn là tiếng Anh), kèm 1 đến 2 truy vấn bằng ngôn ngữ kịch bản. Tên riêng giữ nguyên dạng gốc.
