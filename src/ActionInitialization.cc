/// \file ActionInitialization.cc
/// \brief Implementation of the ActionInitialization class.

#include "ActionInitialization.hh"
#include "PrimaryGeneratorAction.hh"
#include "RunAction.hh"
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

    // SteppingAction feeds the tallies owned by this thread's RunAction.
    SetUserAction(new SteppingAction(runAction));
}
