import os
import glob

# Cấu hình thư mục
TARGET_FOLDER = "StandardizedVideo"   # Nơi chứa file .Mjpeg cần kiểm tra
REPORT_FOLDER = "CountFrame"    # Nơi xuất file kết quả đếm

def count_frames_in_mjpeg(file_path):
    filename = os.path.basename(file_path)
    print(f"--> Đang quét file: {filename} ...")
    
    count = 0
    try:
        with open(file_path, 'rb') as f:
            while True:
                # 1. Đọc 5 byte đầu tiên
                data = f.read(5)
                if not data:
                    break
                
                length = 0
                try:
                    # 2. Đọc thêm 1 byte để check xem là HD (6 số) hay SD (5 số)
                    next_byte = f.read(1)
                    
                    if next_byte and next_byte.isdigit():
                        # Nếu byte tiếp theo là số -> Video HD (Header 6 ký tự)
                        # Ghép 5 byte đầu + 1 byte mới đọc
                        length = int(data + next_byte)
                    else:
                        # Nếu không phải số -> Video SD (Header 5 ký tự)
                        length = int(data)
                        # QUAN TRỌNG: Lùi lại 1 byte vì lỡ đọc thừa (để dành cho vòng lặp sau hoặc data ảnh)
                        f.seek(-1, 1) 
                    
                    # 3. Nhảy qua phần dữ liệu ảnh (Seek) để đếm cho nhanh
                    f.seek(length, 1)
                    count += 1
                    
                except ValueError:
                    print(f"    [CẢNH BÁO] Gặp header lỗi tại frame thứ {count + 1}, dừng quét.")
                    break
        
        # --- XUẤT FILE KẾT QUẢ VÀO FOLDER CountFrame ---
        # Tạo tên file count: "tên_video.Mjpeg.count"
        count_filename = f"{filename}.count"
        count_file_path = os.path.join(REPORT_FOLDER, count_filename)
        
        with open(count_file_path, "w") as f_count:
            f_count.write(str(count))
            
        print(f"    [OK] Xong: {count} frames -> Đã lưu vào '{count_filename}'")
        return count

    except Exception as e:
        print(f"    [LỖI] Không thể đọc file {filename}: {e}")
        return 0

def main():
    # 1. Kiểm tra folder Destination
    if not os.path.exists(TARGET_FOLDER):
        print(f"LỖI: Không tìm thấy thư mục '{TARGET_FOLDER}'!")
        print("Bạn cần chạy 'converter.py' trước để tạo file.")
        return

    # 2. Tạo folder CountFrame nếu chưa có
    if not os.path.exists(REPORT_FOLDER):
        os.makedirs(REPORT_FOLDER)
        print(f"Đã tạo thư mục chứa kết quả: '{REPORT_FOLDER}'")

    # Tìm tất cả file .Mjpeg trong Destination
    files = glob.glob(os.path.join(TARGET_FOLDER, "*.Mjpeg"))
    
    if not files:
        print(f"Không có file .Mjpeg nào trong '{TARGET_FOLDER}'.")
        return

    print(f"Bắt đầu kiểm tra {len(files)} file trong '{TARGET_FOLDER}'...\n")

    total_all = 0
    for file_path in files:
        num = count_frames_in_mjpeg(file_path)
        total_all += num

    print("\n-------------------------------------------")
    print(f"TỔNG CỘNG: {total_all} frames.")
    print(f"Kiểm tra thư mục '{REPORT_FOLDER}' để xem các file .count")

if __name__ == "__main__":
    main()