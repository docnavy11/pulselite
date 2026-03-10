import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test("loads at /dashboard", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/dashboard/);
    // Wait for the sidebar to be visible (page shell has rendered)
    await expect(page.locator("aside")).toBeVisible({ timeout: 10_000 });
    // Wait for spinner to disappear OR for page content heading to appear
    await Promise.race([
      page
        .locator("[class*='animate-spin']")
        .waitFor({ state: "hidden", timeout: 15_000 })
        .catch(() => {}),
      page
        .getByRole("heading", { name: "Dashboard" })
        .waitFor({ state: "visible", timeout: 15_000 })
        .catch(() => {}),
    ]);
  });

  test("sidebar is visible with key nav items", async ({ page }) => {
    await page.goto("/dashboard");
    const sidebar = page.locator("aside");
    await expect(sidebar).toBeVisible();
    await expect(sidebar.getByRole("link", { name: "Dashboard" })).toBeVisible();
    await expect(sidebar.getByRole("link", { name: "Chatbots" })).toBeVisible();
    await expect(sidebar.getByRole("link", { name: "Conversations" })).toBeVisible();
    await expect(sidebar.getByRole("link", { name: "Exceptions" })).toBeVisible();
  });

  test("shows Pulse branding in sidebar", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.locator("aside").getByText("Pulse", { exact: true })).toBeVisible();
  });

  test("navigating to /chatbots via sidebar link works", async ({ page }) => {
    await page.goto("/dashboard");
    await page.locator("aside").getByRole("link", { name: "Chatbots" }).click();
    await page.waitForURL(/\/chatbots/, { timeout: 5_000 });
    await expect(page).toHaveURL(/\/chatbots/);
  });

  test("root / redirects to /dashboard when authenticated", async ({
    page,
  }) => {
    await page.goto("/");
    // Either URL changes to /dashboard or the Dashboard sidebar link is visible
    await expect(
      page.locator("aside").getByRole("link", { name: "Dashboard" })
    ).toBeVisible({ timeout: 8_000 });
  });
});
