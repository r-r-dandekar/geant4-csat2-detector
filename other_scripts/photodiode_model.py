#!/usr/bin/env python3
"""
PIN Photodiode Photocurrent Model — memory-efficient version

Bandwidth split:
  - Carrier transit-time spread (sigma): modelled here via Gaussian convolution
  - RC bandwidth (R_L * C_t):            modelled in TINA via C_t + R_L
"""

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
import matplotlib.pyplot as plt
import os

# =============================================================================
# PARAMETERS — edit here
# =============================================================================

PHOTON_FILE   = "consolidated_photons_only.csv"
CHUNK_SIZE    = 100_000          # rows per chunk while reading photon file
PARTICLE_TYPE = "opticalphoton"  # set None to skip particle-type filter

# --- Photodiode ---
F_C           = 40e6             # Cutoff frequency (Hz) — used for shot noise only
C_T           = 40e-12           # Junction capacitance (F) — informational, used in TINA
SIGMA_TRANSIT = 1.0e-9           # Gaussian transit-time spread (s) [default: 1 ns]
                                  # RC filtering is handled by C_t + R_L in TINA.

# --- Noise ---
SHOT_NOISE_ENABLED = True        # Shot noise from photocurrent (recommended: True)
GAUSSIAN_NOISE_RMS = 0.0         # Extra additive Gaussian noise RMS in amps (0 = off)
NOISE_SEED         = 42

# --- Time grid ---
DT_NS            = 0.1           # Time bin size (ns). Increase if still low on memory.
MAX_DURATION_US  = None          # Limit processing to the first N microseconds of data.
                                  # Set to e.g. 100 to use only the first 100 µs.
                                  # None = use all available data.

# --- Streaming convolution block size ---
# Larger = faster (fewer FFTs) but more RAM per block.
# Memory per block ≈ CONV_BLOCK_SIZE × 40 bytes.
# Default 2^18 = 262144 samples ≈ 10 MB per block.
CONV_BLOCK_SIZE = 1 << 18

# --- Output ---
PLOT_WINDOW_START_NS    = 0      # Start of plot window relative to first photon (ns)
PLOT_WINDOW_DURATION_NS = 2000   # Duration of plot window (ns) = 2 µs

PWL_DOWNSAMPLE = 1               # Write every Nth sample to PWL (1 = all points)

OUTPUT_CSV               = "photocurrent.csv"
OUTPUT_PWL               = "photocurrent.pwl"
OUTPUT_PLOT_CURRENT      = "photocurrent_plot.png"
OUTPUT_PLOT_RESPONSIVITY = "responsivity_plot.png"

# --- Responsivity (wavelength_nm, A/W) ---
# Gap between 540–960 nm is interpolated — see approximation notes in TINA PDF.
RESPONSIVITY_NM_AW = np.array([
    [340,   0.10],
    [420,   0.22],
    [480,   0.33],
    [540,   0.41],
    [960,   0.66],
    [1100,  0.10],
])

# =============================================================================
# PHYSICAL CONSTANTS
# =============================================================================

H_PLANCK = 6.62607015e-34    # J·s
C_LIGHT  = 2.99792458e8      # m/s
Q_CHARGE = 1.60217663e-19    # C
MEV_TO_J = 1.60217663e-13    # J per MeV

# =============================================================================
# RESPONSIVITY
# =============================================================================

def build_responsivity(data):
    return PchipInterpolator(data[:, 0], data[:, 1], extrapolate=False)


def plot_responsivity(data, interp, path):
    wl = np.linspace(data[0, 0], data[-1, 0], 2000)
    r  = np.clip(interp(wl), 0, None)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(wl, r, 'b-', linewidth=1.5, label='PCHIP interpolation')
    ax.scatter(data[:, 0], data[:, 1], color='red', zorder=5,
               s=60, label='Datasheet points')
    ax.axvspan(540, 960, alpha=0.08, color='orange',
               label='Interpolated gap (no data)')
    ax.set_xlabel('Wavelength (nm)')
    ax.set_ylabel('Responsivity (A/W)')
    ax.set_title('Photodiode Responsivity vs Wavelength')
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Saved: {path}")

# =============================================================================
# GAUSSIAN KERNEL  (transit-time broadening only; RC handled in TINA)
# =============================================================================

def build_gaussian_kernel(sigma, dt):
    """
    Normalised Gaussian kernel. Integral over dt = 1 (charge-preserving).
    sigma: transit-time spread (s)
    dt:    time step (s)
    """
    half_width = 5.0 * sigma
    t      = np.arange(-half_width, half_width + dt, dt)
    kernel = np.exp(-0.5 * (t / sigma) ** 2)
    kernel /= kernel.sum() * dt
    return kernel

# =============================================================================
# TIME RANGE SCAN
# =============================================================================

def detect_columns(filepath):
    """Two consolidation pipelines exist with different column names:
    generate_timeseries.py's consolidated.csv uses 'time_ns'/'energy_MeV';
    sweep_consolidate.py's output uses 'time'/'energy' instead. Peek at the
    header and return whichever pair is actually present, so PHOTON_FILE can
    come from either pipeline without a KeyError."""
    header_cols = set(pd.read_csv(filepath, nrows=0).columns)
    time_col   = 'time_ns'   if 'time_ns'   in header_cols else 'time'
    energy_col = 'energy_MeV' if 'energy_MeV' in header_cols else 'energy'
    return time_col, energy_col


def scan_time_range(filepath, chunksize, particle_filter, time_col):
    t_min, t_max = np.inf, -np.inf
    cols = [time_col] + (['particle'] if particle_filter else [])
    for chunk in pd.read_csv(filepath, chunksize=chunksize, usecols=cols):
        if particle_filter:
            chunk = chunk[chunk['particle'] == particle_filter]
        if chunk.empty:
            continue
        t_min = min(t_min, chunk[time_col].min())
        t_max = max(t_max, chunk[time_col].max())
    return float(t_min), float(t_max)

# =============================================================================
# STREAMING OVERLAP-ADD CONVOLUTION + DIRECT FILE OUTPUT
# =============================================================================

def stream_convolve_write(charge_arr, n_bins, kernel, t_min_ns, rng):
    """
    Convolves charge_arr with kernel using overlap-add, block by block.
    Writes output directly to CSV and PWL without holding the full
    output array in RAM.

    Peak extra RAM per call:
        ~5 × CONV_BLOCK_SIZE × 8 bytes  (two FFT buffers + a few temporaries)
        + kernel (tiny)
        + overlap buffer (len(kernel)-1 floats, tiny)

    Returns (total_charge_out, plot_time_ns_array, plot_current_array)
    """
    m          = len(kernel)
    block_size = CONV_BLOCK_SIZE

    # FFT length: next power of 2 >= block_size + m - 1
    fft_len    = 1 << int(np.ceil(np.log2(block_size + m - 1)))
    kernel_fft = np.fft.rfft(kernel.astype(np.float64), fft_len)  # precomputed once

    overlap    = np.zeros(m - 1, dtype=np.float64)  # overlap-add tail buffer
    dt_s       = DT_NS * 1e-9

    # Plot window bounds (in ns, absolute)
    plot_lo_ns = t_min_ns + PLOT_WINDOW_START_NS
    plot_hi_ns = t_min_ns + PLOT_WINDOW_START_NS + PLOT_WINDOW_DURATION_NS
    plot_t_buf = []
    plot_i_buf = []

    total_charge_out = 0.0
    n_blocks         = (n_bins + block_size - 1) // block_size

    with open(OUTPUT_CSV, 'w') as cf, open(OUTPUT_PWL, 'w') as pf:
        cf.write("time_s,current_A\n")
        pf.write("; TINA PWL photocurrent source\n")
        pf.write("; RC filtering handled by C_t + R_L in TINA circuit\n")
        pf.write("; time(s)  current(A)\n")

        for blk_num, blk_start in enumerate(range(0, n_bins, block_size)):
            blk_end = min(blk_start + block_size, n_bins)
            L       = blk_end - blk_start

            # --- Convolve this block ---
            blk     = charge_arr[blk_start:blk_end].astype(np.float64)
            blk_fft = np.fft.rfft(blk, fft_len)
            conv    = np.fft.irfft(blk_fft * kernel_fft, fft_len)  # length fft_len

            # --- Overlap-add ---
            # conv[0..L+m-2] is the full result for this block.
            # The first (m-1) samples receive the tail saved from the previous block.
            # The last (m-1) samples of conv become the tail for the next block.
            result = conv[:L + m - 1]
            if m > 1:
                result[:m - 1] += overlap
                overlap[:] = result[L : L + m - 1]

            out = result[:L].copy()   # L valid output samples for this block

            # --- Noise ---
            if SHOT_NOISE_ENABLED:
                shot_rms = np.sqrt(2.0 * Q_CHARGE * np.abs(out) * F_C)
                out += rng.standard_normal(L) * shot_rms

            if GAUSSIAN_NOISE_RMS > 0.0:
                out += rng.normal(0.0, GAUSSIAN_NOISE_RMS, L)

            total_charge_out += out.sum() * dt_s

            # --- Compute times for this block ---
            global_idx = np.arange(blk_start, blk_end, dtype=np.int64)
            times_s    = t_min_ns * 1e-9 + global_idx * dt_s
            times_ns   = t_min_ns        + global_idx * DT_NS

            # --- Write CSV (vectorised, no Python loop) ---
            np.savetxt(cf,
                       np.column_stack([times_s, out]),
                       fmt=['%.9e', '%.6e'],
                       delimiter=',')

            # --- Write PWL (downsampled) ---
            pwl_sel = global_idx % PWL_DOWNSAMPLE == 0
            if pwl_sel.any():
                np.savetxt(pf,
                           np.column_stack([times_s[pwl_sel], out[pwl_sel]]),
                           fmt=['%.9e', '%.6e'],
                           delimiter=' ')

            # --- Accumulate plot window (tiny slice) ---
            plot_sel = (times_ns >= plot_lo_ns) & (times_ns <= plot_hi_ns)
            if plot_sel.any():
                plot_t_buf.append(times_ns[plot_sel].copy())
                plot_i_buf.append(out[plot_sel].copy())

            # Progress
            print(f"  Convolution: block {blk_num + 1}/{n_blocks} "
                  f"({blk_end / n_bins * 100:.1f}%)",
                  end='\r', flush=True)

    print()   # newline after \r progress

    plot_t = np.concatenate(plot_t_buf) if plot_t_buf else np.array([])
    plot_i = np.concatenate(plot_i_buf) if plot_i_buf else np.array([])
    return total_charge_out, plot_t, plot_i

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("PIN Photodiode Photocurrent Model (memory-efficient)")
    print("=" * 60)

    # --- Responsivity ---
    print("\n[1/6] Building responsivity interpolator...")
    r_interp = build_responsivity(RESPONSIVITY_NM_AW)
    plot_responsivity(RESPONSIVITY_NM_AW, r_interp, OUTPUT_PLOT_RESPONSIVITY)

    # --- Time range ---
    time_col, energy_col = detect_columns(PHOTON_FILE)
    print(f"  Detected columns: time='{time_col}', energy='{energy_col}'")
    print("\n[2/6] Scanning photon file for time range...")
    t_min_ns, t_max_ns = scan_time_range(PHOTON_FILE, CHUNK_SIZE, PARTICLE_TYPE, time_col)
    if MAX_DURATION_US is not None:
        t_max_ns = min(t_max_ns, t_min_ns + MAX_DURATION_US * 1e3)
        print(f"  Limiting to first {MAX_DURATION_US} µs  (t_max = {t_max_ns:.3f} ns)")

    span_ns = t_max_ns - t_min_ns
    n_bins  = int(np.ceil(span_ns / DT_NS)) + 1
    charge_mem_mb  = n_bins * 4 / 1e6    # float32
    print(f"  Range  : {t_min_ns:.3f} – {t_max_ns:.3f} ns  ({span_ns * 1e-6:.4f} ms)")
    print(f"  Bins   : {n_bins:,}  (dt = {DT_NS} ns)")
    print(f"  Charge array (float32) : ~{charge_mem_mb:.0f} MB")
    block_mem_mb = CONV_BLOCK_SIZE * 40 / 1e6
    print(f"  Conv block RAM peak    : ~{block_mem_mb:.0f} MB  "
          f"(block size = {CONV_BLOCK_SIZE:,} samples)")

    wl_lo = RESPONSIVITY_NM_AW[0, 0]
    wl_hi = RESPONSIVITY_NM_AW[-1, 0]

    # --- Scatter photon charges into charge array (float32, in RAM) ---
    print("\n[3/6] Processing photons...")
    charge_arr = np.zeros(n_bins, dtype=np.float32)
    n_total, n_oob = 0, 0

    cols = [time_col, energy_col] + (['particle'] if PARTICLE_TYPE else [])
    for chunk in pd.read_csv(PHOTON_FILE, chunksize=CHUNK_SIZE, usecols=cols):
        if PARTICLE_TYPE:
            chunk = chunk[chunk['particle'] == PARTICLE_TYPE]
        if chunk.empty:
            continue

        energy_mev = chunk[energy_col].to_numpy(dtype=np.float64)
        time_ns    = chunk[time_col].to_numpy(dtype=np.float64)
        n_total   += len(energy_mev)

        energy_j = energy_mev * MEV_TO_J
        wl_nm    = (H_PLANCK * C_LIGHT / energy_j) * 1e9

        in_range  = ((wl_nm >= wl_lo) & (wl_nm <= wl_hi)
                     & (time_ns >= t_min_ns) & (time_ns <= t_max_ns))
        n_oob    += int((~in_range).sum())
        if not in_range.any():
            continue

        wl_nm    = wl_nm[in_range]
        time_ns  = time_ns[in_range]
        energy_j = energy_j[in_range]

        r_vals  = np.clip(r_interp(wl_nm).astype(np.float64), 0.0, None)
        charges = (r_vals * energy_j).astype(np.float32)

        idx = np.floor((time_ns - t_min_ns) / DT_NS).astype(np.int64)
        idx = np.clip(idx, 0, n_bins - 1)
        np.add.at(charge_arr, idx, charges)

    total_charge_in = float(charge_arr.sum())
    print(f"  Photons processed : {n_total:,}")
    print(f"  Out of λ range    : {n_oob:,}")
    print(f"  Total charge      : {total_charge_in:.4e} C")

    # --- Gaussian kernel ---
    print("\n[4/6] Building Gaussian transit-time kernel...")
    kernel = build_gaussian_kernel(SIGMA_TRANSIT, DT_NS * 1e-9)
    print(f"  sigma_transit = {SIGMA_TRANSIT * 1e9:.2f} ns")
    print(f"  Kernel length : {len(kernel)} samples  ({len(kernel) * DT_NS:.1f} ns)")
    print(f"  (RC filtering deferred to TINA: C_t = {C_T * 1e12:.0f} pF + R_L)")

    # --- Streaming convolution ---
    print("\n[5/6] Streaming overlap-add convolution → output files...")
    rng = np.random.default_rng(NOISE_SEED)

    # Free anything we no longer need before the convolution pass
    import gc
    gc.collect()

    total_charge_out, plot_t_ns, plot_i = stream_convolve_write(
        charge_arr, n_bins, kernel, t_min_ns, rng
    )
    del charge_arr   # no longer needed
    gc.collect()

    err_pct = (abs(total_charge_out - total_charge_in)
               / max(total_charge_in, 1e-30) * 100)
    print(f"  Charge conservation error : {err_pct:.3f}%")
    print(f"  Saved: {OUTPUT_CSV}")
    print(f"  Saved: {OUTPUT_PWL}")

    # --- Plot ---
    print("\n[6/6] Plotting...")
    if len(plot_t_ns) > 0:
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot((plot_t_ns - t_min_ns) * 1e-3,
                plot_i * 1e6,
                linewidth=0.6, color='steelblue')
        ax.set_xlabel('Time relative to first photon (µs)')
        ax.set_ylabel('Photocurrent (µA)')
        ax.set_title(f'Photocurrent before RC filtering — '
                     f'first {PLOT_WINDOW_DURATION_NS / 1000:.1f} µs')
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(OUTPUT_PLOT_CURRENT, dpi=150)
        plt.close(fig)
        print(f"  Saved: {OUTPUT_PLOT_CURRENT}")
    else:
        print("  WARNING: no data in plot window — check PLOT_WINDOW_START_NS")

    print("\nDone.")


if __name__ == "__main__":
    main()
