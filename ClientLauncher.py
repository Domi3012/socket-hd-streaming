import sys
from tkinter import Tk

# Import the updated Client class with progress bar
from Client import Client

if __name__ == "__main__":
	try:
		serverAddr = sys.argv[1]
		serverPort = sys.argv[2]
		rtpPort = sys.argv[3]
		fileName = sys.argv[4]	
	except:
		print("[Usage: ClientLauncher.py Server_name Server_port RTP_port Video_file]\n")
		print("Example: python ClientLauncher.py localhost 5000 25000 movie.Mjpeg")
		sys.exit()
	
	root = Tk()
	root.title("RTSP Video Streaming Client")
	root.geometry("800x600")
	root.configure(bg='#f0f0f0')
	
	# Create Client instance
	app = Client(root, serverAddr, serverPort, rtpPort, fileName)
	
	# Start GUI main loop
	root.mainloop()