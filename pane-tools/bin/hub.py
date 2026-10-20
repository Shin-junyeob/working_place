#!/usr/bin/env python3
"""모드 허브 — /mods 가 띄운다(`--session <id>` · `--follow-pane <tmux 대상>`, 자식 도구엔 환경변수로 넘긴다).

위: 따라가는 세션(memo.current_target)의 컨텍스트·비용·사용 한도 게이지(각 세션의 pane-tools mod 가 2초마다 적는 값).
아래: 이 폴더(bin/)의 도구마다 버튼 하나 — 새 모드는 여기에 <이름>.py 를 두면 [<이름>] 버튼이 저절로 생긴다.
버튼을 누르면 그 도구가 이 패널에서 돌고, 끝나면 허브로 돌아온다.
`python3 hub.py --selftest` 로 버튼 목록·게이지 계산을 점검한다.
"""
import argparse
import base64
import curses
import fcntl
import importlib
import json
import locale
import math
import os
import re
import select
import struct
import subprocess
import sys
import termios
import threading
import time
import tty

BIN = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BIN)
import memo  # noqa: E402 — 세션 따라가기·한글 폭 계산을 같이 쓴다
import _lang  # noqa: E402
import _pokedata  # noqa: E402 — 동료 그림(Kitty 용 PNG · Sixel · ▀▄ 용 256색)
from _lang import L, toggle  # noqa: E402
try:
    import pokemon  # noqa: E402 — 메인 화면에 동료 포켓몬을 띄운다
except Exception:  # 포켓몬이 깨져도 허브는 뜬다
    pokemon = None

USAGE = os.path.expanduser('~/.claude/pane-tools/usage')


def tools(folder=BIN):
    """버튼이 될 도구들: bin/ 의 .py 중 허브 자신과 _ 로 시작하는 것 빼고, 이름순."""
    return sorted(f[:-3] for f in os.listdir(folder)
                  if f.endswith('.py') and f != 'hub.py' and not f.startswith('_'))


def bar(frac, width):
    filled = round(max(0.0, min(1.0, frac)) * width)
    return '█' * filled + '░' * (width - filled)


_pairs = {}


def draw_sprite(scr, y, x, grid, gray=False):
    """(r, g, b) 그림을 ▀▄ 반높이 칸으로 — 한 줄에 그림 두 줄. gray 면 밝기만(포켓몬 모드의 [ 그림 c ]).
    색 쌍은 처음 쓸 때 16번부터 만든다."""
    to = _pokedata.gray256 if gray else _pokedata.xterm256
    grid = [[c and to(*c) for c in row] for row in grid]

    def pair(fg, bg):
        if (fg, bg) not in _pairs:
            if len(_pairs) + 17 >= curses.COLOR_PAIRS:  # 쌍이 모자라면 처음부터 다시 쓴다(이전 그림의 쌍)
                _pairs.clear()
            _pairs[(fg, bg)] = 16 + len(_pairs)
            curses.init_pair(_pairs[(fg, bg)], fg, bg)
        return curses.color_pair(_pairs[(fg, bg)])
    for r in range(0, len(grid), 2):
        bot = grid[r + 1] if r + 1 < len(grid) else [None] * len(grid[r])
        for k, (a, b) in enumerate(zip(grid[r], bot)):
            if a is None and b is None:
                continue
            ch, attr = ('▀', pair(a, -1 if b is None else b)) if a is not None else ('▄', pair(b, -1))
            try:
                scr.addstr(y + r // 2, x + k, ch, attr)
            except curses.error:
                pass


KITTY = False  # __main__ 이 curses 를 켜기 전에 kitty_ok() 로 정한다
_sent, _placed = set(), [None]  # 터미널에 보내 둔 그림 번호들 · 지금 화면에 놓인 그림 번호


def kitty_ok():
    """터미널이 Kitty 그래픽을 지원하나 — 질의 뒤 장치 속성(DA1)보다 OK 가 먼저 오면(cmux 확인, 2026-10-20).
    tmux 안에선 통과 설정이 따로 필요해 쓰지 않는다 — 그땐 ▀▄ 로 그린다."""
    if os.environ.get('TMUX') or not sys.stdin.isatty():
        return False
    fd, got = sys.stdin.fileno(), b''
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        os.write(sys.stdout.fileno(), b'\x1b_Gi=31,s=1,v=1,a=q,t=d,f=24;AAAA\x1b\\\x1b[c')
        end = time.time() + 1
        while time.time() < end and not re.search(rb'\x1b\[\?[\d;]*c', got):
            if select.select([fd], [], [], 0.05)[0]:
                got += os.read(fd, 1024)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return b'\x1b_Gi=31;OK' in got


def kitty_cols(pw, ph, rows):
    """pw×ph 픽셀 그림을 rows 줄에 넣을 때 비율이 맞는 칸 수 — 칸의 픽셀 크기는 터미널에 묻는다(모르면 1:2)."""
    try:
        r, c, xp, yp = struct.unpack('HHHH', fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b'\0' * 8))
        ratio = (yp / r) / (xp / c) if xp and yp else 2
    except OSError:
        ratio = 2
    return max(1, round(pw / ph * rows * ratio))


def kitty_show(y, x, key, png, cols, rows):
    """PNG 를 key 번 그림으로 처음 한 번만 보내 두고, (y, x) 칸에 cols×rows 로 놓는다.
    매 화면마다 다시 놓는다 — curses 가 화면을 통째로 지워도 그림이 돌아오게(같은 자리 표시는 바꿔 끼워진다)."""
    out = []
    if _placed[0] not in (None, key):  # 동료가 바뀌면 전 그림을 내린다
        out.append(f'\x1b_Ga=d,d=i,i={_placed[0]},q=2\x1b\\')
    if key not in _sent:
        data = base64.b64encode(png).decode()
        parts = [data[i:i + 4096] for i in range(0, len(data), 4096)]  # Kitty 는 4096바이트씩 받는다
        for i, part in enumerate(parts):
            head = f'a=t,f=100,i={key},q=2,' if i == 0 else ''
            out.append(f'\x1b_G{head}m={int(i < len(parts) - 1)};{part}\x1b\\')
        _sent.add(key)
    out.append(f'\x1b7\x1b[{y + 1};{x + 1}H\x1b_Ga=p,i={key},p=1,c={cols},r={rows},C=1,q=2\x1b\\\x1b8')
    sys.stdout.write(''.join(out))
    sys.stdout.flush()
    _placed[0] = key


def kitty_hide(free=False):
    """놓인 그림을 내린다. free 면 보내 둔 데이터까지 — 다른 모드로 넘어가거나 허브를 닫을 때."""
    if free and _sent:
        sys.stdout.write('\x1b_Ga=d,d=A,q=2\x1b\\')
        _sent.clear()
    elif _placed[0] is not None:
        sys.stdout.write(f'\x1b_Ga=d,d=i,i={_placed[0]},q=2\x1b\\')
    sys.stdout.flush()
    _placed[0] = None


SIXEL = False  # 터미널이 Sixel 이미지를 받으면 True — __main__ 이 sixel_ok() 로 정한다
_six = [None]  # 화면에 그려 둔 Sixel 그림(key). 같은 그림은 다시 보내지 않는다 — 1초마다 보내면 깜빡인다


def sixel_ok():
    """장치 속성(DA1) 응답에 4(Sixel)가 있나. tmux 안이면 tmux 가 대신 답한다 — terminal-features 에 sixel 이 있어야 4.
    8칸×3줄 글자 그림으론 모양이 안 나와서(2026-10-20) Kitty 가 안 되는 터미널은 이걸로 진짜 픽셀을 그린다."""
    if not sys.stdin.isatty():
        return False
    fd, got = sys.stdin.fileno(), b''
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        os.write(sys.stdout.fileno(), b'\x1b[c')
        end = time.time() + 1
        while time.time() < end and not re.search(rb'\x1b\[\?[\d;]*c', got):
            if select.select([fd], [], [], 0.05)[0]:
                got += os.read(fd, 1024)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    m = re.search(rb'\x1b\[\?([\d;]*)c', got)
    return bool(m) and b'4' in m.group(1).split(b';')


def cell_px():
    """글자 칸 하나의 픽셀 크기(가로, 세로) — 터미널에 묻고, 모르면 10×20."""
    try:
        r, c, xp, yp = struct.unpack('HHHH', fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b'\0' * 8))
        if xp and yp:
            return xp / c, yp / r
    except OSError:
        pass
    return 10, 20


def sixel_show(y, x, key, data):
    """(y, x) 칸에 Sixel 그림을 놓는다 — 이미 같은 그림이 놓여 있으면 그대로 둔다."""
    if _six[0] == key:
        return
    sys.stdout.write(f'\x1b7\x1b[{y + 1};{x + 1}H{data}\x1b8')
    sys.stdout.flush()
    _six[0] = key


def level_attr(frac):
    return curses.color_pair(3 if frac >= 0.8 else 2 if frac >= 0.5 else 1)


def fmt_k(n):
    return f'{n / 1000:.0f}k' if n >= 1000 else str(n)


def tw(text):
    """화면 칸 폭 — 한글은 2칸."""
    return sum(memo.cw(c) for c in text)


def label(text, width=11):
    """화면 칸 기준으로 맞춘 이름표 — 한글은 2칸이라 str.ljust 로는 게이지 시작이 어긋난다."""
    return text + ' ' * max(1, width - tw(text))


def layout(labels, w, y=0, x=1):
    """버튼 자리 [(y, 시작, 끝, 글)] — 화면 칸 기준, 줄을 넘치면 두 줄 아래(숫자 표시 자리)로."""
    out = []
    for t in labels:
        if x + tw(t) >= w and x > 1:
            y, x = y + 2, 1
        out.append((y, x, x + tw(t), t))
        x += tw(t) + 2
    return out


def read_usage(sid):
    try:
        with open(f'{USAGE}/{sid}.json', encoding='utf-8') as f:
            return json.load(f), os.path.getmtime(f'{USAGE}/{sid}.json')
    except (OSError, ValueError):
        return None, 0


def main(scr):
    curses.curs_set(0)
    scr.keypad(True)
    scr.timeout(1000)
    curses.mousemask(curses.ALL_MOUSE_EVENTS)
    curses.mouseinterval(0)
    curses.start_color()
    curses.use_default_colors()
    for i, c in ((1, curses.COLOR_GREEN), (2, curses.COLOR_YELLOW), (3, curses.COLOR_RED)):
        curses.init_pair(i, c, -1)
    threading.Thread(target=memo.poll_sessions, daemon=True).start()

    global pokemon
    pk_stamp = 0
    me = os.path.abspath(__file__)
    my_stamp = seen = os.path.getmtime(me)
    seen_at = time.time()
    while True:
        # 허브 자신이 바뀌면 같은 인자로 다시 뜬다 — 오래 켜 두니 옛 코드로 남지 않게. 단 두 가지를 지킨다(2026-10-20 실측):
        # git switch → pull 사이 몇 초 동안 파일이 옛 버전이었는데 그 순간 옮겨 타서, 이 재시작 코드가 없는 옛 허브에
        # 갇혔다(그 뒤 파일이 돌아와도 모름). 그래서 파일이 5초 동안 안 바뀐 뒤에만, 그리고 새 파일에도 재시작 코드가
        # 있을 때만 옮겨 탄다.
        m = os.path.getmtime(me)
        if m != seen:
            seen, seen_at = m, time.time()
        elif m != my_stamp and time.time() - seen_at >= 5:
            with open(me, encoding='utf-8') as f:
                restartable = 'os.execv(' in f.read()
            if restartable:
                kitty_hide(free=True)
                curses.endwin()
                os.execv(sys.executable, [sys.executable, me] + sys.argv[1:])
            my_stamp = m  # 재시작 못 하는 버전이면 지금 코드로 계속 — 파일이 다시 바뀌면 그때 본다
        name, sid, busy, note = memo.current_target()
        art = art_six = None

        h, w = scr.getmaxyx()
        scr.erase()
        put = lambda y, x, t, a=0: memo.put(scr, y, x, t, a)
        head = L(' 모드 허브 → ', ' Mod hub → ') + (name or L('(없음)', '(none)')) + (L(' · 작업 중', ' · working') if busy else '')
        put(0, 0, head + ' ' * max(0, w - tw(head)), curses.A_REVERSE)

        y = 2
        bw = max(10, min(40, w - 30))
        u, at = read_usage(sid) if sid else (None, 0)
        if note:
            put(y, 1, note, curses.A_DIM)
            y += 2
        elif not u:
            put(y, 1, L('게이지 값이 아직 없습니다 — 이 세션엔 mod 가 안 붙어 있습니다(새로 연 세션부터 자동)',
                        'No gauge data yet — this session has no mod attached (new sessions get it automatically)'),
                curses.A_DIM)
            y += 2
        else:
            ctx = u.get('context') or {}
            pct = ctx.get('percent')
            if pct is None and ctx.get('tokens') and ctx.get('window'):
                pct = ctx['tokens'] / ctx['window'] * 100
            if pct is not None:
                f = pct / 100
                x = put(y, 1, label(L('컨텍스트', 'Context')))
                x = put(y, x, bar(f, bw), level_attr(f))
                tok = f' {pct:.0f}%' + (f'  {fmt_k(ctx["tokens"])}/{fmt_k(ctx["window"])}' if ctx.get('tokens') else '')
                put(y, x, tok)
                y += 1
            if u.get('cost') is not None:
                put(y, 1, label(L('비용', 'Cost')) + f'${u["cost"]:.2f}')
                y += 1
            names = {'five_hour': L('5시간 한도', '5h limit'), 'seven_day': L('7일 한도', '7d limit')}
            for r in u.get('rateLimits') or []:
                f = r.get('percentUsed', 0) / 100
                x = put(y, 1, label(names.get(r.get('kind'), r.get('kind', ''))[:10]))
                x = put(y, x, bar(f, bw), level_attr(f))
                put(y, x, f' {f * 100:.0f}%')
                y += 1
            if time.time() - at > 30 and not busy:
                put(y, 1, L(f'({int(time.time() - at)}초 전 값)', f'(as of {int(time.time() - at)}s ago)'), curses.A_DIM)
                y += 1
        y += 1

        try:
            # 허브는 오래 켜 두므로, 포켓몬 코드·데이터가 바뀌면 다시 읽는다(안 그러면 두 화면의 규칙이 어긋난다)
            stamp = max(os.path.getmtime(f) for f in (os.path.join(BIN, 'pokemon.py'), pokemon._pokedata.OUT)
                        if os.path.exists(f))
            if pokemon and stamp != pk_stamp:
                pokemon, pk_stamp = importlib.reload(pokemon), stamp
            lines = pokemon.summary() if pokemon else []
            n = pokemon.partner_id() if lines and w >= 44 else None
            gray = _lang.get('sprite') == 'gray'
            # 동료 그림: Kitty 그래픽이 되면 원본 도트를 3줄에, 아니면 ▀▄ 반높이 칸으로
            png = _pokedata.sprite_png(n, gray) if n and KITTY else None
            cw_, ch_ = cell_px()
            six = _pokedata.sprite_sixel(n, gray, int(3 * ch_)) if n and SIXEL else None
            grid = _pokedata.sprite(n) if n and not (KITTY or SIXEL) and curses.COLORS >= 256 else None
            if png or six or grid:  # 왼쪽에 동료 그림, 오른쪽엔 ' · ' 로 나눈 짧은 줄들
                top = y
                if png:
                    cols, used = kitty_cols(png[1], png[2], 3), 3
                    art = (y, 1, n * 2 + gray, png[0], cols, used)
                elif six:
                    cols, used = math.ceil(six[1] / cw_), 3
                    art_six = (y, 1, (n, gray, six[2], y), six[0])
                else:
                    cols, used = len(grid[0]), (len(grid) + 1) // 2
                    draw_sprite(scr, y, 1, grid, gray)
                sx = cols + 3
                for text, hot, frac in lines:
                    parts = text.split(' · ')
                    for i, part in enumerate(parts):
                        x = put(y, sx, part, curses.A_BOLD if hot else 0)
                        if i == len(parts) - 1 and frac is not None and not hot:
                            put(y, x + 1, bar(frac, 10), curses.A_DIM)
                        y += 1
                y = max(y, top + used)
            else:
                for text, hot, frac in lines:
                    x = put(y, 1, text, curses.A_BOLD if hot else 0)
                    if frac is not None and not hot:
                        put(y, x + 1, bar(frac, 12), curses.A_DIM)
                    y += 1
            y += 1
        except Exception:
            pass

        put(y, 1, L('모드', 'Mods'), curses.A_BOLD)
        y += 1
        mods = tools()
        buttons = []
        for i, (t, (by, x0, x1, btn)) in enumerate(zip(mods, layout([f'[ {t} ]' for t in mods], w, y)), 1):
            buttons.append((by, x0, x1, t))
            put(by, x0, btn, curses.A_BOLD | curses.A_REVERSE)
            if i < 10:
                put(by + 1, x0 + 2, str(i), curses.A_DIM)
        close, lang_btn = layout(['[ close ]', '[ 한/EN ]'], w, h - 1)
        for by, x0, x1, btn in (close, lang_btn):
            put(by, x0, btn, curses.A_BOLD | curses.A_REVERSE)
        put(h - 1, lang_btn[2] + 2, L('클릭·숫자키 · l 언어 · q 닫기', 'click/number · l lang · q close'), curses.A_DIM)
        if _six[0] is not None and (art_six is None or _six[0] != art_six[2]):
            scr.clear()  # 전 그림을 지운다 — 투명 배경이라 새 그림만 덮어쓰면 옛 점이 남는다
            _six[0] = None
        scr.refresh()
        if art_six:
            sixel_show(*art_six)
        if art:
            kitty_show(*art)
        else:
            kitty_hide()

        key = scr.getch()
        pick = None
        if key in (ord('q'), 27):
            break
        if key == curses.KEY_RESIZE:
            _six[0] = None
        if key == ord('l'):
            toggle()
            continue
        if ord('1') <= key <= ord('9') and key - ord('1') < len(buttons):
            pick = buttons[key - ord('1')][3]
        elif key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, b = curses.getmouse()
            except curses.error:
                continue
            if not b & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED):
                continue
            if my == close[0] and close[1] <= mx < close[2]:
                break
            if my == lang_btn[0] and lang_btn[1] <= mx < lang_btn[2]:
                toggle()
                continue
            pick = next((t for by, x0, x1, t in buttons if my == by and x0 <= mx < x1), None)
        if pick:
            kitty_hide(free=True)
            curses.endwin()
            subprocess.run([sys.executable, os.path.join(BIN, pick + '.py')])
            scr.clear()
            _six[0] = None  # 도구가 화면을 덮었으니 그림을 다시 보낸다
            curses.mousemask(curses.ALL_MOUSE_EVENTS)


def selftest():
    import tempfile
    d = tempfile.mkdtemp()
    # Sixel: 2×1 그림(검정·투명)을 6픽셀 높이로 → 6×6, 칠한 점만 팔레트에, 투명 배경 머리말
    six, sw, sh = _pokedata.encode_sixel([[(0, 0, 0, 255), (0, 0, 0, 0)]], 6)
    assert (sw, sh) == (12, 6) and six.startswith('\x1bP0;1;0q"1;1;12;6') and six.endswith('\x1b\\')
    assert six.count('#0;2;') == 1 and '#1' not in six
    for f in ('memo.py', 'tetris.py', 'hub.py', '_lib.py', 'notes.txt'):
        open(os.path.join(d, f), 'w').close()
    assert tools(d) == ['memo', 'tetris']
    assert bar(0.5, 10) == '█' * 5 + '░' * 5
    assert bar(1.7, 4) == '████' and bar(-1, 4) == '░░░░'
    assert fmt_k(84321) == '84k' and fmt_k(512) == '512'
    assert label('컨텍스트') == '컨텍스트   ' and label('5시간 한도') == '5시간 한도 '
    # 버튼 폭은 화면 칸: '[ 한/EN ]' 은 8글자지만 9칸, 다음 버튼은 2칸 띄워 그 뒤에
    assert tw('[ 한/EN ]') == 9 and len('[ 한/EN ]') == 8 and tw('[ close ]') == 9
    assert layout(['[ close ]', '[ 한/EN ]'], 62, 19) == [(19, 1, 10, '[ close ]'), (19, 12, 21, '[ 한/EN ]')]
    # 폭 20: '[ 메모장 ]'(10칸)은 1~11, 다음 것은 13+10 >= 20 이라 두 줄 아래로
    assert layout(['[ 메모장 ]', '[ 테트리스 ]'], 20) == [(0, 1, 11, '[ 메모장 ]'), (2, 1, 13, '[ 테트리스 ]')]
    print('hub selftest ok')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--session', help='따라갈 세션 id(고정)')
    ap.add_argument('--follow-pane', help='제목(세션 이름)을 따라갈 패널 — tmux 는 dev:0.0, cmux 는 cmux:0(이 워크스페이스의 0번 패널)')
    a = ap.parse_args()
    if a.session:  # 자식 도구(memo 등)도 같은 세션을 쓰게 환경변수로 넘긴다
        os.environ['PANE_TOOLS_SESSION'] = a.session
        os.environ.pop('PANE_TOOLS_FOLLOW', None)
    if a.follow_pane:
        os.environ['PANE_TOOLS_FOLLOW'] = a.follow_pane
    if a.selftest:
        selftest()
    else:
        locale.setlocale(locale.LC_ALL, '')
        os.environ.setdefault('ESCDELAY', '25')
        KITTY = kitty_ok()
        SIXEL = not KITTY and sixel_ok()
        try:
            curses.wrapper(main)
        finally:
            kitty_hide(free=True)
