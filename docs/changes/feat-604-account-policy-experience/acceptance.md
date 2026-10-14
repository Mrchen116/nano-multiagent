# feat-604 — 产品验收报告

## Round 1

- mode: full；revalidation_mode: full；日期：2026-10-14。
- Validation snapshot: `9ebe12f8553a593f6179784b0276849fb14e5358 → a2f3a66688e3bc1e17920f2976506bf1d222bc16`。
- 树与运行：验收前 HEAD 精确匹配 validated_at，工作树干净；初始 IM PID 23516 的 cwd 已核实为本 worktree。使用交接的真实 dist（index.html 构建时间 11:33:10），直接由 19765 IM 提供。没有改源码、测试、设计或受控配置，没有继承实施者的通过结论。
- 入口：真实 `/settings/account`、`/settings/policies`，并实际进入 `/settings/nodes`、`/membership`、`/settings/company`、`/onboarding`。Cua 独立临时标签，桌面 1280×720/800、390×844、320×740。

## Verdict

**fail — S7 后台重新读取与草稿/保存交错的必要产品证据尚不足（inconclusive）。**

已实际观察的整体信息架构、视觉层级、角色分流、输入校验和真实停服恢复可交付；不能据这些成功推定后台刷新保护通过。产品实测确认缺陷 0 项；阻断的验收证据缺口 1 项。最高所需动作：补齐 S7 的可控后台刷新产品验收；caller 已通知另有独立代码审查发现，应由其统一裁决修复范围，本报告不把该静态发现记成产品复现。

## 用户旅程体验

账号页先呈现头像、显示名和 @用户名，资料编辑位于同一阅读区，ID/加入时间折叠到账号详情。空间资格和电脑摘要在独立区块，资料保存不会暗示改变成员资格。实际从账号进入电脑页，后者保持设备清单、版本、离线说明及管理动作，账号没有重复这些内容；与电脑页的浅背景、白色表面、青绿色动作和标题节奏一致。管理员只有一台电脑时不突出首次设置；零电脑成员能通过键盘进入助手设置。

策略页先让管理员判断实际容量，再进入明确标注“尚未接入执行”的预设。实际初始值 1.7 GiB / 10 GiB、剩余 8.3 GiB；展开后成员满额文字与管理员可上传状态可分别辨认。插入本次临时 reserved fixture 后，实际读到 10 GiB 占用、1.7 GiB 已用、8.3 GiB 上传中、0 B 剩余，以及上传暂停但文字聊天仍可用的提示。只读成员显示文字值，没有灰色输入表单、容量卡或保存条，因此权限与阅读任务一致。

手机保持单栏，320px 英文长文自然换行，底部导航、末尾字段和操作均可触达。390px 中文长表单真实停服时，失败提示与“放弃修改 / 保存策略”同时可见；320px 英文账号失败也在当前保存区域给出错误，用户无需返回页首。英文容量说明在 320px 与刷新按钮并排时换行较多，但读数、满额警告和主要操作清楚，没有形成阻断。实际 Tab/Enter 可聚焦并触发放弃修改及助手设置入口；输入有标签，实际状态 DOM 补充检查为 role=status。本轮没有声称完成 VoiceOver 朗读验证。

### 实际操作记录

1. 管理员显示名由 `Alex Chen · 设计测试` 改为 `陈晓 · 产品验收`，保存反馈出现，顶栏同步；刷新后保留。展开账号详情可见用户 ID 与加入时间。
2. 显示名纯空格立即出现有效值提示、保存禁用；放弃恢复原值。策略空白模型、留存 0 分别出现原位错误并禁用保存；放弃恢复。后续键盘放弃把留存 34 恢复到已保存的 32。
3. 策略留存改 32，SIGSTOP 本次 IM 后提交，字段/放弃/保存均禁用且显示保存中；对同一进程 TERM+CONT 使真实请求失败，32 保留，底部出现重试提示。恢复相同 DB/secret 服务，点击保存成功，未保存状态退出。
4. 停服时点击刷新用量，容量变为明确失败及重试，预设草稿仍可编辑；恢复后重试重新显示用量。另从 Me 的真实客户端导航进入账号/策略，分别观察资料读取错误与两个独立策略/容量重试入口；恢复后策略和容量 Retry 成功。
5. 320px 英文账号改 `陈晓 · 恢复验证`，真实停服后保存失败仍保留内容；恢复服务后重试成功。
6. 分别登录 member604/private604/pending604/suspended604：admin 为管理员；member 为有效成员、个人空间未启用；private 为个人可用且未加入；pending 为个人可用且待批准；suspended 为个人可用且团队停用。未加入与待批准入口实际进入对应 membership 页；私人继续使用返回账号页。管理员实际进入成员管理。未进行真实审批/停用操作。
7. 只读 member604 在 320px 英文查看分组文字预设。账号零电脑摘要提供管理电脑和助手设置；实际 Tab/Enter 进入 onboarding。

## Reference Artifacts Reviewed

独立观察真实产品后，打开 design 指向的 `prototype.html` 桌面账号/策略画面。以设计契约而非逐像素一致性裁决。

| Reference | Required contract | Actual product evidence | Viewport / state | Conclusion |
|---|---|---|---|---|
| prototype.html 账号；design 身份/空间/关联管理 | 主操作明确，身份/资格/设备职责分开 | 下列账号/停用截图；操作1、6、7；实际电脑页 | 桌面、390、320；五类身份、零/一电脑 | match |
| prototype.html 策略；design 容量与分组预设 | 实际占用与未生效预设可辨认，成员明细按需看 | 满额、只读及桌面截图；操作3、4；临时 reserved fixture | 桌面、390、320；正常/满额/未知/只读 | match |
| prototype.html 保存区域；design 编辑反馈与恢复 | 输入不丢、错误有位置、结果可感知，包含后台更新 | 账号失败截图；操作2–5 | 390中文/320英文真实停服失败与重试 | **inconclusive**：通常失败恢复 match；后台 GET 与草稿/保存交错未独立观测 |

### 代表性画面

- [320英文账号](M1-settings/evidence/review-r1/review-account-320-en.png)
- [390英文账号](M1-settings/evidence/review-r1/review-account-390-en.png)
- [320英文账号真实保存失败](M1-settings/evidence/review-r1/review-account-failure-320-en.png)
- [320英文满额与上传中](M1-settings/evidence/review-r1/review-capacity-full-320-en.png)
- [桌面英文策略](M1-settings/evidence/review-r1/review-policies-desktop-en.png)
- [320英文只读策略](M1-settings/evidence/review-r1/review-readonly-320-en.png)
- [320英文停用资格](M1-settings/evidence/review-r1/review-suspended-320-en.png)

## 问题清单

| # | Severity | Regression relation | 期望 / 实际 / 证据 | Recommended action | Action rationale |
|---|---|---|---|---|---|
| R1-G1 | blocking（验收证据） | unclear | S7要求后台重新加载不丢草稿；实际已观测两页真实失败/重试及策略挂起锁定，但没有独立证明后台 GET 返回发生于编辑中或 PATCH 成功之后。见操作3、5。 | 补齐可控后台重新读取的产品验证；若已按独立代码审查修复则在新 validated_at targeted 复验 S7 | 必验场景的部分成功不能代替剩余条件；不是已复现产品缺陷 |

无额外 Side Findings；不因主观间距偏好阻塞。

## 验收标准覆盖

| Scenario | 期望来源 | 实际验证与证据 | 结果 |
|---|---|---|---|
| S1 身份与资料编辑 | spec S1 / design 决策1、4 | 操作1；身份、详情、顶栏同步、刷新保留；账号截图 | pass |
| S2 电脑管理与空状态 | spec S2 / design 决策1 | 管理员一电脑摘要→真实电脑页；member零电脑→onboarding；操作7 | pass |
| S3 团队资格 | spec S3 / design 决策2 | 五身份实际登录；资格/个人空间区分；membership和管理员成员管理入口；操作6 | pass |
| S4 容量与预设分层 | spec S4 / design 决策3 | 正常、展开、上传中满额 fixture、三组预设及不执行声明；满额截图 | pass |
| S5 只读成员 | spec S5 / design 决策5 | member604真实登录、文字值/无保存/无容量；只读截图 | pass |
| S6 放弃与合法输入 | spec S6 / design 决策4 | 空白名称、空白模型、留存0原位错误/保存禁用；两页放弃；策略Tab/Enter放弃 | pass |
| S7 保存失败与后台刷新 | spec S7 / design 决策4 | 两页失败重试、策略提交锁定均通过；后台GET交错证据不足，R1-G1 | **inconclusive** |
| S8 加载与容量故障 | spec S8 / design 决策5 | 真实停服+客户端导航，资料/策略/容量均出现局部错误和Retry；容量失败不挡预设；恢复Retry成功 | pass |
| S9 桌面、手机与语言 | spec S9 / design 决策6 | 桌面中文两页及电脑参照、桌面英文策略，390中文策略/英文账号、320中文策略/英文两页；真实截图、键盘Tab/Enter、标签及status语义；320实际DOM宽度320辅助确认 | pass |

## 环境与清理

- 只操作 `/tmp/nano-feat604/im.sqlite3` 和本次隔离IM。reserved容量fixture `review604-reservation` 已删除恢复原容量数据；没有改原角色或设备。
- 测试管理员显示名现为 `陈晓 · 恢复验证`，策略留存32天（真实产品保存结果）；其他字段保留。
- 原IM23516因故障验证已停止，恢复服务当前PID **32125**，同cwd/DB/secret/19765；交回caller继续复验，不能清理生产进程。
- reviewer自己的临时标签已关闭，viewport override已reset。截图为本报告必要证据，不包含secret。
- 没有提交；按caller要求只交回报告和小型截图。

## 上层文档同步

- [x] `SPEC.md`：无需更新，未改变跨包架构。
- [x] `docs/specs/im/auth-tenancy.md`：**需要更新**，当前长期契约尚未含本unit界面职责/预设语义/恢复体验增量，由orchestrator最终校正并归并delta-spec。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。
