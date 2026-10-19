#!/usr/bin/env python3
"""테트리스 — ← → 이동 · ↑ 회전 · ↓ 한 칸 · Space 바로 내리기 · c 보관 · p 멈춤 · q 닫기.

`python3 tetris.py --selftest` 로 충돌·회전·줄 지우기를 점검한다.
"""
import curses
import locale
import os
import random
import subprocess
import sys
import time

from _lang import L
from memo import put  # 한글 2칸 폭을 맞춰 그리고, 창 끝에서 잘라 준다

W, H = 10, 20
# 조각: (상자 크기, 칸들 (x, y))
PIECES = {
    'I': (4, [(0, 1), (1, 1), (2, 1), (3, 1)]),
    'O': (2, [(0, 0), (1, 0), (0, 1), (1, 1)]),
    'T': (3, [(1, 0), (0, 1), (1, 1), (2, 1)]),
    'S': (3, [(1, 0), (2, 0), (0, 1), (1, 1)]),
    'Z': (3, [(0, 0), (1, 0), (1, 1), (2, 1)]),
    'J': (3, [(0, 0), (0, 1), (1, 1), (2, 1)]),
    'L': (3, [(2, 0), (0, 1), (1, 1), (2, 1)]),
}
COLOR = {'I': 6, 'O': 3, 'T': 5, 'S': 2, 'Z': 1, 'J': 4, 'L': 7}  # curses 기본 색 번호
SCORE = [0, 100, 300, 500, 800]


def rot(cells, n):
    """시계 방향 90도."""
    return [(n - 1 - y, x) for x, y in cells]


class Game:
    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.board = [[None] * W for _ in range(H)]
        self.bag = []
        self.score = self.lines = 0
        self.over = False
        self.held = None  # 보관함 — 최대 1개
        self.can_hold = True  # 블럭 하나가 떨어지는 동안 보관은 한 번만
        self.next = self.draw()
        self.spawn()

    @property
    def level(self):
        return self.lines // 10 + 1

    def gravity(self):
        return max(0.08, 0.8 * 0.85 ** (self.level - 1))

    def draw(self):
        if not self.bag:
            self.bag = list(PIECES)
            self.rng.shuffle(self.bag)
        return self.bag.pop()

    def spawn(self):
        self.kind, self.next = self.next, self.draw()
        self.place()

    def place(self):
        self.n, cells = PIECES[self.kind]
        self.cells = list(cells)
        self.x, self.y = (W - self.n) // 2, 0
        if self.hit(self.cells, self.x, self.y):
            self.over = True

    def hit(self, cells, x, y):
        return any(not (0 <= x + cx < W and y + cy < H) or (y + cy >= 0 and self.board[y + cy][x + cx])
                   for cx, cy in cells)

    def hold(self):
        """지금 블럭을 보관한다. 비어 있으면 넣고 다음 블럭을, 차 있으면 맞바꾼다."""
        if not self.can_hold:
            return
        if self.held is None:
            self.held = self.kind
            self.spawn()
        else:
            self.held, self.kind = self.kind, self.held
            self.place()
        self.can_hold = False

    def move(self, dx):
        if not self.hit(self.cells, self.x + dx, self.y):
            self.x += dx

    def rotate(self):
        cells = rot(self.cells, self.n)
        for kick in (0, -1, 1, -2, 2):  # 벽에 붙어 있으면 옆으로 밀어 본다
            if not self.hit(cells, self.x + kick, self.y):
                self.cells, self.x = cells, self.x + kick
                return

    def down(self):
        """한 칸 내린다. 못 내리면 굳히고 False."""
        if not self.hit(self.cells, self.x, self.y + 1):
            self.y += 1
            return True
        self.lock()
        return False

    def drop(self):
        while self.down():
            self.score += 2

    def ghost_y(self):
        y = self.y
        while not self.hit(self.cells, self.x, y + 1):
            y += 1
        return y

    def lock(self):
        for cx, cy in self.cells:
            if self.y + cy >= 0:
                self.board[self.y + cy][self.x + cx] = self.kind
        kept = [row for row in self.board if not all(row)]
        cleared = H - len(kept)
        self.board = [[None] * W for _ in range(cleared)] + kept
        self.score += SCORE[cleared] * self.level
        self.lines += cleared
        self.can_hold = True
        self.spawn()


def main(scr):
    curses.curs_set(0)
    scr.keypad(True)
    curses.mousemask(curses.ALL_MOUSE_EVENTS)
    curses.mouseinterval(0)
    curses.start_color()
    curses.use_default_colors()
    for c in range(1, 8):
        curses.init_pair(c, c, -1)

    pairs = {}

    def half(fg, bg):
        """반높이 칸용 (글자색, 배경색) 쌍 — 처음 쓸 때 만든다."""
        if (fg, bg) not in pairs:
            pairs[(fg, bg)] = n = 8 + len(pairs)
            curses.init_pair(n, fg, bg)
        return curses.color_pair(pairs[(fg, bg)])

    ghost_color = 8 if curses.COLORS > 8 else 7  # 회색이 없으면 흰색

    g = Game()
    paused = False
    fall_at = time.time() + g.gravity()
    close_btn = (0, 0, 0)
    while True:
        h, w = scr.getmaxyx()
        scr.erase()
        # cmux 3번 패널(19줄)처럼 판(22줄)이 안 들어가면 ▀▄ 로 두 줄을 한 줄에 그린다 — 판 12줄
        compact = h < H + 2
        bw, bh = (W, H // 2) if compact else (2 * W, H)
        if h < bh + 2 or w < bw + 22:
            put(scr, 0, 0, L(f'창이 작습니다 ({H // 2 + 2}줄 필요) — q 닫기', f'Window too small (needs {H // 2 + 2} rows) — q to close'))
        else:
            ox = 1
            scr.addstr(0, ox, '┌' + '─' * bw + '┐')
            scr.addstr(bh + 1, ox, '└' + '─' * bw + '┘')
            cur = {(g.x + cx, g.y + cy) for cx, cy in g.cells}
            ghost = {(g.x + cx, g.ghost_y() + cy) for cx, cy in g.cells}

            def color(x, y):
                kind = g.board[y][x] or (g.kind if (x, y) in cur else None)
                if kind:
                    return COLOR[kind]
                return ghost_color if (x, y) in ghost and not g.over else None

            for y in range(bh):
                scr.addstr(y + 1, ox, '│')
                for x in range(W):
                    if compact:
                        top, bot = color(x, 2 * y), color(x, 2 * y + 1)
                        if top and bot:
                            scr.addstr(y + 1, ox + 1 + x, '▀', half(top, bot))
                        elif top or bot:
                            scr.addstr(y + 1, ox + 1 + x, '▀' if top else '▄', half(top or bot, -1))
                    else:
                        kind = g.board[y][x] or (g.kind if (x, y) in cur else None)
                        if kind:
                            scr.addstr(y + 1, ox + 1 + 2 * x, '██', curses.color_pair(COLOR[kind]))
                        elif (x, y) in ghost and not g.over:
                            scr.addstr(y + 1, ox + 1 + 2 * x, '░░', curses.A_DIM)
                scr.addstr(y + 1, ox + 1 + bw, '│')
            sx = ox + bw + 4
            put(scr, 1, sx, L('다음', 'Next'))
            n, cells = PIECES[g.next]
            for cx, cy in cells:
                scr.addstr(3 + cy, sx + 2 * cx, '██', curses.color_pair(COLOR[g.next]))
            put(scr, 6, sx, L('보관 c', 'Hold c'), curses.A_NORMAL if g.can_hold else curses.A_DIM)
            if g.held:
                for cx, cy in PIECES[g.held][1]:
                    scr.addstr(8 + cy, sx + 2 * cx, '██',
                               curses.color_pair(COLOR[g.held]) | (0 if g.can_hold else curses.A_DIM))
            put(scr, 11, sx, L('점수  ', 'Score ') + str(g.score))
            put(scr, 12, sx, L('줄    ', 'Lines ') + str(g.lines))
            put(scr, 13, sx, L('레벨  ', 'Level ') + str(g.level))
            for i, t in enumerate(L(('←→ 이동  ↑ 회전', '↓ 한 칸  Space 바로', 'c 보관  p 멈춤', 'q 닫기'),
                                    ('←→ move  ↑ rotate', '↓ step  Space drop', 'c hold  p pause', 'q close'))):
                put(scr, 15 + i, sx, t, curses.A_DIM)
            cy = min(H, h - 1)
            close_btn = (cy, sx, sx + 9)
            put(scr, cy, sx, '[ close ]', curses.A_BOLD | curses.A_REVERSE)
            if g.over:
                put(scr, bh // 2, ox + 1, L(' 게임 오버 · r 다시 ', ' Game over · r retry'), curses.A_REVERSE)
            elif paused:
                put(scr, bh // 2, ox + 1, L(' 멈춤 · p ', ' Paused · p '), curses.A_REVERSE)
        scr.refresh()

        wait = 0.5 if (paused or g.over) else max(0.0, fall_at - time.time())
        scr.timeout(int(wait * 1000))
        key = scr.getch()
        if key in (ord('q'), 27):
            break
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, b = curses.getmouse()
                if b & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED) and my == close_btn[0] \
                        and close_btn[1] <= mx < close_btn[2]:
                    break
            except curses.error:
                pass
            continue
        if g.over:
            if key == ord('r'):
                g = Game()
                fall_at = time.time() + g.gravity()
            continue
        if key == ord('p'):
            paused = not paused
            fall_at = time.time() + g.gravity()
            continue
        if paused:
            continue
        if key == curses.KEY_LEFT:
            g.move(-1)
        elif key == curses.KEY_RIGHT:
            g.move(1)
        elif key == curses.KEY_UP:
            g.rotate()
        elif key == curses.KEY_DOWN:
            if g.down():
                g.score += 1
            fall_at = time.time() + g.gravity()
        elif key in (ord('c'), ord('C')):
            g.hold()
            fall_at = time.time() + g.gravity()
        elif key == ord(' '):
            g.drop()
            fall_at = time.time() + g.gravity()
        if time.time() >= fall_at:
            g.down()
            fall_at = time.time() + g.gravity()


def selftest():
    g = Game(random.Random(1))
    # 회전: T 를 네 번 돌리면 제자리
    t = PIECES['T'][1]
    assert sorted(rot(rot(rot(rot(t, 3), 3), 3), 3)) == sorted(t)
    assert sorted(rot(t, 3)) == [(1, 0), (1, 1), (1, 2), (2, 1)]
    # 벽: 왼쪽 끝 너머로 못 간다
    g.kind, g.n, g.cells, g.x, g.y = 'I', 4, list(PIECES['I'][1]), 0, 0
    g.move(-1)
    assert g.x == 0
    # 세로 I 를 왼쪽 벽에 붙여 돌리면 밀려 들어온다
    g.cells, g.x = rot(g.cells, 4), -2  # 세로 I 는 x=2 열에 있어 실제로는 0열
    assert not g.hit(g.cells, g.x, g.y)
    g.rotate()
    assert not g.hit(g.cells, g.x, g.y)
    # 줄 지우기: 맨 아래 줄을 한 칸 빼고 채우고 I 를 세워 떨어뜨리면 한 줄이 지워진다
    g = Game(random.Random(2))
    g.board[H - 1] = ['Z'] * (W - 1) + [None]
    g.board[H - 2][0] = 'S'
    g.kind, g.n, g.cells, g.x, g.y = 'I', 4, rot(PIECES['I'][1], 4), W - 3, 0  # 세로 I → 9열
    g.drop()
    assert g.lines == 1 and g.score >= 100
    assert g.board[H - 1][0] == 'S' and g.board[H - 1][W - 1] == 'I'  # 위 줄이 내려왔다
    # 보관: 빈 보관함엔 넣고 다음 블럭이 나온다 → 같은 블럭 동안 다시 보관 불가 → 굳으면 다시 가능, 맞바꾼다
    g = Game(random.Random(4))
    first, nxt = g.kind, g.next
    g.hold()
    assert g.held == first and g.kind == nxt and not g.can_hold
    g.hold()
    assert g.held == first and g.kind == nxt  # 한 번만
    g.drop()  # 굳힘 → 새 블럭, 보관 다시 가능
    assert g.can_hold
    cur = g.kind
    g.hold()
    assert g.held == cur and g.kind == first and (g.y, g.x) == (0, (W - PIECES[first][0]) // 2)
    # 꼭대기까지 차면 게임 오버
    g = Game(random.Random(3))
    for y in range(H):
        g.board[y] = ['O'] * W
    g.spawn()
    assert g.over
    print('tetris selftest ok')


def grow_pane():
    """3번 패널은 20줄 남짓이라 판(테두리 포함 22줄)이 안 들어간다 — 게임 동안만 24줄로 키우고 되돌린다.
    갈아 끼워져 되돌리지 못하면 @pt_h 에 남은 높이를 mod 의 openSlot 이 되돌린다."""
    pane = os.environ.get('TMUX_PANE')
    if not pane:
        return lambda: None
    tmux = lambda *a: subprocess.run(['tmux', *a], capture_output=True, text=True).stdout.strip()
    h = tmux('display', '-p', '-t', pane, '#{pane_height}')
    if not h.isdigit() or int(h) >= H + 2:
        return lambda: None
    tmux('set', '-p', '-t', pane, '@pt_h', h)
    tmux('resize-pane', '-t', pane, '-y', '24')

    def restore():
        tmux('resize-pane', '-t', pane, '-y', h)
        tmux('set', '-pu', '-t', pane, '@pt_h')
    return restore


if __name__ == '__main__':
    if sys.argv[1:] == ['--selftest']:
        selftest()
    else:
        locale.setlocale(locale.LC_ALL, '')
        os.environ.setdefault('ESCDELAY', '25')
        restore = grow_pane()
        try:
            curses.wrapper(main)
        finally:
            restore()
