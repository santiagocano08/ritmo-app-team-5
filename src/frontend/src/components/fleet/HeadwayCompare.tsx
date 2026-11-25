interface HeadwayCompareProps {
  headwayAheadS: number | null;
  headwayPlannedS: number;
}

function formatSeconds(seconds: number): string {
  return `${Math.round(seconds)} s`;
}

export function HeadwayCompare({ headwayAheadS, headwayPlannedS }: HeadwayCompareProps) {
  if (headwayAheadS === null) {
    return null;
  }

  const deviation = headwayAheadS - headwayPlannedS;
  const direction = deviation > 0 ? "over" : deviation < 0 ? "under" : "on";
  const directionLabel = direction === "over" ? "sobre el plan" : "bajo el plan";

  return (
    <div data-testid="headway-compare" data-direction={direction} className="text-sm">
      <span className="font-semibold text-text-primary">{formatSeconds(headwayAheadS)}</span>
      <span className="text-text-secondary"> vs {formatSeconds(headwayPlannedS)} del plan</span>
      <span className="ml-1 text-text-secondary">
        {direction === "on" ? (
          "(en el plan)"
        ) : (
          <>
            ({deviation > 0 ? "+" : "−"}
            {formatSeconds(Math.abs(deviation))} {directionLabel})
          </>
        )}
      </span>
    </div>
  );
}
