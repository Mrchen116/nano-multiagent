# bugfix-629: 强制换窗后丢失已读任务与动态上下文重复

## Relations

- Follow-up: [feat-627](../archive/feat-627-codex-context-rollover/spec.md)。本 unit 修复已交付行为，不重写原验收结论。

## 原始报告与确认范围

用户通过调查聊天明确要求：“把问题交给当时的实现者 codex://threads/01a15c3c-faa1-79c0-a161-ae9f1803fecb，让他修”。调查者将该原话、完整证据与修复要求交回本聊天。用户另要求：“主仓也拉下最新代码”。

调查报告：主 checkout 的 `docs/changes/feat-627-codex-context-rollover/retro-pipeline-rootcause.md`（调查者新增，未提交；本 unit 不移动、不覆盖它）。报告确认故障而非仅提出猜测。修复范围是统一动态内容与 Skill 恢复生命周期，并保证强制换窗后能恢复已读但未完成的任务；保持无摘要、Notes/History、来源与授权边界。不通过提高阈值、清空生产会话、删除旧笔记或要求用户重复指令回避问题。

这是 Full bugfix：根因横跨插件、Nano knowledge 与原生快照协议，需要压力/主动换窗、任务来源、重启与回退的独立回归矩阵。默认单 milestone，未发现需要拆分交付的子目标。

## 现象与复现

生产 Nano `be6c1271b`、`dsh-agent-context@0.3.0-rc.1`（插件源码 `7f0a2b78`），Mini PA 同一会话在四轮新请求中都先读取并确认，然后在压力换窗后把旧笔记中“任务已完成”当作当前状态，未完成新请求便结束。

最后一轮 2026-10-21 15:09:17、15:09:32 的实际请求含最新指令及消息定位；15:09:45 换窗后两者消失。compaction summary seq 7031 替换 6985–7028，reason=pressure。模型随后读取 14:10 旧 checkpoint，15:10:10 completed。历史原件仍存在，但缺少当前任务恢复入口。

同轮请求内完整 runtime snapshots 从三份增加至六份，总快照正文从 171,635 增至 349,272 字符；单请求输入（含缓存）从 117,676 增至 223,853 tokens。七个已用 Skill 正文约 52,400 字符随每份快照重复，并非模型反复主动调用 Skill。

生产默认预算 C=258,400、O=32,768、B=16,384、R=6,144。单步约 35,000 tokens 的增量跨过保存区间；提醒之后并未保存新 Notes，就进入硬阈值换窗。

## 影响范围

所有默认启用该插件、动态引用发生变化的 Agent 都可能重复带入其他宿主 context；已有压缩且使用过较大 Skill 的长生命周期 PA 尤其明显。强制换窗的任务丢失同时影响直接输入和已从 Inbox 读入的工作。尚无持久原始历史被删除的证据，不宣称所有会话都已受影响。此前 R1 数据仍在却计算错误的案例不改判为本故障。

## 根因分析

1. 插件每步把引用放进 `systemPrompt.context`；DSH 的公开 runtime snapshot 语义是整份 context 变化时追加完整快照。旧快照仍在 surface，因此不变的其他正文也被重复加入。
2. Nano `knowledge/runtime.ts` 只检查 session 曾有任意 `compaction/end`，然后每次 assemble 把该 session 历史用过的 Skill 全文注入动态 context。与插件引用刷新耦合后形成持续膨胀。
3. 插件硬阈值路径移出完整配对 surface，只保护尚未入日志的新 claim；已读 Inbox 内容也被移出。checkpoint 仅给旧 Notes 路径，没有当前未结束 turn 的恢复定位或新旧状态裁决指引。
4. 原验收覆盖了主动保存 Notes 后换窗和首个 claimed 输入的幸存，未覆盖“旧 Notes 已完成 + 新 Inbox 已读 + 默认 buffer + 保存前硬阈值换窗”的组合。设计审查知道快照整体追加，却未核对宿主其他 contribution 的成本和生命周期。

以上基于调查报告的原始请求对照，并已核对生产版本插件 `index.ts`/`checkpoint.ts`、Nano knowledge hook、锁定 DSH `RuntimeContextProjection` 与 pre-step 公共扩展点。DSH runtime 不在修复范围内；无证据表明两个 compaction owner 同时执行。

## Requirements / Scenarios

### Requirement: 动态导航不会反复复制无变化的正文

#### Scenario: 已用多个 Skill 的 Agent 连续工作
- **GIVEN** Agent 曾使用多个 Skill，且已经发生换窗
- **WHEN** 后续多步只新增普通工具结果和历史引用
- **THEN** 相同 Skill/Memory 正文不因导航变化而逐步重复进入请求，Agent 仍能按需读取所需 Skill 与历史

### Requirement: 强制换窗保留当前工作恢复入口

#### Scenario: 旧笔记已完成，新任务尚未保存
- **GIVEN** 旧 Notes 宣称旧事项已完成，而 Agent 已读取新的直接或 Inbox 请求并尚未完成
- **WHEN** 默认预算下在保存新 Notes 前发生压力或 provider overflow 换窗
- **THEN** Agent 从原始历史恢复当前工作并完成最新请求，不以旧笔记为由误报无新任务，不要求用户重述，不重复已有外部交付

#### Scenario: 同一任务多次换窗与恢复运行
- **WHEN** 当前任务经历多次换窗或节点正常重启
- **THEN** 当前工作和恢复记录仍能定位到同一会话的原始来源，完成状态与已发生的交付一致

### Requirement: 恢复保持既有来源、权限与显式回退

#### Scenario: 非人类或观察来源与插件停用
- **WHEN** 恢复 Agent/system/observer 内容，或用户显式停用该 workspace 插件后继续工作
- **THEN** 恢复内容不变成人类新授权、不扩大跨 Agent 访问；停用仍恢复原摘要机制，已有 Notes/History 不被删除

## 修复方向与完成条件

将高频恢复导航从整份宿主快照中解耦；Skill 恢复改为可定位、按需读取；强制换窗提供由原生日志生成的当前 turn 恢复信息，不建立第二套任务数据库或摘要器。具体公开接口与数据流由设计确定。

回归必须使用默认预算和上述失败组合，检查真实模型请求中的重复正文以及最终交付；脚本预定 finished 不能替代任务恢复证据。分别交付代码验证、独立验收、PR/CI，以及经授权的生产恢复结果。保留生产日志、数据库、会话和旧 Notes。
