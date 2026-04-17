"""
Thin wrapper around google-generativeai for the Mock Message Center.
All Gemini calls go through here — keeps the API key server-side only.
"""
import os
import google.generativeai as genai

_model = None


def _get_model():
    global _model
    if _model is None:
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        genai.configure(api_key=key)
        _model = genai.GenerativeModel("gemini-2.5-flash")
    return _model


def explain_term(term: str) -> str:
    """Return a plain-English 2-sentence definition of a health insurance term."""
    model = _get_model()
    prompt = (
        f"Explain '{term}' to a health insurance member in 2 sentences, "
        "plain English, no jargon. Be concise and helpful."
    )
    response = model.generate_content(prompt)
    return response.text.strip()


def ask_about_message(subject: str, body: str, category: str,
                      history: list, user_msg: str) -> str:
    """
    Multi-turn chat grounded in a specific message.
    history: list of {"role": "user"|"model", "parts": [str]} dicts
              (browser sends this back each turn).
    """
    model = _get_model()
    system_context = (
        f"You are a helpful assistant for a health insurance member. "
        f"The member is reading the following message:\n\n"
        f"Subject: {subject}\nCategory: {category}\n\n{body}\n\n"
        "Answer questions about this message clearly and concisely. "
        "If you're unsure, say so. Keep answers under 150 words."
    )
    # Build a chat with history
    chat = model.start_chat(history=history)
    # Prepend system context to the first user message if history is empty
    if not history:
        full_msg = f"{system_context}\n\nMember's question: {user_msg}"
    else:
        full_msg = user_msg
    response = chat.send_message(full_msg)
    return response.text.strip()
