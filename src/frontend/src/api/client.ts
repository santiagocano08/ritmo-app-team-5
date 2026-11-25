import type {
  CorridorNow,
  CorridorNowResponse,
  NoDataEnvelope,
  RecommendationsResponse,
  SourceStatus,
  SourceStatusResponse,
} from "./types";

const EXPECTED_SCHEMA_VERSION = "1.0.0";

export class SchemaVersionMismatchError extends Error {
  constructor(expected: string, received: unknown) {
    super(
      `Unexpected schema_version: expected "${expected}", received ${JSON.stringify(received)}`,
    );
    this.name = "SchemaVersionMismatchError";
  }
}

export class RefreshFailedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RefreshFailedError";
  }
}

function resolveBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;
  const base = configured && configured.length > 0 ? configured : "/api/v1";
  return base.replace(/\/$/, "");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNoDataBody(body: unknown): body is NoDataEnvelope {
  return isRecord(body) && body.status === "no_data" && !("as_of_ts" in body);
}

async function fetchJson(path: string): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(`${resolveBaseUrl()}${path}`, {
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new RefreshFailedError(`Backend unreachable for ${path}`);
  }

  if (!response.ok) {
    throw new RefreshFailedError(`Backend returned ${response.status} for ${path}`);
  }

  try {
    return (await response.json()) as unknown;
  } catch {
    throw new RefreshFailedError(`Malformed JSON body for ${path}`);
  }
}

function assertSchemaVersion(body: Record<string, unknown>): void {
  if (body.schema_version !== EXPECTED_SCHEMA_VERSION) {
    throw new SchemaVersionMismatchError(EXPECTED_SCHEMA_VERSION, body.schema_version);
  }
}

export async function getCorridorNow(corridorId: string): Promise<CorridorNowResponse> {
  const body = await fetchJson(`/corridor/${encodeURIComponent(corridorId)}/now`);
  if (isNoDataBody(body)) {
    return body;
  }
  if (!isRecord(body)) {
    throw new RefreshFailedError("Corridor snapshot body is not an object");
  }
  assertSchemaVersion(body);
  return body as unknown as CorridorNow;
}

export async function getSourceStatus(corridorId: string): Promise<SourceStatusResponse> {
  const body = await fetchJson(
    `/corridor/${encodeURIComponent(corridorId)}/source-status`,
  );
  if (isNoDataBody(body)) {
    return body;
  }
  if (!isRecord(body)) {
    throw new RefreshFailedError("Source-status body is not an object");
  }
  assertSchemaVersion(body);
  return body as unknown as SourceStatus;
}

export async function getRecommendations(corridorId: string): Promise<RecommendationsResponse> {
  const body = await fetchJson(
    `/corridor/${encodeURIComponent(corridorId)}/recommendations`,
  );
  if (!isRecord(body) || !Array.isArray(body.recommendations)) {
    throw new RefreshFailedError("Recommendations body is malformed");
  }
  return body as unknown as RecommendationsResponse;
}
