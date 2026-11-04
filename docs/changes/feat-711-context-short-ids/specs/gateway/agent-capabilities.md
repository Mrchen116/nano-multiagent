# gateway/agent-capabilities 增量

## ADDED Requirements

### Requirement: 上下文恢复引用简短且稳定

- 首次入模的普通用户材料与最终工具结果正文末尾提供会话内有序短编号；assistant/窗口控制消息不加正文标记。
- 同一逻辑消息经过补标记、裁剪、换窗和重启仍使用相同引用，可恢复原始内容并分段继续读取；物理替换副本不形成重复 History 项。
- source_history 的宿主证据序号与权限范围保留。

### Requirement: 剩余上下文预算简洁表达

- get_context_remaining 只返回工作预算剩余量或未知及估算语义，不默认携带内部预算计算或引用分页。
