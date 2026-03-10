import { test, expect } from "@playwright/test";

// These tests must run WITHOUT auth state — override the project storage state
test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Authentication", () => {
  test("login page renders correctly", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Pulse" })).toBeVisible();
    await expect(page.getByText("Sign in to your account")).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  test("successful login redirects to dashboard", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("test@pulse.dev");
    await page.getByLabel("Password").fill("test");
    await page.getByRole("button", { name: "Sign in" }).click();
    // Wait for redirect to /dashboard (/ redirects server-side to /dashboard)
    await page.waitForURL(/\/(dashboard)?$/, { timeout: 10_000 });
    // Sidebar renders with nav links — check for Dashboard nav item text
    await expect(page.locator("nav").getByText("Dashboard")).toBeVisible({
      timeout: 10_000,
    });
  });

  test("wrong password shows error message", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("test@pulse.dev");
    await page.getByLabel("Password").fill("wrongpassword");
    await page.getByRole("button", { name: "Sign in" }).click();
    // Error appears in the red box
    await expect(
      page.locator(".bg-red-50").first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test("unauthenticated user redirected from /dashboard to /login", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    // ProtectedRoute redirects to /login when no tokens
    await expect(page.getByLabel("Email")).toBeVisible({ timeout: 8_000 });
  });

  test("register page is accessible", async ({ page }) => {
    await page.goto("/register");
    // Page loads without error — check for a form element or heading
    await expect(page.locator("form")).toBeVisible({ timeout: 5_000 });
  });
});
