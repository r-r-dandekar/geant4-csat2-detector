/// \file Scoring.hh
/// \brief Detector scoring regions and volume-name -> region mapping.
///
/// The simulation tallies quantities per detector element. Regions are indexed
/// by the `Region` enum so that tallies can be stored in fixed-size arrays.

#ifndef Scoring_h
#define Scoring_h 1

#include "globals.hh"

namespace score {

// Scored detector elements. kNumRegions doubles as both the array size and the
// "not a scored volume" sentinel (world / envelope / vacuum gap).
enum Region {
    kAluminium = 0,
    kSiCD,
    kTeflon,
    kCsI,
    kSiACD,
    kPhotodiode,
    kNumRegions
};

// Map a logical-volume name to a Region; returns kNumRegions if the volume is
// not a scored detector element. Both teflon wraps map to kTeflon.
Region RegionFromVolume(const G4String& volumeName);

// Human-readable region name (for console / CSV headers).
const char* RegionName(Region region);

}  // namespace score

#endif
