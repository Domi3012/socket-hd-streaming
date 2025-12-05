from tkinter import *
import tkinter.messagebox
from PIL import Image, ImageTk
import socket, threading, os, queue, time
from io import BytesIO

from RtpPacket import RtpPacket

class Client:
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3

    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)

        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)
        self.fileName = filename

        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0

        self.frameNbr = 0
        self.totalFrames = 500 # Mặc định
        self.maxCachedFrame = 0 

        self.isTotalFrameLogged = False
        self.frameQueue = queue.PriorityQueue()
        self.received_frames_ids = set()

        self.stopThreads = False
        self.playEvent = None
        self.rtpThread = None
        self.playerThread = None

        self.isSeeking = False
        self.wasPlaying = False

        self.createWidgets()
        self.connectToServer()

    def createWidgets(self):
        self.master.geometry("800x600")
        self.master.resizable(False, False)

        self.videoFrame = Frame(self.master, bg='black')
        self.videoFrame.pack(side=TOP, expand=True, fill=BOTH)
        self.videoFrame.pack_propagate(False)

        self.label = Label(self.videoFrame, bg='black')
        self.label.pack(expand=True, fill=BOTH)

        self.progressCanvas = Canvas(self.master, height=15, bg='#202020', highlightthickness=0)
        self.progressCanvas.pack(side=TOP, fill=X, padx=5, pady=2)

        self.progressCanvas.bind("<Button-1>", self.onProgressClick)
        self.progressCanvas.bind("<B1-Motion>", self.onProgressDrag)
        self.progressCanvas.bind("<ButtonRelease-1>", self.onProgressRelease)

        self.btnFrame = Frame(self.master)
        self.btnFrame.pack(side=TOP, pady=5)

        Button(self.btnFrame, width=20, text="Setup", command=self.setupMovie).grid(row=0, column=0)
        Button(self.btnFrame, width=20, text="Play", command=self.playMovie).grid(row=0, column=1)
        Button(self.btnFrame, width=20, text="Pause", command=self.pauseMovie).grid(row=0, column=2)
        Button(self.btnFrame, width=20, text="Teardown", command=self.exitClient).grid(row=0, column=3)

        self.updateProgressTimer()

    def _getTotalFramesForUI(self):
        return max(self.totalFrames, 1)

    def setupMovie(self):
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)

    def onProgressClick(self, event):
        if self.state not in (self.READY, self.PLAYING): return
        self.isSeeking = True
        self.wasPlaying = (self.state == self.PLAYING)
        if self.wasPlaying: self.pauseMovie()
        self._seekToPosition(event.x)

    def onProgressDrag(self, event):
        if not self.isSeeking: return
        w = self.progressCanvas.winfo_width()
        if w <= 1: return
        total = self._getTotalFramesForUI()
        ratio = min(max(event.x / w, 0.0), 1.0)
        self.frameNbr = int(ratio * total)
        self._drawProgressBar()

    def onProgressRelease(self, event):
        if not self.isSeeking: return
        self.isSeeking = False
        target = self._seekToPosition(event.x)
        self.clearCache()
        self.frameNbr = target
        if self.wasPlaying:
            self.sendRtspRequest(self.PLAY, seekFrame=target)
            time.sleep(0.05)
            self.startPlayback()
        else:
            self.sendRtspRequest(self.PLAY, seekFrame=target)
            self.sendRtspRequest(self.PAUSE)

    def _seekToPosition(self, x):
        w = self.progressCanvas.winfo_width()
        total = self._getTotalFramesForUI()
        ratio = min(max(x / w, 0.0), 1.0)
        target = int(ratio * total)
        print(f"[Client] Dang tua den frame: {target}")
        self.frameNbr = target
        self._drawProgressBar()
        return target

    def clearCache(self):
        while not self.frameQueue.empty():
            try: self.frameQueue.get_nowait()
            except: break
        self.received_frames_ids.clear()
        self.maxCachedFrame = self.frameNbr

    def _drawProgressBar(self):
            try:
                w = self.progressCanvas.winfo_width()
                h = self.progressCanvas.winfo_height()
                self.progressCanvas.delete("all")
                
                total = self._getTotalFramesForUI()
                
                # 1. Tính toán vị trí ĐỎ (Đang xem)
                played_ratio = min(self.frameNbr / total, 1.0)
                played_w = w * played_ratio

                # 2. Tính toán vị trí XÁM (Real Cache)
                buffered_frames = self.frameQueue.qsize() 
                real_cached_frame = self.frameNbr + buffered_frames
                
                cached_ratio = min(real_cached_frame / total, 1.0)
                cached_w = w * cached_ratio

                # 3. Vẽ Nền Đen
                self.progressCanvas.create_rectangle(0, 0, w, h, fill="#111111", outline="")

                # 4. Vẽ Thanh Xám (Từ đầu đến điểm Cache thực tế)
                if cached_w > played_w:
                    self.progressCanvas.create_rectangle(played_w, 0, cached_w, h, fill="#666666", outline="")

                # 5. Vẽ Thanh Đỏ (Đè lên trên)
                if played_w > 0:
                    self.progressCanvas.create_rectangle(0, 0, played_w, h, fill="#E50914", outline="")
                
                # 6. Cục tròn (Knob)
                self.progressCanvas.create_oval(played_w-5, h/2-5, played_w+5, h/2+5, fill='white', outline='')
                
            except:
                pass

    def updateProgressTimer(self):
        if not self.stopThreads:
            self._drawProgressBar()
            self.master.after(100, self.updateProgressTimer)

    def exitClient(self):
        self.stopThreads = True
        self.stopPlayback()
        self.sendRtspRequest(self.TEARDOWN)
        time.sleep(0.2)
        self.master.destroy()

    def pauseMovie(self):
        if self.state == self.PLAYING:
            self.stopPlayback()
            self.sendRtspRequest(self.PAUSE)

    def playMovie(self):
        if self.state == self.READY:
            self.startPlayback()
            self.sendRtspRequest(self.PLAY)

    def startPlayback(self):
        self.stopThreads = False
        self.playEvent = threading.Event()
        self.playEvent.clear()
        if self.rtpThread is None or not self.rtpThread.is_alive():
            self.rtpThread = threading.Thread(target=self.listenRtp, daemon=True)
            self.rtpThread.start()
        if self.playerThread is None or not self.playerThread.is_alive():
            self.playerThread = threading.Thread(target=self.runPlayer, daemon=True)
            self.playerThread.start()

    def stopPlayback(self):
        if self.playEvent: self.playEvent.set()

    def listenRtp(self):
            try:
                self.rtpSocket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576) 
                self.rtpSocket.settimeout(0.5)
            except: pass
            current_frame_buffer = b""
            while not self.stopThreads:
                try:
                    if self.playEvent.is_set(): break
                    data = self.rtpSocket.recv(65535)
                    if not data: continue
                    pkt = RtpPacket()
                    pkt.decode(data)
                    seq = pkt.seqNum()
                    payload = pkt.getPayload()
                    is_last_packet = (data[1] >> 7) & 1
                    current_frame_buffer += payload
                    if is_last_packet == 1:
                        if seq > self.maxCachedFrame: self.maxCachedFrame = seq
                        
                        # LOGIC MỚI: Chỉ cập nhật totalFrames nếu nó lớn hơn giá trị server gửi
                        # (đề phòng trường hợp hiếm hoi server đếm sai, nhưng thường là giữ nguyên)
                        if seq > self.totalFrames: self.totalFrames = seq

                        if seq not in self.received_frames_ids:
                            self.frameQueue.put((seq, current_frame_buffer))
                            self.received_frames_ids.add(seq)
                        current_frame_buffer = b""
                except socket.timeout: continue
                except: break

    def runPlayer(self):
            is_buffering = True
            while not self.stopThreads:
                try:
                    if self.playEvent.is_set(): break
                    
                    # --- TÍNH SỐ FRAME CÒN LẠI CỦA VIDEO ---
                    frames_left_in_video = self.totalFrames - self.frameNbr

                    # --- SỬA LOGIC BUFFERING ---
                    # Chỉ kích hoạt Buffering khi:
                    # 1. Queue sắp cạn (< 5)
                    # 2. VÀ Video vẫn còn dài (còn hơn 20 frame nữa mới hết)
                    # (Nếu còn < 20 frame thì chạy luôn cho hết, không chờ nữa)
                    if self.frameQueue.qsize() < 5 and not is_buffering and frames_left_in_video > 20:
                        is_buffering = True
                        print("Buffering...")
                    
                    # Nếu đang buffering, kiểm tra điều kiện để chạy tiếp
                    if is_buffering:
                        # Chạy tiếp nếu: Đã gom đủ 20 frame HOẶC Đã gom hết số frame còn lại
                        if self.frameQueue.qsize() > 20 or self.frameQueue.qsize() >= frames_left_in_video:
                            is_buffering = False
                            print("Resuming playback...")
                        else:
                            time.sleep(0.01) # Ngủ chờ nạp thêm
                            continue
                    # ---------------------------

                    if self.frameQueue.empty():
                        time.sleep(0.01)
                        continue

                    seq, imageData = self.frameQueue.get()
                    if seq in self.received_frames_ids: self.received_frames_ids.remove(seq)

                    self.frameNbr = seq
                    self.updateMovie(imageData)
                    time.sleep(0.04) 
                    
                except Exception as e:
                    print("Player error:", e)
                    break

    def updateMovie(self, imageData):
        def update():
            try:
                stream = BytesIO(imageData)
                img = Image.open(stream)
                fw = self.videoFrame.winfo_width()
                fh = self.videoFrame.winfo_height()
                if fw > 1 and fh > 1:
                    iw, ih = img.size
                    ratio = min(fw/iw, fh/ih)
                    img = img.resize((int(iw*ratio), int(ih*ratio)), Image.BILINEAR)
                photo = ImageTk.PhotoImage(img)
                self.label.configure(image=photo); self.label.image = photo
            except: pass
        self.master.after_idle(update)

    def connectToServer(self):
        self.rtspSocket = socket.socket()
        self.rtspSocket.connect((self.serverAddr, self.serverPort))

    def sendRtspRequest(self, requestCode, seekFrame=None):
        self.rtspSeq += 1
        if requestCode == self.SETUP:
            threading.Thread(target=self.recvRtspReply, daemon=True).start()
            msg = f"SETUP {self.fileName} RTSP/1.0\nCseq: {self.rtspSeq}\nTransport: RTP/UDP; client_port: {self.rtpPort}"
        elif requestCode == self.PLAY:
            msg = f"PLAY {self.fileName} RTSP/1.0\nCseq: {self.rtspSeq}\nSession: {self.sessionId}"
            if seekFrame is not None: msg += f"\nRange: npt={seekFrame}"
        elif requestCode == self.PAUSE:
            msg = f"PAUSE {self.fileName} RTSP/1.0\nCseq: {self.rtspSeq}\nSession: {self.sessionId}"
        elif requestCode == self.TEARDOWN:
            msg = f"TEARDOWN {self.fileName} RTSP/1.0\nCseq: {self.rtspSeq}\nSession: {self.sessionId}"
        else: return
        self.requestSent = requestCode
        self.rtspSocket.send(msg.encode())

    def recvRtspReply(self):
        while True:
            try:
                data = self.rtspSocket.recv(1024)
                if data: self.parseRtspReply(data.decode())
                if self.requestSent == self.TEARDOWN: return
            except: break

    def parseRtspReply(self, data):
        lines = data.split('\n')
        code = int(lines[0].split(' ')[1])
        seq = int(lines[1].split(' ')[1])
        if seq != self.rtspSeq: return
        session = int(lines[2].split(' ')[1])
        if self.sessionId == 0: self.sessionId = session
        if code == 200:
            # --- LOGIC MỚI: Đọc tổng số frame từ Server ---
            for line in lines:
                if "Frames:" in line:
                    try: 
                        val = int(line.split(":")[1].strip())
                        self.totalFrames = val
                        
                        # Chỉ in nết chưa từng in trước đó
                        if not self.isTotalFrameLogged:
                            print(f"[Client] Tong so frame video: {self.totalFrames}")
                            self.isTotalFrameLogged = True
                    except: pass
            # ---------------------------------------------
            
            if self.requestSent == self.SETUP: self.state = self.READY; self.openRtpPort()
            elif self.requestSent == self.PLAY: self.state = self.PLAYING
            elif self.requestSent == self.PAUSE: self.state = self.READY
            elif self.requestSent == self.TEARDOWN: self.state = self.INIT

    def openRtpPort(self):
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtpSocket.bind(("", self.rtpPort))
        self.rtpSocket.settimeout(0.5)

    def handler(self):
        self.pauseMovie()
        if tkinter.messagebox.askokcancel("Quit?", "Quit?"): self.exitClient()
        else: self.playMovie()