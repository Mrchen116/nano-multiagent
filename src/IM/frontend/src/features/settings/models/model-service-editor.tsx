import { useId } from 'react';
import type { CatalogProvider, ModelProtocol, ModelService, ServiceModel } from '../../onboarding/onboarding-api';

type Text = (zh: string, en: string) => string;
export interface ServiceDraft {
  revision: string; provider?: string; source: string; display_name: string; protocol?: ModelProtocol;
  base_url: string; api_key: string; credential_stored: boolean; models: ServiceModel[];
}

/** Open a non-secret service snapshot as an independent, revision-bound draft. */
export function serviceDraft(service: ModelService, revision: string): ServiceDraft {
  return { revision, provider: service.provider, source: service.source, display_name: service.display_name,
    protocol: service.protocol, base_url: service.base_url ?? '', api_key: '', credential_stored: service.credential_stored,
    models: service.models.map(({ name: _name, ...model }) => ({ ...model })) };
}

/** Initialize a catalog service using its declared model metadata, or a custom API. */
export function newServiceDraft(revision: string, provider?: CatalogProvider): ServiceDraft {
  const model = provider?.models[0];
  return { revision, source: provider?.provider ?? 'custom', display_name: provider?.display_name ?? '',
    protocol: provider ? undefined : 'openai-completions', base_url: '', api_key: '', credential_stored: false,
    models: [model ? { id: model.id, display_name: model.name, context_window: model.contextWindow,
      max_tokens: model.maxTokens, input: model.inputModalities } : { id: '', input: ['text'] }] };
}

/** Render API fields shared by first-run setup and continuing model management. */
export function ModelServiceEditor({ draft, catalog, disabled, onChange, text }: {
  draft: ServiceDraft; catalog: CatalogProvider[]; disabled: boolean; onChange: (draft: ServiceDraft) => void; text: Text;
}) {
  const prefix = useId();
  const custom = draft.source === 'custom';
  const provider = catalog.find(p => p.provider === draft.source);
  const change = (patch: Partial<ServiceDraft>) => onChange({ ...draft, ...patch });
  const changeModel = (index: number, patch: Partial<ServiceModel>) => change({ models: draft.models.map((m, i) => i === index ? { ...m, ...patch } : m) });
  return <fieldset disabled={disabled} className="model-fields">
    {!draft.provider && <div className="model-tabs" role="group" aria-label={text('连接方式', 'Connection type')}>
      <button type="button" aria-pressed={!custom} disabled={!catalog.length} onClick={() => onChange(newServiceDraft(draft.revision, catalog.find(p => p.provider === 'openai') ?? catalog[0]))}>{text('内置服务商', 'Built-in provider')}</button>
      <button type="button" aria-pressed={custom} onClick={() => onChange(newServiceDraft(draft.revision))}>{text('自定义 API', 'Custom API')}</button>
    </div>}
    {!custom && <label>{text('服务商', 'Provider')}<select aria-label={text('服务商', 'Provider')} value={draft.source} disabled={!!draft.provider} onChange={e => onChange(newServiceDraft(draft.revision, catalog.find(p => p.provider === e.target.value)))}>
      {!provider && <option value={draft.source}>{draft.source}</option>}
      {catalog.map(p => <option key={p.provider} value={p.provider}>{p.display_name}</option>)}
    </select><small>{draft.provider ? text('服务商创建后固定。其他地址或凭据可添加自定义服务。', 'The provider is fixed. Add a custom API for another endpoint or credential.') : text('使用服务商默认连接方式和模型目录。多套凭据请添加自定义服务。', 'Uses provider defaults and its model catalog. Use a custom API for additional credentials.')}</small></label>}
    <label>{text('服务名称', 'Service name')}<input value={draft.display_name} required maxLength={100} onChange={e => change({ display_name: e.target.value })} placeholder={text('例如：团队模型服务', 'For example: Team models')} /></label>
    {custom && <div className="model-grid"><label>{text('API 地址', 'API URL')}<input type="url" required value={draft.base_url} onChange={e => change({ base_url: e.target.value })} placeholder="https://api.example.com/v1" /></label>
      <label>{text('协议', 'Protocol')}<select value={draft.protocol} onChange={e => change({ protocol: e.target.value as ModelProtocol })}><option value="openai-completions">OpenAI Chat Completions</option><option value="openai-responses">OpenAI Responses</option><option value="anthropic-messages">Anthropic Messages</option></select></label></div>}
    <label>{text('API Key', 'API Key')}<input aria-label="API Key" type="password" autoComplete="off" value={draft.api_key} onChange={e => change({ api_key: e.target.value })} placeholder={draft.credential_stored ? text('留空保留当前密钥', 'Leave blank to keep the saved key') : text('粘贴 API Key', 'Paste your API key')} />
      <small>{draft.credential_stored ? text('已保存 · 留空保留，输入新密钥则替换。', 'Key saved · leave blank to keep it, or enter a replacement.') : text('凭据只保存在所选电脑，保存后不会回显。免密服务可留空。', 'Credentials stay on the selected computer and are never shown again. Leave blank for a keyless service.')}</small></label>
    <div className="model-subhead"><h3>{text('模型', 'Models')}</h3><button type="button" className="model-link" onClick={() => change({ models: [...draft.models, { id: '', input: ['text'] }] })}>{text('＋ 添加模型', '+ Add model')}</button></div>
    <p className="model-hint">{text('填写服务提供的模型 ID；显示名称只影响界面。', 'Use the upstream model ID. Display names only change its label.')}</p>
    <datalist id={`${prefix}-catalog`}>{provider?.models.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</datalist>
    {draft.models.map((model, index) => <div className="model-entry" key={index}>
      <div className="model-entry-fields"><label>{text('模型 ID', 'Model ID')}<input list={`${prefix}-catalog`} required value={model.id} onChange={e => {
          const selected = provider?.models.find(item => item.id === e.target.value);
          changeModel(index, selected ? {id: selected.id, display_name: selected.name, context_window: selected.contextWindow, max_tokens: selected.maxTokens, input: selected.inputModalities} : {id: e.target.value});
        }} /></label>
        <label>{text('模型显示名称', 'Model display name')}<input value={model.display_name ?? ''} onChange={e => changeModel(index, { display_name: e.target.value })} placeholder={text('可选', 'Optional')} /></label>
        <button type="button" className="model-remove" aria-label={`${text('移除模型', 'Remove model')} ${index + 1}`} onClick={() => change({ models: draft.models.filter((_, i) => i !== index) })}>×</button></div>
      <details><summary>{text('模型能力', 'Model capabilities')}</summary><div className="model-grid"><label>{text('上下文窗口', 'Context window')}<input type="number" min={1} step={1} value={model.context_window ?? ''} onChange={e => changeModel(index, { context_window: e.target.value ? Number(e.target.value) : undefined })} placeholder={text('使用默认值', 'Use default')} /></label>
        <label>{text('最大输出 token', 'Maximum output tokens')}<input type="number" min={1} step={1} value={model.max_tokens ?? ''} onChange={e => changeModel(index, { max_tokens: e.target.value ? Number(e.target.value) : undefined })} placeholder={text('使用默认值', 'Use default')} /></label></div>
        <label className="model-checkbox"><input type="checkbox" checked={model.input?.includes('image') ?? false} onChange={e => changeModel(index, { input: e.target.checked ? ['text', 'image'] : ['text'] })} />{text('支持图片输入', 'Supports image input')}</label></details>
    </div>)}
    {!custom && <details><summary>{text('高级设置', 'Advanced settings')}</summary><label>{text('API 地址覆盖（可选）', 'API URL override (optional)')}<input type="url" value={draft.base_url} onChange={e => change({ base_url: e.target.value })} placeholder={text('留空使用服务商默认地址', 'Leave blank for the provider default')} /></label></details>}
  </fieldset>;
}
