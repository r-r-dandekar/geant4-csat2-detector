/// \file EventAction.hh
/// \brief Definition of the EventAction class.
///
/// When time-logging is enabled (`timelog=<dir>`), collects this proton's
/// interactions during the event and, at end of event, writes a per-proton
/// detail CSV and appends a row to the per-run index CSV (decisions 28-32).
/// When time-logging is off it does nothing.

#ifndef EventAction_h
#define EventAction_h 1

#include "G4UserEventAction.hh"
#include "globals.hh"

#include <vector>

class G4Event;

class EventAction : public G4UserEventAction {
  public:
    EventAction();
    ~EventAction() override;

    void BeginOfEventAction(const G4Event*) override;
    void EndOfEventAction(const G4Event*) override;

    // True when time-logging is enabled (timelog=<dir> was given).
    bool Logging() const;

    // --- recording interface (called from SteppingAction) -----------------
    void RecordProtonEnterCD(G4double t_ns, G4double ke_MeV);
    void RecordProtonEnterCsI(G4double t_ns, G4double ke_MeV);
    void RecordProtonEnterACD(G4double t_ns, G4double ke_MeV);
    void RecordProtonLeaveCD(G4double t_ns, G4double ke_MeV, bool stopped);
    void RecordProtonLeaveCsI(G4double t_ns, G4double ke_MeV, bool stopped);
    void RecordProtonLeaveACD(G4double t_ns, G4double ke_MeV, bool stopped);
    void RecordProtonEnterPD(G4double t_ns, G4double ke_MeV);
    void RecordProtonLeavePD(G4double t_ns, G4double ke_MeV, bool stopped);
    void RecordPhoton(G4double t_ns, G4double e_MeV);

    // First-entry / first-exit guards (also serve as the index
    // "entered_*"/"stopped_in_*" flags).
    bool EnteredCD()  const { return fEnteredCD; }
    bool EnteredCsI() const { return fEnteredCsI; }
    bool EnteredACD() const { return fEnteredACD; }
    bool EnteredPD()  const { return fEnteredPD; }
    bool LeftCD()     const { return fLeftCD; }
    bool LeftCsI()    const { return fLeftCsI; }
    bool LeftACD()    const { return fLeftACD; }
    bool LeftPD()     const { return fLeftPD; }

  private:
    struct Row {
        G4double    time_ns;
        const char* type;
        const char* particle;
        G4double    energy_MeV;
    };

    void Reset();
    void WriteDetailFile(const G4String& fullPath, G4int eventID) const;
    void AppendIndexRow(const G4String& detailFileName, G4int eventID) const;

    std::vector<Row> fRows;  // all interactions (incl. photons) for the detail file

    // Proton interaction summary (for the index; photons excluded). "PD"
    // here is the proton's own direct passage through the photodiode
    // silicon -- distinct from RecordPhoton()'s optical detections.
    bool fEnteredCD  = false, fEnteredCsI = false, fEnteredACD = false, fEnteredPD = false;
    bool fLeftCD     = false, fStoppedCD  = false;
    bool fLeftCsI    = false, fStoppedCsI = false;
    bool fLeftACD    = false, fStoppedACD = false;
    bool fLeftPD     = false, fStoppedPD  = false;
    G4double fTEnterCD = 0.,  fKeEnterCD  = 0.;
    G4double fTLeaveCD = 0.,  fKeLeaveCD  = 0.;
    G4double fTEnterCsI = 0., fKeEnterCsI = 0.;
    G4double fTLeaveCsI = 0., fKeLeaveCsI = 0.;
    G4double fTEnterACD = 0., fKeEnterACD = 0.;
    G4double fTLeaveACD = 0., fKeLeaveACD = 0.;
    G4double fTEnterPD = 0.,  fKeEnterPD  = 0.;
    G4double fTLeavePD = 0.,  fKeLeavePD  = 0.;
};

#endif
