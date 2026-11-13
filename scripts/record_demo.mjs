// Records screenshots + a short demo video of the offline stack: inbox -> job detail -> studio (evidence hover) -> approve -> pipeline.
// Usage: (stack running: python scripts/e2e_stack.py ; npx vite --port 3100)  node scripts/record_demo.mjs
import { chromium } from "/Users/mekkialbilal/Downloads/Agentic assignment 2/gigbid/apps/web/node_modules/@playwright/test/index.mjs";
import fs from "fs";

const OUT = "docs/images/screens"; fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, recordVideo: { dir: "/tmp/gigbid-video", size: { width: 1280, height: 800 } } });
const page = await ctx.newPage();
const shot = async (n) => page.screenshot({ path: `${OUT}/${n}.png` });
await page.goto("http://127.0.0.1:3100/");
await page.getByRole("button", { name: /new here/i }).click();
await page.getByLabel("Email").fill(`demo${Date.now()}@gigbid.dev`); await page.getByLabel("Password").fill("password123");
await page.getByRole("button", { name: "Create account" }).click();
await page.getByRole("heading", { name: "Set up GigBid" }).waitFor(); await shot("01-onboarding");
await page.getByRole("button", { name: "Finish setup" }).click();
await page.getByPlaceholder(/Search the marketplace/).fill("RAG chatbot over PDFs"); await page.getByRole("button", { name: "Scout now" }).click();
await page.getByRole("link", { name: "Review draft" }).first().waitFor({ timeout: 60000 }); await page.waitForTimeout(1500); await shot("02-inbox");
await page.getByRole("link", { name: "Open" }).first().click(); await page.waitForTimeout(1200); await shot("03-job-detail");
await page.goBack(); await page.getByRole("link", { name: "Review draft" }).first().click();
await page.getByRole("heading", { name: "Proposal studio" }).waitFor(); await page.getByTestId("evidence-claim").first().hover(); await page.waitForTimeout(800); await shot("04-studio-evidence-hover");
await page.getByRole("button", { name: "Approve & send" }).click(); await page.getByRole("heading", { name: "Pipeline" }).waitFor({ timeout: 30000 }); await page.waitForTimeout(800); await shot("05-pipeline");
await page.getByRole("link", { name: "Analytics" }).click(); await page.waitForTimeout(800); await shot("06-analytics");
await page.getByRole("link", { name: "Settings" }).click(); await page.waitForTimeout(800); await shot("07-settings");
await ctx.close(); await browser.close();
console.log(fs.readdirSync("/tmp/gigbid-video"));
