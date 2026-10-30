"""Methodology figures for the website (FR + EN): the calculation chain, the two-track claim discipline, the mooring
element laws, the boundary of the model, and the verification evidence.

    python scripts/draw_methodology.py

-> docs/website/img/{15_method_chain,16_claim_discipline,17_element_kinds,18_model_boundary,19_verification}_{fr,en}.png
   (+ webp 1600 px in docs/website/img/web/)

Every number quoted in figure 19 is read from results/verification/verification_report.json and the test count below;
nothing in these figures is drawn from memory.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle  # noqa: E402
from PIL import Image  # noqa: E402

OUT = ROOT / "docs" / "website" / "img"
(OUT / "web").mkdir(parents=True, exist_ok=True)
VER = json.loads((ROOT / "results" / "verification" / "verification_report.json").read_text())
N_TESTS = 89          # python -m pytest --collect-only  (v1.2.1, 30 Oct 2026)
N_CHECKS = len(VER["checks"])
N_PASSED = sum(1 for c in VER["checks"] if c["passed"])

C = dict(ink="#263238", mute="#78909c", rule="#cfd8dc", panel="#f7f9fa",
         measured="#2e7d32", declared="#f9a825", assumed="#e65100", out="#c62828",
         step="#eceff1", stepline="#455a64", accent="#00838f", line="#1e88e5", fender="#00acc1", strut="#6d4c41")
LAB = "Exploratoire — géométrie du plan d'assemblage, masses déclarées. exo01-sim v1.2.1 · github.com/Biutopic/exo01-sim"
LAB_EN = "Exploratory — assembly-drawing geometry, declared masses. exo01-sim v1.2.1 · github.com/Biutopic/exo01-sim"


def save(fig, name, lang, foot):
    fig.text(0.008, 0.006, foot, fontsize=7.6, color=C["mute"])
    fig.savefig(OUT / f"{name}_{lang}.png", dpi=140, facecolor="white")
    plt.close(fig)
    im = Image.open(OUT / f"{name}_{lang}.png").convert("RGB")
    w, h = im.size
    if w > 1600:
        im = im.resize((1600, int(h * 1600 / w)), Image.LANCZOS)
    im.save(OUT / "web" / f"{name}_{lang}.webp", quality=86, method=6)


def box(ax, x, y, w, h, title, body, fc, ec, tsize=10, bsize=8.3, tc=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                facecolor=fc, edgecolor=ec, linewidth=1.3, zorder=3))
    ax.text(x + 0.022, y + h - 0.035, title, fontsize=tsize, weight="bold", color=tc or C["ink"], va="top", zorder=4)
    if body:
        ax.text(x + 0.022, y + h - 0.035 - 0.052, body, fontsize=bsize, color=C["ink"], va="top", zorder=4, linespacing=1.45)


def arrow(ax, p0, p1, color=None, lw=1.6, style="-|>"):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=13,
                                 color=color or C["stepline"], lw=lw, zorder=2,
                                 shrinkA=2, shrinkB=2))


# ───────────────────────────────────────────────────────────── 15 · the calculation chain
T15 = {
 "fr": dict(
   title="Comment un chiffre est produit",
   sub="La chaîne de calcul d'exo01-sim. Chaque étape est vérifiable séparément ; chaque entrée porte sa provenance.",
   steps=[
     ("1 · Géométrie", "Six flotteurs Flofiz Ø 0,60 × 1,60 m\nen deux rangées, structure\naluminium du plan d'assemblage.\nLa coque de L'Hydronaute est\nreconstituée à partir de sections."),
     ("2 · Masses", "18 postes, 856 kg à vide.\nChaque masse porte sa source.\nUne masse manquante arrête\nle calcul — elle n'est pas devinée."),
     ("3 · Hydrostatique", "Surfaces triangulées coupées par\nle plan d'eau : volume immergé,\ncentre de carène, flottaison.\nÉquilibre (tirant d'eau, gîte,\nassiette) résolu par Newton."),
     ("4 · Hydrodynamique", "Théorie potentielle (Capytaine 3.0),\n12 degrés de liberté couplés\nEXO-01 + bateau. Masse ajoutée,\namortissement de rayonnement,\nefforts de houle."),
     ("5 · Réponse & liaisons", "Mouvements en houle, accélérations\nde pont, effort dans chaque aussière\net défense. Vérification en domaine\ntemporel : mou et pics de reprise."),
   ],
   outs="Franc-bord · gîte · assiette · GM · mouvements en houle · tension des aussières · vitesse · jeu à la poupe",
   prov="Provenance de chaque entrée :", pm="relevé sur plan", pd="déclaré (fournisseur, atelier)", pa="hypothèse versionnée",
   loop="Balayages de conception : position des batteries, arrangement des aussières — le tableau complet est publié, pas seulement le « meilleur » choix.",
   verif="31 contrôles automatiques + 89 tests à chaque modification du code"),
 "en": dict(
   title="How a number is produced",
   sub="The exo01-sim calculation chain. Each stage is separately verifiable; every input carries its provenance.",
   steps=[
     ("1 · Geometry", "Six Flofiz floats Ø 0.60 × 1.60 m\nin two rows, aluminium frame\nfrom the assembly drawing.\nL'Hydronaute's hull is rebuilt\nfrom a table of sections."),
     ("2 · Masses", "18 items, 856 kg light ship.\nEvery mass carries its source.\nA missing mass stops the\ncalculation — it is not guessed."),
     ("3 · Hydrostatics", "Triangulated surfaces cut by the\nwater plane: immersed volume,\ncentre of buoyancy, waterplane.\nEquilibrium (draft, heel, trim)\nsolved by Newton."),
     ("4 · Hydrodynamics", "Potential flow (Capytaine 3.0),\n12 coupled degrees of freedom\nEXO-01 + boat. Added mass,\nradiation damping, wave\nexcitation."),
     ("5 · Response & links", "Motion in waves, deck accelerations,\nload in every line and fender.\nTime-domain check: slack and\nsnatch peaks."),
   ],
   outs="Freeboard · heel · trim · GM · motion in waves · line tension · speed · transom gap",
   prov="Provenance of every input:", pm="read off the drawing", pd="declared (supplier, workshop)", pa="versioned assumption",
   loop="Design sweeps: battery position, mooring arrangement — the full table is published, not only the \u201cbest\u201d choice.",
   verif="31 automatic checks + 89 tests on every change to the code"),
}

for lang, t in T15.items():
    fig = plt.figure(figsize=(14, 7.2))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.text(0.022, 0.955, t["title"], fontsize=17, weight="bold", color=C["ink"])
    ax.text(0.022, 0.912, t["sub"], fontsize=9.6, color=C["mute"])
    PROV = [[C["measured"], C["declared"]], [C["declared"], C["assumed"]], [C["measured"]], [C["assumed"]], [C["assumed"]]]
    w, gap = 0.160, 0.038
    x0, y0, h = 0.022, 0.46, 0.355
    for i, (ttl, body) in enumerate(t["steps"]):
        x = x0 + i * (w + gap)
        box(ax, x, y0, w, h, ttl, body, C["step"], C["stepline"], tsize=10.5, bsize=8.1)
        for j, col in enumerate(PROV[i]):
            ax.add_patch(Rectangle((x + 0.022 + j * 0.022, y0 + 0.028), 0.014, 0.019, facecolor=col, edgecolor="none", zorder=6))
        if i:
            arrow(ax, (x - gap + 0.011, y0 + h / 2), (x - 0.011, y0 + h / 2), lw=1.8)
    # provenance key, on one line under the chain
    ax.text(0.125, 0.405, t["prov"], fontsize=9.4, weight="bold", color=C["ink"], va="center")
    kx = 0.125 + 0.0105 * len(t["prov"]) + 0.012
    for col, lab in [(C["measured"], t["pm"]), (C["declared"], t["pd"]), (C["assumed"], t["pa"])]:
        ax.add_patch(Rectangle((kx, 0.396), 0.014, 0.019, facecolor=col, edgecolor="none"))
        ax.text(kx + 0.021, 0.405, lab, fontsize=9, color=C["ink"], va="center")
        kx += 0.021 + 0.0092 * len(lab) + 0.028
    # outputs band
    box(ax, 0.022, 0.175, 0.956, 0.165, "", "", "#e8f5e9", C["measured"])
    ax.text(0.042, 0.315, ("Sorties" if lang == "fr" else "Outputs"), fontsize=10.5, weight="bold", color="#1b5e20", va="top")
    ax.text(0.042, 0.268, t["outs"], fontsize=9.4, color=C["ink"], va="top")
    ax.text(0.042, 0.215, t["verif"], fontsize=8.8, color="#1b5e20", va="top", style="italic")
    arrow(ax, (0.085, 0.455), (0.085, 0.345))
    # design-sweep loop, drawn in the clear band between the chain and the key
    ax.add_patch(FancyArrowPatch((0.935, 0.437), (0.22, 0.437), arrowstyle="-|>", mutation_scale=12,
                                 color=C["accent"], lw=1.4, ls=(0, (5, 3)), zorder=6))
    ax.text(0.022, 0.105, t["loop"], fontsize=9, color=C["accent"], va="top")
    save(fig, "15_method_chain", lang, LAB if lang == "fr" else LAB_EN)


# ───────────────────────────────────────────────────────────── 16 · claim discipline
T16 = {
 "fr": dict(title="Pourquoi certains chiffres n'existent pas",
   sub="Le simulateur tourne sur deux configurations parallèles. C'est le mécanisme qui empêche une hypothèse de devenir une caractéristique.",
   a_t="Configuration « baseline »", a_b="Les entrées inconnues restent vides.\n\nSi une masse, une position ou une\ncote manque, le calcul ne la remplace\npar rien : il répond\n\n        « non calculé ».\n\nAucun chiffre ne sort d'un trou.",
   b_t="Configuration « illustrative »", b_b="Les mêmes trous sont comblés par\ndes hypothèses explicites, chacune\nécrite dans ASSUMPTIONS.md avec\nsa justification et sa date.\n\nTout résultat qui en sort porte\nl'étiquette « exploratoire ».\n\nChaque hypothèse est datée : une\nmesure la remplace, elle ne la\nconfirme pas.",
   q="Que devient un chiffre ?",
   r1="Entrée mesurée ou déclarée →", r1b="chiffre utilisable pour l'intégration",
   r2="Entrée hypothétique →", r2b="ordre de grandeur, étiqueté, à confirmer par l'essai",
   r3="Entrée absente →", r3b="« non calculé » — jamais une valeur par défaut",
   foot="Conséquence pratique : avant le pesage réel et l'essai de stabilité, aucun chiffre de ce modèle n'est une caractéristique du bateau.\nIls servent à orienter la construction et à préparer les essais — c'est leur seul usage légitime."),
 "en": dict(title="Why some numbers do not exist",
   sub="The simulator runs on two parallel configurations. This is the mechanism that stops an assumption becoming a characteristic.",
   a_t="\u201cBaseline\u201d configuration", a_b="Unknown inputs are left empty.\n\nIf a mass, a position or a dimension\nis missing, the calculation puts\nnothing in its place: it answers\n\n        \u201cnot computed\u201d.\n\nNo number comes out of a hole.",
   b_t="\u201cIllustrative\u201d configuration", b_b="The same holes are filled with\nexplicit assumptions, each written\ninto ASSUMPTIONS.md with its\nreasoning and its date.\n\nEverything that comes out carries\nthe label \u201cexploratory\u201d.\n\nEvery assumption is dated: a\nmeasurement replaces it, it does\nnot confirm it.",
   q="What becomes of a number?",
   r1="Measured or declared input →", r1b="usable figure for the integration work",
   r2="Assumed input →", r2b="order of magnitude, labelled, to be confirmed by trial",
   r3="Missing input →", r3b="\u201cnot computed\u201d — never a default value",
   foot="What this means in practice: before the real weighing and the inclining test, no number from this model is a characteristic of the craft.\nThey exist to steer the build and prepare the trials — that is their only legitimate use."),
}

for lang, t in T16.items():
    fig = plt.figure(figsize=(13, 7.2))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.text(0.03, 0.95, t["title"], fontsize=17, weight="bold", color=C["ink"])
    ax.text(0.03, 0.905, t["sub"], fontsize=9.6, color=C["mute"])
    box(ax, 0.03, 0.47, 0.44, 0.39, t["a_t"], t["a_b"], "#eceff1", C["stepline"], tsize=11.5, bsize=9.2)
    box(ax, 0.53, 0.47, 0.44, 0.39, t["b_t"], t["b_b"], "#fff8e1", C["declared"], tsize=11.5, bsize=9.2)
    ax.text(0.03, 0.405, t["q"], fontsize=11.5, weight="bold", color=C["ink"])
    rows = [(C["measured"], t["r1"], t["r1b"]), (C["declared"], t["r2"], t["r2b"]), (C["out"], t["r3"], t["r3b"])]
    for i, (col, left, right) in enumerate(rows):
        y = 0.34 - i * 0.062
        ax.add_patch(Rectangle((0.03, y - 0.004), 0.006, 0.034, facecolor=col, edgecolor="none"))
        ax.text(0.048, y + 0.013, left, fontsize=9.8, color=col, weight="bold", va="center")
        ax.text(0.345, y + 0.013, right, fontsize=9.8, color=C["ink"], va="center")
    ax.plot([0.03, 0.97], [0.145, 0.145], color=C["rule"], lw=1)
    ax.text(0.03, 0.115, t["foot"], fontsize=9.2, color=C["ink"], va="top", linespacing=1.6)
    save(fig, "16_claim_discipline", lang, LAB if lang == "fr" else LAB_EN)


# ───────────────────────────────────────────────────────────── 17 · element kinds
T17 = {
 "fr": dict(title="Les trois façons de relier EXO-01 au bateau",
   sub="Chaque liaison du modèle a une loi de comportement. C'est ce qui sépare un amarrage qui tient d'un amarrage qui claque.",
   k=[("Aussière", "ne travaille qu'en traction", "Au-delà de sa longueur au repos elle tire.\nEn deçà elle est molle et ne transmet rien.\nLe mou suivi d'une reprise brutale est\nle danger : il est cherché en domaine\ntemporel, pas estimé."),
      ("Défense / push knee", "ne travaille qu'en compression", "Ne transmet un effort que si les deux corps\nse rapprochent assez pour la comprimer.\nC'est elle qui encaisse la poussée des pods ;\nsans elle, toutes les aussières filant vers\nl'avant, le bateau recule."),
      ("Tube rigide", "travaille dans les deux sens", "Pas de mou possible, donc pas de reprise.\nEn contrepartie l'effort alterné passe\nentièrement dans le tube et ses rotules,\net la liaison ne se largue plus à la main.")],
   xl="allongement", yl="effort", comp="compression", trac="traction", slack="mou", slack2="pas de contact",
   foot="Les amortisseurs (snubber caoutchouc, cartouche élastomère) n'entrent dans le modèle que comme une raideur plus faible :\nleur dissipation n'est pas modélisée. Le gain démontré est donc une raideur plus douce, pas une absorption d'énergie."),
 "en": dict(title="The three ways to connect EXO-01 to the boat",
   sub="Every link in the model has a force law. This is what separates a mooring that holds from one that snatches.",
   k=[("Rope", "pulls only", "Beyond its rest length it pulls.\nShorter than that it is slack and\ntransmits nothing. Slack followed by a\nsudden take-up is the danger: it is\nsearched for in the time domain, not estimated."),
      ("Fender / push knee", "pushes only", "Transmits force only when the two bodies\ncome close enough to compress it.\nIt is what takes the thrust of the pods;\nwithout it, with every rope running forward,\nthe boat simply slides aft."),
      ("Rigid tube", "works both ways", "No slack possible, so no snatch.\nIn exchange the alternating load goes\nentirely into the tube and its joints,\nand the link can no longer be released\nby hand.")],
   xl="elongation", yl="force", comp="compression", trac="tension", slack="slack", slack2="no contact",
   foot="Shock absorbers (rubber snubber, elastomer cartridge) enter the model only as a lower stiffness: their damping is not modelled.\nThe demonstrated benefit is therefore a softer stiffness, not energy absorption."),
}

for lang, t in T17.items():
    fig = plt.figure(figsize=(13.5, 7.4))
    ax0 = fig.add_axes([0, 0, 1, 1]); ax0.set_xlim(0, 1); ax0.set_ylim(0, 1); ax0.axis("off")
    ax0.text(0.028, 0.95, t["title"], fontsize=17, weight="bold", color=C["ink"])
    ax0.text(0.028, 0.905, t["sub"], fontsize=9.6, color=C["mute"])
    cols = [C["line"], C["fender"], C["strut"]]
    x = np.linspace(-1, 1, 400)
    laws = [np.where(x > 0, x, 0), np.where(x < 0, x, 0), x]
    for i, ((ttl, rule, body), col, y_) in enumerate(zip(t["k"], cols, laws)):
        left = 0.028 + i * 0.325
        ax = fig.add_axes([left + 0.012, 0.42, 0.21, 0.30])
        ax.axhline(0, color=C["rule"], lw=1); ax.axvline(0, color=C["rule"], lw=1)
        ax.plot(x, y_, color=col, lw=3)
        if i == 0:
            ax.fill_between(x, -1, 1, where=(x < 0), color=C["rule"], alpha=.35)
            ax.text(-0.5, 0.65, t["slack"], fontsize=8, color=C["mute"], ha="center")
        if i == 1:
            ax.fill_between(x, -1, 1, where=(x > 0), color=C["rule"], alpha=.35)
            ax.text(0.5, -0.65, t["slack2"], fontsize=8, color=C["mute"], ha="center")
        ax.set_xlim(-1, 1); ax.set_ylim(-1, 1); ax.set_xticks([]); ax.set_yticks([])
        ax.set_xlabel(t["xl"], fontsize=8, color=C["mute"]); ax.set_ylabel(t["yl"], fontsize=8, color=C["mute"])
        ax.text(0.03, 0.92, t["trac"], transform=ax.transAxes, fontsize=7.5, color=C["mute"], ha="left")
        ax.text(0.03, 0.04, t["comp"], transform=ax.transAxes, fontsize=7.5, color=C["mute"], ha="left")
        for s in ax.spines.values():
            s.set_color(C["rule"])
        ax0.text(left + 0.012, 0.79, ttl, fontsize=12.5, weight="bold", color=col)
        ax0.text(left + 0.012, 0.755, rule, fontsize=9.5, color=C["mute"], style="italic")
        ax0.text(left + 0.012, 0.37, body, fontsize=9, color=C["ink"], va="top", linespacing=1.6)
    ax0.plot([0.028, 0.975], [0.145, 0.145], color=C["rule"], lw=1)
    ax0.text(0.028, 0.115, t["foot"], fontsize=9.2, color=C["ink"], va="top", linespacing=1.6)
    save(fig, "17_element_kinds", lang, LAB if lang == "fr" else LAB_EN)


# ───────────────────────────────────────────────────────────── 18 · model boundary
T18 = {
 "fr": dict(title="Ce que le modèle sait, et ce qu'il ne sait pas",
   sub="Une simulation n'est utile que si sa frontière est dite. Celle-ci est tenue dans ASSUMPTIONS.md, versionnée avec le code.",
   in_t="Dans le modèle",
   ins=["Volume immergé exact des flotteurs à n'importe quelle gîte et assiette",
        "Équilibre statique des deux corps, aussières et défenses comprises",
        "Interaction hydrodynamique entre les deux coques (12 DDL couplés)",
        "Amortissement de rayonnement (écoulement potentiel)",
        "Mou et reprise des aussières, en domaine temporel",
        "Poussée des pods, résistance de coque, remorquage",
        "Franc-bord et gîte sous passagers, lus au regard d'ES-TRIN 19.03/19.04"],
   out_t="Hors du modèle",
   outs=[("Amortissement visqueux", "remplacé par 5 % d'amortissement critique supposé"),
         ("Dissipation des snubbers et des défenses", "seule leur raideur est modélisée"),
         ("Ragage, fluage et vieillissement des cordages", "non modélisés"),
         ("Vent en rafale, courant, sillage réel", "le vent n'entre qu'en charge statique ES-TRIN"),
         ("Coque réelle de L'Hydronaute", "remplacée par une reconstitution par sections"),
         ("Masses réelles", "déclarées et estimées, non pesées"),
         ("Efforts de structure dans le châssis", "aucun calcul de résistance des matériaux")],
   foot="Les deux listes évoluent ensemble : lever une limite demande une mesure, pas un réglage du code.\nLe pesage réel, l'essai de stabilité et le relevé des flotteurs sont les trois mesures qui feraient basculer le plus de lignes de droite à gauche."),
 "en": dict(title="What the model knows, and what it does not",
   sub="A simulation is only useful if its boundary is stated. This one is kept in ASSUMPTIONS.md, versioned with the code.",
   in_t="Inside the model",
   ins=["Exact immersed volume of the floats at any heel and trim",
        "Static equilibrium of both bodies, ropes and fenders included",
        "Hydrodynamic interaction between the two hulls (12 coupled DOF)",
        "Radiation damping (potential flow)",
        "Rope slack and snatch, in the time domain",
        "Pod thrust, hull resistance, towing",
        "Freeboard and heel under passengers, read against ES-TRIN 19.03/19.04"],
   out_t="Outside the model",
   outs=[("Viscous damping", "replaced by an assumed 5 % of critical"),
         ("Dissipation in snubbers and fenders", "only their stiffness is modelled"),
         ("Chafe, creep and ageing of ropes", "not modelled"),
         ("Wind gusts, current, real wake", "wind enters only as the ES-TRIN static load"),
         ("L'Hydronaute's real hull", "replaced by a reconstruction from sections"),
         ("Real masses", "declared and estimated, not weighed"),
         ("Structural loads in the frame", "no strength-of-materials calculation")],
   foot="The two lists move together: lifting a limit takes a measurement, not a change to the code.\nThe real weighing, the inclining test and a survey of the floats are the three measurements that would move the most lines from right to left."),
}

for lang, t in T18.items():
    fig = plt.figure(figsize=(14, 7.8))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.text(0.028, 0.955, t["title"], fontsize=17, weight="bold", color=C["ink"])
    ax.text(0.028, 0.913, t["sub"], fontsize=9.6, color=C["mute"])
    ax.add_patch(FancyBboxPatch((0.028, 0.23), 0.455, 0.645, boxstyle="round,pad=0.012,rounding_size=0.02",
                                facecolor="#e8f5e9", edgecolor=C["measured"], lw=1.3))
    ax.text(0.05, 0.845, t["in_t"], fontsize=12.5, weight="bold", color="#1b5e20")
    for i, s in enumerate(t["ins"]):
        y = 0.79 - i * 0.082
        ax.text(0.052, y, "✓", fontsize=11, color=C["measured"], va="top")
        ax.text(0.078, y, s, fontsize=9.3, color=C["ink"], va="top", wrap=True)
    ax.add_patch(FancyBboxPatch((0.517, 0.23), 0.455, 0.645, boxstyle="round,pad=0.012,rounding_size=0.02",
                                facecolor="#fdecea", edgecolor=C["out"], lw=1.3))
    ax.text(0.539, 0.845, t["out_t"], fontsize=12.5, weight="bold", color="#b71c1c")
    for i, (s, why) in enumerate(t["outs"]):
        y = 0.79 - i * 0.078
        ax.text(0.541, y, "✕", fontsize=10, color=C["out"], va="top")
        ax.text(0.567, y, s, fontsize=9.3, color=C["ink"], va="top", weight="bold")
        ax.text(0.567, y - 0.030, why, fontsize=8.5, color=C["mute"], va="top")
    ax.plot([0.028, 0.972], [0.175, 0.175], color=C["rule"], lw=1)
    ax.text(0.028, 0.145, t["foot"], fontsize=9.2, color=C["ink"], va="top", linespacing=1.6)
    save(fig, "18_model_boundary", lang, LAB if lang == "fr" else LAB_EN)


# ───────────────────────────────────────────────────────────── 19 · verification
def pick(frag):
    for c in VER["checks"]:
        if frag.lower() in c["name"].lower():
            return c
    raise KeyError(frag)


def nums(text):
    """Every number in a check's reported value, as floats, in order."""
    return [float(m) for m in re.findall(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text)]


def sci(v, lang, digits=1):
    """1.4e-15 -> '1,4 · 10⁻¹⁵' (fr) / '1.4 · 10⁻¹⁵' (en)."""
    sup = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")
    mant, exp = f"{v:.{digits}e}".split("e")
    if lang == "fr":
        mant = mant.replace(".", ",")
    return f"{mant} · 10{str(int(exp)).translate(sup)}"


def pct(v, lang, digits=1):
    t = f"{v:.{digits}f}"
    return (t.replace(".", ",") if lang == "fr" else t) + " %"


V_VOL = nums(pick("Analytic buoyancy test body (capsule")["actual"])[0]
V_EQ = max(nums(pick(f"Equilibrium residuals [{k}]")["actual"])[0]
           for k in ["baseline_illustrative", "battery_relocated", "occupants_symmetric", "occupants_asymmetric"])
V_HEEL, V_DV = nums(pick("Deliberately symmetric load")["actual"])[:2]
V_PANEL = nums(pick("BEM panel-size convergence")["actual"])[-1]
V_PANEL2 = nums(pick("Two-body BEM panel convergence")["actual"])[-1]
V_XFORM = nums(pick("BEM computed about the CAD origin")["actual"])[0]
V_TD = nums(pick("Two-body (12 DOF) RK4")["actual"])


def cards(lang):
    L = lang == "fr"
    return [
      (("Contre les formules exactes" if L else "Against exact formulas"),
       ("Volume immergé d'un corps dont la solution\nanalytique est connue : écart relatif {v}.\nLa surface de flottaison est du même ordre.\n\nLe code résout la géométrie, il ne\nl'approche pas."
        if L else
        "Immersed volume of a body whose analytic\nsolution is known: relative error {v}.\nWaterplane area is of the same order.\n\nThe code resolves the geometry, it does\nnot approximate it.").format(v=sci(V_VOL, lang, 2)), C["measured"]),
      (("Résidus d'équilibre" if L else "Equilibrium residuals"),
       ("Force et moment résiduels à la position\nd'équilibre, sur quatre scénarios :\nau pire {v}.\n\nL'équilibre est atteint, pas approché."
        if L else
        "Residual force and moment at the solved\nequilibrium, over four scenarios:\nat worst {v}.\n\nEquilibrium is reached, not approached.").format(v=sci(V_EQ, lang)), C["measured"]),
      (("Symétrie imposée" if L else "Enforced symmetry"),
       ("Chargement volontairement symétrique :\ngîte {h} rad, volumes bâbord et tribord\négaux à {d} m³ près.\n\nAucun biais gauche/droite dans le maillage."
        if L else
        "Deliberately symmetric loading:\nheel {h} rad, port and starboard volumes\nequal to within {d} m³.\n\nNo left/right bias in the mesh.").format(h=sci(abs(V_HEEL), lang), d=sci(V_DV, lang)), C["measured"]),
      (("Convergence du maillage" if L else "Mesh convergence"),
       ("EXO-01 seul, panneaux 0,12 → 0,08 m :\nécart maximal {a}.\nCas couplé à deux corps : {b}.\n\nC'est la limite la plus lâche de la chaîne :\nelle est reportée, pas masquée."
        if L else
        "EXO-01 alone, panels 0.12 → 0.08 m:\nlargest change {a}.\nCoupled two-body case: {b}.\n\nThis is the loosest bound in the chain:\nit is reported, not hidden.").format(a=pct(V_PANEL, lang, 2), b=pct(V_PANEL2, lang)), C["declared"]),
      (("Domaine temporel vs fréquentiel" if L else "Time domain vs frequency domain"),
       ("Intégration pas-à-pas à 12 degrés de liberté\ncomparée à la solution fréquentielle, en\nraffinant le pas de temps : {a}, {b}, {c}.\n\nLes deux voies donnent le même mouvement."
        if L else
        "Step-by-step 12-DOF integration compared\nwith the frequency-domain solution, as the\ntime step is refined: {a}, {b}, {c}.\n\nThe two routes give the same motion.").format(a=sci(V_TD[0], lang), b=sci(V_TD[1], lang), c=sci(V_TD[2], lang)), C["measured"]),
      (("Transport au centre de gravité" if L else "Transport to the centre of gravity"),
       ("Coefficients hydrodynamiques calculés autour\nde l'origine CAO puis transportés au centre\nde gravité, comparés au calcul direct :\nécart {v}.\n\nC'est ce qui permet de déplacer une batterie\nsans relancer le calcul lourd."
        if L else
        "Hydrodynamic coefficients computed about\nthe CAD origin then moved to the centre of\ngravity, compared with the direct solve:\ndifference {v}.\n\nThis is what lets a battery move without\nredoing the heavy calculation.").format(v=sci(V_XFORM, lang)), C["measured"]),
    ]


T19 = {
 "fr": dict(title="Sur quoi repose la confiance dans ces chiffres",
   sub=f"{N_CHECKS} contrôles automatiques, {N_PASSED} au vert, rejoués à chaque modification du code — plus {N_TESTS} tests unitaires. Le rapport complet est publié avec le code.",
   foot_t="Ce que ces contrôles ne disent pas",
   foot=("Ils montrent que le code résout correctement les équations qu'on lui a données. Ils ne disent rien de la justesse des entrées — masses déclarées,\n"
         "coque reconstituée, amortissement supposé. Seuls le pesage réel, l'essai de stabilité et les essais à l'eau trancheront cela.\n"
         "C'est pourquoi tout résultat reste étiqueté « exploratoire » jusqu'à la mise à l'eau.")),
 "en": dict(title="What the confidence in these numbers rests on",
   sub=f"{N_CHECKS} automatic checks, {N_PASSED} green, replayed on every change to the code — plus {N_TESTS} unit tests. The full report is published with the code.",
   foot_t="What these checks do not say",
   foot=("They show the code solves correctly the equations it was given. They say nothing about whether the inputs are right — declared masses,\n"
         "a reconstructed hull, an assumed damping. Only the real weighing, the inclining test and the water trials will settle that.\n"
         "That is why every result stays labelled \u201cexploratory\u201d until launch.")),
}

for lang, t in T19.items():
    fig = plt.figure(figsize=(14, 8.1))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.text(0.028, 0.957, t["title"], fontsize=17, weight="bold", color=C["ink"])
    ax.text(0.028, 0.917, t["sub"], fontsize=9.4, color=C["mute"])
    w, h, gx, gy = 0.295, 0.265, 0.023, 0.03
    for i, (ttl, body, col) in enumerate(cards(lang)):
        cx = 0.028 + (i % 3) * (w + gx)
        cy = 0.595 - (i // 3) * (h + gy)
        box(ax, cx, cy, w, h, ttl, body, C["panel"], col, tsize=9.8, bsize=8.3)
        ax.add_patch(Rectangle((cx, cy), 0.005, h, facecolor=col, edgecolor="none", zorder=5))
    ax.plot([0.028, 0.972], [0.255, 0.255], color=C["rule"], lw=1)
    ax.text(0.028, 0.225, t["foot_t"], fontsize=11.5, weight="bold", color="#b71c1c")
    ax.text(0.028, 0.178, t["foot"], fontsize=9.2, color=C["ink"], va="top", linespacing=1.7)
    save(fig, "19_verification", lang, LAB if lang == "fr" else LAB_EN)


print(f"written 5 figures x 2 languages -> {OUT} (+ web/)  [checks {N_PASSED}/{N_CHECKS}, tests {N_TESTS}]")
