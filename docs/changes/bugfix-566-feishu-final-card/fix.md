# bugfix-566: 恢复飞书最终回复运行信息卡片

## Relations

- Related: feat-523
- Related: refactor-564

## 原始报告

> 之前飞书的最后一条消息是以卡片形式，现在为啥变成普通消息了？哪个需求改错了

> 修复。而且门禁没拦住真的很奇怪，这么显然容易拦截的。写了这么多测试都没找到问题

附件：`codex-clipboard-c7f76394-9592-4380-bc43-167923a7e2e2.png`。截图中同一轮的中间回复与最后回复都显示为普通消息；最后回复没有原生卡片及模型/context 运行信息。

## 现象 / 复现

生产 Mac mini 与本机 Gateway 均运行 `f106d3503`，两边 `display.runtime_footer.enabled` 均为 `true`。用户从飞书触发一次包含中间回复和最终回复的正常 Agent 运行时，中间回复按契约显示为普通消息，但最终回复也错误地走普通消息发送，不再显示正文与 `model · ctx N%` 运行信息同卡的原生卡片。

当前 canonical contract 仍要求：启用运行信息页脚且运行事实可用时，普通飞书最终回复以一张原生卡片承载正文和运行信息；中间回复、工具进度、审批与控制消息保持原投递形态。因而该现象是实现回归，不是需求变更或配置关闭。

可重复的最小证据：当前配置能够把最终正文投影为带非空 `runtime_footer` 的 `ExternalFinalProjection`；同一正文经过 `refactor-564` 新增的完整候选交付路径后，送到飞书适配器的 metadata 只有运行与幂等字段，适配器无法识别其为带运行信息的最终回复，因而选择普通消息发送。

### Requirement: 恢复已启用的飞书最终回复卡片

#### Scenario: 同一运行包含中间回复和最终回复

- **GIVEN** 飞书运行信息页脚已启用，且本轮有可呈现的模型或 context 运行事实
- **WHEN** Agent 在同一运行中先产生中间可见回复，再产生普通最终回复
- **THEN** 中间回复继续以普通消息显示
- **AND** 最终回复以一张原生飞书卡片显示正文与可取得的运行信息
- **AND** 最终正文不因候选交付、图片准备、影子同步或幂等恢复路径而重复发送

#### Scenario: 页脚未启用或运行事实均缺失

- **GIVEN** 飞书运行信息页脚未启用，或本轮模型与 context 运行事实均不可取得
- **WHEN** Agent 发送普通最终回复
- **THEN** 飞书保持普通消息投递，不增加空白卡片或未知占位符

## 根因

`feat-523` 原本在终态事件处构造一次 run-owned final projection，并把 `reply_phase=final` 与非空 `runtime_footer` 作为飞书卡片的展示提示。飞书适配器只有同时收到这两个事实才发送 interactive card，这是防止中间回复误用卡片的既有边界。

`refactor-564` 的提交 `6ee83e2e3` 将普通正文改为在 `model_round_end` 聚合成 `ReplyCandidate`，再统一进入 `MessageDelivery`。这个新入口在终态运行事实到达前即准备并发布候选，且构造外部 `ReplyContext` 时只传播 `run_id`、`output_key` 与 `reply_dedupe_key`，没有把候选的最终展示语义与 runtime footer 投影带入新的唯一交付入口。随后终态事件即使构造出 final projection，候选已经由 delivery owner 发布，旧 observer/fallback 路径也不会再次发送。因此最终正文稳定退化为普通消息。

门禁遗漏同样属于本次根因：重构文档声明“用户侧不变”，但受审增量、milestone 退出标准和真实飞书验收集中在图片、权限、恢复、后台返回卡与完成状态，没有把已有 `feat-523` 的“开启后最终回复为运行信息卡片”列为必须保留的回归场景。永久测试分别验证了 runtime footer formatter、飞书适配器在收到正确 metadata 时会发卡片，以及新的 candidate delivery 能送达；没有一条测试从新候选入口观察最终飞书 outbound 的消息类型和 footer。组件测试全部通过，恰好掩盖了跨边界 metadata 丢失。

修复必须保住以下不变量：Gateway 仍是 runtime footer policy owner；飞书适配器只负责按已批准的最终展示提示渲染；中间回复不获得 footer；最终正文、图片、影子消息和恢复继续使用同一逻辑输出身份，不绕开 `MessageDelivery` 或恢复已删除的双交付路径。

## 修复

`CandidateObserver` 不再在无法判断终态的 `model_round_end` 直接把最后一个无工具正文候选发布出去，而是暂存它：同轮已进入工具调用的候选是确定的中间态，仍在该 round 完成时立即发布；出现下一组 assistant 正文或同一 run 消费新注入时，上一无工具候选也按中间回复发布；成功 `turn_end` 到达时，最后候选才结合该 run 的模型、usage 和 context window 构造 `ExternalFinalProjection`。完整的产品通知仍按原路径立即投递，失败或取消的 run 丢弃未发布候选。

`MessageDelivery` 继续是唯一正文交付 owner。它在准备外部消息时读取上述 run-owned final projection，把 `reply_phase=final` 与非空 `runtime_footer` 写入同一个 `ReplyContext`，并在图片占位符准备后的正文上保留非飞书渠道所需的 footer 后缀。飞书适配器的职责不变：只有已批准的最终态且 footer 非空时才渲染原生卡片；中间候选没有 final projection，因此仍走普通消息。

本次不修改 canonical spec：`docs/specs/gateway/external-channels.md` 已准确要求启用后的飞书最终回复卡片及中间回复普通消息，修复只是让 `refactor-564` 后的新唯一交付路径重新满足该契约。

## 验证

测试策略：扩展既有 `tests/integration/test_pa_candidate_delivery.py`，从真实 compose 入口穿过 kernel、candidate observer、`MessageDelivery`、outbound router 和 `FeishuAdapter`，直接断言 provider 最终只收到一条、正文正确且 card 非空的消息。该 integration seam 是本次“跨边界 metadata 丢失”最低可观察层；既有 formatter 与 adapter 单元测试继续保留，不再重复其纯逻辑断言。`tests/unit/personal_assistant/test_candidate_observer.py` 只补充该 owner 自身的稳定阶段边界：前一候选按中间态发布，只有 terminal candidate 获得 final projection。

- Red：`PYTHONPATH=src .venv/bin/pytest -q tests/integration/test_pa_candidate_delivery.py::test_composed_feishu_final_candidate_uses_runtime_card`，修复前稳定失败于 `client.sent[0]["card"] is not None`，实际为 `None`。
- Green：同一真实组合链路修复后通过，且断言只发送一条 `Final answer`、card 非空并包含配置模型标签。
- 相邻回归：candidate delivery、runtime footer、Feishu adapter 共 `31 passed`；external visible delivery、relay lifecycle、runtime delivery stream、terminal coordinator 共 `70 passed`。
- 全量门禁首次发现带工具中间图片候选被过度延迟，`test_new_group_input_during_upload_rejects_old_draft[True]` 因上传无法开始而超时；修正为“已进入工具调用的候选立即按中间态发布”后，该输入竞争场景重新通过。
- 首轮独立 code review 还指出 cron final-only observer 允许以 `run_status=completed` 作为成功终态；当上游没有重放 `turn_end` 时，暂存候选不能被清理掉。修复把该事件作为缺少 usage/context facts 时的终态兜底，并增加永久单元回归。
- 格式与静态检查、全量本地 CI、独立 code review 和远端 CI 在收尾阶段追加。
