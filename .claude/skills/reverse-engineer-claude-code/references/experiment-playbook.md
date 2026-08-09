# Claude Code 真实实验手册

只有源码和官方文档两条证据路径已经定位出具体未知项后，才使用本手册。

## 成本阶梯

从能够区分假设的最低层级开始，得到答案后立即停止：

| 层级 | 主进程/子进程 | 实验形态 | 用途 |
|---|---|---|---|
| L0 | 无 | 检查源码、文档、CLI help 和已有轨迹 | 始终首先执行 |
| L1 | Luna/Luna | 一个请求或一个子进程，不调用工具 | 激活条件、提示词、生命周期 |
| L2 | Luna/Luna | 两个子进程，输出简单结果 | 并行顺序或屏障语义 |
| L3 | Luna/Luna | 一个子进程，调用一个只读工具 | 子进程权限和工具传播 |
| L4 | 用户批准 | 只使用解决问题所需的最小更大规模 | 低层级无法推断的行为 |

记录实际 token 用量。即使子进程“不调用工具”，它的 system prompt、工具 schema、skill 和仓库附件仍会消耗输入 token，因此成本可能并不低。

## 受控环境

研究功能机制时优先使用干净的临时目录。如果仓库指令本身属于待验证假设，则使用目标仓库，但必须记录其 commit 和 dirty 状态。不得修改或清理用户无关变更。

使用用户已经授权的代理配置。以下是一组有代表性的低成本覆盖配置：

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:4000"
export ANTHROPIC_AUTH_TOKEN="token"
unset ANTHROPIC_API_KEY
export ANTHROPIC_MODEL="codexOAuth:gpt-5.6-luna"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="codexOAuth:gpt-5.6-luna"
export ANTHROPIC_DEFAULT_SONNET_MODEL="codexOAuth:gpt-5.6-luna"
export ANTHROPIC_DEFAULT_OPUS_MODEL="codexOAuth:gpt-5.6-luna"
export ANTHROPIC_DEFAULT_FABLE_MODEL="codexOAuth:gpt-5.6-luna"
export CLAUDE_CODE_SUBAGENT_MODEL="codexOAuth:gpt-5.6-luna"
export CLAUDE_CODE_EFFORT_LEVEL=low
```

不要把占位凭据复制进待提交文件，也不要假设这些值在用户已配置环境之外仍然有效。

## 实验记录

在 `research.md` 中记录以下结构：

```text
claim:
baseline:
  claude_version:
  repository_commit:
  working_tree:
  main_model:
  child_model:
  effort:
method:
  human_input_or_print_mode:
  exact_prompt:
  stop_condition:
result:
  session_id:
  proxy_locator:
  transcript_locator:
  generated_artifact_locator:
  status:
  tokens:
  duration:
observation:
limit:
```

如果官方文档搜索没有结果，另行添加一条搜索记录，包含 `official_entry_points`、`queries`、`version_or_date_range`、`accessed_at` 和 `rejected_near_matches`。结论必须限定在记录的搜索范围内。

## 轨迹阅读顺序

1. 在代理 session 中找到 `*-req-anthropic_messages.json` 文件。
2. 根据 `tools[]` 中的目标工具识别主请求。
3. 阅读主请求的 `system`、`messages`、`metadata`、`model` 和 effort 字段。
4. 提取目标工具的精确 description/schema。
5. 把工具调用与 Claude Code 对话 transcript 对齐。
6. 检查 session 目录下生成的脚本、state 和 journal 产物。
7. 根据 billing metadata、system identity、任务文本或时间识别子请求。
8. 把完成通知与主对话 transcript 对齐。

当时间戳冲突时，不要仅凭文件名推断顺序；使用 tool ID、task ID、run ID 和 journal 事件排序。

## 提示词证据规则

- 根据研究需要引用或提交精确原文。
- 明确文本来自 `system`、工具 description、生成脚本、子任务还是通知。
- 把追加到请求中的仓库指令和 skill 视为独立上下文，不要算作 Claude Code 的厂商提示词。
- 保留原始轨迹定位信息；如果为遵守仓库红线而删除内容，明确标记删节位置。
- 不得提交授权值、secret、本机配置或其他仓库明确禁止提交的内容。

## 矛盾处理

按以下优先级处理证据，不要对不同证据取平均：

1. 公开规范行为：当前官方文档。
2. 已安装版本观察：对应精确 CLI 版本的真实轨迹。
3. 实现落点：固定的源码基线。
4. 所有证据路径都未暴露的重实现细节：明确标注为推论。

源码桩和可工作的已安装二进制文件并不矛盾：这表示源码重建版本不包含已经发布的实现。`--help` 缺少某项内容而文档记录了运行时行为，可能表示 help 文本滞后；先测试再下结论。
