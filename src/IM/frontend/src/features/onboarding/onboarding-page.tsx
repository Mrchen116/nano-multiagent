import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { NanoBrand } from '../../app/shell/nano-brand';
import { getCurrentLanguage, setLanguage, useTranslation } from '../../i18n';
import { useAuthStore } from '../auth/auth-store';
import { createConversation, listConversations } from '../chat/chat-api';
import { createNodeAgent, getNodeCreateState } from '../settings/agents/im-agent-config-api';
import { ModelServicesPanel } from '../settings/models/model-services-panel';
import { getOnboarding, setupNode } from './onboarding-api';
import './onboarding.css';

type Purpose = 'daily' | 'research' | 'coding' | 'custom';
const goals: Record<Purpose, [string, string]> = {
  daily: ['帮我整理资料、安排计划，持续跟进重要的事。', 'Help me organize information, make plans, and follow through on important work.'],
  research: ['帮我查找资料、比较证据，形成有来源的研究结论。', 'Help me research questions, compare evidence, and produce well-sourced conclusions.'],
  coding: ['帮我理解项目、拆解需求，验证每次修改的结果。', 'Help me understand projects, break down requirements, and verify changes.'],
  custom: ['围绕我的目标，先澄清必要信息，再一起推进。', 'Clarify what matters for my goals, then help me take the next step.'],
};
const starters: Record<Purpose, [string, string]> = {
  daily: ['帮我把这周最重要的目标整理成一份可执行计划。先问我三个必要的问题。', 'Help me turn my most important goals for this week into a practical plan. First ask me three essential questions.'],
  research: ['我想了解一个新领域。先问清我的研究问题和用途，再帮我制定查证计划。', 'I want to explore a new field. Ask about my research question and intended use, then help me plan how to verify the evidence.'],
  coding: ['我想推进一个项目。先问我项目位置、目标和当前阻碍，帮我确定第一步。', 'I want to move a project forward. Ask about its location, goal, and current blocker, then help me decide the first step.'],
  custom: ['请围绕我给你的目标，先问三个最必要的问题，再安排第一步。', 'Based on the goal I gave you, ask the three most essential questions, then help me take the first step.'],
};
/** First-run progress is reconstructed from the user's actual node and model state. */
export function OnboardingPage() {
  useTranslation();
  const language = getCurrentLanguage(), zh = language === 'zh';
  const text = (cn: string, en: string) => zh ? cn : en;
  const user = useAuthStore(s => s.user)!;
  const navigate = useNavigate(), cache = useQueryClient();
  const draftKey = `nano-onboarding:${user.id}`;
  const [draft] = useState(() => { try { return JSON.parse(localStorage.getItem(draftKey) ?? '{}'); } catch { return {}; } });
  const [candidateId] = useState<string>(() => draft.agentId ?? `assistant-${crypto.randomUUID().slice(0, 8)}`);
  const [nodeId, setNodeId] = useState<string>(draft.nodeId ?? '');
  const [purpose, setPurpose] = useState<Purpose>(draft.purpose ?? 'daily');
  const [name, setName] = useState<string>(draft.name ?? text('小助理', 'My assistant'));
  const [goal, setGoal] = useState<string>(draft.goal ?? goals.daily[zh ? 0 : 1]);
  const [viewStep, setViewStep] = useState<number | null>(null);
  const [installMethod, setInstallMethod] = useState<'agent' | 'manual'>('agent');
  const [copied, setCopied] = useState(false), [copyError, setCopyError] = useState(false);
  const [editingModel, setEditingModel] = useState(false);
  const [modelChoice, setModelChoice] = useState<string>(draft.modelChoice ?? '');
  const state = useQuery({ queryKey: ['onboarding', user.id], queryFn: getOnboarding, refetchInterval: 3000 });
  const node = state.data?.nodes.find(n => n.node_id === nodeId)
    ?? state.data?.nodes.find(n => n.status === 'online') ?? state.data?.nodes[0];
  const currentNodeId = node?.node_id;
  const setup = useQuery({ queryKey: ['node-setup', user.id, currentNodeId], queryFn: () => setupNode(currentNodeId!, { action: 'status' }), enabled: !!currentNodeId && node?.status === 'online', refetchInterval: 2000, retry: false });
  const configured = !!setup.data?.default_model && setup.data.models.some(m => m.model === setup.data?.default_model);
  const existingAgent = state.data?.agents.find(a => a.agent_id === candidateId) ?? state.data?.agents[0];
  const suggestedStep = node?.status !== 'online' ? 0 : existingAgent ? 3 : configured ? 2 : 1;
  const step = node?.status !== 'online' && viewStep !== 1 ? 0 : viewStep ?? suggestedStep;
  const selectedModel = setup.data?.models.some(m => m.model === modelChoice) ? modelChoice : setup.data?.default_model ?? '';
  useEffect(() => { if (currentNodeId && !nodeId) setNodeId(currentNodeId); }, [currentNodeId, nodeId]);
  useEffect(() => { if (viewStep === null && setup.data && !configured && !existingAgent && node?.status === 'online') setViewStep(1); }, [viewStep, setup.data, configured, existingAgent, node?.status]);
  const operation = setup.data?.operation;
  const working = operation?.state === 'waiting' || operation?.state === 'testing';
  const capabilities = useQuery({ queryKey: ['onboarding-capabilities', user.id, currentNodeId, setup.data?.default_model], queryFn: () => getNodeCreateState(currentNodeId!), enabled: step === 2 && !!currentNodeId && configured, retry: false });
  const create = useMutation({
    mutationFn: async () => {
      const c = capabilities.data?.capabilities;
      if (!node || !c || !name.trim()) throw new Error('not ready');
      return createNodeAgent(node.node_id, {
        agent_id: candidateId, owner_id: user.owner_id, display_name: name.trim(), description: goal.trim(), custom_prompt: goal.trim(),
        work_mode: 'global', workspace_root: null, group_reply_policy: 'MENTION', default_model: selectedModel,
        model_fallbacks: [], reasoning_effort: null, skills: [], skills_selection_mode: 'default_discovery',
        tool_allowlist: c.tools.filter(t => t.default_on).map(t => t.name),
        features: { ...Object.fromEntries((c.features ?? []).map(f => [f.key, f.default_on])), heartbeat: false, cron_scheduling: false },
      });
    },
    onSuccess: async () => { await cache.invalidateQueries({ queryKey: ['onboarding', user.id] }); setViewStep(3); },
  });
  const chat = useMutation({ mutationFn: async () => {
    if (!existingAgent) throw new Error('missing assistant');
    const existing = (await listConversations()).find(c => c.type === 'direct' && c.participants.some(p => p.type === 'agent' && p.id === existingAgent.agent_id));
    if (existing) return { conversation: existing, fresh: false };
    return { conversation: await createConversation({ title: existingAgent.display_name, type: 'direct', participants: [{ type: 'agent', id: existingAgent.agent_id }] }), fresh: true };
  }, onSuccess: async ({ conversation, fresh }) => {
    await cache.invalidateQueries({ queryKey: ["chat", "conversations"] });
    navigate(`/chat/${conversation.id}`, { state: fresh ? { onboardingStarter: starters[purpose][zh ? 0 : 1] } : null });
  } });
  useEffect(() => { localStorage.setItem(draftKey, JSON.stringify({ agentId: candidateId, nodeId: currentNodeId ?? '', purpose, name, goal, modelChoice })); }, [draftKey, candidateId, currentNodeId, purpose, name, goal, modelChoice]);
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
  function choose(next: Purpose) { setPurpose(next); setGoal(goals[next][zh ? 0 : 1]); }
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
          {step === 2 && <><h2>{text('你想让助手帮你做什么？', 'What would you like help with?')}</h2><p className="onboarding-sub">{text('先从一个方向开始。名字和目标之后都可以修改。', 'Start with one direction. You can change the name and goal later.')}</p>
            <div className="onboarding-choices">{(['daily', 'research', 'coding', 'custom'] as Purpose[]).map((p, i) => <button key={p} className={`onboarding-choice ${purpose === p ? 'selected' : ''}`} onClick={() => choose(p)} aria-pressed={purpose === p}><strong>{[text('日常助理', 'Everyday assistant'), text('资料研究', 'Research partner'), text('编程搭档', 'Coding partner'), text('自己定义', 'Your own purpose')][i]}</strong><small>{[text('计划、整理与跟进', 'Plan, organize, and follow through'), text('阅读、调研与归纳', 'Read, investigate, and synthesize'), text('理解项目、开发与排障', 'Understand, build, and debug'), text('按你的工作方式来', 'Adapt to how you work')][i]}</small></button>)}</div>
            <label htmlFor="onboarding-assistant-model">{text('使用的模型', 'Assistant model')}</label><select id="onboarding-assistant-model" value={selectedModel} onChange={e => setModelChoice(e.target.value)}>{setup.data?.models.map(m => { const service = setup.data.services.find(s => s.provider === m.provider); return <option key={m.model} value={m.model}>{m.display_name || m.model} · {service?.display_name || m.provider}</option>; })}</select>
            <label htmlFor="onboarding-name">{text('给助手起个名字', 'Name your assistant')}</label><input id="onboarding-name" value={name} onChange={e => setName(e.target.value)} maxLength={80} />
            <label htmlFor="onboarding-goal">{text('告诉它你的目标', 'Tell it your goal')}</label><textarea id="onboarding-goal" value={goal} onChange={e => setGoal(e.target.value)} />
            <div className="onboarding-preview"><strong>{text('工作电脑', 'Computer')}: {node?.alias || node?.node_name}</strong><p>{text('助手的独立文件夹：', 'Your assistant’s own folder:')}</p><code>{setup.data?.workspace_base ? `${setup.data.workspace_base}/${candidateId}` : text('等待电脑确认…', 'Waiting for your computer…')}</code><p>{text('需要处理其他文件时，再把位置告诉它。', 'Tell it where to find other files when you need them.')}</p></div>
            {(create.error || capabilities.error) && <>{error(text('电脑尚未确认创建结果。名称和目标已保留，重试会核对同一助手。', 'Your computer has not confirmed the result. Your name and goal are preserved; retry checks the same assistant.'))}<button className="onboarding-link" onClick={() => void capabilities.refetch()}>{text('重新检查电脑', 'Check computer again')}</button></>}
            {node?.status !== 'online' && error(text('电脑暂时离线，重新上线后即可继续。', 'Your computer is offline. Continue when it reconnects.'))}
            <div className="onboarding-footer"><button className="onboarding-link" onClick={() => setViewStep(1)}>{text('← 返回', '← Back')}</button><button className="onboarding-primary" disabled={!name.trim() || !capabilities.data || create.isPending || node?.status !== 'online'} onClick={() => create.mutate()}>{create.isPending ? text('正在创建…', 'Creating…') : create.error ? text('核对并重试', 'Check and retry') : text('创建我的助手 →', 'Create my assistant →')}</button></div>
          </>}
          {step === 3 && <><span className="onboarding-chip">{text('助手已创建', 'Assistant created')}</span><h2>{existingAgent?.display_name || name}{text('已准备好', ' is ready')}</h2><p className="onboarding-sub">{text('从一件小事开始，看看你们如何一起工作。', 'Start with a small task and see how you work together.')}</p><div className="onboarding-instructions"><strong>{text('建议从这里开始', 'A place to start')}</strong><p>{starters[purpose][zh ? 0 : 1]}</p></div><p className="onboarding-detail">{text('进入真实聊天后，这条建议会放进输入框；你可以修改它或换成自己的任务，再发送。', 'In your chat, this suggestion will be a draft. Edit it or write your own task before sending.')}</p>{chat.error && error(text('暂时无法打开聊天，请重试。助手已经保留。', 'Could not open the chat. Retry; your assistant is saved.'))}<div className="onboarding-footer"><Link to="/settings/agents">{text('管理助手', 'Manage assistants')}</Link><button className="onboarding-primary" disabled={!existingAgent || chat.isPending} onClick={() => chat.mutate()}>{chat.isPending ? text('正在打开…', 'Opening…') : text('开始第一件事 →', 'Start your first task →')}</button></div></>}
          </>}
        </section>
      </div>
    </main>
  </div>;
}
