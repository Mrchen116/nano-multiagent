[
  {
    "file": "packages/dsh-integration/src/policy/approval.ts",
    "line": 175,
    "summary": "[P2] 持久化判定期间取消后，应补记真正的取消终态",
    "failure_scenario": "当模型已返回 allow，facade 在 L165 将 recovery 封为 terminalReason=allow/finalRoute=allow/complete=true，并在 L166–174 等待 audit update；若父执行在这次异步持久化期间取消，L175 最终返回 {kind:'cancel'}，却没有追加 review_cancelled 或修正终态。session.observe 因此只留下完整 allow trace，无法从该动作的恢复记录知道实际最后走了 cancel。独立运行冻结版本编译产物的 facade 探针，在 storageDomain.update 内对真实父 AbortController 调用 abort 后返回更新结果，直接得到返回 cancel、唯一审计 classifier_allow/allow、recovery.finalRoute=allow、terminalReason=allow、complete=true，且没有 cancelled 行。工具体并未执行，故本 finding 是确定的终态审计错误，不是取消绕过或重复执行。请原实施者保留模型 verdict 事实，同时持久化同 reviewId 的最终取消事实，并保护取消跨越 audit await 的边界；技术不可用/fallback 持久化后的相同取消窗口也应核对。契约：design.md L201–203 的取消审计与真实终态、spec.md L150–155 的最终结果/路由可追踪。普通直接证据已足够，无需追加独立候选核验；第二个加强为外部 deferred storage gate 的探针被本会话工具权限门禁拒绝，未执行，不作为证据。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
