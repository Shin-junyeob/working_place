#!/usr/bin/env bash
# working_place 를 GitHub 에서 저절로 받아 온다 — cron 이 10분마다 부른다(install.sh --auto-pull).
# GitHub 가 PC 로 밀어 줄 수는 없어서 PC 가 가서 확인한다. 이 폴더는 세션이 자동으로 다시 불러오므로 받으면 바로 적용된다.
# 이 PC 에서 고치던 것(커밋 안 한 수정·안 올린 커밋)이 있으면 받지 않는다 — 덮어쓰거나 병합을 만들지 않게.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOG="${HOME}/.claude/pane-tools/autopull.log"
mkdir -p "$(dirname "$LOG")"
say() { echo "$(date '+%F %T') $*" >> "$LOG"; tail -n 200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"; }

cd "$REPO" || exit 0
[ "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" = main ] || { say "main 브랜치가 아니라 건너뜀"; exit 0; }
tries=1; [ "${1:-}" = --boot ] && tries=60  # 켜진 직후(@reboot)엔 네트워크가 잡힐 때까지 2초마다 최대 2분 다시 시도
until git fetch -q origin main 2>/dev/null; do
  tries=$((tries - 1)); [ "$tries" -gt 0 ] || { say "가져오기 실패(네트워크?)"; exit 0; }
  sleep 2
done
behind=$(git rev-list --count HEAD..origin/main)
[ "$behind" -gt 0 ] || exit 0  # 받을 게 없으면 조용히 끝
if [ -n "$(git status --porcelain)" ]; then
  say "새 커밋 ${behind}개가 있지만 이 PC 에 커밋 안 한 수정이 있어 건너뜀 — 커밋·push 후 git pull"
elif [ "$(git rev-list --count origin/main..HEAD)" -gt 0 ]; then
  say "새 커밋 ${behind}개가 있지만 이 PC 에 안 올린 커밋이 있어 건너뜀 — git pull --rebase 후 push"
elif git merge -q --ff-only origin/main 2>/dev/null; then
  say "받음: ${behind}개 → $(git log --oneline -1)"
else
  say "받기 실패: $(git merge --ff-only origin/main 2>&1 | tail -1)"
fi
