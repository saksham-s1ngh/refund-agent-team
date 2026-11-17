# Build Notes

## CLM-0001: validated RoutingDecision

Model: `particle-ai/particle-1:free` (provider: Particle AI). Only `claim_text` was sent; no label column reached the prompt.

```json
{
  "specialists": [
    "billing",
    "shipping",
    "stock"
  ],
  "reason": "The card was charged twice for the whole order, so billing is needed for the duplicate charge. Only one box arrived with the stroller and the car seat was not delivered, so shipping is needed for the missing/partial delivery. The seller page says the car seat is out of stock, so stock is needed for the unavailable item.",
  "confidence": 1.0
}
```

## Specialists vs label

| Specialist | Predicted | `label_specialists` |
|------------|-----------|---------------------|
| billing    | yes       | yes                 |
| shipping   | yes       | yes                 |
| stock      | yes       | yes                 |

Mismatches: none. The prediction matches `billing|shipping|stock` exactly.

## Does the reason hold up?

Holds up fully, and also addresses other issues (car seat out of stock).

## Screenshot

OpenRouter logs for the `claims-router` key, oldest at the bottom:

- **08:24–08:29 PM, Ling 3.2 Flash (Ant Digital):** CLM-0001 runs. Two used about 3,000 output tokens before `max_tokens` existed, then two stopped at the 500-token cap.
- **08:31 PM, Particle-1:** CLM-0001 validated (187 tokens).
- **08:49 PM, Particle-1, two rows at 500 tokens:** CLM-0002 failed twice before the prompt change.
- **09:03 PM and 09:11 PM, Particle-1 (128 and 108 tokens):** CLM-0002 and CLM-0001 validated on the first try after the prompt change.

![OpenRouter activity](activity.png)

## Router prompt (key part)

System prompt in `router.py`:

```
You route customer refund claims to specialists.
billing: charges, double charges, payment amounts.
shipping: missing, late, damaged or partial deliveries.
stock: out-of-stock or unavailable items.
Pick every specialist the claim needs.
The reason must cite concrete facts from the claim text.
Reply with one JSON object containing specialists, reason and confidence, keep reason under 40 words, and stop right after the closing brace.
```

The last sentence was added after CLM-0002 failed twice on `particle-ai/particle-1:free`: both replies left out `confidence`, never closed the object after a long `reason`, and filled the 500-token cap with blank lines. Naming every field, capping `reason`, and saying where to stop make a complete reply more likely, but the provider still doesn't enforce the schema, so validation and the single retry stay the real guard.

Rerun of CLM-0002 with the new sentence (one run, first attempt, finish reason `stop`):

```json
{
  "specialists": ["billing"],
  "reason": "Customer reports two charges for the same knife set and available balance dropped twice, needing one charge returned; this is a double-charge/payment amount issue.",
  "confidence": 0.99
}
```

Matches `label_specialists` (`billing`), with no extra or missing specialists.

### Does a shorter reason still tie each specialist to a fact?

Partly. Rerun of CLM-0001 with the 40-word cap (one run, first attempt):

```json
{
  "specialists": ["billing", "shipping", "stock"],
  "reason": "Card charged twice for whole order, only stroller box arrived, car seat missing, and seller page says car seat out of stock.",
  "confidence": 0.99
}
```

The reason dropped from 59 to 22 words and still has one fact for each specialist (double charge, missing car seat, out of stock). But the earlier long reason named the link outright ("so billing is needed for the duplicate charge"); the short one only lists the facts, so a reader has to infer which fact backs which specialist. Nothing in the prompt or schema requires the pairing yet.

The user message is the claim text only. The reply is constrained with `response_format` set to `json_schema` with `strict: true` using `RoutingDecision`'s schema, plus `provider.require_parameters: true` and `max_tokens=500`.

## Invalid replies: Pydantic errors and what route_claim does

From `.venv/bin/python test_router.py`. The API is mocked, so these are fixed test replies, not model output.

**Malformed reply** (`{"specialists": ["billing"], "reason": "Card charged twice."`, no closing brace):

```
1 validation error for RoutingDecision
  Invalid JSON: EOF while parsing an object at line 1 column 60 [type=json_invalid, input_value='{"specialists": ["billin...: "Card charged twice."', input_type=str]
```

**Confidence 1.5** (`{"specialists": ["billing"], "reason": "Card charged twice.", "confidence": 1.5}`):

```
1 validation error for RoutingDecision
confidence
  Input should be less than or equal to 1 [type=less_than_equal, input_value=1.5, input_type=float]
```

**What route_claim does next**, the same for both:

- If the next reply is valid, it retries once and returns that reply: `{"specialists":["billing"],"reason":"Card charged twice.","confidence":0.9}`.
- If the second reply is also invalid, it stops after 2 calls and raises `ValueError: Model returned an invalid RoutingDecision twice:`, followed by both Pydantic errors and both raw replies. It never falls back to a default decision.

## Confidence and human review

Confidence is the router's self-rated certainty in its specialist set; any decision below a set threshold (e.g. 0.7) goes to a human before specialists act.

## Deliberate schema choice

specialists is a non-empty list, not one value, because claims like CLM-0001 mix billing, shipping and stock; the graph fans out to every listed specialist and merges their answers.

## What I checked or changed

Added require_parameters and max_tokens after a free model ignored strict JSON schema, then switched models until CLM-0001 validated; checked that only claim_text reached the prompt and no label column leaked into it.
