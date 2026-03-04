from fastapi.testclient import TestClient

from nano_multiagent.server.app import create_app


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_task_tool_contract_is_exposed_by_tools_endpoint() -> None:
    app = create_app(auth_token="test-token")
    client = TestClient(app)

    response = client.get("/v1/tools", headers=_auth_headers("req-task-contract"))

    assert response.status_code == 200
    tools = {item["name"]: item for item in response.json()["tools"]}
    task_descriptor = tools["task"]
    assert task_descriptor["input_schema"]["required"] == [
        "load_skills",
        "description",
        "prompt",
        "run_in_background",
    ]
    assert task_descriptor["input_schema"]["properties"]["load_skills"]["type"] == "array"
    assert task_descriptor["input_schema"]["properties"]["load_skills"]["items"]["type"] == "string"
    assert task_descriptor["input_schema"]["properties"]["run_in_background"]["type"] == "boolean"
    assert "mode" not in task_descriptor["input_schema"]["properties"]
    assert "idempotency_key" in task_descriptor["input_schema"]["properties"]
    assert "timeout_seconds" in task_descriptor["input_schema"]["properties"]
    assert "category" in task_descriptor["input_schema"]["properties"]
    assert "subagent_type" in task_descriptor["input_schema"]["properties"]
    assert tools["read"]["description"] == (
        "Read the contents of a file. Supports text files and images (jpg, png, gif, webp). "
        "Images are sent as attachments. For text files, output is truncated to 2000 lines "
        "or 50KB (whichever is hit first). Use offset/limit for large files. "
        "When you need the full file, continue with offset until complete."
    )
    assert tools["bash"]["description"] == (
        "Execute a bash command in the current working directory. Returns stdout and stderr. Output is "
        "truncated to last 2000 lines or 50KB (whichever is hit first). "
        "If truncated, full output is saved to a temp file. Optionally provide a timeout in seconds."
    )
    assert tools["edit"]["description"] == (
        "Edit a file by replacing exact text. The oldText must match exactly (including whitespace). "
        "Use this for precise, surgical edits."
    )
    assert tools["write"]["description"] == (
        "Write content to a file. Creates the file if it doesn't exist, overwrites if it does. "
        "Automatically creates parent directories."
    )
    assert task_descriptor["description"] == (
        "Spawn agent task with category-based or direct agent selection.\n\n"
        "MUTUALLY EXCLUSIVE: Provide EITHER category OR subagent_type, not both (unless continuing a session).\n\n"
        "- load_skills: ALWAYS REQUIRED. Pass at least one skill name (e.g., [\"playwright\"], [\"git-master\", \"frontend-ui-ux\"]).\n"
        "- category: Use predefined category → Spawns Sisyphus-Junior with category config\n"
        "  Available categories:\n"
        "${categoryList}\n"
        "- subagent_type: Use specific agent directly (e.g., \"oracle\", \"explore\")\n"
        "- run_in_background: true=async (returns task_id), false=sync (waits for result). Default: false. "
        "Use background=true ONLY for parallel exploration with 5+ independent queries.\n"
        "- session_id: Existing Task session to continue (from previous task output). Continues agent with FULL CONTEXT PRESERVED - "
        "saves tokens, maintains continuity.\n"
        "- command: The command that triggered this task (optional, for slash command tracking).\n\n"
        "**WHEN TO USE session_id:**\n"
        "- Task failed/incomplete → session_id with \"fix: [specific issue]\"\n"
        "- Need follow-up on previous result → session_id with additional question\n"
        "- Multi-turn conversation with same agent → always session_id instead of new task\n\n"
        "Prompts MUST be in English."
    )
    assert tools["read"]["input_schema"]["properties"]["path"]["description"] == "Path to the file to read (relative or absolute)"
    assert tools["read"]["input_schema"]["properties"]["offset"]["description"] == "Line number to start reading from (1-indexed)"
    assert tools["read"]["input_schema"]["properties"]["limit"]["description"] == "Maximum number of lines to read"
    assert tools["bash"]["input_schema"]["properties"]["command"]["description"] == "Bash command to execute"
    assert tools["bash"]["input_schema"]["properties"]["timeout"]["description"] == (
        "Timeout in seconds (optional, no default timeout)"
    )
    assert tools["edit"]["input_schema"]["properties"]["path"]["description"] == (
        "Path to the file to edit (relative or absolute)"
    )
    assert tools["edit"]["input_schema"]["properties"]["oldText"]["description"] == (
        "Exact text to find and replace (must match exactly)"
    )
    assert tools["edit"]["input_schema"]["properties"]["newText"]["description"] == (
        "New text to replace the old text with"
    )
    assert tools["write"]["input_schema"]["properties"]["path"]["description"] == (
        "Path to the file to write (relative or absolute)"
    )
    assert tools["write"]["input_schema"]["properties"]["content"]["description"] == "Content to write to the file"
    assert task_descriptor["input_schema"]["properties"]["load_skills"]["description"] == (
        "Skill names to inject. REQUIRED - pass [] if no skills needed, but IT IS HIGHLY RECOMMENDED to pass "
        "proper skills like [\"playwright\"], [\"git-master\"] for best results."
    )
    assert task_descriptor["input_schema"]["properties"]["description"]["description"] == (
        "Short task description (3-5 words)"
    )
    assert task_descriptor["input_schema"]["properties"]["prompt"]["description"] == (
        "Full detailed prompt for the agent"
    )
    assert task_descriptor["input_schema"]["properties"]["run_in_background"]["description"] == (
        "true=async (returns task_id), false=sync (waits). Default: false"
    )
    assert task_descriptor["input_schema"]["properties"]["category"]["description"] == (
        "Category (e.g., ${categoryExamples}). Mutually exclusive with subagent_type."
    )
    assert task_descriptor["input_schema"]["properties"]["subagent_type"]["description"] == (
        "Agent name (e.g., 'oracle', 'explore'). Mutually exclusive with category."
    )
    assert task_descriptor["input_schema"]["properties"]["session_id"]["description"] == (
        "Existing Task session to continue"
    )
    assert task_descriptor["input_schema"]["properties"]["command"]["description"] == (
        "The command that triggered this task"
    )
    assert "/v1/tasks" not in {route.path for route in app.routes}
