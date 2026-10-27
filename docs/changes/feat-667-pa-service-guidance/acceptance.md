# feat-667 — 产品验收报告

> Round 1；mode=full；reviewer：独立 product reviewer。Validation snapshot：`c4ebad992ae99e75ee9c3fca88b3eab43abd9ea5 → 7ddaceb942423436bc656fba6707b04f131c9cb1`。验收对象始终是后者；后续报告提交不改变 validated_at。

## Verdict

**fail（阶段报告，必验 #361 二级开发交付证据尚未完成）。** 已完成的常规旅程均 pass；不得据此宣布 M1 通过。后续仅针对 #361 真实 Ready PR、CI、二级执行与逐级回传补验，保留本轮其他结果。

Highest Required Action：补齐未完验收证据后 targeted re-review；当前不据缺证据推断实现错误。issues_count：1项必验缺口，0项已确认实现缺陷；gh_issues_filed：0；needs_re_review：true。

## 环境与方法

- 候选：`/tmp/pa667-review/.e2e-daily.json`，IM `http://127.0.0.1:60038`；用户 nano；PA `pa_dfd4729cb89f`，私聊 `c_41ff9ac601ba`。开工核实 HEAD 为 validated_at，工作区无本任务预存修改；构建及服务启动由 caller 集中准备，采用其受审版本构建证据，不重启生产。
- PA 模型 `codexOAuth:gpt-6-astra` / medium，P/E/Q 为 `codexOAuth:gpt-6.1-sol` / high，codex 审核；未调整模型。通过仓库 IMClient 所用真实登录、消息、Work、配置接口操作；没有直接驱动 DSH 内部入口。
- 真实 provider 请求捕获：`/tmp/pa667-review/provider-requests/*.json`。归并索引 `tool-ledger.json`、`schema-ledger.json`；实际 Work/消息快照 `status-*.json`、`work-*.json`。脚本仅驱动和保存证据，脚本退出或主执行 idle 本身不算交付。
- 同候选 runtime 的 main 文本对照：`/tmp/pa667-text-baseline/.e2e-daily.json`，IM `http://127.0.0.1:50445`，新鲜 PA `pa_e8de70f9d9f0`；配置增量见 `baseline-setup.json`。main Persona 经真实配置保存，main ongoing-work 通过同名 workspace Skill 覆盖，proactive-care 使用 denylist 禁用。实际 provider 第一请求及 Skill 回执核实已消费 main 文案。对照仅三场，不能推导提升率。
- 所有聊天与材料为隔离合成数据。没有外部消息授权，也未调用外部聊天。服务由 caller 统一清理；reviewer 未启动生产或额外服务。

## 用户旅程体验

通过真实 API 观察内容与交付，不评价未操作的 Web/iOS 布局；本片无客户端变更，design 明确允许同客户端 API。

1. 小事直接提供一人份西红柿鸡蛋盖饭的用量、分步时间和剩饭处理提示，不要求用户管理 Task 或团队。原输入 `81df2f239e35424f885676274ff6fd69`，实际答复 `61605d68f7954efeab28c0bfcac270d7`。从来信到完整答案约109秒，内容可用，但不能称低延迟提升。
2. A/B 实际并行：A 为6人90分钟入职分享，B 为2人三日晚餐、120元、忌花生。PA 读取 ongoing-work 后分别使用 `subagent(run_in_background:true)`，返回 continuable A `3363fe41-a7c9-43db-85c2-43d40918950b`、B `c483bbcc-9c59-401e-b01e-d29188b351db`。用户更正 A 为45分钟零经验新人并问炒蛋顺序；短问实际发送 `230e1762f4f7463a91a014d6eba1a745`，更正通过原A ID发送，回执 `25f526d9-8f09-40ea-acdf-0d270a2814ef`。B条件独立。
3. 用户只停A（`e98d0b1b3bff4469b180c4656a5df69e`）：实际 `interrupt_agent(A)` 后 `list_agents` 返回A inactive；B未被中断。B旧初稿发送遇新输入得到 `held_for_revalidation`，PA读取最新要求后才交付完整定稿 `7cdc157445d744d7b400176e6047bc7f`。菜单、用量、合计采购表完整，分项32＋40＋30＝102元，预算余18元，注明估价与库存假设。
4. 明确接续输入 `0d60a896b70247ed9acc5aa62db2b118` 后，PA发往同一A ID，回执 `bdbd4deb-324e-4e20-b766-e0ebf900a161`。原A实际接续、内部回传；主PA核验并清理内部时长试算文字，交付 `11996cc1b6054ee49343434e603b348b`：45分钟连续议程（4＋5＋8＋6＋8＋7＋5＋2）、逐字开场、事实卡、模板和练习。B未重复交付。晚到替换稿未触发重复通知。
5. 观察准备分两步：与A重叠的“拆分A观察样例”被合理并入原A，没有另建事项。为排除已有交办混淆，另建“独立私人准备样例” `c_0dva8i1u`：主人向小周承诺旧书交换活动开场说明，原话含周六14–16点、20人、最多5本、自愿免费及剩书带回。PA读取原话及当前全部可见历史，使用 proactive-care，在私人聊天交付具体四环节草稿 `581ec5fed5aa4988ade079bd2c9c3894`，附原消息链接，说明现场操作为建议，没有编造一换一或捐书规则。原观察群无PA发言，未把承诺当外发授权。
6. 追加“已写好并发给小周、已处理”消息 `3bfb567ae9124e06a2052ecb732673eb`，主人请求仅有新价值才通知 `fc96de6309a241018c3ca537f7bccf78`。PA实际读取更新，修改既有记录后结束；没有向用户发送确认或催办。

7. 同一状态再次请求（`be18bcf547014b1a851872fd2ad583f8`）仍完成读取并保持用户侧静默。覆盖不足请求 `400fab6217ee4d7184cb33810d09ee6e` 指定不可访问群；PA查询无匹配，答复 `68bf7f4f2a5743de8442ee969e76c279` 明确“不能确认所有聊天”“无匹配不代表不存在”“未授权群未知”，且区分主人自报已处理、A稿已向主人交付、是否向小林交付未知。未虚构全覆盖。
8. 三场对照全部保存后，在同候选runtime的基线PA验证个人选择：将 custom_prompt 改为“PA667个人选择：回答尽量简洁，保留这段自定义文字。”并denylist禁用proactive-care，重试 `POST /im/v1/personal-agent` 返回同一binding，配置仍保留。实际请求 `1793091409207171000.json` 的system有自定义、无默认Persona、无proactive-care发现项。之后清空（API规范化保存为null）、禁用两份Skill，重试仍保持；`1793091430140627000.json`及后续system无自定义、无main/候选默认Persona、无两Skill发现项，正常短问仍sent。证据：基线目录 `config-custom.json`、`config-empty.json`、`config-custom-*.json`、`config-empty-*.json` 及provider原件。没有把历史已加载正文误判为重新发现或配置回填；新PA默认指导另由候选初始配置和实际请求确认。

## Reference Artifacts Reviewed

N/A。无前端原型或 must-match 视觉参考；本轮不声称 Web/iOS 视觉体验已验。

## 验收标准覆盖

| Requirement / Scenario | 期望来源 | 实际证据 | 结果 |
|---|---|---|---|
| 按工作规模 / 小事直接完成 | spec.md 同名Scenario | short-1793090415.json；消息61605d…及sent回执；无需用户管理团队 | pass |
| 按工作规模 / 长事项持续交付并说明能力边界 | spec.md 同名Scenario | A/B完整菜单/45分钟稿已交付；用户指定#361真实开发仍待验 | inconclusive |
| 多事项 / 更正与短问题 | spec.md 同名Scenario | 两个后台continuable真实ID；更正原A的25f526d…回执；短问230e176…；最终45分钟稿 | pass |
| 多事项 / 单项停止 | spec.md 同名Scenario | interrupt原A、inactive核对，B菜单7cdc157…真实sent；没有把晚稿当接续授权 | pass |
| 获准观察 / 承诺后的实际准备 | spec.md 同名Scenario | 独立旧书交换原话05290fa…、inbox/conversations完整回执、私人草稿581ec5…；原群无PA发送 | pass |
| 获准观察 / 已处理、无新价值和覆盖不足 | spec.md 同名Scenario | 已处理与无变化两轮静默；覆盖答复68bf7…明确范围与未知；observed-chat-audit.json确认原群无PA发言 | pass |
| 个人选择 / 自定义、清空和禁用保持 | spec.md 同名Scenario | 基线同runtime的config-custom/empty.json、重试原binding、实际provider system验证；新PA候选config-initial.json | pass |
| 主Agent协调 / 任务执行者可再委派一层 | spec.md 同名Scenario及design #361要求 | #361由caller在独立栈驱动，等待实际PR/CI及逐级回传后独立验收 | inconclusive |
| 主Agent协调 / 子Agent只进行内部通信 | spec.md 同名Scenario | 候选主PA39工具含产品工具，A/B一级36工具不含inbox/conversations/send_user_message；send_message仅agent_id/message。原A恢复实际请求仍同一边界；二级真实交付待#361 | inconclusive |
| 主Agent协调 / 主人要求接续已停止事项 | spec.md 同名Scenario | 停止→inactive→主人明确恢复→同一A接续→完整定稿11996cc…sent | pass |

## 有限对照

相同 runtime、模型及实际用户输入；新鲜独立workspace。短事两者均给出可用食谱；main约37秒、候选约109秒，只是单次样本，不归因为文案。长事两者均实际创建两个可续执行者，并把更正传给原A和回答短问；main拒绝旧90分钟稿并要求原A修正，最终45分钟稿 `982b1341f4494ba9b1ed5a399d404cec` 已实际交付。独立观察承诺：main读到原话后选择不接手、不通知，没有私人草稿；候选核对后交付具体草稿。此差异仅支持本次样例，不能证明普遍胜率。

## 问题与未完成项

| ID | Severity | Regression Relation | 期望 / 实际 / 证据 | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| A1 | major（缺验收证据，阻止通过） | unclear | design明确用#361完整开发、独立Ready PR与CI证明二级实际交付。caller仍在独立栈推进，尚未交给reviewer完整结果，故相关两Scenario及长事完整范围保留inconclusive。 | 完成#361后targeted re-review；暂不要求fix-implementation | 算术探针、二级创建回执或静态测试不能替代用户指定完整交付；尚未观察失败，不能猜测根因。 |

**Side observation（不裁为本片实现缺陷）**：使用现有IMClient的prompt-preview辅助调用，在基线配置提交后与稍后各得到503，响应 `{"detail":"target_node_id is not connected"}`。请求是 `POST /im/v1/agents/pa_e8de70f9d9f0/prompt-preview`，body含 `custom_prompt`、保存的features/tool_ids、`skill_ids:[]`、`scenario:"direct"`，未提供target_node_id（沿用helper）。该节点同时间仍可响应消息与配置，最终provider请求已证明配置应用成功。原响应保存 `/tmp/pa667-text-baseline/prompt-preview-observation.json`；本辅助入口请求是否需要额外字段及其归属交caller核实，未读取实现根因，也不把一次辅助503扩成配置主旅程失败。

实际接口健康和配置检查，不等于跨版本升级/节点重启穷举；本片保真以真实现有实例修改、清空、禁用、重试创建和下一轮最终provider组装为证据，既有升级/恢复工程矩阵由worker验证。未对生产升级作任何承诺。

## 上层文档同步

- [x] `SPEC.md`：无需新增架构边界，本片复用既有DSH公开入口。
- [x] `docs/specs/gateway/`：需要在最终通过后归并本unit的 personal-agent、global-agent、agent-capabilities delta；当前未提前覆盖current。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。
