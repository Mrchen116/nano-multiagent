# Independent code review — UX R2 closure

2026-10-06。Review mode: `closure`。冻结候选 `2992200b994e0c24b72a481b5af031c8c6aed942`，fix delta `ba261e12f5c5bba36e8f513d7a3cce74d3f417cc..2992200b994e0c24b72a481b5af031c8c6aed942`；finding origin `ba261e12f`。只核对 [R1](code-review-ux-r1.md) 两条确认问题及修正直接影响，未重审仍有效的其他本轮范围、未重跑全测、未修改源码或操作 UI。R1报告保留其冻结版本历史事实。

使用 `change-code-review`。现场 HEAD 与候选一致。保留其他角色正在写的 `acceptance-ux-r2.md` 与原有 `output/` untracked，仅新增指定报告。

## Findings

```json
[]
```

## Focus finding closure

| R1 finding | 状态 | 直接证据 |
|---|---|---|
| 成员移除成功刷新覆盖未保存名称 | **closed（静态）** | `ChatInfoView.swift:93-95` 在读取前保留dirtyTitle草稿，读取成功使用保留值；`:109,115` 添加与移除均走同一个load。偏好PATCH仍仅在显式title提交时更新名称。重复的添加成员临时保留逻辑已移除，没有改变权限/API |
| Native头像hash与Web实际算法不一致 | **closed** | `CommonViews.swift:51-57` 对UTF-16逐unit，只在左移转Int32，减法/加法保留Int64；六色表/名称来源不变。七个Web实算golden与实际Swift回归结果一致 |

独立Node再次执行Web原表达式，七项结果为：空字符串0、e2e-peer5、Personal Assistant4、My Assistant0、Code Reviewer0、中文助理3、🧑‍💻 Agent1。与 `AvatarTests.swift:7-10` expected完全一致。`/tmp/nano-feat578-ux-final-tests4.log:338-341` 实际执行该测试且通过，关闭R1正常名称/宽hash偏离，不依赖截图主观判断。

## Validation and limits

复用最新原生测试证据：2026-10-06 20:56，24 XCTest +10 Swift Testing、0failure、`TEST SUCCEEDED`，日志 `/tmp/nano-feat578-ux-final-tests4.log`，xcresult `/tmp/nano-ios-build/Logs/Test/Test-NanoIM-2026.10.06_20-55-23-+0800.xcresult`；实际目的设备是独立430 Simulator `AA8F9712-DDCB-405F-9DD9-6D14203B44CB`。本review未运行或改变当前390产品包。冻结fix delta的 `git diff --check`通过。

群名称closure依据明确状态/调用链，不声称已经走过新包真实“改名→移除成员”产品路径。该路径仍交product reviewer。日志有Avatar测试调用的非致命actor-isolation编译warning，但当前Swift5语言模式实际测试通过；没有将未来语言升级的假想风险升级为存活finding。

结论只关闭这两条静态finding；未发现修正delta的新可证实问题。新包UI/物理IME、原Full S2/S6/S9/S10/S21/S27/S29/S30未完成分支、同网刷新及自然到期恢复继续开放。不构成产品接受、Full完成、Ready PR、merge或waive。
