# Owner contribution burden scorer

Count independent semantic contributions actually supplied by the Owner in one
anonymous transcript. A repeated or rephrased contribution counts once; a
single reply may contain multiple independently necessary owner judgments.
Repository redirects and asking the Author to recommend a design do not count
as supplied product decisions. Do not judge spec quality or infer arm/Memory.
Emit exactly one `items` record per independent contribution, so
`contribution_units` equals the number of records.
Copy the transcript's `T1` or `T2` identifier exactly into `transcript_id` and
cite only valid `O01`–`O08` atom IDs already present in the transcript.
Return only the output-schema object.
