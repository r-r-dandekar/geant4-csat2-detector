/// \file Scoring.cc
/// \brief Implementation of the scoring region helpers.

#include "Scoring.hh"
#include "DetectorConstants.hh"

namespace score {

Region RegionFromVolume(const G4String& v) {
    using namespace det;
    if (v == kAluminiumWindowName)     return kAluminium;
    if (v == kSiCoincidenceName)       return kSiCD;
    if (v == kTeflonCsIName ||
        v == kTeflonPhotodiodeName)    return kTeflon;
    if (v == kCsIName)                 return kCsI;
    if (v == kSiAnticoincidenceName)   return kSiACD;
    if (v == kPhotodiodeName)          return kPhotodiode;
    return kNumRegions;  // world / envelope / empty passage
}

const char* RegionName(Region region) {
    switch (region) {
        case kAluminium:  return "Al window";
        case kSiCD:       return "Si C.D.";
        case kTeflon:     return "Teflon";
        case kCsI:        return "CsI(Tl)";
        case kSiACD:      return "Si A.C.D.";
        case kPhotodiode: return "Photodiode";
        default:          return "other";
    }
}

}  // namespace score
