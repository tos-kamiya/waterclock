#!/usr/bin/env python3

import pyxel

import sys
import random
import datetime

DIGIT_DISP_ZOOM = 3

WIDTH = (1 + 4 * 4) * DIGIT_DISP_ZOOM
HEIGHT = 8 * DIGIT_DISP_ZOOM

LIQUD_MOVE_INTERVAL = 4

LIQUID_COLORS = [5, 3, 8, 9]

WALL_COLOR = 13

DIGIT_PATTERN_STRS = [
    "111\n101\n101\n101\n111\n",
    "001\n001\n001\n001\n001\n",
    "111\n001\n111\n100\n111\n",
    "111\n001\n111\n001\n111\n",
    "101\n101\n111\n001\n001\n",
    "111\n100\n111\n001\n111\n",
    "111\n100\n111\n101\n111\n",
    "111\n101\n001\n001\n001\n",
    "111\n101\n111\n101\n111\n",
    "111\n101\n111\n001\n111\n",
]


def remove_bottom_digit(field, pos):
    for y in range(7 * DIGIT_DISP_ZOOM, (7 + 1) * DIGIT_DISP_ZOOM):
        field_y = field[y]
        for x in range((1 + pos * 4) * DIGIT_DISP_ZOOM, (1 + pos * 4 + 3) * DIGIT_DISP_ZOOM):
            if x % 3 == 1:
                field_y[x] = 0


def put_digit(field, pos, digit):
    for y in range(8 * DIGIT_DISP_ZOOM):
        field_y = field[y]
        for x in range((1 + pos * 4) * DIGIT_DISP_ZOOM, (1 + pos * 4 + 3) * DIGIT_DISP_ZOOM):
            if field_y[x] == WALL_COLOR:
                field_y[x] = 0

    for y in range(7 * DIGIT_DISP_ZOOM, (7 + 1) * DIGIT_DISP_ZOOM):
        field_y = field[y]
        for x in range((1 + pos * 4) * DIGIT_DISP_ZOOM, (1 + pos * 4 + 3) * DIGIT_DISP_ZOOM):
            field_y[x] = WALL_COLOR

    dp = DIGIT_PATTERN_STRS[digit].split('\n')
    for dy in range(5):
        for dx in range(3):
            if dp[dy][dx] == '0':
                for y in range((2 + dy) * DIGIT_DISP_ZOOM, (2 + dy + 1) * DIGIT_DISP_ZOOM):
                    field_y = field[y]
                    for x in range((1 + pos * 4 + dx) * DIGIT_DISP_ZOOM, (1 + pos * 4 + dx + 1) * DIGIT_DISP_ZOOM):
                        field_y[x] = WALL_COLOR

class App:

    def __init__(self, scale=8, dropping_point=None):
        pyxel.init(WIDTH, HEIGHT + 1, caption='Water Clock', fps=20, scale=scale)

        self.field = [([0] * WIDTH) for y in range(2 * DIGIT_DISP_ZOOM)] + \
            [([WALL_COLOR] * WIDTH) for y in range(HEIGHT - 2 * DIGIT_DISP_ZOOM)] + [[0] * WIDTH]
        for y in range(1 * DIGIT_DISP_ZOOM, 2 * DIGIT_DISP_ZOOM):
            self.field[y][WIDTH - 1] = WALL_COLOR

        nt = datetime.datetime.now()
        h, m = nt.hour, nt.minute
        self.disp_digits = [h // 10, h % 10, m // 10, m % 10]
        for p in range(4):
            put_digit(self.field, p, self.disp_digits[p])
        self.disp_digits_update_countdown = -1
        self.disp_digits_update_poss = []

        self.dropping_point = dropping_point

        self.liquid_color_index = 0

        pyxel.run(self.update, self.draw)

    def update(self):
        if pyxel.btnp(pyxel.KEY_Q):
            pyxel.quit()
        if pyxel.btnp(pyxel.KEY_C):
            self.liquid_color_index = (self.liquid_color_index + 1) % len(LIQUID_COLORS)

        if self.disp_digits_update_countdown >= 0:
            self.disp_digits_update_countdown -= 1
            if self.disp_digits_update_countdown == 0:
                for p in self.disp_digits_update_poss:
                    put_digit(self.field, p, self.disp_digits[p])

        nt = datetime.datetime.now()
        h, m = nt.hour, nt.minute
        ds = [h // 10, h % 10, m // 10, m % 10]
        if ds != self.disp_digits:
            self.disp_digits_update_countdown = 40
            self.disp_digits_update_poss = []
            for p in range(4):
                if ds[p] != self.disp_digits[p]:
                    remove_bottom_digit(self.field, p)
                    self.disp_digits_update_poss.append(p)
            self.disp_digits = ds

        self.field_update()

    def draw(self):
        pyxel.cls(0)
        for y in range(HEIGHT):
            field_y = self.field[y]
            for x in range(WIDTH):
                c = field_y[x]
                if c <= 0 and 0 < x < WIDTH - 1 and field_y[x - 1] in LIQUID_COLORS and field_y[x + 1] == field_y[x - 1]:
                    c = field_y[x - 1]  # to avoid pixel flicking around liquid
                if c > 0:
                    pyxel.rect(x, y, 1, 1, c)

    def field_update(self):
        field = self.field
        liq_choice = random.randrange(LIQUD_MOVE_INTERVAL)

        for y in range(HEIGHT):
            field_y = field[y]
            if field_y[0] in LIQUID_COLORS:
                field[y][0] = 0
            if field_y[WIDTH - 1] in LIQUID_COLORS:
                field_y[WIDTH - 1] = 0
            for x in range(WIDTH):
                if field_y[x] < 0:
                    field_y[x] += 1

        field_y = field[HEIGHT - 1]
        field_y1 = field[HEIGHT]
        for x in range(WIDTH):
            if field_y1[x] == 0:
                field_y[x] = 0
            elif field_y1[x] != WALL_COLOR:
                field_y1[x] = 0

        for y in range(HEIGHT - 1, 0 - 1, -1):
            field_y = field[y]
            field_y1 = field[y + 1]
            for x in range(1, WIDTH-1):
                if field_y[x] in LIQUID_COLORS:
                    if field_y1[x] <= 0:
                        field_y1[x], field_y[x] = field_y[x], 0
                    elif field_y1[x] in LIQUID_COLORS:
                        if field_y1[x - 1] <= 0:
                            if field_y1[x + 1] <= 0:
                                drops = [field_y1[x], field_y[x]]
                                random.shuffle(drops)
                                field_y1[x - 1] = drops.pop()
                                field_y1[x + 1] = drops.pop()
                                field_y[x] = field_y1[x] = 0
                            else:
                                if field_y[x] in LIQUID_COLORS:
                                    field_y1[x - 1], field_y[x] = field_y[x], 0
                        elif field_y1[x + 1] <= 0:
                            if field_y[x] in LIQUID_COLORS:
                                field_y1[x + 1], field_y[x] = field_y[x], 0

                if field_y[x] in LIQUID_COLORS and (y + x) % LIQUD_MOVE_INTERVAL == liq_choice:
                    if field_y[x - 1] != 0 and field_y[x + 1] <= 0:
                        field_y[x + 1], field_y[x] = field_y[x], 0
                    elif field_y[x + 1] > 0 and field_y[x - 1] <= 0:
                        field_y[x - 1], field_y[x] = field_y[x], 0

        if self.dropping_point == 'random':
            if pyxel.frame_count % 11 == 0:
                x = random.randrange(3, WIDTH - 3)
                field[0][x] = LIQUID_COLORS[self.liquid_color_index]
        else:
            if pyxel.frame_count % 14 == 0:
                x = WIDTH - 3
                field[0][x] = LIQUID_COLORS[self.liquid_color_index]


__doc__ = '''Waterclock.

Usage:
  waterclock [-l|-s]

Option:
  -l    Enlarge window.
  -l    Small window.
  -r    Make a drop point randomly selected.
'''


def main():
    scale = 6
    dropping_point_random = False
    for a in sys.argv[1:]:
        if a in ('-h', '--help', '/?'):
            print(__doc__)
            sys.exit()
        elif a.startswith('-') or a.startswith('/'):
            for c in a[1:]:
                if c == 'l':
                    scale = 16
                elif c == 's':
                    scale = 4
                elif c == 'r':
                    dropping_point_random = True
                else:
                    sys.exit('Unknown option: -%s' % c)
    
    App(scale=scale, 
        dropping_point='random' if dropping_point_random else None)


if __name__ == '__main__':
    main()
