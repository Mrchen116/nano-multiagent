import { createBrowserRouter, Navigate, RouteObject } from "react-router-dom";

import { App } from "./App";
import { BindConfirmPage } from "../features/chat/bind-confirm-page";
import { ChatWorkspacePage } from "../features/chat/chat-workspace-page";
import { LoginPage } from "../features/auth/login-page";
import { RegisterPage } from "../features/auth/register-page";
import { RequireAuth } from "../features/auth/require-auth";
import { MePage } from "../features/me/me-page";
import { AccountPage } from "../features/settings/account/account-page";
import { AgentCreatePage } from "../features/settings/agents/agent-create-page";
import { AgentDetailPage } from "../features/settings/agents/agent-detail-page";
import { AgentsListPage } from "../features/settings/agents/agents-list-page";
import { NodesPage } from "../features/settings/nodes/nodes-page";
import { PoliciesPage } from "../features/settings/policies/policies-page";
import { SettingsPageShell } from "../features/settings/settings-page-shell";

export const appRoutes: RouteObject[] = [
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  {
    path: "/",
    element: (
      <RequireAuth>
        <App />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Navigate to="/chat" replace /> },
      { path: "bind/confirm", element: <BindConfirmPage /> },
      { path: "chat", element: <ChatWorkspacePage /> },
      { path: "chat/:conversationId", element: <ChatWorkspacePage /> },
      { path: "me", element: <MePage /> },
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
            children: [
              {
                index: true,
                element: <AgentsListPage />
              },
              {
                path: ":agentId",
                element: <AgentDetailPage />
              }
            ]
          },
          {
            path: "nodes",
            children: [
              {
                index: true,
                element: <NodesPage />
              },
              {
                path: ":nodeId/agents/new",
                element: <AgentCreatePage />
              }
            ]
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
