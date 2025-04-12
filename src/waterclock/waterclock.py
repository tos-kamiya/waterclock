import argparse
import colorsys
from datetime import datetime, timedelta
import json
import os
import platform
import random
import shutil
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import pygame
from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget, QVBoxLayout, QSizeGrip
from PyQt5.QtGui import QPainter, QImage, QColor, QIcon
from PyQt5.QtCore import QTimer, Qt
from appdirs import user_cache_dir

try:
    from .__about__ import __version__
except ImportError:
    __version__ = "(unknown)"

APP_NAME = "waterclock"
APP_AUTHOR = "tos-kamiya"

CACHE_DIR = user_cache_dir(APP_NAME, APP_AUTHOR)
CACHE_FILE_GEOMETRY = os.path.join(CACHE_DIR, "window_geometry.json")

# --- Constants ---
FRAME_RATE = 20

DIGIT_PIXEL_SIZE: int = 3
THRUHOLE_WIDTH: int = 4
WIDTH: int = (1 + 4 * 4) * DIGIT_PIXEL_SIZE + THRUHOLE_WIDTH
HEIGHT: int = 7 * DIGIT_PIXEL_SIZE

SINKHOLE_OPENING_PERIOD: int = 40
SINKHOLE_EXTENSION: Dict[int, int] = {0: 4, 1: 6, 2: -7, 3: 5, 4: 13, 5: 13, 6: -5, 7: 15, 8: -14, 9: 13}
DROPLET_MOVE_INTERVAL: int = 4
DROPLET_SWAP_INTERVAL: int = 60
DROPLET_DROP_SIZE: int = 2
DROPLET_DROP_INTERVAL: int = 24

COLOR_WALL: int = 99
COLOR_BACKGROUND: int = 0
COLOR_COVER: int = 100

# Digit pattern strings (for 0 to 9)
DIGIT_BITMAP_STRINGS: List[str] = [
    "111\n101\n101\n101\n111\n",  # 0
    "001\n011\n001\n011\n001\n",  # 1
    "111\n001\n111\n100\n111\n",  # 2
    "111\n001\n111\n001\n111\n",  # 3
    "101\n111\n111\n001\n001\n",  # 4
    "111\n100\n111\n001\n111\n",  # 5
    "111\n100\n111\n101\n111\n",  # 6
    "111\n101\n001\n011\n001\n",  # 7
    "111\n101\n111\n101\n111\n",  # 8
    "111\n101\n111\n001\n111\n",  # 9
    "000\n010\n000\n010\n000\n",  # Cover
]
DIGIT_BITMAPS: List[List[List[int]]] = [
    [[int(n) for n in ss] for ss in s.strip().split("\n")] for s in DIGIT_BITMAP_STRINGS
]

# --- Utility Functions ---
def find_icon_file(filename):
    base_dirs = []
    pkg_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data'))
    base_dirs.append(pkg_data_dir)
    try:
        pyinstaller_data_dir = sys._MEIPASS
        base_dirs.append(pyinstaller_data_dir)
    except Exception:
        pass
    base_dirs.append(os.path.abspath("."))

    for b in base_dirs:
        icon_path = os.path.join(b, filename)
        if os.path.exists(icon_path):
            return icon_path
    return None


def generate_desktop_file(theme="default", load_geometry=False):
    if platform.system() != "Linux":
        sys.exit("Error: .desktop file is valid only on Linux system.")

    exec_path = shutil.which("waterclock") or os.path.abspath(sys.argv[0])

    icon_path = find_icon_file("icon256.png") or ""

    options = ""
    if theme:
        options += f" --theme {theme}"
    if load_geometry:
        options += " --load-geometry"

    desktop_file_content = f"""[Desktop Entry]
Name=Water Clock
Comment=A digital water clock simulation
Exec={exec_path}{options}
Icon={icon_path}
Terminal=false
Type=Application
Categories=Utility;
"""
    dest_file = os.path.join(os.getcwd(), "waterclock.desktop")

    try:
        with open(dest_file, "w") as f:
            f.write(desktop_file_content)
        print(f".desktop file generated at {dest_file}", file=sys.stderr)
        print("To integrate with your system, copy this file to ~/.local/share/applications/ or ~/.config/autostart/", file=sys.stderr)
        print("For example:", file=sys.stderr)
        print("  cp waterclock.desktop ~/.local/share/applications/", file=sys.stderr)
    except Exception as e:
        sys.exit(f"Error: Failed to generate .desktop file: {e}")


def load_window_geometry():
    if not os.path.exists(CACHE_FILE_GEOMETRY):
        return None

    try:
        with open(CACHE_FILE_GEOMETRY, "r") as f:
            geometry = json.load(f)
        x, y = int(geometry["window_x"]), int(geometry["window_y"])
        width, height = int(geometry["window_width"]), int(geometry["window_height"])
        print(f"Info: load window geometry from file: {CACHE_FILE_GEOMETRY}", file=sys.stderr)
        return x, y, width, height
    except Exception as e:
        print(f"Error: fail to load window geometry from file: {CACHE_FILE_GEOMETRY}", file=sys.stderr)
        return None


def save_window_geometry(x, y, width, height):
    geometry = {"window_x": x, "window_y": y, "window_width": width, "window_height": height}
    try:
        with open(CACHE_FILE_GEOMETRY, "w") as f:
            json.dump(geometry, f, indent=4)
        print(f"Info: save window geometry to file: {CACHE_FILE_GEOMETRY}", file=sys.stderr)
    except Exception as e:
        print(f"Error: fail to save window geometry to file: {CACHE_FILE_GEOMETRY}", file=sys.stderr)


def modify_v(rgb: Tuple[int, int, int], v_add: float) -> Tuple[int, int, int]:
    assert -1.0 <= v_add <= 1.0

    r, g, b = rgb
    assert 0 <= r < 255
    assert 0 <= g < 255
    assert 0 <= b < 255

    rgb_01 = (r / 255, g / 255, b / 255)  # Normalize RGB to 0-1 range
    hsv = colorsys.rgb_to_hsv(*rgb_01)

    new_v = hsv[2] + v_add
    new_hsv = (hsv[0], hsv[1], max(0.0, min(1.0, new_v)))

    new_rgb_01 = colorsys.hsv_to_rgb(*new_hsv)
    new_rgb = int(new_rgb_01[0] * 255), int(new_rgb_01[1] * 255), int(new_rgb_01[2] * 255)

    return new_rgb


def is_liquid_color(c: int) -> bool:
    return c != COLOR_BACKGROUND and c != COLOR_WALL


def put_colon(field: List[List[int]], put_wall: bool):
    COLON_X: int = 2 * 4 * DIGIT_PIXEL_SIZE + DIGIT_PIXEL_SIZE // 2
    COLON_Y1: int = 2 * DIGIT_PIXEL_SIZE + DIGIT_PIXEL_SIZE // 2
    COLON_Y2: int = 4 * DIGIT_PIXEL_SIZE + DIGIT_PIXEL_SIZE // 2

    if put_wall:
        for y in [COLON_Y1, COLON_Y2]:
            if field[y][COLON_X] != COLOR_WALL:
                field[y][COLON_X] = COLOR_WALL
    else:
        for y in [COLON_Y1, COLON_Y2]:
            if field[y][COLON_X] == COLOR_WALL:
                field[y][COLON_X] = COLOR_BACKGROUND


def create_field(liquid_color: int) -> List[List[int]]:
    """Create the simulation field.

    The field is a 2D grid initialized with background and wall colors.
    The upper part is set to background (0) and the middle part to wall color.
    Also draws the colon separators initially as background.

    Returns:
        A 2D list of integers representing the field.
    """
    field: List[List[int]] = []
    # Upper part: DIGIT_DISP_ZOOM rows as background
    for y in range(1 * DIGIT_PIXEL_SIZE):
        field.append([COLOR_BACKGROUND] * WIDTH)
    # Middle part: rows from DIGIT_DISP_ZOOM to HEIGHT as wall color
    for y in range(DIGIT_PIXEL_SIZE, HEIGHT):
        field.append([COLOR_WALL] * WIDTH)
    # Bottom row: background
    field.append([COLOR_BACKGROUND] * WIDTH)

    # Initially, draw the colon as background
    put_colon(field, False)

    # Draw thru hole
    x = (1 + 4 * 4) * DIGIT_PIXEL_SIZE
    for y in range(DIGIT_PIXEL_SIZE, DIGIT_PIXEL_SIZE * 7):
        if y % 4 != 1:
            field[y][x] = COLOR_BACKGROUND
            field[y][x + 2] = COLOR_BACKGROUND
        if y % 4 != 3:
            field[y][x + 1] = COLOR_BACKGROUND

    for y in range(0, DIGIT_PIXEL_SIZE):
        for x in range(WIDTH):
            if field[y][x] == COLOR_BACKGROUND:
                field[y][x] = liquid_color

    return field


def put_sinkhole(field: List[List[int]], pos: int) -> None:
    """Clear parts of the wall for a digit container at the specified position.

    Args:
        field: The simulation field.
        pos: The digit position (0-3) to update.
    """
    xs = [(pos * 4 + 1) * DIGIT_PIXEL_SIZE + DIGIT_PIXEL_SIZE - 2, (pos * 4 + 3) * DIGIT_PIXEL_SIZE + DIGIT_PIXEL_SIZE - 2]
    for y in range(6 * DIGIT_PIXEL_SIZE, 7 * DIGIT_PIXEL_SIZE):
        for x in xs:
            if field[y][x] == COLOR_WALL:
                field[y][x] = COLOR_BACKGROUND


def remove_sinkhole(field: List[List[int]], pos: int) -> None:
    xs = [(pos * 4 + 1) * DIGIT_PIXEL_SIZE + DIGIT_PIXEL_SIZE - 2, (pos * 4 + 3) * DIGIT_PIXEL_SIZE + DIGIT_PIXEL_SIZE - 2]
    for y in range(6 * DIGIT_PIXEL_SIZE, 7 * DIGIT_PIXEL_SIZE):
        for x in xs:
            field[y][x] = COLOR_WALL


def put_digit(field: List[List[int]], pos: int, digit: int) -> None:
    """Render a digit into the field.

    Clears the digit display area and then draws the digit pattern.
    The '0' parts in the pattern are drawn with the wall color.

    Args:
        field: The simulation field.
        pos: The digit position (0-3) to update.
        digit: The digit (0-9) to display.
    """
    # Clear walls in the digit display area
    for dy in range(5):
        for dx in range(3):
            for y in range((1 + dy) * DIGIT_PIXEL_SIZE, (1 + dy + 1) * DIGIT_PIXEL_SIZE):
                for x in range((1 + pos * 4 + dx) * DIGIT_PIXEL_SIZE, (1 + pos * 4 + dx + 1) * DIGIT_PIXEL_SIZE):
                    if field[y][x] == COLOR_WALL:
                        field[y][x] = COLOR_BACKGROUND

    # Reflect the digit pattern
    db = DIGIT_BITMAPS[digit]
    for dy in range(5):
        for dx in range(3):
            if db[dy][dx] == COLOR_BACKGROUND:
                for y in range((1 + dy) * DIGIT_PIXEL_SIZE, (1 + dy + 1) * DIGIT_PIXEL_SIZE):
                    for x in range((1 + pos * 4 + dx) * DIGIT_PIXEL_SIZE, (1 + pos * 4 + dx + 1) * DIGIT_PIXEL_SIZE):
                        field[y][x] = COLOR_WALL


def droplets_go_down(field: List[List[int]]):
    """Simulate the downward movement of a droplet.

    If the cell below is empty, the droplet moves down. If the cell below
    is occupied by another liquid, it attempts to move diagonally.

    Args:
        field: The simulation field.
    """

    for y in range(HEIGHT - 1, -1, -1):
        field_y: List[int] = field[y]
        field_y1: List[int] = field[y + 1]
        for x in range(1, WIDTH - 1):
            c: int = field_y[x]
            if not is_liquid_color(c):
                continue

            if field_y1[x] == COLOR_BACKGROUND:
                field_y1[x] = c
                field_y[x] = COLOR_BACKGROUND
            elif is_liquid_color(field_y1[x]):
                dx = x + random.choice([-1, 1])
                if field_y1[dx] == COLOR_BACKGROUND:
                    if field_y[dx] == COLOR_BACKGROUND:
                        field_y1[dx] = c
                        field_y[x] = COLOR_BACKGROUND
                    elif is_liquid_color(field_y1[x]):
                        field_y1[dx] = field_y1[x]
                        field_y1[x] = c
                        field_y[x] = COLOR_BACKGROUND


def droplet_swap(field: List[List[int]], x: int, y: int) -> bool:
    """Swap movement of liquid droplets.

    Calculates a weighted displacement based on neighboring cells and
    swaps the droplet with an adjacent cell accordingly.

    Args:
        field: The simulation field.
        x: The x-coordinate of the droplet.
        y: The y-coordinate of the droplet.
    """
    vxvys = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    def count_same_droplets(x: int, y: int):
        c: int = field[y][x]
        same_liquids = 0
        for vx, vy in vxvys:
            dx, dy = x + vx, y + vy
            dc = field[dy][dx]
            if dc == c:
                same_liquids += 1
        return same_liquids

    c: int = field[y][x]
    if not is_liquid_color(c):
        return False

    vx, vy = vxvys[random.randrange(4)]
    dx, dy = x + vx, y + vy
    if not (0 <= dx < WIDTH and 0 <= dy < HEIGHT):
        return False

    dc: int = field[dy][dx]
    if not is_liquid_color(dc) or dc == c:
        return False

    if (dy - y) * (dc - c) > 0 and abs(dc - c) >= 5:
        if random.random() < 0.7:
            return False

    s = count_same_droplets(x, y)

    field[y][x], field[dy][dx] = dc, c

    s2 = count_same_droplets(x, y)
    if s2 < s:
        field[y][x], field[dy][dx] = c, dc

    return True


def droplet_move(field: List[List[int]], x: int, y: int) -> bool:
    """Move a droplet horizontally if there's space.

    Checks if a droplet can move sideways.  It prioritizes moving to a side
    where the adjacent cell is *not* empty, but the destination is.

    Args:
        field (List[List[int]]): The simulation field.
        x (int): The droplet's X position.
        y (int): The droplet's Y position.

    Returns:
        bool: True if the droplet moved, False otherwise.
    """
    if not (0 <= x - 1 and x + 1 < WIDTH):
        return False

    field_y = field[y]
    c: int = field_y[x]
    if not is_liquid_color(c):
        return False
    if y + 1 < HEIGHT and field[y + 1][x] == COLOR_BACKGROUND:
        return False

    if field_y[x - 1] != COLOR_BACKGROUND and field_y[x + 1] == COLOR_BACKGROUND:
        field_y[x + 1] = c
        field_y[x] = COLOR_BACKGROUND
        return True
    elif field_y[x + 1] != COLOR_BACKGROUND and field_y[x - 1] == COLOR_BACKGROUND:
        field_y[x - 1] = c
        field_y[x] = COLOR_BACKGROUND
        return True
    return False


def pop_pick(pick_queue: List[int], pick_interval: int) -> int:
    """Pops a value from a queue, replenishing the queue if it's empty.

    Args:
        pick_queue: A list acting as the queue.  This list will be modified.
        pick_interval: The interval at which the queue is repopulated.

    Returns:
        The next value from the queue.

    Raises:
        AssertionError: if pick_interval is not greater than zero.
    """
    assert pick_interval > 0
    if not pick_queue:
        picks: List[int] = []
        for i in range(pick_interval):
            picks.extend([i] * 5)
        random.shuffle(picks)
        pick_queue[:] = picks
    return pick_queue.pop()


# --- Base Simulation Class ---
class BaseApp:
    def __init__(self) -> None:
        """Initialize the simulation state."""
        self.field: List[List[int]] = []
        self.prevFields: List[List[List[int]]] = []
        self.cover: List[List[int]] = []
        self.sinkholeCounters: List[int] = [-1] * 4
        self.dropMovePicks: List[int] = []
        self.dropSwapPicks: List[int] = []
        self.dropX: int = 0
        self.frameCount: int = 0

    def init_field(self, now: datetime):
        self.field: List[List[int]] = create_field(self.pick_liquid_color(now))
        h: int = now.hour
        m: int = now.minute
        self.dispDigits: List[int] = [h // 10, h % 10, m // 10, m % 10]
        for p in range(4):
            put_digit(self.field, p, self.dispDigits[p])

        cover = self.cover = []
        for y in range(HEIGHT):
            cover.append([0] * WIDTH)

        db = DIGIT_BITMAPS[10]
        for pos in range(4):
            for dy in range(5):
                for dx in range(3):
                    if db[dy][dx] == 1:
                        for y in range((1 + dy) * DIGIT_PIXEL_SIZE, (1 + dy + 1) * DIGIT_PIXEL_SIZE):
                            for x in range((1 + pos * 4 + dx) * DIGIT_PIXEL_SIZE, (1 + pos * 4 + dx + 1) * DIGIT_PIXEL_SIZE):
                                cover[y][x] = COLOR_COVER

    def update_terrain(self, now: datetime) -> None:
        """Update the simulation field.

        This includes updating the displayed digits, moving droplets,
        and performing other field maintenance such as clearing droplets on edges.

        Args:
            now: The current datetime for simulation timing.
        """
        put_colon(self.field, now.second % 6 < 3)

        h: int = now.hour
        m: int = now.minute
        ds: List[int] = [h // 10, h % 10, m // 10, m % 10]
        if ds != self.dispDigits:
            self.digitUpdatedPoss = []
            for p in range(4):
                if ds[p] != self.dispDigits[p]:
                    put_digit(self.field, p, ds[p])
                    put_sinkhole(self.field, p)
                    self.sinkholeCounters[p] = SINKHOLE_OPENING_PERIOD + SINKHOLE_EXTENSION.get(ds[p], 0)
                    # tens digit is flushed at 5, 10, 15.
                    if p == 1 and h % 5 == 0:
                        p1 = 0
                        put_sinkhole(self.field, p1)
                        self.sinkholeCounters[p1] = SINKHOLE_OPENING_PERIOD + SINKHOLE_EXTENSION.get(ds[p1], 0)

            self.dispDigits = ds

        for p in range(4):
            if self.sinkholeCounters[p] >= 0:
                self.sinkholeCounters[p] -= 1
                if self.sinkholeCounters[p] == 0:
                    remove_sinkhole(self.field, p)

    def pick_liquid_color(self, now: Optional[datetime] = None) -> int:
        raise NotImplementedError()

    def update_droplets(self, now: datetime) -> None:
        """Update the state of the droplets in the simulation.

        Args:
            now: The current datetime for simulation timing.

        This function handles:
        - Removing droplets that have reached the edges of the field.
        - Moving droplets down, sideways, and swapping their positions.
        - Generating new droplets at the top of the field.
        """
        field = self.field

        # Remove droplets at the edges of the field
        for y in range(HEIGHT):
            if is_liquid_color(field[y][0]):
                field[y][0] = COLOR_BACKGROUND
            if is_liquid_color(field[y][WIDTH - 1]):
                field[y][WIDTH - 1] = COLOR_BACKGROUND
        for x in range(WIDTH):
            if field[HEIGHT][x] == COLOR_BACKGROUND and is_liquid_color(field[HEIGHT - 1][x]):
                field[HEIGHT - 1][x] = COLOR_BACKGROUND

        # Move droplets
        droplets_go_down(field)
        move_pick = pop_pick(self.dropMovePicks, DROPLET_MOVE_INTERVAL)
        swap_pick = pop_pick(self.dropSwapPicks, DROPLET_SWAP_INTERVAL)
        for y in range(HEIGHT, -1, -1):
            for x in range(1, WIDTH - 1):
                p = y + x
                r = False
                if p % DROPLET_MOVE_INTERVAL == move_pick:
                    r = droplet_move(field, x, y)
                if not r and p % DROPLET_SWAP_INTERVAL == swap_pick:
                    _ = droplet_swap(field, x, y)

        # Generate new droplets
        t: int = self.frameCount % DROPLET_DROP_INTERVAL
        if t < DROPLET_DROP_SIZE:
            if t == 0:
                self.dropX = WIDTH - THRUHOLE_WIDTH - 1 - random.randrange(DIGIT_PIXEL_SIZE * 4) - 1
            c = self.pick_liquid_color(now)
            field[0][self.dropX] = c

    def update_terrain_by_cursor(self, cursor_pos: Tuple[int, int], button_clicked: int) -> None:
        """Update the terrain based on cursor interaction.

        Allows the user to modify the terrain by clicking with the mouse.
        Left-click sets the cell to WALL_COLOR, right-click sets it to background.

        Args:
            cursor_pos: The (x, y) coordinates of the cursor on the field.
            button_clicked: An integer representing the clicked mouse button
                (1 for left-click, 3 for right-click).
        """
        x, y = cursor_pos
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            self.cover[y][x] = 0
            if button_clicked == 1:  # Left-click: set to WALL_COLOR
                self.field[y][x] = COLOR_WALL
            elif button_clicked == 3:  # Right-click: set to background
                if not is_liquid_color(self.field[y][x]):
                    self.field[y][x] = COLOR_BACKGROUND

    def update_droplets_by_cursor(self, cursor_pos: Tuple[int, int], cursor_move: Tuple[int, int]) -> None:
        """Update droplet positions based on cursor interaction.

        Allows dragging of liquid droplets with the mouse.  If a droplet is
        dragged to an empty space, it moves. If dragged near another droplet,
        they can swap.

        Args:
            cursor_pos: Current cursor (x,y) on the field.
            cursor_move:  The (dx,dy) movement of the cursor.
        """
        field = self.field

        x, y = cursor_pos
        if not(0 <= x < WIDTH and 0 <= y < HEIGHT):
            return
        if not is_liquid_color(field[y][x]):
            return

        vx, vy = cursor_move
        dx, dy = x + vx, y + vy
        if 0 <= dx < WIDTH and 0 <= dy < HEIGHT and field[dy][dx] == COLOR_BACKGROUND:
            field[dy][dx] = field[y][x]
            field[y][x] = COLOR_BACKGROUND
        else:
            if dx != 0:
                dests = [(x, y - 1), (x, y + 1)]
            elif vy != 0:
                dests = [(x - 1, y), (x + 1, y)]
            else:
                assert False
            random.shuffle(dests)
            for dx, dy in dests:
                if 0 <= dx < WIDTH and 0 <= dy < HEIGHT and is_liquid_color(field[dy][dx]):
                    field[y][x], field[dy][dx] = field[dy][dx], field[y][x]
                    break  # for dx, dy

    def update(
        self,
        now: Optional[datetime] = None,
        cursor_pos: Optional[Tuple[int, int]] = None,
        cursor_move: Optional[Tuple[int, int]] = None,
        button_clicked: Optional[int] = None,
    ) -> None:
        """Update the simulation state by updating the field and colon,
        optionally handling mouse pointer interactions and click events.

        Args:
            now: The current datetime for simulation timing; if None, uses current system time.
            cursor_pos: The current field coordinates of the mouse pointer.
            cursor_move: The movement direction of the mouse pointer.
            button_clicked: If not None, indicates the mouse button that was clicked
                            (e.g. 1 for left-click, 3 for right-click). If None, no click occurred.
        """
        self.prevFields.append([row[:] for row in self.field])
        if len(self.prevFields) > 2:
            self.prevFields.pop(0)
        self.frameCount += 1

        if now is None:
            now = datetime.now()

        self.update_terrain(now)
        self.update_droplets(now)

        if cursor_pos is not None:
            if button_clicked is not None:
                self.update_terrain_by_cursor(cursor_pos, button_clicked)
            elif cursor_move is not None:
                self.update_droplets_by_cursor(cursor_pos, cursor_move)


class GUIColorConfig:
    def __init__(self, color_scheme: str = "default"):
        self.BASE_COLOR_1 = (0x4a, 0xac, 0xda)  # blue
        self.ACCENT_COLOR_1 = (0xd9, 0xd4, 0x5d)
        self.BASE_COLOR_2 = (0xe0, 0x34, 0x4a)  # red
        self.ACCENT_COLOR_2 = (0xd9, 0xd4, 0x5d)
        self.BASE_COLOR_3 = (0x49, 0xb0, 0xd8)  # green
        self.ACCENT_COLOR_3 = (0xd9, 0xd4, 0x5d)
        self.PALETTE: Dict[int, Tuple[int, int, int]] = {
            11: self.BASE_COLOR_1,
            12: modify_v(self.BASE_COLOR_1, 0.1),
            13: self.ACCENT_COLOR_1,

            21: modify_v(self.BASE_COLOR_2, -0.1),
            22: self.BASE_COLOR_2,
            23: self.ACCENT_COLOR_2,
        }
        if color_scheme == "default":
            self.PALETTE |= {
                COLOR_BACKGROUND: (0xC0, 0xC0, 0xC0),
                COLOR_WALL: (0x20, 0x20, 0x20),
                COLOR_COVER: (0x24, 0x24, 0x24),
            }
        elif color_scheme == "light":
            self.PALETTE |= {
                COLOR_BACKGROUND: (0x40, 0x40, 0x40),
                COLOR_WALL: (0xf0, 0xf0, 0xf0),
                COLOR_COVER: (0xea, 0xea, 0xea),
            }
        elif color_scheme == "dark":
            self.PALETTE |= {
                COLOR_BACKGROUND: (0x40, 0x40, 0x40),
                COLOR_WALL: (0x10, 0x10, 0x10),
                COLOR_COVER: (0x12, 0x12, 0x12),
            }
        self.LIQUID_COLOR_BASES: List[int] = [11, 21]

    def pick_liquid_color(self, frame_count: int, now: Optional[datetime] = None) -> int:
        if now is None:
            return self.LIQUID_COLOR_BASES[0]

        if 2 <= now.hour < 4:
            c = self.LIQUID_COLOR_BASES[1]
            if frame_count % 100 >= 85:
                c += 1
        else:
            c = self.LIQUID_COLOR_BASES[0]
            if frame_count % 8000 == 3:
                c += 2
            elif frame_count % 100 >= 85:
                c += 1
        return c


# --- Pygame Version Class ---
class AppPygame(BaseApp):
    def __init__(self, acceleration: int = 1, add_hours: int = 0, theme: str = "default") -> None:
        """Initialize the Pygame-based simulation."""
        super().__init__()
        self.acceleration = acceleration
        self.add_hours = add_hours
        self.color_config = GUIColorConfig(theme)
        self.prev_raw_mouse_pos: Optional[Tuple[int, int]] = None
        self.window_width: int = WIDTH * 10
        self.window_height: int = HEIGHT * 10

        pygame.init()

        self.screen = pygame.display.set_mode((self.window_width, self.window_height), pygame.RESIZABLE)
        pygame.display.set_caption("Water Clock v" + __version__)
        pygame.display.set_allow_screensaver(True)

        icon_path = find_icon_file("icon32.png")
        if icon_path is not None:
            icon = pygame.image.load(icon_path)
            pygame.display.set_icon(icon)

    def update_canvas_size(self) -> None:
        """Update the canvas size from the current window size."""
        width, height = self.screen.get_rect().size
        self.window_width = width
        self.window_height = height

    def draw(self) -> None:
        """Draw the current simulation field using Pygame."""
        palette = self.color_config.PALETTE
        clock_surface = pygame.Surface((WIDTH, HEIGHT))
        clock_surface.fill(palette[COLOR_BACKGROUND])
        for y in range(HEIGHT):
            for x in range(WIDTH):
                c: int = self.cover[y][x]
                if c == 0:
                    c = self.field[y][x]
                    if c == COLOR_BACKGROUND:
                        for f in self.prevFields[::-1]:
                            if is_liquid_color(f[y][x]):
                                c = f[y][x]
                if c != COLOR_BACKGROUND:
                    color: Tuple[int, int, int] = palette.get(c, (255, 255, 255))
                    clock_surface.fill(color, pygame.Rect(x, y, 1, 1))

        final_scale: float = min(self.window_width / WIDTH, self.window_height / HEIGHT)
        dest_width: int = int(WIDTH * final_scale)
        dest_height: int = int(HEIGHT * final_scale)
        scaled_surface = pygame.transform.scale(clock_surface, (dest_width, dest_height))
        self.screen.fill((0, 0, 0))
        offset_x: int = (self.window_width - dest_width) // 2
        offset_y: int = (self.window_height - dest_height) // 2
        self.screen.blit(scaled_surface, (offset_x, offset_y))

    def get_field_coordinates(self, raw_pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """Convert raw screen coordinates to simulation field coordinates.

        Args:
            raw_pos: The (x, y) position on the window.

        Returns:
            A tuple (field_x, field_y) if the position is within the drawn area,
            or None if the mouse is outside.
        """
        final_scale: float = min(self.window_width / WIDTH, self.window_height / HEIGHT)
        dest_width: int = int(WIDTH * final_scale)
        dest_height: int = int(HEIGHT * final_scale)
        offset_x: int = (self.window_width - dest_width) // 2
        offset_y: int = (self.window_height - dest_height) // 2
        mx, my = raw_pos
        if mx < offset_x or mx >= offset_x + dest_width or my < offset_y or my >= offset_y + dest_height:
            return None
        field_x: int = int((mx - offset_x) / final_scale)
        field_y: int = int((my - offset_y) / final_scale)
        if field_x < 0 or field_x >= WIDTH or field_y < 0 or field_y >= HEIGHT:
            return None
        return (field_x, field_y)

    def run(self) -> None:
        now: datetime = datetime.now()
        if self.add_hours != 0:
            self.init_field(now + timedelta(hours=self.add_hours))
        else:
            self.init_field(now)

        start_time = now
        clock = pygame.time.Clock()

        running: bool = True
        while running:
            raw_mouse_pos: Optional[Tuple[int, int]] = None
            clicked: Optional[int] = None
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.WINDOWRESIZED:
                    self.update_canvas_size()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    raw_mouse_pos = event.pos
                    clicked = event.button
                elif event.type == pygame.MOUSEMOTION:
                    raw_mouse_pos = event.pos
                    if event.buttons[0]:
                        clicked = 1
                    if event.buttons[2]:
                        clicked = 3

            move: Optional[Tuple[int, int]] = None
            pos: Optional[Tuple[int, int]] = None
            if raw_mouse_pos is not None:
                if self.prev_raw_mouse_pos is not None:
                    dx = raw_mouse_pos[0] - self.prev_raw_mouse_pos[0]
                    dy = raw_mouse_pos[1] - self.prev_raw_mouse_pos[1]
                    if abs(dx) > abs(dy):
                        move = (-1 if dx < 0 else 1, 0)
                    elif abs(dy) > abs(dx):
                        move = (0, -1 if dy < 0 else 1)
                pos = self.get_field_coordinates(raw_mouse_pos)
                self.prev_raw_mouse_pos = raw_mouse_pos

            if self.acceleration == 1:
                now: datetime = datetime.now()
                if self.add_hours != 0:
                    now += timedelta(hours=self.add_hours)
                self.update(now=now, cursor_pos=pos, cursor_move=move, button_clicked=clicked)
                self.draw()
                pygame.display.flip()
                clock.tick(FRAME_RATE)
            else:
                elapsed: timedelta = datetime.now() - start_time
                simulated_seconds: float = elapsed.total_seconds() * self.acceleration
                simulated_time: datetime = start_time + timedelta(seconds=simulated_seconds)
                if self.add_hours != 0:
                    simulated_time += timedelta(hours=self.add_hours)
                self.update(now=simulated_time, cursor_pos=pos, cursor_move=move, button_clicked=clicked)
                self.draw()
                pygame.display.flip()
                clock.tick(FRAME_RATE * self.acceleration)
        pygame.quit()
        sys.exit()

    def pick_liquid_color(self, now: Optional[datetime] = None) -> int:
        return self.color_config.pick_liquid_color(self.frameCount, now)


# --- PyQt5 version application class ---
class AppPyQt(BaseApp, QMainWindow):
    def __init__(self, theme: str = "default", load_geometry: bool = False):
        BaseApp.__init__(self)
        QMainWindow.__init__(self)

        self._resizing = False
        self._dragPos = None
        self.initUI()

        self.color_config = GUIColorConfig(theme)

        if load_geometry:
            r = load_window_geometry()
            if r is not None:
                x, y, width, height = r
                self.setGeometry(x, y, width, height)
        else:
            self.setGeometry(100, 100, WIDTH * 10, HEIGHT * 10)

        self.init_field(datetime.now())

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.simulation_step)
        self.timer.start(1000 // FRAME_RATE)

    def initUI(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)

        # Grip widget for resize
        grip = QSizeGrip(self)
        grip.setStyleSheet("background-color: rgba(100, 100, 255, 150);")
        layout.addWidget(grip, 0, Qt.AlignBottom | Qt.AlignRight)

        self.setWindowTitle("Water Clock v" + __version__)

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def closeEvent(self, event):
        geom = self.geometry()
        save_window_geometry(geom.x(), geom.y(), geom.width(), geom.height())
        event.accept()

    def resizeEvent(self, event):
        if self._resizing:
            return super().resizeEvent(event)
        self._resizing = True

        target_ratio = WIDTH / HEIGHT
        new_width = max(100, event.size().width())
        new_height = max(50, event.size().height())
        current_ratio = new_width / new_height if new_height != 0 else target_ratio

        if current_ratio > target_ratio:
            new_width = int(new_height * target_ratio)
        else:
            new_height = int(new_width / target_ratio)

        self.resize(new_width, new_height)

        self._resizing = False
        return super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragPos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragPos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._dragPos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragPos = None

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Escape, Qt.Key_Q):
            self.close()
        else:
            super().keyPressEvent(event)

    def simulation_step(self):
        now = datetime.now()
        self.update(now)
        self.repaint()

    def paintEvent(self, event):
        palette: Dict[int, Tuple[int, int, int]] = self.color_config.PALETTE

        qcolor_cache = {}

        def get_color(color_code):
            if color_code not in qcolor_cache:
                rgb = palette.get(color_code, (250, 250, 250))
                if color_code in [COLOR_WALL, COLOR_COVER]:
                    alpha = 255
                elif color_code == COLOR_BACKGROUND:
                    alpha = 128
                else:
                    alpha = 230
                qcolor_cache[color_code] = QColor(*rgb, alpha)
            return qcolor_cache[color_code]

        painter = QPainter(self)
        img = QImage(WIDTH, HEIGHT, QImage.Format_ARGB32)

        img.fill(get_color(COLOR_BACKGROUND))

        for y in range(HEIGHT):
            for x in range(WIDTH):
                c = self.cover[y][x]
                if c == 0:
                    c = self.field[y][x]
                    if c == COLOR_BACKGROUND:
                        for f in reversed(self.prevFields):
                            if is_liquid_color(f[y][x]):
                                c = f[y][x]
                                break
                if c != COLOR_BACKGROUND:
                    color = get_color(c)
                    img.setPixelColor(x, y, color)

        scale = min(self.width() / WIDTH, self.height() / HEIGHT)
        offset_x = (self.width() - int(WIDTH * scale)) // 2
        offset_y = (self.height() - int(HEIGHT * scale)) // 2

        painter.save()
        painter.translate(offset_x, offset_y)
        painter.scale(scale, scale)
        painter.drawImage(0, 0, img)
        painter.restore()

    def pick_liquid_color(self, now: Optional[datetime] = None) -> int:
        return self.color_config.pick_liquid_color(self.frameCount, now)


# --- Curses Version Class ---
class AppCurses(BaseApp):
    LIQUID_COLOR_BASE = 8

    def __init__(self, curses_module, stdscr) -> None:
        """Initialize the curses-based simulation.

        Args:
            curses_module: The curses module.
            stdscr: The curses standard screen.
        """
        super().__init__()
        self.curses = curses_module
        self.stdscr = stdscr
        curses_module.curs_set(0)
        self.stdscr.nodelay(True)
        self.stdscr.timeout(0)
        curses_module.mousemask(0)  # Disable mouse processing
        curses_module.start_color()

        # Simple color mapping (simulation color -> curses color)
        self.color_map: Dict[int, Tuple[int, int]] = {
            COLOR_BACKGROUND: (curses_module.COLOR_WHITE, curses_module.COLOR_WHITE),

            8: (curses_module.COLOR_CYAN, curses_module.COLOR_CYAN),
            9: (curses_module.COLOR_BLUE, curses_module.COLOR_BLUE),
            10: (curses_module.COLOR_RED, curses_module.COLOR_RED),

            COLOR_WALL: (curses_module.COLOR_BLACK, curses_module.COLOR_BLACK),
            COLOR_COVER: (curses_module.COLOR_BLACK, curses_module.COLOR_BLACK),
        }

        self.color_pairs: Dict[int, Any] = {}
        pair_number: int = 1
        for sim_color, (fg, bg) in self.color_map.items():
            try:
                curses_module.init_pair(pair_number, fg, bg)
            except curses_module.error:
                curses_module.init_pair(pair_number, curses_module.COLOR_WHITE, curses_module.COLOR_BLACK)
            self.color_pairs[sim_color] = curses_module.color_pair(pair_number)
            pair_number += 1
        self.stdscr.clear()

    def get_screen_offsets(self) -> Tuple[int, int, int]:
        """Calculate the offsets for centering the simulation in the terminal.

        Returns:
            A tuple (offset_y, offset_x, horz_scale), where horz_scale is 2 if the terminal is wide enough,
            otherwise 1.
        """
        max_y, max_x = self.stdscr.getmaxyx()
        # If the width is sufficient, draw each simulation pixel as 2 characters wide.
        horz_scale: int = 2 if max_x >= WIDTH * 2 else 1
        offset_y: int = (max_y - HEIGHT) // 2 if max_y >= HEIGHT else 0
        offset_x: int = (max_x - (WIDTH * horz_scale)) // 2 if max_x >= WIDTH * horz_scale else 0
        return offset_y, offset_x, horz_scale

    def draw(self) -> None:
        """Draw the simulation field using curses."""
        curses = self.curses
        self.stdscr.erase()
        offset_y, offset_x, horz_scale = self.get_screen_offsets()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                c: int = self.cover[y][x]
                if c == 0:
                    c = self.field[y][x]
                    if c == COLOR_BACKGROUND:
                        for prev in reversed(self.prevFields):
                            if is_liquid_color(prev[y][x]):
                                c = prev[y][x]
                                break
                attr = self.color_pairs.get(c, curses.A_NORMAL)
                # Draw using "."; if horz_scale is 2, draw ".."
                text: str = "." * horz_scale
                try:
                    self.stdscr.addstr(offset_y + y, offset_x + x * horz_scale, text, attr)
                except curses.error:
                    pass
        self.stdscr.refresh()

    def run(self) -> None:
        """Run the simulation using curses."""
        now: datetime = datetime.now()
        self.init_field(now)

        start_time = time.time()  # sec
        frame_count = 0

        running: bool = True
        while running:
            try:
                key: int = self.stdscr.getch()
                if key == ord("q"):
                    running = False
                # Mouse events are ignored.
            except Exception:
                pass
            now: datetime = datetime.now()
            self.update(now)
            self.draw()

            frame_count += 1
            wait_until = start_time + frame_count / FRAME_RATE # sec
            t = time.time()
            if t < wait_until:
                time.sleep(wait_until - t)
            else:
                start_time = t
                frame_count = 0

    def pick_liquid_color(self, now: Optional[datetime] = None) -> int:
        c = self.LIQUID_COLOR_BASE

        if now is None:
            return c

        if self.frameCount % 8000 == 3:
            c += 2
        elif self.frameCount % 100 >= 85:
            c += 1
        return c


# --- Main Entry Point ---
def main() -> None:
    """Main entry point for the Water Clock simulation.

    Use the --curses command-line option to run the curses version,
    otherwise the Pygame version is started.
    """
    parser = argparse.ArgumentParser(description="Water Clock Simulation")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--curses", action="store_true", help="Use curses for terminal rendering.")
    group.add_argument("--pygame", action="store_true", help="Use Pygame as GUI framework.")
    parser.add_argument(
        "--theme",
        type=str,
        choices=["default", "dark", "light"],
        default="default",
        help="Color theme (choose from 'default', 'dark', or 'light')."
    )
    parser.add_argument(
        "-a", "--acceleration", type=int, default=1, help="Acceleration factor for simulation time (default: 1)."
    )
    parser.add_argument("--add-hours", type=int, default=0, help="Modify start time.")
    parser.add_argument("-g", "--load-geometry", action="store_true", help="Restore window position and size on startup.")
    parser.add_argument("--generate-desktop", action="store_true",
                        help="Generate a .desktop file in the current directory")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)

    args = parser.parse_args()
    if not args.pygame:
        if args.acceleration != 1:
            parser.error("--acceleration is only valid when --pygame is specified")
        if args.add_hours != 0:
            parser.error("--add-hours is only valid when --pygame is specified")

    if args.pygame or args.curses:
        if args.load_geometry:
            parser.error("--load-geometry is invalid when either --pygame or --curses is specified")

    if args.generate_desktop:
        generate_desktop_file(theme=args.theme, load_geometry=args.load_geometry)
        sys.exit(0)

    os.makedirs(CACHE_DIR, exist_ok=True)

    if args.curses:
        import curses

        curses.wrapper(lambda stdscr: AppCurses(curses, stdscr).run())
    elif args.pygame:
        app = AppPygame(acceleration=args.acceleration, add_hours=args.add_hours, theme=args.theme)
        app.run()
    else:
        app = QApplication(sys.argv)
        icon_path = find_icon_file("icon.ico")
        if icon_path is not None:
            app.setWindowIcon(QIcon(icon_path))

        window = AppPyQt(theme=args.theme, load_geometry=args.load_geometry)
        window.show()
        sys.exit(app.exec_())


if __name__ == "__main__":
    main()
