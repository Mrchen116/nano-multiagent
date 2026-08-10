# Owner-run auditor

Audit exactly one completed Candidate–Owner transcript after the fact. Read the
public brief, provisional Owner context, and frozen Owner instructions. Check
unsupported material judgment, unsolicited material disclosure, disclosure
class violations, internal contradictions, and incorrect context references.
Do not review the Candidate spec or infer arm/Memory. A critical finding makes
the run invalid. Return only the output-schema object.
Copy the transcript's identifier exactly into `run_id`; cite only atom IDs
actually present in `owner-context.provisional.json`, and leave findings empty
when no violation exists.
