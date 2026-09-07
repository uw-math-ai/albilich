# Experiment evidence protocol

Experiment datasets, run outputs, and empirical result reports are not distributed
with this source tree. The auditor and synthetic regression fixtures remain
available for validating separately held archives. A source-code checkout alone
is not evidence of proof-solving performance.

Future archives may be labelled `protocol_validated` only after the machine
auditor verifies immutable prompts and problem hashes, environment and seed,
complete run/event logs and proof snapshot, artifact hashes, independent
grading, exact identity between the selected and prompted problem, separation
of reference answers from every agent-visible file, independently backed
scoreboard labels, and (for ablations) at least three matched trials per
condition. General or novelty claims newly produced by this repository use
protocol v5: at least two conditions
must occur exactly once in every problem/repeat block; problem, prompt, budget,
stopping rule, and seed must match within a block; condition specifications and
the selection, block-assignment schedule, and analysis plans are
content-addressed; condition order is replayed with rejection-sampled SHA-256
Fisher--Yates; and the reported problem-level contrast and SHA-256-driven
cluster-bootstrap interval are recomputed by the auditor. The auditor also
recomputes the required number of paired problems using the registered
two-sided normal approximation, rather than trusting a self-reported sample
size. Its minimum detectable effect and problem-level standard-deviation
assumption remain explicit design assumptions whose scientific plausibility
requires external review.

Protocol v4 remains supported only for faithful replay of existing archives.
It validates the declared power-analysis fields structurally but does not
recompute the sample size, so a v4 archive must not be described as carrying
the stronger v5 power-design guarantee. Unknown protocol versions fail closed.

Protocol v5 is the generic experiment-evidence format. Scheduler comparisons use
protocol v6, which additionally replays every archived scheduler decision and
the exact dispatched action, verifies that the registered v17/v18 condition
governed every workflow exposure, and requires complete protocol-v3 randomized
blocks. The assignment commits the exact problem bytes as well as its identifier.
A preregistered schedule also fixes the exact run identifier for every arm,
problem and prompt digests, token budget, and stopping rule, preventing an
operator from selecting among extra replicas after observing outcomes.
A finalization record commits the number and digest of all dispatches plus the
event, snapshot, and result hashes. Condition-blind graders sign only the
condition-free grading-artifact manifest and grading attestation; a separate
out-of-band execution-trace auditor signs commitments to the unblinded trial
manifest and the exact finalized independent-grade file, and attests that the
trace is complete and that labels were finalized before trace review.

Protocol v6 does not accept a merely chosen integer seed. The assignment schedule
preregisters a future randomness event. A separate randomization authority signs
the observed randomness after registration, and every 256-bit block seed is
derived from that value, problem identifier, and repeat index. The authority's
public key is an out-of-band trust input and must differ from registration and
grader keys. This is still a trust statement about the named authority and
source, not an independently proved physical-randomness claim.

Protocol v5 also requires an Ed25519 receipt over the preregistration,
selection rule, assignment schedule, grader protocol, rubric, and analysis
plan. Its public key is deliberately not trusted from the archive itself.
Each grader separately signs the complete label map together with the rubric
and registration receipt. Supply the independently held keys with:

```bash
python -m agents.generation.phase2.experiment_audit \
  --experiments-root /local/archive \
  --trusted-registration-key /independent/custody/registration-public.pem \
  --trusted-randomization-key /randomization/custody/public.pem \
  --trusted-trace-key /trace-audit/custody/public.pem \
  --trusted-grader-key /grader-a/custody/public.pem \
  --trusted-grader-key /grader-b/custody/public.pem
```

A valid receipt proves that the named custodian signed the registered bytes; it
does not prove that no undisclosed pilot runs preceded registration. That
limitation must remain in any empirical claim. General-evidence labels also
require two distinct out-of-band Ed25519 grader keys; names and boolean
`independent` fields inside the archive are not treated as authentication.
Literal condition identifiers are rejected in grading artifacts and evaluation
identifiers, but encoded or semantic condition leakage remains a procedural
blinding risk rather than something this file format can prove absent. This
source release supplies no held-out evidence for the scheduler's fixed weights
or allocation rule.
