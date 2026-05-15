# refactor-353: 统一路径沙箱到 auto_mode_gate 体系

> 类型: refactor
> Owner: czj
> 立项日期: 2026-05-15

## 用户场景 / 现状痛点

feat-333 引入 auto 模式 + classifier + ask 流程后,**路径沙箱(write 工作区外路径)没有跟着升级**,仍走 codex-cli 沿用的"在 tool 入口硬 raise ToolError"路径。结果:

1. 用户在 IM 让 agent 写 `/tmp/mu-bro/hello.py`,agent 直接收到 `path is outside repo sandbox` 错误,无法弹卡片让用户授权。
2. 即使开了 `dangerously-skip-permissions`,`safety.py:_resolve_path` 在 hook 之前硬 raise,**绕不过去** —— 跟 spec "危险旁路语义是不进行任何权限管控" 的承诺直接冲突,等于这个 mode 形同虚设。
3. classifier(yoloClassifier 对齐 CC)看不到工作区外的 tool 调用,丢失了"用户明确说删 /tmp/foo 我可以放行"这种 informed 决策的机会。

对照 CC 源码 `permissions.ts:480-690 + pathValidation.ts:141`,CC `auto` 模式下工作区外路径**从不硬错**,永远走 tool.checkPermissions → classifier → ask 流程;`bypassPermissions` 模式下统一放行。我们的现状属于 feat-333 演进后底层 gate 没跟上的架构错配。

## 验收标准 / 目标状态

- [ ] 用户在 IM/CLI 让 agent 写工作区外路径(如 `/tmp/foo/bar.py`)时,**不再直接报错**,而是触发与 bash 一致的 permission ask 流程(权限卡片 + Allow / Deny / 永久 allow 选项)。
- [ ] 用户点 Allow 后写入真的发生;点 Deny 后写入被拒绝且目标路径不被改动;tool_call.status 正确反映结果。
- [ ] `dangerously-skip-permissions` 开启时,工作区外路径写入直接通过,无任何 ask、无任何报错 —— 真正"不进行任何权限管控"。
- [ ] auto 模式下,classifier 能拿到工作区外路径的完整 tool 调用上下文(transcript 里能看到工具名 + 路径),LLM 有机会基于上下文做 informed 决策(允许 / 拒绝 / 继续 ask)。
- [ ] 现有的"工作区内写入"行为不退化:不引入额外 ask、不打断既有用户体验。
- [ ] 现有的 deny rule(如 `rm -rf /` 这类显式禁止)继续硬拒,不被绕过。
- [ ] 现有单测覆盖路径沙箱的部分,验收口径从"抛 ToolError 文案"改为"hook decision allow/deny/ask"。

## Q & A

- Q1: 这次只解决"工作区外写",还是连"工作区外读"也对齐?
  A: 只解决工作区外**写**(write / edit / multi-edit / 创建等可写操作)。read 现在默认放行(读不会破坏文件),保持不变。CC 也是这个口径(`pathValidation.ts:148` 区分 read vs edit)。
- Q2: 引不引入 `additionalDirectories` 配置(CC 用来永久放行某目录的字段)?
  A: 本 unit 不引入。spec.md feat-333 明确写"非目标:default / plan / dontAsk / acceptEdits"。`additionalDirectories` 不在那个列表里,但属于"高级权限配置",独立 unit 做。本 unit 只做最小架构对齐:工作区外路径走 ask 流程,点临时 Allow 生效一次;不做"永久 allow 这个目录"的持久化。
- Q3: 这次会动 codex-cli 沿用的 safety.py 老代码吗?
  A: 会,因为 `_resolve_path` 的"工作区外硬 raise"就是错配的根源。改法是让它仍能 raise(供 read 等不进 hook 流程的场景),但在涉及写操作时改为返回一个语义信号(`outside_workspace` flag)由 hook 层决策,而不是在 tool 入口烧成异常。
- Q4: 这次是 feat 还是 refactor?
  A: refactor。从用户视角看,我们补齐了一个本该有但缺失的能力(工作区外写要走 ask),但其实是底层架构没跟上 feat-333 演进的修复。改完外部行为是"功能补齐",改的本质是"统一两套并行的权限 gate 为一套"。命名上 refactor 更准 —— 主要工作量是抽象重组,不是新功能开发。
- Q5: dangerously-skip-permissions 现在到底通不通过 safety.py 路径检查?
  A: **不通过**。现状是 `safety.py:_resolve_path` 在 hook 之前硬 raise,不知道 mode 概念。这次修后:dangerously 模式 + 工作区外路径要么完全跳过路径检查、要么 hook 层第一时间放行。两种实现都满足 "不进行任何权限管控"。
- Q6: 现有的 `auto_mode_gate` deny_count / session allowlist / 永久 allow 这些能力,要不要顺手扩到 path 维度?
  A: deny_count 和 session allowlist 直接复用就行(broker 是 tool_name 维度的,path 的 ask 也走相同 broker,语义自然一致)。永久 allow 涉及 `additionalDirectories` 写回(Q2 答案),本 unit 不做。

## 范围与非目标

- 在范围:工作区外的写操作改走 auto_mode_gate 决策(allow / deny / ask),与 bash 一致
- 在范围:dangerously-skip-permissions 模式真正生效在 path 维度
- 在范围:`safety.py` 的工作区外硬错路径从 tool 入口移到 hook 层
- 在范围:相关单测口径迁移(从 ToolError 文案 → hook decision)
- 在范围:e2e 实测:IM 写工作区外 → 卡片 → Allow / Deny 真生效

- 非目标:`additionalDirectories`(永久 allow 某目录)的配置持久化
- 非目标:工作区外**读**的行为变更(现状已经能读,不动)
- 非目标:引入 CC default / plan / dontAsk / acceptEdits 等其他 mode(沿用 feat-333 spec 的非目标)
- 非目标:覆盖到 Read / Glob / Grep 这些非编辑工具(它们不走 path sandbox)

## Relations

- Refs feat-333(本 unit 是 feat-333 演进后底层 gate 未升级的对齐修复)
- 与 feat-333 PR #12 已 merge 的代码无冲突依赖,基于 merge 后的 main 开干
