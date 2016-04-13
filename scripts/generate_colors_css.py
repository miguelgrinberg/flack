#!/usr/bin/env python

# This simple script takes a list of colors and generates a CSS file with them.
# The color data in file colors.txt was obtained from http://bit.ly/1nAzXHD.
# Usage is as follows:
#     ./generate_colors_css.py > colors.css
import re
import random

brightness = 0.9

colors = []
with open('colors.txt', 'r') as f:
    for line in f.readlines():
        m = re.match(
            '^(.*)\s([0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F])', line)
        # parse name and hex code for the color
        name = m.group(1).strip()
        hex1 = m.group(2)
        r = int(hex1[0:2], 16)
        g = int(hex1[2:4], 16)
        b = int(hex1[4:6], 16)

        # adjust brightness of color
        r = int(r * brightness)
        g = int(g * brightness)
        b = int(b * brightness)

        # convert back to hex and save
        hex1 = hex(r)[2:] + hex(g)[2:] + hex(b)[2:]
        colors.append({'name': name, 'hex': hex1})

# randomize color order
random.shuffle(colors)

# write CSS file
i = 0
for color in colors:
    print('.color' + str(i) + ' { font-weight: bold; color: #' +
          color['hex'] + '; } /* ' + color['name'] + ' */')
    i += 1
