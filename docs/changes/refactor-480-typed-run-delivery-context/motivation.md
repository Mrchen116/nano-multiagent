# refactor-480: 完成运行投递上下文类型化切换

> 状态：v2（2026-07-25）

## Relations

- Depends on: 无
- Blocks: 无
- Related: refactor-478、refactor-481；历史 refactor-454

## 原始诉求

> 再看看当前代码仓中有多少巨石代码
>
> 我希望你能明确当前所有的重要的架构问题，如果和CC有类似的概念则和CC的源码的架构做对比，然后用change-spec-author，change-design-author skill（不需要跟我逐个进行对齐），帮我创建独立的几个unit。我要逐个进行重构，完善架构。我最终做一次确认后，再开始按可并行性开始做各个unit的实现。
>
> 中途你全程负责。我只做最终的确认。

## 澄清记录

- Q1: 是否逐项等待确认？
  A: “中途你全程负责。我只做最终的确认。”
- Q2: 是否重新设计 Gateway 投递所有权？
  A: 否；refactor-454 已确定 `runtime_delivery` 为所有者，本 unit 只完成 typed authority 的最终切换。

## 现状痛点

`RunDeliveryContextStore` 已有 typed context，却在每次修改后同步一份 `_legacy_contexts` 字符串字典，并通过 `RunDeliveryRuntimeView(MutableMapping)` 让 observer 继续以字符串 key 读写。终态 stream 又把 typed state 转回 dict。生产已无直接 legacy mirror 消费者，剩余依赖主要是兼容断言。

这导致字段重命名、缺省值和状态迁移需要同时维护 dataclass、双向映射、mutable mapping 和 observer 字符串约定；typed owner 没有真正隐藏不变量。

## 目标状态

`RunDeliveryContextStore` 只保存一种 typed representation，并提供意图化 mutation/query；observer 使用 typed context 和细分的事件 handler，relay lifecycle 与终态 stream 只接收该 store，outcome 使用明确 DTO 投影。删除 legacy mirror、dict façade、dict fallback 和字符串字段写入。

owner-direct、shadow、rolling、权限卡片、工具事件、run liveness、skill-created 配置同步、
终态顺序、detached delivery 的 shutdown drain 和清理时机全部保持。

## 用户侧验收标准（不变性）

用户通过个人助手收到 agent 流式回复、工具与权限事件；owner 消息可直接投递，其他可见性路径按既有规则投影，失败或重连后仍有一致的终态。

### Requirement: 消息投递保持

#### Scenario: 普通 owner 对话
- **WHEN** 用户通过已绑定 channel 发送消息并等待回复
- **THEN** 流式文本、最终消息和已读/可见状态与变更前一致

#### Scenario: Shadow 与 rolling 路径
- **WHEN** 运行满足既有 shadow 或 rolling 条件
- **THEN** 投递目标、更新节奏和最终聚合与变更前一致

#### Scenario: IM 离线不阻塞外部 channel
- **GIVEN** 外部 channel 触发的运行已经建立外部回复上下文
- **WHEN** 内部 IM 暂时不可达
- **THEN** 外部 channel 仍收到用户可见回复，IM 影子同步保持 best-effort

### Requirement: 交互事件保持

#### Scenario: 工具与权限事件穿过投递链
- **WHEN** 运行发布工具状态或权限请求/结果
- **THEN** IM 中事件顺序、卡片状态和终态与变更前一致

#### Scenario: 权限等待期间保持运行活性
- **WHEN** 运行停在工具或权限等待并持续发布 `run_heartbeat`
- **THEN** IM relay 的 liveness 持续推进，不会把仍在等待的运行误收为 stalled

#### Scenario: IM 离线时 skill-created 仍同步配置
- **WHEN** kernel 发布 `skill_created` 而 IM connection 当前未建立
- **THEN** Gateway 仍触发既有 agent 配置同步 side effect

### Requirement: 清理和故障行为保持

#### Scenario: 运行结束、失败或取消
- **WHEN** 运行进入任一终态
- **THEN** 最终投递与 context 清理顺序和变更前一致，不残留跨运行状态

#### Scenario: Gateway 关闭时排空已接收的投递
- **WHEN** Gateway 在仍有 detached message/tool/permission terminal delivery 时关闭
- **THEN** shutdown 在关闭 IM transport 前按既有 deadline 排空这些投递

## 影响范围

- `src/personal_assistant/gateway/runtime_delivery/context.py`
- `src/personal_assistant/gateway/runtime_delivery/observer.py`
- `src/personal_assistant/gateway/runtime_delivery/stream.py`
- `src/personal_assistant/gateway/runtime_delivery/lifecycle.py`
- `src/personal_assistant/gateway/runtime_delivery/task_tracker.py`（保留并验证其 owner 契约）
- `src/personal_assistant/scheduler/heartbeat_runner.py`
- `src/personal_assistant/scheduler/cron_execution_service.py`
- Gateway relay lifecycle 与相关测试
- 不改变 IM API、wire frames 或 kernel event contract

## 迁移与回滚策略

先将现有 ack backfill、visibility、rolling、permission/tool/end 顺序写成行为测试，再逐类事件迁移到 typed mutation，最后删除 legacy mirror 和映射 façade。一次提交内完成单一 authority 切换；出现差异时整体回滚，不保留 typed/legacy 双写。
