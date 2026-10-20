#!/usr/bin/env python3
"""메모장 — 따라가는 Claude 세션으로 메모를 보낸다.

따라갈 세션은 current_target() 이 정한다: PANE_TOOLS_FOLLOW(tmux 패널, 또는 cmux:<패널 번호>) 가 있으면 그 패널 제목(세션 이름)을,
없고 PANE_TOOLS_SESSION 이 있으면 그 세션 하나를, 둘 다 없으면 예전처럼 dev:0.0 패널을 따라간다.
세션별 메모를 바꿔 보여 주고, [send] 를 누르면 받는 세션의
수신함(~/.claude/pane-tools/inbox/<sessionId>.json)에 넣는다. 실제로 프롬프트에 넣는 건
그 세션의 pane-tools mod 다 — 작업 중이면 끝난 뒤에 들어간다.
`python3 memo.py --selftest` 로 편집·배치 계산을 점검한다.
"""
import curses
import json
import locale
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata

from _lang import L

# cmux 는 TERMINFO 로 자기 터미널 설명을 주는데, 그 xterm-256color 엔 rep(같은 글자 N번 반복)가 있다. macOS 기본
# ncurses(6.0, 2015 — Homebrew Python 도 이걸 쓴다)는 rep 로 ░ 같은 여러 바이트 글자를 보낼 때 마지막 바이트만 보내서
# 게이지가 U+FFFD 로 깨졌다(2026-10-20, script 로 보낸 바이트 확인: E2 96 91 대신 91 + ESC[6b). 시스템 설명엔 rep 가
# 없으니 macOS 에선 그 TERM 의 시스템 설명이 있으면 그걸 쓴다. curses 를 켜기 전(이 모듈을 불러올 때) 정해야 하고,
# 허브·테트리스·포켓몬이 모두 이 모듈을 먼저 불러오며 허브가 띄우는 도구도 이 환경을 물려받는다.
if sys.platform == 'darwin' and os.environ.get('TERMINFO'):
    _term = os.environ.get('TERM', '')
    if _term and os.path.exists(f'/usr/share/terminfo/{ord(_term[0]):x}/{_term}'):
        del os.environ['TERMINFO']

ROOT = os.path.expanduser('~/.claude/pane-tools')
WATCH = 'dev:0.0'
CLAUDE = os.path.expanduser('~/.npm-global/bin/claude')
if not os.path.exists(CLAUDE):
    CLAUDE = 'claude'


def cw(ch):
    return 2 if unicodedata.east_asian_width(ch) in 'WF' else 1


def wrap(lines, width):
    """화면 줄 목록 [(줄번호, 시작, 끝)] — 넓은 글자(한글)는 2칸으로 센다."""
    rows = []
    for i, line in enumerate(lines):
        start = w = 0
        for j, ch in enumerate(line):
            if w + cw(ch) > width:
                rows.append((i, start, j))
                start, w = j, 0
            w += cw(ch)
        rows.append((i, start, len(line)))
    return rows


def cursor_pos(lines, width, r, c):
    """커서(줄 r, 글자 c)가 놓이는 (화면 줄, 칸)."""
    rows = wrap(lines, width)
    for k, (i, s, e) in enumerate(rows):
        last_of_line = k + 1 == len(rows) or rows[k + 1][0] != i
        if i == r and s <= c and (c < e or (c == e and last_of_line)):
            return k, sum(cw(ch) for ch in lines[i][s:c])
    return len(rows) - 1, 0


class Buf:
    def __init__(self, text=''):
        self.lines = text.split('\n')
        self.r = len(self.lines) - 1
        self.c = len(self.lines[-1])

    def text(self):
        return '\n'.join(self.lines)

    def insert(self, t):
        for ch in t:
            line = self.lines[self.r]
            if ch == '\n':
                self.lines[self.r:self.r + 1] = [line[:self.c], line[self.c:]]
                self.r, self.c = self.r + 1, 0
            else:
                self.lines[self.r] = line[:self.c] + ch + line[self.c:]
                self.c += 1

    def backspace(self):
        if self.c:
            line = self.lines[self.r]
            self.lines[self.r] = line[:self.c - 1] + line[self.c:]
            self.c -= 1
        elif self.r:
            self.c = len(self.lines[self.r - 1])
            self.lines[self.r - 1] += self.lines.pop(self.r)
            self.r -= 1

    def delete(self):
        line = self.lines[self.r]
        if self.c < len(line):
            self.lines[self.r] = line[:self.c] + line[self.c + 1:]
        elif self.r + 1 < len(self.lines):
            self.lines[self.r] += self.lines.pop(self.r + 1)

    def move(self, key):
        if key == curses.KEY_LEFT:
            if self.c:
                self.c -= 1
            elif self.r:
                self.r -= 1
                self.c = len(self.lines[self.r])
        elif key == curses.KEY_RIGHT:
            if self.c < len(self.lines[self.r]):
                self.c += 1
            elif self.r + 1 < len(self.lines):
                self.r, self.c = self.r + 1, 0
        elif key in (curses.KEY_UP, curses.KEY_DOWN):
            self.r = max(0, min(len(self.lines) - 1, self.r + (1 if key == curses.KEY_DOWN else -1)))
            self.c = min(self.c, len(self.lines[self.r]))
        elif key == curses.KEY_HOME:
            self.c = 0
        elif key == curses.KEY_END:
            self.c = len(self.lines[self.r])


def title_name(title):
    """패널 제목 → 세션 이름. 앞의 상태 기호(✳ ⠂ 등)는 뗀다. 세션 목록 화면이면 None."""
    name = re.sub(r'^[^\w]+', '', title.strip()).strip()
    return None if not name or name == 'claude agents' else name


# ── 수신함: [{id, text}] 를 쌓고, mod 가 넣은 마지막 id 를 <sid>.ack 에 남긴다 ──
def _load(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def acked(sid):
    return int(_load(f'{ROOT}/inbox/{sid}.ack', 0) or 0)


def queued(sid):
    ack = acked(sid)
    return [m for m in _load(f'{ROOT}/inbox/{sid}.json', []) if m['id'] > ack]


def enqueue(sid, text):
    msgs = queued(sid)  # 이미 넣은 것은 여기서 정리된다
    new_id = max([int(time.time() * 1000)] + [m['id'] + 1 for m in msgs])
    msgs.append({'id': new_id, 'text': text})
    os.makedirs(f'{ROOT}/inbox', exist_ok=True)
    path = f'{ROOT}/inbox/{sid}.json'
    with open(path + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(msgs, f, ensure_ascii=False)
    os.replace(path + '.tmp', path)  # mod 가 반쯤 쓴 파일을 읽지 않게


def memo_path(sid):
    return f'{ROOT}/memos/{sid}.txt'


def load_memo(sid):
    try:
        with open(memo_path(sid), encoding='utf-8') as f:
            return f.read()
    except OSError:
        return ''


def save_memo(sid, text):
    os.makedirs(f'{ROOT}/memos', exist_ok=True)
    with open(memo_path(sid), 'w', encoding='utf-8') as f:
        f.write(text)


# ── 세션 목록: `claude agents --json` 이 2초·CPU 1초쯤 들어 따로 돌고, 평소엔 15초마다·0번 패널 세션이 바뀌면 바로 ──
sessions = {}  # 이름 → [세션 정보]
refresh = threading.Event()


def poll_sessions():
    global sessions
    while True:
        refresh.clear()
        try:
            out = subprocess.run([CLAUDE, 'agents', '--json'], capture_output=True, text=True, timeout=20).stdout
            by_name = {}
            for s in json.loads(out):
                by_name.setdefault(s.get('name'), []).append(s)
            sessions = by_name
        except Exception:
            pass
        refresh.wait(15)


def pane_title(target=WATCH):
    """패널 제목. target 은 tmux 대상(예: dev:0.0) 또는 cmux:<번호>. 그 패널(또는 tmux·cmux)이 없으면 None."""
    if target.startswith('cmux:'):
        return cmux_title(target[5:])
    try:
        r = subprocess.run(['tmux', 'display', '-p', '-t', target, '#{pane_title}'], capture_output=True, text=True)
    except OSError:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def cmux_title(index, run=subprocess.run):
    """cmux 에서 이 워크스페이스의 index 번째 패널에 보이는 탭 제목.
    패널 번호로 찾는 이유: surface:N 같은 이름은 cmux 를 다시 켤 때마다 바뀌지만 레이아웃 안의 순서는 그대로다.
    워크스페이스는 CMUX_WORKSPACE_ID(허브가 떠 있는 패널의 것)를 쓰고, 없으면 cmux 가 지금 고른 곳."""
    ws = os.environ.get('CMUX_WORKSPACE_ID')
    scope = ['--workspace', ws] if ws else []
    try:
        panes = json.loads(run(['cmux', 'list-panes', *scope, '--json'], capture_output=True, text=True, timeout=5).stdout)['panes']
        pane = next(p['ref'] for p in panes if p['index'] == int(index))
        tabs = json.loads(run(['cmux', 'list-panels', *scope, '--json'], capture_output=True, text=True, timeout=5).stdout)['surfaces']
        return next(t['title'] for t in tabs if t['pane_ref'] == pane and t.get('selected_in_pane'))
    except (OSError, ValueError, KeyError, StopIteration, subprocess.TimeoutExpired):
        return None


_want = [None]  # 지난번 따라가던 대상 — 바뀌면 세션 목록을 바로 다시 읽는다


def current_target(env=os.environ):
    """따라갈 세션: (이름 또는 표시, sessionId 또는 None, 작업 중?, 안내 문구 — 정해졌으면 '')."""
    follow, fixed = env.get('PANE_TOOLS_FOLLOW'), env.get('PANE_TOOLS_SESSION')
    if fixed and not follow:
        s = next((s for ss in sessions.values() for s in ss if s.get('sessionId') == fixed), None)
        want, out = fixed, ((s or {}).get('name') or fixed[:8], fixed, bool(s) and s.get('state') == 'working', '')
    else:
        watch = follow or WATCH
        title = pane_title(watch)
        want = title_name(title) if title is not None else None
        found = sessions.get(want, []) if want else []
        sid = found[0]['sessionId'] if len(found) == 1 else None
        if title is None:
            note = (L(f'패널 {watch} 을 찾지 못했습니다', f'Pane {watch} not found') if follow
                    else L('따라갈 세션이 없습니다 — /mods 로 여세요', 'No session to follow — open this via /mods'))
        elif not want:
            note = L(f'{watch} 패널이 세션 목록 화면입니다 — 세션을 열면 따라갑니다',
                     f'Pane {watch} shows the session list — open a session to follow it')
        elif not sessions:
            note = L('세션 목록을 읽는 중…', 'Loading sessions…')
        elif len(found) > 1:
            note = L(f'이름이 "{want}" 인 세션이 {len(found)}개라 보낼 곳을 정할 수 없습니다',
                     f'{len(found)} sessions are named "{want}" — cannot tell which one')
        elif not found:
            note = L(f'"{want}" 세션을 실행 중 목록에서 찾지 못했습니다', f'Session "{want}" is not in the running list')
        else:
            note = ''
        out = (want, sid, bool(sid) and found[0].get('state') == 'working', note)
    if want != _want[0]:
        refresh.set()
    _want[0] = want
    return out


# 두벌식 자판 자리 → 영문 키. 한글 자판인 채로 l·s·d 를 누르면 ㅣ·ㄴ·ㅇ 가 들어와 단축키가 안 먹었다.
HANGUL_KEYS = dict(zip('ㅂㅈㄷㄱㅅㅛㅕㅑㅐㅔㅁㄴㅇㄹㅎㅗㅓㅏㅣㅋㅌㅊㅍㅠㅜㅡㅃㅉㄸㄲㅆㅒㅖ',
                       'qwertyuiopasdfghjklzxcvbnmQWERTOP'))


# 한글 자판에선 자모 하나가 입력기 안에서 '조합 중'으로 머물다 다음 키를 눌러야 프로그램에 온다(ㄴ → ㄴㄴ 해야 선택,
# 2026-10-20 실측) — 프로그램 쪽에서 고칠 수 없다. 그래서 macOS 에 macism 이 있으면, 단축키 화면 패널에 포커스가
# 들어올 때 영문 자판으로 바꾸고 나갈 때 들어오기 전 자판으로 되돌린다(cmux 는 패널마다 ESC[I / ESC[O 를 보낸다 — 확인함).
# 들어오기 전 자판은 파일에 둬서 허브와 허브가 띄운 모드가 같이 쓴다. macism 이 없으면(다른 PC) 아무것도 안 한다.
ENGLISH = 'com.apple.keylayout.ABC'
SAVED = f'{ROOT}/input-source.saved'
MACISM = shutil.which('macism') if sys.platform == 'darwin' else None


def focus_reporting(on):
    """터미널의 포커스 들어옴/나감 신호를 켜고 끈다 — 자판 전환을 쓸 수 있을 때만."""
    if MACISM:
        sys.stdout.write('\x1b[?1004h' if on else '\x1b[?1004l')
        sys.stdout.flush()


def on_focus(inside):
    """패널에 들어오면 영문 자판으로(이미 영문이면 그대로), 나가면 들어오기 전 자판으로 되돌린다."""
    if not MACISM:
        return
    try:
        if inside and not os.path.exists(SAVED):
            cur = subprocess.run([MACISM], capture_output=True, text=True, timeout=2).stdout.strip()
            if cur and cur != ENGLISH:
                with open(SAVED, 'w') as f:
                    f.write(cur)
                subprocess.run([MACISM, ENGLISH], capture_output=True, timeout=2)
        elif not inside and os.path.exists(SAVED):
            with open(SAVED) as f:
                prev = f.read().strip()
            os.remove(SAVED)
            if prev:
                subprocess.run([MACISM, prev], capture_output=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        pass


def getkey(scr, wait=-1):
    """getch 처럼 키 번호(시간 초과면 -1)를 돌려주되, 한글 자판으로 친 자모는 같은 자리의 영문 키로 바꾸고,
    포커스 신호(ESC[I / ESC[O)는 자판을 바꾼 뒤 -1 로 삼킨다. wait 는 이 화면이 scr.timeout 에 준 값 —
    신호 뒷부분을 짧게 기다린 뒤 되돌린다. 단축키 화면(허브·포켓몬·테트리스)용 — 메모장 편집엔 쓰지 않는다."""
    try:
        k = scr.get_wch()
    except curses.error:
        return -1
    if k == '\x1b':  # Esc 키이거나 포커스 신호의 시작
        scr.timeout(30)
        try:
            seq = scr.get_wch() + scr.get_wch()
        except (curses.error, TypeError):
            seq = ''
        scr.timeout(wait)
        if seq in ('[I', '[O'):
            on_focus(seq == '[I')
            return -1
        return 27
    if isinstance(k, str):
        k = HANGUL_KEYS.get(k, k)
        return ord(k) if len(k) == 1 else -1
    return k


def put(win, y, x, text, attr=0):
    h, w = win.getmaxyx()
    if not 0 <= y < h or x >= w:
        return x
    for ch in text:
        if x + cw(ch) > w - (1 if y == h - 1 else 0):  # 맨 아래 오른쪽 끝 칸은 쓰면 오류
            break
        try:
            win.addstr(y, x, ch, attr)
        except curses.error:
            pass
        x += cw(ch)
    return x


def main(scr):
    curses.raw()
    curses.curs_set(1)
    scr.keypad(True)
    scr.timeout(500)
    curses.mousemask(curses.ALL_MOUSE_EVENTS)
    curses.mouseinterval(0)
    threading.Thread(target=poll_sessions, daemon=True).start()

    sid = None
    buf = Buf()
    msg = ''  # [send] 를 눌렀을 때의 안내 — 글을 고치면 지운다
    sent_at = 0.0
    buttons = {}

    def send():
        nonlocal msg, sent_at
        text = buf.text().strip()
        if not sid:
            msg = L('보낼 세션이 없습니다', 'No session to send to')
        elif not text:
            msg = L('보낼 내용이 없습니다', 'Nothing to send')
        else:
            enqueue(sid, text)
            buf.__init__('')
            save_memo(sid, '')
            sent_at = time.time()

    while True:
        name, new_sid, busy, note = current_target()
        if new_sid != sid:
            if sid:
                save_memo(sid, buf.text())
            sid = new_sid
            buf = Buf(load_memo(sid) if sid else '')

        if note:  # 세션이 안 정해졌다
            pass
        elif queued(sid):
            idle_long = not busy and time.time() - sent_at > 8
            note = (L('전달 대기 — 작업이 끝나면 들어갑니다', 'Queued — it goes in when the current task finishes')
                    if not idle_long else L('전달 대기 — 오래 걸리면 그 세션에서 /reload-plugins 를 한 번 해 주세요',
                                            'Queued — if it takes long, run /reload-plugins once in that session'))
        elif sent_at and time.time() - sent_at < 30:
            note = L('✓ 전달했습니다', '✓ Delivered')
        else:
            note = msg

        h, w = scr.getmaxyx()
        scr.erase()
        head = L(' 메모 → ', ' Memo → ') + (name or L('(없음)', '(none)')) + (L(' · 작업 중', ' · working') if busy else '')
        put(scr, 0, 0, head.ljust(w), curses.A_REVERSE)
        body_h = max(1, h - 3)
        rows = wrap(buf.lines, w)
        cy, cx = cursor_pos(buf.lines, w, buf.r, buf.c)
        top = max(0, cy - body_h + 1)
        for k, (i, s, e) in enumerate(rows[top:top + body_h]):
            put(scr, 1 + k, 0, buf.lines[i][s:e])
        put(scr, h - 2, 0, note, curses.A_DIM)
        x = 1
        buttons = {}
        for label, act in (('[ send ]', send), ('[ close ]', None)):
            buttons[act] = (x, x + len(label))
            x = put(scr, h - 1, x, label, curses.A_BOLD | curses.A_REVERSE) + 2
        put(scr, h - 1, x, L('Ctrl+S 보내기 · Esc 닫기', 'Ctrl+S send · Esc close'), curses.A_DIM)
        try:
            scr.move(1 + cy - top, min(cx, w - 1))
        except curses.error:
            pass
        scr.refresh()

        try:
            key = scr.get_wch()
        except curses.error:
            continue
        before = buf.text()
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
            except curses.error:
                continue
            if my == h - 1 and bstate & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED):
                hit = next((act for act, (x0, x1) in buttons.items() if x0 <= mx < x1), 'miss')
                if hit is None:  # [ close ]
                    break
                if callable(hit):
                    hit()
        elif key in ('\x1b', '\x11'):  # Esc, Ctrl+Q
            break
        elif key == '\x13':  # Ctrl+S
            send()
        elif key in ('\n', '\r', curses.KEY_ENTER):
            buf.insert('\n')
        elif key in ('\x7f', '\x08', curses.KEY_BACKSPACE):
            buf.backspace()
        elif key == curses.KEY_DC:
            buf.delete()
        elif key == '\t':
            buf.insert('  ')
        elif isinstance(key, str) and key.isprintable():
            buf.insert(key)
        elif isinstance(key, int):
            buf.move(key)
        if buf.text() != before:
            msg = ''
            if sid:
                save_memo(sid, buf.text())
    if sid:
        save_memo(sid, buf.text())


def selftest():
    import tempfile
    global ROOT
    b = Buf()
    b.insert('가나a\n둘')
    assert b.lines == ['가나a', '둘'] and (b.r, b.c) == (1, 1)
    b.backspace(); b.backspace()
    assert b.lines == ['가나a'] and (b.r, b.c) == (0, 3)
    b.move(curses.KEY_HOME); b.delete()
    assert b.lines == ['나a']
    # 폭 5: '가나다' 는 2+2 에서 끊기고 '다' 가 다음 줄
    assert wrap(['가나다'], 5) == [(0, 0, 2), (0, 2, 3)]
    assert cursor_pos(['가나다'], 5, 0, 1) == (0, 2)
    assert cursor_pos(['가나다'], 5, 0, 2) == (1, 0)
    assert cursor_pos(['가나다'], 5, 0, 3) == (1, 2)
    assert cursor_pos(['', 'ab'], 5, 1, 2) == (1, 2)
    assert title_name('✳ my project') == 'my project'
    assert title_name('⠂ 백엔드') == '백엔드'
    assert title_name('claude agents') is None
    ROOT = tempfile.mkdtemp()
    enqueue('s', '하나'); enqueue('s', '둘')
    q = queued('s')
    assert [m['text'] for m in q] == ['하나', '둘'] and q[0]['id'] < q[1]['id']
    with open(f'{ROOT}/inbox/s.ack', 'w') as f:
        f.write(str(q[0]['id']))
    assert [m['text'] for m in queued('s')] == ['둘']
    # 따라갈 세션 고르기: FOLLOW > SESSION > 기본 dev:0.0(있을 때만)
    global sessions, pane_title
    real_title = pane_title
    sid = '8c3f341e-5fa8-4c51-b0ee-a287bf855f8c'
    sessions = {'일': [{'sessionId': sid, 'name': '일', 'state': 'working'}],
                '둘': [{'sessionId': 'a'}, {'sessionId': 'b'}]}
    pane_title = lambda t=WATCH: {'p:1': '✳ 일', 'p:2': '⠂ 둘', WATCH: 'claude agents'}.get(t)
    assert current_target({'PANE_TOOLS_SESSION': sid}) == ('일', sid, True, '')
    assert current_target({'PANE_TOOLS_SESSION': 'deadbeef-1234'}) == ('deadbeef', 'deadbeef-1234', False, '')
    assert current_target({'PANE_TOOLS_FOLLOW': 'p:1', 'PANE_TOOLS_SESSION': 'x'}) == ('일', sid, True, '')
    n, s, b, note = current_target({'PANE_TOOLS_FOLLOW': 'p:2'})
    assert (n, s, b) == ('둘', None, False) and '2' in note  # 같은 이름 둘
    assert current_target({'PANE_TOOLS_FOLLOW': 'p:9'})[:3] == (None, None, False)  # 없는 패널
    assert current_target({})[:2] == (None, None) and current_target({})[3]  # dev:0.0 이 목록 화면
    pane_title = lambda t=WATCH: None  # tmux 에 dev:0.0 이 없다 → /mods 안내
    assert current_target({})[:2] == (None, None) and '/mods' in current_target({})[3]
    pane_title, sessions = real_title, {}
    # cmux:<번호> — 패널 순서로 찾아 그 패널에서 지금 보이는 탭의 제목을 준다(같은 패널의 다른 탭은 무시)
    def fake_cmux(cmd, **_):
        out = {'list-panes': {'panes': [{'index': 0, 'ref': 'pane:7'}, {'index': 2, 'ref': 'pane:9'}]},
               'list-panels': {'surfaces': [{'pane_ref': 'pane:7', 'title': 'other tab', 'selected_in_pane': False},
                                            {'pane_ref': 'pane:7', 'title': '◑ settings', 'selected_in_pane': True},
                                            {'pane_ref': 'pane:9', 'title': 'zsh', 'selected_in_pane': True}]}}[cmd[1]]
        return subprocess.CompletedProcess(cmd, 0, json.dumps(out), '')
    def no_cmux(*_, **__):
        raise OSError
    assert cmux_title('0', fake_cmux) == '◑ settings' and title_name(cmux_title('0', fake_cmux)) == 'settings'
    assert cmux_title('2', fake_cmux) == 'zsh'
    assert cmux_title('5', fake_cmux) is None  # 없는 패널
    assert cmux_title('0', no_cmux) is None    # cmux 가 없거나 안 떠 있음
    # 한글 자판 단축키: ㅣ→l, ㄲ(Shift+r)→R, 영문·특수 키는 그대로, 시간 초과는 -1
    class Fake:
        def __init__(self, k): self.k = k
        def get_wch(self):
            if self.k is None:
                raise curses.error
            return self.k
    assert [getkey(Fake(k)) for k in ('ㅣ', 'ㄴ', 'ㄲ', 'l', ' ', curses.KEY_UP, None)] == \
        [ord('l'), ord('s'), ord('R'), ord('l'), 32, curses.KEY_UP, -1]

    # Esc 와 포커스 신호: 차례로 돌려주는 가짜 화면
    class Seq:
        def __init__(self, keys): self.keys = list(keys)
        def timeout(self, ms): pass
        def get_wch(self):
            if not self.keys:
                raise curses.error
            return self.keys.pop(0)
    seen = []
    real, globals()['on_focus'] = on_focus, seen.append
    try:
        assert getkey(Seq('\x1b')) == 27  # Esc 혼자
        assert getkey(Seq('\x1b[I')) == -1 and getkey(Seq('\x1b[O')) == -1 and seen == [True, False]
    finally:
        globals()['on_focus'] = real
    assert len(HANGUL_KEYS) == 33 and HANGUL_KEYS['ㅔ'] == 'p' and HANGUL_KEYS['ㅖ'] == 'P'
    print('memo selftest ok')


if __name__ == '__main__':
    if sys.argv[1:] == ['--selftest']:
        selftest()
    else:
        locale.setlocale(locale.LC_ALL, '')
        os.environ.setdefault('ESCDELAY', '25')
        curses.wrapper(main)
