"""Harness-only shim (NOT a product fix): lets Spine's unchanged LiteLLMClient call GPT-6 models.

Three incompatibilities, all found 2026-09-25 against litellm 1.97 and OpenAI's API:
  1. Spine sends `max_tokens`; GPT-6 accepts only `max_completion_tokens`.
  2. litellm rejects `reasoning_effort` for gpt-6-* client-side, although the API accepts it.
  3. OpenAI refuses function tools together with reasoning on /v1/chat/completions for
     gpt-6-astra ("use /v1/responses"). Spine talks Chat Completions to every model.
The shim wraps litellm.acompletion in-process and, for gpt-6 models only: renames (1), passes (2)
through via allowed_openai_params, and routes the call through litellm's Responses-API bridge
(`openai/responses/<model>`) for (3). Reasoning stays at Spine's configured effort. Every result
produced with it is labelled "with harness shim". Tracked as a product gap separately.
"""

from __future__ import annotations

import litellm

_acompletion = litellm.acompletion
APPLIED: dict[str, int] = {"renamed": 0}


async def _acompletion_gpt6(*args, **kwargs):  # type: ignore[no-untyped-def]
    model = str(kwargs.get("model", args[0] if args else ""))
    if model.split("/")[-1].startswith("gpt-6"):
        base = model.split("/")[-1]
        kwargs["model"] = f"openai/responses/{base}"
        APPLIED["responses_route"] = APPLIED.get("responses_route", 0) + 1
        if "max_tokens" in kwargs:
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
            APPLIED["renamed"] += 1
        # litellm 1.97 rejects reasoning_effort for gpt-6-* client-side although the API accepts it;
        # pass it through (not drop it) so the model runs at the effort Spine asked for.
        if "reasoning_effort" in kwargs:
            allowed = list(kwargs.get("allowed_openai_params") or [])
            if "reasoning_effort" not in allowed:
                allowed.append("reasoning_effort")
            kwargs["allowed_openai_params"] = allowed
            APPLIED["reasoning_effort_passed"] = APPLIED.get("reasoning_effort_passed", 0) + 1
    return await _acompletion(*args, **kwargs)


litellm.acompletion = _acompletion_gpt6
