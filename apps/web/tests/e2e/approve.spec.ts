import { expect, test } from "@playwright/test";
import { signUpAndGetDraft } from "./helpers";

test("approve a proposal: evidence on hover, dry-run preview, submitted to the pipeline", async ({ page }) => {
  await signUpAndGetDraft(page);
  await page.getByRole("link", { name: "Review draft" }).first().click();
  await expect(page.getByRole("heading", { name: "Proposal studio" })).toBeVisible();
  // every claim shows its evidence on hover
  await page.getByTestId("evidence-claim").first().hover();
  await expect(page.getByTestId("evidence-popover")).toContainText(/evidence|supported/i);
  // dry-run preview shows exactly what is sent and what it costs
  await expect(page.getByTestId("dry-run")).toContainText("Connects cost");
  await page.getByRole("button", { name: "Approve & send" }).click();
  await expect(page.getByRole("heading", { name: "Pipeline" })).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('[data-testid^="col-"] .card').first()).toBeVisible();
});
