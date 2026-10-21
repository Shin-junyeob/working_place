#!/usr/bin/env python3
"""포켓몬 — Claude 를 쓴 만큼(누적 토큰) 포켓몬을 발견해 잡고, 한 마리를 데리고 다니며 진화시켜 세대별 도감을 채운다.

누적 토큰: 각 세션의 pane-tools mod 가 usage/<sid>.json 의 gained 에 적는 값(컨텍스트가 늘어난 만큼)을 모두 더한 것.
- 도감은 세대별(1~9세대). 데이터는 처음 열 때 PokeAPI 에서 받아 ~/.claude/pane-tools/pokedex.json 에 둔다(_pokedata.py). 지금 세대를 다 채우면 다음 세대가 열리고, 야생에선 지금 세대 포켓몬만 나온다.
- 나오는 순서: 스타팅·피카츄·이브이 → 일반(원작 포획률 높은 = 흔한 것부터) → 전설 → 환상. 앞쪽 WINDOW 마리 중 무작위.
- ENCOUNTER_EVERY 토큰마다 탐색 1회. 볼 BALLS 개 + 보유 볼, 다 빗나가면 도망(나중에 다시 나온다). 잡으면 보유 볼 +1.
- 지금 가방에 있는 종은 다른 종의 1/10 확률로만 나오고(BOXED_WEIGHT), 나오면 잡지 않고 급에 따라 몬스터볼 1~5개로 바꾼다(dupe_balls).
- 동료는 한 마리. 데리고 있는 동안 쌓인 토큰이 경험치 — STAGE_XP 를 넘으면 진화. 아직 안 열린 세대로의 진화는 그 세대가 열린 뒤, 이미 가방에 있는 모습으로는 진화하지 않는다.
- 볼 세 가지: 몬스터볼(b) · 슈퍼볼(u, 1.5배) · 하이퍼볼(h, 2배). 전설·환상은 하이퍼볼로만 잡힌다(다른 볼은 쓰지 않고 알려만 준다).
  하이퍼볼은 가방에서 몬스터볼 HYPER_COST 개로 바꾼다. 슈퍼볼은 일한 보상 — 하루에 서로 다른 세션 SUPER_SESSIONS 개
  이상이 PR 병합·배포가 든 completed 를 내면 1개(하루 1개, 기록은 feed.py 가 읽는 ~/.claude/jobs 의 timeline).
- 이로치: 탐색마다 SHINY_RATE. 같은 종이라도 이로치와 기본 모습은 다른 포켓몬으로 친다(중복·진화 막힘 모두 따로). 이름은 금색.
상태는 ~/.claude/pane-tools/pokemon.json. 허브는 summary() 로 동료를 보여 준다.
`python3 pokemon.py --selftest` 로 규칙을 점검한다(데이터가 없으면 먼저 받는다).
"""
import curses
import glob
import json
import locale
import math
import os
import random
import re
import sys
import zlib
from datetime import datetime

import _battle
import _gfx
import _lang
import _pokedata
import feed  # 세션 기록(슈퍼볼 보상) · 금색(이로치)
from _lang import L
import memo
from memo import focus_reporting, getkey, put  # 한글 2칸 폭을 맞춰 그리기 · 한글 자판 단축키 — 메모장과 같이 쓴다

ROOT = os.path.expanduser('~/.claude/pane-tools')
ENCOUNTER_EVERY = 30_000
STAGE_XP = [150_000, 400_000]  # 1→2단계, 2→3단계
BALLS = 3
WINDOW = 4  # 순서상 앞쪽 몇 마리 중에서 나오나
BOXED_WEIGHT = 0.1  # 지금 가방에 있는 종은 다른 종의 1/10 만 나온다(wild_odds)
SHINY_RATE = 1 / 256
HYPER_COST = 100  # 몬스터볼 몇 개로 하이퍼볼 하나
BALL_BONUS = {'ball': 1.0, 'super': 1.5, 'hyper': 2.0}
SUPER_SESSIONS = 3  # 하루에 PR·배포를 끝낸 서로 다른 세션이 이만큼이면 슈퍼볼 1개
SHIP = re.compile(r'PR|병합|배포|merge|deploy', re.I)  # completed 요약에 이게 있으면 '내보낸 일'
NEEDS_NAG = 600  # needs 를 이만큼(초) 넘게 두면 동료가 재촉한다
EGG_EVERY, EGG_MAX, EGG_STEP = 3, 3, 5000  # 슈퍼볼 몇 번마다 알 · 가질 수 있는 알 · 부화 걸음 하나당 토큰
EGG_SHINY = 1 / 64
DONE_SHOW, NEWS_SHOW, STALE = 120, 300, 12 * 3600  # 완료 반응 · 보상 소식 보이는 시간 · 이보다 오래된 needs 는 무시(초)

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


ROMAN = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX']


def shiny_rate(st, n, base=SHINY_RATE):
    """그 세대의 빛나는 부적이 있으면 이로치 2배 — 세대를 완성하면 그 세대 부적을 받는다."""
    return base * (2 if gen(n) in st.get('charms', []) else 1)


def gen_done(st, g):
    return sum(1 for n in st['caught'] if gen(n) == g) >= GEN_SIZE[g]


def _final_evolved(st):
    """가방에서 진화를 거쳐 최종 모습이 된 포켓몬 수."""
    return sum(1 for m in st['box'] if m['id'] not in CHILDREN and depth(m['id']) > 0)


# 훈장 (번호, 한국어, 영어, 조건) — 업적. 체육관에서 이겨 받는 것은 '배지'(st['gym'])로 따로다
BADGES = [('catch1', '첫 포획', 'First catch', lambda st: len(st['caught']) >= 1)] + \
    [(f'catch{k}', f'{k}마리', f'{k} caught', (lambda k: lambda st: len(st['caught']) >= k)(k)) for k in (10, 50, 100, 500)] + \
    [(f'gen{g}', f'{g}세대 완성', f'Gen {g} done', (lambda g: lambda st: g in GEN_SIZE and gen_done(st, g))(g)) for g in range(1, 10)] + [
    ('shiny1', '첫 이로치', 'First shiny', lambda st: len(st['shiny']) >= 1),
    ('shiny5', '이로치 5', '5 shinies', lambda st: len(st['shiny']) >= 5),
    ('legend', '첫 전설', 'First legendary', lambda st: any(DEX[n][5] == 1 for n in st['caught'])),
    ('myth', '첫 환상', 'First mythical', lambda st: any(DEX[n][5] == 2 for n in st['caught'])),
    ('evo1', '첫 진화', 'First evolution', lambda st: st['evolved'] >= 1),
    ('final10', '최종 진화 10', '10 fully evolved', lambda st: _final_evolved(st) >= 10),
    ('super1', '첫 슈퍼볼', 'First Great Ball', lambda st: (st['super_earned'] or 0) >= 1),
    ('super10', '슈퍼볼 10', '10 Great Balls', lambda st: (st['super_earned'] or 0) >= 10),
    ('hyper1', '하이퍼볼 교환', 'Ultra Ball trade', lambda st: st['exchanged'] >= 1)] + \
    [(f'conquer{g}', f'{g}세대 지방 정복', f'Gen {g} gyms cleared',
      (lambda g: lambda st: all(f'gym:{g}-{i}' in st.get('gym', {}) for i in range(8)))(g)) for g in range(1, 10)]


def badge_name(bid):
    """훈장 이름, 또는 체육관 배지('gym:세대-관') 이름."""
    if bid.startswith('gym:'):
        g, i = map(int, bid[4:].split('-'))
        return L(f'{g}세대 {i + 1}관 배지', f'Gen {g} gym {i + 1} badge')
    return next(L(ko, en) for b, ko, en, _ in BADGES if b == bid)


def check_badges(st, today=None):
    """새로 이룬 훈장을 날짜와 함께 적고, 세대를 완성했으면 그 세대 부적을, 지방을 정복했으면 알을 준다. 새 훈장 번호들."""
    today = today or datetime.now().astimezone().strftime('%Y-%m-%d')
    if st.get('super_earned') is None:  # 세기 시작 전 받은 슈퍼볼은 받은 날 수로
        st['super_earned'] = len(st['rewarded'])
    new = [b for b, _, _, ok in BADGES if b not in st['badges'] and ok(st)]
    for b in new:
        st['badges'][b] = today
        tell(st, 'badge', b)
        if b.startswith('gen') and int(b[3:]) not in st['charms']:
            st['charms'].append(int(b[3:]))
            tell(st, 'charm', b[3:])
        if b.startswith('conquer'):  # 지방 정복 — 하이퍼볼 1개와 알(관마다 하이퍼볼은 너무 많았다, 2026-10-21)
            st['hyper'] += 1
            if not give_egg(st):
                st['balls'] += 30  # 알이 가득 차 있으면 볼로
    return new


def boxed(st, shiny=False):
    """가방에 있는 종 — 이로치와 기본 모습은 따로 센다."""
    return {m['id'] for m in st['box'] if bool(m.get('shiny')) == bool(shiny)}


def wild_odds(st):
    """이번 탐색의 후보와 가중치 [(번호, 가중치)] — 가방에 없는 앞쪽 WINDOW 마리는 1, 그 사이에 낀 가방 속 종은
    BOXED_WEIGHT. 가방 속 종은 진화형을 동료 진화로만 얻으니 나와 봐야 볼로 바뀔 뿐인데, 그대로 두면 맨 앞 칸을
    막아 같은 포켓몬만 나왔다(진화 전 스타팅 3종이 4칸 중 3칸). 아예 빼지는 않고 드물게만 나오게 한다."""
    pool, inbag = wild_pool(st), boxed(st)
    fresh = [n for n in pool if n not in inbag][:WINDOW]
    if not fresh:  # 남은 게 전부 가방 속 종이면 그것들끼리
        return [(n, 1) for n in pool[:WINDOW]]
    front = pool[:pool.index(fresh[-1]) + 1]
    return [(n, BOXED_WEIGHT if n in inbag else 1) for n in front]


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
    return {'used': 0, 'box': [], 'partner': None, 'base': 0, 'seen': [], 'caught': [], 'wild': None, 'balls': 0,
            'super': 0, 'hyper': 0, 'shiny': [], 'rewarded': [], 'reward_since': None, 'news': [],
            'badges': {}, 'charms': [], 'evolved': 0, 'exchanged': 0, 'super_earned': None, 'eggs': [], 'showcase': [],
            'gym': {}, 'team': []}


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


def evolutions(st, n, shiny=False):
    """진화할 수 있는 다음 모습들 — 열린 세대 안에서, 가방에 아직 없는 것만. 이상해풀이 가방에 있으면 이상해씨는
    진화하지 않는다: 같은 모습이 두 마리가 되지 않고, 이상해씨는 가방에 남아 야생에서 계속 1/10 로만 나온다."""
    inbag = boxed(st, shiny)  # 이로치는 이로치끼리 — 기본 이상해풀이 있어도 이로치 이상해씨는 진화한다
    return [c for c in opened_evolutions(st, n) if c not in inbag]


def need_xp(n):
    """진화에 필요한 경험치. 진화형이 없으면 None."""
    return STAGE_XP[min(depth(n), 1)] if n in CHILDREN else None


def can_evolve(st, t):
    if st['partner'] is None:
        return False
    m = st['box'][st['partner']]
    return bool(evolutions(st, m['id'], m.get('shiny'))) and partner_xp(st, t) >= need_xp(m['id'])


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
    shiny = rng.random() < shiny_rate(st, n)
    _mark(st, 'seen', n)
    if n in boxed(st, shiny):  # 같은 모습(기본/이로치)이 이미 가방에 있다 → 몬스터볼로
        k = dupe_balls(n)
        st['balls'] += k
        return n, k
    st['wild'] = {'id': n, 'balls': BALLS, **({'shiny': True} if shiny else {})}
    return n, 0


def set_partner(st, t, i):
    if st['partner'] is not None:  # 지금 동료가 쌓은 경험치는 그 포켓몬에게 남긴다
        st['box'][st['partner']]['xp'] = partner_xp(st, t)
    st['partner'], st['base'] = i, t


def throw(st, t, rng=random, kind='ball'):
    """볼 하나(kind: ball · super · hyper). 'caught' / 'missed' / 'fled' · 볼이 없으면 None ·
    전설·환상에 하이퍼볼이 아니면 'needhyper'(볼을 쓰지 않는다 — 가방에서 바꿔 와 다시 던지게)."""
    w = st['wild']
    if not w or (w['balls'] + st['balls'] if kind == 'ball' else st[kind]) <= 0:
        return None
    if DEX[w['id']][5] and kind != 'hyper':
        return 'needhyper'
    if kind != 'ball':
        st[kind] -= 1
    elif w['balls'] > 0:  # 만날 때 받은 볼부터, 다 쓰면 보유 볼
        w['balls'] -= 1
    else:
        st['balls'] -= 1
    if rng.random() < min(1.0, catch_rate(w['id']) * BALL_BONUS[kind]):
        st['box'].append({'id': w['id'], 'xp': 0, **({'shiny': True} if w.get('shiny') else {})})
        _mark(st, 'caught', w['id'])
        if w.get('shiny'):
            _mark(st, 'shiny', w['id'])
        st['wild'] = None
        st['balls'] += 1  # 포획 보상 — 중복이 안 나오니 볼은 여기서 쌓인다
        if st['partner'] is None:
            set_partner(st, t, len(st['box']) - 1)
        return 'caught'
    if w['balls'] + st['balls'] + st['super'] + st['hyper'] <= 0:
        st['wild'] = None
        return 'fled'
    return 'missed'


def exchange(st):
    """몬스터볼 HYPER_COST 개 → 하이퍼볼 1개. 바꿨으면 True."""
    if st['balls'] < HYPER_COST:
        return False
    st['balls'] -= HYPER_COST
    st['hyper'] += 1
    st['exchanged'] = st.get('exchanged', 0) + 1
    return True


def _day(at):
    return datetime.fromisoformat(at.replace('Z', '+00:00')).astimezone().strftime('%Y-%m-%d')


def shipped(folder=feed.JOBS):
    """날짜 → PR 병합·배포가 든 completed 를 낸 세션 이름들."""
    out = {}
    for at, nm, state, detail in feed.feed(folder, limit=None):
        if state == 'done' and SHIP.search(detail):
            out.setdefault(_day(at), set()).add(nm)
    return out


def tell(st, kind, arg='', now=None):
    """동료가 말할 소식을 적어 둔다(보상·배지·알 — 세션 기록에 안 남는 것). 최근 10개만."""
    st['news'] = (st.get('news', []) + [{'at': now or datetime.now().timestamp(), 'kind': kind, 'arg': arg}])[-10:]


def _ts(at):
    return datetime.fromisoformat(at.replace('Z', '+00:00')).timestamp()


def speech(st, t, now=None, folder=feed.JOBS, awake=None):
    """허브 말풍선 (글, 경고인가) — 가장 급한 것 하나. 동료가 없으면 None.
    우선순위: needs 방치 > needs > 진화 가능 > 최근 소식(보상) > 최근 completed > 풀숲.
    awake: 깨어 있는 세션 이름들(허브가 넘긴다) — 없으면 STALE 보다 오래된 needs 는 무시."""
    if st['partner'] is None:
        return None
    now = now or datetime.now().timestamp()
    pn = name(st['box'][st['partner']]['id'])
    events = feed.feed(folder, limit=None)
    since = {}
    for at, nm, state, _ in events:  # 최근 것부터 — 세션마다 가장 최근 blocked 시각
        if state == 'blocked' and nm not in since:
            since[nm] = _ts(at)
    waiting = sorted((since[nm], nm) for nm, g in feed.jobs(folder) if g == 'blocked' and nm in since
                     and (nm in awake if awake is not None else now - since[nm] < STALE))
    if waiting:
        at, nm = waiting[0]
        more = L(f' 외 {len(waiting) - 1}개', f' +{len(waiting) - 1}') if len(waiting) > 1 else ''
        if now - at >= NEEDS_NAG:
            return L(f'{pn}(이)가 {nm}{more} 세션을 콕콕 찌른다! ({int((now - at) // 60)}분째 대기)',
                     f'{pn} pokes {nm}{more}! (waiting {int((now - at) // 60)} min)'), True
        return L(f'{pn}(이)가 {nm}{more} 세션을 쳐다본다…', f'{pn} looks at {nm}{more}…'), False
    if can_evolve(st, t):
        return L(f'{pn}의 몸이 빛나기 시작했다…', f'{pn} starts to glow…'), False
    for n in reversed(st.get('news', [])):
        if now - n['at'] >= NEWS_SHOW:
            continue
        if n['kind'] == 'super':
            return L(f'{pn}(이)가 슈퍼볼을 물어 왔다!', f'{pn} brought you a Great Ball!'), False
        if n['kind'] == 'charm':
            return L(f'빛나는 부적 {ROMAN[int(n["arg"])]}을 얻었다! ({n["arg"]}세대 이로치 2배)',
                     f'Got Shiny Charm {ROMAN[int(n["arg"])]}! (Gen {n["arg"]} shinies x2)'), False
        if n['kind'] == 'hatch':
            hn = int(n['arg'].rstrip('*'))
            return L(f'알이 부화했다! {"✨이로치 " if n["arg"].endswith("*") else ""}{name(hn)}(이)가 태어났다!',
                     f'An egg hatched! {"✨shiny " if n["arg"].endswith("*") else ""}{name(hn)} was born!'), False
        if n['kind'] == 'egg':
            return L(f'{pn}(이)가 알을 안고 왔다!', f'{pn} brought an egg!'), False
        if n['kind'] == 'badge' and n['arg'].startswith('conquer'):
            return L(f'{n["arg"][7:]}세대 지방 정복! {pn}(이)가 하이퍼볼과 알을 받아 왔다!',
                     f'Gen {n["arg"][7:]} gyms cleared! {pn} brought an Ultra Ball and an egg!'), False
        if n['kind'] == 'badge':
            return L(f'{pn}(이)가 새 훈장 [{badge_name(n["arg"])}]을 보고 좋아한다!',
                     f'{pn} admires the new medal [{badge_name(n["arg"])}]!'), False
        if n['kind'] == 'gym':
            return L(f'{pn}(이)가 [{badge_name(n["arg"])}]를 자랑한다!', f'{pn} shows off the [{badge_name(n["arg"])}]!'), False
    if any(t - e['base'] >= 0.9 * e['need'] for e in st.get('eggs', [])):
        return L('알이 흔들린다! 곧 태어날 것 같다.', 'The egg is wobbling! It will hatch soon.'), False
    for at, nm, state, detail in events:
        if now - _ts(at) >= DONE_SHOW:
            break
        if state == 'done':
            return (L(f'{pn}(이)가 박수를 친다! ({nm} 내보냄)', f'{pn} claps! ({nm} shipped)') if SHIP.search(detail) else
                    L(f'{pn}(이)가 기뻐서 뛰어오른다! ({nm} 끝)', f'{pn} jumps for joy! ({nm} done)')), False
    if st['wild'] or tickets(st, t) > 0:
        return L('풀숲이 흔들린다…', 'The tall grass rustles…'), False
    return None


def egg_pool(st):
    """알에서 나올 수 있는 종과 가중치 — 열린 세대의 1단계(진화 전 없음) 중 가방에 없는 것, 전설·환상 빼고.
    베이비 ×3 · 스타팅 ×2."""
    top, inbag = current_gen(st) or GENS, boxed(st)
    return [(n, 3 if DEX[n][7:8] == [1] else 2 if n in STARTERS else 1) for n in DEX
            if gen(n) <= top and not DEX[n][3] and not DEX[n][5] and n not in inbag]


def _pick_egg(st, rng):
    pool = egg_pool(st)
    return rng.choices([n for n, _ in pool], weights=[k for _, k in pool])[0] if pool else None


def give_egg(st, t=None, rng=random):
    """알 하나 — 종은 지금 정해 두고(부화할 때까지 ???) 그 종의 부화 걸음만큼 토큰을 쓰면 부화한다. 가득 차면 못 받는다."""
    n = _pick_egg(st, rng)
    if n is None or len(st.setdefault('eggs', [])) >= EGG_MAX:
        return False
    st['eggs'].append({'id': n, 'base': total_tokens() if t is None else t, 'need': (DEX[n][8] if len(DEX[n]) > 8 else 20) * EGG_STEP})
    tell(st, 'egg')
    return True


def hatch(st, t, rng=random):
    """다 자란 알을 부화한다 — 그새 같은 종이 가방에 들어왔으면 다시 고른다. 이로치는 이때 정한다. [(번호, 이로치)]."""
    out = []
    for e in [e for e in st.get('eggs', []) if t - e['base'] >= e['need']]:
        st['eggs'].remove(e)
        n = e['id'] if e['id'] not in boxed(st) else _pick_egg(st, rng)
        if n is None:
            st['balls'] += 5  # 나올 종이 없으면 볼로
            continue
        shiny = rng.random() < shiny_rate(st, n, EGG_SHINY)
        st['box'].append({'id': n, 'xp': 0, **({'shiny': True} if shiny else {})})
        for key in ('seen', 'caught') + (('shiny',) if shiny else ()):
            _mark(st, key, n)
        if st['partner'] is None:
            set_partner(st, t, len(st['box']) - 1)
        tell(st, 'hatch', f'{n}{"*" if shiny else ""}')
        out.append((n, shiny))
    return out


def egg_text(st, t):
    """'알 2개 · 다음 부화까지 18k' — 알이 없으면 ''."""
    eggs = st.get('eggs', [])
    if not eggs:
        return ''
    left = min(e['need'] - (t - e['base']) for e in eggs)
    return L(f'알 {len(eggs)}개 · 다음 부화까지 {fmt_tok(max(0, left))}', f'{len(eggs)} egg(s) · next hatch in {fmt_tok(max(0, left))}')


def reward(st, folder=feed.JOBS, today=None):
    """일한 보상 — 기능을 켠 날부터, 조건을 채운 날마다 슈퍼볼 1개(하루 1개). 새로 준 개수."""
    today = today or datetime.now().astimezone().strftime('%Y-%m-%d')
    st['reward_since'] = st.get('reward_since') or today
    got = 0
    for day, names in shipped(folder).items():
        if day >= st['reward_since'] and day not in st['rewarded'] and len(names) >= SUPER_SESSIONS:
            st['rewarded'] = (st['rewarded'] + [day])[-60:]
            st['super'] += 1
            st['super_earned'] = (st.get('super_earned') or 0) + 1
            got += 1
            tell(st, 'super')
            if st['super_earned'] % EGG_EVERY == 0:
                give_egg(st)
    return got


def evolve(st, t, rng=random):
    if not can_evolve(st, t):
        return None
    mon = st['box'][st['partner']]
    mon['id'], mon['xp'] = rng.choice(evolutions(st, mon['id'], mon.get('shiny'))), 0  # 이로치는 이로치로 진화
    st['base'] = t
    st['evolved'] = st.get('evolved', 0) + 1
    _mark(st, 'seen', mon['id'])
    _mark(st, 'caught', mon['id'])
    if mon.get('shiny'):
        _mark(st, 'shiny', mon['id'])
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
    m = st['box'][st['partner']]
    n = m['id']
    if n not in CHILDREN:
        return ('final',)
    opened = opened_evolutions(st, n)
    if not opened:
        return ('locked',)
    if not evolutions(st, n, m.get('shiny')):
        return ('blocked', opened)  # 진화형이 이미 가방에 있다
    xp, need = partner_xp(st, t), need_xp(n)
    return ('ready',) if xp >= need else ('progress', xp, need)


def blocked_text(opened):
    if len(opened) == 1:
        return L(f'{name(opened[0])}(이)가 가방에 있어 진화 못 함', f"can't evolve — {name(opened[0])} is already in the bag")
    return L('진화형이 모두 가방에 있어 진화 못 함', "can't evolve — every evolution is already in the bag")


def summary(root=ROOT, awake=None):
    """허브용 몇 줄: (글, 강조여부 — 'warn' 이면 노랑, 진행률 또는 None). awake: 깨어 있는 세션 이름들."""
    if not DEX:  # 아직 도감을 안 받았다 — 받는 건 pokemon 화면이 한다
        return [(L('포켓몬 데이터 없음 — [ pokemon ] 을 열면 받아 옵니다',
                   'No Pokédex yet — open [ pokemon ] to download it'), False, None)]
    st, t = load(root), total_tokens(root)
    fresh = not st.get('reward_since') or st.get('super_earned') is None
    if reward(st) + len(hatch(st, t)) + len(check_badges(st)) or fresh:  # 허브가 켜져 있으면 포켓몬 화면을 안 열어도 보상이 들어온다 · 켠 날은 처음에 적어 둔다
        save(st, root)
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
    said = speech(st, t, awake=awake)
    if said:  # ' · ' 는 허브가 줄을 나누는 표시라 쓰지 않는다
        lines.insert(1, ('💬 ' + said[0].replace(' · ', ', '), 'warn' if said[1] else False, None))
    return lines


def partner_id(root=ROOT):
    """허브에 그림을 띄울 동료의 번호 — 없으면 None."""
    return partner_id_of(load(root))


def partner_id_of(st):
    if st['partner'] is None:
        return None
    m = st['box'][st['partner']]
    return m['id'] + (_pokedata.SHINY if m.get('shiny') else 0)  # 이로치면 이로치 그림 번호


# ── 화면 ──
INFO = {}  # 도감 상세(_pokedata.DETAIL) — 상세 화면을 처음 열 때 읽는다
KITTY = SIXEL = False  # 진짜 그림을 놓을 수 있나 — __main__ 이 curses 를 켜기 전에 _gfx 로 정한다


def draw_info(scr, st, n, h, w, gold):
    """도감 상세: 이름 · 분류 · 타입, 잡았으면 키 · 몸무게 · 설명, 아래에 그림(이로치를 잡았으면 이로치 그림).
    그림은 Sixel·Kitty 가 되면 원본 도트로 — 놓을 그림 (방식, y, x, 키, 데이터, 칸, 줄)을 돌려주고, 화면을 그린 뒤 놓는다."""
    if not INFO:
        put(scr, 1, 1, L('PokeAPI 에서 도감 상세를 받는 중…', 'Downloading Pokédex details from PokeAPI…'), curses.A_DIM)
        scr.refresh()
        try:
            with open(_pokedata.ensure_detail(), encoding='utf-8') as f:
                INFO.update(json.load(f))
            scr.move(1, 0)
            scr.clrtoeol()  # '받는 중…' 글자가 이름 줄에 남지 않게
        except Exception as e:  # 네트워크 오류 등 — 죽지 말고 보여 준다
            put(scr, 2, 1, f'{type(e).__name__}: {e}')
            return
    d, caught, sh = INFO.get(str(n)), n in st['caught'], n in st['shiny']
    x = put(scr, 1, 1, f'No.{n:04d}  ', curses.A_BOLD)
    x = put(scr, 1, x, ('✨' if sh else '') + name(n), gold if sh else curses.A_BOLD)
    put(scr, 1, x + 2, L(f'{gen(n)}세대', f'Gen {gen(n)}') + (L(' · 잡음', ' · caught') if caught else L(' · 봄', ' · seen')), curses.A_DIM)
    y = 3
    if d:
        put(scr, 2, 1, L(f'{d[0]} · {"/".join(d[2])} 타입', f'{d[1]} · {"/".join(d[3])} type'))
        if caught:
            put(scr, 3, 1, L(f'키 {d[4] / 10:g}m · 몸무게 {d[5] / 10:g}kg', f'Height {d[4] / 10:g} m · Weight {d[5] / 10:g} kg'))
            text = L(d[6], d[7])
            for i, (_, a, b) in enumerate(memo.wrap([text], w - 3)[:max(1, h - 12)]):
                put(scr, 5 + i, 1, text[a:b].strip())
                y = 6 + i
        else:
            put(scr, 3, 1, L('잡으면 키·몸무게·도감 설명을 볼 수 있다.', 'Catch it to see its size and Pokédex entry.'), curses.A_DIM)
    room, sid, gray = h - 2 - (y + 1), n + (_pokedata.SHINY if sh else 0), _lang.get('sprite') == 'gray'
    loading = lambda: put(scr, y + 1, 1, L('그림 받는 중…', 'Loading the picture…'), curses.A_DIM) and None  # noqa: E731
    if room < 4:
        return None
    if SIXEL:  # 원본 도트를 정수 배로 — ▀▄ 칸은 평균·256색이라 흐리고 색이 틀렸다(2026-10-21)
        cw_, ch_ = _gfx.cell_px()
        # 그림이 바깥 터미널 아래 끝을 넘으면 터미널 전체가 밀려 올라갔다(2026-10-21 실제 화면). 칸 크기를 잘못 알아
        # 두 배로 그려져도 넘지 않게, 남은 줄의 절반 · 최대 8줄로.
        below = _gfx.rows_below(y + 1)
        room = max(0, min(room, 8, (below - 1) // 2 if below else room))
        if room < 3:
            return None
        six = _pokedata.sprite_sixel_fit(sid, gray, int((w - 2) * cw_), int(room * ch_))
        if not six:
            return loading()
        cols, rows = math.ceil(six[1] / cw_), math.ceil(six[2] / ch_)
        return ('six', y + 1, max(1, (w - cols) // 2), (sid, gray, w, room), six[0], cols, rows)
    if KITTY:
        png = _pokedata.sprite_png(sid, gray)
        if not png:
            return loading()
        cols = _gfx.kitty_cols(png[1], png[2], room)
        return ('kitty', y + 1, max(1, (w - cols) // 2), sid * 2 + gray, png[0], cols, room)
    if curses.COLORS >= 256:
        grid = _pokedata.sprite(sid, room * 2, w - 4)
        if grid:
            _pokedata.draw_sprite(scr, y + 1, max(1, (w - len(grid[0])) // 2), grid, gray)
        else:
            loading()
    return None


SHOWCASE_MAX = 5
# 훈장 → PokeAPI 도구 그림(sprites/items/<이름>.png) — 2026-10-21 미리보기로 보여 드린 짝. 지방 정복은 그 지방 이야기의
# 상징물(처음엔 8관 배지 그림을 썼더니 훈장과 배지가 같은 그림이 됐다).
MEDAL_ART = {'catch1': 'poke-ball', 'catch10': 'great-ball', 'catch50': 'ultra-ball', 'catch100': 'luxury-ball',
             'catch500': 'master-ball', 'gen1': 'fire-stone', 'gen2': 'water-stone', 'gen3': 'thunder-stone',
             'gen4': 'leaf-stone', 'gen5': 'moon-stone', 'gen6': 'sun-stone', 'gen7': 'shiny-stone', 'gen8': 'dusk-stone',
             'gen9': 'dawn-stone', 'shiny1': 'star-piece', 'shiny5': 'comet-shard', 'legend': 'red-chain', 'myth': 'gracidea',
             'evo1': 'rare-candy', 'final10': 'exp-share', 'super1': 'nugget', 'super10': 'big-nugget',
             'hyper1': 'gold-bottle-cap', 'conquer1': 'poke-flute', 'conquer2': 'rainbow-wing', 'conquer3': 'red-orb',
             'conquer4': 'adamant-orb', 'conquer5': 'light-stone', 'conquer6': 'zygarde-cube', 'conquer7': 'sun-flute',
             'conquer8': 'rusted-sword', 'conquer9': 'scarlet-book'}


def art_id(key):
    """훈장 번호 또는 체육관 배지('gym:세대-관') → 그림 번호(_pokedata)."""
    if key.startswith('gym:'):
        g, i = map(int, key[4:].split('-'))
        return _pokedata.BADGE + _battle.GYMS[g][i][1]
    return 'item:' + MEDAL_ART[key]


def owned(st, key):
    """그 훈장·배지를 가졌나."""
    return key in st.get('gym', {}) if key.startswith('gym:') else key in st['badges']


def badge_art(st, keys, y, x, rows):
    """훈장·배지 그림들을 한 장으로 (y, x) 에 rows 줄 높이로 놓을 그림 — main 이 화면을 그린 뒤 놓는다. 못 그리면 None."""
    if not keys or not (SIXEL or KITTY):
        return None
    ids = [art_id(k) for k in keys]
    cw_, ch_ = _gfx.cell_px()
    img = _pokedata.strip_image(ids, int(rows * ch_), 'six' if SIXEL else 'png')
    if not img:
        return None
    cols = math.ceil(img[1] / cw_)
    if SIXEL:
        return ('six', y, x, ('badges', tuple(ids), rows), img[0], cols, rows)
    return ('kitty', y, x, 100000 + zlib.crc32(repr(ids).encode()) % 100000, img[0], cols, rows)


def badge_goal(st, b):
    """못 받은 배지의 진행 (지금, 목표) — 셀 수 없는 것(첫 전설 등)은 None."""
    if b.startswith('catch'):
        return len(st['caught']), int(b[5:])
    if b.startswith('gen'):
        g = int(b[3:])
        return (sum(1 for n in st['caught'] if gen(n) == g), GEN_SIZE[g]) if g in GEN_SIZE else None
    return {'shiny1': (len(st['shiny']), 1), 'shiny5': (len(st['shiny']), 5), 'evo1': (st['evolved'], 1),
            'final10': (_final_evolved(st), 10), 'super1': (st['super_earned'] or 0, 1),
            'super10': (st['super_earned'] or 0, 10), 'hyper1': (st['exchanged'], 1)}.get(b)


def draw_showcase(scr, st, y, w):
    """포켓몬 화면 맨 위 — 훈장(a)·체육관(g)에서 고른 장식(최대 5개)을 글자 한 칸 높이 그림으로 한 줄에, 옆에 빛나는 부적.
    (다음에 쓸 줄, 놓을 그림) — 그림을 못 그리는 터미널이면 이름만."""
    shown = [b for b in st.get('showcase', []) if owned(st, b)]
    charm = ('✦' + ' '.join(ROMAN[g] for g in sorted(st['charms']))) if st['charms'] else ''
    if not shown:
        put(scr, y, 1, L('훈장(a)·체육관(g)에서 장식할 것을 고르세요', 'Pick medals (a) or gym badges (g) to show') + ('  ' + charm if charm else ''),
            curses.A_DIM)
        return y + 2, None
    art = badge_art(st, shown, y, 1, 1)  # 한 글자 크기(2026-10-21 사용자: 2줄은 너무 크다)
    if art:
        put(scr, y, art[5] + 2, charm)
        return y + 2, art
    put(scr, y, 1, '  '.join(badge_name(b) for b in shown) + ('  ' + charm if charm else ''))
    return y + 2, None


def draw_badge_list(scr, st, rows, top, sel, w, btns):
    """훈장(a) 화면 — 전부 나열, 받은 것은 날짜, 못 받은 것은 진행. 📌 는 장식 중. 색은 쓰지 않는다."""
    for k, b in enumerate(rows):
        yy, got = 2 + k, b in st['badges']
        x = put(scr, yy, 0, ('▶ ' if top + k == sel else '  ') + badge_name(b), 0 if got else curses.A_DIM) + 2
        goal = badge_goal(st, b)
        note = st['badges'][b] if got else (f'{min(goal[0], goal[1])}/{goal[1]}' if goal else L('아직', 'not yet'))
        x = put(scr, yy, x, note, 0 if got else curses.A_DIM)
        if b in st.get('showcase', []):
            put(scr, yy, x + 1, '📌')
        btns.append((yy, 1, w - 1, ('pin', b)))


GYM_COST = 2  # 체육관 도전 1회에 쓰는 탐색 기회
GYM_WIN_XP, GYM_LOSE_XP = 60, 30  # 팀원마다 받는 배틀 경험치(이기면 + 체육관 순서 × 10)


def box_level(m):
    return _battle.level(depth(m['id']), m.get('bxp', 0))


def team_of(st):
    """팀 [(가방 번호, 종, 레벨)] — 가방 순서가 아니라 넣은 순서."""
    return [(i, st['box'][i]['id'], box_level(st['box'][i])) for i in st.get('team', []) if i < len(st['box'])]


def toggle_team(st, i):
    """가방 i 번째를 팀에 넣거나 뺀다(최대 6). 결과 메시지."""
    team = st.setdefault('team', [])
    nm = name(st['box'][i]['id'])
    if i in team:
        team.remove(i)
        return L(f'{nm}(을)를 팀에서 뺐다.', f'{nm} left the team.')
    if len(team) >= _battle.TEAM_MAX:
        return L(f'팀은 {_battle.TEAM_MAX}마리까지 — 하나를 빼고 넣자.', f'Up to {_battle.TEAM_MAX} — remove one first.')
    team.append(i)
    return L(f'{nm}(을)를 팀에 넣었다! ({len(team)}/{_battle.TEAM_MAX})', f'{nm} joined the team! ({len(team)}/{_battle.TEAM_MAX})')


def gym_opp(d, g, i):
    """체육관 상대 — 전설·환상은 체육관에 나오지 않는다."""
    return _battle.gym_team(d, g, i, {n: gen(n) for n in DEX if not DEX[n][5]}, {n for n in DEX if n not in CHILDREN})


def gym_gens(st):
    """도전할 수 있는 세대 — 도감이 열린 세대까지."""
    return range(1, (current_gen(st) or GENS) + 1)


def fight(st, t, d, g, i, rng=random, today=None):
    """체육관 도전 — 탐색 GYM_COST 회를 쓰고 자동 배틀. 팀원 모두 배틀 경험치를 받고, 처음 이기면 그 관의 배지
    (하이퍼볼은 한 세대 8관을 모두 이겼을 때 지방 정복 훈장과 함께 — check_badges).
    (이겼나, 기록, 처음 이겼나) · 도전할 수 없으면 (None, 이유, False). 결과는 기록을 보여 주기 전에 바로 적용한다."""
    team = team_of(st)
    if not team:
        return None, L('팀이 비었다 — 가방(e)에서 t 로 넣거나 추천(r)을 적용하자.', 'Empty team — add with t in the bag or apply r.'), False
    if tickets(st, t) < GYM_COST:
        return None, L(f'탐색 기회가 {GYM_COST}번 있어야 도전할 수 있다.', f'You need {GYM_COST} explores to challenge.'), False
    st['used'] += GYM_COST
    won, ev = _battle.battle(d, [(n, lv) for _, n, lv in team], gym_opp(d, g, i), rng)
    for k, _, _ in team:
        st['box'][k]['bxp'] = st['box'][k].get('bxp', 0) + (GYM_WIN_XP + 10 * i if won else GYM_LOSE_XP)
    key, first = f'gym:{g}-{i}', False
    if won and key not in st.setdefault('gym', {}):
        st['gym'][key] = today or datetime.now().astimezone().strftime('%Y-%m-%d')
        tell(st, 'gym', key)
        first = True
    return won, ev, first


def fight_line(ev):
    """배틀 기록 한 칸 → 화면 한 줄."""
    if ev[0] == 'send':
        return L(f'가라, {name(ev[2])}!', f'Go, {name(ev[2])}!') if ev[1] == 'me' else \
            L(f'상대가 {name(ev[2])}(을)를 내보냈다!', f'The leader sent out {name(ev[2])}!')
    if ev[0] == 'faint':
        return L(f'{name(ev[2])}(은)는 쓰러졌다!', f'{name(ev[2])} fainted!')
    _, side, a, b, dmg, f, hp, top = ev
    eff = L('효과가 굉장했다! ', "It's super effective! ") if f > 1 else L('효과가 별로인 듯하다… ', "It's not very effective… ") \
        if 0 < f < 1 else L('효과가 없는 것 같다… ', 'It had no effect… ') if f == 0 else ''
    who = '' if side == 'me' else L('상대 ', 'Foe ')
    return L(f'{who}{name(a)}의 공격! {eff}({name(b)} {hp}/{top})', f"{who}{name(a)} attacks! {eff}({name(b)} {hp}/{top})")


def fight_state(ev, k):
    """기록 k 칸까지 본 지금 — {'me': [종, HP, 최대], 'foe': [...]}."""
    now = {}
    for e in ev[:k]:
        if e[0] == 'send':
            now[e[1]] = [e[2], None, None]
        elif e[0] == 'hit':
            side = 'foe' if e[1] == 'me' else 'me'
            if side in now:
                now[side][1:] = [e[6], e[7]]
    return now


def toggle_showcase(st, b):
    """장식 고르기/빼기(훈장·체육관 배지) — 가진 것만, 최대 SHOWCASE_MAX. 결과 메시지."""
    sc = st.setdefault('showcase', [])
    if b in sc:
        sc.remove(b)
        return L(f'[{badge_name(b)}] 장식을 뺐다.', f'Removed [{badge_name(b)}].')
    if not owned(st, b):
        return L('아직 받지 않았다.', "You haven't earned that yet.")
    if len(sc) >= SHOWCASE_MAX:
        return L(f'장식은 {SHOWCASE_MAX}개까지 — 하나를 빼고 고르자.', f'Up to {SHOWCASE_MAX} — remove one first.')
    sc.append(b)
    return L(f'[{badge_name(b)}] 를 장식했다!', f'Showing [{badge_name(b)}]!')


def bar(frac, width):
    f = round(max(0.0, min(1.0, frac)) * width)
    return '█' * f + '░' * (width - f)


def main(scr):
    curses.curs_set(0)
    scr.keypad(True)
    scr.timeout(2000)
    curses.mousemask(curses.ALL_MOUSE_EVENTS)
    curses.mouseinterval(0)
    curses.start_color()
    curses.use_default_colors()
    feed.init_colors()
    gold = curses.color_pair(feed.NEEDS_PAIR) | curses.A_BOLD  # 이로치 이름 — 256색 220(#ffd700)
    view, top, msg, dg, sel = 'main', 0, '', 1, 0  # sel: 가방·도감에서 커서가 놓인 줄
    info = None  # 도감 상세로 보고 있는 번호
    gsel, rec, battle_now, wr_cache = None, None, None, {}  # 고른 체육관 · 추천 (체육관, 팀, 승률) · 배틀 재생 · 승률 캐시
    BATTLE = _battle.load()  # 체육관을 처음 열 때 없으면 받는다
    if not DEX or len(DEX[1]) < 9:  # 처음 열었거나 옛 형식(알에 쓸 베이비·부화 걸음 없음) — 도감을 받아 온다
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
            while getkey(scr, -1) not in (ord('q'), 27):
                pass
            return
    while True:
        st, t = load(), total_tokens()
        fresh = not st.get('reward_since') or st.get('super_earned') is None
        got, born = reward(st), hatch(st, t)
        badges = check_badges(st)
        if got or born or badges or fresh:
            save(st)
        if born:
            msg = L('알이 부화했다! ', 'Eggs hatched! ') + ', '.join(('✨' if sh else '') + name(n) for n, sh in born)
        if got:
            msg = L(f'오늘 여러 세션이 일을 내보냈다! 슈퍼볼 {got}개를 받았다.', f'Sessions shipped work! Got {got} Great Ball(s).')
        if badges:
            msg = L('훈장을 받았다: ', 'New medal: ') + ', '.join(badge_name(b) for b in badges)
        h, w = scr.getmaxyx()
        art = None
        if view == 'fight' and battle_now['k'] < len(battle_now['ev']):
            battle_now['k'] += 1
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
            y0, art = draw_showcase(scr, st, 2, w)  # 장식 배지는 동료 정보 위에 — 아래 줄들은 y0 기준
            y = y0
            if st['partner'] is None:
                put(scr, y, 1, L('아직 동료가 없습니다. 풀숲을 탐색해 보세요.', 'No partner yet. Try exploring the tall grass.'))
            else:
                m = st['box'][st['partner']]
                n = m['id']
                x = put(scr, y, 1, L('동료  ', 'Partner  '), curses.A_BOLD)
                x = put(scr, y, x, (L('✨이로치 ', '✨shiny ') if m.get('shiny') else '') + name(n),
                        gold if m.get('shiny') else curses.A_BOLD)
                put(scr, y, x, L(f'  (No.{n:04d}, {gen(n)}세대 · {depth(n) + 1}단계)',
                                 f'  (No.{n:04d}, Gen {gen(n)} · stage {depth(n) + 1})'), curses.A_BOLD)
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
            if st.get('eggs'):
                e = min(st['eggs'], key=lambda e: e['need'] - (t - e['base']))
                x = put(scr, y0 + 2, 1, '🥚 ' + egg_text(st, t) + ' ')
                put(scr, y0 + 2, x, bar((t - e['base']) / e['need'], 12), curses.A_DIM)
            y = y0 + 4
            if st['wild']:
                sh = st['wild'].get('shiny')
                x = put(scr, y, 1, L('앗! 야생의 ', 'Oh! A wild '), curses.A_BOLD)
                x = put(scr, y, x, (L('✨이로치 ', '✨shiny ') if sh else '') + name(st['wild']['id']), gold if sh else curses.A_BOLD)
                put(scr, y, x, L('(이)가 나타났다!', ' appeared!'), curses.A_BOLD)
                left = st['wild']['balls'] or st['balls']
                own = '' if st['wild']['balls'] else L(' 보유', ' owned')
                x = button(y + 1, 1, L(f'몬스터볼 b ({left}{own})', f'Poké Ball b ({left}{own})'), 'throw')
                if st['super']:
                    x = button(y + 1, x, L(f'슈퍼볼 u ({st["super"]})', f'Great u ({st["super"]})'), 'super')
                if st['hyper']:
                    x = button(y + 1, x, L(f'하이퍼볼 h ({st["hyper"]})', f'Ultra h ({st["hyper"]})'), 'hyper')
                button(y + 1, x, L('도망 r', 'run r'), 'run')
            else:
                k = tickets(st, t)
                if k > 0:
                    put(scr, y, 1, L(f'탐색 {k}회 가능 · 몬스터볼 {st["balls"]} · 슈퍼볼 {st["super"]} · 하이퍼볼 {st["hyper"]}',
                                     f'{k} explore{"" if k == 1 else "s"} ready · Poké {st["balls"]} · Great {st["super"]} · Ultra {st["hyper"]}'))
                    button(y + 1, 1, L('풀숲 탐색 s', 'explore grass s'), 'explore')
                else:
                    left = ENCOUNTER_EVERY - t % ENCOUNTER_EVERY
                    put(scr, y + 1, 1, L(f'몬스터볼 {st["balls"]} · 슈퍼볼 {st["super"]} · 하이퍼볼 {st["hyper"]}',
                                         f'Poké {st["balls"]} · Great {st["super"]} · Ultra {st["hyper"]}'), curses.A_DIM)
                    x = put(scr, y, 1, L('다음 탐색 ', 'Next explore '))
                    put(scr, y, x, f'{bar(1 - left / ENCOUNTER_EVERY, 24)} {fmt_tok(left)}' + L(' 남음', ' left'))
            today = datetime.now().astimezone().strftime('%Y-%m-%d')
            done = len(shipped().get(today, ()))
            put(scr, y0 + 6, 1, L('오늘 슈퍼볼 받음 ✔', 'Great Ball earned today ✔') if today in st['rewarded'] else
                L(f'오늘 PR·배포를 끝낸 세션 {done}/{SUPER_SESSIONS} — 채우면 슈퍼볼',
                  f'Sessions that shipped a PR/deploy today {done}/{SUPER_SESSIONS} — fill it for a Great Ball'), curses.A_DIM)
            put(scr, y0 + 7, 1, msg)
            x = button(h - 1, 1, L('도감 d', 'dex d'), 'dex')
            x = button(h - 1, x, L('가방 e', 'bag e'), 'box')
            x = button(h - 1, x, L('훈장 a', 'medals a'), 'badges')
            x = button(h - 1, x, L('체육관 g', 'gyms g'), 'gyms')
            button(h - 1, x, L('닫기 q', 'close q'), 'close')  # 동료 그림 컬러/회색은 c 키로(버튼 자리가 모자라 뺐다)
        elif view == 'badges':
            rows = [b for b, _, _, _ in BADGES]
            body = h - 4
            sel = max(0, min(sel, len(rows) - 1))
            top = max(0, min(min(max(top, sel - body + 1), sel), len(rows) - body))
            put(scr, 1, 1, msg or L(f'훈장 {len(st["badges"])}/{len(BADGES)} · 장식 {len(st.get("showcase", []))}/{SHOWCASE_MAX}'
                                    ' — Space 로 장식 고르기/빼기',
                                    f'Medals {len(st["badges"])}/{len(BADGES)} · shown {len(st.get("showcase", []))}/{SHOWCASE_MAX}'
                                    ' — Space to show/hide'), curses.A_DIM)
            draw_badge_list(scr, st, rows[top:top + body], top, sel, w, btns)
            if rows[sel] in st['badges'] and w >= 50:  # 커서가 놓인 훈장 그림을 오른쪽에 크게
                art = badge_art(st, [rows[sel]], 3, w - 14, 4)
            x = button(h - 1, 1, L('돌아가기 q', 'back q'), 'back')
            put(scr, h - 1, x, L('↑↓ 이동 · Space 장식', '↑↓ move · Space show'), curses.A_DIM)
        elif view == 'gyms':
            rows = [(g, i) for g in gym_gens(st) for i in range(8)]
            body = h - 4
            sel = max(0, min(sel, len(rows) - 1))
            top = max(0, min(min(max(top, sel - body + 1), sel), len(rows) - body))
            put(scr, 1, 1, msg or L(f'체육관 배지 {len(st.get("gym", {}))}/{len(rows)} — Enter 도전 준비 · Space 장식',
                                    f'Gym badges {len(st.get("gym", {}))}/{len(rows)} — Enter to prepare · Space to show'), curses.A_DIM)
            for k, (g, i) in enumerate(rows[top:top + body]):
                key = f'gym:{g}-{i}'
                won = st.get('gym', {}).get(key)
                tname = (BATTLE or {}).get('tnames', {}).get(_battle.GYMS[g][i][0], ['', ''])
                x = put(scr, 2 + k, 0, ('▶ ' if top + k == sel else '  ') + L(f'{g}세대 {i + 1}관 ', f'Gen {g} gym {i + 1} ')
                        + L(tname[0], tname[1]), 0 if won else curses.A_DIM)
                if won:
                    x = put(scr, 2 + k, x + 2, '✔ ' + won)
                if key in st.get('showcase', []):
                    put(scr, 2 + k, x + 1, '📌')
                btns.append((2 + k, 1, w - 1, ('gym', (g, i))))
            if w >= 50 and rows:
                art = badge_art(st, [f'gym:{rows[sel][0]}-{rows[sel][1]}'], 3, w - 14, 4)
            x = button(h - 1, 1, L('돌아가기 q', 'back q'), 'back')
            put(scr, h - 1, x, L('↑↓ 이동 · Enter 도전 준비 · Space 장식', '↑↓ move · Enter prepare · Space show'), curses.A_DIM)
        elif view == 'gym':
            g, i = gsel
            opp = gym_opp(BATTLE, g, i)
            team = team_of(st)
            tn = BATTLE['tnames'].get(_battle.GYMS[g][i][0], ['', ''])
            won = st.get('gym', {}).get(f'gym:{g}-{i}')
            put(scr, 1, 1, L(f'{g}세대 {i + 1}관 — {tn[0]} 타입', f'Gen {g} gym {i + 1} — {tn[1]} type')
                + (L(f'  ✔ {won} 승리', f'  ✔ won {won}') if won else ''), curses.A_BOLD)
            put(scr, 3, 1, L('상대  ', 'Foe   ') + ', '.join(f'{name(n)} Lv{lv}' for n, lv in opp), curses.A_DIM)
            put(scr, 4, 1, L('내 팀 ', 'Team  ') + (', '.join(f'{name(n)} Lv{lv}' for _, n, lv in team) or
                                                   L('(비었다 — 가방 e 에서 t, 또는 추천 r → y)', '(empty — t in the bag, or r → y)')))
            wkey = (tuple((n, lv) for _, n, lv in team), g, i)
            if wkey not in wr_cache:
                wr_cache[wkey] = _battle.win_rate(BATTLE, [(n, lv) for _, n, lv in team], opp)
            put(scr, 6, 1, L(f'승률 {wr_cache[wkey]:.0%}', f'Win rate {wr_cache[wkey]:.0%}'), curses.A_BOLD)
            if rec and rec[0] == (g, i):
                rteam = [(st['box'][k]['id'], box_level(st['box'][k])) for k in rec[1]]
                put(scr, 7, 1, L('추천  ', 'Pick  ') + ', '.join(name(n) for n, _ in rteam) +
                    L(f'  (승률 {rec[2]:.0%}) — y 로 적용', f'  ({rec[2]:.0%}) — y to apply'))
            put(scr, 9, 1, msg)
            put(scr, 10, 1, L(f'탐색 기회 {tickets(st, t)}회 · 도전 1번에 {GYM_COST}회', f'{tickets(st, t)} explores · {GYM_COST} per challenge'),
                curses.A_DIM)
            x = button(h - 1, 1, L('도전 Enter', 'fight Enter'), 'fight')
            x = button(h - 1, x, L('추천 r', 'pick r'), 'rec')
            x = button(h - 1, x, L('적용 y', 'apply y'), 'apply')
            button(h - 1, x, L('돌아가기 q', 'back q'), 'back')
        elif view == 'fight':
            ev, k = battle_now['ev'], battle_now['k']
            now = fight_state(ev, k)
            lvs = battle_now['lv']
            y = 1
            for side, label in (('foe', L('상대', 'Foe ')), ('me', L('나  ', 'Me  '))):
                if side in now:
                    n, hp, top_ = now[side]
                    top_ = top_ or _battle.Mon(BATTLE, n, lvs[side][n]).st[0]
                    hp = top_ if hp is None else hp
                    x = put(scr, y, 1, f'{label} {name(n)} Lv{lvs[side][n]} ')
                    put(scr, y, x, f'{bar(hp / top_, 16)} {hp}/{top_}')
                y += 1
            if 'me' in now and 'foe' in now and (SIXEL or KITTY):
                # 2줄 높이로 — 5줄은 너무 컸고, 터미널이 칸 크기를 다르게 그려 실제로는 더 커져 기록과 겹쳤다(2026-10-21).
                # 그래서 그림 아래 자리를 그림 높이의 두 배만큼 비워 둔다.
                below = _gfx.rows_below(y + 1)
                rows_ = 2 if (below is None or below >= 6) and h >= 16 else 0
                if rows_:
                    cw_, ch_ = _gfx.cell_px()
                    ids = [now['me'][0], now['foe'][0]]
                    img = _pokedata.strip_image(ids, int(rows_ * ch_), 'six' if SIXEL else 'png')
                    if img:
                        cols = math.ceil(img[1] / cw_)
                        art = ('six', y + 1, 2, ('fight', tuple(ids), rows_), img[0], cols, rows_) if SIXEL else \
                            ('kitty', y + 1, 2, 200000 + ids[0] * 2000 + ids[1], img[0], cols, rows_)
                    y += rows_ * 2 + 1
            lines = [fight_line(e) for e in ev[:k]][-(h - y - 3):]
            for j, line in enumerate(lines):
                put(scr, y + 1 + j, 1, line, curses.A_BOLD if j == len(lines) - 1 else 0)
            if k >= len(ev):
                res = (L('승리! ', 'You won! ') + (L(f'[{badge_name(battle_now["key"])}]를 받았다!',
                                                  f'Got the [{badge_name(battle_now["key"])}]!') if battle_now['first']
                                                 else L('팀이 경험치를 얻었다.', 'Your team gained experience.'))) \
                    if battle_now['won'] else L('패배… 팀이 경험치를 얻었다. 다시 도전하자!', 'Defeat… your team gained experience.')
                put(scr, h - 2, 1, res, curses.A_BOLD)
            x = button(h - 1, 1, L('돌아가기 q', 'back q'), 'back')
            put(scr, h - 1, x, L('Space 끝까지', 'Space skip'), curses.A_DIM)
        elif view == 'info':
            art = draw_info(scr, st, info, h, w, gold)
            x = button(h - 1, 1, L('돌아가기 q', 'back q'), 'back')
            put(scr, h - 1, x, L('←→ 앞뒤 포켓몬', '←→ prev/next'), curses.A_DIM)
        else:
            open_gen = current_gen(st) or GENS
            rows = ([(n, ('● ' if n in st['caught'] else '○ ' if n in st['seen'] else '  ')
                      + f'{n:04d} ' + (name(n) if n in st['seen'] else '???')) for n in DEX if gen(n) == dg]
                    if dg <= open_gen else []) \
                if view == 'dex' else \
                [(i, ('★ ' if i == st['partner'] else '  ') + ('⚔' if i in st.get('team', []) else ' ') + ('✨' if m.get('shiny') else '')
                  + f'{name(m["id"])}  (No.{m["id"]:03d} · Lv{box_level(m)})')
                 for i, m in enumerate(st['box'])]
            if view == 'dex':
                have = sum(1 for n in st['caught'] if gen(n) == dg)
                put(scr, 1, 1, L(f'◀ {dg}세대 도감 {have}/{GEN_SIZE[dg]} ▶   ● 잡음 ○ 봄',
                                  f'◀ Gen {dg} Pokédex {have}/{GEN_SIZE[dg]} ▶   ● caught ○ seen'), curses.A_DIM)
            else:
                put(scr, 1, 1, msg or L('가방 — 누르면 동료로 데리고 다닌다', 'Bag — pick one to make it your partner'), curses.A_DIM)
            body = h - 4
            if rows:
                sel = max(0, min(sel, len(rows) - 1))
                top = min(max(top, sel - body + 1), sel)  # 커서가 화면 안에 있게
            top = max(0, min(top, len(rows) - body))
            for k, (key, text) in enumerate(rows[top:top + body]):
                attr = 0
                if view == 'box':
                    btns.append((2 + k, 1, w - 1, ('partner', key)))
                    attr = (curses.A_BOLD if key == st['partner'] else 0) | (gold if st['box'][key].get('shiny') else 0)
                else:
                    if key in st['seen']:
                        btns.append((2 + k, 1, w - 1, ('info', key)))
                    attr = gold if key in st['shiny'] else 0  # 이로치를 잡은 종은 도감에서도 금색
                attr |= curses.A_REVERSE if top + k == sel else 0
                put(scr, 2 + k, 1, text.ljust(w - 2) if top + k == sel else text, attr)
            if not rows:
                put(scr, 2, 1, L(f'잠김 — {dg - 1}세대 도감을 채우면 열립니다.',
                                 f'Locked — complete the Gen {dg - 1} Pokédex to open it.') if view == 'dex'
                    else L('아직 잡은 포켓몬이 없습니다.', 'No Pokémon caught yet.'))
            x = button(h - 1, 1, L('돌아가기 q', 'back q'), 'back')
            if view == 'box':
                x = button(h - 1, x, L(f'하이퍼볼 교환 x (몬스터볼 {HYPER_COST})', f'Ultra Ball x ({HYPER_COST} Poké)'), 'exchange')
            put(scr, h - 1, x, L('↑↓ 이동 · Enter 자세히 · ←→ 세대', '↑↓ move · Enter details · ←→ generation') if view == 'dex'
                else L('↑↓ 이동 · Space 동료로 · t 팀', '↑↓ move · Space partner · t team'), curses.A_DIM)
        if _gfx._six['key'] is not None and (not art or art[0] != 'six' or _gfx._six['key'] != art[3]):
            _gfx.redraw()  # 전 그림을 지운다 — tmux 가 화면 전체를 다시 그리게(빈칸으로 덮으면 크기가 어긋날 때 조각이 남았다)
        if _gfx._placed[0] is not None and (not art or art[0] != 'kitty'):
            _gfx.kitty_hide()
        scr.refresh()
        if art and art[0] == 'six':
            _gfx.sixel_show(*art[1:])
        elif art:
            _gfx.kitty_show(*art[1:])

        key = getkey(scr, 2000)
        if key != -1:
            _gfx.sixel_touch()  # 키로 화면이 바뀌면 그림을 다시 놓는다
        act = {ord('q'): 'back' if view != 'main' else 'close', 27: 'back' if view != 'main' else 'close',
               ord('s'): 'explore', ord('b'): 'throw', ord('r'): 'run', ord('v'): 'evolve',
               ord('d'): 'dex', ord('e'): 'box', ord('c'): 'sprite', ord('u'): 'super', ord('h'): 'hyper',
               ord('x'): 'exchange', ord('a'): 'badges', ord('g'): 'gyms', ord('t'): 'team', ord('y'): 'apply'}.get(key)
        if view == 'gym' and key == ord('r'):
            act = 'rec'
        if view == 'gym' and key in (ord('\n'), curses.KEY_ENTER):
            act = 'fight'
        if view == 'fight' and key == ord(' '):
            battle_now['k'] = len(battle_now['ev'])
        if view == 'dex' and key in (curses.KEY_LEFT, curses.KEY_RIGHT):
            dg, top, sel = max(1, min(GENS, dg + (1 if key == curses.KEY_RIGHT else -1))), 0, 0
        if view == 'info' and key in (curses.KEY_LEFT, curses.KEY_RIGHT):
            seen = sorted(n for n in st['seen'] if gen(n) == gen(info))  # 같은 세대에서 본 것끼리 앞뒤로
            info = seen[(seen.index(info) + (1 if key == curses.KEY_RIGHT else -1)) % len(seen)]
        if view in ('box', 'dex', 'badges', 'gyms') and key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE):
            sel += {curses.KEY_UP: -1, curses.KEY_DOWN: 1, curses.KEY_PPAGE: -(h - 4), curses.KEY_NPAGE: h - 4}[key]
        elif view == 'box' and key in (ord(' '), ord('\n'), curses.KEY_ENTER) and st['box']:
            act = ('partner', max(0, min(sel, len(st['box']) - 1)))
        elif view == 'gyms' and key in (ord(' '), ord('\n'), curses.KEY_ENTER):
            rows = [(g, i) for g in gym_gens(st) for i in range(8)]
            gi = rows[max(0, min(sel, len(rows) - 1))]
            act = ('pin', f'gym:{gi[0]}-{gi[1]}') if key == ord(' ') else ('gym', gi)
        elif view == 'badges' and key in (ord(' '), ord('\n'), curses.KEY_ENTER):
            act = ('pin', BADGES[max(0, min(sel, len(BADGES) - 1))][0])
        elif view == 'dex' and key in (ord(' '), ord('\n'), curses.KEY_ENTER):
            n = [m for m in DEX if gen(m) == dg][min(sel, GEN_SIZE[dg] - 1)]
            act = ('info', n) if n in st['seen'] else None
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
        if act == 'exchange' and view == 'box':
            ok = exchange(st)
            if ok:
                save(st)
            msg = L(f'몬스터볼 {HYPER_COST}개를 하이퍼볼 1개로 바꿨다! (하이퍼볼 {st["hyper"]})',
                    f'Traded {HYPER_COST} Poké Balls for an Ultra Ball! (Ultra {st["hyper"]})') if ok else \
                L(f'몬스터볼이 {HYPER_COST}개 있어야 바꿀 수 있다 (지금 {st["balls"]})',
                  f'You need {HYPER_COST} Poké Balls (have {st["balls"]})')
        if act == 'badges' and view == 'main':
            view, top, sel, msg = 'badges', 0, 0, ''
        if act == 'gyms' and view == 'main':
            if BATTLE is None:  # 처음 — 종족값·타입·상성을 받아 온다
                put(scr, 1, 1, L('PokeAPI 에서 배틀 데이터를 받는 중…', 'Downloading battle data from PokeAPI…'), curses.A_DIM)
                scr.refresh()
                try:
                    BATTLE = _battle.ensure()
                except Exception as e:  # 네트워크 오류 등
                    msg, act = L('배틀 데이터를 받지 못했다: ', 'Could not download battle data: ') + f'{type(e).__name__}: {e}', None
            if BATTLE is not None:
                view, top, sel, msg = 'gyms', 0, 0, ''
        if act == 'team' and view == 'box' and st['box']:
            msg = toggle_team(st, max(0, min(sel, len(st['box']) - 1)))
            save(st)
        if act == 'rec' and view == 'gym':
            put(scr, 9, 1, L('추천 팀을 계산하는 중…', 'Working out a team…'), curses.A_DIM)
            scr.refresh()
            cands = [(k, m['id'], box_level(m)) for k, m in enumerate(st['box'])]
            pick = _battle.recommend(BATTLE, cands, gym_opp(BATTLE, *gsel))
            lv = {k: l for k, _, l in cands}
            rec = (gsel, pick, _battle.win_rate(BATTLE, [(st['box'][k]['id'], lv[k]) for k in pick], gym_opp(BATTLE, *gsel)))
            msg = ''
        if act == 'apply' and view == 'gym' and rec and rec[0] == gsel:
            st['team'] = list(rec[1])
            save(st)
            msg = L('추천 팀을 적용했다.', 'Applied the suggested team.')
        if act == 'fight' and view == 'gym':
            team = team_of(st)
            won, ev, first = fight(st, t, BATTLE, *gsel)
            if won is None:
                msg = ev
            else:
                save(st)
                battle_now = {'ev': ev, 'k': 0, 'won': won, 'first': first, 'key': f'gym:{gsel[0]}-{gsel[1]}',
                              'lv': {'me': {n: lv for _, n, lv in team}, 'foe': {n: lv for n, lv in gym_opp(BATTLE, *gsel)}}}
                view, msg = 'fight', ''
                scr.timeout(600)  # 기록을 한 줄씩 — getkey 는 이 값을 따른다(빠뜨리면 키를 누를 때까지 멈춘다)
        if act in ('dex', 'box'):
            view, top, dg, msg = act, 0, current_gen(st) or GENS, ''
            sel = st['partner'] or 0  # 가방은 지금 동료에서 시작
        elif act == 'back' and view == 'fight' and battle_now['k'] < len(battle_now['ev']):
            battle_now['k'] = len(battle_now['ev'])  # 먼저 끝까지 보여 주고, 한 번 더 누르면 돌아간다
        elif act == 'back':
            if view == 'fight':
                scr.timeout(2000)
            view = {'info': 'dex', 'gym': 'gyms', 'fight': 'gym'}.get(view, 'main')  # 한 단계 위로
        elif isinstance(act, tuple) and act[0] == 'gym':
            view, gsel, msg = 'gym', act[1], ''
        elif isinstance(act, tuple) and act[0] == 'pin':
            msg = toggle_showcase(st, act[1])
            save(st)
        elif isinstance(act, tuple) and act[0] == 'info':
            view, info = 'info', act[1]
        elif isinstance(act, tuple):
            set_partner(st, t, act[1])
            save(st)
            pn = name(st['box'][act[1]]['id'])
            msg, view = L(f'{pn}(을)를 데리고 다닙니다.', f'{pn} is now your partner.'), 'main'
        elif view == 'main' and act in ('explore', 'throw', 'super', 'hyper', 'run', 'evolve'):
            if act == 'explore':
                got = explore(st, t)
                if not got:
                    msg = ''
                elif got[1]:
                    msg = L(f'또 {name(got[0])}! 이미 가방에 있어서 몬스터볼 {got[1]}개로 바꿨다.',
                            f'{name(got[0])} again! Already in your bag, so it became {got[1]} Poké Ball(s).')
                elif st['wild'].get('shiny'):
                    msg = L(f'✨ 반짝반짝! 이로치 {name(got[0])}(이)가 튀어나왔다!', f'✨ Sparkle! A shiny {name(got[0])} jumped out!')
                else:
                    msg = L(f'풀숲에서 {name(got[0])}(이)가 튀어나왔다!', f'{name(got[0])} jumped out of the tall grass!')
            elif act in ('throw', 'super', 'hyper') and st['wild']:
                n = st['wild']['id']
                r = throw(st, t, kind={'throw': 'ball'}.get(act, act))
                msg = {'caught': L(f'신난다! {name(n)}(을)를 잡았다!', f'Gotcha! {name(n)} was caught!'),
                       'missed': L('아깝다! 볼에서 빠져나왔다.', 'Argh! It broke free.'),
                       'fled': L(f'{name(n)}(은)는 도망쳐 버렸다…', f'{name(n)} ran away…'),
                       'needhyper': L(f'{name(n)}(은)는 하이퍼볼로만 잡힌다! 가방(e)에서 몬스터볼 {HYPER_COST}개를 바꿔 오자.',
                                      f'Only an Ultra Ball works on {name(n)}! Trade {HYPER_COST} Poké Balls in the bag (e).'),
                       None: L('그 볼이 없다.', "You don't have that ball.")}[r]
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
    st['wild'], st['balls'] = {'id': 19, 'balls': 3}, 0
    never = type('R', (), {'random': lambda s: 0.99})()
    assert [throw(st, t, never) for _ in range(3)] == ['missed', 'missed', 'fled'] and st['wild'] is None
    # 보유 볼이 있으면 기본 3개를 다 써도 도망가지 않고 이어 던진다
    st['wild'], st['balls'] = {'id': 19, 'balls': 3}, 2
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
    pick = type('R', (), {'choices': lambda s, xs, weights: [25], 'random': lambda s: 0.5})()
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
    # 이로치: 기본 피카츄가 가방에 있어도 이로치 피카츄는 잡을 수 있고(볼로 안 바뀜), 이로치가 있으면 그때 볼로
    sh = new_state()
    sh['box'], sh['caught'] = [{'id': 25, 'xp': 0}], [25]
    lucky = type('R', (), {'choices': lambda s, xs, weights: [25], 'random': lambda s: 0.0})()
    assert explore(sh, ENCOUNTER_EVERY, lucky) == (25, 0) and sh['wild'] == {'id': 25, 'balls': BALLS, 'shiny': True}
    assert throw(sh, 0, lucky) == 'caught' and sh['box'][-1] == {'id': 25, 'xp': 0, 'shiny': True} and sh['shiny'] == [25]
    assert explore(sh, 2 * ENCOUNTER_EVERY, lucky) == (25, dupe_balls(25))
    # 이로치 동료는 기본 라이츄가 가방에 있어도 진화하고, 진화해도 이로치
    sh['box'].append({'id': 26, 'xp': 0})
    set_partner(sh, 0, 1)
    sh['box'][1]['xp'] = 10**9
    assert can_evolve(sh, 0) and evolve(sh, 0) == 26 and sh['box'][1]['shiny'] and 26 in sh['shiny']
    assert partner_id_of(sh) == 26 + _pokedata.SHINY
    # 볼: 전설은 하이퍼볼만(다른 볼은 쓰지 않음) · 슈퍼볼 1.5배 · 볼이 없으면 None
    lg = new_state()
    lg['wild'], lg['balls'], lg['super'] = {'id': 150, 'balls': 3}, 0, 1
    assert throw(lg, 0, never, 'super') == 'needhyper' and lg['super'] == 1 and lg['wild']['balls'] == 3
    assert throw(lg, 0, never, 'hyper') is None
    lg['hyper'] = 1
    assert throw(lg, 0, type('R', (), {'random': lambda s: 0.29})(), 'hyper') == 'caught' and lg['hyper'] == 0  # 0.15×2
    r95 = type('R', (), {'random': lambda s: 0.95})()  # 꼬렛 포획률 0.9: 몬스터볼은 빗나가고 슈퍼볼(1.35→1.0)은 잡힌다
    lg['wild'], lg['balls'], lg['super'] = {'id': 19, 'balls': 3}, 0, 1
    assert catch_rate(19) == 0.9 and throw(lg, 0, r95) == 'missed' and throw(lg, 0, r95, 'super') == 'caught'
    # 교환: 몬스터볼 100 → 하이퍼볼 1, 모자라면 그대로
    ex = new_state()
    ex['balls'] = 130
    assert exchange(ex) and (ex['balls'], ex['hyper']) == (30, 1) and not exchange(ex) and ex['balls'] == 30
    # 슈퍼볼 보상: PR·배포를 끝낸 서로 다른 세션 3개인 날만, 하루 1개, 켠 날 전은 주지 않는다
    jd = tempfile.mkdtemp()
    def job(j, rows):
        os.makedirs(f'{jd}/{j}')
        with open(f'{jd}/{j}/state.json', 'w') as f:
            json.dump({'name': j, 'state': 'done'}, f)
        with open(f'{jd}/{j}/timeline.jsonl', 'w') as f:
            f.write(''.join(json.dumps({'at': at, 'state': 'done', 'detail': d, 'text': '…'}) + '\n' for at, d in rows))
    day1, day2 = '2026-10-21T03:00:00Z', '2026-10-22T03:00:00Z'
    job('a', [(day1, 'PR #1 병합'), (day2, '배포 완료')])
    job('b', [(day1, 'deploy ok'), ('2026-10-21T04:00:00Z', 'PR #2 merged')])  # 같은 세션 두 번은 하나
    job('c', [(day1, '문서 정리')])  # 내보낸 일이 아니다
    rw = new_state()
    rw['reward_since'] = '2026-10-01'
    assert reward(rw, jd) == 0  # 첫날은 a·b 두 세션뿐
    job('d', [(day1, '배포 끝')])
    feed._cache.clear()
    assert reward(rw, jd) == 1 and rw['super'] == 1 and reward(rw, jd) == 0  # 하루 1개
    rw2 = new_state()
    assert reward(rw2, jd, today='2026-10-22') == 0 and rw2['reward_since'] == '2026-10-22'  # 켠 날(22일) 전 보상은 없다
    # 도감 상세: 한국어가 없으면 영어, 설명은 최근 판, 줄바꿈은 빈칸, 기본 모습(is_default)만, 타입은 slot 순
    det = _pokedata.build_detail(
        [{'pokemon_species_id': '1', 'local_language_id': '3', 'name': '이상해씨', 'genus': '씨앗포켓몬'},
         {'pokemon_species_id': '1', 'local_language_id': '9', 'name': 'Bulbasaur', 'genus': 'Seed Pokémon'}],
        [{'species_id': '1', 'version_id': '1', 'language_id': '3', 'flavor_text': '옛\n설명'},
         {'species_id': '1', 'version_id': '9', 'language_id': '3', 'flavor_text': '새\n설명'},
         {'species_id': '1', 'version_id': '9', 'language_id': '9', 'flavor_text': 'A seed'}],
        [{'id': '1', 'species_id': '1', 'height': '7', 'weight': '69', 'is_default': '1'},
         {'id': '10001', 'species_id': '1', 'height': '9', 'weight': '1', 'is_default': '0'}],
        [{'pokemon_id': '1', 'type_id': '4', 'slot': '2'}, {'pokemon_id': '1', 'type_id': '12', 'slot': '1'}],
        [{'type_id': '12', 'local_language_id': '3', 'name': '풀'}, {'type_id': '12', 'local_language_id': '9', 'name': 'Grass'},
         {'type_id': '4', 'local_language_id': '9', 'name': 'Poison'}])
    assert det == {1: ['씨앗포켓몬', 'Seed Pokémon', ['풀', 'Poison'], ['Grass', 'Poison'], 7, 69, '새 설명', 'A seed']}, det
    # 동료 반응: needs 방치 > needs > 진화 가능 > 슈퍼볼 소식 > 최근 completed > 풀숲, 잠든 세션의 needs 는 무시
    sd = tempfile.mkdtemp()
    now = 2_000_000_000.0
    iso = lambda sec: datetime.fromtimestamp(now - sec).astimezone().isoformat()  # noqa: E731
    def sjob(j, rows, state='done'):
        os.makedirs(f'{sd}/{j}', exist_ok=True)
        with open(f'{sd}/{j}/state.json', 'w') as f:
            json.dump({'name': j, 'state': state, 'tempo': 'blocked' if state == 'blocked' else 'idle'}, f)
        with open(f'{sd}/{j}/timeline.jsonl', 'w') as f:
            f.write(''.join(json.dumps({'at': iso(sec), 'state': stt, 'detail': d, 'text': '…'}) + '\n' for sec, stt, d in rows))
        feed._cache.clear()
    sp = new_state()
    sp['box'], sp['partner'], sp['base'] = [{'id': 25, 'xp': 0}], 0, 0
    sjob('A', [(300, 'blocked', '물어봄')], 'blocked')
    said = speech(sp, 0, now, sd)
    assert said[1] is False and 'A' in said[0], said
    sjob('A', [(700, 'blocked', '물어봄')], 'blocked')
    assert speech(sp, 0, now, sd)[1] is True  # 10분 넘게 방치 → 경고
    assert speech(sp, 0, now, sd, awake=set()) is None  # 잠든 세션의 needs 는 무시
    sjob('A', [(30, 'done', 'PR #9 병합')])
    assert 'A' in speech(sp, 0, now, sd)[0] and speech(sp, 0, now, sd)[0] == L('피카츄(이)가 박수를 친다! (A 내보냄)', 'Pikachu claps! (A shipped)')
    tell(sp, 'super', now=now - 10)
    assert L('슈퍼볼', 'Great Ball') in speech(sp, 0, now, sd)[0]  # 보상 소식이 완료 반응보다 먼저
    sp['box'][0]['xp'] = 10**9
    assert L('빛나', 'glow') in speech(sp, 0, now, sd)[0]  # 진화 가능이 그보다 먼저
    sp['box'][0]['xp'], sp['news'] = 0, []
    sjob('A', [(500, 'done', '끝')])
    assert speech(sp, 0, now, sd) is None and speech(sp, ENCOUNTER_EVERY, now, sd)[0] == L('풀숲이 흔들린다…', 'The tall grass rustles…')
    # 배지: 이룬 것을 날짜와 함께, 두 번 주지 않는다 · 세대를 완성하면 그 세대 부적 → 그 세대만 이로치 2배
    bd = new_state()
    bd['caught'], bd['shiny'] = [n for n in DEX if gen(n) == 1], [1]
    got = check_badges(bd, today='2026-10-21')
    assert {'catch1', 'catch10', 'catch50', 'catch100', 'gen1', 'shiny1', 'legend', 'myth'} <= set(got) and 'catch500' not in got
    assert bd['charms'] == [1] and bd['badges']['gen1'] == '2026-10-21' and check_badges(bd) == []
    assert shiny_rate(bd, 25) == SHINY_RATE * 2 and shiny_rate(bd, 152) == SHINY_RATE
    assert any(n['kind'] == 'charm' and n['arg'] == '1' for n in bd['news'])
    bd['super_earned'], bd['exchanged'] = 1, 1
    assert set(check_badges(bd)) == {'super1', 'hyper1'}
    # 알: 풀에는 열린 세대의 1단계·가방에 없는 것만(전설·환상 빼고), 베이비 ×3 · 최대 3개 · 다 자라야 부화
    eg = new_state()
    eg['caught'] = [n for n in DEX if gen(n) == 1]  # 1세대 완성 → 2세대까지 열림
    eg['box'] = [{'id': 1, 'xp': 0}]
    pool = dict(egg_pool(eg))
    assert 1 not in pool and 2 not in pool and 144 not in pool and 4 in pool and pool[172] == 3 and pool[4] == 2 and pool[10] == 1
    assert all(gen(n) <= 2 for n in pool)
    first = type('R', (), {'choices': lambda s, xs, weights: [172], 'random': lambda s: 0.5})()
    assert give_egg(eg, 1000, first) and eg['eggs'][0] == {'id': 172, 'base': 1000, 'need': 10 * EGG_STEP}
    assert give_egg(eg, 1000, first) and give_egg(eg, 1000, first) and not give_egg(eg, 1000, first) and len(eg['eggs']) == EGG_MAX
    assert hatch(eg, 1000 + 10 * EGG_STEP - 1, first) == []  # 덜 자랐다
    eg['eggs'] = eg['eggs'][:1]
    eg['box'].append({'id': 172, 'xp': 0})  # 그새 피츄가 가방에 → 다시 고른다
    other = type('R', (), {'choices': lambda s, xs, weights: [175], 'random': lambda s: 0.0})()
    assert hatch(eg, 1000 + 10 * EGG_STEP, other) == [(175, True)] and eg['box'][-1] == {'id': 175, 'xp': 0, 'shiny': True}
    assert 175 in eg['caught'] and 175 in eg['shiny'] and not eg['eggs'] and eg['news'][-1]['kind'] == 'hatch'
    # 슈퍼볼 3번째에 알
    ew = new_state()
    ew['super_earned'], ew['reward_since'] = 2, '2026-10-01'
    assert reward(ew, jd) == 1 and len(ew['eggs']) == 1
    # 장식 배지: 받은 것만, 최대 5개, 다시 고르면 뺀다 · 진행도
    sc = new_state()
    sc['badges'] = {b: '2026-10-21' for b in ('catch1', 'catch10', 'catch50', 'evo1', 'super1', 'hyper1')}
    for b in ('catch1', 'catch10', 'catch50', 'evo1', 'super1'):
        toggle_showcase(sc, b)
    assert sc['showcase'] == ['catch1', 'catch10', 'catch50', 'evo1', 'super1']
    toggle_showcase(sc, 'hyper1')
    assert 'hyper1' not in sc['showcase']  # 6개째는 안 된다
    toggle_showcase(sc, 'catch10')
    toggle_showcase(sc, 'myth')
    assert sc['showcase'] == ['catch1', 'catch50', 'evo1', 'super1']  # 빼기 · 안 받은 건 못 고름
    sc['caught'] = list(range(1, 86))
    assert badge_goal(sc, 'catch100') == (85, 100) and badge_goal(sc, 'gen1') == (85, 151) and badge_goal(sc, 'legend') is None
    assert set(MEDAL_ART) == {b for b, _, _, _ in BADGES}  # 모든 훈장에 그림이 있다
    assert art_id('catch1') == 'item:poke-ball' and art_id('gym:1-0') == _pokedata.BADGE + 1 and art_id('conquer1') == 'item:poke-flute'
    assert not {art_id(b) for b, _, _, _ in BADGES} & {art_id(f'gym:{g}-{i}') for g in range(1, 10) for i in range(8)}  # 훈장과 배지는 다른 그림
    # 체육관: 팀 최대 6 · 탐색 2회 · 처음 이기면 배지+하이퍼볼, 다시 이기면 경험치만 · 8관 모두면 지방 정복 훈장과 알
    gd = {'stats': {74: [40, 80, 100, 30, 30, 20], 7: [44, 48, 65, 50, 64, 43]}, 'types': {74: [6, 5], 7: [11]},
          'eff': {'11,6': 2.0, '11,5': 2.0, '6,11': 1.0, '5,11': 1.0}, 'tnames': {6: ['바위', 'Rock']}}
    gs = new_state()
    gs['box'] = [{'id': 7, 'xp': 0, 'bxp': 3000}] + [{'id': 7, 'xp': 0} for _ in range(6)]
    assert toggle_team(gs, 0) and gs['team'] == [0] and team_of(gs)[0] == (0, 7, 15 + 30)
    for k in range(1, 7):
        toggle_team(gs, k)
    assert len(gs['team']) == 6 and 6 not in gs['team']  # 7번째는 못 넣는다
    toggle_team(gs, 3)
    assert gs['team'] == [0, 1, 2, 4, 5]
    gs['team'] = [0]
    assert fight(gs, ENCOUNTER_EVERY, gd, 1, 0)[0] is None and gs['used'] == 0  # 탐색 기회 1번뿐
    won, ev, first = fight(gs, 4 * ENCOUNTER_EVERY, gd, 1, 0, random.Random(1), today='2026-10-21')
    assert won and first and gs['gym'] == {'gym:1-0': '2026-10-21'} and gs['hyper'] == 0 and gs['used'] == GYM_COST
    assert gs['box'][0]['bxp'] == 3000 + GYM_WIN_XP and ev[0][0] == 'send' and fight_line(ev[-1])
    won, ev, first = fight(gs, 4 * ENCOUNTER_EVERY, gd, 1, 0, random.Random(1))
    assert won and not first and gs['hyper'] == 0  # 관을 이겨도 하이퍼볼은 없다
    assert fight_state(ev, len(ev))['foe'][1] == 0
    gs['gym'].update({f'gym:1-{i}': '2026-10-21' for i in range(8)})
    eggs = len(gs['eggs'])
    assert 'conquer1' in check_badges(gs) and len(gs['eggs']) == eggs + 1 and gs['hyper'] == 1  # 지방 정복 → 하이퍼볼과 알
    print('pokemon selftest ok')


if __name__ == '__main__':
    if sys.argv[1:] == ['--selftest']:
        selftest()
    else:
        locale.setlocale(locale.LC_ALL, '')
        os.environ.setdefault('ESCDELAY', '25')
        focus_reporting(True)  # 허브가 바꿔 둔 영문 자판을 이 패널에서 나가고 들어올 때 맞춘다
        KITTY = _gfx.kitty_ok()
        SIXEL = not KITTY and _gfx.sixel_ok()
        if SIXEL:
            _gfx.tmux_passthrough()
        try:
            curses.wrapper(main)
        finally:
            if _gfx._six['key'] is not None:
                _gfx.redraw()
            _gfx.kitty_hide(free=True)
            focus_reporting(False)
