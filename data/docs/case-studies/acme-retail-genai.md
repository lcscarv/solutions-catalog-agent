# Case study: GenAI product description generator (Acme Retail)

## Context
Acme Retail sells 40,000 SKUs online. Product descriptions were written by hand,
took around 12 minutes each, and many products went live with no description.

## Approach
- An LLM generates a draft from the product attributes and two reference examples
  per category.
- Brand rules (tone, forbidden claims, length) are checked in code after generation.
- A merchandiser approves or edits each draft in a review queue. Nothing is
  published without approval.
- Drafts that fail the rule check are regenerated once, then sent to review flagged.

## Results
- Average handling time dropped from 12 minutes to 3 minutes per product.
- Products without description fell from 18% to 2% in three months.
- 9% of drafts were rejected by reviewers, mostly for wrong material or size.

## Lessons
- Attributes in the source system were the main error source, not the model.
- The review queue was what made the business accept the rollout.
