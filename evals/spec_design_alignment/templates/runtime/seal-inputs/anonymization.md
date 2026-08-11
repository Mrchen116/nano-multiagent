# Anonymization protocol

## Arm identity

Replace arm, workflow, role and treatment identifiers with a per-comparison random label while preserving evidence anchors.

## Artifact normalization

Normalize only presentation metadata registered before the run; preserve substantive wording, structure, omissions and package length.

## Randomization

Derive presentation order from the sealed ordering seed and record the reversible mapping in runner-private output.

## Audit log

Record input/output manifest hashes, applied transformations and the private label map; reject any unregistered edit.
