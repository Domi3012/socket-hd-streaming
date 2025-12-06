# BÁO CÁO ĐỒ ÁN MẠNG MÁY TÍNH - VIDEO STREAMING

## 1. Thông Tin Nhóm Sinh Viên
| STT | Họ và Tên | MSSV |
|:---:|:--- |:--- |
| 1 | Nguyễn Đức Anh Khôi | 24120076 |
| 2 | Nguyễn Quang Phát | 24120117 |
| 3 | Trần Nguyễn Quốc Khánh | 24120192 |

---

## 2. Cấu Trúc Tập Tin
Dưới đây là sơ đồ các file mã nguồn trong dự án:

```text
SOCKET-HD-STREAMING/
│
├── CountFrame            # Thư mục chứa file .count đếm tổng số frame
├── RawVideo              # Thư mục chưa Video chưa qua xử lí định dạng
├── StandardizedVideo      # Thư mục chứa Video đã được xử lí định dạng 
├── Client.py             # Xử lý logic phía Client 
├── ClientLauncher.py     # File khởi chạy Client 
├── converter.py          # Tool tiện ích: Chuyển đổi định dạng video
├── prepare_video.py      # Tool tiện ích: Đếm trước số frame để tạo file .count
├── readme.md
├── RtpPacket.py          # Class đóng gói/giải gói giao thức RTP
├── Server.py             # File khởi chạy Server 
├── ServerWorker.py       # Xử lý logic phía Server 
├── VideoStream.py        # Class đọc file video 
```

## 3. Hướng Dẫn Cài Đặt & Vận Hành

### Giai đoạn 1: Chuẩn bị dữ liệu 

**Bước 1:** Sao chép các video cần phát vào thư mục `RawVideo`.

**Bước 2:** Chạy công cụ chuẩn hóa định dạng video (Convert sang Mjpeg).
```bash
python converter.py
```

**Bước 3:** Chạy công cụ đếm tổng số frame của video.
```bash
python prepare_video.py
```

### Giai đoạn 2: Chạy chương trình 

**Bước 4:** Mở terminal đầu tiên và chạy câu lệnh 
```bash
# Cú pháp: python Server.py <Server_Port>
python Server.py 8888
```

**Bước 5:** Mở terminal thứ hai và chạy câu lệnh tương ứng 
```bash
# Cú pháp: python ClientLauncher.py <Server_IP> <Server_Port> <RTP_Port> <Video_Name>.Mjpeg
python ClientLauncher.py 127.0.0.1 8888 5000 movie.Mjpeg
```
