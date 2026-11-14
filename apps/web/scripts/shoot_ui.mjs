// Screenshots of the redesigned UI for the docs. Needs the stack running (see docs/RUNBOOK.md): web on :3000, a seeded reviewer account.
// usage: cd apps/web && REVIEWER_PASSWORD=... node scripts/shoot_ui.mjs
import { chromium } from "@playwright/test";
import { fileURLToPath } from "node:url";

const BASE = process.env.BASE ?? "http://localhost:3000";
const OUT = fileURLToPath(new URL("../../../docs/images/", import.meta.url));
const pw = process.env.REVIEWER_PASSWORD ?? "gigbid-local-test";
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const page = await ctx.newPage();

// landing page: hero, then scroll through the sections
await page.goto(BASE + "/"); await wait(3500);
await page.screenshot({ path: OUT + "ui_landing_hero.png" });
for (const [i, y] of [[1, 1100], [2, 2300], [3, 3600], [4, 5200]]) { await page.mouse.wheel(0, y - (i === 1 ? 0 : [0, 1100, 2300, 3600][i - 1])); await wait(1800); await page.screenshot({ path: OUT + `ui_landing_${i}.png` }); }

// login
await page.goto(BASE + "/login"); await wait(1500);
await page.screenshot({ path: OUT + "ui_login.png" });
await page.getByLabel("Email").fill("reviewer@gigbid.dev"); await page.getByLabel("Password").fill(pw);
await page.getByRole("button", { name: "Sign in" }).click(); await page.waitForURL("**/inbox"); await wait(2500);
await page.screenshot({ path: OUT + "ui_inbox.png" });

// the first job with a finished draft, if any, then its job page and studio
const review = page.getByRole("link", { name: "Review draft" }).first();
const hasDraft = await review.count();
const firstJob = page.getByTestId("job-row").first().getByRole("link").first();
await firstJob.click(); await wait(2500);
await page.screenshot({ path: OUT + "ui_job.png" });
await page.goBack(); await wait(1000);
if (hasDraft) { await review.click(); await wait(2500); await page.screenshot({ path: OUT + "ui_studio.png" }); }
for (const [name, path] of [["pipeline", "/pipeline"], ["messages", "/messages"], ["runs", "/runs"], ["analytics", "/analytics"], ["settings", "/settings"]]) {
  await page.goto(BASE + path); await wait(2000); await page.screenshot({ path: OUT + `ui_${name}.png` });
}
await browser.close();
console.log("done", hasDraft ? "(with studio)" : "(no draft ready yet)");
