import time, random
from scanwheel import ScanWheel
import framebuf
            
if __name__ == "__main__":
    sw = ScanWheel(linewidth=512, framerate=20)
    
    try:    
        
        NUM_W = 256
        NUM_H = 20
        GLYPH_BYTES = NUM_W // 8 * NUM_H
        
        SCREEN_0 = 0b01000000
        SCREEN_1 = 0b00100000
        SCREEN_2 = 0b00000111
        SCREEN_3 = 0b00010000
        SCREEN_4 = 0b00001000
        
        numbers_memory = bytearray(GLYPH_BYTES * 10)
        with open('numbers.raw', 'rb') as f:
            f.readinto(numbers_memory)
            
        mv = memoryview(numbers_memory)
        numbers = [framebuf.FrameBuffer(mv[(9-i) * GLYPH_BYTES : (10-i) * GLYPH_BYTES], NUM_W, NUM_H, framebuf.MONO_HLSB) for i in range(10)]
            
        sw.align()
        sw.start(leds_state=0b00000111)
        
        n = 0
        while True:
            sw.framebuffer.blit(numbers[n], 128, 0)
            
            sw.framebuffer.rect(0, 0, sw.frame_w, sw.frame_h, SCREEN_0|SCREEN_1|SCREEN_2|SCREEN_3|SCREEN_4)            
            
            n = (n + 1) % 10
            time.sleep(1)
            
    finally:
        sw.stop()
        
        

