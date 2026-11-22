import { setupWorker } from "msw/browser";
import { handlers, setFailRefresh, setScenario } from "./handlers";
import type { ScenarioName } from "./fixtures";
import { scenarios } from "./fixtures";

export const worker = setupWorker(...handlers);

export async function enableMocks(): Promise<void> {
  await worker.start({ onUnhandledRequest: "bypass" });
  installScenarioSwitcher();
}

function installScenarioSwitcher(): void {
  const container = document.createElement("div");
  container.setAttribute("data-testid", "mock-controls");
  container.style.cssText =
    "position:fixed;bottom:12px;right:12px;z-index:9999;background:#14213D;color:#fff;" +
    "padding:10px 12px;border-radius:8px;font:12px Inter,sans-serif;display:flex;gap:8px;align-items:center;";

  const select = document.createElement("select");
  for (const name of Object.keys(scenarios) as ScenarioName[]) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  }
  select.addEventListener("change", () => setScenario(select.value as ScenarioName));

  const failLabel = document.createElement("label");
  failLabel.style.cssText = "display:flex;gap:4px;align-items:center;";
  const failToggle = document.createElement("input");
  failToggle.type = "checkbox";
  failToggle.addEventListener("change", () => setFailRefresh(failToggle.checked));
  failLabel.append(failToggle, document.createTextNode("fail refresh"));

  container.append(document.createTextNode("Scenario:"), select, failLabel);
  document.body.appendChild(container);
}
