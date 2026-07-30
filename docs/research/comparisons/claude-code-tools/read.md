# `read` 工具实现对比：nano-multiagent vs claude-code

## 1. 接口与 Schema

### nano-multiagent (`read.py`)
- **参数名**：`path`（字符串，相对或绝对路径）、`offset`（整数，1-indexed，可选）、`limit`（整数，可选）
- **必需参数**：仅 `path`
- **Schema**：手写 JSON Schema（`input_schema` 字典）
- **额外属性**：`additionalProperties: False`
- **能力**：支持文本文件（带 `cat -n` 行号）和图像（jpg、png、gif、webp）读取

### claude-code (`FileReadTool.ts`)
- **参数名**：`file_path`（字符串，**必须是绝对路径**）、`offset`（整数，0-indexed，可选）、`limit`（正整数，可选）、`pages`（字符串，PDF 专用，如 `"1-5"`）
- **Schema**：使用 `zod/v4` 的 `strictObject` 进行运行时校验
- **输出 schema**：定义了 `discriminatedUnion`，包含 `text`、`image`、`notebook`、`pdf`、`parts`、`file_unchanged` 六种返回类型
- **额外能力**：内置 `pages` 参数支持 PDF 分页读取

### 关键差异
| 维度 | nano-multiagent | claude-code |
|---|---|---|
| 路径类型 | 相对/绝对均可 | **强制绝对路径** |
| offset 基准 | 1-indexed | 0-indexed（但对外提示仍称 line number） |
| PDF 支持 | 无 | 原生支持（`pages` 参数） |
| Notebook 支持 | 无 | 原生支持 `.ipynb` |
| Schema 校验 | 手写 JSON Schema | Zod 严格对象校验 |

---

## 2. 核心实现细节

### nano-multiagent
- **文本读取**：一次性 `path.read_text(encoding="utf-8")`，然后 `splitlines()`
- **分页逻辑**：在内存中切片 `lines[start_index:]`，再应用 `limit`
- **截断逻辑**：自定义 `_truncate_head_lines`，同时检查 `max_lines` 和 `max_bytes`，返回头部内容
- **大文件处理**：无优化，一次性读入内存；大文件仅通过 offset/limit 在内存切片规避
- **图像处理**：直接 `read_bytes()` + `base64.b64encode()`，无压缩、无 resize
- **图像尺寸解析**：手写二进制解析器（PNG/GIF/JPEG/WebP 的 magic bytes），不依赖外部库

### claude-code
- **文本读取**：使用专门的 `readFileInRange.ts`
  - **Fast path**（< 10 MB）：`fs.readFile` + 内存 `indexOf('\n')` 扫描
  - **Streaming path**（≥ 10 MB、管道、设备）：`createReadStream` + 手动逐行解析，**只保留目标范围内的行**，避免 100 GB 文件爆内存
  - 支持 `AbortSignal` 取消
  - 自动去除 UTF-8 BOM 和 `\r`
- **图像处理**：依赖 `sharp`（或 `image-processor-napi`）进行多阶段压缩
  - 标准 resize + downsample
  - 若仍超 token 预算，触发 `compressImageBufferWithTokenLimit` 进行激进压缩
  - 最终 fallback：400x400 JPEG quality 20
- **PDF 处理**：
  - 支持 `pages` 参数提取特定页为图片
  - 大 PDF 自动转图片页（`extractPDFPages`）
  - 小 PDF 直接 base64 返回并作为 `document` block 发送
- **Notebook 处理**：使用 `readNotebook` 解析 `.ipynb` 为 cells 数组

### 关键差异
| 维度 | nano-multiagent | claude-code |
|---|---|---|
| 大文件读取 | 全量读内存 | **双路径优化**（fast + streaming） |
| BOM/CRLF 处理 | 无 | 自动去除 |
| 图像压缩 | 无 | **多阶段 sharp 压缩** |
| 图像尺寸 | 手写解析 | sharp metadata + 二进制 fallback |
| PDF/Notebook | 不支持 | **原生支持** |
| 取消信号 | 无 | `AbortSignal` |

---

## 3. 安全 / 沙盒

### nano-multiagent
- 通过 `ctx.safety.resolve_read_path()` 解析路径
- **允许读取的根目录**：
  - `repo_root`（项目根目录）
  - `~/.codex/skills`（技能目录）
- 使用 `Path.resolve()` 解析后再用 `relative_to()` 检查是否越界
- 无设备文件黑名单
- 无二进制文件扩展名检查

### claude-code
- `expandPath()` 统一处理路径（去空白、Windows 分隔符、波浪号展开）
- **多层权限检查**：
  1. `validateInput` 阶段：检查 deny rule（用户权限设置）
  2. UNC 路径延迟检查（防止 NTLM 凭据泄漏）
  3. **二进制扩展名检查**：`hasBinaryExtension` 拒绝非文本文件（但放行 PDF、图片、SVG）
  4. **设备文件黑名单**：`/dev/zero`、`/dev/urandom`、`/dev/stdin`、`/dev/tty`、`/dev/fd/0-2`、`/proc/*/fd/0-2` 等会被直接拒绝
- **macOS 截图文件名兼容**：自动处理 AM/PM 前的空格/细空格（U+202F）差异

### 关键差异
| 维度 | nano-multiagent | claude-code |
|---|---|---|
| 路径越界检查 | 有（repo + skills） | 有 + deny rule + UNC 延迟 |
| 设备文件保护 | **无** | **完整黑名单** |
| 二进制文件拦截 | **无** | 有（放行 PDF/图片/SVG） |
| 特殊文件名兼容 | 无 | **macOS 截图空格兼容** |

---

## 4. 错误处理

### nano-multiagent
- 统一抛出 `ToolError`，包含 `tool_name` 和可选 `details`
- 具体错误：
  - 文件不存在：`file does not exist`
  - 路径越界：`path is outside repo sandbox`（在 safety 层）
  - offset 非法：`offset must be >= 1`
  - offset 越界：`offset is out of range`
  - 非 UTF-8：`file is not UTF-8 text; read supports text and jpg/png/gif/webp images`
  - 单行超字节限制：提示用 `bash: sed -n` 读取

### claude-code
- 使用标准 `Error` 子类 + 工具框架的 `renderToolUseErrorMessage`
- 专有错误类：
  - `FileTooLargeError`：文件大小超过 `maxSizeBytes`
  - `MaxFileReadTokenExceededError`：内容 token 数超过 `maxTokens`
  - `ImageResizeError`：图像 resize 失败且超过 API 限制
- 文件不存在（ENOENT）时：
  - 尝试 macOS 截图替代路径
  - 调用 `findSimilarFile` 进行模糊匹配
  - 提示 `Did you mean ...?`
- 输入校验阶段返回结构化失败结果（`{ result: false, message, errorCode }`）

### 关键差异
| 维度 | nano-multiagent | claude-code |
|---|---|---|
| 错误类型 | 单一 `ToolError` | **多层级专用 Error 类** |
| 模糊匹配建议 | **无** | **ENOENT 时自动建议相似文件** |
| token 超限 | 无 | `MaxFileReadTokenExceededError` |
| 文件大小超限 | 无（仅按行/字节截断） | `FileTooLargeError`（预读拦截） |

---

## 5. 输出格式 / 返回值结构

### nano-multiagent
统一返回字典，包含：
```python
{
  "path": str,           # 相对 repo_root 的路径
  "offset": int,         # 请求的 offset
  "next_offset": int|None,
  "total_lines": int,
  "truncated": bool,
  "content": [{"type": "text", "text": str}] | [{"type": "image", ...}],
  "details": dict|None,  # 截断元数据
}
```
- 图像返回 mixed content：`text` note + `image` block
- 文本通过 `_add_line_numbers` 添加 `cat -n` 格式行号

### claude-code
使用 discriminated union 输出：
- **`text`**：`filePath`、`content`（带行号）、`numLines`、`startLine`、`totalLines`
- **`image`**：`base64`、`type`、`originalSize`、`dimensions`（original/display 宽高）
- **`notebook`**：`filePath`、`cells`
- **`pdf`**：`filePath`、`base64`、`originalSize`
- **`parts`**：PDF 分页提取后的图片目录信息
- **`file_unchanged`**：去重占位符

文本内容通过 `addLineNumbers` 添加 `cat -n` 格式行号。

### `serialize_result` / `mapToolResultToToolResultBlockParam` 对比

这是工具业务结果 → LLM 可见 `tool_result` 的**转换层**，直接影响模型的理解和后续行为。

#### nano-multiagent (`serialize_result`)
```python
def serialize_result(self, output: Any, error: str | None = None) -> str | list[dict[str, Any]]:
    if error is not None:
        return error

    if isinstance(output, Mapping) and output.get("type") == "file_unchanged":
        return (
            "File unchanged since last read. The content from the earlier "
            "Read tool_result in this conversation is still current — "
            "refer to that instead of re-reading. ({file_path})"
        )

    if isinstance(output, Mapping) and "content" in output:
        content_blocks = output["content"]
        if isinstance(content_blocks, list):
            has_image = any(
                isinstance(block, Mapping) and block.get("type") == "image"
                for block in content_blocks
            )
            if has_image:
                return list(content_blocks)

            texts = [
                block.get("text", "")
                for block in content_blocks
                if isinstance(block, Mapping) and block.get("type") == "text"
            ]
            combined = "\n".join(texts)

            if not combined:
                return "<system-reminder>Warning: the file exists but the contents are empty.</system-reminder>"

            offset = output.get("offset", 1)
            return _add_line_numbers(combined, offset)

    return json_serialize(output)
```
- **文本**：提取 `text` block 拼接后通过 `_add_line_numbers` 添加 `cat -n` 行号；空文件返回 `<system-reminder>` 提示
- **图像**：直接返回 `list[dict]`（provider-neutral 内容块：`text` note + `image` block，含 base64 data 和 mimeType），不经 JSON 序列化，直接流入 kernel 的 provider mapper
- **file_unchanged**：返回 stub 文本字符串，提示模型引用之前的 tool_result

#### claude-code (`mapToolResultToToolResultBlockParam`)
```typescript
mapToolResultToToolResultBlockParam(data, toolUseID) {
  switch (data.type) {
    case 'image':
      return { tool_use_id: toolUseID, type: 'tool_result',
        content: [{ type: 'image', source: { type: 'base64', data: data.file.base64, media_type: data.file.type } }] }
    case 'notebook':
      return mapNotebookCellsToToolResult(data.file.cells, toolUseID)
    case 'pdf':
      return { tool_use_id: toolUseID, type: 'tool_result',
        content: `PDF file read: ${data.file.filePath} (${formatFileSize(data.file.originalSize)})` }
    case 'parts':
      return { tool_use_id: toolUseID, type: 'tool_result',
        content: `PDF pages extracted: ${data.file.count} page(s) from ${data.file.filePath} (${formatFileSize(data.file.originalSize)})` }
    case 'file_unchanged':
      return { tool_use_id: toolUseID, type: 'tool_result', content: FILE_UNCHANGED_STUB }
    case 'text': {
      let content: string
      if (data.file.content) {
        content = memoryFileFreshnessPrefix(data) + formatFileLines(data.file)
          + (shouldIncludeFileReadMitigation() ? CYBER_RISK_MITIGATION_REMINDER : '')
      } else {
        content = data.file.totalLines === 0
          ? '<system-reminder>Warning: the file exists but the contents are empty.</system-reminder>'
          : `<system-reminder>Warning: the file exists but is shorter than the provided offset (${data.file.startLine}). The file has ${data.file.totalLines} lines.</system-reminder>`
      }
      return { tool_use_id: toolUseID, type: 'tool_result', content }
    }
  }
}
```
- **文本**：`formatFileLines` 添加 `cat -n` 行号；空文件 / offset 越界时用 `<system-reminder>` 明确提示模型
- **图像**：返回 Anthropic SDK 原生 `image` block（非 JSON 字符串），模型可直接识别为图像输入
- **PDF**：返回文本摘要（文件名 + 大小），实际内容通过 side-channel 以 `document` block 发送
- **Notebook**：通过 `mapNotebookCellsToToolResult` 把 cell 数组映射为带 `<cell>` 标签的文本块
- **file_unchanged**：返回固定 stub `"File unchanged since last read...

---

## 6. 边缘情况处理

### nano-multiagent
| 场景 | 处理 |
|---|---|
| 空文件 | `total_lines = 0`，返回空 `content` |
| 单行超字节限制 | 返回 sed 提示，不截断行内内容 |
| 图像超大 | 直接原图 base64，**无压缩** |
| 非 UTF-8 文本 | 拒绝并提示 |
| offset > total_lines | 报错 |
| 路径不存在 | 报错 |
| 目录 | 未显式处理（`is_file()` 为 false 时报 "file does not exist"） |

### claude-code
| 场景 | 处理 |
|---|---|
| 空文件 | `<system-reminder>Warning: the file exists but the contents are empty.</system-reminder>` |
| offset > total_lines | `<system-reminder>Warning: the file exists but is shorter than the provided offset...</system-reminder>` |
| 大文件 | streaming path，O(1) 内存 |
| 图像超大 | **多阶段压缩 + token budget 控制** |
| 图像 corrupt/格式未知 | magic bytes 检测 + sharp fallback |
| 重复读取同一文件 | **mtime 去重，返回 `file_unchanged`** |
| macOS 截图空格差异 | **自动尝试 alternate path** |
| 设备文件 | **路径黑名单拦截** |
| PDF 页数过多 | 强制要求 `pages` 参数 |
| Notebook 过大 | 提示用 `bash + jq` 分片读取 |
| 二进制文件误读 | 扩展名拦截 |

---

## 7. 关键差异总结与 nano-multiagent 可借鉴之处

### claude-code 明显优于 nano-multiagent 的方面

1. **大文件读取性能**
   - nano-multiagent 一次性读全文件再切片，大文件会爆内存。
   - **建议**：引入 `readFileInRange` 式的双路径实现（fast path + streaming path）。

2. **图像处理**
   - nano-multiagent 直接原图 base64，既浪费 token 也可能触发 API 大小限制。
   - **建议**：集成 `PIL`/`pillow` 或 `sharp`（若 Node 边界允许）实现图像压缩、resize、token budget 控制。

3. **输出格式**
   - nano-multiagent 已添加 `cat -n` 行号，图像返回 provider-neutral 内容块而非 JSON 字符串。
   - **建议**：定义输出 schema（可用 Pydantic）；支持更多返回类型（PDF、Notebook）。

4. **安全与沙盒**
   - nano-multiagent 缺少设备文件黑名单、二进制扩展名检查、模糊路径建议。
   - **建议**：添加 `/dev/*` 和 `/proc/*/fd/*` 黑名单；在读取前检查二进制扩展名；ENOENT 时做相似文件提示。

5. **去重机制**
   - claude-code 的 `readFileState` + mtime 去重能显著降低重复读取的 token 消耗。
   - **建议**：在 session 或 turn 级别缓存已读文件状态，未变更时返回 stub。

6. **PDF / Notebook 支持**
   - nano-multiagent 完全不支持。
   - **建议**：若产品需要，可逐步引入 `pypdf`/`pdf2image` 和 `nbformat` 支持。

7. **错误粒度**
   - nano-multiagent 的单一 `ToolError` 难以区分“文件太大”和“token 超限”。
   - **建议**：引入 `FileTooLargeError`、`MaxFileReadTokenExceededError` 等专用异常。

### nano-multiagent 相对保留的优势
- **零外部依赖**：图像尺寸解析纯手写，不依赖 `sharp`/`PIL`，在极简部署环境更稳定。
- **实现简洁**：代码量小，逻辑直观，适合快速迭代和理解。
