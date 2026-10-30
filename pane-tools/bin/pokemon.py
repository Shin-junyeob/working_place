#!/usr/bin/env python3
"""포켓몬 — Claude 를 쓴 만큼(누적 토큰) 포켓몬을 발견해 잡고, 한 마리를 데리고 다니며 진화시켜 세대별 도감을 채운다.

누적 토큰: 각 세션의 pane-tools mod 가 usage/<sid>.json 의 gained 에 적는 값(컨텍스트가 늘어난 만큼)을 모두 더한 것.
- 도감은 세대별(1~9세대). 데이터는 처음 열 때 PokeAPI 에서 받아 ~/.claude/pane-tools/pokedex.json 에 둔다(_pokedata.py). 그 세대 도감을 다 채우거나
  사천왕·챔피언을 이기면 다음 세대가 열리고(opened_gen), 야생에선 열린 세대 중 가장 최근 세대가 나온다. 이상한사탕(주간 상)은 동료를 바로 진화시킨다.
- 나오는 순서: 스타팅·피카츄·이브이 → 일반(원작 포획률 높은 = 흔한 것부터) → 전설 → 환상. 앞쪽 WINDOW 마리 중 무작위.
- ENCOUNTER_EVERY 토큰마다 탐색 1회. 볼 BALLS 개 + 보유 볼, 다 빗나가면 도망(나중에 다시 나온다). 잡으면 보유 볼 +1.
- 지금 가방에 있는 종은 다른 종의 1/10 확률로만 나온다(BOXED_WEIGHT). 나오면 똑같이 잡을 수 있다 — 같은 종이라도 개체값(공·방·체
  0~15, roll_iv)이 달라 골라 키운다. 남는 것은 [박사에게] 보내면 급에 따라 몬스터볼 1~5개(dupe_balls) — [정리]는 같은 종 중
  개체값·경험치가 가장 좋은 것만 남기고 한꺼번에. 동료·팀·이로치는 보내지 않는다(send_away).
- 동료는 한 마리. 데리고 있는 동안 쌓인 토큰이 경험치 — STAGE_XP 를 넘으면 진화. 아직 안 열린 세대로의 진화는 그 세대가 열린 뒤.
  갈래가 여럿이면 아직 가방에 없는 모습을 먼저 고른다.
- 체육관·사천왕은 그 세대 포켓몬만 나간다(팀의 다른 세대는 빠진다) — 세대마다 팀을 새로 키운다. 상대는 레벨
  +OPP_LV_BONUS 와 개체값(체육관 7~14 · 사천왕 14 · 챔피언 15)을 가진다(_battle.py).
- 볼 네 가지: 몬스터볼 · 슈퍼볼(1.5배) · 하이퍼볼(2배) · 마스터볼(반드시 잡힘). 전설·환상은 하이퍼볼·마스터볼로만
  잡힌다(다른 볼은 쓰지 않고 알려만 준다). 마스터볼은 세대마다 두 개 — 8관 지방 정복과 사천왕·챔피언 첫 승리.
  체육관은 처음 이길 때마다 하이퍼볼 1개. [교환] → [몬스터볼]에서 볼을 위 단계로 바꾼다(TRADES — 몬스터볼 5 → 슈퍼볼,
  슈퍼볼 20 → 하이퍼볼, 하이퍼볼 5 → 마스터볼). 슈퍼볼은 일한 보상 — 그날 push·PR 병합·배포가 든 completed 가
  하나라도 있으면 1개(하루 1개, 기록은 feed.py 가 읽는 ~/.claude/jobs 의 timeline). 그런 날이 STREAK_DAYS 일 연속이면 하이퍼볼.
- 알: 야생 포켓몬을 잡을 때 EGG_CATCH 확률로 하나(최대 EGG_MAX), 지방 정복 때 하나.
- 주간 과제: 주마다(월요일) WEEKLY 에서 하나 — 이루면 WEEKLY_PRIZE.
- 리전폼(알로라·가라르·히스이·팔데아 모습, FORMS): 이전 세대 탐색(OLD_GEN_RATE)에 그 종의 세대가 지난 폼이 함께 나온다.
  잡으면 가방에 폼 번호(FORMS 의 키, 10000 위)로 들어가 진화·레벨·배틀을 한다 — 종족값·타입은 그 모습 것(battle.json),
  세대·진화 단계는 원래 종으로(sp). 같은 지방 모습으로 진화하고(evo_next), 지방 전용 진화형(REGIONAL_EVO)도 있다.
  도감 숫자에는 안 들어가고 st['forms'] 에 따로 모인다(도감 마지막 쪽에 목록).
- 합체(FUSIONS): 가방에서 큐레무·네크로즈마·버드렉스를 골라 [합체] — 가방의 레시라무·제크로무 / 솔가레오·루나아라 /
  블리자포스·레이스포스 하나를 재료로 써서(사라진다) 합체 모습이 되고, 그 모습의 타입·종족값으로 싸운다. 분리는 없다(2026-10-30).
- 특수 모습(SPECIALS — 메가진화·원시회귀·울트라버스트·거다이맥스): 세대가 열리면(6·7·8·9) 그 포켓몬 + 아이템(메가스톤은 연구 완료,
  구슬은 레이드 포획, 다이수프는 레이드 승리)으로 영구히 바뀐다(change_options · change). 가방 F → 변신 화면.
- 연구 레벨: 종마다 잡기 RESEARCH_CATCH(전설·환상 1) · 진화 1(진화형이 있으면) · 배틀 승리 RESEARCH_WIN 을 채우면 도감 ★ 와
  RESEARCH_PRIZE(research_bump). 우두머리: 탐색의 ALPHA_RATE 로 붉은 눈의 큰 개체 — 포획률 절반, 볼 ALPHA_TRIES 번 안에 못 잡으면
  도망, 잡으면 개체값 최소 ALPHA_IV. 레이드: 주마다 열린 세대의 전설 하나(raid_boss)가 체육관 목록 맨 위 — 모든 세대 팀으로 HP
  ×RAID_HP 보스를 이기면 레이드볼 RAID_BALLS 개로만 잡을 기회(가진 볼은 못 쓴다), 잡든 놓치든 그 주는 끝.
- 이로치: 탐색마다 SHINY_RATE. 같은 종이라도 이로치와 기본 모습은 다른 포켓몬으로 친다(가방 1/10 · 진화 갈래 고르기 모두 따로). 이름은 금색.
- 조작은 방향키·Enter·q: 목록 화면은 ↑↓ 로 줄, ←→ 로 아래 버튼을 고르고, 다른 화면은 방향키로 버튼을 고른다(move_focus).
  도감은 ←→ 가 세대, 도감 상세는 ←→ 가 앞뒤 포켓몬. 가방만 Enter 동료 · Space 팀 · ←→ 세대 · Tab 정렬(SORTS, PC 설정에 저장) · F 합체·분리.
  화면은 패널 폭에 맞춘다 — 긴 줄은 para/fold 로 접고, 80칸 미만이면 버튼 여백을 줄인다. 마우스 클릭도 된다.
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
from datetime import datetime, timedelta

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
EVO_WILD_WEIGHT = 0.1  # 이전 세대 종에서 진화하는 종(에브이·블래키 등)도 1/10 — 주로 진화로 얻게(evo_wild)
SHINY_RATE = 1 / 256
# [교환] → [몬스터볼]: (낼 볼, 받을 볼, 개수) — 마스터볼까지 몬스터볼 500개(5×20×5). 전설은 하이퍼볼부터라 슈퍼볼→하이퍼볼이 비싸다(2026-10-28)
TRADES = [('balls', 'super', 5), ('super', 'hyper', 20), ('hyper', 'master', 5)]
BALL_BONUS = {'ball': 1.0, 'super': 1.5, 'hyper': 2.0}  # 마스터볼은 배율 없이 반드시 잡힌다(throw)
SUPER_SESSIONS = 1  # 하루에 내보낸 일을 끝낸 세션이 이만큼이면 슈퍼볼 1개 — 세션 하나만 쓰는 PC도 받게(2026-10-21 3→1)
SHIP = re.compile(r'PR|병합|배포|merge|deploy|push|푸시', re.I)  # completed 요약에 이게 있으면 '내보낸 일'
NEEDS_NAG = 600  # needs 를 이만큼(초) 넘게 두면 동료가 재촉한다
STREAK_DAYS = 3  # 보상받은 날이 며칠 연속이면 하이퍼볼(3·6·9일째) — 2026-10-23 알에서 바꿈(알은 포획 때 EGG_CATCH)
ALPHA_RATE, ALPHA_IV, ALPHA_TRIES = 0.01, 12, 3  # 우두머리: 탐색 100번에 1번 · 개체값 최소 12 · 볼 3번 안에 못 잡으면 도망
# 레이드 보스 HP 배수 · 레이드볼 · 도전 1번에 쓰는 탐색. 레이드는 모든 세대가 나간다 — 모든 세대 최종 진화형 중 고른 팀을 보스 레벨에 맞춰
# 1~3세대 전설 17마리로 잰 승률(2026-10-30): ×40 개체값 7 49%·15 57%, ×48 40%·49%, ×56 28%·28%
RAID_HP, RAID_BALLS, RAID_COST = 48, 3, 2
RESEARCH_CATCH, RESEARCH_WIN, RESEARCH_PRIZE = 5, 3, ('super', 2)  # 연구: 잡기 5(전설·환상 1) · 진화 1(진화형이 있으면) · 배틀 승리 3
IV_FLOOR = 10  # 알·전설·환상은 개체값이 최소 이만큼(포켓몬고처럼)
OLD_GEN_RATE = 0.2  # 탐색 5번 중 1번은 이전 세대 전체에서 — 다 채운 세대도 이로치를 노릴 수 있게(현재 8 : 이전 2)
EGG_CATCH, EGG_MAX, EGG_STEP = 0.1, 3, 5000  # 잡을 때 알을 함께 얻을 확률 · 가질 수 있는 알 · 부화 걸음 하나당 토큰
# 주간 과제 (종류, 목표, 한국어, 영어) — 주 번호로 하나를 고른다. 이번 주에 쌓인 횟수로 센다
WEEKLY = [('catch', 8, '포켓몬 {n}마리 잡기', 'Catch {n} Pokémon'), ('explore', 15, '풀숲 {n}번 탐색', 'Explore {n} times'),
          ('gym', 5, '체육관·사천왕 {n}번 이기기', 'Win {n} gym/league battles'), ('evolve', 2, '{n}번 진화시키기', 'Evolve {n} times'),
          ('ship', 4, 'push·PR·배포한 날 {n}일', 'Ship on {n} days'), ('hatch', 1, '알 {n}개 부화', 'Hatch {n} egg(s)')]
WEEKLY_PRIZE = [('hyper', 2), ('super', 3), ('candy', 1)]  # 일주일에 한 번이라 후하게 · 이상한사탕은 매주 1개(동료 즉시 진화)
EGG_SHINY = 1 / 64
# 알에서 포켓몬과 함께 나오는 덤 — (볼 종류, 개수, 확률%) (2026-10-21 정함)
EGG_BONUS = [('balls', 1, 60), ('balls', 2, 20), ('balls', 3, 10), ('super', 1, 7), ('hyper', 1, 3)]
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


FORMS = {}  # 리전폼 그림 번호 → (종 번호, 'alola' · 'paldea-aqua-breed' …) — load_forms() 가 채운다
REGION = {'alola': ('알로라', 'Alolan'), 'galar': ('가라르', 'Galarian'), 'hisui': ('히스이', 'Hisuian'), 'paldea': ('팔데아', 'Paldean')}
BREED = {'combat': ('컴뱃종', 'Combat Breed'), 'blaze': ('블레이즈종', 'Blaze Breed'), 'aqua': ('워터종', 'Aqua Breed')}
# 지방 모습만 가는 진화형(원작) — 폼 번호 → 종 번호. 가라르 나옹 → 나이킹, 가라르 파오리 → 창파나이트, 가라르 지그제구리(진화형)
# → 가로막구리, 가라르 코산호 → 산호르곤, 가라르 마임맨 → 마임꽁꽁, 가라르 데스마스 → 데스판, 히스이 포푸니 → 포푸니크,
# 히스이 침바루 → 장침바루, 팔데아 우파 → 토오. 종 번호는 PokeAPI 도감 번호(코드엔 번호만 둔다)
REGIONAL_EVO = {10161: [863], 10166: [865], 10175: [862], 10173: [864], 10168: [866], 10179: [867], 10235: [903],
                10234: [904], 10253: [980]}


# 합체 모습(원작) — 그림 번호(PokeAPI 모습 번호) → (본체 종, 상대 종, 한국어, 영어). 가방에서 본체를 골라 [합체]
FUSIONS = {10022: (646, 644, '블랙큐레무', 'Black Kyurem'), 10023: (646, 643, '화이트큐레무', 'White Kyurem'),
           10155: (800, 791, '네크로즈마(황혼의 갈기)', 'Dusk Mane Necrozma'),
           10156: (800, 792, '네크로즈마(새벽의 날개)', 'Dawn Wings Necrozma'),
           10193: (898, 896, '버드렉스(백마 탄 모습)', 'Ice Rider Calyrex'), 10194: (898, 897, '버드렉스(흑마 탄 모습)', 'Shadow Rider Calyrex')}


SPECIALS = {}  # 특수 모습 번호 → (종, 'mega'|'gmax'|'primal'|'ultra', 열리는 세대, 'x'|'y'|'z'|'', 덧붙일 말) — load_specials()
SPECIAL_KIND = {'mega': ('메가', 'Mega'), 'gmax': ('거다이맥스', 'Gigantamax'), 'primal': ('원시', 'Primal'), 'ultra': ('울트라', 'Ultra')}
SPECIAL_EXTRA = {'male': ('수컷', 'Male'), 'female': ('암컷', 'Female'), 'original': ('500년 전 색', 'Original Color'),
                 'curly': ('젖힌 모습', 'Curly'), 'droopy': ('늘어진 모습', 'Droopy'), 'stretchy': ('뻗은 모습', 'Stretchy'),
                 'single-strike': ('일격의 태세', 'Single Strike'), 'rapid-strike': ('연격의 태세', 'Rapid Strike'),
                 'amped': ('하이한 모습', 'Amped'), 'low-key': ('로우한 모습', 'Low Key')}
ULTRA_BASE = (10155, 10156)  # 울트라네크로즈마는 합체한 네크로즈마(황혼의 갈기·새벽의 날개)에서
PRIMAL_ORB = {382: ('쪽빛구슬', 'Blue Orb'), 383: ('주홍구슬', 'Red Orb')}


def load_specials():
    """받아 둔 특수 모습(specials.json)을 읽는다. 없으면 False — 특수 모습 없이 그대로 돈다."""
    try:
        with open(_pokedata.SPECIALS, encoding='utf-8') as f:
            SPECIALS.update({p: (n, kind, g, letter, extra) for p, n, kind, g, letter, extra in json.load(f) if n in DEX})
    except (OSError, ValueError):
        return False
    return True


def sp(n):
    """리전폼·합체 모습 번호면 원래(본체) 종 번호, 아니면 그대로 — 세대·진화 단계·포획률처럼 종이 정하는 것을 읽을 때."""
    return FORMS[n][0] if n in FORMS else FUSIONS[n][0] if n in FUSIONS else SPECIALS[n][0] if n in SPECIALS else n


def evo_next(n):
    """다음 모습들(세대가 열렸는지·가방과 무관). 리전폼은 같은 지방의 진화형 폼과 REGIONAL_EVO 로만 —
    알로라 꼬렛은 알로라 레트라로(보통 레트라로는 안 간다)."""
    if n not in FORMS:
        return CHILDREN.get(n, [])
    s, region = FORMS[n][0], FORMS[n][1].split('-')[0]
    kids = CHILDREN.get(s, [])
    return [p for p, (c, ident) in FORMS.items() if c in kids and ident.split('-')[0] == region] + \
        [c for c in REGIONAL_EVO.get(n, []) if c in DEX]


def load_forms():
    """받아 둔 리전폼(forms.json)을 읽는다. 없으면 False — 리전폼 없이 그대로 돈다."""
    try:
        with open(_pokedata.FORMS, encoding='utf-8') as f:
            FORMS.update({p: (sp, ident) for p, sp, ident in json.load(f) if sp in DEX})
    except (OSError, ValueError):
        return False
    return True


load_dex()
load_forms()
load_specials()
STARTERS = {1, 4, 7, 152, 155, 158, 252, 255, 258, 387, 390, 393, 495, 498, 501, 650, 653, 656,
            722, 725, 728, 810, 813, 816, 906, 909, 912, 25, 133, 172}


def gen(n):
    return DEX[sp(n)][2]  # 리전폼은 원래 종의 세대


def depth(n):
    """진화 단계(0부터). 그 포켓몬보다 나중 세대에 추가된 진화 전(피츄 같은 베이비)은 세지 않는다 — 1세대 피카츄는 1단계.
    리전폼은 원래 종의 단계(알로라 레트라는 2단계)."""
    n = sp(n)
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


def opened_gen(st):
    """열린 가장 높은 세대 — 1세대부터, 도감을 다 채웠거나 사천왕·챔피언을 이긴 세대의 다음 세대가 열린다(2026-10-27:
    도감만으로는 진화로만 얻는 종 때문에 한 달씩 갇혔다)."""
    g = 1
    while g < GENS and (gen_done(st, g) or str(g) in st.get('league', {})):
        g += 1
    return g


def wild_pool(st):
    """야생에서 나올 차례인 포켓몬들, 순서대로 — 열린 세대 중 가장 최근 세대부터, 그 세대 야생을 다 잡았으면 이전 세대.
    아직 못 잡은 같은 세대 진화형이 남은 계열도 계속 나온다."""
    if current_gen(st) is None:
        return []
    caught = set(st['caught'])
    for g in range(opened_gen(st), 0, -1):
        pool = [n for n in DEX if gen(n) == g and wild_ok(n)
                and (n not in caught or any(gen(d) == g and d not in caught for d in descendants(n)))]
        if pool:
            return sorted(pool, key=order_key)
    return []


def old_pool(st):
    """이전 세대(열린 세대보다 아래 전부) 야생 종 — 잡은 종도 나온다(같은 모습이 가방에 있으면 볼로 바뀐다), 전설·환상 포함.
    모든 세대를 다 채웠으면 전 세대에서. 그 세대 종의 리전폼(FORMS 번호)도 함께 — 진화형 폼도 야생에서 바로."""
    top = opened_gen(st) if wild_pool(st) else GENS + 1
    return [n for n in DEX if gen(n) < top and wild_ok(n)] + [p for p, (sp, _) in FORMS.items() if gen(sp) < top]


ROMAN = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX']


def shiny_rate(st, n, base=SHINY_RATE):
    """그 세대의 빛나는 부적이 있으면 이로치 2배 — 세대를 완성하면 그 세대 부적을 받는다."""
    return base * (2 if gen(n) in st.get('charms', []) else 1)


def gen_done(st, g):
    return sum(1 for n in st['caught'] if gen(n) == g) >= GEN_SIZE[g]


def _final_evolved(st):
    """가방에서 진화를 거쳐 최종 모습이 된 포켓몬 수."""
    return sum(1 for m in st['box'] if not evo_next(m['id']) and depth(m['id']) > 0)


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
      (lambda g: lambda st: all(f'gym:{g}-{i}' in st.get('gym', {}) for i in range(8)))(g)) for g in range(1, 10)] + \
    [(f'champ{g}', f'{g}세대 챔피언', f'Gen {g} champion', (lambda g: lambda st: str(g) in st.get('league', {}))(g))
     for g in range(1, 10)] + [
    ('form1', '첫 리전폼', 'First regional form', lambda st: len(st.get('forms', [])) >= 1),
    ('form_all', '리전폼 완성', 'All regional forms', lambda st: bool(FORMS) and len(st.get('forms', [])) >= len(FORMS)),
    ('fuse1', '첫 합체', 'First fusion', lambda st: st.get('fusions', 0) >= 1),
    ('research1', '첫 연구 완료', 'First research', lambda st: len(st.get('researched', [])) >= 1),
    ('research10', '연구 10', '10 researched', lambda st: len(st.get('researched', [])) >= 10),
    ('research50', '연구 50', '50 researched', lambda st: len(st.get('researched', [])) >= 50),
    ('alpha1', '첫 우두머리', 'First alpha', lambda st: any(m.get('alpha') for m in st['box'])),
    ('raid1', '첫 레이드 포획', 'First raid catch', lambda st: st.get('raids', 0) >= 1),
    ('mega1', '첫 메가진화', 'First Mega Evolution', lambda st: any(SPECIALS.get(p, (0, ''))[1] == 'mega' for p in st.get('specials', []))),
    ('gmax1', '첫 거다이맥스', 'First Gigantamax', lambda st: any(SPECIALS.get(p, (0, ''))[1] == 'gmax' for p in st.get('specials', [])))]


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
        if b.startswith('champ'):  # 사천왕·챔피언을 처음 이기면 마스터볼 — 세대의 마지막 콘텐츠 둘이 마스터볼 하나씩
            st['master'] += 1
        if b.startswith('conquer'):  # 지방 정복 — 마스터볼 1개와 알(관마다는 하이퍼볼 1개 — fight)
            st['master'] += 1
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
    fresh = [n for n in pool if n not in inbag and not evo_wild(n)][:WINDOW]
    if not fresh:  # 남은 게 전부 가방 속 종·이전 세대 진화형이면 그것들끼리 — 진화로만 묶여 막히지 않게
        return [(n, 1) for n in pool[:WINDOW]]
    front = pool[:pool.index(fresh[-1]) + 1]
    return [(n, BOXED_WEIGHT if n in inbag else EVO_WILD_WEIGHT if evo_wild(n) else 1) for n in front]


def evo_wild(n):
    """이전 세대 종에서 진화하는 종(이브이 → 에브이·블래키, 골뱃 → 크로뱃) — 원작은 진화로만 얻지만, 진화로만 묶으면
    세대마다 십수 마리를 동료로 하나씩 키워야 해서 풀숲에도 EVO_WILD_WEIGHT 로 드물게 나온다(2026-10-28 정함)."""
    pre = DEX[n][3]
    return bool(pre) and gen(pre) < gen(n)


def roll_iv(rng=random, floor=0):
    """개체값 [공, 방, 체] 0~15 — 배틀 능력치에 더해진다(_battle.calc)."""
    return [floor + int(rng.random() * (16 - floor)) for _ in range(3)]


def iv_of(m):
    return tuple(m.get('iv', (0, 0, 0)))


def iv_text(m):
    """'공13 방15 체14 (93%)' — 15/15/15 는 ★."""
    a, d, h = iv_of(m)
    pct = round((a + d + h) / 45 * 100)
    return L(f'공{a} 방{d} 체{h}', f'A{a} D{d} H{h}') + f' ({pct}%)' + (' ★' if pct == 100 else '')


def name(n):
    """종 이름 — 리전폼 번호면 '알로라 라타타'처럼(한국어 폼 이름은 PokeAPI 에 일부만 있어 지방 이름을 붙여 만든다)."""
    if n in FUSIONS:
        return L(FUSIONS[n][2], FUSIONS[n][3])
    if n in SPECIALS:  # '메가리자몽 X' · '거다이맥스 우라오스(연격의 태세)' · '원시 가이오가' · '울트라네크로즈마'
        s, kind, _, letter, extra = SPECIALS[n]
        ex = SPECIAL_EXTRA.get(extra, (extra, extra)) if extra else None
        if kind == 'ultra':
            return L('울트라네크로즈마', 'Ultra Necrozma')
        ko = f'{SPECIAL_KIND[kind][0]}{DEX[s][1]}' if kind == 'mega' else f'{SPECIAL_KIND[kind][0]} {DEX[s][1]}'
        return L(ko + (f' {letter.upper()}' if letter else '') + (f'({ex[0]})' if ex else ''),
                 f'{SPECIAL_KIND[kind][1]} {DEX[s][6]}' + (f' {letter.upper()}' if letter else '') + (f' ({ex[1]})' if ex else ''))
    if n in FORMS:
        sp, ident = FORMS[n]
        part = ident.split('-')
        r, b = REGION[part[0]], BREED.get(part[1]) if len(part) > 1 else None
        return L(f'{r[0]} {DEX[sp][1]}' + (f'({b[0]})' if b else ''), f'{r[1]} {DEX[sp][6]}' + (f' ({b[1]})' if b else ''))
    return L(DEX[n][1], DEX[n][6])


def catch_rate(n):
    if DEX[n][5]:
        return 0.2 if DEX[n][5] == 1 else 0.15
    return 0.35 + 0.35 * DEX[n][4] / 255  # 원작 포획률이 높을수록 잘 잡힌다 — 35~70%(2026-10-21 최대 90→70%, 마스터볼을 넣으며)


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
            'super': 0, 'hyper': 0, 'master': 0, 'shiny': [], 'rewarded': [], 'reward_since': None, 'news': [],
            'badges': {}, 'charms': [], 'evolved': 0, 'exchanged': 0, 'super_earned': None, 'eggs': [], 'showcase': [],
            'gym': {}, 'team': [], 'league': {}, 'weekly': None, 'candy': 0, 'forms': [], 'forms_seen': [],
            'research': {}, 'researched': [], 'raid': None, 'items': {}, 'specials': []}  # forms_boxed 는 load 가 처음 옮길 때 적는다


def load(root=ROOT):
    try:
        with open(f'{root}/pokemon.json', encoding='utf-8') as f:
            st = {**new_state(), **json.load(f)}
    except (OSError, ValueError):
        return new_state()
    if not st.get('forms_boxed'):  # 리전폼이 가방에 들어가기 전(2026-10-28)에 잡은 것 — 한 번만 가방에 넣는다(개체값은 아래에서)
        inbag = {m['id'] for m in st['box']}
        st['box'] += [{'id': p, 'xp': 0} for p in st.get('forms', []) if p in FORMS and p not in inbag]
        st['forms_boxed'] = True
    if not st['research']:  # 연구를 넣기 전(2026-10-30)에 잡은 것 — 가방 마릿수를 잡은 횟수로(상은 주지 않는다)
        for m in st['box']:
            if m['id'] in DEX:
                r = st['research'].setdefault(str(m['id']), {})
                r['c'] = r.get('c', 0) + 1
    for i, m in enumerate(st['box']):  # 개체값을 넣기 전(2026-10-28)에 잡은 것 — 저장될 때까지 같은 값이 나오게 자리·종으로 고정
        if 'iv' not in m:
            m['iv'] = roll_iv(random.Random(f'{i}:{m["id"]}'), IV_FLOOR if DEX[sp(m['id'])][5] else 0)
    return st


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
    """박사에게 보낼 때 받는 볼 — 흔할수록 적고 전설·환상은 5개. 리전폼은 원래 종 기준."""
    n = sp(n)
    if DEX[n][5]:
        return 5
    cap = DEX[n][4]
    return 1 if cap >= 190 else 2 if cap >= 90 else 3 if cap >= 45 else 4


def opened_evolutions(st, n):
    """지금 열린 세대 안의 다음 모습들(가방 상태와 무관)."""
    g = opened_gen(st)
    return [c for c in evo_next(n) if gen(c) <= g]


def evolutions(st, n, shiny=False):
    """진화할 수 있는 다음 모습들 — 열린 세대 안에서. 갈래가 여럿이면 가방에 아직 없는 모습만(도감을 채우게), 다 있으면 전부.
    같은 모습이 여럿이어도 된다(2026-10-28 중복 포획부터)."""
    opts, inbag = opened_evolutions(st, n), boxed(st, shiny)  # 이로치는 이로치끼리
    return [c for c in opts if c not in inbag] or opts


def need_xp(n):
    """진화에 필요한 경험치. 진화형이 없으면 None."""
    return STAGE_XP[min(depth(n), 1)] if evo_next(n) else None


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
    odds, old = wild_odds(st), old_pool(st)
    if not odds and not old:
        return None
    st['used'] += 1
    bump(st, 'explore')
    if old and (not odds or rng.random() < OLD_GEN_RATE):
        n = rng.choice(old)
    else:
        n = rng.choices([n for n, _ in odds], weights=[w for _, w in odds])[0]
    if n in FORMS:  # 리전폼 — 이로치 없음, 다른 종처럼 이미 있어도 만나서 잡는다(개체값·박사)
        _mark(st, 'forms_seen', n)
        st['wild'] = {'id': FORMS[n][0], 'form': n, 'balls': BALLS}
        return n, 0
    shiny = rng.random() < shiny_rate(st, n)
    alpha = not DEX[n][5] and rng.random() < ALPHA_RATE
    _mark(st, 'seen', n)
    st['wild'] = {'id': n, 'balls': BALLS, **({'shiny': True} if shiny else {}), **({'alpha': True, 'tries': 0} if alpha else {})}
    return n, 0


def set_partner(st, t, i):
    if st['partner'] is not None:  # 지금 동료가 쌓은 경험치는 그 포켓몬에게 남긴다
        st['box'][st['partner']]['xp'] = partner_xp(st, t)
    st['partner'], st['base'] = i, t


def throw(st, t, rng=random, kind='ball'):
    """볼 하나(kind: ball · super · hyper · master). 'caught' / 'missed' / 'fled' · 볼이 없으면 None ·
    전설·환상에 하이퍼볼·마스터볼이 아니면 'needhyper'(볼을 쓰지 않는다 — 가방에서 바꿔 와 다시 던지게)."""
    w = st['wild']
    if w and w.get('raid'):  # 레이드 보스 — 레이드볼(만날 때 받은 RAID_BALLS 개)만, 하이퍼볼과 같은 2배
        if kind != 'ball':
            return 'raidonly'
        if w['balls'] <= 0:
            return None
        w['balls'] -= 1
        if rng.random() < min(1.0, catch_rate(w['id']) * BALL_BONUS['hyper']):
            st['raid']['done'], st['raids'] = True, st.get('raids', 0) + 1
            orb = [p for p, (s, kind, *_) in SPECIALS.items() if s == w['id'] and kind == 'primal']
            for p in orb:  # 그란돈·가이오가 — 원시회귀 구슬
                give_item(st, f'stone:{p}')
                tell(st, 'item', f'stone:{p}')
            return _caught(st, t, w, rng)
        if w['balls'] <= 0:
            st['wild'], st['raid']['done'] = None, True
            return 'fled'
        return 'missed'
    if not w or (w['balls'] + st['balls'] if kind == 'ball' else st[kind]) <= 0:
        return None
    if DEX[w['id']][5] and kind not in ('hyper', 'master'):
        return 'needhyper'
    if kind != 'ball':
        st[kind] -= 1
    elif w['balls'] > 0:  # 만날 때 받은 볼부터, 다 쓰면 보유 볼
        w['balls'] -= 1
    else:
        st['balls'] -= 1
    if kind == 'master' or rng.random() < min(1.0, catch_rate(w['id']) * BALL_BONUS[kind] * (0.5 if w.get('alpha') else 1)):
        return _caught(st, t, w, rng)
    if w.get('alpha'):  # 우두머리는 ALPHA_TRIES 번 안에 못 잡으면 도망
        w['tries'] = w.get('tries', 0) + 1
        if w['tries'] >= ALPHA_TRIES:
            st['wild'] = None
            return 'fled'
    if w['balls'] + st['balls'] + st['super'] + st['hyper'] + st['master'] <= 0:
        st['wild'] = None
        return 'fled'
    return 'missed'


def _caught(st, t, w, rng):
    """잡았다 — 가방에 넣고(개체값 바닥: 전설·환상 IV_FLOOR · 우두머리 ALPHA_IV) 도감·연구·보상. 'caught'."""
    floor = max(IV_FLOOR if DEX[w['id']][5] else 0, ALPHA_IV if w.get('alpha') else 0)
    # 리전폼은 폼 번호로 가방에 — 도감 숫자(caught) 대신 리전폼 목록(forms)에 적는다
    st['box'].append({'id': w.get('form') or w['id'], 'xp': 0, 'iv': roll_iv(rng, floor),
                      **({'shiny': True} if w.get('shiny') else {}), **({'alpha': True} if w.get('alpha') else {})})
    if w.get('form'):
        _mark(st, 'forms', w['form'])
    else:
        research_bump(st, w['id'], 'c')
        _mark(st, 'caught', w['id'])
        if w.get('shiny'):
            _mark(st, 'shiny', w['id'])
    if st['partner'] is None:
        set_partner(st, t, len(st['box']) - 1)
    st['wild'] = None
    st['balls'] += 1  # 포획 보상 — 중복이 안 나오니 볼은 여기서 쌓인다
    if rng.random() < EGG_CATCH:
        give_egg(st, t)  # 알이 가득 차 있으면 못 받는다
    bump(st, 'catch')
    return 'caught'


def exchange(st, k):
    """TRADES[k] 한 번 — 낼 볼 cost 개 → 받을 볼 1개. 바꿨으면 True. 하이퍼볼로 바꾸면 'hyper1' 훈장이 센다."""
    src, dst, cost = TRADES[k]
    if st[src] < cost:
        return False
    st[src] -= cost
    st[dst] += 1
    if dst == 'hyper':
        st['exchanged'] = st.get('exchanged', 0) + 1
    return True


def _day(at):
    return datetime.fromisoformat(at.replace('Z', '+00:00')).astimezone().strftime('%Y-%m-%d')


def shipped(folder=feed.JOBS):
    """날짜 → push·PR 병합·배포가 든 completed 를 낸 세션 이름들."""
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
        if n['kind'] == 'hatch':  # arg: '번호[*]' 또는 '번호[*]|볼종류:개수'(덤)
            mon, _, extra = n['arg'].partition('|')
            hn, sh = int(mon.rstrip('*')), mon.endswith('*')
            ko, en = (ball_name(*extra.split(':')) if extra else ('', ''))
            return L(f'알이 부화했다! {"✨이로치 " if sh else ""}{name(hn)}(이)가 태어났다!' + (f' 덤으로 {ko}!' if extra else ''),
                     f'An egg hatched! {"✨shiny " if sh else ""}{name(hn)} was born!' + (f' Plus {en}!' if extra else '')), False
        if n['kind'] == 'opengen':
            return L(f'{n["arg"]}세대가 열렸다! 풀숲에서 새 포켓몬이 나온다.', f'Gen {n["arg"]} is open! New Pokémon in the tall grass.'), False
        if n['kind'] == 'streak':
            return L(f'{n["arg"]}일 연속! {pn}(이)가 하이퍼볼을 물어 왔다!', f'{n["arg"]}-day streak! {pn} brought an Ultra Ball!'), False
        if n['kind'] == 'weekly':
            ko = '·'.join(ball_name(b, c)[0] for b, c in WEEKLY_PRIZE)
            en = ', '.join(ball_name(b, c)[1] for b, c in WEEKLY_PRIZE)
            return L(f'주간 과제 달성! {pn}(이)가 {ko}를 받아 왔다!', f'Weekly challenge done! {pn} brought {en}!'), False
        if n['kind'] == 'research':
            pz = ball_name(*RESEARCH_PRIZE)
            return L(f'{name(int(n["arg"]))} 연구 완료! {pn}(이)가 {pz[0]}를 받아 왔다!', f'{name(int(n["arg"]))} research done! {pn} brought {pz[1]}!'), False
        if n['kind'] == 'item':
            names = '·'.join(item_name(k) for k in n['arg'].split(','))
            return L(f'{pn}(이)가 {names}(을)를 찾아 왔다!', f'{pn} found {names}!'), False
        if n['kind'] == 'raid':
            return L(f'레이드 승리! 레이드볼 {RAID_BALLS}개로 {name(int(n["arg"]))}(을)를 잡자!',
                     f'Raid won! Catch {name(int(n["arg"]))} with {RAID_BALLS} Raid Balls!'), False
        if n['kind'] == 'egg':
            return L(f'{pn}(이)가 알을 안고 왔다!', f'{pn} brought an egg!'), False
        if n['kind'] == 'badge' and n['arg'].startswith('conquer'):
            return L(f'{n["arg"][7:]}세대 지방 정복! {pn}(이)가 마스터볼과 알을 받아 왔다!',
                     f'Gen {n["arg"][7:]} gyms cleared! {pn} brought a Master Ball and an egg!'), False
        if n['kind'] == 'badge':
            return L(f'{pn}(이)가 새 훈장 [{badge_name(n["arg"])}]을 보고 좋아한다!',
                     f'{pn} admires the new medal [{badge_name(n["arg"])}]!'), False
        if n['kind'] == 'league':
            return L(f'{n["arg"]}세대 챔피언이 됐다! {pn}(이)가 마스터볼을 받아 왔다!', f'Gen {n["arg"]} champion! {pn} brought a Master Ball!'), False
        if n['kind'] == 'gym':
            return L(f'{pn}(이)가 [{badge_name(n["arg"])}]를 자랑한다! (하이퍼볼 +1)',
                     f'{pn} shows off the [{badge_name(n["arg"])}]! (Ultra Ball +1)'), False
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
    """알에서 나올 수 있는 종과 가중치 — 열린 세대의 1단계(진화 전 없음), 전설·환상 빼고.
    베이비 ×3 · 스타팅 ×2, 가방에 있는 종은 야생처럼 ×BOXED_WEIGHT."""
    top, inbag = opened_gen(st), boxed(st)
    return [(n, (3 if DEX[n][7:8] == [1] else 2 if n in STARTERS else 1) * (BOXED_WEIGHT if n in inbag else 1)) for n in DEX
            if gen(n) <= top and not DEX[n][3] and not DEX[n][5]]


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
    """다 자란 알을 부화한다 — 이로치와 개체값(최소 IV_FLOOR)은 이때 정한다. [(번호, 이로치)]."""
    out = []
    for e in [e for e in st.get('eggs', []) if t - e['base'] >= e['need']]:
        st['eggs'].remove(e)
        n = e['id']
        shiny = rng.random() < shiny_rate(st, n, EGG_SHINY)
        st['box'].append({'id': n, 'xp': 0, 'iv': roll_iv(rng, IV_FLOOR), **({'shiny': True} if shiny else {})})
        research_bump(st, n, 'c')
        for key in ('seen', 'caught') + (('shiny',) if shiny else ()):
            _mark(st, key, n)
        if st['partner'] is None:
            set_partner(st, t, len(st['box']) - 1)
        kind, k, _ = rng.choices(EGG_BONUS, weights=[w for _, _, w in EGG_BONUS])[0]  # 덤 볼 하나는 늘 붙는다
        st[kind] += k
        tell(st, 'hatch', f'{n}{"*" if shiny else ""}|{kind}:{k}')
        bump(st, 'hatch')
        out.append((n, shiny))
    return out


def ball_name(kind, k):
    """('balls'|'super'|'hyper'|'master', 개수) → (한국어, 영어) — '몬스터볼 2개'."""
    ko, en = {'balls': ('몬스터볼', 'Poké Ball'), 'super': ('슈퍼볼', 'Great Ball'), 'hyper': ('하이퍼볼', 'Ultra Ball'),
              'master': ('마스터볼', 'Master Ball'), 'candy': ('이상한사탕', 'Rare Cand')}[kind]
    if kind == 'candy':
        return f'{ko} {k}개', f'{k} {en}{"ies" if int(k) > 1 else "y"}'
    return f'{ko} {k}개', f'{k} {en}{"s" if int(k) > 1 else ""}'


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
    for day, names in sorted(shipped(folder).items()):
        if day >= st['reward_since'] and day not in st['rewarded'] and len(names) >= SUPER_SESSIONS:
            st['rewarded'] = (st['rewarded'] + [day])[-60:]
            st['super'] += 1
            st['super_earned'] = (st.get('super_earned') or 0) + 1
            got += 1
            tell(st, 'super')
            bump(st, 'ship')
            k = streak(st, day)
            if k % STREAK_DAYS == 0:
                st['hyper'] += 1
                tell(st, 'streak', str(k))
    return got


def streak(st, day):
    """day(또는 그 전날)에서 끝나는, 보상받은 날의 연속 일수 — 오늘 아직 안 했어도 어제까지 이어졌으면 센다."""
    got, d = set(st['rewarded']), datetime.strptime(day, '%Y-%m-%d')
    if day not in got:
        d -= timedelta(days=1)
    n = 0
    while d.strftime('%Y-%m-%d') in got:
        n, d = n + 1, d - timedelta(days=1)
    return n


def form_note(n):
    """'꼬렛의 알로라 모습' · '리자몽의 메가 모습' — 도감 상세에서 분류·설명이 없는 모습에."""
    if n in FORMS:
        s, region = FORMS[n][0], REGION[FORMS[n][1].split('-')[0]]
        return L(f'{name(s)}의 {region[0]} 모습', f'{region[1]} form of {name(s)}')
    s, kind = SPECIALS[n][0], SPECIALS[n][1]
    k = {'ultra': ('울트라버스트', 'Ultra Burst'), 'primal': ('원시회귀', 'Primal Reversion')}.get(kind, SPECIAL_KIND[kind])
    return L(f'{name(s)}의 {k[0]} 모습', f'{k[1]} form of {name(s)}')


def item_name(key):
    """아이템 이름 — 'stone:<모습>'(메가스톤·구슬·울트라네크로Z) · 'soup'(다이수프)."""
    if key == 'soup':
        return L('다이수프', 'Max Soup')
    p = int(key.split(':')[1])
    s, kind, _, letter, extra = SPECIALS.get(p, (0, '', 0, '', ''))
    if kind == 'primal':
        return L(*PRIMAL_ORB[s])
    if kind == 'ultra':
        return L('울트라네크로Z', 'Ultranecrozium Z')
    ex = SPECIAL_EXTRA.get(extra, (extra, extra)) if extra else None
    return L(f'{DEX[s][1]}나이트' + letter.upper() + (f'({ex[0]})' if ex else ''), f'{DEX[s][6]}ite' + (f' {letter.upper()}' if letter else '') + (f' ({ex[1]})' if ex else '')) \
        if s in DEX else key


def give_item(st, key, k=1):
    st.setdefault('items', {})[key] = st['items'].get(key, 0) + k


def give_stones(st, n):
    """그 종의 메가스톤들(X·Y 는 따로)과, 네크로즈마면 울트라네크로Z — 쓰는 건 그 세대가 열린 뒤(change_options)."""
    keys = [f'stone:{p}' for p, (s, kind, *_) in SPECIALS.items() if s == n and kind in ('mega', 'ultra')]
    for key in keys:
        give_item(st, key)
    if keys:
        tell(st, 'item', ','.join(keys))


def research_goals(n):
    """그 종의 연구 과제 {'c': 잡기, 'e': 진화, 'w': 배틀 승리} — 진화형이 없으면 진화 과제는 없다."""
    return {'c': 1 if DEX[n][5] else RESEARCH_CATCH, 'e': 1 if n in CHILDREN else 0, 'w': RESEARCH_WIN}


def research_done(st, n):
    r = st.get('research', {}).get(str(n), {})
    return n in DEX and all(r.get(k, 0) >= v for k, v in research_goals(n).items())


def research_bump(st, n, key):
    """연구 기록 하나 — 과제를 다 채우면 연구 완료(도감 ★)와 RESEARCH_PRIZE. 리전폼·합체 모습 번호는 세지 않는다."""
    if n not in DEX:
        return
    r = st.setdefault('research', {}).setdefault(str(n), {})
    r[key] = r.get(key, 0) + 1
    if research_done(st, n) and n not in st.setdefault('researched', []):
        st['researched'].append(n)
        st[RESEARCH_PRIZE[0]] += RESEARCH_PRIZE[1]
        tell(st, 'research', str(n))
        give_stones(st, n)  # 첫 메가스톤
    elif key == 'c' and n in st['researched'] and (r['c'] - research_goals(n)['c']) % research_goals(n)['c'] == 0:
        give_stones(st, n)  # 연구를 끝낸 뒤엔 잡기 목표만큼 더 잡을 때마다 하나 더 — 같은 메가진화를 또 만들 수 있게


def research_text(st, n):
    """'연구 — 잡기 3/5 · 진화 0/1 · 배틀 승리 1/3' (다 채웠으면 ★ 연구 완료)."""
    r, names = st.get('research', {}).get(str(n), {}), {'c': L('잡기', 'catch'), 'e': L('진화', 'evolve'), 'w': L('배틀 승리', 'battle wins')}
    parts = [f'{names[k]} {min(r.get(k, 0), v)}/{v}' for k, v in research_goals(n).items() if v]
    return (L('★ 연구 완료 — ', '★ Research done — ') if research_done(st, n) else L('연구 — ', 'Research — ')) + ' · '.join(parts)


def raid_boss(st, key=None):
    """이번 주 레이드 (세대, 보스) — 열린 세대 중 전설이 있는 세대에서, 주 번호로 정한다. 없으면 None."""
    key = key or week_key()
    gens = [g for g in range(1, opened_gen(st) + 1) if any(gen(n) == g and DEX[n][5] == 1 for n in DEX)]
    if not gens:
        return None
    rng = random.Random(f'raid:{key}')
    g = rng.choice(gens)
    return g, rng.choice(sorted(n for n in DEX if gen(n) == g and DEX[n][5] == 1))


def raid_state(st, key=None):
    """이번 주 레이드 기록 {'week', 'won', 'done', 'pending'} — 주가 바뀌면 새로."""
    key = key or week_key()
    if not st.get('raid') or st['raid'].get('week') != key:
        st['raid'] = {'week': key, 'won': False, 'done': False, 'pending': False}
    return st['raid']


def raid_release(st):
    """이긴 레이드 보스를 포획 기회로 — 다른 야생과 만나는 중이면 그게 끝날 때까지 기다린다."""
    r = st.get('raid')
    if r and r.get('pending') and not st['wild'] and r.get('week') == week_key():
        boss = raid_boss(st, r['week'])[1]
        st['wild'] = {'id': boss, 'balls': RAID_BALLS, 'raid': True,
                      **({'shiny': True} if random.random() < shiny_rate(st, boss, EGG_SHINY) else {})}
        _mark(st, 'seen', boss)
        r['pending'] = False


def week_key(now=None):
    """'2026-W43' — 월요일에 바뀐다."""
    y, w, _ = (now or datetime.now().astimezone()).isocalendar()
    return f'{y}-W{w:02d}'


def weekly(st, key=None):
    """이번 주 과제 {'key','kind','n','done'} — 주가 바뀌었으면 새로 고른다(주 번호로 정해져 두 PC 가 같은 과제)."""
    key = key or week_key()
    w = st.get('weekly')
    if not w or w.get('key') != key:
        w = st['weekly'] = {'key': key, 'kind': WEEKLY[zlib.crc32(key.encode()) % len(WEEKLY)][0], 'n': 0, 'done': False}
    if w['kind'] == 'ship':  # 보상받은 날 목록에서 이번 주 날짜를 센다 — 과제가 생기기 전 이번 주 날도 들어간다
        w['n'] = sum(1 for d in st.get('rewarded', []) if week_key(datetime.strptime(d, '%Y-%m-%d')) == key)
    return w


def bump(st, kind, k=1, key=None):
    """kind 일이 일어났다 — 이번 주 과제가 그 종류면 세고, 목표를 채우면 상을 준다."""
    w = weekly(st, key)
    if w['kind'] != kind or w['done']:
        return
    if kind != 'ship':  # ship 은 weekly() 가 다시 센다
        w['n'] += k
    if w['n'] >= next(g for kd, g, _, _ in WEEKLY if kd == kind):
        w['done'] = True
        for b, c in WEEKLY_PRIZE:
            st[b] += c
        tell(st, 'weekly')


def weekly_text(st):
    w = weekly(st)
    _, goal, ko, en = next(x for x in WEEKLY if x[0] == w['kind'])
    prize = ' · '.join(L(*ball_name(b, c)) for b, c in WEEKLY_PRIZE)
    if w['done']:
        return L(f'주간 과제 완료 ✔ — {ko.format(n=goal)} (상: {prize})', f'Weekly done ✔ — {en.format(n=goal)} (prize: {prize})')
    return L(f'주간 과제: {ko.format(n=goal)} {min(w["n"], goal)}/{goal} — 상: {prize}', f'Weekly: {en.format(n=goal)} {min(w["n"], goal)}/{goal} — prize: {prize}')


def dex_hint(st, n):
    """못 잡은 포켓몬을 얻는 길 — 잡았으면 ''."""
    if n in st['caught']:
        return ''
    if DEX[n][5]:
        return L('전설 — 하이퍼볼·마스터볼' if DEX[n][5] == 1 else '환상 — 하이퍼볼·마스터볼',
                 'legendary — Ultra/Master' if DEX[n][5] == 1 else 'mythical — Ultra/Master')
    if not wild_ok(n):
        pre = DEX[n][3]
        pn = name(pre) if pre in st['seen'] else '???'
        return L(f'진화 — {pn}에서', f'evolve from {pn}')
    if evo_wild(n):
        pre = DEX[n][3]
        pn = name(pre) if pre in st['seen'] else '???'
        return L(f'진화 — {pn}에서 · 야생은 드묾', f'evolve from {pn} · rare in the wild')
    return L('야생', 'wild')


def dex_summary(st, g):
    """'야생에서 남은 것 N · 진화로만 M · 전설·환상 K · 지금 풀숲: A·B·???' — 그 세대가 지금 세대일 때만 풀숲 후보."""
    left = [n for n in DEX if gen(n) == g and n not in st['caught']]
    leg = sum(1 for n in left if DEX[n][5])
    evo = sum(1 for n in left if not DEX[n][5] and not wild_ok(n))
    wild = len(left) - leg - evo
    out = L(f'야생에서 남은 것 {wild} · 진화로만 {evo} · 전설·환상 {leg}', f'Wild left {wild} · evolve-only {evo} · legendary {leg}')
    if wild_pool(st) and gen(wild_pool(st)[0]) == g:
        now = [n for n, w in wild_odds(st) if w == 1]
        if now:
            out += L(' · 지금 풀숲: ', ' · in the grass now: ') + '·'.join(name(n) if n in st['seen'] else '???' for n in now)
    return out


def use_candy(st, t, rng=random):
    """이상한사탕 — 동료가 진화할 수 있는 모습이 있으면 경험치와 상관없이 바로 진화. 진화한 번호 · 못 쓰면 None."""
    if st.get('candy', 0) <= 0 or st['partner'] is None:
        return None
    m = st['box'][st['partner']]
    if not evolutions(st, m['id'], m.get('shiny')):
        return None
    st['candy'] -= 1
    return _evolve(st, t, rng)


def evolve(st, t, rng=random):
    if not can_evolve(st, t):
        return None
    return _evolve(st, t, rng)


def _evolve(st, t, rng):
    mon = st['box'][st['partner']]
    research_bump(st, mon['id'], 'e')
    mon['id'], mon['xp'] = rng.choice(evolutions(st, mon['id'], mon.get('shiny'))), 0  # 이로치는 이로치로 진화
    st['base'] = t
    st['evolved'] = st.get('evolved', 0) + 1
    bump(st, 'evolve')
    if mon['id'] in FORMS:  # 리전폼으로 진화 — 리전폼 목록에
        _mark(st, 'forms_seen', mon['id'])
        _mark(st, 'forms', mon['id'])
        return mon['id']
    _mark(st, 'seen', mon['id'])
    _mark(st, 'caught', mon['id'])
    if mon.get('shiny'):
        _mark(st, 'shiny', mon['id'])
    return mon['id']


def fmt_tok(n):
    return f'{n / 1e6:.2f}M' if n >= 1e6 else f'{n / 1e3:.0f}k' if n >= 1e3 else str(n)


def dex_text(st):
    g, caught = (opened_gen(st) if current_gen(st) else None), set(st['caught'])
    if g is None:
        return L(f'도감 완성! {len(caught)}/{len(DEX)}', f'Pokédex complete! {len(caught)}/{len(DEX)}')
    have = sum(1 for n in caught if gen(n) == g)
    return L(f'도감 {g}세대 {have}/{GEN_SIZE[g]} · 전체 {len(caught)}/{len(DEX)}',
             f'Dex Gen {g} {have}/{GEN_SIZE[g]} · total {len(caught)}/{len(DEX)}')


def evo_status(st, t):
    """동료의 진화 상태: ('final',) · ('locked',) · ('blocked', 진화형들) · ('ready',) · ('progress', 경험치, 필요치)."""
    m = st['box'][st['partner']]
    n = m['id']
    if not evo_next(n):
        return ('final',)
    opened = opened_evolutions(st, n)
    if not opened:
        return ('locked',)
    if not evolutions(st, n, m.get('shiny')):
        return ('blocked', opened)  # 진화형이 이미 가방에 있다
    xp, need = partner_xp(st, t), need_xp(n)
    return ('ready',) if xp >= need else ('progress', xp, need)


def move_focus(btns, focus, key):
    """방향키로 버튼 고르기 — ←→ 는 앞뒤 버튼(끝에서 돌아온다), ↑↓ 는 위·아래 줄에서 가로 위치가 가장 가까운 버튼.
    btns: [(y, x, 끝, act, 글)] 그린 순서. 위·아래에 버튼 줄이 없으면 그대로."""
    if not btns:
        return focus
    acts = [b[3] for b in btns]
    i = acts.index(focus) if focus in acts else 0
    if key in (curses.KEY_LEFT, curses.KEY_RIGHT):
        return acts[(i + (1 if key == curses.KEY_RIGHT else -1)) % len(acts)]
    y, x = btns[i][0], btns[i][1]
    rows = [b for b in btns if (b[0] > y if key == curses.KEY_DOWN else b[0] < y)]
    if not rows:
        return acts[i]
    ny = min(rows, key=lambda b: abs(b[0] - y))[0]
    return min((b for b in rows if b[0] == ny), key=lambda b: abs(b[1] - x))[3]


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
    return art_of(st['box'][st['partner']])


def art_of(m):
    """가방 항목(또는 번호) → 그림 번호: 이로치면 이로치 그림, 리전폼·합체 모습이면 'form:번호'(번호가 이로치 자리와 겹쳐서)."""
    n, shiny = (m['id'], m.get('shiny')) if isinstance(m, dict) else (m, False)
    return f'form:{n}' if n in FORMS or n in FUSIONS or n in SPECIALS else n + (_pokedata.SHINY if shiny else 0)


# ── 화면 ──
INFO = {}  # 도감 상세(_pokedata.DETAIL) — 상세 화면을 처음 열 때 읽는다
KITTY = SIXEL = False  # 진짜 그림을 놓을 수 있나 — __main__ 이 curses 를 켜기 전에 _gfx 로 정한다


def battle_info(st, n):
    """도감 상세의 배틀 정보 줄들 — 종족값(합계)과 가방에서의 레벨, 약점(×4 는 따로), 반감·무효. 데이터가 없으면 [].
    배틀 데이터는 체육관을 처음 열 때 받는다 — 아직 안 받았으면 여기서는 받지 않고 안내만."""
    d = _battle.load() if not BATTLE_DATA else BATTLE_DATA[0]
    if d and not BATTLE_DATA:
        BATTLE_DATA.append(d)
    if not d:
        return [L('배틀 정보는 체육관(g)을 한 번 열면 보인다.', 'Open the gyms (g) once to see battle stats.')]
    if (n in FORMS or n in SPECIALS) and n not in d['stats']:  # 리전폼 자료를 넣기 전에 받은 파일 — 한 번 다시 받는다
        try:
            d = BATTLE_DATA[0] = _battle.ensure()
        except Exception:  # 네트워크 오류 — 배틀 정보 없이
            return []
    if n not in d['stats'] or n not in d['types']:
        return []
    bs = d['stats'][n]
    lvs = [box_level(m) for m in st['box'] if m['id'] == n]
    head = L('종족값 ', 'Stats ') + ' '.join(f'{k}{v}' for k, v in zip(L('H 공 방 특공 특방 S', 'H A B C D S').split(), bs)) + \
        f' ({sum(bs)})' + (L(f' · 가방 Lv{max(lvs)}', f' · bag Lv{max(lvs)}') if lvs else '')
    tn = lambda t: L(*d['tnames'].get(t, ['?', '?']))  # noqa: E731
    f = {t: _battle.factor(d, t, d['types'][n]) for t in range(1, 19)}
    weak = [tn(t) + ('(×4)' if f[t] >= 4 else '') for t in sorted(f, key=lambda t: -f[t]) if f[t] > 1]
    resist = [tn(t) for t in f if 0 < f[t] < 1]
    immune = [tn(t) for t in f if f[t] == 0]
    return [head, L('약점 ', 'Weak ') + ('·'.join(weak) or L('없음', 'none')),
            L('반감 ', 'Resist ') + ('·'.join(resist) or L('없음', 'none')) + (L(' · 무효 ', ' · Immune ') + '·'.join(immune) if immune else '')]


BATTLE_DATA = []  # battle.json 을 한 번만 읽어 둔다


def draw_info(scr, st, n, h, w, gold):
    """도감 상세: 이름 · 분류 · 타입, 잡았으면 키 · 몸무게 · 설명, 아래에 그림(이로치를 잡았으면 이로치 그림).
    그림은 Sixel·Kitty 가 되면 원본 도트로 — 놓을 그림 (방식, y, x, 키, 데이터, 칸, 줄)을 돌려주고, 화면을 그린 뒤 놓는다."""
    if not INFO or (n in FORMS or n in SPECIALS) and str(n) not in INFO:  # 리전폼 자료가 없는 옛 파일이면 ensure_detail 이 다시 받는다
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
    form, spec = FORMS.get(n), SPECIALS.get(n)  # 리전폼·특수 모습 — 타입·키·몸무게·종족값은 그 모습 것, 도감 설명은 없다
    d, sh = INFO.get(str(n)), n in st['shiny']
    caught = n in (st['forms'] if form else st.get('specials', []) if spec else st['caught'])
    x = put(scr, 1, 1, f'No.{sp(n):04d}  ', curses.A_BOLD)
    x = put(scr, 1, x, ('✨' if sh else '') + name(n), gold if sh else curses.A_BOLD)
    put(scr, 1, x + 2, (L('리전폼', 'Regional form') if form else L('특수 모습', 'Special form') if spec else L(f'{gen(n)}세대', f'Gen {gen(n)}'))
        + ((L(' · 만듦', ' · made') if spec else L(' · 잡음', ' · caught')) if caught else L(' · 봄', ' · seen')), curses.A_DIM)
    y = 3
    if (form or spec) and not d:
        put(scr, 2, 1, form_note(n), curses.A_DIM)
    if d:
        put(scr, 2, 1, L(f'{d[0]} · ' if d[0] else '', f'{d[1]} · ' if d[1] else '') + L(f'{"/".join(d[2])} 타입', f'{"/".join(d[3])} type'))
        if caught:
            put(scr, 3, 1, L(f'키 {d[4] / 10:g}m · 몸무게 {d[5] / 10:g}kg', f'Height {d[4] / 10:g} m · Weight {d[5] / 10:g} kg'))
            fy = 5
            for i, line in enumerate(battle_info(st, n)):  # 종족값 · 약점 · 반감/무효 — 팀을 꾸릴 때 보라고
                put(scr, 4 + i, 1, line, curses.A_DIM if i else 0)
                fy = 6 + i
            text = L(d[6], d[7]) or (form_note(n) + '.' if form or spec else '')
            for i, (_, a, b) in enumerate(memo.wrap([text], w - 3)[:max(1, h - 9 - fy)]):
                put(scr, fy + i, 1, text[a:b].strip())
                y = fy + 1 + i
        else:
            put(scr, 3, 1, L('잡으면 키·몸무게·도감 설명을 볼 수 있다.', 'Catch it to see its size and Pokédex entry.'), curses.A_DIM)
    room, sid, gray = h - 3 - (y + 1), f'form:{n}' if form else n + (_pokedata.SHINY if sh else 0), False
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
        return ('kitty', y + 1, max(1, (w - cols) // 2), (300000 + n if form else sid) * 2 + gray, png[0], cols, room)
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
             'conquer8': 'rusted-sword', 'conquer9': 'scarlet-book', 'champ1': 'relic-copper', 'champ2': 'relic-silver',
             'champ3': 'relic-gold', 'champ4': 'relic-vase', 'champ5': 'relic-band', 'champ6': 'relic-statue',
             'champ7': 'pearl-string', 'champ8': 'big-pearl', 'champ9': 'relic-crown',
             'form1': 'galarica-twig', 'form_all': 'galarica-wreath', 'fuse1': 'dna-splicers',
             'research1': 'scope-lens', 'research10': 'poke-radar', 'research50': 'old-amber', 'alpha1': 'kings-rock',
             'raid1': 'wishing-piece', 'mega1': 'mega-ring', 'gmax1': 'dynamax-band'}


def art_id(key):
    """훈장 번호 또는 체육관 배지('gym:세대-관') → 그림 번호(_pokedata). 리전폼 그림('form:번호')은 그대로."""
    if key.startswith('form:'):
        return key
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
    if b.startswith('research'):
        return len(st.get('researched', [])), int(b[8:])
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


GYM_COST, LEAGUE_COST = 2, 4  # 체육관 · 사천왕 도전 1회에 쓰는 탐색 기회
GYM_WIN_XP, GYM_LOSE_XP = 60, 30  # 팀원마다 받는 배틀 경험치(이기면 + 체육관 순서 × 10)


def box_level(m):
    return _battle.level(depth(m['id']), m.get('bxp', 0))


def xp_text(m):
    """배틀 경험치 진행도 — '(10/50)', 상한이면 '(최대)'."""
    bxp = m.get('bxp', 0)
    if bxp // _battle.XP_PER_LEVEL >= _battle.XP_LEVEL_CAP:
        return L('(최대)', '(max)')
    return f'({bxp % _battle.XP_PER_LEVEL}/{_battle.XP_PER_LEVEL})'


def team_of(st, g=None):
    """팀 [(가방 번호, 종, 레벨)] — 가방 순서가 아니라 넣은 순서. g 를 주면 그 세대 포켓몬만(체육관·사천왕 출전)."""
    return [(i, st['box'][i]['id'], box_level(st['box'][i])) for i in st.get('team', [])
            if i < len(st['box']) and (g is None or gen(st['box'][i]['id']) == g)]


SORTS = [('도감번호', 'No.'), ('레벨', 'level'), ('개체값', 'IV'), ('이름', 'name')]  # 가방 정렬(Tab) — 0 이 기본


def bag_order(st, g=None, sort=0):
    """가방 번호들을 보이는 순서로 — g 세대만(None 이면 전체), SORTS[sort] 기준(레벨·개체값은 높은 것부터,
    이름은 지금 언어로 — 한글은 유니코드 순서가 곧 ㄱㄴㄷ 순). 같으면 도감번호, 그다음 잡은 순서."""
    box = st['box']
    by = [lambda m: 0, lambda m: -box_level(m), lambda m: -sum(iv_of(m)), lambda m: name(m['id']).lower()][sort]
    return sorted((i for i, m in enumerate(box) if g is None or gen(m['id']) == g), key=lambda i: (by(box[i]), box[i]['id'], i))


def fighters(st, team):
    """team_of 결과 → 배틀에 넣을 [(종, 레벨, 개체값)]."""
    return [(n, lv, iv_of(st['box'][k])) for k, n, lv in team]


def _drop(st, gone):
    """가방에서 gone(번호 집합)을 빼고 동료·팀 번호를 당겨 맞춘다. 옛 번호 → 새 번호 표."""
    where = {}
    for i in range(len(st['box'])):
        if i not in gone:
            where[i] = len(where)
    st['box'] = [m for i, m in enumerate(st['box']) if i not in gone]
    if st['partner'] is not None:
        st['partner'] = where[st['partner']]
    st['team'] = [where[i] for i in st.get('team', []) if i in where]
    return where


def change_options(st, i):
    """가방 i 번째가 바뀔 수 있는 모습들 [(모습, 재료, 할 수 있나, 못 하는 까닭)] — 재료는 ('mon', 가방 번호)(합체 상대) 또는
    ('item', 키). 모두 되돌릴 수 없다: 합체 상대·아이템은 사라지고, 레벨·경험치·개체값은 그대로 이어진다."""
    m, out = st['box'][i], []
    for f, j in fuse_options(st, i):
        out.append((f, ('mon', j), True, ''))
    for p, (s, kind, g, *_) in SPECIALS.items():
        if (m['id'] not in ULTRA_BASE) if kind == 'ultra' else m['id'] != s:
            continue
        key = 'soup' if kind == 'gmax' else f'stone:{p}'
        why = L(f'{g}세대가 열리면', f'opens with Gen {g}') if opened_gen(st) < g else \
            '' if st.get('items', {}).get(key, 0) > 0 else L('재료 없음', 'no material')
        out.append((p, ('item', key), not why, why))
    return out


def change(st, i, k):
    """change_options 의 k 번째로 바꾼다 — 바뀐 모습 번호 · 못 하면 None. 가방 번호가 당겨질 수 있다(합체 상대가 빠지면)."""
    opts = change_options(st, i)
    if not 0 <= k < len(opts) or not opts[k][2]:
        return None
    f, (what, ref), _, _ = opts[k]
    if what == 'mon':
        i = _drop(st, {ref})[i]  # 합체 상대는 사라진다(2026-10-30 — 분리 없음, 다른 모습은 재료를 다시 모아서)
        st['fusions'] = st.get('fusions', 0) + 1
    else:
        st['items'][ref] -= 1
        _mark(st, 'specials', f)
    st['box'][i]['id'] = f
    return f


def fuse_options(st, i):
    """가방 i 번째(큐레무·네크로즈마·버드렉스, 합체 전)와 합칠 수 있는 것 [(합체 모습, 상대 가방 번호)] — 상대 종마다
    개체값이 가장 좋은 하나, 동료·합체한 것은 빼고. 아직 가방에 없는 합체 모습이 앞."""
    m = st['box'][i]
    out = []
    for f, (base, part, _, _) in FUSIONS.items():
        if m['id'] != base or m.get('fused'):
            continue
        cands = [j for j, o in enumerate(st['box']) if o['id'] == part and j not in (i, st['partner']) and not o.get('fused')]
        if cands:
            out.append((f, max(cands, key=lambda j: sum(iv_of(st['box'][j])))))
    have = {o['id'] for o in st['box']}
    return sorted(out, key=lambda o: o[0] in have)


def send_away(st, idxs):
    """가방의 idxs 번째들을 박사에게 — 동료·팀·이로치는 빼고. 하나마다 dupe_balls 만큼 몬스터볼.
    가방 번호가 당겨지니 동료·팀 번호도 맞춰 옮긴다. (보낸 마릿수, 받은 볼)."""
    keep = {st['partner']} | set(st.get('team', []))
    gone = {i for i in idxs if 0 <= i < len(st['box']) and i not in keep and not st['box'][i].get('shiny')
            and not st['box'][i].get('fused')}  # 합체한 포켓몬은 안에 든 상대까지 사라지니 보내지 않는다
    if not gone:
        return 0, 0
    k = sum(dupe_balls(st['box'][i]['id']) for i in gone)
    _drop(st, gone)
    st['balls'] += k
    st['sent'] = st.get('sent', 0) + len(gone)
    return len(gone), k


def tidy_targets(st):
    """[정리]로 보낼 가방 번호 — 같은 종(이로치 빼고)이 둘 이상이면 개체값이 가장 좋은 것, 배틀 경험치가 가장 많은 것,
    진화 경험치가 가장 많은 것만 남긴다(동료·팀은 send_away 가 지킨다)."""
    groups = {}
    for i, m in enumerate(st['box']):
        if not m.get('shiny'):
            groups.setdefault(m['id'], []).append(i)
    out = []
    for ids in groups.values():
        if len(ids) < 2:
            continue
        box = st['box']
        keep = {max(ids, key=lambda i: (sum(iv_of(box[i])), box[i].get('bxp', 0))),
                max(ids, key=lambda i: (box[i].get('bxp', 0), sum(iv_of(box[i])))),
                max(ids, key=lambda i: (box[i].get('xp', 0), sum(iv_of(box[i]))))}
        out += [i for i in ids if i not in keep]
    keep = {st['partner']} | set(st.get('team', []))
    return [i for i in out if i not in keep]


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


def gym_opp(d, g, i, st=None):
    """체육관 상대 — 전설·환상은 나오지 않는다. i 가 'L' 이면 사천왕·챔피언 팀들 [[(종, 레벨)] × 5],
    'R' 이면 이번 주 레이드 보스 하나 [(종, 8관 레벨 + 2, 개체값 15, HP ×RAID_HP)]."""
    if i == 'R':
        return [(raid_boss(st)[1], 12 + 7 * 7 + (g - 1) * 5 + _battle.OPP_LV_BONUS + 2, (15,) * 3, RAID_HP)]
    gen_of, final = {n: gen(n) for n in DEX if not DEX[n][5]}, {n for n in DEX if n not in CHILDREN}
    return _battle.league_teams(d, g, gen_of, final) if i == 'L' else _battle.gym_team(d, g, i, gen_of, final)


def gym_rate(d, team, g, i, st=None):
    """그 체육관(또는 사천왕 연전) 승률."""
    opp = gym_opp(d, g, i, st)
    return _battle.league_rate(d, team, opp) if i == 'L' else _battle.win_rate(d, team, opp)


def gym_rows(st):
    """체육관 목록 [(세대, 관 또는 'L' · 'R')] — 맨 위는 이번 주 레이드(잡거나 놓치면 다음 주까지 빠진다),
    한 세대 8관을 모두 이기면 그 아래 사천왕·챔피언이 열린다."""
    raid = raid_boss(st)
    return ([(raid[0], 'R')] if raid and not raid_state(st)['done'] else []) + \
        [(g, i) for g in gym_gens(st) for i in list(range(8)) + (['L'] if f'conquer{g}' in st['badges'] else [])]


def gym_gens(st):
    """도전할 수 있는 세대 — 도감이 열린 세대까지."""
    return range(1, opened_gen(st) + 1)


def fight(st, t, d, g, i, rng=random, today=None):
    """체육관 도전 — 탐색 GYM_COST 회를 쓰고 자동 배틀. 팀원 모두 배틀 경험치를 받고, 처음 이기면 그 관의 배지
    와 하이퍼볼 1개(마스터볼은 한 세대 8관을 모두 이겼을 때 지방 정복 훈장과 함께 — check_badges).
    (이겼나, 기록, 처음 이겼나) · 도전할 수 없으면 (None, 이유, False). 결과는 기록을 보여 주기 전에 바로 적용한다."""
    team, cost = team_of(st, None if i == 'R' else g), LEAGUE_COST if i == 'L' else RAID_COST if i == 'R' else GYM_COST  # 레이드는 모든 세대
    if i == 'R' and raid_state(st)['won']:
        return None, L('이번 주 레이드는 이미 이겼다 — 메인 화면에서 레이드볼로 잡자.', 'You already beat this raid — catch it with Raid Balls on the main screen.'), False
    if not team:
        return None, L(f'팀에 {g}세대 포켓몬이 없다 — {g}세대 포켓몬만 나갈 수 있다. 가방에서 [팀]으로 넣거나 [추천] → [적용]을 하자.',
                       f'No Gen {g} Pokémon on the team — only Gen {g} may enter. Add with [team] in the bag, or [pick] → [apply].'), False
    if tickets(st, t) < cost:
        return None, L(f'탐색 기회가 {cost}번 있어야 도전할 수 있다.', f'You need {cost} explores to challenge.'), False
    st['used'] += cost
    mine = fighters(st, team)
    won, ev = (_battle.gauntlet(d, mine, gym_opp(d, g, i, st), rng) if i == 'L' else _battle.battle(d, mine, gym_opp(d, g, i, st), rng))
    for k, n, _ in team:
        st['box'][k]['bxp'] = st['box'][k].get('bxp', 0) + (GYM_WIN_XP + 10 * (8 if i in ('L', 'R') else i) if won else GYM_LOSE_XP)
        if won:
            research_bump(st, sp(n), 'w')
    day, first = today or datetime.now().astimezone().strftime('%Y-%m-%d'), False
    if won:
        bump(st, 'gym')
    if won and i == 'R':  # 레이드 — 레이드볼 RAID_BALLS 개로 잡을 기회(다른 야생과 만나는 중이면 그게 끝난 뒤)
        r = raid_state(st)
        r['won'], r['pending'] = True, True
        give_item(st, 'soup')  # 거다이맥스 재료 — 쓰는 건 8세대가 열린 뒤
        raid_release(st)
        tell(st, 'raid', str(raid_boss(st)[1]))
    elif won and i == 'L' and str(g) not in st.setdefault('league', {}):
        st['league'][str(g)] = day  # 챔피언 훈장(마스터볼)은 check_badges 가
        tell(st, 'league', str(g))
        if g < GENS and not gen_done(st, g):
            tell(st, 'opengen', str(g + 1))
        first = True
    elif won and i != 'L' and f'gym:{g}-{i}' not in st.setdefault('gym', {}):
        st['gym'][f'gym:{g}-{i}'] = day
        st['hyper'] += 1  # 관을 처음 이길 때마다 하이퍼볼 — 세대당 8개(2026-10-21 다시 넣음, 포획률을 70%로 낮추며)
        tell(st, 'gym', f'gym:{g}-{i}')
        first = True
    return won, ev, first


def fold(text, width):
    """text 를 width 칸에 맞춰 빈칸에서 접은 줄들('·' 는 앞 낱말에 붙여) — 폭보다 긴 낱말은 그 줄에서 잘린다."""
    out, line = [], ''
    for word in text.replace(' · ', '\xa0· ').split(' '):
        if line and sum(map(memo.cw, line + ' ' + word)) > width:
            out, line = out + [line], word
        else:
            line = f'{line} {word}' if line else word
    return [x.replace('\xa0', ' ') for x in out + ([line] if line else [])]


def para(scr, y, text, w, attr=0, x=1):
    """text 를 패널 폭에 맞춰 접어 y 줄부터 쓴다 — 다음 빈 줄 번호를 돌려준다(좁은 패널에서 잘리지 않게)."""
    for line in fold(text, max(10, w - x - 1)):
        put(scr, y, x, line, attr)
        y += 1
    return y


def fight_line(ev):
    """배틀 기록 한 칸 → 화면 한 줄."""
    if ev[0] == 'trainer':
        return L(f'— 챔피언 등장! —', '— The Champion appears! —') if ev[1] == _battle.ELITE_COUNT else \
            L(f'— 사천왕 {ev[1] + 1} 등장! —', f'— Elite Four #{ev[1] + 1} appears! —')
    if ev[0] == 'send':
        return L(f'가라, {name(ev[2])}!', f'Go, {name(ev[2])}!') if ev[1] == 'me' else \
            L(f'상대가 {name(ev[2])}(을)를 내보냈다!', f'The foe sent out {name(ev[2])}!')
    if ev[0] == 'faint':
        return L(f'{name(ev[2])}(은)는 쓰러졌다!', f'{name(ev[2])} fainted!')
    _, side, a, b, dmg, f, hp, top = ev
    eff = L('효과가 굉장했다! ', "It's super effective! ") if f > 1 else L('효과가 별로인 듯하다… ', "It's not very effective… ") \
        if 0 < f < 1 else L('효과가 없는 것 같다… ', 'It had no effect… ') if f == 0 else ''
    who = '' if side == 'me' else L('상대 ', 'Foe ')
    return L(f'{who}{name(a)}의 공격! {eff}({name(b)} {hp}/{top})', f"{who}{name(a)} attacks! {eff}({name(b)} {hp}/{top})")


def fight_state(ev, k):
    """기록 k 칸까지 본 지금 — {'me': [종, HP, 최대, 레벨], 'foe': [...]}."""
    now = {}
    for e in ev[:k]:
        if e[0] == 'trainer':
            now.clear()
        elif e[0] == 'send':
            now[e[1]] = [e[2], None, e[4] if len(e) > 4 else None, e[3]]  # 최대 HP(개체값 반영)는 내보낼 때 실려 온다
        elif e[0] == 'hit':
            side = 'foe' if e[1] == 'me' else 'me'
            if side in now:
                now[side][1:3] = [e[6], e[7]]
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
    gsel, rec, battle_now, wr_cache, confirm = None, None, None, {}, None
    chg = None  # 변신 화면이 다루는 가방 번호
    order, bag_g, bag_sort, to_partner = [], None, _lang.get('bag_sort', 0) % len(SORTS), False  # 가방: 보이는 순서(가방 번호들) · 세대(None 전체) · 정렬 · 동료 줄로  # confirm: 한 번 더 누르면 보낼 것  # 고른 체육관 · 추천 (체육관, 팀, 승률) · 배틀 재생 · 승률 캐시
    focus = None  # 고른 버튼(act) — 방향키로 옮기고 Enter 로 누른다. 단축키는 q(닫기)만 남겼다(2026-10-21)
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
    if not FORMS:  # 리전폼 목록 — 못 받으면 리전폼 없이 돈다(다음에 열 때 다시)
        try:
            _pokedata.ensure_forms()
            load_forms()
        except Exception:
            pass
    if not SPECIALS:  # 특수 모습 목록 — 같은 방식
        try:
            _pokedata.ensure_specials()
            load_specials()
        except Exception:
            pass
    while True:
        st, t = load(), total_tokens()
        fresh = not st.get('reward_since') or st.get('super_earned') is None
        got, born = reward(st), hatch(st, t)
        raid_release(st)
        badges = check_badges(st)
        if got or born or badges or fresh:
            save(st)
        if born:
            msg = L('알이 부화했다! ', 'Eggs hatched! ') + ', '.join(('✨' if sh else '') + name(n) for n, sh in born)
        if got:
            msg = L(f'오늘 여러 세션이 일을 내보냈다! 슈퍼볼 {got}개를 받았다.', f'Sessions shipped work! Got {got} Great Ball(s).')
        if badges:  # 방금 한 일의 문구(합체 등)는 남기고 뒤에 붙인다
            msg = (msg + ' · ' if msg else '') + L('훈장을 받았다: ', 'New medal: ') + ', '.join(badge_name(b) for b in badges)
        h, w = scr.getmaxyx()
        tight = w < 80  # 버튼 여백을 줄일 폭
        art = None
        if view == 'fight' and battle_now['k'] < len(battle_now['ev']):
            battle_now['k'] += 1
        scr.erase()
        title = L(f' 포켓몬 · 누적 {fmt_tok(t)} 토큰 · ', f' Pokémon · {fmt_tok(t)} tokens total · ') + dex_text(st)
        if sum(map(memo.cw, title)) > w:  # 좁으면 앞의 이름·낱말을 떼고 숫자만
            title = f' {fmt_tok(t)} · ' + dex_text(st)
        put(scr, 0, 0, title + ' ' * w, curses.A_REVERSE)
        btns, navbtns = [], []  # navbtns: 방향키로 고르는 버튼들 (y, x, 끝, act, 글) — 목록 줄은 btns 에만(마우스용)

        def button(y, x, label, act):
            if w < 50:  # 아주 좁으면 '돌아가기 q' 의 q 꼬리도 뗀다(q 키는 그대로)
                label = label.removesuffix(' q')
            text = f'[{label}]' if tight else f'[ {label} ]'  # 좁은 패널이면 여백을 줄여 한 줄에 들어가게
            end = put(scr, y, x, text, curses.A_BOLD)
            btns.append((y, x, end, act))
            navbtns.append((y, x, end, act, text))
            return end + (1 if tight else 2)

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
                put(scr, y, x, L(f'  (No.{sp(n):04d}, {gen(n)}세대 · {depth(n) + 1}단계)',
                                 f'  (No.{sp(n):04d}, Gen {gen(n)} · stage {depth(n) + 1})'), curses.A_BOLD)
                ev = evo_status(st, t)
                if ev[0] == 'final':
                    put(scr, y + 1, 1, L('더 진화하지 않는 포켓몬입니다.', 'This Pokémon does not evolve any further.'), curses.A_DIM)
                elif ev[0] == 'locked':
                    put(scr, y + 1, 1, L('진화형은 다음 세대가 열리면(사천왕 클리어 또는 도감 완성) 만날 수 있다.',
                                          'Its evolution unlocks with the next generation (beat the Elite Four or finish the dex).'), curses.A_DIM)
                elif ev[0] == 'blocked':
                    put(scr, y + 1, 1, blocked_text(ev[1]), curses.A_DIM)
                elif ev[0] == 'ready':
                    x = put(scr, y + 1, 1, L('✨ 진화할 수 있다!', '✨ It can evolve!'), curses.A_BOLD)
                    button(y + 1, x + 3, L('진화', 'evolve'), 'evolve')
                else:
                    x = put(scr, y + 1, 1, L('진화 ', 'Evolve '))
                    x = put(scr, y + 1, x, f'{bar(ev[1] / ev[2], max(6, min(24, w - 40)))} {fmt_tok(ev[1])}/{fmt_tok(ev[2])}')
                    if st.get('candy'):
                        button(y + 1, x + 3, L(f'이상한사탕 ({st["candy"]})', f'Rare Candy ({st["candy"]})'), 'candy')
            y = y0 + 2
            if st.get('eggs'):
                e = min(st['eggs'], key=lambda e: e['need'] - (t - e['base']))
                x = put(scr, y, 1, '🥚 ' + egg_text(st, t) + ' ')
                put(scr, y, x, bar((t - e['base']) / e['need'], 12), curses.A_DIM)
                y += 1
            y = para(scr, y, weekly_text(st), w, curses.A_DIM if weekly(st)['done'] else 0)
            if st['wild']:
                sh, wd = st['wild'].get('shiny'), st['wild']
                x = put(scr, y, 1, L('레이드 보스 ', 'Raid boss ') if wd.get('raid') else
                        L('앗! 붉은 눈의 우두머리 ', 'Oh! An alpha ') if wd.get('alpha') else L('앗! 야생의 ', 'Oh! A wild '), curses.A_BOLD)
                x = put(scr, y, x, (L('✨이로치 ', '✨shiny ') if sh else '') + name(st['wild'].get('form') or st['wild']['id']),
                        gold if sh else curses.A_BOLD)
                put(scr, y, x, L('(이)가 나타났다!', ' appeared!') + (L(f' (볼 {ALPHA_TRIES - wd.get("tries", 0)}번 안에 못 잡으면 도망)',
                                                                            f' (flees after {ALPHA_TRIES - wd.get("tries", 0)} more throws)')
                                                                          if wd.get('alpha') else ''), curses.A_BOLD)
                if wd.get('raid'):  # 레이드볼만 — 보유 볼은 못 쓴다
                    x = button(y + 1, 1, L(f'레이드볼 ({wd["balls"]})', f'Raid Ball ({wd["balls"]})'), 'throw')
                    button(y + 1, x, L('놓아주기', 'let go'), 'run')
                else:
                    left = wd['balls'] or st['balls']
                    own = '' if wd['balls'] else L(' 보유', ' owned')
                    x = button(y + 1, 1, L(f'몬스터볼 ({left}{own})', f'Poké Ball ({left}{own})'), 'throw')
                    if st['super']:
                        x = button(y + 1, x, L(f'슈퍼볼 ({st["super"]})', f'Great ({st["super"]})'), 'super')
                    if st['hyper']:
                        x = button(y + 1, x, L(f'하이퍼볼 ({st["hyper"]})', f'Ultra ({st["hyper"]})'), 'hyper')
                    if st['master']:
                        x = button(y + 1, x, L(f'마스터볼 ({st["master"]})', f'Master ({st["master"]})'), 'master')
                    button(y + 1, x, L('도망', 'run'), 'run')
                y += 2
            else:
                k = tickets(st, t)
                if k > 0:
                    y = para(scr, y, L(f'탐색 {k}회 가능 · 몬스터볼 {st["balls"]} · 슈퍼볼 {st["super"]} · 하이퍼볼 {st["hyper"]}',
                                       f'{k} explore{"" if k == 1 else "s"} ready · Poké {st["balls"]} · Great {st["super"]} · Ultra {st["hyper"]}')
                             + (L(f' · 마스터볼 {st["master"]}', f' · Master {st["master"]}') if st['master'] else '')
                             + (L(f' · 이상한사탕 {st["candy"]}', f' · Rare Candy {st["candy"]}') if st.get('candy') else ''), w)
                    button(y, 1, L('풀숲 탐색', 'explore grass'), 'explore')
                    y += 1
                else:
                    left = ENCOUNTER_EVERY - t % ENCOUNTER_EVERY
                    x = put(scr, y, 1, L('다음 탐색 ', 'Next explore '))
                    put(scr, y, x, f'{bar(1 - left / ENCOUNTER_EVERY, min(24, max(6, w - x - 12)))} {fmt_tok(left)}' + L(' 남음', ' left'))
                    y = para(scr, y + 1, L(f'몬스터볼 {st["balls"]} · 슈퍼볼 {st["super"]} · 하이퍼볼 {st["hyper"]}',
                                           f'Poké {st["balls"]} · Great {st["super"]} · Ultra {st["hyper"]}')
                             + (L(f' · 마스터볼 {st["master"]}', f' · Master {st["master"]}') if st['master'] else ''), w, curses.A_DIM)
            today = datetime.now().astimezone().strftime('%Y-%m-%d')
            done = len(shipped().get(today, ()))
            y = para(scr, y, (L('오늘 슈퍼볼 받음 ✔', 'Great Ball earned today ✔') if today in st['rewarded'] else
                              L(f'오늘 push·PR·배포 {min(done, SUPER_SESSIONS)}/{SUPER_SESSIONS} — 채우면 슈퍼볼',
                                f'Push/PR/deploy today {min(done, SUPER_SESSIONS)}/{SUPER_SESSIONS} — fill it for a Great Ball'))
                     + L(f' · 연속 {streak(st, today)}일 · {STREAK_DAYS}일마다 하이퍼볼', f' · {streak(st, today)}-day streak · Ultra Ball every {STREAK_DAYS}'),
                     w, curses.A_DIM)
            para(scr, y, msg, w)
            x = button(h - 1, 1, L('도감', 'dex'), 'dex')
            x = button(h - 1, x, L('가방', 'bag'), 'box')
            x = button(h - 1, x, L('교환', 'trade'), 'trade')
            x = button(h - 1, x, L('훈장', 'medals'), 'badges')
            x = button(h - 1, x, L('체육관', 'gyms'), 'gyms')
            button(h - 1, x, L('닫기 q', 'close q'), 'close')
        elif view == 'badges':
            rows = [b for b, _, _, _ in BADGES]
            body = h - 4
            sel = max(0, min(sel, len(rows) - 1))
            top = max(0, min(min(max(top, sel - body + 1), sel), len(rows) - body))
            put(scr, 1, 1, msg or L(f'훈장 {len(st["badges"])}/{len(BADGES)} · 장식 {len(st.get("showcase", []))}/{SHOWCASE_MAX}'
                                    ' — Enter 로 장식 고르기/빼기',
                                    f'Medals {len(st["badges"])}/{len(BADGES)} · shown {len(st.get("showcase", []))}/{SHOWCASE_MAX}'
                                    ' — Enter to show/hide'), curses.A_DIM)
            draw_badge_list(scr, st, rows[top:top + body], top, sel, w, btns)
            if rows[sel] in st['badges'] and w >= 50:  # 커서가 놓인 훈장 그림을 오른쪽에 크게
                art = badge_art(st, [rows[sel]], 3, w - 14, 4)
            x = button(h - 1, 1, L('장식', 'show'), 'pin_sel')
            x = button(h - 1, x, L('돌아가기 q', 'back q'), 'back')
            put(scr, h - 1, x, L('↑↓ 고르기 · ←→ 버튼 · Enter', '↑↓ pick · ←→ button · Enter'), curses.A_DIM)
        elif view == 'gyms':
            rows = gym_rows(st)
            body = h - 4
            sel = max(0, min(sel, len(rows) - 1))
            top = max(0, min(min(max(top, sel - body + 1), sel), len(rows) - body))
            put(scr, 1, 1, msg or L(f'체육관 배지 {len(st.get("gym", {}))}/{sum(1 for r in rows if r[1] != "R")}', f'Gym badges {len(st.get("gym", {}))}/{sum(1 for r in rows if r[1] != "R")}'),
                curses.A_DIM)
            for k, (g, i) in enumerate(rows[top:top + body]):
                key = f'gym:{g}-{i}'
                if i == 'R':
                    rs = raid_state(st)
                    x = put(scr, 2 + k, 0, ('▶ ' if top + k == sel else '  ') + L(f'이번 주 레이드 — {name(raid_boss(st)[1])} ({g}세대)',
                                                                                  f'Raid this week — {name(raid_boss(st)[1])} (Gen {g})'), curses.A_BOLD)
                    if rs['won']:
                        put(scr, 2 + k, x + 2, L('✔ 승리 — 레이드볼로 잡자', '✔ won — catch it'))
                    btns.append((2 + k, 1, w - 1, ('gym', (g, i))))
                    continue
                if i == 'L':
                    won = st.get('league', {}).get(str(g))
                    x = put(scr, 2 + k, 0, ('▶ ' if top + k == sel else '  ') + L(f'{g}세대 사천왕·챔피언', f'Gen {g} Elite Four'),
                            curses.A_BOLD if won else 0)
                else:
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
                g_, i_ = rows[sel]
                art = None if i_ == 'R' else badge_art(st, [f'champ{g_}' if i_ == 'L' else f'gym:{g_}-{i_}'], 3, w - 14, 4)
            x = button(h - 1, 1, L('도전 준비', 'prepare'), 'gym_sel')
            x = button(h - 1, x, L('장식', 'show'), 'pin_gym')
            x = button(h - 1, x, L('돌아가기 q', 'back q'), 'back')
            put(scr, h - 1, x, L('↑↓ 관 · ←→ 버튼 · Enter', '↑↓ gym · ←→ button · Enter'), curses.A_DIM)
        elif view == 'gym':
            g, i = gsel
            opp = gym_opp(BATTLE, g, i, st)
            team = team_of(st, None if i == 'R' else g)
            tn = lambda tp: BATTLE['tnames'].get(tp, ['', ''])  # noqa: E731
            won = st.get('league', {}).get(str(g)) if i == 'L' else (L('이번 주', 'this week') if raid_state(st)['won'] else None) \
                if i == 'R' else st.get('gym', {}).get(f'gym:{g}-{i}')
            y = para(scr, 1, (L(f'{g}세대 사천왕·챔피언 — 5연전', f'Gen {g} Elite Four — 5 battles') if i == 'L' else
                              L(f'이번 주 레이드 — {name(opp[0][0])} ({g}세대 전설, HP ×{RAID_HP})',
                                f'Raid this week — {name(opp[0][0])} (Gen {g} legendary, HP ×{RAID_HP})') if i == 'R' else
                              L(f'{g}세대 {i + 1}관 — {tn(_battle.GYMS[g][i][0])[0]} 타입', f'Gen {g} gym {i + 1} — {tn(_battle.GYMS[g][i][0])[1]} type'))
                     + (L(f'  ✔ {won}\xa0승리', f'  ✔ won\xa0{won}') if won else ''), w, curses.A_BOLD)
            if i == 'L':  # 사천왕 4명(타입)과 챔피언 — 한 명씩, 길면 접는다
                for k, tm in enumerate(opp):
                    who = L('챔피언', 'Champ ') if k == _battle.ELITE_COUNT else L(f'사천왕{k + 1} {tn(_battle.LEAGUE[g][k])[0]}', f'E4 #{k + 1} {tn(_battle.LEAGUE[g][k])[1]}')
                    y = para(scr, y, f'{who}: ' + ', '.join(name(x[0]) for x in tm) + f'\xa0Lv{tm[0][1]}', w, curses.A_DIM)
            else:  # 이름과 레벨은 붙여 접는다(\xa0)
                y = para(scr, y + 1, L('상대  ', 'Foe   ') + ', '.join(f'{name(n)}\xa0Lv{lv}' for n, lv, *_ in opp), w, curses.A_DIM)
            y = para(scr, y, L('내 팀 ', 'Team  ') + (', '.join(f'{name(n)}\xa0Lv{lv}' for _, n, lv in team) or
                                                    L('(비었다 — [추천] → [적용])', '(empty — [pick] → [apply])')), w)
            put(scr, y, 1, L('모든 세대 포켓몬 출전', 'Any generation may enter') if i == 'R' else L(f'{g}세대 포켓몬만 출전', f'Gen {g} Pokémon only'), curses.A_DIM)
            wkey = (tuple(fighters(st, team)), g, i)
            if wkey not in wr_cache:
                if i == 'L' and team:
                    put(scr, y + 1, 1, L('승률 계산 중…', 'Working out the odds…'), curses.A_DIM)
                    scr.refresh()
                wr_cache[wkey] = gym_rate(BATTLE, fighters(st, team), g, i, st)
            put(scr, y + 1, 1, L(f'승률 {wr_cache[wkey]:.0%}', f'Win rate {wr_cache[wkey]:.0%}'), curses.A_BOLD)
            y += 2
            if rec and rec[0] == (g, i):
                rteam = [(st['box'][k]['id'], box_level(st['box'][k])) for k in rec[1]]
                y = para(scr, y, L('추천  ', 'Pick  ') + ', '.join(name(n) for n, _ in rteam) +
                         L(f'  (승률\xa0{rec[2]:.0%})\xa0—\xa0[적용]', f'  ({rec[2]:.0%})\xa0—\xa0[apply]'), w)
            cost = LEAGUE_COST if i == 'L' else RAID_COST if i == 'R' else GYM_COST
            if i == 'R':
                y = para(scr, y, L(f'이기면 레이드볼 {RAID_BALLS}개로 잡을 기회 — 가진 볼은 못 쓴다', f'Win for {RAID_BALLS} Raid Balls to catch it — your own balls don\'t work'), w, curses.A_DIM)
            y = para(scr, y + 1, msg, w)
            para(scr, y, L(f'탐색 기회 {tickets(st, t)}회 · 도전 1번에 {cost}회', f'{tickets(st, t)} explores · {cost} per challenge'),
                 w, curses.A_DIM)
            x = button(h - 1, 1, L('도전', 'fight'), 'fight')
            x = button(h - 1, x, L('추천', 'pick'), 'rec')
            x = button(h - 1, x, L('적용', 'apply'), 'apply')
            button(h - 1, x, L('돌아가기 q', 'back q'), 'back')
        elif view == 'fight':
            ev, k = battle_now['ev'], battle_now['k']
            now = fight_state(ev, k)
            y = 1
            for side, label in (('foe', L('상대', 'Foe ')), ('me', L('나  ', 'Me  '))):
                if side in now:
                    n, hp, top_, lv_ = now[side]
                    top_ = top_ or _battle.Mon(BATTLE, n, lv_).st[0]
                    hp = top_ if hp is None else hp
                    x = put(scr, y, 1, f'{label} {name(n)} Lv{lv_} ')
                    put(scr, y, x, f'{bar(hp / top_, 16)} {hp}/{top_}')
                y += 1
            if 'me' in now and 'foe' in now and (SIXEL or KITTY):
                # 2줄 높이로 — 5줄은 너무 컸고, 터미널이 칸 크기를 다르게 그려 실제로는 더 커져 기록과 겹쳤다(2026-10-21).
                # 그래서 그림 아래 자리를 그림 높이의 두 배만큼 비워 둔다.
                below = _gfx.rows_below(y + 1)
                rows_ = 2 if (below is None or below >= 6) and h >= 16 else 0
                if rows_:
                    cw_, ch_ = _gfx.cell_px()
                    ids = [art_of(now['me'][0]), art_of(now['foe'][0])]  # 리전폼은 'form:번호' 그림
                    img = _pokedata.strip_image(ids, int(rows_ * ch_), 'six' if SIXEL else 'png')
                    if img:
                        cols = math.ceil(img[1] / cw_)
                        art = ('six', y + 1, 2, ('fight', tuple(ids), rows_), img[0], cols, rows_) if SIXEL else \
                            ('kitty', y + 1, 2, 200000 + zlib.crc32(repr(ids).encode()) % 100000, img[0], cols, rows_)
                    y += rows_ * 2 + 1
            lines = [(part, j == k - 1) for j, e in enumerate(ev[:k]) for part in fold(fight_line(e), max(10, w - 2))][-(h - y - 3):]
            for j, (line, last) in enumerate(lines):  # 긴 줄은 접는다 — 마지막 기록(접힌 줄 모두)은 굵게
                put(scr, y + 1 + j, 1, line, curses.A_BOLD if last else 0)
            if k >= len(ev):
                ups = battle_now.get('ups', [])  # 받은 경험치와 레벨업을 결과 줄에 — 쌓이는 게 보이게
                gain = L(f' 경험치 +{battle_now.get("xp", 0)}', f' XP +{battle_now.get("xp", 0)}') + (
                    ' · Lv↑ ' + ', '.join(f'{name(n)} {a}→{b}' for n, a, b in ups[:2])
                    + (L(f' 외 {len(ups) - 2}', f' +{len(ups) - 2}') if len(ups) > 2 else '') if ups else '')
                res = (L('승리! ', 'You won! ') + (L(f'[{badge_name(battle_now["key"])}]을 받았다!' if battle_now['key'].startswith('champ') else f'[{badge_name(battle_now["key"])}]를 받았다!',
                                                  f'Got the [{badge_name(battle_now["key"])}]!') if battle_now['first'] else '') + gain) \
                    if battle_now['won'] else L('패배…', 'Defeat…') + gain
                put(scr, h - 2, 1, res, curses.A_BOLD)
            x = button(h - 1, 1, (L('허브로 q', 'to hub q') if battle_now['won'] else L('다시 준비 q', 'retry q'))
                       if k >= len(ev) else L('돌아가기 q', 'back q'), 'back')
            if k < len(ev):
                put(scr, h - 1, x, L('Enter 끝까지', 'Enter skip'), curses.A_DIM)
        elif view == 'info':
            art = draw_info(scr, st, info, h, w, gold)
            if info in DEX:
                put(scr, h - 2, 1, research_text(st, info), curses.A_BOLD if research_done(st, info) else curses.A_DIM)
            x = button(h - 1, 1, L('돌아가기 q', 'back q'), 'back')
            put(scr, h - 1, x, L('←→ 앞뒤 포켓몬', '←→ prev/next'), curses.A_DIM)
        elif view == 'change':  # 가방 F — 바꿀 모습 고르기(합체·메가진화·거다이맥스·원시회귀·울트라버스트)
            opts = change_options(st, chg) if chg is not None and chg < len(st['box']) else []
            y = para(scr, 1, msg or L(f'{name(st["box"][chg]["id"])} — 바꿀 모습 · 재료는 사라지고 되돌릴 수 없다',
                                      f'{name(st["box"][chg]["id"])} — change into · uses the material, can\'t be undone') if opts else msg, w, curses.A_DIM)
            sel = max(0, min(sel, len(opts) - 1))
            for k, (f, (what, ref), ok, why) in enumerate(opts):
                cost = (f'{name(st["box"][ref]["id"])} Lv{box_level(st["box"][ref])} · {iv_text(st["box"][ref])}' if what == 'mon'
                        else L(f'{item_name(ref)} {st.get("items", {}).get(ref, 0)}개', f'{item_name(ref)} ×{st.get("items", {}).get(ref, 0)}'))
                text = f'{name(f)} ← {cost}' + ('' if ok else f'  · {why}')
                btns.append((y + 1 + k, 1, w - 1, ('chg', k)))
                put(scr, y + 1 + k, 1, text.ljust(w - 2) if k == sel else text,
                    (curses.A_REVERSE if k == sel else 0) | (0 if ok else curses.A_DIM))
            x = button(h - 1, 1, L('바꾸기', 'change'), 'chg_sel')
            button(h - 1, x, L('돌아가기 q', 'back q'), 'back')
        elif view == 'balls':  # [교환] → [몬스터볼] — 한 단계 위 볼로
            put(scr, 1, 1, msg or L('볼 바꾸기 — ↑↓ 고르기 · Enter 바꾸기', 'Swap balls — ↑↓ pick · Enter swap'), curses.A_DIM)
            sel = max(0, min(sel, len(TRADES) - 1))
            for k, (src, dst, cost) in enumerate(TRADES):
                text = L(f'{ball_name(src, cost)[0]} → {ball_name(dst, 1)[0]} · 가진 {st[src]}개',
                         f'{ball_name(src, cost)[1]} → {ball_name(dst, 1)[1]} · have {st[src]}')
                btns.append((3 + k, 1, w - 1, ('swap', k)))
                put(scr, 3 + k, 1, text.ljust(w - 2) if k == sel else text, curses.A_REVERSE if k == sel else 0)
            own = [(k, c) for k, c in st.get('items', {}).items() if c > 0]
            if own:
                para(scr, 7 + len(TRADES), L('아이템: ', 'Items: ') + ' · '.join(f'{item_name(k)} {c}' for k, c in own) + L(' — 가방 F 로 쓴다', ' — use with F in the bag'), w)
            para(scr, 4 + len(TRADES), L(f'지금: 몬스터볼 {st["balls"]} · 슈퍼볼 {st["super"]} · 하이퍼볼 {st["hyper"]} · 마스터볼 {st["master"]}',
                                         f'Now: Poké {st["balls"]} · Great {st["super"]} · Ultra {st["hyper"]} · Master {st["master"]}'), w, curses.A_DIM)
            x = button(h - 1, 1, L('바꾸기', 'swap'), 'swap_sel')
            button(h - 1, x, L('돌아가기 q', 'back q'), 'back')
        elif view == 'dex' and dg == GENS + 2:  # 도감 마지막 쪽 — 특수 모습(메가진화·거다이맥스·원시회귀·울트라버스트)
            made, og, items = st.get('specials', []), opened_gen(st), st.get('items', {})
            rows = []
            for p, (s_, kind, g, *_) in SPECIALS.items():
                key = 'soup' if kind == 'gmax' else f'stone:{p}'
                rows.append((p, ('● ' if p in made else '  ') + f'{s_:04d} ' + name(p) + ('' if p in made else '   · ' + (
                    L(f'{g}세대가 열리면', f'opens with Gen {g}') if og < g else L(f'{item_name(key)} {items.get(key, 0)}개', f'{item_name(key)} ×{items.get(key, 0)}')))))
            put(scr, 1, 1, L(f'◀ 특수 모습 {len(made)}/{len(SPECIALS)}   ● 만듦', f'◀ Special forms {len(made)}/{len(SPECIALS)}   ● made'), curses.A_DIM)
            hint = fold(L('메가스톤·울트라네크로Z: 그 종 연구 완료(이후 5마리마다 또) · 다이수프: 레이드 승리 · 구슬: 그란돈·가이오가 레이드 포획 — 가방 F 로 바꾼다',
                          'Mega Stones, Ultranecrozium Z: finish that species\' research (another every 5 catches after) · Max Soup: raid wins · orbs: catch Groudon/Kyogre in a raid — change with F in the bag'), max(10, w - 2))
            body = h - 3 - len(hint)  # 아래 안내가 접힌 줄 수만큼 목록을 줄인다 — 버튼 줄과 겹치지 않게
            sel = max(0, min(sel, len(rows) - 1))
            top = max(0, min(min(max(top, sel - body + 1), sel), len(rows) - body))
            for k, (p, text) in enumerate(rows[top:top + body]):
                if p in made:
                    btns.append((2 + k, 1, w - 1, ('info', p)))
                put(scr, 2 + k, 1, text.ljust(w - 2) if top + k == sel else text, curses.A_REVERSE if top + k == sel else 0)
            for k, line in enumerate(hint):
                put(scr, h - 1 - len(hint) + k, 1, line, curses.A_DIM)
            x = button(h - 1, 1, L('돌아가기 q', 'back q'), 'back')
            put(scr, h - 1, x, L('↑↓ 이동 · Enter 상세 · ← 리전폼', '↑↓ move · Enter details · ← regional'), curses.A_DIM)
        elif view == 'dex' and dg > GENS:  # 도감 리전폼 쪽
            top_g = opened_gen(st) if wild_pool(st) else GENS + 1
            rows = [(p, ('● ' if p in st['forms'] else '○ ' if p in st['forms_seen'] else '  ')
                     + f'{sp:04d} ' + (name(p) if p in st['forms_seen'] else L(REGION[ident.split('-')[0]][0], REGION[ident.split('-')[0]][1]) + ' ???')
                     + ('' if p in st['forms'] else '   · ' + (
                         L(f'{gen(sp)}세대를 넘기면 나온다', f'appears once Gen {gen(sp)} is behind you') if gen(sp) >= top_g else
                         L('이전 세대 탐색 · 하이퍼볼·마스터볼', 'earlier-gen explore · Ultra/Master') if DEX[sp][5] else
                         L('이전 세대 탐색', 'earlier-gen explore'))))
                    for p, (sp, ident) in FORMS.items()]
            put(scr, 1, 1, L(f'◀ 리전폼 {len(st["forms"])}/{len(FORMS)} ▶   ● 잡음 ○ 봄',
                              f'◀ Regional forms {len(st["forms"])}/{len(FORMS)} ▶   ● caught ○ seen'), curses.A_DIM)
            body = h - 4
            sel = max(0, min(sel, len(rows) - 1))
            top = max(0, min(min(max(top, sel - body + 1), sel), len(rows) - body))
            for k, (p, text) in enumerate(rows[top:top + body]):
                if p in st['forms_seen']:
                    btns.append((2 + k, 1, w - 1, ('info', p)))
                put(scr, 2 + k, 1, text.ljust(w - 2) if top + k == sel else text, curses.A_REVERSE if top + k == sel else 0)
            ready = sum(1 for p, (sp, _) in FORMS.items() if gen(sp) < top_g and p not in st['forms'])
            put(scr, h - 2, 1, L(f'이전 세대 탐색(5번 중 1번)에서 나온다 · 지금 나올 수 있는 폼 {ready}',
                                 f'They show up in earlier-generation explores (1 in 5) · {ready} can appear now')[:w - 2], curses.A_DIM)
            x = button(h - 1, 1, L('돌아가기 q', 'back q'), 'back')
            put(scr, h - 1, x, L('↑↓ 이동 · Enter 상세 · ←→ 세대·특수 모습', '↑↓ move · Enter details · ←→ generation/special'), curses.A_DIM)
        else:
            open_gen = opened_gen(st)
            if view in ('box', 'trade'):  # 보이는 순서(가방 번호들) — 키·버튼이 고른 줄도 이것으로 가방 번호를 찾는다
                order = bag_order(st, bag_g if view == 'box' else None, bag_sort)
            rows = ([(n, ('● ' if n in st['caught'] else '○ ' if n in st['seen'] else '  ')
                      + f'{n:04d} ' + (name(n) if n in st['seen'] else '???') + (' ★' if n in st.get('researched', []) else '')
                      + ('' if n in st['caught'] else '   · ' + dex_hint(st, n))) for n in DEX if gen(n) == dg]
                    if dg <= open_gen else []) \
                if view == 'dex' else \
                [(i, ('★ ' if i == st['partner'] else '  ') + ('⚔' if i in st.get('team', []) else ' ') + ('✨' if m.get('shiny') else '') + ('◆' if m.get('alpha') else '')
                  + (f'{name(m["id"])}  (No.{sp(m["id"]):03d} · Lv{box_level(m)} {xp_text(m)}) · {iv_text(m)}' if w >= 62 else
                     f'{name(m["id"])} Lv{box_level(m)} · {iv_text(m)}'))  # 좁으면 번호·경험치는 빼고 개체값까지 보이게
                 for i, m in ((i, st['box'][i]) for i in order)]
            if view == 'dex':
                have = sum(1 for n in st['caught'] if gen(n) == dg)
                done_r = sum(1 for n in st.get('researched', []) if gen(n) == dg)
                put(scr, 1, 1, L(f'◀ {dg}세대 도감 {have}/{GEN_SIZE[dg]} ▶ ★연구 {done_r}  ● 잡음 ○ 봄',
                                  f'◀ Gen {dg} Pokédex {have}/{GEN_SIZE[dg]} ▶ ★research {done_r}  ● caught ○ seen'), curses.A_DIM)
            elif view == 'trade':
                put(scr, 1, 1, msg or L(f'교환 · 정렬 {SORTS[bag_sort][0]} (Tab) — [박사에게] 한 마리 · [정리] 중복 한꺼번에 · [몬스터볼] 볼 바꾸기',
                                        f'Trade · sort {SORTS[bag_sort][1]} (Tab) — [send] one · [tidy] all duplicates · [balls] swap balls'), curses.A_DIM)
            else:
                page = L('전체', 'all') if bag_g is None else L(f'{bag_g}세대', f'Gen {bag_g}')
                put(scr, 1, 1, msg or L(f'◀ {page} {len(order)}마리 ▶ 정렬 {SORTS[bag_sort][0]} — Enter 동료 · Space 팀 · Tab 정렬',
                                        f'◀ {page} {len(order)} ▶ sort {SORTS[bag_sort][1]} — Enter partner · Space team · Tab sort'), curses.A_DIM)
            body = h - 4
            if to_partner is not False:  # 가방을 열면 지금 동료 줄에서 시작 · 숫자면 그 가방 번호 줄로(합체·분리 뒤)
                go = st['partner'] if to_partner is True else to_partner
                sel, to_partner = order.index(go) if go in order else 0, False
            if rows:
                sel = max(0, min(sel, len(rows) - 1))
                top = min(max(top, sel - body + 1), sel)  # 커서가 화면 안에 있게
            top = max(0, min(top, len(rows) - body))
            for k, (key, text) in enumerate(rows[top:top + body]):
                attr = 0
                if view in ('box', 'trade'):
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
            if view == 'box':
                x = button(h - 1, 1, L('동료로', 'partner'), 'partner_sel')
                x = button(h - 1, x, L('팀', 'team'), 'team')
                pk = order[sel] if order else None  # 고른 줄이 바뀔 수 있는 모습(합체·메가진화·거다이맥스…)이 있으면 [변신]
                if pk is not None and change_options(st, pk):
                    x = button(h - 1, x, L('변신 F', 'change F'), 'fuse')
                x = button(h - 1, x, L(f'정렬: {SORTS[bag_sort][0]}', f'sort: {SORTS[bag_sort][1]}'), 'sort')
                button(h - 1, x, L('돌아가기 q', 'back q'), 'back')
            elif view == 'trade':
                x = button(h - 1, 1, L('박사에게', 'send'), 'send')
                x = button(h - 1, x, L('정리', 'tidy'), 'tidy')
                x = button(h - 1, x, L('몬스터볼', 'balls'), 'balls')
                button(h - 1, x, L('돌아가기 q', 'back q'), 'back')
            else:
                if rows:
                    put(scr, h - 2, 1, dex_summary(st, dg)[:w - 2], curses.A_DIM)
                x = button(h - 1, 1, L('돌아가기 q', 'back q'), 'back')
                put(scr, h - 1, x, L('↑↓ 이동 · Enter 자세히 · ←→ 세대', '↑↓ move · Enter details · ←→ generation'), curses.A_DIM)
        acts = [b[3] for b in navbtns]
        if focus not in acts:  # 처음이거나 그 버튼이 사라졌으면 — 돌아가기·닫기가 아닌 첫 버튼
            focus = next((a for a in acts if a not in ('back', 'close')), acts[0] if acts else None)
        for by, bx, _, a, text in navbtns:
            if a == focus:
                put(scr, by, bx, text, curses.A_BOLD | curses.A_REVERSE)
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
        act = {ord('q'): 'back' if view != 'main' else 'close', 27: 'back' if view != 'main' else 'close'}.get(key)
        lists = view in ('box', 'trade', 'balls', 'change', 'dex', 'badges', 'gyms')  # ↑↓ 는 목록 줄을, ←→ 는 아래 버튼을 고른다
        if view in ('box', 'trade') and key == 9:  # Tab — 정렬 바꾸기
            act = 'sort'
        if view == 'box' and key in (curses.KEY_LEFT, curses.KEY_RIGHT):  # 세대 넘기기: 전체 → 가방에 있는 세대들
            pages = [None] + sorted({gen(m['id']) for m in st['box']})
            bag_g = pages[(pages.index(bag_g) + (1 if key == curses.KEY_RIGHT else -1)) % len(pages)] if bag_g in pages else None
            top, sel, msg = 0, 0, ''
        elif view == 'dex' and key in (curses.KEY_LEFT, curses.KEY_RIGHT):
            dg, top, sel = max(1, min(GENS + 1 + bool(SPECIALS), dg + (1 if key == curses.KEY_RIGHT else -1))), 0, 0  # 뒤의 두 쪽은 리전폼 · 특수 모습
        elif view == 'info' and key in (curses.KEY_LEFT, curses.KEY_RIGHT):
            seen = [p for p in SPECIALS if p in st.get('specials', [])] if info in SPECIALS else \
                [p for p in FORMS if p in st['forms_seen']] if info in FORMS else \
                sorted(n for n in st['seen'] if gen(n) == gen(info))  # 같은 세대(리전폼은 리전폼)에서 본 것끼리 앞뒤로
            info = seen[(seen.index(info) + (1 if key == curses.KEY_RIGHT else -1)) % len(seen)]
        elif lists and key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE):
            sel += {curses.KEY_UP: -1, curses.KEY_DOWN: 1, curses.KEY_PPAGE: -(h - 4), curses.KEY_NPAGE: h - 4}[key]
        elif key in (curses.KEY_LEFT, curses.KEY_RIGHT, curses.KEY_UP, curses.KEY_DOWN):
            focus = move_focus(navbtns, focus, key)
        if key in (ord('\n'), ord('\r'), curses.KEY_ENTER):
            if view == 'dex' and dg == GENS + 2:
                p = list(SPECIALS)[min(sel, len(SPECIALS) - 1)]
                act = ('info', p) if p in st.get('specials', []) else None
            elif view == 'dex' and dg > GENS:
                p = list(FORMS)[min(sel, len(FORMS) - 1)]
                act = ('info', p) if p in st['forms_seen'] else None
            elif view == 'dex':
                n = [m for m in DEX if gen(m) == dg][min(sel, GEN_SIZE[dg] - 1)]
                act = ('info', n) if n in st['seen'] else None
            elif view == 'box':
                act = 'partner_sel'  # 가방에서 Enter 는 동료로
            elif view == 'fight':
                act = 'back'  # 기록을 끝까지 → 한 번 더 누르면 나간다
            elif view != 'info':
                act = focus
        if view == 'box' and key == ord(' '):
            act = 'team'  # Space 는 팀 넣기/빼기
        if view == 'box' and key in (ord('f'), ord('F')):
            act = 'fuse'  # F 는 변신(합체·메가진화·거다이맥스…) 화면 — 가방에선 방향키가 줄·세대라 아래 버튼까지 못 간다
        picked = order[max(0, min(sel, len(order) - 1))] if order and view in ('box', 'trade') else None
        # 고른 줄에 하는 버튼 → 그 줄의 일로
        if act == 'swap_sel':
            act = ('swap', max(0, min(sel, len(TRADES) - 1)))
        if act == 'partner_sel':
            act = ('partner', picked) if picked is not None else None
        elif act == 'pin_sel':
            act = ('pin', BADGES[max(0, min(sel, len(BADGES) - 1))][0])
        elif act in ('gym_sel', 'pin_gym'):
            rows = gym_rows(st)
            gi = rows[max(0, min(sel, len(rows) - 1))]
            act = ('gym', gi) if act == 'gym_sel' else ('pin', f'champ{gi[0]}' if gi[1] == 'L' else f'gym:{gi[0]}-{gi[1]}')
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, b = curses.getmouse()
                if b & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED):
                    act = next((a for by, x0, x1, a in btns if my == by and x0 <= mx < x1), None)
                    focus = act if act in acts else focus
                elif b & getattr(curses, 'BUTTON4_PRESSED', 0):
                    top -= 3
                elif b & getattr(curses, 'BUTTON5_PRESSED', 0):
                    top += 3
            except curses.error:
                pass
        if act == 'sort' and view in ('box', 'trade'):
            bag_sort, top, sel, msg = (bag_sort + 1) % len(SORTS), 0, 0, ''
            _lang.put('bag_sort', bag_sort)  # PC 설정에 — 다시 열어도 그 정렬
        if act == 'close':
            break
        if act == 'chg_sel' and view == 'change':
            act = ('chg', sel)
        if isinstance(act, tuple) and act[0] == 'chg' and view == 'change':
            opts = change_options(st, chg) if chg is not None and chg < len(st['box']) else []
            k = act[1]
            if not 0 <= k < len(opts):
                msg = ''
            elif not opts[k][2]:
                msg = L(f'아직 못 바꾼다 — {opts[k][3]}', f'Not yet — {opts[k][3]}')
            elif confirm != ('chg', chg, k):  # 되돌릴 수 없으니 한 번 더 눌러야 바뀐다
                confirm = ('chg', chg, k)
                msg = L(f'{name(opts[k][0])}(으)로 바꾼다 — 재료는 사라지고 되돌릴 수 없다. 한 번 더 누르면 바뀐다',
                        f'Change into {name(opts[k][0])} — the material is used up and it can\'t be undone. Press again')
            else:
                mon, before = st['box'][chg], name(st['box'][chg]['id'])
                f = change(st, chg, k)
                save(st)
                msg = L(f'오잉!? {before}의 모습이… {name(f)}(으)로 바뀌었다!', f'What? {before} became {name(f)}!')
                view, confirm, rec = 'box', None, None
                to_partner = next(j for j, m in enumerate(st['box']) if m is mon)  # 가방으로 돌아가면 커서는 그 포켓몬에
            act = None
        if act in ('send', 'tidy') and view == 'trade' and picked is not None:
            i = picked
            idxs = [i] if act == 'send' else tidy_targets(st)
            what = (act, tuple(idxs))
            m = st['box'][i]
            if act == 'send' and (i == st['partner'] or i in st.get('team', []) or m.get('shiny') or m.get('fused')):
                msg, confirm = L('동료·팀·이로치·합체한 포켓몬은 박사에게 보내지 않는다(합체는 가방에서 [분리]).',
                                 "Partner, team, shiny and fused Pokémon can't be sent (split a fusion in the bag)."), None
            elif not idxs:
                msg, confirm = L('정리할 것이 없다 — 같은 종이 둘 이상일 때 가장 좋은 것만 남긴다.', 'Nothing to tidy — only duplicates are sent.'), None
            elif confirm != what:  # 되돌릴 수 없으니 한 번 더 눌러야 보낸다
                confirm = what
                msg = L(f'{name(m["id"])} {iv_text(m)} — 한 번 더 누르면 박사에게 보낸다', f'{name(m["id"])} {iv_text(m)} — press again to send') \
                    if act == 'send' else L(f'같은 종 중 가장 좋은 것만 남기고 {len(idxs)}마리를 보낸다 — 한 번 더 누르면 보낸다',
                                            f'Keeps the best of each species and sends {len(idxs)} — press again to send')
            else:
                k, balls = send_away(st, idxs)
                save(st)
                rec, confirm = None, None
                msg = L(f'박사에게 {k}마리를 보냈다! 몬스터볼 +{balls}', f'Sent {k} to the Professor! Poké Balls +{balls}')
        elif act is not None:
            confirm = None
        if isinstance(act, tuple) and act[0] == 'swap':
            src, dst, cost = TRADES[act[1]]
            ok = exchange(st, act[1])
            if ok:
                save(st)
            msg = L(f'{ball_name(src, cost)[0]}를 {ball_name(dst, 1)[0]}로 바꿨다! (지금 {st[dst]}개)',
                    f'Swapped {ball_name(src, cost)[1]} for {ball_name(dst, 1)[1]}! (now {st[dst]})') if ok else \
                L(f'{ball_name(src, cost)[0]}가 있어야 바꿀 수 있다 (지금 {st[src]}개)', f'You need {ball_name(src, cost)[1]} (have {st[src]})')
            act = None
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
        if act == 'team' and view == 'box' and picked is not None:
            msg = toggle_team(st, picked)
            save(st)
        if act == 'fuse' and view == 'box' and picked is not None:
            if change_options(st, picked):
                view, chg, top, sel, msg, confirm = 'change', picked, 0, 0, '', None
            else:
                msg = L('이 포켓몬은 바뀔 수 있는 모습이 없다.', 'This Pokémon has no other form to change into.')
        if act == 'rec' and view == 'gym':
            put(scr, 9, 1, L('추천 팀을 계산하는 중…', 'Working out a team…'), curses.A_DIM)
            scr.refresh()
            cands = [(k, m['id'], box_level(m), iv_of(m)) for k, m in enumerate(st['box']) if gsel[1] == 'R' or gen(m['id']) == gsel[0]]
            opp = gym_opp(BATTLE, *gsel, st)
            if gsel[1] == 'L':  # 연전은 다섯 팀을 이어 붙여 후보를 추리고, 고를 때는 연전 승률로(가볍게 40번씩)
                pick = _battle.recommend(BATTLE, cands, sum(opp, []), rate=lambda tm: _battle.league_rate(BATTLE, tm, opp, runs=40))
            else:
                pick = _battle.recommend(BATTLE, cands, opp)
            rec = (gsel, pick, gym_rate(BATTLE, [c[1:] for c in cands if c[0] in pick], *gsel, st))
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
                ups = [(n, lv, box_level(st['box'][k])) for k, n, lv in team if box_level(st['box'][k]) > lv]
                gain = GYM_WIN_XP + 10 * (8 if gsel[1] == 'L' else gsel[1]) if won else GYM_LOSE_XP
                battle_now = {'ev': ev, 'k': 0, 'won': won, 'first': first, 'xp': gain, 'ups': ups,
                              'key': f'champ{gsel[0]}' if gsel[1] == 'L' else f'gym:{gsel[0]}-{gsel[1]}'}
                view, msg = 'fight', ''
                scr.timeout(600)  # 기록을 한 줄씩 — getkey 는 이 값을 따른다(빠뜨리면 키를 누를 때까지 멈춘다)
        if act in ('dex', 'box', 'trade'):
            view, top, dg, msg, sel = act, 0, opened_gen(st), '', 0
            bag_g, to_partner = None, act == 'box'  # 가방은 전체·지금 동료 줄에서 시작
        elif act == 'balls' and view == 'trade':
            view, top, sel, msg = 'balls', 0, 0, ''
        elif act == 'back' and view == 'fight' and battle_now['k'] < len(battle_now['ev']):
            battle_now['k'] = len(battle_now['ev'])  # 먼저 끝까지 보여 주고, 한 번 더 누르면 나간다
        elif act == 'back' and view == 'fight' and battle_now['won']:
            break  # 이겼으면 다시 준비할 일이 없으니 포켓몬 모드를 닫고 허브로 — 지면 준비 화면으로(아래)
        elif act == 'back':
            if view == 'fight':
                scr.timeout(2000)
            view = {'info': 'dex', 'gym': 'gyms', 'fight': 'gym', 'balls': 'trade', 'change': 'box'}.get(view, 'main')  # 한 단계 위로
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
        elif view == 'main' and act in ('explore', 'throw', 'super', 'hyper', 'master', 'run', 'evolve', 'candy'):
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
            elif act in ('throw', 'super', 'hyper', 'master') and st['wild']:
                n, eggs0 = st['wild'].get('form') or st['wild']['id'], len(st.get('eggs', []))
                r = throw(st, t, kind={'throw': 'ball'}.get(act, act))
                msg = {'caught': L(f'신난다! {name(n)}(을)를 잡았다!', f'Gotcha! {name(n)} was caught!'),
                       'missed': L('아깝다! 볼에서 빠져나왔다.', 'Argh! It broke free.'),
                       'fled': L(f'{name(n)}(은)는 도망쳐 버렸다…', f'{name(n)} ran away…'),
                       'raidonly': L('레이드 보스에겐 레이드볼만 던질 수 있다.', 'Only Raid Balls work on a raid boss.'),
                       'needhyper': L(f'{name(n)}(은)는 하이퍼볼·마스터볼로만 잡힌다! [교환] → [몬스터볼]에서 바꿔 오자.',
                                      f'Only an Ultra or Master Ball works on {name(n)}! Swap balls in [trade] → [balls].'),
                       None: L('그 볼이 없다.', "You don't have that ball.")}[r]
                if r == 'caught' and len(st.get('eggs', [])) > eggs0:
                    msg += L(' 풀숲에서 알도 하나 주웠다!', ' Found an egg in the grass too!')
            elif act == 'run' and st['wild']:
                if st['wild'].get('raid'):  # 레이드 보스를 놓아주면 이번 주 레이드는 끝
                    raid_state(st)['done'] = True
                msg, st['wild'] = L('무사히 도망쳤다.', 'Got away safely.'), None
            elif act in ('evolve', 'candy'):
                before = name(st['box'][st['partner']]['id']) if st['partner'] is not None else ''
                n = evolve(st, t) if act == 'evolve' else use_candy(st, t)
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
    # 이전 세대 진화형(에브이 196 · 블래키 197)은 1/10 — 다른 것이 다 잡히고 그것만 남으면 보통 확률로(막히지 않게)
    ev = new_state(); ev['league'] = {'1': True}
    g2 = [n for n in DEX if gen(n) == 2]
    ev['caught'] = [n for n in DEX if gen(n) == 1]
    order = [n for n in sorted((n for n in g2 if wild_ok(n)), key=order_key)]
    later = [n for n in order[order.index(197) + 1:] if not evo_wild(n) and not DEX[n][5]][:2]  # 순서상 둘 뒤에 오는 일반 종
    ev['caught'] += [n for n in g2 if n not in (196, 197, *later)]
    o = dict(wild_odds(ev))
    assert evo_wild(196) and evo_wild(169) and not evo_wild(152) and not evo_wild(153), o
    assert later and o.get(196) == EVO_WILD_WEIGHT and o.get(197) == EVO_WILD_WEIGHT and all(o.get(n) == 1 for n in later), o
    ev['caught'] += later
    assert dict(wild_odds(ev)) == {196: 1, 197: 1}
    assert dex_hint(ev, 196) == L('진화 — ???에서 · 야생은 드묾', 'evolve from ??? · rare in the wild')
    odds = dict(wild_odds(dup))
    assert odds[25] == BOXED_WEIGHT and sorted(odds.values()).count(1) == WINDOW, odds
    dup['box'] = []
    assert dict(wild_odds(dup)).get(25) == 1  # 진화시켜 가방에서 빠지면 다시 보통 확률
    dup['box'] = [{'id': 25, 'xp': 0}]
    pick = type('R', (), {'choices': lambda s, xs, weights: [25], 'random': lambda s: 0.5})()
    assert explore(dup, ENCOUNTER_EVERY, pick) == (25, 0) and dup['wild']['id'] == 25  # 같은 종도 만나서 잡는다
    assert throw(dup, ENCOUNTER_EVERY, type('R', (), {'random': lambda s: 0.0})()) == 'caught' and [m['id'] for m in dup['box']] == [25, 25]
    assert dup['box'][1]['iv'] == [0, 0, 0] and len(dup['box'][0].get('iv', [])) == 0  # 개체값은 잡을 때(가짜 난수 0 → 0)
    # 개체값: 0~15, 바닥값, 불러올 때 옛 포켓몬에 고정된 값
    assert all(0 <= v <= 15 for _ in range(200) for v in roll_iv()) and min(min(roll_iv(floor=IV_FLOOR)) for _ in range(200)) >= IV_FLOOR
    lr = tempfile.mkdtemp()
    save({**new_state(), 'box': [{'id': 25, 'xp': 0}, {'id': 150, 'xp': 0}]}, lr)
    assert load(lr)['box'][0]['iv'] == load(lr)['box'][0]['iv'] and len(load(lr)['box'][0]['iv']) == 3
    assert min(load(lr)['box'][1]['iv']) >= IV_FLOOR  # 옛 전설도 바닥값부터
    assert iv_text({'iv': [15, 15, 15]}).endswith('(100%) ★') and iv_text({'iv': [0, 0, 0]}).endswith('(0%)')
    # 박사에게: 동료·팀·이로치는 남고, 번호가 당겨져도 동료·팀이 같은 포켓몬을 가리킨다, 볼은 dupe_balls 만큼
    ps = new_state()
    ps['box'] = [{'id': 10, 'xp': 0, 'iv': [1, 1, 1]}, {'id': 10, 'xp': 0, 'iv': [9, 9, 9]}, {'id': 10, 'xp': 0, 'iv': [5, 5, 5], 'shiny': True},
                 {'id': 25, 'xp': 0, 'iv': [2, 2, 2], 'bxp': 900}, {'id': 25, 'xp': 0, 'iv': [15, 15, 15]}, {'id': 25, 'xp': 0, 'iv': [3, 3, 3]},
                 {'id': 1, 'xp': 0, 'iv': [0, 0, 0]}]
    ps['partner'], ps['team'] = 6, [5]
    assert sorted(tidy_targets(ps)) == [0]  # 캐터피 하나 · 피카츄: 최고 개체·경험치는 남고 남은 하나는 팀
    assert send_away(ps, [6, 5, 2]) == (0, 0)  # 동료·팀·이로치는 못 보낸다
    assert send_away(ps, [0, 3]) == (2, dupe_balls(10) + dupe_balls(25)) and ps['balls'] == dupe_balls(10) + dupe_balls(25)
    assert [m['id'] for m in ps['box']] == [10, 10, 25, 25, 1] and ps['box'][ps['partner']]['id'] == 1
    assert ps['team'] == [3] and ps['box'][3]['iv'] == [3, 3, 3] and ps['sent'] == 2
    # 가방 정렬·세대: 도감번호(기본) · 레벨 높은 순 · 개체값 높은 순 · 이름(한글 ㄱㄴㄷ) — 같으면 도감번호
    bo = new_state()
    bo['box'] = [{'id': 152, 'xp': 0, 'iv': [1, 1, 1]}, {'id': 25, 'xp': 0, 'iv': [15, 15, 15]}, {'id': 3, 'xp': 0, 'iv': [5, 5, 5], 'bxp': 500},
                 {'id': 1, 'xp': 0, 'iv': [9, 9, 9]}]
    ids = lambda srt, g=None: [bo['box'][i]['id'] for i in bag_order(bo, g, srt)]  # noqa: E731
    assert ids(0) == [1, 3, 25, 152] and ids(1)[0] == 3 and ids(2) == [25, 1, 3, 152] and ids(0, 2) == [152]
    if L('ko', 'en') == 'ko':
        assert ids(3) == [3, 1, 152, 25]  # 이상해꽃 · 이상해씨 · 치코리타 · 피카츄
    # 경험치: 15만 넘으면 이상해씨 → 이상해풀, 다음은 40만
    assert not can_evolve(st, t + 149_999) and can_evolve(st, t + 150_000)
    assert evolve(st, t + 150_000, rng) == 2 and 2 in st['caught'] and partner_xp(st, t + 150_000) == 0
    # 이상해풀이 가방에 있어도 이상해씨는 진화한다(같은 모습 둘 — 중복 포획부터)
    bar_st = new_state()
    bar_st['box'], bar_st['caught'], bar_st['partner'] = [{'id': 1, 'xp': 10**9}, {'id': 2, 'xp': 0}], [1, 2], 0
    assert can_evolve(bar_st, 0) and evolve(bar_st, 0) == 2
    # 이브이: 샤미드가 가방에 있으면 남은 둘 중에서만
    bar_st['box'] = [{'id': 133, 'xp': 10**9}, {'id': 134, 'xp': 0}]
    bar_st['partner'] = 0
    assert sorted(evolutions(bar_st, 133)) == [135, 136]
    bar_st['box'] += [{'id': 135, 'xp': 0}, {'id': 136, 'xp': 0}]
    assert sorted(evolutions(bar_st, 133)) == [134, 135, 136]  # 다 있으면 아무 모습으로나
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
    # 이로치: 기본 피카츄가 가방에 있어도 이로치 피카츄를 잡고, 이로치가 있어도 또 만난다
    sh = new_state()
    sh['box'], sh['caught'] = [{'id': 25, 'xp': 0}], [25]
    lucky = type('R', (), {'choices': lambda s, xs, weights: [25], 'random': lambda s: 0.0})()
    # (난수 0 이면 우두머리도 함께 — 개체값은 우두머리 바닥 ALPHA_IV 부터)
    assert explore(sh, ENCOUNTER_EVERY, lucky) == (25, 0) and sh['wild'] == {'id': 25, 'balls': BALLS, 'shiny': True, 'alpha': True, 'tries': 0}
    assert throw(sh, 0, lucky) == 'caught' and sh['box'][-1] == {'id': 25, 'xp': 0, 'iv': [ALPHA_IV] * 3, 'shiny': True, 'alpha': True}
    assert sh['shiny'] == [25]
    assert explore(sh, 2 * ENCOUNTER_EVERY, lucky) == (25, 0) and sh['wild']
    sh['wild'] = None
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
    assert throw(lg, 0, type('R', (), {'random': lambda s: 0.29})(), 'hyper') == 'caught' and lg['hyper'] == 0  # 0.2×2
    # 마스터볼: 전설도 난수와 상관없이 잡힌다
    lg['wild'], lg['master'] = {'id': 151, 'balls': 3}, 1
    assert throw(lg, 0, never, 'master') == 'caught' and lg['master'] == 0 and 151 in lg['caught']
    lg['wild'] = {'id': 144, 'balls': 3}
    assert throw(lg, 0, never, 'master') is None  # 마스터볼이 없다
    r95 = type('R', (), {'random': lambda s: 0.95})()  # 꼬렛 포획률 0.7: 몬스터볼은 빗나가고 슈퍼볼(1.05→1.0)은 잡힌다
    lg['wild'], lg['balls'], lg['super'] = {'id': 19, 'balls': 3}, 0, 1
    assert abs(catch_rate(19) - 0.7) < 1e-9 and throw(lg, 0, r95) == 'missed' and throw(lg, 0, r95, 'super') == 'caught'
    assert abs(catch_rate(143) - (0.35 + 0.35 * 25 / 255)) < 1e-9  # 잠만보 약 38%
    # 교환: 몬스터볼 5 → 슈퍼볼 · 슈퍼볼 20 → 하이퍼볼(훈장이 센다) · 하이퍼볼 5 → 마스터볼, 모자라면 그대로 — 마스터볼까지 몬스터볼 500개
    assert math.prod(c for _, _, c in TRADES) == 500
    ex = new_state()
    ex['balls'], ex['super'], ex['hyper'] = 12, 19, 4
    assert exchange(ex, 0) and (ex['balls'], ex['super']) == (7, 20) and exchange(ex, 1) and (ex['super'], ex['hyper']) == (0, 5)
    assert ex['exchanged'] == 1 and exchange(ex, 2) and (ex['hyper'], ex['master']) == (0, 1) and not exchange(ex, 2) and not exchange(ex, 1)
    # 슈퍼볼 보상: 내보낸 일(push·PR·배포)이 있는 날마다 1개(하루 1개), 켠 날 전은 주지 않는다
    jd = tempfile.mkdtemp()
    def job(j, rows):
        os.makedirs(f'{jd}/{j}')
        with open(f'{jd}/{j}/state.json', 'w') as f:
            json.dump({'name': j, 'state': 'done'}, f)
        with open(f'{jd}/{j}/timeline.jsonl', 'w') as f:
            f.write(''.join(json.dumps({'at': at, 'state': 'done', 'detail': d, 'text': '…'}) + '\n' for at, d in rows))
    day1, day2 = '2026-10-21T03:00:00Z', '2026-10-22T03:00:00Z'
    job('a', [(day1, 'main 에 push 완료'), ('2026-10-21T05:00:00Z', 'PR #2 merged')])  # 같은 날 두 번이어도 하나
    job('c', [(day2, '문서 정리')])  # 내보낸 일이 아니다
    rw = new_state()
    rw['reward_since'] = '2026-10-01'
    assert reward(rw, jd) == 1 and rw['super'] == 1 and reward(rw, jd) == 0  # 21일만, 하루 1개
    job('b', [(day2, '배포 완료')])
    feed._cache.clear()
    assert reward(rw, jd) == 1 and rw['super'] == 2 and not rw['eggs']  # 22일 — 연속 2일, 알은 아직
    rw2 = new_state()
    assert reward(rw2, jd, today='2026-10-22') == 1 and rw2['reward_since'] == '2026-10-22'  # 켠 날(22일) 전 보상은 없다
    # 도감 상세: 한국어가 없으면 영어, 설명은 최근 판, 줄바꿈은 빈칸, 다른 모습은 그 번호로, 타입은 slot 순
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
    assert det == {1: ['씨앗포켓몬', 'Seed Pokémon', ['풀', 'Poison'], ['Grass', 'Poison'], 7, 69, '새 설명', 'A seed'],
                   10001: ['', '', [], [], 9, 1, '', '']}, det  # 다른 모습: 제 키·몸무게, 분류·설명 없음
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
    spk = new_state()
    spk['box'], spk['partner'], spk['base'] = [{'id': 25, 'xp': 0}], 0, 0
    sjob('A', [(300, 'blocked', '물어봄')], 'blocked')
    said = speech(spk, 0, now, sd)
    assert said[1] is False and 'A' in said[0], said
    sjob('A', [(700, 'blocked', '물어봄')], 'blocked')
    assert speech(spk, 0, now, sd)[1] is True  # 10분 넘게 방치 → 경고
    assert speech(spk, 0, now, sd, awake=set()) is None  # 잠든 세션의 needs 는 무시
    sjob('A', [(30, 'done', 'PR #9 병합')])
    assert 'A' in speech(spk, 0, now, sd)[0] and speech(spk, 0, now, sd)[0] == L('피카츄(이)가 박수를 친다! (A 내보냄)', 'Pikachu claps! (A shipped)')
    tell(spk, 'super', now=now - 10)
    assert L('슈퍼볼', 'Great Ball') in speech(spk, 0, now, sd)[0]  # 보상 소식이 완료 반응보다 먼저
    spk['box'][0]['xp'] = 10**9
    assert L('빛나', 'glow') in speech(spk, 0, now, sd)[0]  # 진화 가능이 그보다 먼저
    spk['box'][0]['xp'], spk['news'] = 0, []
    sjob('A', [(500, 'done', '끝')])
    assert speech(spk, 0, now, sd) is None and speech(spk, ENCOUNTER_EVERY, now, sd)[0] == L('풀숲이 흔들린다…', 'The tall grass rustles…')
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
    # 알: 풀에는 열린 세대의 1단계(전설·환상 빼고), 베이비 ×3 · 가방에 있는 종 ×BOXED_WEIGHT · 최대 3개 · 다 자라야 부화
    eg = new_state()
    eg['caught'] = [n for n in DEX if gen(n) == 1]  # 1세대 완성 → 2세대까지 열림
    eg['box'] = [{'id': 1, 'xp': 0}]
    pool = dict(egg_pool(eg))
    assert pool[1] == 2 * BOXED_WEIGHT and 2 not in pool and 144 not in pool and 4 in pool and pool[172] == 3 and pool[4] == 2 and pool[10] == 1
    assert all(gen(n) <= 2 for n in pool)
    first = type('R', (), {'choices': lambda s, xs, weights: [172], 'random': lambda s: 0.5})()
    assert give_egg(eg, 1000, first) and eg['eggs'][0] == {'id': 172, 'base': 1000, 'need': 10 * EGG_STEP}
    assert give_egg(eg, 1000, first) and give_egg(eg, 1000, first) and not give_egg(eg, 1000, first) and len(eg['eggs']) == EGG_MAX
    assert hatch(eg, 1000 + 10 * EGG_STEP - 1, first) == []  # 덜 자랐다
    eg['eggs'] = eg['eggs'][:1]
    eg['box'].append({'id': 172, 'xp': 0})  # 그새 피츄가 가방에 들어와도 정해 둔 피츄 그대로
    # 덤은 표의 4번째(슈퍼볼 1개)를 고르는 난수 · 개체값은 바닥값부터(난수 0 → 10)
    other = type('R', (), {'choices': lambda s, xs, weights: [xs[3] if isinstance(xs[0], tuple) else 175],
                           'random': lambda s: 0.0})()
    assert hatch(eg, 1000 + 10 * EGG_STEP, other) == [(172, True)]
    assert eg['box'][-1] == {'id': 172, 'xp': 0, 'iv': [IV_FLOOR] * 3, 'shiny': True}
    assert 172 in eg['caught'] and 172 in eg['shiny'] and not eg['eggs'] and eg['news'][-1]['kind'] == 'hatch'
    assert eg['super'] == 1 and eg['news'][-1]['arg'] == '172*|super:1'  # 포켓몬과 함께 덤 볼 하나
    assert sum(w for _, _, w in EGG_BONUS) == 100 and ball_name('balls', '2') == ('몬스터볼 2개', '2 Poké Balls')
    # 하이퍼볼: 보상받은 날이 3일 연속이면(3·6·9일째) — 하루 빠지면 처음부터. 알은 이제 여기서 주지 않는다
    sd = tempfile.mkdtemp()
    for j, d in enumerate(('2026-11-01', '2026-11-02', '2026-11-03', '2026-11-05', '2026-11-06', '2026-11-07',
                           '2026-11-08', '2026-11-09')):
        os.makedirs(f'{sd}/s{j}')
        with open(f'{sd}/s{j}/state.json', 'w') as f:
            json.dump({'name': f's{j}', 'state': 'done'}, f)
        with open(f'{sd}/s{j}/timeline.jsonl', 'w') as f:
            f.write(json.dumps({'at': f'{d}T03:00:00Z', 'state': 'done', 'detail': 'pushed', 'text': '…'}) + '\n')
    feed._cache.clear()
    ew = new_state()
    ew['reward_since'] = '2026-10-01'
    ew['weekly'] = {'key': week_key(), 'kind': 'hatch', 'n': 0, 'done': False}  # 실제 이번 주 과제가 'ship' 이면 상이 섞인다
    assert reward(ew, sd) == 8 and ew['hyper'] == 2 and not ew['eggs']  # 1~3일 · 4일 빠짐 · 5~7일 → 하이퍼볼 둘 · 8·9일은 4·5일째
    assert sum(1 for n in ew['news'] if n['kind'] == 'streak') == 2
    # 알: 잡을 때 EGG_CATCH 확률로(가득 차면 못 받는다)
    ca = new_state()
    ca['caught'] = [1]
    ca['wild'] = {'id': 25, 'balls': 3}
    assert throw(ca, 0, type('R', (), {'random': lambda s: 0.05})()) == 'caught' and len(ca['eggs']) == 1  # 0.05 < 0.1 → 알
    ca['wild'] = {'id': 26 if 26 in DEX else 27, 'balls': 3}
    assert throw(ca, 0, type('R', (), {'random': lambda s: 0.0})()) == 'caught' and len(ca['eggs']) == 2  # 또 알
    ca['eggs'] = ca['eggs'][:1]
    ca['wild'] = {'id': 19, 'balls': 3}
    assert throw(ca, 0, type('R', (), {'random': lambda s: 0.5})()) == 'caught' and len(ca['eggs']) == 1  # 0.5 ≥ 0.1 → 알 없음
    # 주간 과제: 주 번호로 정해지고, 그 종류만 세며, 목표를 채우면 한 번만 상
    wk = new_state()
    wk['weekly'] = {'key': '2026-W43', 'kind': 'catch', 'n': 0, 'done': False}  # 세는 종류로 고정(ship 은 날짜로 센다)
    w = weekly(wk, '2026-W43')
    kind, goal = w['kind'], next(g for k, g, _, _ in WEEKLY if k == w['kind'])
    other = next(k for k, *_ in WEEKLY if k != kind)
    bump(wk, other, key='2026-W43')
    assert wk['weekly']['n'] == 0
    for _ in range(goal):
        bump(wk, kind, key='2026-W43')
    assert wk['weekly']['done'] and wk['hyper'] == 2 and wk['super'] == 3 and wk['news'][-1]['kind'] == 'weekly'
    assert wk['candy'] == 1  # 이상한사탕은 매주 1개
    bump(wk, kind, key='2026-W43')
    assert wk['hyper'] == 2  # 두 번 주지 않는다
    assert weekly(wk, '2026-W44')['n'] == 0 and not wk['weekly']['done']  # 다음 주는 새 과제
    sw = new_state()
    sw['rewarded'], sw['weekly'] = ['2026-10-19', '2026-10-20', '2026-10-25', '2026-10-26'], {'key': '2026-W43', 'kind': 'ship', 'n': 0, 'done': False}
    assert weekly(sw, '2026-W43')['n'] == 3  # ship 은 보상받은 날 중 이번 주(월~일) 날짜 수
    assert week_key(datetime(2026, 10, 26)) == '2026-W44' and week_key(datetime(2026, 10, 25)) == '2026-W43'  # 월요일에 바뀐다
    # 다음 세대: 도감 완성 또는 사천왕 클리어 — 야생은 열린 세대 중 최신부터, 다 잡았으면 이전 세대
    og = new_state()
    og['caught'] = [n for n in DEX if gen(n) == 1 and wild_ok(n)]  # 1세대 야생만 다 잡고 진화형은 남음
    assert opened_gen(og) == 1 and current_gen(og) == 1
    og['league'] = {'1': '2026-10-26'}
    assert opened_gen(og) == 2 and current_gen(og) == 1 and all(gen(n) == 2 for n in wild_pool(og))
    assert gym_gens(og) == range(1, 3) and any(gen(n) == 2 for n, _ in egg_pool(og))
    og['caught'] += [n for n in DEX if gen(n) == 2 and wild_ok(n)]  # 2세대 야생을 다 잡아도 진화형이 남은 계열은 계속 2세대에서
    assert wild_pool(og) and all(gen(n) == 2 for n in wild_pool(og))
    # 이상한사탕: 진화할 모습이 있으면 경험치와 상관없이 바로 진화, 없으면 쓰지 않는다
    cd = new_state()
    cd['box'], cd['partner'], cd['candy'], cd['caught'] = [{'id': 10, 'xp': 0}], 0, 1, [10]
    assert use_candy(cd, 0) == 11 and cd['candy'] == 0 and cd['box'][0]['id'] == 11 and 11 in cd['caught']
    assert use_candy(cd, 0) is None  # 사탕이 없다
    cd['candy'], cd['box'] = 1, [{'id': 12, 'xp': 0}]
    assert use_candy(cd, 0) is None and cd['candy'] == 1  # 버터플은 더 진화하지 않는다 → 사탕은 그대로
    assert ball_name('candy', 1) == ('이상한사탕 1개', '1 Rare Candy') and ball_name('candy', 2)[1] == '2 Rare Candies'
    # 도감 힌트: 잡은 건 빈칸, 전설·진화·야생 · 요약은 남은 것을 셋으로 나눈다
    dh = new_state()
    dh['caught'], dh['seen'] = [1], [1, 2]
    assert dex_hint(dh, 1) == '' and L('진화', 'evolve') in dex_hint(dh, 2) and L('이상해씨', 'Bulbasaur') in dex_hint(dh, 2)
    assert L('전설', 'legendary') in dex_hint(dh, 150) and dex_hint(dh, 19) == L('야생', 'wild')
    left1 = [n for n in DEX if gen(n) == 1 and n != 1]
    sm = dex_summary(dh, 1)
    nums = [int(x) for x in re.findall(r'\d+', sm.split(L('지금', 'in the'))[0])]
    assert sum(nums) == len(left1), (sm, len(left1))
    assert streak(ew, '2026-11-09') == 5 and streak(ew, '2026-11-10') == 5 and streak(ew, '2026-11-11') == 0
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
    assert toggle_team(gs, 0) and gs['team'] == [0] and team_of(gs)[0] == (0, 7, 15 + min(_battle.XP_LEVEL_CAP, 3000 // _battle.XP_PER_LEVEL))
    for k in range(1, 7):
        toggle_team(gs, k)
    assert len(gs['team']) == 6 and 6 not in gs['team']  # 7번째는 못 넣는다
    toggle_team(gs, 3)
    assert gs['team'] == [0, 1, 2, 4, 5]
    gs['team'] = [0]
    assert fight(gs, ENCOUNTER_EVERY, gd, 1, 0)[0] is None and gs['used'] == 0  # 탐색 기회 1번뿐
    assert fight(gs, 4 * ENCOUNTER_EVERY, gd, 2, 0)[0] is None and gs['used'] == 0  # 꼬부기(1세대)만 있는 팀은 2세대 체육관에 못 나간다
    assert team_of(gs, 2) == [] and team_of(gs, 1)[0][1] == 7 and fighters(gs, team_of(gs, 1))[0][2] == (0, 0, 0)
    won, ev, first = fight(gs, 4 * ENCOUNTER_EVERY, gd, 1, 0, random.Random(1), today='2026-10-21')
    assert won and first and gs['gym'] == {'gym:1-0': '2026-10-21'} and gs['hyper'] == 1 and gs['used'] == GYM_COST
    assert gs['box'][0]['bxp'] == 3000 + GYM_WIN_XP and ev[0][0] == 'send' and fight_line(ev[-1])
    won, ev, first = fight(gs, 4 * ENCOUNTER_EVERY, gd, 1, 0, random.Random(1))
    assert won and not first and gs['hyper'] == 1  # 다시 이기면 하이퍼볼은 없다(처음 한 번만)
    assert fight_state(ev, len(ev))['foe'][1] == 0
    gs['gym'].update({f'gym:1-{i}': '2026-10-21' for i in range(8)})
    eggs = len(gs['eggs'])
    assert 'conquer1' in check_badges(gs) and len(gs['eggs']) == eggs + 1 and gs['master'] == 1  # 지방 정복 → 마스터볼과 알
    gs['league'] = {'1': '2026-10-21'}
    assert 'champ1' in check_badges(gs) and gs['master'] == 2 and gs['hyper'] == 1  # 챔피언 → 마스터볼(세대당 2개)
    # 도감 상세 배틀 정보: 꼬마돌(바위/땅) — 물·풀 ×4, 전기 무효
    BATTLE_DATA[:] = [{'stats': {74: [40, 80, 100, 30, 30, 20]}, 'types': {74: [6, 5]},
                       'eff': {'11,6': 2.0, '11,5': 2.0, '12,6': 2.0, '12,5': 2.0, '13,5': 0.0, '10,6': 0.5, '1,6': 0.5},
                       'tnames': {1: ['노말', 'Normal'], 10: ['불꽃', 'Fire'], 11: ['물', 'Water'], 12: ['풀', 'Grass'], 13: ['전기', 'Electric']}}]
    bi = new_state()
    bi['box'] = [{'id': 74, 'xp': 0, 'bxp': 500}]
    lines = battle_info(bi, 74)
    assert lines[0].endswith(f'(300){L(" · 가방 Lv", " · bag Lv")}{15 + 500 // _battle.XP_PER_LEVEL}') and L('물(×4)', 'Water(×4)') in lines[1]
    assert L('무효 전기', 'Immune Electric') in lines[2] and L('불꽃', 'Fire') in lines[2]
    BATTLE_DATA.clear()
    # 방향키로 버튼 고르기: ←→ 앞뒤(끝에서 돌아옴), ↑↓ 다른 줄에서 가로로 가장 가까운 것
    nb = [(5, 1, 10, 'throw', ''), (5, 12, 20, 'super', ''), (5, 22, 30, 'run', ''),
           (9, 1, 8, 'dex', ''), (9, 10, 17, 'box', ''), (9, 19, 28, 'close', '')]
    K = curses
    assert move_focus(nb, 'throw', K.KEY_RIGHT) == 'super' and move_focus(nb, 'throw', K.KEY_LEFT) == 'close'
    assert move_focus(nb, 'super', K.KEY_DOWN) == 'box' and move_focus(nb, 'close', K.KEY_UP) == 'run'
    assert move_focus(nb, 'run', K.KEY_UP) == 'run' and move_focus(nb, 'gone', K.KEY_RIGHT) == 'super'
    assert move_focus([], None, K.KEY_RIGHT) is None
    # 배틀 경험치 진행도: 50 마다 1레벨, 상한이면 (최대)
    assert xp_text({'id': 1, 'bxp': 60}) == '(10/50)' and xp_text({'id': 1, 'bxp': 10**6}) == L('(최대)', '(max)')
    assert box_level({'id': 1, 'bxp': 60}) == 16  # 이상해씨 15 + 60 // 50
    # 이전 세대 섞기: 1세대만 열렸으면 없음, 2세대가 열리면 탐색의 약 20%가 1세대(잡은 종·전설 포함)
    real_forms = dict(FORMS)  # 리전폼은 받아 둔 파일과 상관없이 정해 둔 셋으로 시험
    FORMS.clear()
    FORMS.update({10091: (19, 'alola'), 10092: (20, 'alola'), 10107: (52, 'alola'), 10108: (53, 'alola'), 10161: (52, 'galar'),
                  10169: (144, 'galar'), 10252: (128, 'paldea-aqua-breed'), 10233: (157, 'hisui')})
    try:
        assert old_pool(new_state()) == []
        o2 = new_state(); o2['league'] = {'1': True}
        op = old_pool(o2)
        assert op and all(gen(n) == 1 for n in op) and 1 in op and 150 in op
        assert {10091, 10169, 10252} <= set(op) and 10233 not in op  # 2세대 종(블레이범)의 폼은 2세대가 지나야
        r, hits = random.Random(3), 0
        for _ in range(2000):
            o2['wild'], o2['used'] = None, 0
            hits += gen(sp(explore(o2, 10**12, r)[0])) == 1
        assert 300 < hits < 500, hits
        # 폼 이름 · 데이터 거르기 · 그림 경로
        assert name(10091) == L(f'알로라 {DEX[19][1]}', f'Alolan {DEX[19][6]}')
        assert name(10252) == L(f'팔데아 {DEX[128][1]}(워터종)', f'Paldean {DEX[128][6]} (Aqua Breed)')
        rows = [{'pokemon_id': p, 'form_identifier': f, 'is_battle_only': b} for p, f, b in
                [('10091', 'alola', '0'), ('10093', 'totem-alola', '0'), ('10099', 'alola-cap', '0'), ('10178', 'galar-zen', '1'),
                 ('10177', 'galar-standard', '0'), ('10252', 'paldea-aqua-breed', '0'), ('10033', 'mega', '0')]]
        mons = [{'id': p, 'species_id': s} for p, s in [('10091', 19), ('10093', 20), ('10099', 25), ('10178', 555),
                                                        ('10177', 555), ('10252', 128), ('10033', 3)]]
        assert _pokedata.build_forms(rows, mons) == [[10091, 19, 'alola'], [10177, 555, 'galar-standard'],
                                                     [10252, 128, 'paldea-aqua-breed']]
        assert _pokedata._src('form:10091') == '10091' and _pokedata._url('form:10091').endswith('/pokemon/10091.png')
        # 만나기 → 잡기(폼 번호로 가방에, 도감 숫자는 그대로) → 다시 나와도 만나서 잡는다
        class Pick:  # 이전 세대 쪽을 고르고, 그 안에서 정한 폼을 · 잡기·진화 갈래는 첫 번째
            def __init__(self, n): self.n = n
            def random(self): return 0.0
            def choice(self, seq): return self.n if self.n in seq else seq[0]
        fm = new_state(); fm['league'] = {'1': True}; fm['balls'] = 0
        assert explore(fm, ENCOUNTER_EVERY, Pick(10091)) == (10091, 0)
        assert fm['wild'] == {'id': 19, 'form': 10091, 'balls': BALLS} and fm['forms_seen'] == [10091]
        assert throw(fm, ENCOUNTER_EVERY, Pick(10091)) == 'caught'
        assert [m['id'] for m in fm['box']] == [10091] and fm['forms'] == [10091] and fm['caught'] == [] and fm['partner'] == 0
        assert 'form1' in check_badges(fm) and 'form_all' not in fm['badges']
        assert explore(fm, 2 * ENCOUNTER_EVERY, Pick(10091)) == (10091, 0) and fm['wild']['form'] == 10091
        fm['wild'] = None
        assert explore(fm, 3 * ENCOUNTER_EVERY, Pick(10169)) == (10169, 0)  # 가라르 프리져 — 전설이라 하이퍼볼부터
        assert throw(fm, 3 * ENCOUNTER_EVERY, Pick(10169)) == 'needhyper'
        # 종이 정하는 값은 원래 종으로 · 진화는 같은 지방 모습으로(보통 모습과 섞이지 않게) · 지방 전용 진화형
        assert gen(10091) == 1 and depth(10091) == 0 and depth(10092) == 1 and dupe_balls(10091) == dupe_balls(19)
        assert evo_next(10091) == [10092] and evo_next(10092) == [] and 10092 not in evo_next(19)
        assert evo_next(10107) == [10108] and 863 in evo_next(10161) and not {53, 10108} & set(evo_next(10161))
        assert need_xp(10091) == STAGE_XP[0] and need_xp(10092) is None
        fm['wild'] = None
        assert evolve(fm, 10**9) == 10092 and fm['box'][0]['id'] == 10092 and 10092 in fm['forms'] and fm['caught'] == []
        assert evo_status(fm, 10**9) == ('final',) and box_level(fm['box'][0]) == _battle.level(1, 0)
        fm['team'] = [0]
        assert team_of(fm, 1) == [(0, 10092, box_level(fm['box'][0]))]  # 배틀엔 폼 번호 — 종족값·타입은 그 모습 것
        # 그림 번호: 리전폼은 'form:번호', Kitty 이미지 번호는 정수
        assert art_of(fm['box'][0]) == 'form:10092' and art_of({'id': 25, 'shiny': True}) == 25 + _pokedata.SHINY
        assert partner_id_of(fm) == 'form:10092' and _pokedata.img_id('form:10092') >= 300000 and _pokedata.img_id(25) == 25
        # 가방에 들어가기 전에 잡은 폼은 한 번만 가방으로(박사에게 보낸 뒤 되살아나지 않게)
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            old = new_state(); old['forms'] = [10091]
            save(old, tmp)
            mig = load(tmp)
            assert [m['id'] for m in mig['box']] == [10091] and 'iv' in mig['box'][0] and mig['forms_boxed']
            mig['box'] = []
            save(mig, tmp)
            assert load(tmp)['box'] == []
    finally:
        FORMS.clear()
        FORMS.update(real_forms)
    # 합체: 큐레무(가방 1) + 제크로무·레시라무 — 동료인 상대는 못 쓰고, 개체값 좋은 상대를, 아직 없는 모습을 먼저
    fu = new_state()
    fu['box'] = [{'id': 25, 'xp': 0, 'iv': [1, 1, 1]}, {'id': 646, 'xp': 5, 'bxp': 120, 'iv': [9, 9, 9]},
                 {'id': 644, 'xp': 0, 'iv': [1, 1, 1]}, {'id': 644, 'xp': 0, 'iv': [15, 15, 15]}, {'id': 643, 'xp': 0, 'iv': [2, 2, 2]}]
    fu['partner'], fu['team'] = 4, [1, 3]
    assert fuse_options(fu, 0) == [] and fuse_options(fu, 1) == [(10022, 3)]  # 레시라무(4)는 동료라 못 쓴다
    assert change_options(fu, 1) == [(10022, ('mon', 3), True, '')] and change(fu, 1, 0) == 10022
    assert [m['id'] for m in fu['box']] == [25, 10022, 644, 643] and 'fused' not in fu['box'][1]  # 상대는 사라진다(분리 없음)
    assert fu['partner'] == 3 and fu['team'] == [1] and fu['box'][1]['bxp'] == 120  # 번호 당김 · 팀에 있던 상대는 빠짐 · 본체 경험치 유지
    assert name(10022) == L('블랙큐레무', 'Black Kyurem') and gen(10022) == 5 and evo_next(10022) == [] and art_of(fu['box'][1]) == 'form:10022'
    assert 'fuse1' in check_badges(fu) and send_away(fu, [1]) == (0, 0)  # 합체한 것은 박사에게 안 간다
    assert change_options(fu, 1) == [] and fuse_options(fu, 2) == []  # 합체한 것은 다시 못 바꾼다
    # 특수 모습: 연구 완료 → 메가스톤(X·Y), 그 뒤 5마리 더 잡을 때마다 또 · 쓰는 건 그 세대가 열린 뒤 · 되돌릴 수 없다
    real_sp = dict(SPECIALS)
    SPECIALS.clear()
    SPECIALS.update({10034: (6, 'mega', 6, 'x', ''), 10035: (6, 'mega', 6, 'y', ''), 10196: (6, 'gmax', 8, '', ''),
                     10078: (383, 'primal', 6, '', ''), 10157: (800, 'ultra', 7, '', '')})
    try:
        mg = new_state()
        mg['box'], mg['partner'] = [{'id': 6, 'xp': 0, 'iv': [5, 5, 5], 'bxp': 300}], 0
        lv0 = box_level(mg['box'][0])
        assert [(f, ok) for f, _, ok, _ in change_options(mg, 0)] == [(10034, False), (10035, False), (10196, False)]
        for key in 'ccccc' + 'www':
            research_bump(mg, 6, key)
        assert mg['items'] == {'stone:10034': 1, 'stone:10035': 1} and mg['news'][-1]['kind'] == 'item'
        for _ in range(RESEARCH_CATCH):
            research_bump(mg, 6, 'c')
        assert mg['items'] == {'stone:10034': 2, 'stone:10035': 2}  # 다시 모은다
        assert change(mg, 0, 0) is None  # 6세대가 아직 안 열렸다
        mg['league'] = {str(g): '2026-10-30' for g in range(1, 6)}  # 5세대까지 사천왕 → 6세대 열림
        assert change(mg, 0, 0) == 10034 and mg['box'][0]['id'] == 10034 and mg['items']['stone:10034'] == 1
        assert mg['specials'] == [10034] and box_level(mg['box'][0]) == lv0 and name(10034) == L('메가리자몽 X', 'Mega Charizard X')
        assert change_options(mg, 0) == [] and item_name('stone:10035') == L('리자몽나이트Y', 'Charizardite Y')
        assert [ok for _, _, ok, _ in change_options({**mg, 'box': [{'id': 6, 'xp': 0}]}, 0)][2] is False  # 거다이맥스는 8세대
        ul = new_state()
        ul['box'], ul['items'], ul['league'] = [{'id': 10155, 'xp': 0}], {'stone:10157': 1}, {str(g): 'x' for g in range(1, 7)}
        assert change(ul, 0, 0) == 10157 and name(10157) == L('울트라네크로즈마', 'Ultra Necrozma')
        pr = new_state()
        raid_state(pr)
        pr['wild'] = {'id': 383, 'balls': RAID_BALLS, 'raid': True}
        assert throw(pr, 0, type('R', (), {'random': lambda s: 0.0})()) == 'caught' and pr['items'] == {'stone:10078': 1}
        assert item_name('stone:10078') == L('주홍구슬', 'Red Orb') and item_name('soup') == L('다이수프', 'Max Soup')
    finally:
        SPECIALS.clear()
        SPECIALS.update(real_sp)
    # 연구: 잡기 5 · 진화 1 · 배틀 승리 3 을 다 채우면 ★ 와 슈퍼볼 2 — 한 번만
    rs = new_state()
    assert research_goals(1) == {'c': 5, 'e': 1, 'w': 3} and research_goals(150) == {'c': 1, 'e': 0, 'w': 3}
    for key in 'ccccce' + 'ww':
        research_bump(rs, 1, key)
    assert not research_done(rs, 1) and rs['super'] == 0 and '2/3' in research_text(rs, 1)
    research_bump(rs, 1, 'w')
    assert research_done(rs, 1) and rs['researched'] == [1] and rs['super'] == 2 and rs['news'][-1]['kind'] == 'research'
    research_bump(rs, 1, 'w')
    research_bump(rs, 10091, 'c')  # 리전폼 번호는 세지 않는다
    assert rs['super'] == 2 and '10091' not in rs['research'] and research_text(rs, 1).startswith(L('★', '★'))
    lr2 = tempfile.mkdtemp()
    save({**new_state(), 'research': {}, 'box': [{'id': 1, 'xp': 0}, {'id': 1, 'xp': 0}]}, lr2)
    assert load(lr2)['research'] == {'1': {'c': 2}}  # 옛 가방은 마릿수를 잡은 횟수로(상 없이)
    # 우두머리: 볼 3번 안에 못 잡으면 보유 볼이 남아도 도망
    al = new_state()
    al['wild'], al['balls'] = {'id': 19, 'balls': BALLS, 'alpha': True, 'tries': 0}, 10
    never2 = type('R', (), {'random': lambda s: 0.99})()
    assert [throw(al, 0, never2) for _ in range(3)] == ['missed', 'missed', 'fled'] and al['wild'] is None
    # 레이드: 이번 주 보스(열린 세대의 전설) · 목록 맨 위 · 이기면 레이드볼 3개로만 · 놓치면 이번 주 끝
    rd = new_state()
    g_r, boss = raid_boss(rd)
    assert g_r == 1 and DEX[boss][5] == 1 and raid_boss(new_state()) == (g_r, boss) and gym_rows(rd)[0] == (1, 'R')
    rd['box'], rd['team'] = [{'id': 7, 'xp': 0, 'bxp': 3000, 'iv': [15] * 3}, {'id': 152, 'xp': 0, 'iv': [0] * 3}], [1, 0]
    assert [n for _, n, _ in team_of(rd)] == [152, 7]  # 레이드엔 다른 세대(치코리타)도 나간다
    gd2 = {'stats': {boss: [1] * 6, 7: [200] * 6, 152: [200] * 6}, 'types': {boss: [11], 7: [11], 152: [12]}, 'eff': {}, 'tnames': {}}
    won, ev, first = fight(rd, 4 * ENCOUNTER_EVERY, gd2, 1, 'R', random.Random(1))
    assert won and not first and rd['wild'] == {**rd['wild'], 'id': boss, 'balls': RAID_BALLS, 'raid': True} and rd['raid']['won']
    assert rd['research']['7']['w'] == 1 and fight(rd, 4 * ENCOUNTER_EVERY, gd2, 1, 'R')[0] is None  # 이번 주는 한 번만
    assert rd['items'] == {'soup': 1}  # 레이드 승리마다 다이수프
    rd['hyper'] = 5
    assert throw(rd, 0, never2, 'hyper') == 'raidonly' and rd['hyper'] == 5  # 가진 볼은 못 쓴다
    assert [throw(rd, 0, never2) for _ in range(RAID_BALLS)] == ['missed', 'missed', 'fled'] and rd['wild'] is None
    assert rd['raid']['done'] and gym_rows(rd)[0] != (1, 'R')
    rc = new_state()
    rc['box'], rc['team'], rc['wild'] = [{'id': 7, 'xp': 0, 'bxp': 3000, 'iv': [15] * 3}], [0], {'id': 19, 'balls': BALLS}
    assert fight(rc, 4 * ENCOUNTER_EVERY, gd2, 1, 'R', random.Random(1))[0] and rc['raid']['pending'] and rc['wild']['id'] == 19
    rc['wild'] = None  # 하던 야생이 끝나면 레이드 보스가 나온다
    raid_release(rc)
    lucky2 = type('R', (), {'random': lambda s: 0.0})()
    assert rc['wild']['raid'] and throw(rc, 0, lucky2) == 'caught' and rc['raids'] == 1 and rc['box'][-1]['id'] == boss
    assert min(rc['box'][-1]['iv']) >= IV_FLOOR and 'raid1' in check_badges(rc)
    # 줄 접기: 폭 안에서 빈칸·쉼표 뒤에서 접고, '·' 는 앞 낱말에 붙인다(한글은 2칸)
    assert fold('가나다 · 라마 · 바사', 12) == ['가나다 ·', '라마 · 바사'] and fold('a, b, c', 3) == ['a,', 'b,', 'c'] and fold('a, b, c', 4) == ['a,', 'b, c']
    assert all(sum(map(memo.cw, x)) <= 20 for x in fold('내 팀 메가니움 Lv39, 블레이범 Lv39, 장크로다일 Lv39, 토게틱 Lv27', 20))
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
