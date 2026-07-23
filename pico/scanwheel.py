import array, time, math
import micropython
import machine, rp2, uctypes
import framebuf

def max_factor(value):
    return value & -value

def bit_length(value):
    return math.frexp(value)[1] - 1

def lerp(a, b, t):
    return a + (b - a) * t


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
    
    LUM_LEDS = const(4)
    RGB_LEDS = const(1)
    
    def __init__(
        self,
        leds : int = 16,
        step : int = 0,
        enable : int = 2,
        reset : int = 3,
        scanlines : int = 20,
        linewidth : int = 1024,
        framerate : float = 15
    ):
        self.pin_leds = leds
        self.pin_step = step
        self.pin_enable = enable
        self.pin_reset = reset

        chunk_count, linewidth = ScanWheel._calculate_chunk_count(linewidth, scanlines)
        chunk_size = (linewidth * scanlines) // chunk_count
        
        self.frame_w = int(linewidth)
        self.frame_h = int(scanlines)
        self.frame_rate = framerate
        
        self.frame_size = int(self.frame_w * self.frame_h)

        frame_aligned = self.frame_size + chunk_size - 1
        preamble_max = 4096
        scratch_max = max(preamble_max, (frame_aligned + 3) // 4)
        
        self.scratch_array = array.array('I', [0] * scratch_max)
        print(f'allocated {scratch_max * 4} bytes for buffers')
        
        self._create_framebuffer(chunk_size)
        
        self.sm = self._state_machine()
        self.dma = ScanWheel._dma_chain(self.frame_memory, chunk_count, chunk_size, self.sm)
        
        config = ScanWheel.read_config()
        self.hconst = config['hconst']
        self.halign = config['halign']
        self.valign = config['valign']
        
    def _generate_preamble(self, leds_state, ramp_a, ramp_b):
        try:
            preamble = 0
            
            # set the state of the LEDs during spin up
            self.scratch_array[preamble] = int(leds_state) << 24
            preamble += 1

            valign = -self.valign
            
            halign = round((self.hconst * self.frame_rate + self.halign) * self.frame_w)
            if halign < 0:
                valign += (-halign // self.frame_w) + 1
            halign = halign % self.frame_w

            f = 1
            fw = self.frame_rate * self.frame_w
            while True:
                freq =  ramp_b * pow(f, ramp_a)
                w = fw * freq
                if w < self.frame_w:
                    break
                
                self.scratch_array[preamble] = int(w) // 2 - 2
                preamble += 1
                valign += 1
                f += 1

            # stabilise at the target scanline length, and pad to vertical alignment
            for _ in range((self.frame_h * 2) - (valign % self.frame_h)):
                self.scratch_array[preamble] = int(self.frame_w // 2 - 2)
                preamble += 1
                
            #print(f'preamble {preamble} lines, {preamble // self.frame_h} frames / voff {preamble % self.frame_h}')
            
            # transition to normal operation
            self.scratch_array[preamble] = int(0)
            preamble += 1
            
            # set the actual line length
            self.scratch_array[preamble] = int(self.frame_w // 2 - 2)
            preamble += 1
            
            # pad with dummy pixels to set the horizontal alignment
            for _ in range(halign):
                self.scratch_array[preamble] = int(0)
                preamble += 1
        
        except IndexError:
            return -1
        
        return preamble
        


    def start(self, leds_state=0):
        
        # turn on the driver
        machine.Pin(self.pin_enable, machine.Pin.OUT).value(0)
        machine.Pin(self.pin_reset, machine.Pin.OUT).value(1)
        time.sleep_us(1000)
        
        # hand over the LEDs
        for p in range(8):
            machine.Pin(self.pin_leds + p, mode=machine.Pin.ALT, alt=machine.Pin.ALT_PIO0)

        # build the preamble list
        ramp_a = -0.25
        ramp_b = 0.3
        preamble = self._generate_preamble(leds_state, ramp_a, ramp_b)
    
        if preamble <= 0:
            print('preamble overruns scratch buffer')
            for _ in range(8):
                ramp_b *= 0.9
                preamble = self._generate_preamble(leds_state, ramp_a, ramp_b)
                if preamble > 0:
                    break
            if preamble <=0:
                sys.exit()
            
            
            
        # now send that to the state machine
        self.sm.put(self.scratch_array[:preamble])

        # and hand over to the dma chain
        self.dma[0].active(1)
        
        self.frame_buffer.fill(0)
        
    def stand_by(self):
        machine.Pin(self.pin_enable, machine.Pin.OUT).value(0)
        time.sleep_us(1000)
        machine.Pin(self.pin_reset, machine.Pin.OUT).value(0)
        time.sleep_us(1000)
        machine.Pin(self.pin_reset, machine.Pin.OUT).value(1)
        time.sleep_us(1000)

        for p in range(8):
            machine.Pin(self.pin_leds + p, machine.Pin.OUT).value(0)

        red = machine.Pin(self.pin_leds + 2, machine.Pin.OUT)
        red.value(1)

                
    def align(self):
        machine.Pin(self.pin_enable, machine.Pin.OUT).value(0)
        time.sleep_us(1000)
        machine.Pin(self.pin_reset, machine.Pin.OUT).value(0)
        time.sleep_us(1000)
        machine.Pin(self.pin_reset, machine.Pin.OUT).value(1)
        time.sleep_us(1000)

        for p in range(8):
            machine.Pin(self.pin_leds + p, machine.Pin.OUT).value(0)

        green = machine.Pin(self.pin_leds + 1, machine.Pin.OUT)
        green.value(1)
        time.sleep(4)
        
        for _ in range(7):
            green.value(1 - green.value())
            time.sleep(0.25)


    def stop(self):
        # turn off the stepper driver
        machine.Pin(self.pin_enable, machine.Pin.OUT).value(1)
        
        # stop the dma
        try:
            for dma in self.dma:
                dma.config(read=0, write=0, count=0, ctrl=dma.pack_ctrl(enable=False), trigger=False)
        except:
            pass
        
        # stop the pio
        try:
            self.sm.active(0)
        except:
            pass

        # turn off the LEDs
        for p in range(8):
            machine.Pin(self.pin_leds + p, machine.Pin.OUT).value(0)
    
    def _create_framebuffer(self, chunk_size):
        scratch_addr = uctypes.addressof(self.scratch_array)
        
        self.frame_memory = uctypes.bytearray_at(scratch_addr + ((chunk_size - (scratch_addr % chunk_size)) % chunk_size), self.frame_size)
        self.frame_buffer = framebuf.FrameBuffer(self.frame_memory, self.frame_w, self.frame_h, framebuf.GS8)

    @staticmethod
    def read_config():
        config = {
            'hconst': float(0.055),
            'halign': float(0.0),
            'valign': int(0),
        }
        try:
            with open('scanwheel.cfg') as f:
                for line in f:
                    line = line.split('#',1)[0].strip()
                    if line and '=' in line:
                        k,v = line.split('=',1)
                        k = k.strip()
                        v = v.strip()
                        try:
                            config[k] = type(config[k])(v)
                        except:
                            config[k] = v
        except:
            pass
        
        return config
    
    @staticmethod
    def write_config(config):
        with open('scanwheel.cfg', 'w') as f:
            for k, v in config.items():
                f.write(f'{k}={v}\n')


    @staticmethod
    def _calculate_chunk_count(frame_w, frame_h):
        DMA_CHANNEL_COUNT = const(12)
        
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
            chunk_count = max(2, frame_size // max_factor(frame_size))
            
            print(f'frame dimensions are unachievable - using {frame_w}x{frame_h} instead')
        
        return chunk_count, frame_w

    @staticmethod
    def _framerate_params(target_fps, frame_size):
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

    def _state_machine(self):
        smfreq, pclk = ScanWheel._framerate_params(self.frame_rate, self.frame_size)
        print(f'sm freq {(smfreq)}, {pclk} clocks/pixel; {(smfreq) / (self.frame_size * pclk)} fps  (target: {self.frame_rate})')

        pio_refresh = pio_assemble(pclk)
        sm = rp2.StateMachine(0, pio_refresh, freq=smfreq, out_base=machine.Pin(self.pin_leds), sideset_base=machine.Pin(self.pin_step))
        sm.active(1)
        
        return sm
    
    @staticmethod
    def _dma_chain(frame_buffer, chunk_count, chunk_size, sm):
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
    

def main():
    import sys

    sw = ScanWheel(linewidth=2048, framerate=20)
    
    try:
        sw.align()
        sw.start(leds_state=0b00000111)
        
        def test_card(path, halign, valign):
            try:
                with open(path, 'rb') as f:
                    offset = (valign * sw.frame_w + halign) % sw.frame_size
                    f.readinto(memoryview(sw.frame_memory)[offset:])
                    if offset > 0:
                        f.readinto(memoryview(sw.frame_memory)[:offset])
            except:
                print(f'{path}')
            
        hpixels = 0
        vlines = 0
        test_cards = ['tcb2048.raw', 'tcj2048.raw', 'tcg2048.raw', 'tcf2048.raw']
        card = 3
        test_card(test_cards[card], hpixels, vlines)

        while True:
            ch = sys.stdin.read(1)
            h, v = hpixels, vlines
            reload = False
            
            if ch == 'a':
                h = hpixels - sw.frame_w // 100
            if ch == 'A':
                h = hpixels - sw.frame_w // 10
            if ch == 'd':
                h = hpixels + sw.frame_w // 100
            if ch == 'D':
                h = hpixels + sw.frame_w // 10
            if ch == 'w':
                v = vlines - 1
            if ch == 's':
                v = vlines + 1
            if ch == 'o':
                config = ScanWheel.read_config()
                config['halign'] = (hpixels / sw.frame_w) + sw.halign
                config['valign'] = sw.valign + vlines
                ScanWheel.write_config(config)
                print('wrote scanwheel.cfg')
            
            t = ord(ch) - ord('1')
            if t >= 0 and t < len(test_cards):
                card = t
                reload = True
                
            if reload or h != hpixels or v != vlines:
                hpixels = h
                vlines = ((v + (sw.frame_h // 2)) % sw.frame_h) - (sw.frame_h // 2)
                print(f'valign={sw.valign + vlines}; halign={(hpixels / sw.frame_w) + sw.halign:.2f}')
                test_card(test_cards[card], hpixels, vlines)
            

        
    finally:
        sw.stop()

if __name__ == "__main__":
    main()
