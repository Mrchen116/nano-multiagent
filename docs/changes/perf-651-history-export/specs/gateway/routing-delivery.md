# Gateway Routing and Delivery Specification (delta for perf-651)

## ADDED Requirements

### Requirement: 原生历史导出在完成边界提供完整派生副本

节点从原生持久会话生成原始 JSONL 和 workspace 可读聊天副本。原始文件保留版本头、原生事件及 fork 继承前缀；可读副本保留文本、来源与图片占位，真人上下文 envelope 不重复进入正文。两者都是派生结果，不能替代原生会话记录。需要完整原始历史的消费者通过 `session.export` 等待导出完成；直接读取正在更新的 JSONL 时可能遇到尚未完成的尾行。

#### Scenario: 连续轮次导出完整且不重复
- **WHEN** 已结束多轮原生聊天，消费者请求 `session.export`
- **THEN** 等待已排队导出完成后返回文件路径，文件包含已导出切面的完整事件序列且无重复；workspace 副本保留对应的全部可读消息

#### Scenario: 分支导出包含自己的完整历史
- **WHEN** 用户成功 fork 历史消息并继续分支会话
- **THEN** 分支文件保留原生继承前缀和分支自己的后续消息，不混入源会话分支点后的内容

#### Scenario: 派生写入失败后重建
- **WHEN** 写入派生副本失败，或进程重启后恢复绑定会话
- **THEN** 失败不能伪报成功导出；下一次导出尝试或启动恢复从原生历史重建完整副本，清除部分写入导致的重复或不完整尾行
