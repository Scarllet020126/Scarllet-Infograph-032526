## 1. Executive Summary

### 1.1 Product Vision
The improved system is a **multi-mode, multi-agent Streamlit application** that turns unstructured content (text/markdown/PDF uploads) into **structured bilingual outputs**, **interactive dashboards**, and **exportable reports**. It preserves the original agentic pipeline philosophy—breaking complex cognition into specialized steps—while adding extensive user control over **model selection**, **prompts**, **token limits**, and **human-in-the-loop editing** between agents.

### 1.2 What “WOW” Means in This Upgrade
“WOW” is a first-class UX and workflow concept expressed as:

1. **A new WOW UI framework**:  
   - Light/Dark theme toggle  
   - English/Traditional Chinese UI toggle  
   - **20 painter-inspired styles** (plus “Jackpot” random style) affecting typography, colors, charts, and layout
2. **Status indicators & an interactive dashboard**:  
   Real-time pipeline progress, cost/time estimates, tokens, model used, retries, citations coverage, and output quality signals.
3. **User-controlled agent execution**:  
   Users can edit each agent’s prompt, choose the model/provider, set max tokens (default **12000**), run agents **one-by-one**, and **edit the output** (text/markdown) before passing to the next agent.
4. **AI Note Keeper**:  
   Paste notes → transform into organized markdown with **keywords highlighted in coral** → apply “AI Magics” (6 features) including **AI Keywords** where users choose keywords + colors.
5. **Medical Regulation Superflow** (new):  
   Upload/paste a medical device regulation summary (txt/md/pdf) → reorganize to a **3000–4000 word** markdown document with **5 tables** and **20 entities with context** → generate **8 interactive infographics “by code/spec”** → allow iterative improvement prompts → produce a **WOW report web page** with downloads (HTML/TXT/MD).

---

## 2. High-Level Architecture (Streamlit on Hugging Face)

### 2.1 Components
1. **Streamlit UI Layer**
   - Sidebar: global settings (theme, language, painter style, API keys, provider defaults)
   - Main area: mode selector + dashboards + workspace tabs
   - Editors: text/markdown editor components (non-code spec; implementation can use Streamlit text areas and a markdown preview)
2. **Agent Orchestration Layer**
   - Reads `agents.yaml` to define agents, default prompts, schemas, routing, and provider/model defaults.
   - Provides a **Run / Pause / Step / Retry** execution model per agent.
3. **Provider Adapter Layer**
   - Normalizes calls across Gemini/OpenAI/Anthropic/Grok.
   - Enforces common options: `model`, `max_tokens`, `temperature`, `structured_output`, `tools` (where supported), and safety filters.
4. **Document Processing Layer**
   - PDF extraction to text + layout hints (headings, tables) with deterministic tooling.
   - Chunking/summarization strategy for long documents.
5. **Artifacts & Export Layer**
   - Stores intermediate artifacts in session state: inputs, agent outputs, tables, entity lists, infographic specs, report bundle.
   - Exporters for Markdown/TXT/HTML; report bundler that embeds infographic components and citations.

### 2.2 Data Flow (Unified)
**Input → Ingestion/Normalization → Extraction/Structuring → Planning/Generation → QA/Validation → Dashboard/Report/Export**

The system supports **multiple modes** that reuse the same orchestration primitives but with different agent graphs defined in `agents.yaml`.

---

## 3. Deployment & Runtime Constraints (Hugging Face Spaces)

### 3.1 Execution Model
- Streamlit runs server-side Python within HF sandbox constraints.
- State persists per user session using Streamlit session state.
- The app must remain responsive under long LLM calls: use non-blocking UX patterns (progress containers, stepper UI, incremental rendering of artifacts).

### 3.2 File Handling
- Accepted uploads: `.txt`, `.md`, `.pdf`
- PDFs: extracted to text plus metadata (page numbers, section hints). The extraction must preserve citation anchors like `(p.12)` for later traceability.

### 3.3 Privacy & Data Retention
- Default: **no persistence** beyond session unless the user explicitly downloads/export.
- Optional (future-safe spec): allow “Save session artifacts” to a user-provided storage, but **not required** in this upgrade.

---

## 4. API Key Management (Required Upgrade)

### 4.1 Key Sources & UI Rules
The system supports four providers. Keys may come from:
1. **Environment variables** (HF secrets): preferred.
2. **User input on webpage** (only if env key is missing).

**Rules:**
- If an environment key exists:  
  - UI displays: “Key detected from environment”  
  - **Never reveal the key** (no partial display, no copy button).
- If missing:  
  - UI shows secure inputs (password-style fields) for the selected provider(s).
  - Keys stored in session state only; never logged, never included in exports.

### 4.2 Provider Key Priority
For each provider:
1) env var → 2) user-provided session key → 3) disabled with actionable error message.

---

## 5. WOW UI/UX Specification

### 5.1 Layout Overview
- **Top Bar**: Mode selector (Insights / Medical Regulation / Note Keeper), Run controls, language toggle, theme toggle, painter style selector (+ Jackpot).
- **Left Sidebar**:
  - Provider/model defaults
  - Token controls (default max_tokens=12000)
  - Temperature and structured output toggles (when applicable)
  - API key panel (conditional display)
- **Main Workspace Tabs**:
  1. **Dashboard** (status + KPIs + artifact timeline)
  2. **Pipeline** (agent-by-agent execution with editable prompts/outputs)
  3. **Artifacts** (tables, entities, citations, infographic gallery)
  4. **Report** (interactive assembled web page + exports)

### 5.2 Themes & Painter Styles (20 + Jackpot)
#### Base toggles
- Light / Dark: affects background, text, borders, chart gridlines.
- English / Traditional Chinese: switches UI strings and optionally output display.

#### 20 painter-inspired styles (examples)
Each style defines a palette + typography rules + chart defaults:
1. Monet (Impressionist pastel haze)
2. Van Gogh (bold strokes, cobalt/yellow)
3. Picasso (cubist contrasts)
4. Klimt (gold + ornament)
5. Hokusai (indigo + wave motifs)
6. Frida Kahlo (vivid folk palette)
7. Dali (surreal high contrast)
8. Pollock (splatter accents)
9. Rothko (soft blocks)
10. Magritte (clean surreal minimal)
11. Matisse (cutout bright)
12. Rembrandt (warm chiaroscuro)
13. Vermeer (cool daylight)
14. Turner (atmospheric gradients)
15. Mondrian (primary grid)
16. Georgia O’Keeffe (desert tones)
17. Edward Hopper (muted modern)
18. Yayoi Kusama (polka dot energy)
19. Basquiat (neo-expressionist)
20. Ukiyo-e Classic (flat ink tones)

**Jackpot**: randomly selects one style, optionally “locks” it for exports.

**Implementation principle (spec-level):**
- Styles are expressed as a **theme token set** (CSS variables or Streamlit theme injection) applied consistently to:
  - Dashboard cards
  - Markdown typography
  - Table styling
  - Infographic color sequences
  - Highlight colors (including coral keyword highlight)

### 5.3 WOW Status Indicators & Interactive Dashboard
The dashboard is not decorative; it is operational:

**Status Indicators**
- Pipeline stage (Idle / Running / Waiting for user edit / Completed / Error)
- Current agent name + provider/model
- Token usage (estimated input+output)
- Latency per agent
- Retry count + backoff status
- Grounding/citation status (Gemini grounding or extracted citations)
- Output integrity checks (schema valid, required sections present, word count targets met)

**Interactive Widgets**
- “Artifact Timeline” showing each agent output version; click to restore a prior version.
- “Diff View” for edited outputs vs original agent output (text/markdown).
- “Quality Gates” checklist per mode (e.g., medical doc must have 5 tables + 20 entities).

---

## 6. Agent Orchestration & Human-in-the-Loop Controls

### 6.1 agents.yaml Contract (Conceptual)
`agents.yaml` defines:
- agent id/name
- purpose
- default prompt templates (EN + zh-TW variants where needed)
- input dependencies (which prior artifact keys feed this agent)
- output type: text, markdown, JSON, or “spec”
- optional schema for structured outputs
- default provider/model mapping

### 6.2 Agent Execution Model (Step-by-Step)
For every agent:
1. User reviews/edits prompt (with reset-to-default)
2. User selects:
   - provider + model (from approved list)
   - max_tokens (default 12000)
   - temperature (mode-dependent defaults)
3. User runs agent
4. Output appears in dual view:
   - Text view
   - Markdown preview (if markdown)
5. User can **edit output** and “Commit as next input”

### 6.3 Supported Models (as requested)
Selectable models list includes:
- OpenAI: `gpt-4o-mini`, `gpt-4.1-mini`
- Gemini: `gemini-2.5-flash`, `gemini-3-flash-preview`, `gemini-2.5-flash-lite`, `gemini-3-pro-preview`
- Anthropic: (expose available Anthropic models configured in deployment)
- Grok: `grok-4-fast-reasoning`, `grok-3-mini`

**Provider capability matrix (spec):**
- Structured output enforcement: best on Gemini/OpenAI (implementation-dependent), partial on others.
- Grounding: Gemini with Google Search grounding when enabled; otherwise show “grounding unavailable for this provider.”

---

## 7. Mode A — Original “Insights Generator” (Preserved & Enhanced)

### 7.1 Purpose
Transform long-form text into structured topics, bilingual summaries, charts/infographics, QA checks, follow-up questions, plus exports.

### 7.2 Pipeline (Representative)
1. Ingestion & cleanup (chunking as needed)
2. Topic extraction (bilingual fields)
3. Visualization planning (choose chart types and data points/specs)
4. QA & finalization (consistency checks + 20 follow-up questions)
5. Optional: social thread generation, audio summary, fact-check grounding (where supported)

### 7.3 Output Artifacts
- Topics JSON
- Visual specs per topic
- Markdown report + bilingual switchable rendering
- Follow-up questions list

---

## 8. Mode B — AI Note Keeper (New)

### 8.1 User Story
User pastes a messy note (text/markdown). The system transforms it into a clean, organized markdown document with highlighted keywords in **coral**. User can then apply “AI Magics” to refine, extend, or reformat.

### 8.2 Note Transformation Requirements
- Input: text or markdown
- Output: organized markdown with:
  - Title (auto-generated if missing)
  - Executive bullet summary
  - Sections with headers
  - Action items / Decisions / Open questions blocks (when detected)
  - **Keywords highlighted in coral color** (rendering approach described below)

### 8.3 Keyword Highlighting (Coral)
Because markdown alone lacks standard color, the system uses one of these render-safe strategies:
- Inline HTML spans: `<span style="color:coral;font-weight:600">keyword</span>` in markdown output, rendered by Streamlit markdown with HTML allowed (with caution).
- Or a controlled renderer that post-processes tokens into styled components (preferred for security).

User controls:
- toggle highlighting on/off
- adjust highlight color (default coral)
- choose “auto keywords” vs “manual keywords list”

### 8.4 AI Magics (6 Features)
1. **AI Keywords (user-defined + color picker)**  
   User enters keywords and selects highlight color(s). The system re-renders note highlighting accordingly.
2. **AI Outline Refiner**  
   Reorders sections into a cleaner hierarchy; preserves content fidelity.
3. **AI Action Extractor**  
   Extracts tasks, owners (if present), deadlines, and creates a mini table.
4. **AI Clarifier (Ambiguity Resolver)**  
   Flags vague phrases, missing context, and proposes questions.
5. **AI Meeting Minutes Formatter**  
   Converts note into minutes format: attendees, agenda, decisions, next steps.
6. **AI Study Cards**  
   Creates Q/A flashcards from the note for review (bilingual optional).

Each Magic is an agent action with editable prompt + model selection.

---

## 9. Mode C — Medical Device Regulation Workflow (New)

### 9.1 Goal
User pastes or uploads a medical device regulation summary (txt/md/pdf). The system produces:
1) A reorganized markdown document of **3000–4000 words**  
2) **5 tables** embedded in the markdown  
3) **20 entities** (defined below) each with context  
4) **8 WOW interactive infographics** generated as safe “code/spec” artifacts  
5) An iterative improvement loop for infographics  
6) A final **WOW report** as an interactive web page + downloads (HTML/TXT/MD)

### 9.2 Input Handling
- Upload or paste
- PDF extraction must preserve:
  - section headings if detectable
  - page anchors for citations
  - table text if extractable
- A “Document Preview” panel shows raw extracted text for transparency.

### 9.3 Medical Regulation Reorganization Agent (Doc Rewriter)
**Requirement:** Output markdown **3000–4000 words** (target range enforced by QA gate).  
**Structure (minimum):**
1. Title + scope
2. Regulatory framework overview
3. Definitions & classification
4. Market authorization / registration pathways
5. Quality management / QMS expectations
6. Clinical evaluation / evidence requirements
7. Post-market surveillance & vigilance
8. Labeling / UDI / traceability
9. Cybersecurity / software (if applicable)
10. Key risks, pitfalls, and compliance checklist
11. Practical guidance: timelines and stakeholder roles

**Five required tables (minimum specification):**
1. Classification rules summary (classes, criteria, examples)
2. Submission/registration pathway comparison (pathway, evidence, timelines, authority)
3. Required technical documentation checklist
4. PMS/vigilance obligations (trigger, reporting timeline, content)
5. Roles & responsibilities matrix (manufacturer, authorized rep, importer, distributor, regulator)

### 9.4 Entity Extraction (20 Entities with Context)
The system must extract **20 entities**, each with:
- entity name
- entity type (Regulatory body, Standard, Regulation, Process, Document, Role, Evidence type, Risk concept, Submission type, Identifier, etc.)
- where it appears (section + optional page anchor)
- “context snippet” (short quote or paraphrase)
- relevance explanation (1–2 sentences)
- relationships to other entities (optional)

**Entity list display:**
- searchable table
- click entity → shows context + linked sections in the markdown

### 9.5 Infographic Generation (8 WOW Interactive Infographs “by code/spec”)
**Interpretation of “by code” for safety:** the agent outputs a **restricted chart specification** (e.g., Vega-Lite JSON or Plotly figure schema) rather than arbitrary executable code. This still qualifies as “code/spec” while preventing unsafe execution.

**Eight required infographic categories (suggested set):**
1. Regulatory pathway flow diagram (interactive steps)
2. Classification decision tree (interactive nodes)
3. Evidence requirements matrix heatmap
4. Timeline Gantt-like view (submission → review → approval → PMS)
5. Stakeholder responsibility network graph
6. Compliance checklist progress board (interactive toggles)
7. Risk management loop (process cycle diagram)
8. PMS & vigilance reporting funnel (events → reportability → timelines)

**Infographic spec requirements:**
- bilingual labels (EN + zh‑TW)
- style-aware palette (painter theme applies)
- accessibility: minimum contrast ratio targets for text/lines; keyboard navigable legends where feasible
- embedded citations links back to doc sections (“Why this chart says that”)

### 9.6 Infographic Improvement Loop (User Prompted)
After initial 8 infographics:
- User selects one or more infographics
- User edits an “Improve infographic prompt” and selects model
- The agent returns an updated infographic spec
- System shows diff: spec changes + visual before/after
- User can accept/reject per infographic

### 9.7 WOW Report Builder
The final report is an **interactive web page view inside Streamlit** assembled from:
- Executive summary
- The 3000–4000 word reorganized markdown
- 5 tables (rendered with consistent styling)
- Entities explorer (20 entities)
- Infographic gallery (8 interactive charts)
- Citations/traceability panel (where available)
- Follow-up questions (20 comprehensive questions at end)

**Downloads supported:**
- **HTML**: self-contained where possible (infographics embedded as JSON specs + renderer)
- **Markdown**: includes tables and links; charts represented as static placeholders + JSON spec appendix
- **TXT**: plain text rendering without interactive components

---

## 10. Data Models (Artifacts) — Canonical Structures

### 10.1 Session Artifact Registry
All outputs are stored as versioned artifacts:
- `artifact_id`, `type`, `created_at`, `agent_id`, `provider`, `model`, `prompt_hash`
- `content_raw`, `content_rendered`, `metadata`

### 10.2 Medical Doc Output Schema (Conceptual)
```json
{
  "doc_markdown": "string",
  "word_count": 3450,
  "tables": [
    { "table_id": "T1", "title": "string", "markdown": "string", "source_anchors": ["p.12"] }
  ],
  "entities": [
    {
      "entity_id": "E1",
      "name": "string",
      "type": "string",
      "context": "string",
      "section": "string",
      "anchors": ["p.7"],
      "relevance": "string",
      "related_entities": ["E2", "E5"]
    }
  ],
  "citations": [
    { "anchor": "p.7", "snippet": "string", "confidence": 0.78 }
  ]
}
```

### 10.3 Infographic Spec Schema (Conceptual)
```json
{
  "infographic_id": "I1",
  "title_en": "string",
  "title_zh": "string",
  "kind": "flow|tree|heatmap|timeline|network|board|cycle|funnel",
  "spec_format": "vega-lite|plotly",
  "spec": {},
  "data_notes": "string",
  "traceability": [
    { "source_section": "Clinical Evaluation", "anchor": "p.15", "reason": "string" }
  ]
}
```

---

## 11. Quality, Validation, and Safety Gates

### 11.1 Deterministic Validation
Before marking an agent step “Complete,” validate:
- JSON schemas parse correctly (when structured)
- Medical doc word count in range 3000–4000 (with tolerance policy)
- Exactly 5 tables exist (or fail with “Regenerate tables” action)
- At least 20 entities exist (or fail with “Extract more entities” action)
- Exactly 8 infographics exist (or fail with “Generate missing infographics” action)

### 11.2 Hallucination Mitigation
- Prefer extraction with anchors/snippets from source.
- When provider supports grounding, enable it for claims-heavy sections.
- QA agent produces:
  - “Potentially unsupported claims” list
  - “Missing definitions” list
  - “Conflicting statements” list

### 11.3 Security for “Infograph by code/spec”
- Only allow **spec formats** supported by a safe renderer.
- Reject any output that contains executable code blocks, imports, file/network operations.
- Enforce a strict allowlist of chart types and fields.

---

## 12. Performance & Reliability

### 12.1 Chunking Strategy
- PDFs and long inputs are chunked by headings/pages.
- The ingestion agent creates a consolidated “clean source” to reduce tokens.
- For 3000–4000 word outputs, the system uses multi-pass generation:
  1) Outline → 2) Section drafting → 3) Assembly → 4) QA length normalization

### 12.2 Retries and Rate Limits
- Automatic retry with exponential backoff on 429/503.
- UI exposes “Retry this agent” and “Switch model/provider” without losing artifacts.

### 12.3 Observability (User-Facing)
Dashboard shows:
- per-agent time
- token estimates
- provider errors
- cache hits (if enabled)
- export readiness checks

---

## 13. Export Specification

### 13.1 Markdown Export
- Includes the reorganized document, tables, entities list, and infographic appendix:
  - Each infographic includes title + short description + embedded spec JSON in an appendix section.

### 13.2 HTML Export
- Single HTML file structure:
  - `<nav>` for sections
  - embedded theme tokens matching painter style
  - infographic renderer loads from embedded JSON specs
- If fully self-contained rendering is constrained, provide an HTML + JSON bundle (zip) as a fallback export option (spec-level requirement; packaging approach depends on HF constraints).

### 13.3 TXT Export
- Plain sections
- Tables flattened to readable text
- Infographics described narratively with key data points

---

## 14. Acceptance Criteria (Must Pass)

1. All original features remain available (agentic pipeline, bilingual output handling, exports, grounding where supported, interactive visualization, follow-up questions).
2. WOW UI: theme toggle, language toggle, 20 painter styles + Jackpot.
3. Status indicators & dashboard present and functional.
4. API key logic: env-first; user input only if missing; never reveal env keys.
5. Agent-by-agent execution with editable prompts/models/max_tokens and editable outputs passed forward.
6. AI Note Keeper works end-to-end including coral keyword highlighting and 6 AI Magics.
7. Medical workflow:
   - accepts txt/md/pdf
   - produces 3000–4000 word markdown
   - includes 5 tables
   - extracts 20 entities with context
   - generates 8 interactive infographics via safe spec
   - supports iterative infographic improvement
   - builds WOW report page and exports HTML/TXT/MD

---

## 15. Follow-Up Questions (20 Comprehensive)

1. For medical regulation PDFs with complex formatting, which PDF extraction approach will be used (text-only vs layout-aware), and how will we measure extraction fidelity (e.g., heading detection accuracy)?
2. Should the 3000–4000 word requirement be enforced strictly (hard fail) or with an automatic “length normalization” pass that expands/compresses sections to fit?
3. What regulatory jurisdictions must be explicitly supported (FDA, EU MDR/IVDR, UKCA, NMPA, PMDA), and should the system detect jurisdiction automatically or require user selection?
4. How should the system handle contradictory statements between the uploaded summary and grounded web sources—show both, pick one, or require user adjudication?
5. What is the required definition of an “entity” in the 20-entity list (named organizations only, or also processes/documents/standards), and should we enforce a minimum variety across entity types?
6. For the 5 required tables, should the system always generate the same table set, or adapt table themes to the document (while still guaranteeing exactly five)?
7. Should the infographic “code/spec” standardize on Vega-Lite, Plotly, or allow both—and what are the constraints for each regarding interactivity and export-to-HTML?
8. What accessibility targets should be enforced for painter styles (contrast ratios, colorblind-safe palettes), and how should we validate them automatically?
9. How will we implement bilingual output for highly technical regulatory terminology—use a glossary memory, user-editable term base, or model-based consistency checks?
10. Should users be able to lock a painter style into exports, or allow exports to include multiple themes (e.g., “print-friendly minimal” version)?
11. What is the expected maximum upload size and page count for PDFs on Hugging Face Spaces, and what user experience should occur when limits are exceeded?
12. Should the agent-by-agent editor support rich diffing (word-level) for markdown, and should users be able to annotate agent outputs with comments for later reuse?
13. How should token budgeting work across multi-pass generation (outline → draft → QA) to avoid blowing through max_tokens, especially with 12000 default?
14. Should we support “batch generation” of multiple medical documents in one session, and if so how will artifacts be organized and exported?
15. For the Note Keeper coral keyword highlighting, do we allow inline HTML rendering in Streamlit (security implications), or implement a safer custom renderer?
16. What are the six AI Magics’ default prompts and safety constraints to prevent content invention (e.g., adding actions that weren’t in the original note)?
17. Should the system provide a “compliance disclaimer” block in medical outputs, clarifying it’s not legal advice, and should that be mandatory in exports?
18. How do we validate that the 8 infographics are truly “based on the previous doc” (traceability rules, anchor requirements, minimum citations per chart)?
19. What caching strategy (if any) should be used to reduce cost and latency—prompt+input hashing per agent, with user-visible cache controls?
20. What testing approach will verify deterministic requirements (5 tables, 20 entities, 8 infographics, word count range) across providers with different structured-output reliability?
