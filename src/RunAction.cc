/// \file RunAction.cc
/// \brief Implementation of the RunAction class.

#include "RunAction.hh"
#include "RunConfig.hh"

#include "G4Run.hh"
#include "G4AccumulableManager.hh"
#include "G4SystemOfUnits.hh"

#include <iomanip>
#include <fstream>

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

RunAction::RunAction() {
    // Register every tally with the (thread-local) accumulable manager so that
    // worker-thread values are merged into the master at end of run.
    auto* mgr = G4AccumulableManager::Instance();
    for (auto& a : fPrimaryEdep)     mgr->Register(a);
    for (auto& a : fOpticalEdep)     mgr->Register(a);
    for (auto& a : fPrimaryStopped)  mgr->Register(a);
    for (auto& a : fSecondaryStopped) mgr->Register(a);
    mgr->Register(fPassedThrough);
    mgr->Register(fBackScatter);
    mgr->Register(fScintPhotons);
    mgr->Register(fCerenkovPhotons);
    mgr->Register(fPhotodiodeDetected);
}

RunAction::~RunAction() = default;

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

void RunAction::BeginOfRunAction(const G4Run*) {
    G4AccumulableManager::Instance()->Reset();
}

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

void RunAction::EndOfRunAction(const G4Run* run) {
    const G4int nEvents = run->GetNumberOfEvent();
    if (nEvents == 0) return;

    // Merge worker-thread accumulables into this (master) instance.
    G4AccumulableManager::Instance()->Merge();

    // Only the master prints the summary.
    if (!IsMaster()) return;

    const G4double divisor = cfg::gLightYieldDivisor;

    auto edep = [](const G4Accumulable<G4double>& a) { return a.GetValue() / MeV; };
    auto cnt  = [](const G4Accumulable<G4double>& a) { return a.GetValue(); };

    G4cout << "\n============================================================\n"
           << "  Run summary : " << nEvents << " protons @ "
           << cfg::gPrimaryEnergy / MeV << " MeV"
           << "   (light_yield_divisor = " << divisor << ")\n"
           << "------------------------------------------------------------\n"
           << std::left << std::setw(14) << "  Region"
           << std::right << std::setw(16) << "PrimaryEdep[MeV]"
           << std::setw(16) << "OptEdep[MeV]"
           << std::setw(12) << "PriStop"
           << std::setw(12) << "SecStop" << "\n";

    for (G4int r = 0; r < score::kNumRegions; ++r) {
        const auto region = static_cast<score::Region>(r);
        G4cout << std::left << "  " << std::setw(12) << score::RegionName(region)
               << std::right << std::setw(16) << edep(fPrimaryEdep[r])
               << std::setw(16) << edep(fOpticalEdep[r])
               << std::setw(12) << cnt(fPrimaryStopped[r])
               << std::setw(12) << cnt(fSecondaryStopped[r]) << "\n";
    }

    G4cout << "------------------------------------------------------------\n"
           << "  Primaries passed through : " << cnt(fPassedThrough) << "\n"
           << "  Primaries back-scattered : " << cnt(fBackScatter) << "\n"
           << "------------------------------------------------------------\n"
           << "  Optical photons (simulated, then x divisor for physical):\n"
           << "    Scintillation generated : " << cnt(fScintPhotons)
           << "   (physical ~ " << cnt(fScintPhotons) * divisor << ")\n"
           << "    Cerenkov generated      : " << cnt(fCerenkovPhotons)
           << "   (NOT scaled by divisor)\n"
           << "    Detected at photodiode  : " << cnt(fPhotodiodeDetected)
           << "   (physical ~ " << cnt(fPhotodiodeDetected) * divisor << ")\n"
           << "============================================================\n"
           << G4endl;

    if (!cfg::gResultsFile.empty()) WriteCsvRow(nEvents);
}

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

void RunAction::WriteCsvRow(G4int nEvents) const {
    const G4String& path = cfg::gResultsFile;
    const G4double  divisor = cfg::gLightYieldDivisor;

    // Write the header only if the file does not yet exist / is empty, so the
    // program owns the schema and the sweep script never has to.
    G4bool needHeader = true;
    {
        std::ifstream probe(path);
        if (probe.good() && probe.peek() != std::ifstream::traits_type::eof())
            needHeader = false;
    }

    std::ofstream out(path, std::ios::app);
    if (!out.is_open()) {
        G4cerr << "RunAction: could not open results file: " << path << G4endl;
        return;
    }

    auto edep = [](const G4Accumulable<G4double>& a) { return a.GetValue() / MeV; };
    auto cnt  = [](const G4Accumulable<G4double>& a) { return a.GetValue(); };

    if (needHeader) {
        out << "energy_MeV,"
            << "stop_Al,stop_SiCD,stop_Teflon,stop_CsI,stop_SiACD,stop_Photodiode,stop_total,"
            << "passed_through,back_scatter,"
            << "edep_Al_MeV,edep_SiCD_MeV,edep_Teflon_MeV,edep_CsI_MeV,edep_SiACD_MeV,edep_Photodiode_MeV,edep_total_MeV,"
            << "optedep_Al_MeV,optedep_SiCD_MeV,optedep_Teflon_MeV,optedep_CsI_MeV,optedep_SiACD_MeV,optedep_Photodiode_MeV,optedep_total_MeV,"
            << "scint_photons,cerenkov_photons,photodiode_detected,"
            << "n_events,ydiv\n";
    }

    // --- per-region sums + totals -----------------------------------------
    G4double stopTotal = 0.0, edepTotal = 0.0, optTotal = 0.0;
    for (G4int r = 0; r < score::kNumRegions; ++r) {
        stopTotal += cnt(fPrimaryStopped[r]);
        edepTotal += edep(fPrimaryEdep[r]);
        optTotal  += edep(fOpticalEdep[r]);
    }

    // Scintillation and photodiode counts are scaled back to physical values by
    // the light-yield divisor; Cerenkov is NOT scaled (it was never reduced).
    const G4double scintPhys    = cnt(fScintPhotons) * divisor;
    const G4double detectedPhys = cnt(fPhotodiodeDetected) * divisor;

    out << cfg::gPrimaryEnergy / MeV << ",";
    for (G4int r = 0; r < score::kNumRegions; ++r) out << cnt(fPrimaryStopped[r]) << ",";
    out << stopTotal << ","
        << cnt(fPassedThrough) << "," << cnt(fBackScatter) << ",";
    for (G4int r = 0; r < score::kNumRegions; ++r) out << edep(fPrimaryEdep[r]) << ",";
    out << edepTotal << ",";
    for (G4int r = 0; r < score::kNumRegions; ++r) out << edep(fOpticalEdep[r]) << ",";
    out << optTotal << ","
        << scintPhys << "," << cnt(fCerenkovPhotons) << "," << detectedPhys << ","
        << nEvents << "," << divisor << "\n";

    out.close();
    G4cout << "RunAction: appended results row to " << path << G4endl;
}
