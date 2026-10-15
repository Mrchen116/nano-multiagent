# Workspace 压缩引擎（高级）

先 `describe_api(topic: compaction)`，读 `dsh-compaction-basic` 与 `dsh-compaction` 的当前公开 types 和 README。压缩会改变会话上下文，应先在用户授权的测试会话验证；不要拿其他 Agent 或生产历史试验。

当前 workspace 插件树属于 Agent preset。一个隔离的 `compaction` provider 会成为该 preset 的引擎，Nano 默认自动压缩会让出，人工 `/compact` 也路由到它；停用后恢复默认引擎。无需禁用宿主 provider 或重启 session。

## 最小方式

源码包中的本地 `engine.mjs` 可以重导出公开引擎：

```js
export { BasicCompactionEngine as default } from '@deepseek-ai/dsh-compaction-basic';
```

bundle patch 插入本地文件，并在条目上 `isolate: {compaction: true}`。自动开关、阈值、保留预算、摘要模型和输出预算通过该条目 config 配置；参数以当前 types 为准，不抄其他版本字段。`retainTokens` 与 `retainRatio` 二选一；摘要 provider/model 必须成对，通常继承当前会话模型即可。先用合理默认值，不为了证明“会压缩”把日常阈值压到每轮都触发。

多个相关 provider/consumer 使用同一个隔离 group。已安装包的配置修改，只覆盖其既有条目到 workspace user overlay，保持 bundle 停用时会一起撤销。

## 定制摘要

需要特殊摘要结构时，继承公开 `BasicCompactionEngine`，使用声明允许的 `summarize(input, agent, signal)` 扩展点，并读取 `SummarizationInput` / `SummaryResult` 的确切返回契约。优先组合现成摘要行为，保留工具调用/结果配对、取消、持久化事务、并发锁与失败处理；不覆盖其私有方法或自己写 history replacement。不要将原始长历史直接当摘要返回。

## 证明实际效果

安装与引擎发现不是压缩成功。准备有可压缩历史的测试会话，保留需要回忆的事实，分别验证自动与人工压缩完成，再继续对话核实事实。`null`/no-op 只是没有可处理区间，不能报“压缩已完成”。自动压力测试可在专用测试会话暂调阈值，完成后恢复用户设置。停用后继续正常对话并验证默认路径，不影响其他 workspace。工具可见、统计或日志 marker 只是辅助证据，最终要有真实压缩事务与可继续使用的上下文。
