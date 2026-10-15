# Case study: Field technician assistant (Volt Energy)

## Context
Volt Energy operates wind farms. Technicians searched 600 PDF manuals and years of
work orders to diagnose turbine faults, often from a phone on site.

## Approach
- Retrieval over manuals and closed work orders, with the turbine model as a
  metadata filter so answers never mix models.
- Every answer cites the manual page or work order it came from.
- If no source passes a relevance threshold, the assistant says it does not know
  and suggests escalation.

## Results
- Median time to find the right procedure went from 25 minutes to 4 minutes.
- In a review of 200 answers, 91% were rated correct and complete by senior
  technicians; 6% were correct but incomplete.

## Lessons
- Metadata filtering by turbine model mattered more than the choice of embedding.
- Scanned manuals needed OCR cleanup before they were useful.
