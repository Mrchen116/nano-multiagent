import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { getCurrentLanguage, useTranslation } from '../../../i18n';
import { useAuthStore } from '../../auth/auth-store';
import { setupNode, type ModelService, type OnboardingNode, type SetupError, type SetupInput, type SetupStatus } from '../../onboarding/onboarding-api';
import { ModelServiceEditor, newServiceDraft, serviceDraft, type ServiceDraft } from './model-service-editor';
import './models.css';


/** Manage one computer's services while keeping editable drafts independent of polling. */
export function ModelServicesPanel({ node, initialAdd = false, onEditingChange, heading, children }: {
  node: OnboardingNode; initialAdd?: boolean; heading?: string; children?: ReactNode; onEditingChange?: (editing: boolean) => void;
}) {
  useTranslation();
  const text = (zh: string, en: string) => getCurrentLanguage() === 'zh' ? zh : en;
  const userId = useAuthStore(s => s.user!.id);
  const cache = useQueryClient();
  const queryKey = ['node-setup', userId, node.node_id];
  const status = useQuery({ queryKey, queryFn: () => setupNode(node.node_id, { action: 'status' }), enabled: node.status === 'online', refetchInterval: query => ['testing', 'waiting'].includes(query.state.data?.operation?.state ?? '') ? 1000 : false, retry: false });
  const [draft, setDraft] = useState<ServiceDraft | null>(null);
  const [opened, setOpened] = useState(false);
  const [removing, setRemoving] = useState<{ service: ModelService; revision: string } | null>(null);
  const [error, setError] = useState<SetupError | null>(null);
  const [notice, setNotice] = useState('');
  const [tracked, setTracked] = useState<{ id: string; action: SetupInput['action'] } | null>(null);
  const [needsReview, setNeedsReview] = useState(false);
  const [comparison, setComparison] = useState<SetupStatus | null>(null);
  const [codexModel, setCodexModel] = useState('');
  const [subscriptionFeedback, setSubscriptionFeedback] = useState(false);
  const data = status.data;
  const offline = node.status !== 'online' || status.isError;
  const catalog = (data?.catalog ?? []).filter(p => p.provider !== 'openai-codex');
  const availableCatalog = catalog.filter(p => !data?.services.some(s => s.provider === p.provider));
  const operation = data?.operation;
  const running = operation?.state === 'testing' || operation?.state === 'waiting';
  const authorization = subscriptionFeedback || operation?.state === 'waiting' || Boolean(operation?.url);
  useEffect(() => { if (operation?.state === 'waiting') setSubscriptionFeedback(true); }, [operation?.state]);
  const conflict = !!draft && (needsReview || error?.code === 'conflict' || (data && draft.revision !== data.revision));
  const mutation = useMutation({
    mutationFn: (input: SetupInput) => setupNode(node.node_id, input),
    onSuccess: (result, input) => {
      cache.setQueryData(queryKey, result);
      if (result.error) { setError(result.error); return; }
      setError(null);
      if (result.operation && input.action !== 'cancel') setTracked({ id: result.operation.id, action: input.action });
    },
    onError: () => {
      setError({ code: 'unavailable', message: text('电脑尚未确认结果。草稿已保留，请检查连接后重试。', 'Your computer has not confirmed the result. Your draft is preserved; check the connection and retry.') });
      setNeedsReview(true);
      void status.refetch();
    },
  });
  const busy = mutation.isPending || running;
  const canWrite = !!data && !offline && !busy;
  useEffect(() => { onEditingChange?.(!!draft || !!removing); }, [draft, removing, onEditingChange]);
  useEffect(() => {
    if (offline && draft) setNeedsReview(true);
  }, [offline, draft]);
  useEffect(() => {
    if (initialAdd && data && !data.services.length && !opened && !offline && !running) {
      setDraft(newServiceDraft(data.revision, availableCatalog.find(p => p.provider === 'openai') ?? availableCatalog[0])); setOpened(true);
    }
  }, [initialAdd, data, opened, offline, running]);
  useEffect(() => {
    if (!tracked || operation?.id !== tracked.id || running) return;
    if (operation?.state === 'succeeded') {
      setSubscriptionFeedback(false);
      setDraft(null); setRemoving(null); setComparison(null); setNeedsReview(false); setError(null);
      setNotice(tracked.action === 'remove' ? text('服务已移除。其他连接保持不变。', 'Service removed. Other connections are unchanged.') : text('连接验证成功，已保存。模型可在助手设置中选择。', 'Connection verified and saved. Models are available in assistant settings.'));
      void cache.invalidateQueries({ queryKey: ['settings'] });
      void cache.invalidateQueries({ queryKey: ['onboarding-capabilities'] });
    } else if (operation?.state === 'failed') {
      setError(operation.error ?? { code: 'invalid', message: text('测试未通过。请检查地址、API Key 和模型后重试，原连接保持可用。', 'The test failed. Check the URL, API key and models, then retry. Your previous connection is preserved.') });
    } else if (operation?.state === 'cancelled') {
      setNotice(tracked.action === 'login' ? text('已取消账号连接。', 'Account connection cancelled.') : tracked.action === 'remove' ? text('已取消移除，服务保持不变。', 'Removal cancelled. This service is unchanged.') : text('验证已取消，未保存修改。草稿已保留，可以调整后重试。', 'Verification cancelled without saving. Your draft is preserved for retry.'));
    }
    setTracked(null);
  }, [tracked, operation, running, cache]);
  const resetFeedback = () => { setSubscriptionFeedback(false); setError(null); setNotice(''); setComparison(null); setNeedsReview(false); };
  const add = () => { if (!data) return; resetFeedback(); setDraft(newServiceDraft(data.revision, availableCatalog.find(p => p.provider === 'openai') ?? availableCatalog[0])); };
  const edit = (service: ModelService) => { if (!data) return; resetFeedback(); setDraft(serviceDraft(service, data.revision)); };
  async function compare() {
    const latest = await status.refetch();
    if (latest.data && !latest.error) setComparison(latest.data);
  }
  function save() {
    if (!draft || !canWrite || conflict) return;
    if (!draft.models.length || draft.models.some(m => !m.id.trim()) || new Set(draft.models.map(m => m.id.trim())).size !== draft.models.length) {
      setError({ code: 'invalid', message: text('至少填写一个模型 ID，同一服务内不能重复。', 'Add at least one model ID; IDs must be unique within a service.') }); return;
    }
    setNotice(''); setError(null);
    mutation.mutate({ action: 'save', revision: draft.revision, provider: draft.provider, source: draft.source,
      display_name: draft.display_name.trim(), protocol: draft.protocol, base_url: draft.base_url.trim() || undefined,
      ...(draft.api_key.trim() ? { api_key: draft.api_key.trim() } : {}),
      models: draft.models.map(m => ({ ...m, id: m.id.trim(), display_name: m.display_name?.trim() || undefined })) });
  }
  const errorMessage = error?.code === 'connection_failed' ? text('连接验证失败。请检查 API 地址、模型和密钥后重试，原连接保持可用。', error.message)
    : error?.code === 'in_use' ? text('此模型仍被助手或工具审批使用，请先更换对应模型，再移除。', error.message)
    : error?.code === 'busy' ? text('这台电脑正在处理另一项模型修改，请等待完成。', error.message)
    : error?.code === 'conflict' ? text('模型配置已在另一页面更新，请核对最新配置后再保存。', error.message)
    : error?.message;
  const latestService = draft?.provider ? comparison?.services.find(s => s.provider === draft.provider) : undefined;
  const codex = data?.catalog.find(p => p.provider === 'openai-codex');
  const codexConnected = data?.services.some(s => s.provider === 'openai-codex');
  const operationFeedback = <>
    {error && <div className="model-notice model-error" role="alert"><p>{errorMessage}</p>{error.dependencies?.length ? <><strong>{text('请先为以下助手更换模型：', 'Choose another model for these assistants first:')}</strong><ul>{error.dependencies.map(a => <li key={a.agent_id}>{a.agent_id.startsWith('system:') ? a.display_name : <Link to={`/settings/agents/${encodeURIComponent(a.agent_id)}`}>{a.display_name}</Link>}</li>)}</ul></> : null}</div>}
    {notice && <div className="model-notice" role="status">{notice}</div>}
    {running && <div className={`model-notice ${authorization ? 'model-authorization' : ''}`} role="status">
      <strong>{operation?.state === 'waiting' ? text('在授权页完成登录', 'Complete sign-in on the authorization page') : text('正在测试模型连接…', 'Testing model connections…')}</strong>
      {!authorization && <p>{text('测试期间原有服务继续可用。', 'Existing services remain available during testing.')}</p>}
      {operation?.code && <code className="model-code">{operation.code}</code>}
      <div className="model-authorization-actions">{operation?.url && <a href={operation.url} target="_blank" rel="noreferrer">{text('打开授权页 ↗', 'Open authorization page ↗')}</a>}<button type="button" className="model-link" disabled={mutation.isPending} onClick={() => mutation.mutate({ action: 'cancel' })}>{text('取消验证', 'Cancel verification')}</button></div>
    </div>}
  </>;
  const feedback = <>
    {data?.catalog_error && <div className="model-notice" role="status"><p>{text('服务商目录暂不可用。可继续使用自定义 API，或重试读取目录。', 'The provider catalog is unavailable. Use a custom API or retry loading the catalog.')}</p><button type="button" onClick={() => void status.refetch()}>{text('重新读取目录', 'Retry catalog')}</button></div>}
    {offline && <div className="model-notice model-error" role="alert"><strong>{text('电脑暂时无法连接', 'Computer unavailable')}</strong><p>{text('请在这台电脑启动 Nano。你的草稿和已保存配置都已保留。', 'Start Nano on this computer. Your draft and saved configuration are preserved.')}</p><button type="button" onClick={() => void status.refetch()}>{text('重新检查连接', 'Check connection again')}</button> <Link to="/onboarding">{text('查看连接指引', 'Connection guide')}</Link></div>}
    {!authorization && operationFeedback}
  </>;
  const addButton = <button className="model-primary" disabled={!canWrite || !!removing} onClick={add}>{text('＋ 添加服务', '+ Add service')}</button>;
  return <div className="model-services">
    {heading && <header className="model-settings-heading"><div><h1>{heading}</h1><p>{text('管理助手可用的 API 服务与模型。', 'Manage API services and models for your assistants.')}</p></div>{!draft && addButton}</header>}
    {children}
    {draft ? <form className="model-card model-editor" onSubmit={e => { e.preventDefault(); save(); }}>
      {!(initialAdd && !data?.services.length) && <><button type="button" className="model-link model-back" disabled={busy} onClick={() => { setDraft(null); resetFeedback(); }}>{text('← 模型服务', '← Model services')}</button>
      <h2>{draft.provider ? text('编辑模型服务', 'Edit model service') : text('添加模型服务', 'Add model service')}</h2>
      <p className="model-hint">{text('修改后先测试连接，成功才会保存。', 'Changes are tested before they are saved.')}</p></>}
      {!catalog.length && <p className="model-hint">{text('服务商目录暂不可用。可继续使用自定义 API，或重新检查连接。', 'The provider catalog is unavailable. You can use a custom API or check the connection again.')}</p>}
      <ModelServiceEditor draft={draft} catalog={draft.provider ? catalog : availableCatalog} disabled={busy} onChange={setDraft} text={text} />
      {feedback}
      {conflict && !offline && <div className="model-notice model-conflict" role="alert"><strong>{text('请核对电脑上的最新配置', 'Review the latest configuration')}</strong><p>{text('另一页面可能已更新配置。上方表单仍是你的草稿，不会自动覆盖。', 'Another page may have changed this configuration. Your draft above has not been replaced.')}</p>
        {!comparison ? <button type="button" onClick={() => void compare()}>{text('查看电脑上的最新配置', 'Compare latest configuration')}</button> : <>
          <div className="model-comparison"><div><strong>{text('电脑上的配置', 'On the computer')}</strong>{latestService ? <p>{latestService.display_name}<br />{latestService.base_url || text('服务商默认地址', 'Provider default URL')}<br />{latestService.models.map(m => m.id).join(', ')}</p> : <p>{draft.provider ? text('此服务已被移除。草稿仍保留，可复制内容后添加新服务。', 'This service was removed. Your draft is preserved; copy it into a new service.') : comparison.services.map(s => `${s.display_name}: ${s.models.map(m => m.id).join(', ')}`).join('; ') || text('还没有服务', 'No services')}</p>}</div>
            <div><strong>{text('你的草稿', 'Your draft')}</strong><p>{draft.display_name}<br />{draft.base_url || text('服务商默认地址', 'Provider default URL')}<br />{draft.models.map(m => m.id).join(', ')}</p></div></div>
          <div className="model-actions"><button type="button" onClick={() => { setDraft(latestService ? serviceDraft(latestService, comparison.revision) : null); resetFeedback(); }}>{text('使用电脑上的配置', 'Use computer configuration')}</button>
            <button type="button" disabled={!!draft.provider && !latestService} onClick={() => { setDraft({ ...draft, revision: comparison.revision }); resetFeedback(); setNotice(text('已核对最新版本。点击测试并保存以重新应用草稿。', 'Latest version reviewed. Test and save to reapply your draft.')); }}>{text('核对后重新应用我的修改', 'Reapply my changes after review')}</button></div>
        </>}</div>}
      <div className="model-footer"><button type="button" disabled={busy} onClick={() => { setDraft(null); resetFeedback(); }}>{text('取消', 'Cancel')}</button><button className="model-primary" disabled={!canWrite || conflict}>{busy ? text('正在验证…', 'Verifying…') : text('测试并保存', 'Test and save')}</button></div>
    </form> : <>
      {!heading && <div className="model-list-heading"><h2>{text('已连接的服务', 'Connected services')}</h2>{addButton}</div>}
      {feedback}
      {removing && <div className="model-notice model-error"><strong>{text('确认移除', 'Remove')} {removing.service.display_name}?</strong><p>{removing.service.provider === 'openai-codex' ? text('只移除这台电脑上的模型路由，保留订阅授权。在用模型需先为助手更换。', 'Only the model routes are removed; subscription authorization is kept. Assistants must switch away from models in use first.') : text('移除服务及其 API 密钥。在用模型需先为助手更换。', 'Remove this service and its API key. Assistants must switch away from models in use first.')}</p>
        {data && removing.revision !== data.revision && <p>{text('配置已更新。请保留并重新选择最新列表中的服务。', 'Configuration changed. Keep this service and select it again from the latest list.')}</p>}
        <div className="model-actions"><button disabled={!canWrite || removing.revision !== data?.revision} onClick={() => mutation.mutate({ action: 'remove', provider: removing.service.provider, revision: removing.revision })}>{text('确认移除', 'Confirm removal')}</button><button disabled={busy} onClick={() => { setRemoving(null); resetFeedback(); }}>{text('保留', 'Keep service')}</button></div></div>}
      <div className="model-card">
        {!data ? <p>{offline ? text('连接后即可读取模型服务。', 'Reconnect to load model services.') : text('正在读取模型服务…', 'Loading model services…')}</p> : data.services.length ? data.services.map(service => <div className="model-service-row" key={service.provider}>
          <div className="model-service-info"><h3>{service.display_name}</h3>
            <small>{service.provider === 'openai-codex' ? text('订阅连接', 'Subscription connection') : service.source === 'custom' ? text('自定义 API', 'Custom API') : catalog.find(p => p.provider === service.source)?.display_name || service.source}</small>
            <div className="model-tags">{service.models.map(m => <span key={m.name}>{m.display_name || m.id}</span>)}</div>
          </div>
          <div className="model-row-actions">
            {service.provider !== 'openai-codex' && <button aria-label={`${text('编辑', 'Edit')} ${service.display_name}`} disabled={!canWrite || !!removing} onClick={() => edit(service)}>{text('编辑', 'Edit')}</button>}
            <button aria-label={`${text('移除', 'Remove')} ${service.display_name}`} className="model-remove-service" disabled={!canWrite || !!removing} onClick={() => { resetFeedback(); setRemoving({ service, revision: data.revision }); }}>{text('移除', 'Remove')}</button>
          </div>
        </div>) : !offline && <div className="model-empty"><h3>{text('还没有模型服务', 'No model services yet')}</h3><p>{text('添加一个 API 服务，供这台电脑上的助手使用。', 'Add an API service for assistants on this computer.')}</p></div>}
      </div><p className="model-hint model-list-hint">{text('在助手设置中选择要使用的模型。', 'Choose which model to use in assistant settings.')}</p>
    </>}
    {codex && !codexConnected && <details className="model-subscription" open={authorization || undefined}>
      <summary>{text('连接 ChatGPT / Codex 订阅', 'Connect a ChatGPT / Codex subscription')}</summary>
      {authorization && operationFeedback}
      {!running && <div className="model-subscription-fields"><label>{text('订阅模型', 'Subscription model')}<select value={codexModel || codex.models[0]?.id || ''} onChange={e => setCodexModel(e.target.value)}>{codex.models.map(m => <option key={m.id} value={m.id}>{m.name || m.id}</option>)}</select></label>
        <button disabled={!canWrite || !codex.models.length || conflict} onClick={() => { setNotice(''); setError(null); setSubscriptionFeedback(true); mutation.mutate({ action: 'login', revision: data!.revision, provider: 'openai-codex', model: codexModel || codex.models[0]!.id }); }}>{text('连接 Codex 账号', 'Connect Codex account')}</button>
      </div>}
    </details>}
  </div>;
}
