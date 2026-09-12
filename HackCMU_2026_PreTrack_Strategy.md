# HackCMU 2026 Pre-Track Project Strategy

## Executive brief

HackCMU 2026 runs from 5:00 p.m. on September 11 to 8:00 p.m. on September 12, with project submission at 4:00 p.m. on September 12. The public rules permit brainstorming and team formation before the event but prohibit beginning the project's build or design before it starts.[^1] Projects are judged on four equally important-looking dimensions: real-life usefulness, technological complexity, originality, and presentation/demo quality.[^2]

The best pre-track strategy is therefore **not to commit to a theme-specific app**. Enter the opening ceremony with two or three flexible problem kernels, a clear way to choose among them, and agreement about who can execute the core interaction. Select the concept that fits a released track naturally; do not retrofit a finished-sounding idea with a weak 50-word justification.

The historical evidence favors projects that combine:

1. a specific, personally legible problem;
2. a non-obvious input or interaction (pose, gyroscope, wearables, binary code, video, VR);
3. a visible transformation that a judge can understand in seconds;
4. genuine computation between input and output; and
5. a narrow end-to-end workflow rather than a broad chatbot.

The three strongest adaptable concepts in this brief are:

- **StepGuard** — a camera-and-voice verifier for physical procedures;
- **AccessLens** — a live accessibility layer for unfamiliar spaces and events; and
- **Repair Relay** — diagnosis, guided repair, and reuse inventory for broken objects.

All three can demonstrate multiple public sponsor technologies without making any one sponsor SDK the whole product.

## What the 2026 event already tells us

The tracks are not yet public in the event materials reviewed, but the mechanics are. Teams choose the best-fitting track when submitting and provide a 50-word explanation. Prize depth depends on how many teams select each track.[^2] This creates two tactical implications:

- **Track fit matters, but crowding also matters.** If two concepts are equally strong, a natural fit in a less crowded track may have better expected value than a strained fit in the obvious AI-heavy track.
- **Overall-winner quality still matters.** The event also names an overall winner, so a team should not sacrifice the product's clarity merely to exploit a category.[^2]

Six sponsor prizes are public: best use of Gemini API, ElevenLabs, Solana, Vultr, Auth0, and MongoDB Atlas.[^2] The organizer also lists Microsoft, Adobe, Jane Street, Citadel, Cursor, and Roblox as event sponsors, although no public prize criteria for those companies were found on the Devpost page.[^2]

Sponsor technology should be treated as a multiplier:

| Sponsor | Strong integration | Weak integration |
|---|---|---|
| Gemini | Multimodal perception or reasoning central to the interaction | Generic text generation behind a chat box |
| ElevenLabs | Voice is necessary because the user's hands/eyes are occupied, or expressive audio is the product | Reading static text aloud |
| Solana | Verifiable settlement, provenance, ownership, or programmable incentives | Minting a token with no product reason |
| Vultr | A deployed real-time backend, GPU inference, or workload whose infrastructure is demonstrated | Merely hosting a static front end |
| Auth0 | Distinct roles, delegated agent actions, or human approval before sensitive operations | Login as a cosmetic checkbox |
| MongoDB Atlas | Operational event history, flexible multimodal records, live state, or semantic retrieval | One small collection used only for persistence |

Gemini's current API supports text, audio, image, and video inputs; its Live API provides bidirectional real-time audio/video interaction, although Live remains a preview feature and has session constraints.[^3] ElevenLabs offers real-time conversational agents with speech recognition, language-model orchestration, text-to-speech, interruption handling, tools, and knowledge bases.[^4] Auth0 specifically documents human-in-the-loop authorization, delegated calls to external APIs, and document-level authorization for RAG—not just sign-in.[^5] These capabilities make multimodal, voice-first, and permission-aware products especially viable for the public sponsor categories.

## Past projects: award-backed and instructive

Public records vary by year. The 2025 ACM page names award recipients but its Devpost gallery remains unpublished; creator pages and posts supply some project detail. The 2024 public gallery contains only seven projects and does not preserve winner badges. The 2023 and 2021 Devpost records are more useful but still incomplete in places. The list below labels award claims conservatively.

### 2025: interaction-first projects dominate

| Project | Recognition | What it did | Why it is instructive |
|---|---|---|---|
| **Medicly** | Grand winner | Used single-camera pose estimation, time-series joint-angle analysis, LLM feedback, and 3D anatomy to make at-home physical therapy observable while keeping clinicians in the approval loop.[^6] | Personal problem, serious workflow, visible CV demo, quantitative output, and responsible human oversight. |
| **null_pointer** | Retro track winner | Turned a phone's gyroscope into a Wii-like pointer/controller, including multiplayer, independent of screen location after calibration.[^7] | Reused a sensor everyone already owns; the demo is instantly playful and technically concrete. |
| **Cortex Cam** | Digital Media winner | Used Meta glasses to observe daily activities and estimate which cognitive functions were engaged, ending with a brain-activity visualization.[^8] | A memorable wearable input and a dashboard that makes invisible behavior visible. Scientific validity would need careful qualification beyond a hackathon prototype. |
| **Driftwords** | Games & Gamification winner | A 3D browser meditation/journaling experience in which a banana-cat character explores an island, fishes, and relaxes.[^9] | Polish and emotional tone can win even without an enterprise-sized problem; the interaction itself carried the idea. |
| **heXray** | Anthropic Best AI Hack | An AI-assisted binary decompiler with deobfuscation and automatic exploit-generation functions.[^10] | The AI tackled a difficult technical artifact instead of wrapping ordinary text chat. |
| **Ensemble** | Honorable mention | Converted audio into vintage/vinyl-style sound using an FFT-based signal-processing chain, PyTorch/Torchaudio, GPU acceleration, and live controls.[^11] | A narrow creative tool with real DSP, audible before/after output, and tunable parameters. |
| **LaternFly** | Honorable mention | Crowdsourced invasive lanternfly sightings and used a trained image classifier plus density mapping to visualize concentrations.[^12] | Combined community collection, a custom dataset/model, and a map that communicated impact immediately. |

The official 2025 page also names **RepCheck** as Health & Sustainability winner and **coDriver** plus **LaternFly** and **Ensemble** as honorable mentions, but public descriptions tied confidently to the named teams were not available for every project.[^13]

### 2024: simple product surfaces, legible real-world value

The public 2024 gallery shows only seven projects, so it should not be treated as a complete record. Still, its submissions reinforce useful patterns:[^14]

- **CMU Safe** adjusted route selection to favor proximity to campus emergency beacons instead of optimizing only for time.[^15]
- **shop.eco** embedded sustainability scoring into Amazon product pages through a browser extension, putting the intervention directly at the decision point.[^16]
- **Carbon Policy Simulator** let users change transportation, energy, and industry policies and see projected emissions over 30 years.[^17]
- **DocConnect** targeted specialist access for rural primary-care patients, while **NavHealth** targeted clinical intake overhead.[^14]

Separately, a creator record identifies **InsurAI** as the Hudson River Trading Best Use of Data winner. It combined an insurance-cost model with biometric and facial-analysis signals.[^18] The concept shows why predictive data demos appeal, but it also illustrates a modern caution: sensitive biometric inference and insurance decisions demand fairness, consent, and validity safeguards. A 2026 team should not make consequential health or financial claims from an unvalidated model.

### 2023: a space theme still rewarded reusable technical mechanisms

The 2023 event had an explicit space prize plus general and sponsor categories, and judged usefulness, complexity, potential, originality, and presentation.[^19]

| Project | Documented recognition | Mechanism |
|---|---|---|
| **TartanSpace** | Third place / second runner-up | Converted answers into sentence embeddings, reduced them to three dimensions with PCA, and displayed people as an explorable social space.[^20] |
| **Space JEDI** | Best Space-Themed Hack | Ingested live orbital data and computed a round-trip route for a hypothetical debris collector, with a Three.js visualization.[^21] |
| **How Do I Look?** | Most Creative Use of GitHub | Combined image-to-text and LLM reasoning to suggest attire for an event.[^22] |
| **Eco Bin** | Best Campus Infrastructure / GSA prize | Used RGB and depth sensing plus a custom classifier to sort trash, compost, and recycling; the creator reports 80% test accuracy and a hardware integration.[^23] |
| **SkyNet** | HRT Best Use of Data | Visualized satellites above Pittsburgh in real time in 3D.[^24] |

The best lesson is not “build for space.” Each project made its mechanism—embedding space, route optimization, multimodal styling, robotic sorting, or live satellite data—visible through the theme.

### 2021: the enduring judging formula

The 2021 gallery preserves clear winner badges and provides a useful baseline:[^25]

- **GEOVID @ CMU**, first place, collected/generated campus-location data, produced real-time and historical heat maps, and explored a GRU model for future dining-density trends.[^26]
- **MUGN'T**, second place, used probabilistic path planning, Dijkstra-style routing, crime-density data, and a Markov-chain risk estimate so users could trade off route speed and safety.[^27]
- **MAGC Map**, third place, reframed collaborative documents as a navigable knowledge graph.[^28]
- **AI Trash Detection Heatmap**, Bloomberg Sustainability winner, retrained an object detector on litter and placed detections onto an interpretable map.[^29]
- **GymGuru**, HRT data winner, paired occupancy data and forecasting with a usable Streamlit interface.[^30]
- **ConvertASL**, Sandia sponsor winner, ran real-time ASL gesture classification in the browser and explicitly worked on lighting and skin-tone variation.[^31]
- **Vinder**, Facebook sponsor winner, built a networked VR first-date environment on two Oculus headsets.[^32]
- **Pandemic Control Simulator**, honorable mention, made users manage a visible simulation rather than merely read a forecast.[^33]

The same four attributes present in 2026—utility, technical substance, originality, and a clear demo—were already explicit in 2021.[^34] The surface technologies changed; the winning structure did not.

## The winning-project pattern

### 1. Start with a vivid user moment

“A patient performs one squat and immediately sees joint-angle errors” is stronger than “an AI platform for health.” “A phone becomes a game controller” is stronger than “a new gaming experience.” The winning pitch should begin with the moment the problem hurts and show the change before explaining the stack.

### 2. Make the input unusual and the output inspectable

High-signal projects used pose landmarks, gyroscopes, glasses, binaries, VR headsets, audio spectra, depth cameras, orbital feeds, or live maps. The point is not hardware for its own sake. It is that judges can see evidence that the software processed something difficult.

### 3. Put deterministic structure around AI

Medicly did not ask an LLM to “judge a workout” from prose. It measured joint geometry and time series before generating human-readable feedback.[^6] LaternFly had a labeled classifier and density map.[^12] heXray operated on binaries.[^10] A 2026 concept should expose intermediate artifacts—detected steps, timestamps, confidence, retrieved evidence, permission checks, or state transitions—so it does not resemble a generic wrapper.

### 4. Design the three-minute story around one golden path

Past rules demanded a three-minute pitch, and the 2025 judging rubric explicitly contrasted real technical difficulty with a superficial ChatGPT wrapper.[^35] A good demo has one actor, one task, one visible failure or obstacle, and one transformed outcome. Secondary features belong on a single “what comes next” slide, not in the live path.

### 5. Sponsor depth beats sponsor count

Using four logos weakly is less convincing than making one sponsor capability indispensable. A second sponsor can support the infrastructure or security layer. The main integration should be explainable in one sentence: “Gemini tracks procedural state from live video; ElevenLabs intervenes because the technician's hands are occupied.”

## Project idea portfolio

Scores are directional judgments for a four-person, 24-hour team. “Flexibility” means ability to map honestly to several plausible tracks after they are announced.

| Idea | Core demo | Flexibility | Technical ceiling | Execution risk | Natural sponsor fit |
|---|---|---:|---:|---:|---|
| **StepGuard** | Catch a missed or wrong step in a physical procedure and explain the recovery | 5/5 | 5/5 | Medium | Gemini, ElevenLabs, Auth0, MongoDB, Vultr |
| **AccessLens** | Navigate a staged obstacle/signage course with adaptive visual, text, and voice help | 5/5 | 4/5 | Medium | Gemini, ElevenLabs, MongoDB, Vultr |
| **Repair Relay** | Diagnose a broken item from video, guide one repair, and log salvaged parts | 5/5 | 4/5 | Low–medium | Gemini, ElevenLabs, MongoDB, optional Solana |
| **TrustCut** | Upload a short clip and receive a timestamped claim/provenance map | 4/5 | 5/5 | High | Gemini, Auth0, MongoDB, optional Solana/Vultr |
| **Handoff** | Turn a messy voice note and images into a role-specific, permissioned action brief | 5/5 | 4/5 | Medium | Gemini, ElevenLabs, Auth0, MongoDB |
| **QuietRoute** | Route by noise, lighting, stairs, crowds, or sensory load, with expiring observations | 4/5 | 4/5 | Medium–high | MongoDB, Gemini, Auth0, Vultr |
| **StorySwitch** | Transform one live explanation into captions, simple language, audio description, and quiz | 5/5 | 3/5 | Low | Gemini, ElevenLabs, MongoDB |
| **ProofQuest** | Verify a real-world micro-challenge and update a shared cooperative game state | 4/5 | 4/5 | Medium | Gemini, MongoDB, Auth0, optional Solana |

### Concept 1 — StepGuard: procedural state, not another chatbot

**Problem.** People miss steps when assembling, repairing, cooking, conducting a lab exercise, or following a safety checklist—especially when their hands are occupied.

**Product.** A phone camera observes a short, bounded procedure and maintains an explicit state machine: completed steps, expected next action, detected anomaly, confidence, and recovery instruction. Voice guidance interrupts only when necessary.

**Golden demo.** Assemble a small object with four visually distinct steps. Deliberately use the wrong part or skip a step. The app pauses, highlights the evidence frame, explains the deviation aloud, and resumes after correction. A second screen shows the event timeline and uncertainty.

**Technical substance.** Multimodal streaming; step-state estimation; temporal evidence; a deterministic transition graph; voice interruption; role-based access to procedure definitions and audit logs. Gemini is perception/reasoning, ElevenLabs is the hands-free interface, MongoDB records state/events, Auth0 distinguishes author/operator/reviewer, and Vultr can host the real-time service.

**Scope cut.** One procedure, four steps, one error class. Do not promise universal action recognition or certify safety.

**Likely track mappings.** Education, accessibility, health, safety/security, industry/productivity, sustainability/repair, or “journey/process.”

### Concept 2 — AccessLens: one environment, many access modes

**Problem.** Unfamiliar environments are difficult for users who cannot reliably see signs, hear announcements, process dense instructions, or tolerate sensory overload.

**Product.** A live scene interpreter that lets a user select an access profile—visual assistance, hearing assistance, plain-language mode, or low-stimulation mode. It turns the same camera/audio stream into the appropriate cues and remembers discovered landmarks.

**Golden demo.** Stage a short “station” or hallway with a sign, an audio announcement, an obstacle, and a changed instruction. Demonstrate two profiles: one receives concise spoken navigation; another receives captions plus simplified next-action cards. End on a map of landmarks discovered during the walkthrough.

**Technical substance.** Real-time audio/video understanding, modality switching, landmark/event memory, confidence-aware cueing, and optional private profiles. Gemini Live is the central multimodal layer; ElevenLabs provides low-latency voice; MongoDB stores the evolving place graph.

**Scope cut.** One controlled indoor route. Phrase output as assistance, not guaranteed navigation, and include an obvious “uncertain—ask a person” state.

**Likely track mappings.** Accessibility, mobility, education, digital media, health, campus life, travel, or community.

### Concept 3 — Repair Relay: from diagnosis to reuse

**Problem.** People discard repairable objects because diagnosis, instructions, and part reuse are fragmented.

**Product.** A camera identifies a narrow class of fault, produces an evidence-linked repair path, gives hands-free instructions, and records any recovered components in a shared parts inventory.

**Golden demo.** Show a small device or mechanical assembly with one planted fault, such as a disconnected wire, missing fastener, or jammed mechanism. The app identifies the likely fault, asks for a confirming view, guides the fix, and adds a spare component to a local reuse board.

**Technical substance.** Active visual inspection (“show me the left connector”), structured troubleshooting, parts matching, inventory search, and outcome verification. If Solana fits the released track, use it only for a meaningful deposit, provenance, or transfer record—not as decoration.

**Scope cut.** One device family and two faults. Never claim mains-electrical or hazardous repair expertise.

**Likely track mappings.** Sustainability, education, community, hardware, circular economy, accessibility, consumer, or retro.

### Concept 4 — TrustCut: evidence map for short-form media

**Problem.** A short video mixes claims, edits, captions, reused footage, and synthetic elements, while viewers receive a single undifferentiated “trust” signal.

**Product.** Segment a clip into timestamped claims and transformations. For each segment, display what was heard/seen, available source evidence, detected inconsistencies, uncertainty, and provenance supplied by the publisher. The output is an inspectable map, not a binary truth score.

**Golden demo.** Use a 20-second team-created clip containing one accurate claim, one unsupported claim, and one edited visual. The system produces a timeline, opens the supporting evidence for the true claim, and shows why the other two remain uncertain.

**Technical substance.** Multimodal video parsing, claim extraction, retrieval, timestamp alignment, provenance hashing, and editorial roles. Solana could anchor an immutable digest; Auth0 can enforce publisher/editor/viewer permissions.

**Scope cut.** One clip under 30 seconds and a curated evidence corpus. Do not promise general deepfake detection or universal fact-checking.

**Likely track mappings.** Digital media, security, civic technology, education, communication, or trust.

### Concept 5 — Handoff: compress the mess, preserve responsibility

**Problem.** Shift changes, incident transfers, volunteer coordination, and care handoffs lose context across voice notes, photos, and partial checklists.

**Product.** Convert a messy multimodal report into a role-specific action brief that separates observations, inferences, unresolved questions, and required approvals. A recipient can ask follow-ups by voice; sensitive actions require human confirmation.

**Golden demo.** One teammate records a rushed handoff with two images and an ambiguity. A second teammate logs in under another role, receives only authorized information, asks a question, and triggers an approval request before the system shares or acts on sensitive content.

**Technical substance.** Structured extraction, uncertainty labeling, role-aware retrieval, event history, and Auth0's human-in-the-loop authorization pattern. This is strongest if tied to a concrete setting such as a student event, makerspace, shelter, clinic simulation, or maintenance shift.

**Scope cut.** Choose one setting and three roles. Without that vertical constraint, it becomes a generic summarizer.

**Likely track mappings.** Productivity, health, safety, community, accessibility, operations, or communication.

### Concept 6 — QuietRoute: routing for the condition maps ignore

**Problem.** Fastest-route systems ignore temporary stairs, broken elevators, crowd density, lighting, noise, and sensory load.

**Product.** An ephemeral condition map where observations expire, confidence changes with corroboration and time, and users route against a personal constraint profile.

**Golden demo.** Simulate three routes across a tiny map. Add a fresh obstruction report and watch the route and confidence change in real time; switch to a different profile and show a different optimum.

**Technical substance.** Multi-objective pathfinding, temporal decay, confidence aggregation, live events, and privacy-aware location handling. This must go beyond the earlier MUGN'T and CMU Safe ideas by emphasizing accessibility variables, expiring evidence, and transparent uncertainty.[^15][^27]

**Scope cut.** A synthetic six-node “campus” and four condition types. Do not depend on obtaining live institutional data.

**Likely track mappings.** Mobility, accessibility, campus, sustainability, health, community, or data.

### Two lower-risk backups

**StorySwitch.** Take a live mini-lecture or demo and render synchronized captions, plain-language steps, audio descriptions of visuals, and a two-question comprehension check. It is very feasible and sponsor-friendly, but the team must add a distinctive interaction—such as user-controlled modality switching with preserved context—to avoid looking like a summarizer.

**ProofQuest.** A cooperative game asks players to complete small real-world acts, verifies evidence conservatively from a photo/video, and changes a shared world. It can map to gamification, sustainability, wellness, or community. Avoid surveillance and never reward high-stakes or dangerous acts.

## Recommendation and selection logic

### Default ranking

1. **StepGuard** — best combination of judge-visible complexity, useful workflow, sponsor depth, and track flexibility.
2. **AccessLens** — strongest human story and live demo, especially if a teammate can test the interaction thoughtfully.
3. **Repair Relay** — safest build scope and broadest sustainability/community fit.
4. **Handoff** — excellent Auth0 story, but only after choosing a concrete domain.
5. **TrustCut** — high ceiling and timely topic, but retrieval and truth claims create demo risk.
6. **QuietRoute** — analytically rich but dependent on presenting a convincing data story.

### Choose based on team advantage

| Team strength | Prefer |
|---|---|
| Computer vision / streaming | StepGuard or AccessLens |
| Full-stack plus product design | Repair Relay or Handoff |
| Security / identity / systems | TrustCut or Handoff |
| Algorithms / data visualization | QuietRoute or TrustCut |
| Games / 3D / creative coding | ProofQuest, or a 3D front end for AccessLens |
| Limited hackathon experience | Repair Relay or StorySwitch |

### Opening-ceremony decision rule

For each released track, score each of the top three concepts from 0–2 on:

- natural track relevance;
- one-sentence problem clarity;
- one unforgettable live interaction;
- team-specific technical advantage;
- achievable golden path by the midpoint;
- deep fit with one sponsor prize; and
- differentiated position relative to known past winners.

Multiply **achievable golden path** and **live interaction** by two. Choose the highest score unless the fit requires changing the target user or core mechanism. If it does, choose the next concept rather than forcing the narrative.

## 24-hour execution shape

The event rules prohibit project building or design before the start, so pre-event work should remain brainstorming and team formation.[^1] Once the event begins:

### Hours 0–1: lock the story

- Write the problem in one sentence and the golden demo in five beats.
- Pick one sponsor integration as central and at most one as supporting.
- Define the visible intermediate artifact: state timeline, evidence frame, confidence, route tradeoff, or permission decision.
- Assign four owners: interaction/front end, intelligence/backend, data/integration, and demo/product. Pair on integration rather than creating four isolated feature branches.

### Hours 1–6: prove the technical heart

- Build the riskiest input-to-structured-output path first.
- Use controlled data and one bounded scenario.
- Log outputs so the demo can fall back to a recorded trace without pretending it is live.
- Test one failure case early.

### Hours 6–14: complete the golden path

- Connect the minimum front end, state store, and primary sponsor integration.
- Remove any feature that does not appear in the three-minute story.
- Add uncertainty and error states; these often increase credibility more than another feature.

### Hours 14–20: make it legible

- Add before/after, progress, and evidence views.
- Use seeded demo data where external services are unreliable, and label it.
- Prepare a single architecture diagram that traces input → computation → output.

### Final hours: rehearse and harden

- Rehearse to 2:30, leaving time for latency and interruption.
- Prepare a 20-second offline video of the golden path.
- Keep the live demo to one browser/device handoff if possible.
- Have one speaker explain the problem and outcome while another operates.

## Three-minute pitch blueprint

**0:00–0:20 — Problem.** One person, one moment, one cost. Avoid market-size filler.

**0:20–0:35 — Promise.** “StepGuard watches this four-step assembly and catches a skipped step before the user continues.”

**0:35–1:45 — Live demo.** Show normal input, the deliberate problem, visible reasoning/evidence, and corrected outcome.

**1:45–2:15 — Technical depth.** One architecture visual; name the difficult transformation and why the sponsor capability is indispensable.

**2:15–2:35 — Trust and limitations.** State what the prototype knows, what it does not know, and where a human remains responsible.

**2:35–2:55 — Use and expansion.** Name the first realistic adopter and one adjacent workflow.

**2:55–3:00 — Close.** Repeat the transformation, not the feature list.

## Red flags to avoid

- A general-purpose chatbot with a theme prompt.
- Six sponsor logos but no indispensable integration.
- Claims of diagnosis, safety certification, truth detection, or insurance fairness from an overnight prototype.
- Depending on private CMU APIs or unavailable live datasets.
- Training a large new model during the event when a smaller classifier, rules layer, or pre-trained multimodal API would prove the mechanism.
- A demo that needs several accounts, devices, or perfect network timing without a recovery path.
- Copying the core mechanism of Medicly, null_pointer, CMU Safe, MUGN'T, or another past winner. Build on the lesson, not the project.

## Bottom line

HackCMU's repeatable winning formula is **specific pain + unusual input + inspectable computation + a polished transformation**. The 2026 sponsor lineup makes real-time multimodal and permission-aware applications especially attractive, but the overall product must remain legible without the sponsor logos.

Enter the track reveal with StepGuard, AccessLens, and Repair Relay as the primary option set. Choose the one that fits a track without changing its user or mechanism, then cut it to a single controlled scenario. A reliable 60-second golden path with visible technical evidence is more competitive than a sprawling platform whose cleverest work cannot be seen.

## Sources

[^1]: HackCMU. “[Hack CMU 2026 Rules](https://hack-cmu-2026.devpost.com/rules).” Devpost, accessed September 11, 2026.
[^2]: HackCMU. “[Hack CMU 2026](https://hack-cmu-2026.devpost.com/).” Devpost, accessed September 11, 2026.
[^3]: Google. “[Gemini API Reference](https://ai.google.dev/api)” and “[Live API Capabilities Guide](https://ai.google.dev/gemini-api/docs/live-api/capabilities).” Google AI for Developers, accessed September 11, 2026.
[^4]: ElevenLabs. “[ElevenAgents Overview](https://elevenlabs.io/docs/eleven-agents/overview)” and “[ElevenAgents Quickstart](https://elevenlabs.io/docs/eleven-agents/quickstart).” Accessed September 11, 2026.
[^5]: Auth0. “[Auth0 for AI Agents](https://auth0.com/docs/get-started/auth0-for-ai-agents).” Accessed September 11, 2026.
[^6]: ACM@CMU. “[HackCMU 2025 Winners](https://www.acmatcmu.com/hackcmu2025/).” 2025; Aarush Agarwal. “[Medicly](https://www.aarushagarwal.dev/projects/Medicly).” Accessed September 11, 2026.
[^7]: ACM@CMU. “[HackCMU 2025 Winners](https://www.acmatcmu.com/hackcmu2025/).” 2025; Siddharth Radhakrishnan. “[HackCMU Winner (Retro Track)](https://www.linkedin.com/in/sidradh).” Accessed September 11, 2026.
[^8]: ACM@CMU. “[HackCMU 2025 Winners](https://www.acmatcmu.com/hackcmu2025/).” 2025; Keegan Wang. “[Cortex Cam HackCMU Post](https://www.linkedin.com/posts/keegan-wang-69b683241_excited-to-share-that-my-team-and-i-won-1st-activity-7373398991172071424-Wfd7).” 2025.
[^9]: ACM@CMU. “[HackCMU 2025 Winners](https://www.acmatcmu.com/hackcmu2025/).” 2025; Phi Nguyen. “[Driftwords](https://www.phinguyen.site/).” 2025.
[^10]: ACM@CMU. “[HackCMU 2025 Winners](https://www.acmatcmu.com/hackcmu2025/).” 2025; Atri Dey. “[heXray Project Description](https://www.linkedin.com/in/atri--dey).” Accessed September 11, 2026.
[^11]: ACM@CMU. “[HackCMU 2025 Winners](https://www.acmatcmu.com/hackcmu2025/).” 2025; Nick Mino. “[Ensemble](https://nickmino.com/).” Accessed September 11, 2026.
[^12]: ACM@CMU. “[HackCMU 2025 Winners](https://www.acmatcmu.com/hackcmu2025/).” 2025; Devin DeCosmo. “[Lanternfly Tracker](https://www.linkedin.com/in/devin-decosmo).” Accessed September 11, 2026.
[^13]: ACM@CMU. “[HackCMU 2025](https://www.acmatcmu.com/hackcmu2025/).” 2025.
[^14]: HackCMU. “[HackCMU 2024 Project Gallery](https://hackcmu-2024.devpost.com/project-gallery).” Devpost, 2024.
[^15]: CMU Safe team. “[CMU Safe](https://devpost.com/software/cmu-safe).” Devpost, September 2024.
[^16]: shop.eco team. “[shop.eco](https://devpost.com/software/shop-eco).” Devpost, September 2024.
[^17]: Carbon Policy Simulator team. “[Carbon Policy Simulator](https://devpost.com/software/carbon-policy-simulator).” Devpost, September 2024.
[^18]: Aditya Dewan. “[InsurAI — HRT Best Use of Data at HackCMU](https://www.linkedin.com/posts/aditya-dewan-7711b91b3_excited-to-announce-that-our-hackcmu-project-activity-7241971545584103424-LiDN).” 2024.
[^19]: HackCMU. “[HackCMU 2023](https://hackcmu-2023.devpost.com/).” Devpost, September 2023.
[^20]: Jason Niow. “[TartanSpace — HackCMU 2023](https://www.linkedin.com/in/jason-niow).” Accessed September 11, 2026; HackCMU. “[2023 Project Gallery](https://hackcmu-2023.devpost.com/project-gallery).” Devpost.
[^21]: Space JEDI team. “[Space JEDI — Junk Elimination and Debris Interception](https://devpost.com/software/junk-elimination-and-debris-interception-jedi).” Devpost, September 2023; Yash Maurya. “[Project Record](https://yashmaurya.com/).”
[^22]: Dishani Lahiri. “[Awards and Recognition](https://dishanil.github.io/).” Accessed September 11, 2026.
[^23]: Arul Rhik Mazumder. “[Eco-Bin (HackCMU 2023)](https://arulrhikm.github.io/projects.html).” Accessed September 11, 2026.
[^24]: Theron Amaralikit. “[HackCMU 2023 HRT Best Use of Data](https://www.linkedin.com/in/theron-amaralikit-2293501b2).” Accessed September 11, 2026; HackCMU. “[2023 Project Gallery](https://hackcmu-2023.devpost.com/project-gallery?page=2).”
[^25]: HackCMU. “[HackCMU 2021 Project Gallery](https://hackcmu21.devpost.com/project-gallery).” Devpost, October 2021.
[^26]: GEOVID team. “[GEOVID @ CMU](https://devpost.com/software/geovid-cmu).” Devpost, October 2021.
[^27]: MUGN'T team. “[MUGN'T](https://devpost.com/software/mugn-t).” Devpost, October 2021.
[^28]: MAGC Map team. “[MAGC Map](https://devpost.com/software/magc-map).” Devpost, October 2021.
[^29]: AI Trash Detection Heatmap team. “[AI Trash Detection Heatmap](https://devpost.com/software/ai-trash-detection-heatmap).” Devpost, October 2021.
[^30]: Haohui Liu. “[GymGuru](https://devpost.com/software/gymguru).” Devpost, October 2021.
[^31]: ConvertASL team. “[ConvertASL](https://devpost.com/software/convert-asl).” Devpost, October 2021.
[^32]: Vinder team. “[Vinder](https://devpost.com/software/betterdate).” Devpost, October 2021.
[^33]: Chinese Boat. “[Pandemic Control Simulator](https://devpost.com/software/pandemic-control-simulator).” Devpost, October 2021.
[^34]: HackCMU. “[HackCMU 2021](https://hackcmu21.devpost.com/).” Devpost, October 2021.
[^35]: HackCMU. “[HackCMU 2025](https://hackcmu-2025.devpost.com/).” Devpost, September 2025.
