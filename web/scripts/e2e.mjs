// End-to-end check of every button and demo path in a real Chrome.
// Usage: node scripts/e2e.mjs [base-url]   (default http://localhost:3000; needs Google Chrome installed)
import { chromium } from "playwright-core";
import path from "node:path";
import { fileURLToPath } from "node:url";

const BASE = (process.argv[2] ?? "http://localhost:3000").replace(/\/$/, "");
const SAMPLES = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../data/samples/policies");
const results = [];
const ok = (name) => { results.push(["ok", name]); console.log("ok    " + name); };
const fail = (name, e) => { results.push(["FAIL", name]); console.log("FAIL  " + name + ": " + (e?.message ?? e).split("\n")[0]); };
async function check(name, fn) { try { await fn(); ok(name); } catch (e) { fail(name, e); } }

const browser = await chromium.launch({ channel: "chrome", headless: true });
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 }, acceptDownloads: true });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const T = 90_000; // first request may wake the free API host
const text = (t) => page.getByText(t, { exact: false }).first();
const btn = (name) => page.getByRole("button", { name, exact: true });

await check("home page loads with hero and Get started", async () => {
  await page.goto(BASE, { waitUntil: "networkidle" });
  await text("Get your home back to").waitFor();
  await text("How it works").waitFor();
});
await check("Get started opens step 1", async () => {
  await btn("Get started").click();
  await text("Where is your home?").waitFor();
  if (await text("How it works").isVisible()) throw new Error("home content still visible");
});
await check("logo returns to the home page", async () => {
  await page.getByRole("button", { name: "AlwaysHome home page" }).click();
  await text("How it works").waitFor();
  await btn("Get started").click();
});
await check("Try: Altadena link looks up the area", async () => {
  await page.getByRole("button", { name: "Altadena" }).click();
  await text("Wildfire exposure").waitFor({ timeout: T });
  await text("Very High").waitFor({ timeout: T });
});
await check("typed address + Look up", async () => {
  await page.getByPlaceholder("Street address, city, ZIP").fill("1200 Chautauqua Blvd, Pacific Palisades, CA 90272");
  await btn("Look up").click();
  await text("1200 CHAUTAUQUA").waitFor({ timeout: T });
});
await check("Continue to step 2", async () => {
  await btn("Continue").click();
  await text("Tell us about your home").waitFor();
});
await check("answer all 8 home questions, numbers, checkbox", async () => {
  // [question heading, answer]: click the answer inside that question's block
  for (const [q, a] of [["Roof material", "Tile"], ["Eaves (roof overhang)", "Enclosed"], ["Attic and crawlspace vents", "Coarse mesh"],
    ["Exterior walls", "Stucco, brick or cement"], ["Windows", "Single pane"], ["Raised deck", "Wood"],
    ["Fence touching the house", "Wood or vinyl"], ["Sheds or outbuildings", "Under 30 ft"]]) {
    const block = page.locator("div", { has: page.getByText(q, { exact: true }) }).filter({ has: page.getByRole("button", { name: a, exact: true }) }).last();
    await block.getByRole("button", { name: a, exact: true }).click();
  }
  const nums = page.locator('input[type="number"]');
  await nums.nth(0).fill("1972"); await nums.nth(1).fill("2000"); await nums.nth(2).fill("1");
  await page.getByLabel("Defensible space done (trees trimmed, brush cleared)").check();
  await btn("Continue").click();
  await text("Your insurance").waitFor();
});
await check("sample policy (FAIR Plan + DIC) fills the form", async () => {
  await page.locator("select").filter({ hasText: "Choose a sample" }).selectOption({ label: "FAIR Plan + DIC (Altadena)" });
  await text("dic_altadena.pdf").waitFor({ timeout: T });
  await text("quote found").waitFor();
  const v = await page.locator('input[placeholder="650000"]').inputValue();
  if (v !== "650000") throw new Error("dwelling limit not filled: " + v);
});
await check("upload a PDF file", async () => {
  await page.locator('input[type="file"]').setInputFiles(path.join(SAMPLES, "homeowners_two_page.pdf"));
  await text("homeowners_two_page.pdf").waitFor({ timeout: T });
});
await check("See my situation opens step 4", async () => {
  await btn("See my situation").click();
  await text("Your situation today").waitFor({ timeout: T });
  await text("If your home burned down tomorrow").waitFor({ timeout: T });
  await text("Gaps in your coverage").waitFor();
});
await check("See my plan opens step 5", async () => {
  await btn("See my plan").click();
  await text("Fixes, best value first").waitFor({ timeout: T });
});
await check("budget slider updates the plan", async () => {
  await page.locator('input[type="range"]').fill("0");
  await text("0 fixes fit your budget").waitFor({ timeout: T });
  await page.locator('input[type="range"]').fill("60000");
  await page.waitForFunction(() => !document.body.innerText.includes("0 fixes fit your budget"), null, { timeout: T });
});
await check("Generate report and Download", async () => {
  await btn("Generate report").click();
  await btn("Download").waitFor({ timeout: 150_000 });
  const body = await page.locator("article.report").innerText();
  console.log("      report starts: " + body.split("\n").slice(0, 2).join(" | ").slice(0, 120));
  if (body.includes("couldn't write")) throw new Error("report failed");
  const [dl] = await Promise.all([page.waitForEvent("download"), btn("Download").click()]);
  if (!dl.suggestedFilename().endsWith(".md")) throw new Error(dl.suggestedFilename());
});
await check("Back buttons and stepper", async () => {
  await btn("Back").last().click();
  await text("Your situation today").waitFor();
  for (const [i, t] of [[0, "Where is your home?"], [1, "Tell us about your home"], [2, "Your insurance"], [3, "Your situation today"], [4, "Fixes, best value first"]]) {
    await page.locator("ol").first().getByRole("button").nth(i).click();
    await text(t).waitFor({ timeout: T });
  }
});
await check("theme toggle switches dark/light", async () => {
  const toggle = page.getByRole("button", { name: /Switch to (dark|light) mode/ });
  const before = await page.evaluate(() => document.documentElement.classList.contains("dark"));
  await toggle.click();
  const after = await page.evaluate(() => document.documentElement.classList.contains("dark"));
  if (before === after) throw new Error("class did not change");
  await toggle.click();
});
for (const label of ["Altadena, FAIR Plan only, older home", "Altadena, FAIR Plan + DIC, partly hardened", "Pacific Palisades, private HO-3, underinsured",
  "Wilshire, well covered, fully hardened", "Edge case: owner answers Unknown to everything, no budget", "Edge case: Unknown everywhere, large budget"]) {
  await check(`demo menu: ${label}`, async () => {
    await page.getByLabel("Fill with a sample homeowner").selectOption({ label });
    await text("Your situation today").waitFor({ timeout: T });
    await text("Chance of losing the house").waitFor({ timeout: T });
    await btn("See my plan").click();
    await text("Your plan").waitFor({ timeout: T });
  });
}
await check("See an example from the home page", async () => {
  await page.getByRole("button", { name: "AlwaysHome home page" }).click();
  await btn("See an example").click();
  await text("If your home burned down tomorrow").waitFor({ timeout: T });
});
await check("example banner: Start with my own home clears the form", async () => {
  await text("You’re viewing an example").waitFor();
  await btn("Start with my own home").click();
  await text("Where is your home?").waitFor();
  if (await page.getByPlaceholder("Street address, city, ZIP").inputValue()) throw new Error("address not cleared");
  if (await text("You’re viewing an example").isVisible()) throw new Error("banner still visible");
});
await check("deep link ?demo=...&step=5", async () => {
  await page.goto(BASE + "/?demo=palisades_underinsured&step=5", { waitUntil: "networkidle" });
  await text("Fixes, best value first").waitFor({ timeout: T });
});
await check("Credits page and back", async () => {
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.getByRole("link", { name: "Credits" }).first().click();
  await text("The team behind AlwaysHome").waitFor();
  await text("Atharva Uplap").waitFor();
  await page.getByRole("link", { name: "Back to the app" }).click();
  await text("Get your home back to").waitFor();
});
await check("no JavaScript errors", async () => { if (errors.length) throw new Error(errors.join(" | ")); });

await browser.close();
const failed = results.filter(([s]) => s === "FAIL").length;
console.log(`\n${results.length - failed}/${results.length} checks passed on ${BASE}`);
process.exit(failed ? 1 : 0);
