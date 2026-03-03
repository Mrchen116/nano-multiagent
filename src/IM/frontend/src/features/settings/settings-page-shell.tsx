import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/settings/agents", label: "Agents" },
  { to: "/settings/nodes", label: "Nodes" },
  { to: "/settings/policies", label: "Policies" },
  { to: "/settings/account", label: "Account" }
];

export function SettingsPageShell() {
  return (
    <section className="grid w-full gap-4 lg:grid-cols-[240px_1fr]">
      <aside className="im-card p-3">
        <p className="im-title mb-3 text-base font-bold">Settings</p>
        <nav className="flex flex-col gap-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                [
                  "rounded-lg px-3 py-2 text-sm font-semibold",
                  isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
                ].join(" ")
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="im-card p-5">
        <Outlet />
      </div>
    </section>
  );
}
