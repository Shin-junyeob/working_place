#!/usr/bin/env bash
# 저장소를 clone 해서 쓰는 사람용(고치고 push 하는 개발용). 그냥 쓰기만 할 거면 README 의 마켓플레이스 설치가 더 쉽다.
#   bash install.sh                    기본: 세션마다 이 폴더의 mod 를 자동으로 불러오게 + 자체 점검
#                                      (macOS 에 cmux 가 있으면 허브를 cmux 분할 패널에 — 이미 정해 둔 곳이 있으면 그대로)
#   bash install.sh --tmux-layout      + tmux 마우스 · sett 레이아웃(~/dev-layout.sh, alias sett) · 허브를 dev:0.3 에, dev:0.0 세션을 따라가게
#   bash install.sh --pokemon-backup   + 매일 17:59 포켓몬 기록 백업(cron)
#   bash install.sh --auto-pull        + 10분마다 GitHub 에서 새 커밋을 받아 온다(cron, 고치던 게 있으면 건너뜀)
# 리눅스 · WSL · macOS 에서 돈다. 여러 번 돌려도 같은 줄을 두 번 넣지 않는다. 덮어쓰기 전엔 .bak-<시각> 으로 남긴다.
set -euo pipefail
MODS="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
OS="$(uname -s)"  # Darwin = macOS
LAYOUT=0 BACKUP=0 PULL=0
for a in "$@"; do
  case "$a" in
    --tmux-layout) LAYOUT=1 ;;
    --pokemon-backup) BACKUP=1 ;;
    --auto-pull) PULL=1 ;;
    *) echo "모르는 옵션: $a (--tmux-layout, --pokemon-backup, --auto-pull)" >&2; exit 1 ;;
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
CMUX=0
[ "$OS" = Darwin ] && [ $LAYOUT = 0 ] && command -v cmux >/dev/null && CMUX=1
python3 - "$S" "$MODS" "$LAYOUT" "$CMUX" <<'EOF'
import json, os, sys
path, mods, layout, cmux = sys.argv[1], sys.argv[2], sys.argv[3] == '1', sys.argv[4] == '1'
# 설정을 dotfiles 저장소에서 심링크로 관리하는 경우가 있다. 링크 자리에 os.replace 하면 링크가 끊겨
# 실제 파일로 바뀌므로, 링크가 가리키는 실제 파일에 쓴다(심링크가 아니면 그대로 같은 경로).
path = os.path.realpath(path)
d = json.load(open(path)) if os.path.exists(path) else {}
env = d.setdefault('env', {})
env['CLAUDE_CODE_PLUGIN_DIRS'] = mods
env['CLAUDE_CODE_PLUGIN_DIR_WATCH'] = '1'  # claude agents 로 띄운 백그라운드 세션도 저장 시 다시 불러온다
if layout:  # sett 레이아웃: 허브는 3번 패널에, 0번 패널(claude agents)에 열린 세션을 따라간다
    d.setdefault('pluginConfigs', {})['pane-tools@inline'] = {
        'options': {'launcher': 'tmux', 'tmuxTarget': 'dev:0.3', 'followPane': 'dev:0.0'}}
elif cmux:
    # macOS + cmux: 지금 보는 cmux 패널을 오른쪽으로 나눠 허브를 띄운다. 백그라운드 세션처럼
    # $CMUX_SURFACE_ID 가 없으면 cmux 는 포커스된 패널을 나누므로 어느 쪽이든 /mods 를 친 화면 옆에 열린다.
    # 허브를 닫으면 '; exit' 로 패널도 닫힌다. 사용자가 이미 정해 둔 곳이 있으면 건드리지 않는다.
    cmd = r"""s=$(cmux new-split right | grep -oE 'surface:[0-9]+' | head -1) && cmux send --surface "$s" {cmd}'; exit\n'"""
    d.setdefault('pluginConfigs', {}).setdefault('pane-tools@inline', {'options': {'launcher': 'command', 'command': cmd}})
tmp = path + '.tmp'
with open(tmp, 'w') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
    f.write('\n')
os.replace(tmp, path)
EOF
ok "CLAUDE_CODE_PLUGIN_DIRS=$MODS"
[ -L "$S" ] && ok "settings.json 심링크 유지 → $(readlink "$S")"
[ $CMUX = 1 ] && ok "허브 위치: cmux 분할 패널 (바꾸려면 /config → pane-tools)"
if grep -q 'pane-tools@working-place' "$S" 2>/dev/null; then warn "마켓에서 설치한 pane-tools 도 켜져 있다 — /plugin 에서 지우세요(두 번 걸립니다)"; fi

if [ $LAYOUT = 1 ]; then
  echo "▶ tmux 레이아웃"
  [ "$OS" = Darwin ] && hint="brew install tmux" || hint="sudo apt install tmux"
  command -v tmux >/dev/null || warn "tmux 없음 — $hint"
  touch "$HOME/.tmux.conf"
  grep -q '^set -g mouse on' "$HOME/.tmux.conf" && ok "tmux 마우스 켜짐" || { echo 'set -g mouse on' >> "$HOME/.tmux.conf"; ok "~/.tmux.conf 에 마우스 추가"; }
  grep -q 'sixel' "$HOME/.tmux.conf" && ok "tmux Sixel 통과 켜짐" || { echo "set -as terminal-features ',xterm*:sixel'  # 허브의 동료 그림(Sixel)을 통과시킨다" >> "$HOME/.tmux.conf"; ok "~/.tmux.conf 에 Sixel 통과 추가(tmux 에 다시 붙으면 적용)"; }
  if [ -f "$HOME/dev-layout.sh" ] && ! cmp -s "$HOME/dev-layout.sh" "$MODS/extras/dev-layout.sh"; then
    cp "$HOME/dev-layout.sh" "$HOME/dev-layout.sh.bak-$STAMP"; warn "기존 ~/dev-layout.sh 는 .bak-$STAMP 로 남김"
  fi
  cp "$MODS/extras/dev-layout.sh" "$HOME/dev-layout.sh" && chmod +x "$HOME/dev-layout.sh"
  case "$(basename "${SHELL:-bash}")" in zsh) RC="$HOME/.zshrc" ;; *) RC="$HOME/.bashrc" ;; esac  # macOS 기본 셸은 zsh
  grep -q "^alias sett=" "$RC" 2>/dev/null && ok "alias sett 있음 ($RC)" || { echo "alias sett='~/dev-layout.sh'" >> "$RC"; ok "alias sett 추가 ($RC)"; }
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
    # systemd 가 있는 리눅스에서만 cron 이 꺼져 있을 수 있다. macOS 는 cron 이 항상 돈다.
    if command -v systemctl >/dev/null; then
      systemctl is-active cron >/dev/null 2>&1 || warn "cron 서비스가 꺼져 있다 — WSL 이면 /etc/wsl.conf 에 [boot] systemd=true 후 wsl --shutdown"
    fi
  else
    warn "crontab 없음 — 백업 예약을 건너뜀"
  fi
fi

if [ $PULL = 1 ]; then
  echo "▶ 10분마다 GitHub 에서 받아 오기"
  if command -v crontab >/dev/null; then
    (crontab -l 2>/dev/null | grep -v extras/autopull.sh || true; echo "*/10 * * * * bash $MODS/extras/autopull.sh") | crontab -
    ok "cron 등록 — 기록: ~/.claude/pane-tools/autopull.log"
  else
    warn "crontab 없음 — 받아 오기 예약을 건너뜀"
  fi
fi

echo "▶ 자체 점검"
for t in memo tetris hub feed; do
  (cd "$MODS/pane-tools/bin" && python3 "$t.py" --selftest) >/dev/null && ok "$t" || warn "$t 자체 점검 실패"
done
command -v claude >/dev/null && { claude plugin validate "$MODS/pane-tools" >/dev/null 2>&1 && ok "pane-tools mod" || warn "pane-tools mod 검사 실패"; }

echo
echo "끝. 새로 여는 Claude 세션에서 /mods (이미 떠 있는 세션은 새 설정을 모른다)."
echo "띄울 곳은 /config → pane-tools 에서 바꾼다(tmux 패널 · 새 창 · 사용자 명령)."
