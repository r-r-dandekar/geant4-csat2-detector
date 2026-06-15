/// \file payload.cc
/// \brief Main program for the particle-detector simulation (`dsim`).
///
/// Command-line arguments (see README):
///   energy=<MeV>     beam energy per primary proton (default 50 MeV)
///   <file>.mac       Geant4 macro to execute (batch mode)
/// If no macro is given, an interactive UI/visualisation session starts.

#include "DetectorConstruction.hh"
#include "ActionInitialization.hh"
#include "RunConfig.hh"

#include "G4RunManagerFactory.hh"
#include "G4UImanager.hh"
#include "G4UIExecutive.hh"
#include "G4VisExecutive.hh"

#include "QBBC.hh"
#include "G4EmStandardPhysics_option4.hh"
#include "G4OpticalPhysics.hh"
#include "G4OpticalParameters.hh"
#include "G4SystemOfUnits.hh"

#include <string>

int main(int argc, char** argv) {
    G4String macroFile;

    // --- parse command-line arguments -------------------------------------
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg.rfind("energy=", 0) == 0) {
            cfg::gPrimaryEnergy = std::stod(arg.substr(7)) * MeV;
            G4cout << "Particle energy set to " << cfg::gPrimaryEnergy / MeV
                   << " MeV" << G4endl;
        } else if (arg.rfind("ydiv=", 0) == 0) {
            cfg::gLightYieldDivisor = std::stod(arg.substr(5));
            if (cfg::gLightYieldDivisor <= 0.0) cfg::gLightYieldDivisor = 1.0;
            G4cout << "Scintillation light-yield divisor set to "
                   << cfg::gLightYieldDivisor << G4endl;
        } else if (arg.rfind("mode=", 0) == 0) {
            const std::string mode = arg.substr(5);
            cfg::gBeamMode = (mode == "realistic") ? cfg::BeamMode::kRealistic
                                                   : cfg::BeamMode::kIdeal;
            G4cout << "Beam mode set to " << mode << G4endl;
        } else if (arg.rfind("results_file=", 0) == 0) {
            cfg::gResultsFile = arg.substr(13);
            G4cout << "Results CSV: " << cfg::gResultsFile << G4endl;
        } else if (arg.find(".mac") != std::string::npos) {
            macroFile = arg;
        }
    }

    // Interactive UI only when no macro is supplied.
    G4UIExecutive* ui = (macroFile.empty())
                            ? new G4UIExecutive(argc, argv)
                            : nullptr;

    // --- run manager: sequential by default, but MT-capable (decision 14) --
    auto* runManager =
        G4RunManagerFactory::CreateRunManager(G4RunManagerType::Serial);

    runManager->SetUserInitialization(new DetectorConstruction());

    // --- physics: QBBC with EM replaced by option4 + optical (decision 11) -
    auto* physicsList = new QBBC;
    physicsList->SetVerboseLevel(1);
    physicsList->ReplacePhysics(new G4EmStandardPhysics_option4());
    physicsList->RegisterPhysics(new G4OpticalPhysics());

    // One scintillation yield for all particles (decision 11): light is
    // proportional to energy deposited, regardless of the depositing particle.
    auto* opticalParams = G4OpticalParameters::Instance();
    opticalParams->SetScintByParticleType(false);

    runManager->SetUserInitialization(physicsList);

    runManager->SetUserInitialization(new ActionInitialization());

    auto* visManager = new G4VisExecutive;
    visManager->Initialize();

    G4UImanager* uiManager = G4UImanager::GetUIpointer();

    if (!ui) {
        // batch mode
        uiManager->ApplyCommand("/control/execute " + macroFile);
    } else {
        // interactive mode
        uiManager->ApplyCommand("/control/execute macros/init_vis.mac");
        ui->SessionStart();
        delete ui;
    }

    delete visManager;
    delete runManager;
    return 0;
}
