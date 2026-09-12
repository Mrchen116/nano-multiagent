# Unit 现场与开放 PR

在 active/archive/retired 唯一解析 unit_id（可带 short description），零/多命中报告歧义。archive 只有匹配开放 PR 才进入小修；无开放 PR 不重启生命周期；retired 不恢复。

从最新 origin/main 建立 `unit/<unit_id>` 和 `<repo-root>/.worktrees/unit-<unit_id>`，恢复时核实本地/远端 head 与未提交修改；不 reset 不明现场。worker 现场计划为 `.worktrees/<unit_id>-M<N>` / `milestone/<unit_id>-M<N>`，由 worker 创建和清理。状态使用现有 git、unit 产物与会话，不建额外状态台账。

开放 PR 从 exact PR head 的 clean unit worktree 恢复。CI 已绿且无待处理反馈就结束；只处理不改需求/design、不新增设计型 milestone 的自包含修复。复用验收上下文，对实际 delta 执行 patch/closure 并更新 PR 与 required CI。需要改变设计或范围时由用户决定是否回 active，不在 archive 中启动另一套生命周期。

收尾删除自己创建或接管的临时现场前确认合法提交已可达、无其他工作或活进程；不按目录名通配清理。
