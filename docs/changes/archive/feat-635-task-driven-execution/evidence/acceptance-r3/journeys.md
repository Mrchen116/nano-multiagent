# Round 3 最终迁移版本 targeted 验收

`validated_at=30cd2e0a1272ec0a157337ebe644ad11e642809c`，包含最新origin/main `0904bc49c`。caller将IM/Node/Web及430原生包切到此版本，保留同一隔离DB与身份；reviewer核对HEAD。R1/R2证据不冒充本版本重新执行。

## J18 模型失败后仅恢复配置

- 新任务tg_e8cd38a9，专用acceptance-default635已通过普通配置选择feat635-unavailable:model。真实失败消息30d4eeb01b044a089ee60f0710c48dc4：模型不支持reasoning effort high；Task仍rev1doing，未伪完成或等待用户。此轮是运行配置错误，与R2的真实proxy403分别记录。
- 07:35:00.812Z仅通过产品配置改回deepseek:deepseek-v4-flash，mirror profile5确认。没有重启、修改Task或发送开始消息。
- 后续自动rev2done，result三条雨天公园替代建议，真实回复5de39e2bd02c48bc92ca8bce2540b7f5。R2 I4关闭。原旧失败任务因重启完成不作为本次配置恢复证据。

## J19 旧提醒核对待确认任务

- tg_a37ca289要求先给不采购建议，创建90秒原生提醒，提交in_review，并保留提醒用于核对最新状态。真实用户消息86a0e5410b0e4f91bc610ff0c4ea2857明确用途与边界。
- schedule_create成功：schedule-1d6942e1-f50f-4d74-baba-c2191f25e722，07:35:26.282Z到期。Task提交遇正常工具审批69909b03-578c-48a4-890a-e73b260c66b7；reviewer在最终版原生Allow once→Submit decision，rev2in_review。
- 旧提醒在审批等待期间已到期；后续原生轮次处理时Task已in_review。真实消息12d80790544e4b3db5bed8db7e837417及工具回读确认rev2in_review，未重新开工/写Task；其他closed/paused保留。此证据覆盖“旧提醒已排队，处理时状态已终止”，不把90秒当精确执行回执。

## J20 最新原生布局与真人控制

- 430实看最新compact cards，根44项按真实七状态计数，纵向仍按todo+paused、doing+waiting等五类组织。新main会省略空组正文，顶部零计数仍在；它没有把waiting变成独立第六组。
- 真实坐标点击顶部Waiting汇总，定位In progress组。waiting卡保留原因与Saved schedule time；打开详情按实际核验显示Next check、Idle，与卡片保存时间区分。截图ios-waiting-navigation430。
- tg_e340c23b详情Pause后rev4paused清wait；Resume后rev5doing并Running；模型自行rev6waiting，真实Schedule-f4165f0b-bbe8-4d0f-9b46-d029ffe8279d，08:09:10.714Z复核，无旧暂停理由审批。截图ios-resumed-running430。控制通过原生可访问性按钮操作，R2可见坐标/用户手动滚动证据保留。
- 负责人选择e2e，11项本人跨层任务，搜索深层后显示祖先路径。Open parent scope进入n2并打开n3详情，Done关闭回n2直属n3in_review与Peer n4done；Back仍保留e2e与搜索词。截图ios-assignee-compact430、ios-deep-compact430。根/负责人/直属入口、独立详情与返回位置没有丢失。
- Web布局没有迁移改动，沿用R1/R2 1280/390真实对照；本轮未重开headed浏览器。

## J21 真人直接输入与Goal边界

- Peer开启Goal配置profile6确认；真实人类消息cee9e0e7599b41f6b34a8c08ac855855只授权创建一个验证Goal并立即完成，不改Task/Schedule。
- 真实回复61f5b3580ca24b69b927f3a17a2e6bcc附工具：get_goal→null；create_goal→goal-1417869f-d1e9-482c-97d1-5ea25e01fcb3 active rev1；update_goal complete→rev2/disarmed；get_goal再读同一complete。没有把自动任务输入冒充真人。Task仍in_review，未创建Schedule。
- 普通配置恢复关闭profile7，07:39:35.230Z确认。后续provider 15:42:57_106请求顶层tools无Goal工具，reviewer独立提取工具名核实；原始请求不进repo。Goal默认关与独立Task语义保留。

## J22 自动第二轮审批

- 新Task tg_426ab51d要求第一轮仅notes记录phase1并普通最终回复结束，第二自动轮再写饮水建议并done，遵守正常审批。没有用户继续消息。
- 第一轮真实消息dadb1f6c01cb4101aedeeb01fe0360f4，07:42:49.368Z起，notes写入后普通final，Task保持rev1doing。
- 第二自动轮消息5788db0d7e4940ee97c2ef009bf50fdd，07:43:13.777Z起，先读notes，再调用task_graph apply；审批bd90f80a-13dd-4054-89b9-3160abca6f32正常pending，没有绕过人类授权。
- reviewer原生进入活动筹备群，Latest messages看见前轮final与第二轮审批卡，Allow once→Submit decision。随后审批resolved、第二轮completed，Task rev2done并有两条饮水建议result，系统完成通知ecd633903bb241d2b6c0f2a30b497f3a。全程没有继续消息；正常审批不是补发执行指令。
- 本测试结果正文存在模型生成的“自嗲”笔误，最终聊天已写“自带”；不影响任务状态/审批机制，未据此追加实现修复。
