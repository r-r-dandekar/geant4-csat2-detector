#!/usr/bin/env python3
"""Plot the particle-detector sweep results.

Reads the CSV produced by the simulation (see RunAction::WriteCsvRow) BY COLUMN
HEADER -- it does not depend on column order -- and produces a set of graphs
versus proton energy:

  1. Primary fate          (stops per region, total, passed-through, back-scatter)
  2. Primary energy deposit (per region + total, MeV)
  3. Optical-photon energy deposit (per region + total, MeV)
  4. Scintillation light    (photons generated / detected, Cerenkov)

In addition, one graph per individual quantity is written to an `individual/`
subdirectory (this reproduces every graph the old LibreOffice script produced,
plus the new observables).

Usage:
    python plot_results.py <results.csv> [output_dir]

If output_dir is omitted, figures are written next to the CSV in a folder named
"<csv-stem>_plots". A combined multi-page PDF is also written.
"""

import os
import sys

import pandas as pd
import matplotlib
matplotlib.use("Agg")  # headless: write files, no interactive window
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

ENERGY = "energy_MeV"

# Friendly labels for known columns (used in legends).
LABELS = {
    "stop_Al": "Al window", "stop_SiCD": "Si C.D.", "stop_Teflon": "Teflon",
    "stop_CsI": "CsI(Tl)", "stop_SiACD": "Si A.C.D.", "stop_Photodiode": "Photodiode",
    "stop_total": "Total stopped", "passed_through": "Passed through",
    "back_scatter": "Back-scattered",
    "edep_Al_MeV": "Al window", "edep_SiCD_MeV": "Si C.D.", "edep_Teflon_MeV": "Teflon",
    "edep_CsI_MeV": "CsI(Tl)", "edep_SiACD_MeV": "Si A.C.D.",
    "edep_Photodiode_MeV": "Photodiode", "edep_total_MeV": "Total",
    "optedep_Al_MeV": "Al window", "optedep_SiCD_MeV": "Si C.D.",
    "optedep_Teflon_MeV": "Teflon", "optedep_CsI_MeV": "CsI(Tl)",
    "optedep_SiACD_MeV": "Si A.C.D.", "optedep_Photodiode_MeV": "Photodiode",
    "optedep_total_MeV": "Total",
    "scint_photons": "Scintillation generated",
    "cerenkov_photons": "Cerenkov generated",
    "photodiode_detected": "Detected at photodiode",
}

# Figure groups: (title, y-axis label, list of columns).
GROUPS = [
    ("Primary fate vs energy", "Number of primaries",
     ["stop_Al", "stop_SiCD", "stop_Teflon", "stop_CsI", "stop_SiACD",
      "stop_Photodiode", "stop_total", "passed_through", "back_scatter"]),
    ("Primary energy deposition vs energy", "Energy deposited (MeV)",
     ["edep_Al_MeV", "edep_SiCD_MeV", "edep_Teflon_MeV", "edep_CsI_MeV",
      "edep_SiACD_MeV", "edep_Photodiode_MeV", "edep_total_MeV"]),
    ("Optical-photon energy deposition vs energy", "Energy deposited (MeV)",
     ["optedep_Al_MeV", "optedep_SiCD_MeV", "optedep_Teflon_MeV", "optedep_CsI_MeV",
      "optedep_SiACD_MeV", "optedep_Photodiode_MeV", "optedep_total_MeV"]),
    ("Scintillation light vs energy", "Photons (physical estimate)",
     ["scint_photons", "photodiode_detected", "cerenkov_photons"]),
]


# Columns that are inputs/metadata rather than plottable observables.
NON_PLOT = {ENERGY, "n_events", "ydiv"}


def make_figure(df, title, ylabel, columns, legend=True):
    """Plot the given columns versus energy on one axes; returns the Figure."""
    fig, ax = plt.subplots(figsize=(8, 5))
    plotted = False
    for col in columns:
        if col not in df.columns:
            continue
        ax.plot(df[ENERGY], df[col], marker="o", markersize=3,
                label=LABELS.get(col, col))
        plotted = True
    ax.set_title(title)
    ax.set_xlabel("Proton energy (MeV)")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    if plotted and legend:
        ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def column_meta(col):
    """Return (y-axis label, title) for an individual single-quantity plot."""
    label = LABELS.get(col, col)
    if col.startswith("stop_"):
        return ("Number of primaries",
                "Total primaries stopped" if col == "stop_total"
                else f"Primaries stopped in {label}")
    if col == "passed_through":
        return ("Number of primaries", "Primaries passed through")
    if col == "back_scatter":
        return ("Number of primaries", "Primaries back-scattered")
    if col.startswith("edep_"):
        return ("Energy deposited (MeV)", f"Primary energy deposit: {label}")
    if col.startswith("optedep_"):
        return ("Energy deposited (MeV)", f"Optical-photon energy deposit: {label}")
    if col in ("scint_photons", "cerenkov_photons", "photodiode_detected"):
        return ("Photons", label)
    return ("", label)


def write_individual_plots(df, parent_dir):
    """One graph per observable column (mirrors the old per-quantity charts)."""
    out_dir = os.path.join(parent_dir, "individual")
    os.makedirs(out_dir, exist_ok=True)
    for col in df.columns:
        if col in NON_PLOT:
            continue
        ylabel, title = column_meta(col)
        fig = make_figure(df, title, ylabel, [col], legend=False)
        png = os.path.join(out_dir, f"{col}.png")
        fig.savefig(png, dpi=120)
        plt.close(fig)
        print(f"  wrote {png}")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python {os.path.basename(sys.argv[0])} <results.csv> [output_dir]")
        sys.exit(1)

    csv_path = sys.argv[1]
    if not os.path.isfile(csv_path):
        print(f"Error: file not found: {csv_path}")
        sys.exit(1)

    stem = os.path.splitext(os.path.basename(csv_path))[0]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else \
        os.path.join(os.path.dirname(os.path.abspath(csv_path)), f"{stem}_plots")
    os.makedirs(out_dir, exist_ok=True)

    df = pd.read_csv(csv_path)
    if ENERGY not in df.columns:
        print(f"Error: column '{ENERGY}' not found. Is this a sweep CSV?")
        sys.exit(1)
    df = df.sort_values(ENERGY)

    pdf_path = os.path.join(out_dir, f"{stem}.pdf")
    with PdfPages(pdf_path) as pdf:
        for i, (title, ylabel, cols) in enumerate(GROUPS, start=1):
            fig = make_figure(df, title, ylabel, cols)
            png = os.path.join(out_dir, f"{i:02d}_{title.split(' vs')[0].replace(' ', '_').lower()}.png")
            fig.savefig(png, dpi=120)
            pdf.savefig(fig)
            plt.close(fig)
            print(f"  wrote {png}")

    print(f"Combined PDF: {pdf_path}")

    # Also emit one graph per individual quantity (covers every graph the old
    # LibreOffice script produced, plus the new observables).
    write_individual_plots(df, out_dir)


if __name__ == "__main__":
    main()
