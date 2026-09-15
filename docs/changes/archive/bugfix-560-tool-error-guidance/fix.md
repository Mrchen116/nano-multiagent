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

- LLM Bridge 提交 `016f32e` 在 Chat/Anthropic 工具转 Responses 时显式传递 `strict`，源请求未指定时使用 `false`，不改写原始 parameters。
- nano 提交 `025784b2f` 将 action 与字段校验错误拆开：未知 action 列出合法 action；已知 action 的错误列出不接受字段和允许字段；同次调用中的空可选文本提示未使用时省略。
- code review 发现首版对空可选字段分流时跳过了必填 `target` 的类型与空白校验；提交 `9f557f7cf` 恢复原校验，并增加 Inbox/Conversations 必填 target 回归用例。
- 未修改工具字段 description、允许字段集合、必填字段、范围限制或 Inbox 消费行为。

## 验证

- Red：新增两个定向用例后，旧实现均返回 `invalid_arguments: unsupported action or fields`，`2 failed`。
- Green：`tests/unit/personal_assistant/test_global_query_tools.py`，`22 passed`。
- 相关 Inbox/Gateway 回归：`test_global_query_tools.py`、`test_global_inbox.py`、`test_global_gateway_runtime.py`，修复 review finding 后 `35 passed`。
- Bridge 转换与路由回归：`tests/test_proxy_converters.py tests/test_chat_completions_routes.py`，`25 passed`。
- Ruff check、Ruff format check 与 `git diff --check` 通过。
- 独立 code review：1 个 confirmed finding；closure finder 与 verifier 均确认 closed，无存活 finding。
- 本地 CI：文档完整性检查通过（234 个 Markdown source、73 条 required route）；Ruff check / format check 通过（1055 files）；Python 两个非 E2E 分片分别 `1889 passed`、`2002 passed`；前端依赖审计无 critical，首次与 Python 分片并跑出现 3 个无关超时，空闲后完整重跑 `759 passed`。
- 本次只细化既有 `invalid_arguments` 文案，不改变 current spec 所定义的权限、消费或查询行为，因此无需修改 canonical spec。
