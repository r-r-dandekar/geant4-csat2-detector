/// \file EventAction.cc
/// \brief Implementation of the EventAction class (per-proton time logging).

#include "EventAction.hh"
#include "RunConfig.hh"

#include "G4Event.hh"
#include "G4SystemOfUnits.hh"
#include "G4AutoLock.hh"
#include "G4Threading.hh"

#include <algorithm>
#include <cstdio>
#include <fstream>

namespace {
// Guards appends to the shared per-run index file (MT-safety; the per-event
// detail files are uniquely named so they never collide).
G4Mutex gIndexMutex = G4MUTEX_INITIALIZER;

// Format an energy (MeV) compactly for use in a filename, e.g. 100 or 2.5.
G4String EnergyTag(G4double mev) {
    char buf[32];
    std::snprintf(buf, sizeof buf, "%g", mev);
    return buf;
}
}  // namespace

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

EventAction::EventAction() = default;
EventAction::~EventAction() = default;

bool EventAction::Logging() const { return !cfg::gTimelogDir.empty(); }

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

void EventAction::BeginOfEventAction(const G4Event*) { Reset(); }

void EventAction::Reset() {
    fRows.clear();
    fEnteredCD = fEnteredCsI = fEnteredACD = fEnteredPD = false;
    fLeftCD = fStoppedCD = fLeftCsI = fStoppedCsI = false;
    fLeftACD = fStoppedACD = fLeftPD = fStoppedPD = false;
    fTEnterCD = fKeEnterCD = fTLeaveCD = fKeLeaveCD = 0.;
    fTEnterCsI = fKeEnterCsI = fTLeaveCsI = fKeLeaveCsI = 0.;
    fTEnterACD = fKeEnterACD = fTLeaveACD = fKeLeaveACD = 0.;
    fTEnterPD = fKeEnterPD = fTLeavePD = fKeLeavePD = 0.;
}

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

void EventAction::RecordProtonEnterCD(G4double t, G4double ke) {
    fEnteredCD = true; fTEnterCD = t; fKeEnterCD = ke;
    fRows.push_back({t, "enter_CD", "proton", ke});
}

void EventAction::RecordProtonEnterCsI(G4double t, G4double ke) {
    fEnteredCsI = true; fTEnterCsI = t; fKeEnterCsI = ke;
    fRows.push_back({t, "enter_CsI", "proton", ke});
}

void EventAction::RecordProtonEnterACD(G4double t, G4double ke) {
    fEnteredACD = true; fTEnterACD = t; fKeEnterACD = ke;
    fRows.push_back({t, "enter_ACD", "proton", ke});
}

void EventAction::RecordProtonLeaveCD(G4double t, G4double ke, bool stopped) {
    fLeftCD = true; fStoppedCD = stopped; fTLeaveCD = t; fKeLeaveCD = ke;
    fRows.push_back({t, stopped ? "stop_CD" : "exit_CD", "proton", ke});
}

void EventAction::RecordProtonLeaveCsI(G4double t, G4double ke, bool stopped) {
    fLeftCsI = true; fStoppedCsI = stopped; fTLeaveCsI = t; fKeLeaveCsI = ke;
    fRows.push_back({t, stopped ? "stop_CsI" : "exit_CsI", "proton", ke});
}

void EventAction::RecordProtonLeaveACD(G4double t, G4double ke, bool stopped) {
    fLeftACD = true; fStoppedACD = stopped; fTLeaveACD = t; fKeLeaveACD = ke;
    fRows.push_back({t, stopped ? "stop_ACD" : "exit_ACD", "proton", ke});
}

void EventAction::RecordProtonEnterPD(G4double t, G4double ke) {
    fEnteredPD = true; fTEnterPD = t; fKeEnterPD = ke;
    fRows.push_back({t, "enter_PD", "proton", ke});
}

void EventAction::RecordProtonLeavePD(G4double t, G4double ke, bool stopped) {
    fLeftPD = true; fStoppedPD = stopped; fTLeavePD = t; fKeLeavePD = ke;
    fRows.push_back({t, stopped ? "stop_PD" : "exit_PD", "proton", ke});
}

void EventAction::RecordPhoton(G4double t, G4double e) {
    fRows.push_back({t, "photon_at_photodiode", "opticalphoton", e});
}

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

void EventAction::EndOfEventAction(const G4Event* event) {
    if (!Logging()) return;

    const G4int id = event->GetEventID();
    const G4String fileName = "evt_E" + EnergyTag(cfg::gPrimaryEnergy / MeV) +
                              "MeV_" + cfg::gTimeTag + "_id" +
                              std::to_string(id) + ".csv";
    const G4String fullPath = cfg::gTimelogDir + "/" + fileName;

    WriteDetailFile(fullPath, id);
    AppendIndexRow(fileName, id);
}

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

void EventAction::WriteDetailFile(const G4String& fullPath, G4int eventID) const {
    // Interactions are recorded in tracking order (proton first, then its
    // photons); sort by time so the file reads as a time series.
    std::vector<Row> rows = fRows;
    std::sort(rows.begin(), rows.end(),
              [](const Row& a, const Row& b) { return a.time_ns < b.time_ns; });

    std::ofstream f(fullPath);
    if (!f.is_open()) {
        G4cerr << "EventAction: cannot open " << fullPath << G4endl;
        return;
    }
    f << "# proton_energy_MeV=" << cfg::gPrimaryEnergy / MeV
      << ", event_id=" << eventID
      << ", run_tag=" << cfg::gTimeTag << "\n";
    f << "time_ns,interaction,particle,energy_MeV\n";
    for (const auto& r : rows)
        f << r.time_ns << "," << r.type << "," << r.particle << ","
          << r.energy_MeV << "\n";
}

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

void EventAction::AppendIndexRow(const G4String& detailFileName,
                                 G4int eventID) const {
    const G4String indexPath =
        cfg::gTimelogDir + "/index_" + cfg::gTimeTag + ".csv";

    G4AutoLock lock(&gIndexMutex);

    bool needHeader = true;
    {
        std::ifstream probe(indexPath);
        if (probe.good() && probe.peek() != std::ifstream::traits_type::eof())
            needHeader = false;
    }

    std::ofstream out(indexPath, std::ios::app);
    if (!out.is_open()) {
        G4cerr << "EventAction: cannot open index " << indexPath << G4endl;
        return;
    }

    if (needHeader) {
        out << "event_id,file,energy_MeV,"
            << "entered_CD,stopped_in_CD,entered_CsI,stopped_in_CsI,"
            << "entered_ACD,stopped_in_ACD,entered_PD,stopped_in_PD,"
            << "t_enter_CD_ns,ke_enter_CD_MeV,t_leave_CD_ns,ke_leave_CD_MeV,"
            << "t_enter_CsI_ns,ke_enter_CsI_MeV,t_leave_CsI_ns,ke_leave_CsI_MeV,"
            << "t_enter_ACD_ns,ke_enter_ACD_MeV,t_leave_ACD_ns,ke_leave_ACD_MeV,"
            << "t_enter_PD_ns,ke_enter_PD_MeV,t_leave_PD_ns,ke_leave_PD_MeV\n";
    }

    out << eventID << "," << detailFileName << "," << cfg::gPrimaryEnergy / MeV << ","
        << (fEnteredCD  ? 1 : 0) << "," << (fStoppedCD  ? 1 : 0) << ","
        << (fEnteredCsI ? 1 : 0) << "," << (fStoppedCsI ? 1 : 0) << ","
        << (fEnteredACD ? 1 : 0) << "," << (fStoppedACD ? 1 : 0) << ","
        << (fEnteredPD  ? 1 : 0) << "," << (fStoppedPD  ? 1 : 0) << ",";

    // Optional proton-interaction columns: value if it happened, else blank.
    // Energy deposited in an element = ke_enter - ke_leave (ke_leave is 0 when
    // the proton stopped inside, so this also covers the full-deposit case).
    const std::pair<bool, G4double> opt[16] = {
        {fEnteredCD,  fTEnterCD},  {fEnteredCD,  fKeEnterCD},
        {fLeftCD,     fTLeaveCD},  {fLeftCD,     fKeLeaveCD},
        {fEnteredCsI, fTEnterCsI}, {fEnteredCsI, fKeEnterCsI},
        {fLeftCsI,    fTLeaveCsI}, {fLeftCsI,    fKeLeaveCsI},
        {fEnteredACD, fTEnterACD}, {fEnteredACD, fKeEnterACD},
        {fLeftACD,    fTLeaveACD}, {fLeftACD,    fKeLeaveACD},
        {fEnteredPD,  fTEnterPD},  {fEnteredPD,  fKeEnterPD},
        {fLeftPD,     fTLeavePD},  {fLeftPD,     fKeLeavePD},
    };
    for (int i = 0; i < 16; ++i) {
        if (opt[i].first) out << opt[i].second;
        out << (i < 15 ? "," : "\n");
    }
}
