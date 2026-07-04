import time
from scanwheel import ScanWheel
            
if __name__ == "__main__":
    sw = ScanWheel(linewidth=512, framerate=20)
    
    try:    
        sw.align()
        
        sw.start(leds_state=0b00000111)

        while True:
            mv = memoryview(sw.framebuffer)
            with open('multirick.raw', 'rb') as f:
                while True:
                    read = f.readinto(mv[:sw.frame_size])
                    time.sleep_us(1000000//15)
                    if read < sw.frame_size:
                        f.seek(0, 0)
            
    finally:
        sw.stop()
        
        

