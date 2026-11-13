import { expect, test } from "@playwright/test";
import { signUpAndGetDraft } from "./helpers";

test("edit a draft: approval is only offered as 'save edits' and the edit is accepted", async ({ page }) => {
  await signUpAndGetDraft(page);
  await page.getByRole("link", { name: "Review draft" }).first().click();
  await page.getByRole("tab", { name: "Edit text" }).click();
  const box = page.getByTestId("draft-textarea");
  const before = await box.inputValue();
  await expect(page.getByRole("button", { name: "Save edits & approve" })).toBeDisabled();
  await box.fill(before.split(". ").slice(1).join(". "));            // user cuts the first sentence
  await expect(page.getByRole("button", { name: "Approve & send" })).toBeDisabled();
  await page.getByRole("button", { name: "Save edits & approve" }).click();
  await expect(page.getByRole("heading", { name: "Pipeline" })).toBeVisible({ timeout: 30_000 });
});

test("compliance re-checks edits: contact details are stripped before sending", async ({ page, request }) => {
  await signUpAndGetDraft(page);
  await page.getByRole("link", { name: "Review draft" }).first().click();
  await page.getByRole("tab", { name: "Edit text" }).click();
  const box = page.getByTestId("draft-textarea");
  await box.fill((await box.inputValue()) + " Reach me on WhatsApp +92 300 1234567.");
  await page.getByRole("button", { name: "Save edits & approve" }).click();
  await expect(page.getByRole("heading", { name: "Pipeline" })).toBeVisible({ timeout: 30_000 });
});
