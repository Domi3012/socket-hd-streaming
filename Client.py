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

        # frame tracking
        self.frameNbr = 0
        self.totalFrames = 1
        self.maxCachedFrame = 0  # largest frame received so far

        # cache (seq -> frame data)
        self.frameCache = {}
        self.cacheLock = threading.Lock()

        # threads
        self.stopThreads = False
        self.playEvent = None
        self.rtpThread = None
        self.playerThread = None

        # seeking
        self.isSeeking = False
        self.wasPlaying = False

        self.createWidgets()
        self.connectToServer()

    # ---------- GUI ----------

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

    # ---------- PROGRESS + SEEK ----------

    def _getTotalFramesForUI(self):
        return max(self.totalFrames, 1)

    def setupMovie(self):
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)

    def onProgressClick(self, event):
        if self.state not in (self.READY, self.PLAYING):
            return
        self.isSeeking = True
        self.wasPlaying = (self.state == self.PLAYING)

        # Nếu đang PLAY thì tạm dừng cả client + server (gửi PAUSE)
        if self.wasPlaying:
            self.pauseMovie()

        # Cập nhật tạm thời vị trí thanh progress
        self._seekToPosition(event.x)

    def onProgressDrag(self, event):
        if not self.isSeeking:
            return
        w = self.progressCanvas.winfo_width()
        if w <= 1:
            return
        total = self._getTotalFramesForUI()
        ratio = min(max(event.x / w, 0.0), 1.0)
        self.frameNbr = int(ratio * total)
        self._drawProgressBar()

    def onProgressRelease(self, event):
        if not self.isSeeking:
            return

        self.isSeeking = False
        target = self._seekToPosition(event.x)
        print(f"[CLIENT] Seek to frame {target}")

        # Xoá cache cũ, chuẩn bị nhận frame mới
        self.clearCache()
        self.frameNbr = target

        if self.wasPlaying:
            # Trước đó đang PLAY: tua xong thì PLAY tiếp từ frame mới
            self.sendRtspRequest(self.PLAY, seekFrame=target)
            time.sleep(0.05)
            self.startPlayback()
        else:
            # Trước đó đang PAUSE: chỉ đổi vị trí trên server, vẫn giữ trạng thái pause
            self.sendRtspRequest(self.PLAY, seekFrame=target)
            # Gửi PAUSE ngay sau đó để server về lại READY
            self.sendRtspRequest(self.PAUSE)

    def _seekToPosition(self, x):
        w = self.progressCanvas.winfo_width()
        total = self._getTotalFramesForUI()
        ratio = min(max(x / w, 0.0), 1.0)
        target = int(ratio * total)
        self.frameNbr = target
        self._drawProgressBar()
        return target

    def clearCache(self):
        with self.cacheLock:
            self.frameCache.clear()
            self.maxCachedFrame = self.frameNbr

    def _drawProgressBar(self):
        try:
            w = self.progressCanvas.winfo_width()
            h = self.progressCanvas.winfo_height()
            self.progressCanvas.delete("all")

            total = self._getTotalFramesForUI()

            played = min(self.frameNbr / total, 1.0)
            cached = min(self.maxCachedFrame / total, 1.0)

            played_w = w * played
            cached_w = w * cached

            # black background
            self.progressCanvas.create_rectangle(0, 0, w, h, fill="black", outline="")

            # gray cached
            if cached_w > played_w:
                self.progressCanvas.create_rectangle(played_w, 0, cached_w, h, fill="#777777", outline="")

            # red played
            self.progressCanvas.create_rectangle(0, 0, played_w, h, fill="red", outline="")

            # white knob
            self.progressCanvas.create_oval(
                played_w - 5, h / 2 - 5,
                played_w + 5, h / 2 + 5,
                fill='white', outline=''
            )
        except:
            pass

    def updateProgressTimer(self):
        if not self.stopThreads:
            self._drawProgressBar()
            self.master.after(100, self.updateProgressTimer)

    # ---------- CONTROL ----------

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

    # ---------- THREADS ----------

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
        if self.playEvent:
            self.playEvent.set()

    # ---------- RTP RECEIVER (STORE BY SEQ ORDER) ----------

    def listenRtp(self):
        try:
            self.rtpSocket.settimeout(0.5)
        except:
            pass

        while not self.stopThreads:
            try:
                if self.playEvent.is_set():
                    break

                data = self.rtpSocket.recv(65535)
                if not data:
                    continue

                pkt = RtpPacket()
                pkt.decode(data)
                seq = pkt.seqNum()
                payload = pkt.getPayload()

                with self.cacheLock:
                    self.frameCache[seq] = payload
                    self.maxCachedFrame = max(self.maxCachedFrame, seq)

            except socket.timeout:
                continue
            except:
                break

    # ---------- PLAYER (PLAY FRAMES IN ORDER) ----------

    def runPlayer(self):
        FRAME_TIME = 1/25

        while not self.stopThreads:
            try:
                if self.playEvent.is_set():
                    break

                with self.cacheLock:
                    if not self.frameCache:
                        time.sleep(0.01)
                        continue

                    # ALWAYS take the smallest frame number
                    seq = min(self.frameCache.keys())
                    imageData = self.frameCache.pop(seq)

                self.frameNbr = seq
                self.updateMovie(imageData)

                if self.frameNbr >= self.totalFrames:
                    self.frameNbr = self.totalFrames

                time.sleep(FRAME_TIME)

            except Exception as e:
                print("Player error:", e)
                break

    # ---------- DISPLAY FRAME ----------

    def updateMovie(self, imageData):
        def update(img_bytes):
            try:
                stream = BytesIO(img_bytes)
                img = Image.open(stream)

                fw = self.videoFrame.winfo_width()
                fh = self.videoFrame.winfo_height()

                iw, ih = img.size
                ratio = min(fw / iw, fh / ih)
                img = img.resize((int(iw * ratio), int(ih * ratio)), Image.BILINEAR)

                photo = ImageTk.PhotoImage(img)
                self.label.configure(image=photo)
                self.label.image = photo
            except:
                pass

        self.master.after(0, update, imageData)

    # ---------- RTSP ----------

    def connectToServer(self):
        self.rtspSocket = socket.socket()
        self.rtspSocket.connect((self.serverAddr, self.serverPort))

    def sendRtspRequest(self, requestCode, seekFrame=None):
        self.rtspSeq += 1

        if requestCode == self.SETUP:
            threading.Thread(target=self.recvRtspReply, daemon=True).start()
            msg = \
                f"SETUP {self.fileName} RTSP/1.0\n" \
                f"Cseq: {self.rtspSeq}\n" \
                f"Transport: RTP/UDP; client_port: {self.rtpPort}"

        elif requestCode == self.PLAY:
            msg = \
                f"PLAY {self.fileName} RTSP/1.0\n" \
                f"Cseq: {self.rtspSeq}\n" \
                f"Session: {self.sessionId}"

            if seekFrame is not None:
                msg += f"\nRange: frame={seekFrame}"

        elif requestCode == self.PAUSE:
            msg = \
                f"PAUSE {self.fileName} RTSP/1.0\n" \
                f"Cseq: {self.rtspSeq}\n" \
                f"Session: {self.sessionId}"

        elif requestCode == self.TEARDOWN:
            msg = \
                f"TEARDOWN {self.fileName} RTSP/1.0\n" \
                f"Cseq: {self.rtspSeq}\n" \
                f"Session: {self.sessionId}"

        else:
            return

        self.requestSent = requestCode
        self.rtspSocket.send(msg.encode())
        print("\n>>> RTSP SENT >>>\n" + msg)

    def recvRtspReply(self):
        while True:
            try:
                data = self.rtspSocket.recv(1024)
                if data:
                    self.parseRtspReply(data.decode())
                if self.requestSent == self.TEARDOWN:
                    return
            except:
                break

    def parseRtspReply(self, data):
        lines = data.split('\n')
        code = int(lines[0].split(' ')[1])
        seq = int(lines[1].split(' ')[1])

        if seq != self.rtspSeq:
            return

        session = int(lines[2].split(' ')[1])
        if self.sessionId == 0:
            self.sessionId = session

        if code == 200:
            for line in lines[3:]:
                if line.startswith("Frames:"):
                    self.totalFrames = int(line.split(":")[1].strip())
                    print("[CLIENT] Total frames:", self.totalFrames)

            if self.requestSent == self.SETUP:
                self.state = self.READY
                self.openRtpPort()
            elif self.requestSent == self.PLAY:
                self.state = self.PLAYING
            elif self.requestSent == self.PAUSE:
                self.state = self.READY
            elif self.requestSent == self.TEARDOWN:
                self.state = self.INIT

    def openRtpPort(self):
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtpSocket.bind(("", self.rtpPort))
        self.rtpSocket.settimeout(0.5)

    def handler(self):
        self.pauseMovie()
        if tkinter.messagebox.askokcancel("Quit?", "Quit the player?"):
            self.exitClient()
        else:
            self.playMovie()
