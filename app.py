#!/usr/bin/env python3
"""app.py — Streamlit frontend: PDF → Markdown + Anki deck (localhost).

Run with: streamlit run app.py
"""
from __future__ import annotations

import time
import tempfile
from pathlib import Path

import streamlit as st

from md_converter.pipeline import convert_pdf
from md_converter.optimizer import Mode
from md_converter.anki_generator import generate_deck, GeneratorOptions
from md_converter.anki_exporter import cards_to_csv, cards_to_txt

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="PDF → Anki",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS injection ─────────────────────────────────────────────────────────────

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=IBM+Plex+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

*, *::before, *::after { box-sizing: border-box; }

[data-testid="stApp"],
[data-testid="stAppViewContainer"],
.main .block-container {
    background-color: #0f0f14 !important;
    color: #e8e6e0 !important;
    font-family: 'IBM Plex Sans', sans-serif;
    max-width: 1400px;
}

.page-title {
    font-family: 'Playfair Display', serif;
    font-size: 2.8rem;
    font-weight: 700;
    color: #f0a500;
    letter-spacing: -0.03em;
    line-height: 1.1;
    margin-bottom: 0.2rem;
}

.page-subtitle {
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 0.82rem;
    font-weight: 300;
    color: #5a5a6a;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    margin-bottom: 2.5rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid #2a2a38;
}

.section-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: #5a5a6a;
    margin-bottom: 0.75rem;
}

.stButton > button {
    background: linear-gradient(135deg, #f0a500 0%, #d09000 100%) !important;
    color: #0f0f14 !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    border: none !important;
    border-radius: 3px !important;
    padding: 0.7rem 2rem !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 16px rgba(240,165,0,0.2) !important;
    width: 100% !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 28px rgba(240,165,0,0.4) !important;
}

[data-testid="stFileUploader"] {
    background: #1a1a24;
    border: 1px dashed #3a3a4a;
    border-radius: 8px;
    padding: 1rem;
    transition: border-color 0.25s;
}
[data-testid="stFileUploader"]:hover { border-color: #f0a500; }

.stats-row {
    display: flex;
    gap: 1px;
    border: 1px solid #2a2a38;
    border-radius: 6px;
    overflow: hidden;
    background: #2a2a38;
    margin: 1.5rem 0;
}
.stat-block {
    flex: 1;
    background: #1a1a24;
    padding: 1.1rem 0.75rem;
    text-align: center;
}
.stat-number {
    font-family: 'Playfair Display', serif;
    font-size: 1.8rem;
    color: #f0a500;
    line-height: 1;
    margin-bottom: 0.25rem;
}
.stat-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #4a4a5a;
    text-transform: uppercase;
    letter-spacing: 0.13em;
}

.markdown-box {
    background: #0c0c11;
    border: 1px solid #2a2a38;
    border-radius: 6px;
    padding: 1.25rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    line-height: 1.75;
    color: #9a9890;
    max-height: 460px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
}

.anki-card {
    background: #1a1a24;
    border: 1px solid #252530;
    border-left: 3px solid #2a2a38;
    border-radius: 4px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 0.55rem;
    transition: all 0.18s ease;
}
.anki-card:hover {
    border-color: #353545;
    border-left-color: #f0a500;
    transform: translateX(3px);
}
.card-front {
    font-family: 'IBM Plex Sans', sans-serif;
    font-weight: 500;
    font-size: 0.88rem;
    color: #dddbd5;
    margin-bottom: 0.4rem;
}
.card-back {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: #6a6a7a;
    line-height: 1.6;
    border-top: 1px solid #252530;
    padding-top: 0.45rem;
    margin-top: 0.2rem;
}

.badge {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    padding: 0.1rem 0.45rem;
    border-radius: 2px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-right: 0.5rem;
    vertical-align: middle;
}
.badge-definition  { background: #0a2040; color: #4a9eff; border: 1px solid #1a4070; }
.badge-theorem     { background: #300a18; color: #ff5070; border: 1px solid #601828; }
.badge-property    { background: #300a18; color: #ff5070; border: 1px solid #601828; }
.badge-formula     { background: #1a0830; color: #c040ff; border: 1px solid #400860; }
.badge-method      { background: #082018; color: #40df80; border: 1px solid #185030; }
.badge-enumeration { background: #281500; color: #f0a500; border: 1px solid #503000; }
.badge-default     { background: #181820; color: #707080; border: 1px solid #282838; }

[data-testid="stDownloadButton"] > button {
    background: transparent !important;
    border: 1px solid #2a2a38 !important;
    color: #9a9890 !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-size: 0.78rem !important;
    padding: 0.45rem 1rem !important;
    border-radius: 3px !important;
    transition: all 0.18s ease !important;
    width: 100% !important;
}
[data-testid="stDownloadButton"] > button:hover {
    border-color: #f0a500 !important;
    color: #f0a500 !important;
}

[data-testid="stRadio"] label,
[data-testid="stSlider"] label {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.72rem !important;
    color: #5a5a6a !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

div[data-testid="stProgress"] > div { background: #1a1a24 !important; }
div[data-testid="stProgress"] > div > div { background: linear-gradient(90deg, #f0a500, #ffb830) !important; }
"""

st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown('<h1 class="page-title">PDF → Anki</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="page-subtitle">Conversion PDF · Génération de cartes de révision</p>',
    unsafe_allow_html=True,
)

# ── Upload + Options ──────────────────────────────────────────────────────────

col_upload, col_opts = st.columns([1.3, 1])

with col_upload:
    st.markdown('<p class="section-label">Fichier PDF</p>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Déposer un fichier PDF",
        type=["pdf"],
        label_visibility="collapsed",
    )

def _sync_slider_to_state() -> None:
    st.session_state["total_cards"] = st.session_state["_tc_slider"]


def _sync_input_to_state() -> None:
    st.session_state["total_cards"] = max(5, min(50, int(st.session_state["_tc_input"])))


if "total_cards" not in st.session_state:
    st.session_state["total_cards"] = 20

with col_opts:
    st.markdown('<p class="section-label">Options</p>', unsafe_allow_html=True)
    mode_choice = st.radio("Mode de conversion", ["Fidelity", "Compact"], horizontal=True)
    format_choice = st.radio("Format export Anki", ["CSV", "TXT", "Les deux"], horizontal=True)

    st.markdown(
        '<p style="font-family:\'JetBrains Mono\',monospace;font-size:0.72rem;'
        'color:#5a5a6a;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.2rem;">'
        'Nombre de cartes par PDF</p>',
        unsafe_allow_html=True,
    )
    st.caption("Nombre total de cartes générées pour chaque PDF.")
    col_slide, col_num = st.columns([3, 1])
    with col_slide:
        st.slider(
            "Nombre de cartes par PDF",
            min_value=5, max_value=50, step=1,
            value=st.session_state["total_cards"],
            key="_tc_slider",
            on_change=_sync_slider_to_state,
            label_visibility="collapsed",
        )
    with col_num:
        st.number_input(
            "Valeur",
            min_value=5, max_value=50, step=1,
            value=st.session_state["total_cards"],
            key="_tc_input",
            on_change=_sync_input_to_state,
            label_visibility="collapsed",
        )

    min_length = st.slider("Longueur min. réponse (caractères)", min_value=5, max_value=100, value=20)
    min_quality = st.slider("Score qualité minimum (0-100)", min_value=0, max_value=100, value=30)
    st.markdown("<br>", unsafe_allow_html=True)
    convert_btn = st.button("Convertir", use_container_width=True)

# ── Conversion ────────────────────────────────────────────────────────────────

_TYPE_BADGE: dict[str, str] = {
    "definition": "badge-definition",
    "theorem": "badge-theorem",
    "property": "badge-property",
    "formula": "badge-formula",
    "method": "badge-method",
    "enumeration": "badge-enumeration",
}

if uploaded_file and convert_btn:
    t_start = time.time()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    progress = st.progress(0, text="Détection du type de PDF…")

    try:
        md_mode = Mode.FIDELITY if mode_choice == "Fidelity" else Mode.COMPACT
        progress.progress(15, text="Extraction du contenu…")
        markdown, report = convert_pdf(tmp_path, mode=md_mode)

        progress.progress(55, text="Nettoyage et structuration…")
        source_name = Path(uploaded_file.name).stem
        gen_opts = GeneratorOptions(
            total_cards_per_pdf=st.session_state["total_cards"],
            min_answer_length=min_length,
            min_quality_score=float(min_quality),
            source_name=source_name,
        )

        progress.progress(70, text="Génération des cartes Anki…")
        cards, filtered_count = generate_deck(markdown, gen_opts)

        progress.progress(90, text="Préparation des exports…")
        fmt_map = {"CSV": "csv", "TXT": "txt", "Les deux": "both"}
        fmt = fmt_map[format_choice]
        csv_str = cards_to_csv(cards) if fmt in ("csv", "both") else ""
        txt_str = cards_to_txt(cards) if fmt in ("txt", "both") else ""

        elapsed = time.time() - t_start
        progress.progress(100, text="Terminé !")
        time.sleep(0.35)
        progress.empty()

    except Exception as exc:
        progress.empty()
        st.error(f"Erreur de conversion : {exc}")
        st.stop()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # ── Stats ──────────────────────────────────────────────────────────────────

    avg_quality = round(sum(c.quality_score for c in cards) / max(1, len(cards)), 1)
    st.markdown(f"""
<div class="stats-row">
  <div class="stat-block">
    <div class="stat-number">{report.total_pages}</div>
    <div class="stat-label">Pages</div>
  </div>
  <div class="stat-block">
    <div class="stat-number">{report.sections_detected}</div>
    <div class="stat-label">Sections</div>
  </div>
  <div class="stat-block">
    <div class="stat-number">{report.tokens_after}</div>
    <div class="stat-label">Tokens</div>
  </div>
  <div class="stat-block">
    <div class="stat-number">{len(cards)}</div>
    <div class="stat-label">Cartes</div>
  </div>
  <div class="stat-block">
    <div class="stat-number">{filtered_count}</div>
    <div class="stat-label">Filtrées</div>
  </div>
  <div class="stat-block">
    <div class="stat-number">{avg_quality}</div>
    <div class="stat-label">Score moyen</div>
  </div>
  <div class="stat-block">
    <div class="stat-number">{elapsed:.1f}s</div>
    <div class="stat-label">Durée</div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Results ───────────────────────────────────────────────────────────────

    col_md, col_anki = st.columns([1, 1])

    with col_md:
        st.markdown('<p class="section-label">Aperçu Markdown</p>', unsafe_allow_html=True)
        preview = markdown[:3000]
        if len(markdown) > 3000:
            preview += "\n\n[… tronqué pour l'aperçu]"
        st.markdown(f'<div class="markdown-box">{preview}</div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(
            "↓ Télécharger .md",
            data=markdown.encode("utf-8"),
            file_name=f"{source_name}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with col_anki:
        st.markdown(
            f'<p class="section-label">Cartes Anki — {len(cards)} générées, {filtered_count} filtrées</p>',
            unsafe_allow_html=True,
        )

        cards_html = ""
        display_cards = cards[:12]
        for card in display_cards:
            badge_cls = _TYPE_BADGE.get(card.card_type, "badge-default")
            back_preview = card.back[:160].replace("\n", " ")
            if len(card.back) > 160:
                back_preview += "…"
            snippet_preview = card.source_snippet[:100].replace("\n", " ") if card.source_snippet else ""
            score_color = "#f0a500" if card.quality_score >= 60 else ("#8888aa" if card.quality_score >= 40 else "#663333")
            cards_html += f"""<div class="anki-card">
  <span class="badge {badge_cls}">{card.card_type}</span>
  <span style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;color:{score_color};float:right;">q={card.quality_score:.0f}</span>
  <div class="card-front">{card.front}</div>
  <div class="card-back">{back_preview}</div>
  {f'<div style="font-size:0.65rem;color:#3a3a5a;font-family:JetBrains Mono,monospace;margin-top:0.3rem;border-top:1px solid #1e1e2e;padding-top:0.25rem;">↳ {snippet_preview}</div>' if snippet_preview else ''}
</div>"""

        if len(cards) > 12:
            cards_html += (
                f'<p style="color:#3a3a4a;font-size:0.72rem;text-align:center;'
                f'font-family:JetBrains Mono,monospace;padding-top:0.5rem;">'
                f'+{len(cards) - 12} cartes supplémentaires dans le fichier</p>'
            )

        st.markdown(cards_html, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        dl1, dl2 = st.columns(2)
        if csv_str:
            with dl1:
                st.download_button(
                    "↓ .anki.csv",
                    data=csv_str.encode("utf-8"),
                    file_name=f"{source_name}.anki.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
        if txt_str:
            with dl2:
                st.download_button(
                    "↓ .anki.txt",
                    data=txt_str.encode("utf-8"),
                    file_name=f"{source_name}.anki.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
