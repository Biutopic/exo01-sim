"""Free-body diagram and result graphs for the final EXO-01 coupling, from results/coupling/final_coupling.json.

    python scripts/draw_coupling_results.py

-> results/coupling/coupling_fbd_{fr,en}.png, coupling_graphs_{fr,en}.png
   and docs/website/img/21_coupling_fbd_{fr,en}.png, 22_coupling_graphs_{fr,en}.png (+ webp)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle, Circle, Polygon, FancyArrowPatch  # noqa: E402
from PIL import Image  # noqa: E402

R = json.loads((ROOT / "results" / "coupling" / "final_coupling.json").read_text())
OUT = ROOT / "results" / "coupling"
WEB = ROOT / "docs" / "website" / "img"
(WEB / "web").mkdir(parents=True, exist_ok=True)
G = R["geometry"]
ALPHA = np.degrees(np.arctan2(G["vee_anchor"][1], G["berth_x_m"] + G["bow_pulley_boat"][0] - G["vee_anchor"][0]))
AMP = 2 * np.cos(np.radians(ALPHA))

C = dict(ink="#17242b", mute="#6b818c", rule="#c9d6dc", hull="#eceff1",
         rope="#b26a00", bump="#2e7d32", wheel="#1565c0", drag="#7b1fa2", grid="#dde6ea")
T = {
 "fr": dict(
   fbd_title="Diagramme des forces — le bateau seul",
   fbd_sub=f"Une seule corde sur une poulie : la tension est la même dans les deux brins. Demi-angle α = {ALPHA:.1f}° → résultante arrière = {AMP:.2f} T.",
   rope="2 brins, tension T chacun", res=f"résultante arrière {AMP:.2f} T\n= réaction de poulie", bump="poussée des 2 défenses",
   wheel="roues : réaction latérale\nseulement après rattrapage du jeu", drag="traînée / poussée transmise",
   eq1="Équilibre longitudinal :", eq2="Équilibre en lacet :",
   eqa="F_défenses = {A:.2f} · T − F_demandée", eqb="M_lacet porté par les défenses ≤ F_défenses × y_défense",
   note="Le lacet n'est pratiquement pas repris par la corde : une poulie qui égalise la tension ne résiste pas au lacet au premier ordre.",
   g_title="Résultats de l'étude",
   g1="Précharge du treuil → efforts", g1x="précharge commandée T₀ [N]", g1y="effort [N]",
   g1a="tension de corde", g1b="réaction de poulie", g1c="compression arrière (total)",
   g2="Compression arrière restante selon le cas", g2x="précharge commandée T₀ [N]", g2y="défense la moins chargée [N]",
   g3="Sensibilité aux raideurs inconnues", g3x="combinaison (corde × défense × roue)", g3y="compression arrière à T₀ = 1 600 N [N]",
   g4="Jeu latéral et lacet", g4x="jeu par roue [mm]", g4y="effort de roue [N]",
   foot="Exploratoire — raideurs des éléments de contact inconnues (balayées). Poussée et résistance issues de la configuration existante."),
 "en": dict(
   fbd_title="Free-body diagram — the boat alone",
   fbd_sub=f"One rope over a pulley: the tension is the same in both legs. Half-angle α = {ALPHA:.1f}° → aft resultant = {AMP:.2f} T.",
   rope="2 legs, tension T each", res=f"aft resultant {AMP:.2f} T\n= pulley reaction", bump="push from the 2 bumpers",
   wheel="wheels: lateral reaction\nonly after the clearance is taken up", drag="drag / transmitted thrust",
   eq1="Longitudinal balance:", eq2="Yaw balance:",
   eqa="F_bumpers = {A:.2f} · T − F_demanded", eqb="yaw carried by the bumpers ≤ F_bumpers × y_bumper",
   note="The rope carries almost no yaw: a pulley that equalises the tension gives no first-order yaw restraint.",
   g_title="Study results",
   g1="Winch preload → forces", g1x="commanded preload T₀ [N]", g1y="force [N]",
   g1a="rope tension", g1b="pulley reaction", g1c="rear compression (total)",
   g2="Remaining rear compression by case", g2x="commanded preload T₀ [N]", g2y="least-loaded bumper [N]",
   g3="Sensitivity to the unknown stiffnesses", g3x="combination (rope × bumper × wheel)", g3y="rear compression at T₀ = 1,600 N [N]",
   g4="Lateral clearance and yaw", g4x="clearance per wheel [mm]", g4y="wheel force [N]",
   foot="Exploratory — contact stiffnesses unknown (swept). Thrust and resistance from the existing configuration."),
}


def save(fig, stem, lang, webnum):
    fig.savefig(OUT / f"{stem}_{lang}.png", dpi=140, bbox_inches="tight", facecolor="white")
    fig.savefig(WEB / f"{webnum}_{stem.replace('coupling_', 'coupling_')}_{lang}.png", dpi=140, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    src = WEB / f"{webnum}_{stem.replace('coupling_', 'coupling_')}_{lang}.png"
    im = Image.open(src).convert("RGB"); w, h = im.size
    if w > 1600:
        im = im.resize((1600, int(h * 1600 / w)), Image.LANCZOS)
    im.save(WEB / "web" / (src.stem + ".webp"), quality=86, method=6)


# ───────────────────────────────────────────────────── free-body diagram
def fbd(lang):
    t = T[lang]
    fig, ax = plt.subplots(figsize=(12.5, 6.6))
    ax.set_aspect("equal"); ax.set_xlim(-1.3, 11.6); ax.set_ylim(-3.4, 3.4); ax.axis("off")
    hull = [(0, -1.34), (0.25, -1.48), (4.8, -1.49), (6.9, -1.45), (7.75, -0.93), (8.0, -0.06),
            (8.0, 0.06), (7.75, 0.93), (6.9, 1.45), (4.8, 1.49), (0.25, 1.48), (0, 1.34)]
    ax.add_patch(Polygon(hull, closed=True, facecolor=C["hull"], edgecolor=C["ink"], lw=1.4, zorder=2))
    ax.text(3.2, 0.0, "L'Hydronaute", fontsize=11, color=C["mute"], ha="center", zorder=3)
    ax.add_patch(Circle((8.0, 0.0), 0.14, facecolor="white", edgecolor=C["rope"], lw=2.4, zorder=6))

    def arrow(p0, p1, col, lw=2.6):
        ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=17, color=col, lw=lw, zorder=7))

    # the two rope legs pull the pulley toward the EXO anchors (aft and outboard)
    for sgn in (+1, -1):
        arrow((8.0, 0.0), (8.0 - 2.3, sgn * 2.3 * np.tan(np.radians(ALPHA))), C["rope"])
    ax.text(6.5, 1.72, t["rope"], fontsize=9.5, color=C["rope"], ha="center")
    # resultant
    arrow((8.0, 0.0), (5.9, 0.0), "#8d4e00", lw=4.0)
    ax.text(6.9, -0.42, t["res"], fontsize=9.5, color="#8d4e00", ha="center", va="top",
            bbox=dict(fc="white", ec="none", pad=1.5))
    # bumpers push forward
    for sgn in (+1, -1):
        arrow((-0.05, sgn * 0.90), (1.55, sgn * 0.90), C["bump"])
        ax.add_patch(Rectangle((-0.28, sgn * 0.90 - 0.32), 0.24, 0.64, facecolor=C["bump"], edgecolor="k", zorder=6))
    ax.text(1.75, 1.22, t["bump"], fontsize=9.5, color=C["bump"], ha="left")
    # wheels
    for sgn in (+1, -1):
        ax.add_patch(Circle((1.20, sgn * 1.63), 0.13, facecolor=C["wheel"], edgecolor="k", zorder=6))
        arrow((1.20, sgn * 1.50), (1.20, sgn * 0.80), C["wheel"], lw=1.9)
    ax.text(1.20, -2.45, t["wheel"], fontsize=9.3, color=C["wheel"], ha="center")
    # demanded surge
    arrow((4.4, -2.05), (6.5, -2.05), C["drag"])
    ax.text(5.45, -2.42, t["drag"], fontsize=9.3, color=C["drag"], ha="center")
    # equations
    ax.text(-1.25, 3.05, t["eq1"], fontsize=10.5, color=C["ink"], weight="bold")
    ax.text(-1.25, 2.68, t["eqa"].format(A=AMP), fontsize=10.5, color=C["ink"], family="monospace")
    ax.text(-1.25, 2.26, t["eq2"], fontsize=10.5, color=C["ink"], weight="bold")
    ax.text(-1.25, 1.89, t["eqb"], fontsize=10.5, color=C["ink"], family="monospace")
    ax.text(-1.25, -3.05, t["note"], fontsize=9.2, color="#b5651d")
    ax.set_title(t["fbd_title"] + "\n" + t["fbd_sub"], fontsize=11.5, loc="left", color=C["ink"])
    save(fig, "coupling_fbd", lang, 21)


# ───────────────────────────────────────────────────── graphs
def graphs(lang):
    t = T[lang]
    fig, axs = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle(t["g_title"], fontsize=13, x=0.012, ha="left", y=0.985, color=C["ink"])

    sw = R["preload_sweep"]
    x = [r["preload_N"] for r in sw]
    ax = axs[0, 0]
    ax.plot(x, [r["rope_N"] for r in sw], "o-", color=C["rope"], lw=2, ms=4, label=t["g1a"])
    ax.plot(x, [r["pulley_N"] for r in sw], "s-", color="#8d4e00", lw=2, ms=4, label=t["g1b"])
    ax.plot(x, [r["bumper_total_N"] for r in sw], "^--", color=C["bump"], lw=2, ms=4, label=t["g1c"])
    ax.set_title(t["g1"], fontsize=10.5, loc="left"); ax.set_xlabel(t["g1x"]); ax.set_ylabel(t["g1y"])
    ax.legend(fontsize=8.5, frameon=False); ax.grid(alpha=.25)

    ax = axs[0, 1]
    for cid, col, ls in [("moored", C["mute"], "-"), ("fwd100", C["bump"], "-"), ("rev100", C["rope"], "-"),
                         ("estop", "#8d4e00", "--"), ("diff_one", C["wheel"], "-"), ("diff_opp", "#c62828", "--")]:
        c = R["cases"].get(cid)
        if not c:
            continue
        rows = [r for r in c["rows"] if r["converged"] and not r.get("unrestrained")]
        if rows:
            ax.plot([r["preload_N"] for r in rows], [r["bumper_min_N"] for r in rows], ls, color=col, lw=1.9,
                    marker="o", ms=3.4, label=cid)
    ax.axhline(0, color="#c62828", lw=1.1, ls=(0, (4, 3)))
    ax.set_title(t["g2"], fontsize=10.5, loc="left"); ax.set_xlabel(t["g2x"]); ax.set_ylabel(t["g2y"])
    ax.legend(fontsize=8, frameon=False, ncol=2); ax.grid(alpha=.25)

    ax = axs[1, 0]
    sens = R["sensitivity"]
    _c = {"soft": "So", "mid": "Mi", "stiff": "St"}
    lab = [f"{_c[s['rope']]}·{_c[s['bumper']]}·{_c[s['wheel']]}" for s in sens]
    v = [s["moored_bumper_N"] for s in sens]
    ax.bar(range(len(v)), v, color=C["bump"], alpha=.8)
    ax.set_xticks(range(len(v))); ax.set_xticklabels(lab, fontsize=6.5, rotation=90)
    ax.set_title(t["g3"], fontsize=10.5, loc="left"); ax.set_xlabel(t["g3x"]); ax.set_ylabel(t["g3y"])
    ax.grid(alpha=.25, axis="y")

    ax = axs[1, 1]
    gs_ = R["gap_scan"]
    for cse, col in [("diff_one", C["wheel"]), ("diff_opp", "#c62828")]:
        rows = [g for g in gs_ if g["case"] == cse]
        if rows:
            ax.plot([g["gap_mm"] for g in rows], [g["wheel_max_N"] for g in rows], "o-", color=col, lw=2, ms=5, label=cse)
            for g in rows:
                ax.annotate(f"{g['dyaw_deg']:+.2f}°", (g["gap_mm"], g["wheel_max_N"]), fontsize=7.5,
                            color=col, xytext=(0, 7), textcoords="offset points", ha="center")
    ax.set_title(t["g4"], fontsize=10.5, loc="left"); ax.set_xlabel(t["g4x"]); ax.set_ylabel(t["g4y"])
    ax.legend(fontsize=8.5, frameon=False); ax.grid(alpha=.25)

    fig.text(0.012, 0.004, t["foot"], fontsize=8.3, color="#b5651d")
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    save(fig, "coupling_graphs", lang, 22)


for lang in ("fr", "en"):
    fbd(lang)
    graphs(lang)
print(f"written FBD and graphs; alpha {ALPHA:.2f}°, amplification {AMP:.3f}")
