import { createReadStream, existsSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig, type Plugin } from "vite";

// Local only: with VITE_LOCAL_IMAGES=1, `npm run dev` serves the owner's master
// PNGs from LOCAL_IMAGES_DIR (default: the repository's data/ folder). The
// plugin applies to the dev server only, so the public build never contains
// or requests an image.
function localImages(): Plugin {
  const dir = process.env.LOCAL_IMAGES_DIR ?? resolve(import.meta.dirname, "..", "data");
  const folders: Record<string, string> = { full: "png", roi: "png_roi" };
  return {
    name: "local-images",
    apply: "serve",
    configureServer(server) {
      if (process.env.VITE_LOCAL_IMAGES !== "1") return;
      server.middlewares.use((req, res, next) => {
        const m = /^\/local-images\/(full|roi)\/(P_\d{5}_(?:LEFT|RIGHT)_MLO)\.png$/.exec(req.url ?? "");
        const path = m ? resolve(dir, folders[m[1]], `${m[2]}.png`) : "";
        if (!m || !existsSync(path)) return next();
        res.setHeader("Content-Type", "image/png");
        createReadStream(path).pipe(res);
      });
    },
  };
}

export default defineConfig({
  base: "./",
  plugins: [localImages()],
  build: {
    assetsInlineLimit: 0,
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, "index.html"),
        about: resolve(import.meta.dirname, "about.html"),
      },
    },
  },
});
