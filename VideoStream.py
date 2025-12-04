import threading

class VideoStream:
    def __init__(self, filename, skip_bytes=0):
        self.filename = filename
        self.skip_bytes = skip_bytes

        # File chính dùng cho streaming
        self.file = open(filename, 'rb')
        if skip_bytes:
            self.file.seek(skip_bytes)

        self.buffer = b""
        self.frameNum = 0

        # LƯU VỊ TRÍ FILE CỦA MỖI FRAME
        self.framePositions = []  # [(file_pos, frame_size), ...]
        self.totalFrames = -1
        self.countingDone = False
        
        # Đếm frame + lưu vị trí trong background
        threading.Thread(target=self._index_frames, daemon=True).start()

    # ------------------------------------------------------------
    # INDEX TẤT CẢ FRAME POSITIONS
    # ------------------------------------------------------------
    def _index_frames(self):
        """Quét file, lưu vị trí của từng frame"""
        print("[VideoStream] Indexing frames...")
        
        with open(self.filename, 'rb') as f:
            if self.skip_bytes:
                f.seek(self.skip_bytes)

            buf = b""
            file_offset = f.tell()
            
            while True:
                chunk = f.read(1024 * 256)
                if not chunk:
                    break
                buf += chunk

                while True:
                    start = buf.find(b'\xff\xd8')  # SOI
                    if start == -1:
                        file_offset += len(buf) - 3
                        buf = buf[-3:]
                        break

                    end = buf.find(b'\xff\xd9', start + 2)  # EOI
                    if end == -1:
                        file_offset += start
                        buf = buf[start:]
                        break

                    # Tìm được 1 frame hoàn chỉnh
                    end += 2
                    frame_size = end - start
                    
                    # Lưu vị trí file của frame này
                    self.framePositions.append((file_offset + start, frame_size))
                    
                    file_offset += end
                    buf = buf[end:]

        self.totalFrames = len(self.framePositions)
        if self.totalFrames <= 0:
            self.totalFrames = 1
            
        self.countingDone = True
        print(f"[VideoStream] Indexed {self.totalFrames} frames")

    def getTotalFrames(self):
        """Trả về tổng frame"""
        if self.totalFrames == -1:
            return 1000  # Estimate khi đang index
        return self.totalFrames

    # ------------------------------------------------------------
    # READ FRAME
    # ------------------------------------------------------------
    def _read_raw_frame(self):
        """Đọc 1 frame JPEG từ file"""
        while True:
            if len(self.buffer) < 1024 * 256:
                chunk = self.file.read(1024 * 256)
                if not chunk:
                    return None
                self.buffer += chunk

            start = self.buffer.find(b'\xff\xd8')
            if start == -1:
                self.buffer = b""
                continue

            if start > 0:
                self.buffer = self.buffer[start:]
                start = 0

            end = self.buffer.find(b'\xff\xd9', start + 2)
            if end == -1:
                chunk = self.file.read(1024 * 256)
                if not chunk:
                    return None
                self.buffer += chunk
                continue

            end += 2
            frame = self.buffer[start:end]
            self.buffer = self.buffer[end:]
            return frame

    def nextFrame(self):
        """Trả về frame tiếp theo"""
        frame = self._read_raw_frame()
        if frame is None:
            return None
        self.frameNum += 1
        return frame

    def frameNbr(self):
        """Số frame hiện tại (1-based)"""
        return self.frameNum

    # ------------------------------------------------------------
    # SEEK NHANH BẰNG FILE POSITION
    # ------------------------------------------------------------
    def seekFrame(self, n):
        """Seek tới frame n (1-based) - NHANH"""
        # Đợi index xong
        if not self.countingDone:
            print("[VideoStream] Waiting for indexing to complete...")
            while not self.countingDone:
                import time
                time.sleep(0.05)
        
        # Clamp
        if n < 1:
            n = 1
        if n > self.totalFrames:
            n = self.totalFrames

        print(f"[VideoStream] Seek to frame {n}/{self.totalFrames}")

        # Reset file pointer
        try:
            self.file.close()
        except:
            pass

        self.file = open(self.filename, 'rb')
        
        # SEEK TRỰC TIẾP ĐẾN VỊ TRÍ FRAME N
        if n > 1 and (n - 1) < len(self.framePositions):
            target_pos, _ = self.framePositions[n - 1]
            self.file.seek(target_pos)
            print(f"[VideoStream] Jumped to file position {target_pos}")
        elif self.skip_bytes:
            self.file.seek(self.skip_bytes)

        self.buffer = b""
        self.frameNum = n - 1  # Vì nextFrame() sẽ +1

    def close(self):
        try:
            self.file.close()
        except:
            pass