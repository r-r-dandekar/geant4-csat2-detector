# scripts/

Helper scripts for running energy sweeps and plotting the results.

### Note
In most of the scripts here, a shell variable called SUBDIR is used. To set this, you can run something like `SUBDIR=mysubdir`.
This is just a quick way to set what sub-directory under `./results` the results are stored in, and allows just copy-pasting the commands from here after you set the variable in your terminal. For example, the above command would be used if the results are all stored in `./results/mysubdir/`. I usually use the current date, but you can use anything that helps you keep organized better.


## `run_sweep.sh`
Runs the simulation at a list of proton energies, appending one summary row per
energy to a single CSV. Run from the build directory (where `dsim` lives):

```bash
bash ../scripts/run_sweep.sh [sweep_csv_path] [nevents] [ydiv] realistic [timelogs_dir]
```

For example,
```bash
bash ../scripts/run_sweep.sh ../results/$SUBDIR/sweep.csv 10000 10000 realistic ../results/$SUBDIR/timelogs
```

- `results/sweep.csv` — output path (required)
- `nevents` — protons per energy (default 500)
- `ydiv` — light-yield divisor (default 1000)
- `mode` — `ideal` or `realistic` (default `ideal`)

The simulation program writes the CSV header itself, so this script only starts
a fresh file and loops.


## consolidate_timelogs.py
The data generated from run_sweep.sh is divided into thousands of .csv files, and does not represent the energy distribution of protons that are actually present in space.
`consolidate_timelogs.py` combines the data from these .csv files into a single file, while shifting the data by randomized amounts of time, and including different numbers of protons of different energy levels, to replicate the distribution of protons as per SPENVIS simulations.

Sample usage:
```bash
python consolidate_timelogs.py ../results/$SUBDIR/timelogs --duration-ms 500 --output ../results/$SUBDIR/consolidated.csv
```


## isolate_photons_in_consolidated.py
The data generated from `consolidate_timelogs.py` contains information of both protons and photons.
`isolate_photons_in_consolidated` filters out the proton entries, leaving only the photon entries, and saves them to an output file.

Sample usage:
```bash
python isolate_photons_in_consolidated.py --input="../results/$SUBDIR/consolidated.csv" --output="../results/$SUBDIR/consolidated_photons_only.csv"
```