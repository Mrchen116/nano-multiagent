import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import { AppProviders } from "./app/providers";
import { router } from "./app/router";
import "./styles/global.css";
import {readPageBootstrap} from './features/auth/page-bootstrap';
import {adoptPageSession} from './features/auth/auth-session';

const bootstrap = readPageBootstrap();
if (bootstrap) adoptPageSession(bootstrap.session);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>
);
