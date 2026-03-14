import * as esbuild from "esbuild";

const watch = process.argv.includes("--watch");

const config = {
  entryPoints: [
    "src/background/index.ts",
    "src/content/index.ts",
    "src/injected/index.ts",
    "src/popup/popup.ts",
  ],
  bundle: true,
  outdir: "dist",
  format: "esm",
  target: "chrome120",
  sourcemap: false,
  minify: !watch,
};

if (watch) {
  const ctx = await esbuild.context(config);
  await ctx.watch();
  console.log("Watching for changes...");
} else {
  await esbuild.build(config);
  console.log("Build complete.");
}





