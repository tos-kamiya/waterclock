import argparse
import colorsys
from datetime import datetime, timedelta
import random
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    from .__about__ import __version__
except ImportError:
    __version__ = "(unknown)"

# --- Constants ---
DIGIT_PIXEL_SIZE: int = 3
THRUHOLE_WIDTH: int = 4
WIDTH: int = (1 + 4 * 4) * DIGIT_PIXEL_SIZE + THRUHOLE_WIDTH
HEIGHT: int = 7 * DIGIT_PIXEL_SIZE

SINKHOLE_OPENING_PERIOD: int = 40
SINKHOLE_EXTENSION: Dict[int, int] = {0: 5, 1: 6, 2: -7, 3: 5, 4: 12, 5: 12, 6: -4, 7: 14, 8: -14, 9: 12}
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
    "111\n111\n001\n001\n001\n",  # 7
    "111\n101\n111\n101\n111\n",  # 8
    "111\n101\n111\n001\n111\n",  # 9
    "000\n010\n000\n010\n000\n",  # Cover
]
DIGIT_BITMAPS: List[List[List[int]]] = [
    [[int(n) for n in ss] for ss in s.strip().split("\n")] for s in DIGIT_BITMAP_STRINGS
]

# --- Utility Functions ---
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


def droplet_go_down(field: List[List[int]], x: int, y: int) -> bool:
    """Simulate the downward movement of a droplet.

    If the cell below is empty, the droplet moves down. If the cell below
    is occupied by another liquid, it attempts to move diagonally.

    Args:
        field: The simulation field.
        x: The x-coordinate of the droplet.
        y: The y-coordinate of the droplet.

    Returns:
        True if the droplet moved, False otherwise.
    """
    c: int = field[y][x]
    if not is_liquid_color(c):
        return False
    if y >= HEIGHT:
        return False

    if y + 1 < HEIGHT and field[y + 1][x] == COLOR_BACKGROUND:
        field[y + 1][x] = c
        field[y][x] = COLOR_BACKGROUND
        return True
    elif y + 1 < HEIGHT and is_liquid_color(field[y + 1][x]):
        dx = x + random.choice([-1, 1])
        if field[y + 1][dx] == COLOR_BACKGROUND:
            if field[y][dx] == COLOR_BACKGROUND:
                field[y + 1][dx] = c
                field[y][x] = COLOR_BACKGROUND
                return True
            elif is_liquid_color(field[y + 1][x]):
                field[y + 1][dx] = field[y + 1][x]
                field[y + 1][x] = c
                field[y][x] = COLOR_BACKGROUND
                return True
    return False


def droplet_swap(field: List[List[int]], x: int, y: int) -> bool:
    """Swap movement of liquid droplets.

    Calculates a weighted displacement based on neighboring cells and
    swaps the droplet with an adjacent cell accordingly.

    Args:
        field: The simulation field.
        x: The x-coordinate of the droplet.
        y: The y-coordinate of the droplet.
    """
    def count_same_droplets(x: int, y: int):
        c: int = field[y][x]
        vxvys = [(-1, 0), (1, 0), (0, -1), (0, 1)]
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

    if random.randrange(2) == 0:
        dx, dy = x + random.choice([-1, 1]), y
    else:
        dx, dy = x, y + random.choice([-1, 1])
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

    c: int = field[y][x]
    if not is_liquid_color(c):
        return False

    if field[y][x - 1] != COLOR_BACKGROUND and field[y][x + 1] == COLOR_BACKGROUND:
        field[y][x + 1] = c
        field[y][x] = COLOR_BACKGROUND
        return True
    elif field[y][x + 1] != COLOR_BACKGROUND and field[y][x - 1] == COLOR_BACKGROUND:
        field[y][x - 1] = c
        field[y][x] = COLOR_BACKGROUND
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
        move_pick = pop_pick(self.dropMovePicks, DROPLET_MOVE_INTERVAL)
        swap_pick = pop_pick(self.dropSwapPicks, DROPLET_SWAP_INTERVAL)
        for y in range(HEIGHT, -1, -1):
            for x in range(1, WIDTH - 1):
                r = droplet_go_down(field, x, y)
                if not r and (y + x) % DROPLET_MOVE_INTERVAL == move_pick:
                    r = droplet_move(field, x, y)
                if not r and (y + x) % DROPLET_SWAP_INTERVAL == swap_pick:
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


# --- Pygame Version Class ---
class AppPygame(BaseApp):
    BASE_COLOR_1 = (0x4a, 0xac, 0xda)  # blue
    ACCENT_COLOR_1 = (0xd9, 0xd4, 0x5d)
    BASE_COLOR_2 = (0xe0, 0x34, 0x4a)  # red
    ACCENT_COLOR_2 = (0xd9, 0xd4, 0x5d)
    BASE_COLOR_3 = (0x49, 0xb0, 0xd8)  # green
    ACCENT_COLOR_3 = (0xd9, 0xd4, 0x5d)
    PALETTE: Dict[int, Tuple[int, int, int]] = {
        COLOR_BACKGROUND: (0xC0, 0xC0, 0xC0),  # Background

        11: BASE_COLOR_1,
        12: modify_v(BASE_COLOR_1, 0.1),
        13: ACCENT_COLOR_1,

        21: modify_v(BASE_COLOR_2, -0.1),
        22: BASE_COLOR_2,
        23: ACCENT_COLOR_2,

        COLOR_WALL: (0x20, 0x20, 0x20),  # Wall
        COLOR_COVER: (0x24, 0x24, 0x24),  # Cover
    }
    LIQUID_COLOR_BASES: List[int] = [11, 21]

    def __init__(self, pygame_module) -> None:
        """Initialize the Pygame-based simulation."""
        super().__init__()
        self.pygame = pygame_module
        pygame_module.init()
        self.window_width: int = WIDTH * 10
        self.window_height: int = HEIGHT * 10
        self.screen = pygame_module.display.set_mode((self.window_width, self.window_height), pygame_module.RESIZABLE)
        pygame_module.display.set_caption("Water Clock v" + __version__)
        pygame_module.display.set_allow_screensaver(True)
        self.prev_raw_mouse_pos: Optional[Tuple[int, int]] = None

    def update_canvas_size(self) -> None:
        """Update the canvas size from the current window size."""
        width, height = self.screen.get_rect().size
        self.window_width = width
        self.window_height = height

    def draw(self) -> None:
        """Draw the current simulation field using Pygame."""
        pygame = self.pygame
        clock_surface = pygame.Surface((WIDTH, HEIGHT))
        clock_surface.fill(self.PALETTE[0])
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
                    color: Tuple[int, int, int] = self.PALETTE.get(c, (255, 255, 255))
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

    def run(self, acceleration: int = 1, add_hours: int = 0) -> None:
        """Run the simulation using Pygame.

        Args:
            acceleration: The simulation acceleration factor.
        """
        pygame = self.pygame

        now: datetime = datetime.now()
        if add_hours != 0:
            self.init_field(now + timedelta(hours=add_hours))
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

            if acceleration == 1:
                now: datetime = datetime.now()
                if add_hours != 0:
                    now += timedelta(hours=add_hours)
                self.update(now=now, cursor_pos=pos, cursor_move=move, button_clicked=clicked)
                self.draw()
                pygame.display.flip()
                clock.tick(20)
            else:
                elapsed: timedelta = datetime.now() - start_time
                simulated_seconds: float = elapsed.total_seconds() * acceleration
                simulated_time: datetime = start_time + timedelta(seconds=simulated_seconds)
                if add_hours != 0:
                    simulated_time += timedelta(hours=add_hours)
                self.update(now=simulated_time, cursor_pos=pos, cursor_move=move, button_clicked=clicked)
                self.draw()
                pygame.display.flip()
                clock.tick(20 * acceleration)
        pygame.quit()
        sys.exit()

    def pick_liquid_color(self, now: Optional[datetime] = None) -> int:
        if now is None:
            return self.LIQUID_COLOR_BASES[0]

        if 1 <= now.hour < 3:
            c = self.LIQUID_COLOR_BASES[1]
            if self.frameCount % 100 >= 85:
                c += 1
        else:
            c = self.LIQUID_COLOR_BASES[0]
            if self.frameCount % 8000 == 3:
                c += 2
            elif self.frameCount % 100 >= 85:
                c += 1
        return c


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

        running: bool = True
        fps: int = 20
        frame_delay: float = 1.0 / fps
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
            time.sleep(frame_delay)

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
    parser = argparse.ArgumentParser(description="Water Clock Simulation with Pygame or Curses")
    parser.add_argument("--curses", action="store_true", help="Use curses for terminal rendering")
    parser.add_argument(
        "-a", "--acceleration", type=int, default=1, help="Acceleration factor for simulation time (default: 1)"
    )
    parser.add_argument("--add-hours", type=int, default=0)
    args = parser.parse_args()
    if args.curses:
        import curses

        curses.wrapper(lambda stdscr: AppCurses(curses, stdscr).run())
    else:
        import pygame

        app = AppPygame(pygame)
        app.run(acceleration=args.acceleration, add_hours=args.add_hours)


if __name__ == "__main__":
    main()
