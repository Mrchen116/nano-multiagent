"""Unit tests for built-in tool presenters."""

from agent.platform.tools.presentation import resolve_presenter_for_tool
from agent.platform.tools.builtins.read import ReadTool
from agent.platform.tools.builtins.write import WriteTool
from agent.platform.tools.builtins.edit import EditTool
from agent.platform.tools.builtins.bash import BashTool
from agent.platform.tools.builtins.web_fetch import WebFetchTool
from agent.platform.tools.builtins.agent import AgentTool
from agent.platform.tools.builtins.memory import MemoryTool
from agent.platform.tools.builtins.skill_manage import SkillManageTool
from agent.platform.tools.builtins.task_stop import TaskStopTool

_TOOL_BY_NAME = {
    "read": ReadTool,
    "write": WriteTool,
    "edit": EditTool,
    "bash": BashTool,
    "web_fetch": WebFetchTool,
    "agent": AgentTool,
    "memory": MemoryTool,
    "skill_manage": SkillManageTool,
    "task_stop": TaskStopTool,
}


class _FakeResult:
    def __init__(self, output=None, error=None):
        self.output = output
        self.error = error


def _presenter(name: str):
    # 决策 12: presenter travels with the tool object; resolve off the built-in
    # tool class .presenter (unknown names → default presenter).
    return resolve_presenter_for_tool(_TOOL_BY_NAME.get(name))


class TestReadPresenter:
    def test_start_shows_path(self) -> None:
        evt = _presenter("read").format_start({"path": "src/app.py"})
        assert evt.visible is True
        assert evt.label == "Read"
        assert evt.summary == "src/app.py"

    def test_end_text_file_lines(self) -> None:
        # feat-409 readfix: summary 与 detail 都必须带 path。
        evt = _presenter("read").format_end(
            {"path": "src/app.py"},
            _FakeResult(output={"path": "src/app.py", "total_lines": 120, "offset": 1}),
            duration_ms=12,
        )
        # feat-409 protoalign: 折叠 summary 中文化为 `<path> · N 行`。
        assert evt.summary == "src/app.py · 120 行"
        assert evt.detail is not None
        assert evt.detail["path"] == "src/app.py"
        assert evt.detail["total_lines"] == 120

    def test_end_text_file_with_limit(self) -> None:
        evt = _presenter("read").format_end(
            {"path": "src/app.py", "limit": 40},
            _FakeResult(
                output={"path": "src/app.py", "total_lines": 120, "offset": 40}
            ),
            duration_ms=12,
        )
        assert evt.summary == "src/app.py · 第 40-79 行"
        assert evt.detail is not None
        assert evt.detail["path"] == "src/app.py"
        assert evt.detail["offset"] == 40
        assert evt.detail["limit"] == 40

    def test_end_image(self) -> None:
        evt = _presenter("read").format_end(
            {"path": "img.png"},
            _FakeResult(
                output={
                    "path": "img.png",
                    "content": [{"type": "image", "data": "..."}],
                }
            ),
            duration_ms=12,
        )
        assert evt.summary == "img.png · image"
        assert evt.detail is not None
        assert evt.detail["path"] == "img.png"
        assert evt.detail["image"] is True

    def test_end_unchanged(self) -> None:
        evt = _presenter("read").format_end(
            {"path": "src/app.py"},
            _FakeResult(output={"path": "src/app.py", "type": "file_unchanged"}),
            duration_ms=12,
        )
        assert evt.summary == "src/app.py · unchanged"
        assert evt.detail is not None
        assert evt.detail["path"] == "src/app.py"
        assert evt.detail["unchanged"] is True

    def test_end_failed_summary_is_clean_path(self) -> None:
        # feat-409 failalign: 失败态 summary = 干净主参数(path),与成功态同构,
        # 绝不含 error 文本(error 只进 detail,展开卡渲染一次)。
        evt = _presenter("read").format_end(
            {"path": "missing.py"},
            _FakeResult(error="file does not exist"),
            duration_ms=2,
        )
        assert evt.summary == "missing.py"
        assert "file does not exist" not in evt.summary
        assert evt.detail is not None
        assert evt.detail["path"] == "missing.py"
        assert evt.detail["error"]["message"] == "file does not exist"


class TestWritePresenter:
    def test_start_shows_path(self) -> None:
        evt = _presenter("write").format_start({"path": "src/app.py"})
        assert evt.label == "Write"
        assert evt.summary == "src/app.py"

    def test_end_created(self) -> None:
        evt = _presenter("write").format_end(
            {"path": "src/app.py", "content": "hello"},
            _FakeResult(output={"type": "create"}),
            duration_ms=5,
        )
        # feat-409 protoalign: summary 对齐原型 `<path> · 新建 <size>`。
        assert evt.summary == "src/app.py · 新建 5B"
        assert evt.detail is not None
        assert evt.detail["path"] == "src/app.py"
        assert evt.detail["bytes"] == 5

    def test_end_updated(self) -> None:
        evt = _presenter("write").format_end(
            {"path": "src/app.py", "content": "hello world"},
            _FakeResult(output={"type": "update"}),
            duration_ms=5,
        )
        # feat-409 protoalign: 覆盖写对齐原型 `<path> · 覆盖 <size>`。
        assert evt.summary == "src/app.py · 覆盖 11B"
        assert evt.detail is not None

    def test_end_failed(self) -> None:
        # feat-409 failalign: 失败态 summary = 干净主参数(path),不含 error 文本。
        evt = _presenter("write").format_end(
            {"path": "src/app.py", "content": "hello"},
            _FakeResult(error="permission denied"),
            duration_ms=5,
        )
        assert evt.summary == "src/app.py"
        assert "permission denied" not in evt.summary
        assert evt.detail is not None
        assert "error" in evt.detail


class TestEditPresenter:
    def test_start_shows_path(self) -> None:
        evt = _presenter("edit").format_start({"path": "src/app.py"})
        assert evt.label == "Edit"
        assert evt.summary == "src/app.py"

    def test_end_updated(self) -> None:
        evt = _presenter("edit").format_end(
            {"path": "src/app.py", "oldText": "foo", "newText": "bar"},
            _FakeResult(output={}),
            duration_ms=5,
        )
        assert "updated" in evt.summary
        assert evt.detail is not None
        assert "diff" in evt.detail

    def test_end_failed(self) -> None:
        # feat-409 failalign: 失败态 summary = 干净主参数(path),不含 error 文本。
        evt = _presenter("edit").format_end(
            {"path": "src/app.py", "oldText": "foo", "newText": "bar"},
            _FakeResult(error="Could not find the exact text"),
            duration_ms=5,
        )
        assert evt.summary == "src/app.py"
        assert "Could not find" not in evt.summary
        assert evt.detail is not None
        assert "error" in evt.detail


class TestBashPresenter:
    def test_start_shows_command_when_no_description(self) -> None:
        # bugfix-427: 无 description 时 format_start 降级显示命令首段，与 format_end 对齐。
        evt = _presenter("bash").format_start({"command": "pytest tests/"})
        assert evt.label == "Bash"
        assert evt.summary == "pytest tests/"

    def test_start_shows_description_when_present(self) -> None:
        # bugfix-427: 有 description 时 format_start.summary = description（人话），
        # 与 format_end 来源一致——开始态即显示人话，不再等到执行完才切换。
        evt = _presenter("bash").format_start(
            {"command": "pytest -xvs tests/unit/", "description": "跑单元测试"}
        )
        assert evt.label == "Bash"
        assert evt.summary == "跑单元测试"

    def test_end_summary_is_description(self) -> None:
        # 决策 4: 折叠态摘要为人话 description，不再是裸 exit/elapsed 状态串。
        evt = _presenter("bash").format_end(
            {"command": "pytest -q", "description": "跑 heartbeat 单元测试"},
            _FakeResult(output={"exitCode": 0, "stdout": "OK"}),
            duration_ms=2100,
        )
        assert evt.summary == "跑 heartbeat 单元测试"
        assert evt.detail is not None
        assert evt.detail["stdout"] == "OK"
        assert evt.detail["command"] == "pytest -q"
        assert evt.detail["exit_code"] == 0

    def test_end_summary_falls_back_to_command_when_no_description(self) -> None:
        # 边界:description 为空时降级显示命令首段，而不是空白。
        evt = _presenter("bash").format_end(
            {"command": "echo hello world"},
            _FakeResult(output={"exitCode": 0, "stdout": "hello world"}),
            duration_ms=10,
        )
        assert evt.summary == "echo hello world"

    def test_end_failed(self) -> None:
        # feat-409 failalign: 失败态 summary = 干净人话主参数(description),与成功态
        # 同构,不含 error 文本。失败由 ✕ 图标 + fail-tag(前端 exit N / failed)表达。
        evt = _presenter("bash").format_end(
            {"command": "pytest", "description": "跑测试"},
            _FakeResult(error="Command exited with code 1"),
            duration_ms=500,
        )
        assert evt.summary == "跑测试"
        assert "Command exited" not in evt.summary
        assert evt.detail is not None
        assert "error" in evt.detail

    def test_end_failed_falls_back_to_command(self) -> None:
        # description 为空时失败态降级为命令首段,仍不含 error。
        evt = _presenter("bash").format_end(
            {"command": "ls /nope"},
            _FakeResult(error="No such file or directory"),
            duration_ms=5,
        )
        assert evt.summary == "ls /nope"
        assert "No such file" not in evt.summary


class TestWebFetchPresenter:
    def test_start_shows_url_with_globe_emoji(self) -> None:
        # feat-425 决策 4: 折叠主参数是 url;emoji 随工具走 = 🌐。
        evt = _presenter("web_fetch").format_start({"url": "https://example.com"})
        assert evt.label == "Web"
        assert evt.summary == "https://example.com"
        assert evt.emoji == "🌐"

    def test_end_success_summary_is_url_detail_has_content(self) -> None:
        # feat-425 决策 4: 折叠行显 url(不再 status=200 (title));detail 读
        # content/status/final_url(放弃 title);emoji=🌐。
        evt = _presenter("web_fetch").format_end(
            {"url": "https://example.com"},
            _FakeResult(
                output={
                    "ok": True,
                    "url": "https://example.com",
                    "final_url": "https://example.com/doc",
                    "status": 200,
                    "content": "正文内容",
                }
            ),
            duration_ms=300,
        )
        assert evt.summary == "https://example.com"
        assert evt.emoji == "🌐"
        assert evt.detail is not None
        assert evt.detail["status"] == 200
        assert evt.detail["content"] == "正文内容"
        assert evt.detail["final_url"] == "https://example.com/doc"
        # 放弃 title:detail 不再带 title key。
        assert "title" not in evt.detail

    def test_end_failed_out_of_band(self) -> None:
        # feat-409 failalign: result.error(out-of-band)失败态 summary = 干净主参数(url)。
        evt = _presenter("web_fetch").format_end(
            {"url": "https://example.com"},
            _FakeResult(error="connection timed out"),
            duration_ms=5000,
        )
        assert evt.summary == "https://example.com"
        assert evt.emoji == "🌐"
        assert "timed out" not in evt.summary
        assert evt.detail is not None
        assert "error" in evt.detail

    def test_end_failed_in_band_ok_false(self) -> None:
        # feat-425 决策 4: 网络错误/非法 URL 时 run() 返回 {ok:False,error},
        # result.error 为空 — presenter 必须判 output["ok"] is False,落失败分支,
        # 绝不产 status=None 的成功串。
        evt = _presenter("web_fetch").format_end(
            {"url": "https://bad.example"},
            _FakeResult(
                output={
                    "ok": False,
                    "url": "https://bad.example",
                    "error": "URL validation failed: Missing domain",
                }
            ),
            duration_ms=5,
        )
        assert evt.summary == "https://bad.example"
        assert evt.emoji == "🌐"
        assert evt.detail is not None
        # 失败态:展开看到可读 error,不含 status=None。
        assert "error" in evt.detail
        assert evt.detail.get("status") is None or "status" not in evt.detail

    def test_end_body_excerpt_relaxed_and_capped(self) -> None:
        # web_fetch detail body 放宽:不再硬截到 500 字,大正文走 _enforce_cap(content)。
        long_body = "A" * 5000
        evt = _presenter("web_fetch").format_end(
            {"url": "https://example.com"},
            _FakeResult(output={"ok": True, "status": 200, "content": long_body}),
            duration_ms=10,
        )
        assert evt.detail is not None
        # body 字段保留远多于旧的 500 字硬截
        assert len(evt.detail["content"]) > 500

    def test_end_preserves_run_truncated_flag(self) -> None:
        # feat-425 A2: run() 默认截到 50K(< _enforce_cap 256KB,cap 不翻转此标志),
        # presenter 必须保留 run() 返回的真实 output["truncated"],而非硬编码 False —
        # 否则正文被截断时 WebCard 不显示"源头已截断"。
        evt = _presenter("web_fetch").format_end(
            {"url": "https://example.com"},
            _FakeResult(
                output={
                    "ok": True,
                    "status": 200,
                    "content": "短正文",
                    "truncated": True,
                }
            ),
            duration_ms=10,
        )
        assert evt.detail is not None
        assert evt.detail["truncated"] is True


class TestAgentPresenter:
    def test_start_shows_description(self) -> None:
        evt = _presenter("agent").format_start(
            {"description": "Refactor auth module", "prompt": "do it"}
        )
        assert evt.label == "Agent"
        assert evt.summary == "Refactor auth module"

    def test_end_completed_has_full_prompt_before_result(self) -> None:
        # 决策 3:完整未截断 prompt 进 detail,且语义上排在结果前。
        long_prompt = "请完成以下任务:\n" + ("步骤 " * 1000)
        evt = _presenter("agent").format_end(
            {
                "description": "派子 agent 改测试",
                "prompt": long_prompt,
                "subagent_type": "general-purpose",
            },
            _FakeResult(
                output={
                    "status": "completed",
                    "content": "已完成",
                    "agent_id": "agt-1",
                }
            ),
            duration_ms=5000,
        )
        assert evt.summary == "派子 agent 改测试"
        assert evt.detail is not None
        # 完整 prompt 不截断
        assert evt.detail["prompt"] == long_prompt
        assert evt.detail["status"] == "completed"
        assert evt.detail["content"] == "已完成"
        assert evt.detail["agent_id"] == "agt-1"
        assert evt.detail["subagent_type"] == "general-purpose"
        # prompt 排在 content(结果)之前
        keys = list(evt.detail.keys())
        assert keys.index("prompt") < keys.index("content")

    def test_end_async_launched(self) -> None:
        evt = _presenter("agent").format_end(
            {"description": "后台任务", "prompt": "go", "run_in_background": True},
            _FakeResult(
                output={
                    "status": "async_launched",
                    "agent_id": "agt-2",
                    "description": "后台任务",
                    "output_file": "/tmp/out.jsonl",
                }
            ),
            duration_ms=100,
        )
        assert evt.detail["status"] == "async_launched"
        assert evt.detail["output_file"] == "/tmp/out.jsonl"
        assert evt.detail["prompt"] == "go"

    def test_end_failed(self) -> None:
        # feat-409 failalign: in-band 失败态 summary = 干净主参数(description),
        # 不含 error 文本;error 进 detail 供 AgentCard 渲染一次。
        evt = _presenter("agent").format_end(
            {"description": "X", "prompt": "go"},
            _FakeResult(output={"status": "failed", "error": "boom", "agent_id": "a"}),
            duration_ms=10,
        )
        assert evt.summary == "X"
        assert "boom" not in evt.summary
        assert evt.detail["error"] == "boom"

    def test_end_failed_out_of_band_summary_is_clean(self) -> None:
        # out-of-band(result.error)失败态同样 summary = description,不含 error。
        evt = _presenter("agent").format_end(
            {"description": "派子 agent", "prompt": "go"},
            _FakeResult(error="dispatch crashed"),
            duration_ms=10,
        )
        assert evt.summary == "派子 agent"
        assert "dispatch crashed" not in evt.summary
        assert evt.detail is not None
        assert "error" in evt.detail

    def test_end_failed_error_is_plain_str(self) -> None:
        # fix 3: detail["error"] must be a clean JSON-serializable string regardless
        # of the raw output.error shape (None / non-str). Front-end AgentCard renders it.
        evt = _presenter("agent").format_end(
            {"description": "X", "prompt": "go"},
            _FakeResult(output={"status": "failed", "agent_id": "a"}),  # no error key
            duration_ms=10,
        )
        assert isinstance(evt.detail["error"], str)
        assert evt.detail["error"] == ""


class TestMemoryPresenter:
    def test_end_success(self) -> None:
        evt = _presenter("memory").format_end(
            {"action": "add", "target": "memory", "content": "记住这件事"},
            _FakeResult(output={"success": True, "message": "added entry to 'memory'"}),
            duration_ms=5,
        )
        assert evt.label == "Memory"
        assert evt.detail is not None
        assert evt.detail["action"] == "add"
        assert evt.detail["target"] == "memory"
        assert evt.detail["content"] == "记住这件事"
        assert evt.detail["success"] is True
        assert "added" in evt.detail["message"]

    def test_end_failure(self) -> None:
        # feat-409 failalign+protoalign: success=False 失败态 summary = 干净人话主参数
        # (`±target` 摘要),不含 error 文本;error 进 detail.message 供 MemoryCard 渲染一次。
        evt = _presenter("memory").format_end(
            {"action": "add", "target": "memory"},
            _FakeResult(output={"success": False, "error": "add requires content"}),
            duration_ms=5,
        )
        assert evt.summary == "+memory"
        assert "requires content" not in evt.summary
        assert evt.detail["success"] is False
        assert evt.detail["message"] == "add requires content"

    def test_end_error_summary_is_clean(self) -> None:
        # out-of-band(result.error)失败态同样 summary = 人话主参数,不含 error。
        evt = _presenter("memory").format_end(
            {"action": "add", "target": "memory"},
            _FakeResult(error="store unavailable"),
            duration_ms=5,
        )
        assert evt.summary == "+memory"
        assert "store unavailable" not in evt.summary
        assert evt.detail is not None
        assert "error" in evt.detail


class TestSkillManagePresenter:
    def test_end_create(self) -> None:
        evt = _presenter("skill_manage").format_end(
            {"action": "create", "name": "my-skill", "content": "..."},
            _FakeResult(
                output={"success": True, "message": "created skill 'my-skill' at /p"}
            ),
            duration_ms=5,
        )
        assert evt.label == "Skill"
        assert evt.detail is not None
        assert evt.detail["action"] == "create"
        assert evt.detail["name"] == "my-skill"
        assert evt.detail["success"] is True
        assert "created" in evt.detail["message"]

    def test_end_failure(self) -> None:
        # feat-409 failalign+protoalign: success=False 失败态 summary = 干净人话主参数
        # (`创建 skill：x`),不含 error 文本;error 进 detail.message 供 SkillCard 渲染一次。
        evt = _presenter("skill_manage").format_end(
            {"action": "create", "name": "x"},
            _FakeResult(output={"success": False, "error": "requires content"}),
            duration_ms=5,
        )
        assert evt.summary == "创建 skill：x"
        assert "requires content" not in evt.summary
        assert evt.detail["success"] is False
        assert evt.detail["message"] == "requires content"

    def test_end_error_summary_is_clean(self) -> None:
        # out-of-band(result.error)失败态同样 summary = 人话主参数,不含 error。
        evt = _presenter("skill_manage").format_end(
            {"action": "create", "name": "x"},
            _FakeResult(error="disk full"),
            duration_ms=5,
        )
        assert evt.summary == "创建 skill：x"
        assert "disk full" not in evt.summary
        assert evt.detail is not None
        assert "error" in evt.detail


class TestTaskStopPresenter:
    def test_end_killed(self) -> None:
        evt = _presenter("task_stop").format_end(
            {"task_id": "agt-9"},
            _FakeResult(
                output={
                    "status": "killed",
                    "task_id": "agt-9",
                    "task_type": "subagent",
                }
            ),
            duration_ms=5,
        )
        assert evt.label == "TaskStop"
        assert evt.detail is not None
        assert evt.detail["task_id"] == "agt-9"
        assert evt.detail["status"] == "killed"

    def test_end_failed(self) -> None:
        # feat-409 failalign: 失败态 summary = 干净主参数(task_id),不含 error 文本。
        evt = _presenter("task_stop").format_end(
            {"task_id": "agt-9"},
            _FakeResult(error="Task 'agt-9' is already completed."),
            duration_ms=5,
        )
        assert evt.summary == "agt-9"
        assert "already completed" not in evt.summary
        assert evt.detail is not None
        assert "error" in evt.detail


class TestDefaultPresenter:
    def test_unknown_tool(self) -> None:
        evt = _presenter("unknown_tool_xyz").format_start({"foo": "bar"})
        assert evt.visible is True
        assert evt.label == "Tool"

    def test_default_end_with_error(self) -> None:
        # feat-409 failalign: default presenter 无干净主参数,失败态 summary 用裸
        # "failed"(不拼 error 文本);error 进 detail 供 ErrorCard 渲染一次。
        evt = _presenter("unknown_tool_xyz").format_end(
            {"foo": "bar"},
            _FakeResult(error="something broke"),
            duration_ms=10,
        )
        assert evt.summary == "failed"
        assert "something broke" not in evt.summary
        assert evt.detail is not None
        assert evt.detail["error"]["message"] == "something broke"
