# feat-636 — 体验方案与实施设计

> 对齐 spec.md；基线 d846b015b877。实现前形成。

## Changelog

- 2026-10-22 实施验收：模型菜单使用能力接口已有的模型/服务显示名，选择值仍是 canonical route ID；已选项完整换行。模型停止等待若本次 operation 已被后续操作覆盖，转显式最新配置核对，不等待不存在的历史槽。Web dirty 配置离开确认由详情页实际接入同一侧栏回调，保留原型中的草稿保护结果。

## 现状分析

### 涉及范围
原生 `Features/{Agents,Tasks,Me}` 与 `UI/{MarkdownView,CommonViews}`；Web `features/settings/agents/{agents-list-page,agents-rail-desktop}.tsx` 及复用入口组件与样式。原生通过 IMClient 接入现有 IM；无新后端权限或执行机制。

### 既有约束
SwiftUI 原生页面，不嵌 WebView；按用户/服务隔离凭据。模型服务 owner 管理、revision 冲突、operation 状态与依赖保护沿用现有 `/im/v1/nodes/:id/setup`。PA 固定绑定，不改变迁移与访问策略。主仓 dirty 内容不碰。用户确认前只保留本地 unit 与成果，不 push 或创建 PR。

### 可复用能力
- 用 IMClient/JSONValue、SettingsFeedback、NanoTheme、AvatarView、nanoUnsavedChanges；少量专用模型服务 wire types，避免另造网络栈。
- 模型服务接口复用 Web onboarding-api.ts：status/save/remove，catalog/services/revision/operation/error.dependencies；编辑保留模型元数据，API key 不回显、不记录；只在调用真实验证成功后显示已保存。订阅登录原有 Web 功能不扩展到本轮原生需求。
- PA 用 `/im/v1/personal-agent` 本人 binding，不靠名称或联系人 role 推定本人关系；联系人继续公开查询。
- 任务图布局与权限/分页逻辑保留，只改变呈现和视口；Markdown 保留现有 AST。

### 相关历史
feat-634 已修交互卡片与发送恢复；本轮普通 Markdown 是独立呈现路径，保留既有回归。现行 agents-nodes/personal-agent/ios-client/task-graphs/agent-work specs 是权限与业务依据。

## 关键决策与内容组织

1. **创建先表达意图。** 默认页顺序：名称、用途（通用/研究/写作，选择仅预填可编辑说明，不发送消息）、说明；设备与模型；高级设置。ID 初始自动生成，工作目录沿用节点默认；模式、ID、自定义目录和工具等高级配置折叠。用户仍可自主选择模式且看到创建后固定说明。设备未配置模型时提供同设备“模型服务”入口，返回重读能力。只保留导航栏创建按钮。
2. **模型服务是独立原生管理流程。** 我的常驻入口→本人设备→服务列表→添加/编辑；设备详情也直达同页。列表显示名称和模型，不显示密钥；编辑页持久标签、默认 API 接入、可添加多个模型、选择协议和服务商。提交后跟踪 operation，仅成功清草稿；失败/取消保留。冲突保留旧 revision，明确“读取最新配置”与“保留草稿并使用最新版本”后才允许再次提交。离线保留显示和草稿，不当作空列表。移除先确认，in_use 显示依赖助手的配置链接。界面只提供“停止等待”，停止本页轮询并保留草稿，不发送无 operation fence 的远端 cancel；提示电脑上的验证可能仍在进行。重读终态前不允许并发保存。
3. **Work 先可读结果，再诊断。** 顶部紧凑在线/主执行状态；Agent ID、session、上下文折叠。轮次标签显示现有真实内容摘要，不生成摘要或编造结果。工具默认显示已有 summary/output 字符串换行（对象则按字段可读或 JSON），原始参数/结构放“技术详情”。JSONDetailView 只负责内容，无导航副作用；需要独立标题由调用页面声明。
4. **策略不靠显示修正迁移。** 当前 Node 将 lowercased always 映射 always，其余映射 mention_only。manual 显示“仅被提及时回复”，保留原始值直到用户主动选择；兼容当前 MENTION/ALWAYS 的语义，未知/NO_REPLY 作为原配置显式显示，不新增未经运行时支持的“不回复”选项。无关保存不改变原始策略值。
5. **紧凑而不压缩正文。** 任务卡标题两行（详情可读全）、负责人/来源一行、子任务计数与入口一行，取消内部大分隔和重复行；顶部状态计数横向滚动并可定位对应组。基于已加载数据的计数标明范围。完成情况用紧凑行；结构提供总览与详情两档，总览按可用宽度缩放整图并可点击进入任务，不缩放正文阅读模式。大字号允许增高，不强求同一行。普通 Markdown 文本和列表取得完整纵向高度，代码/表格横向滚动保持。
6. **本人 PA 有固定位置。** Web Agent 列表及详情/创建/资料的 AgentsRailDesktop 复用同一入口（保留 onSelectAgent 的未保存离开拦截），在搜索之后、普通列表之前置“我的个人助手”卡，点击进入现有 `/settings/agents/:id`；iOS 同位置带头像、PA 标记和“配置”字样，直接进入 AgentConfigView。本人 PA 从下面普通列表去重；不匹配搜索时隐藏。binding 失败单独反馈并可重试，不阻塞联系人。无 PA 不冒充创建入口；既有创建流程本轮不扩展。
7. **细节保持单一主动作。** 资料/设备/策略导航栏保留保存，正文只在 dirty 时显示放弃；成功/错误留在可达反馈区。字段使用持续标签；单 Thread 改“单会话”，workspace 改“工作目录”，online 使用中文。帮助只说用户需要的推送/签名限制。任务详情“完成”关闭改“关闭”。Agent 名称和元信息允许换行。

## 接口与数据流

原生只调用既有 API：contacts 全分页→普通 Agent；personal-agent→本人 PA；setup status→非秘密快照和 catalog→revision-bound 草稿→save→轮询本次 operation→succeeded/failed/cancelled；remove 依赖由服务端权威裁决。新页面不存储 API key 到 UserDefaults/日志，离开销毁草稿；不可把 status 响应错误当空成功。

## 前端原型

[prototype.html](prototype.html) 为设计意图，非产品截图。基线画面及交互见本机 `/Users/czj/.codex/artifacts/ios-uiux-20261022/review.md`；已检查默认任务、创建、配置、Work 四幅原图，复用青绿强调色、白底内容区、身份头像与系统导航，改变信息顺序和占位。

| 区域 | 对齐 | 真实入口 / 状态 | 验收投影 |
|---|---|---|---|
| 原生创建与高级设置 | must-match | Agent→＋，390pt 默认 | 名称目的先于技术字段，展开后可编辑，M1-A |
| 原生模型服务连续路径 | must-match | 我的→模型服务→设备→编辑，正常/测试失败/冲突/离线 | 入口常驻，标签和真实反馈清楚，M1-B |
| Work 轮次与可读结果 | must-match | Agent→Work→轮次，390pt | 状态摘要小于内容，结果换行且标题不跳变，M1-C |
| 任务概览/子任务/结构 | must-match | 任务，390pt 默认和大字号 | 可比较、定位与全图入口，M1-D |
| Web 与原生 PA | must-match | settings/agents，Web1440/390、原生390 | 本人置顶区、直接配置与失败恢复，M1-E |
| 表单/消息细节 | must-match | 对应设置、聊天；默认和accessibility-medium | 文本不裁切，单主保存，持续标签，M1-F |
| 原生系统控件形态 | may-adapt | SwiftUI Form/Picker/Disclosure | 内容关系固定，系统排版适应大字号 |
| 真实后台执行与订阅授权 | out-of-scope | 原有功能保持 | UI fixture 不冒充 LLM 或外部实际交付 |

原型走查证据写入 `prototype-review.md`，渲染后再交 Gate2；真实产品还需独立验收。

## 契约层增量

`delta-spec.md` 锚定 ios-client 与 personal-agent，新增信息组织/可发现性结果；agents-nodes 的模型服务权限和失败语义不变，复用原契约；task-graphs 的分组、分页和权限不变。

## Milestone

| ID | 依赖 / 并行组 | 文件范围 | 退出标准 |
|---|---|---|---|
| M1-experience | 无 / 单阶段 | 原生 Agents/Tasks/Me/UI/Client、Web settings/agents 与相关测试、IM specs | [reviewer] A 创建意图先行；B 模型服务成功/失败/冲突/依赖/离线原生路径；C Work 可读且标题稳定；D 默认任务更紧凑并可定位/总览；E 双端本人 PA 直接配置、他人权限不扩大；F 正文/表单/文案细节；逐项同条件截图前后对比。[worker] 窄测试、构建、真实隔离 IM/Node 与模拟器/浏览器证据，完整优化点映射。 |

## Runbook for Reviewer

资源：新建隔离测试用户 nano/nano1234，专用390pt iPhone16e iOS26.4，默认large与accessibility-medium，浅/深模式；无生产账户/手机/外部凭据。fixture 使用既有公开 API 与 WebRelayConnection 提供中文长消息、任务和Work；PA 在隔离节点创建；模型连接使用仅本地隔离端点（临时测试令牌），不调用真实付费模型。

启动：worktree `pnpm install --frozen-lockfile && pnpm build`；Web 在 `src/IM/frontend` 执行 `npm ci && npm run build`；`PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-up.sh --wt <actual-wt>`，受控 tmux 会话持有；读取 .e2e-ports.env，健康检查新端口 `/health`，不得打印 JWT。原生 `NANO_IOS_BUILD_ROOT=/tmp/nano-feat636-after bash src/IM/ios/scripts/build.sh build`；`DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun simctl` 安装后以真实登录导航。Web真实浏览器使用本次IM；固定fixture同内容进行before/after。停止 `e2e-down.sh --wt <actual-wt>`，关闭自己fixture/Vite/端点/simulator并验证端口释放。

基线构建 `/tmp/nano-feat636-before`，优化构建 `/tmp/nano-feat636-after`；图片放本机 artifacts/feat-636-uiux，不提交截图缓存。测试遵循开发指南，复用既有覆盖；不为文案/颜色写镜像测试。

## 风险与回退

全是客户端；保持 API revision 和 pending 规则，密钥不回显；不同字号截图单独标注。回退本次客户端变更即可，不迁移生产数据。若真实服务与fixture语义不一致，以真实API为准修正fixture和设计，不降低验收。

## 用户追加的消息布局（2026-10-22）

用户实际截图指出气泡内名称和时间冗余。保留现有气泡/头像/颜色，将气泡内整行元信息移除：单聊省略重复名字，群聊和只读 Agent 协作的对方身份放气泡上方；时间以首条、间隔至少5分钟或跨日分隔显示，保留完整日期/时间语义。完成/已发送为正常结果不逐条显示，进行中/失败及已有用量/耗时置于气泡下方，业务状态、重试与权限保持。系统任务通知沿用已有独立呈现。基线为本轮首版 b1d926f27 的单聊/群聊原图（before22/23）与用户圈注画面，新增 [chat-metadata-prototype.html](chat-metadata-prototype.html) 的单聊/群聊和大字号对照；此局部内容关系为must-match，SwiftUI控件可适配。新增M1-G：两种会话实际截图及时间分隔/状态语义回归，产品/静态门禁按该delta局部复验，保留此前未失效结论。
