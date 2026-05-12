import { Outlet } from "react-router-dom";

// M19/R11-2: prototype 5 页里没有 Settings 二级侧栏 / sub-nav pill。
// Agents / Nodes / Account 是各自独立的页面 (UserMenu / 移动 Me 直达),
// 不应共享一层 Settings chrome。这里把 Shell 退化为透传 Outlet,
// 各 page 自己负责全高占满 + 滚动管理。Router 树保留,避免大改路径。
export function SettingsPageShell() {
  return <Outlet />;
}
