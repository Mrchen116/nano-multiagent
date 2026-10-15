# 自定义工具

先 `describe_api(topic: tool)`，读取当前 `dsh-tools` 公开类型中 `ToolDefinition`、`ToolExecution` 和输出契约。模板直接用 JSON Schema 注册，避免混用 `defineTool` 的另一种简写参数形式。

`inject = ['tools']`，在 `apply(ctx)` 中调用 `ctx.tools.register`。必须提供：

- `name`、用户可理解的 `description`。
- `parameters`：对象 JSON Schema，明确输入而不是一个无限制代码字符串。
- `output.schema`：返回值 JSON Schema；`output.render(args, value)`：从业务值投影为模型可读内容。
- `execute(args, exec)`：返回符合 schema 的业务值。不要把 content blocks 当成业务值，除非你的 schema 就明确如此。

模板 `workspace_total` 对整数分求和，适合验证真实数值，不代表用户任务已经实现。按任务改成文件读取、业务 API 或脚本调用，保留清晰输入输出与错误信息。文件按当前 Agent 的 workspace 或明确配置解析；当前工具调用的会话目录是 `exec.agent.session.header.cwd`；相对路径必须以它或明确配置的 workspace 为基准，不要回退到 `process.cwd()`。不要在可替换安装目录保存业务状态。使用 `ctx.fs` 等其他公开服务时继续读取其当前声明，包括路径解析和写入策略参数；不要假定读成功就代表写入上下文也正确。

访问网络或运行子进程时传递 `exec.signal`，在工具返回前处理好自己启动的工作和资源。Python 是 bundle 内的业务脚本，由工具执行函数带明确参数调用；没有旧 `agent.sdk` 动态加载契约。调用公开 API时使用用户已配置/授权的凭据机制，不把凭据写进源码、模板或回复。对外发送等业务权限不能靠更换工具名字绕过。

安装后用至少一组已知输入直接调用新工具，并核对业务值；仅用 bash 运行源码或 Agent 心算得到答案不能证明原生工具可调用。
