# M1-fix Evidence: Web PA Creation Rollback & Pending Recovery Journey

## Claim

1. 当个人助手（PA）创建处于未确认 `pending` 状态（含历史遗留孤儿 `pending` 记录）时，Web 聊天工作区（桌面 `1280×820` 与移动端 `390×844`）不再把未建成的 `conversation_id` 当作已激活私聊导航，零触发 `/im/v1/conversations/:id` 404 与“聊天不可访问”报错。
2. 聊天侧栏置顶项展示已保存的助手名称（“酷狗”）与副标题“继续设置助手”；点击后在当前页弹出恢复弹窗（底部次按钮“稍后” + 主按钮“重新准备”）；Agents 页展示“助手设置中 · 继续设置助手”链接。
3. 在线 Gateway + DSH 节点就绪后，点击“重新准备”完成真实节点 `agent.create`、写入 `agent_profiles` 与 `conversations`，并自动导航进入 `/chat/:id` 主人私聊（展示首次合作小任务引导），同时 Agents 页“我的个人助手”优先区正常显示“酷狗”。

## Environment & Method

- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/bugfix-823-pa-creation-recovery` (`unit/bugfix-823-pa-creation-recovery`, base `origin/develop` `e82150da2`)
- Isolated Stack: `./scripts/e2e-up.sh --wt <ephemeral-wt>`（独立高位端口、独立 SQLite `data/im_service.sqlite3`、独立 `.gateway-config.yaml` 与 `.gateway-workspace/`，同源生产构建前端）
- Browser Driver: Headless Chromium via Playwright（`zh-CN` / `im_lang=zh`，覆盖桌面 `1280×820` 与移动 `390×844`）
- Verification Flow:
  1. 登录隔离测试账号 `nano`；
  2. 在隔离库注入复现 Issue J 的未完成绑定（`binding_id='b_issue_j'`, `agent_id='pa_issuej000001'`, `conversation_id='c_issuej_missing'`, `display_name='酷狗'`, `status='pending'`，且 `conversations` 与 `agent_profiles` 均无对应记录）；
  3. 依次访问 `/chat`（桌面与移动端）、点击置顶项打开恢复弹窗、访问 `/settings/agents`，监听全程网络响应确认在激活前未请求 `/im/v1/conversations/c_issuej_missing`；
  4. 回到 `/chat` 点击置顶项并点击主操作“重新准备”，等待真实 Gateway 节点完成创建并跳转 `/chat/c_issuej_missing`，再回查 `/settings/agents` 与 SQLite 持久化记录；
  5. 执行 `./scripts/e2e-down.sh --wt <ephemeral-wt>`，校验端口无监听并移除临时运行目录与本地 `src/IM/frontend/dist`。

## Result & Locators

- **激活前 `/chat` 侧栏与弹窗**：
  - 置顶项文本：`酷狗 / 继续设置助手`；
  - 点击置顶项未发起 `/im/v1/conversations/c_issuej_missing` 请求，页面无“聊天不可访问”提示，弹出恢复对话框（状态文案“助手尚未准备完成，创建信息已保留。”，底部“稍后” + 主按钮“重新准备”）。
- **激活前 `/settings/agents`**：
  - 顶部状态条显示 `助手设置中 继续设置助手`（链向 `/onboarding`），普通测试助手列表正常可用。
- **点击“重新准备”真实节点恢复后**：
  - 浏览器自动跳转 `/chat/c_issuej_missing`（HTTP `200`），进入“和酷狗，从一件小事开始。”首次私聊引导页；
  - `/settings/agents` 顶部“我的个人助手”优先区展示 `酷狗`；
  - SQLite 核对：`personal_agent_bindings.status = 'active'`，`conversations` 已创建 `id = 'c_issuej_missing'`（`space_id = 'personal:<owner>'`, `config_agent_id = 'pa_issuej000001'`），`agent_profiles` 已创建 `pa_issuej000001`（`work_mode = 'global'`）。
- **截图原件定位（仓外临时目录，不入库）**：
  - `/Users/czj/.t3/userdata/providers/antigravity/ac0a3dfd6dddb20962cecff6ee5fe65e19d3923be20e52c5ab52ff877f7e4c32/antigravity-acp/brain/c1fcbb54-8da0-45bc-b23b-00fed7231944/scratch/e2e-pa-journey/01-chat-pending-desktop.png`
  - `/Users/czj/.t3/userdata/providers/antigravity/ac0a3dfd6dddb20962cecff6ee5fe65e19d3923be20e52c5ab52ff877f7e4c32/antigravity-acp/brain/c1fcbb54-8da0-45bc-b23b-00fed7231944/scratch/e2e-pa-journey/02-chat-pending-recovery-dialog.png`
  - `/Users/czj/.t3/userdata/providers/antigravity/ac0a3dfd6dddb20962cecff6ee5fe65e19d3923be20e52c5ab52ff877f7e4c32/antigravity-acp/brain/c1fcbb54-8da0-45bc-b23b-00fed7231944/scratch/e2e-pa-journey/03-chat-pending-mobile.png`
  - `/Users/czj/.t3/userdata/providers/antigravity/ac0a3dfd6dddb20962cecff6ee5fe65e19d3923be20e52c5ab52ff877f7e4c32/antigravity-acp/brain/c1fcbb54-8da0-45bc-b23b-00fed7231944/scratch/e2e-pa-journey/04-agents-pending-desktop.png`
  - `/Users/czj/.t3/userdata/providers/antigravity/ac0a3dfd6dddb20962cecff6ee5fe65e19d3923be20e52c5ab52ff877f7e4c32/antigravity-acp/brain/c1fcbb54-8da0-45bc-b23b-00fed7231944/scratch/e2e-pa-journey/05-chat-recovered-active-desktop.png`
  - `/Users/czj/.t3/userdata/providers/antigravity/ac0a3dfd6dddb20962cecff6ee5fe65e19d3923be20e52c5ab52ff877f7e4c32/antigravity-acp/brain/c1fcbb54-8da0-45bc-b23b-00fed7231944/scratch/e2e-pa-journey/06-agents-recovered-active-desktop.png`

## Resource Cleanup

- 临时隔离栈已通过 `scripts/e2e-down.sh` 停止，确认监听端口释放、PID 文件清除，临时运行目录与 `src/IM/frontend/dist` 已删除。

## Limits

- 本轮隔离浏览器验证聚焦 Web / Desktop 共享前端与真实 IM + Gateway + DSH 创建恢复主链路；原生 iOS 已由既有 `creation == nil` 守卫覆盖（见 `fix.md` 豁免说明）。
