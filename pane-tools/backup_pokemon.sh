#!/usr/bin/env bash
# pokemon.json 을 Windows 쪽에 날짜별로 백업한다 — cron 이 매일 17:59 에 부른다. 최근 30개만 남긴다.
# cron 줄의 POKEMON_BACKUP_DIR 로 Windows 쪽(C:) 폴더를 주면 WSL 배포판이 초기화돼도 살아남는다.
set -euo pipefail
SRC="$HOME/.claude/pane-tools/pokemon.json"
DST="${POKEMON_BACKUP_DIR:-$HOME/.claude/pane-tools/backup}"  # install.sh 가 WSL 이면 Windows 쪽 폴더를 넘긴다
LOG="$HOME/.claude/pane-tools/backup.log"
[ -f "$SRC" ] || { echo "$(date '+%F %T') 원본 없음 — 건너뜀" >> "$LOG"; exit 0; }
mkdir -p "$DST"
cp "$SRC" "$DST/pokemon-$(date +%F).json"
ls -1t "$DST"/pokemon-*.json | tail -n +31 | xargs -r rm -f
echo "$(date '+%F %T') 백업 완료 → $DST/pokemon-$(date +%F).json" >> "$LOG"
