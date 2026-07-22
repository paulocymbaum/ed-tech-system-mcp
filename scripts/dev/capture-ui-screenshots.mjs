#!/usr/bin/env node
/**
 * Capture workflow UI screenshots for README / docs.
 * Requires the dev UI running: ./scripts/dev/run-workflow-ui.sh
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUT_DIR = path.join(ROOT, "docs/assets");
const UI_URL = process.env.WORKFLOW_UI_URL ?? "http://127.0.0.1:4173";

const MOCK_CONTENT_TRACE = [
  {
    step: 1,
    node_id: "generate_lesson",
    status: "ok",
    attempt: 1,
    validation_errors: [],
    retry_counts: {},
    input_snapshot: { topic: "fractions", grade_level: "6th grade" },
    output_update: { lesson_draft: "Introduction to fractions..." },
    llm_io: {
      model_name: "llama-3.3-70b-versatile",
      llm_complexity: 0.72,
      system_prompt: "You are an expert lesson planner for K-12 educators.",
      user_prompt: "Create a lesson on fractions for 6th grade students.",
      raw_output: '{"title":"Understanding Fractions","objectives":["Define numerator and denominator"]}',
    },
  },
  {
    step: 2,
    node_id: "validate_lesson",
    status: "ok",
    attempt: 1,
    validation_errors: [],
    retry_counts: { lesson_retry_count: 0 },
    input_snapshot: { lesson_draft: "Introduction to fractions..." },
    output_update: { lesson: { title: "Understanding Fractions" } },
    llm_io: null,
  },
  {
    step: 3,
    node_id: "generate_quiz",
    status: "ok",
    attempt: 1,
    validation_errors: [],
    retry_counts: { lesson_retry_count: 0 },
    input_snapshot: { lesson: { title: "Understanding Fractions" } },
    output_update: { quiz_draft: "Q1: What is 1/2 + 1/4?" },
    llm_io: {
      model_name: "llama-3.3-70b-versatile",
      llm_complexity: 0.55,
      system_prompt: "Generate a short formative quiz aligned to the lesson.",
      user_prompt: "Lesson: Understanding Fractions",
      raw_output: '{"questions":[{"prompt":"What is 1/2 + 1/4?"}]}',
    },
  },
  {
    step: 4,
    node_id: "validate_quiz",
    status: "failed",
    attempt: 1,
    validation_errors: ["quiz.questions[0].choices: field required"],
    retry_counts: { lesson_retry_count: 0, quiz_retry_count: 0 },
    input_snapshot: { quiz_draft: "Q1: What is 1/2 + 1/4?" },
    output_update: {},
    llm_io: null,
  },
  {
    step: 5,
    node_id: "generate_quiz",
    status: "retry",
    attempt: 2,
    validation_errors: [],
    retry_counts: { lesson_retry_count: 0, quiz_retry_count: 1 },
    input_snapshot: { quiz_draft: "Q1: What is 1/2 + 1/4?" },
    output_update: { quiz_draft: "Q1 with four choices..." },
    llm_io: {
      model_name: "llama-3.3-70b-versatile",
      llm_complexity: 0.61,
      system_prompt: "Generate a short formative quiz aligned to the lesson.",
      user_prompt: "Fix validation errors: choices required.",
      raw_output: '{"questions":[{"prompt":"What is 1/2 + 1/4?","choices":["1/4","3/4","1/2","1"]}]}',
    },
  },
  {
    step: 6,
    node_id: "validate_quiz",
    status: "ok",
    attempt: 2,
    validation_errors: [],
    retry_counts: { lesson_retry_count: 0, quiz_retry_count: 1 },
    input_snapshot: { quiz_draft: "Q1 with four choices..." },
    output_update: { quiz: { questions: [{ prompt: "What is 1/2 + 1/4?" }] } },
    llm_io: null,
  },
  {
    step: 7,
    node_id: "merge_results",
    status: "ok",
    attempt: 1,
    validation_errors: [],
    retry_counts: { lesson_retry_count: 0, quiz_retry_count: 1, pbl_retry_count: 0 },
    input_snapshot: {},
    output_update: { generation_complete: true },
    llm_io: null,
  },
];

async function waitForWorkflows(page) {
  await page.waitForSelector(".workflow-list .workflow-card", { timeout: 15000 });
  await page.waitForTimeout(600);
}

async function selectWorkflow(page, label) {
  await page.getByRole("button", { name: new RegExp(label, "i") }).click();
  await page.waitForTimeout(400);
}

async function capture(page, name, options = {}) {
  const filePath = path.join(OUT_DIR, `${name}.png`);
  await page.screenshot({ path: filePath, ...options });
  console.log(`saved ${filePath}`);
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  await page.goto(UI_URL, { waitUntil: "networkidle" });
  await waitForWorkflows(page);

  await selectWorkflow(page, "Lesson");
  await page.waitForSelector(".react-flow", { timeout: 10000 });
  await page.waitForTimeout(800);
  await capture(page, "workflow-ui-explorer", { fullPage: true });

  const graph = page.locator(".react-flow");
  await graph.scrollIntoViewIfNeeded();
  await capture(page, "workflow-graph-content-generation");

  await selectWorkflow(page, "Research");
  await page.waitForSelector(".react-flow", { timeout: 10000 });
  await page.waitForTimeout(800);
  await capture(page, "workflow-graph-research-article");

  await selectWorkflow(page, "Lesson");
  await page.waitForSelector(".react-flow", { timeout: 10000 });

  await page.route("**/api/workflows/content-generation/run", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        topic: "fractions",
        grade_level: "6th grade",
        generation_complete: true,
        lesson_retry_count: 0,
        quiz_retry_count: 1,
        pbl_retry_count: 0,
        trace: MOCK_CONTENT_TRACE,
      }),
    });
  });

  await page.getByRole("button", { name: /run and capture trace/i }).click();
  await page.waitForSelector(".trace-item", { timeout: 10000 });
  await page.waitForTimeout(500);

  const replayStep = page.locator(".trace-item-button").nth(4);
  if (await replayStep.count()) {
    await replayStep.click();
    await page.waitForTimeout(400);
  }

  await capture(page, "workflow-trace-replay", { fullPage: true });

  const inspector = page.locator(".inspector-panel");
  if (await inspector.count()) {
    await inspector.scrollIntoViewIfNeeded();
    await capture(page, "workflow-step-inspector");
  }

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
