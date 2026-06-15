/// \file RunConfig.hh
/// \brief Run-time configuration set from command-line arguments.
///
/// Per decision 20, the command-line `energy=` argument is the single source
/// of truth for the beam energy (the `/gun/energy` macro command is NOT used).
/// Additional run-time options (beam mode, output file) are added in later
/// iterations.

#ifndef RunConfig_h
#define RunConfig_h 1

#include "G4SystemOfUnits.hh"
#include "globals.hh"

namespace cfg {

// Energy of each primary proton. Overridden by the `energy=<MeV>` CLI arg.
inline G4double gPrimaryEnergy = 50.0 * MeV;

// Beam mode (decision 17), set via `mode=ideal|realistic`:
//   kIdeal     - pencil beam, straight +z from the centre of the front face.
//   kRealistic - protons spread uniformly over the full 10x10 mm front face
//                with a cosine-law (Lambertian) angular distribution, modelling
//                an isotropic external flux entering the window (decision 18-19).
enum class BeamMode { kIdeal, kRealistic };
inline BeamMode gBeamMode = BeamMode::kIdeal;

// Output CSV path (decision 26), set via `results_file=<path>`. Empty = no CSV
// (console summary only). The program owns the file and its header row.
inline G4String gResultsFile = "";

// Performance knob: the CsI(Tl) scintillation yield is DIVIDED by this factor
// so that far fewer optical photons are simulated (the full ~54000 photons/MeV
// produces ~10^6 photons per proton, which is too many to track/visualise).
// Set via the `ydiv=<N>` CLI arg. Higher = fewer photons = faster.
// Default 1000. To recover physical scintillation photon counts, multiply the
// SCINTILLATION photon tallies (not Cerenkov) by this factor.
inline G4double gLightYieldDivisor = 1000.0;

}  // namespace cfg

#endif
