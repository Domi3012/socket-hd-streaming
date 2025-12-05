import os

class VideoStream:
    def __init__(self, filename):
        self.filename = filename
        try:
            self.file = open(filename, 'rb')
        except:
            raise IOError
        self.frameNum = 0
        self.total_frames = 0
        
        # --- LOGIC MỚI: Đọc file .count ---
        count_file = filename + ".count"
        if os.path.exists(count_file):
            try:
                with open(count_file, 'r') as f:
                    self.total_frames = int(f.read().strip())
                print(f"[VideoStream] Da tai cache: {self.total_frames} frames.")
            except:
                self.total_frames = 500 # Mặc định nếu file lỗi
        else:
            # Nếu chưa chạy tool đếm, mặc định là 500 để không bị crash
            print("[VideoStream] Khong thay file .count, dung mac dinh 500.")
            self.total_frames = 500

    def nextFrame(self):
        """Get next frame."""
        data = self.file.read(5)
        if data: 
            try:
                # Logic HD/SD
                next_byte = self.file.read(1) 
                if next_byte and next_byte.isdigit():
                    framelength = int(data + next_byte)
                else:
                    framelength = int(data)
                    self.file.seek(-1, 1)

                data = self.file.read(framelength)
                self.frameNum += 1
                return data
            except ValueError:
                return None
        return None

    def gotoFrame(self, target_frame_num):
        """Tua nhanh"""
        if target_frame_num < 0: return
        if target_frame_num < self.frameNum:
            self.frameNum = 0
            self.file.seek(0)
            
        while self.frameNum < target_frame_num:
            data = self.file.read(5)
            if not data: break
            try:
                next_byte = self.file.read(1)
                if next_byte and next_byte.isdigit():
                    l = int(data + next_byte)
                else:
                    l = int(data)
                    self.file.seek(-1, 1)
                self.file.seek(l, 1) # Nhảy qua ảnh
                self.frameNum += 1
            except: break

    def frameNbr(self):
        return self.frameNum
        
    def getTotalFrames(self):
        return self.total_frames