#!/usr/bin/env python3
"""포켓몬 — Claude 를 쓴 만큼(누적 토큰) 포켓몬을 발견해 잡고, 한 마리를 데리고 다니며 진화시켜 세대별 도감을 채운다.

누적 토큰: 각 세션의 pane-tools mod 가 usage/<sid>.json 의 gained 에 적는 값(컨텍스트가 늘어난 만큼)을 모두 더한 것.
- 도감은 세대별(1~9세대). 데이터는 처음 열 때 PokeAPI 에서 받아 ~/.claude/pane-tools/pokedex.json 에 둔다(_pokedata.py). 지금 세대를 다 채우면 다음 세대가 열리고, 야생에선 지금 세대 포켓몬만 나온다.
- 나오는 순서: 스타팅·피카츄·이브이 → 일반(원작 포획률 높은 = 흔한 것부터) → 전설 → 환상. 앞쪽 WINDOW 마리 중 무작위.
- ENCOUNTER_EVERY 토큰마다 탐색 1회. 볼 BALLS 개 + 보유 볼, 다 빗나가면 도망(나중에 다시 나온다). 잡으면 보유 볼 +1.
- 지금 가방에 있는 종은 다른 종의 1/10 확률로만 나오고(BOXED_WEIGHT), 나오면 잡지 않고 급에 따라 몬스터볼 1~5개로 바꾼다(dupe_balls).
- 동료는 한 마리. 데리고 있는 동안 쌓인 토큰이 경험치 — STAGE_XP 를 넘으면 진화. 아직 안 열린 세대로의 진화는 그 세대가 열린 뒤, 이미 가방에 있는 모습으로는 진화하지 않는다.
상태는 ~/.claude/pane-tools/pokemon.json. 허브는 summary() 로 동료를 보여 준다.
`python3 pokemon.py --selftest` 로 규칙을 점검한다(데이터가 없으면 먼저 받는다).
"""
import curses
import glob
import json
import locale
import os
import random
import sys

import _lang
import _pokedata
from _lang import L
from memo import put  # 한글 2칸 폭을 맞춰 그리는 함수 — 메모장과 같이 쓴다

ROOT = os.path.expanduser('~/.claude/pane-tools')
ENCOUNTER_EVERY = 30_000
STAGE_XP = [150_000, 400_000]  # 1→2단계, 2→3단계
BALLS = 3
WINDOW = 4  # 순서상 앞쪽 몇 마리 중에서 나오나
BOXED_WEIGHT = 0.1  # 지금 가방에 있는 종은 다른 종의 1/10 만 나온다(wild_odds)

DEX, GENS, GEN_SIZE, CHILDREN = {}, 0, {}, {}  # load_dex() 가 채운다


def load_dex():
    """받아 둔 도감(pokedex.json)을 읽는다. 없으면 False — 허브는 그대로 두고, pokemon 화면이 처음 열릴 때 받는다."""
    global DEX, GENS, GEN_SIZE, CHILDREN
    try:
        with open(_pokedata.OUT, encoding='utf-8') as f:
            DEX = {r[0]: r for r in json.load(f)}  # 번호 → [번호, 한국어, 세대, 진화 전, 포획률, 급, 영어]
    except (OSError, ValueError):
        return False
    GENS = max(r[2] for r in DEX.values())
    GEN_SIZE = {g: sum(1 for r in DEX.values() if r[2] == g) for g in range(1, GENS + 1)}
    CHILDREN = {}
    for r in DEX.values():
        if r[3]:
            CHILDREN.setdefault(r[3], []).append(r[0])
    return True


load_dex()
STARTERS = {1, 4, 7, 152, 155, 158, 252, 255, 258, 387, 390, 393, 495, 498, 501, 650, 653, 656,
            722, 725, 728, 810, 813, 816, 906, 909, 912, 25, 133, 172}


def gen(n):
    return DEX[n][2]


def depth(n):
    """진화 단계(0부터). 그 포켓몬보다 나중 세대에 추가된 진화 전(피츄 같은 베이비)은 세지 않는다 — 1세대 피카츄는 1단계."""
    d, g = 0, gen(n)
    while DEX[n][3] and gen(DEX[n][3]) <= g:
        n, d = DEX[n][3], d + 1
    return d


def order_key(n):
    """나오는 순서: 스타팅류 → 일반(흔한 것부터) → 전설 → 환상."""
    tier = 0 if n in STARTERS else {0: 1, 1: 3, 2: 4}[DEX[n][5]]
    return tier, -DEX[n][4], n


def wild_ok(n):
    """야생에서 나올 수 있나 — 진화 전이 없거나 다른 세대에 있으면. 같은 세대 진화형은 진화로만."""
    pre = DEX[n][3]
    return not pre or gen(pre) != gen(n)


def descendants(n):
    out, todo = [], list(CHILDREN.get(n, []))
    while todo:
        c = todo.pop()
        out.append(c)
        todo += CHILDREN.get(c, [])
    return out


def current_gen(st):
    caught = set(st['caught'])
    for g in range(1, GENS + 1):
        if sum(1 for n in caught if gen(n) == g) < GEN_SIZE[g]:
            return g
    return None  # 전 세대 완성


def wild_pool(st):
    """지금 세대에서 나올 차례인 포켓몬들, 순서대로. 아직 못 잡은 같은 세대 진화형이 남은 계열도 계속 나온다."""
    g, caught = current_gen(st), set(st['caught'])
    if g is None:
        return []
    pool = [n for n in DEX if gen(n) == g and wild_ok(n)
            and (n not in caught or any(gen(d) == g and d not in caught for d in descendants(n)))]
    return sorted(pool, key=order_key)


def wild_odds(st):
    """이번 탐색의 후보와 가중치 [(번호, 가중치)] — 가방에 없는 앞쪽 WINDOW 마리는 1, 그 사이에 낀 가방 속 종은
    BOXED_WEIGHT. 가방 속 종은 진화형을 동료 진화로만 얻으니 나와 봐야 볼로 바뀔 뿐인데, 그대로 두면 맨 앞 칸을
    막아 같은 포켓몬만 나왔다(진화 전 스타팅 3종이 4칸 중 3칸). 아예 빼지는 않고 드물게만 나오게 한다."""
    pool, boxed = wild_pool(st), {m['id'] for m in st['box']}
    fresh = [n for n in pool if n not in boxed][:WINDOW]
    if not fresh:  # 남은 게 전부 가방 속 종이면 그것들끼리
        return [(n, 1) for n in pool[:WINDOW]]
    front = pool[:pool.index(fresh[-1]) + 1]
    return [(n, BOXED_WEIGHT if n in boxed else 1) for n in front]


def name(n):
    return L(DEX[n][1], DEX[n][6])


def catch_rate(n):
    if DEX[n][5]:
        return 0.2 if DEX[n][5] == 1 else 0.15
    return 0.35 + 0.55 * DEX[n][4] / 255  # 원작 포획률이 높을수록 잘 잡힌다


def total_tokens(root=ROOT):
    t = 0
    for f in glob.glob(f'{root}/usage/*.json'):
        try:
            with open(f, encoding='utf-8') as fh:
                t += int(json.load(fh).get('gained') or 0)
        except (OSError, ValueError, TypeError):
            pass
    return t


def new_state():
    return {'used': 0, 'box': [], 'partner': None, 'base': 0, 'seen': [], 'caught': [], 'wild': None, 'balls': 0}


def load(root=ROOT):
    try:
        with open(f'{root}/pokemon.json', encoding='utf-8') as f:
            return {**new_state(), **json.load(f)}
    except (OSError, ValueError):
        return new_state()


def save(st, root=ROOT):
    os.makedirs(root, exist_ok=True)
    p = f'{root}/pokemon.json'
    with open(p + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(st, f, ensure_ascii=False)
    os.replace(p + '.tmp', p)


def tickets(st, t):
    return t // ENCOUNTER_EVERY - st['used']


def partner_xp(st, t):
    if st['partner'] is None:
        return 0
    return st['box'][st['partner']]['xp'] + max(0, t - st['base'])


def dupe_balls(n):
    """이미 가방에 있는 종이 나왔을 때 바꿔 주는 볼 — 흔할수록 적고 전설·환상은 5개."""
    if DEX[n][5]:
        return 5
    cap = DEX[n][4]
    return 1 if cap >= 190 else 2 if cap >= 90 else 3 if cap >= 45 else 4


def opened_evolutions(st, n):
    """지금 열린 세대 안의 다음 모습들(가방 상태와 무관)."""
    g = current_gen(st) or GENS
    return [c for c in CHILDREN.get(n, []) if gen(c) <= g]


def evolutions(st, n):
    """진화할 수 있는 다음 모습들 — 열린 세대 안에서, 가방에 아직 없는 것만. 이상해풀이 가방에 있으면 이상해씨는
    진화하지 않는다: 같은 모습이 두 마리가 되지 않고, 이상해씨는 가방에 남아 야생에서 계속 1/10 로만 나온다."""
    boxed = {m['id'] for m in st['box']}
    return [c for c in opened_evolutions(st, n) if c not in boxed]


def need_xp(n):
    """진화에 필요한 경험치. 진화형이 없으면 None."""
    return STAGE_XP[min(depth(n), 1)] if n in CHILDREN else None


def can_evolve(st, t):
    if st['partner'] is None:
        return False
    n = st['box'][st['partner']]['id']
    return bool(evolutions(st, n)) and partner_xp(st, t) >= need_xp(n)


def _mark(st, key, n):
    if n not in st[key]:
        st[key].append(n)


def explore(st, t, rng=random):
    if st['wild'] or tickets(st, t) <= 0:
        return None
    odds = wild_odds(st)
    if not odds:
        return None
    st['used'] += 1
    n = rng.choices([n for n, _ in odds], weights=[w for _, w in odds])[0]
    _mark(st, 'seen', n)
    if any(m['id'] == n for m in st['box']):  # 이미 가방에 있다 → 몬스터볼로
        k = dupe_balls(n)
        st['balls'] += k
        return n, k
    st['wild'] = {'id': n, 'balls': BALLS}
    return n, 0


def set_partner(st, t, i):
    if st['partner'] is not None:  # 지금 동료가 쌓은 경험치는 그 포켓몬에게 남긴다
        st['box'][st['partner']]['xp'] = partner_xp(st, t)
    st['partner'], st['base'] = i, t


def throw(st, t, rng=random):
    """볼 하나. 'caught' / 'missed' / 'fled'."""
    w = st['wild']
    if not w or w['balls'] + st['balls'] <= 0:
        return None
    if w['balls'] > 0:  # 만날 때 받은 볼부터, 다 쓰면 보유 볼
        w['balls'] -= 1
    else:
        st['balls'] -= 1
    if rng.random() < catch_rate(w['id']):
        st['box'].append({'id': w['id'], 'xp': 0})
        _mark(st, 'caught', w['id'])
        st['wild'] = None
        st['balls'] += 1  # 포획 보상 — 중복이 안 나오니 볼은 여기서 쌓인다
        if st['partner'] is None:
            set_partner(st, t, len(st['box']) - 1)
        return 'caught'
    if w['balls'] + st['balls'] <= 0:
        st['wild'] = None
        return 'fled'
    return 'missed'


def evolve(st, t, rng=random):
    if not can_evolve(st, t):
        return None
    mon = st['box'][st['partner']]
    mon['id'], mon['xp'] = rng.choice(evolutions(st, mon['id'])), 0
    st['base'] = t
    _mark(st, 'seen', mon['id'])
    _mark(st, 'caught', mon['id'])
    return mon['id']


def fmt_tok(n):
    return f'{n / 1e6:.2f}M' if n >= 1e6 else f'{n / 1e3:.0f}k' if n >= 1e3 else str(n)


def dex_text(st):
    g, caught = current_gen(st), set(st['caught'])
    if g is None:
        return L(f'도감 완성! {len(caught)}/{len(DEX)}', f'Pokédex complete! {len(caught)}/{len(DEX)}')
    have = sum(1 for n in caught if gen(n) == g)
    return L(f'도감 {g}세대 {have}/{GEN_SIZE[g]} · 전체 {len(caught)}/{len(DEX)}',
             f'Dex Gen {g} {have}/{GEN_SIZE[g]} · total {len(caught)}/{len(DEX)}')


def evo_status(st, t):
    """동료의 진화 상태: ('final',) · ('locked',) · ('blocked', 진화형들) · ('ready',) · ('progress', 경험치, 필요치)."""
    n = st['box'][st['partner']]['id']
    if n not in CHILDREN:
        return ('final',)
    opened = opened_evolutions(st, n)
    if not opened:
        return ('locked',)
    if not evolutions(st, n):
        return ('blocked', opened)  # 진화형이 이미 가방에 있다
    xp, need = partner_xp(st, t), need_xp(n)
    return ('ready',) if xp >= need else ('progress', xp, need)


def blocked_text(opened):
    if len(opened) == 1:
        return L(f'{name(opened[0])}(이)가 가방에 있어 진화 못 함', f"can't evolve — {name(opened[0])} is already in the bag")
    return L('진화형이 모두 가방에 있어 진화 못 함', "can't evolve — every evolution is already in the bag")


def summary(root=ROOT):
    """허브용 한두 줄: (글, 강조여부, 진행률 또는 None)."""
    if not DEX:  # 아직 도감을 안 받았다 — 받는 건 pokemon 화면이 한다
        return [(L('포켓몬 데이터 없음 — [ pokemon ] 을 열면 받아 옵니다',
                   'No Pokédex yet — open [ pokemon ] to download it'), False, None)]
    st, t = load(root), total_tokens(root)
    lines = []
    if st['partner'] is None:
        lines.append((L('동료 없음 — [ pokemon ] 에서 탐색해 잡아 보세요',
                        'No partner — explore and catch one in [ pokemon ]'), False, None))
    else:
        n, ev = st['box'][st['partner']]['id'], evo_status(st, t)
        p = L(f'동료 {name(n)} · ', f'Partner {name(n)} · ')
        if ev[0] == 'final':
            lines.append((p + L('최종 진화', 'fully evolved'), False, None))
        elif ev[0] == 'locked':
            lines.append((p + L('다음 세대가 열리면 진화', 'evolves once the next generation opens'), False, None))
        elif ev[0] == 'blocked':
            lines.append((p + blocked_text(ev[1]), False, None))
        elif ev[0] == 'ready':
            lines.append((p + L('✨ 진화 가능!', '✨ ready to evolve!'), True, 1.0))
        else:
            left = fmt_tok(ev[2] - ev[1])
            lines.append((p + L(f'진화까지 {left}', f'{left} to evolve'), False, ev[1] / ev[2]))
    k = tickets(st, t)
    nxt = fmt_tok(ENCOUNTER_EVERY - t % ENCOUNTER_EVERY)
    extra = L('야생 포켓몬이 기다리는 중!', 'A wild Pokémon is waiting!') if st['wild'] else \
        L(f'탐색 {k}회 가능', f'{k} explore{"" if k == 1 else "s"} ready') if k > 0 else \
        L(f'다음 탐색까지 {nxt}', f'next explore in {nxt}')
    lines.append((f'{dex_text(st)} · {extra}', bool(st['wild'] or k > 0), None))
    return lines


def partner_id(root=ROOT):
    """허브에 그림을 띄울 동료의 번호 — 없으면 None."""
    st = load(root)
    return None if st['partner'] is None else st['box'][st['partner']]['id']


# ── 화면 ──
def bar(frac, width):
    f = round(max(0.0, min(1.0, frac)) * width)
    return '█' * f + '░' * (width - f)


def main(scr):
    curses.curs_set(0)
    scr.keypad(True)
    scr.timeout(2000)
    curses.mousemask(curses.ALL_MOUSE_EVENTS)
    curses.mouseinterval(0)
    view, top, msg, dg, sel = 'main', 0, '', 1, 0  # sel: 가방에서 커서가 놓인 줄
    if not DEX:  # 처음 열었다 — 도감을 받아 온다
        put(scr, 0, 0, L('PokeAPI 에서 포켓몬 도감을 받는 중…', 'Downloading the Pokédex from PokeAPI…'))
        scr.refresh()
        try:
            _pokedata.ensure()
            if not load_dex():
                raise ValueError(L('받은 도감 파일을 읽지 못했습니다', 'Could not read the downloaded Pokédex'))
        except Exception as e:  # 네트워크 오류 등 — 죽지 말고 보여 준다
            scr.erase()
            put(scr, 0, 0, L('포켓몬 도감을 받지 못했습니다:', 'Could not download the Pokédex:'), curses.A_BOLD)
            put(scr, 1, 0, f'{type(e).__name__}: {e}')
            put(scr, 3, 0, L('q 를 누르면 닫습니다', 'Press q to close'), curses.A_DIM)
            scr.refresh()
            scr.timeout(-1)
            while scr.getch() not in (ord('q'), 27):
                pass
            return
    while True:
        st, t = load(), total_tokens()
        h, w = scr.getmaxyx()
        scr.erase()
        put(scr, 0, 0, L(f' 포켓몬 · 누적 {fmt_tok(t)} 토큰 · ', f' Pokémon · {fmt_tok(t)} tokens total · ') + dex_text(st)
            + ' ' * w, curses.A_REVERSE)
        btns = []

        def button(y, x, label, act):
            text = f'[ {label} ]'
            end = put(scr, y, x, text, curses.A_BOLD | curses.A_REVERSE)
            btns.append((y, x, end, act))
            return end + 2

        if view == 'main':
            y = 2
            if st['partner'] is None:
                put(scr, y, 1, L('아직 동료가 없습니다. 풀숲을 탐색해 보세요.', 'No partner yet. Try exploring the tall grass.'))
            else:
                n = st['box'][st['partner']]['id']
                put(scr, y, 1, L(f'동료  {name(n)}  (No.{n:04d}, {gen(n)}세대 · {depth(n) + 1}단계)',
                                  f'Partner  {name(n)}  (No.{n:04d}, Gen {gen(n)} · stage {depth(n) + 1})'), curses.A_BOLD)
                ev = evo_status(st, t)
                if ev[0] == 'final':
                    put(scr, y + 1, 1, L('더 진화하지 않는 포켓몬입니다.', 'This Pokémon does not evolve any further.'), curses.A_DIM)
                elif ev[0] == 'locked':
                    put(scr, y + 1, 1, L('진화형은 다음 세대 도감이 열리면 만날 수 있다.',
                                          'Its evolution unlocks with the next generation.'), curses.A_DIM)
                elif ev[0] == 'blocked':
                    put(scr, y + 1, 1, blocked_text(ev[1]), curses.A_DIM)
                elif ev[0] == 'ready':
                    x = put(scr, y + 1, 1, L('✨ 진화할 수 있다!', '✨ It can evolve!'), curses.A_BOLD)
                    button(y + 1, x + 3, L('진화 v', 'evolve v'), 'evolve')
                else:
                    x = put(scr, y + 1, 1, L('진화 ', 'Evolve '))
                    put(scr, y + 1, x, f'{bar(ev[1] / ev[2], 24)} {fmt_tok(ev[1])}/{fmt_tok(ev[2])}')
            y = 6
            if st['wild']:
                wn = name(st['wild']['id'])
                put(scr, y, 1, L(f'앗! 야생의 {wn}(이)가 나타났다!', f'Oh! A wild {wn} appeared!'), curses.A_BOLD)
                left = st['wild']['balls'] or st['balls']
                own = '' if st['wild']['balls'] else L(' 보유', ' owned')
                x = button(y + 1, 1, L(f'몬스터볼 b ({left}{own})', f'Poké Ball b ({left}{own})'), 'throw')
                button(y + 1, x, L('도망 r', 'run r'), 'run')
            else:
                k = tickets(st, t)
                if k > 0:
                    put(scr, y, 1, L(f'탐색 {k}회 가능 · 몬스터볼 {st["balls"]}개',
                                     f'{k} explore{"" if k == 1 else "s"} ready · Poké Balls {st["balls"]}'))
                    button(y + 1, 1, L('풀숲 탐색 s', 'explore grass s'), 'explore')
                else:
                    left = ENCOUNTER_EVERY - t % ENCOUNTER_EVERY
                    put(scr, y + 1, 1, L(f'몬스터볼 {st["balls"]}개', f'Poké Balls {st["balls"]}'), curses.A_DIM)
                    x = put(scr, y, 1, L('다음 탐색 ', 'Next explore '))
                    put(scr, y, x, f'{bar(1 - left / ENCOUNTER_EVERY, 24)} {fmt_tok(left)}' + L(' 남음', ' left'))
            put(scr, 9, 1, msg)
            x = button(h - 1, 1, L('도감 d', 'dex d'), 'dex')
            x = button(h - 1, x, L('가방 e', 'bag e'), 'box')
            gray = _lang.get('sprite') == 'gray'  # 허브의 동료 그림 색 — PC마다 따로(settings.json)
            x = button(h - 1, x, L('회색 c', 'gray c') if gray else L('컬러 c', 'color c'), 'sprite')
            button(h - 1, x, 'close q', 'close')
        else:
            open_gen = current_gen(st) or GENS
            rows = ([(n, ('● ' if n in st['caught'] else '○ ' if n in st['seen'] else '  ')
                      + f'{n:04d} ' + (name(n) if n in st['seen'] else '???')) for n in DEX if gen(n) == dg]
                    if dg <= open_gen else []) \
                if view == 'dex' else \
                [(i, ('★ ' if i == st['partner'] else '  ') + f'{name(m["id"])}  (No.{m["id"]:03d})')
                 for i, m in enumerate(st['box'])]
            if view == 'dex':
                have = sum(1 for n in st['caught'] if gen(n) == dg)
                put(scr, 1, 1, L(f'◀ {dg}세대 도감 {have}/{GEN_SIZE[dg]} ▶   ● 잡음 ○ 봄',
                                  f'◀ Gen {dg} Pokédex {have}/{GEN_SIZE[dg]} ▶   ● caught ○ seen'), curses.A_DIM)
            else:
                put(scr, 1, 1, L('가방 — 누르면 동료로 데리고 다닌다', 'Bag — pick one to make it your partner'), curses.A_DIM)
            body = h - 4
            if view == 'box' and rows:
                sel = max(0, min(sel, len(rows) - 1))
                top = min(max(top, sel - body + 1), sel)  # 커서가 화면 안에 있게
            top = max(0, min(top, len(rows) - body))
            for k, (key, text) in enumerate(rows[top:top + body]):
                attr = 0
                if view == 'box':
                    btns.append((2 + k, 1, w - 1, ('partner', key)))
                    attr = (curses.A_REVERSE if top + k == sel else 0) | (curses.A_BOLD if key == st['partner'] else 0)
                put(scr, 2 + k, 1, text.ljust(w - 2) if view == 'box' and top + k == sel else text, attr)
            if not rows:
                put(scr, 2, 1, L(f'잠김 — {dg - 1}세대 도감을 채우면 열립니다.',
                                 f'Locked — complete the Gen {dg - 1} Pokédex to open it.') if view == 'dex'
                    else L('아직 잡은 포켓몬이 없습니다.', 'No Pokémon caught yet.'))
            x = button(h - 1, 1, L('돌아가기 q', 'back q'), 'back')
            put(scr, h - 1, x, L('↑↓ 이동 · ←→ 세대', '↑↓ move · ←→ generation') if view == 'dex'
                else L('↑↓ 이동 · Space 동료로', '↑↓ move · Space set partner'), curses.A_DIM)
        scr.refresh()

        key = scr.getch()
        act = {ord('q'): 'back' if view != 'main' else 'close', 27: 'back' if view != 'main' else 'close',
               ord('s'): 'explore', ord('b'): 'throw', ord('r'): 'run', ord('v'): 'evolve',
               ord('d'): 'dex', ord('e'): 'box', ord('c'): 'sprite'}.get(key)
        if view == 'dex' and key in (curses.KEY_LEFT, curses.KEY_RIGHT):
            dg, top = max(1, min(GENS, dg + (1 if key == curses.KEY_RIGHT else -1))), 0
        if view == 'box' and key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE):
            sel += {curses.KEY_UP: -1, curses.KEY_DOWN: 1, curses.KEY_PPAGE: -(h - 4), curses.KEY_NPAGE: h - 4}[key]
        elif view == 'box' and key in (ord(' '), ord('\n'), curses.KEY_ENTER) and st['box']:
            act = ('partner', max(0, min(sel, len(st['box']) - 1)))
        elif key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE):
            top += {curses.KEY_UP: -1, curses.KEY_DOWN: 1, curses.KEY_PPAGE: -(h - 4), curses.KEY_NPAGE: h - 4}[key]
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, b = curses.getmouse()
                if b & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED):
                    act = next((a for by, x0, x1, a in btns if my == by and x0 <= mx < x1), None)
                elif b & getattr(curses, 'BUTTON4_PRESSED', 0):
                    top -= 3
                elif b & getattr(curses, 'BUTTON5_PRESSED', 0):
                    top += 3
            except curses.error:
                pass
        if act == 'close':
            break
        if act == 'sprite' and view == 'main':
            gray = _lang.put('sprite', 'color' if _lang.get('sprite') == 'gray' else 'gray') == 'gray'
            msg = L('허브의 동료 그림을 회색으로 보여 줍니다.', 'Partner art in the hub is now grayscale.') if gray else \
                L('허브의 동료 그림을 컬러로 보여 줍니다.', 'Partner art in the hub is now in color.')
        if act in ('dex', 'box'):
            view, top, dg = act, 0, current_gen(st) or GENS
            sel = st['partner'] or 0  # 가방은 지금 동료에서 시작
        elif act == 'back':
            view = 'main'
        elif isinstance(act, tuple):
            set_partner(st, t, act[1])
            save(st)
            pn = name(st['box'][act[1]]['id'])
            msg, view = L(f'{pn}(을)를 데리고 다닙니다.', f'{pn} is now your partner.'), 'main'
        elif view == 'main' and act in ('explore', 'throw', 'run', 'evolve'):
            if act == 'explore':
                got = explore(st, t)
                if not got:
                    msg = ''
                elif got[1]:
                    msg = L(f'또 {name(got[0])}! 이미 가방에 있어서 몬스터볼 {got[1]}개로 바꿨다.',
                            f'{name(got[0])} again! Already in your bag, so it became {got[1]} Poké Ball(s).')
                else:
                    msg = L(f'풀숲에서 {name(got[0])}(이)가 튀어나왔다!', f'{name(got[0])} jumped out of the tall grass!')
            elif act == 'throw' and st['wild']:
                n = st['wild']['id']
                r = throw(st, t)
                msg = {'caught': L(f'신난다! {name(n)}(을)를 잡았다!', f'Gotcha! {name(n)} was caught!'),
                       'missed': L('아깝다! 볼에서 빠져나왔다.', 'Argh! It broke free.'),
                       'fled': L(f'{name(n)}(은)는 도망쳐 버렸다…', f'{name(n)} ran away…')}[r]
            elif act == 'run' and st['wild']:
                msg, st['wild'] = L('무사히 도망쳤다.', 'Got away safely.'), None
            elif act == 'evolve':
                before = name(st['box'][st['partner']]['id']) if st['partner'] is not None else ''
                n = evolve(st, t)
                msg = L(f'오잉!? {before}의 모습이… {name(n)}(으)로 진화했다!', f'What? {before} evolved into {name(n)}!') if n else ''
            save(st)


def selftest():
    global DEX
    import struct
    import tempfile
    import zlib
    assert len(DEX) == 1025 and GENS == 9 and GEN_SIZE[1] == 151
    root = tempfile.mkdtemp()
    os.makedirs(f'{root}/usage')
    for sid, g in (('a', 20000), ('b', 15000), ('c', None)):
        with open(f'{root}/usage/{sid}.json', 'w') as f:
            json.dump({'gained': g} if g is not None else {}, f)
    t = total_tokens(root)
    assert t == 35000, t
    st = new_state()
    # 순서: 1세대 처음엔 스타팅·피카츄·이브이, 전설·환상은 맨 끝
    pool = wild_pool(st)
    assert set(pool[:5]) <= {1, 4, 7, 25, 133}, pool[:5]
    assert pool[-5:] and all(DEX[n][5] for n in pool[-5:]) and pool[-1] == 151  # 마지막은 환상 뮤
    assert 2 not in pool and 25 in pool  # 이상해풀은 진화로만, 피카츄는 진화 전(피츄)이 2세대라 야생에서
    assert tickets(st, t) == 1
    rng = random.Random(7)
    n, k = explore(st, t, rng)
    assert n in pool[:WINDOW] and k == 0 and st['wild'] and tickets(st, t) == 0
    assert explore(st, t, rng) is None  # 기회 없음
    # 반드시 잡히는 난수로 포획 → 첫 포획은 자동으로 동료
    st['wild'] = {'id': 1, 'balls': 3}
    assert throw(st, t, type('R', (), {'random': lambda s: 0.0})()) == 'caught'
    assert st['partner'] == 0 and 1 in st['caught'] and st['base'] == t
    assert st['balls'] == 1  # 포획 보상
    # 빗나가기 3번이면 도망
    st['wild'], st['balls'] = {'id': 150, 'balls': 3}, 0
    never = type('R', (), {'random': lambda s: 0.99})()
    assert [throw(st, t, never) for _ in range(3)] == ['missed', 'missed', 'fled'] and st['wild'] is None
    # 보유 볼이 있으면 기본 3개를 다 써도 도망가지 않고 이어 던진다
    st['wild'], st['balls'] = {'id': 150, 'balls': 3}, 2
    assert [throw(st, t, never) for _ in range(5)] == ['missed'] * 4 + ['fled'] and st['balls'] == 0
    # 이미 가방에 있는 종이 나오면 볼로 바뀐다: 흔함 1 · 스타팅급 3 · 전설 5
    assert (dupe_balls(10), dupe_balls(1), dupe_balls(144), dupe_balls(151)) == (1, 3, 5, 5)
    dup = new_state()
    dup['box'], dup['caught'] = [{'id': 25, 'xp': 0}], [25]
    # 가방 속 피카츄는 앞쪽에 남되 1/10 — 새 종 WINDOW 마리는 그대로 1
    odds = dict(wild_odds(dup))
    assert odds[25] == BOXED_WEIGHT and sorted(odds.values()).count(1) == WINDOW, odds
    dup['box'] = []
    assert dict(wild_odds(dup)).get(25) == 1  # 진화시켜 가방에서 빠지면 다시 보통 확률
    dup['box'] = [{'id': 25, 'xp': 0}]
    pick = type('R', (), {'choices': lambda s, xs, weights: [25]})()
    assert explore(dup, ENCOUNTER_EVERY, pick) == (25, dupe_balls(25)) and dup['wild'] is None
    assert dup['balls'] == dupe_balls(25) and dup['used'] == 1
    # 경험치: 15만 넘으면 이상해씨 → 이상해풀, 다음은 40만
    assert not can_evolve(st, t + 149_999) and can_evolve(st, t + 150_000)
    assert evolve(st, t + 150_000, rng) == 2 and 2 in st['caught'] and partner_xp(st, t + 150_000) == 0
    # 바리케이드: 이상해풀이 가방에 있으면 새로 잡은 이상해씨는 경험치가 차도 진화 못 함 → 빠지면 다시 가능
    bar_st = new_state()
    bar_st['box'], bar_st['caught'], bar_st['partner'] = [{'id': 1, 'xp': 10**9}, {'id': 2, 'xp': 0}], [1, 2], 0
    assert evo_status(bar_st, 0) == ('blocked', [2]) and not can_evolve(bar_st, 0) and evolve(bar_st, 0) is None
    bar_st['box'][1]['id'] = 3  # 이상해풀 → 이상해꽃
    assert can_evolve(bar_st, 0) and evolve(bar_st, 0) == 2
    # 이브이: 샤미드가 가방에 있으면 남은 둘 중에서만
    bar_st['box'] = [{'id': 133, 'xp': 10**9}, {'id': 134, 'xp': 0}]
    bar_st['partner'] = 0
    assert sorted(evolutions(bar_st, 133)) == [135, 136]
    bar_st['box'] += [{'id': 135, 'xp': 0}, {'id': 136, 'xp': 0}]
    assert evo_status(bar_st, 0) == ('blocked', [134, 135, 136])
    assert need_xp(2) == 400_000 and need_xp(3) is None and need_xp(83) is not None  # 파오리 → 대파무사(8세대)
    # 나중 세대 베이비는 단계에 안 친다: 피카츄 1단계(15만), 라이츄 2단계, 에레키블(4세대)은 에레키드부터 3단계
    assert (depth(25), depth(26), depth(172), depth(466)) == (0, 1, 0, 2) and need_xp(25) == 150_000
    # 동료를 바꿔도 쌓인 경험치는 그 포켓몬에게 남고, 이브이는 1세대에선 1세대 진화형만
    st['box'].append({'id': 133, 'xp': 0})
    set_partner(st, t + 160_000, 1)
    assert st['box'][0]['xp'] == 10_000
    assert evolve(st, t + 310_000, rng) in (134, 135, 136)
    # 잠긴 진화: 1세대에서 에레브(125)는 진화형(4세대 에레키블)이 잠겨 있다
    st['box'].append({'id': 125, 'xp': 10**9})
    set_partner(st, t, 2)
    assert evo_status(st, t)[0] == 'locked' and not can_evolve(st, t)
    # 1세대를 다 채우면 2세대가 열리고, 에레브는 아직(4세대) 잠김, 2세대 야생엔 2세대만
    st['caught'] = [n for n in DEX if gen(n) == 1]
    assert current_gen(st) == 2 and all(gen(n) == 2 for n in wild_pool(st))
    assert 172 in wild_pool(st)[:5]  # 피츄가 앞쪽
    assert evo_status(st, t)[0] == 'locked'
    st['caught'] = list(DEX)
    assert current_gen(st) is None and wild_pool(st) == [] and dex_text(st).startswith(L('도감 완성', 'Pokédex complete'))
    # 모든 세대가 끝까지 채워질 수 있나: 같은 세대 진화형은 그 세대에서 야생으로 나오는 조상이 있어야 한다
    for n in DEX:
        a = n
        while not wild_ok(a):
            a = DEX[a][3]
        assert gen(a) == gen(n), n
    # 저장·불러오기
    save(st, root)
    assert load(root)['caught'] == st['caught']
    assert summary(root)[0][0].startswith(L('동료 ', 'Partner '))
    # 도감을 아직 안 받았으면 허브엔 안내 한 줄만(죽지 않는다)
    real, DEX = DEX, {}
    try:
        assert len(summary(root)) == 1 and '[ pokemon ]' in summary(root)[0][0]
    finally:
        DEX = real
    # 그림: 팔레트 4비트 + 투명색 PNG 를 직접 만들어 해독 → 여백을 잘라 낸다
    raw = b''.join(b'\x00' + bytes(r) for r in ([0x01, 0x10], [0x00, 0x22]))  # 4×2, 칸마다 팔레트 0/1/2
    chunk = lambda k, b: struct.pack('>I', len(b)) + k + b + struct.pack('>I', zlib.crc32(k + b))  # noqa: E731
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 4, 2, 4, 3, 0, 0, 0))
           + chunk(b'PLTE', bytes([0, 0, 0, 255, 0, 0, 0, 0, 255])) + chunk(b'tRNS', b'\x00')
           + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
    px = _pokedata.decode_png(png)
    assert [[c[3] for c in r] for r in px] == [[0, 255, 255, 0], [0, 0, 255, 255]]
    assert px[0][1][:3] == (255, 0, 0) and px[1][3][:3] == (0, 0, 255)
    red, blue = (255, 0, 0), (0, 0, 255)
    assert _pokedata.shrink(px, 12, 16) == [[red, red, None], [None, blue, blue]]  # 왼쪽 빈 열을 잘라 냄
    assert (_pokedata.xterm256(*red), _pokedata.xterm256(*blue)) == (196, 21)
    assert (_pokedata.gray256(0, 0, 0), _pokedata.gray256(255, 255, 255), _pokedata.gray256(128, 128, 128)) == (16, 231, 244)
    assert _pokedata.shrink([[(0, 0, 0, 0)]], 12, 16) == []
    # Kitty 그래픽용: 여백을 잘라 PNG 로 다시 쓰면 그대로 읽힌다 · 회색은 밝기만
    cut = _pokedata.crop(px)
    assert len(cut) == 2 and len(cut[0]) == 3 and _pokedata.decode_png(_pokedata.encode_png(cut)) == cut
    assert _pokedata.crop(px, gray=True)[0][1] == (76, 76, 76, 255)  # 빨강의 밝기 0.299 × 255
    print('pokemon selftest ok')


if __name__ == '__main__':
    if sys.argv[1:] == ['--selftest']:
        selftest()
    else:
        locale.setlocale(locale.LC_ALL, '')
        os.environ.setdefault('ESCDELAY', '25')
        curses.wrapper(main)
