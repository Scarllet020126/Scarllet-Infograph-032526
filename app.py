import os
import io
import re
import json
import time
import base64
import random
import textwrap
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import streamlit as st

# Optional deps
try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # type: ignore

try:
    import requests  # type: ignore
except Exception as e:
    st.error("Missing dependency: requests. Please add it to requirements.txt")
    raise

# Optional PDF parsers
PDF_BACKEND = None
try:
    import pdfplumber  # type: ignore

    PDF_BACKEND = "pdfplumber"
except Exception:
    try:
        from PyPDF2 import PdfReader  # type: ignore

        PDF_BACKEND = "pypdf2"
    except Exception:
        PDF_BACKEND = None

# Optional plotting
try:
    import plotly.graph_objects as go  # type: ignore
except Exception:
    go = None  # type: ignore


# -----------------------------
# Constants / Config
# -----------------------------

APP_TITLE_EN = "WOW Multi-Agent Insight Studio"
APP_TITLE_ZH = "WOW 多代理洞察工作室"

LANG_EN = "English"
LANG_ZH = "繁體中文"

MODE_INSIGHTS = "Insights Generator"
MODE_NOTES = "AI Note Keeper"
MODE_MEDICAL = "Medical Regulation WOW"

PROVIDERS = ["Gemini", "OpenAI", "Anthropic", "Grok"]

MODEL_CATALOG = {
    "OpenAI": ["gpt-4o-mini", "gpt-4.1-mini"],
    "Gemini": [
        "gemini-2.5-flash",
        "gemini-3-flash-preview",
        "gemini-2.5-flash-lite",
        "gemini-3-pro-preview",
    ],
    "Anthropic": ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"],
    "Grok": ["grok-4-fast-reasoning", "grok-3-mini"],
}

DEFAULT_MAX_TOKENS = 12000
DEFAULT_TEMPERATURE = 0.2

ENV_KEY_MAP = {
    "Gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    "OpenAI": ["OPENAI_API_KEY"],
    "Anthropic": ["ANTHROPIC_API_KEY"],
    "Grok": ["GROK_API_KEY", "XAI_API_KEY"],
}

# Grok (xAI) is OpenAI-compatible in many setups
GROK_OPENAI_BASE_URL = os.environ.get("GROK_BASE_URL", "https://api.x.ai/v1")

# Painter styles (20)
PAINTER_STYLES = {
    "Monet": {"primary": "#7AA6C2", "accent": "#F2D0A7", "bg": "#F7F7FB", "fg": "#1D2433"},
    "Van Gogh": {"primary": "#2A4B9B", "accent": "#F2C14E", "bg": "#0E1B3D", "fg": "#F5F7FF"},
    "Picasso": {"primary": "#1C1C1C", "accent": "#E63946", "bg": "#FAFAFA", "fg": "#161616"},
    "Klimt": {"primary": "#B8860B", "accent": "#2E2A24", "bg": "#FFF8E1", "fg": "#1F1B16"},
    "Hokusai": {"primary": "#1D3557", "accent": "#457B9D", "bg": "#F1FAEE", "fg": "#0B1320"},
    "Frida Kahlo": {"primary": "#2A9D8F", "accent": "#E76F51", "bg": "#FFF3E6", "fg": "#1F2937"},
    "Dali": {"primary": "#6D28D9", "accent": "#F97316", "bg": "#0B1020", "fg": "#F8FAFC"},
    "Pollock": {"primary": "#111827", "accent": "#22C55E", "bg": "#0B0F19", "fg": "#E5E7EB"},
    "Rothko": {"primary": "#7F1D1D", "accent": "#F59E0B", "bg": "#FEF2F2", "fg": "#111827"},
    "Magritte": {"primary": "#0F172A", "accent": "#38BDF8", "bg": "#F8FAFC", "fg": "#0F172A"},
    "Matisse": {"primary": "#2563EB", "accent": "#F43F5E", "bg": "#FFF7ED", "fg": "#111827"},
    "Rembrandt": {"primary": "#92400E", "accent": "#FDE68A", "bg": "#1C1917", "fg": "#FAFAF9"},
    "Vermeer": {"primary": "#1E3A8A", "accent": "#FBBF24", "bg": "#EFF6FF", "fg": "#0F172A"},
    "Turner": {"primary": "#F97316", "accent": "#0EA5E9", "bg": "#FFF7ED", "fg": "#0F172A"},
    "Mondrian": {"primary": "#DC2626", "accent": "#2563EB", "bg": "#FFFFFF", "fg": "#111827"},
    "Georgia O’Keeffe": {"primary": "#7C3AED", "accent": "#84CC16", "bg": "#FAF5FF", "fg": "#111827"},
    "Edward Hopper": {"primary": "#334155", "accent": "#F59E0B", "bg": "#F8FAFC", "fg": "#0F172A"},
    "Yayoi Kusama": {"primary": "#EF4444", "accent": "#111827", "bg": "#FFF1F2", "fg": "#111827"},
    "Basquiat": {"primary": "#0EA5E9", "accent": "#FDE047", "bg": "#0B0F19", "fg": "#F8FAFC"},
    "Ukiyo-e Classic": {"primary": "#0F4C5C", "accent": "#E36414", "bg": "#F6FFF8", "fg": "#0B1320"},
}

STYLE_NAMES = list(PAINTER_STYLES.keys())


# -----------------------------
# Utilities
# -----------------------------

def safe_get_env_key(provider: str) -> Optional[str]:
    for k in ENV_KEY_MAP.get(provider, []):
        v = os.environ.get(k)
        if v:
            return v
    return None


def init_session_state():
    ss = st.session_state
    ss.setdefault("lang", LANG_EN)
    ss.setdefault("theme", "Light")
    ss.setdefault("style_name", "Monet")
    ss.setdefault("mode", MODE_MEDICAL)
    ss.setdefault("max_tokens", DEFAULT_MAX_TOKENS)
    ss.setdefault("temperature", DEFAULT_TEMPERATURE)

    # user-provided keys (only used if env key missing)
    ss.setdefault("api_keys", {p: "" for p in PROVIDERS})

    # agent configs & artifacts
    ss.setdefault("agents", [])
    ss.setdefault("agent_configs", {})  # agent_id -> config
    ss.setdefault("artifacts", [])  # timeline of dicts
    ss.setdefault("current_inputs", {})  # agent_id -> input text
    ss.setdefault("current_outputs", {})  # agent_id -> output text
    ss.setdefault("committed_outputs", {})  # agent_id -> committed output text
    ss.setdefault("pipeline_status", "Idle")
    ss.setdefault("pipeline_active_agent", None)
    ss.setdefault("metrics", {"calls": 0, "errors": 0, "total_seconds": 0.0})

    # medical workflow artifacts
    ss.setdefault("medical_source_text", "")
    ss.setdefault("medical_doc_md", "")
    ss.setdefault("medical_tables", [])
    ss.setdefault("medical_entities", [])
    ss.setdefault("medical_infographics", [])
    ss.setdefault("medical_report_html", "")

    # note keeper
    ss.setdefault("note_raw", "")
    ss.setdefault("note_md", "")
    ss.setdefault("note_keywords", [])
    ss.setdefault("note_keyword_color", "coral")

    # UI toggles
    ss.setdefault("show_raw_json", False)


def tr(en: str, zh: str) -> str:
    return en if st.session_state.lang == LANG_EN else zh


def inject_theme_css(theme: str, style_name: str):
    style = PAINTER_STYLES.get(style_name, PAINTER_STYLES["Monet"])
    bg = "#0B0F19" if theme == "Dark" else style["bg"]
    fg = "#F8FAFC" if theme == "Dark" else style["fg"]
    primary = style["primary"]
    accent = style["accent"]

    # Simple CSS that works in Streamlit. Keeps things consistent.
    css = f"""
    <style>
      :root {{
        --wow-bg: {bg};
        --wow-fg: {fg};
        --wow-primary: {primary};
        --wow-accent: {accent};
        --wow-card: rgba(255,255,255,0.06);
        --wow-border: rgba(148,163,184,0.25);
        --wow-muted: rgba(148,163,184,0.85);
      }}
      .stApp {{
        background: var(--wow-bg);
        color: var(--wow-fg);
      }}
      h1, h2, h3, h4 {{
        color: var(--wow-fg);
      }}
      .wow-card {{
        border: 1px solid var(--wow-border);
        border-radius: 14px;
        padding: 14px 16px;
        background: var(--wow-card);
      }}
      .wow-pill {{
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        border: 1px solid var(--wow-border);
        color: var(--wow-fg);
        background: rgba(15,23,42,0.15);
        font-size: 12px;
      }}
      .wow-accent {{
        color: var(--wow-accent);
        font-weight: 700;
      }}
      .wow-primary {{
        color: var(--wow-primary);
        font-weight: 700;
      }}
      /* Make Streamlit widgets look less default-ish */
      section[data-testid="stSidebar"] {{
        border-right: 1px solid var(--wow-border);
      }}
      /* Links */
      a {{
        color: var(--wow-accent) !important;
      }}
      /* Tables */
      .stMarkdown table {{
        border-collapse: collapse;
        width: 100%;
      }}
      .stMarkdown th, .stMarkdown td {{
        border: 1px solid var(--wow-border);
        padding: 8px 10px;
      }}
      .stMarkdown th {{
        background: rgba(2, 6, 23, 0.25);
      }}
      /* Code blocks */
      pre {{
        border: 1px solid var(--wow-border) !important;
        border-radius: 12px !important;
      }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def jackpot_style():
    st.session_state.style_name = random.choice(STYLE_NAMES)


def bytes_to_text(b: bytes) -> str:
    # Best-effort decoding
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode("utf-8", errors="replace")


def extract_pdf_text(file_bytes: bytes) -> str:
    if PDF_BACKEND is None:
        raise RuntimeError("No PDF parser available. Add pdfplumber or PyPDF2 to requirements.txt.")

    if PDF_BACKEND == "pdfplumber":
        import pdfplumber  # type: ignore

        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                t = page.extract_text() or ""
                if t.strip():
                    text_parts.append(f"\n\n[Page {i}]\n{t}")
        return "\n".join(text_parts).strip()

    # PyPDF2 fallback
    from PyPDF2 import PdfReader  # type: ignore

    reader = PdfReader(io.BytesIO(file_bytes))
    text_parts = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        if t.strip():
            text_parts.append(f"\n\n[Page {i}]\n{t}")
    return "\n".join(text_parts).strip()


def strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        # remove first fence line and last fence if present
        s = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", s)
        s = re.sub(r"\n```$", "", s)
    return s.strip()


def extract_json_substring(s: str) -> str:
    """
    Robustly extract the first JSON object/array from a messy model output.
    """
    s = strip_code_fences(s)
    # Find first '{' or '['
    m = re.search(r"[\{\[]", s)
    if not m:
        return s
    start = m.start()
    # naive balancing for {} or []
    opener = s[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    for i in range(start, len(s)):
        ch = s[i]
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return s[start:]


def safe_json_loads(s: str) -> Any:
    s2 = extract_json_substring(s)
    try:
        return json.loads(s2)
    except Exception:
        # Attempt minor repairs (trailing commas)
        s3 = re.sub(r",(\s*[}\]])", r"\1", s2)
        return json.loads(s3)


def now_ts() -> float:
    return time.time()


def add_artifact(artifact_type: str, title: str, content: str, meta: Optional[Dict[str, Any]] = None):
    st.session_state.artifacts.append(
        {
            "ts": now_ts(),
            "type": artifact_type,
            "title": title,
            "content": content,
            "meta": meta or {},
        }
    )


def html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def highlight_keywords_markdown(md: str, keywords: List[str], color: str = "coral") -> str:
    """
    Highlight keywords using inline HTML spans. Avoid changing inside fenced code blocks.
    This is best-effort; for strict safety, implement a markdown AST renderer.
    """
    if not keywords:
        return md

    # Split by code fences to avoid highlighting code
    parts = re.split(r"(```.*?```)", md, flags=re.DOTALL)
    out = []

    # Sort longer first to reduce nested partial replacements
    kws = sorted({k.strip() for k in keywords if k.strip()}, key=len, reverse=True)
    if not kws:
        return md

    for part in parts:
        if part.startswith("```") and part.endswith("```"):
            out.append(part)
            continue

        replaced = part
        for kw in kws:
            # word-boundary-ish match, but allow medical terms with hyphens
            pattern = re.compile(rf"(?i)(?<![\w-])({re.escape(kw)})(?![\w-])")
            replaced = pattern.sub(rf"<span style='color:{color}; font-weight:700'>\1</span>", replaced)
        out.append(replaced)

    return "".join(out)


# -----------------------------
# Provider Adapters
# -----------------------------

class LLMError(RuntimeError):
    pass


def resolve_api_key(provider: str) -> Tuple[Optional[str], str]:
    """
    Returns (key, source) where source is 'env' | 'user' | 'missing'
    """
    env_key = safe_get_env_key(provider)
    if env_key:
        return env_key, "env"
    user_key = st.session_state.api_keys.get(provider, "").strip()
    if user_key:
        return user_key, "user"
    return None, "missing"


def http_post_json(url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: int = 120) -> Dict[str, Any]:
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code >= 400:
        raise LLMError(f"HTTP {resp.status_code}: {resp.text[:1000]}")
    return resp.json()


def call_openai_like_chat(
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: float,
    base_url: str = "https://api.openai.com/v1",
) -> str:
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    data = http_post_json(url, headers, payload)
    try:
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise LLMError(f"Malformed OpenAI-like response: {e}; data={str(data)[:500]}")


def call_anthropic_messages(
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> str:
    """
    Use Anthropics Messages API via HTTP to avoid SDK dependency.
    """
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    # Convert OpenAI-like messages into Anthropic format
    sys_parts = [m["content"] for m in messages if m["role"] == "system"]
    system_text = "\n".join(sys_parts).strip() if sys_parts else None
    user_parts = []
    for m in messages:
        if m["role"] == "user":
            user_parts.append(m["content"])
        elif m["role"] == "assistant":
            # include prior assistant messages as context
            user_parts.append(f"[Assistant]\n{m['content']}")
    user_text = "\n\n".join(user_parts).strip() if user_parts else ""

    payload: Dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": user_text}],
    }
    if system_text:
        payload["system"] = system_text

    data = http_post_json(url, headers, payload)
    try:
        # Anthropic returns content as list of blocks
        blocks = data.get("content", [])
        texts = []
        for b in blocks:
            if b.get("type") == "text":
                texts.append(b.get("text", ""))
        return "\n".join(texts).strip()
    except Exception as e:
        raise LLMError(f"Malformed Anthropic response: {e}; data={str(data)[:500]}")


def call_gemini_generate(
    api_key: str,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """
    Gemini via HTTP (Generative Language API).
    """
    # Many deployments use: https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key=...
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    data = http_post_json(url, headers, payload)
    try:
        cand = data["candidates"][0]
        parts = cand["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()
    except Exception as e:
        raise LLMError(f"Malformed Gemini response: {e}; data={str(data)[:500]}")


def call_llm(
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
) -> str:
    api_key, source = resolve_api_key(provider)
    if not api_key:
        raise LLMError(f"Missing API key for {provider}. Provide it in the sidebar (env not found).")

    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append({"role": "user", "content": user_prompt.strip()})

    if provider == "OpenAI":
        return call_openai_like_chat(api_key, model, messages, max_tokens, temperature)
    if provider == "Grok":
        return call_openai_like_chat(api_key, model, messages, max_tokens, temperature, base_url=GROK_OPENAI_BASE_URL)
    if provider == "Anthropic":
        return call_anthropic_messages(api_key, model, messages, max_tokens, temperature)
    if provider == "Gemini":
        # Gemini HTTP expects a single prompt; include system prompt inline
        merged = (system_prompt.strip() + "\n\n" + user_prompt.strip()).strip() if system_prompt.strip() else user_prompt.strip()
        return call_gemini_generate(api_key, model, merged, max_tokens, temperature)

    raise LLMError(f"Unknown provider: {provider}")


def call_llm_with_retry(*args, retries: int = 2, backoff: float = 1.8, **kwargs) -> str:
    last_err = None
    for attempt in range(retries + 1):
        try:
            start = now_ts()
            out = call_llm(*args, **kwargs)
            st.session_state.metrics["calls"] += 1
            st.session_state.metrics["total_seconds"] += (now_ts() - start)
            return out
        except Exception as e:
            last_err = e
            st.session_state.metrics["errors"] += 1
            if attempt < retries:
                time.sleep((backoff ** attempt) + random.random() * 0.25)
            else:
                raise
    raise last_err  # type: ignore


# -----------------------------
# Agent definitions
# -----------------------------

@dataclass
class AgentDef:
    agent_id: str
    name: str
    description: str
    default_system: str
    default_user_template: str
    output: str  # "text" | "markdown" | "json"
    mode: str


def default_agents() -> List[AgentDef]:
    return [
        # Insights mode (kept, simplified)
        AgentDef(
            "ins_ingest",
            "Ingestion & Cleanup",
            "Clean and normalize the input; preserve key facts; remove boilerplate.",
            "You are a careful editor. Do not add facts.",
            "INPUT:\n{input}\n\nTASK:\nClean and normalize. Output plain text only.",
            "text",
            MODE_INSIGHTS,
        ),
        AgentDef(
            "ins_extract",
            "Topic Extraction (Bilingual)",
            "Extract key topics in EN + zh-TW as JSON.",
            "Return valid JSON only. No code fences.",
            "From the INPUT, extract 10-20 topics.\nReturn JSON array with keys: topic_id,title_en,title_zh,summary_en,summary_zh,why_it_matters_en(list),why_it_matters_zh(list).\n\nINPUT:\n{input}",
            "json",
            MODE_INSIGHTS,
        ),
        AgentDef(
            "ins_plan",
            "Infographic Planner",
            "Assign chart types and data points; return JSON.",
            "Return valid JSON only. No code fences.",
            "Given topics JSON, add for each: suggested_infographic_type and a small data array of label/value in EN/ZH.\nReturn the full enriched JSON.\n\nTOPICS_JSON:\n{input}",
            "json",
            MODE_INSIGHTS,
        ),
        AgentDef(
            "ins_qa",
            "QA & Follow-up Questions",
            "Validate, improve clarity, generate 20 follow-up questions bilingual.",
            "Return valid JSON only. No code fences.",
            "Given the enriched topics JSON, return JSON object: {topics:[...], follow_up_questions:[{question_en,question_zh} x20]}.\nFix inconsistencies and ensure translations are Traditional Chinese.\n\nINPUT:\n{input}",
            "json",
            MODE_INSIGHTS,
        ),

        # Note Keeper mode
        AgentDef(
            "note_transform",
            "Note → Organized Markdown",
            "Turn raw notes into organized markdown and suggest keywords.",
            "Do not invent events or decisions. Preserve meaning.",
            "Transform the NOTE into organized markdown.\nInclude: Title, Summary bullets, Sections, Action Items, Open Questions.\nAlso output a line 'KEYWORDS:' followed by 8-15 keywords.\n\nNOTE:\n{input}",
            "markdown",
            MODE_NOTES,
        ),
        AgentDef(
            "note_magic",
            "AI Magic (General)",
            "Apply a selected transformation to the current note.",
            "Keep content faithful. Return markdown only.",
            "{input}\n\nINSTRUCTION:\n{instruction}\n\nReturn markdown only.",
            "markdown",
            MODE_NOTES,
        ),

        # Medical mode
        AgentDef(
            "med_ingest",
            "Medical Doc Ingestion",
            "Normalize extracted text, keep citations like [Page X].",
            "You are a compliance editor. Do not add facts.",
            "Clean the INPUT, keep structure hints and page anchors like [Page 3].\n\nINPUT:\n{input}",
            "text",
            MODE_MEDICAL,
        ),
        AgentDef(
            "med_reorg",
            "Reorganize to 3000–4000 word Markdown + 5 tables",
            "Produce a structured markdown document with exactly 5 tables.",
            "Do not add unsupported claims. Use headings and tables. Keep within 3000–4000 words.",
            "From the INPUT, produce a single markdown document 3000–4000 words.\nMust include exactly 5 markdown tables with titles.\nMust be suitable as a medical device regulation summary.\n\nINPUT:\n{input}",
            "markdown",
            MODE_MEDICAL,
        ),
        AgentDef(
            "med_entities",
            "Extract 20 Entities with Context (JSON)",
            "Return 20 entities with context and anchors.",
            "Return valid JSON only. No code fences.",
            "Extract exactly 20 entities from the DOCUMENT.\nReturn JSON array of objects with keys: entity_id,name,type,context,section,anchors(list),relevance,related_entities(list).\n\nDOCUMENT:\n{input}",
            "json",
            MODE_MEDICAL,
        ),
        AgentDef(
            "med_infographics",
            "Generate 8 Interactive Infographics (Spec JSON)",
            "Return 8 infographic specs (safe, non-executable) with bilingual labels.",
            "Return valid JSON only. No code fences.",
            "Based on the DOCUMENT, create exactly 8 infographic specs.\nReturn JSON array. Each item keys:\ninfographic_id,title_en,title_zh,kind (flow|tree|heatmap|timeline|network|board|cycle|funnel), spec_format (plotly), spec (a plotly figure dict), data_notes, traceability(list with source_section,anchor,reason).\nEnsure specs are renderable.\n\nDOCUMENT:\n{input}",
            "json",
            MODE_MEDICAL,
        ),
        AgentDef(
            "med_report",
            "WOW Report Builder (HTML)",
            "Assemble an interactive HTML report with sections + embedded infographic specs.",
            "Return HTML only. No code fences.",
            "Create a single HTML document with:\n- Executive summary\n- The markdown document converted to HTML (keep headings/tables)\n- Entities section (20 entities)\n- Infographics section (8) showing titles and embedding each plotly spec as JSON in <script type='application/json'> tags.\n- A final section with 20 follow-up questions.\n\nInputs:\nMARKDOWN_DOC:\n{doc}\n\nENTITIES_JSON:\n{entities}\n\nINFOGRAPHICS_JSON:\n{infographics}\n\nReturn HTML only.",
            "text",
            MODE_MEDICAL,
        ),
    ]


def load_agents_from_yaml(path: str = "agents.yaml") -> List[AgentDef]:
    if yaml is None:
        return default_agents()
    if not os.path.exists(path):
        return default_agents()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        agents = []
        for a in data.get("agents", []):
            agents.append(
                AgentDef(
                    agent_id=a["agent_id"],
                    name=a.get("name", a["agent_id"]),
                    description=a.get("description", ""),
                    default_system=a.get("default_system", ""),
                    default_user_template=a.get("default_user_template", "{input}"),
                    output=a.get("output", "text"),
                    mode=a.get("mode", MODE_INSIGHTS),
                )
            )
        return agents or default_agents()
    except Exception:
        return default_agents()


def agents_for_mode(mode: str) -> List[AgentDef]:
    all_agents = st.session_state.agents
    return [a for a in all_agents if a.mode == mode]


def ensure_agent_configs():
    """
    Initialize editable configs per agent.
    """
    for a in st.session_state.agents:
        if a.agent_id not in st.session_state.agent_configs:
            # default provider selection per mode
            default_provider = "Gemini"
            default_model = MODEL_CATALOG[default_provider][0]
            st.session_state.agent_configs[a.agent_id] = {
                "provider": default_provider,
                "model": default_model,
                "max_tokens": st.session_state.max_tokens,
                "temperature": st.session_state.temperature,
                "system_prompt": a.default_system,
                "user_template": a.default_user_template,
                "last_error": "",
            }


# -----------------------------
# Rendering helpers (infographics)
# -----------------------------

def render_plotly_spec(spec: Dict[str, Any], key: str):
    if go is None:
        st.info("Plotly not installed. Add plotly to requirements.txt to render infographics.")
        st.json(spec)
        return
    try:
        fig = go.Figure(spec)
        st.plotly_chart(fig, use_container_width=True, key=key)
    except Exception as e:
        st.warning(f"Could not render Plotly spec: {e}")
        st.json(spec)


def make_fallback_infographic(kind: str, title: str) -> Dict[str, Any]:
    # Fallback minimal plotly specs if model returns incomplete specs
    if go is None:
        return {"data": [], "layout": {"title": title}}
    if kind in ("funnel", "board"):
        return go.Figure(
            data=[go.Bar(x=[5, 4, 3, 2, 1], y=["A", "B", "C", "D", "E"], orientation="h")],
            layout=go.Layout(title=title, height=360),
        ).to_plotly_json()
    return go.Figure(
        data=[go.Scatter(x=[1, 2, 3, 4], y=[1, 3, 2, 4], mode="lines+markers")],
        layout=go.Layout(title=title, height=360),
    ).to_plotly_json()


# -----------------------------
# Mode Logic
# -----------------------------

def ui_api_keys_panel():
    st.sidebar.markdown("### " + tr("API Keys", "API 金鑰"))
    for provider in PROVIDERS:
        env_key = safe_get_env_key(provider)
        if env_key:
            st.sidebar.success(f"{provider}: " + tr("Key detected from environment", "已從環境偵測到金鑰"))
        else:
            st.sidebar.text_input(
                f"{provider} " + tr("API Key", "API 金鑰"),
                type="password",
                key=f"api_key_input_{provider}",
                value=st.session_state.api_keys.get(provider, ""),
                on_change=lambda p=provider: st.session_state.api_keys.__setitem__(p, st.session_state.get(f"api_key_input_{p}", "")),
            )


def ui_global_controls():
    st.sidebar.markdown("### " + tr("Global Settings", "全域設定"))
    st.sidebar.selectbox(tr("Language", "語言"), [LANG_EN, LANG_ZH], key="lang")
    st.sidebar.selectbox(tr("Theme", "主題"), ["Light", "Dark"], key="theme")

    cols = st.sidebar.columns([3, 1])
    with cols[0]:
        st.selectbox(tr("Painter Style", "畫家風格"), STYLE_NAMES, key="style_name")
    with cols[1]:
        st.button(tr("Jackpot", "彩蛋"), on_click=jackpot_style)

    st.sidebar.number_input(tr("Default max_tokens", "預設 max_tokens"), min_value=256, max_value=32000, step=256, key="max_tokens")
    st.sidebar.slider(tr("Default temperature", "預設 temperature"), min_value=0.0, max_value=1.0, step=0.05, key="temperature")

    st.sidebar.checkbox(tr("Show raw JSON in UI", "顯示原始 JSON"), key="show_raw_json")


def ui_status_dashboard():
    ss = st.session_state
    st.markdown(f"## {tr('WOW Dashboard', 'WOW 儀表板')}")
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"<div class='wow-card'><div class='wow-pill'>{tr('Status','狀態')}</div><br><span class='wow-primary'>{html_escape(ss.pipeline_status)}</span></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='wow-card'><div class='wow-pill'>{tr('Active Agent','目前代理')}</div><br><span class='wow-accent'>{html_escape(str(ss.pipeline_active_agent) if ss.pipeline_active_agent else '—')}</span></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='wow-card'><div class='wow-pill'>{tr('LLM Calls','呼叫次數')}</div><br><span class='wow-primary'>{ss.metrics['calls']}</span></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='wow-card'><div class='wow-pill'>{tr('Errors','錯誤')}</div><br><span class='wow-accent'>{ss.metrics['errors']}</span></div>", unsafe_allow_html=True)

    st.markdown("<div class='wow-card'>", unsafe_allow_html=True)
    st.markdown(tr("Artifact Timeline (click to restore content):", "產物時間軸（點擊可還原內容）："))
    if not ss.artifacts:
        st.caption(tr("No artifacts yet.", "尚無產物。"))
    else:
        for i, a in enumerate(reversed(ss.artifacts[-30:]), start=1):
            label = time.strftime("%H:%M:%S", time.localtime(a["ts"])) + f" • {a['type']} • {a['title']}"
            if st.button(label, key=f"restore_artifact_{len(ss.artifacts)-i}"):
                # restore to a generic clipboard slot
                ss.setdefault("clipboard", "")
                ss.clipboard = a["content"]
                st.toast(tr("Restored to clipboard slot.", "已還原到剪貼簿欄位。"))
    st.markdown("</div>", unsafe_allow_html=True)

    if "clipboard" in ss:
        st.text_area(tr("Clipboard (restored artifact content)", "剪貼簿（還原的產物內容）"), value=ss.clipboard, height=160)


def run_agent_step(agent: AgentDef, input_text: str, extra_vars: Optional[Dict[str, str]] = None) -> Tuple[str, Optional[Any]]:
    """
    Returns (raw_output_text, parsed_json_if_any)
    """
    cfg = st.session_state.agent_configs[agent.agent_id]
    provider = cfg["provider"]
    model = cfg["model"]
    max_tokens = int(cfg.get("max_tokens", st.session_state.max_tokens))
    temperature = float(cfg.get("temperature", st.session_state.temperature))
    system_prompt = cfg.get("system_prompt", "")
    user_template = cfg.get("user_template", agent.default_user_template)

    vars_map = {"input": input_text}
    if extra_vars:
        vars_map.update(extra_vars)

    # Defensive formatting: if template references unknown vars, don't crash
    try:
        user_prompt = user_template.format(**vars_map)
    except KeyError as e:
        missing = str(e).strip("'")
        raise LLMError(f"Prompt template missing variable: {{{missing}}}")

    st.session_state.pipeline_status = "Running"
    st.session_state.pipeline_active_agent = agent.name

    out = call_llm_with_retry(
        provider=provider,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        retries=2,
    )

    parsed = None
    if agent.output == "json":
        parsed = safe_json_loads(out)

    add_artifact(
        artifact_type=f"{agent.mode}:{agent.agent_id}",
        title=agent.name,
        content=out,
        meta={"provider": provider, "model": model, "max_tokens": max_tokens, "temperature": temperature},
    )

    st.session_state.pipeline_status = "Waiting for user edit"
    st.session_state.pipeline_active_agent = agent.name
    return out, parsed


def ui_agent_runner(mode: str):
    st.markdown(f"## {tr('Pipeline', '流程')}: {mode}")

    agents = agents_for_mode(mode)
    if not agents:
        st.info(tr("No agents defined for this mode.", "此模式沒有定義任何代理。"))
        return

    for agent in agents:
        cfg = st.session_state.agent_configs[agent.agent_id]
        with st.expander(f"{agent.name} — {agent.description}", expanded=False):
            c1, c2, c3 = st.columns([2, 2, 1])
            with c1:
                cfg["provider"] = st.selectbox(
                    tr("Provider", "供應商"),
                    PROVIDERS,
                    index=PROVIDERS.index(cfg["provider"]) if cfg["provider"] in PROVIDERS else 0,
                    key=f"prov_{agent.agent_id}",
                )
            with c2:
                models = MODEL_CATALOG.get(cfg["provider"], [])
                if not models:
                    models = ["(no models configured)"]
                # Keep current model if possible
                if cfg["model"] not in models:
                    cfg["model"] = models[0]
                cfg["model"] = st.selectbox(tr("Model", "模型"), models, key=f"model_{agent.agent_id}")
            with c3:
                cfg["max_tokens"] = st.number_input(
                    tr("max_tokens", "max_tokens"),
                    min_value=256,
                    max_value=32000,
                    step=256,
                    value=int(cfg.get("max_tokens", st.session_state.max_tokens)),
                    key=f"mt_{agent.agent_id}",
                )

            cfg["temperature"] = st.slider(
                tr("temperature", "temperature"),
                0.0,
                1.0,
                float(cfg.get("temperature", st.session_state.temperature)),
                0.05,
                key=f"temp_{agent.agent_id}",
            )

            cfg["system_prompt"] = st.text_area(
                tr("System prompt", "系統提示詞"),
                value=cfg.get("system_prompt", agent.default_system),
                height=90,
                key=f"sys_{agent.agent_id}",
            )
            cfg["user_template"] = st.text_area(
                tr("User prompt template", "使用者提示詞模板"),
                value=cfg.get("user_template", agent.default_user_template),
                height=140,
                key=f"user_{agent.agent_id}",
            )

            # Input to this agent: either committed previous, or current_inputs, or user provided
            default_in = st.session_state.current_inputs.get(agent.agent_id, "")
            input_text = st.text_area(
                tr("Input to this agent", "此代理的輸入"),
                value=default_in,
                height=160,
                key=f"in_{agent.agent_id}",
            )
            st.session_state.current_inputs[agent.agent_id] = input_text

            run_col, reset_col, _ = st.columns([1, 1, 3])
            with run_col:
                if st.button(tr("Run agent", "執行代理"), key=f"run_{agent.agent_id}"):
                    try:
                        out, parsed = run_agent_step(agent, input_text)
                        st.session_state.current_outputs[agent.agent_id] = out
                        cfg["last_error"] = ""
                        st.success(tr("Done.", "完成。"))
                        if agent.output == "json" and st.session_state.show_raw_json:
                            st.json(parsed)
                    except Exception as e:
                        cfg["last_error"] = str(e)
                        st.error(str(e))
                        st.session_state.pipeline_status = "Error"
                        st.session_state.pipeline_active_agent = agent.name

            with reset_col:
                if st.button(tr("Reset prompts", "重置提示詞"), key=f"reset_{agent.agent_id}"):
                    cfg["system_prompt"] = agent.default_system
                    cfg["user_template"] = agent.default_user_template
                    st.toast(tr("Reset done.", "已重置。"))

            if cfg.get("last_error"):
                st.warning(tr("Last error:", "上次錯誤：") + " " + cfg["last_error"])

            out_text = st.session_state.current_outputs.get(agent.agent_id, "")
            if out_text:
                st.markdown("### " + tr("Output (editable)", "輸出（可編輯）"))
                view = st.radio(tr("View", "檢視"), ["Text", "Markdown"], horizontal=True, key=f"view_{agent.agent_id}")
                edited = st.text_area(
                    tr("Edit output before passing to next agent", "傳遞到下一個代理前可編輯輸出"),
                    value=out_text,
                    height=240,
                    key=f"out_{agent.agent_id}",
                )
                st.session_state.current_outputs[agent.agent_id] = edited

                if view == "Markdown":
                    st.markdown("---")
                    st.markdown(edited, unsafe_allow_html=True)

                cA, cB = st.columns([1, 2])
                with cA:
                    if st.button(tr("Commit output", "提交輸出"), key=f"commit_{agent.agent_id}"):
                        st.session_state.committed_outputs[agent.agent_id] = edited
                        add_artifact(f"{mode}:commit", f"Committed: {agent.name}", edited, meta={"agent_id": agent.agent_id})
                        st.toast(tr("Committed as next input.", "已提交作為下一步輸入。"))

                with cB:
                    st.caption(tr(
                        "Tip: Copy committed output into the next agent input field, or use the clipboard restore.",
                        "提示：可將提交的輸出貼到下一個代理輸入欄位，或用時間軸還原到剪貼簿。"
                    ))


def ui_note_keeper():
    st.markdown(f"## {tr('AI Note Keeper', 'AI 筆記管家')}")
    st.text_area(tr("Paste note (text/markdown)", "貼上筆記（文字/Markdown）"), key="note_raw", height=220)

    # Controls
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        st.text_input(
            tr("Keywords (comma separated)", "關鍵字（逗號分隔）"),
            value=",".join(st.session_state.note_keywords) if st.session_state.note_keywords else "",
            key="note_keywords_input",
        )
    with c2:
        st.text_input(tr("Keyword color", "關鍵字顏色"), key="note_keyword_color", value=st.session_state.note_keyword_color)
    with c3:
        if st.button(tr("Apply highlight", "套用標註")):
            raw = st.session_state.note_md or st.session_state.note_raw
            kws = [k.strip() for k in st.session_state.note_keywords_input.split(",") if k.strip()]
            st.session_state.note_keywords = kws
            st.session_state.note_md = highlight_keywords_markdown(raw, kws, st.session_state.note_keyword_color)

    # Run transform agent
    agent = next((a for a in agents_for_mode(MODE_NOTES) if a.agent_id == "note_transform"), None)
    if agent is None:
        st.error(tr("Missing note_transform agent.", "缺少 note_transform 代理。"))
        return

    cfg = st.session_state.agent_configs[agent.agent_id]
    st.markdown("### " + tr("Transform settings", "轉換設定"))
    cA, cB, cC = st.columns([2, 2, 1])
    with cA:
        cfg["provider"] = st.selectbox(tr("Provider", "供應商"), PROVIDERS, key="note_provider")
    with cB:
        models = MODEL_CATALOG.get(cfg["provider"], [MODEL_CATALOG["Gemini"][0]])
        if cfg["model"] not in models:
            cfg["model"] = models[0]
        cfg["model"] = st.selectbox(tr("Model", "模型"), models, key="note_model")
    with cC:
        cfg["max_tokens"] = st.number_input(tr("max_tokens", "max_tokens"), 256, 32000, int(cfg.get("max_tokens", DEFAULT_MAX_TOKENS)), 256, key="note_mt")

    cfg["system_prompt"] = st.text_area(tr("System prompt", "系統提示詞"), value=cfg.get("system_prompt", agent.default_system), height=70, key="note_sys")
    cfg["user_template"] = st.text_area(tr("User prompt template", "使用者提示詞模板"), value=cfg.get("user_template", agent.default_user_template), height=110, key="note_user")

    if st.button(tr("Transform note", "整理筆記"), key="btn_transform_note"):
        try:
            out, _ = run_agent_step(agent, st.session_state.note_raw)
            # Extract keywords line if present
            md = out
            kws = []
            m = re.search(r"(?im)^\s*KEYWORDS\s*:\s*(.+)$", out)
            if m:
                kw_line = m.group(1).strip()
                kws = [k.strip() for k in re.split(r"[,，;；|/]", kw_line) if k.strip()]
                md = re.sub(r"(?im)^\s*KEYWORDS\s*:\s*.+$", "", out).strip()
            st.session_state.note_keywords = kws[:20]
            st.session_state.note_md = md
            st.success(tr("Note transformed.", "筆記已整理完成。"))
        except Exception as e:
            st.error(str(e))

    if st.session_state.note_md:
        st.markdown("### " + tr("Note (editable)", "筆記（可編輯）"))
        view = st.radio(tr("View", "檢視"), ["Text", "Markdown"], horizontal=True, key="note_view")
        edited = st.text_area(tr("Edit note", "編輯筆記"), value=st.session_state.note_md, height=260, key="note_md_edit")
        st.session_state.note_md = edited

        if view == "Markdown":
            kws = st.session_state.note_keywords
            color = st.session_state.note_keyword_color
            rendered = highlight_keywords_markdown(edited, kws, color)
            st.markdown("---")
            st.markdown(rendered, unsafe_allow_html=True)

        st.markdown("### " + tr("AI Magics (6)", "AI 魔法（6 種）"))
        magics = [
            tr("AI Keywords (user-defined highlight)", "AI 關鍵字（自訂標註）"),
            tr("AI Outline Refiner", "AI 大綱優化"),
            tr("AI Action Extractor", "AI 行動項目擷取"),
            tr("AI Clarifier (find ambiguities)", "AI 釐清（找出模糊點）"),
            tr("AI Meeting Minutes Formatter", "AI 會議紀錄格式化"),
            tr("AI Study Cards", "AI 學習卡片"),
        ]
        magic_choice = st.selectbox(tr("Select Magic", "選擇魔法"), magics, key="magic_choice")

        instruction_map = {
            magics[0]: "Highlight user-provided keywords; do not change content.",
            magics[1]: "Improve section hierarchy, reorder for clarity, keep meaning.",
            magics[2]: "Extract action items with owners/dates if present; include a small table.",
            magics[3]: "List ambiguous statements and propose clarifying questions; preserve note.",
            magics[4]: "Convert into meeting minutes format: agenda, decisions, next steps.",
            magics[5]: "Generate 10-20 Q/A flashcards based strictly on the note.",
        }
        instruction = st.text_area(tr("Magic instruction (editable)", "魔法指令（可編輯）"),
                                  value=instruction_map.get(magic_choice, ""),
                                  height=80,
                                  key="magic_instruction")

        magic_agent = next((a for a in agents_for_mode(MODE_NOTES) if a.agent_id == "note_magic"), None)
        if magic_agent is None:
            st.error(tr("Missing note_magic agent.", "缺少 note_magic 代理。"))
            return

        cfgm = st.session_state.agent_configs[magic_agent.agent_id]
        cX, cY, cZ = st.columns([2, 2, 1])
        with cX:
            cfgm["provider"] = st.selectbox(tr("Provider", "供應商"), PROVIDERS, key="magic_provider")
        with cY:
            models = MODEL_CATALOG.get(cfgm["provider"], [MODEL_CATALOG["Gemini"][0]])
            if cfgm["model"] not in models:
                cfgm["model"] = models[0]
            cfgm["model"] = st.selectbox(tr("Model", "模型"), models, key="magic_model")
        with cZ:
            cfgm["max_tokens"] = st.number_input(tr("max_tokens", "max_tokens"), 256, 32000, int(cfgm.get("max_tokens", DEFAULT_MAX_TOKENS)), 256, key="magic_mt")

        cfgm["system_prompt"] = st.text_area(tr("System prompt", "系統提示詞"), value=cfgm.get("system_prompt", magic_agent.default_system), height=60, key="magic_sys")

        if st.button(tr("Run Magic", "施放魔法"), key="btn_run_magic"):
            try:
                out, _ = run_agent_step(
                    magic_agent,
                    st.session_state.note_md,
                    extra_vars={"instruction": instruction},
                )
                st.session_state.note_md = out
                st.success(tr("Magic applied.", "魔法已套用。"))
            except Exception as e:
                st.error(str(e))


def ui_medical_workflow():
    st.markdown(f"## {tr('Medical Regulation WOW', '醫療器材法規 WOW')}")
    st.markdown(tr(
        "Upload or paste a regulation summary (txt/md/pdf). The system will reorganize it into 3000–4000 word markdown, "
        "produce 5 tables, extract 20 entities, generate 8 interactive infographic specs, and build a WOW report.",
        "上傳或貼上法規摘要（txt/md/pdf）。系統會重整為 3000–4000 字 Markdown、產生 5 個表格、擷取 20 個實體、生成 8 個互動資訊圖規格，並建立 WOW 報告。"
    ))

    c1, c2 = st.columns([1, 1])
    with c1:
        uploaded = st.file_uploader(tr("Upload file", "上傳檔案"), type=["txt", "md", "pdf"], key="med_upload")
    with c2:
        st.text_area(tr("Or paste text/markdown", "或貼上文字/Markdown"), key="med_paste", height=160)

    if st.button(tr("Load source", "載入來源"), key="btn_med_load"):
        try:
            text = ""
            if uploaded is not None:
                file_bytes = uploaded.read()
                if uploaded.name.lower().endswith(".pdf"):
                    text = extract_pdf_text(file_bytes)
                else:
                    text = bytes_to_text(file_bytes)
            else:
                text = st.session_state.get("med_paste", "")
            st.session_state.medical_source_text = text.strip()
            add_artifact("medical:source", "Medical Source Loaded", st.session_state.medical_source_text[:120000])
            st.success(tr("Source loaded.", "來源已載入。"))
        except Exception as e:
            st.error(str(e))

    if not st.session_state.medical_source_text:
        st.info(tr("Load a source document to begin.", "請先載入來源文件再開始。"))
        return

    st.markdown("### " + tr("Source Preview", "來源預覽"))
    st.text_area(tr("Extracted text", "擷取文字"), value=st.session_state.medical_source_text, height=200)

    agents = {a.agent_id: a for a in agents_for_mode(MODE_MEDICAL)}

    # Step buttons (run one-by-one, user can edit through Pipeline tab as well)
    st.markdown("### " + tr("Quick Steps", "快速步驟"))
    b1, b2, b3, b4 = st.columns(4)

    with b1:
        if st.button(tr("1) Ingest", "1) 清理"), key="med_step_ingest"):
            try:
                out, _ = run_agent_step(agents["med_ingest"], st.session_state.medical_source_text)
                st.session_state.medical_source_text = out
                st.success(tr("Ingestion done.", "清理完成。"))
            except Exception as e:
                st.error(str(e))

    with b2:
        if st.button(tr("2) Reorganize MD", "2) 重整 MD"), key="med_step_reorg"):
            try:
                out, _ = run_agent_step(agents["med_reorg"], st.session_state.medical_source_text)
                st.session_state.medical_doc_md = out
                st.success(tr("Markdown reorganized.", "Markdown 重整完成。"))
            except Exception as e:
                st.error(str(e))

    with b3:
        if st.button(tr("3) Entities (20)", "3) 實體（20）"), key="med_step_entities"):
            try:
                out, parsed = run_agent_step(agents["med_entities"], st.session_state.medical_doc_md or st.session_state.medical_source_text)
                st.session_state.medical_entities = parsed if isinstance(parsed, list) else []
                st.success(tr("Entities extracted.", "實體擷取完成。"))
            except Exception as e:
                st.error(str(e))

    with b4:
        if st.button(tr("4) Infographics (8)", "4) 資訊圖（8）"), key="med_step_infographics"):
            try:
                out, parsed = run_agent_step(agents["med_infographics"], st.session_state.medical_doc_md or st.session_state.medical_source_text)
                infs = parsed if isinstance(parsed, list) else []
                # Patch missing specs
                patched = []
                for i, item in enumerate(infs, start=1):
                    if not isinstance(item, dict):
                        continue
                    kind = item.get("kind", "line")
                    title = item.get("title_en", f"Infographic {i}")
                    if item.get("spec_format") != "plotly" or not isinstance(item.get("spec"), dict):
                        item["spec_format"] = "plotly"
                        item["spec"] = make_fallback_infographic(kind, title)
                    patched.append(item)
                st.session_state.medical_infographics = patched
                st.success(tr("Infographics generated.", "資訊圖已生成。"))
            except Exception as e:
                st.error(str(e))

    # Display doc + extracted tables (best-effort parse: extract markdown tables)
    if st.session_state.medical_doc_md:
        st.markdown("### " + tr("Reorganized Markdown (editable)", "重整後 Markdown（可編輯）"))
        edited = st.text_area(tr("Edit markdown", "編輯 Markdown"), value=st.session_state.medical_doc_md, height=260, key="med_doc_edit")
        st.session_state.medical_doc_md = edited
        st.markdown("---")
        st.markdown(edited, unsafe_allow_html=True)

        # Extract tables best-effort: markdown table blocks
        tables = re.findall(r"((?:^\|.*\|\s*$\n)+)", edited, flags=re.MULTILINE)
        st.session_state.medical_tables = tables[:10]

        st.markdown("### " + tr("Detected Tables (best-effort)", "偵測到的表格（盡力而為）"))
        if not st.session_state.medical_tables:
            st.caption(tr("No markdown tables detected yet.", "尚未偵測到 Markdown 表格。"))
        else:
            for i, tbl in enumerate(st.session_state.medical_tables[:5], start=1):
                st.markdown(f"**{tr('Table','表格')} {i}**")
                st.markdown(tbl, unsafe_allow_html=True)

    # Entities UI
    if st.session_state.medical_entities:
        st.markdown("### " + tr("Entities (20)", "實體（20）"))
        q = st.text_input(tr("Search entities", "搜尋實體"), key="entity_search")
        ents = st.session_state.medical_entities
        if q.strip():
            ents = [e for e in ents if q.lower() in str(e.get("name", "")).lower() or q.lower() in str(e.get("type", "")).lower()]
        st.dataframe(ents, use_container_width=True)

    # Infographics UI + improvement loop
    if st.session_state.medical_infographics:
        st.markdown("### " + tr("Infographics Gallery (8)", "資訊圖畫廊（8）"))
        for item in st.session_state.medical_infographics:
            title = item.get("title_en") if st.session_state.lang == LANG_EN else item.get("title_zh")
            st.markdown(f"#### {title}")
            spec = item.get("spec", {})
            render_plotly_spec(spec, key=f"inf_{item.get('infographic_id','x')}")

        st.markdown("### " + tr("Improve Infographics", "改善資訊圖"))
        # Select
        ids = [i.get("infographic_id", f"I{idx+1}") for idx, i in enumerate(st.session_state.medical_infographics)]
        selected = st.multiselect(tr("Select infographics", "選擇資訊圖"), ids, default=ids[:1], key="inf_select")

        improve_prompt = st.text_area(
            tr("Improvement prompt", "改善提示詞"),
            value=tr(
                "Improve clarity, add better labels, ensure values are consistent with the document. Return updated JSON specs only.",
                "改善清晰度、加強標籤、確保數值與文件一致。只回傳更新後的 JSON 規格。"
            ),
            height=90,
            key="inf_improve_prompt",
        )

        # Choose provider/model for improvement
        prov = st.selectbox(tr("Provider", "供應商"), PROVIDERS, key="inf_improve_provider")
        model = st.selectbox(tr("Model", "模型"), MODEL_CATALOG.get(prov, MODEL_CATALOG["Gemini"]), key="inf_improve_model")
        mt = st.number_input(tr("max_tokens", "max_tokens"), 256, 32000, DEFAULT_MAX_TOKENS, 256, key="inf_improve_mt")
        temp = st.slider(tr("temperature", "temperature"), 0.0, 1.0, 0.25, 0.05, key="inf_improve_temp")

        if st.button(tr("Run improvement", "執行改善"), key="btn_inf_improve"):
            try:
                current = [i for i in st.session_state.medical_infographics if i.get("infographic_id") in selected]
                user_prompt = f"{improve_prompt}\n\nCURRENT_INFOGRAPHICS_JSON:\n{json.dumps(current, ensure_ascii=False)}\n\nDOCUMENT:\n{st.session_state.medical_doc_md[:60000]}"
                out = call_llm_with_retry(
                    provider=prov,
                    model=model,
                    system_prompt="Return valid JSON only. No code fences.",
                    user_prompt=user_prompt,
                    max_tokens=int(mt),
                    temperature=float(temp),
                    retries=2,
                )
                improved = safe_json_loads(out)
                if isinstance(improved, dict):
                    improved = [improved]
                if not isinstance(improved, list):
                    raise LLMError("Improvement did not return a JSON list/dict.")

                # Merge improvements
                improved_map = {x.get("infographic_id"): x for x in improved if isinstance(x, dict)}
                new_list = []
                for old in st.session_state.medical_infographics:
                    nid = old.get("infographic_id")
                    if nid in improved_map:
                        merged = improved_map[nid]
                        # Patch missing spec
                        if merged.get("spec_format") != "plotly" or not isinstance(merged.get("spec"), dict):
                            merged["spec_format"] = "plotly"
                            merged["spec"] = make_fallback_infographic(merged.get("kind", "line"), merged.get("title_en", nid))
                        new_list.append(merged)
                    else:
                        new_list.append(old)

                st.session_state.medical_infographics = new_list
                add_artifact("medical:infographics_improved", "Infographics Improved", json.dumps(improved, ensure_ascii=False)[:120000])
                st.success(tr("Improvement applied.", "已套用改善。"))
            except Exception as e:
                st.error(str(e))

    # Build WOW Report
    st.markdown("### " + tr("WOW Report", "WOW 報告"))
    if st.button(tr("Build report HTML", "建立報告 HTML"), key="btn_build_report"):
        try:
            if "med_report" not in agents:
                raise LLMError("Missing med_report agent.")
            doc = st.session_state.medical_doc_md
            entities = st.session_state.medical_entities
            infs = st.session_state.medical_infographics
            extra_vars = {
                "doc": doc,
                "entities": json.dumps(entities, ensure_ascii=False),
                "infographics": json.dumps(infs, ensure_ascii=False),
            }
            out, _ = run_agent_step(agents["med_report"], input_text="", extra_vars=extra_vars)
            st.session_state.medical_report_html = out
            st.success(tr("Report built.", "報告已建立。"))
        except Exception as e:
            st.error(str(e))

    if st.session_state.medical_report_html:
        st.markdown("#### " + tr("Report Preview", "報告預覽"))
        st.components.v1.html(st.session_state.medical_report_html, height=520, scrolling=True)

        # Downloads
        html_data = st.session_state.medical_report_html.encode("utf-8")
        st.download_button("Download HTML", html_data, file_name="wow_report.html", mime="text/html")

        md_data = (st.session_state.medical_doc_md or "").encode("utf-8")
        st.download_button("Download Markdown", md_data, file_name="medical_regulation_wow.md", mime="text/markdown")

        txt_data = re.sub(r"<[^>]+>", "", st.session_state.medical_report_html).encode("utf-8")
        st.download_button("Download TXT", txt_data, file_name="wow_report.txt", mime="text/plain")


def ui_insights_mode():
    st.markdown(f"## {tr('Insights Generator', '洞察生成器')}")
    st.text_area(tr("Paste input text", "貼上輸入文字"), key="ins_input", height=220)
    st.caption(tr("Run agents in the Pipeline tab for full control.", "完整控制請到「流程」分頁逐步執行代理。"))


# -----------------------------
# Main App
# -----------------------------

def main():
    st.set_page_config(page_title="WOW Multi-Agent Studio", layout="wide")
    init_session_state()
    st.session_state.agents = load_agents_from_yaml()
    ensure_agent_configs()

    inject_theme_css(st.session_state.theme, st.session_state.style_name)

    # Header
    title = APP_TITLE_EN if st.session_state.lang == LANG_EN else APP_TITLE_ZH
    st.markdown(f"# {title}")
    st.markdown(
        f"<span class='wow-pill'>{html_escape(st.session_state.theme)}</span> "
        f"<span class='wow-pill'>{html_escape(st.session_state.lang)}</span> "
        f"<span class='wow-pill'>{html_escape(st.session_state.style_name)}</span>",
        unsafe_allow_html=True,
    )

    # Sidebar
    ui_global_controls()
    ui_api_keys_panel()
    st.sidebar.markdown("### " + tr("Mode", "模式"))
    st.sidebar.selectbox(
        tr("Select mode", "選擇模式"),
        [MODE_MEDICAL, MODE_NOTES, MODE_INSIGHTS],
        key="mode",
    )

    # Top-level tabs
    tabs = st.tabs([tr("Dashboard", "儀表板"), tr("Workspace", "工作區"), tr("Pipeline", "流程"), tr("Artifacts", "產物")])

    with tabs[0]:
        ui_status_dashboard()

    with tabs[1]:
        if st.session_state.mode == MODE_MEDICAL:
            ui_medical_workflow()
        elif st.session_state.mode == MODE_NOTES:
            ui_note_keeper()
        else:
            ui_insights_mode()

    with tabs[2]:
        ui_agent_runner(st.session_state.mode)

    with tabs[3]:
        st.markdown("## " + tr("Artifacts", "產物"))
        if not st.session_state.artifacts:
            st.info(tr("No artifacts yet.", "尚無產物。"))
        else:
            for a in reversed(st.session_state.artifacts[-80:]):
                st.markdown(f"<div class='wow-card'>", unsafe_allow_html=True)
                st.markdown(
                    f"**{html_escape(a['title'])}**  \n"
                    f"<span class='wow-pill'>{html_escape(a['type'])}</span> "
                    f"<span class='wow-pill'>{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(a['ts']))}</span>",
                    unsafe_allow_html=True,
                )
                meta = a.get("meta") or {}
                if meta:
                    st.caption(", ".join([f"{k}={v}" for k, v in meta.items()]))
                content = a.get("content", "")
                if len(content) > 12000:
                    st.text_area(tr("Content (truncated)", "內容（截斷）"), value=content[:12000] + "\n\n...[truncated]...", height=220)
                else:
                    st.text_area(tr("Content", "內容"), value=content, height=220)
                st.markdown("</div>", unsafe_allow_html=True)

    # Footer status normalization
    if st.session_state.pipeline_status == "Running":
        # In case of unexpected rerun, avoid stuck status
        st.session_state.pipeline_status = "Waiting for user edit"


if __name__ == "__main__":
    main()
