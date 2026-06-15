/// \file ActionInitialization.cc
/// \brief Implementation of the ActionInitialization class.

#include "ActionInitialization.hh"
#include "PrimaryGeneratorAction.hh"
#include "RunAction.hh"
#include "EventAction.hh"
#include "SteppingAction.hh"

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

void ActionInitialization::BuildForMaster() const {
    // Master needs a RunAction to merge accumulables and print the summary.
    SetUserAction(new RunAction);
}

void ActionInitialization::Build() const {
    SetUserAction(new PrimaryGeneratorAction);

    auto* runAction = new RunAction;
    SetUserAction(runAction);

    // EventAction handles per-proton time logging (no-op unless timelog= is set).
    auto* eventAction = new EventAction;
    SetUserAction(eventAction);

    // SteppingAction feeds the RunAction tallies and the EventAction time log.
    SetUserAction(new SteppingAction(runAction, eventAction));
}
