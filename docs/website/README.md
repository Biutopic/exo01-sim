# Website package — "EXO-01 en simulation"

Everything needed for one page/article on biutopic.com (Astro, FR + /en), generated from exo01-sim v1.2 on 29 Oct 2026.

```
docs/website/
  exo01-simulation.fr.md      article, French (frontmatter: title, description, maturity, date, version, repo, lang)
  exo01-simulation.en.md      article, English
  figures.json                15 figures: file, FR/EN caption, exact simulation state behind each render
  key_numbers.json            every number quoted in the article, with its origin
  img/*.png                   renders 1920x1080 + plots (source)
  img/web/*.webp              same, 1600 px wide, 17-64 kB each (what the site should serve)
  img/renders.json            the simulator state (trim, freeboard, wave, line tensions) at the moment of each render
```

## Dropping it into the Astro site

1. Copy `img/web/*.webp` to `public/img/exo01-sim/` (or the site's image folder) and `exo01-simulation.{fr,en}.md` into the content collection used for Journal / Recherche (the markdown is plain CommonMark; the image paths are `img/web/<name>.webp` — rewrite them to the site's public path, e.g. `/img/exo01-sim/<name>.webp`).
2. Keep the maturity label (`maturity` in the frontmatter, and the status blockquote at the top): it is the claim-discipline label the article relies on. Do not strip "exploratoire / exploratory".
3. Captions: `figures.json` holds the FR/EN caption of every figure if the site renders figures from data rather than from the markdown.
4. Link target for "the code": https://github.com/Biutopic/exo01-sim (public).

## Regenerating

```
python app.py --port 8057                              # server
python scripts/render_website.py http://127.0.0.1:8057 # renders -> docs/website/img (needs Playwright + Chromium)
python scripts/run_optimisation_report.py --battery-only ; python scripts/run_comparison.py --bem   # plots
```
then rebuild `img/web` (see the Pillow snippet in the commit) and re-read the numbers in `key_numbers.json` against `results/`.

## Naming discipline (from the project)

EXO-01 (never "HYDRO-02"), L'Hydronaute (the Renaud 8000 vessel), HYDRO-01 (the BlueBoat ASV — not part of this simulation). EXO-01 is a demonstrator being assembled, not water-tested; replication claims limited to "compatible hulls after validation".
