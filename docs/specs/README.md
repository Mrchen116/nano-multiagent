# Evergreen Specifications

> 全仓文档权威地图见 [`../README.md`](../README.md)；写法与归并规则见
> [`../SPEC_GUIDE.md`](../SPEC_GUIDE.md)；跨包架构见 [`../../SPEC.md`](../../SPEC.md)。

本目录是长青行为契约层。每个包目录的 `spec.md` 是短入口索引;具体 Requirement/Scenario 写在同目录的 area 文档里。

| Package | Entry | Area Documents |
|---|---|---|
| kernel (agent) | [`kernel/spec.md`](kernel/spec.md) | [`sdk-boundary.md`](kernel/sdk-boundary.md), [`runs.md`](kernel/runs.md), [`model-runtime.md`](kernel/model-runtime.md), [`background-tasks.md`](kernel/background-tasks.md), [`context-persistence.md`](kernel/context-persistence.md), [`tools-hooks.md`](kernel/tools-hooks.md), [`skills.md`](kernel/skills.md), [`prompts.md`](kernel/prompts.md) |
| IM | [`im/spec.md`](im/spec.md) | [`auth-tenancy.md`](im/auth-tenancy.md), [`conversations-messages.md`](im/conversations-messages.md), [`web-chat-ux.md`](im/web-chat-ux.md), [`tool-timeline.md`](im/tool-timeline.md), [`response-metrics.md`](im/response-metrics.md), [`agents-nodes.md`](im/agents-nodes.md), [`gateway-relay.md`](im/gateway-relay.md) |
| gateway (personal_assistant) | [`gateway/spec.md`](gateway/spec.md) | [`routing-delivery.md`](gateway/routing-delivery.md), [`service-lifecycle.md`](gateway/service-lifecycle.md), [`agent-capabilities.md`](gateway/agent-capabilities.md), [`heartbeat-cron.md`](gateway/heartbeat-cron.md), [`relay-protocol.md`](gateway/relay-protocol.md), [`external-channels.md`](gateway/external-channels.md) |
| cli (coding_cli) | [`cli/spec.md`](cli/spec.md) | Not split yet; current size is still small enough to maintain as one file. |
