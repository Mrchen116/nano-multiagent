# refactor-675 独立代码审查

## Round 1 — full

- 日期：2026-10-28。
- 版本：`f6175e871..9de55b2df`；开始审查时 working tree clean，无额外未提交实现。
- 身份与范围：未参与实现的独立 reviewer；覆盖全部 17 个变更文件及相邻调用链，使用 `change-code-review` 与 `agent-context-review` Mode B。仅写本报告，未修改实现/设计、未提交、未操作生产。
- 结论：1 WARNING（CONFIRMED），0 CRITICAL；修正该部署指令后可做针对性 patch review。本报告不替代最终 verifier、CI 或迁移验收。

```json
[
  {
    "file": ".claude/skills/prod-fleet-deploy/references/runbook.md",
    "line": 51,
    "summary": "[P2] 将目标版本 ready 检查与停服务/切 SHA 顺序统一",
    "failure_scenario": "Air 部署 Agent 更新 Mini 时，第 51 行要求先将固定生产 checkout 切到目标 SHA，然后在停止 IM 前再运行 ready；第 53 行及 66–68 行却要求先停止 Gateway/IM 再 checkout。固定生产目录承载正在运行的 IM/Gateway，按第一条顺序执行会在 live checkout 中替换文件，并可能使随后 stop 使用尚未构建或与当前进程不同版本的 CLI。现在的命令示例顺序正确，但不能消除同一操作单中另一条直接相反的指令。",
    "review_mode": "full",
    "status": "CONFIRMED",
    "surface": "部署 Agent 按需加载的 prod-fleet-deploy reference / 执行顺序",
    "expected": "Agent 在任何生产 checkout 切换或构建前先停止受影响 Gateway/IM，并能在这个约束下完成已安装 supervisor 与候选脚本的前置检查。",
    "observed": "同一 reference 第 51 行明确使用“固定生产 checkout 切到已确认 SHA 后、停止 IM…前”，而第 53 行和代码块明确使用 stop、bootout、checkout 的相反顺序。",
    "impact": "下一次常规版本部署存在实质的执行歧义，可能边运行边替换生产代码，破坏本次引入的生产固定 checkout 更新约束。此 finding 不声称本次同 SHA 迁移已经发生该故障。",
    "recommendation": "统一为先检查已安装 supervisor，再停受影响服务，随后切生产 checkout；候选脚本若必须停服务前检查，使用 git show/独立临时文件等只读取版本内容的方式，或明确切换后的检查发生于停服务之后。",
    "severity": "WARNING",
    "evidence": "受审 9de55b2df 中 runbook.md:51、53、66–68，prod-fleet-deploy/SKILL.md:23；直接读取 Agent 将加载的最终正文，确定性指令冲突，无需生产执行来确认。未运行真实部署 Agent，不宣称模型必然选择错误顺序。"
  }
]
```

## 覆盖与证据

- `scripts/dev_host.py`：逐项读取配置默认/显式缺失、格式/类型处理、真实路径解析、保护目录双向包含、祖先标记、飞书能力拒绝、路径选择与 check 输出。check 不读取/输出 YAML 正文或凭据；返回的是命令版本与路径事实，不冒充真实模型或服务健康证据。
- E2E up/down：guard 在复制配置、删除 handoff/DB、读取飞书 env/取得锁、停止进程之前；显式 default `--main-config` 优先，default/daily/feishu 缺省选择本机源 YAML，再进入既有 profile 转换。down 不因 Mini 禁用飞书而拒绝清理普通隔离栈。
- 开发 Context：实际读 AGENTS → local-development → worktree-runtime / llm-integration，核对当前机器资源、参数来源、缺失资源、历史路径失效与模型证据边界。没有产品模型 prompt/schema/Memory 修改，无须为此再起业务模型任务。编号链实际读 change-spec-author、change-design-author 与 changes README：新建前 fetch、所有 type 的同号冲突、未发布重取号、已发布沿用和禁止 force-push 保持一致。
- Air 独立实际 `check`：在文档推荐的固定 Node 与主仓 `.venv/bin` PATH 下，host=air、Node 24.22.1、Python 3.12.9、飞书允许，日志与参考根存在。初次默认 shell 也被准确报告为 Node 25/Python 3.9；check 没有把版本报告等同兼容认证。
- Mini 独立实际 `check`：从 `~/Repos/nano-multiagent/.worktrees/refactor-675-dev`（`20887f251`，脚本与受审 head 相同）以推荐 PATH 执行，host=mini、Node 24.22.1、Python 3.14.5、飞书禁用；日志存在、reference_root 不存在被准确显示。Mini 开发主仓仍处生产旧 SHA，直接在那里调用新脚本不存在；随后按实际 worktree 定位执行成功。当前 protected_paths 仍包含原生产 data，迁移最终保护集合由 verifier 随迁移收口核对。
- 独立运行 `python3 -m pytest -q tests/integration/test_dev_host.py`：13 passed，0.62s；`git diff --check f6175e871 9de55b2df` 通过。没有启动完整产品栈或重复全量。
- 复用 caller 的版本化证据：Air/Mini 在相同 `20887f251` 的 daily 栈、独立模型回包、down 和 Mini 飞书提前拒绝；这些是 caller 提供的可信运行事实，本 reviewer 未重复起栈。配置消费脚本在 `20887f251..9de55b2df` 无代码变化。
- 已读取 `output/refactor-675/pytest.log`（113 passed）、`native-targeted.log`（2 files / 9 tests passed）；第二轮 `pnpm-test-final.log` 截止本次审查已结束为 2 failed / 780 passed。完整 CI 尚不能记为通过；失败处置属于 caller 最终验证，不凭静态脚本 diff 推定其归因。

## 未验证与边界

生产迁移的最终 600 秒采样、原 data 移入受保护备份、生产完整数据/资源/进程核对正在由 caller 收口。本审查没有对这些未完成步骤报代码缺陷，也不宣称迁移验收完成。未发生产消息、未读取密钥正文、未发包、未 merge。开发 Agent 的代表性消费证据为本 reviewer 在真实两机环境按入口读文档并执行 check；没有捕获一个额外开发 Agent 的 provider payload，不外推为所有模型、多轮恢复与部署行为都可靠。
