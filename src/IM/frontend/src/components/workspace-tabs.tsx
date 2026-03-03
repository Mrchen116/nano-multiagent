import * as Tabs from "@radix-ui/react-tabs";
import { useNavigate } from "react-router-dom";

import { useUiStore } from "../state/ui-store";

export function WorkspaceTabs() {
  const navigate = useNavigate();
  const workspace = useUiStore((state) => state.workspace);
  const setWorkspace = useUiStore((state) => state.setWorkspace);

  return (
    <Tabs.Root
      className="inline-flex items-center gap-2 rounded-full bg-[#ece7dc] p-1"
      value={workspace}
      onValueChange={(value) => {
        const next = value as "chat" | "settings";
        setWorkspace(next);
        navigate(next === "chat" ? "/chat" : "/settings/agents");
      }}
    >
      <Tabs.List aria-label="Workspaces" className="flex gap-1">
        <Tabs.Trigger
          value="chat"
          className="rounded-full px-4 py-1.5 text-sm font-semibold text-slate-600 data-[state=active]:bg-white data-[state=active]:text-slate-900"
        >
          Chat
        </Tabs.Trigger>
        <Tabs.Trigger
          value="settings"
          className="rounded-full px-4 py-1.5 text-sm font-semibold text-slate-600 data-[state=active]:bg-white data-[state=active]:text-slate-900"
        >
          Settings
        </Tabs.Trigger>
      </Tabs.List>
    </Tabs.Root>
  );
}
