"""Harness-only Spine completion adapter using authenticated Codex CLI.

This measures Spine through Codex, not the original direct API backend. Each
completion is a fresh read-only session outside the target checkout. Codex's
agent instructions still add overhead. Spine alone applies returned file writes.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
import uuid
from pathlib import Path

import jsonschema
from orchestrator.core.llm.client import CompletionResult, LLMError, ToolCall

import harness_config as C
from codex_usage import PRICE_BASIS, cost, records, run_sessions, total


def strict_schema(schema):
    """Make optional fields nullable for Codex's strict structured-output schema."""
    import copy
    value = copy.deepcopy(schema)
    def visit(node):
        if isinstance(node, list):
            for item in node:
                visit(item)
        elif isinstance(node, dict):
            for item in list(node.values()):
                visit(item)
            if node.get("type") == "object":
                required = node.get("required", [])
                props = node.get("properties", {})
                for key in props:
                    if key not in required:
                        props[key] = {"anyOf": [props[key], {"type": "null"}]}
                node["required"] = list(props)
                node["additionalProperties"] = False
    visit(value)
    return value


def restore_optional(value, schema):
    if isinstance(value, dict):
        props = schema.get("properties", {})
        return {k: restore_optional(v, props.get(k, {})) for k, v in value.items()
                if not (v is None and k in props and k not in schema.get("required", []))}
    if isinstance(value, list):
        return [restore_optional(v, schema.get("items", {})) for v in value]
    return value


def output_contract(response_format=None, tools=None, tool_choice=None):
    """Use a tool's argument schema directly, with no tool execution by Codex."""
    if tools:
        if len(tools) != 1 or tool_choice != tools[0].name:
            raise LLMError("Codex adapter currently supports one forced output tool only")
        return tools[0].parameters, tools[0].name
    if response_format:
        return response_format.model_json_schema(), None
    # Intake requests arbitrary JSON; wrapping its serialized text avoids imposing
    # a new schema on dynamic dictionaries in Spine's output contract.
    return {"type": "object", "properties": {"text": {"type": "string"}},
            "required": ["text"], "additionalProperties": False}, None


async def complete(self, messages, *, model, response_format=None, json_object=False,
                   temperature=None, max_tokens=None, tools=None, tool_choice=None):
    if C.CODEX_AUTH != "app":
        raise LLMError("SPINE_BACKEND=codex requires CODEX_AUTH=app")
    if C.STOP.exists():
        raise LLMError(C.STOP.read_text())
    schema, tool_name = output_contract(response_format, tools, tool_choice)
    envelope = os.environ.get("CODEX_OUTPUT_MODE", "envelope") == "envelope" and bool(tool_name)
    call_id = uuid.uuid4().hex
    cwd = C.WORK_DIR / "completion-contexts" / call_id
    cwd.mkdir(parents=True)
    dest = Path(os.environ.get("CODEX_CALLS_DIR", str(C.RESULTS_DIR / "codex-calls"))) / call_id
    dest.mkdir(parents=True)
    schema_path = dest / "schema.json"
    wire_schema = output_contract()[0] if envelope else strict_schema(schema)
    schema_path.write_text(json.dumps(wire_schema))
    request = {"messages": [m.to_dict() for m in messages], "model": model,
               "json_object": json_object, "tool_choice": tool_choice,
               "temperature_requested": temperature, "max_tokens_requested": max_tokens}
    (dest / "request.json").write_text(json.dumps(request, indent=2))
    prompt = ("Act as a text completion component for Spine. Use only the supplied messages. "
              "Do not inspect files, run tools, delegate, or apply changes. Return the requested "
              "completion using the output schema. " +
              (f"Return the arguments for {tool_name}: {tools[0].description}. " if tool_name else
               "" if response_format else "Put the completion in the text field; if JSON is requested, text must contain valid serialized JSON. ") +
              "\nMessages (preserve their stated roles when interpreting them):\n" +
              json.dumps(request["messages"], ensure_ascii=False))
    if envelope:
        prompt += ("\nReturn the tool arguments as serialized JSON inside the output's text field. "
                   "The arguments must satisfy this schema:\n" + json.dumps(schema))
    cmd = ["codex", "exec", "--ignore-user-config", "--skip-git-repo-check", "--json",
           "--sandbox", "read-only", "-m", model, "--output-schema", str(schema_path),
           "-c", 'forced_login_method="chatgpt"', "-c", 'web_search="disabled"',
           "-c", f'model_reasoning_effort="{C.CODEX_REASONING_EFFORT}"',
           "-c", "project_doc_max_bytes=0"]
    for feature in ("shell_tool", "multi_agent", "apps", "plugins", "browser_use",
                    "computer_use", "image_generation", "memories", "shell_snapshot"):
        cmd += ["--disable", feature]
    cmd += ["-"]
    env = C.codex_env()
    started = time.time()
    timed_out = False
    with (dest / "events.jsonl").open("wb") as stdout, (dest / "stderr.txt").open("wb") as stderr:
        proc = await asyncio.create_subprocess_exec(*cmd, cwd=cwd, env=env,
            stdin=asyncio.subprocess.PIPE, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            timeout = (C.CODEX_COMPLETION_TIMEOUT_S if C.CODEX_COMPLETION_TIMEOUT_S is not None
                       else getattr(self, "_request_timeout", C.STEP_TIMEOUT_S))
            await asyncio.wait_for(proc.communicate(prompt.encode()), timeout=timeout)
        except TimeoutError:
            import signal
            timed_out = True
            os.killpg(proc.pid, signal.SIGTERM)
            await proc.wait()
        except asyncio.CancelledError:
            import signal
            os.killpg(proc.pid, signal.SIGTERM)
            await proc.wait()
            raise
    text_out = (dest / "events.jsonl").read_text()
    text_err = (dest / "stderr.txt").read_text()
    events = []
    for line in text_out.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue  # preserve a partial final line in the raw log after a timeout
    usage_records = records(C.CODEX_LOGIN_HOME, cwd)
    usage = total(usage_records)
    for f in run_sessions(C.CODEX_LOGIN_HOME, cwd):
        shutil.copy2(f, dest / f.name)
    metadata = {"backend": "codex-cli", "codex_auth": "app", "usage": usage,
                "response_ids": list(usage_records), "price_basis": PRICE_BASIS,
                "cost_usd": cost(model, usage), "model": model,
                "wall_s": time.time()-started, "exit_code": proc.returncode,
                "timeout_s": timeout,
                "timed_out": timed_out,
                "usage_complete": bool(usage_records) and not timed_out and proc.returncode == 0
                    and any(e.get("type") == "turn.completed" for e in events),
                "output_mode": "envelope" if envelope else "schema",
                "temperature_enforced": False, "max_tokens_enforced": False}
    (dest / "usage.json").write_text(json.dumps(metadata, indent=2))
    failures = [e for e in events if e.get("type") == "turn.failed"]
    if proc.returncode or failures or not any(e.get("type") == "turn.completed" for e in events):
        diagnostic = text_out[-4000:] + text_err[-2000:]
        if any(m in diagnostic.lower() for m in C.QUOTA_MARKERS):
            C.STOP.write_text(f"Codex quota failure; inspect {dest}\n")
        raise LLMError(f"Codex completion failed; inspect {dest}: {diagnostic[-1000:]}")
    forbidden = [e for e in events if e.get("type") in ("item.started", "item.completed")
                 and e.get("item", {}).get("type") not in ("agent_message", "reasoning")]
    if forbidden:
        raise LLMError(f"Codex used tools; result excluded from measurement: {dest}")
    if not usage["requests"]:
        raise LLMError(f"No per-response token ledger found: {dest}")
    messages_out = [e["item"]["text"] for e in events if e.get("type") == "item.completed"
                    and e.get("item", {}).get("type") == "agent_message"]
    try:
        value = json.loads(messages_out[-1])
        if envelope:
            value = json.loads(value["text"])
        value = restore_optional(value, schema)
        jsonschema.validate(value, schema)
        text_result = json.dumps(value) if tool_name or response_format else value["text"]
        if json_object:
            json.loads(text_result)
    except (ValueError, IndexError, KeyError, jsonschema.ValidationError) as exc:
        raise LLMError(f"Invalid structured response: {dest}: {exc}") from exc
    return CompletionResult(text=text_result, model=model, prompt_tokens=usage["input"],
        completion_tokens=usage["output"], cost_usd=metadata["cost_usd"],
        latency_ms=metadata["wall_s"]*1000, raw=metadata,
        tool_calls=(ToolCall(call_id, tool_name, value),) if tool_name else ())


def install():
    # Patch the existing class before factories/benchmark instantiate it. This also
    # preserves the intake recorder's wrapper around this exact class method.
    from orchestrator.core.llm.litellm_client import LiteLLMClient
    LiteLLMClient.complete = complete
