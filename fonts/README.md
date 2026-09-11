# Fonts

Only fonts whose license has been read and recorded live here (CLAUDE.md, non-negotiable 9).
Every font below reports `fsType = 0` (installable embedding permitted) in its own `OS/2`
table, and carries the Culmus font-embedding exception to the GPL, which is what allows it
to be embedded in a distributed EPUB.

| File | Family | Version | Role | License |
|---|---|---|---|---|
| `TaameyFrankCLM-Medium.ttf` | Taamey Frank CLM | 0.110 | biblical text — D2 candidate | GPL-2.0 + font-embedding exception (`LICENSE-TaameyFrankCLM.txt`) |
| `HadasimCLM-Regular.otf` | Hadasim CLM | 0.140 | **square placeholder** for commentary — D3 open | GPL-2.0 + font-embedding exception (`LICENSE-Culmus.txt`) |

`Taamey Frank CLM` is the biblical candidate because it carries the Hancock/Hudson Biblical
Hebrew OpenType layout logic, which is what positions ניקוד and טעמים without collisions.
Whether it actually stacks correctly on the Paperwhite is a **device** question (D2), not a
desktop one — see the Phase 1 human gate in `PROGRESS.md`.

`Hadasim CLM` is **not Rashi script.** It is a legible square Hebrew face standing in the
Rashi slot until D3 is decided, which is why `typography.rashi_script` is `false` in
`config/default.yaml`. Nothing in the build assumes Rashi script; the divider, the smaller
size and the dibur-hamatchil styling are what separate commentary from verse.

Inside the EPUB these are renamed to `OEBPS/fonts/biblical_hebrew.ttf` and
`OEBPS/fonts/rashi.otf` (SPEC.md §11); the repo keeps the upstream file names so the
version being shipped is never in doubt.

Sources, both fetched 2026-09-11:

- Taamey Frank CLM — <https://www.sefaria.org/static/fonts/Taamey-Frank/TaameyFrankCLM-Medium.ttf>
- Hadasim CLM, and `LICENSE-Culmus.txt` / `GNU-GPL-2.0.txt` — the Culmus 0.140 release,
  <https://sourceforge.net/projects/culmus/files/culmus/0.140/culmus-0.140.tar.gz>
