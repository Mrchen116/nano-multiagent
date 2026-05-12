# M104 Strict Product Acceptance Playbook

## 1. 适用范围 / 前提条件

### 适用范围
本 playbook 面向“严格产品验收”场景，目标不是跑测试通过，而是站在产品经理视角，用真实用户路径判定系统是否真的可用。

适用于以下类型的验收：
- 真实 IM + 真实 Gateway + 真实 Kernel + 真实浏览器入口的端到端验收
- 重点覆盖 Web IM、Agent 创建与配置、群聊、多轮消息闭环、Heartbeat、附件、Usage 等产品能力
- 需要给出明确 verdict：哪些是“真实用户路径已通过”，哪些只是“测试/文档有证据但未完成真机复验”

### 不适用范围
- 只跑单元测试 / 集成测试的开发自测
- 只看代码 / 只看日志、不走真实浏览器路径的检查
- 以 mock API、假数据、手工伪造响应替代真实链路的“伪验收”

### 前提条件
- 已有可执行仓库与可启动环境
- 允许启动真实 IM / Gateway / Kernel 进程
- 可使用真实浏览器入口；如需自动化辅助，可用 Playwright，但浏览器路径必须指向真实产品入口
- 验收 agent 只做验收，不修代码，不修改 `data/dev-tasks.json`
- 若已有历史 runtime 与报告，必须优先复用，避免从零重建

### 严格口径
以下内容只有在真实用户路径完成后才算通过：
1. IM 与 Agent 多轮真实聊天（至少 2 轮往返）
2. Agent 新增真实链路
3. Agent 提示词修改真实链路，并验证“仅对新会话生效、旧会话不漂移”
4. 真实 Agent 群聊（多 Agent、真实 `@` 提及、`NO_REPLY` 体验）

测试、历史文档、进度记录只能辅助定位，不可替代以上四项的真实验收。

---

## 2. 必读材料清单

每次开始前先读这些材料，避免重复摸索：

### 核心规格与需求
- `/Users/czj/Repos/nano-multiagent/.worktrees/<milestone>/docs/需求.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/<milestone>/docs/operator-runbook.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/<milestone>/docs/IM-SPEC.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/<milestone>/docs/NodeGateway-SPEC.md`

### 当前 milestone 验收/进度材料
至少读：
- `/Users/czj/Repos/nano-multiagent/.worktrees/<milestone>/PROGRESS/<当前主验收进度文件>.md`
- 与当前验收面直接相关的 PROGRESS / ACCEPTANCE 文件

### M104 可直接复用的参考材料
- `/Users/czj/Repos/nano-multiagent/.worktrees/M104/ACCEPTANCE/M104-acceptance.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M104/ACCEPTANCE/M136-group-chat-evidence.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M104/PROGRESS/M135-agent-create.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M104/PROGRESS/M137-Web-IM-token-turn与附件统一路径交付.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M104/PROGRESS/M138-主-Agent与Heartbeat汇报链路产品化.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M104/PROGRESS/M140-NO_REPLY-固定字符串协议与群聊路由边界收口.md`

阅读目标不是复述文档，而是快速回答三件事：
- 这轮必须验什么
- 之前已经做到哪里
- 上一轮卡死在哪里

---

## 3. 环境准备与复用运行态策略

## 核心原则：先复用，再补齐，不要上来全量重启

本次 M104 慢的主要原因之一，是如果不先检查已有 runtime，很容易重复经历：重建数据库、重绑节点、重开浏览器、重造会话、重造 Agent、重复试错 UI。下次必须反过来做。

### Step 0：先看是否已有中间结果
优先检查：
- `/Users/czj/Repos/nano-multiagent/.worktrees/<milestone>/ACCEPTANCE/<milestone>-acceptance.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/<milestone>/ACCEPTANCE/`
- `/Users/czj/Repos/nano-multiagent/.worktrees/<milestone>/ACCEPTANCE/<runtime-dir>/`

最先确认的不是“怎么启动”，而是：
- 是否已经有验收报告草稿
- 是否已有可复用 runtime 目录
- 是否已有 DB、uploads、gateway state、node config、logs
- 是否有历史 conversation id、agent id、截图、问题结论

### Step 1：识别 runtime 是否可复用
以 M104 为例，运行态目录是：
- `/Users/czj/Repos/nano-multiagent/.worktrees/M104/ACCEPTANCE/m104-runtime`

优先检查这些文件：
- `.gateway-state.json`
- `node-config.yaml`
- `im.db`
- `uploads/`
- `gateway.log`
- `im.log`

M104 已验证过的典型内容：
- `.gateway-state.json` 中记录 Gateway PID、health URL、config path
- `node-config.yaml` 中记录复用的 node_id、agents、kernel 端口、IM 端口

### Step 2：最小健康检查顺序
按以下顺序检查，避免无效重启：

1. Gateway state 是否存在
2. Gateway PID 是否仍存活
3. Kernel health 是否正常
4. IM 服务是否还活着
5. `/im/v1/nodes` 是否存在在线节点
6. 浏览器入口 `/` 或 `/chat` 是否可打开

建议检查动作：

```bash
ls -la "/Users/czj/Repos/nano-multiagent/.worktrees/<milestone>/ACCEPTANCE"
ls -la "/Users/czj/Repos/nano-multiagent/.worktrees/<milestone>/ACCEPTANCE/<runtime-dir>"
curl -s http://127.0.0.1:<kernel-port>/v1/health
curl -s http://127.0.0.1:<im-port>/im/v1/nodes | python -m json.tool
ps -p <gateway-pid>
```

### Step 3：只重启缺失的那一段
推荐策略：
- Gateway 活着 + Kernel 健康 + IM 挂了：只重启 IM，并继续使用原 DB / uploads
- Gateway 挂了但 state/config 还在：优先按原 config 恢复 Gateway，不换 config 路径
- DB / uploads / node-config 都还在：不要新建 runtime，不要重绑，不要新造环境
- 只有在原 runtime 明确不可用时，才考虑全量重建

### Step 4：浏览器验收前先确认“可聊态”
在点开浏览器前，先确认：
- IM 首页能打开
- `/im/v1/nodes` 中目标 node 为 `online`
- 若系统有绑定机制，确认节点已归属当前用户
- 若 composer 预期应可输入，先确保不会落在 `Chat unavailable`

否则很容易把“环境没起来”误判成“产品链路有问题”。

---

## 4. 严格验收的最小步骤顺序

严格验收建议固定为以下顺序，减少来回跳转：

1. 读需求 / runbook / 相关 PROGRESS 与 ACCEPTANCE
2. 查已有验收报告与 runtime，优先 resume
3. 做最小健康检查：Gateway / Kernel / IM / node online
4. 打开真实浏览器入口 `/` 或 `/chat`
5. 先完成硬性场景 1：多轮真实聊天
6. 再完成硬性场景 2：Agent 新增
7. 再完成硬性场景 3：Prompt 修改 + 旧会话不漂移 + 新会话生效
8. 再完成硬性场景 4：群聊 + 多 Agent + `@` + `NO_REPLY`
9. 四项若都过，再继续 `docs/需求.md` 余下功能验收
10. 形成 verdict、问题清单、复验重点、follow-up milestone 草案
11. 报告落盘

### 为什么必须先做场景 1
因为场景 1 能最快确认“真实主链路是否活着”：
- Browser
- IM HTTP API
- IM relay / WebSocket
- Gateway
- Kernel
- 回写 IM
- 浏览器展示

如果场景 1 不通，后面 Agent 创建、Prompt、群聊都不值得深挖。

---

## 5. 四个硬性场景的具体验证脚本 / 检查点

## 场景 1：IM ↔ Agent 多轮真实聊天

### 最小目标
- 至少 2 轮完整往返，不是单轮
- 必须能证明不是前端假回显，不是本地 mock

### 推荐执行法
1. 打开真实 Web IM 入口：`http://127.0.0.1:<im-port>/`
2. 进入已有可用会话，或使用系统默认 starter conversation
3. 连续发送至少两条“可精确判断”的消息，例如：
   - `第二轮真实浏览器消息：请只回复“第二轮已收到”。`
   - `第三轮真实浏览器消息：请只回复“第三轮已收到”。`
4. 在浏览器中确认看到精确回复
5. 再用 IM API / DB 辅助确认 relay 与 delivered 事件存在

### 必过检查点
- Composer 可输入
- 浏览器中可见 agent 回复
- 至少 2 次 user→agent→user 可见闭环
- 有服务端证据表明消息走过 relay / completed / delivered

### 辅助证据
- `/im/v1/nodes` 在线节点状态
- `conversation_events`
- `relay_tasks.receipt_detail`
- 浏览器截图
- 会话 ID

### 失败判定
以下任何一种都不能算通过：
- 只发 1 条消息
- 只有前端即时回显，没有后端回执证据
- 只有 API 测试通过，未走真实浏览器路径
- 只看到输入成功，未看到 agent 真回复

---

## 场景 2：Agent 新增真实链路

### 最小目标
通过真实 Settings 页面创建一个新 Agent，并确认它真的落库、归属正确、可在产品中被识别。

### 推荐执行法
1. 打开真实设置页：`/settings/agents`
2. 进入真实创建页：`/settings/agents/new`
3. 创建一个新 agent，建议命名带里程碑标识，例如：`agent-m104-browser`
4. 提交后确认落到详情页：`/settings/agents/<agent-id>`
5. 用 IM API 或 DB 确认 profile 存在，且 node 绑定符合预期

### 必过检查点
- 页面是实 UI，不是 mock 静态页
- 创建动作在浏览器中真实提交成功
- 新 agent 的 detail page 可打开
- 后端能查到该 agent
- agent 所属 node / owner / profile version 正常

### 失败判定
以下情况只能算部分通过或失败：
- 只在 API 层创建，未走 UI
- UI 显示创建成功，但后端查不到 profile
- Agent 创建了，但后续产品路径无法发现它

---

## 场景 3：Prompt 修改，且仅新会话生效、旧会话不漂移

### 这是最容易“只验半套”的场景
M104 的经验是：很多时候只能证实“旧会话不漂移”，但无法证实“新会话生效”。如果后半段没有真实入口，就必须判定未完全通过。

### 推荐执行法
1. 先准备一个已有旧会话，记录当前行为基线
2. 打开 `/settings/agents/<agent-id>`
3. 修改 prompt / metadata，保存
4. 确认 profile version 增长
5. 回到旧会话，再发一条可精确判断的消息，验证旧行为未漂移
6. 再通过真实用户路径为该 agent 创建一个全新会话
7. 在新会话中发送可区分新旧 prompt 的消息
8. 确认新会话表现出新 prompt 行为

### 必过检查点
- 真实浏览器里完成编辑并保存成功
- 旧会话继续表现旧行为
- 新会话真实创建成功
- 新会话表现新 prompt 行为
- 旧 / 新会话差异可被清晰观察和记录

### 失败判定
- 只完成 prompt 保存，不算通过
- 只验证旧会话不漂移，不算完全通过
- 新会话靠改 URL、手工造 API、改数据库创建，不算“真实用户路径”

### M104 明确教训
如果聊天工作区没有“为指定 agent 开新会话”的真实入口，就不要自我安慰说“理论上应该可以”。这应直接记录为产品缺口。

---

## 场景 4：真实 Agent 群聊（多 Agent、真实 @提及、NO_REPLY）

### 最小目标
通过真实浏览器创建群聊，拉入多个 agent，在群里完成真实 `@` 提及，并验证 `NO_REPLY` 相关体验。

### 推荐执行法
1. 从真实浏览器点击 `Create group chat`
2. 在 UI 中真实选择参与者
3. 提交创建群聊
4. 在群里发送消息，分别验证：
   - 不带 `@` 的普通消息
   - 指向单个 agent 的 `@agent` 消息
   - 会触发部分 agent 沉默的消息
5. 观察多 agent 回复和沉默行为
6. 确认 `NO_REPLY` 不应以裸协议字符串泄漏给普通用户；若产品定义允许显示，也需与 spec 一致

### 必过检查点
- 群聊能从 UI 真创建，不是只弹一个空面板
- 至少 2 个 agent 真正进入同一群会话
- `@agent` 有可观察路由效果
- 沉默 agent 不制造群噪声
- 群聊消息走真实 Browser→IM→Gateway→Kernel→IM→Browser 链路

### 失败判定
- 只有“Create group chat”按钮，但无参与者选择 / 提交动作
- 只有测试文件证明有群聊逻辑，浏览器路径不可操作
- 只看日志，不看真实群聊界面

### M104 明确教训
如果真实浏览器里只看到 `Select participants` 静态面板，没有可选对象、没有创建按钮，这一项必须判失败，不可用测试证据替代。

---

## 6. docs/需求.md 余下功能的验收顺序建议

四个硬性场景过后，再按下面顺序检查其余功能，速度最快、依赖最少：

### 6.1 入口与基础可用性
- `/`、`/chat`、starter conversation 是否正常
- 节点在线态是否可见
- 绑定后 composer 是否恢复可用
- 若支持多端，最少做一次浏览器尺寸切换，确认不是只适配桌面宽屏

### 6.2 会话组织与可见性
- 用户是否能看见 direct chat / group chat
- 新创建 agent 是否可从聊天工作区被发现
- 是否能为指定 agent 发起新会话
- 用户是否能看见 agent 间协作会话

### 6.3 Agent 配置管理
- `/settings/agents` 列表
- `/settings/agents/new` 创建
- `/settings/agents/:id` 读写
- 配置变更是否只对新会话生效

### 6.4 群聊规范与 NO_REPLY
- 群创建
- participant 选择
- `@` 路由
- 不回复体验
- 群内噪声控制

### 6.5 Heartbeat 周期值班
- 是否存在 `HEARTBEAT.md` / 对应配置
- 是否能产生独立 session
- 汇报链路是否走 IM
- 没任务时是否安静跳过

### 6.6 Token / Turn 展示
- 单聊是否显示
- 群聊是否显示
- 群聊是否支持按 Agent 视角查看
- `This chat` / `Workspace total` 是否正确递增
- completion tokens 是否真实计入

### 6.7 多媒体 / 附件统一路径
- 浏览器是否能真实上传附件
- 上传后是否形成可访问统一路径
- 消息中是否带附件元信息
- Agent 是否收到标准文件路径而非临时前端对象

### 6.8 设置中心其余项
- `/settings/nodes`
- `/settings/account`
- `/settings/policies`
- 确认是否仍是 mock API，而非真实 IM API

### 6.9 只用“文档/测试证据”的区域要单独标注
若某项本轮只做了代码、测试、历史文档核对，必须明确写成：
- reviewed from doc/test evidence only
- not re-proven by fresh real user path in this run

不能混写成“已通过”。

---

## 7. 常见卡点与快速诊断办法

## 卡点 1：浏览器能打开，但 composer 不可用
优先检查：
- 节点是否 `online`
- 绑定是否完成
- Gateway 是否仍常驻
- `/im/v1/nodes` 中是否有 actionable `last_error`

### 快速判断
- `Chat unavailable` 往往先是环境/在线态问题，不一定是聊天产品逻辑问题

## 卡点 2：Gateway state 在，但实际进程没了
现象：
- `.gateway-state.json` 存在
- `ps -p <pid>` 查不到

处理：
- 视为 stale runtime
- 用原 config 恢复，不换路径，不新造 node-config

## 卡点 3：Kernel 健康，但 IM 已挂
现象：
- `/v1/health` 正常
- 浏览器打不开或 `/im/v1/nodes` 无法访问

处理：
- 只恢复 IM
- 继续沿用原 DB、uploads、config

## 卡点 4：Agent 创建通过，但聊天工作区找不到它
这通常不是环境问题，而是产品问题。

快速结论：
- “Settings 可创建”不等于“产品已完成 Agent 创建闭环”
- 若聊天工作区无法为新 agent 发起新对话，应记为 discoverability / routing 缺口

## 卡点 5：Prompt 编辑后只能验证旧会话不漂移
快速判断：
- 如果没有真实新会话入口，这不是你没点对，而是产品未闭环
- 必须判“部分通过”或“未通过”，并单列问题

## 卡点 6：群聊入口只有空壳 UI
典型现象：
- 点 `Create group chat`
- 只出现 `Select participants` 面板
- 没有 participant controls / create action

快速结论：
- 群聊严格验收直接失败
- 后续 `@` 与 `NO_REPLY` 都不应继续硬凹“理论成立”

## 卡点 7：Usage 有 UI，但数值不对
典型现象：
- `This chat` 在变
- `Workspace total` 不变或为 0
- completion tokens 一直为 0

快速结论：
- 这是产品问题，不是“展示已完成”
- 只能写“visible but incorrect/incomplete”

## 卡点 8：设置页看起来完整，但实际还是 mock
快速检查方向：
- 看页面读写结果是否真的影响 IM 数据
- 必要时核对对应 API 是否仍走 mock settings api

如果是 mock，必须明确写“未完成真实 API 化”。

---

## 8. 需要落盘的证据清单

每轮严格验收至少要保留以下证据，方便中断后续跑，不必重做：

### A. 主报告
- `/Users/czj/Repos/nano-multiagent/.worktrees/<milestone>/ACCEPTANCE/<milestone>-acceptance.md`

### B. Runtime 目录
建议固定放在：
- `/Users/czj/Repos/nano-multiagent/.worktrees/<milestone>/ACCEPTANCE/<runtime-dir>/`

至少保留：
- `.gateway-state.json`
- `node-config.yaml`
- `gateway.log`
- `im.log`
- `im.db`
- `uploads/`

### C. 浏览器证据
- 关键页面截图：主页、chat、agent detail、group chat 面板、usage strip
- 关键 URL
- 会话 ID
- agent ID

### D. API / DB 证据
- `/im/v1/nodes` 输出
- 必要时的 `/im/v1/me`、相关 conversation / profile 查询结果
- relay / event / profile version / usage 等关键字段

### E. 结论证据
- 哪些是 fresh real-path evidence
- 哪些 only doc/test evidence
- 问题清单
- retest focus
- follow-up milestone 草案

### 关键建议
截图和日志不是越多越好，重点是保留“能支撑 verdict 的最小证据”。

---

## 9. 最终 verdict 模板

下面模板建议直接复用到验收报告：

```md
# <Milestone> Acceptance

## Scope
- Worktree:
- Branch:
- Acceptance date:
- Acceptance mode: strict product-manager acceptance, prioritizing real IM + real Gateway + real Kernel + real browser path.
- Resume rule followed:

## Materials Read
- ...

## User Journeys Exercised
### A. Resume existing real runtime
- ...

### B. Real browser entry and live environment health
- ...

### C. Hard scenario 1: IM ↔ Agent multi-round real chat
- ...

### D. Hard scenario 2: real Agent creation
- ...

### E. Hard scenario 3: prompt edit + old session non-drift + new-session effect
- ...

### F. Hard scenario 4: real multi-agent group chat with @ mention / NO_REPLY
- ...

## Passes
### Strict hard scenarios
1. ...
2. ...
3. ...
4. ...

### Other product areas with real-path evidence in this run
- ...

### Other product areas with only doc/test evidence reviewed this round, not re-proven by fresh real user path
- ...

## Issues
1. ...
2. ...

## Retest Focus
1. ...
2. ...

## Suggested Follow-up Milestones
### Mxxx — <title>
- Goal:
- Exit criteria:

## Final Acceptance Verdict
- ...
```

---

## 10. 本次 M104 为什么慢，下次如何提速

## 本次慢的主要原因
1. 没先把“已有 runtime 能否复用”当成第一优先级，容易重复启动和重复造数据。
2. 容易在真实路径未打通前，就在测试、文档、代码阅读里花太多时间。
3. Prompt 修改场景天然容易只验一半；如果不先确认“有没有新会话入口”，会浪费大量点击。
4. 群聊入口的 UI 是否真正可操作，没有尽早用浏览器直接下结论，容易围绕 spec 和测试反复推断。
5. Usage、settings 等“看起来有页面”的功能，若不尽早核对真实 API / 数据变化，容易误判为已完成。

## 下次提速建议

### 先查什么
第一轮只查这 6 件事：
1. 现有 acceptance report 是否存在
2. runtime 目录是否存在
3. Gateway PID 是否活着
4. Kernel health 是否正常
5. IM 是否可访问
6. `/im/v1/nodes` 是否有在线节点

这 6 件事都清楚后，再开浏览器。

### 哪些路径不必重走
如果已有以下内容，可以直接复用，不必重来：
- 已创建的 runtime 目录
- 已存在的 node-config
- 已有的 DB / uploads
- 已确认在线的 node
- 已存在的会话 ID、agent ID
- 已写过的中间验收报告草稿

### 哪些证据可直接复用
可复用：
- 历史 PROGRESS / ACCEPTANCE 结论，用于缩小范围
- runtime 文件，用于 resume
- 之前发现的 blocker，用于优先验证

不可直接替代重新验证：
- 四个硬性场景的最终 verdict
- 新修复后的用户链路结论
- 群聊、prompt 新会话生效、usage 正确性这类强依赖当下产品状态的结论

### 哪些必须先确认，否则后面都在浪费时间
- 是否存在真实可操作的“新会话入口”
- 群聊创建 UI 是否真的有 participant 选择和 create action
- 节点是否 online
- composer 是否可输入

这几个不成立，后面很多验收项都只会变成无效点击。

---

## 11. 可选：后续沉淀为 repo 内 skill 的结构建议

如果后续要把这套流程产品化为 skill，建议采用两层结构：

### Skill 1：acceptance-resume
职责：
- 读取现有 acceptance 报告
- 检查 runtime 目录
- 输出“可复用 / 需恢复 / 需全量重建”的判断

输入：
- worktree path
- milestone id
- expected runtime dir

输出：
- runtime status summary
- resume steps
- known blockers

### Skill 2：strict-product-acceptance
职责：
- 按固定顺序跑四个硬性场景
- 再跑 `docs/需求.md` 其余功能
- 自动生成报告模板与 verdict 草案

输入：
- worktree path
- IM port
- Kernel port
- expected agent ids / conversation ids（可选）

输出：
- pass / partial / fail matrix
- issues
- retest focus
- follow-up milestone drafts

注意：
- skill 负责流程和检查点，不替代真实浏览器操作本身
- skill 可以辅助生成检查 checklist，但不能把“测试通过”冒充成“严格产品验收通过”

---

## 12. 一页版执行摘要

以后再做同类严格验收，先记住：
- 先读报告和 runtime，不要急着重启
- 先确认 Gateway / Kernel / IM / online node 都活着
- 先打通多轮真实聊天，再做其余项
- Prompt 修改必须同时验证“旧会话不漂移 + 新会话生效”
- 群聊必须能从真实 UI 创建，否则直接判失败
- 文档/测试证据只能辅助，不能替代真实用户路径
- 结论必须分清：真实通过、部分通过、只有文档/测试证据
