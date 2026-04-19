import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Dev proxy: forwards /api/* and all backend paths to FastAPI.
    // Adjust target to your FastAPI host:port.
    // Remove if serving from same origin.
    proxy: {
      "/health":        { target: "http://localhost:8000", changeOrigin: true },
      "/llm":           { target: "http://localhost:8000", changeOrigin: true },
      "/org":           { target: "http://localhost:8000", changeOrigin: true },
      "/nodes":         { target: "http://localhost:8000", changeOrigin: true },
      "/thrall":        { target: "http://localhost:8000", changeOrigin: true },
      "/approvals":     { target: "http://localhost:8000", changeOrigin: true },
      "/events":        { target: "http://localhost:8000", changeOrigin: true },
      "/messages":      { target: "http://localhost:8000", changeOrigin: true },
      "/context":       { target: "http://localhost:8000", changeOrigin: true },
      "/chiefs":        { target: "http://localhost:8000", changeOrigin: true },
      "/departments":   { target: "http://localhost:8000", changeOrigin: true },
      "/agents":        { target: "http://localhost:8000", changeOrigin: true },
      "/sandbox":       { target: "http://localhost:8000", changeOrigin: true },
      "/logs":          { target: "http://localhost:8000", changeOrigin: true },
      "/admin":         { target: "http://localhost:8000", changeOrigin: true },
      "/config":        { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    // If serving from FastAPI static files, set base to "" or "/" accordingly
    // base: "/",
  },
});
