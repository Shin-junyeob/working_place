# 포켓몬 모드 — 남은 일 (2026-11-05 회사 PC에서 넘김)

> 회사 PC 세션에서 메인 화면 · 풀숲 만남 · 가방을 사용자 설계대로 바꿨다(커밋 `f3bc45d` ~ `8e30d3e`).
> 아래는 아직 안 한 것. 하나씩 끝내면 이 파일에서 지운다.

## 1. 체육관 목록 — 세대별 쪽 넘기기
- 문제: 3세대부터 목록이 한 화면을 넘어 ↓ 를 계속 눌러야 한다.
- 정한 방향: 가방·도감처럼 **←→ 로 세대를 넘긴다**. 한 쪽 = 레이드·타워 줄 + 그 세대 8관 + 사천왕.
  열 때는 아직 못 이긴 관이 남은 가장 앞 세대. ←→ 가 세대가 되니 Enter = [도전 준비], P = [장식].
- 회사 PC에서 짜 둔 코드(그대로 쓸 수 있음):
  ```python
  def gym_page(st, g):
      """체육관 목록의 g 세대 쪽 — 맨 위 레이드·타워는 늘, 그 아래 그 세대 8관과 사천왕."""
      return [r for r in gym_rows(st) if r[1] in ('R', 'T') or r[0] == g]

  def gym_start(st):
      """체육관 목록을 열 때 보일 세대 — 아직 못 이긴 관·사천왕이 남은 가장 앞 세대, 다 이겼으면 가장 뒤 세대."""
      gens = list(gym_gens(st))
      return next((g for g in gens if any(f'gym:{g}-{i}' not in st.get('gym', {}) for i in range(8))
                   or str(g) not in st.get('league', {})), gens[-1] if gens else 1)
  ```
  `view == 'gyms'` 그리기와 `gym_sel`·`pin_gym` 처리에서 `gym_rows(st)` 대신 `gym_page(st, gym_g)`,
  체육관을 열 때 `gym_g = gym_start(st)`, ←→ 는 `gym_gens(st)` 안에서 돌린다. 머리줄은 `◀ N세대 ▶ 배지 n/8`.

## 2. 렉 걸릴 때 방향키가 쌓여 손을 떼도 계속 움직임
- `main()` 의 `key = getkey(scr, 2000)` 바로 뒤에:
  ```python
  if key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT, curses.KEY_PPAGE, curses.KEY_NPAGE):
      curses.flushinp()  # 느릴 때 쌓인 방향키를 버린다
  ```

## 3. 화면 개편 이어서 — 사용자와 하나씩 정하기
- 끝난 것: 메인(장식 12 · 동료 · 팀 3×2 · 오른쪽 버튼), 풀숲 만남(가운데 포켓몬 · 볼 고르기 · 던지기/도망 · 포획 확률), 가방(아이템 → 포켓몬).
- 남은 것: **[교환]**, **[훈장]**, **[체육관]**(1번과 함께). 도감은 사용자가 "일단 건드리지 말자"로 정함.
- 사용자 방식: 패널 그림(번호 붙인 상자)을 주면 그 비율대로 배치한다. 그림과 다르면 바로 지적하니 비율을 꼼꼼히 맞출 것.

## 4. 확인 못 한 것
- 만남 화면 그림 크기 보정 `SIXEL_SCALE = 1.6` 은 회사 PC(Windows Terminal + tmux) 스크린샷 한 장으로 잰 값.
  개인 PC(cmux, Kitty 그래픽)는 Kitty 경로라 보정 없이 칸 수 그대로 놓는다 — 그림이 너무 크거나 치우치면 `big_art` 를 본다.
- 합체 도구로 실제 합체까지 해 본 적 없음(시험으로만). 체육관 배틀 화면은 메인 개편 뒤 끝까지 눌러 보지 않음.
