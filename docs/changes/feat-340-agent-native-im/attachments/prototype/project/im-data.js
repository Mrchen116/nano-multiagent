// Mock data for the Agent-native IM prototype
window.IM_DATA = {
  currentUser: { id: "user_1", name: "Alex Chen", initials: "AC" },

  agents: [
    { id: "agent_assistant", name: "Assistant", initials: "AS", color: "oklch(0.52 0.14 180)", description: "General-purpose coding & research assistant", status: "online", node: "my-macbook", model: "claude-3-5-sonnet-20241022" },
    { id: "agent_planner",   name: "Planner",   initials: "PL", color: "oklch(0.52 0.14 270)", description: "Sprint planning and task decomposition", status: "online", node: "my-macbook", model: "claude-3-5-sonnet-20241022" },
    { id: "agent_reviewer",  name: "Reviewer",  initials: "RV", color: "oklch(0.52 0.14 30)",  description: "Code review and quality assurance", status: "offline", node: "remote-server", model: "claude-3-haiku-20240307" }
  ],

  conversations: [
    {
      id: "conv_1", kind: "direct-agent", agent_id: "agent_assistant",
      title: "Assistant", kind_label: "Agent", unread: 2,
      last_at: "2026-04-29T10:42:00Z", last_preview: "I've updated src/relay_service.py with the fix.",
      participants: ["You", "Assistant"],
      messages: [
        { id: "m1", sender: "user", content: "Can you help me understand the structure of the src/IM directory and fix the bug in relay_service.py line 312?", at: "2026-04-29T10:38:00Z" },
        {
          id: "m2", sender: "agent", agent_id: "agent_assistant", content: "Let me explore the directory and look at that file.",
          at: "2026-04-29T10:38:08Z", status: "completed",
          tool_calls: [
            { id: "tc1", name: "list_files", status: "completed", duration_ms: 48,
              input: { path: "src/IM", depth: 2 },
              output: "src/IM/\n  app.py\n  api/\n    routes/\n      messages.py\n      agents.py\n  application/\n    relay_service.py\n    event_service.py\n  domain/\n    models.py\n  frontend/" },
            { id: "tc2", name: "read_file", status: "completed", duration_ms: 22,
              input: { path: "src/IM/application/relay_service.py", offset: 300, limit: 30 },
              output: "300: def _dispatch_relay(self, task_id: str, payload: dict):\n301:     \"\"\"Dispatch a relay task to the target node.\"\"\"\n302:     node = self._get_node(payload.get('node_id'))\n303:     if node is None:\n304:         raise RelayError('target_node_id is not connected')\n305:     ...\n312:     result = await self._send(node.endpoint, payload)  # BUG: missing timeout\n313:     return result" },
            { id: "tc3", name: "str_replace_edit", status: "completed", duration_ms: 31,
              input: { path: "src/IM/application/relay_service.py", old_string: "result = await self._send(node.endpoint, payload)  # BUG: missing timeout", new_string: "result = await self._send(node.endpoint, payload, timeout=self.relay_timeout_seconds)" },
              output: "Edit applied successfully." },
            { id: "tc4", name: "bash", status: "completed", duration_ms: 1820,
              input: { command: "cd /repo && python -m pytest tests/test_relay_service.py -x -q 2>&1 | tail -20" },
              output: ".....\n5 passed in 0.84s" }
          ]
        },
        { id: "m3", sender: "agent", agent_id: "agent_assistant",
          content: "I've updated `src/relay_service.py` with the fix.\n\nThe bug on line 312 was a missing `timeout` argument to `_send()`. Without it, relay calls could hang indefinitely if the target node became unresponsive.\n\nThe fix passes `self.relay_timeout_seconds` — the existing config value — to the call. All 5 existing tests pass.",
          at: "2026-04-29T10:38:12Z", status: "completed",
          token_usage: { output: 312, context_used: 14820, context_window: 200000 } },
        { id: "m4", sender: "user", content: "Great. Can you also add a unit test for the timeout case?", at: "2026-04-29T10:42:00Z" },
        {
          id: "m5", sender: "agent", agent_id: "agent_assistant", content: "Writing the test now…",
          at: "2026-04-29T10:42:05Z", status: "running",
          tool_calls: [
            { id: "tc5", name: "read_file", status: "completed", duration_ms: 18,
              input: { path: "tests/test_relay_service.py" },
              output: "import pytest\nfrom unittest.mock import AsyncMock, patch\nfrom IM.application.relay_service import RelayService\n\n# ... existing tests ..." },
            { id: "tc6", name: "str_replace_edit", status: "running", duration_ms: null,
              input: { path: "tests/test_relay_service.py", old_string: "# ... existing tests ...", new_string: "# ... existing tests ...\n\nasync def test_dispatch_relay_timeout():\n    ..." },
              output: null }
          ]
        }
      ]
    },
    {
      id: "conv_2", kind: "group", title: "Sprint Planning", kind_label: "Group", unread: 0,
      last_at: "2026-04-29T09:15:00Z", last_preview: "Planner: I've broken down the auth epic into 6 tasks.",
      participants: ["You", "Assistant", "Planner"],
      messages: [
        { id: "g1", sender: "user", content: "Let's plan the auth epic for next sprint. @Planner can you decompose it? @Assistant can you estimate effort?", at: "2026-04-29T09:10:00Z" },
        {
          id: "g2", sender: "agent", agent_id: "agent_planner", content: "I've broken down the auth epic into 6 tasks.",
          at: "2026-04-29T09:11:00Z", status: "completed",
          tool_calls: [
            { id: "g_tc1", name: "read_file", status: "completed", duration_ms: 15,
              input: { path: "docs/auth-epic.md" },
              output: "# Auth Epic\n## Goals\n- SSO via SAML 2.0\n- Session management\n- Audit logging\n..." },
            { id: "g_tc2", name: "write_file", status: "completed", duration_ms: 9,
              input: { path: "docs/sprint-tasks.md", content: "# Sprint Tasks\n1. SAML IdP integration\n2. Token refresh\n3. Session store\n..." },
              output: "File written: docs/sprint-tasks.md" }
          ]
        },
        { id: "g3", sender: "agent", agent_id: "agent_planner", content: "Tasks:\n1. SAML IdP integration (backend + tests)\n2. Token refresh flow\n3. Redis session store\n4. Audit log schema\n5. Frontend login page\n6. E2E test suite\n\nSaved to `docs/sprint-tasks.md`.", at: "2026-04-29T09:11:05Z", status: "completed",
          token_usage: { output: 189, context_used: 8430, context_window: 200000 } },
        { id: "g4", sender: "agent", agent_id: "agent_assistant", content: "Rough estimates based on codebase familiarity:\n\n- Tasks 1–3: 3 days each (high complexity, new integrations)\n- Task 4: 0.5 day\n- Task 5: 1.5 days\n- Task 6: 2 days\n\n**Total: ~13 days.** Fits a 2-week sprint if we cut scope on task 6.", at: "2026-04-29T09:15:00Z", status: "completed",
          token_usage: { output: 156, context_used: 9820, context_window: 200000 } }
      ]
    },
    {
      id: "conv_3", kind: "direct-agent", agent_id: "agent_planner",
      title: "Planner", kind_label: "Agent", unread: 0,
      last_at: "2026-04-28T17:30:00Z", last_preview: "The roadmap has been updated in ROADMAP.md.",
      participants: ["You", "Planner"],
      messages: [
        { id: "p1", sender: "user", content: "Update the roadmap to reflect Q2 priorities.", at: "2026-04-28T17:28:00Z" },
        {
          id: "p2", sender: "agent", agent_id: "agent_planner", content: "Updating ROADMAP.md now.",
          at: "2026-04-28T17:28:10Z", status: "completed",
          tool_calls: [
            { id: "p_tc1", name: "read_file", status: "completed", duration_ms: 12, input: { path: "ROADMAP.md" }, output: "# Roadmap\n## Q1 2026\n- Multi-agent coordination\n- IM frontend v2\n..." },
            { id: "p_tc2", name: "str_replace_edit", status: "completed", duration_ms: 8, input: { path: "ROADMAP.md", old_string: "## Q1 2026", new_string: "## Q2 2026" }, output: "Edit applied." }
          ]
        },
        { id: "p3", sender: "agent", agent_id: "agent_planner", content: "The roadmap has been updated in `ROADMAP.md` to reflect Q2 priorities.", at: "2026-04-28T17:30:00Z", status: "completed",
          token_usage: { output: 42, context_used: 5210, context_window: 200000 } }
      ]
    },
    {
      id: "conv_4", kind: "agent-network", title: "Agent Network: Deploy", kind_label: "Agent↔Agent", unread: 0,
      last_at: "2026-04-28T14:00:00Z", last_preview: "Reviewer: LGTM. Merging.",
      participants: ["Assistant", "Reviewer"],
      messages: [
        { id: "n1", sender: "agent", agent_id: "agent_assistant", content: "Requesting code review for PR #47 — relay timeout fix.", at: "2026-04-28T13:55:00Z", status: "completed" },
        { id: "n2", sender: "agent", agent_id: "agent_reviewer", content: "Reviewing…", at: "2026-04-28T13:56:00Z", status: "completed",
          tool_calls: [
            { id: "n_tc1", name: "bash", status: "completed", duration_ms: 2100, input: { command: "git diff main..pr/47" }, output: "- result = await self._send(node.endpoint, payload)\n+ result = await self._send(node.endpoint, payload, timeout=self.relay_timeout_seconds)" },
            { id: "n_tc2", name: "bash", status: "completed", duration_ms: 890, input: { command: "python -m pytest tests/ -q" }, output: "......\n6 passed in 1.02s" }
          ]
        },
        { id: "n3", sender: "agent", agent_id: "agent_reviewer", content: "LGTM. The timeout is correctly threaded through. Tests pass. Merging.", at: "2026-04-28T14:00:00Z", status: "completed",
          token_usage: { output: 67, context_used: 11340, context_window: 200000 } }
      ]
    }
  ],

  agentConfigs: [
    {
      agent_id: "agent_assistant", display_name: "Assistant", owner_id: "owner_1",
      description: "General-purpose coding & research assistant",
      system_prompt: "You are a skilled software engineer. Help the user with coding tasks, debugging, and code review. Always run tests after making changes. Be concise.",
      group_reply_policy: "MENTION", skills: ["bash", "file_ops", "web_search"],
      tool_allowlist: ["bash", "read_file", "write_file", "list_files", "str_replace_edit", "web_search"],
      default_model: "claude-3-5-sonnet-20241022", profile_version: 12,
      workspace_root: "~/nano-assistant/workspace/agent_assistant/",
      node_id: "my-macbook", node_name: "My MacBook Pro", node_status: "online",
      updated_at: "2026-04-29T09:00:00Z"
    },
    {
      agent_id: "agent_planner", display_name: "Planner", owner_id: "owner_1",
      description: "Sprint planning and task decomposition",
      system_prompt: "You are a product and engineering planner. Help break down epics into tasks, estimate effort, and maintain project documentation. Be structured and methodical.",
      group_reply_policy: "MENTION", skills: ["file_ops"],
      tool_allowlist: ["read_file", "write_file", "list_files"],
      default_model: "claude-3-5-sonnet-20241022", profile_version: 5,
      workspace_root: "~/nano-assistant/workspace/agent_planner/",
      node_id: "my-macbook", node_name: "My MacBook Pro", node_status: "online",
      updated_at: "2026-04-28T12:00:00Z"
    },
    {
      agent_id: "agent_reviewer", display_name: "Reviewer", owner_id: "owner_1",
      description: "Code review and quality assurance",
      system_prompt: "You are a senior code reviewer. Analyze pull requests, run tests, check for security issues, and provide clear, actionable feedback.",
      group_reply_policy: "ALWAYS", skills: ["bash", "file_ops"],
      tool_allowlist: ["bash", "read_file", "list_files"],
      default_model: "claude-3-haiku-20240307", profile_version: 3,
      workspace_root: "~/nano-assistant/workspace/agent_reviewer/",
      node_id: "remote-server", node_name: "Remote Server", node_status: "offline",
      updated_at: "2026-04-27T08:00:00Z"
    }
  ],

  account: {
    id: "user_1", user_id: "user_1", display_name: "Alex Chen",
    default_entry_node_id: "my-macbook",
    owned_node_ids: ["my-macbook", "lab-server", "remote-server"],
    created_at: "2025-11-01T08:00:00Z"
  },

  nodes: [
    {
      node_id: "my-macbook", node_name: "MacBook Pro (Alex)", alias: "My MacBook Pro",
      status: "online", agent_count: 2,
      last_heartbeat_at: "2026-04-30T10:59:30Z", version: "0.9.4",
      last_error: null, relay_enabled: true, reporting_enabled: true
    },
    {
      node_id: "lab-server", node_name: "Ubuntu Lab Server", alias: "Lab Server",
      status: "online", agent_count: 1,
      last_heartbeat_at: "2026-04-30T09:12:00Z", version: "0.9.2",
      last_error: "relay.accepted timeout after 30s on run_id=xyz123", relay_enabled: true, reporting_enabled: false
    },
    {
      node_id: "remote-server", node_name: "Remote Server (Hetzner)", alias: "Remote Server",
      status: "offline", agent_count: 1,
      last_heartbeat_at: "2026-04-27T08:14:00Z", version: "0.9.1",
      last_error: "connection refused: heartbeat missed for 3d 2h", relay_enabled: true, reporting_enabled: true
    }
  ],

  capabilities: {
    tools: ["bash", "read_file", "write_file", "list_files", "str_replace_edit", "web_search", "create_file", "delete_file"],
    skills: ["bash", "file_ops", "web_search", "code_review", "planning"],
    model_options: ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307", "claude-opus-4"],
    platform_default_model: "claude-3-5-sonnet-20241022"
  }
};

window.IM_UTILS = {
  formatTime(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return `${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`;
  },
  formatDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    const now = new Date();
    const diff = now - d;
    if (diff < 86400000) return this.formatTime(iso);
    if (diff < 172800000) return "Yesterday";
    return `${d.getMonth()+1}/${d.getDate()}`;
  },
  agentById(id) {
    return window.IM_DATA.agents.find(a => a.id === id) || { name: "Agent", initials: "AG", color: "oklch(0.52 0.14 180)" };
  },
  totalDuration(tool_calls) {
    if (!tool_calls) return 0;
    return tool_calls.reduce((s, tc) => s + (tc.duration_ms || 0), 0);
  },
  formatDuration(ms) {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms/1000).toFixed(1)}s`;
  }
};
