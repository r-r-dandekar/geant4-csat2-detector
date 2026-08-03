#!/usr/bin/env python3
"""
Generate a consolidated proton + photon event CSV from SPENVIS-weighted Geant4 simulation files.

Each evt file represents one simulated proton and the optical photons it produced.
The script draws N proton events per energy bin (N = flux × duration), assigns each
a uniform-random arrival time, then offsets all photon times from that evt file by
the same random time.

Usage:
    python generate_timeseries.py <sweep_timelogs_dir> [options]

    --duration-ms FLOAT   Window duration in milliseconds (default: 1000)
    --output PATH         Output CSV path (default: consolidated.csv)
    --seed INT            Random seed for reproducibility (omit for random)

Example:
    python generate_timeseries.py ./sweep_timelogs --duration-ms 500 --output out.csv --seed 42

Requirements:
    pip install numpy pandas
    Python >= 3.10

To run:
# 1-second window (default)
python generate_timeseries.py ./sweep_timelogs

# Custom duration
python generate_timeseries.py ./sweep_timelogs --duration-ms 2000

# With custom output path and reproducible seed
python generate_timeseries.py ./sweep_timelogs --duration-ms 500 --output out.csv --seed 42
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

# ── SPENVIS AP-8 MAX differential flux (protons / cm² / s) ──────────────────
# Derived from integral flux data via log-log interpolation.
# Each entry: (E_low_MeV, E_high_MeV, flux_per_cm2_s)
# All protons in bin [E_low, E_high) are represented by evt files at E_low.
SPENVIS_BINS = [
    (10,    10.5,  4.2935e4),
    (10.5,  11,    3.5839e4),
    (11,    12.5,  7.7577e4),
    (12.5,  15,    7.2180e4),
    (15,    20,    5.0173e4),
    (20,    30,    2.3435e4),
    (30,    40,    7.1380e3),
    (40,    50,    5.6940e3),
    (50,    60,    2.7430e3),
    (60,    70,    2.0890e3),
    (70,    80,    2.0833e3),
    (80,    90,    1.6319e3),
    (90,    100,   1.3138e3),
    (100,   110,   1.5332e3),
    (110,   125,   1.7669e3),
    (125,   150,   2.0420e3),
    (150,   175,   1.8546e3),
    (175,   200,   1.2170e3),
]

# Matches: evt_E20MeV_E20MeV_id1234.csv  (energy may be float like 10.5, 12.5)
EVT_RE = re.compile(r'^evt_E([\d.]+)MeV_E[\d.]+MeV_id\d+\.csv$', re.IGNORECASE)


# ── File discovery ───────────────────────────────────────────────────────────

def discover_files(directory: Path) -> dict[float, list[Path]]:
    """Scan directory and return {energy_MeV: [path, ...]} for all evt files."""
    result: dict[float, list[Path]] = defaultdict(list)
    for f in directory.iterdir():
        m = EVT_RE.match(f.name)
        if m:
            result[float(m.group(1))].append(f)
    return dict(result)


def nearest_energy(target: float, available: list[float]) -> float:
    arr = np.array(available)
    return float(arr[np.argmin(np.abs(arr - target))])


# ── CSV parsing ──────────────────────────────────────────────────────────────

def read_photons(path: Path) -> tuple[np.ndarray, float]:
    """
    Parse one evt CSV.

    Returns
    -------
    photons : ndarray, shape (N, 2)
        Columns: [time_ns, energy_MeV] for opticalphoton rows.
        N may be 0 if the file has no photon events.
    proton_energy : float
        Energy extracted from the filename (MeV).
    """
    m = EVT_RE.match(path.name)
    proton_energy = float(m.group(1)) if m else 0.0

    try:
        df = pd.read_csv(path, comment='#')
        mask = df['particle'] == 'opticalphoton'
        ph = df.loc[mask, ['time_ns', 'energy_MeV']].to_numpy(dtype=np.float64)
    except Exception as exc:
        print(f"  WARNING: could not parse {path.name}: {exc}", file=sys.stderr)
        ph = np.empty((0, 2), dtype=np.float64)

    return ph, proton_energy


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Generate consolidated proton+photon event CSV from SPENVIS-weighted simulations.'
    )
    parser.add_argument('directory', type=Path,
                        help='Path to sweep_timelogs directory')
    parser.add_argument('--duration-ms', type=float, default=1000.0,
                        help='Window duration in milliseconds (default: 1000)')
    parser.add_argument('--output', type=Path, default=Path('consolidated.csv'),
                        help='Output CSV path (default: consolidated.csv)')
    parser.add_argument('--seed', type=int, default=None,
                        help='Random seed for reproducibility')
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    duration_s  = args.duration_ms / 1000.0
    duration_ns = args.duration_ms * 1e6   # ms → ns

    print(f"Duration : {args.duration_ms} ms  ({duration_s} s)")
    print(f"Output   : {args.output}")
    print(f"Scanning : {args.directory}\n")

    # ── Discover evt files ───────────────────────────────────────────────────
    files_by_energy = discover_files(args.directory)
    if not files_by_energy:
        sys.exit("ERROR: No evt files found. Check the directory path.")

    available = sorted(files_by_energy)
    n_total_files = sum(len(v) for v in files_by_energy.values())
    print(f"Found {n_total_files:,} evt files at energies: {available} MeV\n")

    # ── Build execution plan ─────────────────────────────────────────────────
    # Map each bin's lower bound to the nearest available simulated energy.
    print(f"  {'Bin (MeV)':<17} {'Rep. E (MeV)':<14} {'N protons':>10}  {'Files avail':>13}")
    print('  ' + '─' * 58)

    plan: list[tuple[float, float, int, float, list[Path]]] = []
    for E_lo, E_hi, flux in SPENVIS_BINS:
        n = int(round(flux * duration_s))
        if n == 0:
            continue
        rep_e = nearest_energy(E_lo, available)
        paths = files_by_energy[rep_e]
        print(f"  {E_lo:>5} – {E_hi:<8}  {rep_e:<14}  {n:>10,}  {len(paths):>13,}")
        plan.append((E_lo, E_hi, n, rep_e, paths))

    total_protons = sum(n for _, _, n, _, _ in plan)
    print(f"\n  Total protons to generate: {total_protons:,}\n")

    # ── Generate events ──────────────────────────────────────────────────────
    # Strategy: accumulate numpy chunks; single concatenate + argsort at end.
    # For photons, group by unique file index and use broadcasting to avoid
    # a Python loop per proton.

    chunks_time:     list[np.ndarray] = []
    chunks_is_proton: list[np.ndarray] = []   # bool: True = proton
    chunks_energy:   list[np.ndarray] = []

    for E_lo, E_hi, n_protons, rep_e, paths in plan:
        n_files = len(paths)

        # Uniform random arrival times for all protons in this bin
        proton_times = rng.uniform(0.0, duration_ns, size=n_protons)

        # Sample file indices with replacement (handles n_protons > n_files)
        file_indices = rng.integers(0, n_files, size=n_protons)

        # Only read files that were actually sampled
        unique_idxs, inverse = np.unique(file_indices, return_inverse=True)

        loaded: list[tuple[np.ndarray, float]] = [
            read_photons(paths[idx]) for idx in unique_idxs
        ]

        # ── Proton rows ──────────────────────────────────────────────────────
        # Energy for each proton comes from its file's filename
        p_energies = np.array([loaded[i][1] for i in inverse], dtype=np.float64)
        chunks_time.append(proton_times)
        chunks_is_proton.append(np.ones(n_protons, dtype=bool))
        chunks_energy.append(p_energies)

        # ── Photon rows ──────────────────────────────────────────────────────
        # For each unique file, find all protons that used it and vectorise
        # the time-shift via broadcasting: shape (m_protons, n_photons).
        for local_idx, (photons, _pe) in enumerate(loaded):
            if len(photons) == 0:
                continue
            mask = inverse == local_idx
            t_sel = proton_times[mask]          # shape (m,)
            n_ph  = len(photons)

            # (m, n_ph) → flatten → (m * n_ph,)
            shifted   = (t_sel[:, None] + photons[:, 0]).ravel()
            ph_energy = np.tile(photons[:, 1], len(t_sel))

            chunks_time.append(shifted)
            chunks_is_proton.append(np.zeros(len(shifted), dtype=bool))
            chunks_energy.append(ph_energy)

        print(f"  {E_lo}–{E_hi} MeV ({rep_e} MeV files): {n_protons:,} protons done")

    # ── Merge, sort, write ───────────────────────────────────────────────────
    print("\nConcatenating chunks ...")
    all_time      = np.concatenate(chunks_time)
    all_is_proton = np.concatenate(chunks_is_proton)
    all_energy    = np.concatenate(chunks_energy)

    print(f"Sorting {len(all_time):,} rows by time_ns ...")
    order         = np.argsort(all_time, kind='stable')
    all_time      = all_time[order]
    all_is_proton = all_is_proton[order]
    all_energy    = all_energy[order]

    particle_col = np.where(all_is_proton, 'proton', 'opticalphoton')

    print(f"Writing to {args.output} ...")
    pd.DataFrame({
        'time_ns':    all_time,
        'particle':   particle_col,
        'energy_MeV': all_energy,
    }).to_csv(args.output, index=False)

    print(f"\nDone.  {len(all_time):,} rows written to {args.output}")


if __name__ == '__main__':
    main()
