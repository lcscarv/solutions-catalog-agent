# GenAI ROI calculator: how to use it

## Inputs
- Monthly volume of the task (documents, tickets, products).
- Current handling time per item, in minutes.
- Expected handling time with the assistant, including human review.
- Loaded hourly cost of the team doing the task.
- Monthly run cost: model tokens, infrastructure and support.

## Formula
Monthly savings = volume x (current time - new time) / 60 x hourly cost.
Net monthly benefit = monthly savings - monthly run cost.
Payback in months = one-off project cost / net monthly benefit.

## Guidance
- Use the median handling time, not the average, when outliers exist.
- Always include review time in the new handling time; it is the most common
  mistake in GenAI business cases.
- Present a conservative and an expected scenario, never a single number.
