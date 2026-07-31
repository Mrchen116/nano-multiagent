# Retired Change Units

本目录保存曾经进入 spec/design、后来在完整交付前被架构演进或后续 change 取代的 unit。

Retired 与 completed history 不同：

- `docs/changes/archive/` 表示变更已经达到可交付状态并进入 current；
- `docs/changes/retired/` 表示该 unit 不应继续实施，内容只能用于理解历史方向；
- 仍有价值但暂未推进的工作继续留在活动区。

| Unit | 退役原因 | 当前入口 |
|---|---|---|
| [`feat-329-acp-interface-parity`](feat-329-acp-interface-parity/spec.md) | 依赖已删除的 kernel HTTP / ServerClient 架构 | [`SPEC.md`](../../../SPEC.md)、[`kernel specs`](../../specs/kernel/spec.md)、[`CLI specs`](../../specs/cli/spec.md) |
| [`feat-336-generic-channel-architecture`](feat-336-generic-channel-architecture/spec.md) | 被 feat-447 和后续 channel changes 取代 | [`Gateway external channels`](../../specs/gateway/external-channels.md) |

Retired unit 不得直接恢复；若仍有用户问题，应以当前代码和 specs 重新立项。
