#!/usr/bin/env python3
import argparse
import subprocess
import sys
import socket
import os
import time
import math
from typing import Optional
import numpy as np

def ffmpeg_frame_memoryviews(input_path, width, height, screens, fps, ffmpeg_path="ffmpeg"):
    frame_size = width * screens * height * 3
    aspect = 9 * screens / 8
    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel", "error",
        "-i", input_path,
        "-f", "rawvideo",
        "-vf", f"crop='if(gt(iw/ih,{aspect}),ih*{aspect},iw)':'if(gt(iw/ih,{aspect}),ih,iw/({aspect}))':'(iw - if(gt(iw/ih,{aspect}),ih*{aspect},iw))/2':'(ih - if(gt(iw/ih,{aspect}),ih,iw/({aspect})))/2', scale={width * screens}:{height}, fps={fps}",
        "-pix_fmt", "rgb24",
        "-"
    ]
    '''
    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel", "error",
        "-f", "gdigrab", "-framerate", "24", "-i", "desktop",
        "-video_size", "2048x200", "-show_region", "1",
        #"-vf", f"crop='if(gt(iw/ih,{aspect}),ih*{aspect},iw)':'if(gt(iw/ih,{aspect}),ih,iw/({aspect}))':'(iw - if(gt(iw/ih,{aspect}),ih*{aspect},iw))/2':'(ih - if(gt(iw/ih,{aspect}),ih,iw/({aspect})))/2', scale={width * screens}:{height}, fps={fps}",
        "-pix_fmt", "rgb24",
        "-"
    ]
    '''

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.stdout is None:
        raise RuntimeError("ffmpeg stdout not available")

    buf = bytearray(frame_size)
    try:
        while True:
            n = proc.stdout.readinto(buf)
            if not n:
                break
            if n < frame_size:
                break
            yield memoryview(buf)
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        proc.wait()
        

def process_window(
    frame_mv: memoryview,
    src_w: int,
    src_h: int,
    dst_w: int,
    x_offset: int,
    y_offset: int,
    channel: int,
    led_mask: int,
    dest_mv: memoryview,
    dither: bytes,
    dither_offset: int
) -> None:
    frame_arr = np.frombuffer(frame_mv, dtype=np.uint8).reshape((src_h, src_w, 3))
    dest_arr = np.frombuffer(dest_mv, dtype=np.uint8)
    dest_view = dest_arr.reshape((src_h, dst_w))

    x_positions = (np.arange(dst_w, dtype=np.int64) + int(x_offset)) % src_w  # shape (dst_w,)

    src_lines = (np.arange(src_h, dtype=np.int64) + int(y_offset)) % src_h  # shape (src_h,)

    channel_vals = frame_arr[src_lines[:, None], x_positions[None, :], channel].astype(np.uint8)

    thresholds = dither[(x_positions + dither_offset) % 256].astype(np.uint8)  # shape (dst_w,)

    mask_bool = channel_vals > thresholds[None, :]  # shape (src_h, dst_w), dtype bool

    if not mask_bool.any():
        return

    mask_uint8 = (mask_bool.astype(np.uint8) * np.uint8(led_mask))

    np.bitwise_or(dest_view, mask_uint8, out=dest_view)
    
    return

    

def process_frame(pixels, width, height, screens, output, dither):
    prio = [2, 1, 3, 0, 4]
    leds = [0x40, 0x20, 0x07, 0x10, 0x08]
    
    output[:] = b"\x00" * len(output)

    for ss in range(screens):
        s = prio[ss]
        
        x = (s - (2 - screens // 2)) * width
        y = ((2 - s) % height)
        
        if s == 2:
            for c in range(3):
                process_window(pixels, width * screens, height, width, x, y, c, 4 >> c, output, dither, s * 51 + c * 85)
        else:
            process_window(pixels, width * screens, height, width, x, y, 1, leds[s], output, dither, s * 51)


def stream_video(ip, video, width, height, fps, screens, gamma):
    
    def g(v):
        return int(round(math.pow(v / 255.0, 1.0 / gamma) * 255.0))
    
    dither = np.frombuffer(bytes([g(int('{:08b}'.format(n)[::-1], 2)) for n in range(256)]), dtype=np.uint8)

    def tick():
        return time.perf_counter()
    
    with socket.create_connection((ip, 2000), timeout=10) as sock:
        print('Connected')
        
        dropped = 0
        rawframe = bytearray(width * height)
        while True:
            t0 = tick()
            for i, mv in enumerate(ffmpeg_frame_memoryviews(video, width, height, screens, fps)):
                tf = t0 + (i / fps)
                t1 = tick()
                if t1 > tf:
                    dropped += 1
                    continue
                process_frame(mv, width, height, screens, memoryview(rawframe), dither)
                t2 = tick()
                while tick() < tf:
                    time.sleep(0)
                t3 = tick()
                sock.sendall(rawframe)
                t4 = tick()
                
                if (i % round(fps) == 0):
                    print(f'process: {(t2 - t1) * 1000:.2f} ms; send: {(t4 - t3) * 1000:.2f} ms; dropped: {dropped}')
                    dropped = 0

def main():
    parser = argparse.ArgumentParser(description="stream video to scanwheel")
    parser.add_argument("ip", help="Scanwheel address")
    parser.add_argument("video", help="Video file")
    parser.add_argument("-s", "--screens", default=1, type=int, required=False, help="Screens")
    parser.add_argument("-w", "--width", default=1024, type=int, required=False, help="Frame width")
    parser.add_argument("-l", "--lines", default=20, type=int, required=False, help="Scan lines")
    parser.add_argument("-f", "--fps", default=15, type=int, required=False, help="Framerate")
    parser.add_argument("-g", "--gamma", default=1, type=float, required=False, help="Framerate")
    args = parser.parse_args()
    
    stream_video(args.ip, args.video, args.width, args.lines, args.fps, args.screens, args.gamma)
    
if __name__ == "__main__":
    main()

