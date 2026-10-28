import { expect, mock, test } from 'claude-code/testing'
import type { TestBody } from 'claude-code/testing'
import { canReplace, fromPhone, grow, pending, plan, shq } from './register'

const INBOX = '/h/.claude/pane-tools/inbox/S1'

// 파일·저장소·프롬프트를 메모리로 답하고, 넣은 프롬프트를 기록한다
function harness(on: Parameters<TestBody>[1], files: Record<string, string>, drops: string[] = []) {
  const clock = mock.clock(on)
  const store: Record<string, unknown> = {}
  const submitted: string[] = []
  on('env.get', () => ({ value: '/h' }))
  on('session.id', () => ({ value: 'S1' }))
  on('fs.exists', ($, e) => ({ value: e.path in files }))
  on('fs.read', ($, e) => ({ value: files[e.path] ?? '' }))
  const written: string[] = []
  on('fs.write', ($, e) => ((files[e.path] = e.text), written.push(e.path), { value: undefined }))
  on('store.get', ($, e) => ({ value: store[e.key] }))
  on('store.set', ($, e) => ((store[e.key] = e.value), { value: undefined }))
  // drops 에 든 이유를 하나씩 꺼내 거절하고, 다 쓰면 받아들인다
  on('prompt.submit', ($, e) => {
    const drop = drops.shift()
    if (drop !== undefined) return { drop }
    submitted.push(e.text)
    return { text: e.text }
  })
  on('ui.toast', () => ({ value: undefined }) as never)
  on('command.register', () => ({ value: undefined }) as never)
  on('session.start', ($, e) => ({ cwd: e.cwd }) as never)
  // 세션 시작이 2초 타이머를 건다 — tick() 한 번이 수신함 한 번 훑기
  const tick = () => clock.advance(2000)
  return { submitted, files, clock, tick, written }
}

test('넣은 것 다음부터만 고른다', async () => {
  const msgs = [{ id: 3, text: 'c' }, { id: 1, text: 'a' }, { id: 2, text: 'b' }]
  expect(pending(msgs, 1).map(m => m.text)).toEqual(['b', 'c'])
})

test('쌓인 메모를 한 번에 묶어 한 번만 넣고, 다시 훑어도 또 넣지 않는다', async ($, on) => {
  const { submitted, files, tick } = harness(on, {
    [`${INBOX}.json`]: JSON.stringify([{ id: 1, text: '첫 메모' }, { id: 2, text: '둘째 메모' }]),
  })
  await $.session.start({ cwd: '/w', surface: 'terminal', isInteractive: true } as never)
  await tick()
  await tick()
  expect(submitted).toEqual(['첫 메모\n\n둘째 메모'])
  expect(files[`${INBOX}.ack`]).toBe('2')

  files[`${INBOX}.json`] = JSON.stringify([{ id: 1, text: '첫 메모' }, { id: 2, text: '둘째 메모' }, { id: 3, text: '셋째' }])
  await tick()
  expect(submitted).toEqual(['첫 메모\n\n둘째 메모', '셋째'])
})

test('수신함이 없거나 쓰는 도중(깨진 JSON)이면 아무것도 넣지 않는다', async ($, on) => {
  const { submitted, files, tick } = harness(on, {})
  await $.session.start({ cwd: '/w', surface: 'terminal', isInteractive: true } as never)
  await tick()
  files[`${INBOX}.json`] = '[{"id":1,"te'
  await tick()
  expect(submitted).toEqual([])
  expect(files[`${INBOX}.ack`]).toBeUndefined()
})

test('넣기가 거절되면 확인 파일을 쓰지 않고 다음 틱에 다시 넣는다', async ($, on) => {
  const { submitted, files, tick } = harness(on, { [`${INBOX}.json`]: JSON.stringify([{ id: 5, text: '다시' }]) }, ['대화상자 열림'])
  await $.session.start({ cwd: '/w', surface: 'terminal', isInteractive: true } as never)
  await tick()
  expect(submitted).toEqual([])
  expect(files[`${INBOX}.ack`]).toBeUndefined()
  await tick()
  expect(submitted).toEqual(['다시'])
  expect(files[`${INBOX}.ack`]).toBe('5')
})

test('빈 셸이나 이 mod 가 띄운 도구만 갈아 끼운다', async () => {
  const mark = '/p/pane-tools/0.5.0/bin/'
  expect(canReplace('bash', 'bash', mark)).toBe(true)
  expect(canReplace('python3', `python3 '${mark}hub.py'; exec bash`, mark)).toBe(true)
  expect(canReplace('python3', '', mark)).toBe(false) // 사용자가 셸에서 돌린 python 작업
  expect(canReplace('vim', '', mark)).toBe(false)
})

test('띄울 곳: auto 는 tmux 가 있으면 창을 나누고, 없으면 새 터미널 창 · tmux 패널 지정 · 사용자 명령', async () => {
  const base = { launcher: 'auto', tmuxTarget: '', followPane: '', command: '' }
  const cmd = "python3 '/p/bin/hub.py' --session S1"
  const none = { tmux: false, mac: false }
  expect(plan(base, cmd, { tmux: true, mac: false })).toEqual({ argv: ['tmux', 'split-window', '-h', '-l', '45%', cmd] })
  expect(plan(base, cmd, { ...none, wsl: 'Ubuntu' })).toEqual({ argv: ['wt.exe', '-w', 'new', 'wsl.exe', '-d', 'Ubuntu', '-e', 'bash', '-lc', cmd] })
  expect((plan(base, cmd, { tmux: false, mac: true }) as { argv: string[] }).argv[0]).toBe('osascript')
  expect(plan(base, cmd, none)).toEqual({ argv: ['x-terminal-emulator', '-e', 'bash', '-lc', cmd] })
  expect(plan({ ...base, launcher: 'tmux', tmuxTarget: 'dev:0.3' }, cmd, none))
    .toEqual({ argv: ['tmux', 'respawn-pane', '-k', '-t', 'dev:0.3', `${cmd}; exec bash`], slot: 'dev:0.3' })
  expect(plan({ ...base, launcher: 'command', command: 'wezterm cli split-pane -- bash -lc {cmd}' }, cmd, none))
    .toEqual({ argv: ['bash', '-lc', `wezterm cli split-pane -- bash -lc ${shq(cmd)}`] })
  expect(plan({ ...base, launcher: 'command', command: 'cmux split' }, cmd, none)).toEqual({ error: 'nocmd' })
  expect(shq("it's")).toBe(`'it'\\''s'`)
})

test('/mods 는 지정한 tmux 패널에서 사용자 작업이 돌고 있으면 갈아 끼우지 않는다',
  { options: { launcher: 'tmux', tmuxTarget: 'dev:0.3' } }, async ($, on) => {
  const runs: string[][] = []
  on('env.get', ($, e) => ({ value: e.name === 'HOME' ? '/h' : undefined }) as never)
  on('session.id', () => ({ value: 'S1' }))
  on('fs.read', () => { throw new Error('없음') }) // 언어 설정 파일 없음 → 한국어
  on('process.run', ($, e) => {
    runs.push([...e.argv])
    return { value: { exitCode: 0, stdout: e.argv[1] === 'display' ? 'python3\t\n' : '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } } as never
  })
  const r = await $.command.run({ command: 'mods', args: '' } as never)
  expect(JSON.stringify(r)).toContain('열지 않았습니다')
  expect(runs.some(a => a.includes('respawn-pane'))).toBe(false)
})

test('허브 게이지용으로 컨텍스트·비용을 적고, 바뀌지 않으면 다시 쓰지 않는다', async ($, on) => {
  const { files, tick, written } = harness(on, {})
  on('session.usage', () => ({ value: { startedAt: 0, context: { tokens: 84000, window: 200000, percent: 42 }, rateLimits: [], cost: { usd: 1.5 } } }) as never)
  await $.session.start({ cwd: '/w', surface: 'terminal', isInteractive: true } as never)
  await tick()
  await tick()
  const u = JSON.parse(files['/h/.claude/pane-tools/usage/S1.json'] ?? '{}')
  expect(u.context.percent).toBe(42)
  expect(u.cost).toBe(1.5)
  expect(written.filter(p => p.includes('/usage/')).length).toBe(1)
})

test('pokemon 경험치: 컨텍스트가 늘어난 만큼만 쌓고, 줄어든 건(압축) 빼지 않는다', async ($, on) => {
  expect(grow(undefined, 5000)).toBe(0) // 불러온 직후 첫 값은 기준만
  expect(grow(5000, 8000)).toBe(3000)
  expect(grow(8000, 2000)).toBe(0)
  const { files, tick } = harness(on, {})
  const seq = [10000, 14000, 3000, 5000]
  on('session.usage', () => ({ value: { startedAt: 0, context: { tokens: seq.shift() ?? 5000, window: 200000 }, rateLimits: [] } }) as never)
  await $.session.start({ cwd: '/w', surface: 'terminal', isInteractive: true } as never)
  for (let i = 0; i < 4; i++) await tick()
  expect(JSON.parse(files['/h/.claude/pane-tools/usage/S1.json'] ?? '{}').gained).toBe(4000 + 2000)
})

test('/mods 는 tmux 에 닿지 못하면 "다른 프로그램" 이 아니라 연결 문제라고 알린다',
  { options: { launcher: 'tmux', tmuxTarget: 'dev:0.3' } }, async ($, on) => {
  on('env.get', ($, e) => ({ value: e.name === 'HOME' ? '/h' : undefined }) as never)
  on('session.id', () => ({ value: 'S1' }))
  on('fs.read', () => { throw new Error('없음') })
  on('process.run', ($, e) => ({ value: e.argv[1] === 'display'
    ? { exitCode: 1, stdout: '', stderr: 'error connecting to /tmp/tmux-1000/default', isStdoutTruncated: false, isStderrTruncated: false }
    : { exitCode: 0, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }) as never)
  const r = JSON.stringify(await $.command.run({ command: 'mods', args: '' } as never))
  expect(r).toContain('연결할 수 없습니다')
  expect(r).toContain('pkill -USR1')
})

test('허브 [ 설정 ] 에서 고른 띄울 곳이 /config 값보다 먼저 쓰인다',
  { options: { launcher: 'tmux', tmuxTarget: 'dev:0.3' } }, async ($, on) => {
  const runs: string[][] = []
  on('env.get', ($, e) => ({ value: e.name === 'HOME' ? '/h' : undefined }) as never)
  on('session.id', () => ({ value: 'S1' }))
  on('fs.read', () => ({ value: JSON.stringify({ lang: 'ko', launcher: 'tmux', tmuxTarget: '' }) }))
  on('process.run', ($, e) => (runs.push([...e.argv]),
    { value: { exitCode: 0, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }) as never)
  expect(JSON.stringify(await $.command.run({ command: 'mods', args: '' } as never))).toContain('띄웠습니다')
  expect(runs.some(a => a[1] === 'split-window')).toBe(true) // 지정 패널(dev:0.3) 대신 지금 창을 나눴다
  expect(runs.some(a => a.includes('respawn-pane'))).toBe(false)
})

test('/mods 는 피드 패널이 빈 셸이면 피드도 띄우고, 이미 피드가 돌면 그대로 둔다',
  { options: { launcher: 'tmux', tmuxTarget: 'dev:0.3', feedTarget: 'dev:0.2' } }, async ($, on) => {
  const runs: string[][] = []
  let feedPane = '-bash'  // 피드 패널 tty 에서 도는 것
  on('env.get', ($, e) => ({ value: e.name === 'HOME' ? '/h' : undefined }) as never)
  on('session.id', () => ({ value: 'S1' }))
  on('fs.read', () => { throw new Error('없음') })
  on('process.run', ($, e) => {
    runs.push([...e.argv])
    const out = e.argv[1] === 'display' ? (e.argv.includes('dev:0.2') ? 'bash\t/dev/pts/9' : 'bash\t')
      : e.argv[0] === 'ps' ? feedPane : ''
    return { value: { exitCode: 0, stdout: out + '\n', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } } as never
  })
  expect(JSON.stringify(await $.command.run({ command: 'mods', args: '' } as never))).toContain('피드도 dev:0.2')
  expect(runs.some(a => a.includes('respawn-pane') && a.includes('dev:0.2') && a.at(-1)!.includes('feed.py'))).toBe(true)
  runs.length = 0
  feedPane = "bash -c python3 '/p/bin/feed.py'; exec bash\npython3 /p/bin/feed.py"
  expect(JSON.stringify(await $.command.run({ command: 'mods', args: '' } as never))).not.toContain('피드도')
  expect(runs.some(a => a.includes('respawn-pane') && a.includes('dev:0.2'))).toBe(false)
})

test('휴대폰(bridge + mobile)에서 입력한 /mods 만 엔진 패널로 — 웹·터미널은 그대로', async () => {
  expect(fromPhone('bridge', ['terminal', 'mobile'])).toBe(true)
  expect(fromPhone('bridge', ['terminal'])).toBe(false) // 웹(claude.ai/code)
  expect(fromPhone('composer', ['terminal', 'mobile'])).toBe(false) // 맥에서 직접
})
