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

待 M1-fix 实施后回填。

## 验证

待 M1-fix 实施后回填。
