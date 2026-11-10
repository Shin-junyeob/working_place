#!/usr/bin/env python3
"""포켓몬 — Claude 를 쓴 만큼(누적 토큰) 포켓몬을 발견해 잡고, 한 마리를 데리고 다니며 진화시켜 세대별 도감을 채운다.

누적 토큰: 각 세션의 pane-tools mod 가 usage/<sid>.json 의 gained 에 적는 값(컨텍스트가 늘어난 만큼)을 모두 더한 것.
- 도감은 세대별(1~9세대). 데이터는 처음 열 때 PokeAPI 에서 받아 ~/.claude/pane-tools/pokedex.json 에 둔다(_pokedata.py). 그 세대 도감을 다 채우거나
  사천왕·챔피언을 이기고 그 세대 야생 종(전설·환상 포함)을 다 잡으면 다음 세대가 열리고(opened_gen — 모자라면 소식 genwait), 야생에선 열린 세대 중 가장 최근 세대가 나온다. 이상한사탕(주간 상)은 진화할 수 있는 포켓몬 아무나 바로 진화시킨다(가방에서).
- 나오는 순서: 스타팅·피카츄·이브이 → 일반(원작 포획률 높은 = 흔한 것부터) → 전설 → 환상. 앞쪽 WINDOW 마리 중 무작위 —
  후보가 전부 가방에 있으면 후보 전체에서(wild_odds). 탐색 OLD_GEN_RATE 는 이전 세대 전체 + 지금 세대에서 계열을 다 잡은 종(old_pool) — 전설·환상은 한 종마다 OLD_LEGEND_EACH(old_pick).
- ENCOUNTER_EVERY 토큰마다 탐색 1회. 볼 BALLS 개 + 보유 볼, 다 빗나가면 도망(나중에 다시 나온다). 잡으면 보유 볼 +1.
- 지금 가방에 있는 종은 다른 종의 1/10 확률로만 나온다(BOXED_WEIGHT). 나오면 똑같이 잡을 수 있다 — 같은 종이라도 개체값(HP·공·방·특공·특방·스피드
  여섯, 0~15, roll_iv — 목록엔 % 만)이 달라 골라 키운다. 남는 것은 [박사에게] 보내면 급에 따라 몬스터볼 1~5개(dupe_balls) — [정리]는 같은 종 중
  개체값·경험치가 가장 좋은 것만 남기고 한꺼번에. 동료·팀·이로치·우두머리와 재료로 만든 모습(made — 합체·메가 등)은 보내지 않는다(send_away).
- 동료는 한 마리. 데리고 있는 동안 쌓인 토큰이 경험치 — STAGE_XP 를 넘으면 진화. 아직 안 열린 세대로의 진화는 그 세대가 열린 뒤.
  갈래가 여럿이면 아직 가방에 없는 모습을 먼저 고른다.
- 체육관·사천왕은 그 세대 포켓몬만 나간다(팀의 다른 세대는 빠진다) — 세대마다 팀을 새로 키운다. 상대는 레벨
  +OPP_LV_BONUS 와 개체값(체육관 7~14 · 사천왕 14 · 챔피언 15)을 가진다(_battle.py).
- 볼 네 가지: 몬스터볼 · 슈퍼볼(1.5배) · 하이퍼볼(2배) · 마스터볼(반드시 잡힘). 전설·환상은 하이퍼볼·마스터볼로만
  잡힌다(다른 볼은 쓰지 않고 알려만 준다). 마스터볼은 세대마다 두 개 — 8관 지방 정복과 사천왕·챔피언 첫 승리.
  체육관은 처음 이길 때마다 하이퍼볼 1개. [교환] → [몬스터볼]에서 볼을 위 단계로 바꾼다(TRADES — 몬스터볼 5 → 슈퍼볼,
  슈퍼볼 20 → 하이퍼볼, 하이퍼볼 5 → 마스터볼).
- 일한 보상 — 그날 push·PR 병합·배포가 든 completed 가 하나라도 있으면 탐색 +WORK_EXPLORES(하루 한 번, 기록은 feed.py 가 읽는
  ~/.claude/jobs 의 timeline), 주말이면 +WEEKEND_EXPLORES. 그런 날이 STREAK_DAYS 일 연속이면 탐색 +STREAK_BONUS 더 — 쉰 주말은
  연속을 끊지 않고, 일한 주말은 하루로 센다.
- 알: 야생 포켓몬을 잡을 때 EGG_CATCH 확률로 하나(최대 EGG_MAX), 지방 정복 때 하나. 알마다 받은 때(base)부터 따로 자라고, 메인 화면에 한 줄씩(egg_lines). 종류(egg_km, 2·5·7·10·12km)에 따라 덤을 더 준다(EGG_KM_BONUS · EGG_KM_SHINY).
- 주간 과제: 주마다(월요일) WEEKLY 에서 하나 — 이루면 WEEKLY_PRIZE.
- 리전폼(알로라·가라르·히스이·팔데아 모습, FORMS): 이전 세대 탐색(OLD_GEN_RATE)에 그 종의 세대가 지난 폼이 함께 나온다.
  잡으면 가방에 폼 번호(FORMS 의 키, 10000 위)로 들어가 진화·레벨·배틀을 한다 — 종족값·타입은 그 모습 것(battle.json),
  세대·진화 단계는 원래 종으로(sp). 같은 지방 모습으로 진화하고(evo_next), 지방 전용 진화형(REGIONAL_EVO)도 있다.
  도감 숫자에는 안 들어가고 st['forms'] 에 따로 모인다(도감 마지막 쪽에 목록).
- 합체(FUSIONS): 큐레무·네크로즈마·버드렉스 연구를 끝내면 합체 도구(FUSE_ITEMS — 써도 남는다)를 받고, 가방에서 도구 → 기본 포켓몬 — 레시라무·제크로무 / 솔가레오·루나아라 /
  블리자포스·레이스포스 하나를 재료로 써서(사라진다 — 팀 밖·개체값 낮은 것부터) 합체 모습이 된다. 레벨·개체값은 기본(큐레무 등)을
  따르고, 그 모습의 타입·종족값으로 싸운다. 분리는 없다(2026-10-30).
- 특수 모습(SPECIALS — 메가진화·원시회귀·울트라버스트·거다이맥스): 세대가 열리면(6·7·8·9) 그 포켓몬 + 아이템(메가스톤은 연구 완료,
  구슬은 레이드 포획, 다이수프는 레이드 승리)으로 영구히 바뀐다(change_options · change). 가방에서 아이템 → 포켓몬(item_targets). 이로치는 이로치 그림,
  연구는 그 모습 도감에 따로(만들기 1 · 배틀 승리). 메가 지가르데는 도트 그림이 없어 HOME 그림(_pokedata._fetch).
- 연구 레벨: 종마다 잡기 RESEARCH_CATCH(전설·환상·진화로만 얻는 종 1 — 진화해서 얻어도 잡기) · 진화 1(진화형이 있으면) · 배틀 승리 RESEARCH_WIN 을 채우면 도감 ★ 와
  RESEARCH_PRIZE(research_bump). 우두머리: 탐색의 ALPHA_RATE 로 붉은 눈의 큰 개체 — 포획률 절반, 볼 ALPHA_TRIES 번 안에 못 잡으면
  도망, 잡으면 개체값 최소 ALPHA_IV · 배틀 능력치 ×ALPHA_BOOST(alpha_x) · 박사에게·정리로 안 보낸다. 레이드: 주마다 열린 세대의 전설 하나(raid_boss)가 체육관 목록 맨 위 — 모든 세대 팀으로 HP
  ×RAID_HP 보스를 이기면 레이드볼 RAID_BALLS 개로만 잡을 기회(가진 볼은 못 쓴다), 잡든 놓치든 그 주는 끝.
  이기고 못 만난 보스는 월요일이 지나도 한 번 나온다(raid_state 의 late) — 레이드 야생은 자기 주(week)를 들고 다닌다(raid_done).
- 배틀 타워(챔피언 뒤, 체육관 목록의 'T' 줄): 팀 앞 TOWER_SIZE 마리, 시작할 때만 탐색 TOWER_COST 번, 지기 전까지 연승
  (tower_state · tower_opp — 상대는 7연승마다 레벨 +TOWER_LV_STEP·개체값 +1, 상한 없음). TOWER_PRIZES 마다 볼과 병뚜껑.
  병뚜껑(cap 은색 · gcap 금색)은 가방에서 쓰는 특훈 — 고른 개체값(여섯 중) 하나 +1 / 15로(change_options 의 ('iv', k) · ('ivmax', k)).
- 메타몽(DITTO): 야생에선 다른 일반 포켓몬으로 변신해 나오고(disguises · wild['disguise'] · shown), 잡아야 정체가 드러난다.
  이로치 메타몽도 변신한 모습은 보통 색 — 이로치인 것은 정체와 함께 드러난다.
  조로아·조로아크(히스이 포함, ZORUA)는 팀 마지막 포켓몬(없으면 동료)의 환영으로 나온다(illusion) — 같은 disguise 구조.
- 이로치: 탐색마다 SHINY_RATE(리전폼도 — 우두머리도 같다). 같은 종이라도 이로치와 기본 모습은 다른 포켓몬으로 친다(가방 1/10 · 진화 갈래 고르기 모두 따로). 이름은 금색.
- 화면(2026-11-05 개편): 메인은 맨 위 장식(SHOWCASE_MAX) · 동료(그림·이름·진화 게이지, Enter 면 동료 고르기) · 팀 3×2 칸(크기는 패널에 맞춰 team_layout,
  Enter 면 그 자리 고르기 slotpick — 이름 찾기·Tab 정렬, set_slot) · 오른쪽 네모 버튼(side_buttons — 탐색·도감·가방·교환·훈장·체육관·닫기).
  풀숲 만남은 따로(view 'wild'): 가운데 포켓몬(big_art — Sixel 은 SIXEL_SCALE 배로 그려져 그만큼 당긴다) 위에 고른 볼의 포획 확률
  (catch_chance — throw 와 같은 식), 오른쪽 볼 고르기(ball_choices · default_ball — 마스터볼은 저절로 안 고른다), 아래 [던지기]·[도망].
  가방은 아이템 목록(bag_items) → Enter → 쓸 포켓몬(item_targets) → 두 번 눌러 쓴다.
- 조작은 방향키·Enter·q: 메인·만남은 위치대로 움직이고(move_geo — ↑↓ 같은 열, ←→ 옆 열), 목록 화면은 ↑↓ 로 줄, ←→ 로 아래 버튼.
  도감은 ←→ 가 세대, 도감 상세는 ←→ 가 앞뒤 포켓몬. 교환은 Tab 정렬(SORTS, PC 설정에 저장).
  화면은 패널 폭에 맞춘다 — 긴 줄은 para/fold 로 접고, 80칸 미만이면 버튼 여백을 줄인다. 마우스 클릭도 된다.
상태는 ~/.claude/pane-tools/pokemon.json — 못 읽으면 _broken 상태를 돌려주고 save() 가 쓰지 않는다(깨진 JSON 은 .bad 사본).
허브는 summary() 로 동료를 보여 준다. 메인 화면은 동료·팀·알 그림을 장식 배지와 한 번에 놓는다(mon_art · join_art).
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
import shutil
import sys
import time
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
SHIP = re.compile(r'(?<![a-z])PRs?(?![a-z])|병합|배포|(?<![a-z])(merge|deploy|push)|푸시', re.I)  # completed 요약에 이게 있으면 '내보낸 일'
# 영문자만 경계로 — prefix·approval 의 pr 은 빼고(2026-10-30, 실제 기록 37건), 'PR을' 처럼 한글이 붙은 건 잡는다
NEEDS_NAG = 600  # needs 를 이만큼(초) 넘게 두면 동료가 재촉한다
# 일한 보상(2026-11-11 사용자 — 슈퍼볼 1개 · 3일 연속 하이퍼볼에서 바꿈): 그날 탐색 +1, 평일 5일 연속(월~금이면 한 주)마다 +5 더.
# 주말은 보통 쉬어서 쉬어도 연속을 끊지 않고, 주말에 일하면 주말 부스트 — 탐색 +2 에 연속도 하루 센다(같은 날 사용자).
# 받은 탐색은 st['extra'] 에 쌓여 tickets 에 더해진다.
WORK_EXPLORES, WEEKEND_EXPLORES, STREAK_DAYS, STREAK_BONUS = 1, 2, 5, 5
ALPHA_RATE, ALPHA_IV, ALPHA_TRIES = 0.01, 12, 3  # 우두머리: 탐색 100번에 1번 · 개체값 최소 12 · 볼 3번 안에 못 잡으면 도망
ALPHA_BOOST = 1.1  # 우두머리 배틀 능력치 배수(2026-11-06 사용자)
# 레이드 보스 HP 배수 · 레이드볼 · 도전 1번에 쓰는 탐색. 레이드는 모든 세대가 나간다 — 모든 세대 최종 진화형 중 고른 팀을 보스 레벨에 맞춰
# 1~3세대 전설 17마리로 잰 승률(2026-10-30): ×40 개체값 7 49%·15 57%, ×48 40%·49%, ×56 28%·28%
RAID_HP, RAID_BALLS, RAID_COST = 48, 3, 2
# 배틀 타워(챔피언 뒤): 팀 앞 TOWER_SIZE 마리로 지기 전까지 연승. 시작할 때만 탐색 TOWER_COST 번. 상대는 7연승마다 한 단계 —
# 레벨 TOWER_LV0 + 단계 × TOWER_LV_STEP(상한 없이 — 다 키운 팀도 언젠가 진다), 개체값 6 + 단계(15까지). 7번째·49번째는 강한 상대.
TOWER_SIZE, TOWER_COST, TOWER_LV0, TOWER_LV_STEP = 3, 2, 45, 6  # 2026-11-04 측정: 기대 연승 다 키운 팀 58 · Lv79 사용자 팀 44 · Lv60 팀 27
TOWER_PRIZES = [(7, [('super', 3), ('cap', 2)]), (21, [('hyper', 2)]), (49, [('master', 1), ('gcap', 2)])]  # n 연승마다 — 은색 7개 ≈ 금색 1개, 개체값 6칸이라 둘씩
RESEARCH_CATCH, RESEARCH_WIN, RESEARCH_PRIZE = 5, 3, ('super', 2)  # 연구: 잡기 5(전설·환상 1) · 진화 1(진화형이 있으면) · 배틀 승리 3
IV_FLOOR = 10  # 알·전설·환상은 개체값이 최소 이만큼(포켓몬고처럼)
# 이전 세대 탐색에서 전설·환상 한 종이 나올 몫 — 후보 수와 상관없이 같게(2026-11-09 사용자). 처음엔 가중치(다른 종의 10배)라
# 1세대처럼 후보가 몇십 종일 때는 섞기 탐색 넷 중 하나가 같은 전설이었다(파이어가 잡은 뒤에도 연달아). 값은 그 10배가 8세대에서
# 내던 몫(후보 529 · 전설·환상 68 → 한 종 0.88%, 전체 60%) — 8세대쯤 특정 전설 재회 약 15일이라는 그때 결정은 그대로.
OLD_LEGEND_EACH = 0.0088
OLD_LEGEND_CAP = 0.6  # 전설·환상 전체 몫 상한 — 전설이 많아져도 섞기 탐색의 대부분을 차지하지 않게
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
EGG_KM_BONUS = {7: [('super', 1)], 10: [('hyper', 1)], 12: [('hyper', 2)]}  # 오래 걸리는 알일수록 덤을 더(EGG_BONUS 에 더해)
EGG_KM_SHINY = {12: 2}  # 12km 알은 이로치 확률 ×2
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
    regional_only = {c for cs in REGIONAL_EVO.values() for c in cs}  # 나이킹 등 — PokeAPI 는 보통 나옹에서 나온다고 적지만 지방 모습에서만(evo_next)
    for r in DEX.values():
        if r[3] and r[0] not in regional_only:
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
    """열린 가장 높은 세대 — 1세대부터, 도감을 다 채웠거나 사천왕·챔피언을 이기고 그 세대 야생 종(전설·환상 포함)을 다 잡은
    세대의 다음 세대가 열린다. 도감만으로는 진화로만 얻는 종 때문에 한 달씩 갇혔고(2026-10-27), 챔피언만으로는 넘긴 세대의
    전설·환상이 이전 세대 탐색에서 거의 안 나와 2년씩 걸렸다(2026-11-09 사용자) — 진화형은 넘긴 뒤에도 같은 속도로 채운다."""
    g = 1
    while g < GENS and (gen_done(st, g) or (str(g) in st.get('league', {}) and not wild_left(st, g))):
        g += 1
    return g


def wild_left(st, g):
    """g 세대에서 야생으로 잡을 수 있는데(wild_ok — 전설·환상 포함) 아직 못 잡은 종."""
    caught = set(st['caught'])
    return [n for n in DEX if gen(n) == g and wild_ok(n) and n not in caught]


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


def is_legend(n):
    """전설·환상인가 — 리전폼 전설(가라르 프리져 등)도 원래 종으로 판정(2026-11-09)."""
    return bool(DEX[sp(n)][5])


def old_pick(old, rng=random):
    """이전 세대 섞기에서 한 종 — 전설·환상은 한 종마다 OLD_LEGEND_EACH(전체는 OLD_LEGEND_CAP 까지), 나머지는 고르게."""
    legs = sum(1 for n in old if is_legend(n))
    rest = len(old) - legs
    share = min(OLD_LEGEND_CAP, OLD_LEGEND_EACH * legs) if rest else 1
    weights = [share / legs if is_legend(n) else (1 - share) / rest for n in old]
    return rng.choices(old, weights=weights)[0]


# 서식지(2026-11-10 사용자 — 레전드 아르세우스의 지역·낚시에서) — 탐색할 곳을 고르면 그 타입 포켓몬만 나온다. 메인 화면 h 로 바꾼다.
# 열여덟 타입이 모두 어딘가에 들어가게 나눴다. 타입 자료(BATTLE)가 아직 없으면 거르지 않는다.
HABITATS = (('all', '전체', 'All', ()),
            ('grass', '풀숲', 'Grass', (_battle.GRASS, _battle.BUG, _battle.NORMAL, _battle.POISON, _battle.FAIRY)),
            ('water', '물가', 'Water', (_battle.WATER, _battle.ICE)),
            ('cave', '동굴', 'Cave', (_battle.ROCK, _battle.GROUND, _battle.STEEL, _battle.FIGHTING, _battle.FIRE, _battle.DRAGON)),
            ('sky', '하늘', 'Sky', (_battle.FLYING, _battle.PSYCHIC, _battle.GHOST, _battle.DARK, _battle.ELECTRIC)))
TYPES = {}  # 번호 → 타입 번호들 — 포켓몬 화면이 배틀 자료를 읽으면 채운다


def habitat(st):
    """지금 고른 서식지 (키, 한국어, 영어, 타입들)."""
    return next((hb for hb in HABITATS if hb[0] == st.get('habitat')), HABITATS[0])


def in_habitat(st, n):
    """n 이 지금 서식지에 나오나 — '전체'거나 타입을 모르면 늘 나온다(리전폼은 그 모습의 타입)."""
    tys = habitat(st)[3]
    t = TYPES.get(n) or TYPES.get(sp(n))
    return not tys or not t or bool(set(t) & set(tys))


# 증표(소드·실드) — 야생이 MARK_RATE 로 하나 달고 나와 이름 앞에 칭호가 붙는다(가방 상세에 그림). 날씨·시간대 증표는 뺐다
# (시간에 따른 출현은 하지 않기로, 2026-11-05). 우두머리는 늘 우두머리 증표. 칭호는 우리말로 새로 지었다.
MARK_RATE = 0.02
MARKS = {'absent-minded': ('멍한', 'the Absent-Minded'), 'angry': ('화난', 'the Angry'), 'calmness': ('차분한', 'the Calm'),
         'charismatic': ('카리스마 있는', 'the Charismatic'), 'crafty': ('꾀 많은', 'the Crafty'), 'excited': ('신난', 'the Excited'),
         'ferocious': ('사나운', 'the Ferocious'), 'flustered': ('허둥대는', 'the Flustered'), 'humble': ('겸손한', 'the Humble'),
         'intellectual': ('똑똑한', 'the Clever'), 'intense': ('열정적인', 'the Intense'), 'jittery': ('안절부절못하는', 'the Jittery'),
         'joyful': ('즐거운', 'the Joyful'), 'kindly': ('상냥한', 'the Kind'), 'peeved': ('토라진', 'the Peeved'),
         'prideful': ('거만한', 'the Proud'), 'pumped-up': ('의욕 넘치는', 'the Pumped'), 'rowdy': ('시끌벅적한', 'the Rowdy'),
         'scowling': ('찌푸린', 'the Scowling'), 'slump': ('슬럼프에 빠진', 'the Slumping'), 'smiley': ('싱글벙글한', 'the Smiley'),
         'teary': ('눈물 많은', 'the Teary'), 'thorny': ('까칠한', 'the Prickly'), 'unsure': ('망설이는', 'the Unsure'),
         'upbeat': ('쾌활한', 'the Upbeat'), 'vigor': ('기운찬', 'the Vigorous'), 'zero-energy': ('기운 없는', 'the Drained'),
         'zoned-out': ('넋 나간', 'the Zoned-Out'), 'uncommon': ('붙임성 좋은', 'the Sociable'), 'rare': ('은둔하던', 'the Recluse'),
         'alpha': ('우두머리였던', 'the Former Alpha')}
MARK_WEIGHT = {'uncommon': 6, 'rare': 1, 'alpha': 0}  # 나머지 성격 증표는 1씩 — 붙임성은 흔하게, 은둔은 드물게


def roll_mark(rng=random):
    """야생이 달고 나올 증표 — MARK_RATE 로 하나, 아니면 None."""
    if rng.random() >= MARK_RATE:
        return None
    keys = list(MARKS)
    return rng.choices(keys, weights=[MARK_WEIGHT.get(k, 1) for k in keys])[0]


def titled(mark, nm):
    """증표 칭호를 붙인 이름 — '사나운 피카츄' · 'Pikachu the Ferocious'."""
    return L(f'{MARKS[mark][0]} {nm}', f'{nm} {MARKS[mark][1]}') if mark in MARKS else nm


def mark_name(mark):
    return L(f'{MARKS[mark][0]} 증표', mark.replace('-', ' ').title() + ' Mark')


# 리본(포켓몬 HOME 처럼 포켓몬마다) — 키 → (PokeAPI 그림, 한국어, 영어). 같은 리본은 한 번만.
CHAMP_RIBBON = {3: 'hoenn-champion-ribbon', 4: 'sinnoh-champion-ribbon', 6: 'kalos-champion-ribbon', 7: 'alola-champion-ribbon',
                8: 'galar-champion-ribbon', 9: 'paldea-champion-ribbon'}  # 그 밖의 세대는 champion-ribbon
RIBBONS = {**{f'champ{g}': (CHAMP_RIBBON.get(g, 'champion-ribbon'), f'{g}세대 챔피언 리본', f'Gen {g} Champion Ribbon') for g in range(1, 10)},
           'tower21': ('battle-tree-great-ribbon', '배틀 타워 21연승 리본', 'Tower 21-Win Ribbon'),
           'tower49': ('battle-tree-master-ribbon', '배틀 타워 49연승 리본', 'Tower 49-Win Ribbon'),
           'raid': ('legend-ribbon', '레이드 리본', 'Raid Ribbon'),
           'partner': ('best-friends-ribbon', '단짝 리본', 'Best Friends Ribbon'),
           'effort': ('effort-ribbon', '노력 리본', 'Effort Ribbon')}
def ribbon_how():
    return L('사천왕·챔피언을 이긴 팀원 · 배틀 타워 21·49연승 · 레이드를 이긴 팀원 · 동료로 진화 · 개체값 여섯을 모두 15로',
             'beat a league · Tower 21/49 wins · win a raid · evolve as partner · all six IVs at 15')


def give_ribbon(st, idxs, key):
    """가방 번호들에 리본 key — 이미 있는 포켓몬은 건너뛴다. 새로 받은 수(받았으면 동료가 알린다)."""
    got = [i for i in dict.fromkeys(idxs) if 0 <= i < len(st['box']) and key not in st['box'][i].get('ribbons', [])]
    for i in got:
        st['box'][i].setdefault('ribbons', []).append(key)
    if got:
        tell(st, 'ribbon', f'{key}|{mon_name(st["box"][got[0]])}|{len(got)}')
    return len(got)


def mon_name(m):
    """가방 포켓몬의 이름 — 지어 준 이름(닉네임)이 있으면 그것."""
    return m.get('nick') or name(m['id'])


NICK_MAX = 12  # 닉네임 최대 글자 수


def old_pool(st):
    """이전 세대(열린 세대보다 아래 전부)와 지금 세대에서 계열을 다 잡은 야생 종 — 잡은 종도 나온다(같은 모습이 가방에 있으면 볼로 바뀐다), 전설·환상 포함.
    모든 세대를 다 채웠으면 전 세대에서. 그 세대 종의 리전폼(FORMS 번호)도 함께 — 진화형 폼도 야생에서 바로."""
    cur = wild_pool(st)
    top = opened_gen(st) if cur else GENS + 1
    done = [n for n in DEX if gen(n) == top and wild_ok(n) and n not in cur]  # 지금 세대에서 계열을 다 잡은 종도 — 안 그러면
    # 그 세대를 다 채울 때까지 다시 못 만났다(이로치도 못 노림, 2026-11-09 사용자)
    return [n for n in DEX if gen(n) < top and wild_ok(n)] + done + [p for p, (sp, _) in FORMS.items() if gen(sp) < top]


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
    ('super1', '첫 일한 날', 'First work day', lambda st: (st['super_earned'] or 0) >= 1),
    ('super10', '일한 날 10', '10 work days', lambda st: (st['super_earned'] or 0) >= 10),
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
    ('gmax1', '첫 거다이맥스', 'First Gigantamax', lambda st: any(SPECIALS.get(p, (0, ''))[1] == 'gmax' for p in st.get('specials', [])))] + \
    [(f'tower{k}', f'타워 {k}연승', f'Tower {k} wins', (lambda k: lambda st: st.get('tower', {}).get('best', 0) >= k)(k)) for k in (7, 21, 49, 100)]


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
    pool, inbag = [n for n in wild_pool(st) if in_habitat(st, n)], boxed(st)
    fresh = [n for n in pool if n not in inbag and not evo_wild(n)][:WINDOW]
    if not fresh:  # 남은 게 전부 가방 속 종·이전 세대 진화형이면 그것들 전부에서 고르게 — 앞 WINDOW 마리만 쓰니
        return [(n, 1) for n in pool]          # 3세대 41종이 다 가방에 있을 때 스타팅 3종·포챠나만 돌아가며 나왔다(2026-11-09)
    front = pool[:pool.index(fresh[-1]) + 1]
    return [(n, BOXED_WEIGHT if n in inbag else EVO_WILD_WEIGHT if evo_wild(n) else 1) for n in front]


def evo_wild(n):
    """이전 세대 종에서 진화하는 종(이브이 → 에브이·블래키, 골뱃 → 크로뱃) — 원작은 진화로만 얻지만, 진화로만 묶으면
    세대마다 십수 마리를 동료로 하나씩 키워야 해서 풀숲에도 EVO_WILD_WEIGHT 로 드물게 나온다(2026-10-28 정함)."""
    pre = DEX[n][3]
    return bool(pre) and gen(pre) < gen(n)


STAT_KO, STAT_EN = ('체', '공', '방', '특공', '특방', '스'), ('HP', 'Atk', 'Def', 'SpA', 'SpD', 'Spe')  # 개체값 순서 = _battle.calc 능력치 순서


def roll_iv(rng=random, floor=0, n=6):
    """개체값 [HP, 공, 방, 특공, 특방, 스피드] 0~15 — 배틀 능력치에 더해진다(_battle.calc). 2026-11-06 공·방·체 셋에서 여섯으로."""
    return [floor + int(rng.random() * (16 - floor)) for _ in range(n)]


def iv_of(m):
    return tuple(m.get('iv', (0,) * 6))


def iv_pct(m):
    return round(sum(iv_of(m)) / 90 * 100)


def iv_text(m, full=True):
    """full: '체13 공15 방14 특공8 특방3 스10 (70%)', 아니면 '개체값 70%'(목록 — 2026-11-06 사용자). 모두 15 면 ★."""
    pct = iv_pct(m)
    head = ' '.join(L(f'{k}{v}', f'{e}{v}') for k, e, v in zip(STAT_KO, STAT_EN, iv_of(m))) + f' ({pct}%)' if full else \
        L(f'개체값 {pct}%', f'IV {pct}%')
    return head + (' ★' if pct == 100 else '')


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
    except FileNotFoundError:
        return new_state()
    except (OSError, ValueError) as e:  # 깨졌거나 잠깐 못 읽음 — 빈 상태로 덮어쓰면 진행이 다 사라진다(2026-10-30)
        if isinstance(e, ValueError) and not os.path.exists(f'{root}/pokemon.json.bad'):
            shutil.copy(f'{root}/pokemon.json', f'{root}/pokemon.json.bad')
        return {**new_state(), '_broken': True}  # save() 가 이 상태는 쓰지 않는다 — 파일이 다시 읽히면 그대로 이어진다
    if not st.get('forms_boxed'):  # 리전폼이 가방에 들어가기 전(2026-10-28)에 잡은 것 — 한 번만 가방에 넣는다(개체값은 아래에서)
        inbag = {m['id'] for m in st['box']}
        st['box'] += [{'id': p, 'xp': 0} for p in st.get('forms', []) if p in FORMS and p not in inbag]
        st['forms_boxed'] = True
    for b in FUSE_ITEMS:  # 합체 도구를 연구 상으로 바꾸기 전(2026-11-05)에 이미 연구를 끝냈으면 — 한 번 챙겨 준다
        if b in st.get('researched', []) and not st.get('items', {}).get(f'fuse:{b}'):
            st.setdefault('items', {})[f'fuse:{b}'] = 1
    if not st['research']:  # 연구를 넣기 전(2026-10-30)에 잡은 것 — 가방 마릿수를 잡은 횟수로(상은 주지 않는다)
        for m in st['box']:
            if m['id'] in DEX:
                r = st['research'].setdefault(str(m['id']), {})
                r['c'] = r.get('c', 0) + 1
    told = st.setdefault('genwait', [])  # 챔피언은 이겼는데 야생 종이 남아 닫힌 세대 — 소식으로 한 번 알린다(2026-11-09 규칙)
    for g in sorted(int(k) for k in st.get('league', {})):
        if g < GENS and not gen_done(st, g) and wild_left(st, g) and g not in told:
            told.append(g)
            tell(st, 'genwait', f'{g}|{len(wild_left(st, g))}')
    for n in st['caught']:  # 2026-11-09 전에 진화로 얻은 종은 잡기 0 — 1로 맞추고, 과제를 다 채웠으면 지금 연구 완료(상·메가스톤)
        if n in DEX and not wild_ok(n):
            r = st['research'].setdefault(str(n), {})
            r['c'] = max(1, r.get('c', 0))
            research_award(st, n)
    for i, m in enumerate(st['box']):  # 개체값을 넣기 전(2026-10-28)에 잡은 것 — 저장될 때까지 같은 값이 나오게 자리·종으로 고정
        floor = max(IV_FLOOR if DEX[sp(m['id'])][5] else 0, ALPHA_IV if m.get('alpha') else 0)
        if 'iv' not in m:
            m['iv'] = roll_iv(random.Random(f'{i}:{m["id"]}'), floor)
        elif len(m['iv']) == 3:  # 2026-11-06 [공, 방, 체] → [HP, 공, 방] + 새로 뽑은 특공·특방·스피드
            a, d, h = m['iv']
            m['iv'] = [h, a, d] + roll_iv(random.Random(f'iv6:{i}:{m["id"]}'), floor, 3)
    return st


def save(st, root=ROOT):
    if st.get('_broken'):
        return
    os.makedirs(root, exist_ok=True)
    p = f'{root}/pokemon.json'
    with open(p + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(st, f, ensure_ascii=False)
    os.replace(p + '.tmp', p)


def tickets(st, t):
    return t // ENCOUNTER_EVERY + st.get('extra', 0) - st['used']


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
    odds, old = wild_odds(st), [n for n in old_pool(st) if in_habitat(st, n)]
    if not odds and not old:
        return None
    st['used'] += 1
    bump(st, 'explore')
    if old and (not odds or rng.random() < OLD_GEN_RATE):
        n = old_pick(old, rng)
    else:
        n = rng.choices([n for n, _ in odds], weights=[w for _, w in odds])[0]
    shiny = rng.random() < shiny_rate(st, n)  # 리전폼도 이로치·우두머리(2026-11-06 사용자 — 전엔 따로 모으던 시절 규칙으로 없었다)
    alpha = not DEX[sp(n)][5] and rng.random() < ALPHA_RATE
    mark = 'alpha' if alpha else roll_mark(rng)
    if n in FORMS:  # 리전폼 — 다른 종처럼 이미 있어도 만나서 잡는다(개체값·박사)
        ill = illusion(st) if FORMS[n][0] in ZORUA else None  # 히스이 조로아·조로아크도 환영으로
        if not ill:
            _mark(st, 'forms_seen', n)
        st['wild'] = {'id': FORMS[n][0], 'form': n, 'balls': BALLS, **({'shiny': True} if shiny else {}),
                      **({'alpha': True, 'tries': 0} if alpha else {}), **({'disguise': ill} if ill else {}), **({'mark': mark} if mark else {})}
        return ill or n, 0
    # 메타몽은 다른 포켓몬으로 변신해, 조로아·조로아크는 내 포켓몬의 환영으로 나온다 — 잡아야 정체가 드러난다
    disguise = rng.choice(disguises(st)) if n == DITTO else illusion(st) if n in ZORUA else None
    if not (n in ZORUA and disguise):  # 환영은 내 포켓몬 모습이라 새로 본 것이 없다
        _mark(st, 'seen', disguise or n)
    st['wild'] = {'id': n, 'balls': BALLS, **({'shiny': True} if shiny else {}), **({'alpha': True, 'tries': 0} if alpha else {}),
                  **({'disguise': disguise} if disguise else {}), **({'mark': mark} if mark else {})}
    if disguise:
        return disguise, 0
    return n, 0


def set_partner(st, t, i):
    if st['partner'] is not None:  # 지금 동료가 쌓은 경험치는 그 포켓몬에게 남긴다
        st['box'][st['partner']]['xp'] = partner_xp(st, t)
    st['partner'], st['base'] = i, t


def catch_chance(st, kind):
    """지금 야생에 kind 볼을 던졌을 때 잡힐 확률(0~1) — throw 와 같은 식. 레이드볼은 하이퍼볼과 같은 2배, 마스터볼은 1,
    우두머리는 절반, 전설·환상에 몬스터볼·슈퍼볼은 0(던질 수 없다)."""
    w = st['wild']
    if w.get('raid'):
        return min(1.0, catch_rate(w['id']) * BALL_BONUS['hyper'])
    if kind == 'master':
        return 1.0
    if DEX[w['id']][5] and kind not in ('hyper', 'master'):
        return 0.0
    return min(1.0, catch_rate(w['id']) * BALL_BONUS[kind] * (0.5 if w.get('alpha') else 1))


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
        if rng.random() < catch_chance(st, 'ball'):
            raid_done(st)
            st['raids'] = st.get('raids', 0) + 1
            orb = [p for p, (s, kind, *_) in SPECIALS.items() if s == w['id'] and kind == 'primal']
            for p in orb:  # 그란돈·가이오가 — 원시회귀 구슬
                give_item(st, f'stone:{p}')
                tell(st, 'item', f'stone:{p}')
            return _caught(st, t, w, rng)
        if w['balls'] <= 0:
            raid_done(st)
            st['wild'] = None
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
    if kind == 'master' or rng.random() < catch_chance(st, kind):
        return _caught(st, t, w, rng)
    if w.get('alpha'):  # 우두머리는 ALPHA_TRIES 번 안에 못 잡으면 도망
        w['tries'] = w.get('tries', 0) + 1
        if w['tries'] >= ALPHA_TRIES:
            st['wild'] = None
            return 'fled'
    usable = st['hyper'] + st['master'] if DEX[w['id']][5] else w['balls'] + st['balls'] + st['super'] + st['hyper'] + st['master']
    if usable <= 0:  # 전설·환상엔 하이퍼볼·마스터볼만 셈 — 몬스터볼이 남아도 던질 수 없다
        st['wild'] = None
        return 'fled'
    return 'missed'


DITTO = 132
ZORUA = (570, 571)  # 조로아·조로아크 — 환영(illusion)


def illusion(st):
    """조로아·조로아크의 환영 — 원작처럼 팀의 마지막 포켓몬, 팀이 없으면 동료 모습(가방 번호 그대로 — 리전폼·메가도). 없으면 None."""
    i = st['team'][-1] if st.get('team') else st['partner']
    return None if i is None else st['box'][i]['id']


def disguises(st):
    """메타몽이 변신할 모습 — 열린 세대에서 야생으로 나오는 일반 포켓몬(전설·환상·메타몽 빼고)."""
    g = opened_gen(st)
    return [c for c in DEX if c != DITTO and not DEX[c][5] and wild_ok(c) and gen(c) <= g]


def shown(w):
    """야생이 화면에 보이는 번호 — 변신한 메타몽·조로아크 환영이면 그 모습, 리전폼이면 폼 번호."""
    return w.get('disguise') or w.get('form') or w['id']


def _caught(st, t, w, rng):
    """잡았다 — 가방에 넣고(개체값 바닥: 전설·환상 IV_FLOOR · 우두머리 ALPHA_IV) 도감·연구·보상. 'caught'."""
    floor = max(IV_FLOOR if DEX[w['id']][5] else 0, ALPHA_IV if w.get('alpha') else 0)
    g0 = opened_gen(st)
    # 리전폼은 폼 번호로 가방에 — 도감 숫자(caught) 대신 리전폼 목록(forms)에 적는다
    st['box'].append({'id': w.get('form') or w['id'], 'xp': 0, 'iv': roll_iv(rng, floor),
                      **({'shiny': True} if w.get('shiny') else {}), **({'alpha': True} if w.get('alpha') else {}),
                      **({'mark': w['mark']} if w.get('mark') else {})})
    research_bump(st, w['id'], 'c')  # 리전폼도 원래 종(w['id']) 연구에
    if w.get('form'):
        _mark(st, 'forms_seen', w['form'])  # 환영이던 히스이 조로아크는 잡을 때 처음 본다
        _mark(st, 'forms', w['form'])
    else:
        _mark(st, 'seen', w['id'])  # 변신한 메타몽은 잡을 때 처음 '봄'이 된다
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
    if opened_gen(st) > g0:  # 챔피언을 이긴 세대의 마지막 야생 종 — 다음 세대가 열린다
        tell(st, 'opengen', str(opened_gen(st)))
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
    pn = mon_name(st['box'][st['partner']])
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
        if n['kind'] == 'ribbon':  # arg: '리본|받은 포켓몬 이름|몇 마리'
            key, who, k = n['arg'].split('|')
            rb = RIBBONS.get(key, ('', key, key))
            return (L(f'{who}(이)가 {rb[1]}을 받았다!', f'{who} got the {rb[2]}!') if k == '1' else
                    L(f'팀 {k}마리가 {rb[1]}을 받았다!', f'{k} team members got the {rb[2]}!')), False
        if n['kind'] == 'super':
            return L(f'{pn}(이)가 슈퍼볼을 물어 왔다!', f'{pn} brought you a Great Ball!'), False
        if n['kind'] == 'charm':
            return L(f'빛나는 부적 {ROMAN[int(n["arg"])]}을 얻었다! ({n["arg"]}세대 이로치 2배)',
                     f'Got Shiny Charm {ROMAN[int(n["arg"])]}! (Gen {n["arg"]} shinies x2)'), False
        if n['kind'] == 'hatch':  # arg: '번호[*]' 또는 '번호[*]|볼종류:개수[,볼종류:개수…]'(덤 — 알 종류에 따라 여럿)
            mon, _, extra = n['arg'].partition('|')
            hn, sh = int(mon.rstrip('*')), mon.endswith('*')
            names = [ball_name(*x.split(':')) for x in extra.split(',')] if extra else []
            ko, en = ' + '.join(a for a, _ in names), ' + '.join(b for _, b in names)
            return L(f'알이 부화했다! {"✨이로치 " if sh else ""}{name(hn)}(이)가 태어났다!' + (f' 덤으로 {ko}!' if extra else ''),
                     f'An egg hatched! {"✨shiny " if sh else ""}{name(hn)} was born!' + (f' Plus {en}!' if extra else '')), False
        if n['kind'] == 'genwait':  # 챔피언은 이겼는데 그 세대 야생 종이 남았다
            g, k = n['arg'].split('|')
            return L(f'{g}세대 야생 포켓몬 {k}종(전설·환상 포함)을 마저 잡으면 {int(g) + 1}세대가 열린다!',
                     f'Catch the last {k} wild Gen {g} species (legendaries included) to open Gen {int(g) + 1}!'), False
        if n['kind'] == 'opengen':
            return L(f'{n["arg"]}세대가 열렸다! 풀숲에서 새 포켓몬이 나온다.', f'Gen {n["arg"]} is open! New Pokémon in the tall grass.'), False
        if n['kind'] == 'streak':
            return L(f'{n["arg"]}일 연속! 탐색 기회 +{STREAK_BONUS}!', f'{n["arg"]}-day streak! +{STREAK_BONUS} explores!'), False
        if n['kind'] == 'work':
            k = int(n['arg'] or WORK_EXPLORES)
            return (L(f'주말 부스트! {pn}(이)가 신나서 탐색 기회 +{k}!', f'Weekend boost! {pn} is excited: +{k} explores!') if k > WORK_EXPLORES else
                    L(f'오늘도 일했다! {pn}(이)가 신나서 탐색 기회 +{k}!', f'Shipped today! {pn} is excited: +{k} explore!')), False
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
        n, km = e['id'], egg_km(e)
        shiny = rng.random() < shiny_rate(st, n, EGG_SHINY) * EGG_KM_SHINY.get(km, 1)
        st['box'].append({'id': n, 'xp': 0, 'iv': roll_iv(rng, IV_FLOOR), **({'shiny': True} if shiny else {})})
        research_bump(st, n, 'c')
        for key in ('seen', 'caught') + (('shiny',) if shiny else ()):
            _mark(st, key, n)
        if st['partner'] is None:
            set_partner(st, t, len(st['box']) - 1)
        kind, k, _ = rng.choices(EGG_BONUS, weights=[w for _, _, w in EGG_BONUS])[0]  # 덤 볼 하나는 늘 붙는다
        extra = [(kind, k)] + EGG_KM_BONUS.get(km, [])
        for kind, k in extra:
            st[kind] += k
        tell(st, 'hatch', f'{n}{"*" if shiny else ""}|' + ','.join(f'{kind}:{k}' for kind, k in extra))
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


def egg_km(e):
    """알 종류(포켓몬고처럼 거리) — 부화 걸음(need / EGG_STEP)으로: ~10 → 2km · 15~20 → 5km · 25 → 7km · 30~40 → 10km · 50~ → 12km."""
    steps = e['need'] // EGG_STEP
    return 2 if steps <= 10 else 5 if steps <= 20 else 7 if steps <= 25 else 10 if steps <= 40 else 12


def egg_lines(st, t):
    """알마다 한 줄 [('5km 알 · 부화까지 18k', 진행 0~1, km)] — 부화가 빠른 순. 알은 저마다 받은 때(base)부터 자란다
    ('알 2개 · 다음 부화까지'로 묶어 보이면 새 알이 옛 알을 리셋한 것처럼 보였다, 2026-11-04)."""
    out = []
    for e in sorted(st.get('eggs', []), key=lambda e: e['need'] - (t - e['base'])):
        left = max(0, e['need'] - (t - e['base']))
        out.append((L(f'{egg_km(e)}km 알 · 부화까지 {fmt_tok(left)}', f'{egg_km(e)} km egg · hatches in {fmt_tok(left)}'),
                    min(1.0, (t - e['base']) / e['need']), egg_km(e)))
    return out


def reward(st, folder=feed.JOBS, today=None):
    """일한 보상 — 기능을 켠 날부터, 조건을 채운 날마다 탐색 +WORK_EXPLORES(하루 한 번), 평일 STREAK_DAYS 일 연속마다
    +STREAK_BONUS 더. 새로 보상한 날 수."""
    today = today or datetime.now().astimezone().strftime('%Y-%m-%d')
    st['reward_since'] = st.get('reward_since') or today
    got = 0
    for day, names in sorted(shipped(folder).items()):
        if day >= st['reward_since'] and day not in st['rewarded'] and len(names) >= SUPER_SESSIONS:
            st['rewarded'].append(day)  # 자르지 않는다 — 잘린 날을 '안 받은 날'로 보고 다시 줬다(2026-10-30)
            gain = WEEKEND_EXPLORES if datetime.strptime(day, '%Y-%m-%d').weekday() >= 5 else WORK_EXPLORES
            st['extra'] = st.get('extra', 0) + gain
            st['super_earned'] = (st.get('super_earned') or 0) + 1  # 일한 날 수(훈장) — 예전 이름 그대로
            got += 1
            tell(st, 'work', str(gain))
            bump(st, 'ship')
            k = streak(st, day)
            if k % STREAK_DAYS == 0:
                st['extra'] += STREAK_BONUS
                tell(st, 'streak', str(k))
    return got


def streak(st, day):
    """day 까지 보상받은 날의 연속 일수 — 쉰 주말은 건너뛰고(끊지 않음) 일한 주말은 센다(2026-11-11 사용자). 오늘(평일)을
    아직 안 했어도 그 전날까지 이어졌으면 센다."""
    got, d, n, first = set(st['rewarded']), datetime.strptime(day, '%Y-%m-%d'), 0, True
    for _ in range(4000):  # ponytail: 10년쯤이면 충분 — 무한 루프 방지
        if d.weekday() >= 5 and d.strftime('%Y-%m-%d') not in got:
            d -= timedelta(days=1)
            continue
        if d.strftime('%Y-%m-%d') in got:
            n += 1
        elif not first:
            break
        first, d = False, d - timedelta(days=1)
    return n


def form_note(n):
    """'꼬렛의 알로라 모습' · '리자몽의 메가 모습' — 도감 상세에서 분류·설명이 없는 모습에."""
    if n in FORMS:
        s, region = FORMS[n][0], REGION[FORMS[n][1].split('-')[0]]
        return L(f'{name(s)}의 {region[0]} 모습', f'{region[1]} form of {name(s)}')
    s, kind = SPECIALS[n][0], SPECIALS[n][1]
    k = {'ultra': ('울트라버스트', 'Ultra Burst'), 'primal': ('원시회귀', 'Primal Reversion')}.get(kind, SPECIAL_KIND[kind])
    return L(f'{name(s)}의 {k[0]} 모습', f'{k[1]} form of {name(s)}')


FUSE_ITEMS = {646: ('유전자쐐기', 'DNA Splicers'), 800: ('네크로플러스', 'N-Solarizer/Lunarizer'), 898: ('끈의 줄', 'Reins of Unity')}  # 합체 도구 — 쓰면 사라지지 않는다(재료 포켓몬이 사라진다)


def bag_items(st):
    """가방 화면 — [(키, 개수 또는 None(늘 있는 합체 도구))]. 가진 것만: 이상한사탕 · 병뚜껑 · 메가스톤·구슬·Z · 다이수프 · 합체 도구(그 포켓몬이 있으면)."""
    items = st.get('items', {})
    out = ([('candy', st['candy'])] if st.get('candy') else []) + \
        [(k, items[k]) for k in ('gcap', 'cap') if items.get(k)] + \
        sorted(((k, c) for k, c in items.items() if c > 0 and k.startswith('stone:')), key=lambda kc: int(kc[0].split(':')[1])) + \
        ([('soup', items['soup'])] if items.get('soup') else [])
    return out + [(f'fuse:{b}', None) for b in FUSE_ITEMS if items.get(f'fuse:{b}')]  # 합체 도구 — 개수 대신 '도구'로


def item_targets(st, key, query=''):
    """그 아이템을 쓸 수 있는 포켓몬 [(가방 번호, 바꾸기 화면의 칸 번호들, 지금 쓸 수 있나, 못 쓰는 까닭)] — 레벨 높은 것부터.
    이상한사탕은 진화할 수 있는 포켓몬, 합체 도구는 합체 상대가 가방에 있는 기본 포켓몬, 그 밖엔 change_options 에 그 아이템 칸이 있는 포켓몬."""
    out, q = [], query.lower()
    for i in bag_order(st, None, 1):
        m = st['box'][i]
        if q not in name(m['id']).lower():  # 이름 찾기
            continue
        if key == 'candy':
            if evolutions(st, m['id'], m.get('shiny')):
                out.append((i, [], True, ''))
            continue
        opts = change_options(st, i)
        if key.startswith('fuse:'):  # 합체 도구 — 그 기본 포켓몬의 합체 칸들(재료는 가방 속 포켓몬)
            ks = [k for k, o in enumerate(opts) if o[1][0] == 'mon'] if m['id'] == int(key[5:]) else []
        else:
            ks = [k for k, o in enumerate(opts) if o[1] == ('item', key)]
        if ks:
            ok = [k for k in ks if opts[k][2]]
            out.append((i, ks, bool(ok), '' if ok else opts[ks[0]][3]))
    return out


def item_name(key):
    """아이템 이름 — 'stone:<모습>'(메가스톤·구슬·울트라네크로Z) · 'soup'(다이수프) · 'cap'·'gcap'(은색·금색 병뚜껑)."""
    if key == 'soup':
        return L('다이수프', 'Max Soup')
    if key in ('cap', 'gcap'):
        return L('은색 병뚜껑', 'Bottle Cap') if key == 'cap' else L('금색 병뚜껑', 'Gold Bottle Cap')
    if key == 'candy':
        return L('이상한사탕', 'Rare Candy')
    if key.startswith('fuse:'):
        return L(*FUSE_ITEMS[int(key[5:])])
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


def give_fuse_tool(st, n):
    """n 이 합체 기본 포켓몬(FUSE_ITEMS)이면 합체 도구 하나 — 이미 있으면 그만(쓰고 나서도 남는 도구라 하나면 된다, 2026-11-05 사용자)."""
    key = f'fuse:{n}'
    if n in FUSE_ITEMS and not st.get('items', {}).get(key):
        give_item(st, key)
        tell(st, 'item', key)


def give_stones(st, n):
    """그 종의 메가스톤들(X·Y 는 따로)과, 네크로즈마면 울트라네크로Z — 쓰는 건 그 세대가 열린 뒤(change_options)."""
    keys = [f'stone:{p}' for p, (s, kind, *_) in SPECIALS.items() if s == n and kind in ('mega', 'ultra')]
    for key in keys:
        give_item(st, key)
    if keys:
        tell(st, 'item', ','.join(keys))


def research_goals(n):
    """그 종의 연구 과제 {'c': 잡기, 'e': 진화, 'w': 배틀 승리} — 진화형이 없으면 진화 과제는 없다.
    특수 모습은 그 모습의 도감에 따로 {'m': 만들기 1, 'w': 배틀 승리}(2026-10-30)."""
    if n in SPECIALS:
        return {'m': 1, 'w': RESEARCH_WIN}
    # 잡기: 전설·환상과 진화로만 얻는 종(야생에 안 나옴)은 1 — 5로 두면 진화형은 연구를 못 끝내 메가스톤도 못 얻었다(2026-11-09)
    return {'c': 1 if DEX[n][5] or not wild_ok(n) else RESEARCH_CATCH, 'e': 1 if n in CHILDREN else 0, 'w': RESEARCH_WIN}


def research_done(st, n):
    r = st.get('research', {}).get(str(n), {})
    return (n in DEX or n in SPECIALS) and all(r.get(k, 0) >= v for k, v in research_goals(n).items())


def research_award(st, n):
    """과제를 다 채웠는데 아직 완료 전이면 연구 완료 — 도감 ★, RESEARCH_PRIZE, 첫 메가스톤, 합체 도구. 이번에 완료했나."""
    if not research_done(st, n) or n in st.setdefault('researched', []):
        return False
    st['researched'].append(n)
    st[RESEARCH_PRIZE[0]] += RESEARCH_PRIZE[1]
    tell(st, 'research', str(n))
    give_stones(st, n)  # 첫 메가스톤
    give_fuse_tool(st, n)  # 큐레무·네크로즈마·버드렉스 — 합체 도구(한 번, 쓴 뒤에도 남는다)
    return True


def research_bump(st, n, key):
    """연구 기록 하나 — 과제를 다 채우면 연구 완료(도감 ★)와 RESEARCH_PRIZE. 특수 모습은 따로, 리전폼·합체 모습 번호는 세지 않는다."""
    if n not in DEX and n not in SPECIALS:
        return
    r = st.setdefault('research', {}).setdefault(str(n), {})
    r[key] = r.get(key, 0) + 1
    if not research_award(st, n) and key == 'c' and n in DEX and n in st['researched'] and (r['c'] - research_goals(n)['c']) % RESEARCH_CATCH == 0:
        give_stones(st, n)  # 연구를 끝낸 뒤엔 RESEARCH_CATCH 마리 더 잡을 때마다 하나 더 — 전설(목표 1)도 매번이 아니라 5마리마다


def research_text(st, n):
    """'연구 — 잡기 3/5 · 진화 0/1 · 배틀 승리 1/3' (다 채웠으면 ★ 연구 완료)."""
    r = st.get('research', {}).get(str(n), {})
    names = {'c': L('잡기', 'catch'), 'e': L('진화', 'evolve'), 'm': L('만들기', 'make'), 'w': L('배틀 승리', 'battle wins')}
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
        old = st.get('raid') or {}
        st['raid'] = {'week': key, 'won': False, 'done': False, 'pending': False}
        late = old.get('late') or (old.get('week') if old.get('pending') else None)
        if late:  # 지난주에 이기고 아직 못 만난 보스 — 주가 바뀌어도 한 번은 내준다(raid_release)
            st['raid']['late'] = late
    return st['raid']


def raid_done(st):
    """만난 레이드 보스가 끝남(잡음·도망·놓아줌) — 그 보스의 주 기록에만 적는다. 주가 바뀐 뒤면 이번 주 레이드는 그대로 남는다."""
    r = st.get('raid')
    if r and st['wild'].get('week', r.get('week')) == r.get('week'):
        r['done'] = True


def raid_release(st):
    """이긴 레이드 보스를 포획 기회로 — 다른 야생과 만나는 중이면 그게 끝날 때까지 기다린다."""
    r = st.get('raid')
    wk = r and (r.get('late') or (r['week'] if r.get('pending') else None))
    if wk and not st['wild']:
        boss = raid_boss(st, wk)[1]
        st['wild'] = {'id': boss, 'balls': RAID_BALLS, 'raid': True, 'week': wk,
                      **({'shiny': True} if random.random() < shiny_rate(st, boss, EGG_SHINY) else {})}
        _mark(st, 'seen', boss)
        if r.get('late'):
            del r['late']
        else:
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
        return L(f'주간 과제 완료 ✔ — {ko.format(n=goal)} (보상: {prize})', f'Weekly done ✔ — {en.format(n=goal)} (prize: {prize})')
    return L(f'주간 과제: {ko.format(n=goal)} {min(w["n"], goal)}/{goal} — 보상: {prize}', f'Weekly: {en.format(n=goal)} {min(w["n"], goal)}/{goal} — prize: {prize}')


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


def use_candy(st, t, rng=random, i=None):
    """이상한사탕 — 가방 i 번째(없으면 동료)가 진화할 수 있는 모습이 있으면 경험치와 상관없이 바로 진화. 진화한 번호 · 못 쓰면 None.
    가방에서 아무 포켓몬에게나 쓴다(2026-11-05 — 가방이 아이템 화면이 되며)."""
    i = st['partner'] if i is None else i
    if st.get('candy', 0) <= 0 or i is None:
        return None
    m = st['box'][i]
    if not evolutions(st, m['id'], m.get('shiny')):
        return None
    st['candy'] -= 1
    return _evolve(st, t, rng, i)


def evolve(st, t, rng=random):
    if not can_evolve(st, t):
        return None
    n = _evolve(st, t, rng)
    give_ribbon(st, [st['partner']], 'partner')  # 동료로 함께 지내 진화 — 단짝 리본(사탕 진화는 아님)
    return n


def _evolve(st, t, rng, i=None):
    mon = st['box'][st['partner'] if i is None else i]
    research_bump(st, sp(mon['id']), 'e')  # 리전폼은 원래 종 연구에(배틀 승리·포획과 같이)
    mon['id'], mon['xp'] = rng.choice(evolutions(st, mon['id'], mon.get('shiny'))), 0  # 이로치는 이로치로 진화
    if i is None or i == st['partner']:  # 동료의 진화 경험치는 새로 — 다른 포켓몬(사탕)은 동료 경험치를 건드리지 않는다
        st['base'] = t
    st['evolved'] = st.get('evolved', 0) + 1
    bump(st, 'evolve')
    research_bump(st, sp(mon['id']), 'c')  # 진화해서 얻은 것도 그 종을 얻은 것 — 진화형 연구의 '잡기'
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
    """동료의 진화 상태: ('final',) · ('locked',) · ('ready',) · ('progress', 경험치, 필요치)."""
    m = st['box'][st['partner']]
    n = m['id']
    if not evo_next(n):
        return ('final',)
    if not opened_evolutions(st, n):
        return ('locked',)
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


def summary(root=ROOT, awake=None):
    """허브용 몇 줄: (글, 강조여부 — 'warn' 이면 노랑, 진행률 또는 None). awake: 깨어 있는 세션 이름들."""
    if not DEX:  # 아직 도감을 안 받았다 — 받는 건 pokemon 화면이 한다
        return [(L('포켓몬 데이터 없음 — [ pokemon ] 을 열면 받아 옵니다',
                   'No Pokédex yet — open [ pokemon ] to download it'), False, None)]
    st, t = load(root), total_tokens(root)
    if st.get('_broken'):
        return [(L('저장 파일을 읽지 못함 — pokemon.json 을 확인하세요(덮어쓰지 않음)',
                   "Can't read pokemon.json — check it (not overwritten)"), 'warn', None)]
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
    """가방 항목(또는 번호) → 그림 번호: 이로치면 이로치 그림, 리전폼·합체·특수 모습이면 'form:번호'(번호가 이로치 자리와 겹쳐서) —
    이로치 리전폼·합체·특수 모습은 'form:shiny/번호'(PokeAPI 에 이로치 그림이 있다)."""
    n, shiny = (m['id'], m.get('shiny')) if isinstance(m, dict) else (m, False)
    if n in FORMS or n in FUSIONS or n in SPECIALS:
        return f'form:shiny/{n}' if shiny else f'form:{n}'
    return n + (_pokedata.SHINY if shiny else 0)


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
    """도감 상세: 이름 · 분류 · 타입, 잡았으면 키 · 몸무게 · 설명, 아래에 그림(이로치를 잡았으면 보통·이로치 나란히).
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
    unseen = n not in (st['forms_seen'] if form else st.get('specials', []) if spec else st['seen'])  # 못 봤으면 실루엣(2026-11-11 사용자)
    x = put(scr, 1, 1, f'No.{sp(n):04d}  ', curses.A_BOLD)
    x = put(scr, 1, x, '???' if unseen else ('✨' if sh else '') + name(n), curses.A_DIM if unseen else gold if sh else curses.A_BOLD)
    put(scr, 1, x + 2, (L('리전폼', 'Regional form') if form else L('특수 모습', 'Special form') if spec else L(f'{gen(n)}세대', f'Gen {gen(n)}'))
        + (L(' · 아직 못 봄', ' · not seen yet') if unseen else (L(' · 만듦', ' · made') if spec else L(' · 잡음', ' · caught')) if caught else L(' · 봄', ' · seen')),
        curses.A_DIM)
    if unseen:
        d, sh = None, False
        hint = dex_hint(st, n) if n in DEX else L('리전폼 — 그 종의 세대가 지나면 이전 세대 탐색에서', 'regional form — older-generation explores, once its generation is behind you') if form else ''
        put(scr, 2, 1, fit(hint or L('만나면 이름과 모습이 드러난다.', 'Meet it to reveal it.'), w - 2), curses.A_DIM)
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
    room, gray = h - 3 - (y + 1), 2 if unseen else False
    # 이로치를 잡았으면 보통·이로치 그림을 나란히(2026-11-09 사용자 — 전엔 이로치만 보여 보통 색을 볼 수 없었다)
    sids = [f'form:{n}'] if form else [n, n + _pokedata.SHINY] if sh else [n]
    if len(sids) > 1:
        room -= 1  # 그림 아래 '보통 · ✨이로치' 줄
    if room < 4:
        return None
    half, art = (w - 2) // len(sids), None
    for k, sid in enumerate(sids):
        ok, a = info_pic(scr, sid, gray, y + 1, 1 + k * half, half, room, 300000 + n if form else sid)
        if not ok:
            put(scr, y + 1, 1, L('그림 받는 중…', 'Loading the picture…'), curses.A_DIM)
            return None
        art = join_art(art, a)
        if len(sids) > 1:
            label = L('✨이로치', '✨shiny') if k else L('보통', 'normal')
            put(scr, y + 1 + (a[6] if a else room), 1 + k * half + max(0, (half - memo_w(label)) // 2), label, gold if k else curses.A_DIM)
    return art


def info_pic(scr, sid, gray, y, x, width, room, key):
    """도감 상세 그림 하나를 (y, x) 부터 width 칸 · room 줄 안 가운데에 — (받았나, 놓을 그림 또는 None).
    Sixel·Kitty 는 놓을 그림을 돌려주고, 아니면 ▀▄ 칸으로 바로 그린다. key 는 Kitty 이미지 번호의 바탕.
    그림은 남은 줄의 절반 높이 — 가로·세로가 절반이라 넓이 1/4(2026-11-10 사용자: 24줄 패널에서 23칸×11줄이 너무 컸다)."""
    room = max(2, room // 2)
    if SIXEL:  # 원본 도트를 정수 배로 — ▀▄ 칸은 평균·256색이라 흐리고 색이 틀렸다(2026-10-21)
        cw_, ch_ = _gfx.cell_px()
        # 그림이 바깥 터미널 아래 끝을 넘으면 터미널 전체가 밀려 올라갔다(2026-10-21 실제 화면). 칸 크기를 잘못 알아
        # 두 배로 그려져도 넘지 않게, 남은 줄의 절반 · 최대 8줄로.
        below = _gfx.rows_below(y)
        room = max(0, min(room, 8, (below - 1) // 2 if below else room))
        if room < 2:  # 위에서 절반으로 줄였으니 2줄까지는 그린다(3줄 기준이면 작은 패널에서 그림이 사라졌다)
            return True, None
        six = _pokedata.sprite_sixel_fit(sid, gray, int(width * cw_), int(room * ch_))
        if not six:
            return False, None
        cols, rows = math.ceil(six[1] / cw_), math.ceil(six[2] / ch_)
        return True, ('six', y, x + max(0, (width - cols) // 2), (sid, gray, width, room), six[0], cols, rows)
    if KITTY:
        png = _pokedata.sprite_png(sid, gray)
        if not png:
            return False, None
        cols = _gfx.kitty_cols(png[1], png[2], room)
        while cols > width and room > 1:  # 나란히 놓으면 폭이 절반 — 칸을 넘지 않게 줄인다
            room -= 1
            cols = _gfx.kitty_cols(png[1], png[2], room)
        return True, ('kitty', y, x + max(0, (width - cols) // 2), key * 3 + gray, png[0], cols, room)
    if curses.COLORS >= 256:
        grid = _pokedata.sprite(sid, room * 2, width - 2)
        if not grid:
            return False, None
        _pokedata.draw_sprite(scr, y, x + max(0, (width - len(grid[0])) // 2), grid, gray)
    return True, None

SHOWCASE_MAX = 12  # 2026-11-05 사용자: 메인 맨 위 한 줄에 12개까지
# 훈장 → PokeAPI 도구 그림(sprites/items/<이름>.png) — 2026-10-21 미리보기로 보여 드린 짝. 지방 정복은 그 지방 이야기의
# 상징물(처음엔 8관 배지 그림을 썼더니 훈장과 배지가 같은 그림이 됐다).
MEDAL_ART = {'catch1': 'poke-ball', 'catch10': 'great-ball', 'catch50': 'ultra-ball', 'catch100': 'luxury-ball',
             'catch500': 'master-ball', **{f'gen{g}': f'shiny-charm-{g}' for g in range(1, 10)},  # 세대 완성 = 빛나는 부적 + 금색 로마 숫자(_pokedata.charm_numeral, 2026-11-09 사용자)
             'shiny1': 'star-piece', 'shiny5': 'comet-shard', 'legend': 'red-chain', 'myth': 'gracidea',
             'evo1': 'rare-candy', 'final10': 'exp-share', 'super1': 'nugget', 'super10': 'big-nugget',
             'hyper1': 'gold-bottle-cap', 'conquer1': 'poke-flute', 'conquer2': 'rainbow-wing', 'conquer3': 'red-orb',
             'conquer4': 'adamant-orb', 'conquer5': 'light-stone', 'conquer6': 'zygarde-cube', 'conquer7': 'sun-flute',
             'conquer8': 'rusted-sword', 'conquer9': 'scarlet-book', 'champ1': 'relic-copper', 'champ2': 'relic-silver',
             'champ3': 'relic-gold', 'champ4': 'relic-vase', 'champ5': 'relic-band', 'champ6': 'relic-statue',
             'champ7': 'pearl-string', 'champ8': 'big-pearl', 'champ9': 'relic-crown',
             'form1': 'galarica-twig', 'form_all': 'galarica-wreath', 'fuse1': 'dna-splicers',
             'research1': 'scope-lens', 'research10': 'poke-radar', 'research50': 'old-amber', 'alpha1': 'kings-rock',
             'raid1': 'wishing-piece', 'mega1': 'mega-ring', 'gmax1': 'dynamax-band',
             'tower7': 'choice-band', 'tower21': 'choice-scarf', 'tower49': 'choice-specs', 'tower100': 'leftovers'}


def art_id(key):
    """훈장 번호 또는 체육관 배지('gym:세대-관') → 그림 번호(_pokedata). 리전폼 그림('form:번호')은 그대로."""
    if key.startswith(('form:', 'ribbon:', 'mark:')):
        return key
    if key.startswith('gym:'):
        g, i = map(int, key[4:].split('-'))
        return _pokedata.BADGE + _battle.GYMS[g][i][1]
    return 'item:' + MEDAL_ART[key]


def owned(st, key):
    """그 훈장·배지를 가졌나."""
    return key in st.get('gym', {}) if key.startswith('gym:') else key in st['badges']


def badge_art(st, keys, y, x, rows, per_row=0):
    """훈장·배지 그림들을 한 장으로 (y, x) 에 rows 줄 높이로 놓을 그림(per_row 를 주면 그 개수씩 줄을 나눠 쌓는다)
    — main 이 화면을 그린 뒤 놓는다. 못 그리면 None."""
    if not keys or not (SIXEL or KITTY):
        return None
    ids = [art_id(k) for k in keys]
    cw_, ch_ = _gfx.cell_px()
    img = _pokedata.strip_image(ids, int(rows * ch_), 'six' if SIXEL else 'png', per_row)
    if not img:
        return None
    cols = math.ceil(img[1] / cw_)
    if SIXEL:
        return ('six', y, x, ('badges', tuple(ids), rows, per_row), img[0], cols, rows)
    return ('kitty', y, x, 100000 + zlib.crc32(repr((ids, per_row)).encode()) % 100000, img[0], cols, rows)


def bag_text(m, room):
    """가방·교환 목록 한 줄(표시 뒤) — 늘 '이름 Lv · 공 방 체 (%)'(도감번호·경험치는 빼기로, 2026-11-03 사용자).
    room 칸보다 길면 이름 끝을 '…'로 줄여 개체값이 늘 보이게 — 팔데아 켄타로스(블레이즈종)에서 잘렸다."""
    cw = lambda t: sum(map(memo.cw, t))  # noqa: E731
    nm = mon_name(m)
    tail = f' Lv{box_level(m)} · {iv_text(m, False)}'
    if cw(nm + tail) <= room:
        return nm + tail
    while nm and cw(nm + '…' + tail) > room:
        nm = nm[:-1]
    return nm + '…' + tail


def mon_art(n, y, w, x=1, rows=2, max_cols=None, flip=False):
    """메인 화면의 포켓몬 그림(동료·팀 칸) — 그림 번호 n 을 (y, x) 에 화면에서 rows 줄로 보이게. Sixel 은 실제로
    SIXEL_SCALE 배 크게 그려지니 그만큼 작게 요청한다. max_cols 칸을 넘으면 줄인다. 못 놓거나 좁으면 None."""
    if n is None or w < 44 or rows < 1 or not (SIXEL or KITTY):
        return None
    cw_, ch_ = _gfx.cell_px()
    if SIXEL:
        six = _pokedata.sprite_sixel(n, False, max(ch_ // 2, int(rows * ch_ / SIXEL_SCALE)), flip)
        return six and ('six', y, x, ('mon', n, y, x, rows, flip), six[0], math.ceil(six[1] / cw_), rows)
    png = _pokedata.sprite_png(n, flip=flip)  # 같은 포켓몬이 두 칸에 있어도 따로 놓이게 자리도 번호에
    if not png:
        return None
    cols = _gfx.kitty_cols(png[1], png[2], rows)
    while max_cols and cols > max_cols and rows > 1:
        rows -= 1
        cols = _gfx.kitty_cols(png[1], png[2], rows)
    return ('kitty', y, x, 400000 + (_pokedata.img_id(n) * 2 + flip) % 100000 * 10 + (y * 7 + x + rows) % 10, png[0], cols, rows)


SIDE_W = 14  # 메인 화면 오른쪽 버튼 열 폭
TEAM_ART_MAX = 10  # 팀 칸 그림의 가장 큰 높이(줄) — 실제로는 칸 폭(mon_art 의 max_cols)이 먼저 막는다


def wrap_widths(widths, w, start=1):
    """버튼 폭들을 w 칸 패널에 줄 단위로 나눈다 — [[번호…], …]. 한 줄에 안 들어가면 다음 줄로(좁은 패널에서 잘리지 않게)."""
    rows, x = [[]], start
    for i, bw in enumerate(widths):
        if rows[-1] and x + bw > w:
            rows.append([])
            x = start
        rows[-1].append(i)
        x += bw
    return rows if rows[0] else []


def team_layout(free, graphics=True, cap=TEAM_ART_MAX):
    """메인 화면 팀 3×2 가 쓸 수 있는 줄 수 free → (칸 높이, 그림 줄 수). 칸 = 그림 + 이름 + 개체값 (+ 남으면 빈 줄 하나).
    패널 크기에 맞춰 정한다(2026-11-05 사용자 — 고정 6줄이면 22줄 패널에서 아래 글이 잘렸다). 그림 놓을 자리가 없으면 글만 2줄.
    cap: 칸 폭으로 그릴 수 있는 그림 높이 — 폭이 먼저 막히면 그만큼만 잡아 그림과 이름 사이가 벌어지지 않게."""
    ch = free // 2
    if not graphics or ch < 3:
        return 2, 0
    art = min(TEAM_ART_MAX, cap, ch - 2)
    return min(ch, art + 3), art


def memo_w(text):
    return sum(map(memo.cw, text))


def fit(text, width):
    """text 를 width 칸 안으로 — 넘치면 끝을 '…'로."""
    if memo_w(text) <= width:
        return text
    while text and memo_w(text + '…') > width:
        text = text[:-1]
    return text.rstrip() + '…'


def box_button(scr, y, x, width, label, a, btns, navbtns, tall=True, attr=curses.A_BOLD):
    """네모 버튼 하나 — tall 이면 3줄 상자, 아니면 1줄. 클릭은 상자 전체, 고르기 표시는 가운데 줄. 다음 y."""
    inner = width - 2
    lab = fit(label, inner)
    pad = inner - memo_w(lab)  # 한글은 2칸 — str.center 는 글자 수로 맞춰 어긋난다
    text = '│' + ' ' * (pad // 2) + lab + ' ' * (pad - pad // 2) + '│'
    mid = y + 1 if tall else y
    if tall:
        put(scr, y, x, '┌' + '─' * inner + '┐', curses.A_DIM)
        put(scr, y + 2, x, '└' + '─' * inner + '┘', curses.A_DIM)
    put(scr, mid, x, text, attr)
    btns.extend((r, x, x + width - 1, a) for r in range(y, y + (3 if tall else 1)))
    navbtns.append((mid, x, x + width - 1, a, text))
    return y + (3 if tall else 1)


def side_buttons(scr, side, x0, y, h, btns, navbtns, width=None):
    """오른쪽 네모 버튼 열 — 칸이 넉넉하면 3줄 상자, 모자라면 1줄. side: [(글, act[, attr])]."""
    tall = h - 1 - y >= 3 * len(side)
    for label, a, *attr in side:
        y = box_button(scr, y, x0, (width or SIDE_W) - 1, label, a, btns, navbtns, tall, *attr)


BALL_ORDER = [('ball', '몬스터볼', 'Poké'), ('super', '슈퍼볼', 'Great'), ('hyper', '하이퍼볼', 'Ultra'), ('master', '마스터볼', 'Master')]


def ball_choices(st):
    """만남 화면 ② — [(볼, 개수, 던질 수 있나)]. 레이드는 레이드볼만, 전설·환상은 하이퍼볼·마스터볼만."""
    w = st['wild']
    if w.get('raid'):
        return [('ball', w['balls'], w['balls'] > 0)]
    legend = DEX[w['id']][5]
    out = []
    for kind, *_ in BALL_ORDER:
        k = (w['balls'] or st['balls']) if kind == 'ball' else st[kind]
        out.append((kind, k, k > 0 and not (legend and kind in ('ball', 'super'))))
    return out


def default_ball(st, now=None):
    """고른 볼 — now 를 그대로 쓸 수 있으면 그것, 아니면 던질 수 있는 가장 싼 볼(마스터볼은 저절로 고르지 않는다)."""
    ok = [kind for kind, _, can in ball_choices(st) if can]
    if now in ok:
        return now
    return next((kind for kind in ok if kind != 'master'), None)


SIXEL_SCALE = 1.6  # 이 터미널은 Sixel 을 알려 준 칸보다 이만큼 크게 그린다 — 8줄로 놓은 가이오가가 13줄로 보였다(2026-11-05 스크린샷)


def big_art(n, cy, cx, rows, max_cols=None):
    """만남 화면 ① 그림 — 화면에 실제로 보일 크기의 가운데가 (cy, cx) 에 오게, rows 줄 높이로 요청해 놓는다.
    Sixel 은 실제로 SIXEL_SCALE 배 크게 그려지니 그만큼 왼쪽·위로 당긴다. 옆으로 넓은 포켓몬(가이오가)이 실제로 max_cols 칸을
    넘으면 높이를 줄인다. 못 놓으면 None."""
    if n is None or not (SIXEL or KITTY):
        return None
    cw_, ch_ = _gfx.cell_px()
    if SIXEL:
        six = _pokedata.sprite_sixel(n, False, int(rows * ch_))
        if not six:
            return None
        cols = math.ceil(six[1] / cw_)
        if max_cols and cols * SIXEL_SCALE > max_cols:
            px = max(ch_, int(rows * ch_ * max_cols / (cols * SIXEL_SCALE)))
            six, rows = _pokedata.sprite_sixel(n, False, px), px / ch_
            cols = math.ceil(six[1] / cw_)
        y, x = max(2, round(cy - rows * SIXEL_SCALE / 2)), max(1, round(cx - cols * SIXEL_SCALE / 2))
        return ('six', y, x, ('big', n, y, x, rows), six[0], cols, math.ceil(rows))
    png = _pokedata.sprite_png(n)
    if not png:
        return None
    cols = _gfx.kitty_cols(png[1], png[2], rows)
    if max_cols and cols > max_cols:
        rows = max(1, rows * max_cols // cols)
        cols = _gfx.kitty_cols(png[1], png[2], rows)
    return ('kitty', max(2, cy - rows // 2), max(1, cx - cols // 2), 500000 + _pokedata.img_id(n) % 100000, png[0], cols, rows)


def wild_ball_step(st, picked, key):
    """만남 화면 ↑↓ — 던질 볼을 바로 위·아래 것으로(던질 수 있는 것만, 끝에서 멈춤). 포커스는 [던지기]·[도망]에 그대로 —
    전엔 ↑ 로 볼 목록에 올라가 고른 뒤 다시 [던지기]로 내려와야 했다(2026-11-10 사용자)."""
    ok = [kind for kind, _, can in ball_choices(st) if can]
    if not ok:
        return picked
    i = ok.index(picked) if picked in ok else 0
    return ok[max(0, min(len(ok) - 1, i + (-1 if key == curses.KEY_UP else 1)))]


def move_geo(btns, focus, key):
    """메인 화면 방향키 — ↑↓ 는 같은 열(가로가 겹치는 버튼)에서 위·아래, ←→ 는 왼·오른쪽에서 높이가 가장 가까운 것.
    팀 칸과 오른쪽 버튼 열 사이를 ←→ 로 오간다. btns: [(y, x, 끝, act, 글)]."""
    if not btns:
        return focus
    cur = next((b for b in btns if b[3] == focus), btns[0])
    y, x, e = cur[0], cur[1], cur[2]
    if key in (curses.KEY_UP, curses.KEY_DOWN):
        down = key == curses.KEY_DOWN
        cands = [b for b in btns if (b[0] > y if down else b[0] < y) and b[1] < e and b[2] > x]
        return min(cands, key=lambda b: (abs(b[0] - y), abs(b[1] - x)))[3] if cands else cur[3]
    right = key == curses.KEY_RIGHT
    cands = [b for b in btns if (b[1] > x if right else b[1] < x) and b[3] != cur[3]]
    return min(cands, key=lambda b: (abs(b[0] - y), abs(b[1] - x)))[3] if cands else cur[3]


def typed_char(key):
    """getkey 값이 검색어에 넣을 글자인가 — 방향키·Enter 같은 curses 특수키(KEY_MIN~KEY_MAX)와 제어 문자는 아니다.
    전엔 방향키(259 = 'ă')도 '출력 가능한 글자'로 판정돼 검색어에 들어갔다(2026-11-05)."""
    return 32 < key < 0x110000 and not curses.KEY_MIN <= key <= curses.KEY_MAX and chr(key).isprintable()


def pick_list(st, query='', sort=1):
    """팀 칸에 넣을 후보 가방 번호들 — 이름에 query 가 든 것, SORTS[sort] 순(처음은 레벨 높은 것부터)."""
    q = query.lower()
    return [i for i in bag_order(st, None, sort) if q in name(st['box'][i]['id']).lower() or q in st['box'][i].get('nick', '').lower()]


def slot_rows(st, k, query='', sort=1):
    """팀 k 번째 자리 고르기 목록 — 후보들, 그 자리가 차 있고 찾는 중이 아니면 맨 끝에 None(비우기).
    비우기를 맨 위에 두었더니 이름을 치고 바로 Enter 하면 넣는 대신 빠졌다(2026-11-05)."""
    filled = k >= 0 and k < len([j for j in st.get('team', []) if j < len(st['box'])])  # k == -1 은 동료 고르기
    return pick_list(st, query, sort) + ([None] if filled and not query else [])


def set_slot(st, k, i):
    """팀 k 번째 자리에 가방 i 번째를(None 이면 비우기) — 이미 팀에 있으면 두 자리를 맞바꾼다. 결과 메시지."""
    team = [j for j in st.setdefault('team', []) if j < len(st['box'])]
    if i is None:
        if k < len(team):
            gone = team.pop(k)
            st['team'] = team
            return L(f'{name(st["box"][gone]["id"])}(을)를 팀에서 뺐다.', f'Took {name(st["box"][gone]["id"])} off the team.')
        return ''
    if i in team:
        j = team.index(i)
        if k < len(team):
            team[j], team[k] = team[k], team[j]
        st['team'] = team
        return L(f'{name(st["box"][i]["id"])}의 자리를 옮겼다.', f'Moved {name(st["box"][i]["id"])}.')
    if k < len(team):
        team[k] = i
    elif len(team) < _battle.TEAM_MAX:
        team.append(i)
    st['team'] = team
    return L(f'{name(st["box"][i]["id"])}(을)를 팀에 넣었다.', f'{name(st["box"][i]["id"])} joined the team.')


def egg_art(km, y, w):
    """알 그림 한 줄 높이 — (y, 1). 직접 그린 그림(_pokedata.egg_px)이라 받을 것이 없다. 못 놓거나 좁으면 None."""
    if w < 44 or not (SIXEL or KITTY):
        return None
    cw_, ch_ = _gfx.cell_px()
    img = _pokedata.egg_image(km, int(ch_), 'six' if SIXEL else 'png')
    cols = math.ceil(img[1] / cw_)
    return ('six', y, 1, ('egg', km, y), img[0], cols, 2) if SIXEL else ('kitty', y, 1, 300000 + km * 100 + y, img[0], cols, 1)  # 같은 종류 알이 둘이어도 따로 놓이게 줄도 번호에


def join_art(a, b):
    """그림 둘을 한 번에 놓을 하나로 — 화면엔 그림 자리가 하나뿐이라(장식 배지 + 동료). 하나가 None 이면 다른 하나."""
    if not a or not b:
        return a or b
    more = list(a[7]) if len(a) > 7 else []  # 셋째부터는 a 에 이미 붙은 것 뒤로
    if a[0] == 'six':  # 열쇠에 모두 담아야 어느 쪽이 바뀌어도 다시 놓인다
        return ('six', a[1], a[2], (a[3], b[3]), a[4], a[5], a[6], more + [(b[1], b[2], b[4])])
    return (*a[:7], more + [b[1:]])


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
            'super10': (st['super_earned'] or 0, 10), 'hyper1': (st['exchanged'], 1),
            **{f'tower{k}': (st.get('tower', {}).get('best', 0), k) for k in (7, 21, 49, 100)}}.get(b)


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


MEDAL_GROUPS = [  # 훈장 화면 왼쪽 분류 (한국어, 영어, 훈장 번호 앞부분들) — 어디에도 안 맞는 새 훈장은 '기타'로
    ('포획', 'Catches', ('catch',)), ('도감', 'Pokédex', ('gen',)), ('이로치', 'Shinies', ('shiny',)),
    ('전설·환상', 'Legends', ('legend', 'myth')), ('진화', 'Evolution', ('evo', 'final')), ('볼', 'Balls', ('super', 'hyper')),
    ('지방 정복', 'Conquests', ('conquer',)), ('챔피언', 'Champions', ('champ',)),
    ('특수 모습', 'Forms', ('form', 'fuse', 'mega', 'gmax')), ('연구', 'Research', ('research',)),
    ('배틀·레이드', 'Battles', ('alpha', 'raid', 'tower'))]


def medal_groups(st):
    """훈장 화면 왼쪽 열 [(이름, [번호…])] — 맨 위 '장식 중'(가진 장식 — 체육관 배지 포함), 그 아래 MEDAL_GROUPS 분류(2026-11-05 사용자)."""
    ids = [b for b, _, _, _ in BADGES]
    out = [(L('장식 중', 'Showing'), [b for b in st.get('showcase', []) if owned(st, b)])]
    used = set()
    for ko, en, pre in MEDAL_GROUPS:
        grp = [b for b in ids if b.startswith(pre) and b not in used]
        used.update(grp)
        if grp:
            out.append((L(ko, en), grp))
    rest = [b for b in ids if b not in used]
    return out + ([(L('기타', 'Other'), rest)] if rest else [])


GYM_COST, LEAGUE_COST = 2, 4  # 체육관 · 사천왕 도전 1회에 쓰는 탐색 기회
GYM_WIN_XP, GYM_LOSE_XP = 60, 30  # 팀원마다 받는 배틀 경험치(이기면 + 체육관 순서 × 10)


def box_level(m):
    return _battle.level(depth(m['id']), m.get('bxp', 0))


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
    """team_of 결과 → 배틀에 넣을 [(종, 레벨, 개체값[, HP 배수, 능력치 배수])] — 우두머리는 ALPHA_BOOST."""
    return [(n, lv, iv_of(st['box'][k])) + alpha_x(st['box'][k]) for k, n, lv in team]


def alpha_x(m):
    """배틀 튜플 꼬리 — 우두머리면 (HP 배수 1, ALPHA_BOOST), 아니면 ()."""
    return (1, ALPHA_BOOST) if m.get('alpha') else ()


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
    tool_key = f'fuse:{m["id"]}'
    tool, tool_name = st.get('items', {}).get(tool_key, 0) > 0, item_name(tool_key) if m['id'] in FUSE_ITEMS else ''
    for f, j in fuse_options(st, i):  # 합체 도구가 있어야 — 그 기본 포켓몬 연구를 끝내면 받는다
        out.append((f, ('mon', j), tool, '' if tool else L(f'{tool_name} 없음 — {name(m["id"])} 연구를 끝내면 받는다',
                                                           f'no {tool_name} — finish {name(m["id"])}\'s research')))
    for p, (s, kind, g, *_) in SPECIALS.items():
        if (m['id'] not in ULTRA_BASE) if kind == 'ultra' else m['id'] != s:
            continue
        key = 'soup' if kind == 'gmax' else f'stone:{p}'
        why = L(f'{g}세대가 열리면', f'opens with Gen {g}') if opened_gen(st) < g else \
            '' if st.get('items', {}).get(key, 0) > 0 else L('재료 없음', 'no material')
        out.append((p, ('item', key), not why, why))
    iv, items = iv_of(m), st.get('items', {})  # 병뚜껑(배틀 타워 상) — 특훈: 은색은 고른 하나 +1, 금색은 고른 하나를 15로(2026-11-06 사용자)
    for kind, key in (('iv', 'cap'), ('ivmax', 'gcap')):
        out += [((kind, k), ('item', key), True, '') for k in range(6) if iv[k] < 15 and items.get(key, 0) > 0]
    return out


def opt_name(f):
    """바꾸기 화면 한 칸의 이름 — 모습 번호면 그 이름, ('iv', k) 면 은색 특훈('공 +1'), ('ivmax', k) 면 금색('공 15로')."""
    if isinstance(f, tuple):
        ko, en = ('HP', '공격', '방어', '특공', '특방', '스피드')[f[1]], ('HP', 'Attack', 'Defense', 'Sp. Atk', 'Sp. Def', 'Speed')[f[1]]
        return L(f'{ko} +1', f'{en} +1') if f[0] == 'iv' else L(f'{ko} 15로', f'{en} to 15')
    return name(f)


def cap_max(st, i, f):
    """은색 병뚜껑을 그 능력치에 한 번에 쓸 수 있는 개수 — 15까지 남은 칸과 가진 개수 중 작은 쪽(2026-11-10 사용자)."""
    return max(0, min(15 - iv_of(st['box'][i])[f[1]], st.get('items', {}).get('cap', 0)))


def change(st, i, k, n=1):
    """change_options 의 k 번째로 바꾼다 — 바뀐 모습 번호 · 못 하면 None. 가방 번호가 당겨질 수 있다(합체 상대가 빠지면).
    n: 은색 병뚜껑을 그 능력치에 몇 개 쓰나(1 ~ cap_max) — 능력치마다 하나씩 되풀이하던 걸 한 번에(2026-11-10 사용자)."""
    opts = change_options(st, i)
    if not 0 <= k < len(opts) or not opts[k][2]:
        return None
    f, (what, ref), _, _ = opts[k]
    if isinstance(f, tuple):  # 특훈 — 모습은 그대로, 개체값만
        n = max(1, min(n, cap_max(st, i, f))) if f[0] == 'iv' else 1
        st['items'][ref] -= n
        m = st['box'][i]
        m['iv'] = [(min(15, v + n) if f[0] == 'iv' else 15) if j == f[1] else v for j, v in enumerate(iv_of(m))]
        if all(v == 15 for v in m['iv']):
            give_ribbon(st, [i], 'effort')
        return f
    if what == 'mon':
        i = _drop(st, {ref})[i]  # 합체 상대는 사라진다(2026-10-30 — 분리 없음, 다른 모습은 재료를 다시 모아서)
        st['fusions'] = st.get('fusions', 0) + 1
    else:
        st['items'][ref] -= 1
        _mark(st, 'specials', f)
        research_bump(st, f, 'm')
    st['box'][i]['id'] = f
    return f


def fuse_options(st, i):
    """가방 i 번째(기본: 큐레무·네크로즈마·버드렉스, 합체 전)와 합칠 재료 [(합체 모습, 재료 가방 번호)] — 재료 종마다 하나,
    동료·합체한 것은 빼고 팀 밖에서 개체값·경험치가 낮은 것부터(개체값·레벨은 기본을 따르니 재료는 아까운 걸 쓰지 않게).
    아직 가방에 없는 합체 모습이 앞."""
    m = st['box'][i]
    out = []
    for f, (base, part, _, _) in FUSIONS.items():
        if m['id'] != base:
            continue
        cands = [j for j, o in enumerate(st['box']) if o['id'] == part and j not in (i, st['partner'])]
        if cands:
            out.append((f, min(cands, key=lambda j: (j in st.get('team', []), sum(iv_of(st['box'][j])), st['box'][j].get('bxp', 0)))))
    have = {o['id'] for o in st['box']}
    return sorted(out, key=lambda o: o[0] in have)


def made(m):
    """재료를 써서 만든 모습(합체·메가 등)인가 — 되돌릴 수 없으니 박사에게도, [정리]로도 보내지 않는다."""
    return m['id'] in FUSIONS or m['id'] in SPECIALS


def send_away(st, idxs):
    """가방의 idxs 번째들을 박사에게 — 동료·팀·이로치·우두머리는 빼고. 하나마다 dupe_balls 만큼 몬스터볼.
    가방 번호가 당겨지니 동료·팀 번호도 맞춰 옮긴다. (보낸 마릿수, 받은 볼)."""
    keep = {st['partner']} | set(st.get('team', []))
    gone = {i for i in idxs if 0 <= i < len(st['box']) and i not in keep and not st['box'][i].get('shiny')
            and not st['box'][i].get('alpha') and not made(st['box'][i])}
    if not gone:
        return 0, 0
    k = sum(dupe_balls(st['box'][i]['id']) for i in gone)
    _drop(st, gone)
    st['balls'] += k
    st['sent'] = st.get('sent', 0) + len(gone)
    return len(gone), k


def tidy_key(st, i):
    """중복 정리에서 x 로 뺀 포켓몬을 알아보는 열쇠 — 키를 누를 때마다 저장 파일을 다시 읽어 객체가 바뀌므로, 가방 번호와 내용으로."""
    return i, json.dumps(st['box'][i], sort_keys=True)


def tidy_targets(st):
    """[정리]로 보낼 가방 번호 — 같은 종(이로치 빼고)이 둘 이상이면 개체값이 가장 좋은 것, 배틀 경험치가 가장 많은 것,
    진화 경험치가 가장 많은 것만 남긴다(동료·팀은 send_away 가 지킨다)."""
    groups = {}
    for i, m in enumerate(st['box']):
        if not m.get('shiny') and not m.get('alpha') and not made(m):
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


def tower_state(st):
    """배틀 타워 기록 {'streak': 지금 연승, 'best': 최고, 'run': 도전 중인가, 'seed': 이번 도전의 상대 순서}."""
    return st.setdefault('tower', {'streak': 0, 'best': 0, 'run': False, 'seed': 0})


def tower_opp(st, s=None):
    """s 연승째 상대 3마리 [(종, 레벨, 개체값)] — 열린 세대 최종 진화형(전설 빼고), 7연승마다 한 단계 강해진다.
    7번째 판(6, 13, …)은 레벨 +3, 49번째 판(48, 97, …)은 '타워 타이쿤' — 하나가 전설. 이번 도전(seed) 안에서는 늘 같은 상대."""
    tw = tower_state(st)
    s = tw['streak'] if s is None else s
    tier, g = s // 7, opened_gen(st)
    rng = random.Random(f'tower:{tw["seed"]}:{s}')
    pool = sorted(n for n in DEX if n not in CHILDREN and not DEX[n][5] and gen(n) <= g)
    team = rng.sample(pool, TOWER_SIZE)
    if s % 49 == 48:
        team[-1] = rng.choice(sorted(n for n in DEX if DEX[n][5] == 1 and gen(n) <= g) or pool)
    lv = TOWER_LV0 + tier * TOWER_LV_STEP + (3 if s % 7 == 6 else 0)
    return [(n, lv, (min(15, 6 + tier),) * 6) for n in team]


def gym_opp(d, g, i, st=None):
    """체육관 상대 — 전설·환상은 나오지 않는다. i 가 'L' 이면 사천왕·챔피언 팀들 [[(종, 레벨)] × 5],
    'R' 이면 이번 주 레이드 보스 하나 [(종, 8관 레벨 + 2, 개체값 15, HP ×RAID_HP)]."""
    if i == 'T':
        return tower_opp(st)
    if i == 'R':
        return [(raid_boss(st)[1], 12 + 7 * 7 + (g - 1) * 5 + _battle.OPP_LV_BONUS + 2, (15,) * 6, RAID_HP)]
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
    return ([(raid[0], 'R')] if raid and not raid_state(st)['done'] else []) + ([(0, 'T')] if st.get('league') else []) + \
        [(g, i) for g in gym_gens(st) for i in list(range(8)) + (['L'] if f'conquer{g}' in st['badges'] else [])]


def gym_left(st):
    """체육관 화면 왼쪽 열 [('R', 세대) · ('T', 0) · ('G', 세대)] — 레이드 · 배틀 타워 · 열린 세대들(2026-11-05 사용자)."""
    raid = raid_boss(st)
    return ([('R', raid[0])] if raid and not raid_state(st)['done'] else []) + ([('T', 0)] if st.get('league') else []) + \
        [('G', g) for g in gym_gens(st)]


def gym_right(st, g):
    """체육관 화면 오른쪽 열 — g 세대 1~8관, 8관을 모두 이기면 사천왕·챔피언 [(세대, 관 또는 'L')]."""
    return [(g, i) for i in range(8)] + ([(g, 'L')] if f'conquer{g}' in st['badges'] else [])


def gym_start(st):
    """체육관을 열 때 왼쪽에서 고를 줄 — 아직 못 이긴 관·사천왕이 남은 가장 앞 세대, 다 이겼으면 가장 뒤 세대."""
    left = gym_left(st)
    gens = [k for k, (kind, _) in enumerate(left) if kind == 'G']
    for k in gens:
        g = left[k][1]
        if any(f'gym:{g}-{i}' not in st.get('gym', {}) for i in range(8)) or str(g) not in st.get('league', {}):
            return k
    return gens[-1] if gens else 0


def gym_gens(st):
    """도전할 수 있는 세대 — 도감이 열린 세대까지."""
    return range(1, opened_gen(st) + 1)


def fight(st, t, d, g, i, rng=random, today=None):
    """체육관 도전 — 탐색 GYM_COST 회를 쓰고 자동 배틀. 팀원 모두 배틀 경험치를 받고, 처음 이기면 그 관의 배지
    와 하이퍼볼 1개(마스터볼은 한 세대 8관을 모두 이겼을 때 지방 정복 훈장과 함께 — check_badges).
    (이겼나, 기록, 처음 이겼나) · 도전할 수 없으면 (None, 이유, False). 결과는 기록을 보여 주기 전에 바로 적용한다."""
    team = team_of(st)[:TOWER_SIZE] if i == 'T' else team_of(st, None if i == 'R' else g)  # 레이드·타워는 모든 세대
    cost = LEAGUE_COST if i == 'L' else RAID_COST if i == 'R' else (0 if tower_state(st)['run'] else TOWER_COST) if i == 'T' else GYM_COST
    if i == 'R' and raid_state(st)['won']:
        return None, L('이번 주 레이드는 이미 이겼다 — 메인 화면에서 레이드볼로 잡자.', 'You already beat this raid — catch it with Raid Balls on the main screen.'), False
    if not team:
        return None, L(f'팀에 {g}세대 포켓몬이 없다 — {g}세대 포켓몬만 나갈 수 있다. 가방에서 [팀]으로 넣거나 [추천] → [적용]을 하자.',
                       f'No Gen {g} Pokémon on the team — only Gen {g} may enter. Add with [team] in the bag, or [pick] → [apply].'), False
    if tickets(st, t) < cost:
        return None, L(f'탐색 기회가 {cost}번 있어야 도전할 수 있다.', f'You need {cost} explores to challenge.'), False
    st['used'] += cost
    if i == 'T' and not tower_state(st)['run']:  # 새 도전 — 연승 0부터, 상대 순서를 새로
        tower_state(st).update(run=True, streak=0, seed=rng.randrange(1 << 30))
    mine = fighters(st, team)
    won, ev = (_battle.gauntlet(d, mine, gym_opp(d, g, i, st), rng) if i == 'L' else _battle.battle(d, mine, gym_opp(d, g, i, st), rng))
    for k, n, _ in team:
        st['box'][k]['bxp'] = st['box'][k].get('bxp', 0) + (GYM_WIN_XP + 10 * (8 if i in ('L', 'R', 'T') else i) if won else GYM_LOSE_XP)
        if won:
            research_bump(st, n if n in SPECIALS else sp(n), 'w')  # 특수 모습은 그 모습 도감에, 리전폼은 원래 종에
    day, first = today or datetime.now().astimezone().strftime('%Y-%m-%d'), False
    if won:
        bump(st, 'gym')
    if won and i == 'L':
        give_ribbon(st, [k for k, _, _ in team], f'champ{g}')
    if i == 'T':  # 타워 — 이기면 연승 +1(TOWER_PRIZES 마다 상), 지면 도전 끝
        tw = tower_state(st)
        if won:
            tw['streak'] += 1
            tw['best'] = max(tw['best'], tw['streak'])
            if f'tower{tw["streak"]}' in RIBBONS:
                give_ribbon(st, [k for k, _, _ in team], f'tower{tw["streak"]}')
            for every, prize in TOWER_PRIZES:
                if tw['streak'] % every == 0:
                    for key, k in prize:
                        if key in ('cap', 'gcap'):
                            give_item(st, key, k)
                        else:
                            st[key] += k
        else:
            tw.update(run=False, streak=0)
    elif won and i == 'R':  # 레이드 — 레이드볼 RAID_BALLS 개로 잡을 기회(다른 야생과 만나는 중이면 그게 끝난 뒤)
        r = raid_state(st)
        r['won'], r['pending'] = True, True
        give_ribbon(st, [k for k, _, _ in team], 'raid')
        give_item(st, 'soup')  # 거다이맥스 재료 — 쓰는 건 8세대가 열린 뒤
        raid_release(st)
        tell(st, 'raid', str(raid_boss(st)[1]))
    elif won and i == 'L' and str(g) not in st.setdefault('league', {}):
        st['league'][str(g)] = day  # 챔피언 훈장(마스터볼)은 check_badges 가
        tell(st, 'league', str(g))
        if g < GENS and not gen_done(st, g):
            if not wild_left(st, g):
                tell(st, 'opengen', str(g + 1))
            else:
                st.setdefault('genwait', []).append(g)  # load 가 또 알리지 않게
                tell(st, 'genwait', f'{g}|{len(wild_left(st, g))}')
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


def frame(scr, y, x, hh, ww, attr=curses.A_DIM):
    """(y, x) 에 hh×ww 둥근 테두리 — 안은 비워 둔다."""
    put(scr, y, x, '╭' + '─' * (ww - 2) + '╮', attr)
    for r in range(y + 1, y + hh - 1):
        put(scr, r, x, '│', attr)
        put(scr, r, x + ww - 1, '│', attr)
    put(scr, y + hh - 1, x, '╰' + '─' * (ww - 2) + '╯', attr)


def hp_box(scr, y, x, ww, n, lv, hp, top, mine):
    """배틀 상태 상자 — 이름·레벨, HP 막대(반 넘으면 녹색 · 5분의 1 넘으면 노랑 · 그 밑 빨강), 내 쪽만 숫자(원작처럼). 차지한 줄 수."""
    hh = 5 if mine else 4
    frame(scr, y, x, hh, ww)
    lvt = f'Lv{lv}'
    put(scr, y + 1, x + 2, fit(name(n), ww - 5 - len(lvt)), curses.A_BOLD)
    put(scr, y + 1, x + ww - 2 - len(lvt), lvt)
    frac = hp / top if top else 0
    color = curses.color_pair(1 if frac > 0.5 else 2 if frac > 0.2 else 3)
    x2 = put(scr, y + 2, x + 2, 'HP ', curses.A_BOLD)
    put(scr, y + 2, x2, bar(frac, x + ww - 2 - x2), color | curses.A_BOLD)
    if mine:
        num = f'{hp}/{top}'
        put(scr, y + 3, x + ww - 2 - len(num), num)
    return hh


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
    ukey, chg_from, chg_only = None, 'bag', []  # 가방에서 고른 아이템 · 바꾸기 화면에서 돌아갈 곳
    ball_pick = None  # 만남 화면에서 고른 볼(던지기 전까지는 고르기만)
    bag_sel, use_sel, cap_n = 0, 0, 1  # 가방·사용 화면에서 들어가기 전에 고르던 줄(돌아오면 그 줄로) · 은색 병뚜껑 쓸 개수
    pslot, query, pick_sort = 0, '', 1  # 팀 칸 고르기: 몇 번째 자리 · 이름 찾기 · 정렬(처음은 레벨순)
    mon_i, naming = None, None  # 포켓몬 상세 화면의 가방 번호 · 이름 짓는 중이면 입력 중인 글(아니면 None)
    searching = False  # 이름 찾기 입력 중인가 — F 로 켜고 Enter(검색어 유지)·Esc(지움)로 끈다(2026-11-05 사용자)
    gcol, gsub, gtop = 0, 0, 0  # 체육관 화면: 커서가 있는 열(0 왼쪽 · 1 오른쪽) · 오른쪽에서 고른 줄 · 오른쪽 맨 위 줄
    tm, tcol = 0, 0  # 교환 화면: 왼쪽에서 고른 일(0 박사에게 · 1 중복 정리 · 2 볼 바꾸기) · 커서가 있는 열 — 오른쪽 줄은 sel·top
    tidy_skip = set()  # 중복 정리에서 x 로 뺀 포켓몬(tidy_key) — 교환 화면에 있는 동안만, 보내면 비운다(2026-11-10 사용자)
    bcat, bcol = 0, 0  # 훈장 화면: 왼쪽에서 고른 분류 · 커서가 있는 열 — 오른쪽 줄은 sel·top
    order, bag_sort = [], _lang.get('bag_sort', 0) % len(SORTS)  # 교환: 보이는 순서(가방 번호들) · 정렬  # confirm: 한 번 더 누르면 보낼 것  # 고른 체육관 · 추천 (체육관, 팀, 승률) · 배틀 재생 · 승률 캐시
    focus = None  # 고른 버튼(act) — 방향키로 옮기고 Enter 로 누른다. 단축키는 q(닫기)만 남겼다(2026-10-21)
    BATTLE = _battle.load()  # 체육관을 처음 열 때 없으면 받는다
    TYPES.update(BATTLE['types'] if BATTLE else {})  # 서식지 — 타입 자료가 없으면 거르지 않는다
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
    self_path = os.path.abspath(__file__)
    code_stamp = lambda: max(os.path.getmtime(p) for p in glob.glob(os.path.join(os.path.dirname(self_path), '*.py')))  # noqa: E731
    code_mine = code_seen = code_stamp()
    code_at = time.time()
    while True:
        # 코드가 바뀌면(머지·자동 업데이트) 같은 인자로 다시 뜬다 — 열어 둔 화면이 옛 코드로 남지 않게(2026-11-05 사용자).
        # 허브와 같은 규칙: 파일이 5초 동안 안 바뀐 뒤, 새 파일에도 재시작 코드가 있을 때만. 진행은 저장 파일에 있고 화면만 처음으로.
        stamp = code_stamp()
        if stamp != code_seen:
            code_seen, code_at = stamp, time.time()
        elif stamp != code_mine and time.time() - code_at >= 5:
            with open(self_path, encoding='utf-8') as f:
                restartable = 'os.execv(' in f.read()
            if restartable:
                if _gfx._six['key'] is not None:
                    _gfx.redraw()
                _gfx.kitty_hide(free=True)
                curses.endwin()
                os.execv(sys.executable, [sys.executable, self_path] + sys.argv[1:])
            code_mine = stamp  # 재시작 못 하는 버전이면 지금 코드로 계속
        st, t = load(), total_tokens()
        if st.get('_broken'):  # 빈 게임처럼 보여 주지 않는다 — 파일이 다시 읽히면 2초 안에 이어진다
            scr.erase()
            put(scr, 0, 0, L('저장 파일을 읽지 못했습니다 — 덮어쓰지 않고 기다립니다', "Can't read the save — waiting, not overwriting"), curses.A_BOLD)
            put(scr, 1, 0, f'{ROOT}/pokemon.json' + L(' (깨졌으면 사본: pokemon.json.bad)', ' (if corrupt, a copy: pokemon.json.bad)'))
            put(scr, 3, 0, L('q 를 누르면 닫습니다', 'Press q to close'), curses.A_DIM)
            scr.refresh()
            if getkey(scr, 2000) in (ord('q'), 27):
                return
            continue
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
            _gfx.sixel_touch()  # 기록이 한 줄 늘 때마다 tmux 가 패널을 다시 그려 Sixel 그림을 지운다 — 30초 아끼지 말고 다시 놓는다
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
            # 2026-11-05 사용자 설계: ① 맨 위 장식 · ② 동료 그림 · ③ 이름 · ④ 진화 게이지 · ⑤ 오른쪽 네모 버튼 · ⑥ 팀 3×2
            x0 = w - SIDE_W if w >= 56 else w  # 오른쪽 버튼 열이 시작하는 칸 — 아주 좁으면 버튼 열 없이(아래 한 줄)
            lw = x0  # 왼쪽 글은 이 폭에서 접는다(para 는 lw - x - 1 칸)
            _, art = draw_showcase(scr, st, 1, x0)
            pr = 2 if h < 28 else 3 if h < 36 else 4  # 동료 그림 높이 — 큰 패널이면 키운다
            if st['partner'] is None:
                para(scr, 3, L('아직 동료가 없습니다. 풀숲을 탐색해 보세요.', 'No partner yet. Try exploring the tall grass.'), lw)
            else:
                m = st['box'][st['partner']]
                n = m['id']
                pic = mon_art(partner_id_of(st), 3, w, 1, pr, max(8, x0 // 3))
                art = join_art(art, pic)
                px = pic[5] + 3 if pic else 1
                y = 3 + (pr - 2) // 2  # 이름·게이지 두 줄은 그림 높이의 가운데에
                plabel = (L('✨이로치 ', '✨shiny ') if m.get('shiny') else '') + ('◆' if m.get('alpha') else '') + mon_name(m) + f'  Lv.{box_level(m)}'
                put(scr, y, px, plabel, gold if m.get('shiny') else curses.A_BOLD)
                btns.extend((3 + r, 1, x0 - 2, 'partner_pick') for r in range(max(2, pr)))  # 동료를 누르면 동료 고르기(2026-11-05 사용자)
                navbtns.append((y, px, px + memo_w(plabel), 'partner_pick', plabel))
                ev = evo_status(st, t)
                if ev[0] == 'final':
                    put(scr, y + 1, px, L('최종 진화', 'fully evolved'), curses.A_DIM)
                elif ev[0] == 'locked':
                    put(scr, y + 1, px, L('진화는 다음 세대가 열리면', 'evolves once the next generation opens'), curses.A_DIM)
                elif ev[0] == 'ready':
                    x = put(scr, y + 1, px, L('✨ 진화할 수 있다!', '✨ It can evolve!'), curses.A_BOLD)
                    button(y + 1, x + 2, L('진화', 'evolve'), 'evolve')
                else:
                    x = put(scr, y + 1, px, L('진화 ', 'Evolve '))
                    put(scr, y + 1, x, f'{bar(ev[1] / ev[2], max(6, min(16, x0 - x - 16)))} {fmt_tok(ev[1])}/{fmt_tok(ev[2])}')
            y = 3 + pr + 1  # 팀은 동료 그림 아래 한 줄 띄고
            # 아래 글(알 · 주간 과제 · 볼 · 메시지)이 차지할 줄을 먼저 세고, 남은 줄로 팀 칸 크기를 정한다 — 패널 크기에 맞춰
            today = datetime.now().astimezone().strftime('%Y-%m-%d')
            done = len(shipped().get(today, ()))
            wk_gain = WEEKEND_EXPLORES if datetime.now().astimezone().weekday() >= 5 else WORK_EXPLORES
            weekly_line = weekly_text(st) + ' · ' + (L(f'오늘 탐색 +{wk_gain} ✔', f'+{wk_gain} explore today ✔') if today in st['rewarded'] else
                                                     L(f'오늘 push·PR·배포 {min(done, SUPER_SESSIONS)}/{SUPER_SESSIONS}', f'push/PR/deploy today {min(done, SUPER_SESSIONS)}/{SUPER_SESSIONS}')) \
                + L(f' · 연속 {streak(st, today)}일', f' · {streak(st, today)}-day streak')
            balls_line = L(f'몬스터볼\xa0{st["balls"]} · 슈퍼볼\xa0{st["super"]} · 하이퍼볼\xa0{st["hyper"]} · 마스터볼\xa0{st["master"]}',
                           f'Poké\xa0{st["balls"]} · Great\xa0{st["super"]} · Ultra\xa0{st["hyper"]} · Master\xa0{st["master"]}')  # 이름과 숫자는 붙여 접는다
            eggs = egg_lines(st, t)
            egg_h = 2 if w >= 44 and (SIXEL or KITTY) else 1  # 알 그림이 있으면 한 알에 2줄
            k = tickets(st, t)  # ⑤ 오른쪽 네모 버튼 — 맨 위는 가장 자주 누르는 풀숲 탐색
            explore_label = L('앗! 야생', 'Wild!') if st['wild'] else (L(f'{habitat(st)[1]} 탐색 {k}', f'{habitat(st)[2]} {k}') if k < 10 else L(f'{habitat(st)[1]} {k}', f'{habitat(st)[2]} {k}')) if k > 0 else \
                L(f'다음 {fmt_tok(ENCOUNTER_EVERY - t % ENCOUNTER_EVERY)}', f'next {fmt_tok(ENCOUNTER_EVERY - t % ENCOUNTER_EVERY)}')
            # 이름을 explore 라 하면 탐색 함수를 가려 눌렀을 때 꺼졌다(2026-11-05)
            side = [(explore_label, 'encounter' if st['wild'] else 'explore'), (L('도감', 'dex'), 'dex'), (L('가방', 'bag'), 'box'), (L('교환', 'trade'), 'trade'),
                    (L('훈장', 'medals'), 'badges'), (L('체육관', 'gyms'), 'gyms'), (L('닫기 q', 'close q'), 'close')]
            bw = lambda lb: memo_w(f'[{lb.removesuffix(" q") if w < 50 else lb}]') + 1 if tight else memo_w(f'[ {lb} ]') + 2  # noqa: E731 — button() 과 같은 폭
            btn_rows = wrap_widths([bw(lb) for lb, _ in side], w) if x0 >= w else []
            tw = max(10, lw - 1)  # 아래 글은 버튼 바로 앞 칸까지(2026-11-10 사용자 배치 — 22·24줄 패널 47칸)
            text_n = sum(len(fold(s, tw)) for s in (weekly_line, balls_line, ('💬 ' + msg) if msg else '') if s)
            below = len(btn_rows) + len(eggs) * egg_h + text_n
            cw3 = max(10, (x0 - 1) // 3)
            graphics = w >= 44 and (SIXEL or KITTY)
            cw_, ch_ = _gfx.cell_px() if graphics else (1, 2)
            cell_h, art_rows = team_layout(h - y - below, graphics, max(1, int((cw3 - 1) * cw_ / ch_)))  # 그림은 대개 정사각형
            if h < 28 and art_rows:  # 작은 패널은 동료 그림처럼 2줄, 이름·개체값을 바로 아래 — 칸 사이 빈 줄 없이(2026-11-10 사용자 배치)
                art_rows = min(art_rows, 2)
                cell_h = art_rows + 2
            # ⑥ 팀 3×2 — 칸마다 그림 · 이름 레벨 · 개체값. 칸에서 Enter 면 그 자리에 넣을 포켓몬 고르기(slotpick)
            team = [i for i in st.get('team', []) if i < len(st['box'])]
            for k in range(_battle.TEAM_MAX):
                cy, cx = y + (k // 3) * cell_h, 1 + (k % 3) * cw3
                ly = cy + art_rows  # 이름 줄 — 그림 바로 아래
                if k < len(team):
                    mm = st['box'][team[k]]
                    pic = mon_art(art_of(mm), cy, w, cx, art_rows, cw3 - 1)
                    art = join_art(art, pic)
                    label = fit(('◆' if mm.get('alpha') else '') + mon_name(mm), cw3 - 7) + f' Lv.{box_level(mm)}'
                    put(scr, ly + 1, cx, iv_text(mm, False), curses.A_DIM)
                else:
                    label = L('(빈칸)', '(empty)')
                btns.extend((cy + r, cx, cx + cw3 - 1, ('slot', k)) for r in range(art_rows + 2))
                navbtns.append((ly, cx, cx + memo_w(label), ('slot', k), label))
                put(scr, ly, cx, label, (gold if k < len(team) and st['box'][team[k]].get('shiny') else 0) | (0 if k < len(team) else curses.A_DIM))
            y += 2 * cell_h
            # 알은 팀 아래 한 줄 띄고, 볼·주간 과제는 맨 아래(버튼 열 끝과 같은 줄)에 붙인다 — 줄이 모자라면 띄우지 않는다
            # (2026-11-10 사용자 배치: 24줄이면 알 15줄 · 볼 18줄 · 주간 과제 20~22줄)
            last = h - 1 - len(btn_rows)  # 아래 글이 쓸 수 있는 줄 끝(이 줄은 안 씀)
            if last - y >= len(eggs) * egg_h + text_n + 1:
                y += 1
            for text, frac, km in eggs:
                pic = egg_art(km, y, w)
                art = join_art(art, pic)
                x = put(scr, y, pic[5] + 2 if pic else 1, ('' if pic else '🥚 ') + text + ' ')
                put(scr, y, x, bar(frac, max(10, lw - x)), curses.A_DIM)  # 막대는 버튼 바로 앞 칸(lw - 1)까지
                y += egg_h
            y = max(y, last - text_n)
            stop = h - len(btn_rows)  # 아래 글은 버튼 줄 위에서 멈춘다 — 모자라면 볼·메시지를 먼저, 주간 과제는 남는 만큼
            for text, attr in ((balls_line, 0), (('💬 ' + msg) if msg else '', 0), (weekly_line, curses.A_DIM)) if h - y < below - len(btn_rows) \
                    else ((weekly_line, curses.A_DIM), (balls_line, 0), (('💬 ' + msg) if msg else '', 0)):
                for line in fold(text, tw) if text else []:
                    if y >= stop:
                        break
                    put(scr, y, 1, line, attr)
                    y += 1
            if x0 < w:
                side_buttons(scr, side, x0, 2, h, btns, navbtns)
            else:  # 좁으면 버튼을 맨 아래에 — 한 줄에 안 들어가면 여러 줄로(위에서 그 줄 수만큼 비워 두었다)
                for r, row in enumerate(btn_rows):
                    x = 1
                    for i in row:
                        x = button(h - len(btn_rows) + r, x, side[i][0], side[i][1])
        elif view == 'wild':  # 풀숲 만남(2026-11-05 사용자 설계) — ① 가운데 포켓몬 · ② 오른쪽 볼 고르기 · ③ 던지기 · ④ 도망
            wd = st['wild']
            sw = 18 if w >= 60 else 14  # 볼 버튼 열 — '몬스터볼 120' 이 들어가게
            x0 = w - sw
            sh = wd.get('shiny') and not wd.get('disguise')
            y = para(scr, 1, (L('레이드 보스 ', 'Raid boss ') if wd.get('raid') else
                              L('앗! 붉은 눈의 우두머리 ', 'Oh! An alpha ') if wd.get('alpha') else L('앗! 야생의 ', 'Oh! A wild '))
                     + (L('✨이로치 ', '✨shiny ') if sh else '') + (name(shown(wd)) if wd.get('alpha') else titled(wd.get('mark'), name(shown(wd))))
                     + L('(이)가 나타났다!', ' appeared!'), x0, gold | curses.A_BOLD if sh else curses.A_BOLD)
            if wd.get('alpha'):
                y = para(scr, y, L(f'볼 {ALPHA_TRIES - wd.get("tries", 0)}번 안에 못 잡으면 도망친다', f'Flees after {ALPHA_TRIES - wd.get("tries", 0)} more throws'), x0, curses.A_DIM)
            # ① 그림은 패널 한가운데, 폭의 ⅓ 쯤(실제로 보일 크기 기준) · ② 볼은 오른쪽 열 · ③④ 는 아래 가운데에 나란히
            # 높이는 패널에 맞춰(위아래 글·버튼 12줄을 뺀 절반), 폭은 ⅓ 쯤 — 단 오른쪽 볼 열을 넘지 않게
            art = big_art(art_of({'id': shown(wd), 'shiny': sh}), h // 2, w // 2, max(3, (h - 12) // 2), max(6, min(w // 3 + 2, 2 * (x0 - w // 2) - 2)))
            if not art:
                put(scr, h // 2, max(1, (w - memo_w(name(shown(wd)))) // 2), name(shown(wd)), gold if sh else curses.A_BOLD)
            ball_pick = default_ball(st, ball_pick)
            if ball_pick:  # 그림 바로 위에 고른 볼의 포획 확률 — 어떤 볼을 던질지 고르기 쉽게(2026-11-05 사용자)
                bname = L('레이드볼', 'Raid Ball') if wd.get('raid') else next(L(b[1], b[2]) for b in BALL_ORDER if b[0] == ball_pick)
                odds = L(f'{bname}로 잡을 확률 {catch_chance(st, ball_pick):.0%}', f'{bname}: {catch_chance(st, ball_pick):.0%} to catch')
                odds = fit(odds, x0 - 2)  # 볼 열에 붙거나 가리지 않게 — 가운데에 두되 볼 열 앞에서 멈춘다
                put(scr, max(2, (art[1] if art else h // 2) - 1), max(1, min(w // 2 - memo_w(odds) // 2, x0 - 1 - memo_w(odds))), odds, curses.A_BOLD)
            side = []
            for kind, k, can in ball_choices(st):
                ko, en = (('레이드볼', 'Raid') if wd.get('raid') else next((b[1], b[2]) for b in BALL_ORDER if b[0] == kind))
                side.append((('● ' if kind == ball_pick else '') + L(f'{ko} {k}', f'{en} {k}'), ('ball', kind),
                             curses.A_BOLD | (curses.A_UNDERLINE if kind == ball_pick else 0) if can else curses.A_DIM))
            side_buttons(scr, side, x0, 2, h - 6, btns, navbtns, sw + 1)
            note = msg or ('' if ball_pick else L('던질 수 있는 볼이 없다 — [교환]에서 바꿔 오거나 도망치자.', 'No ball to throw — swap in [trade], or run.'))
            put(scr, h - 5, max(1, (w - memo_w(fit(note, w - 2))) // 2), fit(note, w - 2), curses.A_DIM if not msg else 0)  # 한 줄 — 버튼과 겹치지 않게
            bw = max(10, min(16, w // 4))
            box_button(scr, h - 4, max(1, w // 2 - bw - 1), bw, L('던지기', 'throw'), 'throw_sel', btns, navbtns)
            box_button(scr, h - 4, w // 2 + 1, bw, L('놓아주기', 'let go') if wd.get('raid') else L('도망', 'run'), 'run', btns, navbtns)
        elif view == 'bag':  # 가방 = 아이템(2026-11-05 사용자) — 한 줄에 하나, U·Enter·클릭으로 쓸 포켓몬 고르기
            rows = bag_items(st)
            put(scr, 1, 1, msg or L('가방 — 아이템을 고르고 Enter 로 쓴다', 'Bag — pick an item, Enter to use it'), curses.A_DIM)
            body = h - 4
            sel = max(0, min(sel, len(rows) - 1))
            top = max(0, min(min(max(top, sel - body + 1), sel), len(rows) - body))
            for k, (key, c) in enumerate(rows[top:top + body]):
                text = item_name(key) + (L(f'  {c}개', f'  ×{c}') if c is not None else L('  (도구 — 재료 포켓몬이 사라진다)', '  (tool — uses up the partner Pokémon)'))
                btns.append((2 + k, 1, w - 1, ('bagitem', top + k)))
                put(scr, 2 + k, 1, text.ljust(w - 2) if top + k == sel else text, curses.A_REVERSE if top + k == sel else 0)
            if not rows:
                para(scr, 2, L('아이템이 없다 — 연구 완료·레이드·배틀 타워·주간 과제에서 얻는다.', 'No items yet — research, raids, the Battle Tower and weekly tasks give them.'), w, curses.A_DIM)
            button(h - 1, 1, L('돌아가기 q', 'back q'), 'back')  # 쓰기는 Enter·클릭(2026-11-05 사용자 — U 버튼 없음)
        elif view == 'use':  # 가방 → 아이템 → 쓸 포켓몬(F 이름 찾기 — 자리 고르기와 같게, 2026-11-06 사용자)
            rows = item_targets(st, ukey, query)
            put(scr, 1, 1, msg or item_name(ukey) + (L(f' — 찾기: {query}▏ · Enter 확정 · Esc 지우기', f' — find: {query}▏ · Enter keep · Esc clear') if searching else
                                                    L(f' — 누구에게 쓸까 · F 찾기{f" ({query})" if query else ""} · Enter', f' — use on whom? · F find{f" ({query})" if query else ""} · Enter')),
                curses.A_BOLD if searching else curses.A_DIM)
            body = h - 4
            sel = max(0, min(sel, len(rows) - 1))
            top = max(0, min(min(max(top, sel - body + 1), sel), len(rows) - body))
            for k, (i, ks, ok, why) in enumerate(rows[top:top + body]):
                mm = st['box'][i]
                text = (f'⚔ ' if i in st.get('team', []) else '♥ ' if i == st['partner'] else '  ') + ('◆' if mm.get('alpha') else '') + bag_text(mm, w - 7) + ('' if ok else f'  · {why}')
                btns.append((2 + k, 1, w - 1, ('userow', top + k)))
                put(scr, 2 + k, 1, text.ljust(w - 2) if top + k == sel else text, (curses.A_REVERSE if top + k == sel else 0) | (0 if ok else curses.A_DIM))
            if not rows:
                para(scr, 2, L('이 아이템을 쓸 수 있는 포켓몬이 없다.', 'No Pokémon can use this item.'), w, curses.A_DIM)
            else:
                put(scr, h - 2, 1, fit(iv_text(st['box'][rows[sel][0]]), w - 2), curses.A_DIM)
            x = button(h - 1, 1, L('쓰기', 'use'), 'use_sel')
            button(h - 1, x, L('돌아가기 q', 'back q'), 'back')
        elif view == 'mon':  # 포켓몬 상세(2026-11-10 사용자) — 증표·리본(PokeAPI 그림)·이름 짓기. 팀 자리 고르기에서 i
            m = st['box'][mon_i]
            sh, mk, rs = m.get('shiny'), m.get('mark'), m.get('ribbons', [])
            if naming is not None:
                put(scr, 1, 1, fit(L(f'이름: {naming}▏  Enter 저장 · Esc 취소 · 비우면 원래 이름', f'Name: {naming}▏  Enter save · Esc cancel · empty = species'), w - 2), curses.A_BOLD)
            else:
                put(scr, 1, 1, fit(msg or L('N 이름 짓기 · q 돌아가기', 'N name · q back'), w - 2), curses.A_DIM)
            head = ('✨' if sh else '') + ('◆' if m.get('alpha') else '') + titled(mk, mon_name(m)) \
                + (f'  ({name(m["id"])})' if m.get('nick') else '') + f'  Lv{box_level(m)}'
            put(scr, 2, 1, fit(head, w - 2), (gold if sh else 0) | curses.A_BOLD)
            put(scr, 3, 1, fit(iv_text(m), w - 2), curses.A_DIM)
            put(scr, 5, 1, fit(L('증표  ', 'Mark     ') + (mark_name(mk) if mk else L('없음 — 야생이 드물게 달고 나온다', 'none — wild ones rarely carry one')), w - 2),
                0 if mk else curses.A_DIM)
            put(scr, 6, 1, L(f'리본  {len(rs)}개', f'Ribbons  {len(rs)}'), 0 if rs else curses.A_DIM)
            y = 7
            if not rs:
                y = para(scr, y, L('받는 법 — ', 'How — ') + ribbon_how(), w, curses.A_DIM)
            for r in rs[:max(0, h - 13)]:  # 그림 자리(아래 4줄)를 남기고
                put(scr, y, 3, fit('· ' + L(RIBBONS[r][1], RIBBONS[r][2]), w - 4))
                y += 1
            keys = ([f'mark:{mk}-mark'] if mk else []) + [f'ribbon:{RIBBONS[r][0]}' for r in rs]
            per = max(1, (w - 4) // 8)  # 한 줄에 몇 개 — 3줄 높이 그림이 7칸쯤
            lines = -(-len(keys) // per) if keys else 0
            rows_ = min(3 * lines, h - 3 - (y + 1))
            if keys and rows_ >= 2:
                art = badge_art(st, keys, y + 1, 2, rows_, per if lines > 1 else 0)
                if art and art[5] > w - 4:
                    art = None
            x = button(h - 1, 1, L('이름 짓기 N', 'name N'), 'nick')
            button(h - 1, x, L('돌아가기 q', 'back q'), 'back')
        elif view == 'slotpick':  # 팀 칸 Enter — 이 자리에 넣을 포켓몬 고르기(이름 찾기 · Tab 정렬)
            team = [i for i in st.get('team', []) if i < len(st['box'])]
            rows = slot_rows(st, pslot, query, pick_sort)
            put(scr, 1, 1, msg or (L('동료', 'Partner') if pslot == -1 else L(f'팀 {pslot + 1}번 자리', f'Team slot {pslot + 1}'))
                + (L(f' — 찾기: {query}▏ · Enter 확정 · Esc 지우기', f' — find: {query}▏ · Enter keep · Esc clear') if searching else
                   L(f' — F 찾기{f" ({query})" if query else ""} · Tab 정렬 {SORTS[pick_sort][0]} · Enter 넣기 · q 돌아가기',
                     f' — F find{f" ({query})" if query else ""} · Tab sort {SORTS[pick_sort][1]} · Enter put · q back')),
                curses.A_BOLD if searching else curses.A_DIM)
            body = h - 4
            sel = max(0, min(sel, len(rows) - 1))
            top = max(0, min(min(max(top, sel - body + 1), sel), len(rows) - body))
            for k, i in enumerate(rows[top:top + body]):
                if i is None:
                    text, attr = L('— 이 자리 비우기 —', '— empty this slot —'), curses.A_DIM
                else:
                    mm = st['box'][i]
                    mark = (f'⚔{team.index(i) + 1} ' if i in team else '   ') + ('✨' if mm.get('shiny') else '') + ('◆' if mm.get('alpha') else '')
                    text, attr = mark + bag_text(mm, w - 11), gold if mm.get('shiny') else 0
                btns.append((2 + k, 1, w - 1, ('pickrow', top + k)))
                put(scr, 2 + k, 1, text.ljust(w - 2) if top + k == sel else text, attr | (curses.A_REVERSE if top + k == sel else 0))
            if not rows:
                put(scr, 2, 1, L('찾는 이름이 없다.', 'No match.'), curses.A_DIM)
            elif rows[sel] is not None:  # 고른 줄의 개체값 여섯 — 목록은 %만(2026-11-06 사용자)
                put(scr, h - 2, 1, fit(iv_text(st['box'][rows[sel]]), w - 2), curses.A_DIM)
            x = button(h - 1, 1, L('넣기', 'put'), 'pick_sel')
            x = button(h - 1, x, L('자세히 i', 'info i'), 'mon_open')
            button(h - 1, x, L('돌아가기 q', 'back q'), 'back')
        elif view == 'badges':  # 2026-11-05 사용자: 체육관처럼 두 열 — 왼쪽 장식 중·분류, 오른쪽 그 분류의 훈장
            groups = medal_groups(st)
            bcat = max(0, min(bcat, len(groups) - 1))
            lw = max(17, min(20, w // 3))  # '배틀·레이드 0/6' 이 잘리지 않게
            rx = lw + 2
            rw = w - rx - 1
            body = h - 4
            put(scr, 1, 1, msg or (L(f'훈장 {len(st["badges"])}/{len(BADGES)} · 장식 {len(st.get("showcase", []))}/{SHOWCASE_MAX} — '
                                     + ('↑↓ · Enter 장식 넣기/빼기 · ← q' if bcol else '↑↓ · → 안으로 · q 돌아가기'),
                                     f'Medals {len(st["badges"])}/{len(BADGES)} · shown {len(st.get("showcase", []))}/{SHOWCASE_MAX} — '
                                     + ('↑↓ · Enter show/hide · ← q' if bcol else '↑↓ · → into it · q back'))), curses.A_DIM)
            for k, (label, ids) in enumerate(groups):
                cur = k == bcat
                count = str(len(ids)) if k == 0 else f'{sum(1 for b in ids if owned(st, b))}/{len(ids)}'
                text = ('▶ ' if cur else '  ') + fit(f'{label} {count}', lw - 3)
                put(scr, 2 + k, 1, text.ljust(lw) if cur and not bcol else text, (curses.A_REVERSE if not bcol else curses.A_BOLD) if cur else 0)
                btns.append((2 + k, 1, lw, ('medleft', k)))
            ids = groups[bcat][1] if groups else []
            sel = max(0, min(sel, len(ids) - 1))
            top = max(0, min(min(max(top, sel - body + 1), sel), len(ids) - body))
            for k, b in enumerate(ids[top:top + body]):  # 받은 것은 날짜, 못 받은 것은 진행 · 📌 는 장식 중
                cur, got = bcol and top + k == sel, owned(st, b)
                goal = badge_goal(st, b)
                note = (st['badges'].get(b) or st.get('gym', {}).get(b, '')) if got else (f'{min(goal[0], goal[1])}/{goal[1]}' if goal else L('아직', 'not yet'))
                text = fit(('▶ ' if cur else '  ') + f'{badge_name(b)}  {note}' + (' 📌' if b in st.get('showcase', []) else ''), rw)
                put(scr, 2 + k, rx, text.ljust(rw) if cur else text, (curses.A_REVERSE if cur else 0) | (0 if got else curses.A_DIM))
                btns.append((2 + k, rx, w - 1, ('pin', b)))
            if not ids:
                put(scr, 2, rx, fit(L('장식한 것이 없다 — 분류에서 골라 Enter', 'Nothing shown — pick one in a category, Enter'), rw), curses.A_DIM)
            # 커서가 놓인 훈장 그림은 오른쪽 열 목록 바로 아래에(2026-11-05 사용자) — 남은 줄이 모자라면 작게, 2줄도 안 되면 생략
            ay = 2 + min(len(ids), body) + 1
            arows = min(4, h - 2 - ay)
            if bcol and ids and owned(st, ids[sel]) and arows >= 2:
                art = badge_art(st, [ids[sel]], ay, rx + 2, arows)
            button(h - 1, 1, L('돌아가기 q', 'back q'), 'back')
        elif view == 'gyms':  # 2026-11-05 사용자 설계: 왼쪽 레이드 · 배틀 타워 · 세대들, 오른쪽에 고른 세대의 관·사천왕
            left = gym_left(st)
            body = h - 4
            sel = max(0, min(sel, len(left) - 1))
            top = max(0, min(min(max(top, sel - body + 1), sel), len(left) - body))
            lw = max(14, min(26, w // 3))  # 왼쪽 열 폭
            rx = lw + 2  # 오른쪽 열이 시작하는 칸
            rw = w - rx - 1  # 오른쪽 글 폭
            put(scr, 1, 1, msg or (L('↑↓ 관 · ← 세대로 · Enter 도전 준비 · P 장식 · q 세대로', '↑↓ gym · ← back · Enter prepare · P show · q back') if gcol else
                                   L('↑↓ 고르기 · → 세대 안으로 · Enter · q 돌아가기', '↑↓ pick · → into the generation · Enter · q back')), curses.A_DIM)
            for k, (kind, g) in enumerate(left[top:top + body]):
                cur = top + k == sel
                if kind == 'R':
                    label = L(f'레이드 {name(raid_boss(st)[1])}', f'Raid {name(raid_boss(st)[1])}') + (' ✔' if raid_state(st)['won'] else '')
                elif kind == 'T':
                    tw = tower_state(st)
                    label = L(f'배틀 타워 {tw["streak"]}/{tw["best"]}', f'Tower {tw["streak"]}/{tw["best"]}')
                else:
                    have = sum(1 for i in range(8) if f'gym:{g}-{i}' in st.get('gym', {}))
                    label = L(f'{g}세대  {have}/8', f'Gen {g}  {have}/8') + (' 👑' if str(g) in st.get('league', {}) else '')
                attr = (curses.A_REVERSE if not gcol else curses.A_BOLD) if cur else (curses.A_BOLD if kind != 'G' else 0)
                put(scr, 2 + k, 1, (('▶ ' if cur else '  ') + fit(label, lw - 3)).ljust(lw) if cur and not gcol else ('▶ ' if cur else '  ') + fit(label, lw - 3), attr)
                btns.append((2 + k, 1, lw, ('gymleft', top + k)))
            kind, g = left[sel] if left else ('G', 1)
            if kind == 'G':
                right = gym_right(st, g)
                gsub = max(0, min(gsub, len(right) - 1))
                gtop = max(0, min(min(max(gtop, gsub - body + 2), gsub), len(right) - body + 1))
                for k, (gg, i) in enumerate(right[gtop:gtop + body - 1]):
                    y, cur = 2 + k, gcol and gtop + k == gsub
                    gkey = f'gym:{gg}-{i}'
                    if i == 'L':
                        won = st.get('league', {}).get(str(gg))
                        text = L('사천왕·챔피언', 'Elite Four')
                    else:
                        won = st.get('gym', {}).get(gkey)
                        tname = (BATTLE or {}).get('tnames', {}).get(_battle.GYMS[gg][i][0], ['', ''])
                        text = L(f'{i + 1}관 {tname[0]}', f'Gym {i + 1} {tname[1]}')
                    text += (f'  ✔ {won}' if won else '') + (' 📌' if (f'champ{gg}' if i == 'L' else gkey) in st.get('showcase', []) else '')
                    text = fit(('▶ ' if cur else '  ') + text, rw)
                    put(scr, y, rx, text.ljust(rw) if cur else text, (curses.A_REVERSE if cur else 0) | (0 if won else curses.A_DIM))
                    btns.append((y, rx, w - 1, ('gym', (gg, i))))
                ay = 2 + min(len(right), body - 1)
                if 'L' not in [i for _, i in right]:
                    put(scr, ay, rx, fit(L('  사천왕 — 8관을 다 이기면', '  Elite Four — after all 8'), rw), curses.A_DIM)
                    ay += 1
                # 이긴 관의 배지는 목록 아래에(2026-11-10 사용자) — 4개씩 두 줄로 쌓아 크게, 폭·높이에 맞을 때까지 줄이고 2줄도 안 되면 생략
                won_keys = [f'gym:{g}-{i}' for i in range(8) if f'gym:{g}-{i}' in st.get('gym', {})]
                per = 4 if len(won_keys) > 4 else 0
                for rows in range(min(9 if per else 4, h - 3 - ay), 1, -1):
                    art = badge_art(st, won_keys, ay + 1, rx + 2, rows, per)
                    if not art or art[5] <= rw - 2:
                        break
                    art = None
            else:  # 레이드 · 배틀 타워는 오른쪽에 설명만 — Enter 로 바로 도전 준비
                tw = tower_state(st)
                para(scr, 2, L(f'이번 주 레이드 — {name(raid_boss(st)[1])} ({g}세대 전설). 모든 세대가 출전한다. Enter 로 도전 준비.',
                               f'Raid this week — {name(raid_boss(st)[1])} (Gen {g} legendary). Any generation may enter. Enter to prepare.') if kind == 'R' else
                     L(f'배틀 타워 — 지금 {tw["streak"]}연승 · 최고 {tw["best"]}연승. 팀 앞 {TOWER_SIZE}마리가 나간다. Enter 로 도전 준비.',
                       f'Battle Tower — streak {tw["streak"]} · best {tw["best"]}. The first {TOWER_SIZE} of the team fight. Enter to prepare.'),
                     rw + rx, x=rx)
            x = button(h - 1, 1, L('도전 준비', 'prepare'), 'gym_sel')
            x = button(h - 1, x, L('장식 P', 'show P'), 'pin_gym')
            button(h - 1, x, L('돌아가기 q', 'back q'), 'back')
        elif view == 'gym':
            g, i = gsel
            opp = gym_opp(BATTLE, g, i, st)
            team = team_of(st)[:TOWER_SIZE] if i == 'T' else team_of(st, None if i == 'R' else g)
            tn = lambda tp: BATTLE['tnames'].get(tp, ['', ''])  # noqa: E731
            won = st.get('league', {}).get(str(g)) if i == 'L' else (L('이번 주', 'this week') if raid_state(st)['won'] else None) \
                if i == 'R' else st.get('gym', {}).get(f'gym:{g}-{i}')
            tw = tower_state(st)
            y = para(scr, 1, (L(f'배틀 타워 — {tw["streak"] + 1}번째 상대 · 최고 {tw["best"]}연승', f'Battle Tower — opponent #{tw["streak"] + 1} · best {tw["best"]}')
                              if i == 'T' else L(f'{g}세대 사천왕·챔피언 — 5연전', f'Gen {g} Elite Four — 5 battles') if i == 'L' else
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
            put(scr, y, 1, L(f'팀 앞 {TOWER_SIZE}마리 · 모든 세대 출전', f'First {TOWER_SIZE} of the team · any generation') if i == 'T' else
                L('모든 세대 포켓몬 출전', 'Any generation may enter') if i == 'R' else L(f'{g}세대 포켓몬만 출전', f'Gen {g} Pokémon only'), curses.A_DIM)
            okey = repr(opp) if i == 'T' else ''  # 타워는 판마다 상대가 바뀐다
            wkey = (tuple(fighters(st, team)), g, i, okey)
            if wkey not in wr_cache:
                if i == 'L' and team:
                    put(scr, y + 1, 1, L('승률 계산 중…', 'Working out the odds…'), curses.A_DIM)
                    scr.refresh()
                wr_cache[wkey] = gym_rate(BATTLE, fighters(st, team), g, i, st)
            put(scr, y + 1, 1, L(f'승률 {wr_cache[wkey]:.0%}', f'Win rate {wr_cache[wkey]:.0%}'), curses.A_BOLD)
            y += 2
            if rec and rec[0] == (g, i) and rec[2] == okey and all(k < len(st['box']) for k in rec[1]):
                # 추천은 그 상대에게만 — 타워에서 지난 판 추천이 새 상대 앞에 옛 승률로 남아 있었다(2026-11-07 사용자).
                # 승률도 저장해 둔 값이 아니라 적용될 순서 그대로 지금 계산(캐시) — 타워는 앞 순서가 배틀에 영향을 준다.
                rteam = [(k, st['box'][k]['id'], box_level(st['box'][k])) for k in rec[1]]
                rkey = (tuple(fighters(st, rteam)), g, i, okey)
                if rkey not in wr_cache:
                    wr_cache[rkey] = gym_rate(BATTLE, fighters(st, rteam), g, i, st)
                y = para(scr, y, L('추천  ', 'Pick  ') + ', '.join(name(n) for _, n, _ in rteam) +
                         L(f'  (승률\xa0{wr_cache[rkey]:.0%})', f'  ({wr_cache[rkey]:.0%})'), w)  # 눌리지 않는 '[적용]' 글자는 뺐다 — 아래 버튼으로(2026-11-07 사용자)
            cost = LEAGUE_COST if i == 'L' else RAID_COST if i == 'R' else (0 if tw['run'] else TOWER_COST) if i == 'T' else GYM_COST
            if i == 'T':
                y = para(scr, y, L(f'지기 전까지 이어서 — 7연승마다 슈퍼볼 3·은색 병뚜껑 2 · 21연승마다 하이퍼볼 2 · 49연승마다 마스터볼·금색 병뚜껑 2. 시작할 때만 탐색 {TOWER_COST}회',
                                   f'Keep going until you lose — every 7: 3 Great + 2 Bottle Caps · every 21: 2 Ultra · every 49: Master + 2 Gold Bottle Caps. {TOWER_COST} explores to start'), w, curses.A_DIM)
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
            # 원작 배틀 화면처럼(2026-11-06 사용자) — 위: 상대 상태 상자(왼쪽)·상대 그림(오른쪽), 아래: 내 그림(왼쪽, 상대를 보게 좌우
            # 뒤집어)·내 상태 상자(오른쪽), 맨 아래: 대사 상자(마지막 기록 두 줄, 끝나면 결과). 그림은 Kitty·Sixel 일 때만.
            ev, k = battle_now['ev'], battle_now['k']
            now = fight_state(ev, k)
            mb = h - 5  # 대사 상자 첫 줄 — 테두리 2 + 글 2줄, 맨 아래 줄은 버튼
            half = (mb - 1) // 2  # 1 ~ half: 상대 쪽 · half+1 ~ mb-1: 내 쪽
            bw = max(18, min(28, w // 2 - 1))
            spots = {'foe': (1, 1), 'me': (mb - 5, w - 1 - bw)}
            pics = []
            for side in ('foe', 'me'):
                if side not in now:
                    continue
                n, hp, top_, lv_ = now[side]
                top_ = top_ or _battle.Mon(BATTLE, n, lv_).st[0]
                hp_box(scr, *spots[side], bw, n, lv_, top_ if hp is None else hp, top_, side == 'me')
                # 그림 자리 — 상대는 상자 오른쪽 빈 곳 가운데, 나는 상자 왼쪽 빈 곳 가운데
                x0, x1 = (bw + 2, w - 1) if side == 'foe' else (1, w - 2 - bw)
                y0, rows_ = (1, half - 1) if side == 'foe' else (half + 1, mb - half - 2)
                pic = art_of({'id': n, 'shiny': side == 'me' and n in battle_now.get('shiny', ())})
                a = mon_art(pic, y0, w, x0, max(1, rows_), x1 - x0, flip=side == 'me') if rows_ >= 2 else None
                if a:
                    wide = a[5] * (SIXEL_SCALE if a[0] == 'six' else 1)  # Sixel 은 알려 준 칸보다 크게 그려진다
                    pics.append((a[0], a[1], max(x0, round((x0 + x1 - wide) / 2)), *a[3:]))
            if pics:
                one = pics[0]
                rest = tuple((p[1], p[2], p[4]) if p[0] == 'six' else p[1:] for p in pics[1:])
                art = (*one[:3], tuple(p[3] for p in pics) if one[0] == 'six' else one[3], *one[4:], rest)
            talk = [(part, j == k - 1) for j, e in enumerate(ev[:k]) for part in fold(fight_line(e), max(10, w - 4))][-2:]
            if k >= len(ev):
                ups = battle_now.get('ups', [])  # 받은 경험치와 레벨업을 결과 줄에 — 쌓이는 게 보이게
                gain = L(f' 경험치 +{battle_now.get("xp", 0)}', f' XP +{battle_now.get("xp", 0)}') + (
                    ' · Lv↑ ' + ', '.join(f'{name(n)} {a}→{b}' for n, a, b in ups[:2])
                    + (L(f' 외 {len(ups) - 2}', f' +{len(ups) - 2}') if len(ups) > 2 else '') if ups else '')
                tower = battle_now.get('tower')
                prize = [L(*ball_name(key, k)) if key in ('super', 'hyper', 'master') else L(f'{item_name(key)} {k}개', f'{k} {item_name(key)}')
                         for every, pz in TOWER_PRIZES for key, k in pz if tower and tower[0] and tower[0] % every == 0]
                res = (L(f'승리! {tower[0]}연승!', f'Won! {tower[0]} in a row!') + (L(' 보상: ', ' Prize: ') + ', '.join(prize) + ' ·' if prize else '') + gain
                       if battle_now['won'] else L(f'패배… 연승 끝 (최고 {tower[1]}연승)', f'Defeat… streak over (best {tower[1]})') + gain) if tower else \
                    (L('승리! ', 'You won! ') + (L(f'[{badge_name(battle_now["key"])}]을 받았다!' if battle_now['key'].startswith('champ') else f'[{badge_name(battle_now["key"])}]를 받았다!',
                                                  f'Got the [{badge_name(battle_now["key"])}]!') if battle_now['first'] else '') + gain) \
                    if battle_now['won'] else L('패배…', 'Defeat…') + gain
                talk = [(line, True) for line in fold(res, max(10, w - 4))[:2]]  # 길면 두 줄로(Lv↑ 이름이 잘렸다)
            frame(scr, mb, 0, 4, w)
            for j, (line, strong) in enumerate(talk):  # 마지막 기록(접힌 줄 모두)은 굵게
                put(scr, mb + 1 + j, 2, line, curses.A_BOLD if strong else 0)
            x = button(h - 1, 1, (L('다음 상대 q', 'next q') if battle_now['won'] and battle_now.get('tower') else
                                  L('허브로 q', 'to hub q') if battle_now['won'] else L('다시 준비 q', 'retry q'))
                       if k >= len(ev) else L('돌아가기 q', 'back q'), 'back')
            if k < len(ev):
                put(scr, h - 1, x, L('Enter 끝까지', 'Enter skip'), curses.A_DIM)
        elif view == 'info':
            art = draw_info(scr, st, info, h, w, gold)
            if info in DEX or info in SPECIALS:
                put(scr, h - 2, 1, research_text(st, info), curses.A_BOLD if research_done(st, info) else curses.A_DIM)
            x = button(h - 1, 1, L('돌아가기 q', 'back q'), 'back')
            put(scr, h - 1, x, L('←→ 앞뒤 포켓몬', '←→ prev/next'), curses.A_DIM)
        elif view == 'change':  # 가방 F — 바꿀 모습 고르기(합체·메가진화·거다이맥스·원시회귀·울트라버스트)
            opts = change_options(st, chg) if chg is not None and chg < len(st['box']) else []
            base_m = st['box'][chg]
            y = para(scr, 1, msg or L(f'{name(base_m["id"])} Lv{box_level(base_m)} · {iv_text(base_m)} — 특훈할 능력치를 고른다', f'{name(base_m["id"])} Lv{box_level(base_m)} · {iv_text(base_m)} — pick the stat to train')
                     if chg_from == 'use' and ukey in ('cap', 'gcap') else
                     msg or L(f'기본 {name(base_m["id"])} Lv{box_level(base_m)} · {iv_text(base_m)} — 레벨·개체값은 기본을 따르고 재료는 사라진다(되돌릴 수 없다)',
                                      f'Base {name(base_m["id"])} Lv{box_level(base_m)} · {iv_text(base_m)} — keeps the base\'s level and IVs, uses up the material (can\'t be undone)'), w, curses.A_DIM)
            shown_k = chg_only if chg_from == 'use' else list(range(len(opts)))  # 가방에서 왔으면 그 아이템 칸만(메가 줄에 커서가 놓였다)
            sel = max(0, min(sel, len(shown_k) - 1))
            for row, k in enumerate(shown_k):
                f, (what, ref), ok, why = opts[k]
                cost = (L('재료 ', 'material ') + f'{name(st["box"][ref]["id"])} Lv{box_level(st["box"][ref])} · {iv_text(st["box"][ref])}' if what == 'mon'
                        else L(f'{item_name(ref)} {st.get("items", {}).get(ref, 0)}개', f'{item_name(ref)} ×{st.get("items", {}).get(ref, 0)}'))
                text = f'{opt_name(f)} ← {cost}' + ('' if ok else f'  · {why}')
                if row == sel and ok and isinstance(f, tuple) and f[0] == 'iv':  # 은색 병뚜껑 — 몇 개 쓸지(←→)
                    cmax, cur = cap_max(st, chg, f), iv_of(base_m)[f[1]]
                    cap_n = max(1, min(cap_n, cmax))
                    text = L(f'{opt_name(f).split(" ")[0]} {cur} → {cur + cap_n}  ◀ {cap_n}개 ▶ ({1}~{cmax}개 · 가진 {st.get("items", {}).get("cap", 0)}개)',
                             f'{opt_name(f).split(" ")[0]} {cur} → {cur + cap_n}  ◀ {cap_n} ▶ (1–{cmax} · have {st.get("items", {}).get("cap", 0)})')
                btns.append((y + 1 + row, 1, w - 1, ('chg', k)))
                put(scr, y + 1 + row, 1, text.ljust(w - 2) if row == sel else text,
                    (curses.A_REVERSE if row == sel else 0) | (0 if ok else curses.A_DIM))
            x = button(h - 1, 1, L('바꾸기', 'change'), 'chg_sel')
            x = button(h - 1, x, L('돌아가기 q', 'back q'), 'back')
            if chg_from == 'use' and ukey == 'cap':
                put(scr, h - 1, x, L('↑↓ 능력치 · ←→ 개수', '↑↓ stat · ←→ how many'), curses.A_DIM)
        elif view == 'trade':  # 2026-11-05 사용자: 체육관처럼 두 열 — 왼쪽 박사에게 · 중복 정리 · 볼 바꾸기, 오른쪽에 그 내용
            order = bag_order(st, None, bag_sort)  # 박사에게 쪽의 보이는 순서(가방 번호들) — 고른 줄로 가방 번호를 찾는다
            tidy_all = tidy_targets(st)
            tidy = [i for i in tidy_all if tidy_key(st, i) not in tidy_skip]  # x 로 뺀 것은 남긴다
            lw = max(12, min(16, w // 4))  # 왼쪽 메뉴는 짧다 — 오른쪽 이름 자리를 넓게
            rx = lw + 2
            rw = w - rx - 1
            body = h - 4
            put(scr, 1, 1, msg or (
                L(f'↑↓ 고르기 · Tab 정렬 {SORTS[bag_sort][0]} · Enter 두 번 보내기 · ← q 돌아가기', f'↑↓ pick · Tab sort {SORTS[bag_sort][1]} · Enter twice to send · ← q back') if tcol and tm == 0 else
                L('↑↓ 고르기 · Enter 바꾸기 · ← q 돌아가기', '↑↓ pick · Enter swap · ← q back') if tcol and tm == 2 else
                L('↑↓ 고르기 · x 빼기/넣기 · Enter 두 번 보내기 · ← q 돌아가기', '↑↓ pick · x keep/send · Enter twice to send · ← q back') if tcol and tm == 1 else
                L('↑↓ 고르기 · → 안으로 · Enter · q 돌아가기', '↑↓ pick · → into it · Enter · q back')), curses.A_DIM)
            menu = [L('박사에게', 'Professor'), L(f'중복 정리 {len(tidy)}', f'Tidy {len(tidy)}'), L('볼 바꾸기', 'Swap balls')]
            for k, label in enumerate(menu):
                cur = k == tm
                text = ('▶ ' if cur else '  ') + fit(label, lw - 3)
                put(scr, 2 + k, 1, text.ljust(lw) if cur and not tcol else text, (curses.A_REVERSE if not tcol else curses.A_BOLD) if cur else 0)
                btns.append((2 + k, 1, lw, ('tradeleft', k)))
            if tm == 0:  # 가방 전체 — 한 마리씩 박사에게(동료·팀·이로치·우두머리·만든 모습은 못 보낸다)
                rows = [(i, ('♥' if i == st['partner'] else '⚔' if i in st.get('team', []) else ' ') + ('✨' if m.get('shiny') else '') + ('◆' if m.get('alpha') else '')
                         + bag_text(m, rw - 3)) for i, m in ((i, st['box'][i]) for i in order)]
                sel = max(0, min(sel, len(rows) - 1))
                top = max(0, min(min(max(top, sel - body + 1), sel), len(rows) - body))
                for k, (i, text) in enumerate(rows[top:top + body]):
                    cur = tcol and top + k == sel
                    attr = (curses.A_BOLD if i == st['partner'] else 0) | (gold if st['box'][i].get('shiny') else 0) | (curses.A_REVERSE if cur else 0)
                    put(scr, 2 + k, rx, fit(text, rw).ljust(rw) if cur else fit(text, rw), attr)
                    btns.append((2 + k, rx, w - 1, ('trrow', top + k)))
                if not rows:
                    put(scr, 2, rx, L('아직 잡은 포켓몬이 없다.', 'No Pokémon caught yet.'), curses.A_DIM)
                elif tcol:
                    put(scr, h - 2, rx, fit(iv_text(st['box'][rows[sel][0]]), rw), curses.A_DIM)
            elif tm == 1:  # 보낼 것 미리보기 — 같은 종이 둘 이상이면 개체값·배틀 경험치·진화 경험치가 가장 좋은 것만 남긴다
                kept = len(tidy_all) - len(tidy)
                y = para(scr, 2, L(f'같은 종 중 가장 좋은 것만 남기고 {len(tidy)}마리를 보낸다' + (f'(뺀 것 {kept})' if kept else '') + ' — → 로 목록 · x 빼기 · Enter 두 번',
                                   f'Keeps the best of each species and sends {len(tidy)}' + (f' ({kept} kept)' if kept else '') + ' — → list · x keep · Enter twice') if tidy_all else
                         L('정리할 것이 없다 — 같은 종이 둘 이상일 때 가장 좋은 것만 남긴다.', 'Nothing to tidy — only duplicates are sent.'), rw + rx, curses.A_DIM, rx)
                room = max(1, h - 2 - y)
                sel = max(0, min(sel, len(tidy_all) - 1))
                top = max(0, min(min(max(top, sel - room + 1), sel), max(0, len(tidy_all) - room)))
                for k, i in enumerate(tidy_all[top:top + room]):
                    skip = tidy_key(st, i) in tidy_skip
                    cur = tcol and top + k == sel
                    text = fit(('✕ ' if skip else '  ') + bag_text(st['box'][i], rw - 9) + (L('  남김', '  keep') if skip else ''), rw)
                    put(scr, y + k, rx, text.ljust(rw) if cur else text, (curses.A_REVERSE if cur else 0) | (curses.A_DIM if skip else 0))
                    btns.append((y + k, rx, w - 1, ('trrow', top + k)))
            else:  # 볼 바꾸기 — 한 단계 위 볼로
                sel = max(0, min(sel, len(TRADES) - 1))
                for k, (src, dst, cost) in enumerate(TRADES):
                    cur = tcol and k == sel
                    text = fit(L(f'{ball_name(src, cost)[0]} → {ball_name(dst, 1)[0]} · 가진 {st[src]}개',
                                 f'{ball_name(src, cost)[1]} → {ball_name(dst, 1)[1]} · have {st[src]}'), rw)
                    btns.append((2 + k, rx, w - 1, ('swap', k)))
                    put(scr, 2 + k, rx, text.ljust(rw) if cur else text, curses.A_REVERSE if cur else 0)
                para(scr, 3 + len(TRADES), L(f'지금: 몬스터볼 {st["balls"]} · 슈퍼볼 {st["super"]} · 하이퍼볼 {st["hyper"]} · 마스터볼 {st["master"]}',
                                             f'Now: Poké {st["balls"]} · Great {st["super"]} · Ultra {st["hyper"]} · Master {st["master"]}'), rw + rx, curses.A_DIM, rx)
            button(h - 1, 1, L('돌아가기 q', 'back q'), 'back')
        elif view == 'dex' and dg == GENS + 2:  # 도감 마지막 쪽 — 특수 모습(메가진화·거다이맥스·원시회귀·울트라버스트)
            have_sp, og, items = st.get('specials', []), opened_gen(st), st.get('items', {})  # made 라 부르면 made() 를 가려 [박사에게]가 꺼졌다
            rows = []
            for p, (s_, kind, g, *_) in SPECIALS.items():
                key = 'soup' if kind == 'gmax' else f'stone:{p}'
                rows.append((p, ('● ' if p in have_sp else '  ') + f'{s_:04d} ' + name(p) + (' ★' if p in st.get('researched', []) else '')
                             + ('' if p in have_sp else '   · ' + (
                    L(f'{g}세대가 열리면', f'opens with Gen {g}') if og < g else L(f'{item_name(key)} {items.get(key, 0)}개', f'{item_name(key)} ×{items.get(key, 0)}')))))
            put(scr, 1, 1, L(f'◀ 특수 모습 {len(have_sp)}/{len(SPECIALS)}   ● 만듦', f'◀ Special forms {len(have_sp)}/{len(SPECIALS)}   ● made'), curses.A_DIM)
            body = h - 3
            sel = max(0, min(sel, len(rows) - 1))
            top = max(0, min(min(max(top, sel - body + 1), sel), len(rows) - body))
            for k, (p, text) in enumerate(rows[top:top + body]):
                if p in have_sp:
                    btns.append((2 + k, 1, w - 1, ('info', p)))
                put(scr, 2 + k, 1, text.ljust(w - 2) if top + k == sel else text, curses.A_REVERSE if top + k == sel else 0)
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
            rows = [(n, ('● ' if n in st['caught'] else '○ ' if n in st['seen'] else '  ')
                     + f'{n:04d} ' + (name(n) if n in st['seen'] else '???') + (' ★' if n in st.get('researched', []) else '')
                     + ('' if n in st['caught'] else '   · ' + dex_hint(st, n))) for n in DEX if gen(n) == dg] if dg <= open_gen else []
            have = sum(1 for n in st['caught'] if gen(n) == dg)
            done_r = sum(1 for n in st.get('researched', []) if n in DEX and gen(n) == dg)
            put(scr, 1, 1, L(f'◀ {dg}세대 도감 {have}/{GEN_SIZE[dg]} ▶ ★연구 {done_r}  ● 잡음 ○ 봄',
                              f'◀ Gen {dg} Pokédex {have}/{GEN_SIZE[dg]} ▶ ★research {done_r}  ● caught ○ seen'), curses.A_DIM)
            body = h - 4
            if rows:
                sel = max(0, min(sel, len(rows) - 1))
                top = min(max(top, sel - body + 1), sel)  # 커서가 화면 안에 있게
            top = max(0, min(top, len(rows) - body))
            for k, (key, text) in enumerate(rows[top:top + body]):
                if key in st['seen']:
                    btns.append((2 + k, 1, w - 1, ('info', key)))
                attr = (gold if key in st['shiny'] else 0) | (curses.A_REVERSE if top + k == sel else 0)  # 이로치를 잡은 종은 도감에서도 금색
                put(scr, 2 + k, 1, text.ljust(w - 2) if top + k == sel else text, attr)
            if not rows:
                put(scr, 2, 1, L(f'잠김 — {dg - 1}세대 도감을 채우면 열립니다.', f'Locked — complete the Gen {dg - 1} Pokédex to open it.'))
            if rows:
                put(scr, h - 2, 1, dex_summary(st, dg)[:w - 2], curses.A_DIM)
            x = button(h - 1, 1, L('돌아가기 q', 'back q'), 'back')
            put(scr, h - 1, x, L('↑↓ 이동 · Enter 자세히 · ←→ 세대', '↑↓ move · Enter details · ←→ generation'), curses.A_DIM)
        acts = [b[3] for b in navbtns]
        if focus not in acts:  # 처음이거나 그 버튼이 사라졌으면 — 메인은 풀숲 탐색, 그 밖엔 돌아가기·닫기가 아닌 첫 버튼
            focus = next(a for a in ('encounter', 'explore') if a in acts) if view == 'main' and {'encounter', 'explore'} & set(acts) else next((a for a in acts if a not in ('back', 'close')), acts[0] if acts else None)
        for by, bx, _, a, text in navbtns:
            if a == focus and view not in ('gyms', 'trade', 'badges'):  # 체육관·교환·훈장은 키가 두 열 목록을 움직이니 아래 버튼은 고른 것처럼 보이지 않게(마우스로만)
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
        if key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT, curses.KEY_PPAGE, curses.KEY_NPAGE):
            curses.flushinp()  # 화면을 그리는 게 느릴 때 쌓인 방향키를 버린다 — 손을 떼도 계속 움직였다(2026-11-05)
        if key != -1:
            _gfx.sixel_touch()  # 키로 화면이 바뀌면 그림을 다시 놓는다
            fresh_st = load()  # 키를 기다린 2초 사이 허브가 저장했을 수 있다(부화·보상) — 그 위에 적용해야 덮어쓰지 않는다
            if not fresh_st.get('_broken'):
                st = fresh_st
        act = {ord('q'): 'back' if view != 'main' else 'close', 27: 'back' if view != 'main' else 'close'}.get(key)
        lists = view in ('trade', 'change', 'dex', 'badges', 'gyms', 'slotpick', 'bag', 'use')  # ↑↓ 는 목록 줄을, ←→ 는 아래 버튼을 고른다
        if view == 'mon' and naming is not None:  # 이름 짓는 중 — 글자는 이름으로(q 도), Enter 저장 · Esc 취소
            if key == 27:
                naming, act, key = None, None, -1
            elif key in (ord('\n'), ord('\r'), curses.KEY_ENTER):
                nick = naming.strip()
                if nick:
                    st['box'][mon_i]['nick'] = nick
                else:
                    st['box'][mon_i].pop('nick', None)
                save(st)
                msg = L(f'이름을 {mon_name(st["box"][mon_i])}(으)로 정했다.', f'Named {mon_name(st["box"][mon_i])}.')
                naming, act, key = None, None, -1
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                naming, act, key = naming[:-1], None, -1
            elif typed_char(key) or key == 32:
                naming, act, key = (naming + chr(key))[:NICK_MAX], None, -1
            else:
                act = None
        elif view == 'mon' and key in (ord('n'), ord('N')):
            naming, act, key = st['box'][mon_i].get('nick', ''), None, -1
        elif view == 'slotpick' and not searching and key in (ord('i'), ord('I')):
            act, key = 'mon_open', -1
        elif view == 'main' and key in (ord('h'), ord('H')):  # 서식지 바꾸기(2026-11-10 사용자)
            ks = [hb[0] for hb in HABITATS]
            st['habitat'] = ks[(ks.index(habitat(st)[0]) + 1) % len(ks)]
            hb = habitat(st)
            tn = [(BATTLE or {}).get('tnames', {}).get(tp, ['', '']) for tp in hb[3]]
            msg = (L(f'서식지: {hb[1]} — {"·".join(x[0] for x in tn)} 타입만 나온다 (h 로 바꾸기)', f'Habitat: {hb[2]} — only {"/".join(x[1] for x in tn)} types (h to change)')
                   if hb[3] else L('서식지: 전체 — 어떤 포켓몬이든 나온다 (h 로 바꾸기)', 'Habitat: all — anything can appear (h to change)'))
            save(st)
            act, key = None, -1
        elif view in ('slotpick', 'use') and searching:  # 찾는 중 — 글자는 검색어로, 방향키는 그대로 줄 이동
            if key == 27:  # Esc — 검색어를 지우고 찾기 끝
                query, searching, sel, top, act, key = '', False, 0, 0, None, -1
            elif key in (ord('\n'), ord('\r'), curses.KEY_ENTER):  # Enter — 검색어는 두고 찾기 끝(넣기는 다음 Enter)
                searching, act, key = False, None, -1
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                query, sel, top, act = query[:-1], 0, 0, None
            elif typed_char(key):  # 방향키 같은 curses 특수키(KEY_MIN~KEY_MAX)는 글자가 아니다 — 전엔 검색어로 들어갔다
                query, sel, top, act = query + chr(key), 0, 0, None
        elif view in ('slotpick', 'use') and key in (ord('f'), ord('F')):  # F 찾기
            searching, act, key = True, None, -1
        elif view == 'slotpick':  # 평소 — 방향키 줄 이동 · Enter 넣기 · Tab 정렬 · q/Esc 돌아가기
            if key == 9:
                pick_sort, sel, top = (pick_sort + 1) % len(SORTS), 0, 0
        if view == 'change' and chg_from == 'use' and ukey == 'cap':  # 은색 병뚜껑 — ←→ 는 쓸 개수(아래 버튼 대신)
            if key in (curses.KEY_LEFT, curses.KEY_RIGHT):
                cap_n, key = max(1, cap_n + (1 if key == curses.KEY_RIGHT else -1)), -1  # 위쪽 끝은 그릴 때 cap_max 로 자른다
                confirm = None
            elif key in (curses.KEY_UP, curses.KEY_DOWN):
                cap_n, confirm = 1, None
        if view == 'gyms':  # 두 열 — ←→ 로 열을 오가고, 오른쪽에선 ↑↓ 가 관을 고른다. q·Esc 는 오른쪽이면 왼쪽으로
            left = gym_left(st)
            on_gen = bool(left) and left[max(0, min(sel, len(left) - 1))][0] == 'G'
            if key == curses.KEY_RIGHT:
                if on_gen and not gcol:
                    gcol, gsub, gtop = 1, 0, 0
                key = -1
            elif key == curses.KEY_LEFT:
                gcol, key = 0, -1
            elif gcol and key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE):
                gsub += {curses.KEY_UP: -1, curses.KEY_DOWN: 1, curses.KEY_PPAGE: -(h - 5), curses.KEY_NPAGE: h - 5}[key]
                key = -1
            elif key in (ord('q'), 27) and gcol:
                gcol, act, key = 0, None, -1
            elif key in (ord('p'), ord('P')):
                act = 'pin_gym'
            elif key in (ord('\n'), ord('\r'), curses.KEY_ENTER):
                act, key = 'gym_sel', -1
        if view == 'badges':  # 두 열 — ←→ 열 · 왼쪽 ↑↓ 는 분류 · 오른쪽 ↑↓ 는 훈장(lists) · Enter·P 장식 · q·Esc 는 오른쪽이면 왼쪽으로
            groups = medal_groups(st)
            ids = groups[max(0, min(bcat, len(groups) - 1))][1] if groups else []
            if key == curses.KEY_RIGHT:
                if not bcol and ids:
                    bcol, sel, top = 1, 0, 0
                key = -1
            elif key == curses.KEY_LEFT:
                bcol, key = 0, -1
            elif not bcol and key in (curses.KEY_UP, curses.KEY_DOWN):
                bcat, sel, top, msg = max(0, min(len(groups) - 1, bcat + (1 if key == curses.KEY_DOWN else -1))), 0, 0, ''
                key = -1
            elif key in (ord('q'), 27) and bcol:
                bcol, act, key = 0, None, -1
            elif key in (ord('\n'), ord('\r'), curses.KEY_ENTER, ord('p'), ord('P')):
                if not bcol:
                    bcol, sel, top, act = (1, 0, 0, None) if ids else (0, sel, top, None)
                else:
                    act = ('pin', ids[max(0, min(sel, len(ids) - 1))]) if ids else None
                key = -1
        if view == 'trade':  # 두 열 — ←→ 열 · 왼쪽 ↑↓ 는 일 고르기 · 오른쪽 ↑↓ 는 목록(lists) · q·Esc 는 오른쪽이면 왼쪽으로
            if key == curses.KEY_RIGHT:
                if not tcol and (tm != 1 or tidy_targets(st)):  # 중복 정리도 목록 안으로 — x 로 뺄 것을 고른다(2026-11-10 사용자)
                    tcol, sel, top, confirm = 1, 0, 0, None
                key = -1
            elif key in (ord('x'), ord('X')) and tm == 1 and tcol:  # 이 포켓몬은 보내지 않고 남긴다(다시 누르면 다시 보낸다)
                ta = tidy_targets(st)
                if ta:
                    kk = tidy_key(st, ta[max(0, min(sel, len(ta) - 1))])
                    tidy_skip ^= {kk}
                confirm, msg, key = None, '', -1
            elif key == curses.KEY_LEFT:
                tcol, confirm, msg, key = 0, None, '', -1
            elif not tcol and key in (curses.KEY_UP, curses.KEY_DOWN):
                tm, sel, top, confirm, msg = max(0, min(2, tm + (1 if key == curses.KEY_DOWN else -1))), 0, 0, None, ''
                key = -1
            elif key in (ord('q'), 27) and tcol:
                tcol, act, confirm, msg, key = 0, None, None, '', -1
            elif key in (ord('\n'), ord('\r'), curses.KEY_ENTER):
                if tm == 1:
                    act = 'tidy'
                elif not tcol:
                    tcol, sel, top, act = 1, 0, 0, None
                else:
                    act = 'send' if tm == 0 else ('swap', max(0, min(sel, len(TRADES) - 1)))
                key = -1
            elif key == 9 and tm == 0:  # Tab — 박사에게 목록 정렬
                act = 'sort'
        if view == 'dex' and key in (curses.KEY_LEFT, curses.KEY_RIGHT):
            dg, top, sel = max(1, min(GENS + 1 + bool(SPECIALS), dg + (1 if key == curses.KEY_RIGHT else -1))), 0, 0  # 뒤의 두 쪽은 리전폼 · 특수 모습
        elif view == 'info' and key in (curses.KEY_LEFT, curses.KEY_RIGHT):
            seen = [p for p in SPECIALS if p in st.get('specials', [])] if info in SPECIALS else \
                list(FORMS) if info in FORMS else \
                [n for n in DEX if gen(n) == gen(info)]  # 같은 세대(리전폼은 리전폼) 전부 앞뒤로 — 못 본 것은 실루엣(2026-11-11)
            info = seen[(seen.index(info) + (1 if key == curses.KEY_RIGHT else -1)) % len(seen)]
        elif lists and key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE):
            sel += {curses.KEY_UP: -1, curses.KEY_DOWN: 1, curses.KEY_PPAGE: -(h - 4), curses.KEY_NPAGE: h - 4}[key]
        elif view == 'wild' and key in (curses.KEY_UP, curses.KEY_DOWN):  # ↑↓ 는 던질 볼을 바로 바꾼다, ←→ 는 던지기·도망(2026-11-10 사용자)
            ball_pick, msg = wild_ball_step(st, default_ball(st, ball_pick), key), ''
        elif view == 'wild' and key in (curses.KEY_LEFT, curses.KEY_RIGHT):
            focus = 'throw_sel' if key == curses.KEY_LEFT else 'run'
        elif key in (curses.KEY_LEFT, curses.KEY_RIGHT, curses.KEY_UP, curses.KEY_DOWN):
            focus = (move_geo if view in ('main', 'wild') else move_focus)(navbtns, focus, key)
        if key in (ord('\n'), ord('\r'), curses.KEY_ENTER):
            if view == 'dex' and dg == GENS + 2:
                p = list(SPECIALS)[min(sel, len(SPECIALS) - 1)] if SPECIALS else None  # 자료를 못 받았으면 빈 쪽
                act = ('info', p) if p in st.get('specials', []) else None
            elif view == 'dex' and dg > GENS:
                p = list(FORMS)[min(sel, len(FORMS) - 1)] if FORMS else None
                act = ('info', p) if p else None  # 못 본 리전폼도 실루엣으로
            elif view == 'dex':
                act = ('info', [m for m in DEX if gen(m) == dg][min(sel, GEN_SIZE[dg] - 1)])  # 못 본 포켓몬도 실루엣으로
            elif view == 'slotpick':
                act = ('pickrow', sel)
            elif view == 'bag':
                act = ('bagitem', sel)
            elif view == 'use':
                act = ('userow', sel)
            elif view == 'fight':
                act = 'back'  # 기록을 끝까지 → 한 번 더 누르면 나간다
            elif view != 'info':
                act = focus
        picked = order[max(0, min(sel, len(order) - 1))] if order and view == 'trade' else None
        # 고른 줄에 하는 버튼 → 그 줄의 일로
        if act in ('gym_sel', 'pin_gym'):  # 왼쪽이 세대면 오른쪽 열로 들어가고, 오른쪽이면 그 관 · 레이드·타워는 바로
            left = gym_left(st)
            kind, g = left[max(0, min(sel, len(left) - 1))] if left else ('G', 1)
            if kind == 'G' and not gcol:
                act = ('pin', f'champ{g}') if act == 'pin_gym' else None
                if act is None:
                    gcol, gsub, gtop = 1, 0, 0
            elif kind == 'G':
                right = gym_right(st, g)
                gi = right[max(0, min(gsub, len(right) - 1))]
                act = ('gym', gi) if act == 'gym_sel' else ('pin', f'champ{gi[0]}' if gi[1] == 'L' else f'gym:{gi[0]}-{gi[1]}')
            else:
                act = ('gym', (g, kind)) if act == 'gym_sel' else None
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
        if act == 'sort' and view == 'trade':
            bag_sort, top, sel, msg = (bag_sort + 1) % len(SORTS), 0, 0, ''
            _lang.put('bag_sort', bag_sort)  # PC 설정에 — 다시 열어도 그 정렬
        if act == 'close':
            break
        if act == 'chg_sel' and view == 'change':
            act = ('chg', chg_only[sel] if chg_from == 'use' and 0 <= sel < len(chg_only) else sel)
        if isinstance(act, tuple) and act[0] == 'chg' and view == 'change':
            opts = change_options(st, chg) if chg is not None and chg < len(st['box']) else []
            k = act[1]
            if not 0 <= k < len(opts):
                msg = ''
            elif not opts[k][2]:
                msg = L(f'아직 못 바꾼다 — {opts[k][3]}', f'Not yet — {opts[k][3]}')
            elif confirm != ('chg', chg, k):  # 되돌릴 수 없으니 한 번 더 눌러야 바뀐다
                confirm = ('chg', chg, k)
                cn = max(1, min(cap_n, cap_max(st, chg, opts[k][0]))) if isinstance(opts[k][0], tuple) and opts[k][0][0] == 'iv' else 1
                msg = L(f'{opt_name(opts[k][0]).split(" ")[0]} — {item_name(opts[k][1][1])} {cn}개를 쓴다. 한 번 더 누르면 특훈한다',
                        f'{opt_name(opts[k][0]).split(" ")[0]} — uses {cn} {item_name(opts[k][1][1])}. Press again') \
                    if isinstance(opts[k][0], tuple) else L(f'{opt_name(opts[k][0])}(으)로 바꾼다 — 재료는 사라지고 되돌릴 수 없다. 한 번 더 누르면 바뀐다',
                        f'Change into {opt_name(opts[k][0])} — the material is used up and it can\'t be undone. Press again')
            else:
                mon, before = st['box'][chg], name(st['box'][chg]['id'])
                f = change(st, chg, k, cap_n)
                save(st)
                msg = L(f'특훈 완료! {before} — {iv_text(mon)}', f'Hyper Training done! {before} — {iv_text(mon)}') if isinstance(f, tuple) else \
                    L(f'오잉!? {before}의 모습이… {name(f)}(으)로 바뀌었다!', f'What? {before} became {name(f)}!')
                view, confirm, rec, top, cap_n = 'bag', None, None, 0, 1
                sel = max(0, min(bag_sel, len(bag_items(st)) - 1))  # 가방에서 고르던 아이템으로(다 썼으면 가까운 줄)
            act = None
        if act in ('send', 'tidy') and view == 'trade' and picked is not None:
            i = picked
            idxs = [i] if act == 'send' else [j for j in tidy_targets(st) if tidy_key(st, j) not in tidy_skip]
            what = (act, tuple(idxs))
            m = st['box'][i]
            if act == 'send' and (i == st['partner'] or i in st.get('team', []) or m.get('shiny') or m.get('alpha') or made(m)):
                msg, confirm = L('동료·팀·이로치·우두머리와 재료로 만든 모습(합체·메가 등)은 박사에게 보내지 않는다.',
                                 "Partner, team, shiny, alpha and changed (fused, Mega …) Pokémon can't be sent."), None
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
                rec, confirm, tidy_skip = None, None, set()  # 가방 번호가 당겨졌으니 뺀 표시도 비운다
                msg = L(f'박사에게 {k}마리를 보냈다! 몬스터볼 +{balls}', f'Sent {k} to the Professor! Poké Balls +{balls}')
        elif act is not None and not (isinstance(act, tuple) and act[0] == 'userow'):  # 가방 사용도 두 번 눌러야 — 그 확인은 지우지 않는다
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
        if act == 'badges' and view == 'main':  # 장식한 게 있으면 '장식 중'부터, 없으면 첫 분류(포획)부터
            view, top, sel, msg, bcol = 'badges', 0, 0, '', 0
            bcat = 0 if any(owned(st, b) for b in st.get('showcase', [])) else 1
        if act == 'gyms' and view == 'main':
            if BATTLE is None:  # 처음 — 종족값·타입·상성을 받아 온다
                put(scr, 1, 1, L('PokeAPI 에서 배틀 데이터를 받는 중…', 'Downloading battle data from PokeAPI…'), curses.A_DIM)
                scr.refresh()
                try:
                    BATTLE = _battle.ensure()
                    TYPES.update(BATTLE['types'] if BATTLE else {})
                except Exception as e:  # 네트워크 오류 등
                    msg, act = L('배틀 데이터를 받지 못했다: ', 'Could not download battle data: ') + f'{type(e).__name__}: {e}', None
            if BATTLE is not None:  # 아직 못 이긴 관이 남은 가장 앞 세대에서 시작
                view, top, sel, msg, gcol, gsub, gtop = 'gyms', 0, gym_start(st), '', 0, 0, 0
        if act == 'use_sel' and view == 'use':
            act = ('userow', sel)
        if isinstance(act, tuple) and act[0] == 'bagitem' and view == 'bag':
            rows = bag_items(st)
            if 0 <= act[1] < len(rows):
                bag_sel = act[1]  # 돌아오면 이 아이템에(2026-11-10 사용자 — 전엔 맨 위로 갔다)
                view, ukey, sel, top, msg, confirm, query, searching = 'use', rows[act[1]][0], 0, 0, '', None, '', False
                focus = 'use_sel'  # 가방의 [돌아가기] 강조가 넘어와 Enter 가 나갈 것처럼 보였다(2026-11-06 사용자) — Enter 는 늘 쓰기
            act = None
        if isinstance(act, tuple) and act[0] == 'userow' and view == 'use':
            rows = item_targets(st, ukey, query)
            if 0 <= act[1] < len(rows):
                i, ks, ok, why = rows[act[1]]
                before = name(st['box'][i]['id'])
                if not ok:
                    msg = L(f'아직 못 쓴다 — {why}', f'Not yet — {why}')
                elif ukey == 'cap' or ukey != 'candy' and len(ks) > 1:  # 고를 게 더 있다(병뚜껑 능력치·개수, 합체 상대 둘) — 바꾸기 화면에서
                    use_sel = act[1]
                    view, chg, chg_from, chg_only, sel, top, msg, confirm, cap_n = 'change', i, 'use', ks, 0, 0, '', None, 1
                elif confirm != ('use', ukey, i):  # 되돌릴 수 없으니 한 번 더
                    confirm = ('use', ukey, i)
                    msg = L(f'{before}에게 {item_name(ukey)} — 한 번 더 누르면 쓴다(되돌릴 수 없다)', f'{item_name(ukey)} on {before} — press again (can\'t be undone)')
                else:
                    confirm = None
                    if ukey == 'candy':
                        n = use_candy(st, t, i=i)
                        msg = L(f'오잉!? {before}의 모습이… {name(n)}(으)로 진화했다!', f'What? {before} evolved into {name(n)}!') if n else ''
                    else:
                        f = change(st, i, ks[0])
                        msg = L(f'특훈 완료! {before} — {iv_text(st["box"][i])}', f'Hyper Training done! {before} — {iv_text(st["box"][i])}') if isinstance(f, tuple) else \
                            L(f'오잉!? {before}의 모습이… {name(f)}(으)로 바뀌었다!', f'What? {before} became {name(f)}!')
                    save(st)
                    view, top, rec = 'bag', 0, None
                    sel = max(0, min(bag_sel, len(bag_items(st)) - 1))  # 가방에서 고르던 아이템으로
            act = None
        if act == 'partner_pick' and view == 'main':
            view, pslot, query, pick_sort, sel, top, msg, searching = 'slotpick', -1, '', 1, 0, 0, '', False
            act = None
        if act == 'encounter' and view == 'main' and st['wild']:
            view, ball_pick, focus, msg = 'wild', default_ball(st, ball_pick), 'throw_sel', ''
        if view == 'wild' and isinstance(act, tuple) and act[0] == 'ball':
            can = dict((kind, c) for kind, _, c in ball_choices(st)) if st['wild'] else {}
            if can.get(act[1]):
                ball_pick, msg, focus = act[1], '', 'throw_sel'  # 고르기만 — 던지기는 ③
            else:
                msg = L('그 볼은 지금 던질 수 없다.', "You can't throw that ball now.")
            act = None
        if view == 'wild' and act == 'throw_sel':
            act = {'ball': 'throw'}.get(ball_pick, ball_pick) if ball_pick else None
            if act is None:
                msg = L('던질 볼을 먼저 고르자.', 'Pick a ball first.')
        if view == 'wild' and not st['wild']:
            view = 'main'
        if act == 'mon_open' and view == 'slotpick':
            rows_ = slot_rows(st, pslot, query, pick_sort)
            if rows_ and 0 <= sel < len(rows_) and rows_[sel] is not None:
                view, mon_i, naming, msg = 'mon', rows_[sel], None, ''
            act = None
        if act == 'nick' and view == 'mon':
            naming, act = st['box'][mon_i].get('nick', ''), None
        if act == 'pick_sel' and view == 'slotpick':
            act = ('pickrow', sel)
        if isinstance(act, tuple) and act[0] == 'slot' and view == 'main':
            view, pslot, query, pick_sort, sel, top, msg, searching = 'slotpick', act[1], '', 1, 0, 0, '', False
            act = None
        if isinstance(act, tuple) and act[0] == 'pickrow' and view == 'slotpick':
            rows = slot_rows(st, pslot, query, pick_sort)
            if 0 <= act[1] < len(rows) and pslot == -1:  # 동료 고르기
                set_partner(st, t, rows[act[1]])
                msg = L(f'{name(st["box"][rows[act[1]]]["id"])}(을)를 데리고 다닙니다.', f'{name(st["box"][rows[act[1]]]["id"])} is now your partner.')
                save(st)
                view = 'main'
            elif 0 <= act[1] < len(rows):
                msg, rec = set_slot(st, pslot, rows[act[1]]), None
                save(st)
                view = 'main'
            act = None
        if act == 'rec' and view == 'gym':
            put(scr, 9, 1, L('추천 팀을 계산하는 중…', 'Working out a team…'), curses.A_DIM)
            scr.refresh()
            cands = [(k, m['id'], box_level(m), iv_of(m)) + alpha_x(m) for k, m in enumerate(st['box']) if gsel[1] in ('R', 'T') or gen(m['id']) == gsel[0]]
            opp = gym_opp(BATTLE, *gsel, st)
            if gsel[1] == 'L':  # 연전은 다섯 팀을 이어 붙여 후보를 추리고, 고를 때는 연전 승률로(가볍게 40번씩)
                pick = _battle.recommend(BATTLE, cands, sum(opp, []), rate=lambda tm: _battle.league_rate(BATTLE, tm, opp, runs=40))
            else:
                pick = _battle.recommend(BATTLE, cands, opp, size=TOWER_SIZE if gsel[1] == 'T' else _battle.TEAM_MAX)
            rec = (gsel, pick, repr(opp) if gsel[1] == 'T' else '')  # 승률은 화면이 그 순서로 계산한다
            msg = ''
        if act == 'apply' and view == 'gym' and rec and rec[0] == gsel and \
                rec[2] == (repr(gym_opp(BATTLE, *gsel, st)) if gsel[1] == 'T' else '') and all(k < len(st['box']) for k in rec[1]):
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
                gain = GYM_WIN_XP + 10 * (8 if gsel[1] in ('L', 'R', 'T') else gsel[1]) if won else GYM_LOSE_XP
                tw = tower_state(st)
                # 기록엔 종 번호만 있어 이로치를 몰랐다(2026-11-09 이로치 가이오가가 보통 그림) — 팀의 이로치 종을 함께
                # shortcut: 같은 종이 이로치·보통 둘 다 팀에 있으면 둘 다 이로치로 그린다 — 그런 팀이 생기면 기록에 가방 번호를 싣는다
                battle_now = {'ev': ev, 'k': 0, 'won': won, 'first': first, 'xp': gain, 'ups': ups,
                              'shiny': {n for k_, n, _ in team if st['box'][k_].get('shiny')},
                              'tower': (tw['streak'], tw['best']) if gsel[1] == 'T' else None,
                              'key': f'champ{gsel[0]}' if gsel[1] == 'L' else f'gym:{gsel[0]}-{gsel[1]}'}
                view, msg = 'fight', ''
                scr.timeout(600)  # 기록을 한 줄씩 — getkey 는 이 값을 따른다(빠뜨리면 키를 누를 때까지 멈춘다)
        if act in ('dex', 'box', 'trade'):
            view, top, dg, msg, sel = 'bag' if act == 'box' else act, 0, opened_gen(st), '', 0  # 가방은 아이템 화면(2026-11-05)
            tm, tcol, tidy_skip = 0, 0, set()
        elif isinstance(act, tuple) and act[0] == 'medleft':  # 훈장 왼쪽 열 클릭 — 그 분류로
            bcat, bcol, sel, top, msg = act[1], 0, 0, 0, ''
        elif isinstance(act, tuple) and act[0] == 'tradeleft':  # 교환 왼쪽 열 클릭 — 그 일로
            tm, tcol, sel, top, confirm, msg = act[1], 0, 0, 0, None, ''
        elif isinstance(act, tuple) and act[0] == 'trrow':  # 박사에게 목록 줄 클릭 — 그 줄을 고른다(보내기는 Enter 두 번)
            tcol, sel = 1, act[1]
        elif act == 'back' and view == 'fight' and battle_now['k'] < len(battle_now['ev']):
            battle_now['k'] = len(battle_now['ev'])  # 먼저 끝까지 보여 주고, 한 번 더 누르면 나간다
        elif act == 'back' and view == 'fight' and battle_now['won'] and not battle_now.get('tower'):
            break  # 이겼으면 다시 준비할 일이 없으니 포켓몬 모드를 닫고 허브로 — 지면 준비 화면으로(아래)
        elif act == 'back':
            if view == 'fight':
                scr.timeout(2000)
            back_to = {'info': 'dex', 'gym': 'gyms', 'fight': 'gym', 'change': chg_from, 'slotpick': 'main', 'use': 'bag', 'bag': 'main', 'mon': 'slotpick'}.get(view, 'main')  # 한 단계 위로
            if view == 'mon':
                msg, naming = '', None
            if view == 'use':  # 아이템 상세에서 나오면 고르던 아이템으로(2026-11-10 사용자)
                sel, top, msg, confirm = max(0, min(bag_sel, len(bag_items(st)) - 1)), 0, '', None
            elif view == 'change' and chg_from == 'use':  # 능력치·개수 고르기에서 나오면 고르던 포켓몬으로 — 쓰기 확인 문구는 지운다
                sel, top, cap_n, msg, confirm = use_sel, 0, 1, '', None
            view = back_to
        elif isinstance(act, tuple) and act[0] == 'gymleft':  # 체육관 왼쪽 열 클릭 — 그 줄로(세대면 오른쪽에 관들이 바뀐다)
            sel, gcol, gsub, gtop = act[1], 0, 0, 0
        elif isinstance(act, tuple) and act[0] == 'gym':
            if view == 'gyms' and act[1][1] not in ('R', 'T'):  # 오른쪽 열 클릭이면 그 줄을 고른 것으로 — 돌아왔을 때 같은 자리
                right = gym_right(st, act[1][0])
                gcol, gsub = 1, right.index(act[1]) if act[1] in right else 0
            view, gsel, msg = 'gym', act[1], ''
        elif isinstance(act, tuple) and act[0] == 'pin':
            msg = toggle_showcase(st, act[1])
            save(st)
        elif isinstance(act, tuple) and act[0] == 'info':
            view, info = 'info', act[1]
        elif view in ('main', 'wild') and act in ('explore', 'throw', 'super', 'hyper', 'master', 'run', 'evolve', 'candy'):
            if act == 'explore':
                got = explore(st, t)
                if not got:
                    msg = L(f'{habitat(st)[1]}엔 지금 나올 포켓몬이 없다 — h 로 서식지를 바꾸자.', f'Nothing left in {habitat(st)[2]} — press h to change habitat.') \
                        if habitat(st)[3] and tickets(st, t) > 0 and not st['wild'] else ''
                elif got[1]:
                    msg = L(f'또 {name(got[0])}! 이미 가방에 있어서 몬스터볼 {got[1]}개로 바꿨다.',
                            f'{name(got[0])} again! Already in your bag, so it became {got[1]} Poké Ball(s).')
                elif st['wild'].get('shiny') and not st['wild'].get('disguise'):  # 이로치 메타몽은 변신한 모습이 보통 색 — 잡아야 안다
                    msg = L(f'✨ 반짝반짝! 이로치 {name(got[0])}(이)가 튀어나왔다!', f'✨ Sparkle! A shiny {name(got[0])} jumped out!')
                else:
                    msg = L(f'풀숲에서 {name(got[0])}(이)가 튀어나왔다!', f'{name(got[0])} jumped out of the tall grass!')
                if st['wild']:  # 만남 화면으로 — 볼은 고르고 [던지기] 로 던진다
                    view, ball_pick, focus = 'wild', default_ball(st), 'throw_sel'
            elif act in ('throw', 'super', 'hyper', 'master') and st['wild']:
                n, eggs0, ditto, dsh = shown(st['wild']), len(st.get('eggs', [])), st['wild'].get('disguise'), st['wild'].get('shiny')
                real = st['wild'].get('form') or st['wild']['id']
                r = throw(st, t, kind={'throw': 'ball'}.get(act, act))
                msg = {'caught': L(f'신난다! {name(n)}(을)를 잡았다!', f'Gotcha! {name(n)} was caught!'),
                       'missed': L('아깝다! 볼에서 빠져나왔다.', 'Argh! It broke free.'),
                       'fled': L(f'{name(n)}(은)는 도망쳐 버렸다…', f'{name(n)} ran away…'),
                       'raidonly': L('레이드 보스에겐 레이드볼만 던질 수 있다.', 'Only Raid Balls work on a raid boss.'),
                       'needhyper': L(f'{name(n)}(은)는 하이퍼볼·마스터볼로만 잡힌다! [교환] → [몬스터볼]에서 바꿔 오자.',
                                      f'Only an Ultra or Master Ball works on {name(n)}! Swap balls in [trade] → [balls].'),
                       None: L('그 볼이 없다.', "You don't have that ball.")}[r]
                if r == 'caught' and ditto and sp(real) in ZORUA:
                    msg += L(f' …앗! {name(n)}의 모습이 일그러진다… 환영이 풀렸다! 정체는 {"✨이로치 " if dsh else ""}{name(real)}(이)였다!',
                             f' …Huh? {name(n)} is warping… the illusion breaks! It was a {"✨shiny " if dsh else ""}{name(real)}!')
                elif r == 'caught' and ditto:
                    msg += L(f' …어라? {name(n)}의 모습이 흐물흐물 녹아내린다… 정체는 {"✨이로치 " if dsh else ""}메타몽이었다!',
                             f' …Huh? {name(n)} is melting away… it was a {"✨shiny " if dsh else ""}Ditto all along!')
                if r == 'caught' and len(st.get('eggs', [])) > eggs0:
                    msg += L(' 풀숲에서 알도 하나 주웠다!', ' Found an egg in the grass too!')
                if not st['wild']:  # 잡았거나 도망갔으면 메인으로
                    view = 'main'
            elif act == 'run' and st['wild']:
                if st['wild'].get('raid'):  # 레이드 보스를 놓아주면 그 주 레이드는 끝
                    raid_done(st)
                msg, st['wild'], view = L('무사히 도망쳤다.', 'Got away safely.'), None, 'main'
            elif act in ('evolve', 'candy'):
                before = name(st['box'][st['partner']]['id']) if st['partner'] is not None else ''
                n = evolve(st, t) if act == 'evolve' else use_candy(st, t)
                msg = L(f'오잉!? {before}의 모습이… {name(n)}(으)로 진화했다!', f'What? {before} evolved into {name(n)}!') if n else ''
            save(st)


def selftest():
    global DEX
    import struct
    import tempfile

    def unlock(st, top, mark='x'):  # top 세대까지 열기 — 아래 세대 챔피언 승리 + 그 세대 야생 종 전부 포획(opened_gen)
        st['league'] = {**st.get('league', {}), **{str(g): mark for g in range(1, top)}}
        st['caught'] = st['caught'] + [n for n in DEX if gen(n) < top and wild_ok(n) and n not in st['caught']]
        return st
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
    ev = unlock(new_state(), 2)
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
    ev['box'] = [{'id': n, 'xp': 0} for n in wild_pool(ev)]  # 후보가 다 가방에 있어도 앞 WINDOW 마리가 아니라 후보 전부에서
    ev['caught'] = [n for n in ev['caught'] if n not in (152, 155, 158)]  # 스타팅 셋을 다시 후보로 — 다섯 마리(> WINDOW)
    ev['box'] += [{'id': n, 'xp': 0} for n in (152, 155, 158)]
    assert len(wild_pool(ev)) > WINDOW and dict(wild_odds(ev)) == {n: 1 for n in wild_pool(ev)}, wild_odds(ev)
    assert dex_hint(ev, 196) == L('진화 — ???에서 · 야생은 드묾', 'evolve from ??? · rare in the wild')
    odds = dict(wild_odds(dup))
    assert odds[25] == BOXED_WEIGHT and sorted(odds.values()).count(1) == WINDOW, odds
    dup['box'] = []
    assert dict(wild_odds(dup)).get(25) == 1  # 진화시켜 가방에서 빠지면 다시 보통 확률
    dup['box'] = [{'id': 25, 'xp': 0}]
    pick = type('R', (), {'choices': lambda s, xs, weights: [25], 'random': lambda s: 0.5})()
    assert explore(dup, ENCOUNTER_EVERY, pick) == (25, 0) and dup['wild']['id'] == 25  # 같은 종도 만나서 잡는다
    assert throw(dup, ENCOUNTER_EVERY, type('R', (), {'random': lambda s: 0.0})()) == 'caught' and [m['id'] for m in dup['box']] == [25, 25]
    assert dup['box'][1]['iv'] == [0] * 6 and len(dup['box'][0].get('iv', [])) == 0  # 개체값은 잡을 때(가짜 난수 0 → 0)
    # 개체값: 0~15, 바닥값, 불러올 때 옛 포켓몬에 고정된 값
    assert all(0 <= v <= 15 for _ in range(200) for v in roll_iv()) and min(min(roll_iv(floor=IV_FLOOR)) for _ in range(200)) >= IV_FLOOR
    lr = tempfile.mkdtemp()
    save({**new_state(), 'box': [{'id': 25, 'xp': 0}, {'id': 150, 'xp': 0}, {'id': 19, 'xp': 0, 'iv': [15, 3, 7], 'alpha': True}]}, lr)
    assert load(lr)['box'][0]['iv'] == load(lr)['box'][0]['iv'] and len(load(lr)['box'][0]['iv']) == 6
    # 2026-11-06 옛 [공, 방, 체] → [HP, 공, 방] + 새 특공·특방·스피드(우두머리 바닥값, 불러올 때마다 같은 값)
    m6 = load(lr)['box'][2]['iv']
    assert m6[:3] == [7, 15, 3] and min(m6[3:]) >= ALPHA_IV and m6 == load(lr)['box'][2]['iv']
    assert min(load(lr)['box'][1]['iv']) >= IV_FLOOR  # 옛 전설도 바닥값부터
    if FORMS:  # 긴 이름도 개체값(%)은 늘 보인다 — 이름 끝을 줄인다
        bt = bag_text({'id': 10251, 'xp': 0, 'iv': [14, 15, 13, 14, 14, 14]}, 40)
        assert bt.endswith('93%') and '…' in bt and sum(map(memo.cw, bt)) <= 40
    class DittoRng:  # 메타몽을 뽑고, 피카츄로 변신, 이로치·우두머리는 아님
        def random(self): return 0.5
        def choices(self, seq, weights=None): return [DITTO]
        def choice(self, seq): return 25
    dt = new_state()
    assert explore(dt, ENCOUNTER_EVERY, DittoRng()) == (25, 0) and dt['wild']['id'] == DITTO and shown(dt['wild']) == 25
    assert 25 in dt['seen'] and DITTO not in dt['seen'] and 25 in disguises(dt) and DITTO not in disguises(dt)
    assert throw(dt, ENCOUNTER_EVERY, type('R', (), {'random': lambda s: 0.0})()) == 'caught'
    assert dt['box'][-1]['id'] == DITTO and DITTO in dt['caught'] and DITTO in dt['seen'] and 25 not in dt['caught']
    lf = {**new_state(), 'wild': {'id': 150, 'balls': 3}, 'balls': 10, 'hyper': 1}  # 전설: 하이퍼볼이 떨어지면 몬스터볼이 남아도 도망
    assert throw(lf, 0, type('R', (), {'random': lambda s: 0.99})(), 'hyper') == 'fled' and lf['wild'] is None
    if FORMS:  # 리전폼을 잡아도 원래 종 연구에
        rf = {**new_state(), 'wild': {'id': 19, 'form': 10091, 'balls': 3}}
        assert throw(rf, 0, type('R', (), {'random': lambda s: 0.0})()) == 'caught' and rf['research']['19']['c'] == 1
    class ZoroRng:  # 조로아크를 뽑는다
        def random(self): return 0.5
        def choices(self, seq, weights=None): return [571]
        def choice(self, seq): return seq[0]
    zr = {**new_state(), 'box': [{'id': 1, 'xp': 0, 'iv': [1] * 6}, {'id': 25, 'xp': 0, 'iv': [1] * 6}], 'partner': 0, 'team': [0, 1]}
    unlock(zr, 5)  # 5세대 열림
    assert explore(zr, ENCOUNTER_EVERY, ZoroRng()) == (25, 0) and zr['wild']['id'] == 571 and 571 not in zr['seen']  # 팀 마지막(피카츄)의 환영
    assert throw(zr, ENCOUNTER_EVERY, type('R', (), {'random': lambda s: 0.0})()) == 'caught' and zr['box'][-1]['id'] == 571 and 571 in zr['seen']
    zn = {**new_state(), 'league': zr['league']}
    assert explore(zn, ENCOUNTER_EVERY, ZoroRng()) == (571, 0) and 'disguise' not in zn['wild']  # 팀·동료가 없으면 환영 없이
    # 배틀 타워: 챔피언 뒤 열림 · 팀 앞 3마리 · 시작할 때만 탐색 2번 · 7연승마다 상 · 지면 끝(최고 기록은 남는다)
    tw_ = unlock(new_state(), 2)
    assert (0, 'T') in gym_rows(tw_)[:2] and not any(r[1] == 'T' for r in gym_rows(new_state()))
    o0, o6, o48 = tower_opp(tw_, 0), tower_opp(tw_, 6), tower_opp(tw_, 48)
    assert len(o0) == TOWER_SIZE and o0 == tower_opp(tw_, 0) and o0[0][1] == TOWER_LV0 and o0[0][2] == (6,) * 6
    assert o6[0][1] == TOWER_LV0 + 3 and o48[0][1] == TOWER_LV0 + 6 * TOWER_LV_STEP + 3 and o48[0][2] == (12,) * 6 and DEX[o48[-1][0]][5] == 1
    assert all(n not in CHILDREN and gen(n) <= opened_gen(tw_) for n, *_ in o0)
    class Stats(dict):  # 타워 상대는 아무 종이나 — 없는 종은 약하게
        def __init__(self, base, weak): super().__init__(base); self.weak = weak
        def __missing__(self, k): return self.weak
    tw_['box'] = [{'id': 6, 'xp': 0, 'bxp': 2000, 'iv': [15] * 6} for _ in range(4)]
    tw_['team'] = [0, 1, 2, 3]
    gdt = {'stats': Stats({6: [250] * 6}, [5] * 6), 'types': Stats({6: [10]}, [1]), 'eff': {}, 'tnames': {}}
    used0 = tw_['used']
    for k in range(7):
        won, _, _ = fight(tw_, 40 * ENCOUNTER_EVERY, gdt, 0, 'T', random.Random(k))
        assert won
    assert tw_['used'] == used0 + TOWER_COST and tower_state(tw_)['streak'] == 7 and tw_['super'] == 3  # 7연승 상
    assert 'tower7' in check_badges(tw_)
    gdt['stats'], gdt['types'] = Stats({6: [5] * 6}, [250] * 6), Stats({6: [1]}, [10])  # 이제 상대가 훨씬 세다
    assert not fight(tw_, 40 * ENCOUNTER_EVERY, gdt, 0, 'T', random.Random(9))[0]
    assert tower_state(tw_)['run'] is False and tower_state(tw_)['streak'] == 0 and tower_state(tw_)['best'] == 7
    used1 = tw_['used']
    fight(tw_, 40 * ENCOUNTER_EVERY, gdt, 0, 'T', random.Random(10))
    assert tw_['used'] == used1 + TOWER_COST  # 다시 시작하면 또 탐색 2번
    # 병뚜껑 특훈(여섯 칸): 은색은 고른 하나 +1, 금색은 고른 하나를 15로 — 이미 15인 칸은 안 나온다
    cp = {**new_state(), 'box': [{'id': 19, 'xp': 0, 'iv': [15, 3, 14, 15, 15, 15]}], 'items': {'cap': 2, 'gcap': 1}}
    assert [f for f, *_ in change_options(cp, 0)] == [('iv', 1), ('iv', 2), ('ivmax', 1), ('ivmax', 2)]
    assert change(cp, 0, 1) == ('iv', 2) and cp['box'][0]['iv'] == [15, 3, 15, 15, 15, 15] and cp['items']['cap'] == 1
    # 여러 개 한꺼번에 — 15까지 남은 칸과 가진 개수 중 작은 쪽까지만(2026-11-10 사용자)
    cq = {**new_state(), 'box': [{'id': 19, 'xp': 0, 'iv': [10, 3, 14, 15, 15, 15]}], 'items': {'cap': 7}}
    k_atk = next(k for k, o in enumerate(change_options(cq, 0)) if o[0] == ('iv', 1))
    assert cap_max(cq, 0, ('iv', 1)) == 7 and cap_max(cq, 0, ('iv', 0)) == 5 and cap_max(cq, 0, ('iv', 2)) == 1
    assert change(cq, 0, k_atk, 4) == ('iv', 1) and cq['box'][0]['iv'][1] == 7 and cq['items']['cap'] == 3
    assert change(cq, 0, next(k for k, o in enumerate(change_options(cq, 0)) if o[0] == ('iv', 0)), 99) == ('iv', 0)
    assert cq['box'][0]['iv'][0] == 13 and cq['items']['cap'] == 0  # 99개라 해도 가진 3개까지
    assert [f for f, *_ in change_options(cp, 0)] == [('iv', 1), ('ivmax', 1)] and opt_name(('iv', 1)) == L('공격 +1', 'Attack +1')
    assert change(cp, 0, 0) == ('iv', 1) and cp['box'][0]['iv'] == [15, 4, 15, 15, 15, 15]
    assert change(cp, 0, 0) == ('ivmax', 1) and cp['box'][0]['iv'] == [15] * 6 and change_options(cp, 0) == []
    eg2 = {**new_state(), 'eggs': [{'id': 1, 'base': 0, 'need': 125_000}, {'id': 4, 'base': 50_000, 'need': 75_000}]}
    assert [(round(f, 2), km) for _, f, km in egg_lines(eg2, 100_000)] == [(0.8, 7), (0.67, 5)] and len(egg_lines(eg2, 0)) == 2  # 알마다 따로, 빠른 순
    assert [egg_km({'need': k * EGG_STEP}) for k in (10, 15, 20, 25, 40, 120)] == [2, 5, 5, 7, 10, 12]
    first_bonus = type('R', (), {'random': lambda s: 0.99, 'choices': lambda s, xs, weights: [xs[0]]})()  # 이로치 아님 · 덤은 몬스터볼 1
    ek = {**new_state(), 'eggs': [{'id': 798, 'base': 0, 'need': 250_000}, {'id': 123, 'base': 0, 'need': 125_000}]}
    weekly(ek)['done'] = True  # 이번 주 과제가 마침 '알 부화'면 그 보상까지 섞여 날짜 따라 깨졌다(2026-11-09)
    assert len(hatch(ek, 300_000, first_bonus)) == 2 and (ek['balls'], ek['super'], ek['hyper']) == (2, 1, 2)  # 12km 하이퍼볼 2 · 7km 슈퍼볼 1 더
    assert ek['news'][0]['arg'] == '798|balls:1,hyper:2'
    said = speech(ek, 300_000, now=ek['news'][-1]['at'] + 1, folder=tempfile.mkdtemp())  # 가장 최근 — 7km 알
    assert ek['news'][-1]['arg'] == '123|balls:1,super:1' and L('몬스터볼 1개 + 슈퍼볼 1개', '1 Poké Ball + 1 Great Ball') in said[0]
    assert all(len(_pokedata.egg_px(km)) == 16 for km in _pokedata.EGG_KM) and set(_pokedata.EGG_KM) == {2, 5, 7, 10, 12}
    # 팀 칸: 빈칸이면 채우고, 이미 팀이면 자리 맞바꾸기, None 이면 비우기 · 후보는 이름으로 찾는다
    ts = {**new_state(), 'box': [{'id': n, 'xp': 0, 'iv': [5] * 6} for n in (1, 4, 7, 25)], 'team': [0, 1]}
    set_slot(ts, 2, 3)
    assert ts['team'] == [0, 1, 3]
    set_slot(ts, 0, 3)
    assert ts['team'] == [3, 1, 0]  # 이미 팀에 있던 피카츄는 자리만 맞바꾼다
    set_slot(ts, 1, None)
    assert ts['team'] == [3, 0] and pick_list(ts, L('피카', 'Pika')) == [3] and len(pick_list(ts)) == 4
    assert slot_rows(ts, 0)[-1] is None and slot_rows(ts, 0, L('피카', 'Pika')) == [3] and None not in slot_rows(ts, 5)  # 비우기는 맨 끝, 찾는 중·빈칸엔 없다
    nb = [(8, 1, 10, ('slot', 0), ''), (8, 16, 25, ('slot', 1), ''), (13, 1, 10, ('slot', 3), ''), (3, 48, 61, 'explore', ''), (6, 48, 61, 'dex', '')]
    assert move_geo(nb, ('slot', 1), curses.KEY_RIGHT) == 'dex' and move_geo(nb, 'dex', curses.KEY_LEFT) == ('slot', 1)  # 팀 ↔ 버튼 열
    assert move_geo(nb, 'dex', curses.KEY_UP) == 'explore' and move_geo(nb, ('slot', 0), curses.KEY_DOWN) == ('slot', 3)  # ↑↓ 는 같은 열
    assert fit('팔데아 켄타로스', 8) == '팔데아…' and fit('피카츄', 8) == '피카츄'
    # 만남 화면 볼 고르기: 처음은 던질 수 있는 가장 싼 볼, 마스터볼은 저절로 안 고른다 · 전설은 하이퍼볼부터 · 레이드는 레이드볼
    bc = {**new_state(), 'wild': {'id': 16, 'balls': 0}, 'balls': 0, 'super': 0, 'hyper': 0, 'master': 1}
    assert default_ball(bc) is None and default_ball(bc, 'master') == 'master'  # 마스터볼뿐이면 직접 골라야
    bc['super'] = 2
    assert default_ball(bc) == 'super' and default_ball(bc, 'ball') == 'super'
    bc['wild'] = {'id': 150, 'balls': 3}
    assert [c for _, _, c in ball_choices(bc)] == [False, False, False, True] and default_ball(bc) is None
    bc['wild'] = {'id': 150, 'balls': 3, 'raid': True}
    assert ball_choices(bc) == [('ball', 3, True)] and default_ball(bc) == 'ball'
    import ast  # main() 안에서 모듈 함수 이름을 변수로 쓰면 main 전체에서 그 함수가 가려져 누르는 순간 꺼졌다(explore · made, 2026-11-05)
    tree = ast.parse(open(__file__, encoding='utf-8').read())
    funcs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    mainf = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    bound = {x.id for node in ast.walk(mainf) if isinstance(node, (ast.Assign, ast.For, ast.AugAssign))
             for t in (node.targets if isinstance(node, ast.Assign) else [node.target]) for x in ast.walk(t) if isinstance(x, ast.Name)}
    assert not bound & funcs, bound & funcs
    cc = {**new_state(), 'wild': {'id': 19, 'balls': 3}}  # 화면에 보이는 포획 확률 = 던질 때 쓰는 확률
    assert catch_chance(cc, 'super') == min(1.0, catch_rate(19) * 1.5) and catch_chance(cc, 'master') == 1.0
    cc['wild'] = {'id': 150, 'balls': 3}
    assert catch_chance(cc, 'ball') == 0 and catch_chance(cc, 'hyper') == 0.4
    cc['wild'] = {'id': 19, 'balls': 3, 'alpha': True}
    assert catch_chance(cc, 'ball') == catch_rate(19) * 0.5
    # 가방 = 아이템: 가진 것만 한 줄씩 · 아이템마다 쓸 수 있는 포켓몬 · 사탕은 아무 포켓몬에게(동료 경험치는 그대로)
    bg = {**new_state(), 'box': [{'id': 25, 'xp': 0, 'iv': [1] * 6}, {'id': 10, 'xp': 0, 'iv': [15, 2, 3, 15, 15, 15]}, {'id': 646, 'xp': 0, 'iv': [5] * 6},
                                 {'id': 644, 'xp': 0, 'iv': [1] * 6}], 'partner': 0, 'candy': 1, 'items': {'cap': 1, 'soup': 0, 'fuse:646': 1}, 'base': 77}
    assert [k for k, _ in bag_items(bg)] == ['candy', 'cap', 'fuse:646'] and bag_items(bg)[-1][1] is None
    assert {i for i, *_ in item_targets(bg, 'candy')} == {0, 1}  # 진화할 수 있는 피카츄·캐터피 — 큐레무·제크로무는 아니다
    assert [(i, len(ks)) for i, ks, ok, _ in item_targets(bg, 'cap') if i == 1] == [(1, 2)]  # 캐터피는 공·방 두 칸 — 바꾸기 화면에서 고른다
    assert [i for i, *_ in item_targets(bg, 'candy', name(10)[:2])] == [1] and item_targets(bg, 'cap', '없는이름') == []  # 이름 찾기
    assert [i for i, *_ in item_targets(bg, 'fuse:646')] == [2]
    assert use_candy(bg, 999, i=1) == 11 and bg['box'][1]['id'] == 11 and bg['candy'] == 0 and bg['base'] == 77
    assert iv_text({'iv': [15] * 6}).endswith('(100%) ★') and iv_text({'iv': [0] * 6}).endswith('(0%)')
    # 박사에게: 동료·팀·이로치는 남고, 번호가 당겨져도 동료·팀이 같은 포켓몬을 가리킨다, 볼은 dupe_balls 만큼
    ps = new_state()
    ps['box'] = [{'id': 10, 'xp': 0, 'iv': [1] * 6}, {'id': 10, 'xp': 0, 'iv': [9] * 6}, {'id': 10, 'xp': 0, 'iv': [5] * 6, 'shiny': True},
                 {'id': 25, 'xp': 0, 'iv': [2] * 6, 'bxp': 900}, {'id': 25, 'xp': 0, 'iv': [15] * 6}, {'id': 25, 'xp': 0, 'iv': [3] * 6},
                 {'id': 1, 'xp': 0, 'iv': [0] * 6}]
    ps['partner'], ps['team'] = 6, [5]
    assert sorted(tidy_targets(ps)) == [0]  # 캐터피 하나 · 피카츄: 최고 개체·경험치는 남고 남은 하나는 팀
    assert send_away(ps, [6, 5, 2]) == (0, 0)  # 동료·팀·이로치는 못 보낸다
    assert send_away(ps, [0, 3]) == (2, dupe_balls(10) + dupe_balls(25)) and ps['balls'] == dupe_balls(10) + dupe_balls(25)
    assert [m['id'] for m in ps['box']] == [10, 10, 25, 25, 1] and ps['box'][ps['partner']]['id'] == 1
    assert ps['team'] == [3] and ps['box'][3]['iv'] == [3] * 6 and ps['sent'] == 2
    # 가방 정렬·세대: 도감번호(기본) · 레벨 높은 순 · 개체값 높은 순 · 이름(한글 ㄱㄴㄷ) — 같으면 도감번호
    bo = new_state()
    bo['box'] = [{'id': 152, 'xp': 0, 'iv': [1] * 6}, {'id': 25, 'xp': 0, 'iv': [15] * 6}, {'id': 3, 'xp': 0, 'iv': [5] * 6, 'bxp': 500},
                 {'id': 1, 'xp': 0, 'iv': [9] * 6}]
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
    assert need_xp(2) == 400_000 and need_xp(3) is None and need_xp(108) is not None and need_xp(83) is None  # 내루미 → 내룸벨트(4세대) · 파오리는 가라르 모습만 대파무사로
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
    assert _pokedata.crop([[(0, 0, 0, 0), (200, 10, 10, 255)]], 2) == [[_pokedata.SILHOUETTE + (255,)]]  # 실루엣
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
    assert explore(sh, ENCOUNTER_EVERY, lucky) == (25, 0) and sh['wild'] == {'id': 25, 'balls': BALLS, 'shiny': True, 'alpha': True, 'tries': 0, 'mark': 'alpha'}
    assert throw(sh, 0, lucky) == 'caught' and sh['box'][-1] == {'id': 25, 'xp': 0, 'iv': [ALPHA_IV] * 6, 'shiny': True, 'alpha': True, 'mark': 'alpha'}
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
    assert all(SHIP.search(x) for x in ('PR을 올렸다', 'PR #3 merged', 'pushed to main', 'git push 완료', '배포함'))
    assert not any(SHIP.search(x) for x in ('[Test] prefix', 'e-approval todo', 'keep it private', 'improvement_roadmap'))
    ja, jb = ('six', 2, 1, 'b', 'B', 3, 1), ('six', 4, 1, 'p', 'P', 2, 2)  # 장식 배지 + 동료 그림을 한 번에
    assert join_art(ja, jb) == ('six', 2, 1, ('b', 'p'), 'B', 3, 1, [(4, 1, 'P')]) and join_art(None, jb) == jb
    assert join_art(join_art(ja, jb), ('six', 7, 1, 'w', 'W', 2, 2))[7] == [(4, 1, 'P'), (7, 1, 'W')]  # 배지·동료·야생 셋도
    assert join_art(('kitty', 2, 1, 7, b'B', 3, 1), ('kitty', 4, 1, 9, b'P', 2, 2))[7] == [(4, 1, 9, b'P', 2, 2)]
    rw = new_state()
    rw['reward_since'] = '2026-10-01'
    assert reward(rw, jd) == 1 and rw['extra'] == WORK_EXPLORES and rw['super'] == 0 and reward(rw, jd) == 0  # 21일만, 하루 한 번
    job('b', [(day2, '배포 완료')])
    feed._cache.clear()
    assert reward(rw, jd) == 1 and rw['extra'] == 2 * WORK_EXPLORES and not rw['eggs']  # 22일 — 연속 2일, 알은 아직
    rw2 = new_state()
    assert reward(rw2, jd, today='2026-10-22') == 1 and rw2['reward_since'] == '2026-10-22'  # 켠 날(22일) 전 보상은 없다
    global shipped
    real_ship, days70 = shipped, {f'2026-{m:02d}-{d:02d}': ['a'] for m in (7, 8, 9) for d in range(1, 29)}
    shipped = lambda folder=None: days70  # 기록이 60일을 넘어도 한 번 준 날은 다시 주지 않는다
    try:
        rw3 = {**new_state(), 'reward_since': '2026-07-01'}
        assert reward(rw3) == 84 and reward(rw3) == 0 and len(rw3['rewarded']) == 84
    finally:
        shipped = real_ship
    bad = tempfile.mkdtemp()  # 깨진 저장 파일은 덮어쓰지 않고 사본을 남긴다
    open(f'{bad}/pokemon.json', 'w').write('{"box": [{"id": 25')
    bs = load(bad)
    save(bs, bad)
    assert bs['_broken'] and open(f'{bad}/pokemon.json').read() == '{"box": [{"id": 25' and os.path.exists(f'{bad}/pokemon.json.bad')
    assert summary(bad)[0][1] == 'warn' and open(f'{bad}/pokemon.json').read() == '{"box": [{"id": 25'
    assert load(tempfile.mkdtemp()).get('_broken') is None  # 파일이 없으면 새 게임
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
    weekly(eg)['done'] = True  # 이번 주 과제가 '알 부화'여도 그 소식·보상이 안 섞이게(날짜 따라 깨졌다)
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
    assert eg['box'][-1] == {'id': 172, 'xp': 0, 'iv': [IV_FLOOR] * 6, 'shiny': True}
    assert 172 in eg['caught'] and 172 in eg['shiny'] and not eg['eggs'] and eg['news'][-1]['kind'] == 'hatch'
    assert eg['super'] == 1 and eg['news'][-1]['arg'] == '172*|super:1'  # 포켓몬과 함께 덤 볼 하나
    assert sum(w for _, _, w in EGG_BONUS) == 100 and ball_name('balls', '2') == ('몬스터볼 2개', '2 Poké Balls')
    # 일한 보상: 평일 +1 · 일한 토요일(11/7) +2 에 연속 하루 · 쉰 일요일(11/8)은 건너뜀 → 5일째(11/6)·10일째(11/12)에 +5
    sd = tempfile.mkdtemp()
    for j, d in enumerate(('2026-11-02', '2026-11-03', '2026-11-04', '2026-11-05', '2026-11-06', '2026-11-07',
                           '2026-11-09', '2026-11-10', '2026-11-11', '2026-11-12', '2026-11-13')):
        os.makedirs(f'{sd}/s{j}')
        with open(f'{sd}/s{j}/state.json', 'w') as f:
            json.dump({'name': f's{j}', 'state': 'done'}, f)
        with open(f'{sd}/s{j}/timeline.jsonl', 'w') as f:
            f.write(json.dumps({'at': f'{d}T03:00:00Z', 'state': 'done', 'detail': 'pushed', 'text': '…'}) + '\n')
    feed._cache.clear()
    ew = new_state()
    ew['reward_since'] = '2026-10-01'
    ew['weekly'] = {'key': week_key(), 'kind': 'hatch', 'n': 0, 'done': False}  # 실제 이번 주 과제가 'ship' 이면 상이 섞인다
    assert reward(ew, sd) == 11 and ew['extra'] == 10 * WORK_EXPLORES + WEEKEND_EXPLORES + 2 * STREAK_BONUS and ew['hyper'] == 0 and not ew['eggs']
    assert sum(1 for n in ew['news'] if n['kind'] == 'streak') == 2 and tickets(ew, 0) == ew['extra']
    assert streak(ew, '2026-11-08') == 6 and streak(ew, '2026-11-13') == 11 and streak(ew, '2026-11-16') == 11  # 쉰 일요일·다음 월요일(아직)
    assert [n['arg'] for n in ew['news'] if n['kind'] == 'work'].count(str(WEEKEND_EXPLORES)) == 1  # 소식은 최근 10개만 남는다
    assert [n['arg'] for n in ew['news'] if n['kind'] == 'streak'] == ['5', '10']
    assert streak({'rewarded': ['2026-11-02', '2026-11-03', '2026-11-05']}, '2026-11-05') == 1  # 수요일을 빠지면 처음부터
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
    unlock(og, 2, '2026-10-26')
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
    # 장식 배지: 받은 것만, 최대 SHOWCASE_MAX 개, 다시 고르면 뺀다 · 진행도
    sc = new_state()
    filler = [f'gen{g}' for g in range(1, 8)]  # 앞의 다섯과 합쳐 12개를 채울 것
    sc['badges'] = {b: '2026-10-21' for b in ['catch1', 'catch10', 'catch50', 'evo1', 'super1', 'hyper1'] + filler}
    for b in ['catch1', 'catch10', 'catch50', 'evo1', 'super1'] + filler:
        toggle_showcase(sc, b)
    assert sc['showcase'][:5] == ['catch1', 'catch10', 'catch50', 'evo1', 'super1'] and len(sc['showcase']) == SHOWCASE_MAX
    toggle_showcase(sc, 'hyper1')
    assert 'hyper1' not in sc['showcase']  # 13개째는 안 된다
    toggle_showcase(sc, 'catch10')
    toggle_showcase(sc, 'myth')
    assert sc['showcase'] == ['catch1', 'catch50', 'evo1', 'super1'] + filler  # 빼기 · 안 받은 건 못 고름
    sc['caught'] = list(range(1, 86))
    assert badge_goal(sc, 'catch100') == (85, 100) and badge_goal(sc, 'gen1') == (85, 151) and badge_goal(sc, 'legend') is None
    assert set(MEDAL_ART) == {b for b, _, _, _ in BADGES}  # 모든 훈장에 그림이 있다
    # 세대 훈장 — 빛나는 부적 별 가운데에 금색 로마 숫자(가장 넓은 줄 가운데), 크기는 그대로
    star = [[(0, 0, 0, 0)] * 15 for _ in range(9)]
    for x_ in range(1, 14):
        star[4][x_] = (250, 250, 200, 255)
    for g in (1, 8, 9):
        cn = _pokedata.charm_numeral(star, g)
        assert len(cn) == 1 and len(cn[0]) == 13 and (255, 196, 32, 255) in cn[0], g  # 한 줄짜리 별은 잘려도 숫자가 든다
    assert MEDAL_ART['gen3'] == 'shiny-charm-3' and _pokedata._src('item:shiny-charm-3') == 'items/gen5/shiny-charm-3'
    # 훈장 도구 그림: gen9 → gen8 → gen5 순서로 찾은 폴더에서(없으면 바로 아래), 흰 테두리가 없으면 두른다(2026-11-10 사용자)
    assert _pokedata._src('item:poke-ball') == 'items/gen5/poke-ball' and _pokedata._src('item:rusted-sword') == 'items/gen8/rusted-sword'
    assert _pokedata._src('item:galarica-twig') == 'items/galarica-twig' and all(a in _pokedata.ITEM_DIR or a.startswith('shiny-charm-') or
                                                                               _pokedata._item_dir(a) == '' for a in MEDAL_ART.values())
    ol = _pokedata.outline([[(0, 0, 0, 255)]])
    assert len(ol) == 3 and ol[0][0] == (255, 255, 255, 255) and ol[1][1] == (0, 0, 0, 255) and _pokedata.edge_white(ol) == 1.0
    import tempfile  # 옆으로 긴 그림(120×30)은 높이 칸 안에 — 폭이 높이를 넘지 않고 위아래가 빈다
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as _f:
        _f.write(_pokedata.encode_png([[(9, 9, 9, 255)] * 120 for _ in range(30)]))
    _l = _pokedata._local
    _pokedata._local = lambda n: _f.name
    _sp = _pokedata.strip([1], 44)
    _pokedata._local = _l
    os.unlink(_f.name)
    assert len(_sp) == 44 and len(_sp[0]) == 44 and _sp[0][0][3] == 0 and _sp[22][0][3] == 255
    _pokedata._local = lambda n: _f2.name  # 배지: 작은 그림도 키워서 흰 테두리 — 높이 그대로, 둘레가 흰색
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as _f2:
        _f2.write(_pokedata.encode_png([[(9, 9, 9, 255)] * 20 for _ in range(20)]))
    _sb = _pokedata.strip([_pokedata.BADGE + 1], 44)
    _pokedata._local = _l
    os.unlink(_f2.name)
    assert len(_sb) == 44 and len(_sb[0]) == 44 and _sb[0][22] == (255, 255, 255, 255) and _sb[22][22] == (9, 9, 9, 255)
    assert _pokedata.scale2x([[(1, 1, 1, 1), (2, 2, 2, 2)]]) == [[(1, 1, 1, 1)] * 2 + [(2, 2, 2, 2)] * 2] * 2
    _s = _pokedata.strip  # grid: 4개씩 끊어 쌓고, 짧은 줄은 투명으로 채운다
    _pokedata.strip = lambda ids, hh, gap=4: [[(1, 1, 1, 255)] * (len(ids) * 3)] * hh
    _gg = _pokedata.grid(['a'] * 6, 10, 4, gap=2)
    _pokedata.strip = _s
    assert len(_gg) == 10 and len(_gg[0]) == 12 and _gg[6][5][3] == 255 and _gg[6][6][3] == 0 and _gg[4][0][3] == 0
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
    assert team_of(gs, 2) == [] and team_of(gs, 1)[0][1] == 7 and fighters(gs, team_of(gs, 1))[0][2] == (0,) * 6
    won, ev, first = fight(gs, 4 * ENCOUNTER_EVERY, gd, 1, 0, random.Random(1), today='2026-10-21')
    assert won and first and gs['gym'] == {'gym:1-0': '2026-10-21'} and gs['hyper'] == 1 and gs['used'] == GYM_COST
    assert gs['box'][0]['bxp'] == 3000 + GYM_WIN_XP and ev[0][0] == 'send' and fight_line(ev[-1])
    won, ev, first = fight(gs, 4 * ENCOUNTER_EVERY, gd, 1, 0, random.Random(1))
    assert won and not first and gs['hyper'] == 1  # 다시 이기면 하이퍼볼은 없다(처음 한 번만)
    assert fight_state(ev, len(ev))['foe'][1] == 0
    gs['gym'].update({f'gym:1-{i}': '2026-10-21' for i in range(8)})
    eggs = len(gs['eggs'])
    assert 'conquer1' in check_badges(gs) and len(gs['eggs']) == eggs + 1 and gs['master'] == 1  # 지방 정복 → 마스터볼과 알
    unlock(gs, 2, '2026-10-21')
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
    assert box_level({'id': 1, 'bxp': 60}) == 16  # 이상해씨 15 + 60 // 50
    # 이전 세대 섞기: 1세대만 열렸으면 없음, 2세대가 열리면 탐색의 약 20%가 1세대(잡은 종·전설 포함)
    real_forms = dict(FORMS)  # 리전폼은 받아 둔 파일과 상관없이 정해 둔 셋으로 시험
    FORMS.clear()
    FORMS.update({10091: (19, 'alola'), 10092: (20, 'alola'), 10107: (52, 'alola'), 10108: (53, 'alola'), 10161: (52, 'galar'),
                  10169: (144, 'galar'), 10252: (128, 'paldea-aqua-breed'), 10233: (157, 'hisui')})
    try:
        assert old_pool(new_state()) == []
        o2 = unlock(new_state(), 2)
        op = old_pool(o2)
        assert op and all(gen(n) == 1 for n in op) and 1 in op and 150 in op
        assert {10091, 10169, 10252} <= set(op) and 10233 not in op  # 2세대 종(블레이범)의 폼은 2세대가 지나야
        assert is_legend(10169) and is_legend(150) and not is_legend(10091) and not is_legend(19)  # 가라르 프리져도 전설
        # 전설 한 종의 몫은 후보 수와 상관없다 — 1세대(전설 1 · 일반 40)에서도 8세대 규모(전설 68 · 일반 461)에서도 약 0.88%
        r = random.Random(7)
        small = [146] + [n for n in DEX if gen(n) == 1 and not DEX[n][5]][:40]
        big = [n for n in DEX if gen(n) < 8 and DEX[n][5]][:68] + [n for n in DEX if gen(n) < 8 and not DEX[n][5]][:461]
        hit_small = sum(old_pick(small, r) == 146 for _ in range(40000)) / 40000
        hit_big = sum(old_pick(big, r) == big[0] for _ in range(40000)) / 40000
        assert 0.006 < hit_small < 0.012 and 0.006 < hit_big < 0.012, (hit_small, hit_big)
        assert old_pick([150, 151], r) in (150, 151)  # 전설만 남아도 고른다
        o2['caught'] += [152, 153, 154]  # 지금 세대(2)에서 계열을 다 잡은 치코리타는 지금 세대 후보에서 빠져도 이쪽으로 만난다
        assert 152 not in wild_pool(o2) and 152 in old_pool(o2) and 155 not in old_pool(o2)  # 진화형은 원래 야생에 없다(wild_ok)
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
            def choices(self, seq, weights=None): return [self.choice(seq)]
        fm = unlock(new_state(), 2); fm['balls'] = 0; c0 = list(fm['caught'])
        assert explore(fm, ENCOUNTER_EVERY, Pick(10091)) == (10091, 0)
        # (난수 0 이라 이로치·우두머리도 — 리전폼도 같은 판정, 2026-11-06)
        assert fm['wild'] == {'id': 19, 'form': 10091, 'balls': BALLS, 'shiny': True, 'alpha': True, 'tries': 0, 'mark': 'alpha'} and fm['forms_seen'] == [10091]
        assert throw(fm, ENCOUNTER_EVERY, Pick(10091)) == 'caught'
        assert fm['box'][0]['shiny'] and fm['box'][0]['alpha'] and art_of(fm['box'][0]) == 'form:shiny/10091'
        assert [m['id'] for m in fm['box']] == [10091] and fm['forms'] == [10091] and fm['caught'] == c0 and fm['partner'] == 0
        assert 'form1' in check_badges(fm) and 'form_all' not in fm['badges']
        assert explore(fm, 2 * ENCOUNTER_EVERY, Pick(10091)) == (10091, 0) and fm['wild']['form'] == 10091
        fm['wild'] = None
        assert explore(fm, 3 * ENCOUNTER_EVERY, Pick(10169)) == (10169, 0)  # 가라르 프리져 — 전설이라 하이퍼볼부터
        assert throw(fm, 3 * ENCOUNTER_EVERY, Pick(10169)) == 'needhyper'
        # 종이 정하는 값은 원래 종으로 · 진화는 같은 지방 모습으로(보통 모습과 섞이지 않게) · 지방 전용 진화형
        assert gen(10091) == 1 and depth(10091) == 0 and depth(10092) == 1 and dupe_balls(10091) == dupe_balls(19)
        assert evo_next(10091) == [10092] and evo_next(10092) == [] and 10092 not in evo_next(19)
        assert evo_next(10107) == [10108] and 863 in evo_next(10161) and not {53, 10108} & set(evo_next(10161))
        assert evo_next(83) == [] and evo_next(52) == [53] and evo_next(194) == [195] and research_goals(83)['e'] == 0  # 보통 모습은 지방 전용 진화형으로 안 간다
        assert need_xp(10091) == STAGE_XP[0] and need_xp(10092) is None
        fm['wild'] = None
        assert evolve(fm, 10**9) == 10092 and fm['box'][0]['id'] == 10092 and 10092 in fm['forms'] and fm['caught'] == c0
        assert evo_status(fm, 10**9) == ('final',) and box_level(fm['box'][0]) == _battle.level(1, 0)
        fm['team'] = [0]
        assert team_of(fm, 1) == [(0, 10092, box_level(fm['box'][0]))]  # 배틀엔 폼 번호 — 종족값·타입은 그 모습 것
        # 그림 번호: 리전폼은 'form:번호', Kitty 이미지 번호는 정수
        assert art_of(fm['box'][0]) == 'form:shiny/10092' and art_of({'id': 25, 'shiny': True}) == 25 + _pokedata.SHINY
        assert partner_id_of(fm) == 'form:shiny/10092' and _pokedata.img_id('form:10092') >= 300000 and _pokedata.img_id(25) == 25
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
    fu['box'] = [{'id': 25, 'xp': 0, 'iv': [1] * 6}, {'id': 646, 'xp': 5, 'bxp': 120, 'iv': [9] * 6},
                 {'id': 644, 'xp': 0, 'iv': [1] * 6}, {'id': 644, 'xp': 0, 'iv': [15] * 6}, {'id': 643, 'xp': 0, 'iv': [2] * 6}]
    fu['partner'], fu['team'] = 4, [1, 3]
    assert change_options(fu, 1)[0][2] is False and L('연구', 'research') in change_options(fu, 1)[0][3]  # 도구가 없으면 못 한다
    for key in 'c' + 'www':  # 큐레무 연구를 끝내면 유전자쐐기
        research_bump(fu, 646, key)
    assert fu['items'].get('fuse:646') == 1 and [k for k, _ in bag_items(fu)][-1] == 'fuse:646'
    assert fuse_options(fu, 0) == [] and fuse_options(fu, 1) == [(10022, 2)]  # 레시라무(4)는 동료라 못 쓰고, 재료는 팀 밖·개체값 낮은 것
    assert change_options(fu, 1) == [(10022, ('mon', 2), True, '')] and change(fu, 1, 0) == 10022
    assert [m['id'] for m in fu['box']] == [25, 10022, 644, 643] and 'fused' not in fu['box'][1] and fu['box'][1]['iv'] == [9] * 6
    assert fu['box'][2]['iv'] == [15] * 6  # 좋은 제크로무는 남는다 · 개체값은 기본(큐레무) 것
    assert fu['partner'] == 3 and fu['team'] == [1, 2] and fu['box'][1]['bxp'] == 120  # 번호 당김 · 본체 경험치 유지
    assert name(10022) == L('블랙큐레무', 'Black Kyurem') and gen(10022) == 5 and evo_next(10022) == [] and art_of(fu['box'][1]) == 'form:10022'
    assert 'fuse1' in check_badges(fu) and send_away(fu, [1]) == (0, 0)  # 합체한 것은 박사에게 안 간다
    fu2 = {**new_state(), 'box': [{'id': 10022, 'xp': 0, 'iv': [1] * 6}, {'id': 10022, 'xp': 0, 'iv': [9] * 6}]}
    assert send_away(fu2, [0]) == (0, 0) and tidy_targets(fu2) == []  # 팀 밖이어도, 둘이어도 — 재료까지 잃는다
    assert change_options(fu, 1) == [] and fuse_options(fu, 2) == []  # 합체한 것은 다시 못 바꾼다
    # 특수 모습: 연구 완료 → 메가스톤(X·Y), 그 뒤 5마리 더 잡을 때마다 또 · 쓰는 건 그 세대가 열린 뒤 · 되돌릴 수 없다
    real_sp = dict(SPECIALS)
    SPECIALS.clear()
    SPECIALS.update({10034: (6, 'mega', 6, 'x', ''), 10035: (6, 'mega', 6, 'y', ''), 10196: (6, 'gmax', 8, '', ''),
                     10078: (383, 'primal', 6, '', ''), 10157: (800, 'ultra', 7, '', '')})
    try:
        mg = new_state()
        mg['box'], mg['partner'] = [{'id': 6, 'xp': 0, 'iv': [5] * 6, 'bxp': 300}], 0
        lv0 = box_level(mg['box'][0])
        assert [(f, ok) for f, _, ok, _ in change_options(mg, 0)] == [(10034, False), (10035, False), (10196, False)]
        for key in 'ccccc' + 'www':
            research_bump(mg, 6, key)
        assert mg['items'] == {'stone:10034': 1, 'stone:10035': 1} and mg['news'][-1]['kind'] == 'item'
        for _ in range(RESEARCH_CATCH):
            research_bump(mg, 6, 'c')
        assert mg['items'] == {'stone:10034': 2, 'stone:10035': 2}  # 다시 모은다
        mw = new_state()  # 전설(잡기 목표 1)도 연구 뒤엔 5마리마다 — 매번이 아니라
        for key in 'c' + 'www' + 'c' * (RESEARCH_CATCH - 1):
            research_bump(mw, 800, key)
        assert mw['items'] == {'stone:10157': 1, 'fuse:800': 1}  # 네크로즈마 — 울트라네크로Z 와 네크로플러스
        research_bump(mw, 800, 'c')
        assert mw['items'] == {'stone:10157': 2, 'fuse:800': 1}  # 도구는 하나면 된다
        assert change(mg, 0, 0) is None  # 6세대가 아직 안 열렸다
        unlock(mg, 6, '2026-10-30')  # 5세대까지 사천왕 → 6세대 열림
        assert change(mg, 0, 0) == 10034 and mg['box'][0]['id'] == 10034 and mg['items']['stone:10034'] == 1
        assert mg['specials'] == [10034] and box_level(mg['box'][0]) == lv0 and name(10034) == L('메가리자몽 X', 'Mega Charizard X')
        assert change_options(mg, 0) == [] and item_name('stone:10035') == L('리자몽나이트Y', 'Charizardite Y')
        assert [ok for _, _, ok, _ in change_options({**mg, 'box': [{'id': 6, 'xp': 0}]}, 0)][2] is False  # 거다이맥스는 8세대
        ul = new_state()
        ul['box'], ul['items'] = [{'id': 10155, 'xp': 0}], {'stone:10157': 1}
        unlock(ul, 7)
        assert change(ul, 0, 0) == 10157 and name(10157) == L('울트라네크로즈마', 'Ultra Necrozma')
        pr = new_state()
        raid_state(pr)
        pr['wild'] = {'id': 383, 'balls': RAID_BALLS, 'raid': True}
        assert throw(pr, 0, type('R', (), {'random': lambda s: 0.0})()) == 'caught' and pr['items'] == {'stone:10078': 1}
        assert item_name('stone:10078') == L('주홍구슬', 'Red Orb') and item_name('soup') == L('다이수프', 'Max Soup')
        # 특수 모습 연구는 그 모습 도감에 따로(만들기 1 · 배틀 승리 3) · 이로치 특수 모습은 이로치 그림
        assert research_goals(10034) == {'m': 1, 'w': RESEARCH_WIN} and mg['research']['10034'] == {'m': 1}
        for _ in range(RESEARCH_WIN):
            research_bump(mg, 10034, 'w')
        assert research_done(mg, 10034) and 10034 in mg['researched'] and mg['research']['6'].get('w') == 3  # 리자몽 기록은 그대로
        assert art_of({'id': 10034, 'shiny': True}) == 'form:shiny/10034' and art_of({'id': 10034}) == 'form:10034'
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
    # 진화로만 얻는 종(리자몽)의 연구 — 잡기 목표 1, 진화해서 얻으면 잡기로 센다, 옛 저장은 불러올 때 맞춰 바로 완료
    assert research_goals(6)['c'] == 1 and research_goals(4)['c'] == RESEARCH_CATCH and research_goals(150)['c'] == 1
    rz = unlock({**new_state(), 'box': [{'id': 5, 'xp': 0, 'iv': [0] * 6}], 'partner': 0, 'candy': 1}, 2)
    assert use_candy(rz, 0, i=0) == 6 and rz['research']['6']['c'] == 1
    rl = tempfile.mkdtemp()
    save({**new_state(), 'caught': [4, 5, 6], 'research': {'4': {'c': 1}, '6': {'w': 3}}, 'box': [{'id': 6, 'xp': 0}]}, rl)
    lz = load(rl)
    assert lz['research']['6']['c'] == 1 and 6 in lz['researched'] and 5 not in lz['researched']
    assert any(k.startswith('stone:') for k in lz.get('items', {})) or not SPECIALS  # 메가리자몽나이트
    # 우두머리: 볼 3번 안에 못 잡으면 보유 볼이 남아도 도망
    al = new_state()
    al['wild'], al['balls'] = {'id': 19, 'balls': BALLS, 'alpha': True, 'tries': 0}, 10
    never2 = type('R', (), {'random': lambda s: 0.99})()
    assert [throw(al, 0, never2) for _ in range(3)] == ['missed', 'missed', 'fled'] and al['wild'] is None
    # 잡은 우두머리는 박사에게·정리로 안 보내고, 배틀에는 능력치 ×ALPHA_BOOST 로
    al['box'] = [{'id': 1, 'xp': 0, 'iv': [15] * 6}, {'id': 19, 'xp': 0, 'iv': [12] * 6, 'alpha': True},
                 {'id': 19, 'xp': 0, 'iv': [15] * 6, 'bxp': 9999}]
    assert tidy_targets(al) == [] and send_away(al, [1]) == (0, 0) and len(al['box']) == 3
    assert alpha_x(al['box'][1]) == (1, ALPHA_BOOST) and alpha_x(al['box'][2]) == ()
    # 레이드: 이번 주 보스(열린 세대의 전설) · 목록 맨 위 · 이기면 레이드볼 3개로만 · 놓치면 이번 주 끝
    rd = new_state()
    g_r, boss = raid_boss(rd)
    assert g_r == 1 and DEX[boss][5] == 1 and raid_boss(new_state()) == (g_r, boss) and gym_rows(rd)[0] == (1, 'R')
    rd['box'], rd['team'] = [{'id': 7, 'xp': 0, 'bxp': 3000, 'iv': [15] * 6}, {'id': 152, 'xp': 0, 'iv': [0] * 6}], [1, 0]
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
    rc['box'], rc['team'], rc['wild'] = [{'id': 7, 'xp': 0, 'bxp': 3000, 'iv': [15] * 6}], [0], {'id': 19, 'balls': BALLS}
    assert fight(rc, 4 * ENCOUNTER_EVERY, gd2, 1, 'R', random.Random(1))[0] and rc['raid']['pending'] and rc['wild']['id'] == 19
    rc['wild'] = None  # 하던 야생이 끝나면 레이드 보스가 나온다
    raid_release(rc)
    lucky2 = type('R', (), {'random': lambda s: 0.0})()
    assert rc['wild']['raid'] and throw(rc, 0, lucky2) == 'caught' and rc['raids'] == 1 and rc['box'][-1]['id'] == boss
    assert min(rc['box'][-1]['iv']) >= IV_FLOOR and 'raid1' in check_badges(rc)
    # 주가 바뀌어도: 지난주 보스를 놓쳐도 이번 주 레이드는 남고, 지난주에 이기고 못 만난 보스는 한 번 나온다
    rw = {**new_state(), 'raid': {'week': '2026-W40', 'won': True, 'done': False, 'pending': False},
          'wild': {'id': boss, 'balls': 1, 'raid': True, 'week': '2026-W40'}}
    raid_state(rw)
    assert throw(rw, 0, never2) == 'fled' and not rw['raid']['done'] and gym_rows(rw)[0][1] == 'R'
    rp = {**new_state(), 'raid': {'week': '2026-W40', 'won': True, 'done': False, 'pending': True}, 'wild': {'id': 19, 'balls': BALLS}}
    raid_state(rp)
    rp['wild'] = None
    raid_release(rp)
    assert rp['wild']['raid'] and rp['wild']['id'] == raid_boss(rp, '2026-W40')[1] and 'late' not in rp['raid'] and not rp['raid']['done']
    # 줄 접기: 폭 안에서 빈칸·쉼표 뒤에서 접고, '·' 는 앞 낱말에 붙인다(한글은 2칸)
    assert fold('가나다 · 라마 · 바사', 12) == ['가나다 ·', '라마 · 바사'] and fold('a, b, c', 3) == ['a,', 'b,', 'c'] and fold('a, b, c', 4) == ['a,', 'b, c']
    assert all(sum(map(memo.cw, x)) <= 20 for x in fold('내 팀 메가니움 Lv39, 블레이범 Lv39, 장크로다일 Lv39, 토게틱 Lv27', 20))
    # 팀 칸은 남은 줄에 맞춘다 — 22줄 패널(아래 글 5줄)이면 칸 5줄·그림 3줄, 크면 그림 10줄까지(폭이 먼저 막는다), 좁으면 글만
    assert team_layout(22 - 6 - 5) == (5, 3) and team_layout(40) == (13, 10) and team_layout(5) == (2, 0)
    assert team_layout(30, graphics=False) == (2, 0) and team_layout(6) == (3, 1) and team_layout(40, cap=5) == (8, 5)
    assert wrap_widths([5, 5, 5], 12) == [[0, 1], [2]] and wrap_widths([3, 3, 3], 12) == [[0, 1, 2]] and wrap_widths([4, 4, 4], 9) == [[0, 1], [2]] and wrap_widths([], 9) == []
    for free in range(0, 40):  # 어떤 크기든 팀 2줄이 남은 줄을 넘지 않는다(글만 2줄이 최소)
        c, a = team_layout(free)
        assert (2 * c <= free or c == 2) and a + 2 <= c
    # 검색어 글자 판정 — 방향키·Enter·Tab·Esc 는 글자가 아니고, 영문·한글·숫자는 글자
    assert not any(typed_char(k) for k in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT, curses.KEY_ENTER, 9, 10, 13, 27, -1))
    assert all(typed_char(ord(c)) for c in 'aZ9가ㄱ.')
    # 서식지 — 고른 곳의 타입만(타입 모르면 거르지 않음), 나올 게 없으면 탐색이 None
    TYPES.clear(); TYPES.update({1: [12, 4], 4: [10], 7: [11], 25: [13], 133: [1]})
    hb = new_state()
    assert in_habitat(hb, 4) and wild_odds(hb)
    hb['habitat'] = 'water'
    assert habitat(hb)[1] == '물가' and in_habitat(hb, 7) and not in_habitat(hb, 4) and in_habitat(hb, 999999)
    assert {n for n, _ in wild_odds(hb)} <= {n for n in DEX if TYPES.get(n) in (None, [11])} and 7 in {n for n, _ in wild_odds(hb)}
    TYPES.clear()
    # 증표 — MARK_RATE 밖이면 없음, 안이면 하나(우두머리 증표는 뽑히지 않음) · 칭호
    assert roll_mark(type('R', (), {'random': lambda s: 0.5})()) is None
    assert roll_mark(type('R', (), {'random': lambda s: 0.0, 'choices': lambda s, k, weights: [k[weights.index(0) - 1]]})()) in MARKS
    assert MARK_WEIGHT['alpha'] == 0 and titled('ferocious', '피카츄').endswith('피카츄') and titled(None, 'x') == 'x'
    mw = {**new_state(), 'wild': {'id': 25, 'balls': 3, 'mark': 'rare'}}
    assert throw(mw, 0, type('R', (), {'random': lambda s: 0.0})()) == 'caught' and mw['box'][-1]['mark'] == 'rare'
    # 리본 — 한 번만, 동료가 알림 · 닉네임
    rb = {**new_state(), 'box': [{'id': 25, 'xp': 0, 'iv': [15] * 5 + [14]}, {'id': 1, 'xp': 0, 'nick': '뽀삐'}], 'partner': 0}
    assert give_ribbon(rb, [0, 1, 1], 'champ3') == 2 and give_ribbon(rb, [0], 'champ3') == 0
    assert rb['box'][1]['ribbons'] == ['champ3'] and rb['news'][-1]['kind'] == 'ribbon' and speech(rb, 0, awake=set())[0].startswith('팀 2마리')
    assert mon_name(rb['box'][1]) == '뽀삐' and bag_text(rb['box'][1], 40).startswith('뽀삐') and 1 in [i for i in pick_list(rb, '뽀')]
    rb['items'] = {'gcap': 1}  # 금색 병뚜껑으로 여섯이 모두 15 — 노력 리본
    k_ = next(k for k, o in enumerate(change_options(rb, 0)) if o[0] == ('ivmax', 5))
    assert change(rb, 0, k_) == ('ivmax', 5) and 'effort' in rb['box'][0]['ribbons']
    assert all(RIBBONS[r][0].endswith('-ribbon') for r in RIBBONS) and art_id('ribbon:effort-ribbon') == 'ribbon:effort-ribbon'
    # 만남 화면 ↑↓ — 던질 수 있는 볼 사이를 바로 오가고 끝에서 멈춘다(전설엔 몬스터볼·슈퍼볼을 건너뜀)
    wb = new_state(); wb['wild'] = {'id': 25, 'balls': 0}; wb['balls'], wb['super'], wb['hyper'], wb['master'] = 3, 0, 2, 1
    U, D = curses.KEY_UP, curses.KEY_DOWN
    assert wild_ball_step(wb, 'ball', D) == 'hyper' and wild_ball_step(wb, 'hyper', D) == 'master' and wild_ball_step(wb, 'master', D) == 'master'
    assert wild_ball_step(wb, 'hyper', U) == 'ball' and wild_ball_step(wb, 'ball', U) == 'ball'
    wb['wild'] = {'id': 150, 'balls': 0}
    assert wild_ball_step(wb, 'hyper', U) == 'hyper'
    # 체육관 두 열 — 왼쪽 레이드·타워·세대, 오른쪽 고른 세대의 8관(+ 정복하면 사천왕), 시작은 못 이긴 관이 남은 앞 세대
    gy = new_state(); gy['league'] = {}
    assert [k for k, _ in gym_left(gy) if k != 'R'] == ['G'] * opened_gen(gy) and gym_right(gy, 1) == [(1, i) for i in range(8)]
    assert gym_left(gy)[gym_start(gy)] == ('G', 1)
    gy['gym'] = {f'gym:1-{i}': 'd' for i in range(8)}; gy['badges']['conquer1'] = 'd'
    assert gym_right(gy, 1)[-1] == (1, 'L') and gym_left(gy)[gym_start(gy)] == ('G', 1)  # 1세대 사천왕이 남았다
    gy['league'] = {'1': 'd'}  # 챔피언은 이겼지만 1세대 야생 종이 남았으면 2세대는 아직 닫혀 있다(2026-11-09)
    assert opened_gen(gy) == 1 and len(wild_left(gy, 1)) > 0
    unlock(gy, 2, 'd')
    assert ('T', 0) in gym_left(gy)
    lw = unlock(new_state(), 2); lw['caught'].remove(151); lw['master'] = 1  # 뮤만 남았다 — 잡는 순간 2세대가 열린다
    assert opened_gen(lw) == 1 and wild_left(lw, 1) == [151]
    lw['wild'] = {'id': 151, 'balls': BALLS}
    assert throw(lw, 0, random.Random(1), 'master') == 'caught' and opened_gen(lw) == 2 and lw['news'][-1]['kind'] == 'opengen' and gym_left(gy)[gym_start(gy)] == ('G', 2)  # 1세대를 다 이겼으면 2세대부터
    # 훈장 분류 — 맨 위 '장식 중', 모든 훈장이 한 분류에 한 번씩, 장식한 체육관 배지도 '장식 중'에
    mg = new_state(); mg['badges'] = {'catch1': 'd'}; mg['gym'] = {'gym:1-0': 'd'}; mg['showcase'] = ['catch1', 'gym:1-0']
    grps = medal_groups(mg)
    assert grps[0][1] == ['catch1', 'gym:1-0'] and sorted(b for _, ids in grps[1:] for b in ids) == sorted(b for b, _, _, _ in BADGES)
    assert grps[1][1][0] == 'catch1' and all(len(ids) for _, ids in grps[1:])
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
