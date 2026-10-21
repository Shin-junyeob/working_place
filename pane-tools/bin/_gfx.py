"""바깥 터미널에 진짜 그림을 놓는다 — Kitty 그래픽(cmux·Ghostty·kitty) 또는 Sixel(Windows Terminal 1.22+·WezTerm·foot).
허브의 동료 그림과 포켓몬 도감 상세가 같이 쓴다. 감지(kitty_ok · sixel_ok)는 curses 를 켜기 전에 한다.
"""
import base64
import fcntl
import os
import re
import select
import struct
import subprocess
import sys
import termios
import time
import tty

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
_six = {'key': None, 't': 0.0, 'box': None}  # 그려 둔 Sixel 그림 · 보낸 시각 · 바깥 터미널 기준 자리(줄, 칸, 칸 수, 줄 수)


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


def tmux_passthrough():
    """tmux 안이면 이 패널만 passthrough 를 켠다 — tmux 3.4 는 바깥 터미널의 칸 픽셀 크기를 몰라(0×0)
    Sixel 을 'SIXEL IMAGE' 글자로 대신 그리므로, 그림은 tmux 를 거치지 않고 바깥 터미널로 바로 보낸다(2026-10-20)."""
    pane = os.environ.get('TMUX_PANE')
    if pane:
        subprocess.run(['tmux', 'set', '-p', '-t', pane, 'allow-passthrough', 'on'], capture_output=True)


def _outer(y, x):
    """패널 안 (y, x) → 바깥 터미널 기준 (y, x). tmux 밖이면 그대로."""
    pane = os.environ.get('TMUX_PANE')
    if pane:  # 패널 위치(+ 위쪽 상태줄)만큼 옮긴다
        info = subprocess.run(['tmux', 'display', '-p', '-t', pane, '#{pane_top} #{pane_left} #{status} #{status-position}'],
                              capture_output=True, text=True).stdout.split()
        if len(info) >= 2:
            y += int(info[0]) + (1 if info[2:] == ['on', 'top'] else 0)
            x += int(info[1])
    return y, x


def _send(seq):
    """바깥 터미널로 — tmux 안이면 passthrough 로 감싸 tmux 를 건너뛴다."""
    if os.environ.get('TMUX_PANE'):
        seq = '\x1bPtmux;' + seq.replace('\x1b', '\x1b\x1b') + '\x1b\\'
    sys.stdout.write(seq)
    sys.stdout.flush()


def sixel_show(y, x, key, data, cols, rows):
    """(y, x) 칸에 Sixel 그림을 놓는다. 같은 그림이면 30초에 한 번만 다시 놓는다(tmux 가 화면을 다시 그려 지웠을 때 대비)
    — 자주 보내면 깜빡인다. 키를 누르면 바로 다시 놓는다(sixel_touch)."""
    if _six['key'] == key and time.time() - _six['t'] < 30:
        return
    oy, ox = _outer(y, x)
    if _six['box'] and _six['box'][:2] != (oy, ox):
        sixel_hide()
    _send(f'\x1b7\x1b[{oy + 1};{ox + 1}H{data}\x1b8')
    _six.update(key=key, t=time.time(), box=(oy, ox, cols, rows))


def sixel_hide():
    """놓아 둔 그림 자리를 빈칸으로 덮어 지운다 — tmux 는 이 그림을 모르니 허브가 직접 지워야 한다."""
    box = _six['box']
    if box:
        oy, ox, cols, rows = box
        _send('\x1b7' + ''.join(f'\x1b[{oy + 1 + r};{ox + 1}H' + ' ' * cols for r in range(rows)) + '\x1b8')
    _six.update(key=None, box=None)


def sixel_touch():
    """다음 화면에서 그림을 다시 놓게 한다 — 키를 눌러 화면이 바뀔 때."""
    _six['t'] = 0.0
