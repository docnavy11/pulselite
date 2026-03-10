import { test, expect } from "@playwright/test";

test.describe("Conversations", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/conversations");
    // Wait for page to finish loading (heading, empty state, or table)
    await page
      .locator("h1, h2, [class*='empty'], table, [role='table']")
      .first()
      .waitFor({ timeout: 12_000 });
  });

  test("conversations page renders without error", async ({ page }) => {
    // No visible error state
    await expect(
      page.getByText(/something went wrong|error loading/i)
    ).toHaveCount(0);
  });

  test("conversations page shows heading or empty state", async ({ page }) => {
    // Either the "Conversations" heading or the empty-state message is visible
    const heading = page.getByRole("heading", { name: /conversations/i });
    const emptyState = page.getByText(/no conversations yet/i);
    await expect(heading.or(emptyState).first()).toBeVisible({ timeout: 8_000 });
  });

  test("sidebar is visible on conversations page", async ({ page }) => {
    await expect(page.locator("aside")).toBeVisible();
    await expect(
      page.locator("aside").getByRole("link", { name: "Conversations" })
    ).toBeVisible();
  });
});
