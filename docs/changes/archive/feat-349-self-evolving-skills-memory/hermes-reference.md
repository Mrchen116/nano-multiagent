# Hermes Agent: Skill 自进化 + Memory 机制 — 代码级参考

> 对照 hermes-agent 源码逐项核实，所有行号均来自实际文件。  
> 源码仓库：`~/Repos/opensource-hub/self-evolution/hermes-agent`

> **核实状态**（feat-349 design 阶段交叉核对，2026-05）：
> - ✅ **已交叉核实**（设计者亲自读过对应 hermes 源码确认无误）：§1 计数器累加 / 归零 / turn 末检查（`12276` / `15593-15598` / `10726-10729` / `11160-11168`）、§2 fork 触发与创建（`15609-15617` / `max_iterations=16` / interval 置 0 防递归 / `_cached_system_prompt` 继承 / 工具白名单）、§3 prompt 选择逻辑（`4241-4246`）、§6 guidance 注入条件（`5916-5930`）。
> - ⚠️ **worker 复刻前须自行对照原文**（未逐字亲验，行号供定位）：§3 review prompt 全文、§4 `skill_manage` 完整 schema 与各 action 实现、§5 `memory` 工具实现细节、§6 guidance 常量全文。
> - 具体存疑点见 §1 附注、§4 / §6 的 ⚠️ 标注。

---

## 1. Nudge 计数器的完整生命周期

### 变量定义与初始化

`run_agent.py:1970-1972`

```python
self._memory_nudge_interval = 10
self._turns_since_memory = 0
self._iters_since_skill = 0
```

### 配置项读取

`run_agent.py:1975-1978`（`__init__` 中 `memory` config 块）：

```python
mem_config = _agent_cfg.get("memory", {})
self._memory_nudge_interval = int(mem_config.get("nudge_interval", 10))
```

`run_agent.py:2077-2080`（`skills` config 块）：

```python
self._skill_nudge_interval = 10
skills_config = _agent_cfg.get("skills", {})
self._skill_nudge_interval = int(skills_config.get("creation_nudge_interval", 10))
```

配置键名：`memory.nudge_interval`（默认 10）、`skills.creation_nudge_interval`（默认 10）。

### `_turns_since_memory` +1 与归零

**+1 位置**：`run_agent.py:11976`，在 `run_conversation()` 入口，每次用户 turn 开始时：

```python
self._turns_since_memory += 1
if self._turns_since_memory >= self._memory_nudge_interval:
    _should_review_memory = True
    self._turns_since_memory = 0          # 达阈值：归零并设 flag
```

**早归零（工具实际被调用时）**：单工具路径 `run_agent.py:11165-11166`，并发工具路径 `run_agent.py:10726-10727`：

```python
if function_name == "memory":
    self._turns_since_memory = 0
```

**注意**：当工具被 plugin block 或 guardrail 拦截时，`_execution_blocked = True`，**不执行**归零（`run_agent.py:11160-11168`）。这保证被拦截的无效调用不会重置计数器，nudge 仍会在正确轮次触发。

### `_iters_since_skill` +1 与归零

**+1 位置**：`run_agent.py:12276-12278`，每次 API 调用迭代完成后：

```python
if (self._skill_nudge_interval > 0
        and "skill_manage" in self.valid_tool_names):
    self._iters_since_skill += 1
```

**归零（工具实际被调用时）**：`run_agent.py:11167-11168` / `run_agent.py:10728-10729`：

```python
elif function_name == "skill_manage":
    self._iters_since_skill = 0
```

同样：工具被拦截时不归零。

**turn 结束时检查 flag**：`run_agent.py:15594-15598`

```python
if (self._skill_nudge_interval > 0
        and self._iters_since_skill >= self._skill_nudge_interval
        and "skill_manage" in self.valid_tool_names):
    _should_review_skills = True
    self._iters_since_skill = 0
```

### Gateway 重建 agent 时的计数器恢复

Gateway 每条消息新建 `AIAgent`，计数器从 0 开始，可能永远触发不了。解决方案（`run_agent.py:11933-11943`）：

```python
if conversation_history and self._user_turn_count == 0:
    prior_user_turns = sum(1 for m in conversation_history if m.get("role") == "user")
    if prior_user_turns > 0:
        self._user_turn_count = prior_user_turns
        if self._memory_nudge_interval > 0 and self._turns_since_memory == 0:
            self._turns_since_memory = prior_user_turns % self._memory_nudge_interval
```

注意：`_iters_since_skill` **没有类似恢复**，因为 tool iterations 不记录在 history 中，无法重建。

**跨 `run_conversation` 调用不重置**（`run_agent.py:11899-11901`，注释）：

> NOTE: _turns_since_memory and _iters_since_skill are NOT reset here.
> They are initialized in __init__ and must persist across run_conversation
> calls so that nudge logic accumulates correctly in CLI mode.

### ⚠️ 附注：本节只覆盖 `chat_completions` 路径

hermes 另有一条 `codex_app_server` 运行路径，其 `_iters_since_skill` 累加（`_iters_since_skill += turn.tool_iterations`）+ turn 末检查 + spawn 在 `run_agent.py:15721-15763` 另成一套。**本项目不涉及 codex 运行时，复刻 `chat_completions` 路径即可**，此处仅作完整性提示。

---

## 2. 后台 review fork 的完整实现

入口函数：`run_agent.py:4225-4425`，`_spawn_background_review`。

### 触发条件

`run_agent.py:15609-15617`（turn 结束处）：

```python
if final_response and not interrupted and (_should_review_memory or _should_review_skills):
    try:
        self._spawn_background_review(
            messages_snapshot=list(messages),
            review_memory=_should_review_memory,
            review_skills=_should_review_skills,
        )
    except Exception:
        pass  # Background review is best-effort
```

条件：有 final_response、未被打断、至少一个 flag 为 True。

### fork 创建

`run_agent.py:4265-4301`：

```python
review_agent = AIAgent(
    model=self.model,
    max_iterations=16,          # 硬编码上限
    quiet_mode=True,
    platform=self.platform,
    provider=self.provider,
    api_mode=_parent_api_mode,
    base_url=_parent_runtime.get("base_url") or None,
    api_key=_parent_runtime.get("api_key") or None,
    credential_pool=getattr(self, "_credential_pool", None),
    parent_session_id=self.session_id,
)
```

创建的是完整的 `AIAgent` 实例（不是任何精简版），继承父 agent 的 model / provider / credentials。

### 防递归：nudge interval 置 0

`run_agent.py:4307-4308`：

```python
review_agent._memory_nudge_interval = 0
review_agent._skill_nudge_interval = 0
```

interval 设为 0，条件 `nudge_interval > 0` 不成立，review agent 永远不会再 spawn 下一层 review。

### 共享 memory store

`run_agent.py:4304-4306`：

```python
review_agent._memory_store = self._memory_store  # 直接共享同一实例
review_agent._memory_enabled = self._memory_enabled
review_agent._user_profile_enabled = self._user_profile_enabled
```

### 继承 system prompt 缓存（降低成本）

`run_agent.py:4327`：

```python
review_agent._cached_system_prompt = self._cached_system_prompt
```

复用父 agent 缓存的 system prompt 字节，命中 prefix cache，实测节省 ~26%（issue #25322）。

### 工具白名单限制

`run_agent.py:4344-4357`：只允许 `memory` 和 `skill_manage` 两类工具。使用 thread-local plugin hook 注入 whitelist deny rule，非白名单工具调用直接被 deny。

```python
review_whitelist = {
    t["function"]["name"]
    for t in get_tool_definitions(
        enabled_toolsets=["memory", "skills"],
        quiet_mode=True,
    )
}
set_thread_tool_whitelist(
    review_whitelist,
    deny_msg_fmt="Background review denied non-whitelisted tool: {tool_name}. ...",
)
```

### daemon thread 启动

`run_agent.py:4424-4425`：

```python
t = threading.Thread(target=_run_review, daemon=True, name="bg-review")
t.start()
```

`daemon=True`：主进程退出时后台 thread 自动终止，不阻塞。

### stdout/stderr 重定向

`run_agent.py:4267-4269`：

```python
with open(os.devnull, "w", encoding="utf-8") as _devnull, \
     contextlib.redirect_stdout(_devnull), \
     contextlib.redirect_stderr(_devnull):
```

所有 stdout/stderr 丢弃，防止混入主 terminal 输出。

### messages_snapshot 传递方式

调用处（`run_agent.py:15612`）：`messages_snapshot=list(messages)`，即在调用前做一次浅拷贝，传给 `_spawn_background_review`，再作为 `conversation_history` 传给 `review_agent.run_conversation()`。

### 结果回显给用户

`run_agent.py:4377-4394`：

```python
actions = self._summarize_background_review_actions(
    getattr(review_agent, "_session_messages", []),
    messages_snapshot,
)
if actions:
    summary = " · ".join(dict.fromkeys(actions))
    self._safe_print(f"  💾 Self-improvement review: {summary}")
    _bg_cb = self.background_review_callback
    if _bg_cb:
        try:
            _bg_cb(f"💾 Self-improvement review: {summary}")
        except Exception:
            pass
```

`_summarize_background_review_actions`（`run_agent.py:4163-4223`）：扫描 review agent 的 `_session_messages` 中 role=tool 的 `{"success": true, "message": "..."}` 响应，过滤掉 `messages_snapshot` 中已存在的（防止把主对话历史的旧工具结果重复显示），提取 "created" / "updated" / "added" / "removed" 等动词，去重后 `" · "` 拼接。

`background_review_callback` 是可选的 sync callback，Gateway 注入用于把摘要推送给用户（`run_agent.py:1261`）。

---

## 3. Review Prompt 三个常量

### 选择逻辑

`run_agent.py:4241-4246`：

```python
if review_memory and review_skills:
    prompt = self._COMBINED_REVIEW_PROMPT
elif review_memory:
    prompt = self._MEMORY_REVIEW_PROMPT
else:
    prompt = self._SKILL_REVIEW_PROMPT
```

即：两个 flag 都触发 → combined；仅 memory flag → memory prompt；仅 skill flag → skill prompt。

### `_MEMORY_REVIEW_PROMPT`

`run_agent.py:3979-3988`：

```
Review the conversation above and consider saving to memory if appropriate.

Focus on:
1. Has the user revealed things about themselves — their persona, desires,
preferences, or personal details worth remembering?
2. Has the user expressed expectations about how you should behave, their work
style, or ways they want you to operate?

If something stands out, save it using the memory tool.
If nothing is worth saving, just say 'Nothing to save.' and stop.
```

### `_SKILL_REVIEW_PROMPT`

`run_agent.py:3990-4084`（约 90 行）。关键要点（精简，非全文）：

- 开头要求 **ACTIVE**，"most sessions produce at least one skill update"；
- 定义 skill 形态：CLASS-LEVEL，rich SKILL.md + `references/` 目录，非 flat list；
- 触发信号：用户纠正 style/tone/format/verbosity、workflow 纠正、出现 non-trivial technique、已加载的 skill 发现过时；
- 偏好顺序：① 更新当前已加载 skill → ② 更新已有 umbrella skill → ③ 在 umbrella 下加 support file → ④ 创建新 class-level umbrella；
- Support file 三类目录语义：`references/`（session detail + 知识库）、`templates/`（可复制的模板）、`scripts/`（可直接重跑的脚本）；
- **禁止捕获**：环境依赖失败、工具负面断言、transient error、one-off 任务叙事；
- 结尾：`'Nothing to save.' is a real option but should NOT be the default`。

### `_COMBINED_REVIEW_PROMPT`

`run_agent.py:4086-4160`。是 `_SKILL_REVIEW_PROMPT` 的精简版 + memory 段的合并，主要增加：

> **Memory**: who the user is ... **Skills**: how to do this class of task.

核心区分：Memory 存 "who the user is and what the current situation is"；Skills 存 "how to do this class of task for this user"。User preference 两处都要更新（内嵌在 skill 里，也记在 memory 里）。

---

## 4. `skill_manage` 工具

**实现文件**：`tools/skill_manager_tool.py`

### Tool Schema（完整 actions）

`skill_manager_tool.py:797-909`：

```python
SKILL_MANAGE_SCHEMA = {
    "name": "skill_manage",
    "parameters": {
        "properties": {
            "action": {"enum": ["create", "patch", "edit", "delete", "write_file", "remove_file"]},
            "name": str,           # 必填
            "content": str,        # create/edit 必填
            "old_string": str,     # patch 必填
            "new_string": str,     # patch 必填
            "replace_all": bool,   # patch 可选，默认 false
            "category": str,       # create 可选（子目录）
            "file_path": str,      # write_file/remove_file 必填，patch 可选
            "file_content": str,   # write_file 必填
            "absorbed_into": str,  # delete 可选，声明被吸收目标
        },
        "required": ["action", "name"],
    }
}
```

### 命名校验 regex

`skill_manager_tool.py:168`：

```python
VALID_NAME_RE = re.compile(r'^[a-z0-9][a-z0-9._-]*$')
```

首字符必须是字母或数字；允许小写字母、数字、点、下划线、连字符；最长 64 字符（`MAX_NAME_LENGTH = 64`）。

### 内容大小限制

`skill_manager_tool.py:164-165`：

```python
MAX_SKILL_CONTENT_CHARS = 100_000   # SKILL.md 字符上限，约 36k tokens
MAX_SKILL_FILE_BYTES = 1_048_576    # 1 MiB，supporting file 字节上限
```

### frontmatter 校验

`skill_manager_tool.py:217-253`，`_validate_frontmatter()`：

1. 非空；
2. 以 `---` 开头；
3. `\n---\s*\n` 闭合；
4. `yaml.safe_load` 解析为 dict；
5. 必须有 `name` 和 `description` 字段；
6. description 不超过 1024 字符；
7. frontmatter 后必须有非空 body。

### `create` 动作流程

`skill_manager_tool.py:373-427`：

1. 校验 name、category；
2. 校验 frontmatter 和内容大小；
3. **重复检查**：`_find_skill(name)` 跨所有 skills dir 查重，已存在则拒绝；
4. 创建目录 `SKILLS_DIR / [category/] name /`；
5. 原子写入 `SKILL.md`（`_atomic_write_text`）；
6. **安全扫描**：`_security_scan_skill(skill_dir)`，失败则 `shutil.rmtree` 回滚。

### `edit` 动作（full rewrite）

`skill_manager_tool.py:430-460`：

1. 校验 frontmatter + 大小；
2. 查找 skill（不存在报错）；
3. 读取原始内容（备份）；
4. 原子写入新内容；
5. 安全扫描失败则用备份内容原子回滚。

### `patch` 动作（find-and-replace）

`skill_manager_tool.py:463-554`：

1. `old_string` 不能为空，`new_string` 不能为 None（可以是空字符串→删除）；
2. 若指定 `file_path`，校验路径合法性（必须在 `ALLOWED_SUBDIRS` 内）；
3. 使用 **fuzzy match**（`tools/fuzzy_match.py`）：处理空白规范化、缩进差异，返回 `(new_content, match_count, strategy, error)`；
4. `replace_all=False` 时要求唯一匹配；
5. 检查新内容大小，若非 file_path 还要重新校验 frontmatter 完整性；
6. 原子写入，安全扫描失败回滚。

### 辅助文件路径限制

`skill_manager_tool.py:171`：

```python
ALLOWED_SUBDIRS = {"references", "templates", "scripts", "assets"}
```

`_validate_file_path()`（`skill_manager_tool.py:298-323`）：禁止 `..` traversal，路径第一段必须在 `ALLOWED_SUBDIRS` 内，至少两段（不能只写目录名）。

### 安全扫描 `_security_scan_skill`

`skill_manager_tool.py:78-102`：

- ⚠️ **默认值存疑（未亲验）**：reference 记为"默认关闭（`skills.guard_agent_created`，默认 False）"，但用户原始调研笔记记为"保存后默认执行扫描"——两者不一致。**对本 unit 无影响**：design 决策 R6 已定本项目不做 hermes 式安全扫描。
- 开启后调用 `tools/skills_guard.scan_skill()`，返回 `(allowed, reason)`；
- `allowed=False` 或 `allowed=None`（"ask" verdict）都触发回滚并返回错误；
- 扫描失败（异常）不阻塞（warning 日志但返回 None，视为通过）。

### 原子写入

`skill_manager_tool.py:337-366`，`_atomic_write_text()`：

```python
fd, temp_path = tempfile.mkstemp(
    dir=str(file_path.parent),
    prefix=f".{file_path.name}.tmp.",
    suffix="",
)
with os.fdopen(fd, "w", encoding="utf-8") as f:
    f.write(content)
atomic_replace(temp_path, file_path)   # utils.py 里封装 os.replace()
```

temp 文件与目标文件**同目录**，确保 `os.replace()` 是同一文件系统上的原子操作。

### 缓存失效

`skill_manager_tool.py:767-769`（成功后立即执行）：

```python
from agent.prompt_builder import clear_skills_system_prompt_cache
clear_skills_system_prompt_cache(clear_snapshot=True)
```

清除 `prompt_builder.py` 的 in-process LRU cache 和磁盘 snapshot，下次 `build_skills_system_prompt()` 重新扫描目录。

### agent-created 标记

`skill_manager_tool.py:778-787`：只有当 `skill_provenance.is_background_review()` 为 True（来自 `_spawn_background_review` fork）且 action 为 `create` 时，才调用 `mark_agent_created(name)`。前台用户指导的 skill 创建不会被标记，curator 不会自动管理它。

---

## 5. `memory` 工具

**实现文件**：`tools/memory_tool.py`

### Tool Schema（完整 actions）

`memory_tool.py:515-564`：

```python
MEMORY_SCHEMA = {
    "name": "memory",
    "parameters": {
        "properties": {
            "action": {"enum": ["add", "replace", "remove"]},
            "target": {"enum": ["memory", "user"]},  # 默认 "memory"
            "content": str,    # add/replace 必填
            "old_text": str,   # replace/remove 必填（唯一子串匹配）
        },
        "required": ["action", "target"],
    }
}
```

注意：**没有 `read` action**（该功能通过 system prompt 注入实现，不需要 tool 读取）。

### 文件格式

- **MEMORY.md**：`~/.hermes/memories/MEMORY.md`
- **USER.md**：`~/.hermes/memories/USER.md`
- **条目分隔符**：`"\n§\n"`（`ENTRY_DELIMITER = "\n§\n"`，`memory_tool.py:59`）
- 存储为纯文本，条目之间用 `§` 分割行隔开

### 字符上限配置

`run_agent.py:1982-1983`（`MemoryStore` 初始化参数）：

```python
self._memory_store = MemoryStore(
    memory_char_limit=mem_config.get("memory_char_limit", 2200),  # MEMORY.md 默认 2200 char
    user_char_limit=mem_config.get("user_char_limit", 1375),       # USER.md 默认 1375 char
)
```

config 键：`memory.memory_char_limit`、`memory.user_char_limit`。

`_char_count` 计算的是 `ENTRY_DELIMITER.join(entries)` 的长度（不含 trailing delimiter）。

### 文件锁机制

`memory_tool.py:145-179`，`_file_lock()`：

- 锁文件：`.lock` 后缀（`MEMORY.md.lock`、`USER.md.lock`）；
- Unix：`fcntl.flock(fd, LOCK_EX)`（阻塞直到获锁）；
- Windows：`msvcrt.locking(fd.fileno(), LK_LOCK, 1)`；
- **写入用原子 rename**（不用 flock 保护写入本身），所以读取不需要锁，并发读者总看到完整文件；
- `_reload_target(target)` 在锁内重读磁盘（multi-agent / multi-session 安全）。

### 原子写入

`memory_tool.py:434-462`，`_write_file()`：

```python
fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix=".mem_")
with os.fdopen(fd, "w", encoding="utf-8") as f:
    f.write(content)
    f.flush()
    os.fsync(f.fileno())    # fsync 保证 durable
atomic_replace(tmp_path, path)   # os.replace()
```

与 skill 写入的区别：多了 `os.fsync`，确保掉电不丢数据。

### System prompt 里 memory block 的渲染

`memory_tool.py:393-409`，`_render_block()`：

```python
pct = min(100, int((current / limit) * 100))

if target == "user":
    header = f"USER PROFILE (who the user is) [{pct}% — {current:,}/{limit:,} chars]"
else:
    header = f"MEMORY (your personal notes) [{pct}% — {current:,}/{limit:,} chars]"

separator = "═" * 46
return f"{separator}\n{header}\n{separator}\n{content}"
```

完整注入格式示例：

```
══════════════════════════════════════════════
MEMORY (your personal notes) [34% — 748/2,200 chars]
══════════════════════════════════════════════
用户偏好简短回答
§
项目使用 pytest + xdist
```

### 冻结快照模式（prefix cache 保护）

`memory_tool.py:118-142`，`MemoryStore.__init__` + `load_from_disk()`：

- `load_from_disk()` 时捕获 `_system_prompt_snapshot = {"memory": ..., "user": ...}`；
- `format_for_system_prompt(target)` 返回**快照**，从不返回 live entries；
- 中途的 `add`/`replace`/`remove` 只改 in-memory list 和磁盘文件，**不更新快照**；
- 下次 session 开始时重新 load，快照才刷新。

这保证同一 session 内 system prompt 字节不变，Anthropic prefix cache 命中率最大化。

---

## 6. System Prompt 注入

### MEMORY_GUIDANCE 和 SKILLS_GUIDANCE 常驻 guidance

定义：`agent/prompt_builder.py:150-186`

**MEMORY_GUIDANCE**（`prompt_builder.py:150-171`）⚠️ **全文未亲验**，且与用户原始笔记 03 记录的版本明显不同（hermes 可能已更新）；本项目会自行编写 guidance，复刻时以 hermes 当前源码为准：

```
You have persistent memory across sessions. Save durable facts using the memory
tool: user preferences, environment details, tool quirks, and stable conventions.
Memory is injected into every turn, so keep it compact and focused on facts that
will still matter later.
Prioritize what reduces future user steering — the most valuable memory is one
that prevents the user from having to correct or remind you again. ...
Do NOT save task progress, session outcomes, completed-work logs, or temporary TODO
state to memory; use session_search to recall those from past transcripts. ...
Write memories as declarative facts, not instructions to yourself.
'User prefers concise responses' ✓ — 'Always respond concisely' ✗.
```

**SKILLS_GUIDANCE**（`prompt_builder.py:179-186`）：

```
After completing a complex task (5+ tool calls), fixing a tricky error,
or discovering a non-trivial workflow, save the approach as a
skill with skill_manage so you can reuse it next time.
When using a skill and finding it outdated, incomplete, or wrong,
patch it immediately with skill_manage(action='patch') — don't wait to be asked.
Skills that aren't maintained become liabilities.
```

**注入条件**（`run_agent.py:5916-5930`）：

```python
tool_guidance = []
if "memory" in self.valid_tool_names:
    tool_guidance.append(MEMORY_GUIDANCE)
if "session_search" in self.valid_tool_names:
    tool_guidance.append(SESSION_SEARCH_GUIDANCE)
if "skill_manage" in self.valid_tool_names:
    tool_guidance.append(SKILLS_GUIDANCE)
if tool_guidance:
    stable_parts.append(" ".join(tool_guidance))
```

即：只有当对应工具在 toolset 中时才注入 guidance；它们属于 system prompt 的 **stable tier**（随 session 缓存，不随 turn 变化）。

### `<available_skills>` 注入

`agent/prompt_builder.py:1183-1210`，`build_skills_system_prompt()` 返回的字符串注入到 stable tier（`run_agent.py:5983-5990`）：

```
## Skills (mandatory)
Before replying, scan the skills below. If a skill matches or is even partially relevant
to your task, you MUST load it with skill_view(name) and follow its instructions. ...

<available_skills>
  category-name:
    - skill-name: description
    - skill-name: description
  general:
    - ...
</available_skills>

Only proceed without loading a skill if genuinely none are relevant to the task.
```

**缓存**：两层——in-process LRU（OrderedDict，最大条目数，`_SKILLS_PROMPT_CACHE`）+ 磁盘 snapshot（`.skills_prompt_snapshot.json`，按 mtime/size manifest 校验）。`skill_manage` 成功后立即调用 `clear_skills_system_prompt_cache(clear_snapshot=True)` 使两层同时失效。

**触发条件**（`run_agent.py:5974-5990`）：只要 `valid_tool_names` 中包含 `skills_list`、`skill_view`、`skill_manage` 任意一个。

Memory block 属于 **volatile tier**（`run_agent.py:6048-6057`），在 stable + context tier 之后追加，每次 session 开始时从快照读取渲染结果注入。

---

## 7. Profile 隔离

### `get_hermes_home()` 实现

`hermes_constants.py:14-68`：

```python
def get_hermes_home() -> Path:
    val = os.environ.get("HERMES_HOME", "").strip()
    if val:
        return Path(val)
    return Path.home() / ".hermes"
```

所有路径都通过 `get_hermes_home()` 动态解析（不在 import 时缓存），保证 profile 切换后同一进程读取新路径。

### Profile 目录结构

```
~/.hermes/                  ← default profile HERMES_HOME
├── profiles/
│   ├── coder/              ← HERMES_HOME for 'coder' profile
│   │   ├── skills/
│   │   ├── memories/
│   │   ├── config.yaml
│   │   └── ...
│   └── researcher/
└── active_profile          ← 粘性激活文件，内容为 profile name
```

**命名规则**（`hermes_cli/profiles.py:284`）：`^[a-z0-9][a-z0-9_-]{0,63}$`，保留名：`hermes`、`test`、`tmp`、`root`、`sudo`。

### Memory 和 Skill 目录落点

- **Memory**：`get_hermes_home() / "memories"` → `get_memory_dir()`（`memory_tool.py:55-57`）；
- **Skills**：`get_hermes_home() / "skills"` → `SKILLS_DIR`（`skill_manager_tool.py:109`、`skills_tool.py:89`）；
- **Config**：`get_hermes_home() / "config.yaml"` → `get_config_path()`（`hermes_constants.py:278`）。

### `get_active_profile_name()` 实现

`hermes_cli/profiles.py:947-971`：从 `HERMES_HOME` 反推 profile 名，用于 background review fork 的 `_init_kwargs["agent_identity"]`。

```python
def get_active_profile_name() -> str:
    hermes_home = get_hermes_home()
    resolved = hermes_home.resolve()
    default_resolved = _get_default_hermes_home().resolve()
    if resolved == default_resolved:
        return "default"
    profiles_root = _get_profiles_root().resolve()
    try:
        rel = resolved.relative_to(profiles_root)
        parts = rel.parts
        if len(parts) == 1 and _PROFILE_ID_RE.match(parts[0]):
            return parts[0]
    except ValueError:
        pass
    return "custom"
```

---

## 8. 触发到回显的完整时序

以下是一次完整的 nudge→review→回显调用链（以 skill nudge 为例）：

```
1. run_conversation(user_message) 入口
   ├─ run_agent.py:11952  _user_turn_count += 1
   ├─ run_agent.py:11973-11979  检测 memory flag（_turns_since_memory +1，达阈值置 _should_review_memory=True）
   └─ messages.append({"role": "user", ...})

2. 主 agent loop（chat_completions 路径）
   ├─ run_agent.py:12276-12278  每次 API 迭代后 _iters_since_skill += 1
   └─ run_agent.py:10725-10729 / 11164-11168  工具实际执行时（未被 block）归零计数器

3. 主 agent loop 结束，final_response 确定
   run_agent.py:15594-15598  检测 skill flag：
   if _iters_since_skill >= _skill_nudge_interval:
       _should_review_skills = True
       _iters_since_skill = 0

4. run_agent.py:15609-15617  触发条件满足 → 调用 _spawn_background_review()
   参数：messages_snapshot=list(messages), review_memory, review_skills

5. _spawn_background_review()（run_agent.py:4225）
   ├─ 选 prompt（combined / memory / skill）
   └─ 创建 daemon thread，name="bg-review"，启动

6. daemon thread 内部（_run_review 闭包）
   ├─ 安装 auto-deny approval callback（防止 dangerous command 走到 input()）
   ├─ stdout/stderr redirect 到 /devnull
   ├─ _current_main_runtime() 读取父 agent credentials
   ├─ AIAgent(max_iterations=16, quiet_mode=True, ...)
   ├─ 复制 _memory_store / _cached_system_prompt / session_id
   ├─ 设 _memory_nudge_interval=0, _skill_nudge_interval=0（防递归）
   ├─ set_thread_tool_whitelist({"memory", "skill_manage", ...})
   └─ review_agent.run_conversation(
          user_message=prompt + "\n\nYou can only call memory and skill...",
          conversation_history=messages_snapshot,
      )

7. review_agent 内部执行
   ├─ 调用 memory(action="add"/"replace"/"remove") → 直接写 MemoryStore（共享实例）
   └─ 调用 skill_manage(action="create"/"patch") → 写 ~/.hermes/skills/ 磁盘
       └─ skill_manage 成功后 clear_skills_system_prompt_cache()

8. run_conversation 返回后（仍在 daemon thread）
   ├─ _summarize_background_review_actions(review_agent._session_messages, messages_snapshot)
   │   └─ 过滤掉 snapshot 中已有的 tool 结果，提取 success 动词
   ├─ _safe_print(f"  💾 Self-improvement review: {summary}")  ← 打印到父进程 terminal
   └─ background_review_callback(summary)  ← 可选 gateway 推送

9. 主 run_conversation() 早已在步骤 4 之后返回了 final_response 给用户
   （review 在后台异步执行，不阻塞 response delivery）
```

**关键时序点**：`_spawn_background_review` 在 `run_conversation` 还未 return 前被调用（步骤 4），但 thread 是 daemon 异步的，主线程继续执行并 return result；review 的输出回显可能在用户收到 response 之后数秒才打印。

---

## 附录：关键常量速查

| 常量 / 变量 | 值 | 位置 |
|---|---|---|
| `memory.nudge_interval` 默认值 | `10`（turns） | `run_agent.py:1970` |
| `skills.creation_nudge_interval` 默认值 | `10`（tool iterations） | `run_agent.py:2077` |
| `memory.memory_char_limit` 默认值 | `2200` chars | `run_agent.py:1982` |
| `memory.user_char_limit` 默认值 | `1375` chars | `run_agent.py:1983` |
| `MAX_SKILL_CONTENT_CHARS` | `100_000` chars | `skill_manager_tool.py:164` |
| `MAX_SKILL_FILE_BYTES` | `1_048_576` (1 MiB) | `skill_manager_tool.py:165` |
| `MAX_NAME_LENGTH`（skill/category） | `64` chars | `skill_manager_tool.py:111` |
| `MAX_DESCRIPTION_LENGTH` | `1024` chars | `skill_manager_tool.py:112` |
| `VALID_NAME_RE` | `r'^[a-z0-9][a-z0-9._-]*$'` | `skill_manager_tool.py:168` |
| `ENTRY_DELIMITER` | `"\n§\n"` | `memory_tool.py:59` |
| `ALLOWED_SUBDIRS` | `{"references","templates","scripts","assets"}` | `skill_manager_tool.py:171` |
| review fork `max_iterations` | `16` | `run_agent.py:4292` |
| Memory 目录 | `{HERMES_HOME}/memories/` | `memory_tool.py:57` |
| Skills 目录 | `{HERMES_HOME}/skills/` | `skill_manager_tool.py:109` |
| Skills prompt 缓存失效入口 | `clear_skills_system_prompt_cache(clear_snapshot=True)` | `skill_manager_tool.py:768` |
