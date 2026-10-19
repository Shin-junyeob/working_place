#!/usr/bin/env bash
# 저장소를 clone 해서 쓰는 사람용(고치고 push 하는 개발용). 그냥 쓰기만 할 거면 README 의 마켓플레이스 설치가 더 쉽다.
#   bash install.sh                    기본: 세션마다 이 폴더의 mod 를 자동으로 불러오게 + 자체 점검
#   bash install.sh --tmux-layout      + tmux 마우스 · sett 레이아웃(~/dev-layout.sh, alias sett) · 허브를 dev:0.3 에, dev:0.0 세션을 따라가게
#   bash install.sh --pokemon-backup   + 매일 17:59 포켓몬 기록 백업(cron)
# 여러 번 돌려도 같은 줄을 두 번 넣지 않는다. 덮어쓰기 전엔 .bak-<시각> 으로 남긴다.
set -euo pipefail
MODS="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
LAYOUT=0 BACKUP=0
for a in "$@"; do
  case "$a" in
    --tmux-layout) LAYOUT=1 ;;
    --pokemon-backup) BACKUP=1 ;;
    *) echo "모르는 옵션: $a (--tmux-layout, --pokemon-backup)" >&2; exit 1 ;;
  esac
done
ok() { echo "  ✔ $*"; }
warn() { echo "  ⚠ $*"; }

echo "▶ 필요한 프로그램"
for c in claude python3; do command -v "$c" >/dev/null && ok "$c" || warn "$c 없음 — README 의 '준비' 참고"; done

echo "▶ 세션마다 이 폴더의 mod 를 자동으로 불러오게 (~/.claude/settings.json)"
mkdir -p "$HOME/.claude"
S="$HOME/.claude/settings.json"
[ -f "$S" ] && cp "$S" "$S.bak-$STAMP"
python3 - "$S" "$MODS" "$LAYOUT" <<'EOF'
import json, os, sys
path, mods, layout = sys.argv[1], sys.argv[2], sys.argv[3] == '1'
d = json.load(open(path)) if os.path.exists(path) else {}
env = d.setdefault('env', {})
env['CLAUDE_CODE_PLUGIN_DIRS'] = mods
env['CLAUDE_CODE_PLUGIN_DIR_WATCH'] = '1'  # claude agents 로 띄운 백그라운드 세션도 저장 시 다시 불러온다
if layout:  # sett 레이아웃: 허브는 3번 패널에, 0번 패널(claude agents)에 열린 세션을 따라간다
    d.setdefault('pluginConfigs', {})['pane-tools@inline'] = {
        'options': {'launcher': 'tmux', 'tmuxTarget': 'dev:0.3', 'followPane': 'dev:0.0'}}
tmp = path + '.tmp'
with open(tmp, 'w') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
    f.write('\n')
os.replace(tmp, path)
EOF
ok "CLAUDE_CODE_PLUGIN_DIRS=$MODS"
if grep -q 'pane-tools@working-place' "$S" 2>/dev/null; then warn "마켓에서 설치한 pane-tools 도 켜져 있다 — /plugin 에서 지우세요(두 번 걸립니다)"; fi

if [ $LAYOUT = 1 ]; then
  echo "▶ tmux 레이아웃"
  command -v tmux >/dev/null || warn "tmux 없음 — sudo apt install tmux"
  touch "$HOME/.tmux.conf"
  grep -q '^set -g mouse on' "$HOME/.tmux.conf" && ok "tmux 마우스 켜짐" || { echo 'set -g mouse on' >> "$HOME/.tmux.conf"; ok "~/.tmux.conf 에 마우스 추가"; }
  if [ -f "$HOME/dev-layout.sh" ] && ! cmp -s "$HOME/dev-layout.sh" "$MODS/extras/dev-layout.sh"; then
    cp "$HOME/dev-layout.sh" "$HOME/dev-layout.sh.bak-$STAMP"; warn "기존 ~/dev-layout.sh 는 .bak-$STAMP 로 남김"
  fi
  cp "$MODS/extras/dev-layout.sh" "$HOME/dev-layout.sh" && chmod +x "$HOME/dev-layout.sh"
  grep -q "^alias sett=" "$HOME/.bashrc" 2>/dev/null && ok "alias sett 있음" || { echo "alias sett='~/dev-layout.sh'" >> "$HOME/.bashrc"; ok "alias sett 추가"; }
fi

if [ $BACKUP = 1 ]; then
  echo "▶ 포켓몬 기록 매일 17:59 백업"
  DST="$HOME/.claude/pane-tools/backup"
  if command -v cmd.exe >/dev/null && command -v wslpath >/dev/null; then  # WSL 이면 Windows 쪽에 — 배포판이 초기화돼도 남게
    WINHOME="$(cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r')"
    [ -n "$WINHOME" ] && DST="$(wslpath "$WINHOME")/pokemon-backup"
  fi
  if command -v crontab >/dev/null; then
    (crontab -l 2>/dev/null | grep -v backup_pokemon.sh || true; echo "59 17 * * * POKEMON_BACKUP_DIR=$DST bash $MODS/pane-tools/backup_pokemon.sh") | crontab -
    ok "백업 위치: $DST"
    systemctl is-active cron >/dev/null 2>&1 || warn "cron 서비스가 꺼져 있다 — WSL 이면 /etc/wsl.conf 에 [boot] systemd=true 후 wsl --shutdown"
  else
    warn "crontab 없음 — 백업 예약을 건너뜀"
  fi
fi

echo "▶ 자체 점검"
for t in memo tetris hub; do
  (cd "$MODS/pane-tools/bin" && python3 "$t.py" --selftest) >/dev/null && ok "$t" || warn "$t 자체 점검 실패"
done
command -v claude >/dev/null && { claude plugin validate "$MODS/pane-tools" >/dev/null 2>&1 && ok "pane-tools mod" || warn "pane-tools mod 검사 실패"; }

echo
echo "끝. 새로 여는 Claude 세션에서 /mods (이미 떠 있는 세션은 새 설정을 모른다)."
echo "띄울 곳은 /config → pane-tools 에서 바꾼다(tmux 패널 · 새 창 · 사용자 명령)."
