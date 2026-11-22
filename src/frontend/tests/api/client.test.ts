import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import {
  getCorridorNow,
  getSourceStatus,
  RefreshFailedError,
  SchemaVersionMismatchError,
} from "../../src/api/client";
import { isNoData } from "../../src/api/types";
import { server } from "../setup";
import normalFixture from "../../../../contracts/read/fixtures/normal/corridor_now.json";

describe("read client", () => {
  it("returns the parsed snapshot on a valid body", async () => {
    server.use(
      http.get("/api/v1/corridor/:id/now", () => HttpResponse.json(normalFixture)),
    );
    const result = await getCorridorNow("C6-008");
    expect(isNoData(result)).toBe(false);
  });

  it("returns the no-data envelope as a first-class value", async () => {
    server.use(
      http.get("/api/v1/corridor/:id/now", () =>
        HttpResponse.json({ status: "no_data", corridor_id: "C6-008" }),
      ),
    );
    const result = await getCorridorNow("C6-008");
    expect(isNoData(result)).toBe(true);
  });

  it("surfaces a schema-version mismatch instead of rendering", async () => {
    server.use(
      http.get("/api/v1/corridor/:id/now", () =>
        HttpResponse.json({ ...normalFixture, schema_version: "2.0.0" }),
      ),
    );
    await expect(getCorridorNow("C6-008")).rejects.toBeInstanceOf(
      SchemaVersionMismatchError,
    );
  });

  it("treats a 500 as a failed refresh", async () => {
    server.use(
      http.get("/api/v1/corridor/:id/source-status", () =>
        HttpResponse.json({ error: "internal_server_error" }, { status: 500 }),
      ),
    );
    await expect(getSourceStatus("C6-008")).rejects.toBeInstanceOf(RefreshFailedError);
  });

  it("treats a malformed body as a failed refresh", async () => {
    server.use(
      http.get("/api/v1/corridor/:id/now", () =>
        HttpResponse.text("not json", { headers: { "Content-Type": "application/json" } }),
      ),
    );
    await expect(getCorridorNow("C6-008")).rejects.toBeInstanceOf(RefreshFailedError);
  });

  it("treats a non-object body as a failed refresh", async () => {
    server.use(
      http.get("/api/v1/corridor/:id/source-status", () => HttpResponse.json(42)),
    );
    await expect(getSourceStatus("C6-008")).rejects.toBeInstanceOf(RefreshFailedError);
  });
});
