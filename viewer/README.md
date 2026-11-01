# Viewer (TypeScript)

A static results viewer (Vite and TypeScript, no backend, no framework). It
lists every test case with its label and synthetic context, and each model's
three paraphrase answers under each prompt condition and image kind, with
filters for model, condition, image kind, answer format, label, abnormality
type and "answer flipped versus neutral". Selecting a case shows every model
under every condition.

It contains no images and requests none. The public build is checked for
that (`npm run check-dist`): no image files, no image references, and only the
case fields listed in `scripts/build-data.ts` (no paths, hashes or UIDs).

## Build

From `viewer/`, with Node 22.18 or later:

    npm ci
    npm run dev          # local server; generates public/data.json first
    npm run build        # -> dist/; generates public/data.json first
    npm run check-dist
    npm run lint && npm run typecheck

`npm run dev` and `npm run build` run `npm run data` first (`predev` and
`prebuild`), which reads every committed output under `runs/` (all tiers,
test split) and `data/manifests/test.csv` and writes `public/data.json`. A
fresh clone therefore works with `npm ci && npm run dev`. If the page says the
data file is missing, run `npm run data` and reload.

`public/data.json` is generated and gitignored on purpose, like `dist/`: it is
derived entirely from committed outputs, so committing it would duplicate
them (about 2 MB) and it would go stale with every new output; it also
records the commit it was built from, which a committed copy can never match.
The public build regenerates it, and `npm run check-dist` checks the built
copy (no images, only the listed case fields).

## Local images (owner only)

    VITE_LOCAL_IMAGES=1 npm run dev

shows the full mammogram and ROI crop next to each case, served by the dev
server from the local `data/png/` and `data/png_roi/` folders (or
`LOCAL_IMAGES_DIR`). This works only with the dev server; the build never
includes it. Deploy (GitHub Pages) only after the repository is public.
