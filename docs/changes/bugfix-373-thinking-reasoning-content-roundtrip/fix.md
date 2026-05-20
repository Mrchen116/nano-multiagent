# bugfix-373: 主 agent 开 thinking 后,历史回传丢失 assistant tool-call 的 reasoning_content,工具执行后整轮停下

## Relations

- Related: bugfix-366（引入 thinking 时未让历史 round-trip reasoning_content）
- Related: bugfix-369（同一 thinking 连带问题的另一面：门禁分类器；#369 修复后才暴露本 bug）

## 原始报告

用户在 PA 聊天里反复观察到 agent "做了一些工具调用就结束了 / 拿到工具结果之后停下来了":

> http://127.0.0.1:8011/chat/a43e2465... 怎么停下来了，怎么他拿到工具结果之后停下来了？

> 还是和之前一样，做了一些工具调用就结束了。

（第二次是在 bugfix-369 门禁修复已生效、worktree 内核确认放行工具之后复现的，排除门禁因素。）

## 现象 / 复现

PA 聊天里,agent 调用一个工具(如 `bash`)、工具**执行成功完成**后,本该把工具结果回传给模型做下一步推理 / 文字总结,但整轮在这里**戛然而止**:agent 不再产出任何文字,会话结束。用户看到"做了工具调用就停了,没有最终回复"。

**复现链路**(worktree 内核 + kimi K2.6 + 主 agent thinking 开启,LLM proxy 日志 `logs/session/2026-05-20_11-32-10_374_sess_442ac3ad7289d184/`):

1. 用户发"请运行 pwd 和 ls -la"。
2. 主循环第 1 轮:模型返回 `bash: pwd && ls -la` 工具调用(`finish_reason=tool_calls`)。
3. 门禁放行(bugfix-369 已修),`bash` 执行 **completed**,无 ask。
4. 主循环第 2 轮(把工具结果回传):请求被上游**直接拒绝**:
   ```
   {"type":"error","error":{"type":"invalid_request_error",
    "message":"thinking is enabled but reasoning_content is missing in assistant tool call message at index 2"}}
   ```
5. 该轮返回空 content、`finish_reason=stop` → agent loop 收到空响应 → 整轮结束,无文字总结。

核对失败请求体确认:`thinking: {type: adaptive}` 开启,而历史里那条带 `tool_use` 的 assistant 消息既无 thinking 块、也无 `reasoning_content` 字段:

```
[0] role=user      tool_use=False
[1] role=assistant tool_use=True   thinking_block=False  reasoning_content=None   ← 缺失,被上游拒
[2] role=user (tool_result)
```

**触发条件**:主 agent 用带 thinking 的模型(kimi K2.6,`thinking: adaptive`)+ 任意一次工具调用。即"开 thinking + 用工具"必现,是 PA / coding 两个产品共性路径。

## 根因

kimi K2.6(及同类上游)在 `thinking` 开启时,有一条强约束:**回传的对话历史里,每条带 tool_call 的 assistant 消息都必须携带它当时产出的 `reasoning_content`(thinking 块)**——否则请求被判 `invalid_request_error`。

bugfix-366 给主 agent 开 thinking 时,只在**出站请求**加了 `thinking: adaptive`,但 agent loop 的**历史序列化**没有同步跟进:模型返回的 assistant 轮里带的 `reasoning_content` / thinking 块在落进会话历史、再回传给模型时被丢弃了。于是只要发生过一次工具调用,下一轮把"assistant(tool_use) + tool_result"回传时,那条 assistant 消息缺 `reasoning_content`,整个请求被上游拒,工具结果永远喂不回模型 → agent 停在工具调用之后。

**为什么这种错能进来**:

- bugfix-366 的关注点是"让主 agent 会推理"(出站开 thinking),把 thinking 当成一个单向的请求参数,没意识到它对**历史回传**有对称的格式要求(reasoning_content 必须 round-trip)。
- 开 thinking 前,历史里 assistant 消息从来没有 reasoning_content 这个维度,序列化路径自然不保留它;开 thinking 后这个维度才出现,而保留逻辑没补。
- 没有"开 thinking + 走完一次工具调用"的端到端测试 —— 单测多在不开 thinking 或不带工具的路径上,正好绕开这条必现链路。
- 现象长期被 bugfix-369 的门禁 fail-closed 掩盖:门禁先在工具调用前就 ask/卡住,根本走不到"工具执行完回传"这一步,所以这条更深的 round-trip 缺陷直到 #369 修好放行工具后才暴露。

## 修复

<!-- worker 回填 -->

## 验证

<!-- worker 回填 -->
