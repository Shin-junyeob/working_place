"""포켓몬 모드의 체육관 배틀 — 데이터 받기 · 체육관 표 · 자동 배틀 · 승률 · 추천 팀. 화면은 pokemon.py 가 그린다.

데이터(종족값·타입·상성)는 체육관 화면을 처음 열 때 PokeAPI CSV 에서 받아 ~/.claude/pane-tools/battle.json 으로 만든다
(저장소에는 넣지 않는다 — README 의 팬메이드 고지). 여기 있는 건 체육관 타입 표와 배지 그림 번호뿐이다.
허브가 매초 pokemon 을 다시 읽으므로, 이 파일은 불러올 때 네트워크를 쓰지 않는다.
`python3 _battle.py` 로 규칙을 점검한다.
"""
import json
import os
import random

import _pokedata

DATA = f'{_pokedata.ROOT}/battle.json'
POWER = 70  # 모든 공격의 위력 — 기술 이름 없이 자기 타입 공격 한 가지
NORMAL, FIGHTING, FLYING, POISON, GROUND, ROCK, BUG, GHOST, STEEL, FIRE, WATER, GRASS, ELECTRIC, PSYCHIC, ICE, DRAGON, DARK, \
    FAIRY = range(1, 19)  # PokeAPI 타입 번호
# 세대마다 체육관 8곳 (타입, 배지 그림 번호 — PokeAPI sprites/badges). 원작 순서.
# 1~4·6·8·9세대는 그림과 타입을 대조해 맞춤(2026-10-21). 5세대는 블랙·화이트 8관, 8세대는 소드 8관.
# 7세대(알로라)는 체육관이 없어 시련 타입에 61~69번 그림(지방 미확인)을 대신 붙였다 — 바꾸려면 이 표만 고친다.
GYMS = {
    1: [(ROCK, 1), (WATER, 2), (ELECTRIC, 3), (GRASS, 4), (POISON, 5), (PSYCHIC, 6), (FIRE, 7), (GROUND, 8)],
    2: [(FLYING, 9), (BUG, 10), (NORMAL, 11), (GHOST, 12), (FIGHTING, 13), (STEEL, 14), (ICE, 15), (DRAGON, 16)],
    3: [(ROCK, 17), (FIGHTING, 18), (ELECTRIC, 19), (FIRE, 20), (NORMAL, 21), (FLYING, 22), (PSYCHIC, 23), (WATER, 24)],
    4: [(ROCK, 25), (GRASS, 26), (FIGHTING, 27), (WATER, 28), (GHOST, 29), (STEEL, 30), (ICE, 31), (ELECTRIC, 32)],
    5: [(GRASS, 33), (NORMAL, 34), (BUG, 36), (ELECTRIC, 37), (GROUND, 38), (FLYING, 39), (ICE, 40), (DRAGON, 41)],
    6: [(BUG, 43), (ROCK, 44), (FIGHTING, 45), (GRASS, 46), (ELECTRIC, 47), (FAIRY, 48), (PSYCHIC, 49), (ICE, 50)],
    7: [(NORMAL, 63), (WATER, 67), (FIRE, 65), (GRASS, 61), (ELECTRIC, 68), (GHOST, 69), (FAIRY, 66), (DRAGON, 62)],
    8: [(GRASS, 51), (WATER, 52), (FIRE, 53), (FIGHTING, 54), (FAIRY, 56), (ROCK, 57), (DARK, 59), (DRAGON, 60)],
    9: [(BUG, 70), (GRASS, 71), (ELECTRIC, 72), (WATER, 73), (NORMAL, 74), (GHOST, 75), (PSYCHIC, 76), (ICE, 77)],
}
OPP_COUNT = [2, 2, 3, 3, 3, 4, 4, 5]  # 체육관 순서별 상대 마릿수
# 세대마다 사천왕 4명의 타입(원작). 가라르(8)는 사천왕이 없어 골랐다. 챔피언은 타입 없이 그 세대의 강한 최종 진화형.
LEAGUE = {1: [ICE, FIGHTING, GHOST, DRAGON], 2: [PSYCHIC, POISON, FIGHTING, DARK], 3: [DARK, GHOST, ICE, DRAGON],
          4: [BUG, GROUND, FIRE, PSYCHIC], 5: [GHOST, DARK, PSYCHIC, FIGHTING], 6: [FIRE, WATER, STEEL, DRAGON],
          7: [FIGHTING, ROCK, GHOST, FLYING], 8: [DARK, STEEL, FAIRY, DRAGON], 9: [GROUND, STEEL, FLYING, DRAGON]}
ELITE_COUNT, CHAMP_COUNT = 4, 6
TEAM_MAX = 6
XP_PER_LEVEL, XP_LEVEL_CAP = 50, 40  # 50 마다 1레벨 — 100 이면 져서는(+30) 4번에 1레벨이라 못 넘는 관을 키워서 넘을 수 없었다(2026-10-21)


def build(stats, mons, ptypes, eff, tnames):
    """CSV 다섯 개(행 목록) → {'stats': {종: [hp, 공, 방, 특공, 특방, 스피드]}, 'types': {종: [타입…]},
    'eff': {'공격타입,방어타입': 배율(1 이 아닌 것만)}, 'tnames': {타입: [한, 영]}}. 기본 모습(is_default)만."""
    sid = {int(r['id']): int(r['species_id']) for r in mons if r['is_default'] == '1'}
    out = {'stats': {}, 'types': {}, 'eff': {}, 'tnames': {}}
    for r in stats:
        n = sid.get(int(r['pokemon_id']))
        if n and int(r['stat_id']) <= 6:
            out['stats'].setdefault(n, [0] * 6)[int(r['stat_id']) - 1] = int(r['base_stat'])
    for r in sorted(ptypes, key=lambda r: int(r['slot'])):
        n = sid.get(int(r['pokemon_id']))
        if n and int(r['type_id']) <= 18:
            out['types'].setdefault(n, []).append(int(r['type_id']))
    for r in eff:
        if int(r['damage_factor']) != 100:
            out['eff'][f"{r['damage_type_id']},{r['target_type_id']}"] = int(r['damage_factor']) / 100
    for r in tnames:
        t = int(r['type_id'])
        if t <= 18 and r['local_language_id'] in (_pokedata.KO, _pokedata.EN):
            out['tnames'].setdefault(t, ['', ''])[0 if r['local_language_id'] == _pokedata.KO else 1] = r['name']
    return out


def ensure(force=False):
    """battle.json 이 없으면 받아 만든다(처음 체육관을 열 때). 네트워크 오류는 그대로 올린다."""
    if not os.path.exists(DATA) or force:
        d = build(_pokedata._csv('pokemon_stats'), _pokedata._csv('pokemon'), _pokedata._csv('pokemon_types'),
                  _pokedata._csv('type_efficacy'), _pokedata._csv('type_names'))
        os.makedirs(_pokedata.ROOT, exist_ok=True)
        with open(DATA + '.tmp', 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, separators=(',', ':'))
        os.replace(DATA + '.tmp', DATA)
    return load()


def load():
    """battle.json → 번호 키를 정수로. 없으면 None."""
    try:
        with open(DATA, encoding='utf-8') as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    return {'stats': {int(k): v for k, v in d['stats'].items()}, 'types': {int(k): v for k, v in d['types'].items()},
            'eff': d['eff'], 'tnames': {int(k): v for k, v in d['tnames'].items()}}


def level(stage, bxp):
    """배틀 레벨 — 진화 단계(0부터)와 배틀 경험치로. 동료 진화용 토큰 경험치와는 따로다."""
    return 15 + stage * 12 + min(XP_LEVEL_CAP, bxp // XP_PER_LEVEL)


def calc(base, lv):
    """원작 공식을 줄인 능력치 — [HP, 공, 방, 특공, 특방, 스피드]."""
    return [2 * base[0] * lv // 100 + lv + 10] + [2 * b * lv // 100 + 5 for b in base[1:]]


def factor(d, atk, defs):
    """공격 타입 atk 가 방어 타입들 defs 에 주는 배율(0 · 0.25 ~ 4)."""
    f = 1.0
    for t in defs:
        f *= d['eff'].get(f'{atk},{t}', 1.0)
    return f


def best_attack(d, me, foe):
    """me 의 타입 중 foe 에 가장 아픈 것 (타입, 배율)."""
    return max(((t, factor(d, t, d['types'][foe])) for t in d['types'][me]), key=lambda x: x[1])


def matchup(d, me, foe):
    """me 가 foe 를 상대로 얼마나 유리한가 — 내 최고 배율 ÷ 상대 최고 배율."""
    return best_attack(d, me, foe)[1] / max(0.25, best_attack(d, foe, me)[1])


class Mon:
    def __init__(self, d, n, lv):
        self.n, self.lv, self.st = n, lv, calc(d['stats'][n], lv)
        self.hp = self.st[0]


def damage(d, a, b, rng):
    """a 가 b 를 한 번 친 (데미지, 배율). 물리·특수는 공격·특공 중 높은 쪽(방어도 그 짝)."""
    t, f = best_attack(d, a.n, b.n)
    atk, df = (a.st[1], b.st[2]) if a.st[1] >= a.st[3] else (a.st[3], b.st[4])
    dmg = ((2 * a.lv / 5 + 2) * POWER * atk / max(1, df) / 50 + 2) * 1.5 * f * rng.uniform(0.85, 1.0)
    return (max(1, int(dmg)) if f else 0), f


def battle(d, team, opp, rng, log=True):
    """자동 배틀. team·opp: [(종, 레벨)]. (이겼나, 기록) — 기록은 화면이 한 줄씩 보여 준다:
    ('send', 'me'|'foe', 종, 레벨) · ('hit', 공격쪽, 공격종, 맞은종, 데미지, 배율, 남은HP, 최대HP) · ('faint', 쪽, 종)."""
    mine, foes = [Mon(d, n, lv) for n, lv in team], [Mon(d, n, lv) for n, lv in opp]
    ev = []
    say = ev.append if log else (lambda e: None)
    foe = foes.pop(0)
    me = max(mine, key=lambda m: matchup(d, m.n, foe.n))  # 상대에게 가장 유리한 것부터
    mine.remove(me)
    say(('send', 'foe', foe.n, foe.lv))
    say(('send', 'me', me.n, me.lv))
    for _ in range(500):  # 0배끼리 만나면 끝나지 않으니 상한
        order = [(me, foe, 'me'), (foe, me, 'foe')]
        if foe.st[5] > me.st[5] or (foe.st[5] == me.st[5] and rng.random() < 0.5):
            order.reverse()
        for a, b, side in order:
            dmg, f = damage(d, a, b, rng)
            b.hp = max(0, b.hp - dmg)
            say(('hit', side, a.n, b.n, dmg, f, b.hp, b.st[0]))
            if b.hp:
                continue
            say(('faint', 'foe' if side == 'me' else 'me', b.n))
            if side == 'me':
                if not foes:
                    return True, ev
                foe = foes.pop(0)
                say(('send', 'foe', foe.n, foe.lv))
            else:
                if not mine:
                    return False, ev
                me = max(mine, key=lambda m: matchup(d, m.n, foe.n))
                mine.remove(me)
                say(('send', 'me', me.n, me.lv))
            break  # 쓰러진 쪽은 이번 차례에 치지 못한다
    return False, ev


def win_rate(d, team, opp, runs=200, seed=7):
    """같은 대결을 runs 번 — 이긴 비율(0~1). 시드를 고정해 같은 팀이면 늘 같은 값."""
    if not team or not opp:
        return 0.0
    rng = random.Random(seed)
    return sum(battle(d, team, opp, rng, log=False)[0] for _ in range(runs)) / runs


def league_teams(d, g, gen_of, final):
    """g 세대 사천왕 4명과 챔피언의 팀 [[(종, 레벨)] × 5] — 늘 같은 팀. 레벨은 8관보다 낮지만 22마리 5연전이라 더 어렵다:
    8관 레벨에서 사천왕 -13~-7, 챔피언 -5. 8관을 넘은 팀(경험치 2500)이면 약 80%(2026-10-21 실측 — 8관 +4~+12 였을 땐
    경험치를 다 채워도 0%)."""
    top = 12 + 7 * 7 + (g - 1) * 5 - 13  # 8관 레벨 - 13
    ok = sorted(n for n in gen_of if gen_of[n] <= g and n in d['stats'] and n in d['types'])
    teams = []
    for k, t in enumerate(LEAGUE[g]):
        rng = random.Random(g * 1000 + k)
        pool = [n for n in ok if t in d['types'][n]] or ok
        ends = [n for n in pool if n in final] or pool
        teams.append([(rng.choice(ends if j == ELITE_COUNT - 1 else pool), top + 2 * k) for j in range(ELITE_COUNT)])
    strong = sorted((n for n in ok if n in final), key=lambda n: -sum(d['stats'][n]))[:30] or ok
    rng = random.Random(g * 1000 + 9)
    teams.append([(n, top + 8) for n in rng.sample(strong, min(CHAMP_COUNT, len(strong)))])
    return teams


def gauntlet(d, team, teams, rng, log=True):
    """사천왕·챔피언 연전 — 판마다 체력은 회복, 한 판이라도 지면 끝. (이겼나, 기록) — 판 앞에 ('trainer', 순서)."""
    ev = []
    for k, opp in enumerate(teams):
        if log:
            ev.append(('trainer', k))
        won, part = battle(d, team, opp, rng, log)
        ev += part
        if not won:
            return False, ev
    return True, ev


def league_rate(d, team, teams, runs=100, seed=7):
    """연전을 runs 번 — 끝까지 이긴 비율."""
    if not team or not teams:
        return 0.0
    rng = random.Random(seed)
    return sum(gauntlet(d, team, teams, rng, log=False)[0] for _ in range(runs)) / runs


def gym_team(d, g, i, gen_of, final):
    """g 세대 i 번째(0부터) 체육관의 상대 [(종, 레벨)] — 늘 같은 팀(체육관마다 고정 시드).
    gen_of(종 → 세대)에 든 종 중 그 타입이면서 g 세대까지인 것에서, 마지막은 최종 진화형. 종이 모자라면 겹쳐 쓴다.
    전설·환상처럼 체육관에 안 나올 종은 부르는 쪽이 gen_of 에서 뺀다."""
    t = GYMS[g][i][0]
    pool = sorted(n for n, ts in d['types'].items() if t in ts and n in gen_of and gen_of[n] <= g and n in d['stats'])
    if not pool:
        return []
    rng = random.Random(g * 100 + i)
    # 1세대 1관 Lv12 ~ 8관 Lv61. 지금 가방(2단계 Lv39)으로 1~5관은 쉽고 6~8관은 배틀로 10~25레벨 키워야 이긴다(2026-10-21 실측)
    k, lv = OPP_COUNT[i], 12 + i * 7 + (g - 1) * 5
    ends = [n for n in pool if n in final] or pool
    picks = [rng.choice(pool) for _ in range(k - 1)] + [rng.choice(ends)]
    return [(n, lv + (2 if j == k - 1 else 0)) for j, n in enumerate(picks)]


def recommend(d, cands, opp, size=TEAM_MAX, shortlist=12, runs=60, seed=11, rate=None):
    """가진 포켓몬 cands [(가방 번호, 종, 레벨)] 중 opp 에 맞서 승률이 가장 오르도록 하나씩 더한 팀 [가방 번호].
    먼저 상성·능력치로 shortlist 마리를 추리고(전부 돌리면 느리다), 그 안에서 고른다.
    rate(팀) 를 주면 승률 대신 그것으로 고른다 — 사천왕 연전처럼 상대가 여러 팀일 때(opp 는 그 팀들을 이어 붙인 것)."""
    cands = [c for c in cands if c[1] in d['stats'] and c[1] in d['types']]
    if not cands or not opp:
        return []

    def score(c):
        m = Mon(d, c[1], c[2])
        return sum(matchup(d, c[1], n) for n, _ in opp) * (sum(m.st) / 100)
    pool = sorted(cands, key=score, reverse=True)[:shortlist]
    team = []
    while len(team) < min(size, len(pool)):
        best = max((c for c in pool if c not in team),
                   key=lambda c: ((rate or (lambda tm: win_rate(d, tm, opp, runs, seed)))([(x[1], x[2]) for x in team + [c]]),
                                  score(c)))
        team.append(best)
    return [c[0] for c in team]


def selftest():
    # 작은 가짜 데이터: 1 물(11) · 2 불꽃(10) · 3 풀(12) — 물 > 불꽃 > 풀 > 물
    d = build([{'pokemon_id': str(p), 'stat_id': str(s), 'base_stat': '50'} for p in (1, 2, 3) for s in range(1, 7)],
              [{'id': str(p), 'species_id': str(p), 'is_default': '1'} for p in (1, 2, 3)],
              [{'pokemon_id': '1', 'type_id': '11', 'slot': '1'}, {'pokemon_id': '2', 'type_id': '10', 'slot': '1'},
               {'pokemon_id': '3', 'type_id': '12', 'slot': '1'}],
              [{'damage_type_id': a, 'target_type_id': b, 'damage_factor': f} for a, b, f in
               (('11', '10', '200'), ('10', '12', '200'), ('12', '11', '200'), ('10', '11', '50'), ('12', '10', '50'),
                ('11', '12', '50'))],
              [{'type_id': '11', 'local_language_id': '3', 'name': '물'}, {'type_id': '11', 'local_language_id': '9', 'name': 'Water'}])
    d = json.loads(json.dumps(d))  # 파일로 쓰고 읽은 것과 같게(키가 글자)
    d = {'stats': {int(k): v for k, v in d['stats'].items()}, 'types': {int(k): v for k, v in d['types'].items()},
         'eff': d['eff'], 'tnames': {int(k): v for k, v in d['tnames'].items()}}
    assert d['types'][1] == [11] and d['stats'][2] == [50] * 6 and d['tnames'][11] == ['물', 'Water']
    assert factor(d, 11, [10]) == 2.0 and factor(d, 10, [11]) == 0.5 and matchup(d, 1, 2) == 4.0
    assert level(0, 0) == 15 and level(2, 999) == 15 + 24 + 999 // XP_PER_LEVEL and level(1, 10**6) == 27 + XP_LEVEL_CAP
    # 같은 레벨이면 상성이 이긴다 · 시드가 같으면 결과도 같다
    assert win_rate(d, [(1, 30)], [(2, 30)]) > 0.9 and win_rate(d, [(3, 30)], [(2, 30)]) < 0.1
    assert win_rate(d, [(1, 30)], [(2, 30)], seed=3) == win_rate(d, [(1, 30)], [(2, 30)], seed=3)
    won, ev = battle(d, [(3, 30), (1, 30)], [(2, 30)], random.Random(1))
    assert won and ev[0] == ('send', 'foe', 2, 30) and ev[1] == ('send', 'me', 1, 30)  # 불꽃 상대엔 물부터 낸다
    assert ev[-1][0] == 'faint' and ev[-1][1] == 'foe'
    # 추천: 불꽃 체육관이면 물을 고른다
    assert recommend(d, [(0, 3, 30), (1, 1, 30), (2, 2, 30)], [(2, 30), (2, 32)], size=1) == [1]
    # 체육관 상대: 늘 같은 팀 · 마지막은 최종 진화형 · 종이 모자라면 겹쳐 쓴다
    gen_of = {1: 1, 2: 1, 3: 1}
    GYMS[99] = [(10, 0)] * 8
    t1 = gym_team(d, 99, 7, gen_of, final={2})
    assert t1 == gym_team(d, 99, 7, gen_of, final={2}) and len(t1) == OPP_COUNT[7] and t1[-1][0] == 2
    assert all(n == 2 for n, _ in t1) and t1[-1][1] == t1[0][1] + 2
    del GYMS[99]
    # 사천왕·챔피언: 늘 같은 팀 · 4명 4마리 + 챔피언 6마리 · 8관보다 강하다 · 연전은 지면 그 판에서 끝
    LEAGUE[99] = [10, 10, 10, 10]
    lt = league_teams(d, 99, gen_of, final={2})
    assert lt == league_teams(d, 99, gen_of, final={2}) and [len(x) for x in lt] == [4, 4, 4, 4, min(CHAMP_COUNT, 1)]
    assert lt[0][0][1] == 12 + 7 * 7 + 98 * 5 - 13 and lt[3][0][1] == lt[0][0][1] + 6 and lt[4][0][1] == lt[0][0][1] + 8
    del LEAGUE[99]
    won, ev = gauntlet(d, [(1, 100)], [[(2, 10)], [(2, 10)]], random.Random(2))
    assert won and [e for e in ev if e[0] == 'trainer'] == [('trainer', 0), ('trainer', 1)]
    won, ev = gauntlet(d, [(3, 10)], [[(2, 60)], [(2, 10)]], random.Random(2))
    assert not won and ('trainer', 1) not in ev
    assert league_rate(d, [(1, 100)], [[(2, 10)], [(2, 10)]]) == 1.0
    assert all(len(v) == 4 for v in LEAGUE.values()) and sorted(LEAGUE) == list(range(1, 10))
    assert all(len(v) == 8 for v in GYMS.values()) and sorted(GYMS) == list(range(1, 10))
    print('battle selftest ok')


if __name__ == '__main__':
    selftest()
