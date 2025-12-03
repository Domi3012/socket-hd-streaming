from tkinter import *
import tkinter.messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os
import queue
import time
from io import BytesIO

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT
    
    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3
    
    # Initiation..
    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)
        self.fileName = filename
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0
        self.connectToServer()
        self.frameNbr = 0
        
        # Cải thiện: Tăng kích thước buffer và thêm maxsize
        self.frameBuffer = queue.Queue(maxsize=30)
        
        # Cải thiện: Cache ảnh để tránh đọc/ghi file liên tục
        self.imageCache = {}
        self.lastDisplayTime = 0
        
        # Thêm: Biến theo dõi vị trí phát hiện tại
        self.totalFramesReceived = 0
        self.currentPlayingFrame = 0
        
    def createWidgets(self):
        """Build GUI."""
        # Create a label to display the movie
        self.label = Label(self.master, height=25)
        self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)
        
        # Create Setup button
        self.setup = Button(self.master, width=20, padx=3, pady=3)
        self.setup["text"] = "Setup"
        self.setup["command"] = self.setupMovie
        self.setup.grid(row=2, column=0, padx=2, pady=2)
        
        # Create Play button		
        self.start = Button(self.master, width=20, padx=3, pady=3)
        self.start["text"] = "Play"
        self.start["command"] = self.playMovie
        self.start.grid(row=2, column=1, padx=2, pady=2)
        
        # Create Pause button			
        self.pause = Button(self.master, width=20, padx=3, pady=3)
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=2, column=2, padx=2, pady=2)
        
        # Create Teardown button
        self.teardown = Button(self.master, width=20, padx=3, pady=3)
        self.teardown["text"] = "Teardown"
        self.teardown["command"] =  self.exitClient
        self.teardown.grid(row=2, column=3, padx=2, pady=2) 

        # Create a label to display the movie (larger for HD)
        self.label = Label(self.master, height=25)
        self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 
  
        # Create buffer progress bar 
        self.bufferCanvas = Canvas(self.master, height=8, bg='#f5f5f5', highlightthickness=0)
        self.bufferCanvas.grid(row=1, column=0, columnspan=4, sticky=W+E, padx=5, pady=2)
        self.bufferBar = self.bufferCanvas.create_rectangle(0, 0, 0, 8, fill="#747171", outline='')
        self.playbackBar = self.bufferCanvas.create_rectangle(0, 0, 0, 8, fill='#ff0000', outline='')  
        
    def setupMovie(self):
        """Setup button handler."""
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)
    
    def exitClient(self):
        """Teardown button handler."""
        self.sendRtspRequest(self.TEARDOWN)		
        self.master.destroy()
        try:
            os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)
        except:
            pass

    def pauseMovie(self):
        """Pause button handler."""
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.PAUSE)
    
    def playMovie(self):
        """Play button handler."""
        if self.state == self.READY:
            self.playEvent = threading.Event()
            self.playEvent.clear()
            
            # Khởi chạy threads
            threading.Thread(target=self.listenRtp, daemon=True).start()
            threading.Thread(target=self.runPlayer, daemon=True).start()
            threading.Thread(target=self.updateBufferBar, daemon=True).start()
            
            self.sendRtspRequest(self.PLAY)
    
    def listenRtp(self):		
        """Listen for RTP packets."""
        while True:
            try:
                data = self.rtpSocket.recv(65536)
                if data:
                    rtpPacket = RtpPacket()
                    rtpPacket.decode(data)
                    
                    currFrameNbr = rtpPacket.seqNum()
                    print(f"Received frame: {currFrameNbr}, Buffer size: {self.frameBuffer.qsize()}")
                                        
                    if currFrameNbr > self.frameNbr:
                        self.frameNbr = currFrameNbr
                        self.totalFramesReceived += 1  # Đếm tổng số frame nhận được
                        
                        # Lưu trực tiếp dữ liệu, nếu buffer đầy thì đợi
                        try:
                            self.frameBuffer.put(rtpPacket.getPayload(), timeout=0.1)
                        except queue.Full:
                            print("Buffer full, skipping frame")
                            pass
                            
            except socket.timeout:
                continue
            except:
                if self.playEvent.isSet(): 
                    break
                if self.teardownAcked == 1:
                    self.rtpSocket.close()
                    break
 
    def writeFrame(self, data):
        """Write the received frame to a temp image file. Return the image file."""
        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        file = open(cachename, "wb")
        file.write(data)
        file.close()
        
        return cachename

    def updateMovie(self, imageData):
        """Update the image from raw data (improved - no file I/O)."""
        try:
            # Cải thiện: Đọc trực tiếp từ memory thay vì file
            image = Image.open(BytesIO(imageData))
            photo = ImageTk.PhotoImage(image)
            
            self.label.configure(image=photo, height=photo.height()) 
            self.label.image = photo
        except Exception as e:
            print(f"Update movie error: {e}")
            pass
    def connectToServer(self):
        """Connect to the Server. Start a new RTSP/TCP session."""
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
        except:
            tkinter.messagebox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
    
    def sendRtspRequest(self, requestCode):
        """Send RTSP request to the server."""	
                
        # Setup request
        if requestCode == self.SETUP and self.state == self.INIT:
            threading.Thread(target=self.recvRtspReply, daemon=True).start()
            self.rtspSeq += 1
            
            request = f"SETUP {self.fileName} RTSP/1.0\nCseq: {self.rtspSeq}\nTransport: RTP/UDP; client_port: {self.rtpPort}"
            
            self.requestSent = self.SETUP
        
        # Play request
        elif requestCode == self.PLAY and self.state == self.READY:
            self.rtspSeq += 1
            
            request = f"PLAY {self.fileName} RTSP/1.0\nCseq: {self.rtspSeq}\nSession: {self.sessionId}"
        
            self.requestSent = self.PLAY
        
        # Pause request
        elif requestCode == self.PAUSE and self.state == self.PLAYING:
            self.rtspSeq += 1
            
            request = f"PAUSE {self.fileName} RTSP/1.0\nCseq: {self.rtspSeq}\nSession: {self.sessionId}"

            self.requestSent = self.PAUSE
            
        # Teardown request
        elif requestCode == self.TEARDOWN and not self.state == self.INIT:
            self.rtspSeq += 1
            
            request = f"TEARDOWN {self.fileName} RTSP/1.0\nCseq: {self.rtspSeq}\nSession: {self.sessionId}"
            
            self.requestSent = self.TEARDOWN
        else:
            return

        self.rtspSocket.send(request.encode('utf-8'))
        print('\nData sent:\n' + request)
    
    def recvRtspReply(self):
        """Receive RTSP reply from the server."""
        while True:
            reply = self.rtspSocket.recv(1024)
            
            if reply: 
                self.parseRtspReply(reply.decode("utf-8"))
            
            if self.requestSent == self.TEARDOWN:
                self.rtspSocket.shutdown(socket.SHUT_RDWR)
                self.rtspSocket.close()
                break
    
    def parseRtspReply(self, data):
        """Parse the RTSP reply from the server."""
        lines = data.split('\n')
        seqNum = int(lines[1].split(' ')[1])
        
        if seqNum == self.rtspSeq:
            session = int(lines[2].split(' ')[1])
            if self.sessionId == 0:
                self.sessionId = session
            
            if self.sessionId == session:
                if int(lines[0].split(' ')[1]) == 200: 
                    if self.requestSent == self.SETUP:
                        self.state = self.READY
                        self.openRtpPort() 

                    elif self.requestSent == self.PLAY:
                        self.state = self.PLAYING

                    elif self.requestSent == self.PAUSE:
                        self.state = self.READY
                        self.playEvent.set()
                        
                    elif self.requestSent == self.TEARDOWN:
                        self.state = self.INIT
                        self.teardownAcked = 1 
    
    def openRtpPort(self):
        """Open RTP socket binded to a specified port."""
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Cải thiện: Tối ưu timeout
        self.rtpSocket.settimeout(0.5)
        
        # Tăng receive buffer
        self.rtpSocket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4194304)  # 4MB buffer

        try:
            self.rtpSocket.bind(("", self.rtpPort))
        except:
            tkinter.messagebox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

    def handler(self):
        """Handler on explicitly closing the GUI window."""
        self.pauseMovie()
        if tkinter.messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else:
            self.playMovie()
   
    def updateBufferBar(self):
        """Update buffer progress bar continuously."""
        while True:
            try:
                if self.playEvent.isSet():
                    break
                
                # Lấy chiều rộng canvas
                canvas_width = self.bufferCanvas.winfo_width()
                if canvas_width > 1:
                    # Tính vị trí thanh buffer (trắng) - frames đã nhận
                    if self.totalFramesReceived > 0:
                        buffer_width = (canvas_width * self.totalFramesReceived) / max(self.totalFramesReceived, 100)
                    else:
                        buffer_width = 0
                    
                    # Tính vị trí thanh playback (đỏ) - frame đang xem
                    if self.totalFramesReceived > 0:
                        playback_width = (canvas_width * self.currentPlayingFrame) / max(self.totalFramesReceived, 100)
                    else:
                        playback_width = 0
                    
                    # Cập nhật thanh buffer (trắng - phía sau)
                    self.bufferCanvas.coords(self.bufferBar, 0, 0, buffer_width, 8)
                    
                    # Cập nhật thanh playback (đỏ - phía trước)
                    self.bufferCanvas.coords(self.playbackBar, 0, 0, playback_width, 8)
                
                time.sleep(0.1)  # Cập nhật mỗi 100ms
                
            except Exception as e:
                print(f"Buffer bar update error: {e}")
                break
            
    def runPlayer(self):
        """Display frames from buffer with proper frame rate control."""
        print("runPlayer thread started!")
        TARGET_FPS = 20
        FRAME_TIME = 1.0 / TARGET_FPS
        
        # Không cần chờ buffer, bắt đầu ngay khi có frame
        while True:
            try:
                if self.playEvent.isSet():
                    print("runPlayer stopped by playEvent")
                    break
                
                # Lấy frame ngay lập tức
                try:
                    imageData = self.frameBuffer.get(timeout=0.5)
                    self.updateMovie(imageData)
                    self.currentPlayingFrame += 1  # Cập nhật frame đang phát
                    print(f"✓ Displayed frame, buffer: {self.frameBuffer.qsize()}")
                    
                    # Ngủ để duy trì FPS
                    time.sleep(FRAME_TIME)
                    
                except queue.Empty:
                    print("Queue empty, waiting for frames...")
                    time.sleep(0.1)
                    continue
                
            except Exception as e:
                print(f"Player error: {e}")
                import traceback
                traceback.print_exc()
                break
    