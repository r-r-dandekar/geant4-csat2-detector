/// \file PrimaryGeneratorAction.cc
/// \brief Implementation of the PrimaryGeneratorAction class.

#include "PrimaryGeneratorAction.hh"
#include "DetectorConstants.hh"
#include "RunConfig.hh"

#include "G4ParticleGun.hh"
#include "G4ParticleTable.hh"
#include "G4ParticleDefinition.hh"
#include "G4Event.hh"
#include "G4ThreeVector.hh"
#include "G4SystemOfUnits.hh"
#include "G4PhysicalConstants.hh"
#include "Randomize.hh"

#include <cmath>

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

PrimaryGeneratorAction::PrimaryGeneratorAction()
    : fParticleGun(new G4ParticleGun(1)) {
    G4ParticleDefinition* proton =
        G4ParticleTable::GetParticleTable()->FindParticle("proton");
    fParticleGun->SetParticleDefinition(proton);
}

PrimaryGeneratorAction::~PrimaryGeneratorAction() {
    delete fParticleGun;
}

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* event) {
    using namespace det;

    // Launch plane: just in front of the Al window (front of the detector
    // stack), so realistic-mode angled protons still enter the detector.
    const G4double zFront =
        -(kEmptyPassageLength + kSiliconCoincidenceLength + kAluminiumLength);
    const G4double z0 = zFront - 0.1 * mm;

    G4double x0 = 0.0, y0 = 0.0;
    G4ThreeVector direction(0.0, 0.0, 1.0);

    if (cfg::gBeamMode == cfg::BeamMode::kRealistic) {
        // Uniform position over the full 10x10 mm active face (decision 19).
        x0 = (G4UniformRand() - 0.5) * kCrossSectionX;
        y0 = (G4UniformRand() - 0.5) * kCrossSectionY;

        // Cosine-law (Lambertian) angular distribution about +z (decision 18):
        // the physically correct distribution for an isotropic external flux
        // crossing a flat surface. cos(theta) = sqrt(U) gives PDF ~ cos(theta).
        const G4double cosTheta = std::sqrt(G4UniformRand());
        const G4double sinTheta = std::sqrt(1.0 - cosTheta * cosTheta);
        const G4double phi      = twopi * G4UniformRand();
        direction = G4ThreeVector(sinTheta * std::cos(phi),
                                  sinTheta * std::sin(phi),
                                  cosTheta);
    }
    // else: ideal pencil beam -- centre of the face, straight +z.

    fParticleGun->SetParticlePosition(G4ThreeVector(x0, y0, z0));
    fParticleGun->SetParticleMomentumDirection(direction);

    // Energy from the `energy=` command-line argument (single source of truth).
    fParticleGun->SetParticleEnergy(cfg::gPrimaryEnergy);

    fParticleGun->GeneratePrimaryVertex(event);
}
