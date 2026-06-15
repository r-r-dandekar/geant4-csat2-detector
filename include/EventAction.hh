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
    void RecordProtonLeaveCsI(G4double t_ns, G4double ke_MeV, bool stopped);
    void RecordPhoton(G4double t_ns, G4double e_MeV);

    // First-entry guards (also serve as the index "entered_*" flags).
    bool EnteredCD()  const { return fEnteredCD; }
    bool EnteredCsI() const { return fEnteredCsI; }
    bool EnteredACD() const { return fEnteredACD; }
    bool LeftCsI()    const { return fLeftCsI; }

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

    // Proton interaction summary (for the index; photons excluded).
    bool fEnteredCD  = false, fEnteredCsI = false, fEnteredACD = false;
    bool fLeftCsI    = false, fStoppedCsI = false;
    G4double fTEnterCD = 0.,  fKeEnterCD  = 0.;
    G4double fTEnterCsI = 0., fKeEnterCsI = 0.;
    G4double fTLeaveCsI = 0., fKeLeaveCsI = 0.;
    G4double fTEnterACD = 0., fKeEnterACD = 0.;
};

#endif
