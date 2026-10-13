import { useEffect, useReducer, useState } from 'react'
import type { TrajectoryRun } from '@nano/product-contracts'
import { verifiedRun } from './navigation-model.ts'

/** Session-scoped, read-only host operations; no transport or execution controls enter the UI. */
export interface TrajectoryNavigation {
  initialRunId?: string
  parentSessionId?: string
  readRuns(signal: AbortSignal): Promise<readonly TrajectoryRun[]>
  firstSeq(): number | undefined
  hasMore(): boolean
  lastSeq(): number | undefined
  loadThrough(seq: number): Promise<unknown>
  isActive(): boolean
  navigate(run: TrajectoryRun): void
}

/** Load the whole session before applying a run selection, including after a resync. */
export function useRunNavigation(navigation: TrajectoryNavigation | undefined, sessionId: string, historyOpen: boolean) {
  const [runs,setRuns] = useState<readonly TrajectoryRun[]>([])
  const [metadataReady,setMetadataReady] = useState(!navigation)
  const [error,setError] = useState('')
  const [loading,setLoading] = useState(false)
  const [loadError,setLoadError] = useState('')
  const [retryCount,retry] = useReducer(value=>value+1,0)
  const run = verifiedRun(runs,sessionId,navigation?.initialRunId,navigation?.parentSessionId)
  useEffect(()=>{
    if (!navigation) return
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout>
    const update = async () => {
      if (navigation.isActive()) {
        try { const value=await navigation.readRuns(controller.signal); if (!controller.signal.aborted) {setRuns(value);setMetadataReady(true);setError('')} }
        catch(error) {if(!controller.signal.aborted)setError(error instanceof Error?error.message:String(error))}
      }
      if(!controller.signal.aborted)timer=setTimeout(update,2000)
    }
    void update()
    return ()=>{controller.abort();clearTimeout(timer)}
  },[navigation])
  const missingHistory = Boolean(navigation?.initialRunId && navigation.hasMore())
  useEffect(()=>{
    if (!navigation || !missingHistory) {setLoading(false);setLoadError('');return}
    if (!historyOpen) {setLoading(false);return}
    let gone=false;setLoading(true);setLoadError('')
    // Session paging may resolve on a soft failure: coverage, not resolution, is success.
    void navigation.loadThrough(0).then(()=>{
      if(!gone&&navigation.hasMore())setLoadError('尚未完整加载会话历史，请重试读取。')
    }).catch(error=>{if(!gone)setLoadError(error instanceof Error?error.message:String(error))}).finally(()=>{if(!gone)setLoading(false)})
    return()=>{gone=true}
  },[navigation,missingHistory,historyOpen,retryCount])
  return {runs,run,metadataReady,error,loading,loadError,retry,missingHistory,
    blocked:Boolean(navigation?.initialRunId&&!metadataReady)||missingHistory}
}
