function directionText(direction?: number): string | undefined {
  return direction === 1 ? "Estación → barrio" : undefined;
}

export function formatCorridorLabel(corridorId: string, direction?: number): string {
  const text = directionText(direction);
  return text ? `${corridorId} · ${text}` : corridorId;
}
