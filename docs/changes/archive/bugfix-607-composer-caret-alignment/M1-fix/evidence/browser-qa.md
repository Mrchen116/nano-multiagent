# Composer 排版验证

## Claim / Baseline

长草稿发生纵向溢出后，可见文字及提及高亮使用与原生 textarea 相同的排版宽度，反复编辑不会产生光标前的假空位。

修前 `9ebe12f85`：Chromium 外宽 `1119.6015625px`、textarea/mirror clientWidth `1112/1118px`；WebKit 对照 `1192/1198px`。文本值与镜像正文一致。临时显示原生文字并与镜像显色叠放，换行后字形不重合；只同步槽宽即可恢复重合。

最终产品版本 `65499f136275bc241d33976a252230583a68e721`，基线 `9d6946df23e6b061b2cefbda89d00c34955f15c0`。

## Method / Result

真实浏览器加载仓库的 MessagePane 与 global.css，使用 1200、900、390px viewport。每种宽度检查空草稿、保留末尾空格的短草稿、中英文与路径长草稿、连续删除及重新输入、换行、上下滚动、缩短内容；最后选择 mention 并编辑长草稿。Chromium/WebKit 各 25 个状态全部通过：

- textarea/mirror clientWidth 相同；Chromium 为 `1112/812/292px`，WebKit 在相应溢出状态下相同。
- 两层内容高度相同；滚动位置差不超过 `1px`；镜像正文（除装饰性零宽结尾外）与 textarea 值相同。
- 短草稿中的原生空格保留，提及高亮存在；没有修改用户文本来抵消视觉错位。

完整真实入口验证：`e2e-up.sh` 在本 worktree 创建隔离 IM + Gateway，IM `http://127.0.0.1:51678`；浏览器以隔离 nano 用户登录、从 New chat 选择 E2E Agent，并刷新加载最终构建产物。在 `/chat/c_40hwopyi` 执行上述三种宽度的编辑/滚动检查及长草稿原生撤销，共 26 个状态通过。390px 用例走应用真实的移动布局选择，未使用物理手机键盘。

Chromium CDP 组合输入补充观察：通过原生组合输入接口写入 `shen'me'gui` 后提交 `什么鬼`，提交后的草稿与镜像一致。该模拟不证明 macOS 原生候选面板的实际显示效果，不作为物理 IME 验收。

## Locator / Limit

本次一次性脚本、测量 JSON 和截图保留在本机 `output/playwright/bugfix-607/`，不提交截图、日志或运行数据。组件测试不代替浏览器排版；浏览器宽度检查不代替系统中文输入法候选 UI、Firefox 或物理设备验收。完整服务与 Vite 在交付前停止。
