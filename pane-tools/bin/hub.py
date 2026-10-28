#!/usr/bin/env python3
"""모드 허브 — /mods 가 띄운다(`--session <id>` · `--follow-pane <tmux 대상>`, 자식 도구엔 환경변수로 넘긴다).

위: 따라가는 세션(memo.current_target)의 컨텍스트·비용·사용 한도 게이지(각 세션의 pane-tools mod 가 2초마다 적는 값).
아래: 이 폴더(bin/)의 도구마다 버튼 하나 — 새 모드는 여기에 <이름>.py 를 두면 [<이름>] 버튼이 저절로 생긴다.
버튼을 누르면 그 도구가 이 패널에서 돌고, 끝나면 허브로 돌아온다.
`python3 hub.py --selftest` 로 버튼 목록·게이지 계산을 점검한다.
"""
import argparse
import curses
import glob
import importlib
import json
import locale
import math
import os
import subprocess
import sys
import threading
import time

BIN = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BIN)
import memo  # noqa: E402 — 세션 따라가기·한글 폭 계산을 같이 쓴다
import feed  # noqa: E402 — 오른쪽 세션 상태 칸(claude agents 목록·색)
import _lang  # noqa: E402
import _pokedata  # noqa: E402 — 동료 그림(Kitty 용 PNG · Sixel · ▀▄ 용 256색)
import _place  # noqa: E402 — [ 설정 ]: /mods 를 띄울 곳
from _gfx import (_six, cell_px, kitty_cols, kitty_hide, kitty_ok, kitty_show,  # noqa: E402 — 진짜 그림(Kitty·Sixel)
                  sixel_hide, sixel_ok, sixel_show, sixel_touch, tmux_passthrough)
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




KITTY = False  # __main__ 이 curses 를 켜기 전에 kitty_ok() 로 정한다
SIXEL = False  # 터미널이 Sixel 이미지를 받으면 True — __main__ 이 sixel_ok() 로 정한다


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


def inherited_children():
    """이 프로세스가 시작할 때 이미 있던 자식들 — 허브가 os.execv 로 스스로 다시 시작하면, 그 전에 뒤에서 돌던
    `claude agents --json` 이 새 허브의 자식으로 남는데 아무도 거두지 않아 좀비가 됐다(2026-10-21 실제로 남음)."""
    kids = set()
    for task in os.listdir('/proc/self/task') if os.path.isdir('/proc/self/task') else []:
        try:
            with open(f'/proc/self/task/{task}/children') as f:
                kids.update(int(p) for p in f.read().split())
        except OSError:
            pass
    return kids


def reap(kids):
    """물려받은 자식 중 끝난 것을 거둔다(아직 도는 건 다음에). 우리가 subprocess 로 띄운 자식은 건드리지 않는다."""
    for pid in list(kids):
        try:
            if os.waitpid(pid, os.WNOHANG)[0]:
                kids.discard(pid)
        except ChildProcessError:
            kids.discard(pid)


def main(scr):
    curses.curs_set(0)
    scr.keypad(True)
    scr.timeout(1000)
    memo.focus_reporting(True)  # 이 패널에 들어오면 영문 자판, 나가면 원래 자판(macOS + macism)
    curses.mousemask(curses.ALL_MOUSE_EVENTS)
    curses.mouseinterval(0)
    curses.start_color()
    curses.use_default_colors()
    feed.init_colors()  # 1 녹 · 2 노 · 3 빨 · needs 색(claude agents 와 같은 220)
    threading.Thread(target=memo.poll_sessions, daemon=True).start()

    global pokemon
    pk_stamp = 0
    me = os.path.abspath(__file__)
    # 허브가 함께 불러 쓰는 memo·feed·_gfx 등도 바뀌면 옮겨 탄다(모드 화면은 열 때마다 새로 읽으니 상관없다)
    code = lambda: max(os.path.getmtime(p) for p in glob.glob(os.path.join(BIN, '*.py')))  # noqa: E731
    my_stamp = seen = code()
    seen_at = time.time()
    strays = inherited_children()
    while True:
        reap(strays)
        # 허브 자신이 바뀌면 같은 인자로 다시 뜬다 — 오래 켜 두니 옛 코드로 남지 않게. 단 두 가지를 지킨다(2026-10-20 실측):
        # git switch → pull 사이 몇 초 동안 파일이 옛 버전이었는데 그 순간 옮겨 타서, 이 재시작 코드가 없는 옛 허브에
        # 갇혔다(그 뒤 파일이 돌아와도 모름). 그래서 파일이 5초 동안 안 바뀐 뒤에만, 그리고 새 파일에도 재시작 코드가
        # 있을 때만 옮겨 탄다.
        m = code()
        if m != seen:
            seen, seen_at = m, time.time()
        elif m != my_stamp and time.time() - seen_at >= 5:
            with open(me, encoding='utf-8') as f:
                restartable = 'os.execv(' in f.read()
            if restartable:
                sixel_hide()
                kitty_hide(free=True)
                curses.endwin()
                os.execv(sys.executable, [sys.executable, me] + sys.argv[1:])
            my_stamp = m  # 재시작 못 하는 버전이면 지금 코드로 계속 — 파일이 다시 바뀌면 그때 본다
        name, sid, busy, note = memo.current_target()
        art = art_six = None

        h, w = scr.getmaxyx()
        scr.erase()
        edge = {}  # 줄마다 왼쪽 글이 끝나는 칸 — 오른쪽 세션 목록이 그 뒤에만 그리게

        def put(y, x, t, a=0):
            end = memo.put(scr, y, x, t, a)
            edge[y] = max(edge.get(y, 0), end or 0)
            return end
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
        list_top = y  # 게이지는 폭을 다 쓰니 세션 목록은 그 아래 오른쪽 빈자리에

        try:
            # 허브는 오래 켜 두므로, 포켓몬 코드·데이터가 바뀌면 다시 읽는다(안 그러면 두 화면의 규칙이 어긋난다)
            stamp = max(os.path.getmtime(f) for f in (os.path.join(BIN, 'pokemon.py'), pokemon._pokedata.OUT)
                        if os.path.exists(f))
            if pokemon and stamp != pk_stamp:
                pokemon, pk_stamp = importlib.reload(pokemon), stamp
            lines = pokemon.summary(awake=set(memo.sessions) or None) if pokemon else []
            hot_attr = lambda hot: curses.color_pair(feed.NEEDS_PAIR) | curses.A_BOLD if hot == 'warn' else curses.A_BOLD if hot else 0  # noqa: E731
            said = next((ln for ln in lines if ln[0].startswith('💬')), None)
            if said:  # 말풍선은 포켓몬 정보 위에 폭 전체로 — 오른쪽 세션 목록은 그 아래부터(길면 세션 이름을 가렸다)
                lines.remove(said)
                put(y, 1, said[0], hot_attr(said[1]))
                y += 1
                list_top = y
            n = pokemon.partner_id() if lines and w >= 44 else None
            gray = False  # 그림은 늘 컬러(2026-10-28 흑백 설정을 없앴다)
            # 동료 그림: Kitty 그래픽이 되면 원본 도트를 3줄에, 아니면 ▀▄ 반높이 칸으로
            png = _pokedata.sprite_png(n, gray) if n and KITTY else None
            cw_, ch_ = cell_px()
            six = _pokedata.sprite_sixel(n, gray, int(1.5 * ch_)) if n and SIXEL else None  # 세로 1.5줄(사용자 요청: 절반)
            grid = _pokedata.sprite(n) if n and not (KITTY or SIXEL) and curses.COLORS >= 256 else None
            if png or six or grid:  # 왼쪽에 동료 그림, 오른쪽엔 ' · ' 로 나눈 짧은 줄들
                top = y
                if png:
                    cols, used = kitty_cols(png[1], png[2], 3), 3
                    art = (y, 1, _pokedata.img_id(n) * 2 + gray, png[0], cols, used)  # 리전폼은 'form:번호' 라 정수로
                elif six:
                    cols, used = math.ceil(six[1] / cw_), 2
                    art_six = (y, 1, (n, gray, six[2], y), six[0], cols, used)
                else:
                    cols, used = len(grid[0]), (len(grid) + 1) // 2
                    _pokedata.draw_sprite(scr, y, 1, grid, gray)
                sx = cols + 3
                for text, hot, frac in lines:
                    parts = text.split(' · ')
                    for i, part in enumerate(parts):
                        x = put(y, sx, part, hot_attr(hot))
                        if i == len(parts) - 1 and frac is not None and not hot:
                            put(y, x + 1, bar(frac, 10), curses.A_DIM)
                        y += 1
                y = max(y, top + used)
            else:
                for text, hot, frac in lines:
                    x = put(y, 1, text, hot_attr(hot))
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
        close, lang_btn, setup = layout(['[ close ]', '[ 한/EN ]', L('[ 설정 ]', '[ setup ]')], w, h - 1)
        for by, x0, x1, btn in (close, lang_btn, setup):
            put(by, x0, btn, curses.A_BOLD | curses.A_REVERSE)
        put(h - 1, setup[2] + 2, L('s 설정 · l 언어 · q 닫기', 's setup · l lang · q close'), curses.A_DIM)
        # 세션 상태(claude agents 와 같은 색) — 오른쪽 열, 왼쪽 글이 끝난 칸 뒤에만, 자리가 모자라면 이름을 자른다.
        # 깨어 있는 세션만: memo 가 뒤에서 15초마다 받는 `claude agents --json` 목록에 있는 이름(잠든 세션은 거기 없다)
        busy = {n for n, ss in memo.sessions.items() if any(x.get('status') == 'busy' for x in ss)}
        rows = [r for r in feed.jobs(busy=busy) if r[0] in memo.sessions][:max(0, h - 2 - list_top)]
        colw = max((tw(n) for n, _ in rows), default=0)
        for i, (n, st) in enumerate(rows):
            yy = list_top + i
            x0 = max(edge.get(yy, 0) + 3, w - colw - 2)
            room = w - x0 - 1
            if room < 4:
                continue
            while tw(n) > room:
                n = n[:-1]
            memo.put(scr, yy, x0, n, feed.job_attr(st))
        if _six['key'] is not None and (art_six is None or _six['key'] != art_six[2]):
            sixel_hide()  # 전 그림을 지운다 — 투명 배경이라 새 그림만 덮어쓰면 옛 점이 남는다
        scr.refresh()
        if art_six:
            sixel_show(*art_six)
        if art:
            kitty_show(*art)
        else:
            kitty_hide()

        key = memo.getkey(scr, 1000)  # 한글 자판이어도 단축키가 먹게 · 포커스 신호로 자판 전환
        pick = None
        if key in (ord('q'), 27):
            break
        if key != -1:
            sixel_touch()
        if key == curses.KEY_RESIZE:
            sixel_hide()
        if key == ord('l'):
            toggle()
            continue
        if key == ord('s'):
            pick = '_place'
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
            if my == setup[0] and setup[1] <= mx < setup[2]:
                pick = '_place'
            pick = pick or next((t for by, x0, x1, t in buttons if my == by and x0 <= mx < x1), None)
        if pick == '_place':  # 설정은 허브 안의 화면 — 다른 프로그램을 띄우지 않는다
            sixel_hide()
            kitty_hide(free=True)
            _place.screen(scr)
            scr.clear()
            sixel_touch()
        elif pick:
            sixel_hide()
            kitty_hide(free=True)
            memo.focus_reporting(False)  # 도구가 자기 것을 켠다 — 메모장은 안 켜니 신호가 글자로 들어가지 않게
            if pick == 'memo':
                memo.on_focus(False)  # 메모장은 한글을 쓰니 원래 자판으로
            curses.endwin()
            subprocess.run([sys.executable, os.path.join(BIN, pick + '.py')])
            memo.focus_reporting(True)
            memo.on_focus(True)  # 아직 이 패널에 있다 — 다시 영문 자판(이미 바꿔 뒀으면 그대로)
            scr.clear()
            sixel_touch()  # 도구가 화면을 덮었으니 그림을 다시 놓는다
            curses.mousemask(curses.ALL_MOUSE_EVENTS)


def selftest():
    import tempfile
    d = tempfile.mkdtemp()
    # 물려받은 자식 거두기: 끝난 자식을 만들어 두고 거두면 좀비가 남지 않는다
    kid = os.fork()
    if kid == 0:
        os._exit(0)
    time.sleep(0.2)
    left = {kid}
    reap(left)
    assert not left and not os.path.exists(f'/proc/{kid}')
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
        if SIXEL:
            tmux_passthrough()
        try:
            curses.wrapper(main)
        finally:
            sixel_hide()
            kitty_hide(free=True)
            memo.focus_reporting(False)
            memo.on_focus(False)  # 허브를 닫으면 원래 자판으로
