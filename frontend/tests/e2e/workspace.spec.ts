import { expect, test } from "@playwright/test";

test("workspace boots and surfaces backend state", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByTestId("workspace-shell")).toBeVisible();
  await expect(page.getByTestId("backend-status-card")).toBeVisible();
  await expect(page.getByTestId("backend-health-pill")).toContainText("ok");
  await expect(page.getByTestId("catalog-list")).toContainText("get_weather");
  await expect(page.getByTestId("catalog-list")).toContainText("professional_rewrite");
});

test("can create a session and stream a backend response", async ({ page }) => {
  await page.goto("/");

  await page.getByTestId("create-session-button").click();
  await expect(page.getByTestId("session-list")).toContainText("New Session");

  await page.getByTestId("chat-input").fill("Please check the weather forecast for Shanghai.");
  await page.getByTestId("send-button").click();

  await expect(page.getByTestId("stream-banner")).toBeVisible();
  await expect(page.getByTestId("message-stream")).toContainText(
    "Please check the weather forecast for Shanghai.",
  );
  await expect(page.locator(".message-bubble.assistant").last()).toContainText(
    /Shanghai|ClawForge Phase 2 gateway baseline/,
  );
  await expect(page.getByTestId("gateway-query-block")).toContainText(
    "check weather forecast shanghai",
  );
  await expect(page.getByTestId("activated-skill-list")).toContainText("get_weather");
});
