import { test, expect } from "@playwright/test";

test.describe("Chatbots", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/chatbots");
    // Wait for the page heading — signals ProtectedRoute + workspace loaded + chatbots fetch done
    await page
      .getByRole("heading", { name: "Chatbots" })
      .waitFor({ state: "visible", timeout: 20_000 });
  });

  test("chatbots page renders heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: "Chatbots" })
    ).toBeVisible();
  });

  test("Create Chatbot button is visible", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /create chatbot/i })
    ).toBeVisible();
  });

  test("seeded chatbot appears in list", async ({ page }) => {
    // At least one chatbot card link should exist
    const cards = page.locator("a[href*='/chatbots/']");
    await expect(cards.first()).toBeVisible({ timeout: 8_000 });
  });

  test("clicking Create Chatbot opens modal", async ({ page }) => {
    await page.getByRole("button", { name: /create chatbot/i }).click();
    // Modal should appear with a Name input
    await expect(page.getByLabel("Name")).toBeVisible({ timeout: 3_000 });
    // Cancel closes modal
    await page.getByRole("button", { name: /cancel/i }).click();
    await expect(page.getByLabel("Name")).toHaveCount(0);
  });

  test("clicking a chatbot card navigates to chatbot detail", async ({
    page,
  }) => {
    const firstCard = page.locator("a[href*='/chatbots/']").first();
    await firstCard.click();
    await page.waitForURL(/\/chatbots\/.+/, { timeout: 15_000 });
    await expect(page).toHaveURL(/\/chatbots\/.+/);
  });
});
