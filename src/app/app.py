"""
Patent Search Demo - Streamlit UI

Interactive search interface for the Patents Analyzer RAG pipeline.
Supports hybrid retrieval (BM25 + Semantic + Knowledge Graph) with LLM-generated answers.

Usage:
    uv run streamlit run app.py
"""

import json
import re
import sys
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# --- Path setup ---
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.logging_config import setup_logging  # noqa: E402

# --- Constants ---
RAW_DIR = project_root / "data" / "raw"
DATA_DIR = project_root / "data" / "processed"
PATENTS_PATH = DATA_DIR / "patents.json"
BM25_PATH = DATA_DIR / "bm25_index.pkl"
FAISS_PATH = DATA_DIR / "faiss.index"
CHUNK_IDS_PATH = DATA_DIR / "chunk_ids.json"
KG_PATH = DATA_DIR / "knowledge_graph.db"


# ---------------------------------------------------------------------------
# Data loading & retriever initialization (cached)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_patents_data():
    """Load and parse patents.json. Returns (patents_info, all_chunks, patent_files)."""
    if not PATENTS_PATH.exists():
        return None, None, None

    with open(PATENTS_PATH) as f:
        data = json.load(f)

    all_chunks = data.get("chunks", [])
    patent_files = {}  # patent_id -> filename
    patents_info = []

    for patent in data["patents"]:
        patent_id = patent["patent_id"]
        filename = patent.get("metadata", {}).get("filename", "")
        if filename:
            patent_files[patent_id] = filename

        # Use title from patent summary; fall back to patent_id
        title = patent.get("title", patent_id)

        # If title is generic, try to find the real title from (54) field in chunks
        if title in (patent_id, "Unknown Title"):
            for chunk in all_chunks:
                if chunk.get("patent_id") != patent_id:
                    continue
                content = chunk.get("content", "")
                if content.strip().startswith("(54)"):
                    title = content.strip().removeprefix("(54)").strip()
                    title = title.split("\n")[0].strip()
                    break

        patents_info.append(
            {
                "patent_id": patent_id,
                "title": title,
                "chunk_count": patent.get("num_chunks", 0),
            }
        )

    return patents_info, all_chunks, patent_files


@st.cache_data(show_spinner=False, max_entries=50)
def _render_pdf_page_base(pdf_path: str, page_number: int) -> tuple[bytes, float, float, int, int] | None:
    """Render a PDF page to PNG without highlights. Cached by (path, page) only.

    Returns (png_bytes, pdf_width, pdf_height, px_width, px_height), or None if rendering fails.
    """
    import fitz  # PyMuPDF

    path = Path(pdf_path)
    if not path.exists():
        return None

    doc = fitz.open(str(path))
    page_idx = page_number - 1  # metadata is 1-indexed, PyMuPDF is 0-indexed
    if page_idx < 0 or page_idx >= len(doc):
        doc.close()
        return None

    page = doc[page_idx]
    pdf_w, pdf_h = page.rect.width, page.rect.height

    # Render at 150 DPI for good readability
    pixmap = page.get_pixmap(dpi=150)
    img_bytes = pixmap.tobytes("png")
    px_w, px_h = pixmap.width, pixmap.height

    doc.close()
    return img_bytes, pdf_w, pdf_h, px_w, px_h


def render_pdf_page(pdf_path: str, page_number: int, highlight_text: str) -> bytes | None:
    """Render a PDF page as PNG with yellow highlights on matching text.

    The base page render is cached by (path, page) only, so viewing different
    chunks on the same page always reuses the cached render. Highlights are
    applied fresh on every call to ensure the correct text is highlighted.

    Args:
        pdf_path: Absolute path to the PDF file.
        page_number: 1-indexed page number (as stored in chunk metadata).
        highlight_text: Chunk content to search for and highlight.

    Returns:
        PNG image bytes, or None if rendering fails.
    """
    import fitz  # PyMuPDF
    import io
    from PIL import Image, ImageDraw

    base = _render_pdf_page_base(pdf_path, page_number)
    if base is None:
        return None

    img_bytes, pdf_w, pdf_h, px_w, px_h = base
    scale_x = px_w / pdf_w
    scale_y = px_h / pdf_h

    # Re-open the document only for text search (no re-rendering)
    path = Path(pdf_path)
    doc = fitz.open(str(path))
    page_idx = page_number - 1
    page = doc[page_idx]

    # Extract short phrases from the chunk text for searching.
    # Full content is too long for exact match; use first ~80 chars of each
    # sentence to get better hit rate on the actual PDF text.
    sentences = [s.strip() for s in highlight_text.replace("\n", " ").split(".") if s.strip()]
    rects_px: list[tuple[float, float, float, float]] = []
    for sentence in sentences:
        snippet = sentence[:80]
        if len(snippet) < 10:
            continue
        for rect in page.search_for(snippet):
            rects_px.append((
                rect.x0 * scale_x,
                rect.y0 * scale_y,
                rect.x1 * scale_x,
                rect.y1 * scale_y,
            ))

    doc.close()

    if not rects_px:
        return img_bytes  # No text matches found; return the base image as-is

    # Overlay semi-transparent yellow highlights using PIL
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for x0, y0, x1, y1 in rects_px:
        draw.rectangle([x0, y0, x1, y1], fill=(255, 220, 0, 120))
    highlighted = Image.alpha_composite(img, overlay).convert("RGB")

    buf = io.BytesIO()
    highlighted.save(buf, format="PNG")
    return buf.getvalue()


@st.cache_resource(show_spinner=False)
def init_retrievers():
    """Initialize all retrievers (expensive, cached for session)."""
    from src.knowledge_graph.store import KnowledgeGraphStore
    from src.retrieval import BM25Retriever, GraphRetriever, SemanticRetriever

    _, all_chunks, _ = load_patents_data()
    if all_chunks is None:
        return None

    bm25 = BM25Retriever.load(str(BM25_PATH), all_chunks)
    semantic = SemanticRetriever.load(str(FAISS_PATH), str(CHUNK_IDS_PATH), all_chunks)
    kg_store = KnowledgeGraphStore(str(KG_PATH))
    kg_store.connect(check_same_thread=False)
    graph = GraphRetriever.load(
        path="",
        chunks=all_chunks,
        kg_store=kg_store,
        max_hops=2,
        score_decay=0.5,
    )

    return {
        "bm25": bm25,
        "semantic": semantic,
        "graph": graph,
        "kg_store": kg_store,
    }


@st.cache_resource(show_spinner=False)
def init_reranker():
    """Initialize cross-encoder reranker if enabled via env (expensive, cached for session)."""
    from src.retrieval import reranker_from_env

    return reranker_from_env()


@st.cache_resource(show_spinner=False)
def init_llm():
    """Initialize LLM client."""
    from src.llm import LLMClient

    try:
        return LLMClient.from_env()
    except Exception:
        return LLMClient(model="ollama/llama3.1:8b")


# ---------------------------------------------------------------------------
# Search logic
# ---------------------------------------------------------------------------
def run_retrieval(query: str, selected_patents: list[str], top_k: int, weights: dict):
    """Run hybrid retrieval only (no LLM call). Returns (results, stats) or None."""
    from src.retrieval import HybridRetriever

    retrievers = init_retrievers()
    if retrievers is None:
        return None

    hybrid = HybridRetriever(
        bm25_retriever=retrievers["bm25"],
        semantic_retriever=retrievers["semantic"],
        graph_retriever=retrievers["graph"],
        weights=weights,
        rrf_k=60,
        reranker=init_reranker(),
    )

    retrieval_top_k = top_k * 3 if selected_patents else top_k
    results = hybrid.search(query, top_k=retrieval_top_k)

    if selected_patents:
        results = [r for r in results if r.get("patent_id") in selected_patents]
        results = results[:top_k]

    stats = hybrid.get_retriever_stats(results)
    return results, stats


def build_answer_stream(query: str, results: list[dict], max_context_chunks: int):
    """Prepare a streaming answer generator. Returns (chunk_generator, answer_metadata)."""
    from src.llm import AnswerGenerator

    llm_client = init_llm()
    generator = AnswerGenerator(
        llm_client=llm_client,
        max_context_chunks=max_context_chunks,
        include_metadata=True,
    )
    return generator.stream_answer(
        question=query,
        retrieved_chunks=results,
        temperature=0.0,
    )


# ---------------------------------------------------------------------------
# Inline citation helpers
# ---------------------------------------------------------------------------
SOURCE_REF_CSS = """
<style>
.source-ref {
    display: inline;
    background: #e8f0fe;
    border: 1px dashed #4a90d9;
    border-radius: 12px;
    padding: 1px 8px;
    font-size: 0.82em;
    color: #1a56db;
    cursor: pointer;
    text-decoration: none;
    white-space: nowrap;
    transition: background 0.2s, box-shadow 0.2s;
}
.source-ref:hover {
    background: #d0e2fc;
    box-shadow: 0 0 4px rgba(74, 144, 217, 0.4);
}
</style>
"""


def build_source_map(answer_meta: dict, patent_files: dict[str, str]) -> dict[int, str]:
    """Map 1-based source numbers to rich display labels.

    Returns e.g. {1: "EP2390376B1 | Detailed Description | Page 4"}
    """
    source_map: dict[int, str] = {}
    for i, src in enumerate(answer_meta.get("sources", []), start=1):
        patent_id = src.get("patent_id", "?")
        display_id = Path(patent_files.get(patent_id, "")).stem or patent_id
        section = src.get("section", "")
        page = src.get("page", "")
        parts = [display_id]
        if section:
            parts.append(section)
        if page:
            parts.append(f"Page {page}")
        label = " | ".join(parts)
        source_map[i] = label
    return source_map


def _make_citation_span(num: int, source_map: dict[int, str]) -> str | None:
    """Return an HTML badge span for a source number, or None if unknown."""
    label = source_map.get(num)
    if label is None:
        return None
    idx = num - 1  # 0-based index for DOM matching
    return (
        f'<span class="source-ref" data-source-idx="{idx}" '
        f'title="Click to view source">[{num}][{label}]</span>'
    )


def enrich_citations(text: str, source_map: dict[int, str]) -> str:
    """Replace source citation markers with styled, clickable HTML spans.

    Handles LLM citation styles:
    - Bracketed: [Source 1], [Source 1, Source 2]
    - Unbracketed: Source 3, Source 3 (Section: ..., Page: 7)
    """
    # Pass 1: Bracketed forms — [Source X], [Source 1, Source 2, ...]
    bracketed = r"\[(?:Source\s*\d+(?:\s*,\s*)?)+\]"

    def _replace_bracketed(match):
        full = match.group(0)
        nums = [int(n) for n in re.findall(r"Source\s*(\d+)", full)]
        if not nums:
            return full
        spans = []
        for num in nums:
            span = _make_citation_span(num, source_map)
            spans.append(span if span else f"[Source {num}]")
        return " ".join(spans)

    text = re.sub(bracketed, _replace_bracketed, text)

    # Pass 2: Unbracketed — "Source 3" optionally followed by "(Section: ..., Page: ...)"
    # Capital S + digit distinguishes citations from the word "source" in prose.
    unbracketed = r"Source\s+(\d+)(?:\s*\([^)]*\))?"

    def _replace_unbracketed(match):
        num = int(match.group(1))
        span = _make_citation_span(num, source_map)
        return span if span else match.group(0)

    text = re.sub(unbracketed, _replace_unbracketed, text)

    return text


def inject_source_scroll_js():
    """Inject JS that wires click-to-scroll + expand on source citation badges."""
    components.html(
        """
        <script>
        setTimeout(function() {
            var main = window.parent.document.querySelector('[data-testid="stMainBlockContainer"]')
                    || window.parent.document.querySelector('section.main');
            if (!main) return;

            var expanders = main.querySelectorAll('[data-testid="stExpander"]');
            var refs = main.querySelectorAll('.source-ref');

            refs.forEach(function(ref) {
                ref.addEventListener('click', function() {
                    var idx = parseInt(this.getAttribute('data-source-idx'), 10);
                    if (isNaN(idx) || idx >= expanders.length) return;

                    var expander = expanders[idx];
                    var details = expander.querySelector('details');
                    if (details && !details.open) {
                        var summary = details.querySelector('summary');
                        if (summary) summary.click();
                    }

                    expander.scrollIntoView({behavior: 'smooth', block: 'center'});
                    expander.style.boxShadow = '0 0 0 3px #4a90d9';
                    setTimeout(function() {
                        expander.style.boxShadow = '';
                    }, 2000);
                });
            });
        }, 150);
        </script>
        """,
        height=0,
    )


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------
def render_sources(results: list[dict], patent_files: dict[str, str]):
    """Render source chunks as expandable cards with View PDF buttons."""
    st.subheader("Sources")
    if not results:
        st.info("No matching passages to display.")
        return
    for i, r in enumerate(results):
        metadata = r.get("metadata", {})
        patent_id = r.get("patent_id", "?")
        section = metadata.get("section", "")
        page = metadata.get("page", "")
        rrf = r.get("rrf_score", 0)
        rank = i + 1
        content = r.get("content", "")

        # Build retriever tags
        retriever_tags = []
        if r.get("bm25_rank", 0) > 0:
            retriever_tags.append("BM25")
        if r.get("semantic_rank", 0) > 0:
            retriever_tags.append("Semantic")
        if r.get("graph_rank", 0) > 0:
            retriever_tags.append("Graph")

        display_id = Path(patent_files.get(patent_id, "")).stem or patent_id
        page_str = f" | Page {page}" if page else ""
        section_str = f" | {section}" if section else ""
        header = f"**[{rank}]** {display_id}{section_str}{page_str}"

        with st.expander(header):
            st.text(content)
            # Show View PDF button if the PDF file exists
            if patent_id in patent_files and page:
                pdf_path = RAW_DIR / patent_files[patent_id]
                if pdf_path.exists() and st.button("View document", key=f"pdf_{i}"):
                    st.session_state.selected_source = {
                        "patent_id": patent_id,
                        "page": page,
                        "content": content,
                        "section": section,
                        "rank": rank,
                        "filename": patent_files[patent_id],
                    }
                    st.session_state.fresh_source = True
                    st.rerun()
            if retriever_tags:
                st.caption("Found by: " + ", ".join(retriever_tags))




def render_empty_state():
    """Show a helpful message when no search has been performed yet."""


def _cleanup_dialog_state(all_ids: list[str]):
    """Remove temporary dialog widget keys from session state."""
    for key in ("_dlg_sels", "_master_cb"):
        st.session_state.pop(key, None)
    for pid in all_ids:
        st.session_state.pop(f"_pat_{pid}", None)


@st.dialog("Select patents", width="large")
def patent_selection_dialog(patents_info):
    """Popup dialog with tri-state master checkbox and scrollable patent list."""
    all_ids = [p["patent_id"] for p in patents_info]
    n_total = len(all_ids)

    # Initialise dialog-local selections (once per dialog open)
    if "_dlg_sels" not in st.session_state:
        current = set(st.session_state.get("selected_patents", all_ids))
        st.session_state._dlg_sels = {pid: pid in current for pid in all_ids}

    sels = st.session_state._dlg_sels
    n_selected = sum(sels.values())
    all_checked = n_selected == n_total
    none_checked = n_selected == 0
    partial = not all_checked and not none_checked

    # --- Master checkbox (tri-state) ---
    if none_checked:
        master_label = "No patents selected"
    elif all_checked:
        master_label = "All patents selected"
    else:
        master_label = f"{n_selected} patent{'s' if n_selected != 1 else ''} selected"

    def _on_master_toggle():
        new_val = st.session_state._master_cb
        for pid in sels:
            sels[pid] = new_val
            st.session_state[f"_pat_{pid}"] = new_val

    # Force master checkbox to computed state before rendering
    st.session_state._master_cb = all_checked
    st.checkbox(master_label, key="_master_cb", on_change=_on_master_toggle)

    # Inject JS to show indeterminate visual state (dash) when partially selected
    if partial:
        components.html(
            """<script>
            setTimeout(function() {
                var d = window.parent.document.querySelector('[role="dialog"]')
                     || window.parent.document.querySelector('[data-testid="stDialog"]');
                if (d) {
                    var cb = d.querySelector('input[type="checkbox"]');
                    if (cb) cb.indeterminate = true;
                }
            }, 50);
            </script>""",
            height=0,
        )

    # --- Scrollable patent list ---
    with st.container(height=400):
        for p in patents_info:
            pid = p["patent_id"]
            title = p["title"]
            label = f"📄 **{pid}** — {title}" if title != pid else f"📄 **{pid}**"

            def _make_cb(patent_id):
                def _cb():
                    sels[patent_id] = st.session_state[f"_pat_{patent_id}"]

                return _cb

            st.session_state[f"_pat_{pid}"] = sels[pid]
            st.checkbox(label, key=f"_pat_{pid}", on_change=_make_cb(pid))

    # --- OK / Cancel buttons (bottom-right) ---
    _, col_ok, col_cancel = st.columns([0.6, 0.2, 0.2])
    if col_ok.button("OK", type="primary", width="stretch"):
        st.session_state.selected_patents = [pid for pid, v in sels.items() if v]
        _cleanup_dialog_state(all_ids)
        st.rerun()
    if col_cancel.button("Cancel", width="stretch"):
        _cleanup_dialog_state(all_ids)
        st.rerun()


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------
def main():
    # Configure logging (level from LOG_LEVEL env var, defaults to INFO)
    setup_logging()

    st.set_page_config(
        page_title="Patent Search",
        page_icon="\u2697",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # --- Check data availability ---
    patents_info, _all_chunks, patent_files = load_patents_data()
    if patents_info is None:
        st.error(
            "**Data not found.** Run the ingestion pipeline first:\n\n"
            "```\nuv run python src/data_ingestion.py\n```"
        )
        return

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    with st.sidebar:
        st.title("Patent search")

        if st.button(":material/home: Home", width="stretch"):
            for key in (
                "last_result",
                "last_query",
                "last_elapsed",
                "fresh_search",
                "selected_source",
                "fresh_source",
            ):
                st.session_state.pop(key, None)
            st.rerun()

        st.header("Content")
        # Initialize selected patents to all on first load
        all_patent_ids = [p["patent_id"] for p in patents_info]
        if "selected_patents" not in st.session_state:
            st.session_state.selected_patents = list(all_patent_ids)

        selected_patents = st.session_state.selected_patents
        n_selected = len(selected_patents)
        n_total = len(patents_info)

        if st.button(f"Select patents ({n_selected}/{n_total})", width="stretch"):
            _cleanup_dialog_state(all_patent_ids)
            patent_selection_dialog(patents_info)

        st.header("Search")
        top_k = st.slider(
            "Search results to retrieve",
            5,
            15,
            10,
            key="top_k",
            help="Number of chunks retrieved and used as context for the answer",
        )
        with st.expander("Settings"):
            st.slider(
                "Keyword search weight",
                0.0,
                2.0,
                1.0,
                0.1,
                key="w_bm25",
                help="Higher values favor results with exact matching terms (BM25 weight)",
            )
            st.slider(
                "Semantic search weight",
                0.0,
                2.0,
                1.0,
                0.1,
                key="w_sem",
                help="Higher values find results with similar meanings (Semantic weight)",
            )
            st.slider(
                "Knowledge graph weight",
                0.0,
                2.0,
                1.2,
                0.1,
                key="w_graph",
                help="Higher values include results based on related topics and connections (Knowledge graph weight)",
            )

    # ------------------------------------------------------------------
    # Main content
    # ------------------------------------------------------------------
    # --- Initialise retrievers in background (show spinner once) ---
    if "retrievers_ready" not in st.session_state:
        with st.spinner("Loading retrieval indices..."):
            init_retrievers()
        with st.spinner("Initializing LLM..."):
            init_llm()
        st.session_state.retrievers_ready = True

    # --- Query input ---
    st.text(
        "Ask a question about selected content. The answer will be generated based on relevant data from the content."
    )
    query = st.text_area(
        "Query",
        height=120,
        placeholder="Ask your question about the selected patents...",
        key="query_input",
        label_visibility="collapsed",
    )

    search_clicked = st.button("Search", type="primary")

    # --- Trigger search (retrieval only, streaming deferred) ---
    _pending_stream = None
    _pending_answer_meta = None
    _search_t0 = None

    if search_clicked and not selected_patents:
        st.warning("Please select at least one patent.")
    elif search_clicked and query.strip():
        weights = {
            "bm25": st.session_state.w_bm25,
            "semantic": st.session_state.w_sem,
            "graph": st.session_state.w_graph,
        }

        _search_t0 = time.perf_counter()

        # Clear previous PDF selection on new search
        st.session_state.pop("selected_source", None)

        # Phase 1: Retrieval
        with st.spinner("Searching patents..."):
            try:
                retrieval_result = run_retrieval(
                    query=query.strip(),
                    selected_patents=selected_patents,
                    top_k=top_k,
                    weights=weights,
                )
            except Exception as exc:
                st.error("**Retrieval error:** " + str(exc))
                return

            if retrieval_result is None:
                st.error("Retrievers could not be initialized. Check data files.")
                return

            results, stats = retrieval_result

        if not results:
            # Clear any stale previous results so the old answer isn't re-displayed
            for key in ("last_result", "last_query", "last_elapsed", "fresh_search"):
                st.session_state.pop(key, None)
            st.warning(
                "No matching passages found for your query. "
                "Try rephrasing it or adjusting the search weights in **Settings**."
            )
            return

        # Phase 2: Prepare LLM stream (consumed inside bordered container below)
        try:
            stream, answer_meta = build_answer_stream(
                query=query.strip(),
                results=results,
                max_context_chunks=top_k,
            )
            _pending_stream = stream
            _pending_answer_meta = answer_meta
        except RuntimeError as exc:
            st.error("**LLM connection error:** " + str(exc))
            return
        except Exception as exc:
            st.error("**Error:** " + str(exc))
            return

        # Persist results (answer text filled in after streaming)
        st.session_state.last_result = {
            "results": results,
            "answer": answer_meta,
            "stats": stats,
        }
        st.session_state.last_query = query.strip()
        st.session_state.fresh_search = True

    # --- Display results ---
    if "last_result" in st.session_state:
        result = st.session_state.last_result
        answer = result["answer"]
        results = result["results"]
        stats = result["stats"]
        elapsed = st.session_state.get("last_elapsed", 0)

        fresh = st.session_state.pop("fresh_search", False)

        has_selected = "selected_source" in st.session_state

        if has_selected:
            left_col, right_col = st.columns([0.45, 0.55], gap="medium")
        else:
            left_col = st.container()

        with left_col, st.container(border=True):
            st.markdown(SOURCE_REF_CSS, unsafe_allow_html=True)

            if fresh and _pending_stream is not None:
                # Stream answer with manual loop, then enrich citations
                source_map = build_source_map(answer, patent_files)
                placeholder = st.empty()
                full_text = ""
                with st.spinner("Generating answer..."):
                    for chunk in _pending_stream:
                        full_text += chunk
                        placeholder.markdown(full_text + "\u258c")
                enriched = enrich_citations(full_text, source_map)
                answer["answer"] = enriched
                placeholder.markdown(enriched, unsafe_allow_html=True)
                elapsed = time.perf_counter() - _search_t0
                st.session_state.last_elapsed = elapsed

            st.caption("Completed in " + f"{elapsed:.1f}s")

            if not fresh:
                # Answer (re-display from session state)
                st.markdown(answer["answer"], unsafe_allow_html=True)

            # Sources
            render_sources(results, patent_files)

            # Wire click-to-scroll on citation badges
            inject_source_scroll_js()

            # Retriever stats (at the bottom)
            st.divider()
            total = stats.get("total_results", len(results))
            stat_cols = st.columns(4)
            stat_cols[0].metric(
                "Keyword search",
                stats.get("bm25_hits", 0),
                help=f"Results found by exact keyword matching (BM25). {stats.get('bm25_hits', 0)} of {total} passages matched your search terms directly.",
            )
            stat_cols[1].metric(
                "Semantic search",
                stats.get("semantic_hits", 0),
                help=f"Results found by meaning similarity (vector search). {stats.get('semantic_hits', 0)} of {total} passages are conceptually related to your query.",
            )
            stat_cols[2].metric(
                "Knowledge graph",
                stats.get("graph_hits", 0),
                help=f"Results found via entity relationships in the knowledge graph. {stats.get('graph_hits', 0)} of {total} passages were discovered by traversing concept connections.",
            )
            stat_cols[3].metric(
                "Found by 2+ methods",
                stats.get("multi_retriever_hits", 0),
                help=f"{stats.get('multi_retriever_hits', 0)} of {total} passages were independently confirmed by more than one search method — these are the most reliable results.",
            )

            meta = answer["metadata"]
            reranker_status = "on" if init_reranker() is not None else "off"
            st.caption(
                "Model: " + meta.get("model", "?") + "  |  "
                "Context: "
                + str(meta.get("chunk_count", 0))
                + "/"
                + str(meta.get("total_retrieved", 0))
                + " chunks"
                + "  |  Reranker: "
                + reranker_status
            )


        # PDF viewer panel
        if has_selected:
            source = st.session_state.selected_source
            with right_col, st.container(border=True):
                header_cols = st.columns([0.85, 0.15])
                header_cols[0].subheader(source["patent_id"] + " — Page " + str(source["page"]))
                if header_cols[1].button("Close", key="close_pdf"):
                    del st.session_state.selected_source
                    st.rerun()

                if source.get("section"):
                    st.caption(
                        "Section: " + source["section"] + "  |  Source #" + str(source["rank"])
                    )

                pdf_path = str(RAW_DIR / source["filename"])
                with st.spinner("Rendering PDF page..."):
                    img_bytes = render_pdf_page(pdf_path, source["page"], source["content"])

                if img_bytes:
                    st.image(img_bytes, width="stretch")
                else:
                    st.warning(
                        "Could not render page "
                        + str(source["page"])
                        + " from "
                        + source["filename"]
                        + "."
                    )

                # Auto-scroll to PDF viewer when source was just selected
                if st.session_state.pop("fresh_source", False):
                    components.html(
                        f"""
                        <script>
                        // {time.time()}
                        setTimeout(function() {{
                            var doc = window.parent.document;

                            var selectors = [
                                'section.main',
                                '[data-testid="stMain"]',
                                '[data-testid="stAppViewContainer"]',
                                '[data-testid="stMainBlockContainer"]'
                            ];
                            for (var i = 0; i < selectors.length; i++) {{
                                var el = doc.querySelector(selectors[i]);
                                if (el && el.scrollHeight > el.clientHeight) {{
                                    el.scrollTo({{top: 0, behavior: 'smooth'}});
                                }}
                            }}

                            window.parent.scrollTo({{top: 0, behavior: 'smooth'}});
                        }}, 300);
                        </script>
                        """,
                        height=0,
                    )

    elif not search_clicked:
        render_empty_state()
    elif search_clicked and not query.strip():
        st.warning("Please type your question.")


if __name__ == "__main__":
    main()
