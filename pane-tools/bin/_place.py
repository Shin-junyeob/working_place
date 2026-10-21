"""허브의 [ 설정 ] — /mods 를 어디에 띄울지 고른다. 고른 값은 ~/.claude/pane-tools/settings.json 에 적고,
/mods(register.ts)가 실행할 때마다 읽어 /config 값보다 먼저 쓴다 — 다시 불러올 필요 없이 다음 /mods 부터.
r 로 지우면 다시 /config 를 따른다.
"""
import curses
import json
import os

import _lang
from _lang import L
from memo import cw, getkey, put

KEYS = ('launcher', 'tmuxTarget', 'followPane', 'command', 'feedTarget')
CONFIG = os.path.expanduser('~/.claude/settings.json')


def from_config(path=CONFIG):
    """/config 에 적힌 pane-tools 설정(폴더로 불러오면 @inline, 마켓이면 @working-place)."""
    try:
        with open(path, encoding='utf-8') as f:
            cfgs = json.load(f).get('pluginConfigs') or {}
    except (OSError, ValueError):
        return {}
    for k, v in cfgs.items():
        if k.startswith('pane-tools@'):
            return dict(v.get('options') or {})
    return {}


def current(config=CONFIG):
    """지금 /mods 가 쓰는 값 — 허브에서 고른 것이 있으면 그것, 없으면 /config, 그것도 없으면 기본값."""
    o = {'launcher': 'auto', 'tmuxTarget': '', 'followPane': '', 'command': '', 'feedTarget': ''}
    o.update({k: str(v) for k, v in from_config(config).items() if k in KEYS})
    o.update({k: str(_lang.get(k)) for k in KEYS if _lang.get(k) is not None})
    return o


def mode(o):
    """설정 → 화면의 고르기 칸 하나."""
    if o['launcher'] == 'tmux':
        return 'pane' if o['tmuxTarget'] else 'split'
    return o['launcher'] if o['launcher'] in ('window', 'command') else 'auto'


def save(choice, value=''):
    """고르기 칸 → 설정 값(settings.json)."""
    launcher, target, command = {
        'auto': ('auto', '', None), 'window': ('window', '', None), 'split': ('tmux', '', None),
        'pane': ('tmux', value, None), 'command': ('command', '', value)}[choice]
    _lang.put('launcher', launcher)
    _lang.put('tmuxTarget', target)
    if command is not None:
        _lang.put('command', command)


def reset():
    for k in KEYS:
        _lang.put(k, None)


def ask(scr, y, prompt, value):
    """한 줄 입력 — Enter 정하기 · Esc 취소(None)."""
    curses.curs_set(1)
    try:
        while True:
            h, w = scr.getmaxyx()
            scr.move(y, 0)
            scr.clrtoeol()
            x = put(scr, y, 1, prompt, curses.A_BOLD)
            x = put(scr, y, x + 1, value)
            scr.move(y, min(x, w - 1))
            scr.refresh()
            try:
                k = scr.get_wch()
            except curses.error:
                continue
            if k in ('\n', '\r', curses.KEY_ENTER):
                return value.strip()
            if k == '\x1b':
                return None
            if k in (curses.KEY_BACKSPACE, '\x7f', '\b'):
                value = value[:-1]
            elif isinstance(k, str) and k.isprintable():
                value += k
    finally:
        curses.curs_set(0)


def screen(scr):
    sel = None
    while True:
        o = current()
        rows = [('auto', L('자동', 'Auto'), L('tmux 안이면 지금 창을 나누고, 아니면 새 창', 'split in tmux, else a new window')),
                ('window', L('새 창', 'New window'), L('WSL 은 Windows Terminal, macOS 는 Terminal', 'Windows Terminal on WSL, Terminal on macOS')),
                ('split', L('현재 창에 서브패널', 'Split this window'), L('tmux 지금 창을 오른쪽으로 나눈다', 'split the current tmux window to the right')),
                ('pane', L('다른 패널', 'Another pane'), o['tmuxTarget'] or L('Enter 로 패널 입력 (예: dev:0.3)', 'Enter a pane (e.g. dev:0.3)')),
                ('command', L('사용자 명령', 'Custom command'), o['command'] or L('{cmd} 자리를 넣은 명령 (예: wezterm cli split-pane -- bash -lc {cmd})',
                                                                              'a command with {cmd} (e.g. wezterm cli split-pane -- bash -lc {cmd})')),
                ('follow', L('따라갈 패널', 'Follow pane'), o['followPane'] or L('비움 — /mods 를 입력한 세션', 'empty — the session that ran /mods')),
                ('feed', L('피드 패널', 'Feed pane'), o['feedTarget'] or L('비움 — /mods 때 피드는 안 띄움(허브 버튼으로)', 'empty — /mods does not open the feed'))]
        if sel is None:
            sel = [r[0] for r in rows].index(mode(o))
        h, w = scr.getmaxyx()
        scr.erase()
        head = L(' 설정 — /mods 를 띄울 곳 ', ' Settings — where /mods opens ')
        put(scr, 0, 0, head + ' ' * max(0, w - sum(cw(c) for c in head)), curses.A_REVERSE)
        y = 2
        for i, (key, name, hint) in enumerate(rows):
            if key == 'follow':
                y += 1
                put(scr, y, 1, L('허브·메모가 따라갈 세션 · /mods 때 같이 띄울 피드', 'Session to follow · feed opened with /mods'), curses.A_BOLD)
                y += 1
                mark = '  '
            elif key == 'feed':
                mark = '  '
            else:
                mark = '(•)' if key == mode(o) else '( )'
            x = put(scr, y, 1, f'{mark} {name}', curses.A_REVERSE if i == sel else curses.A_BOLD)
            put(scr, y, x + 2, hint, curses.A_DIM)
            y += 1
        y += 1
        put(scr, y, 1, L('바로 다음 /mods 부터 적용 · /config 보다 먼저', 'Applies from the next /mods · overrides /config'), curses.A_DIM)
        put(scr, h - 1, 1, L('↑↓ 고르기 · Enter/Space 정하기 · r /config 값으로 · q 돌아가기',
                             '↑↓ move · Enter/Space choose · r use /config · q back'), curses.A_DIM)
        scr.refresh()
        k = getkey(scr, 1000)
        if k in (ord('q'), 27):
            return
        if k == curses.KEY_UP:
            sel = (sel - 1) % len(rows)
        elif k == curses.KEY_DOWN:
            sel = (sel + 1) % len(rows)
        elif k == ord('r'):
            reset()
            sel = None
        elif k in (10, 13, curses.KEY_ENTER, ord(' ')):
            key = rows[sel][0]
            if key in ('auto', 'window', 'split'):
                save(key)
            elif key == 'pane':
                v = ask(scr, h - 2, L('패널:', 'Pane:'), o['tmuxTarget'] or 'dev:0.3')
                if v:
                    save('pane', v)
            elif key == 'command':
                v = ask(scr, h - 2, L('명령:', 'Command:'), o['command'])
                if v and '{cmd}' in v:
                    save('command', v)
            elif key == 'feed':
                v = ask(scr, h - 2, L('피드 패널(예: dev:0.2, 비우면 안 띄움):', 'Feed pane (e.g. dev:0.2, empty = none):'), o['feedTarget'])
                if v is not None:
                    _lang.put('feedTarget', v)
            else:
                v = ask(scr, h - 2, L('따라갈 패널(비우면 /mods 세션):', 'Follow pane (empty = /mods session):'), o['followPane'])
                if v is not None:
                    _lang.put('followPane', v)


def selftest():
    import tempfile
    d = tempfile.mkdtemp()
    _lang.PATH, _lang.ROOT = f'{d}/settings.json', d
    cfg = f'{d}/claude.json'
    with open(cfg, 'w') as f:
        json.dump({'pluginConfigs': {'pane-tools@inline': {'options': {'launcher': 'tmux', 'tmuxTarget': 'dev:0.3'}}}}, f)
    _lang.put('lang', 'ko')
    assert mode(current(cfg)) == 'pane' and current(cfg)['tmuxTarget'] == 'dev:0.3'  # /config 를 따른다
    save('split')
    assert mode(current(cfg)) == 'split' and current(cfg)['tmuxTarget'] == ''  # 허브에서 고른 게 먼저
    save('command', 'x {cmd}')
    assert mode(current(cfg)) == 'command' and current(cfg)['command'] == 'x {cmd}'
    reset()
    assert mode(current(cfg)) == 'pane' and _lang.get('lang') == 'ko'  # 지우면 다시 /config, 다른 설정은 남는다
    print('place selftest ok')


if __name__ == '__main__':
    selftest()
