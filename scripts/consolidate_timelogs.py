#!/usr/bin/env python3
"""
Generate a consolidated proton + photon event CSV from SPENVIS-weighted Geant4 simulation files.

Each evt file represents one simulated proton and the optical photons it produced.
The script draws N proton events per energy bin (N = flux × duration), assigns each
a uniform-random arrival time, then offsets all photon times from that evt file by
the same random time.

Usage:
    python consolidate_timelogs.py <sweep_timelogs_dir> [options]

    --duration-ms FLOAT   Window duration in milliseconds (default: 1000)
    --output PATH         Output CSV path (default: consolidated.csv)
    --seed INT            Random seed for reproducibility (omit for random)

Example:
    python consolidate_timelogs.py ../results/$SUBDIR/timelogs--duration-ms 500 --output out.csv --seed 42

Requirements:
    pip install numpy pandas
    Python >= 3.10

To run:
# 1-second window (default)
python consolidate_timelogs.py ../results/$SUBDIR/timelogs

# Custom duration
python consolidate_timelogs.py ../results/$SUBDIR/timelogs --duration-ms 2000

# With custom output path and reproducible seed
python consolidate_timelogs.py ../results/$SUBDIR/timelogs --duration-ms 500 --output ../results/$SUBDIR/consolidated.csv --seed 42
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import random
import csv

TARGET_INTERVALS = [
    (10,    10.5),
    (10.5,  11),
    (11,    12.5),
    (12.5,  15),
    (15,    20),
    (20,    30),
    (30,    40),
    (40,    50),
    (50,    60),
    (60,    70),
    (70,    80),
    (80,    90),
    (90,    100),
    (100,   110),
    (110,   125),
    (125,   150),
    (150,   175),
    (175,   200),
]

# 2. Load CSV data
df = pd.read_csv('../data/spenvis-integral-flux.csv')
csv_energy = df['Energy (MeV)'].to_numpy()
csv_flux = df['Integral Flux'].to_numpy()


# 3. Helper function for log-log interpolation of integral flux F(E)
def interpolate_integral_flux(energy_points, raw_energy, raw_flux):
    log_raw_energy = np.log(raw_energy)
    log_raw_flux = np.log(raw_flux)
    log_target_energy = np.log(energy_points)

    log_interpolated_flux = np.interp(
        log_target_energy, log_raw_energy, log_raw_flux
    )
    return np.exp(log_interpolated_flux)


# 4. Compute class-wise flux for each bin
SPENVIS_BINS = []
for e_min, e_max in TARGET_INTERVALS:
    f_min = interpolate_integral_flux(e_min, csv_energy, csv_flux)
    f_max = interpolate_integral_flux(e_max, csv_energy, csv_flux)

    # Class-wise flux = F(E_min) - F(E_max)
    interval_flux = f_min - f_max

    SPENVIS_BINS.append((e_min, e_max, float(interval_flux)))


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

    with open(args.output, mode='w', newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)
        header = ['Energy_MeV', 'Integral_Flux', 'Status']
        writer.writerow(header)
        for E_lo, E_hi, n, rep_e, _ in plan:
            paths = files_by_energy[rep_e]
            for i in range(n):
                path = random.choice(paths)
                df = pd.read_csv(path)
                # TODO: Actually filter consolidate the stuff




if __name__ == '__main__':
    main()
