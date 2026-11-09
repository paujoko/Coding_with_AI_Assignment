import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
// Fonts are bundled, not loaded from a CDN: the demo must work offline.
import "@fontsource/host-grotesk/latin-400.css";
import "@fontsource/host-grotesk/latin-500.css";
import "@fontsource/host-grotesk/latin-600.css";
import "@fontsource/jetbrains-mono/latin-400.css";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
