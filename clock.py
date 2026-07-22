import time, random
from scanwheel import ScanWheel
from framing import Framing
import micropython, machine, framebuf

tzoffset = 0

def set_time():
    try:
        import network, ntptime

        config = ScanWheel.read_config()
        
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect(config['ssid'], config['wifipw'])

        connection_timeout = 10
        while connection_timeout > 0:
            if wlan.status() >= 3:
                break
            
            connection_timeout -= 1
            print('connecting...')
            time.sleep(1)

        if wlan.status() == 3:
            print('connected')
            for _ in range(10):
                try:
                    ntptime.settime()
                except:
                    pass
            
            global tzoffset
            tzoffset = round(float(config.get('tzoffset', '0')) * 60 * 60)
            print("time:", time.localtime(time.time() + tzoffset))
        
    finally:
        try:
            wlan.disconnect()
        except:
            pass

        try:
            wlan.active(False)
        except:
            pass

def clock():
    sw = ScanWheel(linewidth=512, framerate=20)
    fm = Framing(sw)
    
    sw.stand_by()
    
    set_time()

    rtc = machine.RTC()
    
    try:
        
        NUM_W = 256
        NUM_H = 20
        GLYPH_BYTES = NUM_W // 8 * NUM_H
        
        
        numbers_memory = bytearray(GLYPH_BYTES * 10)
        with open('numbers.raw', 'rb') as f:
            f.readinto(numbers_memory)
            
        mv = memoryview(numbers_memory)
        numbers = [framebuf.FrameBuffer(mv[(9-i) * GLYPH_BYTES : (10-i) * GLYPH_BYTES], NUM_W, NUM_H, framebuf.MONO_HLSB) for i in range(10)]
        
        def number(n):
            return numbers[n % 10]
        
        #pal_lum = framebuf.FrameBuffer(bytearray([0x40]), 2, 1, framebuf.MONO_HLSB)
        pal_rgb = framebuf.FrameBuffer(bytearray([0x07]), 2, 1, framebuf.GS4_HMSB)

        sw.align()
        sw.start(leds_state=0b00000111)
        
        seconds = -1
        
        while True:
            now = time.localtime(time.time() + tzoffset) # (year, month, day, hours, minutes, seconds, subseconds)

            if now[5] == seconds:
                continue

            seconds = now[5]

            for w in range(5):
                fm.windows[Framing.WINDOW_0 + w].fill(0)

            fm.windows[Framing.WINDOW_0].blit(number(now[3] // 10), 256, 0)
            fm.windows[Framing.WINDOW_1].blit(number(now[3]  % 10),  64, 0)
            fm.windows[Framing.WINDOW_2].blit(number(now[4] // 10), 192, 0, 0, pal_rgb)
            fm.windows[Framing.WINDOW_3].blit(number(now[4]  % 10),   0, 0)

            fm.windows[Framing.WINDOW_4].blit(number(now[5] // 10),   0, 0)
            fm.windows[Framing.WINDOW_4].blit(number(now[5]  % 10), 256, 0)
            
            for w in range(5):
                fm.windows[Framing.WINDOW_0 + w].rect(0, 0, sw.frame_w, sw.frame_h, 7)
            
            fm.present()
            
    finally:
        sw.stop()
        
if __name__ == "__main__":
    clock()
        
