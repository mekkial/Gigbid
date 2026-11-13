import { expect, test } from "@playwright/test";
import { uniq } from "./helpers";

test("onboarding: register, choose persona, set rates and Connects budget, land in the inbox", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /new here/i }).click();
  await page.getByLabel("Email").fill(uniq());
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Set up GigBid" })).toBeVisible();
  await page.getByLabel(/Full-stack web developer/).check();
  await page.getByLabel("Minimum hourly rate (USD)").fill("55");
  await page.getByLabel("Weekly Connects budget").fill("120");
  await page.getByRole("button", { name: "Finish setup" }).click();
  await expect(page.getByRole("heading", { name: "Inbox" })).toBeVisible();
  await expect(page.getByText("No jobs yet")).toBeVisible();
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByLabel("Minimum hourly rate (USD)")).toHaveValue("55");
  await expect(page.getByLabel("Weekly Connects budget")).toHaveValue("120");
});
