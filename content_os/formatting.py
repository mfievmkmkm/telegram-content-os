import html
import re


SOURCE_LINE = re.compile(
    r"^\s*(?:источник|source|ссылка|подробнее)\s*:\s*.*$",
    re.IGNORECASE,
)


def clean_generated_post(value: str) -> str:
    """Normalize model output and never expose internal research links."""
    text = (value or "").strip()
    text = re.sub(r"^```(?:html|markdown)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    lines = [line for line in text.splitlines() if not SOURCE_LINE.match(line)]
    text = "\n".join(lines)
    text = re.sub(r"(?m)^\s*https?://\S+\s*$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def telegram_html(value: str) -> str:
    """Render a small, safe subset of model formatting as Telegram HTML."""
    text = clean_generated_post(value)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", text)
    escaped = html.escape(text, quote=False)
    for tag in ("b", "strong", "i", "em", "u", "s", "blockquote"):
        escaped = re.sub(
            rf"&lt;(/?){tag}&gt;",
            lambda match: f"<{match.group(1)}{tag}>",
            escaped,
            flags=re.IGNORECASE,
        )
    return escaped


def plain_text(value: str) -> str:
    return re.sub(r"<[^>]+>", "", clean_generated_post(value))


EMOJI_SETS = {
    "liga": ("⚡", "🧠", "⚽", "🔥", "🎯", "🥶", "👀"),
    "gifts": ("💎", "📉", "🎁", "🔥", "🧠", "👀", "⚠️"),
}


def decorate_post(value: str, channel_key: str) -> str:
    """Guarantee readable emphasis and emoji anchors even when the LLM ignores markup."""
    text=plain_text(value)
    text=re.sub(r"\*\*|__|(?<!\*)\*(?!\*)", "", text)
    paragraphs=[part.strip() for part in re.split(r"\n\s*\n",text) if part.strip()]
    if not paragraphs: return text
    emojis=EMOJI_SETS.get(channel_key,EMOJI_SETS["liga"])
    paragraphs[0]=f"{emojis[0]} <b>{paragraphs[0]}</b>"
    if len(paragraphs)>2:
        paragraphs[1]=f"{emojis[1]} {paragraphs[1]}"
        paragraphs[-2]=f"{emojis[3]} <i>{paragraphs[-2]}</i>"
    elif len(paragraphs)==2:
        paragraphs[1]=f"{emojis[1]} <i>{paragraphs[1]}</i>"
    last=paragraphs[-1]
    if not last.startswith(emojis): paragraphs[-1]=f"{emojis[2]} {last}"
    return "\n\n".join(paragraphs)
