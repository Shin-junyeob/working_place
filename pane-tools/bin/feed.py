#!/usr/bin/env python3
"""세션 활동 피드 — claude agents 의 세션들이 끝내거나(✔) 묻거나(▲) 시작한(●) 순간을 최근 것부터 한 줄씩.

데몬이 작업마다 남기는 ~/.claude/jobs/<id>/timeline.jsonl({at, state, detail, text})을 읽는다. 쓰는 건 없다.
사용자가 보낸 말(text 가 빈 줄)과 작업 중간 경과는 빼고, 상태가 바뀌었거나 끝/질문의 요약이 새로 바뀐 줄만.
↑↓ 스크롤 · q 닫기. `python3 feed.py --selftest` 로 거르기·정렬을 점검한다.
"""
import curses
import json
import locale
import os
import sys
import time
from datetime import datetime

from _lang import L
from memo import cw, focus_reporting, getkey, put

JOBS = os.path.expanduser('~/.claude/jobs')
# claude agents 의 상태 묶음 — needs 가 맨 위, 끝난 것은 아래
ORDER = {'blocked': 0, 'needs_input': 0, 'failed': 1, 'working': 2, 'done': 3}
MARK = {'done': '✔', 'blocked': '▲', 'needs_input': '▲', 'failed': '✖'}


def jobs(folder=JOBS):
    """claude agents 목록의 세션 [(이름, 상태)] — needs → working → done, 묶음 안에선 최근 것 먼저.
    지운 작업은 폴더에 tmp/ 만 남으므로 state.json 이 있는 것만 목록에 있는 것이다."""
    out = []
    for j in os.listdir(folder) if os.path.isdir(folder) else []:
        try:
            with open(os.path.join(folder, j, 'state.json'), encoding='utf-8') as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        out.append((d.get('updatedAt') or '', d.get('name') or j, d.get('state') or ''))
    out.sort(reverse=True)  # updatedAt 은 ISO 시각이라 글자 순 = 시간 순
    out.sort(key=lambda r: ORDER.get(r[2], 2))  # 안정 정렬 — 묶음 안에선 최근 것 먼저가 유지된다
    return [r[1:] for r in out]


def job_attr(state):
    """claude agents 와 같은 색 — completed 녹색, needs 노랑, working 회색 (색 짝 1 녹 · 2 노 · 3 빨)."""
    if state == 'done':
        return curses.color_pair(1)
    if ORDER.get(state) == 0:
        return curses.color_pair(2) | curses.A_BOLD
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
    for i, c in ((1, curses.COLOR_GREEN), (2, curses.COLOR_YELLOW), (3, curses.COLOR_RED)):
        curses.init_pair(i, c, -1)
    focus_reporting(True)
    top = 0
    while True:
        h, w = scr.getmaxyx()
        items = feed()
        top = max(0, min(top, len(items) - (h - 2)))
        scr.erase()
        head = L(' 세션 활동 ', ' Session activity ')
        put(scr, 0, 0, head + ' ' * max(0, w - sum(cw(c) for c in head)), curses.A_REVERSE)
        if not items:
            put(scr, 2, 1, L('아직 기록이 없습니다 — claude agents 로 띄운 세션이 일하면 여기에 쌓입니다',
                             'Nothing yet — sessions started from claude agents show up here'), curses.A_DIM)
        for i, (at, name, st, detail) in enumerate(items[top:top + h - 2]):
            x = put(scr, i + 1, 1, f'{when(at):>11} ', curses.A_DIM)
            x = put(scr, i + 1, x, f'{MARK.get(st, "●")} {name}  ', job_attr(st))
            put(scr, i + 1, x, clip(detail, w - x - 1), curses.A_DIM if st == 'working' else 0)
        put(scr, h - 1, 1, L('↑↓ 스크롤 · q 닫기', '↑↓ scroll · q close'), curses.A_DIM)
        scr.refresh()
        key = getkey(scr, 2000)
        if key in (ord('q'), 27):
            break
        if key == curses.KEY_UP:
            top = max(0, top - 1)
        elif key == curses.KEY_DOWN:
            top += 1
    focus_reporting(False)


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
