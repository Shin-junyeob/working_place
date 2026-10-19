import { expect, mock, test } from 'claude-code/testing'
import type { TestBody } from 'claude-code/testing'
import { commandKey, fmt, parseEstimate } from './register'

const MIN = 60_000
const last = <T>(xs: T[]) => xs[xs.length - 1]

// 엔진 자리에서 Bash 를 ms 만큼 걸리게 하고, 플러그인이 띄우는 토스트·상태줄을 기록한다
function harness(on: Parameters<TestBody>[1], ms: number, stored: Record<string, unknown> = {}) {
  const clock = mock.clock(on)
  // 저장소는 테스트가 메모리로 직접 답한다 — 무엇이 기록됐는지(sets) 그대로 보기 위해
  const sets: Record<string, unknown> = {}
  on('store.get', ($, e) => ({ value: e.key in sets ? sets[e.key] : stored[e.key] }))
  on('store.set', ($, e) => ((sets[e.key] = e.value), { value: undefined }))
  const toasts: string[] = []
  const statuses: (string | undefined)[] = []
  on('ui.toast', ($, e) => (toasts.push(e.text), { value: undefined }))
  on('ui.status', ($, e) => (statuses.push(e.text), { value: undefined }))
  on('tool.call', { tool: 'Bash' }, async ($, e) => {
    if (!e.run_in_background) await clock.sleep(ms)
    return { result: { stdout: 'ok', stderr: '', interrupted: false } as never }
  })
  return { clock, toasts, statuses, sets }
}

test('설명 속 예상 시간을 읽는다', async () => {
  expect(parseEstimate('1~8 단계 빌드 차례로 (30~60 분)')).toBe(60 * MIN)
  expect(parseEstimate('통합 시험 다시 돌리기 (약 1 시간)')).toBe(60 * MIN)
  expect(parseEstimate('2 단계 시험 실행')).toBeUndefined()
  expect(commandKey('cd /a/b && timeout 240 node x.js --n 3')).toBe('node x.js --n #')
  expect([fmt(90_000), fmt(90_000, true), fmt(30_000, true), fmt(undefined, true)]).toEqual(['2분', '2 min', '30s', 'unknown'])
})

test('지난 기록으로 예상을 잡아 시작부터 보이고, 예상 안에 끝나면 경고 없이 끝남만 알린다', async ($, on) => {
  const cmd = 'pytest -q tests'
  const { clock, toasts, statuses, sets } = harness(on, 7 * MIN, { ['dur:' + commandKey(cmd)]: [10 * MIN] })
  const call = $.tool.call({ tool: 'Bash', command: cmd, description: '전체 시험' })
  await clock.settle()
  expect(last(statuses)).toBe('⏳ 전체 시험 · 0초 / 예상 10분')
  await clock.advance(7 * MIN)
  await call
  expect(toasts).toEqual(['✔ 끝남(7분): 전체 시험'])
  expect(last(statuses)).toBeUndefined()
  expect(sets['dur:' + commandKey(cmd)]).toEqual([10 * MIN, 7 * MIN])
})

test('예상을 크게 넘기면 한 번 경고한다', async ($, on) => {
  const { clock, toasts } = harness(on, 6 * MIN)
  const call = $.tool.call({ tool: 'Bash', command: 'make slow', description: '느린 빌드 (약 2 분)' })
  await clock.advance(3 * MIN + 30_000)
  expect(toasts).toEqual([])
  await clock.advance(1 * MIN) // 4분 30초 — 기준 max(3, 4)=4분 넘음
  expect(toasts).toEqual(['⚠ 예상보다 오래 걸림: 느린 빌드 (약 2 분) (4분째, 예상 2분)'])
  await clock.advance(2 * MIN)
  await call
  expect(last(toasts)).toBe('✔ 끝남(6분): 느린 빌드 (약 2 분)')
})

test('30초 안에 끝나는 명령은 아무것도 띄우지 않고 기록도 안 한다', async ($, on) => {
  const { clock, toasts, statuses, sets } = harness(on, 10_000)
  const call = $.tool.call({ tool: 'Bash', command: 'ls' })
  await clock.advance(MIN)
  await call
  expect(toasts).toEqual([])
  expect(statuses).toEqual([])
  expect(sets).toEqual({})
})

test('백그라운드는 시작을 알리고, 예상 시간이 지나면 확인하라고 알린다', async ($, on) => {
  const { clock, toasts } = harness(on, 0)
  await $.tool.call({ tool: 'Bash', command: 'run-all', description: '전체 시험 (약 30 분)', run_in_background: true })
  expect(toasts).toEqual(['▶ 백그라운드 시작: 전체 시험 (약 30 분) (예상 30분)'])
  await clock.advance(29 * MIN)
  expect(toasts.length).toBe(1)
  await clock.advance(1 * MIN)
  expect(last(toasts)).toBe('⏰ 전체 시험 (약 30 분): 예상 30분 지남 — 끝났는지 확인하세요')
})
