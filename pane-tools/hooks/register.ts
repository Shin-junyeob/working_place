import type { EngineInterface, Register } from 'claude-code'

// /mods 하나로 들어가는 모드 허브 — bin/hub.py 가 세션의 컨텍스트·비용 게이지와 bin/ 의 도구 버튼(memo, tetris, pokemon …)을 띄운다.
// 어디에 띄울지는 사용자가 /config 에서 고른다(userConfig): tmux 패널 · 새 터미널 창 · 사용자 명령(cmux·wezterm·zellij …).
// 메모는 bin/memo.py 가 받는 세션의 수신함 pane-tools/inbox/<sessionId>.json 에 [{id, text}] 로 쌓고,
// 받는 세션의 이 mod 가 읽어 $.prompt.submit 으로 넣는다 — 작업 중이면 엔진이 한가해질 때까지 기다렸다 넣는다.
// 게이지는 각 세션의 이 mod 가 pane-tools/usage/<sessionId>.json 에 적어 둔 값을 허브가 읽는다.
// 글자는 pane-tools/settings.json 의 lang(허브의 [ 한/EN ] 버튼)을 따른다.
const SHELLS = new Set(['bash', 'sh', 'zsh'])
// 게임이 키우기 전 높이를 적어 두는 tmux 패널 옵션 — 게임이 도중에 갈아 끼워져도 다음 도구가 되돌린다
const HEIGHT_OPT = '@pt_h'
const TICK_MS = 2000

export type Msg = { id: number; text: string }

// 아직 안 넣은 메시지만, 오래된 순으로 — 기준은 마지막으로 넣은 id ($.fs 에 삭제가 없어 파일을 비우지 못한다)
export function pending(msgs: Msg[], last: number): Msg[] {
  return msgs.filter(m => m.id > last).sort((a, b) => a.id - b.id)
}

export function compose(msgs: Msg[]): string {
  return msgs.map(m => m.text.trim()).filter(Boolean).join('\n\n')
}

// 갈아 끼워도 되는 패널인가 — 빈 셸이거나, 이 mod 가 띄운 도구(mark = <플러그인>/bin/)일 때만. 사용자가 돌리는 python 작업은 죽이지 않는다
export function canReplace(current: string, startCommand: string, mark: string): boolean {
  return SHELLS.has(current) || startCommand.includes(mark)
}

export type Opts = { launcher: string; tmuxTarget: string; followPane: string; command: string }
export type Where = { tmux: boolean; wsl?: string; mac: boolean }

// 셸에 한 덩어리로 넘길 수 있게 작은따옴표로 감싼다
export const shq = (s: string) => `'${s.replace(/'/g, `'\\''`)}'`

// 허브를 어떻게 띄울지 — 실행할 argv 와, 정해진 tmux 패널을 갈아 끼우는 경우 그 패널(slot)
export function plan(o: Opts, cmd: string, w: Where): { argv: string[]; slot?: string } | { error: 'nocmd' } {
  const mode = o.launcher === 'tmux' || o.launcher === 'window' || o.launcher === 'command' ? o.launcher : w.tmux ? 'tmux' : 'window'
  if (mode === 'command') {
    if (!o.command.includes('{cmd}')) return { error: 'nocmd' }
    return { argv: ['bash', '-lc', o.command.split('{cmd}').join(shq(cmd))] }
  }
  if (mode === 'tmux') {
    if (o.tmuxTarget) return { argv: ['tmux', 'respawn-pane', '-k', '-t', o.tmuxTarget, `${cmd}; exec bash`], slot: o.tmuxTarget }
    return { argv: ['tmux', 'split-window', '-h', '-l', '45%', cmd] } // 허브를 닫으면 패널도 닫힌다
  }
  if (w.wsl) return { argv: ['wt.exe', '-w', 'new', 'wsl.exe', '-d', w.wsl, '-e', 'bash', '-lc', cmd] }
  if (w.mac) return { argv: ['osascript', '-e', `tell application "Terminal" to do script ${JSON.stringify(cmd)}`] }
  return { argv: ['x-terminal-emulator', '-e', 'bash', '-lc', cmd] }
}

const home = async ($: EngineInterface) => (await $.env.get('HOME')) ?? '/tmp'

// 한/영 — 허브의 [ 한/EN ] 버튼이 적는 설정을 읽는다
async function L($: EngineInterface, ko: string, en: string) {
  try {
    return JSON.parse(await $.fs.read(`${await home($)}/.claude/pane-tools/settings.json`)).lang === 'en' ? en : ko
  } catch {
    return ko
  }
}

let busy = false
async function deliver($: EngineInterface) {
  if (busy) return
  busy = true
  try {
    const sid = await $.session.id()
    const base = `${await home($)}/.claude/pane-tools/inbox/${sid}`
    if (!(await $.fs.exists(`${base}.json`))) return
    let msgs: Msg[]
    try {
      msgs = JSON.parse(await $.fs.read(`${base}.json`))
    } catch {
      return // 메모장이 쓰는 도중이면 다음 틱에
    }
    const key = `last:${sid}`
    const todo = pending(msgs, ((await $.store.get(key)) as number | undefined) ?? 0)
    const top = todo.at(-1)?.id
    if (top === undefined) return
    const last = ((await $.store.get(key)) as number | undefined) ?? 0
    // 기준을 먼저 올린다 — 다시 불러온 뒤 타이머가 겹쳐도 두 번 넣지 않게
    await $.store.set(key, top)
    const text = compose(todo)
    // 한가해져 실제로 들어간 뒤에야 확인 파일을 쓴다 — 메모장의 '✓ 전달했습니다' 가 거짓이 되지 않게
    const r = text ? await $.prompt.submit({ text, asUser: true }) : undefined
    if (r?.drop !== undefined) {
      await $.store.set(key, last) // 거절됐으면 되돌려 다음 틱에 다시 넣는다
      $.ui.toast(`${await L($, '메모를 넣지 못해 다시 시도합니다', 'Could not deliver the memo, retrying')}: ${r.drop}`)
      return
    }
    await $.fs.write(`${base}.ack`, String(top))
  } finally {
    busy = false
  }
}

// 설정대로 허브를 띄우고, 사용자에게 보일 한 줄을 돌려준다
async function openHub($: EngineInterface, o: Opts) {
  const root = $.plugin.root
  const mark = `${root}/bin/`
  let cmd = `python3 ${shq(`${root}/bin/hub.py`)} --session ${await $.session.id()}`
  if (o.followPane) cmd += ` --follow-pane ${shq(o.followPane)}`
  const where: Where = {
    tmux: (await $.process.run(['tmux', 'has-session']).catch(() => ({ exitCode: 1 }))).exitCode === 0,
    wsl: await $.env.get('WSL_DISTRO_NAME'),
    mac: (await $.process.run(['uname', '-s']).catch(() => ({ stdout: '' }))).stdout.trim() === 'Darwin',
  }
  const p = plan(o, cmd, where)
  if ('error' in p) return L($, '사용자 명령에 {cmd} 자리가 없습니다 — /config 의 pane-tools command 를 확인해 주세요',
    'The custom command has no {cmd} placeholder — check pane-tools "command" in /config')
  if (p.slot) {
    const info = await $.process.run(['tmux', 'display', '-p', '-t', p.slot, '#{pane_current_command}\t#{pane_start_command}'])
    // 물어보는 것 자체가 실패하면 패널이 바쁜 게 아니라 tmux 에 못 닿은 것 — 소켓 파일이 지워지면 이렇다(2026-10-21 실제로 겪음)
    if (info.exitCode !== 0) return L($, `tmux 패널 ${p.slot} 에 연결할 수 없습니다: ${info.stderr.trim()} — 패널 이름을 확인하거나, 소켓이 사라졌다면 셸에서 pkill -USR1 -o -x tmux 로 되살리세요.`,
      `Cannot reach tmux pane ${p.slot}: ${info.stderr.trim()} — check the pane name, or if the socket vanished run pkill -USR1 -o -x tmux.`)
    const [cur = '', start = ''] = info.stdout.trim().split('\t')
    if (!canReplace(cur, start, mark)) return L($, `패널 ${p.slot} 에서 ${cur || '다른 프로그램'}이 돌고 있어 열지 않았습니다. 끝낸 뒤 다시 입력해 주세요.`,
      `Pane ${p.slot} is running ${cur || 'another program'}, so the hub was not opened. Try again when it finishes.`)
    const h = (await $.process.run(['tmux', 'show', '-pv', '-t', p.slot, HEIGHT_OPT])).stdout.trim()
    if (h) {
      await $.process.run(['tmux', 'resize-pane', '-t', p.slot, '-y', h])
      await $.process.run(['tmux', 'set', '-pu', '-t', p.slot, HEIGHT_OPT])
    }
  }
  const r = await $.process.run(p.argv).catch((e: unknown) => ({ exitCode: 1, stderr: String(e) }))
  return r.exitCode === 0 ? L($, '모드 허브를 띄웠습니다.', 'Opened the mods hub.')
    : `${await L($, '모드 허브를 열지 못했습니다', 'Could not open the mods hub')} (${p.argv[0]}): ${r.stderr.trim()}`
}

// 허브 게이지용 — 컨텍스트·비용·사용 한도를 2초마다, 바뀌었을 때만 적는다.
// gained: 컨텍스트 토큰이 늘어난 만큼의 누적(압축으로 줄면 무시하고 다시 늘면 또 센다) — pokemon 모드의 경험치.
// 다시 불러와도 이어지게 $.store 에 두고, 불러온 직후 첫 값은 기준으로만 삼는다(두 번 세지 않게).
let lastUsage = ''
let lastTokens: number | undefined
let gained: number | undefined
export function grow(prev: number | undefined, now: number | undefined): number {
  return prev !== undefined && now !== undefined && now > prev ? now - prev : 0
}
async function writeUsage($: EngineInterface) {
  const u = await $.session.usage()
  const sid = await $.session.id()
  gained ??= ((await $.store.get(`gain:${sid}`)) as number | undefined) ?? 0
  const add = grow(lastTokens, u.context.tokens)
  lastTokens = u.context.tokens ?? lastTokens
  if (add) {
    gained += add
    await $.store.set(`gain:${sid}`, gained)
  }
  const text = JSON.stringify({ context: u.context, cost: u.cost?.usd ?? null, rateLimits: u.rateLimits, gained })
  if (text === lastUsage) return
  lastUsage = text
  await $.fs.write(`${await home($)}/.claude/pane-tools/usage/${sid}.json`, text)
}

export const register: Register = (on, options) => {
  const o: Opts = {
    launcher: String(options.launcher ?? 'auto'),
    tmuxTarget: String(options.tmuxTarget ?? ''),
    followPane: String(options.followPane ?? ''),
    command: String(options.command ?? ''),
  }
  on('session.start', async ($, e, next) => {
    // immediate: 작업 중에도 기다리지 않고 바로 연다 (/reload-plugins 처럼)
    await $.command.register({ name: 'mods', description: '모드 허브 열기 · Open the mods hub (gauges, memo, games)', immediate: true })
    $.clock.every(TICK_MS, () => {
      void deliver($)
      void writeUsage($).catch(() => undefined)
    })
    return next(e)
  })

  on('command.run', { command: 'mods' }, async $ => ({ text: await openHub($, o) }))
}
