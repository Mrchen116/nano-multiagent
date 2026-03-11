# 【重要】CLI 从用户发消息到工具调用的时序图

> 简化版：仅包含文本输入流程，不含斜杠命令。

```mermaid
sequenceDiagram
    autonumber
    actor User as 用户
    participant CLI as REPL + Input
    participant App as app/commands
    participant Client as ServerClient
    participant API as HTTP API
    participant Runs as RunsRegistry
    participant Runtime as AgentRuntime
    participant Loop as AgentLoop
    participant LLM as LLM
    participant Reg as ToolRegistry
    participant Tool as Tool
    participant SSE as 事件流 SSE

    User->>CLI: 输入文本
    CLI->>App: _send_message_from_repl(text)

    opt 无 session
        App->>Client: create_session()
        Client->>API: POST /v1/sessions
        API-->>Client: session_id
    end

    App->>Client: send_message_async(session_id, text)
    Client->>API: POST /v1/sessions/{id}/messages:async
    API->>Runs: submit(parts)
    API-->>Client: 202 { run_id }
    Client-->>App: run_id

    Runs->>Runtime: run(session_id, parts, run_id)
    Runtime->>Loop: loop.run(state)
    Loop->>LLM: generate(messages, tools)
    LLM-->>Loop: content + tool_calls

    loop 每个 tool_call (可多轮)
        Loop->>Reg: execute(name, args)
        Reg->>Tool: run(args)
        Tool-->>Reg: result
        Reg-->>Loop: output
        Note over Loop,SSE: Hook 发布 tool_* 事件到 SSE
        Loop->>LLM: generate(messages + tool_result)
        LLM-->>Loop: 下一轮 content/tool_calls
    end

    Loop-->>Runtime: TurnResult
    Runtime-->>Runs: completed
    Runs->>SSE: publish(run_status)

    loop CLI 轮询
        App->>Client: stream_session_events()
        Client->>API: GET /v1/sessions/{id}/events
        API-->>Client: tool_*, text_delta, run_status
        App->>Client: get_run(run_id)
        Client->>API: GET /v1/runs/{run_id}
    end

    App-->>CLI: payload (message, tool_updates)
    CLI-->>User: 显示 assistant 回复
```

## 组件与文件路径对照表

| 时序图参与者 | 父目录 | 文件名 |
|-------------|--------|--------|
| REPL + Input | `nano_multiagent/cli` | `app/commands.py` + `input/repl_input.py` |
| app/commands | `nano_multiagent/cli/app` | `commands.py` |
| ServerClient | `nano_multiagent/cli` | `http_client.py` |
| HTTP API | `nano_multiagent/server/routes` | `session.py` |
| RunsRegistry | `nano_multiagent/runs` | `registry.py` |
| AgentRuntime | `nano_multiagent/agent` | `runtime.py` |
| AgentLoop | `nano_multiagent/agent` | `loop.py` |
| LLM | `nano_multiagent/llm/protocols` | `openai_compat/client.py` 等 |
| ToolRegistry | `nano_multiagent/tools` | `registry.py` |
| Tool | `nano_multiagent/tools/builtins` | `bash.py`、`edit.py`、`read.py` 等 |
| 事件流 SSE | `nano_multiagent/server` | `sse.py` + `session.py`(stream_session_events) |

> 所有路径均相对于 `src/` 目录。

## 关键接口

| 操作 | 方法 | 路径 |
|------|------|------|
| 发送消息 | POST | `/v1/sessions/{id}/messages:async` |
| 轮询事件 | GET | `/v1/sessions/{id}/events` |
| 查询 Run | GET | `/v1/runs/{run_id}` |
