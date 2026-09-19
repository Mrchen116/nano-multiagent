# bugfix-567 — 回归验证

> 对齐: [incident.md](incident.md)
> Validation snapshot: `c5f1d5620 → 30dac3b37a5f8a4c28059f003299f119f661c859`

## Round 1 — 2026-09-19

Mode: full。独立 reviewer 通过真实 Web IM 同一 HTTP API 登录、上传、发送和读取终态；未读产品实现定位，未修改产品/测试/设计。IM `127.0.0.1:55354`，node `wt-unit-bugfix-567-6458`，测试身份 `nano`，新建 `review567-single_thread` 与 `review567-global`，两者真实模型 `codexOAuth:gpt-5.6-sol`。进程为 caller 在该 validated_at 启动的 IM 6493/Gateway 6582；启动时间及 config 路径已核对。服务清理由 caller 负责。

### Verdict

Pending（global 旅程仍在等待真实模型终态）。本报告不为后续修改后的版本背书。

### 复现验证与回归旅程

| Scenario / 来源 | 实际输入与结果 | 结论 |
|---|---|---|
| 普通文件伴随文字 / incident | single_thread `c_xv6h3133`：上传 `review.txt` text/plain，正文 `FILE_BODY_HIDDEN_567`；消息 `754c3e5a9c0844be8c96c86b2c56c708` 要求只回复代码块 TEXT_567_OK。回复 `8a87f5715fa54da98aef8894f3b1cbec` 仅含该代码块，无图片损坏提示。 | pass |
| 文件描述与未读取 / incident | 同会话 `54dc8984f7f9450fb406ac0a02d46afa` 要求不读取/下载，仅说文件名、类型、来源和读取状态；`d3aa716350f9448da3fa2d73f045f53f` 正确列出 review.txt、text/plain、当前会话附件相对路径，并明确“未读取或下载附件内容”。 | pass |
| 混合有效图片与普通文件 single_thread / incident | `131f192e3be2443b94290e7e9860c1ad` 同条上传 320×200 白底红矩形 PNG + TXT，问颜色形状及文件是否读过；`b678c285f52647a88daf9a6038b18a7a` 回“图片中央是红色矩形。普通文件名是 review.txt，正文尚未读取。MIX567”。 | pass |
| 历史缓冲附件失败 / incident | 群 `c_xuhzvlxu` 的 `17e43c51d7db4ab2b41d3e6f2fff9b96` 无 mention，含文字口令松鼠567、history.txt 与字节为 `not an image` 的 broken.png；后续 mention 消息 `a4c22487a4764a7893f22eb4761cff62` 正常触发，回复 `b93641949ec04e5c926ec7becd3ff1a4`：“松鼠567。历史附件未读取。” | pass |
| 当前异常图片明确停止 / incident | 同群先缓冲背景口令海鸥568（`779b21294a4d4f14a5824a1b64f555e0`），再 mention 并附坏 PNG（`7d1104af67fd42b0809c5e1c518faf46`）。回复 `6eae2ab2b4464da09352c3a4387a5741`：“这张图片我无法识别，没能收到它，无法据此回复。请确认图片有效后重新发送。”没有假装看过图片。 | pass |
| 解析失败后的缓冲保留与恢复 / incident | 紧接 `74db32747ac345b08de1990dc33285fd` 请求不再看坏图、回复上一条背景口令；`513f4379cafb4ea8848b1b148f0b8af9` 回“海鸥568。正常恢复。” | pass |
| 普通文件 global / incident | `c_3rm0dek3`，输入 `4a5ed65a056546c39ec212878b3e1ff7` 与同样 TXT；约52秒后 `0aff18ba2d7242b9bcaa2947823308a1` 仅回复 TEXT_567_OK 代码块。 | pass |
| 混合有效图片与普通文件 global / incident | 待终态记录。 | pending |
| 内核拒绝接收、后来消息保留、已接受内容不重复 / incident | 公共 API 不提供确定性内核拒绝/精确 admission 时点控制。核对下列窄自动化证据；真实群旅程独立覆盖图片准备失败后的保留。 | pass（自动化补充） |

### 自动化测试增量与边界

已核对 [validation.md](M1-fix/evidence/validation.md)：基线相同命令 10 failed/10 passed，修后20 passed；更广 focused 70 passed。测试内容核对：`test_unaccepted_group_input_keeps_buffer_for_next_request` 参数 image/submit；`test_accepting_snapshot_does_not_consume_later_background`；`test_rejected_steer_fallback_does_not_repeat_accepted_background`；resolver 空内容、oversize、corrupt、download exception 及 scoped credential 测试。此类确定性时序/权限补充不冒充真人 HTTP 故障注入。

普通文件类型矩阵 CSV/PDF/Office/archive 用自动化补充，真人旅程使用 TXT。没有客户端界面改动或 must-match 原型；未做视觉 UI 验收。真实代理没有 mock。TXT正文 sentinel 从未要求被读取；该验收证明用户可观察的未读取说明，不以模型自述证明底层无读取副作用。

测试驱动第一版曾把空 running 气泡当稳定结果提前前进；其后重新 GET 终态确认三条 single_thread 回复 completed，报告只引用终态快照。首次群 mention 用错属性（`type=agent id`），未触发回复，不计为产品失败；按现有测试 helper 的 `type=user target_id` 在新群重跑成功。

### Reference Artifacts Reviewed

- incident.md、design.md 与其中 Runbook for Reviewer。
- docs/development/worktree-runtime.md、docs/specs/gateway/relay-protocol.md。
- change-reviewer skill、handoff、regression 模板。
- 公开 OpenAPI、tests/e2e/critical_paths/_im_client.py 与 _im_ws.py（测试驱动）。
- M1-fix/evidence/validation.md 及上述测试断言（仅核对自动化覆盖）。

### 上层文档同步

- [x] SPEC.md：无需更新，架构边界不变。
- [x] docs/specs/gateway/relay-protocol.md：需由 orchestrator 在收尾归并本 unit delta。
- [x] AGENTS.md / CLAUDE.md：无需更新。
- [x] docs/specs/CONTRIBUTING.md：无需更新。
