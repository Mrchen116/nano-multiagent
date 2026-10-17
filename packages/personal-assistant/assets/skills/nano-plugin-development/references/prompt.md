# 提示词和上下文贡献

先 `describe_api(topic: prompt)`，确认当前 `SystemPrompt.section` / `context` 参数。无需创建一个假工具来安装提示词。

静态风格或领域说明用 `ctx.systemPrompt.section`，动态、任务相关事实用公开 `context` 注册。使用插件独有的名字；不要重用 Nano/DSH 既有 section 名，不设 `complete`，不 suppress runtime context，不改身份、审批、收发消息或系统职责。

模板添加报销报告结构，仅在相关任务中生效，不要求无关回答也遵循格式。`interpolate: false` 保留业务文本中的花括号，避免被当成宿主变量。动态 provider 按当前 API 的同步/异步契约实现，不猜签名；不要在每次模型组装时做无关昂贵工作。

原生注册随插件生命周期撤销，通常不需要手工 unregister。验证时用同 workspace 的干净新聊天或 Agent，看一个未重复格式要求的自然业务问题是否得到目标结构；停用后确认贡献撤销。旧聊天可能记得之前的格式，不能仅靠旧聊天仍用该格式就判定停用失败。
