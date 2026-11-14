import { expect, test } from "@playwright/test";
import { uniq } from "./helpers";

test("degraded mode: a banner appears when the marketplace is down and clears when it recovers", async ({ page, request }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: /new here/i }).click();
  await page.getByLabel("Email").fill(uniq());
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.getByRole("button", { name: "Finish setup" }).click();
  await expect(page.getByTestId("degraded-banner")).toHaveCount(0);
  await request.post("http://127.0.0.1:8101/_admin/fail_next/200");       // marketplace outage
  await expect(page.getByTestId("degraded-banner")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("degraded-banner")).toContainText(/queued/i);
  await request.post("http://127.0.0.1:8101/_admin/fail_next/0");         // recovery
  await expect(page.getByTestId("degraded-banner")).toHaveCount(0, { timeout: 20_000 });
});
