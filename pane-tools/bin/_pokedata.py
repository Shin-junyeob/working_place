"""포켓몬 도감 데이터를 PokeAPI 공개 데이터(CSV)에서 받아 ~/.claude/pane-tools/pokedex.json 으로 만든다.

저장소에는 포켓몬 데이터를 넣지 않는다(비공식 팬메이드 — README 참고). pokemon 모드를 처음 열 때 한 번 받는다.
종마다 [번호, 한국어 이름, 세대, 진화 전 번호(없으면 0), 포획률, 급(0 일반·1 전설·2 환상), 영어 이름].
`python3 _pokedata.py` 로 직접 다시 받을 수도 있다(새 세대가 나왔을 때).
동료 그림도 같은 원칙 — PokeAPI 기본 도트(96×96, 1~1025번 모두 같은 도트 풍)를 필요할 때 한 장씩 sprites/ 에 받는다.
"""
import colorsys
import csv
import io
import json
import os
import struct
import threading
import urllib.request
import zlib

ROOT = os.path.expanduser('~/.claude/pane-tools')
OUT = f'{ROOT}/pokedex.json'
BASE = 'https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/'
KO, EN = '3', '9'  # PokeAPI 의 언어 번호
SPRITES = f'{ROOT}/sprites'
SPRITE_URL = 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{}.png'


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
                     int(r['capture_rate']), 2 if r['is_mythical'] == '1' else 1 if r['is_legendary'] == '1' else 0, en])
    rows.sort()
    if [r[0] for r in rows] != list(range(1, len(rows) + 1)):
        raise ValueError('PokeAPI 데이터에 빈 번호가 있다')
    return rows


def ensure(force=False):
    """도감 파일이 없으면 받아 만든다. 만든 파일 경로를 돌려준다(네트워크 오류는 그대로 올린다)."""
    if os.path.exists(OUT) and not force:
        return OUT
    rows = build(_csv('pokemon_species'), _csv('pokemon_species_names'))
    os.makedirs(ROOT, exist_ok=True)
    with open(OUT + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(OUT + '.tmp', OUT)
    return OUT


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


_sprites, _fetching = {}, set()


def _local(n):
    """받아 둔 그림 파일 경로. 없으면 뒤에서 받기 시작하고 None — 허브가 멈추지 않게."""
    path = f'{SPRITES}/{n}.png'
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


def _fetch(n, path):
    try:
        with urllib.request.urlopen(SPRITE_URL.format(n), timeout=20) as r:
            data = r.read()
        decode_png(data)  # 깨진 파일은 저장하지 않는다
        os.makedirs(SPRITES, exist_ok=True)
        with open(path + '.tmp', 'wb') as f:
            f.write(data)
        os.replace(path + '.tmp', path)
    except Exception:
        pass


if __name__ == '__main__':
    print(ensure(force=True))
