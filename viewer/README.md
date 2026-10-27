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
    npm run data         # runs/ and data/manifests/test.csv -> public/data.json
    npm run build        # -> dist/
    npm run check-dist
    npm run lint && npm run typecheck

`public/data.json` and `dist/` are generated and not committed. The viewer
reads whatever outputs are committed under `runs/`.

## Local images (owner only)

    VITE_LOCAL_IMAGES=1 npm run dev

shows the full mammogram and ROI crop next to each case, served by the dev
server from the local `data/png/` and `data/png_roi/` folders (or
`LOCAL_IMAGES_DIR`). This works only with the dev server; the build never
includes it. Deploy (GitHub Pages) only after the repository is public.
