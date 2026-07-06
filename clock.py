import time, random
from scanwheel import ScanWheel
import framebuf
import micropython
            
if __name__ == "__main__":
    sw = ScanWheel(linewidth=512, framerate=20, windows=True)
    
    try:    
        
        NUM_W = 256
        NUM_H = 20
        GLYPH_BYTES = NUM_W // 8 * NUM_H
        
        
        numbers_memory = bytearray(GLYPH_BYTES * 10)
        with open('numbers.raw', 'rb') as f:
            f.readinto(numbers_memory)
            
        mv = memoryview(numbers_memory)
        numbers = [framebuf.FrameBuffer(mv[(9-i) * GLYPH_BYTES : (10-i) * GLYPH_BYTES], NUM_W, NUM_H, framebuf.MONO_HLSB) for i in range(10)]
            
        sw.align()
        sw.start(leds_state=0b00000111)
        
        n = 0
        while True:
            for w in range(5):
                window = sw.windows[ScanWheel.WINDOW_0 + w]
                window.fill(0)
                window.blit(numbers[(n+w)%10], 128, 0)
                window.rect(0, 0, sw.frame_w, sw.frame_h, 1)
            
            sw.windows_present()
                        
            n = (n + 1) % 10
            time.sleep(1)
            
    finally:
        sw.stop()
        
        

