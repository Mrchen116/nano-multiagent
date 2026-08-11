# Question mapper

## Inputs

Consume the frozen transcript, decision inventory IDs, owner replay events and artifact checkpoints without arm identity.

## Mapping rules

Map semantically equivalent questions to one decision ID; separate retrievable-fact questions, first escalation, repeated questions and unregistered decisions.

## Output contract

Emit immutable records containing run ID, transcript evidence span, decision ID, semantic-question ID, category and whether user action was required.

## Failure handling

Mark ambiguous mappings for blind adjudication; never infer a favorable category or edit the source transcript.
