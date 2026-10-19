import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { NanoBrand } from '../../app/shell/nano-brand';
import { getCurrentLanguage, setLanguage, useTranslation } from '../../i18n';
import { useAuthStore } from '../auth/auth-store';
import { createPersonalAgent, getPersonalAgent } from '../personal-agent/personal-agent-api';
import { ModelServicesPanel } from '../settings/models/model-services-panel';
import { getOnboarding, setupNode } from './onboarding-api';
import './onboarding.css';

/** First-run progress is reconstructed from the user's actual node and model state. */
export function OnboardingPage() {
  useTranslation();
  const language = getCurrentLanguage(), zh = language === 'zh';
  const text = (cn: string, en: string) => zh ? cn : en;
  const user = useAuthStore(s => s.user)!;
  const navigate = useNavigate(), cache = useQueryClient();
  const draftKey = `nano-onboarding:${user.id}`;
  const [draft] = useState(() => { try { return JSON.parse(localStorage.getItem(draftKey) ?? '{}'); } catch { return {}; } });
  const [requestKey] = useState<string>(() => draft.requestKey ?? crypto.randomUUID());
  const [nodeId, setNodeId] = useState<string>(draft.nodeId ?? '');
  const [name, setName] = useState<string>(draft.name ?? text('小助理', 'My assistant'));
  const [goal, setGoal] = useState<string>(draft.goal ?? '');
  const [observe, setObserve] = useState(true);
  const [viewStep, setViewStep] = useState<number | null>(null);
  const [installMethod, setInstallMethod] = useState<'agent' | 'manual'>('agent');
  const [copied, setCopied] = useState(false), [copyError, setCopyError] = useState(false);
  const [editingModel, setEditingModel] = useState(false);
  const personal = useQuery({queryKey:['personal-agent',user.id],queryFn:getPersonalAgent,retry:false,refetchInterval:3000});
  const state = useQuery({ queryKey: ['onboarding', user.id], queryFn: getOnboarding, refetchInterval: 3000 });
  const node = state.data?.nodes.find(n => n.node_id === nodeId)
    ?? state.data?.nodes.find(n => n.status === 'online') ?? state.data?.nodes[0];
  const currentNodeId = node?.node_id;
  const setup = useQuery({ queryKey: ['node-setup', user.id, currentNodeId], queryFn: () => setupNode(currentNodeId!, { action: 'status' }), enabled: !!currentNodeId && node?.status === 'online', refetchInterval: 2000, retry: false });
  const configured = !!setup.data?.default_model && setup.data.models.some(m => m.model === setup.data?.default_model);
  const existingAgent = personal.data?.binding;
  const suggestedStep = node?.status !== 'online' ? 0 : existingAgent ? 3 : configured ? 2 : 1;
  const step = node?.status !== 'online' && viewStep !== 1 ? 0 : viewStep ?? suggestedStep;
  useEffect(() => { if (currentNodeId && !nodeId) setNodeId(currentNodeId); }, [currentNodeId, nodeId]);
  useEffect(() => { if (viewStep === null && setup.data && !configured && !existingAgent && node?.status === 'online') setViewStep(1); }, [viewStep, setup.data, configured, existingAgent, node?.status]);
  const operation = setup.data?.operation;
  const working = operation?.state === 'waiting' || operation?.state === 'testing';
  const create = useMutation({
    mutationFn: () => {
      if (!node || !name.trim()) throw new Error('not ready');
      return createPersonalAgent({request_key:requestKey,node_id:node.node_id,display_name:name.trim(),initial_goal:goal.trim()||undefined,observation_enabled:observe});
    },
    onSuccess: async result => {
      await Promise.all([cache.invalidateQueries({queryKey:['personal-agent']}),cache.invalidateQueries({queryKey:['onboarding',user.id]}),cache.invalidateQueries({queryKey:['chat']})]);
      if (result.binding) navigate(`/chat/${result.binding.conversation_id}`);
    },
  });
  useEffect(() => { localStorage.setItem(draftKey, JSON.stringify({requestKey,nodeId:currentNodeId??'',name,goal})); }, [draftKey,requestKey,currentNodeId,name,goal]);
  async function copy() {
    const install = state.data?.install;
    if (!install?.available) return;
    const prompt = text(
      `请帮我安装 Nano 电脑端并连接 ${install.origin}。运行这个服务的安装器：\n${install.command}\n保留已有配置、凭据和工作文件；不要部署 IM 服务。安装后打开浏览器让我确认电脑绑定，再回到网页完成模型和助手设置。不要向我索取账号密码、模型密钥或登录文件；不要改全局设置。`,
      `Install the Nano computer client and connect it to ${install.origin}. Run the service installer:\n${install.command}\nPreserve existing configuration, credentials, and work files. Do not deploy an IM server. Open the browser for me to confirm this computer, then return to the webpage for model and assistant setup. Do not request passwords, model keys, or login files, or change global settings.`,
    );
    try { await navigator.clipboard.writeText(installMethod === 'manual' ? install.command : prompt); setCopied(true); setCopyError(false); }
    catch { setCopyError(true); }
  }
  const title = [text('连接电脑', 'Connect computer'), text('连接模型', 'Connect model'), text('认识你的助手', 'Meet your assistant'), text('开始第一件事', 'Start your first task')];
  const error = (message: string) => <p className="onboarding-error" role="alert">{message}</p>;
  const next = (index: number, disabled = false) => <button className="onboarding-primary" disabled={disabled} onClick={() => setViewStep(index)}>{text('继续 →', 'Continue →')}</button>;
  return <div className="onboarding-screen">
    <header className="onboarding-topbar"><NanoBrand /><div className="onboarding-account"><span>{user.display_name} · {text('个人空间', 'Personal space')}</span><Link to="/membership">{text('加入团队', 'Join team')}</Link><div className="im-auth-language" role="group" aria-label={text('语言', 'Language')}><button onClick={() => setLanguage('zh')} aria-pressed={zh}>中</button><span>/</span><button onClick={() => setLanguage('en')} aria-pressed={!zh}>EN</button></div></div></header>
    <main className="onboarding-main"><div className="onboarding-intro"><span>{text('从这里开始', 'START HERE')}</span><h1>{text('让你的第一个助手，准备好工作。', 'Get your first assistant ready to work.')}</h1><p>{text('服务已经为你准备好了。连接自己的电脑，选好模型，告诉助手你想做什么。', 'Your space is ready. Connect your computer, choose a model, and tell your assistant what matters.')}</p></div>
      <div className="onboarding-layout"><aside><ol className="onboarding-steps">{title.map((label, i) => <li key={label} className={i === step ? 'active' : i < step ? 'done' : ''}><span>{i < step ? '✓' : i + 1}</span>{label}</li>)}</ol><p className="onboarding-note">{text('助手在你自己的电脑上工作，文件保存在该电脑。', 'Your assistant works on your computer, where its files are stored.')}<br /><br />{text('进度会自动保留，随时可以回来继续。', 'Your progress is saved. Come back whenever you are ready.')}</p><Link className="onboarding-skip" to="/chat">{text('稍后设置，先看看空间', 'Set up later, explore your space')}</Link></aside>
        <section className="onboarding-card" aria-live="polite">
          {state.isPending ? <p>{text('正在准备你的空间…', 'Loading your space…')}</p> : state.error ? <>{error(text('暂时无法读取设置进度。你的数据仍会保留。', 'Setup progress could not be loaded. Your data is preserved.'))}<button className="onboarding-secondary" onClick={() => void state.refetch()}>{text('重试', 'Retry')}</button></> : <>
          {step === 0 && <><h2>{text('把这台电脑接进来', 'Connect your computer')}</h2><p className="onboarding-sub">{text('选择你习惯的方式。两种方式都会把电脑连接到当前个人空间。', 'Choose the way you prefer. Both connect a computer to this personal space.')}</p>
            <div className="onboarding-choices">{(['agent', 'manual'] as const).map(method => <button key={method} className={`onboarding-choice ${installMethod === method ? 'selected' : ''}`} onClick={() => { setInstallMethod(method); setCopied(false); }} aria-pressed={installMethod === method}><span className="onboarding-chip">{method === 'agent' ? text('已有本地 Agent？推荐', 'Have a local agent? Recommended') : text('一条命令', 'One command')}</span><strong>{method === 'agent' ? text('交给本地 Agent', 'Ask your local agent') : text('自己动手安装', 'Install it yourself')}</strong><small>{method === 'agent' ? text('复制说明，让 Codex、Claude Code 等帮你安装。', 'Copy instructions for Codex, Claude Code, or another local agent.') : text('在电脑终端粘贴运行，按提示确认连接。', 'Paste into a terminal and confirm the computer in your browser.')}</small></button>)}</div>
            {state.data?.install.available ? <div className="onboarding-instructions"><p>{installMethod === 'agent' ? text('把安装说明发给电脑上的 Agent。它会完成安装，在需要时请你确认。', 'Send the instructions to your local agent. It will install Nano and ask you to confirm the computer.') : text('在要运行助手的电脑上打开终端，粘贴运行：', 'Open a terminal on the computer that will run your assistant:')}</p><code>{state.data.install.command}</code><button className="onboarding-secondary onboarding-copy" onClick={() => void copy()}>{copied ? text('已复制，请到电脑上继续', 'Copied. Continue on your computer.') : installMethod === 'agent' ? text('复制安装说明', 'Copy agent instructions') : text('复制安装命令', 'Copy install command')}</button>{copyError && error(text('无法自动复制，请选中上方命令手动复制。', 'Clipboard is unavailable. Select and copy the command above.'))}</div> : error(text('管理员尚未发布电脑端安装包，请稍后刷新。', 'The computer installer has not been published yet. Please refresh later.'))}
            <p className="onboarding-detail">{text('支持 macOS / Linux。Windows 请在 WSL 中运行。无需安装 IM 服务。', 'Supports macOS and Linux. Use WSL on Windows. No IM server installation needed.')}</p>
            {state.data && state.data.nodes.length > 1 && <label>{text('选择电脑', 'Choose computer')}<select value={currentNodeId} onChange={e => setNodeId(e.target.value)}>{state.data.nodes.map(n => <option key={n.node_id} value={n.node_id}>{n.alias || n.node_name}</option>)}</select></label>}
            <p className={`onboarding-status ${node?.status === 'online' ? 'ok' : ''}`} role="status"><span />{node ? `${node.alias || node.node_name} · ${node.status === 'online' ? text('已连接', 'Connected') : text('暂时离线', 'Offline')}` : text('等待电脑连接… 安装完成后会自动更新', 'Waiting for your computer… This updates after installation.')}</p>
            {node?.status !== 'online' && node && <p className="onboarding-detail">{text('在该电脑重跑上方命令即可恢复。已有身份、配置和文件会保留。', 'Run the command on that computer again to reconnect. Your identity, settings, and files are preserved.')}</p>}
            {node?.status === 'online' && <div className="onboarding-footer"><span />{next(configured ? 2 : 1)}</div>}
          </>}
          {step === 1 && <><h2>{text('给助手接通一个模型', 'Connect a model')}</h2><p className="onboarding-sub">{text('选择你使用的服务商，填写 API Key，测试成功后即可创建助手。', 'Choose your provider, enter an API key, and verify the connection before creating your assistant.')} · {node?.alias || node?.node_name}</p>
            {node && <ModelServicesPanel key={node.node_id} node={node} initialAdd onEditingChange={setEditingModel} />}
            <div className="onboarding-footer"><button className="onboarding-link" onClick={() => setViewStep(0)}>{text('← 返回', '← Back')}</button>{next(2, !configured || working || editingModel || node?.status !== 'online')}</div>
          </>}
          {step === 2 && <><h2>{text('你想让助手帮你做什么？', 'What would you like help with?')}</h2><p className="onboarding-sub">{text('给它一个名字，有想推进的事情可以一起交代。','Give it a name and, if you like, a goal to start with.')}</p>
            <label htmlFor="onboarding-name">{text('给助手起个名字', 'Name your assistant')}</label><input id="onboarding-name" value={name} onChange={e => setName(e.target.value)} maxLength={80} />
            <label htmlFor="onboarding-goal">{text('最近想推进什么？（可选）', 'What would you like to work on? (optional)')}</label><textarea id="onboarding-goal" value={goal} onChange={e => setGoal(e.target.value)} />
            <label style={{display:'flex',gap:8,alignItems:'center'}}><input type="checkbox" style={{width:'auto'}} checked={observe} onChange={e=>setObserve(e.target.checked)}/>{text('了解我的聊天与任务，主动跟进','Follow my conversations and tasks')}</label>
            <p className="onboarding-detail">{text('助手可按需查询你有权查看的已参与聊天，相关资料由你配置的模型处理。你随时可以暂停观察或排除聊天；PA 看过不代表你已读。','Your assistant can look up conversations you participated in and can still access. Your configured model processes relevant information. Pause observation or exclude chats anytime; your assistant does not mark messages read for you.')}</p>
            {create.error && error(text('电脑尚未确认创建结果。名称和目标已保留，重试会核对同一助手。','Your computer has not confirmed creation. Your name and goal are preserved; retry checks the same assistant.'))}
            {node?.status !== 'online' && error(text('电脑暂时离线，重新上线后即可继续。', 'Your computer is offline. Continue when it reconnects.'))}
            <div className="onboarding-footer"><button className="onboarding-link" onClick={() => setViewStep(1)}>{text('← 返回', '← Back')}</button><button className="onboarding-primary" disabled={!name.trim() || !configured || !personal.isSuccess || create.isPending || node?.status !== 'online'} onClick={() => create.mutate()}>{create.isPending ? text('正在创建…', 'Creating…') : create.error ? text('核对并重试', 'Check and retry') : text('创建并开始合作 →', 'Create and start →')}</button></div>
          </>}
          {step === 3 && <><span className="onboarding-chip">{text('我的个人助手','My personal assistant')}</span><h2>{existingAgent?.display_name || name}</h2><p className="onboarding-sub">{existingAgent?.status==='active'?text('继续交代目标、查看进展，或直接问一件过去的事。','Continue your goals, check progress, or ask about a past conversation.'):text('助手正在准备，创建信息和目标已保存。','Your assistant is getting ready. Its setup and goal are saved.')}</p><div className="onboarding-footer"><Link to="/settings/agents">{text('管理助手','Manage assistants')}</Link><button className="onboarding-primary" disabled={!existingAgent} onClick={()=>existingAgent&&navigate(`/chat/${existingAgent.conversation_id}`)}>{text('打开个人助手 →','Open personal assistant →')}</button></div></>}

          </>}
        </section>
      </div>
    </main>
  </div>;
}
