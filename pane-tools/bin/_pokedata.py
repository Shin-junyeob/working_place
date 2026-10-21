"""포켓몬 도감 데이터를 PokeAPI 공개 데이터(CSV)에서 받아 ~/.claude/pane-tools/pokedex.json 으로 만든다.

저장소에는 포켓몬 데이터를 넣지 않는다(비공식 팬메이드 — README 참고). pokemon 모드를 처음 열 때 한 번 받는다.
종마다 [번호, 한국어 이름, 세대, 진화 전 번호(없으면 0), 포획률, 급(0 일반·1 전설·2 환상), 영어 이름].
`python3 _pokedata.py` 로 직접 다시 받을 수도 있다(새 세대가 나왔을 때).
동료 그림도 같은 원칙 — PokeAPI 기본 도트(96×96, 1~1025번 모두 같은 도트 풍)를 필요할 때 한 장씩 sprites/ 에 받는다.
"""
import colorsys
import csv
import curses
import io
import json
import os
import struct
import threading
import urllib.request
import zlib

ROOT = os.path.expanduser('~/.claude/pane-tools')
OUT = f'{ROOT}/pokedex.json'
DETAIL = f'{ROOT}/pokedex_detail.json'  # 도감 상세(분류·타입·키·몸무게·설명) — 상세 화면을 처음 열 때 받는다
BASE = 'https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/'
KO, EN = '3', '9'  # PokeAPI 의 언어 번호
SPRITES = f'{ROOT}/sprites'
SPRITE_URL = 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{}.png'
SHINY = 10000  # 그림 번호에 더하면 이로치 그림(sprites/pokemon/shiny/<번호>.png) — 허브는 번호를 정수 그대로 쓴다


def _csv(name):
    with urllib.request.urlopen(BASE + name + '.csv', timeout=60) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode('utf-8'))))


def build(species, names):
    """CSV 두 개(행 목록)로 도감 행을 만든다 — 네트워크와 분리해 시험할 수 있게."""
    nm = {}
    for r in names:
        if r['local_language_id'] in (KO, EN):
            nm[(int(r['pokemon_species_id']), r['local_language_id'])] = r['name']
    rows = []
    for r in species:
        n = int(r['id'])
        en = nm.get((n, EN), r['identifier'].title())
        rows.append([n, nm.get((n, KO), en), int(r['generation_id']), int(r['evolves_from_species_id'] or 0),
                     int(r['capture_rate']), 2 if r['is_mythical'] == '1' else 1 if r['is_legendary'] == '1' else 0, en,
                     int(r.get('is_baby') or 0), int(r.get('hatch_counter') or 20)])  # 베이비 · 부화 걸음(알)
    rows.sort()
    if [r[0] for r in rows] != list(range(1, len(rows) + 1)):
        raise ValueError('PokeAPI 데이터에 빈 번호가 있다')
    return rows


def ensure(force=False):
    """도감 파일이 없으면 받아 만든다. 만든 파일 경로를 돌려준다(네트워크 오류는 그대로 올린다)."""
    if os.path.exists(OUT) and not force:
        try:
            with open(OUT, encoding='utf-8') as f:
                if len(json.load(f)[0]) >= 9:  # 옛 형식(베이비·부화 걸음 없음)이면 다시 받는다
                    return OUT
        except (OSError, ValueError, IndexError):
            pass
    rows = build(_csv('pokemon_species'), _csv('pokemon_species_names'))
    os.makedirs(ROOT, exist_ok=True)
    with open(OUT + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(OUT + '.tmp', OUT)
    return OUT


def build_detail(names, flavor, mons, ptypes, tnames):
    """CSV 다섯 개(행 목록) → {번호: [분류 한, 분류 영, [타입 한], [타입 영], 키 dm, 몸무게 hg, 설명 한, 설명 영]}.
    설명은 가장 최근 게임판의 것, 줄바꿈은 빈칸으로. 한국어가 없으면 영어로 채운다."""
    genus, text, ver = {}, {}, {}
    for r in names:
        if r['local_language_id'] in (KO, EN):
            genus[(int(r['pokemon_species_id']), r['local_language_id'])] = r['genus']
    for r in flavor:
        k = (int(r['species_id']), r['language_id'])
        if r['language_id'] in (KO, EN) and int(r['version_id']) >= ver.get(k, -1):
            ver[k], text[k] = int(r['version_id']), ' '.join(r['flavor_text'].split())
    tname = {(int(r['type_id']), r['local_language_id']): r['name'] for r in tnames if r['local_language_id'] in (KO, EN)}
    types = {}
    for r in sorted(ptypes, key=lambda r: int(r['slot'])):
        types.setdefault(int(r['pokemon_id']), []).append(int(r['type_id']))
    out = {}
    for r in mons:
        if r['is_default'] != '1':
            continue
        n, pid = int(r['species_id']), int(r['id'])
        ts = types.get(pid, [])
        en_g, en_t = genus.get((n, EN), ''), text.get((n, EN), '')
        out[n] = [genus.get((n, KO)) or en_g, en_g, [tname.get((t, KO)) or tname.get((t, EN), '') for t in ts],
                  [tname.get((t, EN), '') for t in ts], int(r['height']), int(r['weight']), text.get((n, KO)) or en_t, en_t]
    return out


def ensure_detail(force=False):
    """도감 상세 파일이 없으면 받아 만든다(CSV 5개, 처음 한 번). 네트워크 오류는 그대로 올린다."""
    if os.path.exists(DETAIL) and not force:
        return DETAIL
    d = build_detail(_csv('pokemon_species_names'), _csv('pokemon_species_flavor_text'), _csv('pokemon'),
                     _csv('pokemon_types'), _csv('type_names'))
    os.makedirs(ROOT, exist_ok=True)
    with open(DETAIL + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(DETAIL + '.tmp', DETAIL)
    return DETAIL


def decode_png(data):
    """PNG → RGBA 행렬(행마다 (r, g, b, a)). PokeAPI 그림이 쓰는 팔레트(1~8비트)·RGB·RGBA 8비트만, 인터레이스 없이.
    Pillow 와 7종(1·4·6·7·9세대)을 픽셀 단위로 대조해 일치(2026-10-20)."""
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('PNG 가 아니다')
    i, idat, plte, trns, hdr = 8, b'', [], b'', None
    while i < len(data):
        n, kind = struct.unpack('>I4s', data[i:i + 8])
        body, i = data[i + 8:i + 8 + n], i + 12 + n
        if kind == b'IHDR':
            hdr = struct.unpack('>IIBBBBB', body)
        elif kind == b'PLTE':
            plte = [tuple(body[k:k + 3]) for k in range(0, len(body), 3)]
        elif kind == b'tRNS':
            trns = body
        elif kind == b'IDAT':
            idat += body
    if not hdr:
        raise ValueError('IHDR 없음')
    w, h, depth, ctype, _, _, interlace = hdr
    if interlace or ctype not in (2, 3, 6) or (ctype != 3 and depth != 8):
        raise ValueError(f'지원 안 하는 PNG (색 유형 {ctype}, {depth}비트)')
    ch = {2: 3, 3: 1, 6: 4}[ctype]
    bpp, stride = max(1, ch * depth // 8), (w * ch * depth + 7) // 8
    raw, prev, rows, p = zlib.decompress(idat), bytearray(stride), [], 0
    for _ in range(h):
        f, line = raw[p], bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        for k in range(stride):  # 행 필터 되돌리기: 1 왼쪽 · 2 위 · 3 평균 · 4 Paeth
            a, b = line[k - bpp] if k >= bpp else 0, prev[k]
            c = prev[k - bpp] if k >= bpp else 0
            if f == 1:
                line[k] = (line[k] + a) & 255
            elif f == 2:
                line[k] = (line[k] + b) & 255
            elif f == 3:
                line[k] = (line[k] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[k] = (line[k] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        if ctype == 3:
            per = 8 // depth
            idx = [(line[x // per] >> (8 - depth * (x % per + 1))) & ((1 << depth) - 1) for x in range(w)]
            rows.append([plte[j] + (trns[j] if j < len(trns) else 255,) for j in idx])
        else:
            rows.append([tuple(line[ch * x:ch * x + ch]) + (() if ch == 4 else (255,)) for x in range(w)])
    return rows


def xterm256(r, g, b):
    """가장 가까운 256색 큐브 번호(16~231)."""
    q = lambda v: 0 if v < 48 else 1 if v < 115 else (v - 35) // 40  # noqa: E731
    return 16 + 36 * q(r) + 6 * q(g) + q(b)


def gray256(r, g, b):
    """밝기만 남긴 256색 회색 번호 — 검정 16 · 회색 232~255(24단계) · 흰색 231."""
    v = 0.299 * r + 0.587 * g + 0.114 * b
    return 16 if v < 4 else 231 if v > 246 else 232 + min(23, max(0, round((v - 8) / 10)))


def shrink(px, max_h, max_w):
    """투명 여백을 잘라 내고 칸마다 원본 픽셀을 평균 내 줄인다. 칸은 (r, g, b), 투명은 None.
    6×8 처럼 아주 작게 줄이면 한 점만 집는 방식은 눈·윤곽이 빠져 얼룩지므로 평균을 내고 채도를 35% 올린다
    (7종을 나란히 비교해 고름, 2026-10-20). 덮인 비율 40% 미만인 칸은 투명.
    256색으로는 그릴 때 바꾼다(xterm256 · gray256) — 컬러/회색 설정을 바꿔도 다시 줄일 필요 없게."""
    on = [(x, y) for y, r in enumerate(px) for x, c in enumerate(r) if c[3] > 127]
    if not on:
        return []
    x0, x1 = min(x for x, _ in on), max(x for x, _ in on) + 1
    y0, y1 = min(y for _, y in on), max(y for _, y in on) + 1
    s = max((y1 - y0) / max_h, (x1 - x0) / max_w, 1)
    w, h = max(1, round((x1 - x0) / s)), max(1, round((y1 - y0) / s))

    def cell(x, y):
        xs = range(x0 + int(x * s), max(x0 + int(x * s) + 1, min(x1, x0 + int((x + 1) * s))))
        ys = range(y0 + int(y * s), max(y0 + int(y * s) + 1, min(y1, y0 + int((y + 1) * s))))
        cs = [px[j][i] for j in ys for i in xs]
        op = [c for c in cs if c[3] > 127]
        if len(op) < 0.4 * len(cs):
            return None
        hue, lum, sat = colorsys.rgb_to_hls(*(sum(c[k] for c in op) / len(op) / 255 for k in range(3)))
        return tuple(round(v * 255) for v in colorsys.hls_to_rgb(hue, lum, min(1, sat * 1.35)))
    return [[cell(x, y) for x in range(w)] for y in range(h)]


def encode_png(px):
    """RGBA 행렬 → PNG(필터 없음). Kitty 그래픽으로 보낼 잘라 낸·회색 그림을 만든다."""
    raw = b''.join(b'\x00' + bytes(v for c in row for v in c) for row in px)
    chunk = lambda k, b: struct.pack('>I', len(b)) + k + b + struct.pack('>I', zlib.crc32(k + b))  # noqa: E731
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', len(px[0]), len(px), 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def crop(px, gray=False):
    """투명 여백을 잘라 낸 RGBA 행렬 — gray 면 밝기만 남긴다. 다 투명하면 []."""
    on = [(x, y) for y, r in enumerate(px) for x, c in enumerate(r) if c[3] > 127]
    if not on:
        return []
    x0, x1 = min(x for x, _ in on), max(x for x, _ in on) + 1
    y0, y1 = min(y for _, y in on), max(y for _, y in on) + 1
    g = lambda c: (lambda v: (v, v, v, c[3]))(round(0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]))  # noqa: E731
    return [[g(c) if gray else c for c in r[x0:x1]] for r in px[y0:y1]]


def encode_sixel(px, height):
    """RGBA 행렬 → Sixel(높이 height 픽셀로 늘이거나 줄여서, 칠하지 않은 점은 투명). (문자열, 가로, 세로).
    글자 칸으로는 8칸×3줄에 모양이 안 나와서(2026-10-20 비교) 진짜 픽셀로 그린다 — Windows Terminal 1.22+·WezTerm·foot 등.
    회색 그림이면 32단계, 컬러면 6×6×6 색으로 줄인다."""
    s = height / len(px)
    w = max(1, round(len(px[0]) * s))
    img = [[px[min(len(px) - 1, int(y / s))][min(len(px[0]) - 1, int(x / s))] for x in range(w)] for y in range(height)]
    gray = all(c[0] == c[1] == c[2] for row in px for c in row if c[3] > 127)
    if len({c[:3] for row in px for c in row if c[3] > 127}) <= 255:  # 도트는 보통 수십 색 — 원본 색 그대로(216색으로 깎으면 색이 틀어졌다)
        key, top = (lambda c: tuple(c[:3])), 255  # noqa: E731
    else:
        key = (lambda c: (c[0] * 31 // 255,) * 3) if gray else (lambda c: tuple(v * 5 // 255 for v in c[:3]))  # noqa: E731
        top = 31 if gray else 5
    pal, idx = {}, [[None] * w for _ in range(height)]
    for y, row in enumerate(img):
        for x, c in enumerate(row):
            if c[3] > 127:
                idx[y][x] = pal.setdefault(key(c), len(pal))
    out = ['\x1bP0;1;0q"1;1;%d;%d' % (w, height)]
    out += ['#%d;2;%d;%d;%d' % ((i,) + tuple(round(v * 100 / top) for v in k)) for k, i in pal.items()]
    for band in range(0, height, 6):
        for i in pal.values():
            row = ''.join(chr(63 + sum(1 << k for k in range(6) if band + k < height and idx[band + k][x] == i))
                          for x in range(w))
            if row.strip('?'):
                out.append('#%d%s$' % (i, row))
        out.append('-')
    out.append('\x1b\\')
    return ''.join(out), w, height


_sprites, _fetching = {}, set()


_pairs = {}  # draw_sprite 의 (글자색, 배경색) → curses 색 쌍 번호


def draw_sprite(scr, y, x, grid, gray=False):
    """(r, g, b) 그림을 ▀▄ 반높이 칸으로 — 한 줄에 그림 두 줄. gray 면 밝기만(포켓몬 모드의 [ 그림 c ]).
    색 쌍은 처음 쓸 때 16번부터 만든다."""
    to = gray256 if gray else xterm256
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


def _local(n):
    """받아 둔 그림 파일 경로. 없으면 뒤에서 받기 시작하고 None — 허브가 멈추지 않게."""
    path = f'{SPRITES}/{f"shiny/{n - SHINY}" if n > SHINY else n}.png'
    if os.path.exists(path):
        return path
    if n not in _fetching:  # ponytail: 실패해도 이 허브가 켜져 있는 동안은 다시 안 받는다
        _fetching.add(n)
        threading.Thread(target=_fetch, args=(n, path), daemon=True).start()
    return None


def sprite(n, max_h=6, max_w=8):
    """n번 포켓몬의 작은 그림(shrink 결과) — Kitty 그래픽이 안 되는 터미널에서 ▀▄ 로 그릴 때."""
    key = (n, max_h, max_w)
    if key not in _sprites:
        path = _local(n)
        if not path:
            return None
        with open(path, 'rb') as f:
            _sprites[key] = shrink(decode_png(f.read()), max_h, max_w)
    return _sprites[key]


def sprite_png(n, gray=False):
    """Kitty 그래픽용 (PNG, 가로 픽셀, 세로 픽셀) — 여백을 잘라 내 칸에 꽉 차게. 아직 없으면 None."""
    key = ('png', n, gray)
    if key not in _sprites:
        path = _local(n)
        if not path:
            return None
        with open(path, 'rb') as f:
            px = crop(decode_png(f.read()), gray)
        _sprites[key] = (encode_png(px), len(px[0]), len(px)) if px else None
    return _sprites[key]


def sprite_sixel(n, gray, height):
    """Sixel 용 (문자열, 가로 픽셀, 세로 픽셀) — 여백을 잘라 height 픽셀 높이로. 아직 그림을 안 받았으면 None."""
    key = ('sixel', n, gray, height)
    if key not in _sprites:
        path = _local(n)
        if not path:
            return None
        with open(path, 'rb') as f:
            px = crop(decode_png(f.read()), gray)
        _sprites[key] = encode_sixel(px, height) if px else None
    return _sprites[key]


def sprite_sixel_fit(n, gray, max_w, max_h):
    """max_w×max_h 픽셀 안에 원본 도트를 가장 큰 정수 배로 — 큰 그림(도감 상세)이 뭉개지지 않게. 아직 없으면 None."""
    key = ('fit', n, gray, max_w, max_h)
    if key not in _sprites:
        path = _local(n)
        if not path:
            return None
        with open(path, 'rb') as f:
            px = crop(decode_png(f.read()), gray)
        k = min(max_h // len(px), max_w // len(px[0])) if px else 0
        _sprites[key] = encode_sixel(px, k * len(px) if k else max_h) if px else None
    return _sprites[key]


def _fetch(n, path):
    try:
        with urllib.request.urlopen(SPRITE_URL.format(f'shiny/{n - SHINY}' if n > SHINY else n), timeout=20) as r:
            data = r.read()
        decode_png(data)  # 깨진 파일은 저장하지 않는다
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + '.tmp', 'wb') as f:
            f.write(data)
        os.replace(path + '.tmp', path)
    except Exception:
        pass


if __name__ == '__main__':
    print(ensure(force=True))
