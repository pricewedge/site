import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Estimates are served from `${VITE_DATA_BASE}` (default `/data`). They are
// deliberately not part of the JS bundle: the client reads single securities out
// of the binary shards with HTTP range requests, so the site stays small no
// matter how large the panel grows.
export default defineConfig({
  plugins: [react()],
  build: { target: "es2020", sourcemap: true },
  server: { fs: { allow: [".."] } },
});
