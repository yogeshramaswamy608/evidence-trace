# Labeling rubric, version 1

Frozen before labeling starts. The one revision allowed by the reliability rule (kappa below 0.6) gets a new version number and date, and both versions are published.

## What is labeled

Each checkable claim of a run gets exactly one label, judged only against the evidence items exposed to the agent in that run (the exposure log), never against telemetry the agent did not see.

## Labels

1. Supported: one or more exposed items, read together, make the whole claim true, including its entities, direction and time window.
2. Partly supported: exposed items make part of the claim true, or make it true only for a narrower scope than the claim states.
3. Unsupported: no exposed item bears on the truth of the claim.
4. Contradicted: at least one exposed item makes the claim false.
5. Not checkable: a recommendation or a statement that is not factual. Excluded from all denominators and counted.

## Extra mark

Supportable from collected data: set on an unsupported claim when telemetry collected in the run, but never exposed to the agent, would support it. This separates missing exploration from invention.

## Decision rules

1. One contradicting item outweighs any number of supporting items, unless the claim is scoped to exclude it.
2. A claim naming several services, backed for only some of them, is partly supported.
3. A claim with a time window wider than the evidence covers is partly supported.
4. A claim with the right entity but the wrong direction (increase stated, decrease shown) is contradicted.
5. A root-cause claim backed only by symptoms that several causes would produce is partly supported.
6. A claim the agent marks as no evidence found is labeled on its content like any other claim.
7. For Condition B, label first without reading the agent's own links, then compare the agent's links with the evidence used for the label.
8. When two labels seem equally right, choose the less favorable to the agent and write why.

## Segmentation

1. One claim states one fact about one entity in one time window.
2. Split a sentence joined by "and" or "because" into its parts; the "because" part is its own claim.
3. Keep numbers, units, service names and times exactly as the agent wrote them.
4. In Condition A, correct the model-proposed segmentation by hand under these rules; in Condition B, check that each listed claim is atomic and that no factual statement in the free text is missing.

## Record per label

Run id, claim id, label, the evidence ids used, the supportable mark where it applies, and one line of reason.
