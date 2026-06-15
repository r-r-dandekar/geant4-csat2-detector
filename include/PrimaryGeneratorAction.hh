/// \file PrimaryGeneratorAction.hh
/// \brief Definition of the PrimaryGeneratorAction class.
///
/// Iteration 1: fires a single proton as an "ideal" pencil beam -- straight
/// along +z from the centre of the front face. The realistic (cosine-law,
/// full-face) beam mode and the run-time mode switch are added later.

#ifndef PrimaryGeneratorAction_h
#define PrimaryGeneratorAction_h 1

#include "G4VUserPrimaryGeneratorAction.hh"
#include "globals.hh"

class G4ParticleGun;
class G4Event;

class PrimaryGeneratorAction : public G4VUserPrimaryGeneratorAction {
  public:
    PrimaryGeneratorAction();
    ~PrimaryGeneratorAction() override;

    void GeneratePrimaries(G4Event* event) override;

    const G4ParticleGun* GetParticleGun() const { return fParticleGun; }

  private:
    G4ParticleGun* fParticleGun = nullptr;
};

#endif
