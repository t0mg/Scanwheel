import array, time, math
import machine, rp2, uctypes, sys, gc

def max_factor(value):
    return value & -value

def bit_length(value):
    return math.frexp(value)[1] - 1

def lerp(a, b, t):
    return a + (b - a) * t

def bytearray_aligned(size, alignment):
    buffer = bytearray(size + alignment - 1)
    aligned_addr = (uctypes.addressof(buffer) + alignment) & ~(alignment - 1)
    return uctypes.bytearray_at(aligned_addr, size)


def pio_assemble(pclk):
    assert(pclk >= 2)
    
    @rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW, out_init=(rp2.PIO.OUT_LOW,)*8, autopull=True, pull_thresh=8)
    def pio_program():
        out(pins, 8)                        # load the LED states for the spinup
        
        label("spin_up")
        out(y, 32)                          # load the loop counter
        jmp(not_y, "at_speed")              # if it's zero, proceed to scanning
        
        mov(x, y).side(1)       [pclk-2]    # step pin high
        label("spin_hi")
        nop()                   [pclk-2]
        jmp(x_dec, "spin_hi")
        
        mov(x, y).side(0)       [pclk-1]    # step pin low
        label("spin_lo")
        nop()                   [pclk-2]
        jmp(x_dec, "spin_lo")
        
        jmp("spin_up")
        
        label("at_speed")
        out(y, 32)                          # load the line loop counter
        
        wrap_target()                       # main loop
        
        out(pins, 8).side(1)    [pclk-2]    # pixel output...
        mov(x, y)                           # ... +1 clock to load the loop counter
        label("step_hi")                    # output half a line with the step pin high:
        out(pins, 8).side(1)    [pclk-2]    #   pixel output...
        jmp(x_dec, "step_hi")               #   ... +1 clock to loop
        
        out(pins, 8).side(0)    [pclk-2]    # same again, with the step pin low
        mov(x, y)
        label("step_lo")
        out(pins, 8).side(0)    [pclk-2]
        jmp(x_dec, "step_lo")
        
        wrap()
        
    return pio_program



class ScanWheel:

    def __init__(
        self,
        leds : int = 16,
        step : int = 0,
        enable : int = 2,
        reset : int = 3,
        scanlines : int = 20,
        linewidth : int = 1024,
        framerate = 15
    ):
        self.pin_leds = leds
        self.pin_step = step
        self.pin_enable = enable
        self.pin_reset = reset

        chunk_count, linewidth = ScanWheel.calculate_chunk_count(linewidth, scanlines)
        chunk_size = (linewidth * scanlines) // chunk_count
        
        self.frame_w = int(linewidth)
        self.frame_h = int(scanlines)
        self.frame_rate = framerate
        
        self.frame_size = int(self.frame_w * self.frame_h)

        self.framebuffer = bytearray_aligned(self.frame_size, chunk_size)
        
        self.sm = self.state_machine()
        self.dma = ScanWheel.dma_chain(self.framebuffer, chunk_count, chunk_size, self.sm)
        
        self.valign = 0
        self.halign = 0
        
        self.read_config()


    def start(self, leds_state=0):
        
        # turn on the driver
        machine.Pin(self.pin_enable, machine.Pin.OUT).value(0)
        machine.Pin(self.pin_reset, machine.Pin.OUT).value(1)
        time.sleep_us(1000)
        
        # build the preamble list
        preamble = array.array('I')
        
        # set the state of the LEDs during spin up
        preamble.append(int(leds_state) << 24)

        # set a series of decreasing scanline lengths to ramp up the motor
        start_w = self.frame_w * self.frame_rate / 2

        valign = self.valign
        if self.halign < 0:
            valign += 1
        halign = round(self.halign * self.frame_w) % self.frame_w
        
        a = -0.4
        b = 0.8
        f = 1
        fw = self.frame_rate * self.frame_w * b
        while True:
            freq = pow(f, a)
            w = fw * freq
            if w < self.frame_w:
                break
            
            preamble.append(int(w) // 2 - 2)
            valign += 1
            
            f += b

            
        for _ in range((self.frame_h * 2) - (valign % self.frame_h)):
            preamble.append(int(self.frame_w) // 2 - 2)
            valign += 1
        
        # transition to normal operation
        preamble.append(int(0))
        
        # set the actual line length
        preamble.append(int(self.frame_w) // 2 - 2)
        
        # pad with dummy pixels to set the horizontal alignment
        for _ in range(halign):
            preamble.append(int(0))
            
        print(len(preamble))
            
        # now send that to the state machine
        self.sm.put(preamble)

        # and hand over to the dma chain
        self.dma[0].active(1)
        
    def align(self):
        machine.Pin(self.pin_enable, machine.Pin.OUT).value(0)
        time.sleep_us(1000)
        machine.Pin(self.pin_reset, machine.Pin.OUT).value(0)
        time.sleep_us(1000)
        machine.Pin(self.pin_reset, machine.Pin.OUT).value(1)
        time.sleep_us(1000)

        
        green = machine.Pin(self.pin_leds + 1, machine.Pin.OUT)
        green.value(1)
        time.sleep(4)
        
        for _ in range(7):
            green.value(1 - green.value())
            time.sleep(0.25)

        green.init(mode=machine.Pin.ALT, alt=machine.Pin.ALT_PIO0)



    def stop(self):
        # turn off the driver
        machine.Pin(self.pin_enable, machine.Pin.OUT).value(1)
        
        # and the LEDs
        for p in range(8):
            machine.Pin(self.pin_leds + p, machine.Pin.OUT).value(0)


    def read_config(self):
        try:
            with open('scanwheel.cfg') as f:
                for line in f:
                    line = line.split('#',1)[0].strip()
                    if line and '=' in line:
                        k,v = line.split('=',1)
                        k = k.strip()
                        
                        if   k == 'halign':
                            self.halign = int(v)
                        elif k == 'valign':
                            self.valign = int(v)

        except:
            pass

    @staticmethod
    def calculate_chunk_count(frame_w, frame_h):
        DMA_CHANNEL_COUNT = 12
        
        frame_size = frame_w * frame_h
        chunk_count = frame_size // max_factor(frame_size)
        
        if chunk_count >= DMA_CHANNEL_COUNT:
            new_w = 0
            for c in range(2, DMA_CHANNEL_COUNT + 1):
                for b in range(2):
                    s = 1 << max(0, bit_length((frame_size - 1) // c) + b)
                    w = s * c / frame_h
                    if w % 1 == 0:
                        if abs(w - frame_w) < abs(new_w - frame_w):
                            new_w = w

            frame_w = new_w
            
            frame_size = frame_w * frame_h
            chunk_count = frame_size // max_factor(frame_size)
            
            print(f'frame dimensions are unachievable - using {frame_w}x{frame_h} instead')
        
        while chunk_count * 2 <= DMA_CHANNEL_COUNT:
            chunk_count *= 2
        
        return chunk_count, frame_w

    @staticmethod
    def framerate_params(target_fps, frame_size):
        sys_clock = machine.freq() * 256
        fps = 1000
        pdiv = 128
        sdiv = 3

        for p in range(2, 9):
            d = round(sys_clock / (target_fps * frame_size * p))

            f = (sys_clock // d) / (p * frame_size)
            
            if abs(f - target_fps) < abs(fps - target_fps):
                fps = f
                pdiv = p
                sdiv = d
                
        return sys_clock // sdiv, pdiv

    def state_machine(self):
        smfreq, pclk = ScanWheel.framerate_params(self.frame_rate, self.frame_size)
        print(f'sm freq {(smfreq)}, {pclk} clocks/pixel; {(smfreq) / (self.frame_size * pclk)} fps  (target: {self.frame_rate})')

        pio_refresh = pio_assemble(pclk)
        sm = rp2.StateMachine(0, pio_refresh, freq=smfreq, out_base=machine.Pin(self.pin_leds), sideset_base=machine.Pin(self.pin_step))
        sm.active(1)
        
        return sm
    
    @staticmethod
    def dma_chain(frame_buffer, chunk_count, chunk_size, sm):
        print(f'creating dma chain with {chunk_count} chunks of {chunk_size} bytes')
        dma = [rp2.DMA() for _ in range(chunk_count)]
            
        chunk_bits = bit_length(chunk_size)
        for d in range(chunk_count):
            dma[d].config(
                read = uctypes.addressof(frame_buffer) + d * chunk_size,
                write = sm,
                count = chunk_size,
                ctrl = dma[d].pack_ctrl(size=0, inc_read=True, inc_write=False, treq_sel=0, irq_quiet=True, chain_to=dma[(d + 1) % chunk_count].channel, ring_size=chunk_bits),
                trigger = False
            )
            
        return dma




if __name__ == "__main__":
    sw = ScanWheel(linewidth=2048, framerate=24)
    
    try:
        sw.align()
            
        sw.start(leds_state=0b00000111)
        
        with open('tcf2048.raw', 'rb') as f:
            f.readinto(sw.framebuffer)

        while True:
            time.sleep(0)
            

        
    finally:
        sw.stop()
        
        

