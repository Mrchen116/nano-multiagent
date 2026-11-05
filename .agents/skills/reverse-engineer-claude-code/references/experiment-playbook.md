# Claude Code 真实实验手册

运行受控轨迹或解释现有请求时使用；已有有效证据可复用。

## 成本与现场

使用能够区分当前假设的最小实验，沿用用户已配置/授权的模型与代理；只有实验确需不同模型或并发时才调整，并遵守既有预算。无需固定型号、effort 或逐级跑完所有实验。

在隔离目录运行；仓库指令属于待验假设时记录目标 commit 与 dirty 状态。保留无关工作，不复制占位凭据或重写用户的代理配置。记录实际主/子模型、effort、token 与耗时；无工具调用也可能有大量上下文成本。

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

## 轨迹定位

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
