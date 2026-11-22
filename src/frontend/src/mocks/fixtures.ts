import type {
  CorridorNow,
  CorridorNowResponse,
  NoDataEnvelope,
  SourceStatus,
  SourceStatusResponse,
} from "../api/types";

import normalCorridor from "../../../../contracts/read/fixtures/normal/corridor_now.json";
import normalStatus from "../../../../contracts/read/fixtures/normal/source_status.json";
import bunchingCorridor from "../../../../contracts/read/fixtures/c1_bunching/corridor_now.json";
import bunchingStatus from "../../../../contracts/read/fixtures/c1_bunching/source_status.json";
import gapCorridor from "../../../../contracts/read/fixtures/c2_gap/corridor_now.json";
import gapStatus from "../../../../contracts/read/fixtures/c2_gap/source_status.json";
import breakdownCorridor from "../../../../contracts/read/fixtures/c5_breakdown/corridor_now.json";
import breakdownStatus from "../../../../contracts/read/fixtures/c5_breakdown/source_status.json";
import outageCorridor from "../../../../contracts/read/fixtures/d1_source_outage/corridor_now.json";
import outageStatus from "../../../../contracts/read/fixtures/d1_source_outage/source_status.json";

export interface FixtureScenario {
  corridorNow: CorridorNowResponse;
  sourceStatus: SourceStatusResponse;
}

const CORRIDOR_ID = "C6-008";

export const noDataCorridorEnvelope: NoDataEnvelope = {
  status: "no_data",
  corridor_id: CORRIDOR_ID,
};

export const noDataSourceStatusEnvelope: NoDataEnvelope = {
  status: "no_data",
  corridor_id: CORRIDOR_ID,
  sources_down: [],
};

export const scenarios = {
  normal: {
    corridorNow: normalCorridor as CorridorNow,
    sourceStatus: normalStatus as SourceStatus,
  },
  c1_bunching: {
    corridorNow: bunchingCorridor as CorridorNow,
    sourceStatus: bunchingStatus as SourceStatus,
  },
  c2_gap: {
    corridorNow: gapCorridor as CorridorNow,
    sourceStatus: gapStatus as SourceStatus,
  },
  c5_breakdown: {
    corridorNow: breakdownCorridor as CorridorNow,
    sourceStatus: breakdownStatus as SourceStatus,
  },
  d1_source_outage: {
    corridorNow: outageCorridor as CorridorNow,
    sourceStatus: outageStatus as SourceStatus,
  },
  no_data: {
    corridorNow: noDataCorridorEnvelope,
    sourceStatus: noDataSourceStatusEnvelope,
  },
} satisfies Record<string, FixtureScenario>;

export type ScenarioName = keyof typeof scenarios;

export const corridorId = CORRIDOR_ID;
