# Particle Detector Simulation (Geant4)

A Geant4 simulation of a proton-detector telescope:

```
beam +z ->  [Al window] [Si C.D.] === vacuum gap === [CsI(Tl) + side photodiode, teflon-wrapped] [Si A.C.D.]
```

- **Al window** – stops protons below ~10 MeV
- **Si coincidence detector (C.D.)** – flags a proton entering
- **vacuum gap**
- **CsI(Tl) scintillator** – produces light when a proton deposits energy; wrapped in reflective teflon with an optical window onto the photodiode
- **photodiode** – reads the scintillation light (side-mounted on the CsI)
- **Si anti-coincidence detector (A.C.D.)** – flags a proton leaving (> ~100 MeV)

Target: **Geant4 11.4.1**.

Outputs an end-of-run summary to the console and (optionally) a one-row-per-run
CSV. A sweep script and a matplotlib plotting script turn an energy scan into
graphs.

## Building

```bash
cd new-code
mkdir -p build && cd build
cmake ..
make -j
```

This produces the `dsim` executable and copies the macros into `build/macros/`.

## Running

Interactive (opens a visualisation window):

```bash
./dsim
```

Batch mode with a macro and a chosen beam energy:

```bash
./dsim energy=100 macros/run.mac
```

### Command-line arguments

Arguments are conventionally given in this order: `energy=`, `ydiv=`, `mode=`,
`results_file=`, then the macro file. (Order is not enforced.)

| Argument             | Meaning                                                                 | Default  |
|----------------------|-------------------------------------------------------------------------|----------|
| `energy=<MeV>`       | Kinetic energy of each primary proton                                   | 50 MeV   |
| `ydiv=<N>`           | Light-yield divisor: divides the CsI(Tl) scintillation yield to keep the optical-photon count tractable (higher = fewer photons = faster). Does not affect energy deposition. | 1000 |
| `mode=ideal\|realistic` | Beam mode. `ideal`: pencil beam, normal incidence at the centre. `realistic`: uniform over the 10×10 mm face with cosine-law (Lambertian) incidence, modelling an isotropic external flux. | ideal |
| `results_file=<path>`| Append a one-row run summary to this CSV (the program writes the header if the file is new). Omit for console-only output. | — (none) |
| `<file>.mac`         | Geant4 macro to execute (batch mode)                                    | —        |

Example: `./dsim energy=100 ydiv=1000 mode=ideal results_file=results/run.csv macros/run.mac`

## Energy sweep

To sweep many energies into one CSV (one row per energy), run from the build
directory:

```bash
bash ../scripts/run_sweep.sh results/sweep.csv [nevents] [ydiv] [mode]
```

e.g. `bash ../scripts/run_sweep.sh results/sweep.csv 500 1000 ideal`.

## Plotting

Turn a sweep CSV into graphs (versus proton energy) with the matplotlib script:

```bash
pip install -r ../scripts/requirements.txt     # pandas + matplotlib (first time)
python ../scripts/plot_results.py results/sweep.csv
```

PNGs and a combined PDF are written to `results/sweep_plots/`, with one graph
per individual quantity in a `results/sweep_plots/individual/` subdirectory. The
script reads the CSV by column header, so it is unaffected by column reordering.

The beam energy is controlled **only** by `energy=` — the `/gun/energy` macro
command is intentionally not used.

## Layout

| Path        | Contents                                  |
|-------------|-------------------------------------------|
| `payload.cc`| `main()` — run manager, physics, startup  |
| `include/`  | Class headers + `DetectorConstants.hh`    |
| `src/`      | Class implementations                     |
| `macros/`   | Visualisation and run macros              |
| `scripts/`  | Energy-sweep + analysis scripts           |
