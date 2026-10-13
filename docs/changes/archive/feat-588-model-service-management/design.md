# feat-588: API 优先的模型服务管理 — 技术方案

> 对齐：[spec.md](spec.md)。基线 main `f8a0aab1d`；实际前置实现为 PR #337 / `7083a0936`，本 unit 以其为 stacked PR base，不自动合并或部署。

## Changelog

## 现状分析

### 涉及范围

`apps/node/src/model-setup.ts` 拥有首次接入异步操作；`configuration.ts` 保存本机 YAML，`providers.ts` 生成 DSH profile。`packages/dsh-integration/src/model-setup.ts` 使用公开 settings、credentials、authorization 和 llm 接口。`apps/im-server/src/onboarding.ts` 执行 owner 检查及输出字段投影。Web 的 onboarding 页面目前以本机代理/订阅为主，API 表单折叠，完成后没有可达的模型服务管理入口。现有配置仅新增一个全局唯一 model name，不能编辑或删除。

### 既有约束

只在 dsh-integration import DSH 公开 exports；Node 仅通过 integration/client 管理 stdio 子进程。PA/IM/Channels 不理解 DSH 配置。保留现有 Agent 主模型、备用和审批模型引用，不迁移生产配置。IM owner 检查在发送和返回 RPC 两侧均成立；新密钥不回显、不进 IM DB、日志或 YAML。

### 可复用能力

- **用**现有 node.setup.request/reply、status 轮询、设备绑定、Agent 创建、runtime supervisor、Node 原子文件写入和共享持久化队列；不新增 kernel HTTP、执行 loop 或独立设置数据库。
- **改** NativeModelSetup：目录从 `ctx.llm.listConfigurableProviders()` / `discoverModels()` 获取；新增安全快照及验证后应用事务。使用公开 credentials record API 保留/替换密钥。
- **用** DSH `0.2.1-alpha.1` 的 provider profile、catalog、credential 和 settings 接口。参考源码 `/Users/czj/Repos/opensource-hub/deepseek-harness` commit `5badb15009ae1756c3afe0ae0cef1faafc290ccc`，重点 `packages/client/ui-settings-models`、`packages/llm/llm-pi-ai`。安装后再核对锁定 exports；不引用前端私有实现。
- **不用**开发者机器的代理发现作为产品路径；自定义服务仍可手填 loopback URL。
- DSH 的单次 generate 不接受 key/baseURL 覆盖；直接用候选替换 live settings 来测试会污染已有助手。复用 RuntimeClient 创建临时、无 Agent 的 DSH 连接验证进程，验证结束销毁。

### 相关历史

feat-587 提供集中首次引导、节点安装和安全 relay，是本 unit 前置。feat-581 的 Node/DSH 边界继续有效。current spec 的 Agent 运行能力与 IM 归属规则不变，API 服务管理作为增量落入同一最窄 area。

## 架构总览

Web 共用模型服务编辑器 → IM owner relay → Node ModelSetup（目录、候选、依赖、操作）→ integration stdio（DSH 公开目录/密钥/settings/stream）。Node 拥有一个正常执行进程和按需创建、验证后立即关闭的临时探测进程；后者只发模型连接测试，不注册 Agent、不访问用户 workspace。

## 关键决策

1. **首次设置与日常设置使用同一个编辑器。** `/onboarding` 模型步骤默认展开 API 接入；`/settings/models` 常驻入口放在现有头像菜单和 Me 页，与电脑设置相邻。页面上方明确电脑与在线状态，服务列表使用名称、协议/提供商、模型数量和编辑操作，避免把 JSON 配置当产品界面。
2. **内置目录与自定义 API 是并列路径。** 内置提供商使用 DSH 默认地址、协议、模型元数据；可按需展开地址和模型编辑。自定义需显示名称、URL、协议、key 和至少一个模型。内置 provider ID 固定且不能重复添加；同一厂商多套地址/凭据用自定义服务，UI 给出入口。订阅登录保留独立次要入口，API key 编辑不覆盖 OAuth grant。
3. **模型引用与上游 ID 分开。** 新模型 `name` 为稳定 Nano 引用（服务 ID + 上游 ID），`id` 为 wire ID；现有缺少 id 的配置按 `id ?? name`，保留全部已有引用。服务名称可改，服务 ID 不改；修改上游模型 ID 视为删除旧模型并添加新模型。Agent 主模型、备用、审批模型及能力展示统一解析，避免同名模型指错服务。
4. **验证不修改正在使用的服务。** Node 创建受限权限临时 home，integration 只通过本机 stdio 把当前 API credential 交给 Node 内存用于空密钥探测；不进入任何 IM frame。探测继承需要的环境凭据，使用候选完整 profile，对新增/修改后的各模型做真实短文本调用。成功后进入 Node 既有共享写队列，先做最终 revision/依赖检查，通过后才允许 live integration stage（保存旧 profile/credential 并应用已验证候选），再原子写 YAML 和更新 Node 内存；失败在释放队列前 rollback profile/key。finish 仅释放 integration 的内存事务，不再应用配置或执行持久化。取消只在提交前生效，提交开始后返回最终结果，不显示“取消成功”却落盘。
5. **共享写队列保护已有引用，revision 阻止旧页覆盖。** status 返回持久 revision；每次 save/delete 必带打开编辑时的 revision。冲突保留草稿并提示重新载入，不能自动用新 revision 再提交。依赖检查在 ModelSetup 开始及 Node 写队列执行时发生；Agent 保存也在队列内重新 resolve，避免模型移除与 Agent 保存交叉。检查主模型、备用、空主模型使用的默认，以及 tool approval model；列出受影响助手，系统审批依赖给可理解的说明。删除未被依赖的默认模型后默认改为首个剩余模型；无模型且无依赖允许清空。
6. **范围内字段改动保留其余配置。** 更新匹配模型时保留 reasoning/extra body 等已有字段；编辑支持 ID、显示名、context window、max output tokens 和 text/image 输入能力。密钥输入留空保留；已保存仅返回 has_credential。删除服务清理其 API credential，OAuth 服务删除仅移除路由且明确保留订阅授权；不暗中注销账号。
7. **IM 指定安装版本，GitHub Releases 承担程序包下载。** 按用户 2026-10-13 的补充决定，替换 feat-587 将包文件直接交给 IM 提供的方案。IM 继续提供当前站点的安装脚本和小型 manifest；安装器直接下载 manifest 固定的 Release asset，不经 IM 代理，不查询 latest。版本配套由部署携带的 manifest 保证，不要求文件与 IM 同源。

## 接口与数据流

### 产品 RPC

复用 `POST /im/v1/nodes/:nodeId/setup`。请求动作 `status | save | remove | login | cancel`；保留旧 configure 接线直至同一前端全部切换，最终不留无调用者的兼容层。`save` 输入 `revision`、可选已有 `provider`、`service`（显示名、catalog provider 或 custom 协议/地址、模型数组）、write-only `api_key`；`remove` 输入 revision/provider。所有 mutation 同节点互斥，busy 明确返回，不静默吞新请求。请求只接收定义字段，不接受任意 DSH patch。

status 返回 `revision`、`services`（稳定 ID、显示名、来源、协议、URL、has_credential、模型的引用/上游 ID/元数据）、`catalog`（provider/displayName/models）、`models`（保留 Agent/onboarding 选择投影）、`default_model`、`workspace_base` 和 operation。catalog 使用当前运行时可配置的 llm-pi-ai API 提供商，OAuth 项单独用于登录，不把其他 DSH plugin namespace 当 API。返回目录异常时展示可重试状态，自定义入口仍可用，不谎报“没有服务”。

operation 带 id、state、可安全展示 message、可选依赖名字；polling 只覆盖服务快照，不覆盖编辑草稿和其 revision。远端错误不透传提供商原文。离线/鉴权失败保留草稿但禁用保存，恢复后先加载最新 revision 让用户明确决定重新编辑。

### 本机 integration 接口

- `model.setup.catalog`：DSH 目录和模型元数据，错误归一化。
- `model.setup.credential`：仅 Node→本机 integration 的可信 stdio 读 API record；OAuth 不返回、不复制。调用者不得把结果放入 safe snapshot。
- `model.setup.test`：临时 runtime 接收 profile、key（或使用环境凭据），用 DSH stream 测候选模型，45 秒/模型且可取消；只返回成功/失败。
- `model.setup.stage` / `finish`：stage 在最终依赖检查通过后的共享写队列内应用已验证候选或删除，并持有旧 profile/credential 以备 rollback；finish(commit=true) 仅释放内存快照，finish(false) 恢复旧 profile/key。Node 不解释 credentials record 内部持久格式。probe 在 finally shutdown/rm，启动失败也清理。
- 既有订阅登录流程保留公开 authorization device flow，不通过 API credential probe。

首次接入测试成功 → 共用列表显示已连接服务 → 选择模型继续创建助手 → 真实聊天回复。后续编辑成功 → invalidation 刷新服务与 Agent capabilities → 同一助手下一轮采用更新连接。模型服务层设置变化不重建助手或已有聊天。

### 提交临界区与失败权威

NodeConfiguration 将模型提交接入现有 persistence 队列，提供 `persistModels(next, expectedRevision, { apply, rollback })`。apply/rollback 回调由 ModelSetup 提供，配置存储不 import DSH；这是现有共享写边界的扩展，不另建锁或事务管理器。

1. 临界区入口再次核对当前 revision 和最新 Agent 主/备用/默认/审批引用。检查不通过就退出，**不调用 stage**；该节点普通 Agent 保存与模型提交共用此队列。Agent write 在队列中再次按当前 llm resolve，防止先在队列外验证后留下悬空引用。
2. 调用 apply 回调：integration stage 保存旧状态，安装已通过隔离测试的 profile/key。stage 内部发生失败时立即恢复；Node 尚未写 YAML。删除时已有依赖已稳定核对，无合法在用引用会在检查与撤路由之间插入。
3. 原子写 next YAML 成功后更新 Node 内存和持久 revision，此处为提交成功边界。若写失败，仍在队列内执行 rollback，保持旧 YAML/内存为权威；恢复结束前不释放队列给后续 Agent 保存。回滚 RPC 遇到执行子进程退出时，Node 先恢复该执行进程，再以旧 YAML 初始化配置并恢复旧凭据，未完成前不接受下一次模型提交，也不报普通成功。
4. 完成后 finish(commit=true) 只清除内存快照，不再有会导致新 YAML 失效的 settings/credentials I/O；若提交后 RPC 断开，不把已持久成功的配置报告成“验证失败”。执行进程恢复按已提交 YAML 重建，客户端通过 status/revision 对账。

隔离测试阶段始终使用旧 live 连接。提交阶段只有已验证候选可以进入 live settings；引用检查先于任何 live 删除，Node 内存的新增/移除在 YAML 成功后发布。保存失败后的权威是旧 YAML 与对应旧 profile/key，成功后是新 YAML。测试必须控制 Agent 保存先入队、模型移除后入队及相反顺序，并验证 stage 失败与 YAML 写失败均保持原引用/连接可用；不是只断言私有调用顺序。

编辑草稿携带打开时的 revision。冲突后提供“电脑上的最新配置”摘要（服务、地址、模型）与当前草稿，用户可采用最新配置，或核对后明确重新应用草稿；此时才采纳新 revision。离线只禁用保存并显示恢复入口，不销毁表单，恢复也不自动覆盖草稿。

### 安装分发

当前 `Mrchen116/nano-multiagent` 为公开仓库（2026-10-13 经 GitHub 仓库元数据核实），直接在该仓库发布，不另建分发仓库，不要求安装用户持有 GitHub token。Release 仅包含现有 allowlist 生成的程序包及非敏感版本信息；不包含用户配置、凭据或数据库。

| 所属位置 | 职责 |
|---|---|
| IM `/install.sh` | 保留当前 public URL 的安全注入、用户目录安装与绑定流程；不依赖请求 Host，不包含用户凭据。 |
| IM `/install/manifest.json` | 返回与本次 IM 部署配套的 `version`、`sha256`、`download_url`、`node_major`、`pnpm_version`；保留 `package` 文件名供旧脚本读取。响应使用 `no-store`。 |
| GitHub Releases | 在固定 tag 下提供 `nano-node.tgz`，用户电脑直接下载并校验；允许 GitHub 正常重定向到其 asset 存储域名。 |
| IM `/install/nano-node.tgz` | 已发出的旧安装脚本仍会请求此地址，改为 `302` 到同一 manifest 的固定 `download_url`，不读取或转发包体；重定向响应 `no-store`。新脚本直接读 manifest URL。 |

版本标识使用程序包构建源的完整 commit SHA，tag 为 `node-<完整 SHA>`，下载地址形如 `https://github.com/Mrchen116/nano-multiagent/releases/download/node-<完整 SHA>/nano-node.tgz`。这是发布命名约定，不表示该 Release 已存在。`download_url` 来自发布产物，只允许指定公开仓库的 HTTPS Release asset 地址；不接受浏览器传入下载地址，不使用 `/latest/download/`。同一 tag/asset 发布后不覆盖；修改包必须发布新版本。manifest 的 SHA-256 对应实际上传的包字节。

**发布与部署顺序：**

1. 发布任务针对固定 commit 构建并验证一次电脑端包，生成 SHA-256 和含完整下载地址的 manifest；沿用 `scripts/build-node-release.mjs` 的 allowlist，不引入另一套打包方式。
2. 将这个包上传到对应 tag 的 GitHub Release。发布后以匿名下载确认地址可用且 SHA-256 相同，才能将该 manifest 提升为可部署产物；失败时保留现有线上 manifest。发布权限只在发布环境使用，不分发到客户端。
3. IM 的部署产物携带该次已验证 manifest，并核对 `version` 与配套构建记录一致；部署 IM 与 manifest 作为同一版本切换。IM 不需要存放包体，也不在每次用户访问安装页面时请求 GitHub API。
4. 回退 IM 时一起恢复上一部署的 manifest，保留已发布旧 Release。已安装节点不会因此自动降级或改写数据；新安装按回退后的 manifest 选择版本。

**安装数据流：** 用户从 IM 获取脚本 → 脚本准备 Node/pnpm → 从同一 IM 获取并固定一份 manifest → 从其 `download_url` 下载到临时目录 → SHA-256 校验 → 沿用既有解压、依赖安装、完整目录提升 → 向脚本固定的 IM 执行设备绑定。GitHub 承担程序包流量；Node.js 和 npm 依赖仍使用原来的官方分发源，不经过 IM。

**失败与恢复：** manifest 缺失或格式不合法时，IM 不宣称安装器就绪。GitHub 不可达、asset 不存在或校验失败时，脚本说明失败阶段并提示重试，临时下载清理且既有安装/配置不变。不自动改取 latest、不跳过校验，也不增加由 IM/Tunnel 代理整个包的兜底；下载可达性不能据此宣称覆盖所有地区网络。

**实现与验证边界：** 修改现有 build-node-release、IM install routes、install.sh 及最窄安装测试；发布任务复用仓库实际 CI 能力实现。验证新脚本直连指定 asset、旧路径仅重定向、发布后 latest 改变不影响固定版本、错误哈希不切换版本、重装保留身份及部署回退后的 manifest。隔离测试可使用显式测试下载源模拟响应，不作为生产下载源或 GitHub 真人发布证据；真实匿名 Release 下载验收在正式发布后记录。此分发增量仍需纳入独立设计审查；实际 Release 发布与部署尚未执行。

## 前端原型

- 原型：[prototype.html](prototype.html)，包含常驻设置、首次模型步骤、内置/自定义编辑、处理中/失败/冲突/依赖/离线状态。
- 用户目标：先判断“改哪台电脑的哪个服务”，再进入有明确返回和保存反馈的编辑；不把全部服务表单堆在一个长页面。常驻列表优先辨认服务与模型，手机保持行内动作、完整名称可换行。
- 沿用 Nano 青绿强调色、顶部身份及导航，设置正文改为白底紧凑列表。移除开发者代理为主的叙述。演示控件在产品区域外。

### 2026-10-13 UI 设计修订

用户实际试用否定了此前视觉方案；原 Gate 2 的 UI 判断失效，后端边界与数据契约 retained。基线是用户给出的桌面/手机真实截图，问题在整体层级而非单一间距：过大的介绍区、独立大电脑卡片、重复章节标题、每行头像/标签/按钮争夺注意力、授权操作扩散成全页横幅。旧截图“无挤压”的结论不足以证明完成度。

参照本机 DSH `ui-settings-models` 的实际组件及样式：16px 标题、14px 服务名、紧凑行内动作、按需展开编辑。参考其主次关系和操作收敛，保留 Nano 的多电脑上下文、真实验证与草稿恢复契约。

- 日常管理以服务列表为主体，单一 22px 页面标题；去掉英文眉题和重复的大章节标题。内容宽约 736px，白底，取消大卡片套列表和无意义首字头像。
- 电脑是当前配置的归属：置于标题下紧凑上下文行，选择器与在线状态相邻；不独占一个大卡片。编辑时仍保持可辨认且禁切换。
- 每项服务两至三行：名称为主，服务类型为辅，模型名称用轻量分隔文本。编辑为常用动作，移除为低强调文字动作，点击后原有确认与依赖保护保留。手机不将动作另起一行、不使用大号标签。
- 新增/编辑保持单一编辑区，名称/连接参数、模型列表分组。内置/自定义为紧凑切换器；高级能力按需展开。桌面合理双列，手机一列；提交置于表单自然末尾，不悬浮遮挡字段。取消可回到服务列表。
- Codex 作为次要连接方式保留在列表后；授权码、打开授权页与取消只出现于该区域，标题/说明不扩成列表上方的大横幅。API 测试/失败/冲突仍贴近表单提交区。
- 桌面用户菜单的模型入口仅保留图标与名称，删除换成三行的功能说明，使用模型专用图标而非重复电脑图标。手机“我的”同样精简。

验收判断：在 390×844 的真实页面，标题、电脑、两项服务及添加/订阅入口可在正常首屏辨认；操作目标至少 36px（手机 40px），不靠极小字体换密度。1440/768/390 三宽度实际看图，并走查新增、编辑、授权和失败状态。长服务名允许换行、动作不遮挡，长模型名称不撑宽。无需改变用户已选语言或抹掉数据。

### 现有 UX grounding

基线为 feat-587 浏览器画面：`review-587-reference-model.png`（上一版原型）、`review-587-api-error-narrow.png`（真实 UI）（上一交付外部 evidence-output）。作者直接查看画面，模型步骤保留集中式向导与步骤位置；日常入口沿用当前 `app/shell/user-menu.tsx` 与 `features/me/me-page.tsx`。截图副本及原型走查见 [evidence/prototype-review.md](evidence/prototype-review.md)。

### 原型对齐契约

| 原型区域/状态 | 对齐级别 | 产品入口 | 必验 viewport/状态 | 下游投影 |
|---|---|---|---|---|
| 紧凑电脑上下文且编辑中固定；服务名称主层、类型/模型次层；无大卡套列表；手机动作同行 | must-match | settings/models | 1440/768/390，已有多服务/离线/无电脑 | M1 A |
| 单一编辑区；紧凑方式切换；连接与模型分组，提交在表单内 | must-match | onboarding + settings/models | 三宽度，空/多模型/长名称；key 空保留；已有服务厂商只读 | M1 B |
| API 反馈贴近表单；Codex 授权局限其连接区；草稿恢复动作可辨认 | must-match | 同上 | 错误贴近表单，草稿不丢，只有测试成功后继续 | M1 C |
| 控件与局部间距 | may-adapt | 同上 | 允许沿用 React 当前样式，信息层级和可读性保持 | M1 A/B |
| 演示控制、固定头像/聊天背景 | out-of-scope | 无 | 实际产品用现有账号与真实导航；不新增演示按钮 | N/A |

### 原型走查

实际渲染及代表截图记录在 [evidence/prototype-review.md](evidence/prototype-review.md)。该检查只证明设计可读可操作，产品实测另行完成。

## 契约层增量

- IM：[specs/im/agents-nodes.md](specs/im/agents-nodes.md) → current `docs/specs/im/agents-nodes.md`。
- Gateway：[specs/gateway/agent-capabilities.md](specs/gateway/agent-capabilities.md) → current `docs/specs/gateway/agent-capabilities.md`。

## 风险与回退

DSH 目录可能包含厂商特定 auth；内置 API 目录按公开 metadata 分类，只承诺目录呈现及明确测试反馈，不声称所有厂商均已真人验证。API key 和 URL 保存后的生效由真实请求验收。临时进程比 live probe 启动慢，但保持已有连接可用；仅用户测试时启动。回退本 unit 前先导出本机非敏感配置与备份，新增模型引用含 id 的配置不能让旧代码误发 namespaced wire ID；不自动回退生产。

## Runbook for Reviewer

实施 worktree 使用隔离 `.runtime/feat-588`，IM 18488、严格 key 验证 API 18489；Node identity/workspace/home 与生产隔离。所有本 unit harness 脚本在实施期创建并给出实际版本，不能把尚未运行的命令当证据。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM/Node/API | `./scripts/e2e-down.sh --wt <unit-worktree>`；独立安装节点执行 `pa stop --config <isolated-config>`；API gate 终止其记录 PID | `PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-up.sh --wt <unit-worktree>`；无模型 onboarding fixture 与 API key gate 由本 unit harness 提供，实际命令写入 M1 evidence | IM `/health`、节点在线、API gate 错误 key=401、正确 key 真实 READY |
| 构建产物 | 无 | `pnpm build`；frontend `npm run build`；按 installer 现有脚本同步包 | 受审 commit 与健康/静态入口一致 |

**Review 驱动方式**：必须真浏览器走首次 API→助手→真实回复、常驻编辑/新增多模型、错误 key 保持原助手可用、空 key 保留、同名模型分服务、依赖删除、两页 revision 冲突、离线/恢复、刷新/节点重启及 390/768/1440 布局。只读 API 辅助核对权限/secret 投影，不能替代 UI。

**验收前置**：本机现有 LLM_PROXY `127.0.0.1:4000` 提供已验证 `codexOAuth:gpt-6-luna` 实际推理。隔离 API 18489 用本 unit 测试 key 严格认证后转发真实推理，具备有效/无效 key、地址切换观察能力；不读或修改真实第三方密钥。不把这个受控 API 端点说成真人云厂商凭据验收。内置目录由锁定 DSH 真实 catalog 核实，厂商真人 OAuth/付费 key 不在必验范围；订阅登录路径保留已有覆盖。隔离 IM 注册测试账号及第二 owner 使用现有测试 bootstrap，不操作生产租户。录像在首次真实回复结束，不添加“刷新后继续”章节。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | API 接入与持续管理完整闭环 | feat-587 | 无 | apps/node、apps/im-server onboarding/install、packages/dsh-integration、product-contracts（如共享类型需要）、Web onboarding/settings/navigation、隔离 harness、installer/build/release 与 specs | [reviewer] A：电脑/服务身份、入口和三宽度的视觉组织明确（S2/S8）；B：API 优先、目录/自定义、多模型/同名服务、新增/编辑到同一助手真实回复（S1/S3/S4/S5）；C：失败/取消/冲突/依赖/离线可恢复且旧连接可用（S6/S7）；F：当前 IM 指定版本，包直下载且失败保留原安装（S9）。[worker] D：public dependency contract、配置 roundtrip、wire ID、revision/依赖写队列、credential rollback、Agent 保存/模型移除交错与 stage/YAML 失败边界、不泄露 key、隔离 probe cleanup 的窄测试与构建通过；E：留下原型与真实浏览器对照、真实推理/重启证据和安装包验证，独立门禁及 CI 通过；G：manifest 固定版本/哈希、旧路径仅重定向、错误哈希保护与发布部署顺序验证；实际 Release 发布后的匿名下载证据单独记录。 |
