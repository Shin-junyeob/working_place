#!/usr/bin/env bash
SESSION=dev
WORK_DIR="${SETT_DIR:-$HOME}"  # 패널들이 시작할 폴더 — 셸 설정(~/.bashrc, macOS 는 ~/.zshrc)에서 export SETT_DIR=... 로 바꾼다

# 레이아웃 (패널 0~3)
#   0 좌     60%  전체높이   claude agents
#   1 우상   40%  높이 20%   셸 (비워 둠)
#   2 우중   40%  높이 35%   세션 활동 피드(feed.py — 세션들이 끝내거나 묻는 순간을 한 줄씩. q 로 닫으면 셸)
#   3 우하   40%  높이 45%   셸 — /mods 허브가 뜨는 고정 자리(오른쪽에 세션 상태 칸이 있어 둘째 claude agents 는 안 띄운다)
# ※ split-window 의 -l 은 "새로 생기는 패널"의 크기다.

# 실제 화면 크기로 세션을 만든다 — -d 로 만들면 80x24 에서 쪼갠 뒤 늘어나 비율이 틀어진다
if [ -n "${TMUX:-}" ]; then
  read -r W H < <(tmux display -p '#{client_width} #{client_height}')
else
  read -r H W < <(stty size 2>/dev/null)
fi
W=${W:-200}; H=$(( ${H:-51} - 1 ))   # 상태줄 1줄 제외

tmux kill-session -t "$SESSION" 2>/dev/null

PANE_LEFT=$(tmux new-session -d -s "$SESSION" -x "$W" -y "$H" -c "$WORK_DIR" -P -F '#{pane_id}')

# 가로: 좌 60 | 우 40
PANE_TOP=$(tmux split-window -h -l $((W * 40 / 100)) -t "$PANE_LEFT" -c "$WORK_DIR" -P -F '#{pane_id}')

# 우측 세로: 상 20 / 중 35 / 하 45 — 아래쪽부터 떼어 낸다
PANE_MID=$(   tmux split-window -v -l $((H * 80 / 100)) -t "$PANE_TOP" -c "$WORK_DIR" -P -F '#{pane_id}')
PANE_BOTTOM=$(tmux split-window -v -l $((H * 45 / 100)) -t "$PANE_MID" -c "$WORK_DIR" -P -F '#{pane_id}')

tmux send-keys -t "$PANE_LEFT"   'claude agents' C-m   # 0
                                                       # 1 셸 (비워 둠)
FEED="${MODS_DIR:-$HOME/.claude/mods}/pane-tools/bin/feed.py"
[ -f "$FEED" ] && tmux send-keys -t "$PANE_MID" "python3 '$FEED'" C-m   # 2
                                                       # 3 셸 (WORK_DIR)
tmux select-pane -t "$PANE_LEFT"

# 아직 붙어있는 클라이언트가 있으면 전환, 방금 detach 됐으면 새로 attach
tmux switch-client -t "$SESSION" 2>/dev/null || tmux attach -t "$SESSION"
