import { useEffect, useRef, useState } from 'react';
import { authFetch } from '../../auth/auth-fetch';
import { withBase } from '../../auth/auth-api';
import { useAuthStore } from '../../auth/auth-store';
import { tr } from './agent-work-text';

/** The parent owns IM credentials; the opaque iframe receives only its fixed read channel. */
export function AgentTrajectory({ agentId, sessionId, positions, onBack }: { agentId: string; sessionId: string | null; positions: Record<string, { top: number; firstSeq?: number; rowKey?: string; detailTab?: string }>; onBack(): void }) {
  const frame = useRef<HTMLIFrameElement>(null);
  const revision = useAuthStore(state => state.revision);
  const userId = useAuthStore(state => state.user?.id);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState('loading');
  const [message, setMessage] = useState('正在连接节点并读取原生轨迹…');
  const [clear, setClear] = useState(false);
  useEffect(() => {
    if (!sessionId || !userId) return;
    let disposed = false, socket: WebSocket | undefined, port: MessagePort | undefined;
    let iframeReady = false, version: string | undefined, initialized = false;
    const positionKey = `${userId}:${revision}:${sessionId}`;
    const requests = new Set<string>();
    setClear(false); setState('loading'); setMessage('正在连接节点并读取原生轨迹…');
    const initialize = () => {
      if (disposed || initialized || !iframeReady || !version || !frame.current?.contentWindow) return;
      initialized = true;
      const channel = new MessageChannel(); port = channel.port1;
      port.onmessage = event => {
        const request = event.data;
        if (!request || typeof request.requestId !== 'string') return;
        if (socket?.readyState !== WebSocket.OPEN) {
          port?.postMessage({ type: 'error', requestId: request.requestId, code: 'trajectory_disconnected', message: '更新已中断' }); return;
        }
        requests.add(request.requestId); socket.send(JSON.stringify(request));
      };
      port.start();
      frame.current.contentWindow.postMessage({ type: 'nano-trajectory-init', sessionId, version, language: 'zh', theme: 'light', position: positions[positionKey], assetBase: new URL(withBase('/trajectory/'), location.href).href }, '*', [channel.port2]);
    };
    const receive = (event: MessageEvent) => {
      if (event.source !== frame.current?.contentWindow || disposed) return;
      if (event.data?.type === 'viewer-position' && Number.isFinite(event.data.top)) positions[positionKey] = { top: event.data.top, firstSeq: event.data.firstSeq, rowKey: event.data.rowKey, detailTab: event.data.detailTab };
      if (event.data?.type === 'nano-trajectory-ready') { iframeReady = true; initialize(); }
      if (event.data?.type === 'viewer-status') {
        setState(event.data.state);
        setMessage(event.data.state === 'ready' ? '已连接 · 实时更新 · 只读' : event.data.message || '更新已中断，当前为已加载记录');
      }
    };
    window.addEventListener('message', receive);
    void (async () => {
      const response = await authFetch('/im/v1/auth/ws-ticket', { method: 'POST', body: '{}', credentials: 'include' });
      if (!response.ok) throw new Error(`无法建立轨迹连接 (${response.status})`);
      const { ticket } = await response.json() as { ticket: string };
      if (disposed) return;
      const url = new URL(withBase('/im/ws/agent-trajectory'), location.href);
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      url.search = new URLSearchParams({ ticket, agent_id: agentId, session_id: sessionId }).toString();
      socket = new WebSocket(url);
      socket.onmessage = event => {
        if (disposed) return;
        const value = JSON.parse(event.data);
        if (value.type === 'ready') { version = value.version; initialize(); }
        else if (value.type === 'failed') { setState('error'); setMessage(value.message); }
        else { requests.delete(value.requestId); port?.postMessage(value); }
      };
      socket.onclose = event => {
        if (disposed) return;
        for (const requestId of requests) port?.postMessage({ type: 'error', requestId, code: 'trajectory_disconnected', message: event.reason || '更新已中断' });
        requests.clear();
        if (event.code === 1008 && initialized) { setClear(true); setState('error'); setMessage('访问资格已失效，轨迹内容已清除'); }
        else { setState(initialized ? 'interrupted' : 'error'); setMessage(previous => event.reason || (initialized ? '更新已中断，当前为已加载记录' : previous)); }
      };
      socket.onerror = () => { if (!disposed) { setState('error'); setMessage('节点连接失败，可返回工作记录或重试'); } };
    })().catch(error => { if (!disposed) { setState('error'); setMessage(error.message); } });
    return () => { disposed = true; window.removeEventListener('message', receive); port?.close(); socket?.close(); };
  }, [agentId, sessionId, revision, userId, attempt, positions]);

  if (!sessionId) return <div className="im-work-state">{tr('暂无可查看的执行')} <button onClick={onBack}>{tr('返回工作记录')}</button></div>;
  return <div className="im-native-trajectory">
    <div className="im-native-status" role="status"><span>{message}</span>{['error', 'interrupted'].includes(state) && <><button onClick={() => setAttempt(value => value + 1)}>{tr('重新读取')}</button><button onClick={onBack}>{tr('返回工作记录')}</button></>}</div>
    {!clear && <iframe key={`${sessionId}:${revision}:${attempt}`} ref={frame} title="DSH 原生执行轨迹" src={withBase('/trajectory/')} sandbox="allow-scripts" />}
  </div>;
}
