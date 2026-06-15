# include/

Class headers and shared definitions.

| File                        | Purpose                                                                 |
|-----------------------------|-------------------------------------------------------------------------|
| `DetectorConstants.hh`      | Fixed detector dimensions, volume names, material name. **Do not change these casually** — they describe the real hardware. |
| `RunConfig.hh`              | Run-time configuration set from the command line (beam energy, light-yield divisor, beam mode, results-file path). |
| `DetectorConstruction.hh`   | Builds geometry + materials + optical properties/surfaces.              |
| `PrimaryGeneratorAction.hh` | The proton source (ideal pencil or realistic cosine-law beam).          |
| `RunAction.hh`              | Owns the per-run tallies (accumulables) and writes the console summary + CSV row. |
| `EventAction.hh`            | Per-proton time logging (no-op unless `timelog=` is set): collects interactions and writes the per-event detail CSV + per-run index row. |
| `SteppingAction.hh`         | Per-step classification that fills the tallies (and the time log).      |
| `Scoring.hh`                | Scoring `Region` enum + volume-name → region mapping.                   |
| `ActionInitialization.hh`   | Registers the user actions (per thread).                                |
