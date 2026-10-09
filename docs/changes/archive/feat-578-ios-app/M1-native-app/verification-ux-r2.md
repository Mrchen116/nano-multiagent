# Verification Report: feat-578 UX R2 closure

> Validation snapshot: `ba261e12f5c5bba36e8f513d7a3cce74d3f417cc → 2992200b994e0c24b72a481b5af031c8c6aed942`

2026-10-06。使用 `change-verifier`，`verification_mode: targeted-closure`。先前报告 [verification-ux-r1.md](verification-ux-r1.md)，focus issues V1/V2。只核对两条修正及关联契约/回归，不重验整个unit或旧有效范围。`requires_full_verification: false`。

## Summary

| 维度 | 本轮结果 |
|---|---|
| Completeness | 2/2指定静态问题closed；成员移除新包产品路径仍待reviewer |
| Correctness | 0CRITICAL /0WARNING /0SUGGESTION（仅targeted-closure范围） |
| Coherence | 普通名称草稿保护和Web实际配色算法对齐，无共享后端/权限/协议影响 |
| Verdict | **pass（有限静态closure）**；不表示产品接受或Full完成 |

## Completeness / correctness

| Focus / 契约 | 实现与证据 | 结论 |
|---|---|---|
| V1：Feature stores保留草稿，界面不因reload丢存活草稿（design:77,90；本轮群改名保护） | `ChatInfoView.swift:93-95`统一保存已有dirtyTitle，成功后保留普通名称；addMember`:109`和removeMember`:115`共用此load，原偏好PATCH`:100`不覆盖未提交名称 | **closed（静态）**。不把load接线证明写成真实成员删除验收；新候选“编辑未保存名称→确认移除成员→名称仍保留”继续由product reviewer观察 |
| V2：Web六色hash与同名身份继承（design:119；S7；delta聊天输入和身份延续Web体验） | `CommonViews.swift:51-57`按Web仅移位Int32、减/加保留宽值；`AvatarTests.swift:6-11`使用七个实算JS结果，涵盖R1三项错误名、普通/中文/UTF-16emoji | **closed**。独立JS重新得0/5/4/0/0/3/1，与实际Swift测试一致；palette/peer identity/call sites未改，不扩大复审 |

## Evidence

- 候选冻结：现场HEAD `2992200b994e0c24b72a481b5af031c8c6aed942`；fix delta只有上述源码修正、新Avatar行为测试及对应记录。原 `code-review-ux-r1.md`/`verification-ux-r1.md`已由caller纳入候选，保留其历史mismatch，未改写为原先已通过。
- 原生回归：日志 `/tmp/nano-feat578-ux-final-tests4.log`直接记录 `xcodebuild -project src/IM/ios/NanoIM.xcodeproj -scheme NanoIM -destination 'platform=iOS Simulator,id=AA8F9712-DDCB-405F-9DD9-6D14203B44CB' -derivedDataPath /tmp/nano-ios-build -disableAutomaticPackageResolution -onlyUsePackageVersionsFromResolvedFile test`，20:56实际24 XCTest、10 Swift Testing、0failure及 `TEST SUCCEEDED`；新增Avatar测试在日志338-341通过。xcresult `/tmp/nano-ios-build/Logs/Test/Test-NanoIM-2026.10.06_20-55-23-+0800.xcresult`。候选归属来自caller冻结交接；日志本身无commit字段。未重跑全测或操作Simulator。
- 独立算术复核：逐UTF-16执行当前Web表达式 `h = (h << 5) - h + charCodeAt(i)`、`Math.abs(h)%6`，七项与golden全部相同；该行为测试保护明确Web视觉身份契约，而非简单getter或私有调用次数。
- 冻结fix delta及当前working diff的 `git diff --check`通过。报告完成后独立执行 `/Users/czj/Repos/nano-multiagent/.venv/bin/python scripts/docs_check.py`，299 maintained Markdown/75 required routes通过；不从docs结果推导产品完整性。

## Coherence / affected reference

两条修正都留在原生客户端内：名称保存只收敛已有load与普通状态，未持久化secret/新增普通草稿框架；配色沿用现有Web事实，未更改Web实现或palette。R1所有未失效映射继续保留其原范围。P1–P6、M1-R1/W2/W3的真实产品/viewport/键盘/设备退出证据不由静态closure替代。

## Issues / closure result

V1 closed；V2 closed。没有新的确认CRITICAL或WARNING，不要求full重验。R1的`implementation-mismatch`在本候选指定两项实现层已关闭；其旧报告仍是原冻结版本事实。

**待产品证据**：product R2当前使用的是`ba261e12f`包；新候选群名移除实际路径尚未因此通过。Mac锁屏/用户解锁及原生体验交给负责reviewer/root，本角色没有操作UI或将等待扩张为实现失败。

原Full **S2/S6/S9/S10/S21/S27/S29/S30**的未完成分支仍开放；物理原版安装/信任/HTTPS登录/peer42不证明新候选整体UI、物理IME、同网续签或自然到期恢复。结论不支持产品接受、Full完成、Ready PR、merge、门槛豁免或部署。
