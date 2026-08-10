# refactor-479: 收拢 Skill 批量复盘生命周期

> 状态：v3（2026-07-25）

## Relations

- Depends on: 无
- Blocks: 无
- Related: refactor-476、refactor-477

## 原始诉求

> 再看看当前代码仓中有多少巨石代码
>
> 我希望你能明确当前所有的重要的架构问题，如果和CC有类似的概念则和CC的源码的架构做对比，然后用change-spec-author，change-design-author skill（不需要跟我逐个进行对齐），帮我创建独立的几个unit。我要逐个进行重构，完善架构。我最终做一次确认后，再开始按可并行性开始做各个unit的实现。
>
> 中途你全程负责。我只做最终的确认。

## 澄清记录

- Q1: 是否逐个确认方案？
  A: “中途你全程负责。我只做最终的确认。”
- Q2: 是否把产品 workspace 规则下沉到 kernel？
  A: 否；CLI 的 `.nanocode`、Gateway 的 `.nanoassistant` 与 workspace catalog 仍由各产品提供，kernel 只拥有从触发到终态的通用生命周期。
- Q3: 产品是否继续注入 asyncio scheduling/drain port？
  A: 否；真实 enqueue 来自同步 tool worker thread。lifecycle 自己拥有线程安全 admission 与
  单 coordinator，产品只通过 build-time SDK policy 提供 workspace/root 事实。
- Q4: 30 秒超时后是否可以把 asyncio carrier 已取消等同于同步工具已经退出？
  A: 否；Python 不能安全终止已经运行的工具线程。30 秒是 analysis result deadline，不是伪造
  cleanup 的期限。超时后必须拒绝新工具执行并取消 carrier/尚未启动的工作；已经运行的同步工具
  必须由 execution owner 跟踪到真实结束。在此之前，同一 review identity 保持隔离，Kernel
  close 也不得报告完成。review 使用独立 worker，不得阻塞当前用户 turn。

## 现状痛点

一次 skill-view 达到阈值后，触发会跨越 core queue/dedupe、SDK drain、产品 scheduler、workspace 映射、临时分析 session、轮询终态和 platform evidence/mark-reviewed。CLI 与 Gateway 各复制一份“创建 session → submit → 最多轮询 300 次 → 判终态”的实现。

当前没有模块对 enqueue 到 finish 的闭环负责。历史上这个边界已出现只在启动时 drain、根目录选错、闭包捕获最后 workspace、同名 skill 选错 root 等缺陷。

## 目标状态

kernel 装配图中形成一个明确的批量复盘 lifecycle service，拥有 thread-safe admission、
queue、dedupe、running、auxiliary analysis run、cancel-settle 和 finish 语义；产品在
`build_kernel` 时只注入 SDK-owned workspace/root policy。evidence 读取和 reviewed 标记继续
使用既有 platform 能力；auxiliary review 使用不加载 consumer/workspace/deployment override
的 trusted tool catalog，`skill_view` / `skill_manage` 再由 internal exact-root capability
限制在同一个目标 root。真实同步工具执行由 review-owned scope 跟踪到结束，产品不再复制
session/polling/scheduler 协议。

本 unit 不改变阈值、review prompt、自动演进规则、目录约定或用户启停方式。

## 用户侧验收标准（不变性）

该机制没有独立 UI；可观察结果是用户持续使用 skill 后，系统仍在正确的产品 workspace 中异步生成复盘并更新对应 skill，且不阻塞当前对话。

### Requirement: 自动复盘触发保持

#### Scenario: Skill 使用达到既有阈值
- **WHEN** 用户在 CLI 或个人助手中持续使用某个 skill 并达到触发条件
- **THEN** 系统仍异步启动一次对应复盘，不阻塞当前请求，结果与变更前一致

#### Scenario: 同步工具线程触发复盘
- **WHEN** `skill_view` 由 ToolRegistry 的同步 worker thread 执行并越过阈值
- **THEN** enqueue 原子接受并唤醒 lifecycle owner，不依赖该线程存在 asyncio loop

### Requirement: 产品工作区隔离保持

#### Scenario: 两个产品或多个 workspace 存在同名 skill
- **WHEN** 某一 workspace 的 skill 触发复盘
- **THEN** 证据读取、更新和 reviewed 标记仍落在该产品的正确 workspace/root，不影响同名 skill

#### Scenario: 同名 product/workspace/deployment tool override
- **GIVEN** 正常会话的 tool catalog 以任一受支持层级覆盖了 `skill_view` 或 `skill_manage`
- **WHEN** 自动复盘执行同名工具调用
- **THEN** 正常会话仍保留既有 override 行为，但复盘不执行该 override，且只能读取或 patch
  触发 identity 绑定的 skill/root

#### Scenario: 只读兼容 root 不回退到可写同名 skill
- **WHEN** 命中的 skill 位于产品声明为只读的 compat root
- **THEN** 本轮复盘明确 skip，既不启动修改 run，也不回退写入 workspace/global 的同名 skill

### Requirement: 失败隔离保持

#### Scenario: 后台分析失败或超时
- **WHEN** LLM 运行失败、取消或超过既有等待边界
- **THEN** 当前用户请求不受影响；底层 auxiliary run 在 30 秒 result deadline 后进入 cancel，
  已运行的同步工具真实结束并确认 cleanup 后才释放 identity，失败/cancelled 不写 reviewed 标记

#### Scenario: 关闭时仍有同步复盘工具运行
- **WHEN** Kernel close 命中一个已进入同步工具线程的复盘
- **THEN** close 拒绝新的复盘并取消 carrier/未启动工作，但在真实工具线程结束前不释放同一
  identity、不返回成功关闭；close 返回后不再发生该复盘的文件副作用

## 影响范围

- `src/agent/core/agent/runtime.py` 的触发队列
- `src/agent/sdk/kernel.py` 的 drain/runner 入口
- skill batch review platform 实现
- core `TurnRequest` / ToolContext 的 internal exact-root capability、trusted turn tool runtime
- ToolRegistry / StreamingToolExecutor / KernelExecutor 的 review-owned tool execution settlement
- `src/coding_cli/product.py`
- `src/personal_assistant/gateway/runtime.py`
- 两产品工作区策略和相关测试
- `specs/kernel/sdk-boundary.md`：build-time `SkillReviewPolicy` SDK delta
- `specs/kernel/skills.md`：把已 drift 的 `scope="pa"` canonical 词汇校正为生产现状
  `scope="global"`（仅文档归并，无行为迁移）

## 迁移与回滚策略

先用真实 tool-worker 入口和跨产品契约测试锁定阈值、workspace 选择、三层同名 tool override
攻击、exact-root capability、dedupe、真实工具线程 settlement、close 顺序与失败隔离，再引入
单一 lifecycle service，迁移 CLI/Gateway build-time policy，最后删除 engine queue 和产品
polling/scheduler。不得保留双 scheduler、同时 drain 同一 queue，或在同步工具仍运行时伪造
cleanup ack；失败时整体回滚。
