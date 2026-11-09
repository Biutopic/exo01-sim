"""Dimensioned build drawing of the selected coupling arrangement -> results/coupling/selected_arrangement.png

    python scripts/draw_selected_arrangement.py [ARRANGEMENT_ID]

Plan and elevation with a schedule of points and loads beside them. Geometry comes from exo01/arrangements.py, so
the drawing cannot disagree with what the model solves; loads come from results/coupling/connection_loads.json.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from exo01 import arrangements as AR  # noqa: E402

AID = sys.argv[1] if len(sys.argv) > 1 else AR.DEFAULT
META = AR.ARRANGEMENTS[AID]
OUT = ROOT / "results" / "coupling"
try:
    CL = json.loads((OUT / "connection_loads.json").read_text())["arrangements"].get(AID, {}).get("elements", {})
except (OSError, KeyError):
    CL = {}

CFG = json.loads((ROOT / "configs" / "illustrative.json").read_text())["host_boat"]
HULL = CFG["buoyant_surface"]["stations_mm"]
CAB = CFG["clearance_reference"]["boat_cabin_stations_mm"]
DECK = CFG["buoyant_surface"]["topside_top_mm"] / 1000.0
XB, DZ = AR.X_BERTH, AR.Z_DATUM_OFFSET       # DZ converts a boat z into the EXO frame (negative: -0.15)

INK, RULE, ROPE, FEND, WHEELC, DIM = "#1b2b36", "#9fb3c0", "#b8860b", "#0d6f78", "#5c7384", "#a3322a"
WATER = "#4a90c2"

fig = plt.figure(figsize=(17.0, 9.6))
fig.patch.set_facecolor("white")
gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 0.40], height_ratios=[1.25, 1.0],
                      hspace=0.16, wspace=0.04, left=0.025, right=0.985, top=0.945, bottom=0.095)
axp, axe, axt = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[:, 1])

GEO = AR.element_geometry(AID)
ELS = {e["id"]: e for e in AR.build(AID)}


def col_of(e):
    return FEND if e["id"].startswith("BUMPER") else (WHEELC if e["id"].startswith("WHEEL") else ROPE)


# ───────────────────────────────────────────── plan
xs = [XB + p[0] / 1000 for p in HULL]
ys = [p[1] / 1000 for p in HULL]
axp.fill(xs + xs[::-1], ys + [-y for y in ys[::-1]], color="#eef3f6", ec=INK, lw=1.6, zorder=2)
axp.add_patch(Rectangle((0, -2.25), 5.20, 4.50, fill=False, ec=RULE, lw=1.6, zorder=1))
for sgn in (1, -1):
    axp.add_patch(Rectangle((0.50, sgn * 1.67 - 0.30), 4.84, 0.60, fc="#dfe8ed", ec=RULE, lw=1.0, zorder=1))

for i, e in enumerate(GEO, 1):
    a, b = e["a"], e["b"]
    legs = [(a, b)] + ([(e["a2"], b)] if e.get("a2") else [])
    for p0, p1 in legs:
        axp.plot([p0[0], p1[0]], [p0[1], p1[1]], color=col_of(e),
                 lw=6.5 if e["kind"] == "fender" else 2.4, solid_capstyle="round", zorder=4)
    for pt in [p for p, _ in legs] + [b]:
        axp.plot(pt[0], pt[1], "o", ms=5.5, mfc="white", mec=INK, mew=1.4, zorder=6)
    mx, my = 0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1])
    axp.text(mx, my, str(i), fontsize=8.5, fontweight="bold", color="white", ha="center", va="center",
             bbox=dict(boxstyle="circle,pad=0.22", fc=col_of(e), ec="white", lw=1.1), zorder=7)

axp.annotate("", xy=(0, -2.72), xytext=(5.20, -2.72), arrowprops=dict(arrowstyle="<->", color=DIM, lw=1.1))
axp.text(2.60, -2.90, "EXO frame 5,20 m", ha="center", fontsize=8.5, color=DIM)
axp.annotate("", xy=(-0.42, -2.25), xytext=(-0.42, 2.25), arrowprops=dict(arrowstyle="<->", color=DIM, lw=1.1))
axp.text(-0.56, 0, "4,50 m", rotation=90, va="center", ha="center", fontsize=8.5, color=DIM)
axp.annotate("", xy=(XB, 2.62), xytext=(XB + 8.0, 2.62), arrowprops=dict(arrowstyle="<->", color=DIM, lw=1.1))
axp.text(XB + 4.0, 2.72, "Hydronaute 8,00 m — transom at EXO x = 2,265 m", ha="center", fontsize=8.5, color=DIM)
axp.set_xlim(-0.95, 11.3); axp.set_ylim(-3.1, 3.05); axp.set_aspect("equal"); axp.axis("off")
axp.set_title(f"{AID} — plan", fontsize=11.5, color=INK, loc="left", pad=4)

# ───────────────────────────────────────────── elevation (starboard), boat z converted into the EXO frame
axe.axhline(DZ, color=WATER, lw=1.3, zorder=1)
axe.text(-0.9, DZ + 0.05, "waterline", fontsize=7.8, color=WATER)
axe.add_patch(Rectangle((XB, DZ), 8.0, DECK, fc="#eef3f6", ec=INK, lw=1.5, zorder=2))
cx = [XB + p[0] / 1000 for p in CAB]
ctop = [DZ + p[2] / 1000 for p in CAB]
axe.fill_between(cx, DZ + DECK, ctop, color="#f6f9fb", ec=INK, lw=1.2, zorder=2)
axe.text(XB + 3.3, DZ + 1.45, "cabin", fontsize=8.5, color=INK, alpha=0.45, ha="center")
axe.add_patch(Rectangle((0, -0.30), 5.20, 3.00, fill=False, ec=RULE, lw=1.4, ls=(0, (6, 4)), zorder=1))
axe.text(0.08, 2.78, "EXO envelope — 3,00 m above the waterline (Erdre air draft 3,80 m)",
         fontsize=7.8, color=DIM)
for sgn in (1,):
    axe.add_patch(Rectangle((0.50, -0.60), 4.84, 0.60, fc="#dfe8ed", ec=RULE, lw=1.0, zorder=1))

for i, e in enumerate(GEO, 1):
    a, b = e["a"], e["b"]
    for p0, p1 in [(a, b)] + ([(e["a2"], b)] if e.get("a2") else []):
        axe.plot([p0[0], p1[0]], [p0[2], p1[2]], color=col_of(e),
                 lw=6.0 if e["kind"] == "fender" else 2.2, solid_capstyle="round", zorder=4)
axe.set_xlim(-0.95, 11.3); axe.set_ylim(-0.95, 3.05); axe.set_aspect("equal"); axe.axis("off")
axe.set_title("elevation, starboard — boat heights converted into the EXO frame", fontsize=11.5, color=INK,
              loc="left", pad=4)

# ───────────────────────────────────────────── schedule
axt.axis("off")
rows = []
for i, e in enumerate(GEO, 1):
    raw = ELS[e["id"]]
    L = CL.get(e["id"], {})
    st, wv = L.get("max_abs_T_N"), L.get("wave_peak_N")
    mag = max(abs(st or 0.0), wv or 0.0)
    ex, bx = raw["exo_point_m"], raw["boat_point_m"]
    rows.append((i, e["id"], col_of(e),
                 f"({ex[0]:.2f}, {ex[1]:+.2f}, {ex[2]:.2f})",
                 f"[{bx[0]:.2f}, {bx[1]:+.2f}, {bx[2]:.2f}]",
                 f"{e['length_m']:.2f}",
                 ("—" if not mag else (f"{mag:.0f} N" + (" ·w" if (wv or 0) > abs(st or 0) else "")))))

y = 0.985
axt.text(0.0, y, "SCHEDULE", fontsize=9.5, fontweight="bold", color=INK, va="top")
y -= 0.035
for h, x in (("#", 0.0), ("element", 0.055), ("EXO point ( )", 0.27), ("boat point [ ]", 0.55), ("len", 0.83),
             ("load", 0.90)):
    axt.text(x, y, h, fontsize=7.4, color=DIM, va="top", fontweight="bold")
y -= 0.022
axt.plot([0, 1], [y, y], color=RULE, lw=0.8)
y -= 0.024
for i, eid, c, ep, bp, ln, ld in rows:
    axt.text(0.0, y, str(i), fontsize=7.4, color="white", va="top",
             bbox=dict(boxstyle="circle,pad=0.18", fc=c, ec="none"))
    axt.text(0.055, y, eid, fontsize=7.3, color=INK, va="top")
    axt.text(0.27, y, ep, fontsize=6.9, color=DIM, va="top", family="monospace")
    axt.text(0.55, y, bp, fontsize=6.9, color=DIM, va="top", family="monospace")
    axt.text(0.83, y, ln, fontsize=7.0, color=INK, va="top", family="monospace")
    axt.text(0.90, y, ld, fontsize=7.0, color=INK, va="top", family="monospace")
    y -= 0.052

y -= 0.02
axt.plot([0, 1], [y, y], color=RULE, lw=0.8)
y -= 0.035
spec = [
    ("Preload", f"{META['design_preload_N']:.0f} N on the primary elements, on an inline dynamometer"),
    ("Secondaries", f"rigged snug, about {AR.T_SNUG:.0f} N — not tensioned"),
    ("To couple", f"{META['ops_actions']} tensioning actions"),
    ("Rope", "12 mm polyester: MBL 25–30 kN against 9,5 kN required"),
    ("Watch", "the crossed stern ropes — wave-governed, amplification 4,2–4,5"),
    ("Wheels", "0 N in every static case: a stop, not a load path"),
]
for k, v in spec:
    axt.text(0.0, y, k, fontsize=7.4, color=DIM, va="top", fontweight="bold")
    axt.text(0.30, y, v, fontsize=7.4, color=INK, va="top", wrap=True)
    y -= 0.050
y -= 0.012
gate = (f"GATING — needs {META['needs_boat_fittings']} on the host boat and no cleat rating is known. "
        f"Pull-out, not shear. Verify before any powered trial (COUPLING.md §18.1)."
        if META["needs_boat_fittings"] else "Needs no fittings on the host boat.")
axt.text(0.0, y, gate, fontsize=7.6, color=DIM if not META["needs_boat_fittings"] else "#9c2f26",
         va="top", wrap=True, fontweight="bold")

fig.text(0.025, 0.052, META["title"], fontsize=10, color=INK)
fig.text(0.025, 0.030, "Exploratory: proxy hull and float surfaces, assumed contact stiffnesses, assumed boat "
                       "attachment points. Loads are a design-load note (docs/STRUCTURAL.md), not a structural "
                       "verification.", fontsize=7.8, color=DIM)
fig.text(0.025, 0.012, "·w = governed by the wave peak rather than the static envelope.",
         fontsize=7.8, color=DIM)
fig.savefig(OUT / "selected_arrangement.png", dpi=165, facecolor="white")
print(f"written {OUT/'selected_arrangement.png'}  ({AID})")
