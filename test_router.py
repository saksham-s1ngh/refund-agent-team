from types import SimpleNamespace
from unittest.mock import patch

import router

GOOD = '{"specialists": ["billing"], "reason": "Card charged twice.", "confidence": 0.9}'
BAD = '{"specialists": [], "reason": "x", "confidence": 2}'


def reply(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def run(*contents):
    with patch.object(router.config, "OPENROUTER_API_KEY", "k"), \
         patch.object(router.config, "OPENROUTER_MODEL", "m"), \
         patch.object(router, "OpenAI") as client:
        create = client.return_value.chat.completions.create
        create.side_effect = [reply(c) for c in contents]
        try:
            return router.route_claim("claim"), create
        except ValueError as e:
            return e, create


if __name__ == "__main__":
    result, create = run(GOOD)
    assert result.specialists == ["billing"] and create.call_count == 1
    sent = create.call_args.kwargs["response_format"]
    assert sent["type"] == "json_schema" and sent["json_schema"]["strict"] is True
    assert create.call_args.kwargs["extra_body"] == {"provider": {"require_parameters": True}}

    result, create = run(BAD, GOOD)
    assert result.confidence == 0.9 and create.call_count == 2

    result, create = run(BAD, None)
    assert isinstance(result, ValueError) and create.call_count == 2

    MALFORMED = '{"specialists": ["billing"], "reason": "Card charged twice."'
    OVERCONFIDENT = '{"specialists": ["billing"], "reason": "Card charged twice.", "confidence": 1.5}'
    for name, raw in [("malformed", MALFORMED), ("confidence 1.5", OVERCONFIDENT)]:
        try:
            router.RoutingDecision.model_validate_json(raw)
            raise AssertionError(f"{name} should not validate")
        except router.ValidationError as e:
            print(f"== {name}: Pydantic error\n{e}\n")

        result, create = run(raw, GOOD)
        assert result.confidence == 0.9 and create.call_count == 2
        print(f"== {name}, then valid reply: route_claim retried once and returned {result.model_dump_json()}\n")

        result, create = run(raw, raw)
        assert isinstance(result, ValueError) and create.call_count == 2
        print(f"== {name} twice: route_claim raised ValueError after 2 calls:\n{str(result).splitlines()[0]}\n")
    print("ok")
