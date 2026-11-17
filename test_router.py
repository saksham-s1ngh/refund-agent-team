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
    print("ok")
