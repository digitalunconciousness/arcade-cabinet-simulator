# Arcade Cabinet Fault Simulator — Project Plan v0.2

**Status:** Pre-feasibility, seeking technical review
**Date:** April 2026

## Executive summary

We want to build a software tool that simulates an entire arcade cabinet — PCB, power supply, monitor, controls, coin mech, lights, audio chain, wiring harness — and lets a user inject realistic faults anywhere in the system, then see those faults manifest as the actual cabinet would behave. Two use cases drive this: **diagnostic aid** (reproduce a fault we're seeing on a real cabinet to narrow down causes before pulling the cabinet apart) and **training mode** (random fault generator, user has to diagnose and locate the failure).

Initial target is **Centipede**, both because it's a relatively simple, well-documented cabinet and because we just refit the board and have fresh hands-on data to validate against. Long-term we want to be able to add more cabinets — at the end of this document there's a tier analysis of what other titles would cost to port, with **Area 51** as the marquee example of a much-harder-than-Centipede case.

The core architectural call is that we don't gate-level simulate the entire cabinet. We use full netlist-level simulation for the PCB (where the interesting logic lives) and **behavioral models with curated fault states** for the peripherals — PSU, monitor, trackball, coin mech, etc. The two layers communicate through a shared "cabinet bus" carrying power rails, signals, and mechanical events. This is the same mental model real techs already use: nobody traces individual transistors in a Wells-Gardner deflection chassis, they know the chassis-level fault categories and learn the symptom-to-cause mapping.

## Goals (v1)

- **One full cabinet (Centipede) playable end-to-end**, with fault injection on every major subsystem.
- **PCB**: gate-level netlist coverage of sync generator, address decoder, and main RAM region. Fault primitives stuck-at-0, stuck-at-1, pin-open, pin-to-pin short on instrumented pins. Bus-level fault injection on the 6502 and POKEY interfaces.
- **Peripherals**: behavioral models with documented fault states for power supply, CRT chassis, trackball, coin mech, buttons, marquee/bezel lights, audio amp/speaker, wiring harness.
- **UI**: cabinet-cutaway view with clickable subsystems, schematic view for the PCB, PCB-photo view for chip/pin-level faults, live probe view for waveforms.
- **Training mode**: random fault scenario generator with realism-weighted distribution, scoring/timing, hint and reveal system.

## Explicit non-goals (v1)

- Generic any-board support — every cabinet beyond Centipede is its own porting project (see scaling section).
- Full analog fault realism (resistive faults, intermittent thermal faults, capacitor degradation curves). Defer to v2 — get the digital story right first.
- Replacing 6502 or POKEY with gate-level netlist. They stay as MAME's existing functional models with fault injection at the bus interface.
- Reverse-engineering the Atari custom chips (motion object generator, playfield generator) into TTL netlists. Excellent long-term project, explicitly out of v1 scope.

---

## Architecture overview

Three layers, deliberately decoupled:

1. **Simulator core.** MAME built from source with our patch set: extended Centipede netlist coverage, the fault-injection device class, and the cabinet bus bridge. We track upstream MAME so we can rebase as the netlist library evolves.
2. **Cabinet bus + peripheral models.** A separate process (or in-MAME plugin, TBD) hosting the behavioral models for PSU, monitor, controls, etc. Connected to MAME via a structured message bus.
3. **UI + training orchestration.** Standalone web or Electron app. Renders cabinet/schematic/PCB views, manages fault scenarios, scores training sessions. Talks only to the bus — no direct MAME dependency.

Decoupling means UI iteration is fast (web stack), peripheral models can be added without touching MAME, and MAME stays close to upstream.

---

## The cabinet bus

The integration glue is a small message-passing layer carrying three classes of state:

- **Power rails** (AC mains, +5V, +12V, sometimes -5V). Each consumer reports its current draw; the PSU model supplies; voltages on each rail are computed from load and fault state. A faulting PSU with sagging +5V causes the PCB to misbehave in realistic brownout patterns *and* makes the trackball encoder unreliable, all from one fault.
- **Signal lines** (composite video and sync from PCB → monitor, audio from PCB → amp, control inputs from peripherals → PCB, coin pulses from coin mech → PCB). The harness sits in the middle and can fault any line.
- **Mechanical events** (coin drop, button press, trackball motion). Originate from the user UI and route to the appropriate peripheral, which generates the corresponding electrical signals.

Every peripheral and the PCB itself speak this bus. Fault propagation falls out naturally from the rail/signal/event abstraction — no special-case logic needed.

Implementation is most likely a JSON-over-TCP or msgpack-over-TCP server hosted Lua-side inside MAME, with the peripheral models running in a separate Python or Node process subscribing to the relevant signals. Final choice depends on Phase 1 performance characterization.

---

## Component 1: PCB simulator with fault injection

### The constraint

MAME's netlist topology is fixed at netlist-compile time — we can't dynamically rewire connections at runtime. So the design is **pre-instrumentation**: the netlist source is auto-modified at build time to insert a transparent "fault buffer" device on every pin we want to be able to break. The buffer is pass-through by default and adds minimal solver overhead. At runtime, the user flips a parameter on the buffer to change its behavior.

### The fault device (sketch)

This is approximately what the C++ looks like — actual MAME netlist code uses specific macros and conventions (`NETLIB_OBJECT`, `NETLIB_UPDATEI`, `NETLIB_RESET`), but the structure is faithful:

```cpp
// src/lib/netlist/devices/nld_fault_buffer.cpp

NETLIB_OBJECT(fault_buffer)
{
    NETLIB_CONSTRUCTOR(fault_buffer)
    , m_A(*this, "A")                  // input pin
    , m_Y(*this, "Y")                  // output pin
    , m_mode(*this, "MODE", 0)         // 0=normal, 1=stuck_hi, 2=stuck_lo, 3=open
    , m_power(*this, "VCC", "GND")
    {
        register_subalias("A", m_A);
        register_subalias("Y", m_Y);
    }

    NETLIB_UPDATEI()
    {
        switch (m_mode())
        {
            case MODE_NORMAL:     m_Y.push(m_A() ? 1 : 0, NLTIME_FROM_NS(1)); break;
            case MODE_STUCK_HIGH: m_Y.push(1, NLTIME_FROM_NS(1)); break;
            case MODE_STUCK_LOW:  m_Y.push(0, NLTIME_FROM_NS(1)); break;
            case MODE_OPEN:       m_Y.set_hiz(); break;
        }
    }

private:
    logic_input_t  m_A;
    logic_output_t m_Y;
    param_int_t    m_mode;
    nld_power_pins m_power;
};
```

For pin-to-pin shorts, a separate `FAULT_SHORT` device with two terminals normally hi-Z; when activated, connected through low resistance. Selectively placed only between physically adjacent pin pairs (read from KiCad PCB layout) to keep topology realistic.

### Auto-instrumentation

A Python preprocessor over the generated netlist `.cpp`:

1. Parse every `NET_C(net_name, device.pin, ...)` line.
2. For each instrumented pin, rename the original net, insert a `FAULT_BUFFER`, rewire so the original signal flows through the buffer.
3. Emit a JSON manifest mapping `(reference_designator, pin_number)` → `fault_device_name`. The UI uses the manifest to resolve clicks to fault targets.

Lives outside MAME's source so we don't touch upstream. Output is the modified `.cpp` plus a `.manifest.json`.

### Centipede coverage targets for v1

We don't netlist the whole board — three sub-circuits chosen for educational value, fault visibility, and self-containedness:

**Target A — Sync generator** (sheets 4-5). Pure TTL counter chain producing HSYNC, VSYNC, and timing signals. Built from 74161s and a few 74xx gates. Faults produce visually obvious symptoms — rolling pictures, torn frames, missing video. Effort: 2-4 weekends.

**Target B — Address decoder** (sheet 2). 74139/74138 decoders for ROM, RAM, POKEY, EAROM, video RAM chip-selects. Faults make specific subsystems inaccessible — corrupting playfield-RAM CS produces immediately recognizable graphics corruption. Effort: 2 weekends.

**Target C — Working RAM region** (sheet 3, the 2114 chips). RAMs, address mux, data bus buffers. Lets us simulate stuck data/address lines, dead RAM cells, bad bus buffers — by far the most common real-world fault category on these boards. Effort: 3-4 weekends including a "bad RAM cell" model that injects faults at storage-cell level.

### What stays as functional emulation

- 6502 CPU. Faults at its bus pins via fault buffers between the C++ CPU and the netlist.
- POKEY. Same approach.
- Atari custom motion-object and playfield generators. Same approach. Long-term reverse-engineering project, explicitly out of v1 scope.

---

## Component 2: Power supply

The PSU deserves real-ish electrical modeling because it's small enough to be tractable and because power faults cascade in interesting ways. Model it as: AC mains → transformer → bridge rectifier → filter caps → regulators → output rails.

Each stage has documented fault modes:
- **Bad bridge rectifier**: half-wave operation (massive ripple) or open (rail dies)
- **Dried filter cap**: AC ripple visible on DC rail, severity proportional to load
- **Failed regulator**: rail at incorrect voltage, dies under load, or shorts rail to higher rail (catastrophic)
- **Undervoltage from sagging mains**: all rails proportionally low
- **Overload trip**: rail collapses when consumer draw exceeds limit

Other consumers on the bus draw current from the rails; the PSU model computes resulting rail voltages. This is what makes "the PSU is dying" cascade believably across the rest of the cabinet.

This level of modeling is right for power because PSU faults are extremely common on old cabinets and the failure modes are well-understood. ~2 weekends of work, big diagnostic-value payoff.

---

## Component 3: CRT monitor

The biggest peripheral. A real Wells-Gardner 19K6100 chassis is several boards (PSU, deflection, video amp, HV) and gate-level modeling would be a project unto itself — and not particularly useful, because nobody troubleshoots a CRT chassis at the transistor level.

Approach: **chassis model with named fault categories**, each applying a visual transformation to MAME's framebuffer output. Most are achievable as shader effects in BGFX (which MAME already supports):

- **No HV** — dark screen, faint glow
- **Vertical collapse** — single bright horizontal line
- **Horizontal collapse** — single bright vertical line
- **Weak focus** — blurred picture, severity adjustable
- **Brightness drift** — overall level wandering
- **Color drift** (color monitors) — channel imbalance, missing color
- **Bad caps in deflection** — tearing, picture instability, geometry distortion
- **Dim picture** — cathode wear, contrast loss
- **Sync lock failure** — picture rolls or tears
- **Ringing/ghosting** — bandwidth issues in video amp

The chassis model also consumes from PSU rails (so a dying PSU dims/distorts the picture) and accepts video+sync from the PCB (so PCB sync faults break monitor lock). Both directions matter for realistic fault propagation.

Effort: 4-8 weekends. The shader work for the visual effects is the bulk of it.

---

## Component 4: Trackball (Centipede-specific)

A 4.5" Atari trackball is two optical encoders producing quadrature pulses on X and Y axes. Behavioral simulation is straightforward: position state from user mouse/trackball input, generate quadrature pulse pairs at rates appropriate to motion velocity.

Fault modes:
- **Dead opto** on one axis — that axis stops responding
- **Dirty roller** — intermittent pulses, jumpy/skipping cursor
- **Seized bearing** — input dampened, sluggish response
- **Failed quadrature phase** — cursor moves wrong direction (this one is *immediately* recognizable and a classic real-world fault)
- **Encoder PCB cap failure** — signal noise/bouncing

Trackball issues are some of the most common things you actually see on a working Centipede in the wild, so this is high-priority for training value. Effort: 1-2 weekends.

---

## Component 5: Coin mech, buttons, lights, audio, harness

Fast to summarize because they're individually simple but collectively important:

**Coin mech.** State machine: idle → coin detected → validation → accept/reject. Faults: stuck switch (free credits, very common!), dirty contact (intermittent acceptance), jammed mech (rejects valid coins), miscalibrated.

**Buttons.** Trivial state model. Faults: stuck closed, stuck open, intermittent, slow/sticky, contact bounce.

**Marquee + bezel lighting.** Fluorescent tube + ballast for the marquee. Faults: dead tube, bad ballast (slow start, flicker, hum), aging tube (dim, color shift). Button lamps if present even simpler.

**Audio chain** (amp + speaker). Fault categories: distortion (bad coupling cap), no audio (dead amp), hum (ground loop or filter cap), blown speaker (rasping/no output). The amp board could be netlisted someday but not v1.

**Wiring harness.** Connections between everything. Faults: open (broken wire — subsystem stops working), short (chafed insulation — usually catastrophic), high resistance (corroded molex pin — voltage drop, intermittent). The harness is the connective tissue that makes faults *propagate* between subsystems.

Combined effort: 3-5 weekends for all five.

---

## Component 6: Training mode

Once fault injection plumbing exists, this is mostly content authoring rather than engineering.

- **Fault scenario library** — JSON files describing scenarios. Each has the fault(s), difficulty rating, optional backstory ("customer reports the screen rolls intermittently when the cabinet warms up"), and the correct diagnosis path.
- **Realism-weighted random selection** — bad caps, RAM failures, dirty trackball rollers, and connector issues hit way more often than "chip E7 pin 7 stuck low," because that's what actually happens. Weighting derived from EE consultation and our own barcade fault history.
- **Diagnostic scoring** — track which probe points the user checks, in what order, time to diagnosis. Could feed into staff onboarding metrics.
- **Multi-fault scenarios** — most "broken" cabinets have 2-3 things wrong simultaneously. Learning to *not* stop after finding the first fault is itself a core skill, and easy to teach with composed scenarios.
- **Hint and reveal system** — after the user gives up or solves, show the fault tree and explain the chain of reasoning.

Initial library of ~20-30 scenarios is realistic for v1, growing organically afterwards.

---

## Component 7: UI

Web app served locally, talking to the cabinet bus over WebSocket. Four views:

- **Cabinet view** — 2D cutaway illustration of a Centipede upright cabinet. Click into the monitor chassis, PSU, harness routing, trackball assembly, coin door, etc. Each component gets its own fault-injection panel.
- **Schematic view** — KiCad schematic SVG export with clickable components for PCB-level faults.
- **PCB-photo view** — high-res photo of the actual Centipede PCB with hand-mapped clickable regions per chip and key trace. Source material from Sean Riddle's PCB scan archive plus our own scans of the freshly-refit board.
- **Probe view** — live waveform graphs from any selected net or rail, rendered with WebGL/Canvas.

Fault state is a list of active injections; users can save/load scenarios as JSON.

---

## Phasing and rough schedule

Evening/weekend pace, single developer with occasional EE consultation:

| Phase | Scope | Estimate |
|---|---|---|
| 0 | Build MAME from source, run Centipede, read existing Centipede netlist code, get comfortable with MAME's netlist runtime and Lua debugger | 2-3 weekends |
| 1 | `FAULT_BUFFER` device + auto-instrumentation preprocessor, prove on trivial test netlist | 3-4 weekends |
| 2 | Netlist sync generator (Target A), integrate, demo first end-to-end PCB fault | 3-4 weekends |
| 3 | Cabinet bus + control bridge (Lua TCP/JSON server), minimal UI: schematic view + fault inject + one probe | 4-6 weekends |
| 4 | Power supply model + simple peripherals (coin mech, buttons, lights, harness) | 6-8 weekends |
| 5 | Netlist address decoder + RAM region (Targets B, C) | 4-6 weekends |
| 6 | CRT monitor model + trackball + audio chain | 8-12 weekends |
| 7 | Cabinet view UI + PCB-photo view + scenario library + training mode + polish | 8-12 weekends |

**Total: ~12-18 months of evening time** to a polished, demo-able v1.

The phasing deliberately gets a working PCB-only demo by end of Phase 2 (~10 weeks in) and a usable cabinet simulation by end of Phase 4 (~6 months in). Anything past that is improving fidelity and adding training features. If we ever need to ship something earlier, there's a natural cutoff at every phase boundary.

---

## Scaling and portability — what about other cabinets?

Once the Centipede framework exists, what's the cost of adding another cabinet? It depends almost entirely on **what era the hardware is from**, because MAME's netlist library — and the entire idea of gate-level fault injection — has a hard ceiling around the late 1980s. After that, custom chips dominate and you can only fault at the bus interface.

I'd group cabinets into rough tiers:

### Tier 1 — Same era as Centipede (1979-1983 Atari and similar)

**Examples:** Asteroids, Tempest, Battlezone, Missile Command, Lunar Lander, Black Widow.

Architecture is very similar — 6502 (or 6502+vector generator on the vector games), TTL glue, custom audio. Schematic conventions are identical, parts library is mostly the same. Most of the framework Centipede needs *is* the framework these need.

**Estimated effort per title:** 2-4 months evening time after Centipede is done. Most of that is netlist authoring for the relevant sub-circuits and scenario library content. Vector games (Asteroids, Tempest) add the vector generator as a new sub-circuit but it's still pure TTL.

**Peripherals:** mostly familiar — different control schemes (rotary encoder for Tempest, twin sticks for Battlezone), same monitor classes, same PSU class, same coin/lights/audio. New peripheral models per cabinet but they're variations on existing ones.

### Tier 2 — Other 8-bit golden age (Pac-Man, Galaga, Donkey Kong, Defender)

Different CPU (Z80 mostly, 6809 for Defender), different custom chips, but MAME has good emulation for all of them. Schematic conventions less standardized than Atari but documentation is broadly available.

**Estimated effort per title:** 3-6 months. The CPU change isn't a real obstacle (MAME handles it; we just attach fault buffers to a different bus). The custom chips per title — Namco's video chips, Williams's blitter, Nintendo's 8257 — vary in how much is netlist-able. Some are pure TTL realizations and could be netlisted; some are LSI custom and stay functional.

**Peripherals:** monitor and PSU models mostly transfer (Williams uses different PSUs but same fault categories). Cocktail vs. upright cabinets need different cutaway art. Joystick + buttons mostly already covered.

### Tier 3 — JAMMA-era 80s/early-90s 2D (Street Fighter II, Final Fight, Sunset Riders)

Standardized JAMMA wiring is actually a big *win* for us — one harness model covers a huge range of cabinets. CPU is usually 68000 + Z80 sound CPU; both well-supported in MAME. Custom video/sprite chips are heavier (Capcom CPS-1, Sega System 16, etc.) and stay as functional models.

**Estimated effort per title:** 4-8 months. Less netlist coverage proportionally because more of the board is custom silicon; more emphasis on bus-interface faults and on RAM/ROM faults. The JAMMA harness model becomes high-leverage.

**Peripherals:** generic JAMMA cabinet model becomes its own asset. Most Tier-3 cabinets share the same monitor/PSU/coin classes with config-level differences.

### Tier 4 — Mid-90s 32-bit era (Area 51, Mortal Kombat 3, NBA Jam, Cruis'n USA)

This is where the gate-level approach largely breaks down, and Area 51 is the case in point.

**Area 51 / CoJag specifics:** CoJag uses a Motorola 68EC020 (or 33 MHz MIPS R3000 in later boards) plus the Atari Jaguar's "Tom" and "Jerry" custom chips, with 4 MB of RAM and a 64-bit ROM bus. Tom contains the GPU, Object Processor, Blitter, and DRAM controller; Jerry contains the DSP and audio DACs. These are *enormously* complex custom ASICs. There is no realistic path to gate-level netlisting them — the silicon is undocumented at that level and even if it weren't, the netlist solver couldn't run them at game speed.

What this means in practice: for Area 51, the PCB simulator stays almost entirely at MAME's existing functional emulation. Fault injection happens at:
- The CPU bus interface (data, address, control lines)
- The custom-chip bus interfaces (Tom, Jerry, hard drive controller)
- RAM chips at the chip-pin level (and these are common failure points — Area 51's built-in self-test specifically tests the DRAM banks and reports per-bank or per-bit failures, and a documented real-world failure case involves a bad solder joint on a GAL chip causing a missing /UCAS signal to one DRAM bank)
- ROM/HDD controller signals
- Power rails
- The lightgun interface

The cabinet-level simulation is where most of the value is for a CoJag cabinet. Most failures on these boards are: bad caps (everywhere — these boards are 30+ years old now), dead RAM (very common, and the self-test gives you a head start), failed Tom or Jerry (you can really only diagnose this at the bus level anyway — replacement is the only realistic repair), bad PSU, monitor problems, lightgun calibration and optical issues.

**The lightgun is its own modeling problem.** It uses a photodiode that detects the CRT scan, with timing relative to sync to determine where on the screen the gun is pointing. This means lightgun behavior is *coupled* to monitor behavior in ways that make the simulator interesting — a flickering monitor causes lightgun aiming problems, a misadjusted lightgun looks like a software bug, etc. Modeling this honestly requires the monitor model and lightgun model to actually exchange timing information. Doable, but it's new work that doesn't exist for Centipede.

**Estimated effort for Area 51:** 6-12 months on top of having Centipede done. Less netlist coverage but more bus-level fault scaffolding, much more elaborate self-test integration (the existing CoJag self-test is a goldmine for training scenarios — we should hook into it directly), new lightgun model with monitor coupling, HDD model, and the cabinet itself is different (sit-down or upright with two guns, different monitor, different PSU class). Realistic-fault content authoring is also significantly bigger because there are more failure modes.

### Tier 5 — Late 90s+ 3D era (Sega Naomi, Namco System 23, Cruis'n World successors)

Currently infeasible for our approach, and probably for any approach in the foreseeable future. These are essentially gaming PCs with custom GPUs — the level of custom silicon is overwhelming and MAME's functional emulation is already pushing limits. Fault simulation at the bus level might be possible eventually but it's genuinely a different project. Out of scope.

### What this means strategically

The framework we build for Centipede gives us **most** of the leverage for Tier 1 titles, **most** of the cabinet-level leverage for Tier 2-3 titles, and **the cabinet-level leverage but not much more** for Tier 4 titles. So:

- Centipede first (we have hands-on data and the era is forgiving).
- After Centipede works, the cheap wins are Tier 1 (Asteroids, Tempest, Missile Command). Each is months not years.
- Area 51 is a great second-era target *because* it stresses the framework in different ways — proves the cabinet-level architecture, exercises the bus-level fault injection (which Centipede uses minimally), forces us to model lightgun-monitor coupling. But it's a much bigger project than another Tier 1 cabinet.

If the goal is **maximum diagnostic-tool value at the barcade**, the strategic order is probably: Centipede → tighten the framework → next-most-broken-cabinet-on-our-floor → then expand by era.

If the goal is **demonstrating the system's range**, jumping from Centipede to Area 51 is the right move: it proves the architecture handles a wildly different era and creates a great pair of demos.

---

## Specific questions for technical review

1. **Fault model coverage on the digital side.** Are stuck-at + open + short the right primitives for PCB-level faults, or are we missing common failure modes (open-collector glitches, slow rise/fall, transient/temperature-dependent faults)?
2. **Realism of clean digital faults.** Will technicians who train on the simulator and then work on real boards find the symptoms recognizable, or will the lack of analog imperfection make it feel artificial?
3. **PSU modeling depth.** Is the rectifier→filter→regulator→rails model sufficient, or do we need actual transient response (inrush, transformer saturation, regulator dropout dynamics)? Where is the diminishing-returns line?
4. **CRT fault categories.** Are the named monitor failure modes the right list? What's missing from the Wells-Gardner-19K6100-failure-mode-spotter's-guide perspective?
5. **Most-common-fault prioritization.** What's the actual distribution of failure modes you see on 40-year-old arcade cabinets? My intuition is bad caps (especially in PSU and monitor) + dead RAM cells + connector/harness issues + control wear dominate, with chip-pin faults much rarer. Should those weight the v1 scenario library?
6. **Lightgun modeling (looking ahead to Area 51).** How honest do we need to be about the photodiode/sync coupling for the simulation to be useful, vs. modeling the lightgun as an idealized pointing device with categorical faults?
7. **Hardware corners I'm ignoring.** Single most obvious thing that's missing from this plan?

---

## References

- MAME source: `github.com/mamedev/mame`, especially `src/lib/netlist/`
- MAME-KiCad bridge: `github.com/mamedev/discrete`
- Centipede service manual: Internet Archive
- Atari CoJag service docs and Raymond Jett's CoJag troubleshooting guide (PLD Archive wiki) for Area 51 reference
- Sean Riddle's PCB scan archive (high-res board photos)
- Wells-Gardner monitor service literature for chassis fault categories
