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
| `timelog=<dir>`      | Enable per-proton time logging into `<dir>` (see below). Independent of `results_file`. | — (off) |
| `timetag=<tag>`      | Run tag used in time-log filenames. Defaults to a launch timestamp.     | timestamp |
| `<file>.mac`         | Geant4 macro to execute (batch mode)                                    | —        |

Example: `./dsim energy=100 ydiv=1000 mode=ideal results_file=results/run.csv macros/run.mac`

## Energy sweep

To sweep many energies into one CSV (one row per energy), run from the build
directory:

```bash
bash ../scripts/run_sweep.sh results/sweep.csv [nevents] [ydiv] [mode]
```

e.g. `bash ../scripts/run_sweep.sh results/sweep.csv 500 1000 ideal`.

## Per-proton time logging

With `timelog=<dir>`, every proton (event) writes its own detail CSV recording
*when* it interacts with the detector and *when* each scintillation photon is
detected:

```bash
./dsim energy=100 timelog=timelogs macros/run.mac     # beamOn N -> N detail files
```

Each detail file `evt_E<energy>MeV_<runtag>_id<eventID>.csv` has one row per
interaction (sorted by time):

```
# proton_energy_MeV=100, event_id=7, run_tag=20260615_142233
time_ns,interaction,particle,energy_MeV
0.512,enter_CD,proton,99.81
0.673,enter_CsI,proton,98.90
1.21,photon_at_photodiode,opticalphoton,2.95e-06
...
```

`interaction` ∈ {`enter_CD`, `exit_CD`/`stop_CD`, `enter_CsI`, `exit_CsI`/`stop_CsI`,
`enter_ACD`, `exit_ACD`/`stop_ACD`, `enter_PD`, `exit_PD`/`stop_PD`,
`photon_at_photodiode`}. `enter_PD`/`exit_PD`/`stop_PD` are the proton's own
direct passage through the photodiode silicon — distinct from
`photon_at_photodiode`, which is an optical-photon detection, not a proton
interaction. The `<runtag>` defaults to a launch timestamp (override with
`timetag=`) so repeated runs into the same folder never collide.

A per-run **aggregated index** `index_<runtag>.csv` is also written, one row per
proton, carrying the proton's interaction times/energies and entry/exit flags
(but **not** the photon detections — those stay in the detail files):

```
event_id,file,energy_MeV,
entered_CD,stopped_in_CD,entered_CsI,stopped_in_CsI,entered_ACD,stopped_in_ACD,
entered_PD,stopped_in_PD,
t_enter_CD_ns,ke_enter_CD_MeV,t_leave_CD_ns,ke_leave_CD_MeV,
t_enter_CsI_ns,ke_enter_CsI_MeV,t_leave_CsI_ns,ke_leave_CsI_MeV,
t_enter_ACD_ns,ke_enter_ACD_MeV,t_leave_ACD_ns,ke_leave_ACD_MeV,
t_enter_PD_ns,ke_enter_PD_MeV,t_leave_PD_ns,ke_leave_PD_MeV
```

`t_leave_*_ns`/`ke_leave_*_MeV` are blank if the proton never entered that
element. `ke_leave` is `0` when `stopped_in_*` is `1` (the proton ranged out
inside), otherwise it is the exit kinetic energy. Energy deposited in an
element is `ke_enter_*_MeV - ke_leave_*_MeV` in both cases.

> For physically correct photon counts/timing in the detail files, run with
> `ydiv=1` (the divisor reduces the simulated photon count).

The sweep script can enable this too (5th argument), using a per-energy run tag:

```bash
bash ../scripts/run_sweep.sh results/sweep.csv 500 1000 ideal timelogs
```

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
