"""
Lets a buyer talk an RFx into existence instead of filling a form. Claude
drives the conversation (asks what's missing: category, line items,
quantities, questionnaire, commercial terms) and maintains a structured
draft via a tool call, so the UI always has something concrete to render
alongside the chat - not just prose.
"""
import os
import anthropic

MODEL = "claude-sonnet-5"

UPDATE_TOOL = {
    "name": "update_rfx_draft",
    "description": (
        "Replace the current RFx draft with an updated version reflecting everything "
        "decided in the conversation so far. Call this whenever new information changes "
        "the draft - new line items, quantity changes, questionnaire additions, terms "
        "changes. Always pass the FULL draft (not a diff)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "category": {"type": "string"},
            "scope": {"type": "string", "description": "1-3 sentence scope/context for vendors."},
            "currency_base": {"type": "string"},
            "commercial_terms": {
                "type": "object",
                "properties": {
                    "payment_terms": {"type": "string"},
                    "delivery_location": {"type": "string"},
                    "delivery_window": {"type": "string"},
                    "warranty_minimum": {"type": "string"},
                },
            },
            "questionnaire": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"q_id": {"type": "string"}, "question": {"type": "string"}, "type": {"type": "string"}},
                },
            },
            "line_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item_code": {"type": "string"},
                        "description": {"type": "string"},
                        "qty": {"type": "number"},
                        "unit": {"type": "string"},
                    },
                },
            },
        },
        "required": ["title", "category", "scope", "line_items"],
    },
}

SYSTEM_PROMPT = """You are an RFx co-pilot inside a procurement platform. A category buyer is
talking an RFx (request for quote) into existence with you instead of filling out a form by
hand. Have a short, efficient conversation: figure out the category, ask for (or propose,
then confirm) the line items with quantities, a short scope paragraph, a vendor questionnaire
(3-6 yes/no or short-answer questions covering things like OEM authorization, compliance
certs, delivery commitment), and commercial terms (payment terms, delivery location/window,
warranty minimum).

Don't interrogate the buyer with a giant intake form - propose sensible defaults for a
category buyer to confirm or edit, the way a sharp category manager colleague would. Keep
your spoken replies short. Every time the draft changes (even partially), call
update_rfx_draft with the FULL current draft state, not just the delta - the UI renders
directly from your tool call. Use item_code values like CAT-001, CAT-002 (CAT = a short
prefix derived from the category) in the order you add them."""


def _client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")
    return anthropic.Anthropic(api_key=api_key)


def copilot_turn(user_message: str, history: list, current_draft: dict | None):
    client = _client()
    messages = list(history)
    messages.append({"role": "user", "content": user_message})

    resp = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        tools=[UPDATE_TOOL],
        messages=messages,
    )
    messages.append({"role": "assistant", "content": resp.content})

    reply_text = "".join(b.text for b in resp.content if b.type == "text")
    new_draft = current_draft
    tool_use_blocks = [b for b in resp.content if b.type == "tool_use"]

    if tool_use_blocks:
        new_draft = tool_use_blocks[0].input
        # Claude expects a tool_result before we can send another user turn later,
        # so append a lightweight acknowledgement now.
        tool_results = [{"type": "tool_result", "tool_use_id": b.id, "content": "Draft updated."} for b in tool_use_blocks]
        messages.append({"role": "user", "content": tool_results})
        if not reply_text:
            # model may reply with just the tool call; ask it to also summarize
            resp2 = client.messages.create(
                model=MODEL, max_tokens=500, system=SYSTEM_PROMPT,
                tools=[UPDATE_TOOL], messages=messages,
            )
            messages.append({"role": "assistant", "content": resp2.content})
            reply_text = "".join(b.text for b in resp2.content if b.type == "text")

    return reply_text, new_draft, messages
