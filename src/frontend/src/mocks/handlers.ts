import { http, HttpResponse } from "msw";
import {
  corridorId,
  recommendationsResponseFixture,
  scenarios,
  type ScenarioName,
} from "./fixtures";

interface MockControl {
  scenario: ScenarioName;
  failRefresh: boolean;
}

export const mockControl: MockControl = {
  scenario: "normal",
  failRefresh: false,
};

export function setScenario(scenario: ScenarioName): void {
  mockControl.scenario = scenario;
}

export function setFailRefresh(fail: boolean): void {
  mockControl.failRefresh = fail;
}

const base = "/api/v1";

export const handlers = [
  http.get(`${base}/corridor/:corridorId/now`, () => {
    if (mockControl.failRefresh) {
      return HttpResponse.json(
        { error: "internal_server_error", correlation_id: "mock" },
        { status: 500 },
      );
    }
    return HttpResponse.json(scenarios[mockControl.scenario].corridorNow);
  }),
  http.get(`${base}/corridor/:corridorId/source-status`, () => {
    if (mockControl.failRefresh) {
      return HttpResponse.json(
        { error: "internal_server_error", correlation_id: "mock" },
        { status: 500 },
      );
    }
    return HttpResponse.json(scenarios[mockControl.scenario].sourceStatus);
  }),
  http.get(`${base}/corridor/:corridorId/recommendations`, () => {
    if (mockControl.failRefresh) {
      return HttpResponse.json(
        { error: "internal_server_error", correlation_id: "mock" },
        { status: 500 },
      );
    }
    return HttpResponse.json(recommendationsResponseFixture);
  }),
];

export { corridorId };
