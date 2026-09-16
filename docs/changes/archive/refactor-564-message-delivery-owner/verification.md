# Verification Report: refactor-564-message-delivery-owner

## Round 1 — full + corrected-delta

Validation snapshot: `6ee4c71ab → 6ee83e2e35cb02006295d59d042d4d2d2e1d442f`.

- verification_mode: full
- verdict: fail
- CRITICAL: 1; WARNING: 0; SUGGESTION: 0
- requires_full_verification: false（修复后需覆盖后台运行完整链及相关共享候选/反馈边界）
- 核对范围：motivation、design 与 M1 退出标准，两个 delta、最终 kernel/gateway current 契约、SPEC.md 跨包边界、testing.md，以及真实源码与回归测试。
- 本轮只编辑本报告；使用提供的 unit worktree，没有自行启动服务或操作生产。没有提交。

## Completeness

| M1 退出标准 | 结果与证据 |
|---|---|
| 普通/显式/恢复交付 owner | 前台与显式入口成立；后台普通输出仍有绕过权限和完整轮收集的入口，见 C1 |
| SDK 无产品交付状态 | `src/agent/sdk/permissions.py:1` 只声明通用允许/拒绝；旧 OutputCandidate/OutputResult/BoundOutputControl/output_handler 已从 src 删除 |
| 系统来源反馈、有限修正、停止/新输入 | `delivery_feedback.py:18`、`session_run_coordinator.py:1993`、`delivery_ledger.py:103`；聚焦测试通过 |
| 完整轮/权限/多轮/恢复保护 | 已有前台回归覆盖完整轮、拒绝、两次修正、stop/reset、上传期间新输入和 ACK 丢失；后台权限缺口未被原测试覆盖 |
| 产品 reviewer 真实旅程 | 由独立产品验收负责；本报告不把 mocked transport 测试宣称为真实飞书/Web 验收 |

Prototype / Reference：N/A，无布局变更。

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 / 验证 | 状态 |
|---|---|---|---|
| 完整模型轮完成、多 chunk/tool、异常不完整 | `src/agent/core/agent/loop.py:791`；`gateway/runtime_delivery/candidate_observer.py:83` | `test_model_round_end.py`、`test_candidate_observer.py` | 前台 covered；后台 C1 |
| SDK 真实会话权限检查、不执行工具 | `src/agent/sdk/kernel.py:2205`；`core/agent/runtime.py:351` | `test_sdk_tool_authorization.py` | covered |
| 普通权限及 descriptor 在批准前绑定 | `gateway/message_delivery.py:174`；`gateway/delivery_permission.py:18` | `test_pa_delivery_manual_permission.py` 真实 Kernel broker 的 allow/deny/stop；原 owner 单测含路径替换保护 | 前台 covered；后台 C1 |
| 准备期间新输入不发布旧群候选 | `gateway/session_run_coordinator.py:632`；`runtime_delivery/context.py:316`；`message_delivery.py:300` | `test_pa_delivery_input_admission.py`，以实际 pending_id 消费回执释放门禁 | covered |
| 私有失败反馈为系统来源、最多两次、第二次文字说明 | `gateway/delivery_feedback.py:18`；`session_run_coordinator.py:2017`；`delivery_ledger.py:103` | `test_session_run_coordinator_delivery_feedback.py` 包含解析、成功、耗尽、busy、stop/reset/new input | covered |
| 显式发送失败不额外安排普通反馈 | `gateway/internal_dispatch.py:207,286,489` | 显式入口只返回工具事实；不调用 coordinator feedback | covered |
| 已确认/未知/部分交付复用原身份 | `gateway/message_delivery.py:389`；`delivery_ledger.py:37` | `test_reply_delivery_recovery.py`：删源重放、活跃 run、稳定 ID、provider 过期窗口 | covered |
| 完成帧不读源、不越过未知 ACK | `runtime_delivery/image_connection.py:107` | `test_im_reply_image_delivery.py:54,87` | covered |
| 飞书先交付、IM 离线后补 | `message_delivery.py:284,705,874`；`shadow_sync.py:329` | `test_pa_offline_image_shadow.py:55` 使用已存快照；外部原身份回执不重新生成 | covered |

### 本轮独立执行

```sh
.venv/bin/pytest -q tests/unit/personal_assistant/test_candidate_observer.py tests/unit/personal_assistant/test_session_run_coordinator_delivery_feedback.py tests/integration/test_pa_delivery_input_admission.py tests/integration/test_pa_delivery_manual_permission.py tests/unit/agent/test_model_round_end.py tests/contract/test_sdk_tool_authorization.py
```

结果：**23 passed in 14.89s**。该结果证明上述聚焦行为；不代替 root 的全量测试、CI 和产品验收。

## Coherence

| Design 决定 | 核对结果 | 证据 |
|---|---|---|
| 内核生成与 Gateway 交付分离 | 符合 | 内核轮结束只发布通用事实；SDK 权限接口不带图片/渠道状态 |
| 普通候选只有一个完整轮入口 | 后台有实质偏离 | 前台 candidate observer 成立；非群后台仍每条 assistant_message 调 deliver_background |
| IM 写入只接受已准备投影 | 符合 | `image_connection.py:113` 未准备正文拒绝；完成只使用 saved projection |
| Shadow 不独立准备 Agent 正文 | 符合 | `shadow_sync.py:329,347,388` 委托 owner 的投影/提交 |
| composition 仅接线 | 基本符合 | 构造 owner/candidate observer；后台遗留接线导致 C1 |
| 反馈由产品 coordinator 调度 | 前台/已接入群后台符合 | `session_run_coordinator.py:1993` 原路由及模型生命周期，稳定 submission 与实际准入计数 |

## Issues

### CRITICAL

**C1 — 非群/外部后台普通回复绕过图片权限与完整轮反馈链。**

契约：`docs/specs/gateway/routing-delivery.md:16` 要求普通图片回复执行同等发送权限判断；22–24 要求图片语法不能越权。design「所有权」「完整候选」「权限复用」「失败反馈」要求后台对应 coordinator 也经同一流程。

实际：`src/personal_assistant/gateway/composition.py:813` 的后台观察器只接管 web_relay 且启用 revalidate_output 的运行。其余后台经 `background_subscriptions.py:262` 逐条 assistant_message → background sender → `message_delivery.py:769`；其中 799 直接 `images.prepare`，随后 project/upload/commit，未调用 `authorize_tool`，也没有完整 model_round_end 边界及 bounded failure feedback。

独立一次性复现：使用真实 MessageDelivery、RunDeliveryContextStore、ReplyImages 和临时 SQLite/PNG（图片在 workspace 外），Kernel.authorize_tool 设置为拒绝，IM 仅替换协议 transport/ACK；调用 deliver_background 后输出：`{'permission_calls': 0, 'snapshot_saved': True, 'public_sends': 1}`。临时目录随脚本退出清理；未读取真实用户图片。

修复：所有普通 BACKGROUND_TASK 回复进入现有完整轮候选观察器、权限检查与 coordinator 反馈流程，保留真实路由、background_returns、稳定身份与群恢复；删除绕过流程的后台正文准备/提交入口。最低保护应从真实后台订阅接线验证 deny 不读取/上传/公开，多块一轮完整发布，以及失败修正与停止。

### WARNING

无。

### SUGGESTION

无。

## Round 2 — targeted-closure

Validation snapshot: `c4ba604625001290f0191be06ae7ad741c9b4626 → c2d8c14226d219665cf50a584974fe357e629640`.

- verification_mode: targeted-closure
- review_round: 2
- fix_delta_range: `6ee83e2e3..c2d8c1422`（生产实现冻结于 `4e6093e32`，最后提交只修正外部协议测试 fixture）
- focus_issues: C1
- verdict: **pass**
- CRITICAL: **0**; WARNING: **0**; SUGGESTION: **0**
- requires_full_verification: **false**
- validated_issues: **C1 closed**；保留 Round 1 其余通过结论，复验覆盖本次共享候选与反馈影响。

### C1 关闭证据

1. `src/personal_assistant/gateway/background_subscriptions.py:244` 不再接收原始后台正文发送器；`composition.py:808` 对全部来源渠道转交 coordinator，不再仅处理 web_relay 群复核。旧 `MessageDelivery.deliver_background` 和 `assistant_reply_delivery` 接口已删除。
2. `session_run_coordinator.py:500` 接管全部 BACKGROUND_TASK，注册实际 session/run/generation；`_seed_background_delivery:653` 保存原生目标、外部 provider/thread 与 shadow conversation/message/saga。后台继承统一 candidate observer，在 `model_round_end` 才生成候选，随后进入原 `MessageDelivery.deliver_candidate` 的 descriptor/权限/快照/回执链。
3. `session_run_coordinator.py:718` 的后台反馈在终态通过相同 `try_submit_idle`、`feedback_parts`、持久 ledger 准入，继承 logical_request_id；预算仍是两次实际准入，第二次只要求文字。stop/reset、新真人输入、session generation 和 superseded 门禁均在 transition 中检查。successor 注册到同一持久订阅，不另开原始发送分支。
4. `runtime_delivery/candidate_observer.py:82` 收集各 chunk 的 background_returns 并去重，不因末块无 sidecar 丢失；纯 sidecar 轮只提交过程信息。独立单测覆盖两种情况。
5. 新后台集成测试使用实际 compose_gateway、Kernel、权限链、SQLite 和图片资源准备，模拟边界仅为 LLM/网络协议：跨 chunk 图片完整发布且一次上传、真实权限 deny 与 missing 均不上传不公开草稿、随后系统反馈文字修正、两次额度持久化且耗尽停止。Feishu 成功及拒绝两种路径保持原 receive_id 和 IM shadow turn_start conversation；拒绝路径无图片上传。

### 本轮独立执行与限制

```sh
PYTHONPATH=src .venv/bin/pytest -q tests/integration/test_background_reply_images.py tests/unit/personal_assistant/test_candidate_observer.py tests/unit/personal_assistant/test_background_subscription_manager.py tests/unit/personal_assistant/test_session_run_coordinator_delivery_feedback.py tests/integration/test_pa_delivery_input_admission.py tests/integration/test_pa_delivery_manual_permission.py
```

首次：**36 passed / 2 failed in 44.31s**，只失败于两条新增 external fixture，原因是 fake `send_prepared_message` 返回任意消息 ID 而非真实协议状态 `delivered`，使同一 ID 正确进入未知回执恢复。测试运行期间该文件由实施方收尾；本 verifier 未改测试。最终 `c2d8c1422` 修正协议 ACK、等待可观察正文，以及在真实携带路由的 turn_start 断言 conversation。

```sh
PYTHONPATH=src .venv/bin/pytest -q tests/integration/test_background_reply_images.py -k external
```

最终：**2 passed, 5 deselected in 9.73s**。其他 36 项通过证据保留；产品源码与前次执行相同。第三方 protobuf 发出 datetime 弃用提示，不是产品失败。本轮不重复 root 全量套件，不替代独立真实产品验收或远端 CI。

## Round 3 — targeted permission-operation closure

Validation snapshot: `c4ba604625001290f0191be06ae7ad741c9b4626 → 150fbe30d80695a7e61a3eaf35ce2b43df4db116`.

- verification_mode: targeted-closure + corrected-delta
- fix_delta_range: `c2d8c1422..150fbe30d`
- focus: 真实产品验收的权限分类来源表示修正（P1）
- verdict: **pass**；CRITICAL **0** / WARNING **0** / SUGGESTION **0**
- requires_full_verification: **false**；保留 Round 1/2 其余结论。

独立核对：

- `agent/sdk/kernel.py:2214` 的可选 operation_description 经 executor/conversation 进入 `core/agent/runtime.py:396`，仅写 typed HookContext 字段。模型 arguments 和 session metadata 不被读取成该字段；生产源码中该字段只有一个赋值入口。默认 None 保留真实模型工具调用的既有投影。
- `platform/hooks/builtins/auto_mode_gate.py:324` 仅改变本次 classifier action 的表示为 host_operation，完整保留所复用的 permission_policy 与原 proposed_action；没有改工具策略、拦截顺序、显式 deny、人工审批或取消。`core/tools/registry.py:511` 仍以原 tool name/arguments 运行原拦截链。
- Kernel/SDK/core 新增的是通用宿主操作说明，没有图片、渠道或送达状态字段。当前会话普通回复的业务解释只在 Gateway `delivery_permission.py:56` 构造。说明不被用作允许标记，也没有新增 bypass flag。
- kernel delta 新增的「宿主操作与模型工具调用可区分」Scenario 与 current `docs/specs/kernel/runs.md:529` 文字及实现对应；design changelog 明确这属于来源修正而非授权。gateway delta 无本次新偏离。

独立执行：

```sh
PYTHONPATH=src .venv/bin/pytest -q tests/contract/test_sdk_tool_authorization.py tests/unit/personal_assistant/test_pa_reply_delivery.py tests/unit/test_auto_mode_gate_dispatch.py tests/unit/test_auto_mode_gate_hook.py tests/integration/test_pa_delivery_manual_permission.py
```

**76 passed in 11.19s**。包含真实 SDK→classifier 最终 payload 的 host_operation/原参数投影、classifier allow 与 deny、metadata/model arguments 不能伪造来源、tool policy 显式 deny 保持，以及 Gateway 人工 allow/deny/stop。该范围不包含另行实施中的 sidecar 修复；未改源码/测试。

## Round 4 — targeted IM sidecar compatibility closure

- executed_base: `c4ba604625001290f0191be06ae7ad741c9b4626`
- validated_at / effective_through: `d4a59af212690dfe50af77a1b689e572ad32499c`
- fix_delta_range: `150fbe30d..d4a59af21`
- verification_mode: targeted-closure + corrected-delta retention
- focus: P2，Bash 后台返回不阻断原 IM 权限审批交付
- verdict: **pass**；CRITICAL **0** / WARNING **0** / SUGGESTION **0**
- requires_full_verification: **false**；Round 1–3 已关闭问题与通过结论继续有效。

`runtime_delivery/observer.py:2317` 只在 Gateway 的显示投影入口复制 event 并过滤 IM 不支持的 background_returns 项；支持的 subagent/workflow 原对象和顺序保持。Kernel 事件、模型输入的 task-notification、正文及权限决策均未被修改。IM `domain/models.py:159,231` 的既有 schema 正式只接受 subagent/workflow。current `routing-delivery.md:463–491` 明确 Bash 保留第二条普通文本、subagent/workflow 保留结构化卡，因此此次是恢复既有契约，不需要新增 delta。

独立执行：

```sh
PYTHONPATH=src .venv/bin/pytest -q tests/integration/test_pa_background_return_permission.py tests/integration/test_pa_delivery_manual_permission.py tests/unit/personal_assistant/test_candidate_observer.py
```

**12 passed in 14.15s**。真实 Kernel Bash 后台任务产生 task-notification 与 bash sidecar；严格 IM parser 接收显示帧无协议错误，人工权限卡可见、批准前无上传、批准后图片一次送达。run_status/injection_consumed 两个入口均保留 subagent/workflow 卡且原 event 不被变更；现有手动 allow/deny/stop 和 candidate sidecar 聚合保护通过。

本次没有 canonical/delta 修改，最终两个 delta 与 current 对齐结论保留为 **aligned**；该提交中的独立 design-review 报告不是本轮实现通过的替代证据。本 verifier 仍只编辑 verification.md，无源码或测试修改。

## Corrected Delta Reconciliation

最终校对 snapshot / effective_through：`d4a59af212690dfe50af77a1b689e572ad32499c`。两份 delta 与最终 current 契约均重新核对。

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| kernel/runs 删除产品交付回调 | SDK/core 旧输出接口已删除，loop 不等待业务状态；canonical runs 已撤销旧 requirement | Round 1 SDK surface / 完整轮检查 | aligned |
| kernel/runs 完整模型轮事实 | `core/agent/loop.py:791`；canonical runs:500 明确 group/context revision/完成事实 | `test_model_round_end.py`；candidate observer 完整/异常轮 | aligned |
| kernel/runs 通用权限检查 | `sdk/kernel.py:2205`，无渠道/图片业务状态 | `test_sdk_tool_authorization.py`；前后台真实权限链 | aligned |
| kernel/runs 宿主操作与模型调用可区分 | SDK typed operation_description → HookContext → host_operation；保留原 policy/full action，说明不构成授权 | Round 3 真实 classifier payload/allow/deny/伪造来源/人工权限覆盖 | aligned |
| gateway 普通私有失败反馈、有限修正 | 前台及全部后台进入统一 owner，coordinator 以稳定 logical ID 共享两次 ledger；canonical routing-delivery:603,615 与 delta 相符 | 前台 feedback；后台成功/拒绝/缺图/预算耗尽；manual stop 与输入门禁 | aligned |
| gateway 显式错误与原身份恢复/部分完成 | dispatch 不追加普通反馈；owner commit/ledger 只恢复未确认部分；源码未被本次修复改变 | Round 1 recovery / offline snapshot 结论保留 | aligned |
| design 输入来源表示修正 | design:11 改成输入 part 顶层 `context_origin=system`，与 `delivery_feedback.py:27` 实际返回完全一致；未新增来源枚举/业务 kernel 状态 | `test_feedback_is_parsed_as_system_input` | aligned |

### Uncovered Observable Behavior

None。后台修复恢复了既有普通图片权限、完整交付和失败恢复契约，没有新增未被 delta 覆盖的用户功能；保留 feat-563 的 Runtime、图文及 relay/IM 行为要求。

Outcome: **aligned**。

Implementation verification passed with 0 critical issues and 0 warnings. PR 交付仍须由 orchestrator 汇总全量、独立产品验收及远端 CI 门禁；本报告不授予合并或部署授权。
