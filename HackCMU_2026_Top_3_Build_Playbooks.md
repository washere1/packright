# HackCMU 2026: Top Three Hardware Build Playbooks

This brief expands **K2 FaultFinder**, **PackRight**, and **PowerPatch** into credible sub-24-hour projects. The estimates assume four people working in parallel, access to ordinary lab parts, and aggressive scope control.

## Quick comparison

| | K2 FaultFinder | PackRight | PowerPatch |
|---|---|---|---|
| Primary track | IFM | Travelling | Optimization |
| One-line pitch | A physical electronics trainer that diagnoses hidden faults by choosing and executing safe measurements | A suitcase that measures how it is packed and physically guides a better arrangement | A miniature grid that optimally allocates scarce energy among real loads |
| Main user | Repair technician, student, field engineer | Traveler, especially with strict baggage limits or mobility constraints | Facility or microgrid operator |
| Core problem | Troubleshooting is sequential, manual-heavy, and prone to unnecessary or unsafe tests | A scale reports total weight only after packing; it does not help decide what to move or remove | Renewable supply and demand vary, while not every load is equally important |
| Best judge moment | Judge inserts a secret fault; the board requests measurements and locates it | Judge drops a mystery object into one corner; the suitcase identifies the imbalance and guides a correction | Judge shadows the “solar” source; power visibly reroutes and critical loads stay on |
| MVP completion likelihood | 70–80% | 85–90% | 80–85% |
| Polished stretch version | 40–50% | 55–65% | 55–65% |
| Biggest risk | Model latency/reliability | Load-cell mechanics/calibration | Power electronics and excessive energy-system scope |
| Best strategic reason | Highest sponsor relevance and originality | Clearest usefulness and lowest execution risk | Strongest physical spectacle plus serious optimization |

The completion estimates are judgment calls, not measured probabilities. They describe a narrowly scoped version, not every feature below.

---

# 1. K2 FaultFinder

## The problem

Diagnosing hardware is an information-gathering problem. A technician sees a symptom, consults a schematic or manual, chooses a test point, takes a measurement, updates the possible causes, and repeats. Three things make that difficult:

1. Manuals contain relevant limits and procedures, but the information is scattered through prose and diagrams.
2. An unnecessary test wastes time; an unsafe test can damage equipment.
3. General-purpose assistants tend to guess from the symptom rather than grounding their conclusion in live measurements.

**K2 FaultFinder is a small instrumented device with real, switchable faults.** K2 reads the device documentation and the accumulated measurement history, then chooses the next allowable diagnostic tool. Firmware performs the measurement, returns structured telemetry, and a deterministic safety layer prevents invalid actions. The system stops only when it can name a fault and verify the repaired state.

This is not “ChatGPT for electronics.” It is a constrained, physical diagnostic agent whose reasoning is tested against hidden ground truth.

## The best weekend device

Use one simple signal chain that is rich enough to support distinct failure modes:

```text
Light/temperature sensor → analog divider → microcontroller → MOSFET → fan or LED load
        TP1                    TP2              TP3          TP4
```

Add a labeled fault bank hidden behind a cover:

- F1: sensor disconnected;
- F2: sensor divider shorted or wrong resistance;
- F3: controller output stuck low;
- F4: MOSFET gate disconnected;
- F5: load disconnected or jammed/high-current;
- F6: supply droop introduced through a series resistance.

Five well-separated faults are better than twelve ambiguous ones. Keep every signal at 3.3 V or 5 V.

### Recommended hardware

- ESP32, Arduino, or RP2040 telemetry controller;
- INA219/INA260 for branch current and supply voltage;
- MCU ADC or ADS1115 for test-point voltages;
- analog multiplexer such as 74HC4051 if several points share one ADC;
- DIP switches or relays for fault injection;
- addressable LEDs placed beside labeled test points;
- small fan, motor, or high-brightness LED as the visible load;
- a laptop running the orchestration layer and K2 endpoint;
- a prominent physical **RESET / SAFE** button.

Do not build a moving robotic probe for the MVP. LEDs can tell a user where a probe would go, while electronically multiplexed test points supply the actual measurement. A motorized probe is mechanically fragile and adds little to the diagnostic story.

## System architecture

```text
Hidden fault switch
        ↓
Physical circuit → MCU telemetry → validated tools → K2 Horizon
        ↑                                  ↓           ↓
 LED test-point map ← action validator ← requested test / diagnosis
```

Expose only a tiny tool vocabulary:

- `read_voltage(test_point)`
- `read_current(branch)`
- `set_safe_stimulus(level)`
- `query_manual(section)`
- `submit_diagnosis(fault_id, evidence)`

The action validator checks argument names, allowed ranges, maximum number of tests, and whether the requested test is read-only. K2 never receives a generic shell, never controls GPIO directly, and never sets PWM or relay states outside the fixed tool schema.

### What K2 contributes

K2 should do the part that a fixed solver handles poorly: combine the manual’s unstructured constraints with the symptom and measurement history, select a useful next tool, and produce a grounded diagnosis. The official K2 Horizon materials emphasize small/on-device models and tool use; the 3.7B model card provides a dedicated reasoning and tool-call parser. [IFM announcement](https://ifm.ai/k2/press-release/), [K2 Horizon technical overview](https://ifm.ai/blog/k2/), [K2 Horizon 3.7B model card](https://huggingface.co/IFM/K2-Horizon-3.7B).

Run a simple non-LLM baseline as well:

- **Checklist baseline:** always measure supply, sensor, controller output, gate, then load current.
- **K2 system:** choose tests adaptively from the evidence.

Report median measurements-to-correct-diagnosis across the five faults. This converts “the model sounded smart” into an actual experiment.

## Three-minute demo

### 0:00–0:20 — Establish the stakes

“When a machine fails, the symptom rarely tells you which component failed. Technicians lose time searching manuals and probing points that may be irrelevant or unsafe.”

Point to the working fan responding to the sensor.

### 0:20–0:40 — Let the judge create the failure

Hand a judge a covered rotary switch or set of labeled cards. They select one fault without telling the presenter. The fan stops or behaves incorrectly.

This matters: a judge-created input proves the demo is live and not a rehearsed animation.

### 0:40–1:40 — Show evidence-seeking, not conversation

The screen should display a compact diagnostic tree, not a chat window:

```text
Observed: fan off; sensor stimulus = 80%
Test 1: supply rail TP1 → 5.02 V ✓
Test 2: controller output TP3 → 3.28 V ✓
Test 3: load current → 0.00 A ✗
Hypothesis: open load path, 94% confidence
```

Each requested test point lights physically as the measurement occurs. A small timer and “tests used” counter remain visible.

### 1:40–2:15 — Diagnosis and repair

K2 submits the fault with evidence. The judge reveals or resets the fault switch. The system automatically reruns a verification measurement, and the fan starts.

### 2:15–2:45 — Quantitative payoff

Show a five-row evaluation:

- correct faults: 5/5;
- median tests: K2 2.4 versus checklist 5;
- unsafe actions executed: 0;
- median diagnostic time: measured value.

Only show numbers actually collected during the hackathon.

### 2:45–3:00 — Close

“K2 does not replace the meter or control the circuit. It decides what evidence to collect next, and every claim is verified against the physical system.”

## How to wow the judges

- **Give the judge the fault switch.** Unscripted selection is the strongest credibility signal.
- **Use a physical illuminated schematic.** Mount the board behind clear acrylic or on foam board; run LEDs along the signal path as tests occur.
- **Make uncertainty visible.** Possible causes should disappear from a five-card physical or on-screen fault tree as evidence arrives.
- **Show a counterfactual.** Include a toggle between “fixed checklist” and “adaptive K2.” The test-count difference demonstrates value.
- **Run locally if reliable.** An “internet disconnected” indicator would make the edge story memorable. IFM says the smaller Horizon models target on-device use and all models include quantization support. Local inference is a bonus, not worth sacrificing the live demo.
- **Have a failure-aware interface.** If a model response is invalid, display “rejected by safety validator” and retry. A visibly rejected unsafe/unknown action can actually strengthen the engineering story.

## Feasibility under 24 hours

### MVP: feasible, with disciplined boundaries

An MVP needs only three faults, three measurement tools, LEDs at test points, and one correct K2 tool-use loop. That is very achievable with a known-good example circuit.

### Suggested parallel schedule

| Wall-clock time | ECE | CS | Statistics/ML | STEM / demo lead |
|---|---|---|---|---|
| Hours 0–2 | Build normal circuit and fault bank | Prove one K2 request and parse one tool call | Define fault matrix and baseline | Draw physical schematic; source enclosure |
| Hours 2–6 | Add telemetry and test-point LEDs | Serial/API bridge and tool validator | Write expected readings per fault | Label board and make judge fault control |
| Hours 6–10 | Stabilize fault injection | Complete iterative tool loop | Run first fault trials and tune prompts | Build compact diagnostic display |
| Hours 10–15 | Add up to five faults | Logging, reset, timeouts | Collect baseline/K2 metrics | Script demo; recruit blind testers |
| Hours 15–20 | Electrical reliability | Offline/local path only if stable | Analyze results | Polish enclosure and visuals |
| Hours 20–24 | Freeze hardware; repair only | Freeze features; backup capture | Final numbers | Rehearse and trim to 2:40 |

### First-hour kill test

Can K2 reliably return one allowed structured tool call from a short prompt in an acceptable time? Test this before building the full agent. The 3.7B model’s official high-reasoning serving recommendations can imply a long response path; it is reasonable to infer that interactive latency may be a demo risk on weak local hardware. Use the sponsor’s fastest supported endpoint if local inference is not smooth.

### Cut these first

1. robotic probe;
2. schematic computer vision;
3. voice interface;
4. more than five faults;
5. automatic repair.

### Likely judge objection

**“Couldn’t a decision tree diagnose this toy circuit?”**

Answer honestly: yes, for a single fixed board. The contribution is the guarded interface between an open reasoning model, unstructured service knowledge, and physical measurement tools. Demonstrate some transfer by changing a threshold or component note in the manual without rewriting the diagnostic tree. The fixed checklist is the baseline, not something to hide.

---

# 2. PackRight

## The problem

Travelers discover that luggage is overweight at the worst time: after packing or at the check-in counter. A normal scale gives only a total. It does not answer:

- Which low-priority item should be removed?
- Where should a heavy item move so a wheeled bag is less awkward or tip-prone?
- Is one side carrying most of the load?
- Can a fragile or must-keep item remain while the weight limit changes?

**PackRight is an instrumented suitcase platform that measures total weight and two-dimensional center of mass, recognizes a small set of tagged items, solves a constrained repacking problem, and guides the traveler with lights mounted inside the bag.**

The strongest version is not “computer vision that recognizes your clothes.” It is a reliable physical measurement system with a clear optimization objective.

## The best weekend device

Build an open suitcase or a suitcase-shaped tray with four load cells, one beneath each corner. Divide the interior into four or six illuminated zones. Use 5–8 demo objects with colored AprilTags, NFC stickers, or manually entered priorities:

- medicine: must keep;
- laptop: must keep and fragile;
- charger: high value;
- water bottle: heavy and movable;
- shoes: low priority;
- book: medium priority.

The system observes the change in the four corner forces when an item is added. From static equilibrium it estimates total weight and center of mass:

```text
W = F_FL + F_FR + F_RL + F_RR
x ≈ width × (F_FR + F_RR) / W
y ≈ length × (F_RL + F_RR) / W
```

It then minimizes a weighted objective such as:

```text
overweight penalty
+ distance of center of mass from target
+ fragile-placement violations
+ removal cost based on user priority
```

### Recommended hardware

- four single-point load cells or four small platform scales;
- one HX711 per independent load cell, or a multichannel ADC designed for strain gauges;
- ESP32/Arduino collecting forces at 10–20 Hz;
- addressable LED strips defining quadrants or target zones;
- physical dial/buttons for airline limit and trip mode;
- rigid top plate and mechanically isolated feet;
- optional overhead webcam for AprilTags;
- 5–8 attractive weighted demo blocks with clear travel-item labels.

Rigidity matters more than sensor sophistication. If the top plate flexes or touches the enclosure, calibration will drift.

## System architecture

```text
Four corner forces ──→ weight + center-of-mass estimate ──→ optimizer
Tagged item metadata ───────────────────────────────────────→ optimizer
Trip constraints ───────────────────────────────────────────→ optimizer
                                                             ↓
                                                  LED move/remove guidance
```

### MVP versus stretch

**MVP:** measure weight and center of mass; judge changes the limit; system indicates the heaviest/lowest-priority tagged item to remove and a target quadrant for rebalancing.

**Stretch:** overhead AprilTags provide exact item identity and position; a geometric solver enforces non-overlap and fragile zones. Do not promise general 3D packing.

## Three-minute demo

### 0:00–0:20 — Establish the problem

“A luggage scale tells you that you failed. PackRight tells you what to do next.”

Show the suitcase with four green quadrant lights.

### 0:20–0:50 — Create a bad pack

Place the laptop and essentials, then put a heavy water bottle in one far corner. The physical balance map turns red on that side; a center-of-mass dot moves visibly. Show total weight and a simple tip/handle-torque proxy.

### 0:50–1:30 — Let the judge perturb it

Ask a judge to add a mystery weighted object anywhere. Do not tell the system the position. The corner sensors detect the weight and approximate location. The corresponding physical quadrant pulses red.

### 1:30–2:05 — Change the real travel constraint

Turn a physical “baggage limit” dial from, for example, 20 to 15 pounds. PackRight identifies the lowest-cost removable item while preserving medicine and laptop. The item’s tag/zone lights amber.

### 2:05–2:30 — Guided physical correction

Remove the suggested item and move the bottle into the green target zone. The LEDs sweep toward the target; the entire border turns green when weight and balance constraints pass.

### 2:30–2:50 — Evidence

Display:

- weight error after calibration;
- center-of-mass error from a few known placements;
- before/after imbalance or estimated handle torque;
- constraints satisfied: 4/4.

### 2:50–3:00 — Close

“PackRight turns a passive container into an instrument that measures, optimizes, and guides—before the traveler reaches the airport.”

## How to wow the judges

- **Make the suitcase itself the display.** Interior LEDs should point to the item and destination; avoid requiring judges to watch a laptop.
- **Let a judge place the mystery weight.** The system should infer its quadrant from force changes in real time.
- **Use an old-fashioned physical limit dial.** It makes the constraint change obvious and gives the optimizer a theatrical trigger.
- **Build beautiful demo objects.** Uniform labeled blocks make the computation intelligible and the video polished.
- **Show force vectors.** Four vertical LED bars at the corners can visualize real load distribution.
- **Add one accessibility angle carefully.** Better balance can reduce awkward rolling/lifting, but do not make unsupported medical claims.
- **Use a visible baseline.** A cheap hanging scale answers only “17.2 lb”; PackRight answers “remove the shoes, then move the bottle here.”

## Feasibility under 24 hours

### MVP: the safest of the three

With a rigid tray and four working sensor channels, the full demo can be completed without vision. The optimization can initially operate on six known blocks and four target zones.

### Suggested parallel schedule

| Wall-clock time | ECE | CS | Statistics/ML | STEM / demo lead |
|---|---|---|---|---|
| Hours 0–2 | Mount one load cell and read stable values | Set up serial stream and live plot | Define objective and constraints | Select suitcase/tray and design zones |
| Hours 2–6 | Mount all four cells; calibrate | Implement device protocol and LEDs | Implement CoM equations and optimizer | Build/tag weighted demo items |
| Hours 6–10 | Filter drift and corner cross-talk | Integrate live guidance | Validate with known weights/positions | Finish physical layout and labels |
| Hours 10–15 | Add limit dial/buttons | Add item metadata and reset | Measure weight/CoM error; tune objective | Write demo and run user tests |
| Hours 15–20 | Hardware strain test | AprilTags only if MVP is frozen | Produce final evaluation | Enclosure and visual polish |
| Hours 20–24 | Freeze hardware | Freeze features; backup capture | Final numbers | Rehearse with judge perturbations |

### First-hour kill test

Put one known weight at three locations. Can the system distinguish left/right and front/back consistently? If not, fix the mechanics before touching the optimizer.

### Cut these first

1. full clothing/object recognition;
2. a ToF pressure/height map;
3. arbitrary 3D bin packing;
4. mobile application;
5. motorized rearrangement.

### Likely judge objection

**“Why not just use a luggage scale?”**

Perform the answer. A scale detects only total weight; it cannot identify imbalance, respect item priorities, or give an actionable repacking plan after the airline limit changes. The demo must feature all three distinctions.

---

# 3. PowerPatch

## The problem

Small grids, emergency shelters, remote systems, and even buildings with backup power face the same constraint: supply changes while loads have unequal importance. A refrigerator, radio, pump, and comfort light should not be treated identically. Naive control either overloads the source, drains storage too early, or shuts off more service than necessary.

**PowerPatch is a safe low-voltage miniature grid with real sources, measured loads, storage state, and physical priority controls. An optimizer schedules which devices receive power and when, then the board visibly reroutes energy after a disturbance.**

The problem being solved is not merely switching LEDs. It is constrained resource allocation over time:

- limited and varying source power;
- critical versus deferrable loads;
- minimum on/off durations;
- finite stored energy;
- user-selected priorities;
- optional inrush or peak-power limits.

## The best weekend device

Use a 5 V or 12 V protected supply and four recognizable load modules:

- **medicine refrigerator:** blue LED plus fan, high priority and continuous-service requirement;
- **water pump:** small pump/fan, important but schedulable;
- **emergency radio:** speaker or LED radio prop, medium continuous demand;
- **comfort lighting:** bright LED strip, lowest priority and dimmable.

The “solar” source may be a small panel under a lamp, but a physical source-capacity slider or selectable resistor bank is a more reliable demo disturbance. The system must measure actual branch current even if the available budget is emulated.

### Recommended hardware

- ESP32/Arduino as real-time controller;
- protected 5 V or 12 V DC supply;
- INA219/INA260 sensors for source and important branches;
- logic-level MOSFET modules for each load;
- small fans, LEDs, buzzer/speaker, or miniature pump;
- potentiometers or rotary switches for supply and priority;
- commercial USB power bank or supercapacitor only as a stretch storage source;
- addressable LEDs laid out as animated power-flow lines;
- laptop for optimization and telemetry, with a rule-based controller fallback.

Avoid homemade lithium charging. A commercial protected pack can be treated as a source; otherwise simulate state of charge and focus on measured allocation among loads.

## Technical core

At every planning interval, select load states `u[i,t]` and storage power `b[t]` to maximize weighted service:

```text
maximize Σ priority[i] × service[i,t]
         − switching penalty
         − unmet critical-demand penalty

subject to:
Σ load_power[i] × u[i,t] ≤ available_source[t] + battery_discharge[t]
state_of_charge[t+1] = state_of_charge[t] + charge[t] − discharge[t]
minimum on/off times
critical-load service constraints
```

This can be a small mixed-integer program, dynamic program, or exhaustive search over four binary loads. Use the simplest method that always solves in under a second. The impressive part is measured closed-loop execution, not the solver brand.

### Baseline

Compare the optimizer with one naive rule:

- first-come/first-served;
- fixed-priority greedy; or
- keep every load on until the source collapses.

Use a physical **BASELINE / OPTIMIZED** switch. Run the same disturbance in both modes and compare critical-service time or overload events.

## Three-minute demo

### 0:00–0:20 — Establish the scenario

“This shelter has solar power, limited storage, and four loads. If the sun disappears, which services survive—and for how long?”

All four modules are active. Animated LEDs show energy moving from source to loads.

### 0:20–0:45 — Explain the constraints physically

Point to the refrigerator, pump, radio, and comfort light. Show their measured watts on small labels or meters. The priority knobs are physical and understandable.

### 0:45–1:25 — Create the disturbance

Let a judge cover the solar panel or turn the source knob from 8 W to 4 W. The power-flow LEDs slow. The comfort light dims or turns off, the pump becomes intermittent, and the critical refrigerator remains on. Storage LEDs show a controlled discharge.

### 1:25–1:55 — Change the objective

The judge turns the radio priority above the pump because an emergency message is expected. The optimizer replans; the physical energy route changes within seconds.

### 1:55–2:30 — Show the baseline counterfactual

Flip to baseline mode and replay the same recorded or live source profile. The source overload indicator trips, or critical-service minutes drop. Flip back to optimized mode and recover.

### 2:30–2:50 — Evidence

Show only two metrics:

- critical demand served, optimized versus baseline;
- energy wasted or overload events.

### 2:50–3:00 — Close

“PowerPatch turns a changing energy budget into the most useful possible physical service—and makes every tradeoff inspectable.”

## How to wow the judges

- **Build an illuminated one-line diagram.** Put the source, storage, bus, and loads on a black or clear acrylic panel. Addressable LEDs should animate power direction and magnitude.
- **Use recognizable loads.** Four anonymous LEDs feel like a class project; a tiny fan-backed fridge, pump wheel, radio, and room light create a miniature world.
- **Let a judge cause the outage and change priority.** Two independent live perturbations prove optimization rather than scripting.
- **Make conservation visible.** Branch wattages should approximately sum to measured source/storage power. That signals real instrumentation.
- **Show baseline and optimized behavior on the same hardware.** This is more convincing than a bar chart alone.
- **Give the grid a clock.** A small “minutes of critical service remaining” counter makes finite storage immediately meaningful.
- **Use sound sparingly.** A brief overload click/alarm in baseline mode creates contrast; optimized mode should remain calm.

## Feasibility under 24 hours

### MVP: highly feasible without a real battery charger

Four MOSFET-switched loads, one measured source, a source-capacity knob, and an exhaustive-search optimizer are enough. Real storage improves the story but is not necessary if the UI clearly labels simulated state of charge. Never imply simulated energy is measured.

### Suggested parallel schedule

| Wall-clock time | ECE | CS | Statistics/ML | STEM / demo lead |
|---|---|---|---|---|
| Hours 0–2 | Switch one load safely and measure current | Establish serial commands/telemetry | Define loads, constraints, and baseline | Design miniature grid layout and scenario |
| Hours 2–6 | Build four protected load channels | Implement controller state machine | Build optimizer on fixed inputs | Construct recognizable load props |
| Hours 6–10 | Add source/priority knobs and sensors | Integrate plan execution and LEDs | Add horizon/storage state; test edge cases | Assemble illuminated one-line diagram |
| Hours 10–15 | Thermal/current reliability test | Baseline switch, logging, recovery | Collect repeated baseline comparisons | Write/rehearse disturbance demo |
| Hours 15–20 | Add real panel/storage only if stable | Polish local UI | Final metrics and plots | Finish labels and enclosure |
| Hours 20–24 | Freeze hardware | Freeze features; backup capture | Verify numbers | Rehearse and stress-test resets |

### First-hour kill test

Can one real load be switched while its current measurement changes correctly and the telemetry reaches the optimizer? If the answer is no, simplify voltage, sensors, or drivers immediately.

### Cut these first

1. homemade battery management;
2. real maximum-power-point tracking;
3. AC mains of any kind;
4. weather forecasting;
5. cloud dashboard;
6. more than four loads.

### Likely judge objection

**“Isn’t this just turning off the least important light?”**

The demo must include a temporal constraint that greedy priority handles badly. For example, the pump must run two consecutive intervals to complete a water cycle, while the refrigerator cannot remain off for more than one interval. With limited stored energy and a changing supply forecast, the optimizer decides *when* to serve each load, not just which priority number is largest.

---

# Recommendation and selection rule

Choose based on what the team can prove in the first two hours:

## Choose K2 FaultFinder if

- the K2 endpoint returns valid tool calls with tolerable latency;
- someone can build and debug a small circuit confidently;
- the team wants the highest originality and IFM-track alignment;
- the team is willing to evaluate the model instead of merely showcasing it.

## Choose PackRight if

- the load cells produce stable, position-sensitive readings;
- the team wants the highest probability of a finished, useful artifact;
- mechanical fabrication and visual polish are available;
- a clear travel story matters more than sponsor alignment.

## Choose PowerPatch if

- the team has current sensors, MOSFET modules, and safe DC loads;
- it wants the strongest table-side spectacle;
- the statistics/ML member is comfortable formulating a small scheduling problem;
- the ECE member can keep the power system simple and robust.

## Final ranking under a strict 24-hour deadline

1. **PackRight** — best completion probability and simplest three-minute story.
2. **K2 FaultFinder** — best winning upside, provided the model/tool loop works immediately.
3. **PowerPatch** — excellent visual and technical project, but physical presentation requires more fabrication.

If the team has access to a clean electronics bench and reliable K2 service, swap the first two. If load cells or K2 inference are unavailable, PowerPatch becomes the best choice.
