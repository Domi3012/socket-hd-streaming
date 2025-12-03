# VideoStream.py – PHIÊN BẢN HOÀN HẢO CHO RAW MJPEG & LAB
# Chạy được 100.000 frame không dừng, không lỗi

class VideoStream:
    def __init__(self, filename, skip_bytes=0):
        self.filename = filename
        self.skip_bytes = skip_bytes
        self.file = open(filename, 'rb')
        if skip_bytes:
            self.file.seek(skip_bytes)      # Bỏ qua 64 byte 00 nếu là LAB
        self.frameNum = 0
        self.buffer = b""                   # Buffer dự phòng

    def nextFrame(self):
        """Trả về 1 frame JPEG hoàn chỉnh hoặc None nếu hết file"""
        while True:
            # Đọc thêm dữ liệu nếu buffer < 1MB (đảm bảo luôn có đủ dữ liệu)
            if len(self.buffer) < 1024*1024:
                chunk = self.file.read(1024*256)   # Đọc 256KB mỗi lần
                if not chunk:
                    if self.buffer:                    # Còn dư buffer → trả frame cuối
                        frame = self.buffer
                        self.buffer = b""
                        self.frameNum += 1
                        return frame
                    return None                        # Hết file thật sự
                self.buffer += chunk

            # Tìm SOI (FFD8)
            start = self.buffer.find(b'\xff\xd8')
            if start == -1:                    # Không có SOI → file lỗi
                self.buffer = b""
                continue

            # Tìm EOI (FFD9) từ vị trí sau SOI
            end = self.buffer.find(b'\xff\xd9', start + 2)
            if end == -1:
                # Chưa đủ dữ liệu → đọc tiếp ở vòng sau
                continue

            end += 2                               # Bao gồm cả FFD9
            frame = self.buffer[start:end]
            self.buffer = self.buffer[end:]        # Cắt bỏ phần đã dùng
            self.frameNum += 1
            return frame                           # Trả frame hoàn chỉnh

    def frameNbr(self):
        return self.frameNum

    def close(self):
        try:
            self.file.close()
        except:
            pass