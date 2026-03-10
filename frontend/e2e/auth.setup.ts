// frontend/e2e/auth.setup.ts
import { test as setup } from "@playwright/test";
import path from "path";

const authFile = path.join(__dirname, ".auth/user.json");

setup("authenticate as dev user", async ({ page }) => {
  await page.goto("/login");

  // Fill credentials
  await page.getByLabel("Email").fill("test@pulse.dev");
  await page.getByLabel("Password").fill("test");
  await page.getByRole("button", { name: "Sign in" }).click();

  // Wait for the dashboard to load — the sidebar "Dashboard" nav link is a reliable signal.
  // The app router server-redirect from / → /dashboard may keep the URL at /, so we
  // check for the sidebar nav instead of the URL.
  await page.getByRole("link", { name: "Dashboard" }).waitFor({ timeout: 10_000 });

  // Save auth state (localStorage tokens + cookies)
  await page.context().storageState({ path: authFile });
});
