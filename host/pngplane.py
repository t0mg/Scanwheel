#!/usr/bin/env python3
from PIL import Image
import argparse
import sys

def convert_image(img):
    w, h = img.size
    wb = (w + 7) // 8
    
    dither = [int('{:08b}'.format(n)[::-1], 2) for n in range(256)]

    pixels = list(img.getdata())

    converted = bytearray(wb * h)
    
    for y in range(h):
        for x in range(0, w, 8):
            p = 0
            for b in range(8):
                if pixels[y * w + x + b] > dither[(y * 16 + x + b) & 255]:
                    p |= (128 >> b)
                
            converted[y * wb + x // 8] = p

    return bytes(converted)

def main():
    parser = argparse.ArgumentParser(description="Convert png to bit plane")
    parser.add_argument("input", help="Input png file")
    parser.add_argument("output", help="Output raw file")
    args = parser.parse_args()
    
    try:
        im = Image.open(args.input)
    except Exception as e:
        print("Error opening input:", e, file=sys.stderr)
        sys.exit(1)

    im = im.convert("L")

    converted = convert_image(im)

    try:
        with open(args.output, "wb") as f:
            f.write(converted)
    except Exception as e:
        print("Error writing output:", e, file=sys.stderr)
        sys.exit(1)

    print(f"Wrote {len(converted)} bytes to {args.output}")

if __name__ == "__main__":
    main()
