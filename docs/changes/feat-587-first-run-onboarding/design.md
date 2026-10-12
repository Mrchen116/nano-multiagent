# feat-587: 托管 IM 首次使用 — 设计

> 对齐 [spec.md](spec.md)。用户明确授权自主裁决。设计日：2026-10-13。

## Changelog

## 现状分析

### 涉及范围

- IM identity/current auth 将公司 active 作为账号可用性；Messaging contacts、Work、task graphs 是公司共享视图。Node/config、会话附件等仍有 owner/participant 边界。`db.ts` 目前只执行建表脚本，需要显式增量迁移。
- `apps/node` 拥有 CLI、配置与 provider 目录，`packages/dsh-integration` 拥有唯一 DSH 公开 API 接线；已用锁定 DSH 的 RuntimeClient 初始化空 providers/agents，返回 protocol 1 / DSH 0.2.1-alpha.1 并正常关闭，空节点可启动。
- Web 注册固定跳 membership；无电脑时已有绑定提示，但缺安装器和连续首次旅程。
- 本地 Raft `05f7d8f` 提供自动检测、模型连接 UI 和可恢复引导；其 Codex driver 是独立执行引擎，不能照搬到 DSH-only 架构。
- 已安装的 DSH `0.2.1-alpha.1` / pi-ai `0.87.1` 包含 `openai-codex`、原生 OAuth 和 device-code。公开 seam：authorization、credentials、settings、llm；无需私有 import。
- LLM_PROXY `11eebf8` 是 Python 独立服务，有自己的 OAuth pool，没有 CLI credential import；`/health` 不提供模型目录。本 unit 不将 Python 代理设为新用户必装依赖。

### 既有约束

保持 Node→integration/client→stdio DSH；PA/Channels/IM 不 import DSH。安装不要求用户部署 IM，不替换已有配置、凭据或 workspace。个人自动可用不能放开现有公司资源。真栈/录屏使用隔离端口、账号、配置和工作目录。

### 可复用能力

- 用现有设备公钥证明和网页确认绑定；首次新设备省去无意义的“转移全部已有 Agent”终端确认，真正跨 owner 转移仍保留双端确认。
- 用现有 LaunchAgent/background 生命周期；安装器只负责依赖、分发和调用 setup/start，不另造 supervisor。
- 用现有 owner-authorized Gateway request/response、Agent ConfigurationOperations、聊天创建与消息接口。
- 用 DSH credentials 保存新 API key/OAuth grant，Node YAML 保存非敏感路由；旧 YAML api_key 不强制迁移。
- 用现有浅色/青绿设计、认证控件、错误反馈、React Query 和双语机制。

### 相关历史

refactor-581 建立 DSH-only 边界；feat-572/bugfix-574 建立公司访问和设备证明，保留其已有租户/转移安全语义；feat-586/相关体验规范用于整体视觉验收。历史编号以仓库已有归档为准，不把历史实现叙事代替 current。

## 架构总览

浏览器连接已运行的 IM。安装器从同一 IM 下载与服务构建匹配的电脑端代码包，在用户目录准备 Node/pnpm/依赖，生成该 IM 专属空节点配置，调用现有设备绑定和 start。电脑端通过现有出站 WS 报告状态并处理 setup RPC；DSH 在无 Agent/模型时也常驻，原生模型能力由 integration 暴露为产品级 setup 操作。

## 关键决策

1. **个人可用性与公司资格分开，资源范围固定。** users 新增 `personal_space_enabled`（旧行 0，新注册 1），既有 membership_status 保留公司 none/pending/active/suspended。`account_status` 派生为 personal enabled 或公司 active；旧 pending/suspended 保持原限制。新增注册 none + personal enabled，owner 不变，绝不授予 company admin。无空间切换器，本期返回“自己资源 + 获准公司资源”并集；新个人资源默认私有。
2. **范围记录在资源上，不随批准变化。** conversations、agent_profiles、task_graphs 新增 space_id；旧行事务回填 `company:default`，新个人行 `personal:<owner>`。Work/trajectory 继承 Agent，附件继承会话；节点/config/metrics 仍只归 owner。派生、fork、Agent 创建任务继承源空间。公司批准不移动私人历史。个人 Agent 不因 owner 获批就可跨空间主动投递/修改任务或接入公司会话。
3. **团队加入为显式动作。** `/company/join` 将 none 变为 pending；公司管理员只看到申请者/既有成员。批准 legacy pending 可激活其原账号。停用撤销当前会话和公司访问；personal enabled 用户可重新登录继续个人使用，旧公司账号保持历史停用语义。管理员操作必须同时满足公司 active 与 admin。异步 HTTP 返回、WS replay/broadcast/trajectory 持续复核资源资格。
4. **一条受支持安装器，两种表达入口。** Prompt 与手动命令调用同一安装器，绑定服务来源为 IM 配置的 public URL，不能从不可信 Host header 拼接。使用仅含发布 allowlist 的压缩包与 SHA-256 manifest，由 `scripts/build-node-release.mjs` 在构建后生成，IM `/install.sh`、`/install/manifest.json`、`/install/nano-node.tgz` 提供。包只含 package manifests/lockfile、已编译 lib、必要 assets/patch，不含 node_modules、配置、凭据、数据库、源码 worktree 或日志。没有产物时明确 503，页面不展示不可执行的成功路径。
5. **安装作用域为当前用户和目标 IM。** macOS/Linux x64/arm64，Windows 指引 WSL。不 sudo、不改 shell/global npm。已有满足版本的 Node 可复用，否则下载官方 Node 24 用户目录发行包并按官方 SHASUMS 校验；pnpm 固定仓库版本。依赖在发布目录安装；setup 创建 `~/.nanoassistant/connections/<origin-hash>/config.yaml`，固定随机 node identity。重复安装复用当前配置并确认同源；提供 `NANO_INSTALL_ROOT` 用于隔离验收。压缩包按版本/哈希目录解压，失败不覆盖已在用版本。
6. **DSH 原生接入优先。** `openai-codex` 走原生 provider 与 device-code 登录。发现本机 Codex 只呈现“检测到 Codex；为 Nano 登录一次”，不冒充凭据已复用。不给 refresh token 制造第二个刷新者。已运行 LLM_PROXY 可从显式配置路径或固定已知位置读取非敏感 profile/model 元信息，用户选择后在节点发起真实验证；不扫盘、不复制其 OAuth pool。标准 API 预置 OpenAI/DeepSeek/Anthropic，自定义兼容端点展示协议/地址/模型。模型预置从安装 catalog 获取或允许用户明确填写，不从编造版本推断。
7. **Node 是路由配置权威；DSH 是新凭据权威。** provider 配置增加显式 native/protocol 区分，native route 不强制 openai-completions/baseURL。integration 用公开 settings mutation 应用完整 provider map，credentials.modifyRecord 存放新 Key，llm 原生调用验证；通过后 Node 原子持久化非敏感模型配置。每次冷启动从 Node 配置重新调和 provider map，避免 DSH settings 覆盖 YAML。失败恢复旧 provider map；验证失败不开放下一步。编辑已有被使用 provider 不在首次设置范围，优先复用或增加新路由。
8. **长操作可查询，页面刷新不会丢失上下文。** 模型测试/OAuth 在节点内有一个当前 setup operation，开始快速返回状态，浏览器有界轮询；不把长模型调用塞入 10 秒 Gateway request timeout。登录返回 provider notice/code/link，取消可达；节点重启后仍保留已成功的凭据和路由，未完成登录回到重试。operation 错误只返回稳定类别与修复建议，不回传 upstream body/Key。
9. **首个助手提供用途引导而不预置假完成。** 日常助理/资料研究/编程搭档/自定义四种用途，名称与目标可编辑，默认 global 个人助手、独立 workspace，Heartbeat/Cron 默认关闭。通过既有 Agent 创建操作持久化，随机后缀保证全库 Agent ID 唯一；重试复用客户端保存的同一候选 ID。用途决定可编辑默认目标与建议起步任务；创建前显示节点返回的真实 workspace 路径。创建完成跳真实聊天并提供建议起步任务，建议本身不冒充模型回复；成功以真实 assistant 回复为准。

## 接口与数据流

### 空间授权

在 IM 内集中 `accountEnabled(user)`, `defaultSpace(user)`, `canAccessSpace(user, space)`, `requireSpace`, `requireCompanyAdmin` 和 actor-space 推导。保留已有 owner/participant 检查，空间检查只叠加不替代。列表、单对象读取、写入、幂等 receipt 和事件均同一语义。schema migration 以 schema_migrations/列检查在事务中幂等执行，旧 suspended 不被恢复。

### Onboarding 与 setup

- `GET /im/v1/onboarding`：本人的节点与 Agent、发布可用性和安装材料。无密钥、无别人的资源；现有已拥有 Agent 的用户不被强制引导。
- `POST /im/v1/company/join`：本人显式申请；幂等 pending/active，suspended 保持需管理员处理。
- `POST /im/v1/nodes/:node_id/setup`：owner + 当前绑定校验；限定 action `status/configure/login/cancel`，转发 `node.setup.request`。状态包括 configured models、discovered local options、operation 状态与 OAuth 公共 notice。API key 只经 HTTPS/WSS 内存转发、不写 IM SQLite、不日志打印；持久化在节点 DSH credential store，返回 projection 不含原值。
- `node.setup.request` / `node.setup`：Node 调用 integration 的 `model.setup.*` RPC。Gateway 校验回包来自请求对应的连接/epoch；HTTP 返回再次核对 owner 资格。一个节点同一时刻一个模型 mutation；重复点击复用当前 operation 或明确 busy。
- integration 直接声明依赖 `dsh-authorization`, `dsh-credentials`, `dsh-settings`, `dsh-llm-pi-ai`，使用这些包公开 exports；不导入 pi-ai 私有实现。OAuth `authorization.begin` 选择 `oauth`，原生 select 提供 device_code 时自动选它，notice 返回验证链接和 code；不启动本地 callback HTTP。
- 配置测试使用 llm 原生 stream 的单次短请求，要求得到非空文本；health/model catalog 只作候选发现。图片/tool 兼容性保留实际协议能力，不把简单文本验证声称完整所有工具验收。

### 安装 / 绑定

脚本从 manifest 读取已发布包、checksum 与版本，在本机用户目录装配；`pa setup --im-service-url <origin> [--config <private-path>]` 生成空 agents/providers 后走设备证明。浏览器绑定成功可返回 onboarding；本机新设备无需再输入 yes，已有设备跨 owner 转移保留确认。安装器输出当前步骤和恢复命令。后台节点不能依赖安装终端环境，运行路径为绝对路径并由现有生命周期保存。

### 前端路由

注册成功进入 `/onboarding`；登录按 account_status 进入，已有用户保持深链。RequireAuth 允许 account active；onboarding 页面不挂重型聊天布局，保留 Nano 标识、语言与个人空间身份。首次访问聊天的未完成个人用户可从空态继续；`/bind/confirm` 仍可直达。团队入口位于引导 header 和既有账号页，none 可主动申请、pending 显示等待并保留继续个人使用按钮。页面自动检测并恢复到最早未完成步骤，可返回查看已完成步骤。已创建 Agent 的情况下恢复进入真实聊天而非重复创建。

## 前端原型

- [prototype.html](prototype.html) 为可连续操作的四步旅程；外层明确仅演示，模拟电脑/网络事件位于产品区域之外。原型含一次性 code/link/等待/取消、无发现与已有代理、自定义协议/地址、离线和创建失败、团队申请及可继续输入的聊天交接；外层按钮模拟服务事件，不代表已经进行 OAuth。
- 目标：每步只要求一个必要决定，重要动作在当前卡片末端，失败紧邻操作；状态和恢复路径可见。电脑/模型配置信息与助手用途信息分步展开。

### 现有 UX grounding

已通过真实 Vite 页面查看 `/register`，浅灰背景、白色圆角卡片、青绿主要动作和品牌标识可辨认。保留这些设计语言；移除注册后内部公司审批强阻断，新增侧边进度、两种安装卡片、模型来源状态和用途卡片。基线截图 `output/playwright/feat-587-baseline-register.png` 为本机证据，不提交缓存。

### 原型对齐契约

| 区域/状态 | 对齐级别 | 产品入口 | viewport/状态 | M1 验收 |
|---|---|---|---|---|
| 四步层级和当前主要动作 | must-match | /onboarding | 1280/768/390 宽 | 连续理解位置、下一步和恢复；不出现聊天侧栏干扰 |
| 两种安装选择与复制反馈 | must-match | 连接电脑 | 默认/切换/复制/已连接/离线 | 同一安装目标，命令可执行、长文本不撑破屏幕 |
| 模型来源、验证与错误 | must-match | 连接模型 | 无发现/已有代理/Codex/API/失败/处理中 | 不把已发现当已验证，错误有可操作恢复，Key 不回显 |
| 团队申请 | must-match | header/账号 | none/pending | 个人使用不受申请影响，私人历史不因批准开放 |
| 用途→名称目标→电脑与文件位置 | must-match | 认识助手 | 默认/自定义/创建失败 | 减少必填、合理默认、无进阶表单占位 |
| 首次真实聊天 | must-match | 最后一步→chat | 发送/回复/重进 | 起步建议与真实回复明确，重复进入不重建 |
| 自适应排版与控件形式 | may-adapt | 全流程 | 390/768/1280 | 步骤移动到顶部，保留阅读与触控质量 |
| 模拟电脑/网络控制 | out-of-scope | 原型外层 | 仅演示 | 真实产品不存在，改为真实服务事件 |

### 原型走查

设计作者通过浏览器连续走通安装→模拟连接→模型验证→用途与名称→创建→聊天，并在 1280、768、390 宽度检查布局。R1 修订后另走通 device-code/取消、自定义协议地址/失败后重试、用途目标切换、创建失败重试、建议与自写聊天、团队申请后继续个人设置，检查 1280 授权与 390 自定义表单/聊天/团队画面。已查看安装、助手表单、窄屏和聊天画面；窄屏通过自然纵向滚动容纳表单，没有横向溢出或控件重叠。代表性图在 `output/playwright/feat-587-prototype-*.png`，原型事件均为演示。产品截图与录屏在实施阶段重新生成，不能沿用原型冒充。

## 契约层增量

- `specs/im/auth-tenancy.md`：个人可用性、显式公司申请、固定空间范围。
- `specs/im/agents-nodes.md`：首次设置、安装材料、模型连接与引导创建、设备整体交接及目录空间。
- `specs/im/agent-work.md` 与 `specs/im/task-graphs.md`：在统一空间规则下保持公司共享、补私人访问边界，保留原有场景。
- `specs/gateway/service-lifecycle.md`：空节点 bootstrap、安装与恢复。
- `specs/gateway/agent-capabilities.md`：模型配置/验证与 native OAuth 接入。
- `specs/gateway/task-graphs.md`：调用主体在固定空间内维护任务，复用 IM 的权威空间规则。

## 风险与回退

空间改动影响共享表面，必须覆盖两个私人用户、旧公司用户和批准前后矩阵，以及 legacy 库迁移。schema 为增量但旧服务不了解私人范围，产生私人数据后不能直接回滚到不支持隔离的旧服务；回退使用升级前数据库备份或修复前向版本，不允许在私人库上启动旧版本。安装失败保留旧版本与配置；不删除用户目录。OAuth 依赖账号可用性，提供 API 和既有代理替代，不假称检测即已授权。

## Runbook for Reviewer

| 服务 | 停止 | 启动 | 健康检查 |
|---|---|---|---|
| 隔离 IM/Node | `./scripts/e2e-down.sh --wt <unit-worktree>`；安装演示节点用其 config 执行 `pa stop` | `PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-up.sh --wt <unit-worktree>`；首次演示只复用此 IM，另建全新个人账号与 installer root | 本次高位端口 `/health`、owner 节点 online、真实聊天 |
| Web | 终止本次记录的 Vite PID | built frontend 由隔离 IM 同源提供；需要开发时另用高位 Vite | /register、/onboarding、/chat |

**Review 驱动方式**：真实浏览器完成注册、两种安装材料查看/复制、电脑确认、模型、助手创建和聊天；首次手动安装真实执行页面产物。本地 Agent prompt 用独立执行任务验证其指令足以驱动同一安装器，不预置助手冒充。复制录屏过程中的耗时可加章节说明。

**验收前置**：本机 Node/npm/pnpm、Chrome/Playwright、ffmpeg 可用；本地 LLM_PROXY `/health` 已读验证通过，`config/e2e/gateway.yaml` 提供不含密钥的 DeepSeek 测试 route。核心视频使用现有 loopback 代理/自定义 API 路径，OAuth 用原生 flow+可控 issuer/interaction 验证 code、取消与失败，真实第三方账号授权仅有条件验证并在报告明确边界；不伪造真人授权通过。需在真栈验证代理完成真实模型调用。生产 IM 不在隔离验证中变更。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-onboarding | 个人首次使用完整闭环 | 无 | 无 | IM 空间/installer/setup、Node bootstrap/model、integration 公开 seam、Web 引导、相关测试与文档 | [reviewer] S1–S12 与全部 must-match 在真栈可复核；视频真实注册到首个模型回复。[worker] 最低层空间矩阵、迁移、安装重复/失败、空 DSH、native/API 配置/OAuth 状态、前端交互通过；原型对照、安装/真实模型/窄屏证据，整机转移前后私人 Agent/Work 与旧会话/任务矩阵；本地 CI 和远端 CI 通过。 |
