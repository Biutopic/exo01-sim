"""Recommended layout drawing (top + side view) from the configuration geometry: fenders, lines, passenger zones,
batteries, counterweight -> docs/website/img/14_layout_{fr,en}.png (+ webp). Numbers from results/stability and
results/mooring (v1.2). Exploratory: geometry of the assembly drawing, assumed berth placement.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle, Polygon, FancyBboxPatch, Circle  # noqa: E402

cfg = json.loads((ROOT / "configs" / "illustrative.json").read_text())
OUT = ROOT / "docs" / "website" / "img"
T = {
    "fr": dict(title="EXO-01 + L'Hydronaute — implantation recommandée (modèle v1.2, exploratoire)", top="Vue de dessus", side="Vue de côté",
               deck="pont arrière", upper="plateforme haute (z 2,2 m)", nodeck="pas de pont : accès interdit", crew="zone équipage / matériel — pas de passagers\n(pas de flotteur sous les 0,5 m arrière)",
               pax_rear="passagers : 4 max au total, répartis", pax_upper="passagers : plateforme haute", batt="batteries 2 × 120 kg\nconsole au-delà du montant avant, x 5,05 m, +0,3 m", cw="",
               cab="armoire : pont arrière, centrée,\nau plus près du bateau (x 1,75)", fender="défenses / push knees\nx 2,1, y ±0,9 m, ≥ 3 kN, course ≥ 50 mm", cross="aussières croisées (poupe)", tow="aussières de remorquage → taquets milieu",
               lines="cordes ≈ 10 kN/m (snubber / nylon 12 mm), prétension 200–400 N", boat="L'Hydronaute (position d'accostage supposée)", floats="flotteurs Flofiz Ø 0,60 × 1,60 m (×6)",
               wl="flottaison à vide (batteries x 5,05) : franc-bord pont arrière 0,41 m, assiette +2,7°", pax4="4 passagers sur un bord (moitié avant) : franc-bord résiduel 0,22 m, sans lest", note="Exploratoire — géométrie du plan d'assemblage, masses déclarées ; critères ES-TRIN 19.03 utilisés en lecture, régime applicable à confirmer."),
    "en": dict(title="EXO-01 + L'Hydronaute — recommended layout (model v1.2, exploratory)", top="Top view", side="Side view",
               deck="rear deck", upper="upper platform (z 2.2 m)", nodeck="no deck: no access", crew="crew / equipment zone — no passengers\n(no float under the aft 0.5 m)",
               pax_rear="passengers: 4 max in total, spread", pax_upper="passengers: upper platform", batt="batteries 2 × 120 kg\nbracket beyond the forward post, x 5.05 m, raised 0.3 m", cw="",
               cab="cabinet: rear deck, centred,\nas close to the boat as possible (x 1.75)", fender="fenders / push knees\nx 2.1, y ±0.9 m, ≥ 3 kN, stroke ≥ 50 mm", cross="crossed stern lines", tow="tow lines → midship cleats",
               lines="lines ≈ 10 kN/m (snubber / 12 mm nylon), pretension 200–400 N", boat="L'Hydronaute (assumed berth)", floats="Flofiz floats Ø 0.60 × 1.60 m (×6)",
               wl="light-ship waterline (batteries x 5.05): rear-deck freeboard 0.41 m, trim +2.7°", pax4="4 passengers on one side (forward half): residual freeboard 0.22 m, no ballast", note="Exploratory — assembly-drawing geometry, declared masses; ES-TRIN 19.03 figures used as a reading grid, applicable regime to be confirmed."),
}
BX = 2.2          # boat stern in the EXO frame
C = dict(deck="#cfd8dc", upper="#b0bec5", float="#37474f", boat="#eceff1", pax="#43a047", crew="#e53935", nodeck="#9e9e9e", batt="#ef6c00", cw="#6d4c41", fender="#00acc1", line="#f9a825", frame="#455a64")

for lang, t in T.items():
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(13.5, 11.5), gridspec_kw=dict(height_ratios=[1.35, 1]))
    # ---------------- top view
    ax.set_aspect("equal"); ax.set_xlim(-0.6, 10.8); ax.set_ylim(-3.4, 3.4)
    for s in cfg["buoyant_surfaces"]:
        x0, x1 = s["x_span_m"]; y = s["y_m"]; r = s["radius_m"]
        nose = s["nose_length_m"]
        if s["nose_dir"] > 0:
            body = Rectangle((x0, y - r), x1 - x0 - nose, 2 * r); tip = Polygon([[x1 - nose, y - r], [x1, y - r * 0.35], [x1, y + r * 0.35], [x1 - nose, y + r]])
        else:
            body = Rectangle((x0 + nose, y - r), x1 - x0 - nose, 2 * r); tip = Polygon([[x0 + nose, y - r], [x0, y - r * 0.35], [x0, y + r * 0.35], [x0 + nose, y + r]])
        for pt in (body, tip):
            pt.set_facecolor(C["float"]); pt.set_edgecolor("k"); pt.set_alpha(0.85); ax.add_patch(pt)
    ax.text(2.9, -2.85, t["floats"], ha="center", fontsize=8, color=C["float"])
    # boat
    bow = [[BX + 8.0, 0.0]]
    hull = [[BX, -1.49], [BX + 6.2, -1.49], [BX + 7.4, -1.30], [BX + 7.95, -0.43]] + bow + [[BX + 7.95, 0.43], [BX + 7.4, 1.30], [BX + 6.2, 1.49], [BX, 1.49]]
    ax.add_patch(Polygon(hull, closed=True, facecolor=C["boat"], edgecolor="k", lw=1.2, zorder=2))
    ax.text(BX + 5.0, 0.0, t["boat"], ha="center", va="center", fontsize=9, color="#546e7a", zorder=3)
    # decks and zones
    ax.add_patch(Rectangle((0, -2.2735), 2.1, 4.547, facecolor=C["deck"], edgecolor="k", lw=1, zorder=1))
    ax.add_patch(Rectangle((0, -2.2735), 1.0, 4.547, facecolor=C["crew"], alpha=0.25, hatch="//", edgecolor=C["crew"], zorder=1.5))
    ax.add_patch(Rectangle((1.0, -1.6), 1.1, 3.2, facecolor=C["pax"], alpha=0.30, edgecolor=C["pax"], zorder=1.5))
    ax.add_patch(Rectangle((2.1, -2.2485), 1.425, 4.497, facecolor=C["upper"], alpha=0.35, edgecolor="k", ls="--", zorder=1.5))
    ax.add_patch(Rectangle((2.1, -1.6), 1.425, 3.2, facecolor=C["pax"], alpha=0.25, edgecolor=C["pax"], ls=":", zorder=1.6))
    ax.add_patch(Rectangle((3.525, -2.2485), 1.425, 4.497, facecolor=C["nodeck"], alpha=0.25, hatch="xx", edgecolor=C["nodeck"], zorder=1.5))
    ax.text(-0.5, 2.75, t["crew"], ha="left", fontsize=8, color=C["crew"], rotation=0)
    ax.text(1.3, 0.0, t["pax_rear"], ha="center", va="center", fontsize=8, color="#1b5e20", zorder=4, rotation=90)
    ax.text(2.81, 2.55, t["pax_upper"], ha="center", fontsize=8, color="#1b5e20")
    ax.text(4.24, -2.6, t["nodeck"], ha="center", fontsize=8, color="#616161")
    ax.text(1.05, -3.1, t["deck"], fontsize=8); ax.text(2.2, -3.1, t["upper"], fontsize=8)
    # posts and frame
    for x in (0.05, 2.1, 4.95):
        for y in (-2.25, 2.25):
            ax.add_patch(Circle((x, y), 0.08, facecolor=C["frame"], zorder=5))
    ax.plot([0, 4.95, 4.95, 0, 0], [-2.2735, -2.2735, 2.2735, 2.2735, -2.2735], color=C["frame"], lw=1.5, zorder=4)
    ax.plot([4.24, 4.24], [-2.2735, 2.2735], color=C["frame"], lw=2.5, zorder=4)
    # batteries, cabinet, counterweight
    for y in (-2.05, 2.05):
        ax.add_patch(Rectangle((5.05 - 0.275, y - 0.15), 0.55, 0.30, facecolor=C["batt"], edgecolor="k", zorder=6))
    ax.annotate(t["batt"], (5.05, 2.2), (6.6, 2.75), fontsize=8, color=C["batt"], arrowprops=dict(arrowstyle="->", color=C["batt"]))
    ax.add_patch(Rectangle((1.75 - 0.325, -0.225), 0.65, 0.45, facecolor="#80cbc4", edgecolor="k", zorder=6))
    ax.annotate(t["cab"], (1.75, -0.22), (2.6, -1.45), fontsize=8, color="#00695c", arrowprops=dict(arrowstyle="->", color="#00695c"), bbox=dict(fc="white", ec="none", alpha=0.8), zorder=9)
    # fenders
    for y in (-0.9, 0.9):
        ax.add_patch(FancyBboxPatch((2.08, y - 0.18), 0.12, 0.36, boxstyle="round,pad=0.01", facecolor=C["fender"], edgecolor="k", zorder=7))
    ax.annotate(t["fender"], (2.14, -0.9), (-0.5, -2.2), fontsize=8, color="#006064", arrowprops=dict(arrowstyle="->", color="#006064"))
    # lines: crossed stern lines (aft posts x 2.1, y ±2.25 -> opposite stern cleats x 2.5, y ∓1.3) and tow lines (-> midship cleats x 6.5, y ±1.35)
    for sgn in (1, -1):
        ax.plot([2.1, BX + 0.3], [sgn * 2.25, -sgn * 1.3], color=C["line"], lw=2.2, zorder=6)
        ax.plot([2.1, BX + 4.3], [sgn * 2.25, sgn * 1.35], color=C["line"], lw=2.2, zorder=6)
        for cx, cy in ((BX + 0.3, sgn * 1.3), (BX + 4.3, sgn * 1.35)):
            ax.add_patch(Circle((cx, cy), 0.07, facecolor="k", zorder=7))
    ax.text(2.45, 0.0, t["cross"], fontsize=8, color="#8d6e00", ha="left", va="center", rotation=0, zorder=8, bbox=dict(fc="white", ec="none", alpha=0.7))
    ax.text(4.6, 1.95, t["tow"], fontsize=8, color="#8d6e00", zorder=8, bbox=dict(fc="white", ec="none", alpha=0.7))
    ax.text(5.6, -1.95, t["lines"], fontsize=8, color="#8d6e00", zorder=8, bbox=dict(fc="white", ec="none", alpha=0.7))
    ax.set_title(f"{t['title']}\n{t['top']}", fontsize=11, loc="left")
    ax.set_xlabel("x [m] (EXO frame, 0 = rear deck edge)"); ax.set_ylabel("y [m]"); ax.grid(alpha=.2)
    # ---------------- side view
    ax2.set_aspect("equal"); ax2.set_xlim(-0.6, 10.8); ax2.set_ylim(-1.0, 3.3)
    wl = -0.41 + 0.0                      # rear-deck datum 0.38 m above water at light ship (batteries x 4.24): draw the waterline at z = -0.38
    ax2.axhspan(-1.0, wl, color="#1565c0", alpha=0.25, zorder=0); ax2.axhline(wl, color="#1565c0", lw=1)
    for s in cfg["buoyant_surfaces"]:
        if s["y_m"] < 0:
            continue
        x0, x1 = s["x_span_m"]; z = s["z_axis_m"]; r = s["radius_m"]
        ax2.add_patch(FancyBboxPatch((x0, z - r), x1 - x0, 2 * r, boxstyle="round,pad=0.0,rounding_size=0.25", facecolor=C["float"], edgecolor="k", alpha=0.85, zorder=2))
    ax2.add_patch(Rectangle((0, -0.03), 2.1, 0.06, facecolor=C["deck"], edgecolor="k", zorder=3))
    ax2.add_patch(Rectangle((2.1, 2.17), 1.425, 0.06, facecolor=C["upper"], edgecolor="k", zorder=3))
    ax2.plot([2.1, 4.95], [2.72, 2.72], color="#1a237e", lw=4, zorder=3)        # panels
    for x in (0.05, 2.1, 4.95):
        ax2.plot([x, x], [0, 2.72 if x > 1 else 1.1], color=C["frame"], lw=2.5, zorder=3)
    ax2.plot([4.24, 4.24], [0, 2.72], color=C["frame"], lw=3, zorder=3)
    ax2.plot([0, 4.95], [0, 0], color=C["frame"], lw=2, zorder=3); ax2.plot([0, 4.95], [2.1, 2.1], color=C["frame"], lw=1.5, zorder=3)
    # boat profile (datum: boat z 0 ~ 0.18 m below the EXO deck datum in world at the moored equilibrium -> approx)
    bz = -0.18
    ax2.add_patch(Polygon([[BX, bz - 0.55], [BX + 7.4, bz - 0.55], [BX + 8.0, bz + 0.1], [BX + 8.0, bz + 0.78], [BX, bz + 0.78]], closed=True, facecolor=C["boat"], edgecolor="k", alpha=0.6, zorder=1))
    ax2.add_patch(Rectangle((BX + 0.5, bz + 0.78), 5.6, 1.45, facecolor="#f5f5f5", edgecolor="k", alpha=0.6, zorder=1))
    # fenders at the transom, batteries, counterweight, cabinet, passengers (4 on the forward half) and crew zone
    ax2.add_patch(Rectangle((2.08, 0.05), 0.12, 0.4, facecolor=C["fender"], edgecolor="k", zorder=5))
    ax2.add_patch(Rectangle((5.05 - 0.275, 0.33), 0.55, 0.5, facecolor=C["batt"], edgecolor="k", zorder=5))
    ax2.plot([4.95, 5.33], [0.0, 0.33], color=C["frame"], lw=2.5, zorder=4); ax2.plot([4.95, 5.33], [0.33, 0.33], color=C["frame"], lw=2.5, zorder=4)   # bracket
    ax2.add_patch(Rectangle((1.75 - 0.325, 0.03), 0.65, 1.0, facecolor="#80cbc4", edgecolor="k", zorder=5))
    for i in range(4):
        x = 1.05 + 0.26 * i
        ax2.add_patch(Circle((x, 1.55), 0.11, facecolor=C["pax"], zorder=6)); ax2.plot([x, x], [0.03, 1.44], color=C["pax"], lw=4, zorder=6)
    ax2.add_patch(Rectangle((0, -0.03), 1.0, 1.1, facecolor=C["crew"], alpha=0.15, hatch="//", edgecolor=C["crew"], zorder=4))
    ax2.annotate(t["wl"], (6.0, wl), (6.0, -0.85), fontsize=8, color="#0d47a1", arrowprops=dict(arrowstyle="->", color="#0d47a1"))
    ax2.text(1.5, 1.9, t["pax4"], fontsize=8, color="#1b5e20", ha="center", bbox=dict(fc="white", ec="none", alpha=0.8), zorder=9)
    ax2.annotate("", (0.0, 0.0), (0.0, wl), arrowprops=dict(arrowstyle="<->", color="k")); ax2.text(-0.55, -0.2, "0.41 m", fontsize=8)
    ax2.set_title(t["side"], fontsize=11, loc="left"); ax2.set_xlabel("x [m]"); ax2.set_ylabel("z [m] (rear-deck datum)"); ax2.grid(alpha=.2)
    fig.text(0.01, 0.005, t["note"], fontsize=8, color="#b5651d")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(OUT / f"14_layout_{lang}.png", dpi=140); plt.close(fig)
    from PIL import Image
    im = Image.open(OUT / f"14_layout_{lang}.png").convert("RGB"); w, h = im.size
    if w > 1600:
        im = im.resize((1600, int(h * 1600 / w)), Image.LANCZOS)
    (OUT / "web").mkdir(exist_ok=True); im.save(OUT / "web" / f"14_layout_{lang}.webp", quality=85, method=6)
print("written")
