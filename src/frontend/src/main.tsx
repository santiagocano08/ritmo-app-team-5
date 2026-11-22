import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./styles/index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
});

async function bootstrap(): Promise<void> {
  if (import.meta.env.VITE_ENABLE_MOCKS === "true") {
    const { enableMocks } = await import("./mocks/browser");
    await enableMocks();
  }

  const rootElement = document.getElementById("root");
  if (!rootElement) {
    throw new Error("Root element #root not found");
  }

  createRoot(rootElement).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </StrictMode>,
  );
}

void bootstrap();
