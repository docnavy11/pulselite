import { test, expect } from "@playwright/test";

test.describe("Exceptions Queue", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/exceptions");
    // Wait for page to finish loading (heading, empty state, or table)
    await page
      .locator("h1, h2, [class*='empty'], table, [role='table']")
      .first()
      .waitFor({ timeout: 12_000 });
  });

  test("exceptions page renders without error", async ({ page }) => {
    await expect(
      page.getByText(/something went wrong|error loading/i)
    ).toHaveCount(0);
  });

  test("exceptions page shows heading or empty state", async ({ page }) => {
    // Heading is "Exceptions Queue"; empty state is "No exceptions - your AI is handling everything!"
    const heading = page.getByRole("heading", { name: /exceptions queue/i });
    const emptyState = page.getByText(/no exceptions/i);
    await expect(heading.or(emptyState).first()).toBeVisible({ timeout: 8_000 });
  });

  test("can navigate from exceptions back to dashboard via sidebar", async ({
    page,
  }) => {
    await page
      .locator("aside")
      .getByRole("link", { name: "Dashboard" })
      .click();
    await page.waitForURL(/\/(dashboard)?$/, { timeout: 5_000 });
    await expect(
      page.locator("aside").getByRole("link", { name: "Dashboard" })
    ).toBeVisible();
  });
});
