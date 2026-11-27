#!/usr/bin/env python3
"""세션 활동 — 0번 패널이 보고 있는 세션의 작업 목록을 레일(git 그래프)로 그리고, 그 아래 깨어 있는 모든 세션의 지금 상태를 한 줄씩.

작업 목록은 Claude Code 가 세션마다 남기는 ~/.claude/tasks/<sessionId>/<번호>.json({subject, activeForm, status}),
세션 상태는 데몬이 작업마다 남기는 ~/.claude/jobs/<id>/state.json · timeline.jsonl({at, state, detail, text})을 읽는다. 쓰는 건 없다.
레일: 제목 앞 번호 순(1, 1-1, 1-2, 2 …)으로 끝난 것 ✔ · 진행 중 ● · 대기 ○. 작업 중 끼어든 일은 세션이 '1-1. …' 처럼 번호를 달아
넣고, 레일은 그것을 부모에서 갈라진 갈래(├─┐ … ├─┘)로 들여 그린다(2026-11-27 사용자 — 줄글 피드를 바꿨다).
세션 줄의 소식은 사용자가 보낸 말(text 가 빈 줄)과 작업 중간 경과를 뺀 마지막 사건 — 포켓몬 모드는 같은 사건들(feed)로 일한 날을 센다.
←→ 다른 세션 · Enter 0번 패널 세션으로 · q 닫기. `python3 feed.py --selftest` 로 점검한다.
"""
import curses
import glob
import json
import locale
import os
import re
import sys
import time
from datetime import datetime

from _lang import L
from memo import WATCH, cw, focus_reporting, getkey, pane_title, put, title_name

JOBS = os.path.expanduser('~/.claude/jobs')
TASKS = os.path.expanduser('~/.claude/tasks')  # Claude Code 의 작업 목록 — 세션마다 <sessionId>/<번호>.json
PIDS = os.path.expanduser('~/.claude/sessions')  # 떠 있는 Claude 프로세스마다 <pid>.json({sessionId, procStart, …})
LABEL = re.compile(r'^\s*(\d{1,3}(?:-\d{1,3})*)[.)]?\s+')  # 제목 앞 번호 '2. ' · '1-1 ' — 한 칸 세 자리까지(날짜 '2026-11-26' 은 아니다)
DUE = re.compile(r'\s*\(~(\d{1,2}:\d\d)(?:,\s*([^)]*))?\)')  # 제목에 적은 예상 시각 '(~14:30)' · '(~17:00, 사용자 확인)'
# claude agents 의 상태 묶음 — needs 가 맨 위, 끝난 것은 아래
ORDER = {'blocked': 0, 'needs_input': 0, 'failed': 1, 'working': 2, 'done': 3}
MARK = {'done': '✔', 'blocked': '▲', 'needs_input': '▲', 'failed': '✖'}


def last_row(path):
    """timeline 의 마지막 온전한 줄(끝 4KB 만 읽는다 — 쓰는 도중인 끝 줄은 건너뛴다)."""
    try:
        with open(path, 'rb') as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 4096))
            lines = f.read().splitlines()
    except OSError:
        return {}
    for line in reversed(lines):
        try:
            return json.loads(line)
        except ValueError:
            pass
    return {}


def group(d, last=None, busy=False):
    """claude agents 와 같은 묶음(그 안의 xo 함수를 따름). 데몬은 답을 받아 다시 일할 때 state.json 을 working 으로
    바꾸지 않으므로(2026-10-21 실제 세션: blocked → 사용자 답 → done 사이 내내 blocked), 마지막 줄이 사용자 말
    (text 가 빈 줄)이면 그 답을 처리하는 중 = working 으로 본다. busy 는 claude agents --json 의 실시간 상태."""
    st = d.get('state') or ''
    if busy or (last and last.get('state') != 'working' and not last.get('text')):
        return 'working'
    if st in ('done', 'failed'):
        return st
    return 'blocked' if d.get('tempo') == 'blocked' or ORDER.get(st) == 0 else 'working'


def sessions(folder=JOBS, busy=None):
    """claude agents 목록의 세션 [(이름, 상태, sessionId, (at, 마지막 소식))] — needs → working → done, 묶음 안에선 최근 것 먼저.
    지운 작업은 폴더에 tmp/ 만 남으므로 state.json 이 있는 것만 목록에 있는 것이다. busy: 지금 일하는 세션의 이름 또는 sessionId 들 —
    안 주면 진짜 기록 폴더일 때 pid 파일의 실시간 busy(awake)를 쓴다. 데몬은 일을 남긴 채 턴을 끝낸 세션을 blocked 로 적어서,
    이걸 빼먹은 곳(허브의 포켓몬 대사)은 백그라운드로 일하는 세션을 입력 대기로 봤다(2026-11-27 KNK_ERP).
    마지막 소식은 피드 사건(events)의 마지막 — 아직 없으면 state.json 의 요약."""
    if busy is None:
        busy = {sid for sid, b in ((awake() if folder == JOBS else None) or {}).items() if b}
    out = []
    for j in os.listdir(folder) if os.path.isdir(folder) else []:
        try:
            with open(os.path.join(folder, j, 'state.json'), encoding='utf-8') as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        name, tl = d.get('name') or j, os.path.join(folder, j, 'timeline.jsonl')
        last = last_row(tl)
        st = group(d, last, name in busy or d.get('sessionId') in busy)
        try:
            ev = _read(tl)
        except OSError:
            ev = []
        news = (ev[-1][0], ev[-1][2]) if ev else (d.get('updatedAt') or '', d.get('detail') or '')
        if st == 'working' and last.get('state') == 'working' and last.get('detail'):  # 일하는 중이면 시작 소식 대신 마지막 경과
            news = (last.get('at') or news[0], last['detail'].strip())
        out.append((d.get('updatedAt') or '', name, st, d.get('sessionId') or '', news))
    out.sort(key=lambda r: r[0], reverse=True)  # updatedAt 은 ISO 시각이라 글자 순 = 시간 순
    out.sort(key=lambda r: ORDER.get(r[2], 2))  # 안정 정렬 — 묶음 안에선 최근 것 먼저가 유지된다
    return [r[1:] for r in out]


def jobs(folder=JOBS, busy=None):
    """claude agents 목록의 세션 [(이름, 상태)] — sessions() 의 앞 두 칸(허브의 세션 칸·포켓몬이 쓴다)."""
    return [r[:2] for r in sessions(folder, busy)]


def awake(folder=PIDS, proc='/proc'):
    """깨어 있는 세션 {sessionId: 지금 일하는 중인가} — pid 파일의 프로세스가 살아 있고 시작 시각(procStart)이 /proc 의 것과
    같은 것. 재부팅 뒤 같은 번호를 다른 프로세스가 쓰면 시작 시각이 다르다. 일하는 중은 pid 파일의 status 'busy'(claude agents 의
    실시간 상태와 같다 — 백그라운드 담당이 도는 동안도 busy). claude agents --json(2초)을 피드에서 또 돌리지 않으려고.
    /proc 이 없으면(macOS) None — 거르지 않는다."""
    if not os.path.isdir(os.path.join(proc, 'self')):
        return None
    out = {}
    for f in glob.glob(os.path.join(folder, '*.json')):
        try:
            with open(os.path.join(proc, str(int(os.path.basename(f)[:-5])), 'stat')) as fh:  # 죽은 번호는 여기서 바로 넘어간다
                start = fh.read().rsplit(')', 1)[1].split()[19]  # 22번째 칸 starttime — 이름에 ')' 가 있어도 마지막 것 뒤부터
            with open(f, encoding='utf-8') as fh:
                d = json.load(fh)
        except (OSError, ValueError, IndexError):
            continue
        if str(d.get('procStart')) == start and d.get('sessionId'):
            out[d['sessionId']] = out.get(d['sessionId']) or d.get('status') == 'busy'  # 같은 세션 프로세스가 둘이면 하나라도 busy
    return out


def tasks(sid, folder=TASKS):
    """세션의 작업 목록 [{id, text, state, at, due}] — 번호 순, 목록이 없으면 []. id 는 제목 앞 번호('1-1')이고 없으면 작업 번호.
    진행 중이면 activeForm('…하는 중'), 아니면 제목에서 앞 번호와 예상 시각('(~14:30)')을 떼고 예상 시각은 due 로.
    at 은 파일을 고친 시각(상태가 바뀐 때)."""
    out = []
    for f in glob.glob(os.path.join(folder, sid, '*.json')) if re.fullmatch(r'[\w-]+', sid or '') else []:
        try:
            with open(f, encoding='utf-8') as fh:
                d = json.load(fh)
            at = os.path.getmtime(f)
        except (OSError, ValueError):
            continue
        st = d.get('status')
        if st not in ('pending', 'in_progress', 'completed'):
            continue
        subj = d.get('subject') or ''
        n = LABEL.match(subj)
        subj = subj[n.end():] if n else subj
        m = DUE.search(subj)
        if m:
            subj = subj[:m.start()] + (f' ({m[2]})' if m[2] else '') + subj[m.end():]
        text = d.get('activeForm') if st == 'in_progress' and d.get('activeForm') else subj
        out.append({'id': n[1] if n else str(d.get('id', '')), 'text': text.strip(), 'state': st, 'at': at, 'due': m[1] if m else ''})
    out.sort(key=lambda t: [int(x) if x.isdigit() else 10 ** 9 for x in t['id'].split('-')])  # 1, 1-1, 1-2, 2, 10 순
    return out


MARKS = {'completed': '✔', 'in_progress': '●', 'pending': '○'}


def rail(ts):
    """작업 목록(번호 순) → 레일 줄 [(선, 작업 또는 None)]. 하위 작업(1-1)은 git 갈래처럼 부모 아래에서 갈라져(├─┐)
    한 칸 들여 가고, 뒤에 이어지는 작업이 있으면 다시 합친다(├─┘). 부모가 없는 번호는 맨 위 단계로 둔다."""
    nodes, top = {}, []
    for t in ts:  # 번호 순이라 부모가 먼저 온다
        node = nodes[t['id']] = (t, [])
        parent = nodes.get(t['id'].rpartition('-')[0])
        (parent[1] if parent else top).append(node)
    rows = []

    def walk(level, prefix, after):
        for i, (t, kids) in enumerate(level):
            more = i < len(level) - 1 or after  # 이 작업(과 그 하위) 뒤로 이어지는 줄이 있나
            rows.append((prefix + MARKS[t['state']], t))
            if kids:
                rows.append((prefix + ('├─┐' if more else '└─┐'), None))
                walk(kids, prefix + ('│ ' if more else '  '), more)
                if more:
                    rows.append((prefix + '├─┘', None))
    walk(top, '', False)
    return rows


def fit_rail(rows, budget):
    """레일이 칸보다 길면 앞에서부터 하위까지 다 끝난 맨 위 단계 작업들을 '완료 N개' 한 줄로 접고,
    그래도 길면 뒤를 '… N줄 더' 로 자른다."""
    if len(rows) <= budget:
        return rows
    starts = [i for i, (ln, t) in enumerate(rows) if t and len(ln) == 1] + [len(rows)]  # 맨 위 단계 작업 줄
    cut = 0
    for a, b in zip(starts, starts[1:]):
        if any(t and t['state'] != 'completed' for _, t in rows[a:b]):
            break
        cut = b
    done = [t for _, t in rows[:cut] if t]
    if len(done) > 1:
        rows = [('✔', {'id': '', 'text': L(f'완료 {len(done)}개', f'{len(done)} done'), 'state': 'completed',
                       'at': max(t['at'] for t in done), 'due': ''})] + rows[cut:]
    if len(rows) > budget:
        rows = rows[:max(0, budget - 1)] + [('…', {'id': '', 'text': L(f'{len(rows) - budget + 1}줄 더', f'{len(rows) - budget + 1} more'),
                                                   'state': 'pending', 'at': 0, 'due': ''})]
    return rows


def task_when(t):
    """레일 오른쪽 시각 — 끝난 것은 끝난 시각, 진행 중은 '시작~예상', 대기는 '~예상'(제목에 적혀 있을 때만)."""
    at = when(datetime.fromtimestamp(t['at']).astimezone().isoformat()) if t['at'] else ''
    if t['state'] == 'completed':
        return at
    return f'{at}~{t["due"]}' if t['state'] == 'in_progress' else f'~{t["due"]}' if t['due'] else ''


NEEDS_PAIR = 9  # claude agents 의 Needs input 색 — 256색 220(#ffd700). 기본 노랑은 Windows Terminal 에서 겨자색이라 달라 보였다


def init_colors():
    """색 짝 1 녹 · 2 노 · 3 빨 · NEEDS_PAIR — 허브와 피드가 같이 쓴다."""
    for i, c in ((1, curses.COLOR_GREEN), (2, curses.COLOR_YELLOW), (3, curses.COLOR_RED),
                 (NEEDS_PAIR, 220 if curses.COLORS >= 256 else curses.COLOR_YELLOW)):
        curses.init_pair(i, c, -1)


def job_attr(state):
    """claude agents 와 같은 색 — completed 녹색, needs 220 노랑, working 회색."""
    if state == 'done':
        return curses.color_pair(1)
    if ORDER.get(state) == 0:
        return curses.color_pair(NEEDS_PAIR)
    return curses.color_pair(3) if state == 'failed' else curses.A_DIM


def events(rows, prev=(None, None)):
    """한 세션의 timeline 줄들 → (피드에 올릴 줄 [(at, state, detail)], 마지막 (state, detail)) — prev 로 이어 읽는다."""
    out = []
    for r in rows:
        st, detail = r.get('state'), (r.get('detail') or '').strip()
        if st != 'working' and not r.get('text'):
            continue  # 사용자가 보낸 말이 detail 로 찍힌 줄
        if st != prev[0] or (st != 'working' and detail != prev[1]):
            out.append((r.get('at') or '', st, detail))
        prev = (st, detail)
    return out, prev


_cache = {}  # 경로 → (읽은 바이트, 마지막 상태, 사건들) — 세션 기록이 수백 KB 라 늘어난 만큼만 읽는다


def _read(path):
    size = os.path.getsize(path)
    done, prev, ev = _cache.get(path, (0, (None, None), []))
    if size < done:  # 파일이 새로 쓰였다
        done, prev, ev = 0, (None, None), []
    if size > done:
        with open(path, 'rb') as f:
            f.seek(done)
            chunk = f.read()
        cut = chunk.rfind(b'\n') + 1  # 쓰는 도중인 마지막 줄은 다음에
        rows = []
        for line in chunk[:cut].splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
        new, prev = events(rows, prev)
        ev = ev + new
        done += cut
    _cache[path] = (done, prev, ev)
    return ev


def feed(folder=JOBS, limit=200):
    """모든 세션의 사건 [(at, 이름, state, detail)] — 최근 것 먼저."""
    out = []
    for j in os.listdir(folder) if os.path.isdir(folder) else []:
        try:
            with open(os.path.join(folder, j, 'state.json'), encoding='utf-8') as f:
                name = json.load(f).get('name') or j
            out += [(at, name, st, d) for at, st, d in _read(os.path.join(folder, j, 'timeline.jsonl'))]
        except (OSError, ValueError):
            continue  # 지운 작업이거나 아직 기록이 없다
    out.sort(reverse=True)
    return out[:limit]


def when(at, today=None):
    """ISO(UTC) → 이 PC 시각 'HH:MM', 오늘이 아니면 'MM-DD HH:MM'."""
    try:
        t = datetime.fromisoformat(at.replace('Z', '+00:00')).astimezone()
    except ValueError:
        return at[:16]
    return t.strftime('%H:%M') if t.date() == (today or datetime.now().astimezone().date()) else t.strftime('%m-%d %H:%M')


def clip(text, width):
    """화면 칸 기준으로 자른다 — 한글은 2칸."""
    out, used = '', 0
    for c in text:
        if used + cw(c) > width:
            return out[:-1] + '…' if out else ''
        out, used = out + c, used + cw(c)
    return out


def main(scr):
    curses.curs_set(0)
    scr.keypad(True)
    curses.start_color()
    curses.use_default_colors()
    init_colors()
    scr.timeout(2000)  # getkey 는 이 값을 따른다 — 빠뜨리면 키를 누를 때까지 다시 그리지 않는다(2026-10-21 피드가 멈춰 있었다)
    focus_reporting(True)
    pinned = followed = None  # ←→ 로 고른 세션(sessionId — 이름은 겹칠 수 있다) · 0번 패널이 보고 있는 세션 이름
    me = os.path.abspath(__file__)
    start = seen = os.path.getmtime(me)
    seen_at = time.time()
    while True:
        # 패널에 오래 띄워 두니, 이 파일이 바뀌면(자동 받기 등) 5초 동안 그대로인 것을 확인하고 새 코드로 다시 뜬다
        m = os.path.getmtime(me)
        if m != seen:
            seen, seen_at = m, time.time()
        elif m != start and time.time() - seen_at >= 5:
            curses.endwin()
            os.execv(sys.executable, [sys.executable, me] + sys.argv[1:])
        up = awake()  # 데몬 기록은 세션이 일을 남긴 채 턴을 끝내면 blocked 로 적는다 — 지금 busy 면 일하는 중(노란색 아님)
        board = sessions(busy={sid for sid, b in (up or {}).items() if b})
        if up:  # 깨어 있는 세션만(허브의 세션 칸과 같은 목록) — 하나도 못 찾으면 거르지 않는다(pid 파일 형식이 바뀌었을 수도)
            board = [r for r in board if r[2] in up]
        now = title_name(pane_title(os.environ.get('PANE_TOOLS_FOLLOW') or WATCH) or '')
        if now != followed:  # 0번 패널 세션이 바뀌면 다시 따라간다
            pinned, followed = None, now
        key_of = lambda r: r[2] or r[0]  # noqa: E731
        i = next((k for k, r in enumerate(board) if pinned and key_of(r) == pinned), None)
        if i is None:
            pinned, i = None, next((k for k, r in enumerate(board) if r[0] == now), 0)
        scr.erase()
        draw(scr, board, i if board else None, pinned is None)
        scr.refresh()
        key = getkey(scr, 2000)
        if key in (ord('q'), 27):
            break
        if key in (curses.KEY_LEFT, curses.KEY_RIGHT) and board:
            pinned = key_of(board[(i + (1 if key == curses.KEY_RIGHT else -1)) % len(board)])
        elif key in (ord('\n'), ord('\r'), curses.KEY_ENTER):
            pinned = None
    focus_reporting(False)


def width(text):
    return sum(cw(c) for c in text)


def draw(scr, board, cur, following):
    """제목 · board[cur] 세션(진행 막대) · 그 세션의 레일 · 깨어 있는 모든 세션의 상태 한 줄씩 · 안내."""
    h, w = scr.getmaxyx()
    name = board[cur][0] if cur is not None else None
    right = f' ◀ {cur + 1}/{len(board)} ▶ ' if name else ' '
    left = clip(L(' 세션 활동', ' Session activity') + (f' · {name}' if name else ''), w - width(right))
    put(scr, 0, 0, left + ' ' * max(0, w - width(left) - width(right)) + right, curses.A_REVERSE)
    put(scr, h - 1, 1, L('←→ 다른 세션 · q 닫기 · 0번 패널 세션을 따라간다', '←→ other session · q close · follows pane 0') if following else
        L('←→ 다른 세션 · Enter 0번 패널 세션으로 · q 닫기', '←→ other session · Enter back to pane 0 · q close'), curses.A_DIM)
    if not name:
        put(scr, 2, 1, L('아직 세션이 없습니다 — claude agents 로 띄운 세션이 여기에 나옵니다',
                         'No sessions yet — sessions started from claude agents show up here'), curses.A_DIM)
        return
    _, st, sid, _ = board[cur]
    ts = tasks(sid)
    x = put(scr, 1, 1, f'{MARK.get(st, "●")} {name}', job_attr(st) | curses.A_BOLD)
    if ts:
        d, k = sum(t['state'] == 'completed' for t in ts), sum(t['state'] == 'in_progress' for t in ts)
        fill = round(d / len(ts) * 12)
        x = put(scr, 1, put(scr, 1, x + 2, '━' * fill, curses.color_pair(1)), '─' * (12 - fill), curses.A_DIM)
        put(scr, 1, x, f' {d}/{len(ts)}', curses.A_DIM)
        tail = L(f'{k}개 진행', f'{k} running') if k else L('목록 완료', 'list done') if d == len(ts) else ''
        put(scr, 1, w - 1 - width(tail), tail, curses.A_DIM)
    space = h - 6  # 제목 · 세션 줄 · 빈 줄 둘 · '세션' 제목 · 안내를 뺀 줄
    rows = rail(ts)
    shown = min(len(board), max(min(len(board), 6), space - max(1, len(rows))))  # 세션 줄은 적어도 6줄, 레일이 짧으면 더
    rows = fit_rail(rows, max(1, space - shown))
    y = 3
    if not rows:
        put(scr, y, 2, clip(L('작업 목록이 없습니다 — 목록을 쓰는 세션은 여기에 흐름이 그려집니다',
                              'No task list — a session that keeps one gets its flow drawn here'), w - 3), curses.A_DIM)
        y += 1
    for line, t in rows:
        x = 2
        for ch in line:
            x = put(scr, y, x, ch, curses.color_pair(1) if ch == '✔' else curses.A_BOLD if ch == '●' else curses.A_DIM)
        if t:
            stamp = task_when(t)
            room = w - x - 2 - (width(stamp) + 1 if stamp else 0)
            put(scr, y, x + 1, clip(f'{t["id"]} {t["text"]}'.strip(), room),
                curses.A_BOLD if t['state'] == 'in_progress' else curses.A_DIM if t['state'] == 'pending' else 0)
            if stamp:
                put(scr, y, w - 1 - width(stamp), stamp, curses.A_DIM)
        y += 1
    y += 1
    put(scr, y, 1, L(f'세션 {len(board)}', f'Sessions {len(board)}'), curses.A_DIM)
    tw = max([width(when(r[3][0])) for r in board[:shown] if r[3][0]] or [0])
    for i, (n, s, _, (at, detail)) in enumerate(board[:shown]):
        y += 1
        if i == shown - 1 and shown < len(board):
            put(scr, y, 1, L(f'… {len(board) - i}개 더 (←→ 로 넘겨 보기)', f'… {len(board) - i} more (←→ to page)'), curses.A_DIM)
            break
        x = put(scr, y, 1, f'{when(at) if at else "":>{tw}} ', curses.A_DIM)
        x = put(scr, y, x, f'{MARK.get(s, "●")} ', job_attr(s))
        x = put(scr, y, x, n, job_attr(s) | (curses.A_REVERSE if i == cur else 0))
        put(scr, y, x + 2, clip(detail, w - x - 3), curses.A_DIM if s == 'working' else 0)


def selftest():
    import tempfile
    rows = [{'at': '1', 'state': 'working', 'detail': '시작', 'text': ''},
            {'at': '2', 'state': 'working', 'detail': '중간 경과', 'text': ''},       # 경과 → 뺀다
            {'at': '3', 'state': 'blocked', 'detail': 'A 로 할까요?', 'text': '…'},
            {'at': '4', 'state': 'blocked', 'detail': '응 A 로', 'text': ''},         # 사용자 말 → 뺀다
            {'at': '5', 'state': 'blocked', 'detail': 'B 도 할까요?', 'text': '…'},   # 새 질문 → 올린다
            {'at': '6', 'state': 'done', 'detail': '끝', 'text': '…'},
            {'at': '7', 'state': 'done', 'detail': '다음 것도 해줘', 'text': ''},     # 사용자 말 → 뺀다
            {'at': '8', 'state': 'working', 'detail': '다시 시작', 'text': ''}]
    assert [e[0] for e in events(rows)[0]] == ['1', '3', '5', '6', '8'], events(rows)
    d = tempfile.mkdtemp()
    for j, name, st in (('a', 'A', 'done'), ('b', 'B', 'working'), ('c', None, None)):
        os.makedirs(os.path.join(d, j, 'tmp'))
        if st:
            with open(os.path.join(d, j, 'state.json'), 'w') as f:
                json.dump({'state': st, 'name': name, 'updatedAt': j}, f)
    tl = os.path.join(d, 'a', 'timeline.jsonl')
    with open(tl, 'w') as f:
        f.write(''.join(json.dumps(r) + '\n' for r in rows[:3]))
    assert [(e[0], e[1]) for e in feed(d)] == [('3', 'A'), ('1', 'A')]
    with open(tl, 'a') as f:  # 이어 쓴 줄만 더 읽고, 경계에서 두 번 올리지 않는다 · 끝나지 않은 줄은 기다린다
        f.write(''.join(json.dumps(r) + '\n' for r in rows[3:]) + '{"at": "9", "sta')
    assert [e[0] for e in feed(d)] == ['8', '6', '5', '3', '1'], feed(d)
    assert jobs(d) == [('B', 'working'), ('A', 'done')]
    # 세션 줄: sessionId 와 마지막 소식(사용자 말·중간 경과를 뺀 마지막 사건, 없으면 state.json 요약)
    assert sessions(d) == [('B', 'working', '', ('b', '')), ('A', 'done', '', ('8', '다시 시작'))], sessions(d)
    e = tempfile.mkdtemp()  # 일하는 중이면 시작 소식('시작') 대신 마지막 경과('중간 경과')
    os.makedirs(os.path.join(e, 'w'))
    with open(os.path.join(e, 'w', 'state.json'), 'w') as f:
        json.dump({'state': 'working', 'name': 'W', 'updatedAt': 'z', 'sessionId': 'S1'}, f)
    with open(os.path.join(e, 'w', 'timeline.jsonl'), 'w') as f:
        f.write(''.join(json.dumps(r) + '\n' for r in rows[:2]))
    assert sessions(e) == [('W', 'working', 'S1', ('2', '중간 경과'))], sessions(e)
    # 일을 남긴 채 턴을 끝내 데몬이 blocked 로 적었어도 지금 busy(sessionId)면 일하는 중 — 노란색은 진짜 입력 대기만(2026-11-27 KNK_ERP)
    os.makedirs(os.path.join(e, 'k'))
    with open(os.path.join(e, 'k', 'state.json'), 'w') as f:
        json.dump({'state': 'blocked', 'tempo': 'active', 'name': 'K', 'updatedAt': 'y', 'sessionId': 'S9'}, f)
    with open(os.path.join(e, 'k', 'timeline.jsonl'), 'w') as f:
        f.write(json.dumps({'at': '1', 'state': 'blocked', 'detail': '아직 끝나지 않았습니다 — 백그라운드로 진행 중', 'text': '…'}) + '\n')
    assert dict((n, st) for n, st, *_ in sessions(e, busy={'S9'}))['K'] == 'working'
    assert dict((n, st) for n, st, *_ in sessions(e))['K'] == 'blocked'
    # 깨어 있는 세션: pid 파일의 시작 시각이 /proc 과 같을 때만 — 이 프로세스로 시험, 다른 시작 시각·죽은 번호·깨진 파일은 뺀다
    if os.path.isdir('/proc/self'):
        pd = tempfile.mkdtemp()
        with open('/proc/self/stat') as fh:
            me = fh.read().rsplit(')', 1)[1].split()[19]
        for pid, start, sid in ((os.getpid(), me, 'S1'), (os.getppid(), '1', 'S2'), (4194999, me, 'S3')):
            with open(os.path.join(pd, f'{pid}.json'), 'w') as f:
                json.dump({'pid': pid, 'procStart': start, 'sessionId': sid}, f)
        with open(os.path.join(pd, 'x.json'), 'w') as f:
            f.write('{')
        assert awake(pd) == {'S1': False}, awake(pd)
        with open(os.path.join(pd, f'{os.getpid()}.json'), 'w') as f:
            json.dump({'pid': os.getpid(), 'procStart': me, 'sessionId': 'S1', 'status': 'busy'}, f)
        assert awake(pd) == {'S1': True}
    assert awake(d, proc=d) is None  # /proc 이 없는 곳(macOS)
    # 작업 목록: 제목 앞 번호 순(1, 1-1, 2, 10) · 번호가 없으면 작업 번호 · 날짜는 번호로 보지 않는다 · 예상 시각은 떼고 due 로
    # · 진행 중은 activeForm · 모르는 상태와 이상한 id 는 뺀다
    td = tempfile.mkdtemp()
    os.makedirs(os.path.join(td, 'S1'))
    for i, st, subj, act in ((10, 'pending', '10. 줄 고치기 (~17:00, 사용자 확인)', ''), (1, 'completed', '1. 재현 안 됨, 닫음', '재현하는 중'),
                             (2, 'in_progress', '2. 판정 빠르게 (~14:30)', '판정 빠르게 하는 중'), (3, 'deleted', '3. 지움', ''),
                             (7, 'completed', '1-1 트러블 슈팅', ''), (8, 'pending', '2026-11-26 업무보고서 쓰기', '')):
        with open(os.path.join(td, 'S1', f'{i}.json'), 'w') as f:
            json.dump({'id': str(i), 'subject': subj, 'activeForm': act, 'status': st, 'blocks': [], 'blockedBy': []}, f)
    ts = tasks('S1', td)
    assert [(t['id'], t['text'], t['due']) for t in ts] == [('1', '재현 안 됨, 닫음', ''), ('1-1', '트러블 슈팅', ''), ('2', '판정 빠르게 하는 중', '14:30'),
                                                           ('8', '2026-11-26 업무보고서 쓰기', ''), ('10', '줄 고치기 (사용자 확인)', '17:00')], ts
    assert tasks('', td) == tasks('../S1', td) == tasks('없음', td) == []
    assert task_when(ts[4]) == '~17:00' and task_when(ts[2]).endswith('~14:30') and task_when(dict(ts[0], at=0)) == ''
    # 레일: 번호 순, 하위 작업은 부모 아래에서 갈라져 들여 가다 뒤에 작업이 있으면 합친다 — 사용자 예시(2026-11-27) 그대로
    T = lambda i, st: {'id': str(i), 'text': '', 'state': st, 'at': 0, 'due': ''}  # noqa: E731
    r = rail([T(1, 'in_progress'), T('1-1', 'completed'), T('1-2', 'in_progress'), T(2, 'pending'), T(3, 'pending')])
    assert [ln for ln, _ in r] == ['●', '├─┐', '│ ✔', '│ ●', '├─┘', '○', '○'] and [t['id'] for _, t in r if t] == ['1', '1-1', '1-2', '2', '3']
    assert [ln for ln, _ in rail([T(1, 'completed'), T(2, 'in_progress'), T('2-1', 'in_progress')])] == ['✔', '●', '└─┐', '  ●']  # 뒤가 없으면 합치지 않는다
    assert [ln for ln, _ in rail([T(1, 'pending'), T('1-1', 'pending'), T('1-1-1', 'pending'), T(2, 'pending')])] == \
        ['○', '├─┐', '│ ○', '│ ├─┐', '│ │ ○', '│ ├─┘', '├─┘', '○']
    assert [ln for ln, _ in rail([T('1-1', 'pending'), T(2, 'pending')])] == ['○', '○'] and rail([]) == []  # 부모 없는 번호는 맨 위
    # 넘치면 앞에서부터 하위까지 다 끝난 맨 위 작업들을 한 줄로 접고, 그래도 넘치면 뒤를 자른다
    long = rail([T(1, 'completed'), T('1-1', 'completed'), T(2, 'completed'), T(3, 'in_progress'), T('3-1', 'pending'), T(4, 'pending')])
    f = fit_rail(long, 7)
    assert fit_rail(long, 10) == long and [ln for ln, _ in f] == ['✔', '●', '├─┐', '│ ○', '├─┘', '○'] and f[0][1]['text'] == L('완료 3개', '3 done')
    assert [ln for ln, _ in fit_rail(long, 4)] == ['✔', '●', '├─┐', '…']
    assert [ln for ln, _ in fit_rail(rail([T(1, 'in_progress'), T('1-1', 'completed'), T(2, 'pending')]), 2)] == ['●', '…']  # 1 이 안 끝났으면 접지 않는다
    # 묶음: 답을 받아 일하는 중이면 state.json 이 blocked 여도 working · busy 면 working · tempo blocked 면 needs
    assert group({'state': 'blocked', 'tempo': 'blocked'}, rows[3]) == 'working'
    assert group({'state': 'blocked', 'tempo': 'blocked'}, rows[4]) == 'blocked'
    assert group({'state': 'done', 'tempo': 'idle'}, rows[5], busy=True) == 'working'
    assert group({'state': 'done', 'tempo': 'idle'}, rows[5]) == 'done'
    assert last_row(tl)['at'] == '8'  # 쓰는 도중인 끝 줄('{"at": "9", "sta')은 건너뛴다
    t = datetime(2026, 10, 21, 2, 0).astimezone()  # 이 PC 시간대 기준으로 만든 시각
    iso = t.astimezone().isoformat()
    assert when(iso, t.date()) == '02:00' and when(iso, datetime(2030, 1, 1).date()) == '10-21 02:00'
    assert clip('가나다', 5) == '가…' and clip('abc', 5) == 'abc'
    print('feed selftest ok')


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        selftest()
    else:
        locale.setlocale(locale.LC_ALL, '')
        os.environ.setdefault('ESCDELAY', '25')
        curses.wrapper(main)
