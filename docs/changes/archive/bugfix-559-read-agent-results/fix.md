# bugfix-559：Read 超限错误与后台 Agent 返回纠偏

## 原始报告

> “ok，这个点，我们要改。agent工具的返回结果我们也要改，改成跟安装的CC版本一致。对不对？就改这两点”

## 现象 / 复现

生产会话中，父 Agent 读取子会话 JSONL 的第 15 行时，58,797 字节的单行超出 51,200 字节读取上限。实际文件已有 140 行且子任务继续运行，但 Read 返回“文件存在，内容为空”，父 Agent 据此误判停滞并停止子任务。后台 agent 返回还指导模型 Read 完整会话文件来查进度。

范围只有以下两点，唯一 milestone 为 M1-fix：

- Read 所选文本超过既有读取大小或行数预算时，返回明确的工具错误，说明实际值、上限，以及用 offset/limit 分段或搜索；不把截断当成空文件。真实空文件仍返回空文件提示，预算内读取保持原样。
- 后台 agent 启动返回对齐已安装 Claude Code 2.1.268 的语义：内部元数据不向用户照抄；完成前不假定结果；等待自动通知；不重复工作；不得 Read/tail 完整子会话 JSONL。续传保留 nano 现有 agent_id 接口，不虚构 SendMessage。适用于显式后台与前台自动转后台；运行中 follow-up 的提示不得与之矛盾。

不新增 TaskOutput、worktree 隔离或 cwd 参数，不改变子会话持久化、完成通知和停止机制，不部署服务。

## 根因

Read 的 _truncate_head_lines 仅保留能放入预算的完整行；首行过长时输出为空。to_model_output 只检查空字符串，丢失 total_lines/truncated 信息，错误标为空文件。原本的读取预算必须保留，改为显式失败而非静默丢失所选内容。

Agent 的后台返回把原始 JSONL 当作进度接口推荐给模型，虽然现有后台任务机制已经提供完成通知。已安装 CC 2.1.268 的受控实验表明，启动结果保留 output_file 但明确禁止 Read/tail，并要求等待通知。现有 nano API、agent identity 和一次完成通知不应改变。

证据：本次对话中的生产工具结果与 CC 2.1.268 实验；CC 主模型 sol、子模型 terra、effort high，后台任务正常完成。参考源码与安装版提示有差异，以实际安装版返回为准。

## 修复

- Read 对所选文本先校验既有行数/字节预算；超限抛出 ToolError，保留实际值、上限与分段/搜索建议，失败不登记到读取状态。预算内的结果结构和图片读取不变。
- agent 的显式后台与自动后台共用启动返回，按照实测 CC 2.1.268 返回改为内部元数据提示、禁止预测或重复工作、禁止 Read/tail JSONL、等待完成通知。运行中 follow-up 与工具 schema 提示同步纠偏，续传保留 nano API。
- 当前契约已归并到 kernel tools-hooks / background-tasks。更新已有测试，不新增平行测试文件；移除旧 Read 截断断言，改为超限错误、UTF-8 字节、边界成功、缩小范围重试和失败不缓存的回归保护。
- 实现：b110a7394220b8e860efab4436ebed31d4d9075f；旧描述测试校正：4faf5bdfbd40bd40e1a3a8191d9c686bb11d5108。

## 验证

- 修前：针对性回归 8 failed / 43 passed，确认缺失超限错误及后台返回约束。
- 修后：Read / agent / contract 聚焦 51 passed；全量发现旧描述断言后校正，相关 54 passed。
- SDK 一次性探针：58,797 字节首行通过真实工具执行器和 Anthropic mapper，在下一轮请求中得到 `File content (57.4KB) exceeds maximum allowed size (50.0KB)` 及分段/搜索建议，无空文件误报。模型客户端为确定性驱动，无新外部 LLM 调用；未改变全局 provider 协议。
- 全量非 E2E：3866 passed，唯一失败是仍期待旧 Read 描述的测试；已校正且其所属文件与全部聚焦回归再次通过。
- 最终同步主干 bugfix-558 后相关 103 passed；该增量仅涉及 PA Skill roots，没有修改本次 Read/agent 文件。
- Ruff check、Ruff format --check、docs-check、git diff --check 通过。
- 独立 change-code-review finder 完整审查：[]，没有需交独立 verifier 的候选。详见 M1-fix/code-review.md。
- 前端 CI 等价检查：npm ci、critical audit 通过；全量 757 passed / 2 failed（渲染等待与 5 秒超时），未修改前端，单独复跑两个文件 72 passed。远端 CI 以最终 PR 为准。
