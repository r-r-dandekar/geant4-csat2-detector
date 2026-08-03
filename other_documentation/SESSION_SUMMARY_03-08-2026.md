# Session Summary — Detector Tracking, Realistic Flux Weighting, and Proton-Induced Photocurrent Modeling

## Overview

The detector under simulation is a proton telescope: an Al entrance window,
a silicon coincidence detector (CD), a vacuum drift gap, a CsI(Tl)
scintillator with a side-mounted photodiode (PD) read out through it, and a
silicon anti-coincidence detector (ACD) at the back. This work did three
things: corrected the modeled thickness of CD/ACD to match the real
hardware, made the simulation's energy-sweep output represent a physically
realistic proton flux rather than an arbitrary sample, and added a model of
the electrical photocurrent that protons directly generate in CD, ACD, and
PD by ionizing the silicon — as opposed to the photocurrent already modeled
from CsI's scintillation light hitting the PD.

This document leads with the physics — what each component physically is,
what we assumed about it, and why — and only briefly notes the underlying
software changes, since the intended reader is expected to know the detector
better than the codebase.

---

## 1. Detector geometry: CD and ACD are 300 µm, not 1.78 mm

CD, ACD, and the photodiode (PD) are the same physical part: a silicon PIN
photodiode. The simulation had been modeling CD and ACD as 1.78 mm of solid
silicon, while modeling the same part in its PD role as only 300 µm.

This inconsistency traces to two different datasheet numbers for the same
component. **1.78 mm is the thickness of the full packaged part** —
silicon die plus plastic casing. **300 µm is the depletion-layer thickness
at the part's intended 70 V reverse bias.** Those are not the same
quantity, and modeling CD/ACD as 1.78 mm of solid silicon silently substituted
the package dimension for the active silicon dimension.

Why 300 µm is the physically correct number to use: a PIN diode's defining
feature is a thin, lightly-doped ("intrinsic") layer sandwiched between the
p- and n-type regions. Because it's so lightly doped, that layer depletes —
becomes fully swept of free carriers, with a strong internal field across it
— at a modest reverse bias. Datasheets quote "depletion layer thickness" at
the rated operating voltage specifically because that's the design point at
which the intrinsic layer is *fully* depleted. So 300 µm is not "the
depleted fraction of a thicker die" — for a properly biased PIN diode, it's
essentially the entire active silicon thickness, full stop. The other ~1.48
mm of the 1.78 mm package is not silicon at all.

Modeling CD/ACD as a full 1.78 mm of silicon therefore overstates real
proton energy deposition, since silicon has much higher stopping power than
whatever casing material actually occupies most of that thickness. The fix:
CD and ACD are now modeled as 300 µm of silicon, matching PD. The casing
itself is deliberately **not** modeled (no separate material/geometry for
it) — this is a simplification, not an oversight, and it means the model
still doesn't capture whatever scattering or energy loss happens in the
casing before a proton reaches the active silicon.

(This correction also happens to restore a value already specified in the
project's own design-decision log, which had called for 0.03 cm — the code
had drifted from its own prior decision independently of this investigation.)

---

## 2. Realistic proton flux weighting (SPENVIS)

A Geant4 run only ever simulates however many protons you ask it to — a few
hundred to a few thousand per energy, purely for statistics. That is not what
the detector actually sees in orbit: the real trapped-proton environment has
a strongly energy-dependent flux (many more low-energy protons than
high-energy ones, following a roughly power-law-like falling spectrum), and
the number of protons hitting the detector per second at each energy varies
by many orders of magnitude across the energy range.

The consolidation step (`sweep_consolidate.py`) exists to bridge this gap:
it takes the modest number of *simulated* protons per energy and resamples
them (with repetition) into a much larger, weighted set whose relative
proportions across energies match a real flux model, spread across a chosen
observation-time window — producing something that looks like what the
detector would actually record over that period, built out of the physics
we already simulated.

The flux model used is derived from **SPENVIS AP-8 MAX** data — a standard
model of the trapped proton radiation environment. SPENVIS naturally
reports flux as an **integral** (cumulative) quantity: `J(>E)`, the flux of
all protons with energy greater than `E`, in protons/cm²/s. To get the
number of protons expected in a specific energy *bin* (say, between two of
the simulated energies), you difference the integral flux at the bin's two
edges: `flux_in_bin = J(>E_low) − J(>E_high)`. Values of `J` at energies not
directly tabulated are found by log-log interpolation, which is the
standard way to interpolate flux spectra (they're closer to power laws than
straight lines, so interpolating in log-log space, not linear space, keeps
the interpolated values physically reasonable).

The number of protons a given differential flux implies over an observation
window follows directly from what "flux" means dimensionally: protons per
unit area per unit time. So the expected count is
`count = flux (protons/cm²/s) × duration (s) × area (cm²)`, using the
detector's actual 10 mm × 10 mm active face as the area. This is the
standard way to turn a flux model into a synthetic event count for a
simulation, and it was cross-checked against the raw SPENVIS integral data
directly (the log-log-interpolate-then-difference values were verified to
reproduce a known-correct reference table, computed from the same underlying
SPENVIS numbers, to within numerical noise).

The practical effect: the sweep's output CSV now represents a physically
meaningful synthetic exposure — e.g., "what the detector would see over 1
second in this environment" — rather than a sample whose relative proton
counts per energy were arbitrary.

---

## 3. Per-element proton entry/exit tracking

The simulation timelog already recorded, for the CsI crystal, the time and
kinetic energy of a proton both *entering* and *leaving* (or stopping in)
the crystal — enough to compute energy deposited there directly
(`KE_enter − KE_leave`, with `KE_leave = 0` if the proton ranged out inside).
The Si coincidence detector (CD) and anti-coincidence detector (ACD) only
had the *entry* half of this recorded; the photodiode (PD) had no
proton-tracking at all — only optical photon detections, a separate physical
process (scintillation light absorption, not proton ionization).

This was extended so all four elements (CD, CsI, ACD, PD) now record both
halves consistently, which is what makes it possible to compute
per-element proton energy deposit — the input the photocurrent model below
needs — for CD, ACD, and PD, not just CsI.

---

## 4. Proton-induced photocurrent model

This is the main physics content of this work: a model of the electrical
current that protons generate directly in the CD, ACD, and PD silicon by
ionizing it — as distinct from the *photon*-induced photocurrent already
modeled separately (scintillation light from CsI striking the PD, converted
to current via the photodiode's wavelength-dependent responsivity/quantum
efficiency).

### 4.1 Charge generation: ionization, not photon absorption

When a proton (or any charged particle) passes through silicon, it loses
energy along its track primarily by ionizing the lattice — knocking
electrons out of the valence band, creating electron-hole pairs. The mean
energy required to create one electron-hole pair in silicon is a material
constant, **W ≈ 3.6 eV**, essentially independent of the incident particle's
energy or the exact ionization mechanism. So the number of pairs created by
a proton depositing energy `edep` (from Geant4's own energy-deposition
tracking) is simply `N = edep / W`, and the resulting charge is
`Q = N × q` (`q` = elementary charge).

This is fundamentally different from the photon-induced mechanism, where
the relevant conversion factor is the photodiode's *responsivity* — a
wavelength-dependent quantity describing how efficiently absorbed photons
convert to charge, which has no bearing on charge produced by direct
ionization. Confusing the two mechanisms (e.g. applying a responsivity curve
to proton-deposited energy) would be a category error; keeping them fully
separate, as done here, is a hard physical requirement, not a stylistic
choice.

### 4.2 Why full charge collection efficiency was assumed

Not all charge generated in a silicon detector reaches the electrodes.
Whether it does depends entirely on *where* it's created relative to the
diode's depleted (field) region:

- **Inside the depletion region**, the strong built-in field (from the
  reverse bias) sweeps electrons and holes apart immediately. This is
  *drift* transport: fast (nanosecond-scale, as derived below), essentially
  deterministic, and with negligible opportunity for the carriers to
  recombine before being collected. Collection efficiency here is
  genuinely close to 100%.
- **Outside the depletion region** (undepleted, field-free silicon),
  carriers have no directed force acting on them and can only move by slow,
  random thermal diffusion. Most such carriers recombine — are lost —
  before ever reaching the depletion edge; this is the classic lossy
  collection pathway in a partially-depleted detector, and it is genuinely
  difficult to model without detailed doping-profile data we don't have.

The reasoning for assuming ~100% efficiency here is not "PIN diodes are
generally good detectors" as a rule of thumb — it's that **if the entire
active silicon volume is depleted, the lossy pathway has nowhere to exist**.
There is no undepleted region left for charge to be generated in and lost
from. And this is not merely assumed for CD, ACD, and PD generically: it
follows directly from §1 above, where the datasheet's 300 µm depletion
thickness at the intended 70 V bias was shown to equal the *entire* modeled
silicon thickness of all three elements. Full depletion here isn't a
generic property of PIN diodes — it's a specific, checked property of this
part at this bias.

### 4.3 Pulse timing: derived from carrier drift physics

Charge generated in the depletion region doesn't appear at the electrodes
instantaneously — it has to physically drift across the depletion width
under the field first, and that transit takes a finite, calculable time,
which sets the shape/duration of the resulting current pulse.

The field across the depletion region is simply bias over distance:
`E = V/d = 70 V / 300 µm ≈ 2.33 kV/cm`. This number matters beyond its own
sake because it determines *which* drift regime applies. Silicon's carrier
velocity is proportional to field (`v = μE`, `μ` = mobility) only up to a
point; above roughly 10–20 kV/cm, velocity saturates and stops increasing
with field. Since 2.33 kV/cm is well below that threshold, the
mobility-proportional regime applies here — this was checked against the
actual field, not assumed by default.

Electrons and holes have different mobilities in silicon (electrons
~1400 cm²/V·s, holes ~450 cm²/V·s — holes are the slower carrier by roughly
a factor of three). Both drift the same 300 µm depletion width but at
different speeds, giving transit times of roughly **9 ns for electrons**
and **29 ns for holes**. Every ionization event produces one of each, moving
in opposite directions; the induced current from that event isn't fully
finished until *both* carrier types have finished transiting. Since holes
are slower, they set when collection is actually complete — the ~29 ns
figure, not the faster electron time, is the physically meaningful pulse
duration.

### 4.4 Pulse shape: a deliberate simplification, and its cost

The textbook-exact induced-current shape for this kind of event (Ramo's
theorem, for charge generated along a track drifting under a roughly
uniform field) is a two-level trapezoid: full current while both carrier
types are still moving, dropping to a lower level once the faster electrons
finish and only the slower holes remain, until they finish too.

This model uses a single symmetric Gaussian pulse instead, which does not
capture that two-level structure. This is a known, explicit approximation,
made for two reasons: it keeps the same pulse-shaping approach already used
for the photon-induced current model (so the two current sources are built
consistently and can eventually be summed), and the shape is largely washed
out anyway by the external readout circuit's own RC filtering, which is
applied afterward and matters more to the final observed waveform than the
exact shape assumed here.

The width of that Gaussian (its standard deviation) was set to roughly
**one-third of the 29 ns hole transit time (~10 ns)**, deliberately *not*
equal to the full 29 ns. The reason is that a Gaussian is symmetric about
its center, so setting its width equal to the full one-sided physical
duration would spread a substantial fraction of the pulse to *before* the
triggering event — a modest but real violation of causality. Using a
narrower width keeps the pulse's overall spread comparable to the real
~29 ns duration without exaggerating it, at the cost of still allowing a
small, explicitly acknowledged non-causal tail.

### 4.5 Shot noise, and a deliberate non-use of the datasheet's bandwidth spec

Shot noise — the fundamental statistical fluctuation in any current made of
discrete charge carriers — was added using the standard formula
`σ = √(2 q I Δf)`, where `Δf` is a noise bandwidth. The datasheet's own
"cutoff frequency" (40 MHz) was used for this `Δf`, but **deliberately not**
for shaping the pulse itself. The reasoning: a datasheet cutoff frequency is
almost always measured with the manufacturer's own external test load
resistor, meaning it reflects a combination of the diode's intrinsic
response *and* an external RC time constant particular to that test
circuit — it is not a clean measurement of the diode's own carrier-transit
physics. Using it to shape the pulse here, when the external readout
circuit's own RC filtering (its own resistor and capacitance) is applied
downstream anyway, would double-count the same RC rolloff twice. This
mirrors how the photon-induced current model already treats the same
datasheet number.

### 4.6 Additivity of proton- and photon-induced current

Proton-induced ionization current and photon-induced (scintillation)
current are treated as simply additive — the same underlying carriers
(electrons and holes), collected by the same field, regardless of what
created them. This holds physically as long as three conditions are true,
all of which apply here:

- The device operates in a linear, low-injection regime (true for
  individual particle/photon events at these rates — nowhere near enough
  carrier density to perturb the internal field).
- There's no internal charge-carrier multiplication (true for a plain PIN
  photodiode; this would *not* hold for an avalanche photodiode, where gain
  could interact nonlinearly between the two populations).
- There's no nonlinear quenching in the *collection* process itself. (Birks'
  law quenching, used elsewhere in this simulation, describes nonlinearity
  in how much scintillation *light* a given energy deposit produces in
  CsI — it has no counterpart in how a photodiode collects already-existing
  charge, so it doesn't apply here and doesn't threaten additivity.)

Because of this, the two mechanisms can be modeled entirely independently —
as they are, in two separate scripts — and combined later by direct
summation, provided both are evaluated on the same absolute timeline.

### 4.7 Other simplifications, stated explicitly

- **Casing not modeled** (§1): CD/ACD energy deposit reflects only the
  300 µm of active silicon; any real energy loss or scattering in the
  package's casing material is not represented.
- **Instantaneous charge generation:** each hit's charge is treated as
  generated at a single instant (the proton's entry time) rather than
  spread across its transit of the element. This is justified by timescale
  separation — a proton crosses even the full CD/ACD/PD thickness in
  picoseconds, far faster than the ~10–30 ns carrier-collection process
  that dominates the actual pulse duration, so treating generation as
  instantaneous relative to collection is a small effect.

---

## 5. Software changes (brief)

The above physics is implemented by two scripts:
`sweep_consolidate.py` (flux-weighted resampling, described in §2) and the
new `proton_photocurrent_model.py` (the photocurrent model in §4), which
reads `sweep_consolidate.py`'s output and, per element, converts energy
deposits to charge, bins them in time, applies the Gaussian transit-time
smoothing and shot noise from §4, and writes out a current waveform (CSV,
a SPICE/TINA-importable format, and a plot) per element.

Beyond the physics changes above, this session also fixed a number of
purely software-engineering issues in the consolidation pipeline: excessive
memory use and runtime on large sweeps, a units/scaling bug that made the
observation-time-window setting not actually affect output size, some
inconsistent column-naming between two alternative versions of the
consolidation script, and a couple of related plotting/validation scripts
that needed the same fixes to stay compatible. None of these affected the
physics described above; they affected whether the pipeline could run
correctly and efficiently at realistic data volumes.

---

## 6. Open items

- Any detector output generated before the §1 geometry fix or the §3
  tracking extension used the old, incorrect CD/ACD thickness or lacked
  ACD/PD exit tracking — it needs to be regenerated.
- The pulse-shape simplification (§4.4) is a known approximation; a more
  physically direct alternative (building the pulse from each event's
  actual measured transit time rather than an assumed Gaussian width) was
  considered but not implemented, in favor of consistency with the existing
  photon-current model.
- Proton- and photon-induced current are not yet actually summed into one
  combined signal (§4.6) — they are currently written as separate outputs,
  to be combined once both are evaluated on a shared timeline.
- The exact SPENVIS query parameters behind the flux model in §2 (specific
  orbit, shielding assumption, mission epoch) are taken as given from the
  reference data provided and were not independently re-derived.
