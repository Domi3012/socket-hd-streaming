import os

class VideoStream:
    def __init__(self, filename):
        # 1. Mở file VIDEO (Tự động tìm trong StandardizedVideo nếu cần)
        if os.path.exists(filename):
            self.filename = filename
        elif os.path.exists(os.path.join("StandardizedVideo", filename)):
            self.filename = os.path.join("StandardizedVideo", filename)
        else:
            self.filename = filename 

        try:
            self.file = open(self.filename, 'rb')
            print(f"[VideoStream] Da mo file: {self.filename}")
        except:
            raise IOError

        # 2. Định vị file COUNT (Trỏ thẳng vào thư mục CountFrame)
        # Lấy tên file gốc (vd: movie.Mjpeg)
        basename = os.path.basename(self.filename)
        
        # Đường dẫn ưu tiên số 1: CountFrame/movie.Mjpeg.count
        self.count_file = os.path.join("CountFrame", basename + ".count")
        
        # Đường dẫn ưu tiên số 2: Ngay cạnh file video (backup)
        self.backup_count_file = self.filename + ".count"

        self.frameNum = 0
        self.total_frames = self.get_total_frames()

    def get_total_frames(self):
        # Cách 1: Tìm trong CountFrame
        if os.path.exists(self.count_file):
            with open(self.count_file, 'r') as f:
                val = int(f.read().strip())
                print(f"[VideoStream] Lay frame tu CountFrame: {val}")
                return val
        
        # Cách 2: Tìm ngay cạnh video (nếu bạn lỡ chạy tool tạo file ở ngoài)
        if os.path.exists(self.backup_count_file):
            with open(self.backup_count_file, 'r') as f:
                val = int(f.read().strip())
                print(f"[VideoStream] Lay frame canh video: {val}")
                return val

        # Không tìm thấy -> Mặc định 500
        print("[VideoStream] Khong thay file .count -> Dung mac dinh 500")
        return 500

    def nextFrame(self):
        data = self.file.read(5)
        if data: 
            try:
                # Logic đọc HD/SD
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
                self.file.seek(l, 1) 
                self.frameNum += 1
            except: break

    def frameNbr(self):
        return self.frameNum
        
    def getTotalFrames(self):
        return self.total_frames