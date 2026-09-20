# Confirmed scope — amended 2026-09-19

- Nominal 12 V house-bank distribution; 40 A simultaneous continuous **target**.
- Guaranteed operating-input design range: **9.5–16 V**, revised with the owner's
  approval on 2026-09-16 to provide headroom for the latch-off controller.
- Eight channels retain their maximum branch fuse sizes: 10/10/5/5/5/5/5/20 A.
- Mostly VHF/GPS and other electronics, lights, and intermittently operated pumps.
  Exact models, inrush/stall currents and channel allocation are unspecified.
- External relays are an owner-provided fallback for pumps. No onboard relay
  circuitry is requested. Motor current must use the relay's separately protected
  power circuit if the intent is to keep it off this PCB; switching only the coil
  does not qualify an arbitrary relay or pump combination.
- Initial USB programming takes place with the house-bank connection disconnected;
  later firmware updates are OTA. Preserve USB-only logic power and boot/reset
  access. Simultaneous house-bank/USB operation is not a required operating mode.
- Three manually assembled boards; paste and hot air/hot plate are available.
  All exact BOM parts must be available from DigiKey in the required quantities.
  On 2026-09-19 the owner clarified that the published BOM must be **per board**;
  the owner applies ordering multiples. Never embed the planned batch count in it.
- Direct-entry screw output terminals; upstream main fusing, no onboard MIDI fuse.
- Power may be applied with a **mixture of AUTO and BYPASS fuse positions**.
  Unloaded startup is not an allowed design assumption. Review startup and
  automatic recovery with connected loads, including MOSFET linear-mode SOA;
  parallel MOSFETs must not be assumed to share startup current equally.
  Fuse positions are changed only with battery power disconnected, never live.
- On 2026-09-19 the owner explicitly accepted **latch-off at a lower startup
  load while retaining the 40 A continuous target**. Successful full-40-A BYPASS
  startup is not required. Select and document the lower startup envelope; do
  not weaken fault protection to force full-load startup.
- On 2026-09-19, after reviewing branch/input protection coordination, the owner
  selected: **"Isolate the faulty channel so healthy outputs keep operating."**
  This supersedes accepting whole-board latch-off as the response to an output
  short. It applies to both AUTO and BYPASS; the ESP32 and healthy outputs must
  remain operating. Protection must work without firmware, including during
  MCU reset. See [channel isolation review](channel-isolation-review.md).
- The earlier acceptance of lower-load startup does not authorize one shorted
  branch to prevent otherwise admissible healthy loads from starting. Include
  a short present at power-up as well as a short applied during operation.
- Retain hardware latch-off/no automatic retry as the fault-response design
  basis, now local to the faulty branch. A genuine shared-input fault or
  excessive aggregate healthy startup load can still require a common shutdown;
  ordinary single-output shorts must not be reclassified as shared-input faults.
  No reliance on ESP32 firmware to enforce protection or retain a fault latch.

## Deliberately outside this review's supplied inputs

The owner asked not to pursue battery chemistry/model, charger/settings, upstream
fuse/feeder details, enclosure/location or mechanical restrictions. These remain
**unknown**, not verified safe. Do not silently infer battery fault current,
transient amplitude/energy, ambient temperature or available cooling. Board-level
corrections can proceed without treating installation qualification as complete.
On 2026-09-15 the owner authorized enlarging the PCB for electrical reliability,
selecting a fabrication service with heavier copper, and initially designing for 9–16 V
operation with reverse-polarity blocking and overvoltage disconnection around
17 V. The lower operating limit is now 9.5 V as recorded above. Higher-voltage
charging/equalization is allowed to disconnect the outputs.

The earlier request to defer hardware testing referred to the **host PC freeze
investigation**, not PCB validation. Prototype bring-up and thermal/load testing
remain necessary before assigning a measured continuous-current or marine-service
rating. Ordering prototype bare boards precedes those tests.

## Pump and relay boundary

Short run time reduces average heating but does not remove startup/stall current
or inductive turn-off stress. Do not raise fuse limits on that basis. A relay coil
also stores inductive energy; use suitable coil suppression (built-in or external)
and observe polarity where a diode is fitted. [TI inductive-load guidance](https://www.ti.com/document-viewer/lit/html/SLVAF04).

Direct pump use is not qualified, nor is this board approved as the sole automatic
bilge-pump or other safety-critical power/control path. Those are installation and
prototype-validation questions, not resolved by the owner's relay fallback.
