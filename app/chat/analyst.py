"""
The "stop clicking, start asking" layer. Claude gets a tool that lets it run
real pandas queries against the normalized comparison table (and vendor
metadata / questionnaire answers), so it can actually answer compound asks
like "cheapest per line, but only among vendors who cleared the quality
questionnaire" instead of us hardcoding that one demo question.
"""
import json
import os
import pandas as pd
import anthropic

MODEL = "claude-sonnet-5"

TOOLS = [
    {
        "name": "run_pandas_query",
        "description": (
            "Execute a short pandas expression or a few statements against the comparison "
            "dataset to answer the buyer's question. Two variables are available: `df` "
            "(the normalized line-item comparison table, one row per vendor per matched "
            "RFx line item) and `vendor_meta` (a dict keyed by vendor_name with "
            "questionnaire_answers, commercial_terms, extraction_warnings, vendor_ref). "
            "Assign your final answer to a variable called `result` (a DataFrame, Series, "
            "dict, list, or plain value). Variables you define here (including `result`) "
            "persist and are available in your next run_pandas_query call within this same "
            "turn - use this to build up multi-step analysis incrementally rather than "
            "recomputing everything each time. Use pandas idioms freely - groupby, "
            "sort_values, idxmin, merge, etc. df columns: vendor_name, item_code, "
            "rfx_description, qty_requested, qty_quoted, qty_gap, unit_price_inr, "
            "unit_basis, box_size, match_confidence, needs_buyer_review, review_reason, "
            "carried_forward, notes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code, using df/vendor_meta/pd, ending by setting `result`."}
            },
            "required": ["code"],
        },
    }
]

SYSTEM_PROMPT = """You are a procurement analyst assistant. You are working over a comparison
table Aerchain built from five vendors' RFx responses for an IT hardware refresh. Buyers will
ask you natural-language questions - simple lookups, cross-vendor comparisons, conditional
splits ("cheapest per line among vendors who passed the quality questionnaire"), and questions
about data quality ("which lines am I most exposed on"). Use the run_pandas_query tool to
actually compute answers from the real data - never guess or state a number you have not
verified via the tool.

Ground rules:
- If a line has needs_buyer_review=True or carried_forward=True, mention that when it's
  relevant to the buyer's question - don't let a flagged, uncertain number look identical to
  a solid one in a recommendation.
- If the buyer's question implies eligibility criteria not explicitly captured as a column
  (e.g. "cleared the quality questionnaire"), derive it from vendor_meta's
  questionnaire_answers yourself, state in your answer what rule you applied (e.g. which
  questions and what counted as a pass), and say so plainly since it's a judgment call the
  buyer should be able to override.
- Variables you set in one run_pandas_query call DO persist and are available in your next
  call within this same turn - you can build up an analysis step by step (e.g. compute an
  eligibility list first, then filter using it in a later call) rather than redoing
  everything in one query.
- Prefer running one well-constructed query over many small ones, but do run more than one
  if the question genuinely needs multiple steps.
- For open-ended or subjective questions ("which vendor is best", "who should I pick"), there
  is no single correct metric - don't try to compute one score that decides it. Instead, run
  ONE query that builds a small per-vendor summary table (things like: coverage % of RFx lines
  quoted, count of lines needing buyer review, count of carried-forward lines, and a simple
  price-competitiveness measure such as how often that vendor is cheapest per line or their
  average rank), then reason about the trade-offs in prose and give a recommendation with your
  reasoning stated plainly so the buyer can weigh it differently if they want to.
- After you have the answer, respond in plain prose (with a short table if it helps) - do not
  dump raw JSON at the buyer.
- If the data can't answer the question (nothing matched, all flagged, etc.), say that plainly
  rather than forcing an answer.
"""


def _client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")
    return anthropic.Anthropic(api_key=api_key)


def _safe_exec(code: str, persistent_env: dict):
    allowed_builtins = {
        "len": len, "sum": sum, "min": min, "max": max, "sorted": sorted,
        "round": round, "range": range, "list": list, "dict": dict, "set": set,
        "str": str, "float": float, "int": int, "bool": bool, "abs": abs,
        "enumerate": enumerate, "zip": zip, "any": any, "all": all,
    }
    global_env = {"__builtins__": allowed_builtins}
    exec(code, global_env, persistent_env)
    return persistent_env.get("result", "No `result` variable was set.")


def _stringify_result(result):
    if isinstance(result, pd.DataFrame):
        return result.to_string(max_rows=60)
    if isinstance(result, pd.Series):
        return result.to_string()
    try:
        return json.dumps(result, indent=2, default=str)
    except TypeError:
        return str(result)


def ask_analyst(question: str, df: pd.DataFrame, vendor_meta: dict, history=None) -> tuple[str, list]:
    """Runs one turn of the analyst chat. Returns (answer_text, updated_history)."""
    client = _client()
    messages = list(history) if history else []
    messages.append({"role": "user", "content": question})

    # Persists across every tool call within THIS turn, so the model can
    # build up intermediate results (an eligibility list, a summary table)
    # step by step instead of starting from scratch each call.
    persistent_env = {"df": df, "vendor_meta": vendor_meta, "pd": pd}

    trace = []
    for _ in range(8):  # cap tool-use loop
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text")
            return text, messages

        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            code = block.input.get("code", "")
            trace.append(code)
            try:
                result = _safe_exec(code, persistent_env)
                output = _stringify_result(result)
            except Exception as e:
                output = f"ERROR running query: {e}"
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output[:6000],
            })
        messages.append({"role": "user", "content": tool_results})

    return "I ran out of steps trying to answer that - try breaking the question into smaller parts.", messages
