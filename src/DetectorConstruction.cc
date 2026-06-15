/// \file DetectorConstruction.cc
/// \brief Implementation of the DetectorConstruction class.

#include "DetectorConstruction.hh"
#include "DetectorConstants.hh"
#include "RunConfig.hh"

#include "G4NistManager.hh"
#include "G4Material.hh"
#include "G4Element.hh"
#include "G4Box.hh"
#include "G4SubtractionSolid.hh"
#include "G4LogicalVolume.hh"
#include "G4PVPlacement.hh"
#include "G4ThreeVector.hh"
#include "G4SystemOfUnits.hh"
#include "G4VisAttributes.hh"
#include "G4Colour.hh"

#include "G4MaterialPropertiesTable.hh"
#include "G4OpticalSurface.hh"
#include "G4LogicalBorderSurface.hh"

#include <vector>
#include <cmath>

using namespace det;

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

DetectorConstruction::DetectorConstruction() = default;
DetectorConstruction::~DetectorConstruction() = default;

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

G4VPhysicalVolume* DetectorConstruction::Construct() {
    fNist = G4NistManager::Instance();

    Geometry world    = BuildWorld();
    Geometry envelope = BuildEnvelope(world.logical);
    fEnvelopePhys = envelope.physical;

    BuildAluminiumWindow(envelope.logical);
    Geometry siCoincidence = BuildSiliconCoincidence(envelope.logical);
    BuildEmptyPassage(envelope.logical);
    Geometry csi = BuildCsI(envelope.logical);
    fCsIPhys = csi.physical;
    BuildSiliconAnticoincidence(envelope.logical);
    Geometry photodiode = BuildPhotodiode(envelope.logical);
    fPhotodiodePhys = photodiode.physical;

    // Optical surfaces (teflon reflector + photodiode readout) need the
    // physical-volume pointers captured above.
    SetupOpticalSurfaces();

    // Scoring volume kept as the Si coincidence detector (as in the original
    // code, used by RunAction's dose calculation).
    fScoringVolume = siCoincidence.logical;

    return world.physical;
}

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......
// Generic builders
//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

G4Box* DetectorConstruction::MakeBox(const G4String& name, const Vec3& s) {
    // G4Box takes half-lengths.
    return new G4Box(name, 0.5 * s.x, 0.5 * s.y, 0.5 * s.z);
}

G4LogicalVolume* DetectorConstruction::MakeLogical(G4Box* solid,
                                                   G4Material* material,
                                                   const G4String& name) {
    return new G4LogicalVolume(solid, material, name);
}

G4VPhysicalVolume* DetectorConstruction::Place(const Vec3& c,
                                               G4LogicalVolume* logical,
                                               const G4String& name,
                                               G4LogicalVolume* mother) {
    return new G4PVPlacement(nullptr,                       // no rotation
                             G4ThreeVector(c.x, c.y, c.z),  // position
                             logical,                       // logical volume
                             name,                          // name
                             mother,                        // mother volume
                             false,                         // no boolean op
                             0,                             // copy number
                             true);                         // check overlaps
}

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......
// World & envelope
//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

Geometry DetectorConstruction::BuildWorld() {
    Geometry g;
    Vec3 size{ kWorldScaleFactor * kDetectorSizeX,
               kWorldScaleFactor * kDetectorSizeY,
               kWorldScaleFactor * kDetectorSizeZ };

    g.solid    = MakeBox(kWorldName, size);
    g.logical  = MakeLogical(g.solid, MaterialVacuum(), kWorldName);

    // The world must be invisible, otherwise it is drawn as an opaque solid
    // box that hides everything inside it.
    auto* vis = new G4VisAttributes();
    vis->SetVisibility(false);
    g.logical->SetVisAttributes(vis);

    g.physical = Place({ kOriginX, kOriginY, kOriginZ }, g.logical, kWorldName,
                       nullptr);
    return g;
}

Geometry DetectorConstruction::BuildEnvelope(G4LogicalVolume* mother) {
    Geometry g;
    Vec3 size{ kDetectorSizeX + kEnvelopeExtraX,
               kDetectorSizeY + kEnvelopeExtraY,
               kDetectorSizeZ };

    g.solid   = MakeBox(kEnvelopeName, size);
    g.logical = MakeLogical(g.solid, MaterialVacuum(), kEnvelopeName);

    // Blue wireframe: if not wireframe, some inner components don't render
    // even at low alpha (reason unclear -- kept from original code).
    auto* vis = new G4VisAttributes(G4Colour(0.0, 0.0, 1.0));
    vis->SetForceWireframe(true);
    g.logical->SetVisAttributes(vis);

    g.physical = Place({ kOriginX, kOriginY, kOriginZ }, g.logical,
                       kEnvelopeName, mother);
    return g;
}

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......
// Detector elements (beam order)
//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

Geometry DetectorConstruction::BuildAluminiumWindow(G4LogicalVolume* mother) {
    Geometry g;
    Vec3 size{ kCrossSectionX, kCrossSectionY, kAluminiumLength };

    g.solid   = MakeBox(kAluminiumWindowName, size);
    g.logical = MakeLogical(g.solid, MaterialAluminium(), kAluminiumWindowName);

    Vec3 centre{ kOriginX, kOriginY,
                 -(kEmptyPassageLength + kSiliconCoincidenceLength
                   + kAluminiumLength / 2.0) };
    g.physical = Place(centre, g.logical, kAluminiumWindowName, mother);

    g.logical->SetVisAttributes(new G4VisAttributes(G4Colour(0.45, 0.25, 0.0, 0.5)));
    return g;
}

Geometry DetectorConstruction::BuildSiliconCoincidence(G4LogicalVolume* mother) {
    Geometry g;
    Vec3 size{ kCrossSectionX, kCrossSectionY, kSiliconCoincidenceLength };

    g.solid   = MakeBox(kSiCoincidenceName, size);
    g.logical = MakeLogical(g.solid, MaterialSilicon(), kSiCoincidenceName);

    Vec3 centre{ kOriginX, kOriginY,
                 -(kEmptyPassageLength + kSiliconCoincidenceLength / 2.0) };
    g.physical = Place(centre, g.logical, kSiCoincidenceName, mother);

    g.logical->SetVisAttributes(new G4VisAttributes(G4Colour(0.0, 0.0, 1.0, 0.5)));
    return g;
}

Geometry DetectorConstruction::BuildEmptyPassage(G4LogicalVolume* mother) {
    Geometry g;
    Vec3 size{ kCrossSectionX, kCrossSectionY, kEmptyPassageLength };

    g.solid   = MakeBox(kEmptyPassageName, size);
    g.logical = MakeLogical(g.solid, MaterialVacuum(), kEmptyPassageName);

    Vec3 centre{ kOriginX, kOriginY, -(kEmptyPassageLength / 2.0) };
    g.physical = Place(centre, g.logical, kEmptyPassageName, mother);

    g.logical->SetVisAttributes(new G4VisAttributes(G4Colour(0.0, 1.0, 1.0, 0.5)));
    return g;
}

Geometry DetectorConstruction::BuildCsI(G4LogicalVolume* mother) {
    Geometry g;
    // The CsI crystal sits inside the teflon wrap, so it is smaller than the
    // cross-section by the wrap thickness on each side.
    Vec3 size{ kCrossSectionX - 2.0 * kTeflonThicknessCsI,
               kCrossSectionY - 2.0 * kTeflonThicknessCsI,
               kCsILength      - 2.0 * kTeflonThicknessCsI };

    g.solid   = MakeBox(kCsIName, size);
    g.logical = MakeLogical(g.solid, MaterialCsITl(), kCsIName);

    Vec3 centre{ kOriginX, kOriginY, kCsILength / 2.0 };
    g.physical = Place(centre, g.logical, kCsIName, mother);

    // Build the teflon wrap (with the photodiode coupling window) and keep its
    // physical volume for the reflective optical surface.
    fTeflonCsIPhys = BuildCsITeflonCoating(mother);

    g.logical->SetVisAttributes(new G4VisAttributes(G4Colour(1.0, 1.0, 0.0, 0.5)));
    return g;
}

Geometry DetectorConstruction::BuildSiliconAnticoincidence(G4LogicalVolume* mother) {
    Geometry g;
    Vec3 size{ kCrossSectionX, kCrossSectionY, kSiliconAnticoincidenceLength };

    g.solid   = MakeBox(kSiAnticoincidenceName, size);
    g.logical = MakeLogical(g.solid, MaterialSilicon(), kSiAnticoincidenceName);

    Vec3 centre{ kOriginX, kOriginY,
                 kCsILength + kSiliconAnticoincidenceLength / 2.0 };
    g.physical = Place(centre, g.logical, kSiAnticoincidenceName, mother);

    g.logical->SetVisAttributes(new G4VisAttributes(G4Colour(0.0, 0.0, 1.0, 0.5)));
    return g;
}

Geometry DetectorConstruction::BuildPhotodiode(G4LogicalVolume* mother) {
    Geometry g;
    // The photodiode is a thin slab on the +y side face of the CsI. Its thin
    // dimension (y) faces the crystal.
    Vec3 size{ kCrossSectionX   - 2.0 * kTeflonThicknessPhotodiode,
               kPhotodiodeLength - 2.0 * kTeflonThicknessPhotodiode,
               kCrossSectionY   - 2.0 * kTeflonThicknessPhotodiode };

    g.solid   = MakeBox(kPhotodiodeName, size);
    g.logical = MakeLogical(g.solid, MaterialSilicon(), kPhotodiodeName);

    Vec3 centre{ kOriginX,
                 kCrossSectionY / 2.0 + kPhotodiodeLength / 2.0,
                 kCsILength / 2.0 };
    g.physical = Place(centre, g.logical, kPhotodiodeName, mother);

    BuildPhotodiodeTeflonCoating(mother);

    // Magenta so the side-mounted photodiode is easy to pick out from the
    // (blue) silicon detectors during the visual check.
    g.logical->SetVisAttributes(new G4VisAttributes(G4Colour(1.0, 0.0, 1.0, 0.7)));
    return g;
}

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......
// Teflon wraps (hollow boxes with an optical coupling window carved out)
//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

G4VPhysicalVolume* DetectorConstruction::BuildCsITeflonCoating(
        G4LogicalVolume* mother) {
    const G4double t = kTeflonThicknessCsI;

    G4Box* outer = MakeBox("csi_teflon_outer",
                           { kCrossSectionX, kCrossSectionY, kCsILength });
    G4Box* inner = MakeBox("csi_teflon_inner",
                           { kCrossSectionX - 2.0 * t,
                             kCrossSectionY - 2.0 * t,
                             kCsILength      - 2.0 * t });

    // Hollow box (shell).
    auto* shell = new G4SubtractionSolid("csi_teflon_shell", outer, inner);

    // Carve the optical coupling window out of the +y wall (decision 5): a box
    // punched through the +y face over the photodiode footprint, so light can
    // leave the crystal toward the photodiode. The cut box is deep enough in y
    // (4*t) to fully clear the wall.
    G4Box* window = MakeBox("csi_teflon_window",
                            { kCouplingWindowX, 4.0 * t, kCouplingWindowZ });
    auto* shellWithWindow =
        new G4SubtractionSolid(kTeflonCsIName, shell, window, nullptr,
                               G4ThreeVector(0.0, kCrossSectionY / 2.0, 0.0));

    auto* logical = new G4LogicalVolume(shellWithWindow, MaterialTeflon(),
                                        kTeflonCsIName);

    G4VPhysicalVolume* physical =
        Place({ kOriginX, kOriginY, kCsILength / 2.0 }, logical, kTeflonCsIName,
              mother);

    logical->SetVisAttributes(new G4VisAttributes(G4Colour(0.3, 0.3, 0.3, 0.3)));
    return physical;
}

void DetectorConstruction::BuildPhotodiodeTeflonCoating(G4LogicalVolume* mother) {
    const G4double t = kTeflonThicknessPhotodiode;

    G4Box* outer = MakeBox("pd_teflon_outer",
                           { kCrossSectionX, kPhotodiodeLength, kCrossSectionY });
    G4Box* inner = MakeBox("pd_teflon_inner",
                           { kCrossSectionX   - 2.0 * t,
                             kPhotodiodeLength - 2.0 * t,
                             kCrossSectionY   - 2.0 * t });

    auto* shell = new G4SubtractionSolid("pd_teflon_shell", outer, inner);

    // Carve a matching window out of the -y wall (the face toward the CsI) so
    // the photodiode wrap does not re-block the light let through by the CsI
    // window.
    G4Box* window = MakeBox("pd_teflon_window",
                            { kCouplingWindowX, 4.0 * t, kCouplingWindowZ });
    auto* shellWithWindow =
        new G4SubtractionSolid(kTeflonPhotodiodeName, shell, window, nullptr,
                               G4ThreeVector(0.0, -kPhotodiodeLength / 2.0, 0.0));

    auto* logical = new G4LogicalVolume(shellWithWindow, MaterialTeflon(),
                                        kTeflonPhotodiodeName);

    Place({ kOriginX,
            kCrossSectionY / 2.0 + kPhotodiodeLength / 2.0,
            kCsILength / 2.0 },
          logical, kTeflonPhotodiodeName, mother);

    logical->SetVisAttributes(new G4VisAttributes(G4Colour(0.5, 0.5, 0.5, 0.4)));
}

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......
// Materials
//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

G4Material* DetectorConstruction::MaterialVacuum() {
    // Built once and reused for world / envelope / vacuum gap so there is a
    // single material instance (and a single shared RINDEX table).
    if (fVacuum) return fVacuum;

    // A near-perfect vacuum ("interGalactic").
    const G4double atomicNumber = 1.0;
    const G4double massOfMole   = 1.008 * g / mole;
    const G4double density      = 1.0e-25 * g / cm3;
    const G4double temperature  = 2.73 * kelvin;
    const G4double pressure     = 3.0e-18 * pascal;

    fVacuum = new G4Material("interGalactic", atomicNumber, massOfMole, density,
                             kStateGas, temperature, pressure);

    // RINDEX = 1 so that optical photons can propagate through the vacuum
    // (between the CsI window and the photodiode). Without it, optical photons
    // are killed at the CsI boundary -- a cause of the old "no light" behaviour.
    std::vector<G4double> energy   = { 1.0 * eV, 5.0 * eV };
    std::vector<G4double> rindex   = { 1.0, 1.0 };
    auto* mpt = new G4MaterialPropertiesTable();
    mpt->AddProperty("RINDEX", energy, rindex);
    fVacuum->SetMaterialPropertiesTable(mpt);

    return fVacuum;
}

G4Material* DetectorConstruction::MaterialAluminium() {
    return fNist->FindOrBuildMaterial("G4_Al");
}

G4Material* DetectorConstruction::MaterialSilicon() {
    return fNist->FindOrBuildMaterial("G4_Si");
}

G4Material* DetectorConstruction::MaterialCsITl() {
    // Cesium iodide doped with ~1% thallium.
    G4Material* csi = fNist->FindOrBuildMaterial("G4_CESIUM_IODIDE");

    auto* thallium = new G4Element("Thallium", "Tl", 81.0, 206.97742 * g / mole);

    auto* csiTl = new G4Material(kCsIMaterialName, 4.51 * g / cm3, 2);
    csiTl->AddMaterial(csi, 99.0 * perCent);
    csiTl->AddElement(thallium, 1.0 * perCent);

    // Attach RINDEX + scintillation properties + Birks quenching.
    BindCsIScintillation(csiTl);
    return csiTl;
}

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......
// Optical properties
//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

void DetectorConstruction::BindCsIScintillation(G4Material* csiTl) {
    // Photon-energy grid spanning the CsI(Tl) emission band (~400-700 nm).
    // Geant4 requires energies in increasing order.
    constexpr G4int    kN     = 16;
    constexpr G4double kEmin  = 1.78 * eV;   // ~697 nm
    constexpr G4double kEmax  = 3.10 * eV;   // ~400 nm
    constexpr G4double kPeakNm  = 550.0;     // CsI(Tl) emission peak
    constexpr G4double kSigmaNm = 45.0;      // emission band width (approx.)

    std::vector<G4double> energy(kN), rindex(kN), absLength(kN), emission(kN);
    for (G4int i = 0; i < kN; ++i) {
        const G4double e = kEmin + (kEmax - kEmin) * i / (kN - 1);
        energy[i]    = e;
        rindex[i]    = 1.79;        // CsI(Tl) refractive index
        absLength[i] = 400.0 * mm;  // bulk absorption length

        // Broad Gaussian emission spectrum peaking at ~550 nm.
        // NOTE: literature-based approximation -- replace with the actual
        //       crystal's measured emission curve once a datasheet is available.
        const G4double lambdaNm = 1239.841984 / (e / eV);
        emission[i] = std::exp(-0.5 * std::pow((lambdaNm - kPeakNm) / kSigmaNm, 2.0));
    }

    auto* mpt = new G4MaterialPropertiesTable();
    mpt->AddProperty("RINDEX",    energy, rindex);
    mpt->AddProperty("ABSLENGTH", energy, absLength);

    // Two scintillation components (fast + slow). In Geant4 11 these use the
    // SCINTILLATIONCOMPONENT1/2 keys -- the legacy FAST/SLOWCOMPONENT names used
    // by the old code are NOT recognised, so no photons were ever generated.
    mpt->AddProperty("SCINTILLATIONCOMPONENT1", energy, emission);
    mpt->AddProperty("SCINTILLATIONCOMPONENT2", energy, emission);

    // Total light yield. Knoll gives an average of ~65,000 photons/MeV for
    // CsI(Tl); 54,000/MeV is used here (decision 7).
    // Divided by the light-yield divisor (performance knob, default 1000) so the
    // photon count stays tractable; multiply scintillation tallies back by this
    // factor to recover physical counts. Does NOT affect energy deposition.
    const G4double scintYield = (54000.0 / MeV) / cfg::gLightYieldDivisor;
    mpt->AddConstProperty("SCINTILLATIONYIELD", scintYield);
    mpt->AddConstProperty("RESOLUTIONSCALE", 1.0);

    // Time constants and fast/slow split from Knoll Table 8.3 for CsI(Tl).
    // YIELDRATIO 0.64 (old key) -> fast fraction 0.64, slow fraction 0.36,
    // expressed via SCINTILLATIONYIELD1/2 in Geant4 11.
    mpt->AddConstProperty("SCINTILLATIONTIMECONSTANT1", 0.68 * us);
    mpt->AddConstProperty("SCINTILLATIONTIMECONSTANT2", 3.5 * us);
    mpt->AddConstProperty("SCINTILLATIONYIELD1", 0.64);
    mpt->AddConstProperty("SCINTILLATIONYIELD2", 0.36);

    csiTl->SetMaterialPropertiesTable(mpt);

    // Birks' constant for scintillation quenching. Literature-order value for
    // CsI(Tl); replace with a measured/datasheet value when available (decision 9).
    csiTl->GetIonisation()->SetBirksConstant(0.0032 * mm / MeV);
}

void DetectorConstruction::SetupOpticalSurfaces() {
    // --- Teflon reflector on the wrapped CsI faces ------------------------
    // Because the coupling window was carved out of the teflon, the CsI is only
    // adjacent to the teflon on the 5 wrapped faces; the +y window patch is
    // adjacent to the vacuum instead. So a single CsI -> teflon border surface
    // reflects light on exactly the wrapped faces.
    auto* teflonSurface = new G4OpticalSurface("teflon_reflector");
    teflonSurface->SetType(dielectric_metal);   // metal-backed reflector (no transmission)
    teflonSurface->SetModel(unified);
    teflonSurface->SetFinish(groundfrontpainted);

    std::vector<G4double> e            = { 1.5 * eV, 4.0 * eV };
    std::vector<G4double> reflectivity = { 0.98, 0.99 };  // teflon (PTFE) reflectivity
    std::vector<G4double> efficiency   = { 0.0, 0.0 };    // a reflector, not a detector
    auto* teflonMpt = new G4MaterialPropertiesTable();
    teflonMpt->AddProperty("REFLECTIVITY", e, reflectivity);
    teflonMpt->AddProperty("EFFICIENCY",   e, efficiency);
    teflonSurface->SetMaterialPropertiesTable(teflonMpt);

    if (fCsIPhys && fTeflonCsIPhys) {
        new G4LogicalBorderSurface("csi_teflon_border", fCsIPhys,
                                   fTeflonCsIPhys, teflonSurface);
    }

    // --- Photodiode readout -----------------------------------------------
    // Photons that leave the crystal through the window cross the vacuum and
    // strike the photodiode. EFFICIENCY = 1 means every photon reaching the
    // photodiode is absorbed and counted as "detected".
    // NOTE: replace EFFICIENCY = 1 with the photodiode's wavelength-dependent
    //       quantum-efficiency curve once a datasheet is available (decision 10).
    auto* pdSurface = new G4OpticalSurface("photodiode_readout");
    pdSurface->SetType(dielectric_metal);
    pdSurface->SetModel(unified);
    pdSurface->SetFinish(polished);

    std::vector<G4double> pdReflectivity = { 0.0, 0.0 };
    std::vector<G4double> pdEfficiency   = { 1.0, 1.0 };
    auto* pdMpt = new G4MaterialPropertiesTable();
    pdMpt->AddProperty("REFLECTIVITY", e, pdReflectivity);
    pdMpt->AddProperty("EFFICIENCY",   e, pdEfficiency);
    pdSurface->SetMaterialPropertiesTable(pdMpt);

    if (fEnvelopePhys && fPhotodiodePhys) {
        new G4LogicalBorderSurface("photodiode_border", fEnvelopePhys,
                                   fPhotodiodePhys, pdSurface);
    }
}

G4Material* DetectorConstruction::MaterialTeflon() {
    return fNist->FindOrBuildMaterial("G4_TEFLON");
}
