import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { getCurrentLanguage, useTranslation } from '../../../i18n';
import { useAuthStore } from '../../auth/auth-store';
import { getOnboarding } from '../../onboarding/onboarding-api';
import { ModelServicesPanel } from './model-services-panel';

/** Provide a permanent, computer-scoped home for model service management. */
export function ModelsPage() {
  useTranslation();
  const text = (zh: string, en: string) => getCurrentLanguage() === 'zh' ? zh : en;
  const userId = useAuthStore(s => s.user!.id);
  const [nodeId, setNodeId] = useState('');
  const [editing, setEditing] = useState(false);
  const state = useQuery({ queryKey: ['onboarding', userId], queryFn: getOnboarding, refetchInterval: 3000 });
  const node = state.data?.nodes.find(n => n.node_id === nodeId) ?? state.data?.nodes[0];
  const title = text('模型服务', 'Model services');
  return <section className="model-settings-page"><div className="model-settings-inner">
    {(state.isPending || state.error || !node) && <header className="model-settings-heading"><h1>{title}</h1></header>}
    {state.isPending ? <p>{text('正在读取电脑…', 'Loading computers…')}</p> : state.error ? <div className="model-notice model-error" role="alert"><p>{text('暂时无法读取电脑列表。', 'Could not load your computers.')}</p><button onClick={() => void state.refetch()}>{text('重试', 'Retry')}</button></div> : !node ? <div className="model-card model-empty"><h2>{text('先连接运行助手的电脑', 'Connect a computer first')}</h2><p>{text('模型连接和凭据保存在你选择的电脑上。', 'Model connections and credentials stay on the computer you choose.')}</p><Link to="/onboarding">{text('连接电脑 →', 'Connect computer →')}</Link></div> :
      <ModelServicesPanel key={node.node_id} node={node} heading={title} onEditingChange={setEditing}>
        <div className="model-device">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4"/></svg>
          <label><span className="sr-only">{text('选择电脑', 'Choose computer')}</span><select disabled={editing} value={node.node_id} onChange={e => setNodeId(e.target.value)}>{state.data?.nodes.map(n => <option key={n.node_id} value={n.node_id}>{n.alias || n.node_name}</option>)}</select></label>
          <span className={`model-device-status ${node.status !== 'online' ? 'offline' : ''}`}>{node.status === 'online' ? text('在线', 'Online') : text('离线', 'Offline')}</span>
        </div>
      </ModelServicesPanel>}
  </div></section>;
}
