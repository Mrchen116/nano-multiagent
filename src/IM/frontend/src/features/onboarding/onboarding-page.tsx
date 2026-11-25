import { AvatarPicker } from "../chat/components/avatar-picker";
import { AssistantPortrait, avatarVariantFor } from "../chat/components/assistant-portrait";
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { desktopScopedKey, isDesktopClient } from '../../desktop/desktop-context';
import { DesktopDualInstallPicker, hasDesktopInstallAwareness } from '../../desktop/desktop-install-picker';
import { DesktopNodeOnboardingBanner } from '../../desktop/desktop-node-onboarding-banner';
import { useIsMobile } from '../../hooks/use-is-mobile';
import { OnboardingWelcome } from './onboarding-welcome';
import { ProductHeader } from '../home/product-header';
import { getCurrentLanguage, useTranslation } from '../../i18n';
import { useAuthStore } from '../auth/auth-store';
import { createPersonalAgent, getPersonalAgent } from '../personal-agent/personal-agent-api';
import { ModelServicesPanel } from '../settings/models/model-services-panel';
import { getOnboarding, setupNode } from './onboarding-api';
import { bindingTargetKey } from './binding-target';
import { InstallPlatformPicker, suggestedPlatform, WindowsInstallPanel } from './windows-install';
import './onboarding.css';

/** First-run progress is reconstructed from the user's actual node and model state. */
export function OnboardingPage() {
  const { t } = useTranslation();
  const language = getCurrentLanguage(), zh = language === 'zh';
  const text = (cn: string, en: string) => zh ? cn : en;
  const user = useAuthStore(s => s.user)!;
  const navigate = useNavigate(), cache = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const reconnectId = searchParams.get('node') || null;
  const draftKey = desktopScopedKey(`nano-onboarding:${user.id}`);
  const [draft] = useState(() => { try { return JSON.parse(localStorage.getItem(draftKey) ?? '{}'); } catch { return {}; } });
  const isMobile = useIsMobile();
  const phoneHandoff = isMobile && suggestedPlatform() !== 'windows';
  const [platform, setPlatform] = useState(suggestedPlatform);
  const [windowsOpened, setWindowsOpened] = useState(false);
  const targetKey = bindingTargetKey(user.id);
  const [bindingTarget, setBindingTarget] = useState(() => localStorage.getItem(targetKey));
  useEffect(() => {
    const onBinding = (event: StorageEvent) => {
      if (event.key === targetKey) setBindingTarget(event.newValue);
    };
    window.addEventListener('storage', onBinding);
    return () => window.removeEventListener('storage', onBinding);
  }, [targetKey]);
  const [started, setStarted] = useState(Boolean(draft.started));
  const [installExpanded, setInstallExpanded] = useState(false);
  const [requestKey] = useState<string>(() => draft.requestKey ?? crypto.randomUUID());
  const [nodeId, setNodeId] = useState<string>(draft.nodeId ?? '');
  const [name, setName] = useState<string>(draft.name ?? text('小助理', 'My assistant'));
  const [avatar, setAvatar] = useState<number>(draft.avatar ?? avatarVariantFor(user.id));
  const [viewStep, setViewStep] = useState<number | null>(null);
  const [installMethod, setInstallMethod] = useState<'agent' | 'manual'>('manual');
  const [copied, setCopied] = useState(false), [copyError, setCopyError] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false), [linkCopyError, setLinkCopyError] = useState(false);
  const [editingModel, setEditingModel] = useState(false);
  const personal = useQuery({queryKey:['personal-agent',user.id],queryFn:getPersonalAgent,retry:false,refetchInterval:3000});
  const state = useQuery({ queryKey: ['onboarding', user.id], queryFn: getOnboarding, refetchInterval: 3000 });
  const selectedId = reconnectId ?? bindingTarget ?? personal.data?.binding?.node_id ?? nodeId;
  const node = state.data?.nodes.find(n => n.node_id === selectedId)
    ?? (bindingTarget === null && !reconnectId ? state.data?.nodes.find(n => n.status === 'online') ?? state.data?.nodes[0] : undefined);
  const currentNodeId = node?.node_id;
  useEffect(() => {
    if (!reconnectId || currentNodeId !== reconnectId) return;
    localStorage.setItem(targetKey, reconnectId);
    setBindingTarget(reconnectId);
    setSearchParams(params => { params.delete('node'); return params; }, { replace: true });
  }, [reconnectId, currentNodeId, targetKey, setSearchParams]);
  const setup = useQuery({ queryKey: ['node-setup', user.id, currentNodeId], queryFn: () => setupNode(currentNodeId!, { action: 'status' }), enabled: !!currentNodeId && node?.status === 'online', refetchInterval: 2000, retry: false });
  const configured = !!setup.data?.default_model && setup.data.models.some(m => m.model === setup.data?.default_model);
  const existingAgent = personal.data?.binding;
  const suggestedStep = node?.status !== 'online' ? 0 : existingAgent ? 3 : configured ? 2 : 1;
  const step = node?.status !== 'online' && (viewStep !== 1 || bindingTarget !== null || reconnectId) ? 0 : viewStep ?? suggestedStep;
  useEffect(() => { if (currentNodeId && !nodeId) setNodeId(currentNodeId); }, [currentNodeId, nodeId]);
  useEffect(() => { if (viewStep === null && setup.data && !configured && !existingAgent && node?.status === 'online') setViewStep(1); }, [viewStep, setup.data, configured, existingAgent, node?.status]);
  const operation = setup.data?.operation;
  const working = operation?.state === 'waiting' || operation?.state === 'testing';
  const create = useMutation({
    mutationFn: () => {
      const displayName = existingAgent?.display_name ?? name.trim();
      if (!node || !displayName) throw new Error('not ready');
      return createPersonalAgent({request_key:personal.data?.creation?.request_key ?? requestKey,node_id:existingAgent?.node_id ?? node.node_id,display_name:displayName,...(!existingAgent || personal.data?.creation?.request_key === requestKey ? {avatar_variant:avatar} : {})});
    },
    onSuccess: async result => {
      await Promise.all([cache.invalidateQueries({queryKey:['personal-agent']}),cache.invalidateQueries({queryKey:['onboarding',user.id]}),cache.invalidateQueries({queryKey:['chat']})]);
      if (result.binding?.status === 'active') navigate(`/chat/${result.binding.conversation_id}`);
    },
  });
  useEffect(() => { localStorage.setItem(draftKey, JSON.stringify({requestKey,nodeId:currentNodeId??'',name,started,avatar})); }, [draftKey,requestKey,currentNodeId,name,started,avatar]);
  const install = state.data?.install;
  const dualDesktopAware = hasDesktopInstallAwareness(install);
  const windows = !dualDesktopAware && platform === 'windows' && install?.windows_x64 !== undefined;
  const installAvailable = dualDesktopAware
    ? Boolean(install?.available || install?.windows_x64 || install?.desktop_darwin_arm64 || install?.desktop_win32_x64)
    : windows ? !!install?.windows_x64 : install?.available;
  function awaitWindowsBinding(opened: boolean) {
    setWindowsOpened(opened);
    setViewStep(0);
    localStorage.setItem(targetKey, '');
    setBindingTarget('');
  }
  const installPrompt = install ? text(
      `请帮我安装 Crewden 电脑端并连接 ${install.origin}。运行这个服务的安装器：\n${install.command}\n保留已有配置、凭据和工作文件；不要部署 IM 服务。安装后打开浏览器让我确认电脑绑定，再回到网页完成模型和助手设置。不要向我索取账号密码、模型密钥或登录文件；不要改全局设置。`,
      `Install the Crewden computer client and connect it to ${install.origin}. Run the service installer:\n${install.command}\nPreserve existing configuration, credentials, and work files. Do not deploy an IM server. Open the browser for me to confirm this computer, then return to the webpage for model and assistant setup. Do not request passwords, model keys, or login files, or change global settings.`,
    ) : '';
  async function copy() {
    if (!install?.available) return;
    try { await navigator.clipboard.writeText(installMethod === 'manual' ? install.command : installPrompt); setCopied(true); setCopyError(false); }
    catch { setCopied(false); setCopyError(true); }
  }
  const setupLink = `${window.location.origin}/onboarding`;
  const showWelcome = !started && bindingTarget === null && state.isSuccess && state.data.nodes.length === 0 && personal.isSuccess && !existingAgent;
  const completed = [node?.status === 'online', node?.status === 'online' && setup.isSuccess && configured, existingAgent?.status === 'active'];
  const stepHints = [text('助手工作的地方', 'A place for your assistant to work'), text('接入你已有的模型服务', 'Use a model service you have'), text('起个名字，开始合作', 'Give it a name and begin')];
  const title = [text('连接电脑', 'Connect computer'), text('连接模型', 'Connect model'), text('创建个人助手', 'Create personal assistant')];
  const error = (message: string) => <p className="onboarding-error" role="alert">{message}</p>;
  const next = (index: number, disabled = false) => <button className="onboarding-primary" disabled={disabled} onClick={() => setViewStep(index)}>{text('继续', 'Continue')}</button>;
  return <div className="onboarding-screen product-entry">
    <ProductHeader page="setup" accountName={user.display_name} />
    {showWelcome ? <OnboardingWelcome name={user.display_name} onStart={() => setStarted(true)} /> : <main className="onboarding-main"><div className="onboarding-layout"><aside><div className="onboarding-intro"><span>{text('首次设置', 'Getting started')}<span className="onboarding-mobile-step">{text(`步骤 ${Math.min(step + 1, 3)} / 3`, `Step ${Math.min(step + 1, 3)} of 3`)}</span></span><h1>{text('一起把助手\n准备好。', 'Get your\nassistant ready.')}</h1><p>{text('完成这三步，开始和你的长期个人助手对话。', 'Three steps to your first conversation with a long-term personal assistant.')}</p></div>
      <ol className="onboarding-steps">{title.map((label, i) => <li key={label} aria-current={i === Math.min(step,2) ? 'step' : undefined} className={i === Math.min(step,2) ? 'active' : completed[i] ? 'done' : ''}><span>{completed[i] ? '✓' : i + 1}</span><div><strong>{label}</strong><small>{stepHints[i]}</small></div></li>)}</ol><p className="onboarding-note">{text('助手在连接的电脑上执行任务、保存工作文件。执行时需要保持电脑在线。', 'Your assistant runs tasks and saves work files on the connected computer. Keep it online while work runs.')}<br /><br />{text('已完成的设置会保留，随时可以回来继续。', 'Completed setup is saved. Come back whenever you are ready.')}</p>{state.isSuccess && state.data.nodes.length === 0 && bindingTarget === null && !existingAgent && <button className="onboarding-intro-return" onClick={() => setStarted(false)}>{text('重新查看使用介绍', 'Review the introduction')}</button>}<Link className="onboarding-skip" to="/chat">{text('稍后继续，返回个人空间', 'Continue later, open your space')} <span aria-hidden="true">↗</span></Link></aside>
        <section className="onboarding-card" aria-live="polite">
          {state.isPending ? <p>{text('正在准备你的空间…', 'Loading your space…')}</p> : state.error ? <>{error(text('暂时无法读取设置进度。你的数据仍会保留。', 'Setup progress could not be loaded. Your data is preserved.'))}<button className="onboarding-secondary" onClick={() => void state.refetch()}>{text('重试', 'Retry')}</button></> : <>
          {personal.isError && <div className="onboarding-error" role="alert"><p>{text('暂时无法确认个人助手状态，已填写的内容会保留。', 'We couldn’t check your personal assistant. Your input is preserved.')}</p><button className="onboarding-link" onClick={() => void personal.refetch()}>{text('重新检查助手状态', 'Retry assistant status')}</button></div>}
          {step === 0 && <><span className="onboarding-card-eyebrow">{text('第一步 · 工作环境', 'Your computer')}</span><h2>{text('连接你的工作电脑', 'Connect your computer')}</h2><p className="onboarding-sub">{text('在这台电脑上安装 Crewden 电脑端，让助手可以执行任务、处理文件。', 'Install the Crewden computer client on the computer where your assistant will run tasks and work with files.')}</p>

            {phoneHandoff && <div className="onboarding-handoff"><strong>{text('正在用手机？到电脑上继续', 'On your phone? Continue on a computer')}</strong><p>{text('在工作电脑上打开此链接，登录同一账号即可接着设置。', 'Open this link on your work computer and sign in to the same account to continue.')}</p><div><input aria-label={text('电脑端设置链接', 'Computer setup link')} value={setupLink} readOnly /><button className="onboarding-secondary" onClick={async () => { try { await navigator.clipboard.writeText(setupLink); setLinkCopied(true); setLinkCopyError(false); } catch { setLinkCopyError(true); } }}>{linkCopied ? text('已复制', 'Copied') : text('复制链接', 'Copy link')}</button></div>{linkCopyError && <p role="alert">{text('请选中上方链接手动复制。', 'Select and copy the link above.')}</p>}</div>}
            {phoneHandoff && <button className="onboarding-install-toggle" aria-expanded={installExpanded} onClick={() => setInstallExpanded(!installExpanded)}>{text('查看电脑上的安装步骤', 'View computer installation steps')} <span aria-hidden="true">{installExpanded ? '−' : '+'}</span></button>}
            {(!phoneHandoff || installExpanded) && <div className="onboarding-install-content">
            {isDesktopClient() ? (
              <DesktopNodeOnboardingBanner
                inline
                onConnected={(connectedId) => {
                  localStorage.setItem(targetKey, connectedId);
                  setNodeId(connectedId);
                  setBindingTarget(connectedId);
                  void state.refetch();
                }}
              />
            ) : dualDesktopAware && install ? (
              <DesktopDualInstallPicker
                install={install}
                onRecheck={() => void state.refetch()}
                onStartDesktopOrWindows={awaitWindowsBinding}
                renderUnixHeadless={() => (
                  <>
                    {install.available && <div className="onboarding-install-tabs" role="group" aria-label={text('安装方式', 'Installation method')}>{(['manual', 'agent'] as const).map(method => <button key={method} onClick={() => { setInstallMethod(method); setCopied(false); setCopyError(false); }} aria-pressed={installMethod === method}>{method === 'manual' ? text('在终端安装', 'Use a terminal') : text('交给本地 Agent', 'Use a local agent')}</button>)}</div>}
                    {install.available ? <>
                      <ol className="onboarding-install-steps"><li><span>1</span>{installMethod === 'manual' ? text('复制命令，在工作电脑的终端粘贴运行。', 'Copy the command and run it in your computer’s terminal.') : text('复制说明，发给电脑上的 Codex、Claude Code 等。', 'Copy the instructions into Codex, Claude Code, or another local agent.')}</li><li><span>2</span>{text('安装后，在打开的网页中确认绑定这台电脑。', 'After installation, confirm the computer in the browser that opens.')}</li><li><span>3</span>{text('回到这里，电脑连接成功后即可继续。', 'Return here to continue once your computer connects.')}</li></ol>
                      <div className="onboarding-instructions"><div className="onboarding-command-header"><span aria-hidden="true"><i /><i /><i /></span>{installMethod === 'manual' ? text('终端命令', 'Terminal command') : text('给本地 Agent 的说明', 'Instructions for your local agent')}</div>{installMethod === 'manual' ? <code>{install.command}</code> : <details open={copyError || undefined}><summary>{text('查看完整安装说明', 'View installation instructions')}</summary><code>{installPrompt}</code></details>}</div>
                      <button className="onboarding-primary onboarding-copy" onClick={() => void copy()}>{copied ? text('已复制，请到电脑上继续', 'Copied. Continue on your computer.') : installMethod === 'agent' ? text('复制安装说明', 'Copy agent instructions') : text('复制安装命令', 'Copy install command')}{copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}</button>
                      {copyError && error(text('无法自动复制，请选中上方内容手动复制。', 'Clipboard is unavailable. Select and copy the text above.'))}
                    </> : <div className="onboarding-unavailable" role="status"><strong>{text('安装包暂不可用', 'The installer is not available yet')}</strong><p>{text('当前服务尚未提供电脑端安装包。你的账号已就绪，可以稍后回来继续。', 'This service has not published a computer installer. Your account is ready; you can return and continue later.')}</p><button className="onboarding-secondary" onClick={() => void state.refetch()}>{text('重新检查', 'Check again')}</button></div>}
                  </>
                )}
              />
            ) : (
              <>
            {install?.windows_x64 === undefined && <p className="onboarding-platforms">macOS <span>·</span> Linux <span>·</span> Windows (WSL)</p>}
            {install?.windows_x64 !== undefined && <InstallPlatformPicker value={platform} onChange={value => {
              setPlatform(value);
              if (bindingTarget === '' && value === 'unix') { localStorage.removeItem(targetKey); setBindingTarget(null); }
            }}/>}
            {windows ? node?.status === 'online' ? <p>{t('computers.windows.online')}</p> :
              <WindowsInstallPanel materials={install?.windows_x64} onStart={awaitWindowsBinding} onRecheck={() => void state.refetch()}/>
              : <>
            {install?.available && <div className="onboarding-install-tabs" role="group" aria-label={text('安装方式', 'Installation method')}>{(['manual', 'agent'] as const).map(method => <button key={method} onClick={() => { setInstallMethod(method); setCopied(false); setCopyError(false); }} aria-pressed={installMethod === method}>{method === 'manual' ? text('在终端安装', 'Use a terminal') : text('交给本地 Agent', 'Use a local agent')}</button>)}</div>}
            {install?.available ? <>
              <ol className="onboarding-install-steps"><li><span>1</span>{installMethod === 'manual' ? text('复制命令，在工作电脑的终端粘贴运行。', 'Copy the command and run it in your computer’s terminal.') : text('复制说明，发给电脑上的 Codex、Claude Code 等。', 'Copy the instructions into Codex, Claude Code, or another local agent.')}</li><li><span>2</span>{text('安装后，在打开的网页中确认绑定这台电脑。', 'After installation, confirm the computer in the browser that opens.')}</li><li><span>3</span>{text('回到这里，电脑连接成功后即可继续。', 'Return here to continue once your computer connects.')}</li></ol>
              <div className="onboarding-instructions"><div className="onboarding-command-header"><span aria-hidden="true"><i /><i /><i /></span>{installMethod === 'manual' ? text('终端命令', 'Terminal command') : text('给本地 Agent 的说明', 'Instructions for your local agent')}</div>{installMethod === 'manual' ? <code>{install.command}</code> : <details open={copyError || undefined}><summary>{text('查看完整安装说明', 'View installation instructions')}</summary><code>{installPrompt}</code></details>}</div>
              <button className="onboarding-primary onboarding-copy" onClick={() => void copy()}>{copied ? text('已复制，请到电脑上继续', 'Copied. Continue on your computer.') : installMethod === 'agent' ? text('复制安装说明', 'Copy agent instructions') : text('复制安装命令', 'Copy install command')}{copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}</button>
              {copyError && error(text('无法自动复制，请选中上方内容手动复制。', 'Clipboard is unavailable. Select and copy the text above.'))}
            </> : <div className="onboarding-unavailable" role="status"><strong>{text('安装包暂不可用', 'The installer is not available yet')}</strong><p>{text('当前服务尚未提供电脑端安装包。你的账号已就绪，可以稍后回来继续。', 'This service has not published a computer installer. Your account is ready; you can return and continue later.')}</p><button className="onboarding-secondary" onClick={() => void state.refetch()}>{text('重新检查', 'Check again')}</button></div>}
            </>}
              </>
            )}
            </div>}
            {state.data && state.data.nodes.length > (bindingTarget === '' ? 0 : 1) && <label>
              {bindingTarget === '' ? text('选择你刚刚确认的电脑', 'Choose the computer you just confirmed') : text('选择电脑', 'Choose computer')}
              <select value={currentNodeId ?? ''} onChange={e => {
                const selected = e.target.value;
                localStorage.setItem(targetKey, selected);
                setNodeId(selected);
                setBindingTarget(selected);
              }}>
                {!currentNodeId && <option value="" disabled>{text('选择电脑', 'Choose computer')}</option>}
                {state.data.nodes.map(n => <option key={n.node_id} value={n.node_id}>{n.alias || n.node_name}</option>)}
              </select>
            </label>}
            {installAvailable || node ? <p className={`onboarding-status ${node?.status === 'online' ? 'ok' : ''}`} role="status"><span />{node ? `${node.alias || node.node_name} · ${node.status === 'online' ? text('已连接', 'Connected') : text('暂时离线', 'Offline')}` : windows && windowsOpened ? t('computers.windows.waiting') : text('等待电脑连接，连接后会自动更新', 'Waiting for your computer. This updates when it connects.')}</p> : null}
            {node?.status !== 'online' && node && !windows && install?.available && <p className="onboarding-detail">{text('在该电脑重跑上方命令即可恢复。已有身份、配置和文件会保留。', 'Run the command on that computer again to reconnect. Your identity, settings, and files are preserved.')}</p>}
            {node?.status === 'online' && <div className="onboarding-footer"><span />{next(configured ? 2 : 1)}</div>}
          </>}
          {step === 1 && <><span className="onboarding-card-eyebrow">{text('第二步 · 模型连接', 'Model connection')}</span><h2>{text('给助手接通一个模型', 'Connect a model')}</h2><p className="onboarding-sub">{text('模型提供理解和推理能力。选择你已有的接入方式，验证成功后就可以继续。', 'A model gives your assistant language and reasoning capabilities. Choose an access method you already have, then verify it to continue.')}</p><p className="onboarding-connected-computer"><span aria-hidden="true">✓</span> {node?.alias || node?.node_name}</p>
            {node && <ModelServicesPanel key={node.node_id} node={node} initialAdd onEditingChange={setEditingModel} onConnected={() => setViewStep(2)} />}
            <div className="onboarding-footer"><button className="onboarding-link" onClick={() => setViewStep(0)}>{text('← 返回', '← Back')}</button>{!editingModel && next(2, !configured || working || node?.status !== 'online')}</div>
          </>}
          {step === 2 && <><span className="onboarding-card-eyebrow">{text('第三步 · 认识你的助手', 'Meet your assistant')}</span><h2>{text('给你的个人助手起个名字', 'Name your personal assistant')}</h2><p className="onboarding-sub">{text('它会成为你的长期协作伙伴。名字随时可以修改，先选一个你喜欢的称呼。','This is the start of a long-term working relationship. Pick a name you like; you can change it later.')}</p>
            <div className="onboarding-identity-preview"><AssistantPortrait variant={avatar} size={44} /><div><strong>{name.trim() || text('你的个人助手', 'Your personal assistant')}</strong><small>{text('为你服务的长期助手', 'Your long-term personal assistant')}</small></div></div>
            <label htmlFor="onboarding-name">{text('给助手起个名字', 'Name your assistant')}</label><input id="onboarding-name" value={name} onChange={e => setName(e.target.value)} maxLength={80} />
            <AvatarPicker personal value={avatar} onChange={setAvatar} disabled={create.isPending} />
            <div className="onboarding-ready-summary"><span>✓ {node?.alias || node?.node_name}</span><span>{configured && !setup.isError ? '✓ ' : ''}{setup.data?.models.find(model => model.model === setup.data?.default_model)?.display_name || setup.data?.default_model || text('等待模型确认', 'Waiting for model confirmation')}</span></div>
            <details className="onboarding-privacy"><summary>{text('它可以看到什么？', 'What can your assistant see?')}</summary><p>{text('助手可按需查询你有权查看的已参与聊天，相关资料由你配置的模型处理。你随时可以排除聊天；助手看过不代表你已读。','Your assistant can look up conversations you participated in and can still access. Your configured model processes relevant information. Exclude chats anytime; your assistant does not mark messages read for you.')}</p></details>
            <p className="onboarding-detail">{text('创建后进入你与助手的私人对话，由你发送第一条消息。', 'Creation opens your private assistant conversation. You choose the first message to send.')}</p>
            {create.error && error(text('电脑尚未确认创建结果。名称已保留，重试会核对同一助手。','Your computer has not confirmed creation. Your name is preserved; retry checks the same assistant.'))}
            {node?.status !== 'online' && error(text('电脑暂时离线，重新上线后即可继续。', 'Your computer is offline. Continue when it reconnects.'))}
            {personal.isPending && <p role="status" className="onboarding-detail">{text('正在确认个人助手状态…', 'Checking your personal assistant…')}</p>}
            {setup.isError && <div className="onboarding-error" role="alert"><p>{text('暂时无法确认模型连接，请重新检查。', 'We couldn’t confirm the model connection. Please check again.')}</p><button className="onboarding-link" onClick={() => void setup.refetch()}>{text('重新检查模型', 'Check model again')}</button></div>}
            <div className="onboarding-footer"><button className="onboarding-link" onClick={() => setViewStep(1)}>{text('← 返回', '← Back')}</button><button className="onboarding-primary" disabled={!name.trim() || !configured || setup.isError || !personal.isSuccess || create.isPending || node?.status !== 'online'} onClick={() => create.mutate()}>{create.isPending ? text('正在创建…', 'Creating…') : create.error ? text('核对并重试', 'Check and retry') : text('创建个人助手', 'Create personal assistant')}</button></div>
          </>}
          {step === 3 && <>{create.isError && error(text('电脑尚未确认创建结果，请重试。','Your computer has not confirmed creation. Please retry.'))}<span className="onboarding-chip">{text('我的个人助手','My personal assistant')}</span><h2>{existingAgent?.display_name || name}</h2><p className="onboarding-sub">{existingAgent && !personal.data?.creation ?text('继续交代目标、查看进展，或直接问一件过去的事。','Continue your goals, check progress, or ask about a past conversation.'):text('助手正在准备，创建信息已保存。','Your assistant is getting ready. Its setup is saved.')}</p><div className="onboarding-footer"><Link to="/settings/agents">{text('管理助手','Manage assistants')}</Link>{existingAgent && !personal.data?.creation ? <button className="onboarding-primary" onClick={()=>navigate(`/chat/${existingAgent.conversation_id}`)}>{text('打开个人助手 →','Open personal assistant →')}</button> : <button className="onboarding-primary" disabled={!personal.data?.creation || create.isPending || node?.status !== 'online'} onClick={()=>create.mutate()}>{create.isPending ? text('正在准备…','Preparing…') : text('重新准备','Retry setup')}</button>}</div></>}

          </>}
        </section>
      </div>
    </main>}
  </div>;
}
