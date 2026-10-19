import type { EngineInterface, Register } from 'claude-code'

// 작업마다 예상 소요 시간을 잡아 상태줄에 보이고, 예상을 넘기면 알린다
// (전역 규칙: 오래 걸리는 작업은 예상 시간을 말하고, 넘기면 직접 확인한다).
// 예상 = 같은 명령의 지난 실행 시간(최근 5회 중앙값, 세션을 넘어 $.store) > 설명 속 "(약 30 분)" > 모름.
// 백그라운드 명령은 끝나는 때를 알 수 없어, 예상 시간이 지나면 확인하라고만 알린다.
const SEC = 1000
const MIN = 60 * SEC
const QUIET = 30 * SEC // 이보다 빨리 끝나는 명령엔 아무것도 띄우지 않고 기록도 안 한다
const NO_EST_WARN = 10 * MIN // 예상을 모를 때의 경고 기준

// "(30~60 분)" → 60분, "(약 1 시간)" → 60분, "2 단계 시험" → 없음(단위가 바로 붙은 숫자만 본다)
export function parseEstimate(text: string): number | undefined {
  const m = /(\d+(?:\.\d+)?)(?:\s*~\s*(\d+(?:\.\d+)?))?\s*(분|시간|min|hours?|h)(?![a-z])/i.exec(text)
  if (!m) return undefined
  const n = Number(m[2] ?? m[1])
  return Math.round(n * (/^(분|min)$/i.test(m[3]!) ? MIN : 60 * MIN))
}

// shortcut: 숫자만 지우고 앞부분 80자로 같은 명령을 묶는다 — 인자만 다른 다른 작업이 섞이면 키를 더 정교하게
export function commandKey(command: string): string {
  const core = command.replace(/^(\s*cd\s+\S+\s*&&\s*)+/, '').replace(/^timeout\s+\d+\s+/, '')
  return core.replace(/\d+/g, '#').replace(/\s+/g, ' ').trim().slice(0, 80)
}

export function fmt(ms: number | undefined, en = false): string {
  if (ms === undefined) return en ? 'unknown' : '모름'
  if (ms < MIN) return `${Math.round(ms / SEC)}${en ? 's' : '초'}`
  if (ms < 60 * MIN) return `${Math.round(ms / MIN)}${en ? ' min' : '분'}`
  return `${Math.floor(ms / (60 * MIN))}${en ? 'h ' : '시간 '}${Math.round((ms % (60 * MIN)) / MIN)}${en ? ' min' : '분'}`
}

// 한/영 — pane-tools 허브의 [ 한/EN ] 버튼이 적는 ~/.claude/pane-tools/settings.json 을 따른다. 없으면 한국어
async function english($: EngineInterface) {
  try {
    return JSON.parse(await $.fs.read(`${(await $.env.get('HOME')) ?? ''}/.claude/pane-tools/settings.json`)).lang === 'en'
  } catch {
    return false
  }
}

const median = (xs: number[]) => (xs.length ? [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)] : undefined)

export const register: Register = on => {
  on('tool.call', async ($, e, next) => {
    const isBash = e.tool === 'Bash'
    const label = isBash ? (e.description || e.command).slice(0, 40) : e.tool
    const key = 'dur:' + (isBash ? commandKey(e.command) : e.tool)
    const past = ((await $.store.get(key)) as number[] | undefined) ?? []
    const est = median(past) ?? (isBash && e.description ? parseEstimate(e.description) : undefined)
    const en = await english($)
    const f = (ms: number | undefined) => fmt(ms, en)

    if (isBash && e.run_in_background) {
      const wait = est ?? NO_EST_WARN
      $.ui.toast(en ? `▶ Started in background: ${label} (est. ${f(est)})` : `▶ 백그라운드 시작: ${label} (예상 ${f(est)})`)
      $.clock.after(wait, () => $.ui.toast(en ? `⏰ ${label}: past the ${f(wait)} estimate — check whether it finished`
        : `⏰ ${label}: 예상 ${f(wait)} 지남 — 끝났는지 확인하세요`))
      return next(e)
    }

    const t0 = await $.clock.now()
    const limit = est ? Math.max(est * 1.5, est + 2 * MIN) : NO_EST_WARN
    let shown = false
    let warned = false
    let ticker: { cancel: () => void } | undefined
    const tick = async () => {
      const elapsed = (await $.clock.now()) - t0
      shown = true
      $.ui.status(`⏳ ${label} · ${f(elapsed)} / ${en ? 'est.' : '예상'} ${f(est)}`)
      if (!warned && elapsed >= limit) {
        warned = true
        $.ui.toast(en ? `⚠ Taking longer than expected: ${label} (${f(elapsed)}, est. ${f(est)})`
          : `⚠ 예상보다 오래 걸림: ${label} (${f(elapsed)}째, 예상 ${f(est)})`)
      }
    }
    const start = () => {
      void tick()
      ticker = $.clock.every(QUIET, () => void tick())
    }
    // 오래 걸릴 걸 아는 명령은 시작하자마자, 모르는 명령은 30초가 지나야 보인다
    const first = est !== undefined && est >= MIN ? (start(), undefined) : $.clock.after(QUIET, start)

    try {
      return await next(e)
    } finally {
      first?.cancel()
      ticker?.cancel()
      const elapsed = (await $.clock.now()) - t0
      if (shown) {
        $.ui.status(undefined)
        if (elapsed >= MIN) $.ui.toast(en ? `✔ Done (${f(elapsed)}): ${label}` : `✔ 끝남(${f(elapsed)}): ${label}`)
      }
      if (elapsed >= QUIET) await $.store.set(key, [...past, elapsed].slice(-5))
    }
  })
}
