from config import get_config

'''
Thin wrapper around the one supported model: Gemma via the Gemini API
(https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api). Non-thinking,
single generate_content call per turn -- the AI layer is stateless by design
(Notes-structuring_ideas.md), so multi-turn conversations are rendered into a
single prompt string each call instead of using server-side chat sessions.

Gemma has no system-instruction support on this endpoint, so the persona is
just the top of every prompt.

DECISION: if no gemma_api_key is configured, calls return a visible
"[AI disabled]" placeholder instead of erroring, so every flow in the apps can
be exercised end-to-end before you've set up the key.
'''

PERSONA = (
    "You are the voice of a personal accountability app. You are talking to its one user. "
    "Be concise (2-4 sentences), warm, and encouraging, but honest -- you push the user to "
    "follow through without ever being a jerk. Never use markdown formatting, just plain text. "
    "Do not invent tasks, data, or history beyond what is given to you."
)

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=get_config()["gemma_api_key"])
    return _client


def generate(prompt):
    """One prompt string in, one text reply out."""
    cfg = get_config()
    if not cfg["gemma_api_key"]:
        return "[AI disabled -- no gemma_api_key in server config.json. This is where the AI's reply would appear.]"
    response = _get_client().models.generate_content(
        model=cfg["gemma_model"],
        contents=f"{PERSONA}\n\n{prompt}",
    )
    return (response.text or "").strip()


def render_transcript(messages):
    """[{role: 'ai'|'user', text}] -> readable block for inclusion in a prompt."""
    lines = []
    for m in messages:
        who = "You (the app)" if m["role"] == "ai" else "User"
        lines.append(f"{who}: {m['text']}")
    return "\n".join(lines)


def chat_reply(messages):
    """Free-form chat screen. Client sends the whole transcript every call
    (nothing persisted server-side, per v1_design.md AI-chat decision)."""
    prompt = (
        "You are in a free-form chat with the user. The conversation so far:\n\n"
        f"{render_transcript(messages)}\n\n"
        "Write your next reply."
    )
    return generate(prompt)
