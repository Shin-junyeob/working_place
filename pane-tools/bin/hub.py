#!/usr/bin/env python3
"""모드 허브 — /mods 가 띄운다(`--session <id>` · `--follow-pane <tmux 대상>`, 자식 도구엔 환경변수로 넘긴다).

위: 따라가는 세션(memo.current_target)의 컨텍스트·비용·사용 한도 게이지(각 세션의 pane-tools mod 가 2초마다 적는 값).
아래: 이 폴더(bin/)의 도구마다 버튼 하나 — 새 모드는 여기에 <이름>.py 를 두면 [<이름>] 버튼이 저절로 생긴다.
버튼을 누르면 그 도구가 이 패널에서 돌고, 끝나면 허브로 돌아온다.
`python3 hub.py --selftest` 로 버튼 목록·게이지 계산을 점검한다.
"""
import argparse
import curses
import importlib
import json
import locale
import os
import subprocess
import sys
import threading
import time

BIN = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BIN)
import memo  # noqa: E402 — 세션 따라가기·한글 폭 계산을 같이 쓴다
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
    while True:
        name, sid, busy, note = memo.current_target()

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
            for text, hot, frac in pokemon.summary() if pokemon else []:
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
        scr.refresh()

        key = scr.getch()
        pick = None
        if key in (ord('q'), 27):
            break
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
            curses.endwin()
            subprocess.run([sys.executable, os.path.join(BIN, pick + '.py')])
            scr.clear()
            curses.mousemask(curses.ALL_MOUSE_EVENTS)


def selftest():
    import tempfile
    d = tempfile.mkdtemp()
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
    ap.add_argument('--follow-pane', help='제목(세션 이름)을 따라갈 tmux 패널, 예: dev:0.0')
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
        curses.wrapper(main)
