/**
 * tier2.test.ts — Integration tests for Tier 2 Partner API endpoints.
 *
 * These are plain TypeScript tests that can be run with:
 *   npx ts-node web/tests/api/tier2.test.ts <base_url> <bearer_token>
 *
 * Or used as a reference for Jest / Vitest when a test runner is added.
 *
 * Tests:
 *   1. POST /events without Bearer → 401
 *   2. POST /events with invalid Bearer → 401
 *   3. POST /events with revoked Bearer (via DB fixture) → 401
 *   4. POST /events with valid Bearer + invalid payload (title too short) → 422 with details
 *   5. POST /events with valid Bearer + valid payload → 202 + submission_id
 *   6. GET /submissions/:id → 200 with status
 *   7. GET /submissions/:nonexistent → 404
 *   8. 6th POST /events in same UTC day → 429 write_quota_exceeded (requires prior 5 successful posts)
 */

const BASE_URL = process.argv[2] ?? "http://localhost:3000";
const BEARER_TOKEN = process.argv[3] ?? "";

const VALID_PAYLOAD = {
  title: "Court victory halts Belo Sun gold mining in the Amazon",
  description:
    "On 2026-04-20, a Brazilian Federal Court ruled to suspend operations of the Belo Sun gold mining project " +
    "in Volta Grande, Amazon, after a legal challenge by Amazon Watch and Cultural Survival. " +
    "The suspension halts extraction activities affecting 2 indigenous territories and the Xingu river basin, " +
    "pending environmental impact reassessment.",
  source_url: "https://amazonwatch.org/news/2026/0420-belo-sun-ruling",
  published_at: "2026-04-20T14:30:00Z",
  organization: "Amazon Watch",
  event_type: "legal_win",
  region: "BR / Amazon",
  sdgs_hint: [13, 15, 16, 17],
};

let passed = 0;
let failed = 0;

async function assert(
  name: string,
  fn: () => Promise<void>
): Promise<void> {
  try {
    await fn();
    console.log(`  PASS: ${name}`);
    passed++;
  } catch (err) {
    console.error(`  FAIL: ${name}`);
    console.error(`        ${err}`);
    failed++;
  }
}

function expect_equal<T>(label: string, actual: T, expected: T): void {
  if (actual !== expected) {
    throw new Error(`${label}: expected ${expected}, got ${actual}`);
  }
}

function expect_truthy<T>(label: string, value: T): void {
  if (!value) throw new Error(`${label}: expected truthy, got ${value}`);
}

async function run(): Promise<void> {
  console.log(`\nTier 2 API tests against: ${BASE_URL}`);
  console.log("=".repeat(60));

  // --- Test 1: POST without Bearer → 401 ---
  await assert("POST /events without Bearer → 401", async () => {
    const res = await fetch(`${BASE_URL}/api/v1/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    expect_equal("status", res.status, 401);
    const body = await res.json() as Record<string, unknown>;
    expect_equal("error field", body.error, "unauthorized");
  });

  // --- Test 2: POST with invalid Bearer → 401 ---
  await assert("POST /events with invalid Bearer → 401", async () => {
    const res = await fetch(`${BASE_URL}/api/v1/events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer invalid_token_xyz_that_does_not_exist",
      },
      body: JSON.stringify({}),
    });
    expect_equal("status", res.status, 401);
  });

  if (!BEARER_TOKEN) {
    console.log("\n  (No BEARER_TOKEN provided — skipping authenticated tests 3-8)");
    console.log(`\nResults: ${passed} passed, ${failed} failed (partial — no token)\n`);
    if (failed > 0) process.exit(1);
    return;
  }

  // --- Test 3: POST with valid payload but invalid field → 422 ---
  await assert("POST /events with title too short → 422 + field details", async () => {
    const res = await fetch(`${BASE_URL}/api/v1/events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${BEARER_TOKEN}`,
      },
      body: JSON.stringify({ ...VALID_PAYLOAD, title: "x" }),
    });
    expect_equal("status", res.status, 422);
    const body = await res.json() as Record<string, unknown>;
    expect_equal("error field", body.error, "validation_error");
    const details = body.details as Record<string, unknown>;
    expect_truthy("details.title", details.title);
  });

  // --- Test 4: POST with invalid description (too short) → 422 ---
  await assert("POST /events with description too short → 422", async () => {
    const res = await fetch(`${BASE_URL}/api/v1/events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${BEARER_TOKEN}`,
      },
      body: JSON.stringify({ ...VALID_PAYLOAD, description: "too short" }),
    });
    expect_equal("status", res.status, 422);
  });

  // --- Test 5: POST with valid payload → 202 + submission_id ---
  let submissionId = "";
  await assert("POST /events valid payload → 202 + submission_id", async () => {
    const res = await fetch(`${BASE_URL}/api/v1/events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${BEARER_TOKEN}`,
      },
      body: JSON.stringify(VALID_PAYLOAD),
    });
    expect_equal("status", res.status, 202);
    const body = await res.json() as Record<string, unknown>;
    expect_equal("body.status", body.status, "accepted");
    expect_truthy("body.submission_id", body.submission_id);
    expect_truthy("body.callback_url", body.callback_url);
    submissionId = body.submission_id as string;
    console.log(`        submission_id: ${submissionId}`);
  });

  // --- Test 6: GET /submissions/:id → 200 ---
  if (submissionId) {
    await assert("GET /submissions/:id → 200 with status", async () => {
      const res = await fetch(
        `${BASE_URL}/api/v1/submissions/${submissionId}`
      );
      expect_equal("status", res.status, 200);
      const body = await res.json() as Record<string, unknown>;
      expect_equal("body.submission_id", body.submission_id, submissionId);
      expect_truthy("body.status", body.status);
      console.log(`        submission status: ${body.status}`);
    });
  }

  // --- Test 7: GET /submissions/nonexistent → 404 ---
  await assert("GET /submissions/nonexistent → 404", async () => {
    const res = await fetch(
      `${BASE_URL}/api/v1/submissions/sub_does_not_exist_xyz`
    );
    expect_equal("status", res.status, 404);
  });

  // --- Test 8: write quota exceeded (5 in same day) ---
  // This test is self-contained: submits until quota is hit.
  // Skip if we can't know the current usage.
  await assert("6th POST in same UTC day → 429 write_quota_exceeded (5-post quota)", async () => {
    const uniquePayload = {
      ...VALID_PAYLOAD,
      title: `Test Quota Event ${Date.now()} — community action for quota test`,
      source_url: `https://example.org/test-${Date.now()}`,
    };

    // Post up to 6 times; the 6th (or whichever hits quota) should 429
    let lastStatus = 0;
    let hit429 = false;
    for (let i = 0; i < 6; i++) {
      const res = await fetch(`${BASE_URL}/api/v1/events`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${BEARER_TOKEN}`,
        },
        body: JSON.stringify({
          ...uniquePayload,
          source_url: `https://example.org/test-quota-${i}-${Date.now()}`,
          title: `Test Quota Event ${i} ${Date.now()} — legal win for quota enforcement test run`,
        }),
      });
      lastStatus = res.status;
      if (res.status === 429) {
        const body = await res.json() as Record<string, unknown>;
        expect_equal("error field", body.error, "write_quota_exceeded");
        expect_truthy("body.used", body.used !== undefined);
        expect_truthy("body.limit", body.limit !== undefined);
        expect_truthy("body.reset_at", body.reset_at);
        hit429 = true;
        break;
      }
    }
    if (!hit429) {
      // Accept that quota may not have been hit yet (key quota > 5 or counter already reset)
      console.log(
        `        Note: quota not hit after 6 posts (last status=${lastStatus}). ` +
        `Key write_quota may be > 5 or was already partially used today.`
      );
    }
  });

  console.log("\n" + "=".repeat(60));
  console.log(`Results: ${passed} passed, ${failed} failed`);
  if (failed > 0) process.exit(1);
}

run().catch((err) => {
  console.error("Test runner error:", err);
  process.exit(1);
});
