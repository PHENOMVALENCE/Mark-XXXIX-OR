#web_search.py
from valence.log import get_logger
from valence.settings import LEGACY_KEYS_FILE, get_settings
from valence import models as valence_models

log = get_logger("actions.web_search")

API_CONFIG_PATH = LEGACY_KEYS_FILE


def _get_api_key() -> str:
    key = get_settings().gemini_api_key
    if not key:
        raise RuntimeError(
            "No Gemini API key configured. Set GEMINI_API_KEY in .env "
            "(copy .env.example) or run: python -m valence.doctor"
        )
    return key


def _gemini_search(query: str) -> str:
    from google import genai

    client   = genai.Client(api_key=_get_api_key())
    response = client.models.generate_content(
        model=valence_models.REASONING,
        contents=query,
        config={"tools": [{"google_search": {}}]},
    )

    text = ""
    for part in response.candidates[0].content.parts:
        if hasattr(part, "text") and part.text:
            text += part.text

    text = text.strip()
    if not text:
        raise ValueError("Gemini returned an empty response.")
    return text


def _ddg_search(query: str, max_results: int = 6) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS

    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title":   r.get("title",  ""),
                "snippet": r.get("body",   ""),
                "url":     r.get("href",   ""),
            })
    return results


def _format_ddg(query: str, results: list[dict]) -> str:
    if not results:
        return f"No results found for: {query}"

    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):   lines.append(f"{i}. {r['title']}")
        if r.get("snippet"): lines.append(f"   {r['snippet']}")
        if r.get("url"):     lines.append(f"   {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()

def _compare(items: list[str], aspect: str) -> str:
    query = (
        f"Compare {', '.join(items)} in terms of {aspect}. "
        "Give specific facts and data."
    )
    try:
        return _gemini_search(query)
    except Exception as e:
        log.warning("Gemini compare failed (%s) - falling back to DuckDuckGo.", e)

    # DDG fallback: fetch results per item and merge
    all_results: dict[str, list] = {}
    for item in items:
        try:
            all_results[item] = _ddg_search(f"{item} {aspect}", max_results=3)
        except Exception:
            all_results[item] = []

    lines = [f"Comparison — {aspect.upper()}", "─" * 40]
    for item in items:
        lines.append(f"\n▸ {item}")
        for r in all_results.get(item, [])[:2]:
            if r.get("snippet"):
                lines.append(f"  • {r['snippet']}")
    return "\n".join(lines)

def web_search(
    parameters:     dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    query  = params.get("query", "").strip()
    mode   = params.get("mode",  "search").lower().strip()
    items  = params.get("items", [])
    aspect = params.get("aspect", "general").strip() or "general"

    if not query and not items:
        return "Please provide a search query, sir."

    if items and mode != "compare":
        mode = "compare"

    if player:
        player.write_log(f"[Search] {query or ', '.join(items)}")

    log.info("Query: %r  Mode: %s", query, mode)

    if mode == "compare" and items:
        return _compare(items, aspect)

    try:
        from or_client import client
        result = client.chat(
            query,
            system="You are a web search assistant. Answer factually and concisely."
        )
        log.info("OpenRouter answered.")
        return result
    except Exception as primary_error:
        log.warning("OpenRouter failed (%s) - falling back to DuckDuckGo.", primary_error)

    # Separate try, not a nested one. Previously the fallback lived inside the
    # first handler with a second `except Exception` after it — which Python
    # never reaches, so a DuckDuckGo failure escaped web_search() entirely
    # instead of being reported to the user.
    try:
        results = _ddg_search(query)
        log.info("DuckDuckGo returned %d result(s).", len(results))
        return _format_ddg(query, results)
    except Exception as fallback_error:
        log.error("Every search backend failed: %s", fallback_error)
        return (
            f"I couldn't search for '{query}' — both the AI provider and the "
            "web search fallback are unavailable. This usually means there's "
            "no network connection or no provider is configured."
        )