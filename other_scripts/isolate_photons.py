import pandas as pd

# Load the consolidated dataset
df = pd.read_csv('consolidated.csv')

# Filter out rows where the 'particle' column is 'proton'
filtered_df = df[df['particle'] != 'proton']

# Save the resulting dataframe to a new CSV file
filtered_df.to_csv('consolidated_photons_only.csv', index=False)

print("Filtering complete. Data saved to 'consolidated_photons_only.csv'.")