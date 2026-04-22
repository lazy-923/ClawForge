const apiBase = (
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.FRONTEND_SMOKE_API_BASE_URL ||
  "http://127.0.0.1:8002/api"
).replace(/\/$/, "");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function fetchJson(path) {
  const response = await fetch(`${apiBase}${path}`);
  assert(response.ok, `Request failed for ${path}: ${response.status} ${response.statusText}`);
  return response.json();
}

async function main() {
  console.log(`[smoke] using API base: ${apiBase}`);

  const health = await fetchJson("/health");
  assert(health.status === "ok", "Backend health status must be ok");
  assert(typeof health.name === "string" && health.name.length > 0, "Health payload must include name");

  const sessions = await fetchJson("/sessions");
  assert(Array.isArray(sessions), "Sessions endpoint must return an array");

  const skills = await fetchJson("/skills");
  assert(Array.isArray(skills), "Skills endpoint must return an array");
  assert(
    skills.every((item) => typeof item.name === "string" && typeof item.description === "string"),
    "Skills payload must include name and description",
  );

  const staleAudit = await fetchJson("/skills/audit/stale");
  assert(Array.isArray(staleAudit), "Stale audit endpoint must return an array");

  console.log("[smoke] health ok");
  console.log(`[smoke] sessions: ${sessions.length}`);
  console.log(`[smoke] skills: ${skills.length}`);
  console.log(`[smoke] stale audit entries: ${staleAudit.length}`);
  console.log("[smoke] frontend-backend contract looks healthy");
}

main().catch((error) => {
  console.error(`[smoke] failed: ${error.message}`);
  process.exit(1);
});
