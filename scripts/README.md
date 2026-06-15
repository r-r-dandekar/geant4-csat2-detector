# scripts/

Helper scripts for running energy sweeps and plotting the results.

## `run_sweep.sh`
Runs the simulation at a list of proton energies, appending one summary row per
energy to a single CSV. Run from the build directory (where `dsim` lives):

```bash
bash ../scripts/run_sweep.sh results/sweep.csv [nevents] [ydiv] [mode]
```

- `results/sweep.csv` — output path (required)
- `nevents` — protons per energy (default 500)
- `ydiv` — light-yield divisor (default 1000)
- `mode` — `ideal` or `realistic` (default `ideal`)

The simulation program writes the CSV header itself, so this script only starts
a fresh file and loops.

## `plot_results.py`
Reads a sweep CSV **by column header** and writes graphs versus proton energy
(primary fate, primary energy deposition, optical-photon energy deposition, and
scintillation light) as PNGs plus a combined PDF.

```bash
pip install -r requirements.txt        # pandas + matplotlib (first time only)
python plot_results.py results/sweep.csv [output_dir]
```

If `output_dir` is omitted, figures go in `<csv-stem>_plots/` next to the CSV.
It writes the four grouped figures + a combined PDF, and also one graph per
individual quantity in an `individual/` subdirectory (reproducing every graph
the old LibreOffice script produced, plus the new observables).
