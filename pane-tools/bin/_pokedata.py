"""포켓몬 도감 데이터를 PokeAPI 공개 데이터(CSV)에서 받아 ~/.claude/pane-tools/pokedex.json 으로 만든다.

저장소에는 포켓몬 데이터를 넣지 않는다(비공식 팬메이드 — README 참고). pokemon 모드를 처음 열 때 한 번 받는다.
종마다 [번호, 한국어 이름, 세대, 진화 전 번호(없으면 0), 포획률, 급(0 일반·1 전설·2 환상), 영어 이름].
`python3 _pokedata.py` 로 직접 다시 받을 수도 있다(새 세대가 나왔을 때).
"""
import csv
import io
import json
import os
import urllib.request

ROOT = os.path.expanduser('~/.claude/pane-tools')
OUT = f'{ROOT}/pokedex.json'
BASE = 'https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/'
KO, EN = '3', '9'  # PokeAPI 의 언어 번호


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


if __name__ == '__main__':
    print(ensure(force=True))
