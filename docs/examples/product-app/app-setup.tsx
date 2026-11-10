// Product app entry point. app-kit handles runtime config, the query client,
// tracking, error reporting and the error boundary; the product supplies its
// router and how to get the user's JWT.
import { createRoot } from "react-dom/client";
import { CoreAppProvider } from "@booking-core/app-kit";
import { configureCoreClient } from "@booking-core/api-client";
import { RouterProvider } from "@tanstack/react-router";
import { router } from "./router";
import { auth } from "./auth";
import "./theme.css";

configureCoreClient({
  baseUrl: window.__CONFIG__.apiUrl,
  getToken: () => auth.getAccessToken(),
  getTenantId: () => auth.currentTenantId(),
});

createRoot(document.getElementById("root")!).render(
  <CoreAppProvider appName="coworking-member">
    <RouterProvider router={router} />
  </CoreAppProvider>,
);
