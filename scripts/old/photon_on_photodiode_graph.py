import pandas as pd
import matplotlib.pyplot as plt
import glob
import os
import argparse
import random

def process_timelogs(directory, fraction):
    all_files = glob.glob(os.path.join(directory, '*.csv'))
    all_photon_times = []

    for file in all_files:
        # Skip files containing 'index'
        if 'index' in os.path.basename(file):
            continue
        
        # Apply fraction-based sampling
        if random.random() > fraction:
            continue
            
        try:
            df = pd.read_csv(file, comment='#', usecols=['time_ns', 'interaction'])
            photons = df[df['interaction'] == 'photon_at_photodiode']['time_ns']
            if not photons.empty:
                all_photon_times.append(photons)
        except (pd.errors.EmptyDataError, ValueError):
            continue

    return pd.concat(all_photon_times, ignore_index=True) if all_photon_times else pd.Series(dtype=float)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process scintillator logs.")
    parser.add_argument("fraction", type=float, help="Fraction of files to process (0.0 to 1.0)")
    args = parser.parse_args()

    directory = '/home/radhan/CSAT/Geant4-Detector/geant4/detector-sim/build/results/sweep_timelogs'
    
    print(f"Processing {args.fraction * 100}% of files...")
    photon_times = process_timelogs(directory, args.fraction)

    if not photon_times.empty:
        plt.figure(figsize=(10, 6))
        plt.hist(photon_times, bins=100, color='blue', alpha=0.7)
        plt.title(f'Photon Times (Sampled at {args.fraction*100}%)')
        plt.xlabel('Time (ns)')
        plt.ylabel('Frequency')
        plt.savefig('photon_time_distribution.png')
        print("Graph saved as photon_time_distribution.png")
    else:
        print("No data collected.")