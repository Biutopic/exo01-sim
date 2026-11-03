"""Dimensioned drawings of the final EXO-01 coupling (front V-rope on a bow pulley + winch, two rear compression
bumpers, two lateral dockwheels): top view, side view and the free-body diagram of the force path.

    python scripts/draw_coupling.py

-> results/coupling/coupling_{top,side,fbd}.png  and docs/website/img/20_coupling_{fr,en}.png (+ webp)

Geometry comes from configs/illustrative.json (float positions, hull stations, clearance reference) and from the
measured product dimensions; the numbers printed on the drawing are the ones the study used.
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
from matplotlib.patches import Rectangle, Circle, Polygon, FancyArrowPatch, FancyBboxPatch  # noqa: E402
from PIL import Image  # noqa: E402

import warnings  # noqa: E402
warnings.simplefilter("ignore")
cfg = json.loads((ROOT / "configs" / "illustrative.json").read_text())
HB = cfg["host_boat"]
ST = np.array(HB["buoyant_surface"]["stations_mm"], float) / 1000.0     # x, half-beam, keel rise
CR = HB["clearance_reference"]
OUT = ROOT / "results" / "coupling"
OUT.mkdir(parents=True, exist_ok=True)
WEB = ROOT / "docs" / "website" / "img"

# geometry, identical to scripts/run_final_coupling.py
X_CROSS, BUMP_PROJ = 2.10, 0.165
X_BERTH = X_CROSS + BUMP_PROJ
Y_BUMP = 0.90
X_WHEEL_BOAT, Y_HULL, Y_FLOAT_FACE, WHEEL_GAP = 1.20, 1.49, 1.67, 0.030
X_VEE, Y_VEE, Z_VEE = 5.20, 2.25, 0.30
X_BOW_BOAT, Z_BOW_BOAT = 8.00, 0.78
BOW_X = X_BERTH + X_BOW_BOAT
ALPHA = np.degrees(np.arctan2(Y_VEE, BOW_X - X_VEE))

# real flotations, so the side view is not drawn from a guessed draft
from exo01.analysis import evaluate  # noqa: E402
from exo01.config import load_config, resolve  # noqa: E402
_r = evaluate(resolve(load_config("illustrative"),
                      {"host_boat": {"placement_in_exo_frame": dict(HB["placement_in_exo_frame"], x_m=X_BERTH)},
                       "propulsion": {"thrust_fraction": 0.0}}))
_EQ = _r["equilibrium"]
_GE = _r["mass"]["com_m"]
WL_EXO = float(_GE[2]) - float(_EQ["com_height_above_waterline_m"])   # the common waterline, in EXO frame z
_BEQ = _r["bodies"]["boat"]["equilibrium"]
BOAT_DRAFT = float(_BEQ["draft_hull_proxy_m"])
# the boat frame's z = 0 is its hull bottom at the transom, so its draft puts that plane below the waterline
BOAT_Z0 = WL_EXO - BOAT_DRAFT
print(f"waterline in EXO z = {WL_EXO:+.3f} m | boat draft {BOAT_DRAFT:.3f} m | boat z=0 plane at {BOAT_Z0:+.3f} m")

C = dict(ink="#17242b", mute="#6b818c", rule="#c9d6dc", float="#37474f", deck="#cfd8dc",
         hull="#eceff1", rope="#b26a00", bump="#2e7d32", wheel="#1565c0", winch="#6a1b9a", water="#1565c0")
T = {
 "fr": dict(top="Vue de dessus", side="Vue de côté — chaîne d'effort avant",
            title="EXO-01 — accouplement final : corde en V sur poulie d'étrave, deux défenses de compression arrière, deux roues latérales",
            sub=f"Géométrie du plan d'assemblage et des produits retenus. Demi-angle du V α = {ALPHA:.1f}° → résultante arrière = 1,83 × tension de corde.",
            rope="corde continue polyester 12–14 mm", pulley="poulie d'étrave", pvm="OCEAN PVM2\n(protection d'angle,\ncharge admissible non publiée)",
            winch="treuil VEVOR 12 V\n+ capteur de tension\n+ verrou mécanique", bump="2 × défense moussée OCEAN\nØ 220 × 640, profil 3/4",
            wheel="2 × Talamex Dockwheel\n(Ø non publié)", float_="flotteurs Flofiz Ø 0,60 × 1,60 (×6)", deck="pont arrière EXO",
            boat="L'Hydronaute — 8,00 m, 2 100 kg", cross="traverse arrière x 2,10",
            note="Exploratoire — raideurs des trois éléments de contact INCONNUES (aucune courbe force-déflexion publiée) : balayées, jamais supposées.",
            lbl_gap="jeu latéral coque → face de flotteur", lbl_proj="projection défense", lbl_berth="tableau arrière"),
 "en": dict(top="Top view", side="Side view — forward force path",
            title="EXO-01 — final coupling: V-rope on a bow pulley, two rear compression bumpers, two lateral wheels",
            sub=f"Assembly-drawing geometry and the selected products. V half-angle α = {ALPHA:.1f}° → aft resultant = 1.83 × rope tension.",
            rope="continuous 12–14 mm polyester rope", pulley="bow pulley", pvm="OCEAN PVM2\n(corner fender,\nno published load rating)",
            winch="VEVOR 12 V winch\n+ load cell\n+ mechanical lock", bump="2 × OCEAN foam fender\nØ 220 × 640, 3/4 profile",
            wheel="2 × Talamex Dockwheel\n(Ø not published)", float_="Flofiz floats Ø 0.60 × 1.60 (×6)", deck="EXO rear deck",
            boat="L'Hydronaute — 8.00 m, 2,100 kg", cross="rear crossmember x 2.10",
            note="Exploratory — the three contact elements' stiffnesses are UNKNOWN (no published force-deflection curve): swept, never assumed.",
            lbl_gap="lateral clearance hull → float face", lbl_proj="bumper projection", lbl_berth="transom"),
}


def hull_outline():
    x = X_BERTH + ST[:, 0]
    y = ST[:, 1]
    return np.concatenate([np.column_stack([x, y]), np.column_stack([x[::-1], -y[::-1]])])


def dim(ax, p0, p1, text, off=0.0, vertical=False, fs=8, color=None):
    color = color or C["mute"]
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    n = np.array([0.0, off]) if not vertical else np.array([off, 0.0])
    a, b = p0 + n, p1 + n
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="<|-|>", mutation_scale=8, color=color, lw=0.9, shrinkA=0, shrinkB=0))
    m = (a + b) / 2
    ax.text(m[0], m[1], text, fontsize=fs, color=color, ha="center",
            va="bottom" if not vertical else "center", rotation=0 if not vertical else 90,
            bbox=dict(fc="white", ec="none", pad=1.2))


def draw(lang):
    t = T[lang]
    fig = plt.figure(figsize=(15.5, 11.2))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.32, 1], hspace=0.17)

    # ───────────────────────────── top view
    ax = fig.add_subplot(gs[0]); ax.set_aspect("equal")
    ax.set_xlim(-0.6, 11.4); ax.set_ylim(-3.5, 3.5)
    ax.add_patch(Polygon(hull_outline(), closed=True, facecolor=C["hull"], edgecolor=C["ink"], lw=1.3, zorder=2))
    ax.text(X_BERTH + 2.4, -0.62, t["boat"], ha="center", fontsize=10, color=C["mute"], zorder=3)
    for s in cfg["buoyant_surfaces"]:
        x0, x1 = s["x_span_m"]; y = s["y_m"]; r = s["radius_m"]
        ax.add_patch(Rectangle((x0, y - r), x1 - x0, 2 * r, facecolor=C["float"], edgecolor="k", alpha=.85, zorder=1))
    ax.add_patch(Rectangle((0, -2.27), X_CROSS, 4.54, facecolor=C["deck"], edgecolor=C["ink"], lw=1, zorder=1))
    ax.text(X_CROSS / 2, 0, t["deck"], ha="center", va="center", fontsize=9, color=C["mute"], zorder=3)
    ax.plot([X_CROSS, X_CROSS], [-2.27, 2.27], color=C["ink"], lw=2.4, zorder=3)
    for yy in (-1, 1):
        ax.plot([0.05, X_VEE], [yy * 2.27, yy * 2.27], color=C["float"], lw=1.6, zorder=1)
    # rear bumpers (3/4 profile, 640 long -> drawn across y)
    for sgn in (+1, -1):
        ax.add_patch(Rectangle((X_CROSS, sgn * Y_BUMP - 0.32), BUMP_PROJ, 0.64,
                               facecolor=C["bump"], edgecolor="k", lw=1, zorder=5))
    ax.annotate(t["bump"], xy=(X_CROSS + BUMP_PROJ / 2, Y_BUMP + 0.32), xytext=(0.22, 1.05),
                fontsize=8.6, color=C["bump"], ha="center",
                arrowprops=dict(arrowstyle="->", color=C["bump"], lw=1))
    # dockwheels
    for sgn in (+1, -1):
        ax.add_patch(Circle((X_BERTH + X_WHEEL_BOAT, sgn * (Y_FLOAT_FACE + 0.125)), 0.125,
                            facecolor=C["wheel"], edgecolor="k", lw=1, zorder=5))
        ax.plot([X_BERTH + X_WHEEL_BOAT, X_BERTH + X_WHEEL_BOAT], [sgn * (Y_HULL + WHEEL_GAP), sgn * Y_FLOAT_FACE],
                color=C["wheel"], lw=2.2, zorder=4)
    ax.annotate(t["wheel"], xy=(X_BERTH + X_WHEEL_BOAT, -(Y_FLOAT_FACE + 0.25)), xytext=(0.22, -1.62),
                fontsize=8.6, color=C["wheel"], ha="center", arrowprops=dict(arrowstyle="->", color=C["wheel"], lw=1))
    # V-rope + pulley
    for sgn in (+1, -1):
        ax.plot([X_VEE, BOW_X], [sgn * Y_VEE, 0.0], color=C["rope"], lw=2.6, zorder=6, solid_capstyle="round")
        ax.add_patch(Circle((X_VEE, sgn * Y_VEE), 0.10, facecolor="white", edgecolor=C["rope"], lw=2, zorder=7))
    ax.add_patch(Circle((BOW_X, 0.0), 0.14, facecolor="white", edgecolor=C["rope"], lw=2.4, zorder=8))
    ax.add_patch(Rectangle((BOW_X - 0.06, -0.43), 0.26, 0.86, facecolor="#ffe0b2", edgecolor=C["rope"], lw=1.2, zorder=6))
    ax.annotate(t["pvm"], xy=(BOW_X + 0.18, -0.30), xytext=(9.6, -2.25), fontsize=8.4, color=C["rope"], ha="center",
                arrowprops=dict(arrowstyle="->", color=C["rope"], lw=1))
    ax.text(BOW_X - 0.1, -0.72, t["pulley"], fontsize=8.6, color=C["rope"], ha="center")
    ax.add_patch(Rectangle((X_VEE - 0.52, Y_VEE - 0.17), 0.46, 0.34, facecolor=C["winch"], edgecolor="k", lw=1, zorder=7))
    ax.annotate(t["winch"], xy=(X_VEE - 0.3, Y_VEE + 0.17), xytext=(2.45, 3.08), fontsize=8.4, color=C["winch"],
                ha="center", arrowprops=dict(arrowstyle="->", color=C["winch"], lw=1))
    ax.text((X_VEE + BOW_X) / 2 - 0.15, Y_VEE / 2 - 0.02, t["rope"], fontsize=8.6, color=C["rope"],
            rotation=-float(ALPHA), ha="center", bbox=dict(fc="white", ec="none", pad=1))
    # angle mark
    th = np.linspace(0, -np.radians(ALPHA), 40)
    arc = np.column_stack([BOW_X - 1.6 * np.cos(th), -1.6 * np.sin(th)])
    ax.plot(arc[:, 0], arc[:, 1], color=C["rope"], lw=1.1, zorder=6)
    ax.plot([BOW_X, X_VEE - 0.4], [0, 0], color=C["rope"], lw=0.8, ls=(0, (4, 3)), zorder=5)
    ax.text(BOW_X - 2.05, -0.95, f"α = {ALPHA:.1f}°", fontsize=9.5, color=C["rope"], ha="center",
            bbox=dict(fc="white", ec="none", pad=1.5))
    # dimensions
    ax.text(X_BERTH + 0.14, -2.82, f"{t['lbl_proj']} {1000*BUMP_PROJ:.0f} mm", fontsize=7.8, color=C["mute"], va="top")
    ax.plot([X_BERTH, X_BERTH + 0.10], [-2.72, -2.80], color=C["mute"], lw=0.8)
    dim(ax, (X_BERTH + X_WHEEL_BOAT + 0.9, Y_HULL), (X_BERTH + X_WHEEL_BOAT + 0.9, Y_FLOAT_FACE),
        f"{1000*(Y_FLOAT_FACE-Y_HULL):.0f} mm", vertical=True, fs=8)
    ax.text(X_BERTH + X_WHEEL_BOAT + 1.05, (Y_HULL + Y_FLOAT_FACE) / 2, t["lbl_gap"], fontsize=7.6, color=C["mute"],
            va="center")
    dim(ax, (X_VEE, -1.95), (BOW_X, -1.95), f"{BOW_X - X_VEE:.2f} m", fs=8.5)
    dim(ax, (X_BERTH, 2.70), (BOW_X, 2.70), "LOA 8.00 m", fs=8.5)
    ax.plot([X_CROSS, X_CROSS], [-3.30, -2.85], color=C["mute"], lw=0.8, ls=(0, (3, 3)))
    ax.text(X_CROSS - 0.08, -3.42, t["cross"], fontsize=7.6, color=C["mute"], ha="right")
    ax.plot([X_BERTH, X_BERTH], [-3.05, -2.85], color=C["mute"], lw=0.8, ls=(0, (3, 3)))
    ax.text(X_BERTH + 0.10, -3.14, f"{t['lbl_berth']} x {X_BERTH:.3f}", fontsize=7.6, color=C["mute"], ha="left")
    ax.set_title(t["top"], fontsize=11, loc="left", color=C["ink"])
    ax.set_xlabel("x [m] — EXO frame"); ax.set_ylabel("y [m]")
    ax.grid(alpha=.13)

    # ───────────────────────────── side view
    ax2 = fig.add_subplot(gs[1]); ax2.set_aspect("equal")
    ax2.set_xlim(-0.6, 11.4); ax2.set_ylim(-1.15, 2.05)
    wl = WL_EXO
    ax2.axhspan(-1.15, wl, color=C["water"], alpha=.14, zorder=0)
    ax2.axhline(wl, color=C["water"], lw=1, zorder=1)
    ax2.add_patch(Rectangle((0.5, -0.60), 4.84, 0.60, facecolor=C["float"], edgecolor="k", alpha=.85, zorder=2))
    ax2.add_patch(Rectangle((0, -0.03), X_CROSS, 0.06, facecolor=C["deck"], edgecolor=C["ink"], zorder=3))
    for xx in (0.05, X_CROSS, X_VEE):
        ax2.plot([xx, xx], [0, 1.15], color=C["float"], lw=2.2, zorder=3)
    # boat side: keel line from the stations, deck at 0.78 above its catalogue WL (sitting 0.19 above the EXO datum)
    zb = BOAT_Z0
    keel = np.column_stack([X_BERTH + ST[:, 0], BOAT_Z0 + ST[:, 2]])
    side = np.vstack([keel, [[BOW_X, zb + 0.78], [X_BERTH, zb + 0.78]]])
    ax2.add_patch(Polygon(side, closed=True, facecolor=C["hull"], edgecolor=C["ink"], lw=1.2, zorder=2))
    ax2.add_patch(Rectangle((X_BERTH + 0.5, zb + 0.78), 5.6, 0.72, facecolor="#f5f7f8", edgecolor=C["ink"], lw=1, alpha=.85, zorder=2))
    # bumper, wheel, rope
    ax2.add_patch(Rectangle((X_CROSS, 0.03), BUMP_PROJ, 0.22, facecolor=C["bump"], edgecolor="k", zorder=6))
    ax2.add_patch(Circle((X_BERTH + X_WHEEL_BOAT, 0.14), 0.125, facecolor=C["wheel"], edgecolor="k", zorder=6))
    ax2.plot([X_VEE, BOW_X], [Z_VEE, zb + Z_BOW_BOAT], color=C["rope"], lw=2.4, zorder=7)
    ax2.add_patch(Circle((BOW_X, zb + Z_BOW_BOAT), 0.10, facecolor="white", edgecolor=C["rope"], lw=2, zorder=8))
    ax2.add_patch(Rectangle((X_VEE - 0.5, Z_VEE - 0.13), 0.44, 0.26, facecolor=C["winch"], edgecolor="k", zorder=7))
    rise = (zb + Z_BOW_BOAT) - Z_VEE
    ax2.annotate("", (BOW_X + 0.30, Z_VEE), (BOW_X + 0.30, zb + Z_BOW_BOAT),
                 arrowprops=dict(arrowstyle="<|-|>", color=C["mute"], lw=0.9))
    vfrac = 100 * abs(rise) / np.hypot(BOW_X - X_VEE, rise)
    updown = ("sous" if rise < 0 else "au-dessus de") if lang == "fr" else ("below" if rise < 0 else "above")
    lift = ("soulève l'étrave" if rise < 0 else "appuie sur l'étrave") if lang == "fr" else \
           ("lifts the bow" if rise < 0 else "presses the bow down")
    ax2.text(BOW_X + 0.42, Z_VEE + rise / 2,
             (f"poulie {1000*abs(rise):.0f} mm {updown}\nl'ancrage EXO → la corde\n{lift} de {vfrac:.0f} % de sa tension"
              if lang == "fr" else
              f"pulley {1000*abs(rise):.0f} mm {updown}\nthe EXO anchor → the rope\n{lift} by {vfrac:.0f} % of its tension"),
             fontsize=8, color=C["mute"], va="center")
    ax2.annotate("", (X_CROSS - 0.05, 0.60), (X_BERTH + 0.05, 0.60), arrowprops=dict(arrowstyle="->", color=C["bump"], lw=2))
    ax2.text(X_CROSS - 0.08, 0.68, ("poussée" if lang == "fr" else "push"), fontsize=8.5, color=C["bump"], ha="right")
    ax2.annotate("", (BOW_X, zb + Z_BOW_BOAT + 0.42), (BOW_X - 1.5, zb + Z_BOW_BOAT + 0.42),
                 arrowprops=dict(arrowstyle="->", color=C["rope"], lw=2))
    ax2.text(BOW_X - 1.6, zb + Z_BOW_BOAT + 0.48, ("traction arrière" if lang == "fr" else "aft pull"),
             fontsize=8.5, color=C["rope"], ha="right")
    ax2.set_title(t["side"], fontsize=11, loc="left", color=C["ink"])
    ax2.set_xlabel("x [m]"); ax2.set_ylabel("z [m] — datum pont arrière EXO" if lang == "fr" else "z [m] — EXO rear-deck datum")
    ax2.grid(alpha=.13)

    fig.suptitle(t["title"], fontsize=12.5, y=0.985, x=0.012, ha="left", color=C["ink"])
    fig.text(0.012, 0.955, t["sub"], fontsize=9.3, color=C["mute"], ha="left")
    fig.text(0.012, 0.006, t["note"], fontsize=8.2, color="#b5651d", ha="left")
    fig.savefig(OUT / f"coupling_views_{lang}.png", dpi=140, bbox_inches="tight", facecolor="white")
    WEB.mkdir(parents=True, exist_ok=True)
    fig.savefig(WEB / f"20_coupling_{lang}.png", dpi=140, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    im = Image.open(WEB / f"20_coupling_{lang}.png").convert("RGB")
    w, h = im.size
    if w > 1600:
        im = im.resize((1600, int(h * 1600 / w)), Image.LANCZOS)
    (WEB / "web").mkdir(exist_ok=True)
    im.save(WEB / "web" / f"20_coupling_{lang}.webp", quality=86, method=6)


for lang in ("fr", "en"):
    draw(lang)
print(f"written {OUT}/coupling_views_{{fr,en}}.png and {WEB}/20_coupling_{{fr,en}}.png (+ webp)   alpha = {ALPHA:.2f} deg")
