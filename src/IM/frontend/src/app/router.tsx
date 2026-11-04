import { createBrowserRouter, Navigate, RouteObject } from "react-router-dom";
import {lazy, Suspense} from 'react';

import { App } from "./App";
import { BindConfirmPage } from "../features/chat/bind-confirm-page";
import { LoginPage } from "../features/auth/login-page";
import { RegisterPage } from "../features/auth/register-page";
import { MembershipPage } from "../features/auth/membership-page";
import { CompanyMembersPage } from "../features/settings/company/company-members-page";
import { RequireAuth } from "../features/auth/require-auth";
import { MePage } from "../features/me/me-page";
import { AccountPage } from "../features/settings/account/account-page";
import { AgentCreatePage } from "../features/settings/agents/agent-create-page";
import { AgentProfilePage } from "../features/settings/agents/agent-profile-page";
import { AgentsListPage } from "../features/settings/agents/agents-list-page";
import { NodesPage } from "../features/settings/nodes/nodes-page";
import { PoliciesPage } from "../features/settings/policies/policies-page";
import { SettingsPageShell } from "../features/settings/settings-page-shell";

// Agent pages should not download the chat editor and task graph renderer.
const ModelsPage=lazy(()=>import('../features/settings/models/models-page').then(m=>({default:m.ModelsPage})));
const OnboardingPage=lazy(()=>import('../features/onboarding/onboarding-page').then(m=>({default:m.OnboardingPage})));
const TaskGraphsPage=lazy(()=>import('../features/tasks/task-graphs-page').then(m=>({default:m.TaskGraphsPage})));
const ChatWorkspacePage=lazy(()=>import('../features/chat/chat-workspace-page').then(m=>({default:m.ChatWorkspacePage})));

export const appRoutes: RouteObject[] = [
  { path: "/onboarding", element: <RequireAuth><Suspense fallback={null}><OnboardingPage /></Suspense></RequireAuth> },
  { path: "/membership", element: <MembershipPage /> },
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
      { path: "chat", element: <Suspense fallback={null}><ChatWorkspacePage /></Suspense> },
      { path: "chat/:conversationId", element: <Suspense fallback={null}><ChatWorkspacePage /></Suspense> },
      { path: "me", element: <MePage /> },
      { path: "tasks", element: <Suspense fallback={null}><TaskGraphsPage /></Suspense> },
      { path: "tasks/:graphId", element: <Suspense fallback={null}><TaskGraphsPage /></Suspense> },
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
                path: "new",
                element: <AgentCreatePage />
              },
              {
                path: ":agentId",
                element: <AgentProfilePage />
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
          { path: "models", element: <Suspense fallback={null}><ModelsPage /></Suspense> },
          { path: "company", element: <CompanyMembersPage /> },
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
