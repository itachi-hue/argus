import * as esbuild from "esbuild";

const watch = process.argv.includes("--watch");

const common = {
  bundle: true,
  outdir: "dist",
  target: "chrome120",
  sourcemap: false,
  minify: !watch,
};

// Service worker must be ESM ("type": "module" in manifest)
const bgConfig = {
  ...common,
  entryPoints: ["src/background/index.ts"],
  format: "esm",
};

// Content, injected, and popup are classic scripts — use IIFE
// so that any test-only `export` statements are stripped from output
const classicConfig = {
  ...common,
  entryPoints: [
    "src/content/index.ts",
    "src/injected/index.ts",
    "src/popup/popup.ts",
  ],
  format: "iife",
};

if (watch) {
  const ctx1 = await esbuild.context(bgConfig);
  const ctx2 = await esbuild.context(classicConfig);
  await Promise.all([ctx1.watch(), ctx2.watch()]);
  console.log("Watching for changes...");
} else {
  await Promise.all([
    esbuild.build(bgConfig),
    esbuild.build(classicConfig),
  ]);
  console.log("Build complete.");
}
