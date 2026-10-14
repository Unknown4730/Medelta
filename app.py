"""MedDelta-RAG Streamlit dashboard.

All research logic is imported from ``src/meddelta/`` — NO computation
lives in Streamlit callbacks.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Ensure the package is importable when running via `streamlit run app.py`
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from meddelta.config import DISCLAIMER, GENERATED_DIR
from meddelta.delta import calculate_delta
from meddelta.embed import load_embeddings
from meddelta.evidence import build_evidence_manifest
from meddelta.models import Observation
from meddelta.retrieval import retrieve_baseline

# ── Page config ───────────────────────────────────────────────────

st.set_page_config(
    page_title="MedDelta-RAG",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS for premium feel ───────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.disclaimer-banner {
    background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
    color: #fbbf24;
    padding: 12px 20px;
    text-align: center;
    font-weight: 600;
    font-size: 0.95rem;
    border-radius: 8px;
    margin-bottom: 1.2rem;
    letter-spacing: 0.3px;
}

.metric-card {
    background: linear-gradient(145deg, #1e293b, #0f172a);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

.metric-card h4 {
    color: #94a3b8;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 4px;
}

.metric-card .value {
    color: #e2e8f0;
    font-size: 1.5rem;
    font-weight: 700;
}

.record-card {
    background: linear-gradient(145deg, #1e293b, #0f172a);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 16px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

.record-card h3 {
    color: #38bdf8;
    margin-bottom: 12px;
    font-weight: 600;
}

.status-ok { color: #4ade80; font-weight: 700; }
.status-error { color: #f87171; font-weight: 700; }

.score-chip {
    display: inline-block;
    background: #334155;
    color: #e2e8f0;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.82rem;
    margin: 2px 4px;
}
</style>
""", unsafe_allow_html=True)

# ── Disclaimer banner ─────────────────────────────────────────────

st.markdown(f'<div class="disclaimer-banner">⚠️ {DISCLAIMER}</div>', unsafe_allow_html=True)

st.markdown("# 🔬 MedDelta-RAG Dashboard")
st.caption("Comparability-First Retrieval for Evidence-Linked Temporal Change Detection")

# ── Data loading ──────────────────────────────────────────────────


@st.cache_data
def load_corpus() -> list[Observation]:
    csv_path = GENERATED_DIR / "observations.csv"
    if not csv_path.exists():
        return []
    df = pd.read_csv(csv_path)
    corpus: list[Observation] = []
    for _, row in df.iterrows():
        corpus.append(Observation(
            record_id=str(row["record_id"]),
            patient_id=str(row["patient_id"]),
            observed_at=datetime.fromisoformat(str(row["observed_at"])),
            concept_code=str(row["concept_code"]),
            concept_label=str(row["concept_label"]),
            value=float(row["value"]),
            unit=str(row["unit"]),
            canonical_value=float(row["canonical_value"]),
            canonical_unit=str(row["canonical_unit"]),
            condition_context=str(row["condition_context"]) if pd.notna(row.get("condition_context")) else None,
            anatomical_site=str(row["anatomical_site"]) if pd.notna(row.get("anatomical_site")) else None,
            note_text=str(row.get("note_text", "")),
            source_type=str(row.get("source_type", "lab")),
            is_synthetic=True,
        ))
    return corpus


@st.cache_resource
def load_emb():
    try:
        return load_embeddings()
    except Exception:
        return None


corpus = load_corpus()

if not corpus:
    st.error(
        "No generated data found. Run `python scripts/generate_dataset.py` first."
    )
    st.stop()

embeddings = load_emb()

# ── Sidebar controls ──────────────────────────────────────────────

st.sidebar.markdown("## ⚙️ Controls")

method_labels = {
    "M1 — Metadata-only": "metadata_only",
    "M2 — Semantic-only": "semantic_only",
    "M3 — Hybrid (proposed)": "hybrid",
}
selected_label = st.sidebar.radio("**Retrieval Method**", list(method_labels.keys()), index=2)
method = method_labels[selected_label]

patients = sorted({obs.patient_id for obs in corpus})
patient = st.sidebar.selectbox("**Patient**", patients)

patient_obs = [obs for obs in corpus if obs.patient_id == patient]
patient_obs.sort(key=lambda o: o.observed_at)

obs_options = {
    f"{obs.record_id}  |  {obs.concept_code}  |  {obs.observed_at.strftime('%Y-%m-%d')}": obs
    for obs in patient_obs
}
if not obs_options:
    st.warning("No observations for selected patient.")
    st.stop()

selected_key = st.sidebar.selectbox(
    "**Current Observation**", list(obs_options.keys()),
    index=len(obs_options) - 1,
)
current = obs_options[selected_key]

# ── Run retrieval ─────────────────────────────────────────────────

result = retrieve_baseline(current, f"Compare current {current.concept_code} with baseline", corpus, method, embeddings, top_k=3)

delta_result = None
baseline = None
if result.ranked_candidates:
    baseline = result.ranked_candidates[0].observation
    delta_result = calculate_delta(current, baseline)

manifest = build_evidence_manifest(current, result, delta_result)

# ── Main content ──────────────────────────────────────────────────

col_cur, col_base = st.columns(2)

with col_cur:
    st.markdown('<div class="record-card"><h3>📋 Current Observation</h3>', unsafe_allow_html=True)
    st.markdown(f"**Record ID:** `{current.record_id}`")
    st.markdown(f"**Date:** {current.observed_at.strftime('%Y-%m-%d %H:%M')}")
    st.markdown(f"**Concept:** {current.concept_label} (`{current.concept_code}`)")
    st.markdown(f"**Value:** {current.value:.4f} {current.unit}")
    st.markdown(f"**Canonical:** {current.canonical_value:.4f} {current.canonical_unit}")
    if current.anatomical_site:
        st.markdown(f"**Site:** {current.anatomical_site}")
    st.markdown(f"**Context:** {current.condition_context or 'N/A'}")
    st.caption(current.note_text)
    st.markdown('</div>', unsafe_allow_html=True)

with col_base:
    st.markdown('<div class="record-card"><h3>🔍 Retrieved Baseline</h3>', unsafe_allow_html=True)
    if baseline:
        status_cls = "status-ok" if result.status == "OK" else "status-error"
        st.markdown(f'**Status:** <span class="{status_cls}">{result.status}</span>', unsafe_allow_html=True)
        st.markdown(f"**Record ID:** `{baseline.record_id}`")
        st.markdown(f"**Date:** {baseline.observed_at.strftime('%Y-%m-%d %H:%M')}")
        st.markdown(f"**Value:** {baseline.value:.4f} {baseline.unit}")
        st.markdown(f"**Canonical:** {baseline.canonical_value:.4f} {baseline.canonical_unit}")
        if baseline.anatomical_site:
            st.markdown(f"**Site:** {baseline.anatomical_site}")

        # Score display
        if result.ranked_candidates[0].score_components:
            sc = result.ranked_candidates[0].score_components
            chips = " ".join(
                f'<span class="score-chip">{k}: {v:.3f}</span>'
                for k, v in sc.items()
            )
            st.markdown(f"**Scores:** {chips}", unsafe_allow_html=True)
        st.markdown(f"**Combined Score:** {result.ranked_candidates[0].score:.4f}")
    else:
        st.markdown(f'<span class="status-error">⚠️ {result.status}</span>', unsafe_allow_html=True)
        st.info("No comparable baseline found for this observation with the selected method.")
    st.markdown('</div>', unsafe_allow_html=True)

# ── Delta results ─────────────────────────────────────────────────

st.markdown("---")
st.markdown("### 📊 Delta Results")

if delta_result:
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Absolute Change", f"{delta_result.absolute_change:+.4f}")
    d2.metric(
        "Percentage Change",
        f"{delta_result.percentage_change:+.2f}%" if delta_result.percentage_change is not None else "Undefined",
    )
    d3.metric("Change / Day", f"{delta_result.change_per_day:+.6f}")
    d4.metric("Elapsed Days", f"{delta_result.elapsed_days:.1f}")
    if delta_result.status != "OK":
        st.warning(f"Delta status: **{delta_result.status}**")
else:
    st.info("No delta computed — no valid baseline selected.")

# ── Evidence manifest ─────────────────────────────────────────────

st.markdown("---")
with st.expander("📑 Evidence Manifest", expanded=False):
    e1, e2 = st.columns(2)
    with e1:
        st.markdown("**Current Record**")
        st.json({
            "record_id": manifest.current_record.record_id,
            "observed_at": manifest.current_record.observed_at.isoformat(),
            "value": manifest.current_record.value,
            "unit": manifest.current_record.unit,
            "canonical_value": manifest.current_record.canonical_value,
            "canonical_unit": manifest.current_record.canonical_unit,
        })
    with e2:
        if manifest.baseline_record:
            st.markdown("**Baseline Record**")
            st.json({
                "record_id": manifest.baseline_record.record_id,
                "observed_at": manifest.baseline_record.observed_at.isoformat(),
                "value": manifest.baseline_record.value,
                "unit": manifest.baseline_record.unit,
                "canonical_value": manifest.baseline_record.canonical_value,
                "canonical_unit": manifest.baseline_record.canonical_unit,
            })
        else:
            st.markdown("**Baseline Record:** None")

    st.markdown(f"**Formula Version:** `{manifest.formula_version}`")
    st.markdown(f"**Method:** `{manifest.retrieval_result.method}`")
    if manifest.warnings:
        for w in manifest.warnings:
            st.warning(w)

# ── Timeline visualization ────────────────────────────────────────

st.markdown("---")
st.markdown("### 📈 Patient Timeline")

timeline_data = []
for obs in patient_obs:
    is_current = obs.record_id == current.record_id
    is_baseline = baseline and obs.record_id == baseline.record_id
    role = "Current" if is_current else ("Baseline" if is_baseline else "Other")
    timeline_data.append({
        "Date": obs.observed_at,
        "Value": obs.canonical_value,
        "Concept": obs.concept_code,
        "Record ID": obs.record_id,
        "Role": role,
        "Size": 14 if is_current or is_baseline else 6,
    })

if timeline_data:
    tdf = pd.DataFrame(timeline_data)
    fig = px.scatter(
        tdf,
        x="Date",
        y="Value",
        color="Concept",
        size="Size",
        hover_data=["Record ID", "Role"],
        title=f"Observations for {patient}",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(15,23,42,0.8)",
        paper_bgcolor="rgba(15,23,42,0.8)",
        font=dict(family="Inter", color="#e2e8f0"),
        title_font_size=18,
        hoverlabel=dict(bgcolor="#1e293b", font_size=12),
    )

    # Highlight current & baseline
    if baseline:
        fig.add_trace(go.Scatter(
            x=[current.observed_at, baseline.observed_at],
            y=[current.canonical_value, baseline.canonical_value],
            mode="lines",
            line=dict(color="#fbbf24", width=2, dash="dash"),
            name="Delta Link",
            showlegend=True,
        ))

    st.plotly_chart(fig, use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────

st.markdown("---")
st.caption(DISCLAIMER)
