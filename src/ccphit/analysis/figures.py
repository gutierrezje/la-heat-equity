"""Shared figure style and output location for the analysis modules."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display in this environment
import matplotlib.pyplot as plt

FIG_DIR = Path("data/figures")

# Warm sequential for risk, diverging for differences. Deliberately not the default
# viridis/jet: heat maps read better warm, and a diverging scale must have a neutral
# midpoint so "no difference" is visually null.
RISK_CMAP = "YlOrRd"
DIVERGE_CMAP = "RdBu_r"
INK = "#1c1c1c"
MUTED = "#8a8a8a"

PALETTE = {
    "urban": "#c1272d",  # dense, vulnerable, well-served
    "remote": "#e08214",  # far from everything
    "hot_only": "#b8860b",  # hot but not vulnerable
    "low": "#4575b4",  # low risk
}


def setup() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": MUTED,
            "axes.labelcolor": INK,
            "axes.titlesize": 11,
            "axes.titleweight": "semibold",
            "axes.labelsize": 9.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.color": INK,
            "ytick.color": INK,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "legend.frameon": False,
            "legend.fontsize": 8.5,
            "figure.titlesize": 13,
            "figure.titleweight": "bold",
            "font.size": 9.5,
        }
    )


def save(fig, name: str, dpi: int = 150) -> Path:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / f"{name}.png"
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"  figure -> {path}")
    return path


def annotate(ax, text: str, loc: str = "lower right") -> None:
    """A short takeaway burned into the figure, so it travels with the image."""
    xy = {"lower right": (0.98, 0.02), "lower left": (0.02, 0.02),
          "upper left": (0.02, 0.98), "upper right": (0.98, 0.98)}[loc]
    ha = "right" if "right" in loc else "left"
    va = "bottom" if "lower" in loc else "top"
    ax.annotate(
        text,
        xy=xy,
        xycoords="axes fraction",
        ha=ha,
        va=va,
        fontsize=8,
        color=MUTED,
        style="italic",
    )
