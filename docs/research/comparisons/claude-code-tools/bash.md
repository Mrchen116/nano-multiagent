# `bash` 工具实现对比：nano-multiagent vs claude-code

## 1. 接口与 Schema

### nano-multiagent
- **字段极简**：仅 `command`（必填，string）和 `timeout`（可选，number，单位秒）。
- **无额外元数据**：没有描述、后台运行、沙箱控制等字段。
- **无 `description`**：无描述字段用于权限弹窗展示。
- **Schema 示例**：
  ```python
  {
      "type": "object",
      "properties": {
          "command": {"type": "string", "description": "Bash command to execute"},
          "timeout": {"type": "number", "description": "Timeout in seconds (optional, no default timeout)"},
      },
      "required": ["command"],
      "additionalProperties": False,
  }
  ```

### claude-code
- **字段丰富**：`command`（必填）、`timeout`（可选，number，单位毫秒，上限由配置决定）、`description`（用于权限弹窗展示）、`run_in_background`（后台运行）、`dangerouslyDisableSandbox`（显式关闭沙箱）、`_simulatedSedEdit`（内部模拟 sed 编辑）。
- **严格校验**：使用 `z.strictObject` 禁止额外字段；`semanticNumber` 和 `semanticBoolean` 增强 LLM 理解。
- **Schema 示例**：
  ```typescript
  z.strictObject({
    command: z.string().describe('The command to execute'),
    timeout: semanticNumber(z.number().optional()).describe(
      `Optional timeout in milliseconds (max ${getMaxTimeoutMs()})`,
    ),
    description: z.string().optional().describe(...),
    run_in_background: semanticBoolean(z.boolean().optional()).describe(...),
    dangerouslyDisableSandbox: semanticBoolean(z.boolean().optional()).describe(...),
    _simulatedSedEdit: z.object({ filePath: z.string(), newContent: z.string() }).optional(),
  })
  ```

---

## 2. 核心实现细节

### nano-multiagent
- **执行方式**：`subprocess.Popen(["bash", "-c", command], ...)`，使用 `selectors.DefaultSelector` 对 stdout/stderr 做非阻塞流式读取。
- **超时处理**：通过 `threading.Timer` 在超时后 `kill()` 进程。
- **输出截断**：按行数和字节数双重截断，超长的完整输出写入临时文件，返回中附带临时文件路径。
- **事件流**：支持 `event_stream=True` 将输出实时推送到事件流。
- **代码位置**：`/Users/czj/Repos/nano-multiagent/src/agent/platform/tools/safety.py`

### claude-code
- **执行方式**：`runShellCommand()` 返回异步生成器（async generator），支持逐块输出和进度更新。
- **后台任务**：支持 `run_in_background`，助手模式下若命令运行超过 15 秒会自动转为后台任务，返回 `backgroundTaskId`。
- **输出持久化**：大输出写入 `persistedOutputPath`，支持图片检测（`isImage`）。
- **模拟编辑**：`_simulatedSedEdit` 用于在不实际执行 sed 的情况下做内容替换，绕过权限检查。
- **代码位置**：`/Users/czj/Repos/opensource-hub/claude-code/src/tools/BashTool/BashTool.tsx`

---

## 3. 安全与权限

### nano-multiagent
- **策略模型**：前缀白名单 + 禁止片段。
- **允许前缀**：
  ```python
  bash_allowed_prefixes = (
      "bash", "cat", "command -v", "echo", "false", "git", "head", "ls",
      "pwd", "pytest", "python", "python3", "rg", "sed", "sleep", "tail",
      "true", "wc",
  )
  ```
- **检查方式**：将命令按 `&&` 拆分后，检查每段是否以允许前缀开头；若不在白名单则抛出 `ToolError`。
- **无 AST 分析**：纯字符串前缀匹配，无深度解析。
- **代码位置**：`/Users/czj/Repos/nano-multiagent/src/agent/platform/tools/safety.py`

### claude-code
- **多层安全体系**：
  1. **模式权限**（`modeValidation.ts`）：`acceptEdits` 模式下自动允许 `mkdir`、`touch`、`rm`、`rmdir`、`mv`、`cp`、`sed`。
  2. **用户权限规则**（`bashPermissions.ts`）：支持 `exact`、`prefix`、`wildcard` 三种规则，可配置为 `allow`、`ask`、`deny`。
  3. **AST 安全分析**（`bashSecurity.ts` / `bashPermissions.ts`）：集成 tree-sitter 对命令做语法树解析，检测注入、混淆、危险变量等。
  4. **路径约束**（`pathValidation.ts`）：对 ~30 个常用命令提取路径，校验读写权限、阻止 `cd` 后的写操作、阻止危险删除路径（如 `rm -rf /`）。
  5. **复合命令检查**（`bashCommandHelpers.ts`）：对管道和逻辑运算符拆分段落，逐段校验；禁止子 shell 和命令组。
  6. **沙箱决策**（`shouldUseSandbox.ts`）：根据全局配置、`dangerouslyDisableSandbox` 标志和用户排除列表决定是否启用沙箱。
  7. **破坏性警告**（`destructiveCommandWarning.ts`）：对 `git reset --hard`、`rm -rf`、`DROP TABLE`、`terraform destroy` 等命令在权限弹窗中显示警告信息（仅提示，不影响决策）。
- **安全校验器列表**（`bashSecurity.ts`）：不完整命令、jq 系统函数、混淆标志、shell 元字符、危险变量、换行符、命令替换 `$()` / `${}`、进程替换 `<()` / `>()`、IFS 注入、git commit 替换、`/proc/environ` 访问、畸形 token 注入、反斜杠转义空白/操作符、brace expansion、控制字符、Unicode 空白、Zsh 危险命令等 20 余项。

---

## 4. 错误处理

### nano-multiagent
- **非零退出码统一转为 `ToolError`**：包含退出码、信号名、超时信息、截断后的 stdout/stderr。
- **策略违规直接抛错**：命令不在白名单内时立即拒绝，无用户交互。
- **超时错误**：通过 `threading.Timer` 触发，返回明确的超时信息。

### claude-code
- **权限结果对象**：`PermissionResult` 区分 `allow`、`ask`、`deny`、`passthrough`，支持携带 `updatedInput` 和 `decisionReason`。
- **执行错误**：通过异步生成器流式返回错误状态；支持 `interrupted` 标记。
- **后台任务错误**：后台任务的状态通过独立接口查询，错误不会阻塞主流程。
- **AST 解析失败降级**：若 tree-sitter 不可用，回退到同步的 `bashCommandIsSafe_DEPRECATED`（基于正则和 shell-quote）。

---

## 5. 输出格式与返回值结构

### nano-multiagent
`run()` 返回结构化字典：
```python
{
    "stdout": execution.text,
    "stderr": "",
    "exitCode": execution.exit_code,
    "truncated": execution.truncated,
    "fullOutputPath": execution.full_output_path,  # optional
}
```
- **stdout / stderr 分离**：独立字段，不再混在字符串里
- **退出码**：显式返回 `exitCode`
- **截断标记**：`truncated` 为 `True` 时，完整输出已写入临时文件，`fullOutputPath` 指向该文件

### claude-code
- **结构化输出对象**：
  ```typescript
  {
    stdout?: string
    stderr?: string
    rawOutputPath?: string      // 原始大输出文件路径
    interrupted?: boolean       // 是否被中断
    isImage?: boolean           // 输出是否为图片
    backgroundTaskId?: string   // 后台任务 ID
    persistedOutputPath?: string // 持久化输出路径
  }
  ```
- **流式输出**：通过 async generator 产生 `Progress` 和 `Result` 事件，前端可实时渲染。
- **图片支持**：自动检测输出是否为图片格式，前端可直接渲染。

### `serialize_result` / `mapToolResultToToolResultBlockParam` 对比

这是工具业务结果 → LLM 可见 `tool_result` 的**转换层**。

#### nano-multiagent (`serialize_result`)
```python
def serialize_result(self, output: Any, error: str | None = None) -> str:
    if error is not None:
        return error
    if not isinstance(output, Mapping):
        return json_serialize(output)
    stdout = output.get("stdout", "") or ""
    truncated = output.get("truncated", False)
    full_output_path = output.get("fullOutputPath")
    if stdout:
        stdout = stdout.lstrip("\n")
        stdout = stdout.rstrip()
    if truncated and full_output_path:
        preview = stdout[:500] if stdout else ""
        stdout = (
            f"{preview}\n"
            f"(Output truncated. Full output written to: {full_output_path})"
        )
    return stdout or "(no output)"
```
- **错误透传**：若 `error` 非空，直接返回错误文本
- **stdout 清洗**：去除前导换行、trim 尾部空白，避免模型被无意义换行干扰
- **截断提示**：超限时保留前 500 字符预览，并追加完整输出文件路径
- **不再 JSON 序列化**：直接返回精简文本，不占用模型 token

#### claude-code (`mapToolResultToToolResultBlockParam`)
```typescript
mapToolResultToToolResultBlockParam({ interrupted, stdout, stderr, isImage, backgroundTaskId, backgroundedByUser, assistantAutoBackgrounded, structuredContent, persistedOutputPath, persistedOutputSize }, toolUseID) {
  // 1. 结构化内容优先（如 MCP 工具返回的 block 数组）
  if (structuredContent && structuredContent.length > 0) {
    return { tool_use_id: toolUseID, type: 'tool_result', content: structuredContent }
  }

  // 2. 图片输出 → 原生 image block
  if (isImage) {
    const block = buildImageToolResult(stdout, toolUseID)
    if (block) return block
  }

  // 3. stdout 清洗：去除前导空行、trim 尾部
  let processedStdout = stdout
  if (stdout) {
    processedStdout = stdout.replace(/^(\s*\n)+/, '')
    processedStdout = processedStdout.trimEnd()
  }

  // 4. 大输出持久化：替换为 <persisted-output> 消息 + preview
  if (persistedOutputPath) {
    const preview = generatePreview(processedStdout, PREVIEW_SIZE_BYTES)
    processedStdout = buildLargeToolResultMessage({
      filepath: persistedOutputPath, originalSize: persistedOutputSize ?? 0,
      isJson: false, preview: preview.preview, hasMore: preview.hasMore,
    })
  }

  // 5. stderr + 中断标记
  let errorMessage = stderr.trim()
  if (interrupted) {
    if (stderr) errorMessage += EOL
    errorMessage += '<error>Command was aborted before completion</error>'
  }

  // 6. 后台任务信息
  let backgroundInfo = ''
  if (backgroundTaskId) {
    const outputPath = getTaskOutputPath(backgroundTaskId)
    if (assistantAutoBackgrounded) {
      backgroundInfo = `Command exceeded the assistant-mode blocking budget (...) and was moved to the background with ID: ${backgroundTaskId}. It is still running — you will be notified when it completes. Output is being written to: ${outputPath}. In assistant mode, delegate long-running work to a subagent or use run_in_background to keep this conversation responsive.`
    } else if (backgroundedByUser) {
      backgroundInfo = `Command was manually backgrounded by user with ID: ${backgroundTaskId}. Output is being written to: ${outputPath}`
    } else {
      backgroundInfo = `Command running in background with ID: ${backgroundTaskId}. Output is being written to: ${outputPath}`
    }
  }

  // 7. 拼接为单条文本，标记 is_error
  return {
    tool_use_id: toolUseID, type: 'tool_result',
    content: [processedStdout, errorMessage, backgroundInfo].filter(Boolean).join('\n'),
    is_error: interrupted,
  }
}
```
- **文本清洗**：去除前导空行 + trimEnd，避免模型被无意义的换行干扰
- **大输出降级**：超限时替换为 `<persisted-output>` 摘要，模型知道去哪个文件看完整输出
- **结构化内容直通**：MCP 等工具返回的 block 数组直接透传，不走字符串拼接
- **后台任务信息**：明确告诉模型任务 ID、输出路径、后续操作建议
- **is_error 标记**：`interrupted` 时设置 `is_error: true`，API 层面让模型知道这是异常结果

---

## 6. 边缘情况处理

### nano-multiagent
- **`&&` 复合命令拆分**：简单按 `&&` 拆分后逐段检查前缀。
- **输出截断**：按最大行数和最大字节数截断，防止上下文溢出。
- **超时**：支持可选超时，超时后强制 kill 进程。
- **局限性**：无管道、子 shell、重定向、环境变量注入等专项检查。

### claude-code
- **复合命令与管道**：`bashCommandHelpers.ts` 将管道和逻辑运算符拆分为独立段，逐段走完整权限流程；禁止子 shell `(...)` 和命令组 `{...}`。
- **环境变量剥离**：权限匹配时迭代剥离前导环境变量（如 `FOO=bar bazel ...`）和安全包装器（如 `timeout 30 ...`），防止绕过。
- **重定向路径检查**：`pathValidation.ts` 解析输出重定向（`>`、`>>`、`<`），校验目标路径是否在允许的工作目录内。
- **危险删除路径**：阻止 `rm -rf /`、`rm -rf ~`、`rm -rf .` 等高风险操作。
- **后台任务自动切换**：助手模式下命令运行超过 15 秒自动转为后台，避免阻塞对话。
- **Unicode 与控制字符**：`bashSecurity.ts` 检测 Unicode 空白、控制字符、反斜杠转义操作符等混淆手段。
- **Zsh 专属危险命令**：检测 `sudo` 配合 `!!`、`!*` 等历史扩展。

---

## 7. 关键差异与 nano-multiagent 可借鉴之处

| 维度 | nano-multiagent | claude-code | 借鉴建议 |
|:---|:---|:---|:---|
| **Schema 设计** | 极简，仅 command + timeout | 丰富，含描述、后台运行、沙箱开关、模拟编辑 | 增加 `description` 和 `run_in_background` 等字段，提升可控性 |
| **权限模型** | 简单前缀白名单 | 多层：模式权限 + 用户规则 + AST 分析 + 路径约束 + 沙箱决策 | 引入规则引擎（exact/prefix/wildcard）替代单一白名单 |
| **安全分析** | 无 AST，纯字符串匹配 | tree-sitter AST + 20+ 专项校验器 | 集成 bash AST 解析器，检测命令替换、进程替换、IFS 注入等 |
| **路径安全** | 无 | 对 ~30 个命令做路径提取与读写分类校验 | 增加路径解析层，阻止危险删除和越界写操作 |
| **复合命令** | 仅按 `&&` 拆分 | 支持管道、逻辑运算符拆分，并禁止子 shell | 扩展复合命令分析，覆盖 `\|`、`;`、子 shell |
| **错误处理** | 统一抛 `ToolError` | 结构化 `PermissionResult` + 流式错误 | 采用结构化结果对象，区分 allow/ask/deny |
| **输出管理** | 字符串 + 临时文件路径 | 结构化对象 + 持久化路径 + 图片检测 + 后台任务 ID | 返回结构化字典，支持大输出持久化和图片识别 |
| **用户体验** | 策略违规直接拒绝 | 破坏性警告、权限弹窗描述、自动后台化 | 增加破坏性命令提示和可选的后台执行能力 |
| **沙箱集成** | 由 `ToolSafety` 统一封装 | 独立的 `SandboxManager` + `shouldUseSandbox` 决策 | 将沙箱启用逻辑从执行层中抽离，单独决策 |

**总结**：claude-code 的 `bash` 工具是一个高度工程化的系统，安全、权限、执行、输出、用户体验各层职责清晰。nano-multiagent 当前实现简洁高效，适合快速原型，但在面向生产环境时，建议逐步引入 claude-code 的分层安全架构——尤其是 **AST 驱动的安全分析**、**细粒度路径校验** 和 **结构化权限结果**。
