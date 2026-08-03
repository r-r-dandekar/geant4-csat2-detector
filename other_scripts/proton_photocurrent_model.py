#!/usr/bin/env python3
"""
Proton-Induced Photocurrent Model -- CD / ACD / PD (direct ionization)

Companion to photodiode_model.py, which models the PHOTON-induced
photocurrent at the photodiode (scintillation light -> photodiode via
responsivity/QE). This script models a SEPARATE mechanism: protons directly
ionizing the CD, ACD, and PD silicon as they pass through (or stop in) them.
The two mechanisms are approximately additive (see proton_photocurrent_plan.md)
-- summing this script's output with photodiode_model.py's would give total
photocurrent, but only if both are run over consistently-generated data with a
shared timeline; they are written as separate files here rather than assumed
summed (see Assumption 2 below).

ASSUMPTIONS (decided here; see proton_photocurrent_plan.md for the full
derivation and datasheet numbers -- restate/revisit if these don't hold):

  1. Charge collection efficiency ~100% for CD, ACD, and PD at the intended
     70V bias. All three are the same Si PIN photodiode part, and PIN diodes
     are designed so their thin active region is essentially fully depleted
     at rated bias -- confirmed here since the datasheet's 300um depletion
     thickness at 70V exactly matches the modeled Si thickness of all three
     elements (DetectorConstants.hh). No collection-efficiency discount is
     applied.

  2. Output is SEPARATE per element (proton_photocurrent_CD.csv/.pwl, etc.),
     not summed with photodiode_model.py's photon-induced current. Combining
     them later requires both scripts to be run over data sharing a common
     absolute timeline (not automatically true today -- this script scans
     ITS OWN input for its own time axis, shared only across CD/ACD/PD, not
     against photodiode_model.py's separate PHOTON_FILE).

  3. Charge per hit uses W_Si = 3.6 eV/electron-hole pair -- direct ionization,
     NOT wavelength/responsivity-dependent (responsivity only applies to
     photon absorption, handled separately by photodiode_model.py).

  4. Pulse shape: a Gaussian transit-time kernel, matching
     photodiode_model.py's convention (SIGMA_TRANSIT), rather than a
     rectangular pulse built from the actual per-hit (t_exit - t_enter) we
     log. Chosen for architectural consistency with the existing photon
     script (same convolution machinery, trivial to add the two current
     streams together later) over the alternative's better physical
     grounding. SIGMA_TRANSIT below is derived from the datasheet's 300um
     depletion width at 70V: at that field (~2.33kV/cm, below Si's
     saturation threshold, so mobility-limited drift applies), the
     hole-limited full collection time is ~29ns; SIGMA_TRANSIT is set to
     roughly 1/3 of that so most of the Gaussian's mass falls within the
     physically expected collection window. This is a symmetric
     approximation (the same simplification photodiode_model.py already
     makes) -- it lets a little charge appear to arrive slightly before
     generation, which isn't causal, but is a small effect relative to the
     pulse width and gets smoothed further by TINA's own RC filtering
     downstream.

  5. The datasheet's 40MHz "cutoff frequency" is used ONLY for shot noise
     (same convention as photodiode_model.py), NOT for pulse shaping --
     it's almost certainly an RC/system bandwidth that would double-count
     with TINA's own C_t + R_L filtering if reused here.

  6. CD/ACD's plastic casing is not modeled (only their 300um active silicon
     is, per the DetectorConstants.hh geometry fix) -- energy loss in the
     casing material itself is not represented; edep already reflects only
     the 300um of modeled silicon.

  7. Uses t_enter_<elem>_ns as the single reference instant for when a hit's
     charge is generated (not spread across [t_enter, t_exit]) -- that
     window is normally far shorter than DT_NS and the transit-time
     convolution below, so treating it as instantaneous is a small
     simplification.

Bandwidth split (same convention as photodiode_model.py):
  - Carrier transit-time spread (sigma): modelled here via Gaussian convolution
  - RC bandwidth (R_L * C_t):            modelled in TINA via C_t + R_L
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# =============================================================================
# PARAMETERS -- edit here
# =============================================================================

INPUT_FILE = "simulated_proton_photon_strikes_1ms.csv"  # sweep_consolidate.py output
CHUNK_SIZE = 100_000               # rows per chunk while reading the input file
ELEMENTS   = ['CD', 'ACD', 'PD']   # tracked elements to model (CsI excluded on purpose)

# --- Photodiode part (same part used for CD, ACD, and PD) ---
F_C           = 40e6      # Cutoff frequency (Hz) -- used for shot noise only (assumption 5)
C_T           = 40e-12    # Junction capacitance (F) -- informational, used in TINA
SIGMA_TRANSIT = 10.0e-9   # Gaussian transit-time spread (s) -- derived from the ~29ns
                          # hole-limited collection time at 300um depletion / 70V bias
                          # (assumption 4). RC filtering is handled by C_t + R_L in TINA.

# --- Silicon ionization physics ---
W_SI = 3.6   # eV per electron-hole pair (direct ionization; not wavelength-dependent)

# --- Noise ---
SHOT_NOISE_ENABLED = True         # Shot noise from photocurrent (recommended: True)
GAUSSIAN_NOISE_RMS = 0.0          # Extra additive Gaussian noise RMS in amps (0 = off)
NOISE_SEED         = 42

# --- Time grid ---
DT_NS           = 0.1             # Time bin size (ns)
MAX_DURATION_US = 2500            # Limit processing to the first N microseconds
                                   # (default 2500us = 2.5ms) -- output size scales
                                   # with duration/DT_NS regardless of hit count, so
                                   # the full SIM_DURATION_NS (often 1s) is not
                                   # practical at this DT_NS. Set to None to use all
                                   # available data instead.

# --- Streaming convolution block size ---
CONV_BLOCK_SIZE = 1 << 18         # ~10MB per block at float64; larger = fewer FFTs

# --- Output ---
PLOT_WINDOW_START_NS    = 0
PLOT_WINDOW_DURATION_NS = 2000    # 2us plot window

PWL_DOWNSAMPLE = 1                # Write every Nth sample to PWL (1 = all points)

OUTPUT_PREFIX = "proton_photocurrent"  # -> {PREFIX}_{elem}.csv / .pwl / _plot.png

# =============================================================================
# PHYSICAL CONSTANTS
# =============================================================================

Q_CHARGE = 1.60217663e-19    # C

# =============================================================================
# GAUSSIAN KERNEL (transit-time broadening only; RC handled in TINA)
# =============================================================================

def build_gaussian_kernel(sigma, dt):
    """Normalised Gaussian kernel; integral over dt = 1 (charge-preserving)."""
    half_width = 5.0 * sigma
    t      = np.arange(-half_width, half_width + dt, dt)
    kernel = np.exp(-0.5 * (t / sigma) ** 2)
    kernel /= kernel.sum() * dt
    return kernel

# =============================================================================
# TIME RANGE SCAN -- single pass, shared across CD/ACD/PD
# =============================================================================

def scan_time_range(filepath, chunksize, elements):
    """Scan once for the overall [t_min, t_max] across all elements' entry
    times, so CD/ACD/PD end up on one common time grid (same t_min, same dt)
    -- convenient for aligning/summing them later even though they're
    written to separate files."""
    t_min, t_max = np.inf, -np.inf
    cols = [f't_enter_{e}_ns' for e in elements] + [f'edep_{e}_MeV' for e in elements]
    for chunk in pd.read_csv(filepath, chunksize=chunksize, usecols=cols):
        for e in elements:
            valid = chunk.loc[chunk[f'edep_{e}_MeV'].notna(), f't_enter_{e}_ns']
            if valid.empty:
                continue
            t_min = min(t_min, valid.min())
            t_max = max(t_max, valid.max())
    return float(t_min), float(t_max)

# =============================================================================
# STREAMING OVERLAP-ADD CONVOLUTION + DIRECT FILE OUTPUT (per element)
# =============================================================================

def stream_convolve_write(charge_arr, n_bins, kernel, t_min_ns, rng,
                           out_csv, out_pwl, elem_label):
    """Convolves charge_arr with kernel using overlap-add, block by block, and
    writes output directly to CSV and PWL without holding the full output
    array in RAM. Mirrors photodiode_model.py's stream_convolve_write exactly."""
    m          = len(kernel)
    block_size = CONV_BLOCK_SIZE
    fft_len    = 1 << int(np.ceil(np.log2(block_size + m - 1)))
    kernel_fft = np.fft.rfft(kernel.astype(np.float64), fft_len)

    overlap = np.zeros(m - 1, dtype=np.float64)
    dt_s    = DT_NS * 1e-9

    plot_lo_ns = t_min_ns + PLOT_WINDOW_START_NS
    plot_hi_ns = t_min_ns + PLOT_WINDOW_START_NS + PLOT_WINDOW_DURATION_NS
    plot_t_buf, plot_i_buf = [], []

    total_charge_out = 0.0
    n_blocks = (n_bins + block_size - 1) // block_size

    with open(out_csv, 'w') as cf, open(out_pwl, 'w') as pf:
        cf.write("time_s,current_A\n")
        pf.write(f"; TINA PWL photocurrent source -- proton-induced, {elem_label}\n")
        pf.write("; RC filtering handled by C_t + R_L in TINA circuit\n")
        pf.write("; time(s)  current(A)\n")

        for blk_num, blk_start in enumerate(range(0, n_bins, block_size)):
            blk_end = min(blk_start + block_size, n_bins)
            L       = blk_end - blk_start

            blk     = charge_arr[blk_start:blk_end].astype(np.float64)
            blk_fft = np.fft.rfft(blk, fft_len)
            conv    = np.fft.irfft(blk_fft * kernel_fft, fft_len)

            result = conv[:L + m - 1]
            if m > 1:
                result[:m - 1] += overlap
                overlap[:] = result[L:L + m - 1]

            out = result[:L].copy()

            if SHOT_NOISE_ENABLED:
                shot_rms = np.sqrt(2.0 * Q_CHARGE * np.abs(out) * F_C)
                out += rng.standard_normal(L) * shot_rms
            if GAUSSIAN_NOISE_RMS > 0.0:
                out += rng.normal(0.0, GAUSSIAN_NOISE_RMS, L)

            total_charge_out += out.sum() * dt_s

            global_idx = np.arange(blk_start, blk_end, dtype=np.int64)
            times_s    = t_min_ns * 1e-9 + global_idx * dt_s
            times_ns   = t_min_ns        + global_idx * DT_NS

            np.savetxt(cf, np.column_stack([times_s, out]),
                       fmt=['%.9e', '%.6e'], delimiter=',')

            pwl_sel = global_idx % PWL_DOWNSAMPLE == 0
            if pwl_sel.any():
                np.savetxt(pf, np.column_stack([times_s[pwl_sel], out[pwl_sel]]),
                           fmt=['%.9e', '%.6e'], delimiter=' ')

            plot_sel = (times_ns >= plot_lo_ns) & (times_ns <= plot_hi_ns)
            if plot_sel.any():
                plot_t_buf.append(times_ns[plot_sel].copy())
                plot_i_buf.append(out[plot_sel].copy())

            print(f"  [{elem_label}] Convolution: block {blk_num + 1}/{n_blocks} "
                  f"({blk_end / n_bins * 100:.1f}%)", end='\r', flush=True)

    print()
    plot_t = np.concatenate(plot_t_buf) if plot_t_buf else np.array([])
    plot_i = np.concatenate(plot_i_buf) if plot_i_buf else np.array([])
    return total_charge_out, plot_t, plot_i

# =============================================================================
# PER-ELEMENT PROCESSING
# =============================================================================

def process_element(elem, t_min_ns, t_max_ns, n_bins, rng):
    print(f"\n--- Element: {elem} ---")
    col_edep  = f'edep_{elem}_MeV'
    col_enter = f't_enter_{elem}_ns'

    charge_arr = np.zeros(n_bins, dtype=np.float32)
    n_hits = 0

    for chunk in pd.read_csv(INPUT_FILE, chunksize=CHUNK_SIZE,
                              usecols=[col_enter, col_edep]):
        valid = chunk[chunk[col_edep].notna()]
        if valid.empty:
            continue

        edep_mev = valid[col_edep].to_numpy(dtype=np.float64)
        t_ns     = valid[col_enter].to_numpy(dtype=np.float64)
        n_hits  += len(edep_mev)

        # Charge generation: direct ionization, W_Si = 3.6 eV/pair (assumption 3).
        n_pairs = (edep_mev * 1e6) / W_SI
        charges = (n_pairs * Q_CHARGE).astype(np.float32)

        in_range = (t_ns >= t_min_ns) & (t_ns <= t_max_ns)
        if not in_range.any():
            continue
        t_ns, charges = t_ns[in_range], charges[in_range]

        idx = np.floor((t_ns - t_min_ns) / DT_NS).astype(np.int64)
        idx = np.clip(idx, 0, n_bins - 1)
        np.add.at(charge_arr, idx, charges)

    total_charge_in = float(charge_arr.sum())
    print(f"  Proton hits processed : {n_hits:,}")
    print(f"  Total charge (in)     : {total_charge_in:.4e} C")

    kernel = build_gaussian_kernel(SIGMA_TRANSIT, DT_NS * 1e-9)
    print(f"  sigma_transit = {SIGMA_TRANSIT * 1e9:.2f} ns  "
          f"(kernel length {len(kernel)} samples, {len(kernel) * DT_NS:.1f} ns)")

    out_csv = f"{OUTPUT_PREFIX}_{elem}.csv"
    out_pwl = f"{OUTPUT_PREFIX}_{elem}.pwl"
    out_png = f"{OUTPUT_PREFIX}_{elem}_plot.png"

    total_charge_out, plot_t_ns, plot_i = stream_convolve_write(
        charge_arr, n_bins, kernel, t_min_ns, rng, out_csv, out_pwl, elem)
    del charge_arr

    err_pct = (abs(total_charge_out - total_charge_in)
               / max(total_charge_in, 1e-30) * 100)
    print(f"  Charge conservation error : {err_pct:.3f}%")
    print(f"  Saved: {out_csv}")
    print(f"  Saved: {out_pwl}")

    if len(plot_t_ns) > 0:
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot((plot_t_ns - t_min_ns) * 1e-3, plot_i * 1e6,
                linewidth=0.6, color='firebrick')
        ax.set_xlabel('Time relative to window start (µs)')
        ax.set_ylabel('Photocurrent (µA)')
        ax.set_title(f'Proton-induced photocurrent -- {elem} -- '
                     f'first {PLOT_WINDOW_DURATION_NS / 1000:.1f} µs')
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(out_png, dpi=150)
        plt.close(fig)
        print(f"  Saved: {out_png}")
    else:
        print(f"  WARNING: no data in plot window for {elem} "
              f"-- check PLOT_WINDOW_START_NS")

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("Proton-Induced Photocurrent Model (CD / ACD / PD)")
    print("=" * 60)

    print("\n[1/3] Scanning input file for time range (shared across CD/ACD/PD)...")
    t_min_ns, t_max_ns = scan_time_range(INPUT_FILE, CHUNK_SIZE, ELEMENTS)
    if MAX_DURATION_US is not None:
        t_max_ns = min(t_max_ns, t_min_ns + MAX_DURATION_US * 1e3)
        print(f"  Limiting to first {MAX_DURATION_US} µs  (t_max = {t_max_ns:.3f} ns)")

    span_ns = t_max_ns - t_min_ns
    n_bins  = int(np.ceil(span_ns / DT_NS)) + 1
    charge_mem_mb = n_bins * 4 / 1e6
    print(f"  Range  : {t_min_ns:.3f} - {t_max_ns:.3f} ns  ({span_ns * 1e-6:.4f} ms)")
    print(f"  Bins   : {n_bins:,}  (dt = {DT_NS} ns)")
    print(f"  Charge array (float32) per element : ~{charge_mem_mb:.0f} MB")

    rng = np.random.default_rng(NOISE_SEED)

    print("\n[2/3] Processing each element...")
    for elem in ELEMENTS:
        process_element(elem, t_min_ns, t_max_ns, n_bins, rng)

    print("\n[3/3] Done.")


if __name__ == "__main__":
    main()
