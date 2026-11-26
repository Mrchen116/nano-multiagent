import { AssistantIllustration } from "../chat/components/avatar";
import { Laptop, KeyRound } from 'lucide-react';
import { Link } from 'react-router-dom';
import { getCurrentLanguage, useTranslation } from '../../i18n';

/** Explain the first-use outcome and prerequisites before asking for installation. */
export function OnboardingWelcome({ name, onStart }: { name: string; onStart(): void }) {
  useTranslation();
  const text = (zh: string, en: string) => getCurrentLanguage() === 'zh' ? zh : en;
  return <main className="onboarding-welcome">
    <section className="onboarding-welcome-copy">
      <span className="onboarding-card-eyebrow">{text('账号已就绪，欢迎加入 Crewden', 'Your Crewden account is ready')}</span>
      <h1>{text(`${name}，让助手加入你的日常。`, `${name}, make room for your assistant.`)}</h1>
      <p className="onboarding-welcome-lead">{text('把零散想法理清，把一件想做的事往前推。从一句话开始，慢慢找到你们的合作方式。', 'Untangle an idea or take the next step on something you care about. Start with a conversation and find your way of working together.')}</p>
      <div className="onboarding-welcome-prep"><h2>{text('开始前，准备好两样东西', 'Two things to have ready')}</h2>
        <p><span aria-hidden="true"><Laptop /></span><span><strong>{text('一台可以保持在线的电脑', 'A computer you can keep online')}</strong><small>{text('安装 Crewden 电脑端，供助手执行任务、保存工作文件。', 'Install the Crewden computer client so your assistant can run tasks and keep work files.')}</small></span></p>
        <p><span aria-hidden="true"><KeyRound /></span><span><strong>{text('一个可用的模型服务', 'Access to a model service')}</strong><small>{text('使用 API 密钥或支持的订阅授权。模型费用由对应服务商收取。', 'Use an API key or a supported subscription. Model costs are charged by your provider.')}</small></span></p>
      </div>
      <button className="onboarding-primary" onClick={onStart}>{text('设置我的助手', 'Set up my assistant')} <span aria-hidden="true">→</span></button>
      <Link className="onboarding-welcome-skip" to="/chat">{text('先进入空间看看', 'Explore my space first')}</Link>
      <p className="onboarding-welcome-resume">{text('连接电脑 → 连接模型 → 为助手命名。可以中途离开，回来继续。', 'Connect a computer, connect a model, then name your assistant. You can leave and continue later.')}</p>
    </section>
    <aside className="onboarding-welcome-preview" aria-label={text('个人助手使用示意', 'Illustration of using an assistant')}>
      <div className="onboarding-preview-label">{text('设置完成后 · 使用示意', 'After setup · Illustration')}</div>
      <div className="onboarding-pa-preview"><div className="onboarding-pa-preview-header"><span aria-hidden="true"><AssistantIllustration size={32} /></span><div><strong>{text('你的个人助手', 'Your personal assistant')}</strong><small>{text('与你的私人对话', 'A private conversation with you')}</small></div></div>
        <div className="onboarding-preview-user">{text('这周的发布要延期了，帮我跟进相关讨论，整理还有哪些事要做。', 'This week’s release is delayed. Follow the relevant discussions and help me work out what still needs doing.')}</div>
        <div className="onboarding-preview-reply"><span aria-hidden="true"><AssistantIllustration size={32} /></span><p>{text('我们可以先明确要跟进的聊天和目标，再持续整理变化与下一步。', 'Let’s identify the conversations and goal, then keep track of changes and next steps.')}</p></div>
      </div>
      <div className="onboarding-welcome-role"><strong>{text('先有自己的助手，再一起协作', 'Your assistant first. Collaboration when you need it.')}</strong><p>{text('个人助手长期为你服务；承担专业职责的数字员工是你的协作伙伴。以后可以在聊天里把相关的人与数字同事 聚到一起。', 'Your assistant works for you over time. Digital coworkers take on professional roles. Bring the right people and Agents into a conversation when you need them.')}</p></div>
      <p className="onboarding-preview-caption">{text('这是使用示意，尚未创建助手或执行任务。', 'This is an illustration. No assistant has been created or task run.')}</p>
    </aside>
  </main>;
}
