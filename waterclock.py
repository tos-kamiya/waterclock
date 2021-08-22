#!/usr/bin/env python3

try:
    import pyxel
except ImportError:
    pyxel = None

try:
    import curses
except ImportError:
    curses = None

import time
import sys
import random
import datetime


DIGIT_DISP_ZOOM = 3

WIDTH = (1 + 4 * 4) * DIGIT_DISP_ZOOM
HEIGHT = 8 * DIGIT_DISP_ZOOM

LIQUID_MOVE_INTERVAL = 4
LIQUID_SEP_INTERVAL = 120

SINKHOLE_OPENING_PERIOD = 45

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


def put_sinkhole(field, pos):
    for x in [(1 + pos * 4) * DIGIT_DISP_ZOOM + 1, (1 + pos * 4 + 2) * DIGIT_DISP_ZOOM + 1]:
        for y in range(2 * DIGIT_DISP_ZOOM, 8 * DIGIT_DISP_ZOOM):
            field_y = field[y]
            if field_y[x] == WALL_COLOR:
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


def liquid_separate(field, x, y, prefer_x):
    c = field[y][x]
    if c not in LIQUID_COLORS:
        return

    wx = wy = 0
    for dy in range(-2, 2+1):
        if not (0 <= y + dy < HEIGHT):
            continue  # for dy
        field_ydy = field[y + dy]
        for dx in range(-2, 2+1):
            if not (0 <= x + dx < WIDTH):
                continue  # for dx
            dist = abs(dx) + abs(dy)
            if not (1 <= dist <= 3):
                continue  # for dx
            if field_ydy[x + dx] == c:
                wx += dx
                wy += dy
        wx = min(1, max(-1, wx))
    wy = min(1, max(-1, wy))
    if prefer_x:
        if wx != 0 and field[y][x + wx] in LIQUID_COLORS:
            field[y][x], field[y][x + wx] = field[y][x + wx], field[y][x]
        elif wy != 0 and field[y + wy][x] in LIQUID_COLORS:
            field[y][x], field[y + wy][x] = field[y + wy][x], field[y][x]
    else:
        if wy != 0 and field[y + wy][x] in LIQUID_COLORS:
            field[y][x], field[y + wy][x] = field[y + wy][x], field[y][x]
        elif wx != 0 and field[y][x + wx] in LIQUID_COLORS:
            field[y][x], field[y][x + wx] = field[y][x + wx], field[y][x]


class App:
    def __init__(self, dropping_point=None):
        self.field = [([0] * WIDTH) for y in range(2 * DIGIT_DISP_ZOOM)] + \
            [([WALL_COLOR] * WIDTH) for y in range(HEIGHT - 2 * DIGIT_DISP_ZOOM)] + [[0] * WIDTH]
        if dropping_point == 'both':
            for x in range(3):
                self.field[7 * DIGIT_DISP_ZOOM - 1][x] = 0

        nt = datetime.datetime.now()
        h, m = nt.hour, nt.minute
        self.disp_digits = [h // 10, h % 10, m // 10, m % 10]
        for p in range(4):
            put_digit(self.field, p, self.disp_digits[p])
        self.disp_digits_update_countdown = -1
        self.disp_digits_update_poss = []

        self.dropping_point = dropping_point
        self.drop_accel = 0
        self.drop_move_picks = []
        self.drop_sep_picks = []

        self.liquid_color_index = 0

        self.frame_count = 0

    def field_update(self):
        field = self.field

        nt = datetime.datetime.now()
        h, m = nt.hour, nt.minute
        ds = [h // 10, h % 10, m // 10, m % 10]
        if ds != self.disp_digits:
            self.disp_digits_update_countdown = SINKHOLE_OPENING_PERIOD
            self.disp_digits_update_poss = []
            for p in range(4):
                if ds[p] != self.disp_digits[p]:
                    put_sinkhole(self.field, p)
                    self.disp_digits_update_poss.append(p)
            self.disp_digits = ds

        if self.disp_digits_update_countdown >= 0:
            self.disp_digits_update_countdown -= 1
            if self.disp_digits_update_countdown == 0:
                for p in self.disp_digits_update_poss:
                    put_digit(self.field, p, self.disp_digits[p])

        if not self.drop_move_picks:
            picks = []
            for i in range(LIQUID_MOVE_INTERVAL):
                picks.extend([i] * 5)
            self.drop_move_picks = picks
            random.shuffle(self.drop_move_picks)

        if not self.drop_sep_picks:
            picks = []
            for i in range(LIQUID_SEP_INTERVAL):
                picks.extend([i] * 5)
            self.drop_sep_picks = picks
            random.shuffle(self.drop_sep_picks)

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

        dp = self.drop_move_picks.pop()
        ds = self.drop_sep_picks.pop()
        ds_prefer_x = random.randrange(2) == 0
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

                c = field_y[x]
                if c in LIQUID_COLORS:
                    if (y + x) % LIQUID_MOVE_INTERVAL == dp:
                        if field_y[x - 1] > 0 and field_y[x + 1] <= 0:
                            field_y[x + 1], field_y[x] = c, 0
                        elif field_y[x + 1] > 0 and field_y[x - 1] <= 0:
                            field_y[x - 1], field_y[x] = c, 0
                    if (y + x) % LIQUID_SEP_INTERVAL == ds:
                        liquid_separate(field, x, y, ds_prefer_x)

        if self.dropping_point in ['random', 'patchwork']:
            if self.frame_count % (6 - self.drop_accel) == 0:
                if self.dropping_point == 'patchwork':
                    self.liquid_color_index = (self.liquid_color_index + 1) % len(LIQUID_COLORS)
                x = random.randrange(3, WIDTH - 3)
                field[0][x] = LIQUID_COLORS[self.liquid_color_index]
        elif self.dropping_point == 'both':
            if self.frame_count % (6 - self.drop_accel) == 0:
                x = 4 * 4 * DIGIT_DISP_ZOOM - 5
                field[0][x] = LIQUID_COLORS[self.liquid_color_index]
                x = 1 * 4 * DIGIT_DISP_ZOOM - 5
                field[0][x] = LIQUID_COLORS[(self.liquid_color_index + 1) % len(LIQUID_COLORS)]
        else:
            if self.frame_count % (11 - self.drop_accel) == 0:
                x = 4 * 4 * DIGIT_DISP_ZOOM - 5
                field[0][x] = LIQUID_COLORS[self.liquid_color_index]

if pyxel is not None:
    class AppPyxel(App):
        def __init__(self, scale=8, dropping_point=None):
            super().__init__(dropping_point=dropping_point)

            pyxel.init(WIDTH, HEIGHT + 1, caption='Water Clock', fps=20, scale=scale)

        def run(self):
            pyxel.run(self.update, self.draw)

        def update(self):
            self.frame_count = pyxel.frame_count

            if pyxel.btnp(pyxel.KEY_Q):
                pyxel.quit()
            if pyxel.btnp(pyxel.KEY_C):
                if self.dropping_point == 'both':
                    self.liquid_color_index = (self.liquid_color_index + 2) % len(LIQUID_COLORS)
                else:
                    self.liquid_color_index = (self.liquid_color_index + 1) % len(LIQUID_COLORS)
            if pyxel.btnp(pyxel.KEY_UP):
                self.drop_accel = min(3, self.drop_accel + 1)
            elif pyxel.btnp(pyxel.KEY_DOWN):
                self.drop_accel = max(-3, self.drop_accel - 1)

            self.field_update()

        def draw(self):
            pyxel.cls(0)

            if self.drop_accel != 0:
                if self.drop_accel < 0:
                    s = '-' * -self.drop_accel
                else:
                    s = '+' * self.drop_accel
                pyxel.text(0, 0, s, 1)

            for y in range(HEIGHT):
                field_y = self.field[y]
                for x in range(WIDTH):
                    c = field_y[x]
                    if c <= 0 and 0 < x < WIDTH - 1 and field_y[x - 1] in LIQUID_COLORS and field_y[x + 1] == field_y[x - 1]:
                        c = field_y[x - 1]  # to avoid pixel flicking around liquid
                    if c > 0:
                        pyxel.rect(x, y, 1, 1, c)

if curses is not None:
    class AppCurses(App):
        def __init__(self, dropping_point=None):
            super().__init__(dropping_point=dropping_point)

        def run(self):
            curses.wrapper(self.main)

        def main(self, sc):
            self.stdscr = sc
            height, width = sc.getmaxyx()
            if height < HEIGHT or width < WIDTH * 2:
                sys.exit('Error: required screen size is %d x %d, but actual was %d x %d.' % (WIDTH * 2, HEIGHT, width, height))

            curses.start_color()
            curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)
            curses.init_pair(5, curses.COLOR_BLUE, curses.COLOR_BLACK)
            curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)
            curses.init_pair(8, curses.COLOR_RED, curses.COLOR_BLACK)
            curses.init_pair(9, curses.COLOR_YELLOW, curses.COLOR_BLACK)
            curses.init_pair(13, curses.COLOR_WHITE, curses.COLOR_BLACK)
            curses.curs_set(0)
            curses.noecho()
            curses.cbreak()
            sc.nodelay(True)

            while True:
                c = sc.getch()
                if c == ord('q'):
                    break
                elif c == ord('c'):
                    if self.dropping_point == 'both':
                        self.liquid_color_index = (self.liquid_color_index + 2) % len(LIQUID_COLORS)
                    else:
                        self.liquid_color_index = (self.liquid_color_index + 1) % len(LIQUID_COLORS)
                elif c == curses.KEY_UP:
                    self.drop_accel = min(3, self.drop_accel + 1)
                elif c == curses.KEY_DOWN:
                    self.drop_accel = max(-3, self.drop_accel - 1)

                time.sleep(1.0/20)
                self.update()
                self.draw()

        def update(self):
            self.frame_count += 1
            self.field_update()
        
        def draw(self):
            stdscr = self.stdscr
            stdscr.clear()

            for y in range(0, HEIGHT):
                field_y = self.field[y]
                for x in range(0, WIDTH):
                    c = field_y[x]
                    if c <= 0 and 0 < x < WIDTH - 1 and field_y[x - 1] in LIQUID_COLORS and field_y[x + 1] == field_y[x - 1]:
                        c = field_y[x - 1]  # to avoid pixel flicking around liquid
                    if c == 0:
                        stdscr.addstr(y, x*2, '  ', curses.color_pair(0))
                    else:
                        stdscr.addstr(y, x*2, '\u2588\u2588', curses.color_pair(c))

            if self.drop_accel != 0:
                if self.drop_accel < 0:
                    s = '-' * -self.drop_accel
                else:
                    s = '+' * self.drop_accel
                stdscr.addstr(0, 0, s, curses.color_pair(7))

            stdscr.refresh()


__doc__ = '''Waterclock.

Usage:
  waterclock [-t|-l|-s] [-r|-b|-p]

Option:
  -l    Enlarge window.
  -s    Small window.
  -r    Random mode: randomly changes position of ink drop.
  -b    Encampment mode: Different colors of ink from both ends.
  -p    Patchwork mode: randomly changes position and color of ink drop.
  -t    Run in terminal.
'''


def main():
    scale = 8
    dropping_point = None
    terminal_mode = pyxel is None
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
                    dropping_point = 'random'
                elif c == 'b':
                    dropping_point = 'both'
                elif c == 'p':
                    dropping_point = 'patchwork'
                elif c == 't':
                    terminal_mode = True
                else:
                    sys.exit('Unknown option: -%s' % c)
    
    if terminal_mode:
        if curses is None:
            sys.exit('Error: fail to load `curses` library')
        app = AppCurses(dropping_point=dropping_point)
    else:
        if pyxel is None:
            sys.exit('Error: fail to load `pyxel` library')
        app = AppPyxel(dropping_point=dropping_point, scale=scale)

    app.run()


if __name__ == '__main__':
    main()
