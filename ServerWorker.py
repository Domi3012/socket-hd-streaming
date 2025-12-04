from random import randint
import sys, traceback, threading, socket, time

from VideoStream import VideoStream
from RtpPacket import RtpPacket


class ServerWorker:
    SETUP = 'SETUP'
    PLAY = 'PLAY'
    PAUSE = 'PAUSE'
    TEARDOWN = 'TEARDOWN'

    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    OK_200 = 0
    FILE_NOT_FOUND_404 = 1
    CON_ERR_500 = 2

    clientInfo = {}

    def __init__(self, clientInfo):
        self.clientInfo = clientInfo

    def run(self):
        threading.Thread(target=self.recvRtspRequest).start()

    def recvRtspRequest(self):
        connSocket = self.clientInfo['rtspSocket'][0]
        while True:
            data = connSocket.recv(4096)
            if data:
                print("\n===== RTSP REQUEST =====")
                print(data.decode())
                print("========================\n")
                self.processRtspRequest(data.decode())

    # --------------------------------------------------------------------
    # PROCESS RTSP REQUEST
    # --------------------------------------------------------------------
    def processRtspRequest(self, data):
        request = data.split('\n')

        # Example: PLAY movie.mjpeg RTSP/1.0
        line1 = request[0].split(' ')
        requestType = line1[0]
        filename = line1[1]

        # CSeq
        seq = request[1].split(' ')[1]

        # ===================== SETUP =====================
        if requestType == self.SETUP:
            if self.state == self.INIT:
                print("[SERVER] SETUP")

                try:
                    self.clientInfo['videoStream'] = VideoStream(filename)
                except IOError:
                    self.replyRtsp(self.FILE_NOT_FOUND_404, seq)
                    return

                self.clientInfo['session'] = randint(100000, 999999)
                self.clientInfo['rtpPort'] = int(request[2].split(' ')[3])
                self.state = self.READY

                self.replyRtsp(self.OK_200, seq)

        # ===================== PLAY =====================
        elif requestType == self.PLAY and self.state == self.READY:
            print("[SERVER] PLAY")

            # --- SEEK RANGE: frame=X ---
            seekFrame = None
            for line in request:
                if "Range:" in line and "frame=" in line:
                    try:
                        seekFrame = int(line.split("frame=")[1].strip())
                    except:
                        pass

            if seekFrame is not None:
                print(f"[SERVER] SEEK TO FRAME {seekFrame}")
                self.seekToFrame(seekFrame)

            # CREATE RTP SOCKET
            self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Increase send buffer for HD video (default is ~200KB, increase to 2MB)
            try:
                self.clientInfo["rtpSocket"].setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2 * 1024 * 1024)
                print("[SERVER] RTP send buffer set to 2MB")
            except:
                print("[SERVER] Warning: Could not increase send buffer")

            # SEND REPLY
            self.replyRtsp(self.OK_200, seq)

            # START STREAM THREAD
            self.clientInfo['event'] = threading.Event()
            self.clientInfo['worker'] = threading.Thread(target=self.sendRtp)
            self.clientInfo['worker'].start()

            self.state = self.PLAYING

        # ===================== PAUSE =====================
        elif requestType == self.PAUSE and self.state == self.PLAYING:
            print("[SERVER] PAUSE")
            self.state = self.READY
            self.clientInfo['event'].set()
            self.replyRtsp(self.OK_200, seq)

        # ===================== TEARDOWN =====================
        elif requestType == self.TEARDOWN:
            print("[SERVER] TEARDOWN")
            self.clientInfo['event'].set()
            self.replyRtsp(self.OK_200, seq)

            try:
                self.clientInfo['rtpSocket'].close()
            except:
                pass

            try:
                self.clientInfo['videoStream'].close()
            except:
                pass

    # --------------------------------------------------------------------
    # SEEK IMPLEMENTATION
    # --------------------------------------------------------------------
    def seekToFrame(self, n):
        """Seek đến đúng frame n bằng API của VideoStream."""
        video = self.clientInfo['videoStream']
        video.seekFrame(n)
        print(f"[SERVER] SEEK COMPLETE → AT FRAME {video.frameNbr() + 1}")

    # --------------------------------------------------------------------
    # RTP SEND LOOP
    # --------------------------------------------------------------------
    def sendRtp(self):
        video = self.clientInfo['videoStream']
        rtpSocket = self.clientInfo["rtpSocket"]
        
        # FPS control: 25 FPS = 0.04s per frame
        FRAME_INTERVAL = 0.04
        last_send_time = time.time()

        while True:
            if self.clientInfo['event'].is_set():
                return

            frame = video.nextFrame()
            if frame is None:
                print("[SERVER] END OF VIDEO")
                return

            frameNbr = video.frameNbr()
            
            # CHECK FRAME SIZE
            frame_size = len(frame)
            if frameNbr <= 10:
                print(f"[SERVER] Frame {frameNbr}: {frame_size} bytes ({frame_size/1024:.1f} KB)")
            
            if frame_size > 60000:
                print(f"[SERVER] WARNING: Frame {frameNbr} is {frame_size} bytes - TOO LARGE for single UDP packet!")
            
            packet = self.makeRtp(frame, frameNbr)

            try:
                addr = self.clientInfo['rtspSocket'][1][0]
                port = self.clientInfo['rtpPort']
                rtpSocket.sendto(packet, (addr, port))
                
                # Logging for debug
                if frameNbr <= 10 or frameNbr % 100 == 0:
                    print(f"[SERVER] Sent frame {frameNbr}")
                
            except Exception as e:
                print(f"[SERVER] RTP SEND ERROR at frame {frameNbr}: {e}")
                traceback.print_exc()
                return

            # Frame rate control - important for HD video
            current_time = time.time()
            elapsed = current_time - last_send_time
            sleep_time = FRAME_INTERVAL - elapsed
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            last_send_time = time.time()

    # --------------------------------------------------------------------
    # MAKE RTP PACKET
    # --------------------------------------------------------------------
    def makeRtp(self, payload, frameNbr):
        version = 2
        padding = 0
        extension = 0
        cc = 0
        marker = 0
        pt = 26
        seqnum = frameNbr
        ssrc = 0

        rtpPacket = RtpPacket()
        rtpPacket.encode(
            version,
            padding,
            extension,
            cc,
            seqnum,
            marker,
            pt,
            ssrc,
            payload
        )
        return rtpPacket.getPacket()
    
    # --------------------------------------------------------------------
    # REPLY RTSP - FIXED VERSION
    # --------------------------------------------------------------------
    def replyRtsp(self, code, seq):
        """Gửi RTSP response về cho client"""
        
        # Xác định status message
        if code == self.OK_200:
            reply = 'RTSP/1.0 200 OK\n'
        elif code == self.FILE_NOT_FOUND_404:
            reply = 'RTSP/1.0 404 NOT FOUND\n'
        elif code == self.CON_ERR_500:
            reply = 'RTSP/1.0 500 CONNECTION ERROR\n'
        
        # Thêm CSeq
        reply += f'CSeq: {seq}\n'
        
        # Thêm Session nếu đã được khởi tạo
        if 'session' in self.clientInfo:
            reply += f'Session: {self.clientInfo["session"]}\n'
        
        # ===== QUAN TRỌNG: Gửi tổng số frame =====
        if 'videoStream' in self.clientInfo:
            totalFrames = self.clientInfo['videoStream'].getTotalFrames()
            reply += f'Frames: {totalFrames}\n'
        
        # Kết thúc header
        reply += '\n'
        
        # Gửi response
        connSocket = self.clientInfo['rtspSocket'][0]
        try:
            connSocket.send(reply.encode())
            print("\n===== RTSP RESPONSE =====")
            print(reply)
            print("=========================\n")
        except:
            print("[SERVER] ERROR: Failed to send RTSP response")
            traceback.print_exc()