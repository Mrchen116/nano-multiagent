---
status: research-snapshot
recorded-at: 2026-08-10
nano-baseline: 6a5860b488bd87f88e9c12d452d3657b39dfdd65
upstream: openclaw
upstream-baseline: be94853de0d0a282cfbe63316084a73613819084
installed-openclaw: 2026.4.2
installed-baseline: d74a12264aa5fb0598605e8f04e1864b7239ddd5
current-owner: pending-adoption
---

# OpenClaw 消息时间与上下文前缀 — 2026-08-10

本研究包记录 OpenClaw 如何让模型在长会话里自然感知每条消息的时间，以及它如何把普通消息 envelope、回复链、群聊、转发、排队消息和跨会话来源按需放进上下文。重点是时间的更新频率、模型如何理解时间语义，以及这种机制如何避免无谓破坏 prompt cache。

这是带源码基线的研究快照，不代表 nano-multiagent 已经实现这些行为，也不覆盖任何 current spec。若决定采用，应另建 change unit，把最终契约归并到对应 current spec。

| 材料 | 作用 |
|---|---|
| [`research.md`](research.md) | 基线、源码证据、机制分层、未知项与候选采用契约 |
| [`OpenClaw 消息时间与上下文前缀机制.md`](OpenClaw%20消息时间与上下文前缀机制.md) | 面向实现者的结论文章：时间何时更新、有哪些 prefix、何谓“按需出现” |
