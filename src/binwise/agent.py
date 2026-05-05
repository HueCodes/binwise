from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

import anthropic

MODEL = "claude-opus-4-7"

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "string", "description": "Identified item, including material if discernible"},
                    "bin": {
                        "type": "string",
                        "description": "Bin id from the city's bins list, or 'unknown' if not covered",
                    },
                    "prep": {"type": "string", "description": "Prep instruction, may be empty"},
                    "why": {"type": "string", "description": "One short sentence citing the rule that applies"},
                },
                "required": ["item", "bin", "prep", "why"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def _build_system_prompt(city: dict) -> str:
    """Build the prompt-cached system prompt from a v0.1 city file.

    The serialization is deterministic (sorted keys, fixed indent) so the
    prompt prefix is byte-stable across requests for the same city, which is
    the precondition for prompt-cache hits.
    """
    ruleset_json = json.dumps(city, sort_keys=True, indent=2, ensure_ascii=False)
    location = ", ".join(p for p in [city.get("name"), city.get("state"), city.get("country")] if p)
    return (
        f"You are a recycling sorting assistant for {location}.\n\n"
        "Your task: look at the user's image, identify each distinct item, and tell them which bin it goes in. "
        "Use ONLY the city ruleset below. Do NOT apply rules from other cities or general recycling intuition.\n\n"
        "Ruleset (binwise v0.1 schema):\n"
        f"{ruleset_json}\n\n"
        "Decision procedure for each item:\n"
        "1. If the item matches an entry in `edge_cases`, use that entry. Edge cases override the rules array.\n"
        "2. Otherwise, identify the item's material category. Match against the `category` field across `rules`, using the taxonomy aliases as guidance (e.g. a yogurt cup is `rigid_plastic_3_7`).\n"
        '3. If the matching rule has `bin: "depends"`, pick the `conditions` entry whose `if` text describes what you observe in the image (clean vs. soiled, fist-sized vs. small, intact vs. broken).\n'
        '4. If no rule covers the item, set `bin` to "unknown" and explain in `why`.\n\n'
        "Output: one entry per distinct item visible. `bin` must be one of the bin ids in the city's `bins` array "
        '(typically "recycling", "compost", "landfill", "hazardous", "special") or "unknown". '
        'Keep `why` to one short sentence that names the specific rule ("plastic-lined paper, not accepted in SF compost"), '
        "not general advice."
    )


def _encode_image(path: Path) -> tuple[str, str]:
    mime, _ = mimetypes.guess_type(path.name)
    if mime is None or not mime.startswith("image/"):
        mime = "image/jpeg"
    data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return mime, data


def sort_image(image_path: Path, rules: dict, *, client: anthropic.Anthropic | None = None) -> dict:
    """Send an image + city rules to Claude and return the parsed verdict.

    The system prompt (city rules) is prompt-cached, so repeated calls against
    the same city pay the cache write once and read on subsequent requests.
    """
    client = client or anthropic.Anthropic()
    mime, data = _encode_image(image_path)
    system_prompt = _build_system_prompt(rules)

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}},
                    {"type": "text", "text": "What is in this image and where does each item go?"},
                ],
            }
        ],
    )

    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise RuntimeError(f"No text block in response. stop_reason={response.stop_reason}")
    parsed = json.loads(text)

    return {
        "items": parsed["items"],
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0),
            "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
        },
    }
