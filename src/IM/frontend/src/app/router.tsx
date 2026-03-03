import { createBrowserRouter, Navigate, RouteObject } from "react-router-dom";

import { App } from "./App";
import { ChatWorkspacePage } from "../features/chat/chat-workspace-page";
import { PlaceholderBlock } from "../features/settings/placeholders";
import { SettingsPageShell } from "../features/settings/settings-page-shell";

export const appRoutes: RouteObject[] = [
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Navigate to="/chat" replace /> },
      { path: "chat", element: <ChatWorkspacePage /> },
      { path: "chat/:conversationId", element: <ChatWorkspacePage /> },
      {
        path: "settings",
        element: <SettingsPageShell />,
        children: [
          {
            index: true,
            element: <Navigate to="/settings/agents" replace />
          },
          {
            path: "agents",
            element: <PlaceholderBlock title="Agents" description="Agent profiles and versions." />
          },
          {
            path: "agents/:agentId",
            element: <PlaceholderBlock title="Agent Detail" description="Edit one agent profile." />
          },
          {
            path: "nodes",
            element: <PlaceholderBlock title="Nodes" description="Node status and center config." />
          },
          {
            path: "policies",
            element: <PlaceholderBlock title="Policies" description="Global policy controls." />
          },
          {
            path: "account",
            element: <PlaceholderBlock title="Account" description="Owner account metadata." />
          }
        ]
      }
    ]
  }
];

export const router = createBrowserRouter(appRoutes);
