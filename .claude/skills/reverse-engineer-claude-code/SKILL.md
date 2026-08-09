---
name: reverse-engineer-claude-code
description: 逆向研究 Claude Code 当前功能，产出可复现的行为与实现契约。当用户要求理解、复现、移植或对比 Claude Code 的系统提示词、工具契约、Agent 编排、持久化、权限流程或隐藏运行时实现时使用，尤其适用于本地开源重建版本较旧或仅含桩实现的情况；不用于普通使用说明或无需逆向取证的常规开发任务。
---

# 逆向研究 Claude Code

从三条主要证据路径重建行为，必要时再升级到已安装包或二进制文件分析。始终区分厂商事实、直接观察和实现推论，使其他工程师可以复现调查过程及其设计结论。

## 不可变默认规则

- 主 Claude Code 进程及其所有子 Agent 默认使用 `codexOAuth:gpt-5.6-luna`，除非用户明确授权使用其他模型。
- 从 `CLAUDE_CODE_EFFORT_LEVEL=low`、单个 Agent、不调用工具且每次只测试一个变量开始。
- 把真实模型调用视为有预算的实验。不要仅为证明存在并行能力而扩大并发规模。
- 实验默认只读；只有无法通过只读操作区分目标功能，且用户已授权写入时，才能执行写操作。
- 把捕获请求中的 `system + tools + messages` 视为该已安装版本在对应执行分支上实际面向模型提供方的完整提示词。保留原始内容及其定位信息；可以把原文直接写入研究产物，但必须排除 secret、本机配置等仓库明确禁止提交的内容，并标记删节位置。
- 公开契约必须以 Anthropic 当前官方文档为依据。社区帖子只能作为发现线索，不能作为权威来源。
- 只能以只读方式分析用户本机已安装的软件包或二进制文件。不得修改可执行文件、绕过许可或保护机制，也不得提取无关秘密。

运行真实实验或撰写最终重建结论前，先阅读 [`references/experiment-playbook.md`](references/experiment-playbook.md)。

## 工作流

### 1. 提出可判别的问题

把请求转化为可以由一次观察证实或证伪的主张，例如：

- 功能由什么精确条件激活？
- 编排由模型选择、CLI 选择，还是两者共同选择？
- 哪一层工具 schema 和提示词指导模型？
- 工具调用会阻塞、返回任务句柄，还是稍后发出通知？
- 哪些状态会持久化，恢复会复用什么？
- 子 Agent 继承哪些权限？

不要从宽泛的演示开始。维护一张假设表，至少包含 `claim`、`lane`、`observation`、`confidence` 和 `remaining unknown`。

### 2. 固定本地源码证据

解释代码前，先记录两个仓库的状态：

```bash
git -C <nano-repo> rev-parse HEAD
git -C <claude-code-repo> rev-parse HEAD
git -C <claude-code-repo> status --short --branch
```

如果上游 checkout 存在未提交修改，用 `git show HEAD:<path>` 检查已提交基线，并把只存在于工作区的内容单独标注。依次搜索：

1. 功能开关、注册入口、命令接线、设置项和权限界面；
2. 目标工具实现或生成的桩代码；
3. 相邻且完整的基础能力，例如 Agent 执行、查询循环、任务状态、通知和流式工具调度；
4. 即使实现缺失也能暴露行为的测试和 schema。

空桩只能证明功能预留了落点，不能证明该功能只存在于客户端、只存在于服务端，或不存在于已安装的二进制文件中。

### 3. 建立官方契约

搜索当前 Claude Code 官方文档和发布说明。记录 URL、访问日期、适用的 CLI 版本、激活规则、限制、权限、持久化、模型选择和已记录的失败行为。

如果没有找到官方契约，记录可复现的反向搜索：搜索过的官方入口、精确查询词或关键词、版本或日期范围、访问日期，以及被排除的近似结果。表述为“在本次搜索范围内未找到”，不要表述为“没有文档”。

如果已安装 CLI 与文档不一致，报告差异并只测试该项行为，不要悄悄选择其中一方。CLI 的 `--help` 文本可能落后于隐藏设置或新发布设置。

### 4. 运行最小真实轨迹

确认代理健康状态和已安装 CLI 版本。导出用户已有的代理设置，然后强制主进程和子进程都使用 Luna：

```bash
export ANTHROPIC_MODEL="codexOAuth:gpt-5.6-luna"
export CLAUDE_CODE_SUBAGENT_MODEL="codexOAuth:gpt-5.6-luna"
export CLAUDE_CODE_EFFORT_LEVEL=low
```

只能由人工输入激活的功能必须使用交互式终端。除非官方契约明确说明非人工输入来源等价，否则不要用 `claude -p` 替代。为实验设定明确的停止条件，并捕获：

- Claude Code session ID 和版本；
- 代理 session 目录；
- 在汇总前从 LLM Proxy 逐字检查完整请求 envelope：`model`、`max_tokens`、`output_config`/effort、`stream`、`metadata`、`system`、`tools`、`messages`、缓存控制、日志中存在的 beta/header 元数据，以及代理与上游路由字段；
- 目标工具的精确 schema 和 description；
- 生成的脚本或计划；
- task/run 状态、journal 事件和通知形态；
- 子请求的提示词栈和工具集；
- 与实际执行相关的完整响应 envelope：content/工具调用、stop reason/details、usage 与 cache usage、service tier、耗时、错误，以及代理与上游的映射关系。

使用以下命令汇总代理请求：

```bash
python3 .claude/skills/reverse-engineer-claude-code/scripts/inspect_anthropic_session.py \
  <proxy-session-directory> --tool Workflow
```

只有确实需要精确文本时才使用 `--show-system` 或 `--show-last-message`；这些模式可能暴露仓库上下文，不得把输出原样提交。

### 5. 升级到已安装包或二进制文件分析

只有当源码、官方文档和现有轨迹仍留下影响实现的重大问题时，才使用这条证据路径。操作前先阅读 [`references/binary-analysis-playbook.md`](references/binary-analysis-playbook.md)。

先检查已安装版本、包元数据、wrapper、签名、链接的运行时和精确功能字符串。对于打包的 JavaScript/原生可执行文件，在考虑原生反汇编前，先恢复并检查内嵌 JavaScript 调用点。二进制文件里仅仅存在某个运行时或 parser 字符串，不足以证明该功能使用它；必须串起功能特定的验证、编译和执行调用链。

记录 `claude --version` 的输出、二进制文件绝对路径、文件格式、签名者、运行时或编译器标记、相关字节偏移或提取的函数片段，以及分析边界。把这些主张标记为 **Binary observation**，并与较旧的本地源码基线和真实运行行为分开。

### 6. 重建提示词栈

对于每个捕获请求，先检查 LLM Proxy 的原始请求 JSON。`system`、`tools` 和 `messages` 字段是 Claude Code 实际提供给模型提供方的逐字提示词，其余顶层字段则是该次调用实际使用的请求参数。这是直接运行时证据，不是根据 transcript 近似重建的提示词。

始终区分以下层次：

1. CLI 基础 system prompt；
2. 功能激活附件或 system reminder；
3. 目标工具 description 和输入 schema；
4. 主模型编写的脚本或任务提示词；
5. 子 Agent system prompt 和工作流专用附加指令；
6. 返回主对话的异步任务通知。

根据研究需要直接引用或提交精确捕获的原文，并保留轨迹定位信息；如果为遵守仓库红线而删除内容，明确标记删节位置。只有任务范围明确包含可移植重实现时，才另写一份**自行编写的替代提示词（authored surrogate prompt）**；不得用该替代提示词取代对精确捕获提示词的分析。

不要把单条分支的观察夸大成通用结论。一次请求无法揭示尚未捕获的激活方式、权限结果、已保存或远程工作流、错误路径及后续版本的提示词变体。代理之后由模型提供方附加的指令也不属于 Claude Code 请求 payload，必须单独标注。

### 7. 产出实现契约

交付物必须覆盖：

- 激活条件和适用资格；
- 公开输入及面向模型的输入；
- 调度和并发；
- 子上下文和工具权限；
- 权限与审批边界；
- 持久化、journal、通知和恢复；
- 错误、取消和部分结果；
- 已保存或内置的入口；
- 成本控制和模型路由；
- 源码落点和可复用的相邻组件；
- 未知项，以及解决每一项未知所需的最低成本实验。

把每一条重要陈述标记为以下类型之一：

- **Official fact** — 当前一手官方文档；
- **Source observation** — 固定 commit 的本地源码；
- **Runtime observation** — 可定位到具体 trace/session 的观察；
- **Binary observation** — 来自已记录安装版本和调用点的只读证据；
- **Inference** — 实现兼容行为所需的综合推论。

## 停止条件

当官方契约、源码落点和一条运行时轨迹在请求关注的行为上相互印证时，停止实验。只有新的实验会改变实现决策或解决重大矛盾时，才继续实验。提高模型档位、增加 Agent 数量或扩大写入范围前，必须先征得用户同意。

## 交付物

对于较大规模的调查，创建一份带日期的研究快照，其中包含：

- `README.md` — 状态、范围、基线、当前负责人和产物索引；
- `research.md` — 证据账本、精确定位、观察结果和局限；
- 面向读者的文章 — 运行模型、提示词栈、运行时状态机和重实现蓝图。

从研究索引链接到该资料包。在逆向行为被正式采纳并完成实现前，不要把它提升为当前产品规范。
