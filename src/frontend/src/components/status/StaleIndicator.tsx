export function StaleIndicator({ stale }: { stale: boolean }) {
  if (!stale) {
    return null;
  }

  return (
    <div
      data-testid="stale-indicator"
      role="status"
      aria-live="polite"
      className="rounded-token border border-border bg-app px-4 py-2 text-sm text-text-secondary"
    >
      Sin conexión con el servidor. Mostrando la última información recibida; reintentando…
    </div>
  );
}
