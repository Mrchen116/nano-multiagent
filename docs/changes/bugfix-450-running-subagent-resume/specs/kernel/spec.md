# kernel Specification (delta for bugfix-450)

## ADDED Requirements

### Requirement: running subagent follow-up must be deliverable before it is acknowledged

When a consumer uses the built-in `agent` tool to send a follow-up prompt to an existing subagent that is still running, the kernel only acknowledges the follow-up as queued if the original running subagent can actually consume it in the same subagent session. The follow-up is not allowed to be silently dropped or handled by a second unrelated concurrent subagent run.

#### Scenario: follow-up to a running subagent is consumed by that subagent
- **GIVEN** a session has launched a background subagent and received its `agent_id`
- **WHEN** the consumer invokes the built-in `agent` tool with that `agent_id` and a follow-up prompt while the subagent is still running
- **THEN** a successful queued result means the follow-up will be consumed by that running subagent at a safe turn boundary
- **AND** the subagent's subsequent observable output or transcript reflects that the follow-up entered the same subagent session

#### Scenario: follow-up cannot be delivered to the live running subagent
- **GIVEN** a session has an `agent_id` whose task record still appears running
- **WHEN** the consumer invokes the built-in `agent` tool with a follow-up prompt but the kernel cannot confirm a live delivery path to that running subagent
- **THEN** the tool call does not report the follow-up as successfully queued
- **AND** the kernel does not silently create a second concurrent subagent run to handle the prompt

#### Scenario: completed subagent follow-up still resumes from transcript
- **GIVEN** a subagent has reached a terminal state and its transcript remains available
- **WHEN** the consumer invokes the built-in `agent` tool with that `agent_id` and a follow-up prompt
- **THEN** the kernel continues the existing subagent conversation from its transcript rather than creating an unrelated subagent identity

## MODIFIED Requirements

## REMOVED Requirements
