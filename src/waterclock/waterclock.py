#!/usr/bin/env python3
import argparse
from datetime import datetime, timedelta
import random
import sys
import time
from typing import Dict, List, Optional, Tuple

try:
    from .__about__ import __version__
except ImportError:
    __version__ = "(unknown)"

# --- Constants ---
DIGIT_DISP_ZOOM: int = 3
WIDTH: int = (1 + 4 * 4) * DIGIT_DISP_ZOOM  # 51
HEIGHT: int = 7 * DIGIT_DISP_ZOOM  # 21
WALL_COLOR: int = 16
SINKHOLE_OPENING_PERIOD: int = 35
LIQUID_MOVE_INTERVAL: int = 4
LIQUID_SEP_INTERVAL: int = 120
LIQUID_DROP_SIZE: int = 2
LIQUID_DROP_INTERVAL: int = 14

LIQUID_COLOR_POPULATION: Dict[int, int] = {8: 150, 10: 850, 11: 1}
LIQUID_COLORS: List[int] = list(LIQUID_COLOR_POPULATION.keys())
LIQUID_COLOR_QUEUE: List[int] = []
for c, p in LIQUID_COLOR_POPULATION.items():
    LIQUID_COLOR_QUEUE.extend([c] * p)
random.shuffle(LIQUID_COLOR_QUEUE)

# PALETTE (for pygame: RGB)
PALETTE: Dict[int, Tuple[int, int, int]] = {
    0: (0xC0, 0xC0, 0xC0),  # Background
    8: (0x84, 0xC2, 0xDA),  # Water 1
    9: (0x81, 0xB8, 0xCF),  # Water 2
    10: (0x4C, 0xA4, 0xC4),  # Water 3
    11: (0xF3, 0x8C, 0x79),  # Water 4
    16: (0x20, 0x20, 0x20),  # Wall
}

# Digit pattern strings (for 0 to 9)
DIGIT_PATTERN_STRS: List[str] = [
    "111\n101\n101\n101\n111\n",  # 0
    "001\n001\n001\n001\n001\n",  # 1
    "111\n001\n111\n100\n111\n",  # 2
    "111\n001\n111\n001\n111\n",  # 3
    "101\n101\n111\n001\n001\n",  # 4
    "111\n100\n111\n001\n111\n",  # 5
    "111\n100\n111\n101\n111\n",  # 6
    "111\n101\n001\n001\n001\n",  # 7
    "111\n101\n111\n101\n111\n",  # 8
    "111\n101\n111\n001\n111\n",  # 9
]

# Colon drawing positions (separator between hour and minute)
COLON_X: int = 2 * 4 * DIGIT_DISP_ZOOM + DIGIT_DISP_ZOOM // 2
COLON_Y1: int = 2 * DIGIT_DISP_ZOOM + DIGIT_DISP_ZOOM // 2
COLON_Y2: int = 4 * DIGIT_DISP_ZOOM + DIGIT_DISP_ZOOM // 2


# --- Utility Functions ---
def create_field() -> List[List[int]]:
    """Create the simulation field.

    The field is a 2D grid initialized with background and wall colors.
    The upper part is set to background (0) and the middle part to wall color.
    Also draws the colon separators initially as background.

    Returns:
        A 2D list of integers representing the field.
    """
    field: List[List[int]] = []
    # Upper part: DIGIT_DISP_ZOOM rows as background (0)
    for y in range(1 * DIGIT_DISP_ZOOM):
        field.append([0] * WIDTH)
    # Middle part: rows from DIGIT_DISP_ZOOM to HEIGHT as wall color
    for y in range(DIGIT_DISP_ZOOM, HEIGHT):
        field.append([WALL_COLOR] * WIDTH)
    # Bottom row: background (0)
    field.append([0] * WIDTH)

    # Initially, draw the colon as background (0)
    field[COLON_Y1][COLON_X] = 0
    field[COLON_Y2][COLON_X] = 0
    return field


def put_sinkhole(field: List[List[int]], pos: int) -> None:
    """Clear parts of the wall for a digit container at the specified position.

    Args:
        field: The simulation field.
        pos: The digit position (0-3) to update.
    """
    x_indices = [(1 + pos * 4 + 0) * DIGIT_DISP_ZOOM + 1, (1 + pos * 4 + 2) * DIGIT_DISP_ZOOM + 1]
    for x in x_indices:
        for y in range(6 * DIGIT_DISP_ZOOM, 7 * DIGIT_DISP_ZOOM):
            if field[y][x] == WALL_COLOR:
                field[y][x] = 0


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
    for y in range(1 * DIGIT_DISP_ZOOM, 6 * DIGIT_DISP_ZOOM):
        for x in range((1 + pos * 4) * DIGIT_DISP_ZOOM, (1 + pos * 4 + 3) * DIGIT_DISP_ZOOM):
            if field[y][x] == WALL_COLOR:
                field[y][x] = 0
    # Overwrite the bottom row with wall color
    for y in range(6 * DIGIT_DISP_ZOOM, 7 * DIGIT_DISP_ZOOM):
        for x in range((1 + pos * 4) * DIGIT_DISP_ZOOM, (1 + pos * 4 + 3) * DIGIT_DISP_ZOOM):
            field[y][x] = WALL_COLOR
    # Reflect the digit pattern (set wall color where the pattern has "0")
    dp: List[str] = DIGIT_PATTERN_STRS[digit].strip().split("\n")
    for dy in range(5):
        for dx in range(3):
            if dp[dy][dx] == "0":
                for y in range((1 + dy) * DIGIT_DISP_ZOOM, (1 + dy + 1) * DIGIT_DISP_ZOOM):
                    for x in range((1 + pos * 4 + dx) * DIGIT_DISP_ZOOM, (1 + pos * 4 + dx + 1) * DIGIT_DISP_ZOOM):
                        field[y][x] = WALL_COLOR


def liquid_separate(field: List[List[int]], x: int, y: int, prefer_x: bool) -> None:
    """Separate a liquid droplet to simulate its movement.

    Calculates a weighted displacement based on neighboring cells and
    swaps the droplet with an adjacent cell accordingly.

    Args:
        field: The simulation field.
        x: The x-coordinate of the droplet.
        y: The y-coordinate of the droplet.
        prefer_x: Whether to prefer horizontal movement over vertical.
    """
    c: int = field[y][x]
    if c not in LIQUID_COLORS:
        return
    wx: int = 0
    wy: int = 0
    for dy in range(-2, 3):
        yy: int = y + dy
        if yy < 0 or yy >= len(field):
            continue
        for dx in range(-2, 3):
            xx: int = x + dx
            if xx < 0 or xx >= len(field[0]):
                continue
            dist: int = abs(dx) + abs(dy)
            if not (1 <= dist <= 3):
                continue
            if field[yy][xx] == c:
                wx += dx
                wy += dy
    wx = max(-1, min(1, wx))
    wy = max(-1, min(1, wy))
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


# --- Base Simulation Class ---
class BaseApp:
    def __init__(self) -> None:
        """Initialize the simulation state."""
        self.field: List[List[int]] = create_field()
        self.prev_fields: List[List[List[int]]] = []
        now: datetime = datetime.now()
        h: int = now.hour
        m: int = now.minute
        self.dispDigits: List[int] = [h // 10, h % 10, m // 10, m % 10]
        for p in range(4):
            put_digit(self.field, p, self.dispDigits[p])
        self.dispDigitsUpdateCountdown: int = -1
        self.dispDigitsUpdatePoss: List[int] = []
        self.dropAccel: int = 0
        self.dropX: int = 0
        self.dropMovePicks: List[int] = []
        self.dropSepPicks: List[int] = []
        self.liquidColorIndex: int = 0
        self.frameCount: int = 0

    def update_colon(self, now: Optional[datetime] = None) -> None:
        """Update the colon separator between hour and minute.

        The colon alternates its state every 3 seconds (using WALL_COLOR and background)
        so that it does not interfere with the moving droplets.

        Args:
            now: The current datetime. If None, the current system time is used.
        """
        if now is None:
            now = datetime.now()

        if now.second % 6 < 3:
            # If in the first 3 seconds of a 6-second period, draw the colon with WALL_COLOR.
            for y in [COLON_Y1, COLON_Y2]:
                if self.field[y][COLON_X] != WALL_COLOR:
                    self.field[y][COLON_X] = WALL_COLOR
        else:
            # Otherwise, clear the colon (set to background 0).
            for y in [COLON_Y1, COLON_Y2]:
                if self.field[y][COLON_X] == WALL_COLOR:
                    self.field[y][COLON_X] = 0

    def field_update(self, now: Optional[datetime] = None) -> None:
        """Update the simulation field.

        This includes updating the displayed digits, moving droplets,
        and performing other field maintenance such as clearing droplets on edges.

        Args:
            now: The current datetime for simulation timing. If None, uses current system time.
        """
        if now is None:
            now = datetime.now()
        h: int = now.hour
        m: int = now.minute
        ds: List[int] = [h // 10, h % 10, m // 10, m % 10]
        if ds != self.dispDigits:
            self.dispDigitsUpdateCountdown = SINKHOLE_OPENING_PERIOD
            self.dispDigitsUpdatePoss = []
            for p in range(4):
                if ds[p] != self.dispDigits[p]:
                    put_sinkhole(self.field, p)
                    self.dispDigitsUpdatePoss.append(p)
            self.dispDigits = ds
        if self.dispDigitsUpdateCountdown >= 0:
            self.dispDigitsUpdateCountdown -= 1
            if self.dispDigitsUpdateCountdown == 0:
                for p in self.dispDigitsUpdatePoss:
                    put_digit(self.field, p, self.dispDigits[p])
        # Remove droplets at the edges of the field
        for y in range(HEIGHT):
            if self.field[y][0] in LIQUID_COLORS:
                self.field[y][0] = 0
            if self.field[y][WIDTH - 1] in LIQUID_COLORS:
                self.field[y][WIDTH - 1] = 0
        for x in range(WIDTH):
            if self.field[HEIGHT][x] == 0 and self.field[HEIGHT - 1][x] in LIQUID_COLORS:
                self.field[HEIGHT - 1][x] = 0
        # Prepare timing data for droplet movement
        if not self.dropMovePicks:
            picks: List[int] = []
            for i in range(LIQUID_MOVE_INTERVAL):
                for _ in range(5):
                    picks.append(i)
            random.shuffle(picks)
            self.dropMovePicks = picks
        if not self.dropSepPicks:
            picks = []
            for i in range(LIQUID_SEP_INTERVAL):
                for _ in range(5):
                    picks.append(i)
            random.shuffle(picks)
            self.dropSepPicks = picks
        dpMove: int = self.dropMovePicks.pop() if self.dropMovePicks else 0
        dsPick: int = self.dropSepPicks.pop() if self.dropSepPicks else 0
        dsPreferX: bool = random.randint(0, 1) == 0
        # Move droplets
        for y in range(HEIGHT, -1, -1):
            for x in range(1, WIDTH - 1):
                if self.field[y][x] in LIQUID_COLORS:
                    if y + 1 < len(self.field) and self.field[y + 1][x] <= 0:
                        self.field[y + 1][x] = self.field[y][x]
                        self.field[y][x] = 0
                    elif y + 1 < len(self.field) and self.field[y + 1][x] in LIQUID_COLORS:
                        if dsPreferX:
                            if x + 1 < WIDTH and self.field[y + 1][x + 1] <= 0:
                                self.field[y + 1][x + 1] = self.field[y][x]
                                self.field[y][x] = 0
                        else:
                            if x - 1 >= 0 and self.field[y + 1][x - 1] <= 0:
                                self.field[y + 1][x - 1] = self.field[y][x]
                                self.field[y][x] = 0
                c: int = self.field[y][x]
                if c in LIQUID_COLORS:
                    if (y + x) % LIQUID_MOVE_INTERVAL == dpMove:
                        if self.field[y][x - 1] > 0 and self.field[y][x + 1] <= 0:
                            self.field[y][x + 1] = c
                            self.field[y][x] = 0
                        elif self.field[y][x + 1] > 0 and self.field[y][x - 1] <= 0:
                            self.field[y][x - 1] = c
                            self.field[y][x] = 0
                    elif (y + x) % LIQUID_SEP_INTERVAL == dsPick:
                        liquid_separate(self.field, x, y, dsPreferX)
        # Generate new droplets
        t: int = self.frameCount % (LIQUID_DROP_SIZE * (LIQUID_DROP_INTERVAL - self.dropAccel))
        if t < LIQUID_DROP_SIZE:
            if t == 0:
                self.dropX = WIDTH - 1 - random.randrange(DIGIT_DISP_ZOOM * 4) - 1
                self.liquidColorIndex = (self.liquidColorIndex + 1) % len(LIQUID_COLOR_QUEUE)
            self.field[0][self.dropX] = LIQUID_COLOR_QUEUE[self.liquidColorIndex]

    def update(self, now: Optional[datetime] = None) -> None:
        """Update the simulation state by updating the field and colon."""
        self.prev_fields.append([row[:] for row in self.field])
        if len(self.prev_fields) > 2:
            self.prev_fields.pop(0)
        self.frameCount += 1
        self.field_update(now)
        self.update_colon(now)


# --- Pygame Version Class ---
class AppPygame(BaseApp):
    def __init__(self, pygame_module) -> None:
        """Initialize the Pygame-based simulation."""
        super().__init__()
        self.pygame = pygame_module
        pygame_module.init()
        self.window_width: int = WIDTH * 10
        self.window_height: int = HEIGHT * 10
        self.screen = pygame_module.display.set_mode((self.window_width, self.window_height), pygame_module.RESIZABLE)
        pygame_module.display.set_caption("Water Clock v" + __version__)

    def update_canvas_size(self) -> None:
        """Update the canvas size from the current window size."""
        width, height = self.screen.get_rect().size
        self.window_width = width
        self.window_height = height

    def handle_mouse(self, pos: Tuple[int, int], button: int) -> None:
        """Handle mouse click events to change cell states.

        Right-click sets the cell to WALL_COLOR, left-click sets it to background (0).

        Args:
            pos: The (x, y) position of the mouse click.
            button: The mouse button (1 for left, 3 for right).
        """
        final_scale: float = min(self.window_width / WIDTH, self.window_height / HEIGHT)
        dest_width: int = int(WIDTH * final_scale)
        dest_height: int = int(HEIGHT * final_scale)
        offset_x: int = (self.window_width - dest_width) // 2
        offset_y: int = (self.window_height - dest_height) // 2
        mx, my = pos
        if mx < offset_x or mx >= offset_x + dest_width or my < offset_y or my >= offset_y + dest_height:
            return
        field_x: int = int((mx - offset_x) / final_scale)
        field_y: int = int((my - offset_y) / final_scale)
        if field_x < 0 or field_x >= WIDTH or field_y < 0 or field_y >= HEIGHT:
            return
        if button == 3:  # Right-click: set to WALL_COLOR
            self.field[field_y][field_x] = WALL_COLOR
        elif button == 1:  # Left-click: set to background (0)
            self.field[field_y][field_x] = 0

    def draw(self) -> None:
        """Draw the current simulation field using Pygame."""
        pygame = self.pygame
        clock_surface = pygame.Surface((WIDTH, HEIGHT))
        clock_surface.fill(PALETTE[0])
        for y in range(HEIGHT):
            for x in range(WIDTH):
                c: int = self.field[y][x]
                if c == 0:
                    for f in self.prev_fields[::-1]:
                        if f[y][x] in LIQUID_COLORS:
                            c = f[y][x]
                if c > 0:
                    color: Tuple[int, int, int] = PALETTE.get(c, (255, 255, 255))
                    clock_surface.fill(color, pygame.Rect(x, y, 1, 1))
        final_scale: float = min(self.window_width / WIDTH, self.window_height / HEIGHT)
        dest_width: int = int(WIDTH * final_scale)
        dest_height: int = int(HEIGHT * final_scale)
        scaled_surface = pygame.transform.scale(clock_surface, (dest_width, dest_height))
        self.screen.fill((0, 0, 0))
        offset_x: int = (self.window_width - dest_width) // 2
        offset_y: int = (self.window_height - dest_height) // 2
        self.screen.blit(scaled_surface, (offset_x, offset_y))

    def run(self, acceleration: int = 1) -> None:
        """Run the simulation using Pygame.

        Args:
            acceleration: The simulation acceleration factor.
        """
        pygame = self.pygame
        clock = pygame.time.Clock()
        running: bool = True
        if acceleration == 1:
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.WINDOWRESIZED:
                        self.update_canvas_size()
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        self.handle_mouse(event.pos, event.button)
                    elif event.type == pygame.MOUSEMOTION:
                        if event.buttons[0]:
                            self.handle_mouse(event.pos, 1)
                        if event.buttons[2]:
                            self.handle_mouse(event.pos, 3)
                self.update()
                self.draw()
                pygame.display.flip()
                clock.tick(20)
        else:
            start_time: datetime = datetime.now()
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.WINDOWRESIZED:
                        self.update_canvas_size()
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        self.handle_mouse(event.pos, event.button)
                    elif event.type == pygame.MOUSEMOTION:
                        if event.buttons[0]:
                            self.handle_mouse(event.pos, 1)
                        if event.buttons[2]:
                            self.handle_mouse(event.pos, 3)
                elapsed = datetime.now() - start_time
                simulated_seconds: float = elapsed.total_seconds() * acceleration
                simulated_time: datetime = start_time + timedelta(seconds=simulated_seconds)
                self.update(simulated_time)
                self.draw()
                pygame.display.flip()
                clock.tick(20 * acceleration)
        pygame.quit()
        sys.exit()


# --- Curses Version Class ---
class AppCurses(BaseApp):
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
            0: (curses_module.COLOR_WHITE, curses_module.COLOR_WHITE),
            8: (curses_module.COLOR_CYAN, curses_module.COLOR_CYAN),
            9: (curses_module.COLOR_BLUE, curses_module.COLOR_BLUE),
            10: (curses_module.COLOR_BLUE, curses_module.COLOR_BLUE),
            11: (curses_module.COLOR_RED, curses_module.COLOR_RED),
            16: (curses_module.COLOR_BLACK, curses_module.COLOR_BLACK),
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
                c: int = self.field[y][x]
                if c == 0:
                    for prev in reversed(self.prev_fields):
                        if prev[y][x] in LIQUID_COLORS:
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
    args = parser.parse_args()
    if args.curses:
        import curses

        curses.wrapper(lambda stdscr: AppCurses(curses, stdscr).run())
    else:
        import pygame

        app = AppPygame(pygame)
        app.run(acceleration=args.acceleration)


if __name__ == "__main__":
    main()
