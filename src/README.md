# src/

Implementations of the classes declared in `include/`. (`payload.cc`, the
`main()` entry point, lives at the project root.)

| File                        | Purpose                                                                 |
|-----------------------------|-------------------------------------------------------------------------|
| `DetectorConstruction.cc`   | Geometry (Al window, Si C.D., vacuum gap, teflon-wrapped CsI(Tl) with a photodiode coupling window, Si A.C.D.), materials, the CsI(Tl) scintillation MPT, and the optical surfaces (teflon reflector + photodiode readout). |
| `PrimaryGeneratorAction.cc` | Generates each primary proton: ideal pencil beam, or realistic cosine-law beam over the full face. |
| `RunAction.cc`              | Registers/merges accumulables, prints the end-of-run summary, and appends the CSV row (program-owned header). |
| `SteppingAction.cc`         | Classifies each step: energy deposition by region, primary/secondary stops, passed-through/back-scatter, optical photons generated (scintillation vs Cerenkov), and photodiode detections. |
| `Scoring.cc`                | Volume-name → scoring-region mapping and region names.                  |
| `ActionInitialization.cc`   | Wires the user actions together (SteppingAction feeds the thread's RunAction). |

## Key physics notes
- Geant4 11 scintillation keys (`SCINTILLATIONCOMPONENT1/2`, `SCINTILLATIONYIELD1/2`,
  `SCINTILLATIONTIMECONSTANT1/2`) are used — the legacy `FAST/SLOWCOMPONENT` names
  are silently ignored in 11.x, which is why the old code produced no light.
- The vacuum is given `RINDEX = 1` so scintillation photons can propagate to the
  photodiode; the teflon coupling window is carved out of the wrap so light is not
  reflected back at the readout face.
- The light-yield divisor (`ydiv`) reduces the simulated photon count for
  performance and does **not** affect energy deposition; multiply scintillation
  tallies by it to recover physical counts.
