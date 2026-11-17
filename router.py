from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import config

SYSTEM_PROMPT = (
    "You route customer refund claims to specialists. "
    "billing: charges, double charges, payment amounts. "
    "shipping: missing, late, damaged or partial deliveries. "
    "stock: out-of-stock or unavailable items. "
    "Pick every specialist the claim needs. "
    "The reason must cite concrete facts from the claim text."
)


class RoutingDecision(BaseModel):
    # extra="forbid" emits additionalProperties: false, which strict mode requires.
    model_config = ConfigDict(extra="forbid")

    specialists: list[Literal["billing", "shipping", "stock"]] = Field(min_length=1)
    reason: str = Field(description="One or two short sentences citing facts from the claim.")
    confidence: float = Field(ge=0, le=1)


def route_claim(claim_text: str) -> RoutingDecision:
    if not config.OPENROUTER_API_KEY or not config.OPENROUTER_MODEL:
        raise RuntimeError("Set OPENROUTER_API_KEY and OPENROUTER_MODEL in the environment or .env")

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=config.OPENROUTER_API_KEY)
    errors = []
    for _ in range(2):  # first try + one retry
        response = client.chat.completions.create(
            model=config.OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": claim_text},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "RoutingDecision",
                    "strict": True,
                    "schema": RoutingDecision.model_json_schema(),
                },
            },
            # Cap output so a runaway reply fails fast instead of streaming filler.
            max_tokens=500,
            # Only route to providers that actually enforce response_format.
            extra_body={"provider": {"require_parameters": True}},
        )
        content = response.choices[0].message.content
        try:
            return RoutingDecision.model_validate_json(content or "")
        except ValidationError as e:
            errors.append(f"{e}\nRaw reply: {content!r}")

    raise ValueError("Model returned an invalid RoutingDecision twice:\n" + "\n---\n".join(errors))
