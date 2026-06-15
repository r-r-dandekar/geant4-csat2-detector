/// \file SteppingAction.hh
/// \brief Definition of the SteppingAction class.
///
/// Classifies each step and feeds the per-run tallies in RunAction: energy
/// deposition by region, primary/secondary stops, passed-through/back-scattered
/// primaries, optical photons generated (scintillation vs Cerenkov), and
/// photons detected at the photodiode.

#ifndef SteppingAction_h
#define SteppingAction_h 1

#include "G4UserSteppingAction.hh"
#include "globals.hh"

class RunAction;
class EventAction;
class G4OpBoundaryProcess;

class SteppingAction : public G4UserSteppingAction {
  public:
    SteppingAction(RunAction* runAction, EventAction* eventAction);
    ~SteppingAction() override;

    void UserSteppingAction(const G4Step*) override;

  private:
    RunAction*   fRunAction = nullptr;
    EventAction* fEventAction = nullptr;
    G4OpBoundaryProcess* fBoundary = nullptr;  // cached optical boundary process
};

#endif
