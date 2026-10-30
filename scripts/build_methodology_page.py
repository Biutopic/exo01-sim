"""Build docs/website/methodologie-interactive.html: the interactive FR/EN methodology page for the website.

    python scripts/build_methodology_page.py

The page is one self-contained HTML file. Simulator renders from docs/website/img/web are embedded as data URIs so
the page works offline and inside an artifact. Verification numbers come from results/verification/verification_report.json.
"""
import base64
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "docs" / "website" / "img" / "web"
VER = json.loads((ROOT / "results" / "verification" / "verification_report.json").read_text())
N_CHECKS = len(VER["checks"])
N_PASSED = sum(1 for c in VER["checks"] if c["passed"])
N_TESTS = 89


def pick(frag):
    for c in VER["checks"]:
        if frag.lower() in c["name"].lower():
            return c
    raise KeyError(frag)


def nums(t):
    return [float(m) for m in re.findall(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", t)]


SUP = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def sci(v, lang, d=1):
    m, e = f"{v:.{d}e}".split("e")
    if lang == "fr":
        m = m.replace(".", ",")
    return f"{m} · 10{str(int(e)).translate(SUP)}"


def pc(v, lang, d=1):
    t = f"{v:.{d}f}"
    return (t.replace(".", ",") if lang == "fr" else t) + " %"


V = dict(
    vol=nums(pick("Analytic buoyancy test body (capsule")["actual"])[0],
    eq=max(nums(pick(f"Equilibrium residuals [{k}]")["actual"])[0]
           for k in ["baseline_illustrative", "battery_relocated", "occupants_symmetric", "occupants_asymmetric"]),
    heel=abs(nums(pick("Deliberately symmetric load")["actual"])[0]),
    panel=nums(pick("BEM panel-size convergence")["actual"])[-1],
    panel2=nums(pick("Two-body BEM panel convergence")["actual"])[-1],
    xform=nums(pick("BEM computed about the CAD origin")["actual"])[0],
    td=nums(pick("Two-body (12 DOF) RK4")["actual"]),
)

RENDERS = ["01_moored_still_iso", "09_exo_alone_iso", "02_moored_still_top", "04_beam_sea_max_roll", "13_rao_comparison"]
IMG = {k: "data:image/webp;base64," + base64.b64encode((W / f"{k}.webp").read_bytes()).decode() for k in RENDERS}


def checks(lang):
    L = lang == "fr"
    return [
        dict(v=sci(V["vol"], lang, 2), warn=False,
             t="Contre les formules exactes" if L else "Against exact formulas",
             p=("Volume immergé d'un corps dont la solution analytique est connue."
                if L else "Immersed volume of a body whose analytic solution is known.")),
        dict(v=sci(V["eq"], lang), warn=False,
             t="Résidus d'équilibre" if L else "Equilibrium residuals",
             p=("Force et moment résiduels à la position d'équilibre, sur quatre scénarios."
                if L else "Residual force and moment at the solved equilibrium, over four scenarios.")),
        dict(v=sci(V["heel"], lang) + " rad", warn=False,
             t="Symétrie imposée" if L else "Enforced symmetry",
             p=("Gîte sous un chargement volontairement symétrique : pas de biais gauche/droite dans le maillage."
                if L else "Heel under a deliberately symmetric loading: no left/right bias in the mesh.")),
        dict(v=f'{pc(V["panel"], lang, 2)} / {pc(V["panel2"], lang)}', warn=True,
             t="Convergence du maillage" if L else "Mesh convergence",
             p=("EXO-01 seul puis le cas couplé, panneaux 0,12 → 0,08 m. La limite la plus lâche de la chaîne."
                if L else "EXO-01 alone then the coupled case, panels 0.12 → 0.08 m. The loosest bound in the chain.")),
        dict(v=f'{sci(V["td"][0], lang)} → {sci(V["td"][2], lang)}', warn=False,
             t="Domaine temporel vs fréquentiel" if L else "Time domain vs frequency domain",
             p=("Intégration pas-à-pas à 12 degrés de liberté comparée à la solution fréquentielle."
                if L else "Step-by-step 12-DOF integration compared with the frequency-domain solution.")),
        dict(v=sci(V["xform"], lang), warn=False,
             t="Transport au centre de gravité" if L else "Transport to the centre of gravity",
             p=("Ce qui permet de déplacer une batterie sans relancer le calcul lourd."
                if L else "What lets a battery move without redoing the heavy calculation.")),
    ]


DATA = dict(renders=IMG, checks={"fr": checks("fr"), "en": checks("en")},
            counts=dict(checks=N_CHECKS, passed=N_PASSED, tests=N_TESTS))
TPL = (ROOT / "scripts" / "templates" / "methodology_page.html").read_text()
html = TPL.replace("/*__DATA__*/null", json.dumps(DATA, ensure_ascii=False))
out = ROOT / "docs" / "website" / "methodologie-interactive.html"
out.write_text(html)
print(f"written {out.relative_to(ROOT)}  ({len(html)/1024:.0f} kB, {N_PASSED}/{N_CHECKS} checks, {N_TESTS} tests)")
