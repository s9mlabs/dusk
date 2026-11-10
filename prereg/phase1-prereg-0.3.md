# Dusk Phase 1 pre-registration

**Status: version 0.3, approved 10 November 2026** by Abhiram Sribhashyam and Udeern Varanasi
(Udeern's approval relayed by Abhiram). Written by Claude. Locked by `lock-0.3.json` and
timestamped with OpenTimestamps before any held-out data was generated. It replaces version 0.2
([`phase1-prereg.md`](phase1-prereg.md), locked by `lock-0.2.json`). No held-out data existed when
it was written, so nothing here can have been shaped by held-out results.

This document doesn't change from here. Any later change is a new, dated, timestamped version that
says what changed and why.

The proposals behind this version, with the reasons for each, are in
[`revision-0.3-draft.md`](revision-0.3-draft.md). Abhiram approved them on 4 November 2026.
Udeern reviewed them on 10 November 2026 and asked for items 9, 17 and 18 to be settled before
approval. This text settles them as section 12 describes.

## 1. What Phase 1 tests

Dusk (the program was called NEXUS; the code package keeps the name `nexus`) reads a circuit's
activity, the pokes applied to it and an imperfect wiring diagram. For each circuit it says either
"no switch" or gives a datasheet for every switch it finds: Trigger, Threshold, Timing, Reach,
Priority and Cost. Each continuous field comes as an interval, not a single number.

Phase 1 runs Dusk on simulated circuits where the right answers were planted on purpose, and asks
four questions:

1. Does it find the switches that are there, with the right values? (Recovery)
2. Does it refuse to invent switches that aren't? (No false switches)
3. Do two circuits built differently but with the same switch get the same datasheet?
   (Degenerate twins)
4. Does it predict what an unseen poke will do better than a model that only knows the wiring?
   (Prediction)

Questions 1 and 2 are the gate: if either fails, the tool gets fixed before anything else (Phase 1
checkpoint). Question 4 is reported whether it passes or fails, and a loss doesn't stop the program
(decision D8).

M5 and M7 results are extra analyses outside this pre-registration, and every report labels them
that way.

## 2. Fixed before any held-out data exists

These are written, hashed and timestamped before the held-out set is generated:

- this document;
- the thresholds file for this version: every pass mark and fixed setting below, as numbers;
- the scoring priors, `configs/scoring_priors.json` (already locked by `lock-scoring-0.1.json`);
- the wiring error settings, `configs/corruption.json`, with its placeholder note replaced by the
  wording of section 3;
- the split manifest (section 4);
- the scoring code (already locked by `lock-scoring-0.1.json`; the two fixes in section 5 are made
  under this version and locked with it);
- the list of fields that can be recovered at all (section 5.2), computed on training data only.

Dusk's predictions on the held-out set are hashed and timestamped before any scoring. The held-out
answers are encrypted to the key holder (section 7) and can't be read before then.

## 3. The circuit library

- **Size.** 5,000 circuits, under 6 brain states. The 200-circuit pilot (3 November 2026, files in
  `logs/pilot/m3/`) accepted 200 of 200 circuits at 1.00 to 1.07 tries each, took 55 seconds per
  circuit on average including Jaxley compilation, and used 35 MB per circuit. With the extra
  noise seeds of the held-out circuits (below) and the larger winner-take-all protocol (below),
  the full library is estimated at about 115 to 120 hours and 260 to 270 GB on the laptop (RTX 4050,
  6 GB). The laptop drive had 872 GB free on 6 November 2026. No cloud machine is needed. The
  estimate is checked again on the first batch, before the rest is generated.
- **Noise seeds.** 3 per trial, except held-out whole circuits, which get 10 (for their noise
  ceiling, section 5.6).
- **Switch types.** Four, each built from a published model and in graded form: release
  (disinhibition), volume knob (gain), winner-take-all, and global shutoff.
  - The two-state stochastic switch is left out of this version. It flips at random, and the probe
    measures a fixed gate ratio, so its planted answers can't be measured as things stand.
  - Gain is built so the trigger inhibits a tonically active neuron that shunts the output. It
    changes the slope of the input's effect without driving the output directly.
  - Winner-take-all is built so the triggers drive only the competing units, which inhibit each
    other and the opposite relay. Inputs reach their outputs through their own relays.
  - In every switch type, no trigger shares a target neuron with a non-trigger input. A frozen
    test checks this.
- **Circuits with no switch.** Between a third and a half of the library: plain circuits, plus
  decoys that look like a switch (adaptation, shunting inhibition, or bistability with no gate).
- **Degenerate twins.** Pairs whose measured datasheets match within a stated tolerance and whose
  biophysical parameters differ (section 5.4).
- **Pokes.** Every input is always one of the single-poke targets, so each paired poke has an
  unpaired reference. Each circuit gets:
  - 50 single pokes;
  - paired pokes: one input held at 10, 20 or 30 mV for the whole trial while another gets the
    standard 15 mV, 100 ms poke, for every ordered pair of inputs and every hold level;
  - paired steps: one input held at 15 mV while another steps to 30 mV from 1500 to 1800 ms, for
    every ordered pair;
  - with three or more inputs, a priority poke: every pair of inputs held at 30 mV while each
    remaining input gets a 15 mV, 100 ms poke.

  A two-input circuit gets 58 pokes (1,044 trials). Winner-take-all, with four inputs, gets 110
  (1,980 trials).
- **Planted answers.** Each gate's datasheet is measured from the simulated circuit by the probe,
  at the library's time step. When a gate controls more than one input-to-output path (in this
  version, only global shutoff), the probe measures every path and the datasheet holds their
  combined value:
  - trigger gain and the two timing ratios, which are scored on a log10 scale: the mean of their
    log10 values (a geometric mean);
  - threshold and reach, which are scored on a linear scale: the ordinary mean.

  A circuit is accepted only if every controlled path measures as a switch with a finite value for
  every field. Otherwise it is redrawn, like any circuit that fails acceptance, and the number
  redrawn is reported per type. Trigger identity is unchanged, since all paths share the trigger.
- **Time step.** The library is simulated at 0.2 ms. There, voltages are 0.03 to 0.3 mV from the
  converged solution for most neurons and up to 0.87 mV in the latched bistable pair. Planted
  answers are measured at the same step, so the bench is consistent with itself, but the circuits
  are the NeuroML model at 0.2 ms, not the continuous one. These voltage errors are small next to
  the 10 mV recording noise. That does not by itself show that every derived measurement is
  unaffected, and the report says so.
- **Wiring corruption.** Each simulated animal is one draw of wiring errors. A circuit's "animal" is
  that draw (D4). Only the diagram shown to the methods changes. The simulated circuit always uses
  its true wiring.
  - **The settings are assumed test conditions, not measured biological error rates.** Published
    fly connectome work shows that wiring maps contain errors (Dorkenwald et al. 2024), but no
    source gives these four numbers directly. A 94% accuracy for guessing a neuron's transmitter
    (Eckstein et al. 2024) is not a 6% sign error rate, because a wrong transmitter label does not
    always change whether a connection excites or inhibits. No source was found for the strength
    error spread.
  - **Base settings:** 10% missing connections, 5% false connections, 5% sign flips, and strength
    errors with a standard deviation of 0.3 in log10 units.
  - **How each error is made, in this order, for each true connection:**
    1. *Missing:* with probability 0.10 the connection is left off the diagram, and nothing else
       is done to it. This applies to chemical synapses and gap junctions.
    2. *Sign flip:* with probability 0.05, an excitatory synapse is shown as inhibitory or the
       reverse. Shunting synapses and gap junctions have no sign to flip.
    3. *Strength error:* every connection still on the diagram has its strength multiplied by
       10^z, with z drawn from a normal distribution with mean 0 and standard deviation 0.3. One
       standard deviation is about a factor of two. Strength is the synaptic or gap conductance
       divided by the receiving neuron's leak conductance.
  - **False connections, added after the above:** their number is drawn from a binomial
    distribution over the true connections with probability 0.05, so about 5 per 100 true
    connections. Each joins an ordered pair of neurons drawn at random from the pairs with no true
    connection (up to 100 draws; if none is free, that false connection is skipped). Each is a
    chemical synapse, excitatory with probability 0.7 and inhibitory otherwise, with a strength
    drawn uniformly from 0.1 to 0.5.
  - **Half and double checks.** Every animal also stores two more diagrams, drawn the same way at
    half and at double the base settings: missing 5% and 20%; false connections and sign flips
    2.5% and 10%; strength spread 0.15 and 0.60 log10 units. Only the diagram changes, so no extra
    simulation is needed. Every test that reads the diagram is rerun on them with the same scoring
    rules, and the results are reported next to the base results. They are not pass marks.
  - Dusk's recovery step does not read the diagram (section 5.2), so the recovery result can't
    depend on these settings. The prediction test and the wiring baselines do.
- **No spiking circuits in this phase (Abhiram, 2 November 2026).** Every circuit uses graded,
  non-spiking neurons connected by graded synapses and gap junctions, the way worm circuits work.
  Switch types whose published models spike (for example winner-take-all, after Wang 2002) are
  built as graded versions, and the report says so. The translator from NeuroML to Jaxley
  (tarjuman 0.5.1) drops spike-triggered synapses, while graded synapses and gap junctions match
  NEURON (section 6). Spiking circuits come in a later version of this plan.
- **Consequence for energy (M6).** The energy milestone needs one spiking switch, and the worm
  energy route has no published check. M6 is out of this version's scope, and Cost is not scored.

## 4. What is held out

Four kinds of unseen material, each split on its own unit. Every trial, repeat and noise seed of a
unit sits on the same side of the split.

| Held-out kind | Unit | Share held out | Share for validation |
|---|---|---|---|
| Whole circuits | circuit ID | 20% | 20% |
| Neurons | neuron ID, within training circuits | 20% | 20% |
| Poke types | poke-type label | 20% | 20% |
| Brain states | state label | 20% | 20% |

- At least one unit of each kind goes to test and one to validation, and at least three units of
  each kind must exist.
- A trial counts as test data if any of its four units is held out.
- Model and design choices use the training and validation splits only.
- With 6 brain states, this leaves 4 for training, 1 for validation and 1 for testing.
- **Held-out circuits per switch type:** at least 100. With 100 circuits, an observed pass rate of
  80% has a 95% interval of about 71% to 87%, which is enough to tell 80% from 70%. With about
  3,000 switch circuits over four types and 20% held out, each type gets about 150.

## 5. Tests and pass marks

All numbers are also in the thresholds file. Where the two disagree, this document wins, and the
disagreement is a bug to fix before approval.

### 5.1 Recovery

- A continuous field counts as recovered when the method's 90% interval contains the planted value
  **and** the interval is no wider than **0.5** of that field's prior range. A wide interval that
  happens to contain the answer doesn't count.
- **"90% interval" is a joint level per circuit.** A method's intervals for one circuit, across
  all its identifiable fields and all its gates, should all contain the planted values together in
  about 90% of circuits. (A per-field 90% level would make ten intervals all hold only about 35% of
  the time if their errors were independent, whatever the model's quality.)
- **How Dusk makes and checks its joint intervals.** Training circuits only:
  1. 20% of the training animals are set aside at random (seeded) for calibration. The network is
     trained on the rest and gives a 5% and a 95% quantile for each field, on the scoring scale.
  2. Per field, the calibration miss score is how far the planted value falls outside the
     interval (negative when inside), and each interval is first widened to cover 90% of its
     field's calibration values, with the finite-sample correction (level 0.9 x (1 + 1/n)).
  3. Joint step: for each calibration circuit, each field's remaining miss is divided by that
     field's spread of miss scores, and the circuit's score is its largest such value over all its
     identifiable fields and gates. Circuits are grouped by the number of gates; within each group
     the widening is set at the 0.9 x (1 + 1/n) quantile of these scores, and applied in each
     field's own units.
  4. A held-out circuit gets the widening of the group matching the number of gates Dusk calls.
  Any other method may use its own procedure, but is scored against the same joint level.
- Trigger identity is scored by exact match, and its gain by the interval rule. Priority is scored
  by pairwise order agreement with the planted ranks (D3). A predicted tie counts as disagreement.
- **Pass:** in at least **80%** of held-out switch circuits, every identifiable field (5.2) is
  recovered. The width limit stays at **0.5**. Cost is left out until M6.
- **Reported, for Dusk and for `sbi`:** how often all of a circuit's intervals hold together (should
  be near 90%), how often each single interval holds (now expected above 90%), interval widths as a
  share of the prior, the number of circuits that pass, and an interval score (CRPS).
- The joint rule was proposed on 6 November 2026 after looking at development results, and the
  report says so.
- **Null row.** An estimator that ignores the data and returns the prior must fail this test. If it
  passes, the test is too easy, and that's reported.

### 5.2 Which fields can be recovered at all

- Method: one neural posterior per switch type, trained with `sbi` on the measured summary features
  of training circuits. "Perfect simulated data" means voltages with recording noise but no wiring
  corruption; corruption only changes the stored diagram, which these features don't use.
- Each circuit's interval comes from a model that did not train on it (5 folds).
- A field is identifiable for a switch type when its 90% posterior interval is no wider than 0.5 of
  the prior range in at least 80% of that type's training circuits. This step uses a per-field 90%
  level, unchanged from version 0.2. So a field can be on the list while its joint interval breaks
  the width limit; that counts as a failure.
- A switch type with fewer than 20 planted triggers in training is left undecided.
- Unit: one field for one switch type. The list is computed on training data only, then hashed and
  timestamped before any scoring. Dusk isn't charged for fields on the "not identifiable" list, and
  the report names them.

### 5.3 No false switches

- **Pass:** at least **90%** of held-out no-switch and decoy circuits get "no switch". Reported for
  plain circuits and decoys separately, and for each decoy kind.

### 5.4 Degenerate twins

- **Finding a twin.** Each capacitance, leak and conductance of the original is multiplied by a
  separate random factor (log-normal, standard deviation 0.25 in natural-log units; 0.10 for
  winner-take-all), the copy is re-measured by the probe, and it is kept if every field lands within
  **0.1 of the prior range** of the original's value, on that field's scoring scale (log10 for gain
  and the timing ratios, linear for threshold and reach). At most 20 tries per circuit.
- **What happens without a twin.** The circuit has no pair. The report gives the twin-finding rate
  per type next to the twins result.
- A twin pair matches when both datasheets meet the recovery rule and their intervals overlap on
  every identifiable field.
- **Pass:** at least **80%** of held-out twin pairs match.

### 5.5 Leak

- Close a planted gate, then measure how much of its direct effect on downstream activity other
  paths restore (resample ablation and path patching).
- Reported as a distribution over gates and pokes. The median must be at most **10%**.
- This measures how redundant the generated circuits are, not how good Dusk is.

### 5.6 Prediction (P2)

- Held-out whole circuits are rerun with **10** noise seeds to estimate their noise ceiling, using a
  split-half estimate with Spearman-Brown correction. The other three held-out kinds use the 3
  seeds every trial has, and the report says their ceilings are noisier. Scores are fractions of
  the ceiling.
- Circuits whose mean ceiling, without any floor, is below **0.1** are left out of this test, and
  the count is reported. Then, for the kept circuits only, each bootstrap sample of the ceiling is
  floored at 0.1, so no sample divides by zero. (Flooring first would lift every mean to 0.1 and
  nothing would ever be left out.)
- The uncertainty in each ceiling is carried into the bootstrap.
- The comparison is against baseline 1 (a fitted wiring-constrained linear model, as in Creamer,
  Leifer and Pillow), both pooled over states and fitted per state. Dusk has to beat both.
- **Pass:** on held-out, state-dependent pokes, the 95% bootstrap interval (over circuits) of the
  paired difference between Dusk and baseline 1 excludes zero, in Dusk's favour.
- All four held-out kinds are reported, along with the other baselines (synapse count, wiring-blind,
  fully connected, shuffled wiring, and the state-by-input linear model), and the half and double
  wiring error checks (section 3).

### 5.7 Tie rule

- If baseline 4 (a linear model with a state-by-input term) scores within **0.02** of Dusk on
  state-dependent pokes, there's no switching result to report, and the report says so. A tie
  overrides a prediction pass.

### 5.8 Mixed results

- Results are reported per switch type. Phase 1 passes only for the types that pass, and the report
  names the ones that fail.

### 5.9 Exclusions

Decided before generation. Excluded runs are counted and reported per switch type and per reason.

- A run is excluded if any voltage is NaN or infinite, if any voltage leaves -150 to +80 mV, or if
  the run fails the file checker.
- A circuit is excluded if more than 10% of its runs are excluded.
- If more than 5% of the circuits of one switch type are excluded, that type's generator gets fixed
  and the type is regenerated before any scoring.
- Nothing is excluded after predictions are hashed.

## 6. Reproducibility

Every reported number names the device it came from.

| What | Same device | Across devices |
|---|---|---|
| PyTorch training | bit for bit | CPU against GPU differ by up to 6e-08 per parameter; tolerance **1e-6** |
| Jaxley simulation | bit for bit (GPU, float32) | measured before generation; tolerance stated then |
| Jaxley against NEURON, graded voltage | | within **0.02 mV** |

- **How the NEURON check is run.** Jaxley in float64 at a 0.0025 ms step, against NEURON 9.0.2.
  All 8 circuit types agree to within 0.02 mV (worst seen 0.007 mV). At a 0.01 ms step NEURON
  diverges on the stiff graded synapses of latched or strongly driven cells, and Jaxley in float32
  drifts at fine steps, which is why this method is used. The library itself runs at 0.2 ms
  (section 3).
- Every simulated run stores the inputs the simulator actually received. A frozen test reads them
  back and compares them for every generator.

## 7. Locking and access

- The files in section 2 are hashed into one lock file and timestamped with OpenTimestamps. One
  command checks later that none of them changed.
- **Key holder (D7): Udeern Varanasi** (Abhiram, 3 November 2026). Held-out answers and held-out
  response targets are encrypted with age (X25519) inside the generator, to Udeern's public key:

  `age1vte8j93exfsjdcarne4tq2ar9ssfw9zqe3sp4sj8feew7v59r4cq8dtpvw`

  Udeern keeps the private key and decrypts once, after predictions are hashed and timestamped.
- Every opening of the held-out set goes through one function that logs who, what and why, and
  stops at the limit. A failed opening counts.
- **Access limit: 3 openings.** One for the scoring run, one for a rerun after a bug in the scoring
  code (the bug and the fix are logged first), and one spare. Using the spare is reported.
- Results are published whether they pass or fail.

## 8. The energy field (Cost)

- Every switch's datasheet must carry a Cost value; the checker rejects files without one. Until M6
  exists, generators record a blank Cost and log each time they do.
- Cost is scored only after M6, and only for switch types M6 covers.

## 9. What would count as a failure of this plan itself

Each of these would be reported, not hidden:

- the prior-only null row passes recovery (the test is too easy);
- fewer than 100 held-out circuits survive exclusions for a switch type;
- the identifiability step marks most fields "not identifiable" even on perfect data;
- any lock check fails, or an opening of the held-out set is missing from the log.

## 10. Decisions

Settled on 2 November 2026 for version 0.2: D3 (the six fields), D4 (states, animals, trials),
6 brain states, D6 (Jaxley with NEURON as the check), no spiking circuits, and the numbers in
sections 4 to 7.

Settled for version 0.3 (proposed in `revision-0.3-draft.md`, approved by Abhiram on 4 November
2026, reviewed by Udeern on 10 November 2026; final approval is section 11):

1. Name Dusk; 5,000 circuits; the poke protocol; scoring scales; the identifiability method.
2. Noise-ceiling floor order (section 5.6) and tied priorities counted as wrong (section 5.1).
3. 10 noise seeds for held-out circuits only (item 8, option b).
4. Wiring errors stated as assumptions, defined exactly, with half and double checks (item 9).
5. Twin tolerance and search settings (item 10).
6. Stochastic switch left out (item 11).
7. NEURON check method and library time step stated (items 12 and 13).
8. D7: Udeern holds the key (item 14).
9. Rebuilt gain and winner-take-all circuits and the priority poke (items 15 and 16).
10. Joint 90% interval level per circuit (item 17).
11. Global shutoff measured on every path and combined (item 18, option B).

## 11. Approval

Both approved this exact text, which `lock-0.3.json` hashes.

| Name | Role | Decision | Date |
|---|---|---|---|
| Abhiram Sribhashyam | Founder | Approved | 10 November 2026 |
| Udeern Varanasi | Head of Research | Approved (relayed by Abhiram) | 10 November 2026 |

## 12. Changes from version 0.2

- **Name** NEXUS to Dusk. Section 1.
- **Library:** count fixed at 5,000 from the pilot; four switch types (stochastic switch dropped);
  rebuilt gain and winner-take-all; the full poke protocol including the priority poke; 10 seeds for
  held-out circuits; time step stated. Section 3.
- **Global shutoff (item 18):** every controlled path measured; log-scored fields combined by
  geometric mean, linear fields by ordinary mean; a circuit with any path that does not measure as a
  switch is redrawn. Section 3.
- **Wiring errors (item 9):** "measured error rates" replaced by assumed test conditions, each error
  defined, with half and double checks on extra diagrams. Section 3.
  - *Found while writing this version:* the corruption code draws strength errors as e^z with
    standard deviation 0.3, which is natural-log units (one standard deviation is about a factor of
    1.35), while the draft and the review both read 0.3 as log10 units (about a factor of 2). This
    version uses log10, as written, and the code is changed to match before generation. If the
    approvers prefer the smaller spread, section 3 changes instead.
- **Recovery (item 17):** joint 90% level per circuit, with Dusk's calibration method and what is
  reported; tied priorities count as wrong. Section 5.1.
- **Identifiability:** the method as built. Section 5.2.
- **Twins (item 10):** tolerance, search settings and the no-twin rule. Section 5.4. The smaller
  winner-take-all perturbation (0.10) and the 20 tries were tried on development circuits on
  10 November 2026 (`logs/pilot/m3/wta_sd010.json`, `others_sd025.json`,
  `shutoff_allpaths_sd025.json`): twins were found for 10 of 10 winner-take-all circuits and for
  every accepted gain, release and global shutoff circuit (4, 4 and 5), using at most 13 tries.
- **Prediction (items 6 and 8):** seed counts and the floor order. Section 5.6.
- **NEURON check (item 12).** Section 6. The spike-time row is dropped, since no circuit spikes.
- **Key holder and public key (item 14).** Section 7.
- **M5 and M7** labelled as outside this pre-registration. Section 1.

## Sources

- Dorkenwald, S. et al. (2024). Neuronal wiring diagram of an adult brain. Nature.
  https://doi.org/10.1038/s41586-024-07558-y
- Eckstein, N. et al. (2024). Neurotransmitter classification from electron microscopy images at
  synaptic sites in Drosophila melanogaster. Cell. https://doi.org/10.1016/j.cell.2024.03.016
- Creamer, M., Leifer, A. and Pillow, J. (2024). bioRxiv. https://doi.org/10.1101/2024.09.22.614271
- Wang, X.-J. (2002). Probabilistic decision making by slow reverberation in cortical circuits.
  Neuron. https://doi.org/10.1016/s0896-6273(02)01092-9
