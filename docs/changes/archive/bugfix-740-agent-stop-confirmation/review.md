# bugfix-740 独立审查

- executed_base 与 effective_base 均为 `520d9f5fbfed547cf9c012c4315faabb2ca92635`。
- 初审 validated_at 为 `c365579520907a3969eea2feeffde018c190612c`。定向复审 validated_at 为 `15fced6972031f607a1a7211e2d5fe5b42b68331`。
- effective_through 为 `15fced6972031f607a1a7211e2d5fe5b42b68331` 的实现、测试和契约。后续仅变更归档和审查记录。

独立审查者 `stop_confirmation_review` 验证了旧格式凭证、新执行实例、证据缺失、超时和删除前校验。Gateway 契约与最终实现一致，无遗留 findings。

初审发现旧版可能以管理实例 B 保存停止凭证，同时以原执行实例 A 上报。最初修复让管理实例 C 即使成功清理也无法确认。定向复审在同次开机与机器重启后重放旧版生成的凭证，均确认 C 成功后恢复停用并以 A 保存凭证。C 超时或没有原停止证据时仍然不确认。下一次重连复用已归一的凭证。

受影响的 Node、IM 和原生 DSH 回归通过。未在生产执行清理。
