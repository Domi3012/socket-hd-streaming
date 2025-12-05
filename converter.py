import sys
import os
import glob
import shutil # Thư viện dùng để copy file

# --- CẤU HÌNH THƯ MỤC (Dựa theo hình ảnh mới nhất của bạn) ---
INPUT_FOLDER = "RawVideo"           # Nơi chứa file gốc (có thể lẫn lộn chuẩn/chưa chuẩn)
OUTPUT_FOLDER = "StandardizedVideo" # Nơi xuất file kết quả

def is_standard_format(file_path):
    """
    Hàm kiểm tra nhanh xem file đã có header kích thước chưa.
    Cách kiểm tra: Đọc 5 byte đầu tiên.
    - Nếu 5 byte đó là chữ số (VD: '12034') -> Đã chuẩn.
    - Nếu 5 byte đó chứa ký tự lạ hoặc FF D8 -> Chưa chuẩn.
    """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(5)
            # Kiểm tra xem 5 ký tự này có phải là số không
            if len(header) == 5 and header.isdigit():
                return True
    except:
        pass
    return False

def convert_to_lab_format(input_file, output_file):
    display_name = os.path.basename(input_file)
    print(f"--> Đang kiểm tra: {display_name} ...")
    
    # TRƯỜNG HỢP 1: File đã chuẩn -> Chỉ cần COPY
    if is_standard_format(input_file):
        print(f"    [INFO] File này ĐÃ CHUẨN định dạng (có header). Đang copy...")
        try:
            shutil.copy2(input_file, output_file)
            print(f"    [OK] Đã copy sang: {os.path.basename(output_file)}")
        except Exception as e:
            print(f"    [LỖI] Copy thất bại: {e}")
        return

    # TRƯỜNG HỢP 2: File chưa chuẩn (Raw) -> Tiến hành CONVERT
    print(f"    [INFO] File Raw MJPEG. Đang xử lý thêm header...")
    try:
        with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
            data = f_in.read()
            
            start = 0
            frame_count = 0
            
            while True:
                # Tìm đầu frame (FF D8)
                start_pos = data.find(b'\xff\xd8', start)
                if start_pos == -1: break
                    
                # Tìm cuối frame (FF D9)
                end_pos = data.find(b'\xff\xd9', start_pos)
                if end_pos == -1: break
                
                # Cắt frame ra
                frame_data = data[start_pos : end_pos + 2]
                frame_size = len(frame_data)
                
                # Tạo header 5-byte
                header = str(frame_size).zfill(5).encode()
                
                f_out.write(header)
                f_out.write(frame_data)
                
                frame_count += 1
                start = end_pos + 2
                
        print(f"    [OK] Convert xong: {os.path.basename(output_file)} ({frame_count} frames)")
        
    except Exception as e:
        print(f"    [LỖI] Xử lý file {display_name}: {e}")

def batch_process():
    # Kiểm tra folder Input
    if not os.path.exists(INPUT_FOLDER):
        print(f"LỖI: Không tìm thấy thư mục '{INPUT_FOLDER}'!")
        return

    # Tạo folder Output
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    # Quét file: Tìm cả .mjpeg (thường) và .Mjpeg (đã convert)
    # Vì có thể bạn để lẫn lộn file đã convert vào folder nguồn
    files_grabbed = []
    types = ('*.mjpeg', '*.Mjpeg', '*.MJPEG') 
    for files in types:
        files_grabbed.extend(glob.glob(os.path.join(INPUT_FOLDER, files)))
    
    # Lọc trùng lặp file (nếu có)
    files_grabbed = list(set(files_grabbed))

    if not files_grabbed:
        print(f"Không tìm thấy file video nào trong '{INPUT_FOLDER}'!")
        return

    print(f"Tìm thấy {len(files_grabbed)} file. Bắt đầu xử lý...\n")

    for file_path in files_grabbed:
        filename = os.path.basename(file_path)
        base_name = os.path.splitext(filename)[0]
        
        # Luôn xuất ra đuôi .Mjpeg (viết hoa chữ M để đánh dấu file chuẩn)
        output_path = os.path.join(OUTPUT_FOLDER, f"{base_name}.Mjpeg")
        
        convert_to_lab_format(file_path, output_path)

    print("\n-------------------------------------------")
    print(f"HOÀN TẤT! Kiểm tra thư mục '{OUTPUT_FOLDER}'.")

if __name__ == "__main__":
    batch_process()