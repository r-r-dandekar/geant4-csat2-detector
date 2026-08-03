/// \file DetectorConstants.hh
/// \brief Fixed geometric parameters of the particle detector.
///
/// These dimensions describe the physical detector and MUST NOT be changed
/// casually -- they correspond to the real hardware. Values resolved during
/// the design review (see 003-decisions.md) are noted inline.

#ifndef DetectorConstants_h
#define DetectorConstants_h 1

#include "G4SystemOfUnits.hh"

namespace det {

// ---------------------------------------------------------------------------
// Overall detector / world / envelope
// ---------------------------------------------------------------------------
constexpr G4double kDetectorSizeX = 1.04 * cm;
constexpr G4double kDetectorSizeY = 1.04 * cm;
constexpr G4double kDetectorSizeZ = 15.0 * cm;

// The envelope is made slightly larger than the detector in x/y so that the
// side-mounted photodiode does not protrude out of its mother (envelope)
// volume, which Geant4 dislikes.
constexpr G4double kEnvelopeExtraX = 0.05 * cm;
constexpr G4double kEnvelopeExtraY = 0.05 * cm;

// World volume is CONST_FACTOR larger than the detector in every dimension.
constexpr G4double kWorldScaleFactor = 1.2;

// Origin (centre of world / envelope).
constexpr G4double kOriginX = 0.0 * cm;
constexpr G4double kOriginY = 0.0 * cm;
constexpr G4double kOriginZ = 0.0 * cm;

// ---------------------------------------------------------------------------
// Active transverse cross-section of the detector stack (10 mm x 10 mm).
// NOTE: 001-intent.md said 50 mm x 50 mm -- that was an error in the doc.
//       The real cross-section is 10 mm x 10 mm (decision 1).
// ---------------------------------------------------------------------------
constexpr G4double kCrossSectionX = 1.0 * cm;
constexpr G4double kCrossSectionY = 1.0 * cm;

// ---------------------------------------------------------------------------
// Longitudinal (z) thicknesses of each element, in beam order.
// ---------------------------------------------------------------------------
constexpr G4double kAluminiumLength          = 0.065 * cm;  // window: stops protons < ~10 MeV
constexpr G4double kSiliconCoincidenceLength  = 0.178 * cm;  // Si C.D.
constexpr G4double kEmptyPassageLength        = 5.0  * cm;  // vacuum drift gap
constexpr G4double kCsILength                 = 3.3  * cm;  // CsI(Tl) scintillator
constexpr G4double kSiliconAnticoincidenceLength = 0.178 * cm;  // Si A.C.D.
constexpr G4double kPhotodiodeLength          = 0.03 * cm;  // photodiode (300 um)

// ---------------------------------------------------------------------------
// Teflon reflective wrapping.
// ---------------------------------------------------------------------------
constexpr G4double kTeflonThicknessCsI        = 0.01 * cm;  // wrap on CsI -- resolved to 0.01 cm (decision 3)
constexpr G4double kTeflonThicknessPhotodiode = 0.005 * cm; // wrap on photodiode

// Optical coupling window aperture in the teflon (decision 5): the patch of
// teflon between the CsI and the photodiode is opened so scintillation light
// can reach the photodiode. Sized to the photodiode's facing footprint.
constexpr G4double kCouplingWindowX = kCrossSectionX - 2.0 * kTeflonThicknessPhotodiode;
constexpr G4double kCouplingWindowZ = kCrossSectionY - 2.0 * kTeflonThicknessPhotodiode;

// ---------------------------------------------------------------------------
// Volume names (used for identification in stepping / scoring).
// ---------------------------------------------------------------------------
constexpr const char* kWorldName            = "world";
constexpr const char* kEnvelopeName         = "envelope";
constexpr const char* kAluminiumWindowName  = "aluminum_window";
constexpr const char* kSiCoincidenceName    = "silicon_coincidence_detector";
constexpr const char* kEmptyPassageName     = "empty_passage";
constexpr const char* kCsIName              = "CsI(Tl)";
constexpr const char* kSiAnticoincidenceName = "silicon_anticoincidence_detector";
constexpr const char* kPhotodiodeName       = "photodiode";
constexpr const char* kTeflonCsIName        = "teflon_coating_CsI";
constexpr const char* kTeflonPhotodiodeName = "teflon_coating_photodiode";

constexpr const char* kCsIMaterialName      = "CsI_Tl";

}  // namespace det

#endif
