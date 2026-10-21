"""mods 전체 한/영 전환 — ~/.claude/pane-tools/settings.json 의 "lang" ("ko" | "en").
같은 파일에 PC마다 다른 설정도 둔다(get/put) — 예: "sprite" ("color" | "gray", 허브의 동료 그림 색).

L('메모', 'Memo') 처럼 두 말을 나란히 적고, 허브의 [ 한/EN ] 버튼(toggle)이 바꾼다.
mod(register.ts)와 long-run-watch 도 같은 파일을 읽는다.
"""
import json
import os

ROOT = os.path.expanduser('~/.claude/pane-tools')
PATH = f'{ROOT}/settings.json'
_cache = {'mtime': None, 'lang': 'ko'}


def _settings():
    try:
        with open(PATH, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def lang():
    try:
        m = os.path.getmtime(PATH)
    except OSError:
        return 'ko'
    if m != _cache['mtime']:  # 화면을 그릴 때마다 부르니, 파일이 바뀌었을 때만 다시 읽는다
        _cache['mtime'], _cache['lang'] = m, 'en' if _settings().get('lang') == 'en' else 'ko'
    return _cache['lang']


def L(ko, en):
    return en if lang() == 'en' else ko


def get(key, default=None):
    return _settings().get(key, default)


def put(key, value):
    s = _settings()
    if value is None:  # None 은 지우기
        s.pop(key, None)
    else:
        s[key] = value
    os.makedirs(ROOT, exist_ok=True)
    with open(PATH + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(s, f, ensure_ascii=False)
    os.replace(PATH + '.tmp', PATH)
    return value


def toggle():
    return put('lang', 'ko' if lang() == 'en' else 'en')
