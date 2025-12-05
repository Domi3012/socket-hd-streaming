import glob
import os

def count_frames(filename):
    print(f"Dang quet file: {filename} ...")
    count = 0
    try:
        with open(filename, 'rb') as f:
            while True:
                # 1. Đọc 5 byte đầu
                data = f.read(5)
                if not data: break
                
                length = 0
                try:
                    # 2. Hack: Đọc thêm 1 byte để check HD (6 số) hay SD (5 số)
                    next_byte = f.read(1)
                    
                    if next_byte and next_byte.isdigit():
                        # Nếu là số -> Video HD (6 số)
                        length = int(data + next_byte)
                    else:
                        # Nếu không phải số -> Video SD (5 số)
                        length = int(data)
                        # Quan trọng: Lùi lại 1 byte vì lỡ đọc thừa
                        f.seek(-1, 1) 
                    
                    # 3. Nhảy qua phần dữ liệu ảnh (Seek) để đếm cho nhanh
                    f.seek(length, 1)
                    count += 1
                    
                except ValueError:
                    print(" -> Gap header loi, dung quet.")
                    break
        
        # Lưu kết quả chính xác vào file
        with open(filename + ".count", "w") as f_count:
            f_count.write(str(count))
            
        print(f" -> XONG! Tim thay: {count} frames.")
        
    except Exception as e:
        print(f" -> Loi file: {e}")

# Quét lại toàn bộ
print("--- BAT DAU QUET LAI FRAME ---")
files = glob.glob("*.Mjpeg") + glob.glob("*.mjpeg")
# Lọc trùng lặp (do chữ hoa thường)
files = list(set(files))

for video in files:
    count_frames(video)