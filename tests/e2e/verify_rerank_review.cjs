const { createHash } = require("node:crypto");
const fs = require("node:fs/promises");
const path = require("node:path");
const { chromium } = require("playwright");

const baseUrl = process.env.RERANK_REVIEW_URL || "http://127.0.0.1:8765";
const outputDir = process.env.RERANK_REVIEW_OUTPUT || "/tmp/needradar-rerank-review-qa";
const expectedQueries = Number(process.env.EXPECTED_REVIEW_QUERIES || 100);
const expectedCandidates = Number(process.env.EXPECTED_REVIEW_CANDIDATES || 2000);
const browserPath =
  process.env.PLAYWRIGHT_BROWSER_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const protocol = "single-expert-blind-test-retest-v1";

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function reviewGrade(blindId) {
  return Number.parseInt(sha256(`grade:${blindId}`).slice(0, 2), 16) % 3;
}

async function waitForApp(page) {
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.locator("#app").waitFor({ state: "visible" });
  await page.locator("#sourceSummary").filter({ hasText: `${expectedCandidates} 个候选` }).waitFor();
}

async function main() {
  await fs.mkdir(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: browserPath });
  const errors = [];
  const externalRequests = [];
  const downloads = [];
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
    const page = await context.newPage();
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(`console: ${message.text()}`);
    });
    page.on("pageerror", (error) => errors.push(`page: ${error.message}`));
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (!['127.0.0.1', 'localhost'].includes(url.hostname)) externalRequests.push(request.url());
    });
    page.on("download", async (download) => {
      const destination = path.join(outputDir, download.suggestedFilename());
      await download.saveAs(destination);
      downloads.push(download.suggestedFilename());
    });

    await waitForApp(page);
    const reviewPackage = await page.evaluate(async () => (await fetch("/api/package")).json());
    assert(reviewPackage.query_count === expectedQueries, `expected ${expectedQueries} frozen queries`);
    assert(reviewPackage.candidate_count === expectedCandidates, `expected ${expectedCandidates} frozen candidates`);
    const serializedPackage = JSON.stringify(reviewPackage);
    for (const forbidden of ["original_rank", "original_score", "reranked_rank", "relevance_score", "model_id"]) {
      assert(!serializedPackage.includes(forbidden), `browser package leaked ${forbidden}`);
    }
    await page.screenshot({ path: path.join(outputDir, "desktop-first-pass.png"), fullPage: true });

    await page.locator("#progressFile").setInputFiles({
      name: "invalid-progress.json",
      mimeType: "application/json",
      buffer: Buffer.from("{}"),
    });
    await page.locator("#toast").filter({ hasText: "无法导入" }).waitFor();

    await page.locator('.grade-button[data-grade="0"]').click();
    await page.locator("#progressText").filter({ hasText: `1 / ${expectedCandidates}` }).waitFor();
    await page.reload({ waitUntil: "networkidle" });
    await page.locator("#progressText").filter({ hasText: `1 / ${expectedCandidates}` }).waitFor();

    const storageKey = `needradar-rerank-review:${protocol}:${reviewPackage.source_template_sha256}`;
    const firstPass = Object.fromEntries(
      reviewPackage.rows.map((row) => [
        row.blind_document_id,
        { grade: reviewGrade(row.blind_document_id), notes: "", uncertain: false, decided_at: "2026-07-13T00:00:00Z" },
      ]),
    );
    await page.evaluate(
      ({ key, sourceHash, decisions }) => {
        localStorage.setItem(
          key,
          JSON.stringify({
            state_version: 1,
            protocol_version: "single-expert-blind-test-retest-v1",
            source_template_sha256: sourceHash,
            stage: "first_pass",
            created_at: "2026-07-13T00:00:00Z",
            updated_at: "2026-07-13T00:00:00Z",
            first_pass_completed_at: null,
            retest_started_at: null,
            retest_completed_at: null,
            completed_at: null,
            first_pass: decisions,
            retest: {},
            adjudications: {},
            reliability: null,
            cursor: { query_id: null, candidate_index: 0, retest_index: 0, adjudication_index: 0 },
          }),
        );
      },
      { key: storageKey, sourceHash: reviewPackage.source_template_sha256, decisions: firstPass },
    );
    await page.reload({ waitUntil: "networkidle" });
    await page.locator("#stageActionButton").filter({ hasText: "冻结首轮" }).waitFor();
    page.once("dialog", (dialog) => dialog.accept());
    await page.locator("#stageActionButton").click();
    await page.locator("#stageTitle").filter({ hasText: "隐藏重测尚未开始" }).waitFor();
    await page.locator("#panelActionButton").click();
    const retestLayout = await page.evaluate(() => ({
      workspaceColumns: getComputedStyle(document.querySelector("#reviewWorkspace")).gridTemplateColumns,
      contentWidth: document.querySelector(".review-content").getBoundingClientRect().width,
      decisionWidth: document.querySelector(".decision-rail").getBoundingClientRect().width,
    }));
    assert(retestLayout.contentWidth >= 700, `retest content column is too narrow: ${JSON.stringify(retestLayout)}`);
    assert(retestLayout.decisionWidth <= 280, `retest decision column is too wide: ${JSON.stringify(retestLayout)}`);
    await page.screenshot({ path: path.join(outputDir, "desktop-retest.png"), fullPage: true });

    const retestIds = [...reviewPackage.rows]
      .sort((left, right) =>
        sha256(`${reviewPackage.source_template_sha256}:retest:${left.blind_document_id}`).localeCompare(
          sha256(`${reviewPackage.source_template_sha256}:retest:${right.blind_document_id}`),
        ),
      )
      .slice(0, Math.ceil(expectedCandidates * 0.1))
      .map((row) => row.blind_document_id);
    const retest = Object.fromEntries(
      retestIds.map((blindId, index) => [
        blindId,
        {
          grade: index === 0 ? (firstPass[blindId].grade + 1) % 3 : firstPass[blindId].grade,
          notes: "",
          uncertain: false,
          decided_at: "2026-07-15T00:00:00Z",
        },
      ]),
    );
    await page.evaluate(
      ({ key, decisions }) => {
        const current = JSON.parse(localStorage.getItem(key));
        current.stage = "retest";
        current.first_pass_completed_at = "2026-07-13T00:00:00Z";
        current.retest_started_at = "2026-07-15T00:00:00Z";
        current.retest = decisions;
        localStorage.setItem(key, JSON.stringify(current));
      },
      { key: storageKey, decisions: retest },
    );
    await page.reload({ waitUntil: "networkidle" });
    await page
      .locator("#progressText")
      .filter({ hasText: `${retestIds.length} / ${retestIds.length}` })
      .waitFor();
    await page.locator("#stageActionButton").click();
    await page.locator("#comparisonPanel").waitFor({ state: "visible" });
    const disagreementId = retestIds[0];
    await page.locator(`.grade-button[data-grade="${firstPass[disagreementId].grade}"]`).click();
    await page.locator("#notesInput").fill("重读后确认首轮等级更符合直接有用性标准。");
    await page.locator("#adjudicateButton").click();
    await page.locator("#stageTitle").filter({ hasText: "单专家盲审已完成" }).waitFor();
    await page.screenshot({ path: path.join(outputDir, "desktop-complete.png"), fullPage: true });

    await page.locator("#downloadFinalButton").click();
    const deadline = Date.now() + 5000;
    while (downloads.length < 4 && Date.now() < deadline) await new Promise((resolve) => setTimeout(resolve, 50));
    for (const filename of [
      "reviewer-single.csv",
      "reviewer-retest.csv",
      "labels-adjudicated.csv",
      "labels-adjudicated.manifest.json",
    ]) {
      assert(downloads.includes(filename), `missing download ${filename}`);
    }
    const manifest = JSON.parse(await fs.readFile(path.join(outputDir, "labels-adjudicated.manifest.json"), "utf8"));
    assert(manifest.labels_path === "labels-adjudicated.csv", "manifest label path is not portable");
    assert(manifest.retest_sample_count === retestIds.length, "manifest retest count does not match the pool");
    assert(manifest.disagreement_count === 1, "manifest disagreement count is not 1");
    assert(manifest.acceptance.passed === true, "high-consistency fixture should pass evidence thresholds");

    assert(errors.length === 0, errors.join("\n"));
    assert(externalRequests.length === 0, `external browser requests detected: ${externalRequests.join(", ")}`);
    await context.close();

    const mobile = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const mobilePage = await mobile.newPage();
    mobilePage.on("console", (message) => {
      if (message.type() === "error") errors.push(`mobile console: ${message.text()}`);
    });
    mobilePage.on("pageerror", (error) => errors.push(`mobile page: ${error.message}`));
    await waitForApp(mobilePage);
    const overflowDetails = await mobilePage.evaluate(() => ({
      viewport: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      offenders: [...document.querySelectorAll("body *")]
        .map((element) => ({
          element: `${element.tagName.toLowerCase()}#${element.id}.${element.className}`,
          left: element.getBoundingClientRect().left,
          right: element.getBoundingClientRect().right,
          width: element.getBoundingClientRect().width,
        }))
        .filter((item) => item.left < -1 || item.right > window.innerWidth + 1)
        .slice(0, 12),
    }));
    assert(
      overflowDetails.documentWidth <= overflowDetails.viewport,
      `mobile page has horizontal overflow: ${JSON.stringify(overflowDetails)}`,
    );
    await mobilePage.screenshot({ path: path.join(outputDir, "mobile-first-pass.png"), fullPage: true });
    assert(errors.length === 0, errors.join("\n"));
    await mobile.close();

    process.stdout.write(
      JSON.stringify(
        {
          package: { queries: reviewPackage.query_count, candidates: reviewPackage.candidate_count },
          downloads: downloads.sort(),
          screenshots: [
            "desktop-first-pass.png",
            "desktop-retest.png",
            "desktop-complete.png",
            "mobile-first-pass.png",
          ],
          console_errors: errors.length,
          external_requests: externalRequests.length,
        },
        null,
        2,
      ) + "\n",
    );
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
