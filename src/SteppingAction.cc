/// \file SteppingAction.cc
/// \brief Implementation of the SteppingAction class.

#include "SteppingAction.hh"
#include "RunAction.hh"
#include "EventAction.hh"
#include "Scoring.hh"

#include "G4Step.hh"
#include "G4Track.hh"
#include "G4StepPoint.hh"
#include "G4VPhysicalVolume.hh"
#include "G4LogicalVolume.hh"
#include "G4OpticalPhoton.hh"
#include "G4VProcess.hh"
#include "G4ProcessManager.hh"
#include "G4ProcessVector.hh"
#include "G4OpBoundaryProcess.hh"
#include "G4SystemOfUnits.hh"

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

SteppingAction::SteppingAction(RunAction* runAction, EventAction* eventAction)
    : fRunAction(runAction), fEventAction(eventAction) {}

SteppingAction::~SteppingAction() = default;

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

void SteppingAction::UserSteppingAction(const G4Step* step) {
    G4Track* track = step->GetTrack();
    const G4int    parentID  = track->GetParentID();
    const G4bool   isPrimary = (parentID == 0);
    const G4double edep      = step->GetTotalEnergyDeposit();
    auto* particle = track->GetParticleDefinition();
    const G4bool isOptical =
        (particle == G4OpticalPhoton::OpticalPhotonDefinition());

    // Pre-step volume -> scoring region.
    score::Region region = score::kNumRegions;
    if (auto* vol = step->GetPreStepPoint()->GetTouchableHandle()->GetVolume()) {
        region = score::RegionFromVolume(vol->GetLogicalVolume()->GetName());
    }

    // (1) Energy deposition by region: primary protons vs optical photons.
    //     (Secondary non-optical edep is not tracked -- per decision 16 the
    //      only secondary energy of interest is optical-photon energy.)
    if (region != score::kNumRegions && edep > 0.0) {
        if (isOptical)        fRunAction->AddOpticalEdep(region, edep);
        else if (isPrimary)   fRunAction->AddPrimaryEdep(region, edep);
    }

    // (2) Optical photons generated in this step: count scintillation and
    //     Cerenkov separately (only scintillation is scaled by the divisor).
    for (const auto* sec : *step->GetSecondaryInCurrentStep()) {
        if (sec->GetParticleDefinition()
                == G4OpticalPhoton::OpticalPhotonDefinition()) {
            if (const G4VProcess* creator = sec->GetCreatorProcess()) {
                const G4String& name = creator->GetProcessName();
                if (name == "Scintillation")  fRunAction->AddScintillationPhotons(1.0);
                else if (name == "Cerenkov")  fRunAction->AddCerenkovPhotons(1.0);
            }
        }
    }

    // (3) Photon detected at the photodiode: optical-boundary status Detection.
    if (isOptical) {
        if (!fBoundary) {
            G4ProcessVector* procs = particle->GetProcessManager()->GetProcessList();
            for (G4int i = 0; i < static_cast<G4int>(procs->size()); ++i) {
                if ((*procs)[i]->GetProcessName() == "OpBoundary") {
                    fBoundary = dynamic_cast<G4OpBoundaryProcess*>((*procs)[i]);
                    break;
                }
            }
        }
        if (fBoundary && fBoundary->GetStatus() == Detection) {
            fRunAction->AddPhotodiodeDetected(1.0);
            if (fEventAction && fEventAction->Logging()) {
                fEventAction->RecordPhoton(track->GetGlobalTime() / ns,
                                           track->GetKineticEnergy() / MeV);
            }
        }
    }

    // (4) Time-logging of proton interactions (only when timelog is enabled).
    if (isPrimary && !isOptical && fEventAction && fEventAction->Logging()) {
        G4StepPoint* pre  = step->GetPreStepPoint();
        G4StepPoint* post = step->GetPostStepPoint();

        // Entry into CD / CsI / ACD / photodiode: first step inside the volume
        // starts on a geometry boundary; the pre-step point holds the entry
        // time/energy. "PD" here is the proton's own direct passage through
        // the photodiode silicon -- distinct from the optical-photon
        // detections handled in block (3) above.
        if (pre->GetStepStatus() == fGeomBoundary) {
            const G4double t  = pre->GetGlobalTime() / ns;
            const G4double ke = pre->GetKineticEnergy() / MeV;
            if (region == score::kSiCD && !fEventAction->EnteredCD())
                fEventAction->RecordProtonEnterCD(t, ke);
            else if (region == score::kCsI && !fEventAction->EnteredCsI())
                fEventAction->RecordProtonEnterCsI(t, ke);
            else if (region == score::kSiACD && !fEventAction->EnteredACD())
                fEventAction->RecordProtonEnterACD(t, ke);
            else if (region == score::kPhotodiode && !fEventAction->EnteredPD())
                fEventAction->RecordProtonEnterPD(t, ke);
        }

        // Leaving the CD / CsI / ACD / photodiode: either the proton crosses
        // out, or it stops (ranges out) inside -- log whichever happens
        // first, once per element. Mirrors the entry logic above, one region
        // at a time.
        const bool isTrackedElement = (region == score::kSiCD ||
                                       region == score::kCsI ||
                                       region == score::kSiACD ||
                                       region == score::kPhotodiode);
        if (isTrackedElement) {
            bool alreadyLeft = false;
            if      (region == score::kSiCD)      alreadyLeft = fEventAction->LeftCD();
            else if (region == score::kCsI)       alreadyLeft = fEventAction->LeftCsI();
            else if (region == score::kSiACD)     alreadyLeft = fEventAction->LeftACD();
            else                                  alreadyLeft = fEventAction->LeftPD();

            if (!alreadyLeft) {
                auto recordLeave = [&](G4double t, G4double ke, bool stopped) {
                    if (region == score::kSiCD)
                        fEventAction->RecordProtonLeaveCD(t, ke, stopped);
                    else if (region == score::kCsI)
                        fEventAction->RecordProtonLeaveCsI(t, ke, stopped);
                    else if (region == score::kSiACD)
                        fEventAction->RecordProtonLeaveACD(t, ke, stopped);
                    else
                        fEventAction->RecordProtonLeavePD(t, ke, stopped);
                };
                if (track->GetTrackStatus() == fStopAndKill &&
                    track->GetKineticEnergy() <= 0.0) {
                    recordLeave(post->GetGlobalTime() / ns, 0.0, /*stopped=*/true);
                } else if (post->GetStepStatus() == fGeomBoundary) {
                    auto* nextVol = post->GetPhysicalVolume();
                    const score::Region nextRegion =
                        nextVol ? score::RegionFromVolume(
                                      nextVol->GetLogicalVolume()->GetName())
                                : score::kNumRegions;
                    if (nextRegion != region)
                        recordLeave(post->GetGlobalTime() / ns,
                                    post->GetKineticEnergy() / MeV, /*stopped=*/false);
                }
            }
        }
    }

    // (5) Fate of the primary proton.
    if (isPrimary && !isOptical) {
        const G4StepStatus postStatus =
            step->GetPostStepPoint()->GetStepStatus();
        if (postStatus == fWorldBoundary) {
            // Leaving the world: forward exit = punch-through, else back-scatter.
            if (track->GetMomentumDirection().z() >= 0.0)
                fRunAction->AddPassedThrough();
            else
                fRunAction->AddBackScatter();
        } else if (track->GetTrackStatus() == fStopAndKill &&
                   track->GetKineticEnergy() <= 0.0 &&
                   region != score::kNumRegions) {
            fRunAction->AddPrimaryStopped(region);
        }
    }
    // (6) Secondary (non-optical) particles that stop, tracked separately.
    else if (!isPrimary && !isOptical) {
        if (track->GetTrackStatus() == fStopAndKill &&
            track->GetKineticEnergy() <= 0.0 &&
            region != score::kNumRegions) {
            fRunAction->AddSecondaryStopped(region);
        }
    }
}
