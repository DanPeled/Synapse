// SPDX-FileCopyrightText: 2026 Dan Peled
//
// SPDX-License-Identifier: GPL-3.0-or-later

import * as esbuild from "esbuild";
import { cp, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, "..");
const outDir = resolve(root, "src/synapse_sim/assets");

await mkdir(outDir, { recursive: true });

await esbuild.build({
  entryPoints: [resolve(__dirname, "renderer.js")],
  bundle: true,
  format: "esm",
  platform: "browser",
  target: ["es2020"],
  outfile: resolve(outDir, "viewer.bundle.js"),
  sourcemap: false,
  minify: false,
  define: {
    "process.env.NODE_ENV": '"production"',
  },
});

await cp(resolve(__dirname, "index.html"), resolve(outDir, "index.html"));

console.log(`Wrote ${resolve(outDir, "viewer.bundle.js")}`);
