import { expect, test } from "@playwright/test";
import { signUpAndGetDraft } from "./helpers";

test("reject with a reason: nothing is sent and the reason shows up in analytics", async ({ page }) => {
  await signUpAndGetDraft(page);
  await page.getByRole("link", { name: "Review draft" }).first().click();
  await page.getByRole("button", { name: "Reject…" }).click();
  const confirm = page.getByRole("button", { name: "Confirm reject" });
  await expect(confirm).toBeDisabled();                              // a reason is required
  await page.getByLabel("Why are you rejecting this?").fill("too generic opening");
  await confirm.click();
  await expect(page.getByRole("heading", { name: "Inbox" })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("link", { name: "Analytics" }).click();
  await expect(page.getByText("too generic opening")).toBeVisible();
});
