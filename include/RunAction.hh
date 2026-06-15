/// \file RunAction.hh
/// \brief Definition of the RunAction class.
///
/// Owns all per-run tallies as G4Accumulables (thread-safe; merged across
/// worker threads into the master, which prints the summary). SteppingAction
/// feeds the tallies through the Add* methods.

#ifndef RunAction_h
#define RunAction_h 1

#include "G4UserRunAction.hh"
#include "G4Accumulable.hh"
#include "Scoring.hh"
#include "globals.hh"

#include <array>

class G4Run;

class RunAction : public G4UserRunAction {
  public:
    RunAction();
    ~RunAction() override;

    void BeginOfRunAction(const G4Run*) override;
    void EndOfRunAction(const G4Run*) override;

    // --- accumulation interface (called from SteppingAction) --------------
    void AddPrimaryEdep(score::Region r, G4double e)   { fPrimaryEdep[r]   += e; }
    void AddOpticalEdep(score::Region r, G4double e)   { fOpticalEdep[r]   += e; }
    void AddPrimaryStopped(score::Region r)            { fPrimaryStopped[r]   += 1.0; }
    void AddSecondaryStopped(score::Region r)          { fSecondaryStopped[r] += 1.0; }
    void AddPassedThrough()                            { fPassedThrough     += 1.0; }
    void AddBackScatter()                              { fBackScatter       += 1.0; }
    void AddScintillationPhotons(G4double n)           { fScintPhotons      += n; }
    void AddCerenkovPhotons(G4double n)                { fCerenkovPhotons   += n; }
    void AddPhotodiodeDetected(G4double n)             { fPhotodiodeDetected += n; }

  private:
    // Append one summary row to the results CSV (program owns the file and
    // writes the header if the file is new). decision 26.
    void WriteCsvRow(G4int nEvents) const;

    // Energy deposited (Geant4 internal units) by the primary proton / by
    // optical photons, per region.
    std::array<G4Accumulable<G4double>, score::kNumRegions> fPrimaryEdep;
    std::array<G4Accumulable<G4double>, score::kNumRegions> fOpticalEdep;
    // Particle stop counts per region (primaries vs secondaries kept separate).
    std::array<G4Accumulable<G4double>, score::kNumRegions> fPrimaryStopped;
    std::array<G4Accumulable<G4double>, score::kNumRegions> fSecondaryStopped;

    G4Accumulable<G4double> fPassedThrough;      // primaries exiting the back
    G4Accumulable<G4double> fBackScatter;        // primaries exiting backwards
    G4Accumulable<G4double> fScintPhotons;       // scintillation photons generated (simulated)
    G4Accumulable<G4double> fCerenkovPhotons;    // Cerenkov photons generated (simulated)
    G4Accumulable<G4double> fPhotodiodeDetected; // photons detected at photodiode (simulated)
};

#endif
