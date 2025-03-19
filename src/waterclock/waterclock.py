import argparse
from datetime import datetime, timedelta
import random
import sys

import pygame

try:
    from .__about__ import __version__
except ImportError:
    __version__ = "(unknown)"

# --- 定数 ---
DIGIT_DISP_ZOOM = 3
WIDTH = (1 + 4 * 4) * DIGIT_DISP_ZOOM  # 51
HEIGHT = 7 * DIGIT_DISP_ZOOM  # 21
WALL_COLOR = 13
SINKHOLE_OPENING_PERIOD = 30
LIQUID_MOVE_INTERVAL = 4
LIQUID_SEP_INTERVAL = 120
LIQUID_DROP_SIZE = 2
LIQUID_DROP_INTERVAL = 14

LIQUID_COLOR_POPULATION = {1: 150, 3: 850, 4: 1}
LIQUID_COLORS = list(LIQUID_COLOR_POPULATION.keys())
LIQUID_COLOR_QUEUE = []
for c, p in LIQUID_COLOR_POPULATION.items():
    LIQUID_COLOR_QUEUE.extend([c] * p)
random.shuffle(LIQUID_COLOR_QUEUE)

# パレット（16進カラー→RGB）
PALETTE = {
    0: (0xC0, 0xC0, 0xC0),  # 背景
    1: (0x84, 0xC2, 0xDA),  # 水1
    2: (0x81, 0xB8, 0xCF),  # 水2
    3: (0x4C, 0xA4, 0xC4),  # 水3
    4: (0xF3, 0x8C, 0x79),  # 水4
    13: (0x20, 0x20, 0x20),  # 壁
}

# 数字パターン（0～9）
DIGIT_PATTERN_STRS = [
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


# --- ユーティリティ関数 ---
def create_field():
    # 上部：DIGIT_DISP_ZOOM行は背景（0）
    field = [[0] * WIDTH for _ in range(1 * DIGIT_DISP_ZOOM)]
    # 中間部：DIGIT_DISP_ZOOM～HEIGHT行は壁色
    field += [[WALL_COLOR] * WIDTH for _ in range(DIGIT_DISP_ZOOM, HEIGHT)]
    # 一番下の行
    field.append([0] * WIDTH)
    return field


def put_sinkhole(field, pos):
    x_indices = [(1 + pos * 4 + i) * DIGIT_DISP_ZOOM + 1 for i in [0, 2]]
    for x in x_indices:
        for y in range(6 * DIGIT_DISP_ZOOM, 7 * DIGIT_DISP_ZOOM):
            if field[y][x] == WALL_COLOR:
                field[y][x] = 0


def put_digit(field, pos, digit):
    # 数字描画部分の壁をクリア
    for y in range(0, 6 * DIGIT_DISP_ZOOM):
        for x in range((1 + pos * 4) * DIGIT_DISP_ZOOM, (1 + pos * 4 + 3) * DIGIT_DISP_ZOOM):
            if field[y][x] == WALL_COLOR:
                field[y][x] = 0
    # 下部の行は壁で上書き
    for y in range(6 * DIGIT_DISP_ZOOM, 7 * DIGIT_DISP_ZOOM):
        for x in range((1 + pos * 4) * DIGIT_DISP_ZOOM, (1 + pos * 4 + 3) * DIGIT_DISP_ZOOM):
            field[y][x] = WALL_COLOR
    # 数字パターンを反映（パターン中 "0" 部分に壁色をセット）
    dp = DIGIT_PATTERN_STRS[digit].strip().split("\n")
    for dy in range(5):
        for dx in range(3):
            if dp[dy][dx] == "0":
                for y in range((1 + dy) * DIGIT_DISP_ZOOM, (1 + dy + 1) * DIGIT_DISP_ZOOM):
                    for x in range((1 + pos * 4 + dx) * DIGIT_DISP_ZOOM, (1 + pos * 4 + dx + 1) * DIGIT_DISP_ZOOM):
                        field[y][x] = WALL_COLOR


def liquid_separate(field, x, y, prefer_x):
    c = field[y][x]
    if c not in LIQUID_COLORS:
        return
    wx, wy = 0, 0
    for dy in range(-2, 3):
        yy = y + dy
        if yy < 0 or yy >= len(field):
            continue
        for dx in range(-2, 3):
            xx = x + dx
            if xx < 0 or xx >= len(field[0]):
                continue
            dist = abs(dx) + abs(dy)
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


# --- シミュレーション本体 ---
class App:
    def __init__(self):
        self.field = create_field()
        self.prev_fields = []

        now = datetime.now()
        h = now.hour
        m = now.minute
        self.dispDigits = [h // 10, h % 10, m // 10, m % 10]
        for p in range(4):
            put_digit(self.field, p, self.dispDigits[p])
        self.dispDigitsUpdateCountdown = -1
        self.dispDigitsUpdatePoss = []
        self.dropAccel = 0
        self.dropX = 0
        self.dropMovePicks = []
        self.dropSepPicks = []
        self.liquidColorIndex = 0
        self.frameCount = 0

        # 初期ウィンドウサイズ（リサイズ可能フラグ付き）
        self.window_width = WIDTH * 10
        self.window_height = HEIGHT * 10
        self.screen = pygame.display.set_mode((self.window_width, self.window_height), pygame.RESIZABLE)
        pygame.display.set_caption("Water Clock")

    def update_canvas_size(self):
        width, height = self.screen.get_rect().size
        self.window_width = width
        self.window_height = height

    def field_update(self, now=None):
        if now is None:
            now = datetime.now()
        h = now.hour
        m = now.minute

        # 文字盤を更新
        ds = [h // 10, h % 10, m // 10, m % 10]
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

        # 画面の端に来た水滴は除去する
        for y in range(HEIGHT):
            if self.field[y][0] in LIQUID_COLORS:
                self.field[y][0] = 0
            if self.field[y][WIDTH - 1] in LIQUID_COLORS:
                self.field[y][WIDTH - 1] = 0
        for x in range(WIDTH):
            if self.field[HEIGHT][x] == 0 and self.field[HEIGHT - 1][x] in LIQUID_COLORS:
                self.field[HEIGHT - 1][x] = 0

        # 水滴移動のタイミング調整用のデータ生成
        if not self.dropMovePicks:
            picks = []
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

        dpMove = self.dropMovePicks.pop() if self.dropMovePicks else 0
        dsPick = self.dropSepPicks.pop() if self.dropSepPicks else 0
        dsPreferX = random.randint(0, 1) == 0

        # 水滴の移動（左右移動、落下、分離）
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
                c = self.field[y][x]
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

        # 水滴の生成
        t = self.frameCount % (LIQUID_DROP_SIZE * (LIQUID_DROP_INTERVAL - self.dropAccel))
        if t < LIQUID_DROP_SIZE:
            if t == 0:
                self.dropX = WIDTH - 1 - random.randrange(DIGIT_DISP_ZOOM * 4) - 1
                self.liquidColorIndex = (self.liquidColorIndex + 1) % len(LIQUID_COLOR_QUEUE)
            self.field[0][self.dropX] = LIQUID_COLOR_QUEUE[self.liquidColorIndex]

    def update(self, now=None):
        self.prev_fields.append([row[:] for row in self.field])
        if len(self.prev_fields) > 2:
            self.prev_fields.pop(0)
        self.frameCount += 1
        self.field_update(now=now)

    def draw(self):
        # 内部サーフェス（論理解像度 WIDTH×HEIGHT）に1セル1ピクセルで描画
        clock_surface = pygame.Surface((WIDTH, HEIGHT))
        clock_surface.fill(PALETTE[0])
        if self.dropAccel != 0:
            font = pygame.font.SysFont(None, 16)
            s = ("-" * (-self.dropAccel)) if self.dropAccel < 0 else ("+" * self.dropAccel)
            text_surface = font.render(s, True, (255, 255, 255))
            clock_surface.blit(text_surface, (0, 16))
        for y in range(HEIGHT):
            for x in range(WIDTH):
                c = self.field[y][x]
                # もし現在が背景（0）であれば、前フレームの同じ位置が水滴ならその水滴色を使用
                if c == 0:
                    for f in self.prev_fields[::-1]:
                        if f[y][x] in LIQUID_COLORS:
                            c = f[y][x]
                if c > 0:
                    color = PALETTE.get(c, (255, 255, 255))
                    clock_surface.fill(color, pygame.Rect(x, y, 1, 1))

        # 内部サーフェスをウィンドウ内にアスペクト比維持で拡大
        final_scale = min(self.window_width / WIDTH, self.window_height / HEIGHT)
        dest_width = int(WIDTH * final_scale)
        dest_height = int(HEIGHT * final_scale)
        scaled_surface = pygame.transform.scale(clock_surface, (dest_width, dest_height))

        # ウィンドウ全体を黒で塗り、中央に配置（letterbox）
        self.screen.fill((0, 0, 0))
        offset_x = (self.window_width - dest_width) // 2
        offset_y = (self.window_height - dest_height) // 2
        self.screen.blit(scaled_surface, (offset_x, offset_y))


def waterclock_main(acceleration: int):
    pygame.init()
    app = App()
    clock = pygame.time.Clock()
    running = True

    if acceleration == 1:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.WINDOWRESIZED:
                    app.update_canvas_size()
            app.update()
            app.draw()
            pygame.display.flip()
            clock.tick(20)  # 約20FPS
    else:
        start_time = datetime.now()

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.WINDOWRESIZED:
                    app.update_canvas_size()

            # 経過実時間に加速度を乗じたシミュレーション時刻を生成
            elapsed = datetime.now() - start_time
            simulated_seconds = elapsed.total_seconds() * acceleration
            simulated_time = start_time + timedelta(seconds=simulated_seconds)

            app.update(now=simulated_time)
            app.draw()
            pygame.display.flip()
            clock.tick(20 * acceleration)

    pygame.quit()
    sys.exit()


def main():
    parser = argparse.ArgumentParser(description="Water Clock Simulation Test with Acceleration")
    parser.add_argument(
        "-a", "--acceleration", type=int, default=1, help="Acceleration factor for simulation time (default: 1)"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    waterclock_main(acceleration=args.acceleration)


if __name__ == "__main__":
    main()
