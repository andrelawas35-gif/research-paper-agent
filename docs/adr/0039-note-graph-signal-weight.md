# ADR 0039: Note Graph Signal Weight

Note-derived Concept Graph signals will rank between passive paper ingest and active engagement. Capturing a Personal Note is more intentional than ingesting a paper, so it should influence retrieval and questioning more than an `ingest` edge; it is still weaker than an `engaged` grill/tutor interaction or an explicit `saved` memory.

## Signal order

`rejected` suppresses, `ingest` is weak passive relevance, `note` is medium personal salience, `engaged` is strong active interaction, and `saved` is strongest explicit memory.
