# Handoff — "Méthodologie EXO-01" for biutopic.com (Recherche)

For the session working on the biutopic.com Astro site. This folder is self-contained; nothing here needs the
simulator repository to build or run.

Source of truth: **github.com/Biutopic/exo01-sim** (public), `docs/website/`. Generated 30 Oct 2026 from
exo01-sim v1.2.1. Regenerate with `python scripts/build_methodology_page.py` and `python scripts/draw_methodology.py`.

---

## What this is

A methodology page for the Recherche section: how EXO-01 — a floating platform that clips onto an existing boat — is
simulated before launch, and what the resulting figures are worth. It is the companion to the existing article
`exo01-simulation.{fr,en}.md` ("EXO-01 en simulation"), which reports *what the model found*. This one covers *how*.

Two forms are provided. **Ship the interactive one if the site can host a static HTML page**; it is the better page.

### A. `methodologie-interactive.html` — interactive, bilingual, one file (269 kB)

Self-contained: inline CSS and JS, images embedded as data URIs. The only outside request is the Google Fonts
stylesheet (Archivo, Newsreader, IBM Plex Mono). No framework, no bundler, no build step.

Six sections: the calculation chain · a node graph of the system with three flow walkthroughs · the mooring force laws
with a slider · the simulator's own renders in waves · what is left to measure · the verification numbers.

Interactive, not decorative:
- **§02** 16 parts of the system in six clusters, with labelled edges. Three flows (*Eau calme*, *Calcul en houle*,
  *Étude d'amarrage*) light their path and dim the rest. Clicking a part shows what it does and its real file count.
  The graph scrolls horizontally below ~900 px — it is inside its own `overflow-x:auto` container, the page body never
  scrolls sideways.
- **§03** a slider moves the boat −60 → +60 mm; the three link types (rope, fender, rigid tube) show their force law,
  the load in newtons and their state (slack / no contact / in tension) live.
- **§05** measurement cards light on hover or tap.

**FR/EN toggle in the header.** The choice is kept per viewer in `localStorage` (wrapped in try/catch; the page renders
correctly without it). One URL therefore serves both languages. To pin a language instead, set `L` at the top of the
script and remove the toggle markup.

**Integration options, easiest first:**
1. Copy the file to `public/recherche/methodologie-exo01/index.html` and link to it. Zero changes.
2. Paste its `<title>`, `<style>`, markup and `<script>` into a `.astro` page. Everything is plain HTML/CSS/JS; the only
   thing to check is that the site's global CSS does not override `body`, `h1`–`h3` or `.chip`. The page defines its own
   tokens on `:root`, so it also follows the site's light/dark setting via `prefers-color-scheme` and
   `data-theme="light"` / `data-theme="dark"` on the root element.
3. If the site has a strict CSP, the inline `<script>` and `<style>` need a nonce or hash.

Accessibility: keyboard-reachable graph nodes, visible focus states, `prefers-reduced-motion` respected.

### B. `methodologie.fr.md` / `methodology.en.md` — static articles

Plain CommonMark with frontmatter (`title`, `description`, `maturity`, `date`, `version`, `repo`, `lang`), matching the
existing article's shape. Image paths are `img/web/<name>.webp` — rewrite them to the site's public path. Use these if
the site's content collection is the only route, or as the printable/RSS version alongside the interactive page.

They reference the five figures in `img/`, in `_fr` and `_en` variants. **The text inside each figure is translated, so
serve `_fr` on the French page and `_en` on `/en`.** `methodology_figures.json` has every caption in both languages plus
what each figure is built from, if the site renders figures from data.

### `img/`

- `15_method_chain` · `16_claim_discipline` · `17_element_kinds` · `18_model_boundary` · `19_verification`, each
  `_fr` and `_en`, 1600 px webp, 64–89 kB. These belong to the static articles.
- `01_moored_still_iso` · `09_exo_alone_iso` · `02_moored_still_top` · `04_beam_sea_max_roll` · `13_rao_comparison` —
  simulator renders, already embedded inside the interactive page. Included here in case the site wants them separately
  (social card, teaser, Recherche index thumbnail).

---

## Editorial rules that must survive editing

1. **Keep the `maturity` frontmatter and the footer status line.** Every figure also carries the exploratory label in its
   own footer. The page's credibility rests on stating its own status; a version that strips the label makes a stronger
   claim than the work supports.
2. **Verification ≠ validation.** The numbers in §06 and in figure 19 show that the code solves its equations correctly
   (residuals ~10⁻¹⁵, enforced symmetry, mesh convergence 1.5 % / 5.6 %). They say nothing about whether the inputs are
   right. The page says so once, in the footer. Do not let a caption or a pull quote turn these into proof that the
   platform behaves as modelled.
3. **Do not add caveats.** An earlier draft repeated the limitation in every section and read as defensive. The limits
   now appear once as the measurement programme in §05 — which is the confident form of the same information. Keep that
   balance.
4. **Naming.** EXO-01 (never "HYDRO-02"). L'Hydronaute is the Renaud 8000 vessel. HYDRO-01 is the BlueBoat ASV and is
   not part of this simulation. EXO-01 is a demonstrator being assembled, not water-tested.
5. **Figures are generated, not drawn by hand.** Every number in figure 19 and in §06 is read from
   `results/verification/verification_report.json` at build time. If a check changes, regenerate — do not edit a caption.

---

## Why this page sits in Recherche

It documents the R&D work itself rather than its results: the technical uncertainties that were open (where to put the
masses, how to couple the two hulls, whether a linear mooring model is adequate), the systematic work done to resolve
them, the tooling built for it, and the verification evidence — all dated, versioned, and traceable to a public
repository with its full history. That is the kind of record an R&D claim is assessed on, and it is also simply the
honest way to publish figures from a craft that has not yet floated.

Three things make it checkable by a third party: the repository is public and the commit history is intact; every
quoted figure has a generating script in it; and the assumptions are held in a versioned `ASSUMPTIONS.md` rather than
in prose. Whether and how it is used in a CIR/CII file is for BIUTOPIC and its accountant to decide — this note only
describes what the page contains.

---

## Suggested placement

Recherche → a child page of the existing "EXO-01 en simulation" article, titled **Méthodologie** / **Methodology**,
linked from that article's "Méthode" section (which can then be shortened to a paragraph pointing here). Suggested
slugs: `/recherche/exo01-methodologie` and `/en/research/exo01-methodology`.

Questions on content or on regenerating anything: the simulator repository, or the session that produced this.
