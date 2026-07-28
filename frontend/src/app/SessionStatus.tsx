export function SessionStatus({
  state,
  onRetry,
}: {
  state: "loading" | "error";
  onRetry?: () => void;
}) {
  if (state === "loading") {
    return (
      <main className="session-panel session-panel--message" role="status">
        Yuklanmoqda…
      </main>
    );
  }
  return (
    <main
      className="session-panel session-panel--message"
      role="alert"
    >
      <p>Server bilan bog‘lanib bo‘lmadi.</p>
      <button type="button" onClick={onRetry}>Qayta urinish</button>
    </main>
  );
}
