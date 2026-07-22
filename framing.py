import array, time, math
import micropython
import machine, rp2, uctypes
import framebuf
from scanwheel import ScanWheel

@micropython.asm_thumb
def _ior_bits_to_bytes_(r0, r1, r2, r3): # dst, src, len, byte
    lsr(r2, r2, 3)
    label(LOOP)
    
    ldrb(r4, [r1, 0])
    mov(r5, 128)
    label(BITS)
    
    tst(r4, r5)
    beq(NOBIT)
    
    ldrb(r6, [r0, 0])
    orr(r6, r3)
    strb(r6, [r0, 0])
    
    label(NOBIT)
    add(r0, r0, 1)
    lsr(r5, r5, 1)
    bne(BITS)

    add(r1, r1, 1)
    sub(r2, r2, 1)
    bgt(LOOP)


class Framing:
    
    LUM_LEDS = const(4)
    RGB_LEDS = const(1)
    
    WINDOW_OFFSETS = [-2, -1, 0, 1, 2]
    WINDOW_PLANES = [0x40, 0x20, 0x07, 0x10, 0x08]
    
    WINDOW_0 = const(0)
    WINDOW_1 = const(1)
    WINDOW_2 = const(2)
    WINDOW_3 = const(3)
    WINDOW_4 = const(4)
    WINDOW_RGB = const(WINDOW_2)
    
    def __init__(self, scanwheel):
        self.scanwheel = scanwheel
        
        w, h = self.scanwheel.frame_w, self.scanwheel.frame_h
        lum_bytes_w = (w + 7) // 8
        rgb_bytes_w = (w + 1) // 2
        
        lum_bytes = lum_bytes_w * h
        rgb_bytes = rgb_bytes_w * h
        
        self.window_memory = [
            bytearray(lum_bytes),
            bytearray(lum_bytes),
            bytearray(rgb_bytes),
            bytearray(lum_bytes),
            bytearray(lum_bytes),
        ]
        
        self.windows = [
            framebuf.FrameBuffer(self.window_memory[0], w, h, framebuf.MONO_HLSB),
            framebuf.FrameBuffer(self.window_memory[1], w, h, framebuf.MONO_HLSB),
            framebuf.FrameBuffer(self.window_memory[2], w, h, framebuf.GS4_HMSB),
            framebuf.FrameBuffer(self.window_memory[3], w, h, framebuf.MONO_HLSB),
            framebuf.FrameBuffer(self.window_memory[4], w, h, framebuf.MONO_HLSB),
        ]
        
            
    def present(self):
        if len(self.windows) == 0:
            return
        
        self.scanwheel.frame_buffer.blit(self.windows[Framing.WINDOW_RGB], 0, 0)

        dst = uctypes.addressof(self.scanwheel.frame_memory)
        fs = self.scanwheel.frame_size
        fw = self.scanwheel.frame_w
        fh = self.scanwheel.frame_h
        
        for w in range(len(Framing.WINDOW_OFFSETS)):
            if w != Framing.WINDOW_RGB:
                src = uctypes.addressof(self.window_memory[w])
                off = ((Framing.WINDOW_OFFSETS[w]) % fh) * fw
                
                if off < fs:
                    _ior_bits_to_bytes_(dst + off, src, fs - off, Framing.WINDOW_PLANES[w])
                if off > 0:
                    _ior_bits_to_bytes_(dst, src + (fs - off) // 8, off, Framing.WINDOW_PLANES[w])
                

def main():
    sw = ScanWheel(linewidth=2048, framerate=15)
    fm = Framing(sw)
    
    try:
        sw.align()
        sw.start(leds_state=0b00000111)
        
        while True:
            for i in range(5):
                w = fm.windows[Framing.WINDOW_0 + i]
                w.rect(0, 0, sw.frame_w, sw.frame_h, 7)
                w.ellipse(sw.frame_w // 2, sw.frame_h // 2, sw.frame_w * 3 // 9, sw.frame_h * 3 // 8, 7, True)
            
            fm.present()
            
    finally:
        sw.stop()



if __name__ == "__main__":
    main()
