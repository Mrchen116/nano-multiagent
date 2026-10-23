/** Execution facts enrich the native projection without mutating its shared target. */
import type { TrajectoryRun } from '@nano/product-contracts'
import type { TrajectorySnapshot } from './trajectory-contract.ts'
import type { TrajectoryTurnModel } from './layout.ts'
import type { TrajectoryCellProps } from './trajectory-record.ts'
import { deriveTrajectoryTimeline, type TrajectoryTimelineMode } from './timeline.ts'

export const stateText: Record<TrajectoryRun['state'], string> = {
  running: '运行中', completed: '已完成', failed: '失败', cancelled: '已取消', unknown: '结束未知',
}

/** Resolve identity only from facts reread through this frame's fixed observer. */
export function verifiedRun(runs: readonly TrajectoryRun[], sessionId: string, runId?: string, parentSessionId?: string) {
  return runs.find(run => run.runId === runId && run.sessionId === sessionId && (!parentSessionId || run.parentSessionId === parentSessionId))
}

/** Use producer-owned purpose rather than guessing from internal identifiers. */
export function runTitle(run: TrajectoryRun): string {
  return run.kind === 'combined' ? '记忆与技能复盘' : run.kind === 'memory' ? '记忆整理' : run.kind === 'skills' ? '技能复盘' : run.label || '子 Agent 执行'
}

/** Test inclusive native event coordinates; unknown coordinates cannot prove membership. */
export function inRun(seq: number | undefined, run: TrajectoryRun): boolean {
  return seq !== undefined && run.startSeq !== undefined && seq >= run.startSeq && (run.endSeq === undefined || seq <= run.endSeq)
}

/** Supply absent native tool/stream coordinates from their recorded request or owner. */
export function coordinateLayout(turns: readonly TrajectoryTurnModel[], snapshot: TrajectorySnapshot): TrajectoryTurnModel[] {
  const calls = new Map<string, number>()
  const collect = (call: {callId: string; subCalls?: readonly import('@deepseek-ai/dsh-client-ui-conversation/client').ToolCallBlock[]}, seq: number) => {
    calls.set(call.callId, seq)
    for (const child of call.subCalls ?? []) collect(child, seq)
  }
  for (const node of snapshot.eventNodes) {
    if (node.kind === 'assistant') for (const block of node.blocks) if (block.kind === 'tool-call') collect(block, node.seq)
    if (node.kind === 'tool-result') collect(node, calls.get(node.callId) ?? node.seq)
  }
  for (const call of snapshot.runningCalls) {
    const request = snapshot.requests.find(item => item.purpose === 'assistant' && item.turn === call.turn && item.step === call.step)
    if (request) collect(call, request.startSeq)
  }
  return turns.map(turn => ({...turn, groups: turn.groups.map(group => ({...group, cells: group.cells.map(cell => {
    if (cell.sourceSeq !== undefined && cell.sourceSeq !== Number.MAX_SAFE_INTEGER) return cell
    let seq = cell.callId ? calls.get(cell.callId) : undefined
    if (cell.recordId?.startsWith('assistant\u0000')) {
      const [, turn, step] = cell.recordId.split('\u0000')
      seq = snapshot.requests.find(request => request.purpose === 'assistant' && request.turn === Number(turn) && request.step === Number(step))?.startSeq
    }
    return {...cell, sourceSeq: seq}
  })}))}))
}

/** Decorate actual tool records, inserting unmatched launches into the same native ledger. */
export function withLaunches(turns: readonly TrajectoryTurnModel[], runs: readonly TrajectoryRun[], sessionId: string, firstSeq: number | undefined): TrajectoryTurnModel[] {
  const result = turns.map(turn => ({...turn, groups: turn.groups.map(group => ({...group, cells: [...group.cells]}))}))
  for (const run of runs.filter(run => run.parentSessionId === sessionId)) {
    const groups = result.flatMap(turn => turn.groups)
    const owner = run.callId ? groups.find(group => group.cells.some(cell => cell.callId === run.callId)) : undefined
    if (owner) {
      owner.cells = owner.cells.map(cell => cell.callId === run.callId ? {...cell, launchRuns: [...(cell.launchRuns ?? []), run]} : cell)
      continue
    }
    if (run.launchSeq !== undefined && (firstSeq === undefined || run.launchSeq < firstSeq)) continue
    const cell: TrajectoryCellProps = {index:0, recordId:`run:${run.runId}`, kind:'context', sourceSeq:run.launchSeq,
      text:runTitle(run), timeSeconds:null, startedAt:run.startedAt, launchRuns:[run],
      inputDetail:JSON.stringify(run,null,2), messageSource:{type:'nano-run',runId:run.runId}}
    let group = groups.find(group => group.cells.some(item => item.sourceSeq !== undefined && item.sourceSeq >= (run.launchSeq ?? Infinity)))
    if (!group) group = groups.at(-1)
    if (!group) { group = {title:'发起',cells:[]}; result.push({turn:null,groups:[group]}) }
    const index = group.cells.findIndex(item => item.sourceSeq !== undefined && item.sourceSeq >= (run.launchSeq ?? Infinity))
    group.cells.splice(index < 0 ? group.cells.length : index, 0, cell)
  }
  let index = 0
  return result.map(turn => ({...turn,groups:turn.groups.map(group=>({...group,cells:group.cells.map(cell=>({...cell,index:++index}))}))}))
}

/** Derive native-domain bounds while retaining exact seq membership at shared edges. */
export function executionFocus(turns: readonly TrajectoryTurnModel[], run: TrajectoryRun | undefined, mode: TrajectoryTimelineMode) {
  if (!run || run.startSeq === undefined) return {indexes:null, range:null}
  const indexes = new Set(turns.flatMap(turn=>turn.groups.flatMap(group=>group.cells.filter(cell=>inRun(cell.sourceSeq,run)).map(cell=>cell.index))))
  const spans = deriveTrajectoryTimeline(turns,mode)?.spans.filter(span=>indexes.has(span.index)) ?? []
  return {indexes,range:spans.length ? {start:Math.min(...spans.map(span=>span.start)),end:Math.max(...spans.map(span=>span.end))} : null}
}
