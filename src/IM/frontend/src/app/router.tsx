import { createBrowserRouter, Navigate, RouteObject } from "react-router-dom";

import { App } from "./App";
import { ChatWorkspacePage } from "../features/chat/chat-workspace-page";
import { AccountPage } from "../features/settings/account/account-page";
import { AgentDetailPage } from "../features/settings/agents/agent-detail-page";
import { AgentsListPage } from "../features/settings/agents/agents-list-page";
import { NodesPage } from "../features/settings/nodes/nodes-page";
import { PoliciesPage } from "../features/settings/policies/policies-page";
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
            element: <AgentsListPage />
          },
          {
            path: "agents/:agentId",
            element: <AgentDetailPage />
          },
          {
            path: "nodes",
            element: <NodesPage />
          },
          {
            path: "policies",
            element: <PoliciesPage />
          },
          {
            path: "account",
            element: <AccountPage />
          }
        ]
      }
    ]
  }
];

export const router = createBrowserRouter(appRoutes);
