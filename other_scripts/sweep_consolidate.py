"""Consolidate per-proton Geant4 timelog files into one flux-weighted,
time-ordered event stream (protons + optical photons), scaled to a target
real-world observation window (SIM_DURATION_NS).

Rewritten for memory- and runtime-scalability. The original implementation:
  (a) resampled from a few hundred raw evt files up to `flux` times each
      (e.g. 76.6M for the 0.5 MeV bin) via random.choices(), re-opening and
      re-parsing the SAME handful of files line-by-line in Python up to
      ~100,000x each -- almost all of that work was pure duplication.
  (b) appended every resampled event as a Python tuple to one growing list,
      then called list.sort() on the whole thing -- at ~380M+ events that's
      tens of GB of pure object overhead, held in RAM all at once before any
      output is written. This is what was causing the OOM kill.

A later revision fixed (a) and (b) via per-energy chunking + a final
heapq.merge() across the sorted chunk files. That fixed memory, but the final
merge was still a pure-Python, row-by-row csv.reader/csv.writer/heapq loop --
at hundreds of millions of rows, per-row Python object overhead made that
merge step itself extremely slow (likely tens of minutes to hours).

This version keeps the memory-bounded per-energy chunked generation, but
replaces the slow row-by-row merge with TIME-WINDOW BUCKETING:
  1. Parse each unique raw evt file exactly once (cached).
  2. Generate each energy's flux-weighted resampling in bounded-size chunks
     (MAX_PROTONS_PER_CHUNK), vectorized with NumPy.
  3. Instead of sorting each chunk and writing one chunk file, split each
     chunk's rows into N_TIME_WINDOWS non-overlapping on-disk buckets by
     time (vectorized: one sort-by-window-index groups rows into contiguous
     slices, no per-row Python loop). Every chunk from every energy appends
     into the same set of window files.
  4. Finalize by reading each window file ONCE, IN INCREASING TIME ORDER,
     sorting it (fast -- each window holds roughly total_rows/N_TIME_WINDOWS
     rows, not the whole sweep) and appending it straight to the final
     output. Since windows are non-overlapping and processed in time order,
     concatenating their sorted contents is globally time-sorted -- no
     cross-window merge step is needed at all.
This keeps peak memory bounded (one chunk during generation, one window
during finalization -- neither scales with total row count) while doing
every hot-path operation as a vectorized NumPy/pandas bulk operation instead
of per-row Python.
"""

import os
import re
import tempfile

import numpy as np
import pandas as pd
from tqdm import tqdm

# ---- Configuration ----------------------------------------------------------
SIM_DURATION_NS = 2_500_000
DATA_DIR = './sweep_timelogs'
OUTPUT_FILENAME = 'simulated_proton_photon_strikes_2500_us.csv'
SEED = None  # set an int for reproducible runs

# Bounds peak memory during GENERATION: each chunk's arrays (protons + their
# photons) are held in RAM only long enough to bucket and append them. Tune
# down if your machine has less RAM; tune up for fewer, larger append calls.
MAX_PROTONS_PER_CHUNK = 5_000_000

# Bounds peak memory during FINALIZATION (the sort-and-append pass): each
# window holds roughly (total rows / N_TIME_WINDOWS) at a time, not the whole
# sweep. More windows = smaller/faster individual sorts but more small
# per-chunk append calls during generation; fewer windows = the opposite.
N_TIME_WINDOWS = 256

# Updated Energy Levels
TARGET_ENERGIES = [0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, 10.5, 11.0,
                   12.5, 15.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0,
                   100.0, 110.0, 125.0, 150.0, 175.0, 200.0]

# Differential proton flux, protons/cm^2/s, per energy (SPENVIS-derived --
# rank-correlates strongly (Spearman ~0.9) with the AP-8 MAX integral flux
# table, but is NOT a constant-factor derivative of it; treat these as the
# best-available differential flux values, not literal event counts).
# Keys must correspond to your simulation's data file energy labels.
#
# FIX (was a bug): this used to be used directly as an absolute proton count
# (`int(get_interpolated_flux(energy))`), with no duration or area scaling --
# meaning changing SIM_DURATION_NS never changed the output size, only how
# tightly the same huge count was packed in time. That contradicted both (a)
# generate_timeseries.py, which correctly does `n = flux * duration_s` for
# its own SPENVIS-derived flux table, and (b) plot_results.py's validation
# plots (spenvis_integral_flux.png / spenvis_differential_flux.png), whose
# entire method -- comparing (count / duration_s) against the SPENVIS
# reference curve -- only makes sense if count == flux_rate * duration * area
# by construction. Fixed below: flux is now a rate, converted to a count via
# rate * duration_s * AREA_CM2 in process_and_sort().
FLUX_MAP = {
    0.1: 51780000, 0.25: 44780000, 0.5: 76630000, 0.75: 52430000, 1.0: 36880000,
    2.5: 25952000, 5.0: 18829000, 7.5: 34725000, 10.0: 24014000, 10.5: 9228900,
    11.0: 3991000, 12.5: 1438800, 15.0: 656000, 20.0: 463900, 30.0: 324970,
    40.0: 479030, 50.0: 228530, 60.0: 50173, 70.0: 23435, 80.0: 7138,
    90.0: 5694, 100.0: 2743, 110.0: 2089, 125.0: 5029, 150.0: 5342,
    175.0: 3071, 200.0: 2621
}

# Detector active area (cm^2) the FLUX_MAP rate is applied over -- matches the
# simulated 10mm x 10mm active cross-section (DetectorConstants.hh:
# kCrossSectionX = kCrossSectionY = 1.0 cm), i.e. the real hardware's face.
AREA_CM2 = 1.0

# Testing knob: scales every FLUX_MAP value by this factor (e.g. 1e-6 to turn
# ~76.6M protons/cm^2/s into ~77 protons/cm^2/s equivalent). This is on top of
# the rate*duration_s*AREA_CM2 conversion below, so it still shrinks a test
# run's output regardless of SIM_DURATION_NS.
FLUX_MULTIPLIER = 1.0

# NOTE on output size: the total row count is driven by
# sum(FLUX_MAP.values()) * FLUX_MULTIPLIER * (SIM_DURATION_NS * 1e-9) *
# AREA_CM2, NOT by how many raw evt files exist on disk. SIM_DURATION_NS now
# DOES change the output size (longer window -> proportionally more events,
# same as a real detector would see) -- this differs from earlier advice in
# this file's history, back when flux was used as a bare count. If the
# resulting output is impractically large, reduce SIM_DURATION_NS,
# FLUX_MULTIPLIER, or the FLUX_MAP values themselves.

def get_interpolated_flux(target_energy):
    """Linear interpolation for flux levels not explicitly in the map (rate,
    protons/cm^2/s), scaled by FLUX_MULTIPLIER. Does NOT include duration or
    area -- see process_and_sort() for the rate -> count conversion."""
    keys = sorted(FLUX_MAP.keys())
    return np.interp(target_energy, keys, [FLUX_MAP[k] for k in keys]) * FLUX_MULTIPLIER

# Detector elements whose proton entry/exit times we pull out of each evt
# file, in beam order. For CsI(Tl), energy deposited must come from the
# PROTON's own enter/exit kinetic energy (these rows), NOT from the optical
# photons it produces -- those are handled separately, unchanged, below. "PD"
# is the proton's own direct passage through the photodiode silicon, distinct
# from the photon_at_photodiode rows (which stay in the photon-only pipeline).
TRACKED_ELEMENTS = ['CD', 'CsI', 'ACD', 'PD']
N_ELEM = len(TRACKED_ELEMENTS)

# Matches filenames written by EventAction, e.g. evt_E100MeV_E100MeV_id7.csv
# (energy tag uses C's "%g" formatting -- 100.0 -> "100", not "100.0"; this
# was verified byte-for-byte against C's snprintf("%g", ...) for every value
# in TARGET_ENERGIES, so a Python/C formatting mismatch is NOT the cause of
# any energy silently having zero matched files -- see resolve_energy_files).
EVT_RE = re.compile(r'^evt_E([\d.]+)MeV_.*\.csv$', re.IGNORECASE)


def elem_col_names():
    names = []
    for elem in TRACKED_ELEMENTS:
        names += [f't_enter_{elem}_ns', f't_exit_{elem}_ns', f'edep_{elem}_MeV']
    return names


def discover_files(data_dir):
    """Group raw evt files by the energy tag embedded in their filename
    (as a string, to avoid float dict-key equality pitfalls)."""
    files_by_tag = {}
    for name in os.listdir(data_dir):
        m = EVT_RE.match(name)
        if not m:
            continue
        files_by_tag.setdefault(m.group(1), []).append(os.path.join(data_dir, name))
    return files_by_tag


def resolve_energy_files(energy, files_by_tag):
    """Find the files for `energy`: exact %g-formatted tag match first (the
    normal case), falling back to the numerically-nearest discovered tag
    (within a tight relative tolerance) in case some files on disk used a
    different run/naming convention than expected. Returns (files, tag) or
    (None, None) if nothing close enough was found.
    """
    tag = f"{energy:g}"
    files = files_by_tag.get(tag)
    if files is not None:
        return files, tag

    best_tag, best_diff = None, None
    for t in files_by_tag:
        try:
            val = float(t)
        except ValueError:
            continue
        diff = abs(val - energy)
        if best_diff is None or diff < best_diff:
            best_tag, best_diff = t, diff

    if best_tag is not None and best_diff <= max(1e-6, 1e-6 * energy):
        return files_by_tag[best_tag], best_tag

    return None, None


def print_energy_match_report(files_by_tag):
    """Unmissable diagnostic printed BEFORE any (potentially long)
    processing: which TARGET_ENERGIES actually matched files, and how many.
    A silent per-energy skip used to only print one easy-to-miss warning line
    buried among tqdm progress bars -- this makes the root cause of any
    missing energy visible immediately, on the very next run."""
    print("\nEnergy -> matched files:")
    any_missing = False
    for energy in TARGET_ENERGIES:
        files, matched_tag = resolve_energy_files(energy, files_by_tag)
        n = len(files) if files else 0
        flag = ""
        if not files:
            flag = "  <-- NO FILES FOUND"
            any_missing = True
        elif matched_tag != f"{energy:g}":
            flag = f"  (matched via fallback tag '{matched_tag}', not exact)"
        print(f"  {energy:>7g} MeV  (expected tag '{energy:g}'): {n:>7} files{flag}")
    if any_missing:
        print("  Discovered tags on disk:", sorted(files_by_tag.keys()))
    print()


def parse_event_file(file_path):
    """Parse one per-proton evt CSV -- exactly once per unique file, cached
    by the caller across every chunk/energy that resamples it.

    Returns (photon_times, photon_energies, elem_arr):
      photon_times/energies -- float64 arrays, one entry per detected photon.
      elem_arr -- float64 array shape (N_ELEM, 3): columns
                  (t_enter_ns, t_exit_ns, edep_MeV) per tracked element, row
                  order matching TRACKED_ELEMENTS; NaN where the proton never
                  entered/exited that element. edep is derived purely from
                  the proton's own enter/exit rows, never from photons.
    """
    photon_times, photon_energies = [], []
    enter, exit_ = {}, {}

    with open(file_path, 'r') as f_in:
        for line in f_in:
            if line.startswith('#') or line.startswith('time_ns'):
                continue
            parts = line.rstrip('\n').split(',')
            if len(parts) < 4:
                continue
            t_ns, interaction, particle, energy = parts

            if particle == 'opticalphoton':
                photon_times.append(float(t_ns))
                photon_energies.append(float(energy))
                continue

            for elem in TRACKED_ELEMENTS:
                if interaction == f'enter_{elem}':
                    enter[elem] = (float(t_ns), float(energy))
                elif interaction in (f'exit_{elem}', f'stop_{elem}'):
                    exit_[elem] = (float(t_ns), float(energy))

    elem_arr = np.full((N_ELEM, 3), np.nan, dtype=np.float64)
    for i, elem in enumerate(TRACKED_ELEMENTS):
        e_in, e_out = enter.get(elem), exit_.get(elem)
        if e_in is not None:
            elem_arr[i, 0] = e_in[0]
        if e_out is not None:
            elem_arr[i, 1] = e_out[0]
        if e_in is not None and e_out is not None:
            elem_arr[i, 2] = e_in[1] - e_out[1]

    return (np.asarray(photon_times, dtype=np.float64),
            np.asarray(photon_energies, dtype=np.float64),
            elem_arr)


def generate_chunk_rows(files, energy, n_protons, rng, cache):
    """Vectorized generation of one chunk's proton+photon rows.

    `cache` maps file_path -> parse_event_file(path), populated lazily so
    each unique file is parsed exactly once for the whole run no matter how
    many times / in how many chunks it gets resampled.

    Returns (time, is_proton, energy, elem_cols) NumPy arrays for this chunk
    only (unsorted, unwritten).
    """
    n_files = len(files)
    proton_times = rng.uniform(0.0, SIM_DURATION_NS, size=n_protons)
    file_indices = rng.integers(0, n_files, size=n_protons)
    unique_idxs, inverse = np.unique(file_indices, return_inverse=True)

    loaded = []
    for idx in unique_idxs:
        path = files[idx]
        if path not in cache:
            cache[path] = parse_event_file(path)
        loaded.append(cache[path])

    # --- proton rows: vectorized fancy-index lookup (no per-proton Python
    # loop -- elem_by_file is only as large as the number of unique files
    # used in this chunk, typically a few hundred to a couple thousand).
    elem_by_file = np.stack([ld[2] for ld in loaded])   # (n_used_files, N_ELEM, 3)
    elem_for_proton = elem_by_file[inverse]              # (n_protons, N_ELEM, 3)

    proton_elem_cols = np.empty((n_protons, 3 * N_ELEM), dtype=np.float64)
    proton_elem_cols[:, 0::3] = elem_for_proton[:, :, 0] + proton_times[:, None]  # t_enter
    proton_elem_cols[:, 1::3] = elem_for_proton[:, :, 1] + proton_times[:, None]  # t_exit
    proton_elem_cols[:, 2::3] = elem_for_proton[:, :, 2]                          # edep (unshifted)

    time_chunks      = [proton_times]
    is_proton_chunks = [np.ones(n_protons, dtype=bool)]
    energy_chunks    = [np.full(n_protons, energy, dtype=np.float64)]
    elem_chunks      = [proton_elem_cols]

    # --- photon rows: group protons by which file they used via a single
    # sort (not one O(n_protons) boolean mask per file), then broadcast the
    # time shift per group -- same trick as generate_timeseries.py, but
    # grouped with searchsorted instead of repeated masks since n_protons
    # per chunk can be in the millions.
    group_order = np.argsort(inverse, kind='stable')
    sorted_inverse = inverse[group_order]
    boundaries = np.searchsorted(sorted_inverse, np.arange(len(loaded) + 1))

    for local_idx, (p_times, p_energies, _elem) in enumerate(loaded):
        if p_times.size == 0:
            continue
        members = group_order[boundaries[local_idx]:boundaries[local_idx + 1]]
        if members.size == 0:
            continue
        t_sel = proton_times[members]
        shifted = (t_sel[:, None] + p_times[None, :]).ravel()
        energies = np.tile(p_energies, len(t_sel))

        time_chunks.append(shifted)
        is_proton_chunks.append(np.zeros(shifted.size, dtype=bool))
        energy_chunks.append(energies)
        elem_chunks.append(np.full((shifted.size, 3 * N_ELEM), np.nan, dtype=np.float64))

    return (np.concatenate(time_chunks),
            np.concatenate(is_proton_chunks),
            np.concatenate(energy_chunks),
            np.concatenate(elem_chunks, axis=0))


def window_index(time_arr):
    """Map absolute times to a time-window bucket index in [0, N_TIME_WINDOWS)."""
    idx = np.floor(time_arr / SIM_DURATION_NS * N_TIME_WINDOWS).astype(np.int64)
    return np.clip(idx, 0, N_TIME_WINDOWS - 1)


def append_chunk_to_windows(time_arr, is_proton_arr, energy_arr, elem_arr, window_dir):
    """Split one generated chunk's rows into N_TIME_WINDOWS on-disk buckets by
    time and append each bucket to its own window file. Vectorized: a single
    sort-by-window-index groups rows into contiguous slices (no per-row
    Python loop, no per-window boolean mask)."""
    widx = window_index(time_arr)
    order = np.argsort(widx, kind='stable')
    widx_sorted = widx[order]
    boundaries = np.searchsorted(widx_sorted, np.arange(N_TIME_WINDOWS + 1))

    particle_col  = np.where(is_proton_arr[order], 'proton', 'opticalphoton')
    time_sorted   = time_arr[order]
    energy_sorted = energy_arr[order]
    elem_sorted   = elem_arr[order]

    for w in range(N_TIME_WINDOWS):
        lo, hi = boundaries[w], boundaries[w + 1]
        if hi <= lo:
            continue

        df = pd.DataFrame({
            'particle': particle_col[lo:hi],
            'time': time_sorted[lo:hi],
            'energy': energy_sorted[lo:hi],
        })
        for i, col in enumerate(elem_col_names()):
            df[col] = elem_sorted[lo:hi, i]

        win_path = os.path.join(window_dir, f"win_{w:04d}.csv")
        write_header = not os.path.exists(win_path)
        df.to_csv(win_path, mode='a', index=False, header=write_header, na_rep='')


def finalize_windows(window_dir, output_path):
    """Read each time-window file ONCE, in increasing time order, sort it
    (fast -- each window holds roughly total_rows/N_TIME_WINDOWS rows, not
    the whole sweep) and append it straight to the final output. Since
    windows are non-overlapping and processed in time order, concatenating
    their sorted contents is globally time-sorted -- no cross-window merge
    needed."""
    header = ['particle', 'time', 'energy'] + elem_col_names()
    with open(output_path, 'w', newline='') as f_out:
        f_out.write(','.join(header) + '\n')

    for w in tqdm(range(N_TIME_WINDOWS), desc="Finalizing time windows"):
        win_path = os.path.join(window_dir, f"win_{w:04d}.csv")
        if not os.path.exists(win_path):
            continue
        # Each window file already carries its own header (written once, by
        # the first append_chunk_to_windows() call that created it) -- read
        # it normally rather than overriding with header=None/names=, which
        # would misread that real header line as a data row.
        df = pd.read_csv(win_path)
        df.sort_values('time', kind='mergesort', inplace=True)  # stable
        df.to_csv(output_path, mode='a', index=False, header=False, na_rep='')
        os.remove(win_path)
        del df


def process_and_sort():
    files_by_tag = discover_files(DATA_DIR)
    if not files_by_tag:
        print(f"Error: no evt files found in {DATA_DIR}")
        return

    print_energy_match_report(files_by_tag)

    rng = np.random.default_rng(SEED)
    cache = {}  # file_path -> parse_event_file(path), shared across all chunks

    window_dir = tempfile.mkdtemp(prefix='sweep_consolidate_windows_')
    total_protons = 0
    total_photons = 0
    any_processed = False

    duration_s = SIM_DURATION_NS * 1e-9
    print(f"Duration: {SIM_DURATION_NS} ns ({duration_s:.3e} s), "
          f"area: {AREA_CM2} cm^2, flux multiplier: {FLUX_MULTIPLIER}")
    print(f"Temp dir for time-window buckets: {window_dir}")

    for energy in TARGET_ENERGIES:
        files, _ = resolve_energy_files(energy, files_by_tag)
        if not files:
            print(f"Warning: No files for {energy} MeV. Skipping.")
            continue

        # rate (protons/cm^2/s) -> count, matching generate_timeseries.py's
        # own flux*duration convention (see FLUX_MAP comment above).
        flux_rate = get_interpolated_flux(energy)
        flux = int(round(flux_rate * duration_s * AREA_CM2))
        if flux == 0:
            continue

        any_processed = True
        n_chunks = -(-flux // MAX_PROTONS_PER_CHUNK)  # ceil division
        remaining = flux
        for _chunk_i in tqdm(range(n_chunks), desc=f"{energy:g} MeV", leave=False):
            n_protons = min(MAX_PROTONS_PER_CHUNK, remaining)
            remaining -= n_protons

            time_arr, is_proton_arr, energy_arr, elem_arr = generate_chunk_rows(
                files, energy, n_protons, rng, cache)

            append_chunk_to_windows(time_arr, is_proton_arr, energy_arr, elem_arr, window_dir)

            total_protons += n_protons
            total_photons += int((~is_proton_arr).sum())

            # Free this chunk's arrays before the next one starts -- peak
            # memory stays bounded to one chunk, not the whole sweep.
            del time_arr, is_proton_arr, energy_arr, elem_arr

    if not any_processed:
        print("Error: nothing generated -- check DATA_DIR and TARGET_ENERGIES.")
        os.rmdir(window_dir)
        return

    print(f"Finalizing {N_TIME_WINDOWS} time windows into {OUTPUT_FILENAME} ...")
    finalize_windows(window_dir, OUTPUT_FILENAME)
    os.rmdir(window_dir)

    print(f"Process finished. Generated {total_protons} protons and {total_photons} photons.")


if __name__ == "__main__":
    process_and_sort()
