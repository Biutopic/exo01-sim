# Methodology package — "Méthodologie / Methodology"

A self-contained visual section for biutopic.com, FR + EN, generated from exo01-sim v1.2.1 on 30 Oct 2026.
It is a companion to the main article (`exo01-simulation.{fr,en}.md`), not a replacement: the article says what the
model found, this page says how it was made and what it is worth.

```
docs/website/
  methodologie.fr.md            article FR (frontmatter: title, description, maturity, date, version, repo, lang)
  methodology.en.md             article EN
  methodology_figures.json      the 10 figures: file, FR/EN caption, what the figure is built from
  img/1{5..9}_*_{fr,en}.png     source renders, 1960 px wide
  img/web/1{5..9}_*_{fr,en}.webp  what the site should serve, 1600 px, 64–89 kB each
```

## The five figures

| id | what it carries | why it is in the package |
|---|---|---|
| `15_method_chain` | the five calculation stages, with a provenance dot per stage and the design-sweep loop | answers "where does a number come from" |
| `16_claim_discipline` | baseline vs illustrative; what becomes of a measured / assumed / missing input | the claim-discipline argument, in one picture |
| `17_element_kinds` | force-vs-elongation law of a rope, a fender and a rigid tube | why the mooring conclusions are not a linear-spring artefact |
| `18_model_boundary` | inside the model / outside the model, with the reason for each exclusion | the limits, stated before anyone has to ask |
| `19_verification` | the six families of checks with their measured errors, and what they do not prove | the evidence, and its ceiling |

## Dropping it into the Astro site

1. Copy `img/web/1{5..9}_*.webp` to the same folder the main article's images already use (e.g. `public/img/exo01-sim/`)
   and rewrite the image paths in the markdown from `img/web/<name>.webp` to the site's public path.
2. Serve the `_fr` figures on the FR page and the `_en` figures on `/en` — the text inside the figures is translated,
   so a shared image would break the language.
3. **Keep the maturity label** (`maturity` in the frontmatter and the status blockquote at the top). The whole point of
   this page is the claim discipline; stripping its own label would be self-refuting.
4. `methodology_figures.json` holds the FR/EN caption of every figure if the site renders figures from data rather than
   from the markdown, plus what each figure is built from.
5. Suggested placement: a sibling page of the main article ("Méthodologie" / "Methodology") linked from the article's
   "Méthode" section, rather than a replacement for it.

## Regenerating

```
python scripts/draw_methodology.py        # 5 figures x 2 languages -> docs/website/img (+ web/)
```

Figure 19 reads every number it prints from `results/verification/verification_report.json` at run time, and the test
count is a constant at the top of the script (`N_TESTS`) — update it with `python -m pytest --collect-only`. Nothing in
the figures is typed from memory; if a check changes, re-run the script rather than editing a caption.

## Claim discipline (applies to this package too)

Every figure carries the exploratory label in its footer, with the version and the repository. The numbers in figure 19
are verification results (the code solves its equations correctly), not validation results (the inputs are right) —
figure 19's own footer says so, and that distinction should survive any editing of the captions.

## Interactive version

`methodologie-interactive.html` is the same five sections as one self-contained interactive page, FR/EN toggle in the
header (the choice is remembered per viewer in `localStorage`). No build step, no external JS; the only outside request
is the Google Fonts stylesheet.

Three things on it are interactive rather than animated:

- **§03** a slider moves the boat relative to the platform; the three force laws, the loads in newtons and the state of
  each element (slack / no contact / in tension) follow it live. At +34 mm the rope reads 400 N, which is the working
  pretension the mooring study settled on.
- **§04** picking a measurement lights the limits it would lift, and names the three that no planned measurement lifts.
- **§01** and **§05** replay their sequence on demand; both are complete and readable at rest.

**To embed in Astro**: serve it as a static page (copy the file into `public/` and link it), or inline its `<style>`,
markup and `<script>` into a `.astro` page — it uses no framework and no bundler. The language toggle replaces the need
for two URLs, so it sits equally under `/methodologie` and `/en/methodology`; if the site prefers one language per URL,
read the `exo-lang` key or set `L` at the top of the script and drop the toggle.

Numbers in §05 are the same verification results as figure 19 and are written into the page's `CHECKS` array — if the
verification report changes, update both (`scripts/draw_methodology.py` regenerates the figure; the array is by hand).
