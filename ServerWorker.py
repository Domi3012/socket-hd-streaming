from random import randint
import sys, traceback, threading, socket
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
            try:
                data = connSocket.recv(256)
                if data:
                    print("Data received:\n" + data.decode("utf-8"))
                    self.processRtspRequest(data.decode("utf-8"))
            except:
                break

    def processRtspRequest(self, data):
        request = data.split('\n')
        line1 = request[0].split(' ')
        requestType = line1[0]
        filename = line1[1]
        seq = request[1].split(' ')
        
        if requestType == self.SETUP:
            if self.state == self.INIT:
                print("processing SETUP\n")
                try:
                    self.clientInfo['videoStream'] = VideoStream(filename)
                    self.state = self.READY
                except IOError:
                    self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])
                
                self.clientInfo['session'] = randint(100000, 999999)
                self.replyRtsp(self.OK_200, seq[1])
                self.clientInfo['rtpPort'] = request[2].split(' ')[3]
        
        elif requestType == self.PLAY:
            if self.state == self.READY:
                print("processing PLAY\n")
                self.state = self.PLAYING
                
                # Xử lý tua
                for line in request:
                    if "Range:" in line:
                        try:
                            target = int(line.split('=')[-1])
                            self.clientInfo['videoStream'].gotoFrame(target)
                        except: pass

                self.clientInfo['rtpSocket'] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.replyRtsp(self.OK_200, seq[1])
                self.clientInfo['event'] = threading.Event()
                self.clientInfo['worker'] = threading.Thread(target=self.sendRtp)
                self.clientInfo['worker'].start()
        
        elif requestType == self.PAUSE:
            if self.state == self.PLAYING:
                print("processing PAUSE\n")
                self.state = self.READY
                self.clientInfo['event'].set()
                self.replyRtsp(self.OK_200, seq[1])
        
        elif requestType == self.TEARDOWN:
            print("processing TEARDOWN\n")
            self.clientInfo['event'].set()
            self.replyRtsp(self.OK_200, seq[1])
            self.clientInfo['rtpSocket'].close()
            
    def sendRtp(self):
        MAX_CHUNK = 20000
        while True:
            self.clientInfo['event'].wait(0.005) 
            if self.clientInfo['event'].isSet(): break 
            
            data = self.clientInfo['videoStream'].nextFrame()
            if data: 
                frameNumber = self.clientInfo['videoStream'].frameNbr()
                try:
                    address = self.clientInfo['rtspSocket'][1][0]
                    port = int(self.clientInfo['rtpPort'])
                    
                    if len(data) > MAX_CHUNK:
                        chunks = [data[i:i+MAX_CHUNK] for i in range(0, len(data), MAX_CHUNK)]
                        for i, chunk in enumerate(chunks):
                            marker = 1 if i == len(chunks)-1 else 0
                            self.clientInfo['rtpSocket'].sendto(self.makeRtp(chunk, frameNumber, marker),(address,port))
                    else:
                        self.clientInfo['rtpSocket'].sendto(self.makeRtp(data, frameNumber, 1),(address,port))
                except:
                    print("Connection Error")

    def makeRtp(self, payload, frameNbr, marker=0):
        version = 2
        padding = 0
        extension = 0
        cc = 0
        pt = 26
        seqnum = frameNbr
        ssrc = 0 
        rtpPacket = RtpPacket()
        rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload)
        return rtpPacket.getPacket()
        
    def replyRtsp(self, code, seq):
        if code == self.OK_200:
            reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session'])
            
            # --- LOGIC MỚI: Gửi kèm tổng số frame cho Client ---
            if 'videoStream' in self.clientInfo:
                total_frames = self.clientInfo['videoStream'].getTotalFrames()
                reply += f"\nFrames: {total_frames}"
            # ---------------------------------------------------

            connSocket = self.clientInfo['rtspSocket'][0]
            connSocket.send(reply.encode())
        elif code == self.FILE_NOT_FOUND_404:
            print("404 NOT FOUND")
        elif code == self.CON_ERR_500:
            print("500 CONNECTION ERROR")