import streamlit as st
import pdfplumber
import anthropic
import json
import io

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Script to Prompt",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Dark cinematic background */
  .stApp { background-color: #0a0a0b; color: #e5e5e5; }
  section[data-testid="stSidebar"] { background-color: #111113; border-right: 1px solid #1e1e22; }

  /* Hide default Streamlit chrome */
  #MainMenu, footer, header { visibility: hidden; }

  /* Headings */
  h1 { color: #fbbf24 !important; font-family: 'Georgia', serif; letter-spacing: 2px; }
  h2, h3 { color: #e5e5e5 !important; }

  /* Prompt text boxes */
  .prompt-box {
    background-color: #111113;
    border: 1px solid #1e1e22;
    border-left: 3px solid #d97706;
    border-radius: 6px;
    padding: 14px 16px;
    font-family: 'Courier New', monospace;
    font-size: 13px;
    line-height: 1.6;
    color: #d1d1d1;
    margin-bottom: 10px;
    white-space: pre-wrap;
  }

  /* Scene header */
  .scene-header {
    background: linear-gradient(90deg, #1a1408 0%, #111113 100%);
    border: 1px solid #2a2006;
    border-left: 4px solid #d97706;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 12px;
  }
  .scene-number { color: #d97706; font-family: monospace; font-size: 12px; letter-spacing: 2px; }
  .scene-title { color: #fbbf24; font-family: monospace; font-size: 15px; font-weight: bold; }
  .scene-synopsis { color: #9ca3af; font-size: 13px; margin-top: 6px; }

  /* Category badge */
  .badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 6px;
  }
  .badge-storyboard   { background: #1e3a5f; color: #60a5fa; }
  .badge-previz       { background: #1a3320; color: #4ade80; }
  .badge-style        { background: #3b1f5e; color: #c084fc; }
  .badge-character    { background: #5e1f1f; color: #f87171; }
  .badge-location     { background: #1f3a3a; color: #2dd4bf; }

  /* Upload area */
  [data-testid="stFileUploader"] {
    background-color: #111113;
    border: 2px dashed #2a2a30;
    border-radius: 10px;
    padding: 10px;
  }

  /* Buttons */
  .stButton > button {
    background-color: #d97706;
    color: #0a0a0b;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    padding: 10px 24px;
    letter-spacing: 1px;
  }
  .stButton > button:hover { background-color: #fbbf24; }

  /* Expander */
  .streamlit-expanderHeader { color: #9ca3af !important; }

  /* Input fields */
  .stTextInput > div > div > input, .stTextArea textarea {
    background-color: #111113 !important;
    color: #e5e5e5 !important;
    border: 1px solid #2a2a30 !important;
  }
</style>
""", unsafe_allow_html=True)

# ── Categories ────────────────────────────────────────────────────────────────
CATEGORIES = {
    "storyboard":  ("🎥", "Storyboard Shot",    "badge-storyboard"),
    "previz":      ("🏙️", "Pre-Visualization",  "badge-previz"),
    "style":       ("🎨", "Style / Mood Board",  "badge-style"),
    "character":   ("👤", "Character Design",    "badge-character"),
    "location":    ("📍", "Location Scout",      "badge-location"),
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def extract_text_from_pdf(file_bytes: bytes) -> str:
    text_pages = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_pages.append(t)
    return "\n\n".join(text_pages)

def build_system_prompt() -> str:
    return """You are a professional script breakdown supervisor and pre-production consultant with 20 years of experience in Hollywood feature films and immersive VR experiences.

Your task is to analyze a film or VR script and produce a structured breakdown with AI image generation prompts for each major scene.

RULES:
1. Identify scenes by their sluglines (INT./EXT. LOCATION - TIME) or narrative beats for VR scripts
2. Extract 8-20 of the most visually significant scenes — skip pure dialogue scenes with no visual action
3. For each scene, generate prompts ONLY for the requested categories
4. Every prompt must be SELF-CONTAINED and work standalone for Midjourney or DALL-E — include all needed context
5. Be specific and visual. Never use abstract words like "emotional" — describe what the camera actually sees
6. Return ONLY valid JSON — no markdown fences, no explanation, nothing outside the JSON

PROMPT WRITING STYLE PER CATEGORY:

storyboard: Camera angle (low angle / high angle / dutch / OTS), shot size (ECU / CU / MS / LS / aerial), subject + action, environment, lighting direction, camera movement if any.
Example: "Low angle medium shot, detective crouching behind overturned desk, gun aimed at dark hallway, fluorescent lights flickering overhead, handheld slight shake"

previz: Environment for 3D pre-viz or concept art. Location type, architectural style, time of day, weather, atmosphere, scale.
Example: "Vast industrial warehouse interior, concrete and corrugated steel, golden hour shafting through broken skylights, dust motes suspended in air, 30-foot ceilings, abandoned machinery throughout"

style: Visual language and cinematic references. Specific color palette, film stock feel, cinematographer or director reference, contrast, genre tone.
Example: "Desaturated teal and orange palette, high contrast, Roger Deakins naturalistic diffused lighting, reminiscent of No Country for Old Men, 35mm grain, 2.39:1 anamorphic widescreen"

character: Character appearance for concept artists. Age, build, clothing details, hair, skin tone, expression, distinctive features.
Example: "Woman, late 30s, athletic build, worn leather jacket over grey hoodie, dark jeans, dried blood on left sleeve, short dark hair disheveled, jaw set with determination, slight exhaustion around eyes"

location: Location manager briefing. Architectural style, materials, era, condition, spatial requirements, geographic region feel.
Example: "1970s brutalist municipal building exterior, raw poured concrete, wide imposing entrance steps, institutional scale, slightly weathered, Pacific Northwest mid-size city, overcast sky"

OUTPUT JSON SCHEMA:
{
  "script_title": "string",
  "total_scenes": number,
  "scenes": [
    {
      "scene_number": number,
      "slugline": "string",
      "synopsis": "string (2-3 sentences)",
      "characters": ["string"],
      "prompts": {
        "storyboard": "string or null",
        "previz": "string or null",
        "style": "string or null",
        "character": "string or null",
        "location": "string or null"
      }
    }
  ]
}

Only include prompt keys for the requested categories. Set others to null."""

def build_user_prompt(script_text: str, selected: list[str]) -> str:
    categories_str = ", ".join(selected)
    # Trim very long scripts to avoid token limits
    max_chars = 80000
    if len(script_text) > max_chars:
        script_text = script_text[:max_chars] + "\n\n[SCRIPT TRUNCATED FOR LENGTH]"
    return f"""Analyze this script and generate image generation prompts for each major scene.

REQUESTED PROMPT CATEGORIES: {categories_str}

Return ONLY valid JSON. No preamble, no explanation, no markdown code fences.

SCRIPT:
---
{script_text}
---"""

def call_claude(api_key: str, script_text: str, selected_categories: list[str]) -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=build_system_prompt(),
        messages=[{"role": "user", "content": build_user_prompt(script_text, selected_categories)}]
    )
    # Find text block (skip thinking blocks)
    raw = ""
    for block in response.content:
        if block.type == "text":
            raw = block.text.strip()
            break
    # Strip markdown fences if Claude added them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)

def render_prompt_block(category: str, prompt_text: str):
    icon, label, badge_class = CATEGORIES[category]
    st.markdown(f'<span class="badge {badge_class}">{icon} {label}</span>', unsafe_allow_html=True)
    st.markdown(f'<div class="prompt-box">{prompt_text}</div>', unsafe_allow_html=True)
    st.code(prompt_text, language=None)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Settings")
    api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-...",
        help="Get your key at console.anthropic.com"
    )
    st.markdown("---")
    st.markdown("## 🎬 Prompt Categories")
    st.markdown("Select what to generate for each scene:")
    selected_categories = []
    for key, (icon, label, _) in CATEGORIES.items():
        if st.checkbox(f"{icon} {label}", value=True, key=f"cat_{key}"):
            selected_categories.append(key)
    st.markdown("---")
    st.markdown("### About")
    st.markdown(
        "Upload a PDF film or VR script and get AI image generation prompts "
        "for storyboards, pre-viz, style, characters, and locations.",
        help=None
    )

# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown('<h1 style="text-align:center; margin-bottom:4px;">🎬 SCRIPT TO PROMPT</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align:center; color:#6b6b7b; letter-spacing:3px; font-size:12px; margin-bottom:32px;">PRE-PRODUCTION AI BREAKDOWN TOOL</p>', unsafe_allow_html=True)

# ── Upload ────────────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Drop your PDF script here",
    type=["pdf"],
    help="Upload a movie script or VR experience script in PDF format"
)

if uploaded_file:
    with st.spinner("Reading PDF..."):
        script_text = extract_text_from_pdf(uploaded_file.read())

    if len(script_text) < 200:
        st.error("⚠️ Could not extract text from this PDF. It may be a scanned document. Please use a text-based PDF.")
        st.stop()

    word_count = len(script_text.split())
    page_estimate = round(word_count / 200)

    col1, col2, col3 = st.columns(3)
    col1.metric("Words Extracted", f"{word_count:,}")
    col2.metric("Estimated Pages", f"~{page_estimate}")
    col3.metric("Categories Selected", len(selected_categories))

    with st.expander("📄 Preview extracted text", expanded=False):
        st.text(script_text[:3000] + ("..." if len(script_text) > 3000 else ""))

    st.markdown("---")

    # Validate before running
    if not api_key:
        st.warning("👈 Enter your Anthropic API key in the sidebar to continue.")
        st.stop()

    if not selected_categories:
        st.warning("👈 Select at least one prompt category in the sidebar.")
        st.stop()

    if "results" not in st.session_state:
        st.session_state.results = None
    if "last_file" not in st.session_state:
        st.session_state.last_file = None

    # Reset results if new file uploaded
    if st.session_state.last_file != uploaded_file.name:
        st.session_state.results = None
        st.session_state.last_file = uploaded_file.name

    col_btn, col_info = st.columns([2, 5])
    with col_btn:
        analyze = st.button("🎬 ANALYZE SCRIPT", use_container_width=True)
    with col_info:
        st.markdown(
            '<p style="color:#6b6b7b; font-size:13px; padding-top:10px;">'
            'Claude Opus will analyze your script and generate prompts for each scene. '
            'This may take 1–3 minutes for a full script.</p>',
            unsafe_allow_html=True
        )

    if analyze:
        with st.spinner("🎬 Claude is breaking down your script... this may take a minute or two..."):
            try:
                st.session_state.results = call_claude(api_key, script_text, selected_categories)
            except json.JSONDecodeError:
                st.error("Claude returned an unexpected response. Please try again.")
                st.stop()
            except anthropic.AuthenticationError:
                st.error("Invalid API key. Please check your Anthropic API key in the sidebar.")
                st.stop()
            except Exception as e:
                st.error(f"Something went wrong: {str(e)}")
                st.stop()

    # ── Results ───────────────────────────────────────────────────────────────
    if st.session_state.results:
        data = st.session_state.results
        scenes = data.get("scenes", [])
        title = data.get("script_title", uploaded_file.name)

        st.markdown(f"## 🎞️ {title}")
        st.markdown(f'<p style="color:#6b6b7b;">{len(scenes)} scenes analyzed · {len(selected_categories)} prompt categories</p>', unsafe_allow_html=True)

        # Export buttons
        st.markdown("---")
        col_e1, col_e2, col_e3 = st.columns(3)

        # Build export content
        markdown_export = f"# {title} — Script to Prompt\n\n"
        plain_export = f"{title.upper()} — SCRIPT TO PROMPT\n{'='*60}\n\n"
        for scene in scenes:
            slugline = scene.get('slugline', f"SCENE {scene.get('scene_number', '')}")
            synopsis = scene.get('synopsis', '')
            markdown_export += f"## SCENE {scene.get('scene_number', '')} — {slugline}\n\n"
            markdown_export += f"*{synopsis}*\n\n"
            plain_export += f"SCENE {scene.get('scene_number', '')} — {slugline}\n{synopsis}\n\n"
            for cat_key in selected_categories:
                prompt = scene.get('prompts', {}).get(cat_key)
                if prompt:
                    _, label, _ = CATEGORIES[cat_key]
                    markdown_export += f"**{label.upper()}:**\n```\n{prompt}\n```\n\n"
                    plain_export += f"{label.upper()}:\n{prompt}\n\n"
            markdown_export += "---\n\n"
            plain_export += "-"*60 + "\n\n"

        with col_e1:
            st.download_button(
                "⬇️ Export Markdown",
                data=markdown_export,
                file_name=f"{title.replace(' ', '_')}_prompts.md",
                mime="text/markdown",
                use_container_width=True
            )
        with col_e2:
            st.download_button(
                "⬇️ Export Plain Text",
                data=plain_export,
                file_name=f"{title.replace(' ', '_')}_prompts.txt",
                mime="text/plain",
                use_container_width=True
            )
        with col_e3:
            st.download_button(
                "⬇️ Export JSON",
                data=json.dumps(data, indent=2),
                file_name=f"{title.replace(' ', '_')}_prompts.json",
                mime="application/json",
                use_container_width=True
            )

        st.markdown("---")

        # Render each scene
        for scene in scenes:
            scene_num = scene.get("scene_number", "")
            slugline = scene.get("slugline", "")
            synopsis = scene.get("synopsis", "")
            characters = scene.get("characters", [])
            prompts = scene.get("prompts", {})

            # Scene header
            chars_str = " · ".join(characters) if characters else ""
            st.markdown(f"""
            <div class="scene-header">
                <div class="scene-number">SCENE {scene_num:02d}</div>
                <div class="scene-title">{slugline}</div>
                <div class="scene-synopsis">{synopsis}</div>
                {"<div style='color:#6b6b7b; font-size:12px; margin-top:6px;'>👥 " + chars_str + "</div>" if chars_str else ""}
            </div>
            """, unsafe_allow_html=True)

            # Prompts in columns (2 per row)
            prompt_items = [(k, v) for k, v in prompts.items() if v and k in selected_categories]

            for i in range(0, len(prompt_items), 2):
                cols = st.columns(2)
                for j, (cat_key, prompt_text) in enumerate(prompt_items[i:i+2]):
                    with cols[j]:
                        icon, label, badge_class = CATEGORIES[cat_key]
                        st.markdown(f'<span class="badge {badge_class}">{icon} {label}</span>', unsafe_allow_html=True)
                        st.text_area(
                            label="",
                            value=prompt_text,
                            height=120,
                            key=f"prompt_{scene_num}_{cat_key}",
                            label_visibility="collapsed"
                        )

            st.markdown("<br>", unsafe_allow_html=True)

else:
    # Empty state
    st.markdown("""
    <div style="text-align:center; padding: 60px 20px; color: #3a3a44;">
        <div style="font-size: 64px; margin-bottom: 16px;">🎬</div>
        <div style="font-size: 18px; color: #6b6b7b;">Upload a PDF script to get started</div>
        <div style="font-size: 13px; color: #3a3a44; margin-top: 8px;">
            Supports movie scripts, TV scripts, and VR experience scripts
        </div>
    </div>
    """, unsafe_allow_html=True)
