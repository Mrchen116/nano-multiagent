# `write` 工具实现对比：nano-multiagent vs. claude-code

## 1. 接口与 Schema

### nano-multiagent (`WriteTool`)
- **参数**：`path` (string), `content` (string)
- **路径类型**：支持相对路径或绝对路径
- **必填项**：`path`, `content`
- **附加属性**：`additionalProperties: False`
- **Schema 形式**：手写 Python dict
- **描述**：创建文件（不存在时）或覆盖（存在时），自动创建父目录

### claude-code (`FileWriteTool`)
- **参数**：`file_path` (string), `content` (string)
- **路径类型**：**强制要求绝对路径**，描述中明确说明 "must be absolute, not relative"
- **必填项**：`file_path`, `content`
- **Schema 形式**：Zod v4 严格对象 (`z.strictObject`)，懒加载 (`lazySchema`)
- **输出 Schema**：明确定义了返回值结构，包含 `type`、`filePath`、`content`、`structuredPatch`、`originalFile`、`gitDiff`

---

## 2. 核心实现细节

### nano-multiagent
```python
file_path = ctx.safety.resolve_path(raw_path, cwd=ctx.cwd, tool_name=self.name)
file_path.parent.mkdir(parents=True, exist_ok=True)
file_path.write_text(content, encoding="utf-8")
```
- 通过 `ctx.safety.resolve_path()` 解析路径
- 自动创建父目录 (`mkdir(parents=True, exist_ok=True)`)
- 直接使用 `pathlib.Path.write_text()` 写入
- 总是以 UTF-8 编码写入

### claude-code
```typescript
const fullFilePath = expandPath(file_path)
await getFsImplementation().mkdir(dir)
// ... 原子性读取-修改-写入 ...
writeTextContent(fullFilePath, content, enc, 'LF')
```
- 使用 `expandPath()` 展开路径（处理 `~` 等）
- 使用抽象的 `getFsImplementation()` 进行文件系统操作，便于测试和跨平台
- `writeTextContent()` 支持指定编码和换行符处理策略
- **明确保留模型传入的换行符**：注释说明 "Write is a full content replacement — the model sent explicit line endings in `content` and meant them. Do not rewrite them."
- 在写入前有一段原子性读取-修改-写入的临界区，避免并发修改

---

## 3. 安全 / 沙盒

### nano-multiagent
- 依赖 `ctx.safety.resolve_path()` 进行路径解析和沙箱限制
- 支持相对路径，基于 `ctx.cwd` 解析
- 代码中未显示更多细节（需查看 `ctx.safety` 的实现）

### claude-code
- `expandPath()` 在 `backfillObservableInput` 阶段就被调用，防止通过 `~` 或相对路径绕过 hook 的 allowlist
- `validateInput()` 中进行多层检查：
  1. **Team Memory Secrets 检查**：`checkTeamMemSecrets()` — 禁止向团队记忆文件写入 secrets
  2. **权限规则检查**：`matchingRuleForInput()` — 根据用户权限设置 deny 规则拒绝写入
  3. **UNC 路径安全检查**：跳过 Windows UNC 路径（`\\` 或 `//`）的文件系统操作，防止 NTLM 凭据泄漏到恶意 SMB 服务器
- `preparePermissionMatcher` 支持基于通配符的权限匹配

---

## 4. 错误处理

### nano-multiagent
- **未显式处理错误**。代码中没有 try-catch：
  - `resolve_path` 失败会抛出异常
  - `mkdir` 失败会抛出异常
  - `write_text` 失败会抛出异常
- 错误直接向上传播，由外层框架捕获

### claude-code
- `validateInput()` 返回结构化的验证结果：
  ```typescript
  { result: false, message: "...", errorCode: 0|1|2|3 }
  ```
  - `errorCode: 0` — Team memory secrets 违规
  - `errorCode: 1` — 权限设置拒绝
  - `errorCode: 2` — 文件尚未读取（覆盖现有文件时必须先读）
  - `errorCode: 3` — 文件自读取后已被修改
- `call()` 内部有细粒度的错误处理：
  - `readFileSyncWithMetadata` 的 `ENOENT` 被捕获并视为新文件
  - 如果在临界区发现文件被意外修改，抛出 `FILE_UNEXPECTEDLY_MODIFIED_ERROR`
  - LSP 通知失败仅记录日志，不中断主流程
- 所有错误通过 `renderToolUseErrorMessage` 渲染为友好的用户消息

---

## 5. 输出格式 / 返回值结构

### nano-multiagent
```python
{
    "type": "create" | "update",
    "filePath": string,
    "displayPath": string,
}
```
- `run()` 返回结构化 dict，区分文件创建 (`create`) 和更新 (`update`)
- 包含绝对路径 (`filePath`) 和相对 repo_root 的显示路径 (`displayPath`)
- 不含字节数、diff 或原始内容

### claude-code
```typescript
{
    type: 'create' | 'update',
    filePath: string,
    content: string,
    structuredPatch: Hunk[],
    originalFile: string | null,
    gitDiff?: ToolUseDiff
}
```
- **结构化输出**，区分文件创建 (`create`) 和更新 (`update`)
- 返回完整的内容、结构化 diff patch、原始文件内容
- 可选返回 `gitDiff`（远程模式下）
- 通过 `mapToolResultToToolResultBlockParam` 映射为不同的人类可读消息：
  - create: `"File created successfully at: ${filePath}"`
  - update: `"The file ${filePath} has been updated successfully."`

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
    write_type = output.get("type")

    if write_type == "create":
        return f"File created successfully at: {file_path}"
    elif write_type == "update":
        return f"The file {file_path} has been updated successfully."
    else:
        return json_serialize(output)
```
- **create / update 语义区分**：根据 `type` 返回不同的人类可读纯文本
- **极简纯文本**：不含字节数、不含 diff、不含原始内容
- **错误透传**：`error` 参数非空时直接返回错误文本
- **兜底**：非预期结构时回退到 JSON 序列化

#### claude-code (`mapToolResultToToolResultBlockParam`)
```typescript
mapToolResultToToolResultBlockParam({ filePath, type }, toolUseID) {
  switch (type) {
    case 'create':
      return {
        tool_use_id: toolUseID, type: 'tool_result',
        content: `File created successfully at: ${filePath}`,
      }
    case 'update':
      return {
        tool_use_id: toolUseID, type: 'tool_result',
        content: `The file ${filePath} has been updated successfully.`,
      }
  }
}
```
- **create / update 语义区分**：明确告诉模型是"新建"还是"更新"
- **极简纯文本**：不含字节数、不含 diff、不含原始内容，仅一句人类可读摘要
- **Diff 去哪了**：`structuredPatch`、`originalFile`、`gitDiff` 等结构化数据走 **UI 层** 展示，不占用模型 token

### 关键启示
与 `edit` 工具一致，claude-code 的 `write` 转换层遵循同一原则：**给模型的结果极简、纯文本、区分语义；结构化数据留给 UI**。nano-multiagent 在重构后已采用相同策略，`serialize_result` 返回极简人类可读文本而非 JSON 化全量数据。

---

## 6. 边缘情况处理

| 场景 | nano-multiagent | claude-code |
|------|-----------------|-------------|
| **覆盖现有文件** | 直接覆盖，无警告 | 强制要求先 `read`；读取后若文件被外部修改则拒绝写入 |
| **并发修改** | 无处理 | 通过 mtime 对比和内容对比双重检查防止 |
| **换行符** | 直接写入模型提供的内容 | 同样直接写入，但明确在代码注释中记录了这一设计决策 |
| **编码** | 固定 UTF-8 | 自动检测现有文件编码并复用；新文件默认 UTF-8 |
| **父目录不存在** | `mkdir(parents=True, exist_ok=True)` | `getFsImplementation().mkdir(dir)` |
| **相对路径** | 支持 | 不支持，强制绝对路径 |
| **UNC/SMB 路径** | 无特殊处理 | 主动跳过，防止凭据泄漏 |
| **Secrets 写入** | 无检查 | `checkTeamMemSecrets()` 拦截 |
| **LSP 同步** | 无 | 写入后主动通知 LSP server (didChange + didSave) |
| **VSCode 集成** | 无 | `notifyVscodeFileUpdated()` 触发 diff 视图更新 |
| **文件历史/备份** | 无 | `fileHistoryTrackEdit()` 记录编辑历史 |
| **Skill 自动加载** | 无 | 根据文件路径自动发现和加载 skill |

---

## 7. 关键差异与 nano-multiagent 可借鉴之处

### 7.1 强制 "Read-Before-Write" 规则
claude-code 最重要的安全设计之一是：**覆盖现有文件前必须先读取**。这通过 `readFileState` 跟踪实现，有效防止模型在不知情的情况下覆盖用户或 linter 的最新修改。nano-multiagent 目前直接覆盖，存在数据丢失风险。

### 7.2 并发修改检测
claude-code 不仅对比时间戳，还在 Windows 等时间戳不可靠的场景下 fallback 到**内容对比**。nano-multiagent 完全没有这一层保护。

### 7.3 结构化返回值
claude-code 返回完整的 diff patch 和原始内容，使上层 UI 可以展示精确的变更对比。nano-multiagent `run()` 返回 `{"type", "filePath", "displayPath"}`，信息密度低，不利于调试和审计。

### 7.4 权限与安全的深度集成
claude-code 的 `validateInput` 将权限检查、secrets 防护、UNC 路径安全整合为统一的验证流程。nano-multiagent 的安全逻辑隐藏在 `ctx.safety.resolve_path()` 中，但缺少针对写入场景的专项校验。

### 7.5 生态系统集成
claude-code 在写入后会同步触发：
- LSP 诊断更新
- VSCode diff 视图
- 文件历史备份
- Skill 自动发现

这些生态集成显著提升了开发者体验，nano-multiagent 作为 agent 平台可以考虑引入类似的 hook 机制。

### 7.6 路径规范化前置
claude-code 在 `backfillObservableInput` 阶段就调用 `expandPath()`，确保后续的权限 allowlist 不会被 `~` 或相对路径绕过。nano-multiagent 的 `resolve_path` 发生在运行时，如果 allowlist 检查在解析之前执行，可能存在绕过风险。

### 7.7 错误信息的人机工程
claude-code 为每种拒绝场景分配了 error code 和明确的英文说明，便于用户理解和自动化处理。nano-multiagent 依赖底层异常的消息，用户体验较差。
