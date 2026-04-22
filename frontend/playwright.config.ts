import { defineConfig } from "@playwright/test";

const backendCommand =
  "powershell -Command \"& 'D:\\develop\\miniconda3\\envs\\mini-claw\\python.exe' -m uvicorn backend.app:app --host 127.0.0.1 --port 8002\"";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: "http://127.0.0.1:3000",
    channel: "msedge",
    headless: true,
  },
  webServer: [
    {
      command: backendCommand,
      cwd: "D:\\develop\\Code\\python\\AgentLearning\\OpenClaw\\ClawForge",
      url: "http://127.0.0.1:8002/api/health",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "npm run dev",
      cwd: "D:\\develop\\Code\\python\\AgentLearning\\OpenClaw\\ClawForge\\frontend",
      env: {
        NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8002/api",
      },
      url: "http://127.0.0.1:3000",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
