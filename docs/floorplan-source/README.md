# Floorplan source

The hand-written half of the Floorplan map (github.com/haydenschmitty/floorplan), kept here because
`floorplan/` ignores itself and is never committed.

- `architecture.json` — the parts of the system, what each is for, the flows and the guided tour.
- `descriptions/*.json` — a plain-language name and one-line description for all 53 source files and 21 server endpoints.
- `recent-work.json` — what was last worked on, framed against what was asked, so the map highlights it.

To rebuild the map on a machine that has the plugin:

```
claude plugin marketplace add haydenschmitty/floorplan
claude plugin install floorplan@floorplan
cp -r docs/floorplan-source/* floorplan/        # restore the hand-written half
# then ask Claude Code to "update the floorplan", or run the skill's build.mjs
node floorplan/serve.mjs                        # open it at http://127.0.0.1:4378
```

A second, static map of the same codebase (different tool, no server) is in `docs/codemap/`.
