/// \file DetectorConstruction.hh
/// \brief Definition of the DetectorConstruction class.
///
/// Builds the particle-detector geometry (in beam order):
///   Al window -> Si coincidence detector -> vacuum gap ->
///   CsI(Tl) scintillator (teflon-wrapped, with a side photodiode) ->
///   Si anti-coincidence detector.
///
/// Iteration 1: geometry + materials only. Optical/scintillation properties
/// and surfaces are added in the optical iteration.

#ifndef DetectorConstruction_h
#define DetectorConstruction_h 1

#include "G4VUserDetectorConstruction.hh"
#include "globals.hh"

class G4VPhysicalVolume;
class G4LogicalVolume;
class G4Box;
class G4Material;
class G4NistManager;

/// Bundles the three representations of one detector element.
struct Geometry {
    G4Box*            solid    = nullptr;
    G4LogicalVolume*  logical  = nullptr;
    G4VPhysicalVolume* physical = nullptr;
};

/// Simple (x, y, z) triple used for sizes and positions.
struct Vec3 {
    G4double x = 0.0;
    G4double y = 0.0;
    G4double z = 0.0;
};

class DetectorConstruction : public G4VUserDetectorConstruction {
  public:
    DetectorConstruction();
    ~DetectorConstruction() override;

    G4VPhysicalVolume* Construct() override;

    G4LogicalVolume* GetScoringVolume() const { return fScoringVolume; }

  private:
    // --- generic volume builders ------------------------------------------
    G4Box*            MakeBox(const G4String& name, const Vec3& fullSize);
    G4LogicalVolume*  MakeLogical(G4Box* solid, G4Material* material,
                                  const G4String& name);
    G4VPhysicalVolume* Place(const Vec3& centre, G4LogicalVolume* logical,
                             const G4String& name,
                             G4LogicalVolume* mother);

    // --- per-element builders (all placed in the envelope) ----------------
    Geometry BuildWorld();
    Geometry BuildEnvelope(G4LogicalVolume* mother);
    Geometry BuildAluminiumWindow(G4LogicalVolume* mother);
    Geometry BuildSiliconCoincidence(G4LogicalVolume* mother);
    Geometry BuildEmptyPassage(G4LogicalVolume* mother);
    Geometry BuildCsI(G4LogicalVolume* mother);
    Geometry BuildSiliconAnticoincidence(G4LogicalVolume* mother);
    Geometry BuildPhotodiode(G4LogicalVolume* mother);

    // Teflon wraps (with the optical coupling window carved out).
    // BuildCsITeflonCoating returns the placed physical volume so that an
    // optical border surface can be attached to it.
    G4VPhysicalVolume* BuildCsITeflonCoating(G4LogicalVolume* mother);
    void BuildPhotodiodeTeflonCoating(G4LogicalVolume* mother);

    // --- materials --------------------------------------------------------
    G4Material* MaterialVacuum();   // cached; built once with RINDEX = 1
    G4Material* MaterialAluminium();
    G4Material* MaterialSilicon();
    G4Material* MaterialCsITl();    // built once with full scintillation MPT
    G4Material* MaterialTeflon();

    // --- optical setup ----------------------------------------------------
    void BindCsIScintillation(G4Material* csiTl);   // RINDEX + scintillation MPT + Birks
    void SetupOpticalSurfaces();                    // teflon reflector + photodiode readout

    G4NistManager*   fNist = nullptr;
    G4LogicalVolume* fScoringVolume = nullptr;

    // Cached materials.
    G4Material* fVacuum = nullptr;

    // Physical-volume pointers needed for optical border surfaces.
    G4VPhysicalVolume* fEnvelopePhys   = nullptr;
    G4VPhysicalVolume* fCsIPhys        = nullptr;
    G4VPhysicalVolume* fTeflonCsIPhys  = nullptr;
    G4VPhysicalVolume* fPhotodiodePhys = nullptr;
};

#endif
