# bugfix-560: 工具参数错误提示可指导模型重试

## 原始报告

> 「判定非法，给的报错，llm看不懂？还是报错没写好」
>
> 「我觉得就改Bridge，以及工具的错误提示就行了。字段 description 不用强调，一般不会错。」

## 现象 / 复现

全局 Agent 调用 `inbox(action="check")` 时，Codex Responses 路径曾把可选字段补成空值，形成 `{"action":"check","target":"","cursor":"","limit":20}`。`inbox` 正确拒绝了 `check` 不接受的 `target`，但只返回 `invalid_arguments: unsupported action or fields`：错误没有区分 action 与字段问题，也没有指出应删除哪个字段或当前 action 接受哪些字段，模型无法据此可靠修正并重试。

本次范围限定为两项：LLM Bridge 保留源工具 schema 的 non-strict 语义；工具参数错误点名不支持字段和允许字段，并在可选文本为空时提示未使用应省略。字段 description、工具参数契约和对空值的拒绝规则不变。

## 根因

LLM Bridge 在 Anthropic/Chat 工具转换为 Responses 工具时曾省略 `strict`。Responses 会尝试把省略 `strict` 的 schema 规范化为 strict，导致原本只要求 `action` 的 schema 被改写并生成全部字段。本机 LLM_PROXY 已有提交 `016f32e`，通过在转换结果中显式设置 `strict: false` 保留原可选字段语义，真实探针已返回仅含 `action` 的调用。

nano 的参数校验从全局 Inbox 首次实现提交 `d6f746c347` 起，把“不支持的 action”和“当前 action 不接受的字段”合并为同一个无上下文错误。原功能要求非法参数返回明确 `invalid_arguments`、失败不消费 Inbox；修复必须继续拒绝非法字段、保留错误码且不放宽访问或消费边界，只提高模型可见错误的可操作性。

## 修复

## 验证
