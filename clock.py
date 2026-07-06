import time, random
from scanwheel import ScanWheel
import micropython, machine, framebuf
            
if __name__ == "__main__":
    sw = ScanWheel(linewidth=512, framerate=20, windows=True)

    rtc = machine.RTC()
    rtc.datetime((2026, 7, 6, 0, 11, 23, 0, 0))
    
    try:
        
        NUM_W = 256
        NUM_H = 20
        GLYPH_BYTES = NUM_W // 8 * NUM_H
        
        
        numbers_memory = bytearray(GLYPH_BYTES * 10)
        with open('numbers.raw', 'rb') as f:
            f.readinto(numbers_memory)
            
        mv = memoryview(numbers_memory)
        numbers = [framebuf.FrameBuffer(mv[(9-i) * GLYPH_BYTES : (10-i) * GLYPH_BYTES], NUM_W, NUM_H, framebuf.MONO_HLSB) for i in range(10)]
        
        pal_lum = None # framebuf.FrameBuffer(bytearray([0x40]), 2, 1, framebuf.MONO_HLSB)
        pal_rgb = framebuf.FrameBuffer(bytearray([0x07]), 2, 1, framebuf.GS4_HMSB)
        palettes = [pal_lum, pal_lum, pal_rgb, pal_lum, pal_lum]

        sw.align()
        sw.start(leds_state=0b00000111)
        
        seconds = -1
        
        while True:
            now = rtc.datetime() # (year, month, day, weekday, hours, minutes, seconds, subseconds)
            if now[6] == seconds:
                continue

            seconds = now[6]
            
            for w in range(5):
                window = sw.windows[ScanWheel.WINDOW_0 + w]
                
                window.fill(0)
                
                if w == 0:
                    n = now[4] // 10
                elif w == 1:
                    n = now[4] % 10
                elif w == 2:
                    n = now[5] // 10
                elif w == 3:
                    n = now[5] % 10
                else:
                    n = now[6] % 10
                    
                if n < 10:
                    window.blit(numbers[n], 128, 0, 0, palettes[w])
                    
                window.rect(0, 0, sw.frame_w, sw.frame_h, 7)
            
            sw.windows_present()
            
    finally:
        sw.stop()
        
        

