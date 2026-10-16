# Tools

Query `describe_api(topic: tool)` and read the installed `dsh-tools` README and public `ToolDefinition`, `ToolExecution` and schema declarations. Prefer its documented `defineTool` DSL, as in the shipped tool template; raw `ctx.tools.register` schemas use DSH's supported JSON Schema subset. A raw `type` is one string, not an array; use supported `oneOf` for alternatives. Do not assume full JSON Schema support or mix raw schemas with the DSL's property declarations.

`execute(args, exec)` returns the declared business value; `output.render` projects it into model-readable content. Pass `exec.signal` to cancellable work. Native registration exposes new independent tool names without changing static tool choices; do not shadow existing tools or bypass their permissions.

File paths follow the calling session's `exec.agent.session.header.cwd`, not `process.cwd()`. For `ctx.fs`, read its current resolution and write-policy contract too. A successful read does not establish a correct write-policy context. Keep credentials out of source and responses, and use only configured/authorized business access.

The integer-cents template demonstrates a callable tool, not a completed expense-file feature. Exercise the installed native tool against a known business input before reporting success.
