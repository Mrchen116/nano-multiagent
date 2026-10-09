# Independent code review — UX R1

2026-10-06。Review mode: `patch`。冻结范围：`5fde316f3c2d9e31984bfbbac41f5ce53af38b53..ba261e12f5c5bba36e8f513d7a3cce74d3f417cc`；此前完整产品基线 `107290abe`。现场 `codex/feat-578-ios-app`，仅原有 `output/` untracked；未修改产品源码、测试或配置，未操作 Simulator/phone，未派其他 agent。

使用 `change-code-review`，独立审查本轮原生产品 diff 及其直接调用链。审查了输入 UTF-16/IME candidate 接线、提及稳定 ID 和同名处理、头像来源、Markdown AST 和复制、待发媒体、群成员与名称草稿、管理表单/secret、任务祖先/选中候选、Work 状态与语义、Agent 详情刷新、提醒来源、viewport 已读。三份 UX 审视及 `ux-correction-r1.md` 用于界定修正范围，不把其中的建议自动作为已批准的新功能契约。

## Findings

```json
[
  {
    "file": "src/IM/ios/NanoIM/Features/Chat/ChatInfoView.swift",
    "line": 108,
    "summary": "[P2] 成员移除仍会覆盖未保存的聊天名称",
    "failure_scenario": "群创建者在聊天详情修改名称但不保存，随后确认移除另一成员。新增的成员添加路径会暂存并恢复名称，但同一页面 removeMember 在第114行成功后仍直接 await load()，load 在第94行无条件 title = value.title，导致未保存名称被服务器旧名替换。本轮保护覆盖偏好和添加成员，遗漏了同一正常成员管理路径；这是本轮修正未关闭的已有问题，并非新引入的删除API故障。",
    "review_mode": "patch",
    "status": "CONFIRMED"
  },
  {
    "file": "src/IM/ios/NanoIM/UI/CommonViews.swift",
    "line": 49,
    "summary": "[P2] 头像hash与要求继承的Web算法不一致",
    "failure_scenario": "同名 Personal Assistant 的头像在 Web 选 palette[4]，原生选 palette[0]。Web avatar.tsx 的 (hash << 5) - hash + charCodeAt(i) 只在移位时按32位处理，后续减加仍为Number；原生每步 UInt32 &*31 &+ 强制回绕。独立运算得到 Web hash2369571070/index4 与原生signed hash-1925396226/index0，My Assistant 与 Code Reviewer 也不同。这不破坏原生页内一致性，但违反 design.md:119 明确的 Web 配色算法继承。",
    "review_mode": "patch",
    "status": "CONFIRMED"
  }
]
```

最小修正建议：成员移除成功后的权威重读沿用本轮添加成员的普通名称草稿保留语义；不要改变删除权限/API。头像应复用 Web 实际移位/Number 算术语义，保留六色调色盘；不要为修正原生而改变未受本轮影响的 Web 行为。

## Direct evidence and limits

- 草稿：`ChatInfoView.swift:19,93-114` 的状态与调用链足以确认成功移除路径会重置名称；未执行成员删除或冒充产品验收。新增 `:108` 保留逻辑说明同一受影响流程已有最小实现方式。
- 配色：`src/IM/frontend/src/features/chat/components/avatar.tsx:20-23` 与 `CommonViews.swift:49-50` 逐步算术不等价。独立 Node 运算执行 Web 原式及 `Math.imul(...,31) ... | 0` 对照原生回绕，结果如下；不依赖主观截图判断。

| Name | Web hash / index | Native signed hash / index |
|---|---|---|
| Personal Assistant | 2369571070 / 4 | -1925396226 / 0 |
| My Assistant | -8482918038 / 0 | 107016554 / 2 |
| Code Reviewer | -5209870632 / 0 | -914903336 / 2 |

可复查运算：分别逐 UTF-16 unit 执行 `web = (web << 5) - web + unit` 与 `native = (Math.imul(native, 31) + unit) | 0`，最后 `Math.abs(hash) % 6`。它确认算法偏离，不声称完整头像 UI 或设备体验已验收。

复用 `/tmp/nano-feat578-ux-batch-tests3.log` 的实际结果：23 XCTest + 10 Swift Testing，0 failure，`TEST SUCCEEDED`；命令、xcresult 和能力边界见 `verification-ux-r1.md`。该套件保护本轮输入/内容及已有协议逻辑，未覆盖以上成员刷新与配色等价。冻结 diff 的 `git diff --check` 通过。未重复未变化的 Python/Web 全测。

结论限定本轮 patch。没有把源码或测试作为产品 UI 验收；没有重开无关全仓审查。Full S2/S6/S9/S10/S21/S27/S29/S30 的未完成分支、物理设备体验及自然到期续签仍开放；本报告不支持 Ready PR、merge、门槛豁免或部署。
