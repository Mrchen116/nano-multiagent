# Code Review

## Round 1 — full

- reviewer_target: `/root/uiux_static_gate`（未参与受审实现的独立 reviewer）
- review_mode: `full`
- scope: `origin/main` / HEAD `d846b015b8774461bb26b172e458443ce1eb071d` 到本轮冻结 working tree；含全部 18 个 tracked 产品/测试 diff，以及 untracked `personal-agent-entry.tsx`、`ModelServiceModels.swift`、`ModelServicesView.swift`、`ModelServiceContractsTests.swift`。未把未提交或 untracked 漏出受审范围。
- branch: `unit/feat-636-ios-uiux-polish`
- started_at: `2026-10-22T10:50:00+08:00`
- completed_at: `2026-10-22T10:58:00+08:00`
- verdict: **Issues Found — 2 CONFIRMED / 0 PLAUSIBLE**

## Coverage 与证据

已读 AGENTS、unit spec/design/delta、Gate 2 R3 Approved，以及 current iOS、PA、agents-nodes 与实际调用链。覆盖模型 setup wire/metadata/key/revision/operation、停止等待与冲突整份替换、依赖助手链接；PA 本人 binding、公开联系人权限/全分页、搜索/去重/失败隔离、Web 两个 rail 的 `onSelectAgent`；创建默认 ID、pending、能力与聊天路由；Markdown 完整文本、JSON 内嵌/独立页面；任务密度/状态计数/fit 图/权限与原分页/owner 逻辑；表单与群策略原值保留。

复用 caller 的 frontend 相关 2 文件 9 测试、frontend build 与全量 102 文件 951 测试结果；模型原有 3 契约测试和真实隔离 status 解码证据适用。未重复全量测试。独立 `git diff --check` 通过。构建和真实 GUI 尚由 caller 执行，本报告不将未完成的产品验收当作代码 finding。

针对 F1 独立在仓外 `/tmp/nano-feat636-static-review` 复制原窄 package，使用受审最新 `ModelServiceModels.swift`、真实 IMClient/Session/Transport seam 及单一可控 transport 增加一个临时复现：`completedForeignOperationLeavesStoppedOwnOperationUnrecoverable`。`DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer swift test --package-path /tmp/nano-feat636-static-review --filter completedForeignOperationLeavesStoppedOwnOperationUnrecoverable` 通过（1 测试，0.006s），直接确认固定 B 终态后的重读、keepDraft 与 closeEditor 均仍 `trackedID=own`、`pending=true`、`canWrite=false`。Node `apps/node/src/model-setup.ts:29,67,117,163` 证实只保存当前 operation，不提供 A 的历史回查；不是凭空假设服务器可返回任意状态。

F2 由原/新搜索谓词与去重条件直接成立；iOS 搜索框明确承诺设备匹配。未为此重跑镜像测试或操作浏览器。

## Findings

```json
[
  {
    "file": "src/IM/ios/NanoIM/Features/Me/ModelServiceModels.swift",
    "line": 262,
    "summary": "[P2] 为已被后续操作覆盖的本页 operation 提供显式恢复",
    "failure_scenario": "在模型页提交 A 后点击“停止等待”；A 在电脑上完成，另一个 Web/手机页面随后提交并完成 B。Node ModelSetup 只保留一个 this.operation，之后 status 永远返回 B，不再返回 A。本页 receive() 只接受 trackedID==operation.id 才能清理 trackedID，因此 pending 永远为 true、canWrite 永远 false；重读、冲突比较/保留草稿乃至放弃回列表都不能恢复本页，添加/编辑/移除一直被禁用。不能把 B 成功当 A 成功，但需要显式核对最新配置后解除旧跟踪的恢复动作。现有测试的 foreign B 后再次返回 own A 不符合 Node 单 operation 槽的实际序列。",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "src/IM/ios/NanoIM/Features/Agents/AgentsView.swift",
    "line": 24,
    "summary": "[P2] PA 优先区去重时保留原有联系人搜索字段",
    "failure_scenario": "本人 PA 联系人名为“小助理”、设备名为“Mac mini”，用户按搜索框提示输入“Mac mini”：filtered 会匹配该联系人，但 regular 无条件将本人 PA 移除；personalMatches 只查 binding 名称/ID/个人助手标签，最终本人 PA 完全消失。Web 同根问题位于 personal-agent-entry.tsx:22 和两个组装列表：原搜索包含 public-agents.ts 映射的 owner_display_name（description），本人 PA 去重后优先卡缺少该字段，按本人姓名搜索也丢失原有匹配。应让优先卡复用同一联系人的原有可搜索字段，再按身份去重。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

## 其他结论与边界

未发现密钥回显/空值覆盖、模型元数据丢失、冲突整份替换串用草稿、依赖链接指向错误助手、PA 公共可见性提升管理权限、Web 离开拦截绕过、JSON 展开改变父导航标题或任务查询权限/分页回归的存活问题。创建后聊天通过既有 root `OpenURLAction` 处理，未误判为外开浏览器。

只写本报告，未修改产品/设计/测试，未提交、部署、操作模拟器/浏览器或服务。verifier 报告等待 caller 最终证据后单独执行；本轮不替代产品旅程验收或用户效果确认。


## Round 2 — closure + targeted delta

- reviewer_target: `/root/uiux_static_gate`（同一独立 reviewer）
- review_mode: `closure`（F1/F2），并审查关联 `agent-detail-page.tsx/.test.tsx` delta。
- scope: R1 之后的 operation 覆盖恢复、PA 搜索字段复用及新接入的桌面详情页 PA 离开保护。其余冻结实现、current 契约与 R1 覆盖继续有效；未扩大为重复 full，也未开始 verifier。
- completed_at: `2026-10-22T11:19:00+08:00`
- verdict: **Approved — 0 surviving findings**

### Focus finding closure

| Finding | 状态 | 独立复核 |
|---|---|---|
| R1-F1：旧 operation 被后续覆盖后永远 pending | closed | `receive` 在明确收到不同 ID 时释放旧 tracker，保留草稿、设置 needsReview，清空 comparison；B 仍运行时 pending 保持阻止写入，B 终态后也必须通过最新 comparison 的人工 keep/replace 才能保存。没有把 B 的成功写成 A 的成功，也不再等不可能回查的 A 历史。新测试使用实际单槽的 A testing → B testing → B succeeded，核对草稿、pending、review、revision 与恢复；原停止等待/本人失败/重试成功另行保留。 |
| R1-F2：本人 PA 去重后丢失既有搜索匹配 | closed | iOS 优先卡用已过滤 contacts 的本人命中补充 binding 搜索，设备名匹配保持；Web 两个组装入口均把同一 PA 联系人的 description 传给共享卡，owner 搜索得到保留。去重仍按本人 binding ID，不扩大他人权限；新增 owner 搜索断言覆盖真实 list 组装。 |

### 关联 delta 审查

独立阅读 `AgentDetailPageContent` 的新增 `pendingAgent/selectAgent`、两处 `AgentsRailDesktop` 接线及确认 modal；点击本人 PA 与普通 rail 条目都经过 callback。dirty 时只记录目标，继续编辑清空目标且不改 draft，明确离开才 navigate；按钮 `type=button`，不会触发表单保存。目标路由编码保留，页面按 agentId key 重建，切换后不会携带旧 pending 状态。新增真实组件测试核对未立即 navigate、继续编辑保留名称、明确离开才导航、且没有自动保存。未发现本 delta 的新增存活问题。

复用并亲自查看 `/tmp/nano-feat636-web-dirty-red.log` 的回归前失败证据及 `/tmp/nano-feat636-web-final-related.log` 的 detail/list/rail 3 文件 34 测试通过结果；`/tmp/nano-feat636-web-build3.log` build 成功。`/tmp/nano-feat636-ios-test2.log` 是 Xcode 全 suite 21 测试 / 4 suites、TEST SUCCEEDED，覆盖更新后的模型测试。R1 frontend 全量结果只对未受影响范围保留，不冒充这些后改动的全量重跑。独立 `git diff --check` 通过，没有重跑已有效的完整测试。

### Findings

```json
[]
```

### 边界

只追加本报告，未修改产品/设计/测试、未提交、未操作模拟器/浏览器或服务。完整 GUI/gallery 和用户效果确认仍由 caller 继续；本报告不代替产品验收，full/corrected-delta verifier 等最终证据另行执行。


## Round 3 — targeted delta：模型标签与区域语言值

- reviewer_target: `/root/uiux_static_gate`
- review_mode: `patch`（caller 冻结的 R2 后模型显示名与 Me locale 补正 working-tree delta）
- completed_at: `2026-10-22T11:43:00+08:00`
- verdict: **Approved — 0 surviving findings**

独立核对 `AgentModelOption` 新增可选 `display_name/provider_display_name` 以及 `AgentEditorFields` 主模型 Menu、平台默认与备用模型标签。`apps/node/src/capabilities.ts:52–53` 已返回这两个字段；客户端不新增模型协议。标签可换行，菜单 tag、识别、推理解析及提交仍用 canonical `name`；没有将显示名当作路由提交。既有 AgentContracts 测试扩展 wire metadata 断言，同时保留 route ID 断言，归属和 seam 合适。

`SettingsAccountView` 的两行 Picker tag 使 `zh-CN/en-*` 等当前区域值匹配相应可见语言，未交互时不主动规范化或改变草稿；用户主动换语言时才切到另一基础值。既有保存/重置/dirty 行为保持，没有新增后端或状态层。

亲自查看 `/tmp/nano-feat636-ios-after4.log` BUILD SUCCEEDED 及 `/tmp/nano-feat636-ios-test4.log` 最终 TEST SUCCEEDED（21 tests / 4 suites，11:39:24）；test4 包含本轮 locale 补正，不把此前 test3 当作最终源码验证。未为两个标签 tag 写框架镜像测试，依赖现有 wire/设置契约与 caller 的真实截图复验。R1/R2 结论继续有效；未再运行全量实现审查。

```json
[]
```

只追加代码审查报告；full/corrected-delta 结果单独写 verification.md。未操作共享模拟器、浏览器或服务，未修改产品/设计/测试。


## Round 4 — targeted delta：用户追加聊天元信息分层

- reviewer_target: `/root/uiux_static_gate`
- review_mode: `patch`，受审范围为 `b1d926f27` 后 caller 冻结的 `ChatModels.swift`、`ConversationView.swift`、`ChatMessageView.swift`、`TimelineTests.swift` diff；没有重新打开此前已覆盖实现。
- completed_at: `2026-10-22T12:09:55+08:00`
- verdict: **Approved — 0 surviving findings**

已读用户新增原话/spec Requirement、design M1-G、Gate2 Round4 Approved 与新增 ios-client delta。时间分隔由完整已加载 timeline 的呈现层计算，首条普通消息、相邻至少300秒、跨所选 calendar 本地日期时标记；配置boundary和system_notice不改变前一条普通消息。nanoDate保留原分数秒/非分数秒解码，历史加载后整组重新计算，不依赖陈旧分隔缓存。今天显示时分、历史显示完整年月日及时间，与设计语义一致。

ConversationView 仅在 group 或 is_observer 时传递名字显示开关，observer direct 没有误按单聊隐藏双方Agent身份；消息视图仅将对方普通消息名称放气泡上方。自己的身份方向/头像保持。正常完成/发送标签消失，进行中/失败仍紧邻相应消息，原用量详情/耗时移到气泡下方；原Markdown、附件、交互回复、process、permission、只读和发送恢复分支没有被替换或放宽。系统任务通知保留独立分支。未发现新增 correctness 或职责偏离。

`TimelineTests` 追加稳定时间分组风险，覆盖首条、相近、跨日、299秒、恰好300秒、分数秒与配置边界；已有 timeline merge 测试保留历史/重放排序 seam。红日志 `/tmp/nano-feat636-chat-time-red.log` 是新增符号尚不存在导致的编译失败，不能夸称已观察旧产品行为断言失败。最终 `/tmp/nano-feat636-ios-test5.log` TEST SUCCEEDED：44 XCTest（含 Timeline 3项）+ 21 Swift Testing / 4 suites。已复用有效结果，独立 diff-check 通过；没有为纯标签/框架呈现新增镜像测试。

```json
[]
```

静态审查通过不代替新增单聊/群聊默认及辅助字号真实截图、时间/运行失败状态产品复验；verification保持待这些证据，不将旧21组画廊当作新增scope已验。只改报告，未操作GUI/浏览器/服务或产品源码。

R4 effective_through：`3200455b0`；最终28路径source manifest已独立SHA256核对一致。`/tmp/nano-feat636-ios-archive4.log` 为本聊天delta后的Release arm64 ARCHIVE SUCCEEDED；未因本地提交metadata重跑此前有效测试。
