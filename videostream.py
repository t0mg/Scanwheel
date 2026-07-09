#!/usr/bin/env python3
import argparse
import subprocess
import sys
import socket
import os
import time

def ffmpeg_frame_memoryviews(input_path, width, height, fps, ffmpeg_path="ffmpeg"):
    frame_size = width * height * 3
    zoom = 1.0
    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel", "error",
        "-i", input_path,
        "-vf", f"crop='min(iw,ih)/{zoom}':'min(iw,ih)/{zoom}':'(iw-min(iw,ih)/{zoom})/2':'(ih-min(iw,ih)/{zoom})/2',scale={width}:{height},fps={fps}",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-"
    ]

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
        
        
dither = [int('{:08b}'.format(n)[::-1], 2) for n in range(256)]

def process_frame(pixels, width, height, frame, output):
    for y in range(height):
        for x in range(width):
            idx = y * width + x
            
            r = 1 if pixels[idx * 3 + 0] > dither[(frame * 29 + y * 16 + x + 85 * 0) & 255] else 0
            g = 1 if pixels[idx * 3 + 1] > dither[(frame * 29 + y * 16 + x + 85 * 1) & 255] else 0
            b = 1 if pixels[idx * 3 + 2] > dither[(frame * 29 + y * 16 + x + 85 * 2) & 255] else 0
            
            output[idx] = r << 2 | g << 1 | b



def stream_video(ip, video, width, height, fps):
    with socket.create_connection((ip, 2000), timeout=10) as sock:
        print('Connected')
        
        rawframe = bytearray(width * height)
        while True:
            t0 = time.perf_counter()
            for i, mv in enumerate(ffmpeg_frame_memoryviews(video, width, height, fps)):
                process_frame(mv, width, height, i, memoryview(rawframe))
                while time.perf_counter() < t0 + i / fps:
                    time.sleep(0)
                sock.sendall(rawframe)

def main():
    parser = argparse.ArgumentParser(description="stream video to scanwheel")
    parser.add_argument("ip", help="Scanwheel address")
    parser.add_argument("video", help="Video file")
    parser.add_argument("-w", "--width", default=1024, type=int, required=False, help="Frame width")
    parser.add_argument("-l", "--lines", default=20, type=int, required=False, help="Scan lines")
    parser.add_argument("-f", "--fps", default=15, type=int, required=False, help="Framerate")
    args = parser.parse_args()
    
    stream_video(args.ip, args.video, args.width, args.lines, args.fps)
    
if __name__ == "__main__":
    main()

