import { expect, type Page } from "@playwright/test";

export const uniq = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}@e2e.dev`;

/** Register a fresh user, finish onboarding, scout, and wait until at least one draft awaits approval. */
export async function signUpAndGetDraft(page: Page, query = "RAG chatbot over PDFs") {
  await page.goto("/");
  await page.getByRole("button", { name: /new here/i }).click();
  await page.getByLabel("Email").fill(uniq());
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Set up GigBid" })).toBeVisible();
  await page.getByRole("button", { name: "Finish setup" }).click();
  await expect(page.getByRole("heading", { name: "Inbox" })).toBeVisible();
  await page.getByPlaceholder(/Search the marketplace/).fill(query);
  await page.getByRole("button", { name: "Scout now" }).click();
  await expect(page.getByRole("link", { name: "Review draft" }).first()).toBeVisible({ timeout: 45_000 });
}
