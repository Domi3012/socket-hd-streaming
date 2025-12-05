import sys

def convert_to_lab_format(input_file, output_file):
    print(f"Đang xử lý: {input_file} -> {output_file}")
    
    with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
        data = f_in.read()
        
        # Tìm kiếm các frame JPEG dựa trên Start Marker (0xFF 0xD8)
        # Lưu ý: Cách này đơn giản, áp dụng cho file MJPEG chuẩn (chỉ chứa các ảnh nối tiếp)
        start = 0
        frame_count = 0
        
        while True:
            # Tìm đầu frame (FF D8)
            start_pos = data.find(b'\xff\xd8', start)
            if start_pos == -1:
                break
                
            # Tìm cuối frame (FF D9)
            # Lưu ý: Tìm FF D9 tiếp theo sau start_pos
            end_pos = data.find(b'\xff\xd9', start_pos)
            if end_pos == -1:
                break
            
            # Cắt frame ra
            # +2 để lấy cả 2 byte FF D9
            frame_data = data[start_pos : end_pos + 2]
            frame_size = len(frame_data)
            
            # --- QUAN TRỌNG: Tạo header 5-byte ---
            # Ví dụ: Size là 12345 -> Header là "12345"
            # Ví dụ: Size là 500 -> Header là "00500"
            header = str(frame_size).zfill(5).encode()
            
            # Ghi vào file mới: [Header] + [Frame]
            f_out.write(header)
            f_out.write(frame_data)
            
            frame_count += 1
            # Di chuyển con trỏ để tìm frame tiếp theo
            start = end_pos + 2
            
    print(f"Xong! Đã chuyển đổi {frame_count} frame.")

# --- CÁCH SỬ DỤNG ---
# Đổi tên file bên dưới
INPUT_NAME = "../sample/standard/sample1.mjpeg"  # File bạn tải trên mạng
OUTPUT_NAME = "../sample/lab/sample1.Mjpeg" # File dùng cho đồ án

if __name__ == "__main__":
    # Kiểm tra xem người dùng có nhập đủ tham số không (argc)
    # Cần 2 tham số: [Tên script] [File nguồn] [File đích]
    if len(sys.argv) != 3:
        print("Cách sử dụng: python video_converter.py <input_file> <output_file>")
        print("Ví dụ: python video_converter.py standard.mjpeg movie.Mjpeg")
        sys.exit(1) # Thoát chương trình với mã lỗi

    # Lấy tham số từ dòng lệnh (argv)
    input_name = sys.argv[1]
    output_name = sys.argv[2]

    # Gọi hàm xử lý
    convert_to_lab_format(input_name, output_name)