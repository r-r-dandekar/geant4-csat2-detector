#!/bin/bash
#
# Energy sweep: run the simulation at many proton energies and append one row
# per energy to a single CSV. The simulation program owns the CSV header, so
# this script only has to start a fresh file and loop.
#
# Run from the build directory (where the `dsim` executable lives):
#   bash ../scripts/run_sweep.sh results/sweep.csv [nevents] [ydiv] [mode] [timelog_dir]
#
#   <output.csv>   required - path to the aggregate results CSV
#   [nevents]      protons per energy (default 500)
#   [ydiv]         light-yield divisor (default 1000)
#   [mode]         ideal | realistic (default ideal)
#   [timelog_dir]  if given, also write per-proton time-log files into this
#                  folder, using a per-energy run tag (one index per energy)

set -e

OUT=${1:?Usage: run_sweep.sh <output.csv> [nevents] [ydiv] [mode] [timelog_dir]}
NEVENTS=${2:-500}
YDIV=${3:-1000}
MODE=${4:-ideal}
TIMELOG_DIR=${5:-}

if [ ! -x ./dsim ]; then
    echo "Error: ./dsim not found. Run this from the build directory." >&2
    exit 1
fi

# Energy points (MeV).
ENERGIES="0.1 0.25 0.5 0.75 1 2.5 5 7.5 10 10.5 11 12.5 15 20 30 40 50 60 70 80 90 100 110 125 150 175 200"

# Start a fresh file so the program writes a new header row.
mkdir -p "$(dirname "$OUT")"
rm -f "$OUT"

# Temporary macro: initialise then fire NEVENTS protons.
MAC=$(mktemp sweep_XXXX.mac)
cat > "$MAC" <<EOF
/run/initialize
/run/beamOn $NEVENTS
EOF

for E in $ENERGIES; do
    echo "  energy=${E} MeV ..."
    if [ -n "$TIMELOG_DIR" ]; then
        # Per-energy run tag so each energy gets its own index file.
        ./dsim energy="$E" ydiv="$YDIV" mode="$MODE" results_file="$OUT" \
               timelog="$TIMELOG_DIR" timetag="E${E}MeV" "$MAC" > /dev/null
    else
        ./dsim energy="$E" ydiv="$YDIV" mode="$MODE" results_file="$OUT" "$MAC" > /dev/null
    fi
done

rm -f "$MAC"
echo "Done. Results written to $OUT"
