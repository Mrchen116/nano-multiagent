# M1 Code Review

- reviewer: `/root/review_577_static`，独立，`gpt-6.1-sol/high`
- review_mode: full
- executed_base: `1daf6676debe129088d9bd0612b489d1eba0301a`
- validated_at: `e6b202cb87c4deb4e9f9763d5c78e59d28576dba`
- 范围：完整diff、相关调用链、current specs和unit设计；未修改受审对象。
- 结果：`[]`，无有证据的存活代码缺陷。
- 边界：不把本结论当作真机软件键盘/standalone验收；产品回归和verification单独完成。

本文件由caller根据reviewer原始返回归档，原始返回为JSON空数组。


## Round 2 — offset 修复 patch

- reviewer: `/root/review_577_static`，继续独立审查，未参与实现。
- review_mode: `patch`
- executed_base: `1daf6676debe129088d9bd0612b489d1eba0301a`
- pre_fix_head: `e6b202cb87c4deb4e9f9763d5c78e59d28576dba`
- validated_at: `bd170820be5f17f17093189d36290c377b0463ff`
- diff_range: `e6b202cb87c4deb4e9f9763d5c78e59d28576dba..bd170820be5f17f17093189d36290c377b0463ff`
- 结果：`[]`。未发现有证据的存活 patch 缺陷。
- 覆盖：新增offsetTop与height由同一手机/编辑焦点/scale≈1条件发布，blur/桌面/缩放/卸载一起移除；既有scroll监听可达；移动`#root`的relative top仅消费实际偏移，不加入固定68px、不强制scrollTo，也未使用transform或fixed来改变既有浮层包含块。既有providers测试增加68pxscroll与blur恢复行为，未新建重复测试。复用8项focused tests/build；不重复Python全量或初轮full review。
- 边界：初轮失败由镜像硬件输入触发的iOS输入辅助条及自动平移观察而来，实体软件键盘尚未验证。code review不是独立产品回归，也不将caller修后冷启观察称为reviewer真机实测；targeted-closure/full最终门禁见verification/regression。


## Round 3 — 用户输入反馈修复 patch

- reviewer: `/root/review_577_static`，独立，未参与实现。
- review_mode: `patch`
- executed_base: `76fe1d7e7c2a4d07da06453fd2b4658749bb6f87`
- pre_fix_head: `71c6ec84c1df79a3d3dcd38b039d0fac800aa99f`
- validated_at: `fbb77fe83e1132c57b9ad9af4c8a5a0ffbb4f162`
- diff_range: `71c6ec84c1df79a3d3dcd38b039d0fac800aa99f..fbb77fe83e1132c57b9ad9af4c8a5a0ffbb4f162`
- findings: `[]`。没有有证据的存活patch缺陷。
- 实际调用链：MessagePane由ChatWorkspace传入isMobile；手机Enter在本地slash/commit逻辑之前stopPropagation并return，不preventDefault，因此原生换行/IME动作继续，window冒泡阶段mention/slash候选处理不会收到该Enter；桌面沿旧路径。发送按钮仍走原handleSubmit/commit完整草稿，候选指针选择入口未改。enterKeyHint只在手机设enter。
- composer底部覆盖：同一viewport hook条件内比较visualViewport.height与documentElement.clientHeight-1，收缩时发布0px，等高且仍有焦点时移除；blur/缩放/桌面/卸载同样移除。CSS只改变具体会话composer安全区，默认env保持，正常dropzone padding和列表导航安全区未改。没有第二套事件监听或固定机型键盘阈值。
- 测试：旧手机Enter/slash行为测试按新契约改写、补mention冒泡风险用例，原providers覆盖增加键盘恢复但不失焦的行为；不重复新建风险owner。复用caller记录红4fail/93pass、修后97pass及build；既有Python代码未变，复用4119pass。最终front全量由caller运行，本review独立读取`input-r3-full.log`末尾确认86 files/808 passed/145.72s，未重复运行。
- 限制：静态与jsdom证据不证明实体中文输入法或软件键盘布局；独立产品及用户同版本复查仍必须完成。
