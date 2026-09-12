# HackCMU 2026: Hardware-First Track Brief

**Tracks:** Optimization, Food, Travelling, Multiplayer, and IFM / K2 Horizon  
**Team:** ECE + CS + Statistics/ML + related STEM  
**Design constraint:** The physical system must be indispensable. Software should sense, estimate, optimize, coordinate, or control—not merely wrap a generic AI interface.

## Executive recommendation

The five strongest concepts, balancing originality, technical depth, usefulness, relevance, and a three-minute demo, are:

1. **K2 FaultFinder Bench (IFM):** an instrumented electronics board with switchable faults; K2 Horizon chooses the next safe measurement from a schematic and live telemetry while a deterministic layer executes or guides it.
2. **PackRight (Travelling):** an instrumented suitcase that solves a live weight-distribution and packing problem, then guides physical repacking with LEDs.
3. **PowerPatch (Optimization):** a tabletop DC microgrid that visibly reallocates scarce power when supply, demand, or priority changes.
4. **Circuit Heist (Multiplayer):** a distributed cooperative puzzle whose physical controllers and rules reconfigure based on synchronized player actions.
5. **FreshSort (Food):** a multisensor produce-freshness station with a real mechanical sorting gate and an honest uncertainty estimate.

**Best overall bet:** K2 FaultFinder Bench if the team can run K2 reliably by the first evening. It makes the sponsor technology necessary without turning the project into a chatbot.  
**Best low-risk bet:** PackRight. Its physical transformation is immediate, the optimization is legible, and the whole demo fits on one table.  
**Best spectacle-to-risk ratio:** PowerPatch or Circuit Heist.

## How the concepts were filtered

Past HackCMU standouts repeatedly combined a narrow real problem, an unusual input or physical interface, inspectable computation, and a transformation judges could understand immediately. These concepts therefore require:

- at least one meaningful sensor and one meaningful actuator or physical output;
- a technical kernel that is not just calling a model API;
- a visible before/after or disturbance/recovery moment;
- one measurable result, such as error, latency, power served, waste diverted, balance, or synchronization;
- a complete demo path that survives without internet access where practical.

Scores below are directional, from 1–5. **Build risk** assumes roughly a weekend and ordinary hackathon hardware.

---

## Track 1: Optimization

### 1. PowerPatch — a microgrid in a box

Build a safe, low-voltage tabletop grid with two sources, a battery or supercapacitor, and several loads representing a clinic, refrigerator, and nonessential device. The controller continually decides which loads to serve, when to charge, and how to respond to a supply failure.

- **Hardware:** ESP32 or similar MCU, current/voltage sensors, MOSFET or relay-switched LED/fan/heater loads, small solar panel or variable bench supply, battery/supercapacitor, physical priority knobs.
- **Technical core:** receding-horizon control or mixed-integer optimization under source, storage, and priority constraints; deterministic power-control firmware; live telemetry and energy accounting.
- **Three-minute demo:** show all loads running; cover the solar panel or disconnect a source; the optimizer sheds a low-priority load, protects the critical load, and restores service when capacity returns. Then a judge changes a priority knob and sees a different optimal allocation.
- **Why it scores:** the optimization is physically visible, the constraints are real, and the result maps cleanly to resilient energy systems.
- **Evidence to display:** percent of critical demand served, energy lost, and the baseline-versus-optimized result.
- **Scores:** originality 4, difficulty 5, demo 5, usefulness 5, relevance 5. **Risk:** medium.

### 2. FlowSort — adaptive physical routing

Create a miniature conveyor or gravity-fed sorter that routes tagged objects to bins while priorities and bin capacity change. Instead of classifying objects and stopping there, the system solves the online routing and scheduling problem and actuates the route.

- **Hardware:** small belt or chute, photoelectric/ToF sensors, color or RFID reader, load cells or bin sensors, servo gates, emergency-stop button.
- **Technical core:** online min-cost flow, job-shop scheduling, or constrained queueing; state estimation for object positions; embedded timing and fault recovery.
- **Three-minute demo:** send several objects with different deadlines through the system; block a bin or announce a rush item; gates reroute the queue while a live counter shows improved throughput or lateness.
- **Why it scores:** it resembles a real logistics/manufacturing cell, and the solver’s decisions become motion rather than a graph.
- **Scope guardrail:** use one belt, two gates, and three destinations. Reliable timing is more impressive than a sprawling mechanism.
- **Scores:** originality 4, difficulty 5, demo 5, usefulness 5, relevance 5. **Risk:** medium.

### 3. QuietShape — self-tuning acoustic space

Build a small acoustic enclosure with motorized panels or shutters. A microphone array measures the sound field; an optimizer changes panel angles or apertures to reduce reverberation or noise at a chosen seat while preserving sound elsewhere.

- **Hardware:** 2–4 microphones, speaker, stepper/servo-driven panels, enclosure, optional LEDs showing the target zone.
- **Technical core:** impulse-response measurement, signal processing, a constrained black-box optimizer, and motor control with repeatable geometry.
- **Three-minute demo:** play a sharp click or test signal, show the baseline decay/noise, select a seat, and watch the enclosure physically reconfigure. Replay the signal and show the measured improvement.
- **Why it scores:** it crosses acoustics, controls, and statistics; the before/after is both audible and numerical.
- **Scope guardrail:** optimize one metric at two listening positions. Do not attempt general room acoustics.
- **Scores:** originality 5, difficulty 5, demo 5, usefulness 4, relevance 5. **Risk:** medium-high.

---

## Track 2: Food

### 1. FreshSort — uncertainty-aware produce triage

Build a station for exactly one food—such as bananas, avocados, or bread—that combines weight, color, temperature/humidity, firmness, or volatile-gas proxies and then physically sorts items into “use now,” “later,” or “inspect.”

- **Hardware:** camera, load cell, temperature/humidity sensor, optional VOC sensor, small compression/force probe, servo chute or rotating platform.
- **Technical core:** sensor calibration, feature fusion, a small interpretable statistical model, uncertainty estimation, and motor sequencing.
- **Three-minute demo:** process visibly different samples; show the sensor trace and confidence; let the sorter route them. Introduce an ambiguous sample and demonstrate that it chooses “inspect” instead of pretending certainty.
- **Why it scores:** it addresses food waste, uses ML only where measurements justify it, and ends with an unmistakable physical action.
- **Scientific honesty:** call the output a freshness or ripeness proxy—not a guarantee of safety. Use a very narrow food category and collect a small labeled calibration set.
- **Scores:** originality 4, difficulty 4, demo 5, usefulness 5, relevance 5. **Risk:** medium.

### 2. FlavorForge — a physical preference optimizer

Create a micro-dosing machine that mixes three safe flavor dimensions—such as sweet, sour, and salty colored water—then learns a person’s preference from pairwise choices. The point is closed-loop experimental design, not recipe generation.

- **Hardware:** three peristaltic pumps or gravity-fed servo valves, cup/scale, buttons or rotary encoder, rinse path, transparent tubing and LEDs.
- **Technical core:** Bayesian preference learning or a contextual bandit, dose calibration, closed-loop dispensing, and constraints on total concentration.
- **Three-minute demo:** the judge compares two tiny mixes twice; the system predicts and dispenses a third formulation closer to the learned preference. The UI shows the preference surface and uncertainty shrinking.
- **Why it scores:** statistical ML is central but grounded in a tactile food experience; pumps and calibration make it a real instrument.
- **Scope guardrail:** use food-safe ingredients only if consumption is planned; otherwise demo with colored water and frame it as a prototype for beverage formulation.
- **Scores:** originality 5, difficulty 4, demo 5, usefulness 4, relevance 5. **Risk:** medium.

### 3. ThermoTote — split-temperature food transport

Build a lunch carrier with independently monitored hot and cold compartments. A limited energy budget is allocated between compartments to keep both within target bands during transport.

- **Hardware:** insulated two-zone enclosure, temperature sensors, fans, Peltier modules or safe resistive heaters, MOSFET drivers, current sensor, small display, physical lid sensor.
- **Technical core:** thermal system identification, model-predictive or priority-based control, energy budgeting, and fault-safe power electronics.
- **Three-minute demo:** place warm and cold containers in their zones, open one lid or add a warm disturbance to the cold side, and show the controller reallocate power while protecting the more time-sensitive compartment.
- **Why it scores:** food transport is an overlooked food problem, and thermal control produces strong plots and a visible physical build.
- **Safety:** keep temperatures modest, isolate food from electronics, add current and temperature limits, and use sealed water containers for the demo.
- **Scores:** originality 4, difficulty 5, demo 4, usefulness 5, relevance 5. **Risk:** medium-high.

---

## Track 3: Travelling

### 1. PackRight — an instrumented suitcase

Turn a carry-on into a live constrained-packing assistant. Corner load cells measure total weight and center of mass; a shallow distance or pressure map estimates occupied space; LEDs indicate where the next item should go to satisfy balance, fragility, and airline-weight constraints.

- **Hardware:** four load cells with HX711 amplifiers, lid ToF sensors or pressure grid, addressable LED strips, buttons for item type/priority, optional NFC tags.
- **Technical core:** calibration and sensor fusion, constrained bin-packing/placement heuristics, center-of-mass estimation, and incremental re-optimization.
- **Three-minute demo:** pack several marked objects badly; show an overweight or unstable corner; remove or move the LED-indicated item; the suitcase reaches the target weight and balance. Let a judge add a “fragile” item and recompute.
- **Why it scores:** nearly every traveler understands the problem immediately, and the physical before/after makes the optimization legible.
- **Scope guardrail:** solve 2D placement and weight balance, not full 3D computer vision. A foam-board suitcase mockup is acceptable if it looks deliberate.
- **Scores:** originality 4, difficulty 4, demo 5, usefulness 5, relevance 5. **Risk:** low-medium.

### 2. WayBand — beacon-and-haptic station navigation

Build a wristband or belt that guides a traveler through a mock station without requiring them to watch a phone. Fixed beacons and onboard ranging/IMU sensing estimate position; directional vibration patterns signal turns and warn of a nearby obstacle.

- **Hardware:** 3–4 BLE or UWB anchors, wearable ESP32/UWB module, IMU, 4–8 vibration motors, front ToF sensor, physical destination selector.
- **Technical core:** ranging calibration, particle/Kalman filtering, route graph logic, haptic language design, and graceful recovery after a missed turn.
- **Three-minute demo:** a teammate walks a compact taped route, deliberately misses a turn, receives a distinct correction, and reaches the destination without looking at a screen. Show positioning error and recovery time.
- **Why it scores:** it is a useful accessibility-oriented travel interface and integrates RF, embedded systems, estimation, and human factors.
- **Scope guardrail:** do not claim replacement for a mobility aid. Test with sighted volunteers under controlled conditions and present it as supplemental guidance.
- **Scores:** originality 4, difficulty 5, demo 5, usefulness 5, relevance 5. **Risk:** medium-high; BLE is safer than UWB if hardware is unavailable.

### 3. SteadyServe — active travel tray

Build a compact two-axis platform that keeps a cup or meal level on a moving bus, train, wheelchair, or aircraft tray. The rig senses platform motion and rejects disturbances while monitoring spill risk.

- **Hardware:** IMU, two high-torque servos or gimbal motors, cup platform, optional load cell or capacitive spill ring, physical tilt/disturbance base.
- **Technical core:** complementary/Kalman filtering, feed-forward plus PID control, actuator characterization, saturation handling, and spill-risk estimation.
- **Three-minute demo:** put colored water in a clear sealed or high-sided cup, tilt and shake the base with control off, then repeat with control on. Quantify peak tilt and liquid loss or spill events.
- **Why it scores:** controls difficulty is obvious, the demo is visceral, and the use case extends to travelers with limited dexterity.
- **Scope guardrail:** optimize small, slow disturbances. Avoid an overpowered mechanism and include mechanical stops.
- **Scores:** originality 4, difficulty 5, demo 5, usefulness 4, relevance 4. **Risk:** medium.

---

## Track 4: Multiplayer

### 1. Circuit Heist — distributed cooperative puzzle hardware

Give each of 3–4 players a different physical control module—tilt maze, rotary encoder, pressure pad, wire patch panel, or rhythm button. No module can be solved independently: one player’s action changes the valid state or feedback on another module.

- **Hardware:** several ESP32 nodes, distinct sensors/controls, LEDs/haptics, central physical lockbox with solenoid or servo, optional wired fallback network.
- **Technical core:** distributed event/state synchronization, latency handling, dynamically generated constraint graphs, debouncing, and recoverable network behavior.
- **Three-minute demo:** the judges see the locked objective, three players coordinate two or three simultaneous actions, the rules visibly change, and the physical box opens. Pull one node briefly to show recovery rather than total failure.
- **Why it scores:** “multiplayer” exists in the circuitry and coordination, not just several users on a web page. It is memorable and naturally theatrical.
- **Usefulness framing:** a reusable platform for cooperative exhibits, classrooms, team-building, and accessible game-controller research.
- **Scores:** originality 5, difficulty 4, demo 5, usefulness 4, relevance 5. **Risk:** medium.

### 2. SplitPilot — asymmetric co-op rover

Build one rover controlled by several players with deliberately incomplete roles: a navigator sees obstacle distance, a driver controls motion but not the map, and an engineer allocates a limited power budget among motors, lights, and sensors.

- **Hardware:** two-wheel rover, motor drivers/encoders, ToF or ultrasonic sensors, ESP32 radio, three distinct handheld controllers, LEDs showing power allocation.
- **Technical core:** real-time network protocol, role-based partial information, closed-loop motor control, resource allocation, and safety interlocks.
- **Three-minute demo:** the team traverses a short obstacle course; the engineer must sacrifice speed to power a sensor, the navigator calls a hidden turn, and the driver completes the delivery. Finish with a measured time/energy score.
- **Why it scores:** the mechanics make cooperation necessary, and the demo combines gameplay with robotics rather than hiding the robot behind autonomous AI.
- **Scope guardrail:** keep autonomy minimal and the course small. The multiplayer mechanics are the innovation.
- **Scores:** originality 4, difficulty 5, demo 5, usefulness 4, relevance 5. **Risk:** medium-high.

### 3. SyncGarden — a networked physical orchestra

Each player controls a sculptural instrument using a different gesture—tilt, pressure, touch, breath, or proximity. The network must synchronize their inputs into a shared light-and-sound object; players cooperatively lock phase or reproduce a pattern.

- **Hardware:** 3–4 wireless sensor controllers, central LED sculpture, speaker/MIDI output, force/IMU/capacitive/proximity sensors, optional haptics.
- **Technical core:** clock synchronization, jitter compensation, gesture calibration, collaborative state machine, and real-time DSP or generative rules.
- **Three-minute demo:** start with intentionally unsynchronized players and chaotic light/sound; show the haptic cues bring them into phase; the sculpture blooms when synchronization crosses a threshold. Display latency and phase error.
- **Why it scores:** it is visually polished, physical, and inclusive of nontraditional game interfaces.
- **Usefulness framing:** collaborative musical education, rehabilitation exercises, or museum interaction—not merely a light toy.
- **Scores:** originality 4, difficulty 4, demo 5, usefulness 3, relevance 5. **Risk:** medium.

---

## Track 5: IFM — Best Use of K2 Horizon

IFM describes K2 Horizon as an open family ranging from 0.9B to 375B parameters, with the smaller models aimed at constrained and on-device use. That creates a more distinctive opportunity than another chat application: use K2 as a local, high-level reasoner over live hardware telemetry while deterministic firmware owns timing, actuation, and safety. The 0.9B or 3.7B model may be suitable depending on the provided hardware and quantization; prove the inference path immediately and retain an API fallback if the rules allow it.

### 1. K2 FaultFinder Bench — reasoning over real electronics

Build a small electronic system with hidden, switch-selectable faults: open sensor line, swapped polarity, stuck digital input, excess motor current, or incorrect resistor network. The system exposes a schematic, component notes, and live measurements. K2 selects the most informative next safe test and explains its diagnosis; a guarded controller performs allowable measurements or lights the probe point.

- **Hardware:** custom or breadboard circuit, MCU telemetry hub, voltage/current/logic measurements, relays or DIP switches for fault injection, LED probe-point map, optional motor/sensor subsystem.
- **K2’s necessary role:** reason across a long service manual/schematic description, past measurements, and structured tool results to choose the next diagnostic action. A fixed rule engine validates each action before execution.
- **Technical core beyond the model:** fault-injection architecture, measurement isolation, tool-call schema, safe action validator, information-gain or test-cost baseline, and evaluation over known faults.
- **Three-minute demo:** a judge secretly flips one fault switch; K2 requests two or three live measurements; LEDs mark each probe point; the device identifies the fault and verifies the repair. Compare tests-to-diagnosis against a fixed checklist.
- **Why it avoids AI slop:** the model cannot succeed without physical evidence, its claims are checked against measurements, and every decision is auditable.
- **Scores:** originality 5, difficulty 5, demo 5, usefulness 5, relevance 5. **Risk:** medium-high.

### 2. RelayZero — offline disaster logistics nodes

Create several low-bandwidth field nodes representing shelters or travel parties. Each node reports inventory, demand, location, and link quality over LoRa or another local radio. A K2-enabled edge hub converts incomplete natural-language field reports into a constrained allocation plan, while a conventional optimizer validates quantities and sends compact instructions back to physical displays.

- **Hardware:** 3–4 LoRa or ESP-NOW nodes, buttons/sensors for supplies and occupancy, GPS or simulated location switches, e-ink/OLED displays, central laptop or edge computer.
- **K2’s necessary role:** interpret fragmented, inconsistent reports; identify missing information; call inventory and route tools; produce a structured request for the optimizer.
- **Technical core beyond the model:** radio protocol, intermittent-link queueing, constrained allocation solver, message integrity, local-first operation, and K2 output validation.
- **Three-minute demo:** disconnect internet, change one shelter’s demand, and degrade one radio link. The hub produces a new feasible allocation and the physical destination nodes update when messages arrive.
- **Why it avoids AI slop:** K2 handles ambiguity; mathematics enforces feasibility; radios and displays prove the system works under a real operational constraint.
- **Scores:** originality 5, difficulty 5, demo 4, usefulness 5, relevance 5. **Risk:** high unless the radio layer is working early.

### 3. ToolTalk Station — guarded natural-language assembly

Build a small instrumented workbench where a user asks for a physical assembly task, such as sorting parts and placing them in a fixture. K2 turns the request, tool descriptions, and live sensor feedback into a sequence of high-level actions. A deterministic controller validates geometry and executes those actions on a simple gantry, rotary carousel, or two-servo arm.

- **Hardware:** simple pick/place or rotary sorter, limit switches, force/load sensing, tagged parts, camera or color sensor, emergency stop.
- **K2’s necessary role:** plan with tool constraints, react to a failed grasp or missing part, and revise only at the symbolic action level.
- **Technical core beyond the model:** motion primitives, state machine, constraint validator, feedback and recovery, calibration, and latency instrumentation.
- **Three-minute demo:** a judge requests one of several supported assemblies; the mechanism begins, detects a deliberately missing or misplaced part, asks for or selects an alternative, and completes the task.
- **Why it avoids AI slop:** the output is a verified physical plan, not prose. The model never controls PWM, bypasses limits, or invents unapproved actions.
- **Scores:** originality 4, difficulty 5, demo 5, usefulness 5, relevance 5. **Risk:** high; choose a carousel over a robot arm to reduce mechanics risk.

**IFM technology sources:** [IFM’s K2 Horizon announcement](https://ifm.ai/k2/press-release/), [IFM technical introduction](https://ifm.ai/blog/k2/), and the [K2 Horizon 3.7B model card](https://huggingface.co/IFM/K2-Horizon-3.7B).

---

## Decision matrix

| Concept | Track | Judge-fit average | Build risk | Hardware wow | Best team strength |
|---|---|---:|---|---:|---|
| K2 FaultFinder Bench | IFM | 5.0 | Medium-high | 5 | Full-team integration |
| PowerPatch | Optimization | 4.8 | Medium | 5 | ECE + optimization |
| PackRight | Travelling | 4.6 | Low-medium | 4 | Sensors + algorithms |
| FlowSort | Optimization | 4.8 | Medium | 5 | Embedded timing + scheduling |
| Circuit Heist | Multiplayer | 4.6 | Medium | 5 | Networking + interaction design |
| FreshSort | Food | 4.6 | Medium | 5 | Statistics/ML + mechatronics |
| QuietShape | Optimization | 4.8 | Medium-high | 5 | DSP + experimental design |
| WayBand | Travelling | 4.8 | Medium-high | 4 | RF + sensor fusion |
| FlavorForge | Food | 4.6 | Medium | 5 | Preference learning + pumps |
| ToolTalk Station | IFM | 4.8 | High | 5 | Planning + robotics |
| SplitPilot | Multiplayer | 4.6 | Medium-high | 5 | Control + networking |
| ThermoTote | Food | 4.6 | Medium-high | 4 | Thermal/power control |
| RelayZero | IFM | 4.8 | High | 4 | Edge systems + optimization |
| SteadyServe | Travelling | 4.4 | Medium | 5 | Controls |
| SyncGarden | Multiplayer | 4.2 | Medium | 5 | DSP + human interaction |

## What to prototype first

Run three 45–60 minute feasibility spikes before committing:

1. **The irreplaceable physical loop:** read one real sensor and actuate one real output end-to-end.
2. **The technical kernel:** solve one toy instance with measured data, not fabricated JSON.
3. **The hero moment:** record a 20-second phone video of the disturbance and visible recovery/transformation.

Kill or simplify a concept if any one of these fails. The winning weekend plan is generally one reliable mechanism, one serious algorithm, and one unforgettable interaction—not five half-working subsystems.

## Team split

- **ECE:** power, sensors, signal integrity, actuator drivers, firmware, safety, and physical test fixtures.
- **CS:** device protocol, state machine, solver integration, local UI, logging, and demo reset/recovery.
- **Statistics/ML:** calibration, uncertainty, optimization/modeling, baseline comparison, and quantitative evaluation.
- **Related STEM:** mechanical build, domain model, experimental design, user workflow, enclosure, and pitch/demo ownership, adjusted to their specialty.

Pair the ECE and CS members on the end-to-end loop from hour one. The statistics/ML member should define the baseline and metric before collecting data. The fourth member should own the physical usability and the three-minute story, not become a catch-all.

## Three-minute demo template

- **0:00–0:20 — Problem:** one sentence and one physical object.
- **0:20–0:45 — Baseline:** show the failure or inefficient initial state.
- **0:45–1:15 — Technical reveal:** point to sensors, constraints, and the computation in plain language.
- **1:15–2:10 — Live disturbance:** let a judge change a load, fault, item, route, or player input.
- **2:10–2:35 — Physical response:** the system reroutes, balances, opens, diagnoses, stabilizes, or reallocates.
- **2:35–2:50 — Evidence:** show one before/after metric with units.
- **2:50–3:00 — Close:** state the user, benefit, and track relevance in one line.

Keep the dashboard subordinate to the object. If the mechanism stops moving, the audience should still understand the last valid state from LEDs, labels, and physical layout. Include a manual reset and a prerecorded backup clip, but plan to demo live.

## Anti-slop checklist

- The project remains valuable if every generative-model call is removed, except in the IFM track where K2 must perform a clearly bounded reasoning function.
- Sensors produce real, calibrated measurements; sample data is labeled as simulation.
- Optimization or ML is compared with a simple baseline.
- Model uncertainty leads to “inspect,” “ask,” or “stop,” not fabricated confidence.
- Low-level control and safety are deterministic.
- The physical artifact is necessary to both the problem and the proof.
- The pitch names one user and one scenario rather than claiming a universal platform.
- The demo ends with a measurable physical outcome.
