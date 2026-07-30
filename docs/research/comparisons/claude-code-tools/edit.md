# nano-multiagent 与 claude-code 的 `edit` 工具实现对比

## 1. 接口与 Schema

### nano-multiagent (`EditTool`)
- **参数**: `path` (string), `oldText` (string), `newText` (string)
- **必填**: 三个参数全部必填
- **额外属性**: `additionalProperties: False`
- **无类型校验库**: 手写 JSON Schema，无运行时类型校验
- **无 `replace_all`**: 只能单次替换
- **无 `description`**: 无描述字段用于权限弹窗展示

### claude-code (`FileEditTool`)
- **参数**: `file_path` (string), `old_string` (string), `new_string` (string), `replace_all` (boolean, optional, default false)
- **Schema 引擎**: 使用 `zod/v4` 做严格对象校验 (`z.strictObject`)
- **`semanticBoolean`**: `replace_all` 支持语义化布尔值解析
- **输出也有 Schema**: `outputSchema` 用 zod 定义了 `FileEditOutput`
- **支持批量编辑概念**: 内部工具 `getPatchForEdits` 可处理多段编辑，但单次 `FileEditTool.call` 只接收一个 edit

### 关键差异
| 特性 | nano-multiagent | claude-code |
|---|---|---|
| Schema 严格度 | 手写 JSON Schema | Zod 运行时校验 |
| replace_all | 不支持 | 支持 |
| 参数命名 | `oldText`/`newText` | `old_string`/`new_string` |
| 输出 Schema | 无 | 有 |

---

## 2. 核心实现细节

### nano-multiagent
- **替换方式**: `source.replace(old_text, new_text, 1)` — 单次替换
- **唯一性检查**: `source.count(old_text)`，0 则报错，>1 则报错
- **diff 生成**: Python `difflib.unified_diff`，基于整文件行列表
- **无预处理**: 直接按用户输入的字符串匹配，不做引号、空格、反斜杠等规范化

### claude-code
- **替换方式**: `applyEditToFile()` 包装 `String.prototype.replace` / `replaceAll`
- **quote 规范化 (`findActualString`)**: 若直接匹配失败，自动将弯引号（curly quotes）转为直引号再试匹配
- **quote 保留 (`preserveQuoteStyle`)**: 匹配成功后，若文件里用的是弯引号，自动把 `new_string` 里的直引号按上下文转成对应的弯引号
- **尾部空格处理**: `stripTrailingWhitespace`（Markdown 文件除外）
- **desanitize**: 针对 API 脱敏标签（如 `<fnr>` → `<function_results>`）做自动还原匹配
- **diff 生成**: 使用 `diff` 库的 `structuredPatch`，并做 `convertLeadingTabsToSpaces` 预处理
- **多 edit 支持**: `getPatchForEdits` 内部可串行应用多个 edit，并检查 `old_string` 是否是前面某个 `new_string` 的子串，防止重叠/顺序错误

### 关键差异
| 特性 | nano-multiagent | claude-code |
|---|---|---|
| 引号兼容 | 无 | 弯引号 ↔ 直引号自动适配 |
| 脱敏标签兼容 | 无 | 自动 desanitize |
| 尾部空格 | 不处理 | 自动 strip（Markdown 除外） |
| 多 edit 原子性 | 不支持 | 内部支持多 edit 并做冲突检查 |
| diff 库 | Python difflib | `diff` npm 包 (structuredPatch) |

---

## 3. 安全 / 沙盒

### nano-multiagent
- **路径解析**: `ctx.safety.resolve_path(raw_path, cwd=ctx.cwd, tool_name=self.name)`
- **文件存在性**: 检查 `file_path.exists() and file_path.is_file()`
- **无大小限制**: 未对大文件做限制
- **无 UNC/SMB 防护**: 无特殊路径过滤
- **无读取前置要求**: 不强制要求先 read 再 edit

### claude-code
- **路径解析**: `expandPath(file_path)`，统一处理 `~`、相对路径、Windows 路径分隔符
- **权限检查**: `checkWritePermissionForTool` + `matchingRuleForInput` deny 规则
- **UNC 路径安全**: 显式跳过 `\\` 或 `//` 开头的 UNC 路径，防止 `fs.existsSync` 触发 SMB NTLM 凭据泄漏
- **大文件保护**: `MAX_EDIT_FILE_SIZE = 1 GiB`，超限时拒绝编辑
- **强制先读**: `readFileState` 校验，若文件未被 `Read` 工具完整读取过，则拒绝编辑
- **staleness 检查**: 对比最后修改时间与 `readFileState` 中的 timestamp；Windows 上若 timestamp 变化但内容没变，还会做内容回退比对
- **Team Memory Secret Guard**: `checkTeamMemSecrets` 防止向团队记忆文件写入敏感信息
- **Settings 文件额外校验**: `validateInputForSettingsFileEdit` 对 Claude 设置文件做专门校验

### 关键差异
| 特性 | nano-multiagent | claude-code |
|---|---|---|
| 强制先 read | 否 | 是 |
| 文件 staleness | 无 | timestamp + 内容双重检查 |
| 大文件限制 | 无 | 1 GiB |
| UNC/SMB 防护 | 无 | 显式跳过 |
| 权限规则 deny | 基础 resolve_path | 完整的 allow/deny 规则体系 |
| 敏感信息写入 | 无 | TeamMemSecrets 检查 |

---

## 4. 错误处理

### nano-multiagent
- **统一异常类**: `ToolError`
- **错误场景**:
  1. `oldText` 为空 → `oldText cannot be empty`
  2. 文件不存在 → `file does not exist`
  3. 未找到匹配 → `Could not find the exact text to replace`
  4. 多个匹配 → `Found multiple matches; text must be unique`
  5. 替换后无变化 → `No changes made`
- **无错误码**: 纯文本消息
- **无行为区分**: 全部直接报错

### claude-code
- **校验阶段返回对象**: `{ result: false, behavior: 'ask', message, errorCode, meta? }`
- **错误码体系** (部分):
  - `1`: `old_string === new_string`
  - `2`: deny 规则命中
  - `3`: 文件已存在但 `old_string` 为空（试图创建已存在文件）
  - `4`: 文件不存在且 `old_string` 非空
  - `5`: `.ipynb` 文件要求用 `NotebookEditTool`
  - `6`: 文件未先读取
  - `7`: 文件在读取后被外部修改
  - `8`: 未找到匹配字符串
  - `9`: 多个匹配但 `replace_all` 为 false
  - `10`: 文件过大
- **运行时抛错**: `FILE_UNEXPECTEDLY_MODIFIED_ERROR`（原子写入阶段发现内容被改）
- **元数据丰富**: 很多错误带 `meta`（如 `isFilePathAbsolute`, `actualOldString`）

### 关键差异
| 特性 | nano-multiagent | claude-code |
|---|---|---|
| 错误码 | 无 | 有 (errorCode) |
| 行为策略 | 全部报错 | 校验阶段可 `behavior: 'ask'` 让用户确认 |
| 错误元数据 | 无 | `meta` 对象 |
| 文件类型引导 | 无 | `.ipynb` 引导到 NotebookEditTool |

---

## 5. 输出格式 / 返回值结构

### nano-multiagent
`run()` 返回结构化字典：
```python
{
    "filePath": str(file_path),
    "displayPath": display_path,
    "replaceAll": False,
    "details": {
        "diff": <unified_diff_string>,
        "firstChangedLine": <int>,
    },
}
```

### claude-code
```typescript
{
    data: {
        filePath: string,
        oldString: string,
        newString: string,
        originalFile: string,
        structuredPatch: StructuredPatchHunk[],
        userModified: boolean,
        replaceAll: boolean,
        gitDiff?: GitDiff,
    }
}
```
- **结构化 patch**: 不是纯文本 diff，而是带 `oldStart/oldLines/newStart/newLines/lines` 的对象数组
- **原始文件内容**: 返回 `originalFile`，方便 UI 做前后对比
- **userModified**: 标记用户是否在确认前修改了建议内容
- **gitDiff**: 远程模式下可选附加真实 Git diff

### 关键差异
| 特性 | nano-multiagent | claude-code |
|---|---|---|
| diff 格式 | 纯文本 unified diff | 结构化 hunks 数组 |
| 返回原始内容 | 否 | 是 |
| 用户修改标记 | 无 | `userModified` |
| Git diff 集成 | 无 | 可选 `gitDiff` |

### `serialize_result` / `mapToolResultToToolResultBlockParam` 对比

这是工具业务结果 → LLM 可见 `tool_result` 的**转换层**。

#### nano-multiagent (`serialize_result`)
```python
def serialize_result(self, output: Any, error: str | None = None) -> str:
    if error is not None:
        return error
    if not isinstance(output, Mapping):
        return json_serialize(output)
    file_path = output.get("displayPath", output.get("filePath", "unknown"))
    if output.get("replaceAll"):
        return (
            f"The file {file_path} has been updated. "
            "All occurrences were successfully replaced."
        )
    return f"The file {file_path} has been updated successfully."
```
- **错误透传**：若 `error` 非空，直接返回错误文本
- **极简人类可读摘要**：提取 `displayPath` / `filePath` 返回一句成功提示，不再整包 JSON 序列化
- **replaceAll 区分**：明确告知"全部替换" vs "单次替换"
- **Diff 去哪了**：`details.diff` 等结构化数据留给 UI 层展示，不占用模型 token

#### claude-code (`mapToolResultToToolResultBlockParam`)
```typescript
mapToolResultToToolResultBlockParam(data: FileEditOutput, toolUseID) {
  const { filePath, userModified, replaceAll } = data
  const modifiedNote = userModified
    ? '.  The user modified your proposed changes before accepting them. '
    : ''

  if (replaceAll) {
    return {
      tool_use_id: toolUseID, type: 'tool_result',
      content: `The file ${filePath} has been updated${modifiedNote}. All occurrences were successfully replaced.`,
    }
  }

  return {
    tool_use_id: toolUseID, type: 'tool_result',
    content: `The file ${filePath} has been updated successfully${modifiedNote}.`,
  }
}
```
- **极度精简**：只返回一句人类可读的成功/失败摘要，**不含 diff、不含原始内容**
- **replaceAll 区分**：明确告知"全部替换" vs "单次替换"
- **userModified 提示**：若用户在弹窗中修改了建议，追加提示 `. The user modified your proposed changes before accepting them.`
- **Diff 去哪了**：`structuredPatch` / `originalFile` 等结构化数据走 **UI 层** (`renderToolResultMessage`) 展示给人类，**不占用模型 token**

### 关键启示
claude-code 的设计哲学是：**给模型的 tool_result 要极简、纯文本、人类可读；给 UI 的数据要结构化、可渲染**。nano-multiagent 把 diff 和元数据全部 JSON 化塞进 tool_result，既浪费 token，又增加模型解析负担。

---

## 6. 边缘情况处理

### nano-multiagent
| 场景 | 处理 |
|---|---|
| 空 `oldText` | 显式拒绝 |
| 文件不存在 | 显式拒绝 |
| 0 匹配 | 拒绝 |
| >1 匹配 | 拒绝 |
| 替换后内容不变 | 拒绝 |
| 旧字符串是前面新字符串子串 | N/A（无多 edit） |
| 引号不一致 | 不匹配即失败 |
| 尾部空格差异 | 不匹配即失败 |
| Windows 换行符 | 未显式处理 |

### claude-code
| 场景 | 处理 |
|---|---|
| 空 `old_string` + 文件不存在 | 允许（创建新文件） |
| 空 `old_string` + 文件有内容 | 拒绝（errorCode 3） |
| 0 匹配 | 先尝试 quote normalize、desanitize，再失败 |
| >1 匹配 + `replace_all=false` | 拒绝并提示用户用 `replace_all` 或增加上下文 |
| 替换后内容不变 | `getPatchForEdits` 抛错 |
| 旧字符串是前面新字符串子串 | `getPatchForEdits` 抛错，防止重叠编辑 |
| 引号不一致 | `findActualString` 自动适配 |
| 尾部空格差异 | `stripTrailingWhitespace` 自动处理（Markdown 除外） |
| Windows 换行符 | 读取时统一 `\r\n` → `\n`；写入时保留原文件换行风格 |
| 文件在读取后被 linter/用户修改 | timestamp + 内容双重 staleness 检查 |
| 多字节编码 (UTF-16 LE BOM) | 读取时检测 BOM 并选 `utf16le` 编码 |

---

## 7. 关键差异总结与 nano-multiagent 可借鉴之处

### 7.1 规范化匹配（最值得借鉴）
**claude-code 的做法**: `findActualString` + `preserveQuoteStyle` + `desanitizeMatchString` + `stripTrailingWhitespace`  
**nano-multiagent 的现状**: 纯字面量匹配，极易因引号、尾部空格、API 脱敏标签导致失败。  
**建议**: 引入类似的“模糊但安全”的匹配层，至少处理：
- 弯引号 ↔ 直引号
- 尾部空格（非 Markdown）
- 换行符统一

### 7.2 强制先读机制
**claude-code 的做法**: `readFileState` 跟踪，edit 前必须完整读过文件。  
**nano-multiagent 的现状**: 无此限制。  
**建议**: 增加 `readFileState` 或类似状态机，避免模型在没看过文件的情况下盲目编辑。

### 7.3 staleness 检查
**claude-code 的做法**: 对比 timestamp，Windows 下还做内容回退比对。  
**nano-multiagent 的现状**: 无。  
**建议**: 在写入前做原子性读取-比对，防止外部修改（如 linter、用户手动编辑）导致覆盖。

### 7.4 `replace_all` 支持
**claude-code 的做法**: 参数化支持，且对多匹配场景给出明确错误提示。  
**nano-multiagent 的现状**: 不支持。  
**建议**: 增加 `replace_all` 参数，提升批量重命名等场景的可用性。

### 7.5 错误码与行为策略
**claude-code 的做法**: 校验阶段返回 `{ result, behavior, errorCode, meta }`，支持 `ask` 让用户确认。  
**nano-multiagent 的现状**: 直接抛 `ToolError`。  
**建议**: 将“可恢复/可确认”的错误与“致命错误”分离，给上层 UI 更多处理空间。

### 7.6 输出结构化
**claude-code 的做法**: 返回结构化 patch、原始文件内容、userModified 标记。  
**nano-multiagent 的现状**: 仅返回文本 diff 和首变更行号。  
**建议**: 将 diff 结构化，便于前端做语法高亮、折叠、side-by-side 对比。

### 7.7 安全与权限
**claude-code 的做法**: 大文件限制、UNC 路径跳过、TeamMemSecrets、settings 文件校验。  
**nano-multiagent 的现状**: 仅依赖 `ctx.safety.resolve_path`。  
**建议**: 逐步引入文件大小限制、敏感路径过滤、以及更细粒度的权限规则。
