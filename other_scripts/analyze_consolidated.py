import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Configuration
INPUT_FILE = 'simulated_proton_photon_strikes_1ms.csv'
SPIKE_TIME_LIMIT_NS = 20.0  # Set this to whatever time frame you want to view

# The energy thresholds based on your original flux map requirements
THRESHOLDS = [0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, 10.5, 11.0, 
              12.5, 15.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 
              100.0, 110.0, 125.0, 150.0, 175.0]

def analyze_and_plot():
    print(f"Loading data from {INPUT_FILE}...")
    df = pd.read_csv(INPUT_FILE)
    df['time'] = pd.to_numeric(df['time'], errors='coerce')
    df['energy'] = pd.to_numeric(df['energy'], errors='coerce')
    
    # Split datasets
    photons = df[df['particle'] == 'opticalphoton'].copy()
    protons = df[df['particle'] == 'proton'].copy()
    
    if photons.empty and protons.empty:
        print("Error: No valid data found in the dataset.")
        return

    print(f"Found {len(protons)} protons and {len(photons)} photons.")

    # ==========================================
    # DATA PROCESSING: Energy to Wavelength
    # ==========================================
    # Wavelength (nm) = hc / E(eV)
    # hc ≈ 1239.8 eV*nm
    # E(eV) = E(MeV) * 1,000,000
    # Therefore: Wavelength (nm) = 1239.8 / (E(MeV) * 1,000,000) = 0.0012398 / E(MeV)
    
    # Filter out 0 energy to prevent division by zero
    photons = photons[photons['energy'] > 0]
    photons['wavelength_nm'] = 0.0012398 / photons['energy']

    # ==========================================
    # 1. TABLES: Cumulative and Range Data (Photons)
    # ==========================================
    if not photons.empty:
        cumulative_data = []
        for t in THRESHOLDS:
            count = len(photons[photons['energy'] >= t])
            cumulative_data.append({'Energy_Threshold_MeV': f">= {t}", 'Photon_Count': count})
        df_cumulative = pd.DataFrame(cumulative_data)

        range_data = []
        for i in range(len(THRESHOLDS) - 1):
            low = THRESHOLDS[i]
            high = THRESHOLDS[i+1]
            count = len(photons[(photons['energy'] >= low) & (photons['energy'] < high)])
            range_data.append({'Energy_Range_MeV': f"{low} to {high}", 'Photon_Count': count})
        
        max_thresh = THRESHOLDS[-1]
        range_data.append({'Energy_Range_MeV': f">= {max_thresh}", 'Photon_Count': len(photons[photons['energy'] >= max_thresh])})
        df_ranges = pd.DataFrame(range_data)

        print("\n--- INTEGRATED / CUMULATIVE PHOTON DATA ---")
        print(df_cumulative.to_string(index=False))
        
        print("\n--- DIFFERENTIAL / RANGES PHOTON DATA ---")
        print(df_ranges.to_string(index=False))

        df_cumulative.to_csv('photon_cumulative_data.csv', index=False)
        df_ranges.to_csv('photon_ranges_data.csv', index=False)
        print("\n(Tables saved as CSV files)")

    # ==========================================
    # 2. GRAPHS
    # ==========================================
    plt.style.use('ggplot') 
    
    # Graph 1: Distribution of Photon Wavelengths
    if not photons.empty:
        fig1, ax1 = plt.subplots(figsize=(10, 6))
        # Dropping NA and infinite values just in case
        valid_wavelengths = photons['wavelength_nm'].replace([np.inf, -np.inf], np.nan).dropna()
        
        ax1.hist(valid_wavelengths, bins=50, color='purple', edgecolor='black', alpha=0.7)
        ax1.set_title('Distribution of Photon Wavelengths', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Wavelength (nm)', fontsize=12)
        ax1.set_ylabel('Number of Photons', fontsize=12)
        ax1.set_yscale('log') 
        plt.tight_layout()
        fig1.savefig('photon_wavelength_distribution.png', dpi=300)

    # Graph 2: Photon Spikes for Configurable Time Frame
    if not photons.empty:
        photons_filtered = photons[photons['time'] <= SPIKE_TIME_LIMIT_NS].copy()
        
        fig2, ax2 = plt.subplots(figsize=(12, 5))
        if not photons_filtered.empty:
            ax2.vlines(x=photons_filtered['time'], ymin=0, ymax=photons_filtered['energy'], 
                       color='red', linewidth=1.5, label='Photon Strike')
            ax2.scatter(photons_filtered['time'], photons_filtered['energy'], color='black', s=10, zorder=3)
        else:
            ax2.text(0.5, 0.5, f'No photons found in the first {SPIKE_TIME_LIMIT_NS} ns', 
                     horizontalalignment='center', verticalalignment='center', transform=ax2.transAxes)

        ax2.set_title(f'Photon Strikes: First {SPIKE_TIME_LIMIT_NS} ns', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Time (ns)', fontsize=12)
        ax2.set_ylabel('Energy (MeV)', fontsize=12)
        ax2.set_xlim(0, SPIKE_TIME_LIMIT_NS)
        
        if not photons_filtered.empty:
            ax2.set_ylim(0, photons_filtered['energy'].max() * 1.1)

        plt.tight_layout()
        fig2.savefig(f'photon_spikes_{SPIKE_TIME_LIMIT_NS}ns.png', dpi=300)

    # Graph 3: Proton Distribution by Energy Level
    if not protons.empty:
        fig3, ax3 = plt.subplots(figsize=(12, 6))
        
        # Because protons are injected at discrete, specific energy levels, 
        # a bar chart of value counts is much cleaner than a binned histogram.
        proton_counts = protons['energy'].value_counts().sort_index()
        
        # Plotting the discrete counts
        proton_counts.plot(kind='bar', color='orange', edgecolor='black', alpha=0.8, ax=ax3)
        
        ax3.set_title('Proton Distribution by Energy Level', fontsize=14, fontweight='bold')
        ax3.set_xlabel('Proton Energy (MeV)', fontsize=12)
        ax3.set_ylabel('Number of Protons (Log Scale)', fontsize=12)
        ax3.set_yscale('log')
        
        # Rotate x-axis labels if there are many discrete energy levels
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        fig3.savefig('proton_energy_distribution.png', dpi=300)

    print(f"\nGraphs saved to directory.")
    plt.show()

if __name__ == "__main__":
    analyze_and_plot()