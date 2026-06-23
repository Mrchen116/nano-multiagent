# bugfix-426-M1 — Progress

## [对齐] design 多模态措辞 vs 内核 text-only 现实（开工前 orchestrator 确认）

- Context: design 决策2/3 写「注入携带完整多模态 parts、content 为 list 时不强转 text」，
  暗示 LLM 边界走多模态 content。
- 现实核查（grep 证据）:
  - `agent/core/agent/state.py:87-103` `render_user_text()` 把 parts 渲染成纯文本，image→`[image:placeholder]`，返回 str。runtime 用 `user_text`(str) 喂 loop（loop.py:202-207 `build_chat_messages(user_text=...)`）。
  - 图片仅作为 `input` hook 的 `images` 字段传出（runtime.py:387），但全仓**无任何 hook 消费它把图片塞回 LLM 消息**（grep `images`/`image_url` 命中均为工具/read 无关项）。即正常 submit 路径今天图片也到不了模型。
  - anthropic mapper（providers/anthropic/mapper.py:147-151）对 user 角色消息 `content:[{"type":"text","text": message.content}]`——若 content 传 list 会把 list 塞进 text 字段，**直接坏**。openai_compat 透传 list 但 gateway 建的 part 形状 `{"type":"image","image_url":<url>}` 与 vision 格式 `{"type":"image_url","image_url":{"url":...}}` 不匹配。
- Decision（orchestrator 确认）: 注入复用 submit 同款 `parse_input_parts + render_user_text`，content 为 str。
  - 决策2 真实意图 = 「注入与 submit 走完全相同的 parts→message 转换、带不带附件无差别」；
    用 render_user_text 正好让该字面成立（两条路径都是 placeholder+全文），不引入与既有不一致的多模态平行物、不碰坏 mapper。
  - 决策3「content 为 list 时不强转 text」在此前提下 moot（注入 content 本就是 str），registry stranded 续跑 `{"type":"text","text":msg.content}` 对 str 已正确。
  - 决策3 仍要做：stranded 续跑 origin 跟随注入来源（用户 steer→USER）+ inject_pending_message/pending 承载 origin。
  - 真多模态打通是预存内核限制（与本 unit 无关、submit 也没通），不在本 unit 范围。
- delta-spec 多模态措辞由 orchestrator 收尾归并按现实校正。

## R1 — <pending>

## R2 — <pending>

## R3 — <pending>

## R4 — <pending>
