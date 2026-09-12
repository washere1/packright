import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { TripStateProvider } from "./trip-state";

createRoot(document.getElementById("root")!).render(
  <StrictMode><TripStateProvider><App /></TripStateProvider></StrictMode>,
);
