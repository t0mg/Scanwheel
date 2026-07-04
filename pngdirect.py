#!/usr/bin/env python3
from PIL import Image
import argparse
import sys

def pack_image(img):
    w, h = img.size
    
    dither = [int('{:08b}'.format(n)[::-1], 2) for n in range(256)]

    pixels = list(img.getdata())

    packed = bytearray(w * h)
    
    for y in range(h):
        for x in range(w):
            idx = y * w + x
            r = 1 if pixels[idx][0] > dither[(y * 16 + x + 85 * 0) & 255] else 0
            g = 1 if pixels[idx][1] > dither[(y * 16 + x + 85 * 1) & 255] else 0
            b = 1 if pixels[idx][2] > dither[(y * 16 + x + 85 * 2) & 255] else 0
            packed[idx] = r << 2 | g << 1 | b

    return bytes(packed)

def main():
    parser = argparse.ArgumentParser(description="Convert png to raw framebuffer bytes")
    parser.add_argument("input", help="Input png file")
    parser.add_argument("output", help="Output raw file")
    parser.add_argument("-w", "--width", default=2048, type=int, required=False, help="Frame width")
    parser.add_argument("-l", "--lines", default=20, type=int, required=False, help="Scan lines")
    args = parser.parse_args()
    
    width = args.width
    lines = args.lines

    try:
        im = Image.open(args.input)
    except Exception as e:
        print("Error opening input:", e, file=sys.stderr)
        sys.exit(1)

    im = im.convert("RGB")
    im = im.resize((width, lines), resample=Image.LANCZOS)

    packed = pack_image(im)

    try:
        with open(args.output, "wb") as f:
            f.write(packed)
    except Exception as e:
        print("Error writing output:", e, file=sys.stderr)
        sys.exit(1)

    print(f"Wrote {len(packed)} bytes to {args.output} (size {width}x{lines})")

if __name__ == "__main__":
    main()
