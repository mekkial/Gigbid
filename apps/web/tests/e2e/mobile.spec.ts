import { expect, test } from "@playwright/test";
import { signUpAndGetDraft } from "./helpers";

test("phone width: navigation collapses to a menu and job cards replace the table", async ({ page }) => {
  await signUpAndGetDraft(page);
  await expect(page.getByRole("button", { name: "Menu" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Jobs" })).toBeHidden();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow).toBe(false);                                        // no horizontal page scroll
  await page.getByRole("button", { name: "Menu" }).click();
  await page.getByRole("link", { name: "Pipeline" }).click();
  await expect(page.getByRole("heading", { name: "Pipeline" })).toBeVisible();
});
