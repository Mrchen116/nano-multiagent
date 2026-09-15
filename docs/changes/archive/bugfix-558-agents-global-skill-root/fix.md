# bugfix-558：PA 发现当前 Codex 用户级 Skill 目录

## 现象与复现

当前 Codex 官方把 `$HOME/.agents/skills` 定义为用户级 Skill 目录，适用于该用户打开的所有仓库；旧的 `$CODEX_HOME/skills`（默认 `~/.codex/skills`）仍保留为 deprecated 兼容路径。

当有效 Skill 只存在于 `~/.agents/skills/<name>/SKILL.md` 时，PA Gateway 不会在 node/agent capabilities 中上报它，因此 Web IM 的 Agent 配置页无法显示或选择该 Skill。相同文件复制到 `~/.codex/skills` 后才会出现。

验收场景：

- **GIVEN** Gateway 用户的 `~/.agents/skills` 中存在有效 Skill
- **WHEN** 用户打开在线节点上的 Agent 新建页或既有 Agent 配置页
- **THEN** 该 Skill 出现在“兼容来源”候选中
- **AND** 它不因来自用户级兼容目录而默认选中
- **AND** 既有 `~/.claude/skills`、`~/.codex/skills` 和 `~/.nanoassistant/skills` 继续可用
- **AND** 本次不新增 `<workspace>/.agents/skills`，不改变 `skill_manage` 写入目录

## 根因

PA 产品 composition 与 Gateway 侧共享 Skill usage 查询都把共享读取 roots 固定为 `~/.nanoassistant/skills`、`~/.claude/skills`、`~/.codex/skills`。这反映了旧 Codex 目录约定，但没有跟进当前官方 `$HOME/.agents/skills` 用户级目录。

由于 Kernel、capability preview/runtime 和 `skill_view` 都只解析消费者显式传入的 roots，未声明的 `~/.agents/skills` 不会进入任何 PA 发现链路。前端仅渲染 Gateway 上报的候选，因此不是前端过滤或 SKILL.md 格式问题。

## 修复

- 在 PA product composition 的有序用户级 Skill roots 中，将 `~/.agents/skills` 插入 `~/.nanoassistant/skills` 与既有 `~/.claude/skills`、`~/.codex/skills` 之间；工作区 roots 保持 `.nanoassistant`、`.claude`、`.codex`，未新增 `.agents`。
- Gateway 的共享 Skill usage 查询采用相同用户级 root 顺序，使该目录中的 `.usage.json` 能按 Agent 所属 session 过滤后上报。
- 沿用既有 capability 来源投影：只有 `~/.nanoassistant/skills` 属于 `global` 且默认选中，`~/.agents/skills` 属于 `compatibility` 且 `default_on=false`。`global_skill_root` 和 `skill_manage` 写入目标未改变。
- 更新 PA 当前行为契约及既有 product wiring、capability payload、usage reporting 测试，不修改历史 feat-519 文档。

回退时可删除两处 `~/.agents/skills` 读取 root 及对应测试/契约增量；该回退不涉及数据迁移或写入目录恢复。

## 验证

TDD Red（生产代码修改前）：

- `../../.venv/bin/python -m pytest -q tests/unit/personal_assistant/test_product_workspace_layout.py::test_pa_kernel_passes_product_workspace_and_global_roots tests/unit/personal_assistant/test_gateway_upstream_reporter.py::test_node_capabilities_marks_pa_global_skills_default_on tests/unit/personal_assistant/test_gateway_im_connection_behavior.py::test_im_connection_skills_usage_includes_agents_shared_root_for_agent_sessions tests/contract/test_capability_payload_contract.py::test_node_capabilities_payload_matches_contract tests/contract/test_capability_payload_contract.py::test_agent_capabilities_payload_matches_contract` → `5 failed`；失败分别证明 kernel root wiring、node/agent capability discovery 与 Gateway usage reporting 尚未包含 `~/.agents/skills`。

Green 与扩展验证：

- 同一组 5 个聚焦用例 → `5 passed in 0.45s`。
- `../../.venv/bin/python -m pytest -q tests/unit/personal_assistant/test_product_workspace_layout.py tests/unit/personal_assistant/test_gateway_upstream_reporter.py tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/contract/test_capability_payload_contract.py` → `52 passed in 2.58s`。
- `ulimit -n 4096 && env -u SEARXNG_URL ../../.venv/bin/python -m pytest -q tests/unit/personal_assistant` → `1304 passed in 50.49s`。提高文件描述符上限并清除宿主的 SearXNG provider 覆盖后，PA 全量 unit suite 在隔离测试口径下通过。
- `git diff --check` → 通过。
- `../../.venv/bin/python -m ruff check`（本次修改的 Python 源码与测试）→ `All checks passed!`。
- `PYTHON=../../.venv/bin/python ./scripts/docs-check` → `documentation integrity passed: 236 maintained Markdown sources, 73 required routes`。
- 独立 code review → `Approved`，`0 critical / 0 warning`；仅记录既有两处 root tuple 需依靠测试保持同步的非阻断残余限制。
- 同步 `origin/main` 到 `e63857a46` 后完成 rebase；主干增量未修改本修复的产品路径或测试 seam，review 结论保留有效，并由最终树全量 CI 复验。
- 最终树本地 CI：documentation integrity、`ruff check .`、`ruff format --check .` 通过；agent/PA 分片 `1882 passed`，remaining Python 分片 `1977 passed`；前端 `npm audit --audit-level=critical` 通过（无 critical），Vitest `759 passed`。
