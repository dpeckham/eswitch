# Confirmed scope — 2026-09-15

- Nominal 12 V house-bank distribution; 40 A simultaneous continuous **target**.
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
- Direct-entry screw output terminals; upstream main fusing, no onboard MIDI fuse.

## Deliberately outside this review's supplied inputs

The owner asked not to pursue battery chemistry/model, charger/settings, upstream
fuse/feeder details, enclosure/location or mechanical restrictions. These remain
**unknown**, not verified safe. Do not silently infer battery fault current,
transient amplitude/energy, ambient temperature or available cooling. Board-level
corrections can proceed without treating installation qualification as complete.
The existing board outline is retained unless a necessary layout correction is
explicitly documented.

The owner has elected to perform physical-fit, thermal and load testing later.
That testing is deferred, not waived: it remains required before assigning a
continuous-current or marine-service rating and before using a board for a
safety-critical load.

## Pump and relay boundary

Short run time reduces average heating but does not remove startup/stall current
or inductive turn-off stress. Do not raise fuse limits on that basis. A relay coil
also stores inductive energy; use suitable coil suppression (built-in or external)
and observe polarity where a diode is fitted. [TI inductive-load guidance](https://www.ti.com/document-viewer/lit/html/SLVAF04).

Direct pump use is not qualified, nor is this board approved as the sole automatic
bilge-pump or other safety-critical power/control path. Those are installation and
prototype-validation questions, not resolved by the owner's relay fallback.
