"""
Patent Search Demo - Streamlit UI

Interactive search interface for the Patents Analyzer RAG pipeline.
Supports hybrid retrieval (BM25 + Semantic + Knowledge Graph) with LLM-generated answers.

Usage:
    uv run streamlit run app.py
"""

import sys
import json
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# --- Path setup ---
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

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

    patents_info = []
    all_chunks = []
    patent_files = {}  # patent_id → filename
    for patent in data["patents"]:
        patent_id = patent["patent_id"]
        chunks = patent["chunks"]

        # Extract the real patent title from (54) field in page-1 chunks
        title = patent_id  # fallback
        for chunk in chunks:
            content = chunk.get("content", "")
            if content.strip().startswith("(54)"):
                title = content.strip().removeprefix("(54)").strip()
                # Take only the first line / sentence
                title = title.split("\n")[0].strip()
                break

        patents_info.append({
            "patent_id": patent_id,
            "title": title,
            "chunk_count": len(chunks),
        })
        all_chunks.extend(chunks)
        filename = patent.get("metadata", {}).get("filename", "")
        if filename:
            patent_files[patent_id] = filename

    return patents_info, all_chunks, patent_files


@st.cache_data(show_spinner=False)
def render_pdf_page(pdf_path: str, page_number: int, highlight_text: str) -> bytes | None:
    """Render a PDF page as PNG with yellow highlights on matching text.

    Args:
        pdf_path: Absolute path to the PDF file.
        page_number: 1-indexed page number (as stored in chunk metadata).
        highlight_text: Chunk content to search for and highlight.

    Returns:
        PNG image bytes, or None if rendering fails.
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

    # Extract short phrases from the chunk text for searching.
    # Full content is too long for exact match; use first ~80 chars of each
    # sentence to get better hit rate on the actual PDF text.
    sentences = [s.strip() for s in highlight_text.replace("\n", " ").split(".") if s.strip()]
    highlight_color = fitz.utils.getColor("yellow")

    for sentence in sentences:
        # Use first 80 chars of each sentence as search query
        snippet = sentence[:80]
        if len(snippet) < 10:
            continue
        rects = page.search_for(snippet)
        for rect in rects:
            annot = page.add_highlight_annot(rect)
            annot.set_colors(stroke=highlight_color)
            annot.set_opacity(0.4)
            annot.update()

    # Render at 150 DPI for good readability
    pixmap = page.get_pixmap(dpi=150)
    img_bytes = pixmap.tobytes("png")

    doc.close()
    return img_bytes


@st.cache_resource(show_spinner=False)
def init_retrievers():
    """Initialize all retrievers (expensive, cached for session)."""
    from src.retrieval import BM25Retriever, SemanticRetriever, GraphRetriever
    from src.knowledge_graph.store import KnowledgeGraphStore

    _, all_chunks, _ = load_patents_data()
    if all_chunks is None:
        return None

    bm25 = BM25Retriever.load(str(BM25_PATH), all_chunks)
    semantic = SemanticRetriever.load(
        str(FAISS_PATH), str(CHUNK_IDS_PATH), all_chunks
    )
    kg_store = KnowledgeGraphStore(str(KG_PATH))
    kg_store.connect(check_same_thread=False)
    graph = GraphRetriever.load(
        path="", chunks=all_chunks, kg_store=kg_store,
        max_hops=2, score_decay=0.5,
    )

    return {
        "bm25": bm25,
        "semantic": semantic,
        "graph": graph,
        "kg_store": kg_store,
    }


@st.cache_resource(show_spinner=False)
def init_llm():
    """Initialize LLM client."""
    from src.llm import LLMClient
    try:
        return LLMClient.from_env()
    except Exception:
        return LLMClient(model="ollama/llama2")


# ---------------------------------------------------------------------------
# Search logic
# ---------------------------------------------------------------------------
def run_retrieval(query: str, selected_patents: list[str], top_k: int,
                  weights: dict):
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
# Rendering helpers
# ---------------------------------------------------------------------------
def render_sources(results: list[dict], patent_files: dict[str, str]):
    """Render source chunks as expandable cards with View PDF buttons."""
    st.subheader("Sources")
    for i, r in enumerate(results):
        metadata = r.get("metadata", {})
        patent_id = r.get("patent_id", "?")
        section = metadata.get("section", "")
        page = metadata.get("page", "")
        rrf = r.get("rrf_score", 0)
        rank = r.get("final_rank", "")
        content = r.get("content", "")

        # Build retriever tags
        retriever_tags = []
        if r.get("bm25_rank", 0) > 0:
            retriever_tags.append("BM25")
        if r.get("semantic_rank", 0) > 0:
            retriever_tags.append("Semantic")
        if r.get("graph_rank", 0) > 0:
            retriever_tags.append("Graph")

        page_str = f" | Page {page}" if page else ""
        section_str = f" | {section}" if section else ""
        header = f"#{rank}  {patent_id}{section_str}{page_str}  —  RRF {rrf:.4f}"

        with st.expander(header):
            st.text(content)
            # Show View PDF button if the PDF file exists
            if patent_id in patent_files and page:
                pdf_path = RAW_DIR / patent_files[patent_id]
                if pdf_path.exists():
                    if st.button("View document", key=f"pdf_{i}"):
                        st.session_state.selected_source = {
                            "patent_id": patent_id,
                            "page": page,
                            "content": content,
                            "section": section,
                            "rank": rank,
                            "filename": patent_files[patent_id],
                        }
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
    if col_ok.button("OK", type="primary", use_container_width=True):
        st.session_state.selected_patents = [pid for pid, v in sels.items() if v]
        _cleanup_dialog_state(all_ids)
        st.rerun()
    if col_cancel.button("Cancel", use_container_width=True):
        _cleanup_dialog_state(all_ids)
        st.rerun()


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(
        page_title="Patent Search",
        page_icon="\u2697",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # --- Check data availability ---
    patents_info, all_chunks, patent_files = load_patents_data()
    if patents_info is None:
        st.error(
            "**Data not found.** Run the ingestion pipeline first:\n\n"
            "```\nuv run python scripts/data_ingestion_pipeline.py\n```"
        )
        return

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    with st.sidebar:
        st.title("Patent search")

        if st.button(":material/home: Home", use_container_width=True):
            for key in ("last_result", "last_query", "last_elapsed",
                        "fresh_search", "selected_source"):
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

        if st.button(f"Select patents ({n_selected}/{n_total})", use_container_width=True):
            _cleanup_dialog_state(all_patent_ids)
            patent_selection_dialog(patents_info)

        st.header("Search")
        top_k = st.slider("Results to retrieve", 3, 20, 10, key="top_k")

        with st.expander("Settings"):
            max_context = st.slider("Context chunks", 1, 10, 5, key="max_ctx")
            w_bm25 = st.slider("BM25 weight", 0.0, 2.0, 1.0, 0.1, key="w_bm25")
            w_semantic = st.slider("Semantic weight", 0.0, 2.0, 1.0, 0.1, key="w_sem")
            w_graph = st.slider("Knowledge graph weight", 0.0, 2.0, 0.5, 0.1, key="w_graph")


    # ------------------------------------------------------------------
    # Main content
    # ------------------------------------------------------------------
    # --- Initialise retrievers in background (show spinner once) ---
    if "retrievers_ready" not in st.session_state:
        with st.spinner("Loading retrieval indices..."):
            init_retrievers()
            init_llm()
        st.session_state.retrievers_ready = True

    # --- Query input ---
    st.text("Ask a question about selected content. The answer will be generated based on relevant data from the content.")
    query = st.text_area(
        "",
        height=120,
        placeholder="What Si content is needed for yield stress above 700 MPa?",
        key="query_input",
        label_visibility="collapsed",
    )

    search_clicked = st.button("Search", type="primary")

    # --- Trigger search ---
    if search_clicked and query.strip():
        weights = {
            "bm25": st.session_state.w_bm25,
            "semantic": st.session_state.w_sem,
            "graph": st.session_state.w_graph,
        }

        t0 = time.perf_counter()

        # Clear previous PDF selection on new search
        st.session_state.pop("selected_source", None)

        # Phase 1: Retrieval
        progress_placeholder = st.empty()
        progress_placeholder.caption("Searching patents...")
        try:
            retrieval_result = run_retrieval(
                query=query.strip(),
                selected_patents=selected_patents,
                top_k=top_k,
                weights=weights,
            )
        except Exception as exc:
            progress_placeholder.empty()
            st.error(f"**Retrieval error:** {exc}")
            return

        if retrieval_result is None:
            progress_placeholder.empty()
            st.error("Retrievers could not be initialized. Check data files.")
            return

        results, stats = retrieval_result

        # Phase 2: Streaming LLM generation
        progress_placeholder.caption("Generating answer...")
        try:
            stream, answer_meta = build_answer_stream(
                query=query.strip(),
                results=results,
                max_context_chunks=max_context,
            )
            answer_text = st.write_stream(stream)
        except RuntimeError as exc:
            progress_placeholder.empty()
            st.error(f"**LLM connection error:** {exc}")
            return
        except Exception as exc:
            progress_placeholder.empty()
            st.error(f"**Error:** {exc}")
            return

        progress_placeholder.empty()

        elapsed = time.perf_counter() - t0
        answer_meta["answer"] = answer_text

        # Persist results for re-display on reruns
        st.session_state.last_result = {
            "results": results,
            "answer": answer_meta,
            "stats": stats,
        }
        st.session_state.last_query = query.strip()
        st.session_state.last_elapsed = elapsed
        st.session_state.fresh_search = True

    # --- Display results ---
    if "last_result" in st.session_state:
        result = st.session_state.last_result
        answer = result["answer"]
        results = result["results"]
        stats = result["stats"]
        elapsed = st.session_state.get("last_elapsed", 0)

        # On the initial search run the answer was already streamed above,
        # so we only re-render it on subsequent reruns (e.g. clicking View PDF).
        fresh = st.session_state.pop("fresh_search", False)

        has_selected = "selected_source" in st.session_state

        if has_selected:
            left_col, right_col = st.columns([0.45, 0.55], gap="medium")
        else:
            left_col = st.container()

        with left_col:
            st.caption(f"Completed in {elapsed:.1f}s")

            if not fresh:
                # Answer (re-display from session state)
                st.markdown(answer["answer"])

            # Sources
            render_sources(results, patent_files)

            # Retriever stats (at the bottom)
            st.divider()
            stat_cols = st.columns(4)
            stat_cols[0].metric("BM25 hits", stats.get("bm25_hits", 0))
            stat_cols[1].metric("Semantic hits", stats.get("semantic_hits", 0))
            stat_cols[2].metric("Graph hits", stats.get("graph_hits", 0))
            stat_cols[3].metric("Multi-retriever", stats.get("multi_retriever_hits", 0))

            meta = answer["metadata"]
            st.caption(
                f"Model: {meta.get('model', '?')}  |  "
                f"Context: {meta.get('chunk_count', 0)}/{meta.get('total_retrieved', 0)} chunks"
            )

        # PDF viewer panel
        if has_selected:
            source = st.session_state.selected_source
            with right_col:
                header_cols = st.columns([0.85, 0.15])
                header_cols[0].subheader(
                    f"{source['patent_id']} — Page {source['page']}"
                )
                if header_cols[1].button("Close", key="close_pdf"):
                    del st.session_state.selected_source
                    st.rerun()

                if source.get("section"):
                    st.caption(f"Section: {source['section']}  |  Source #{source['rank']}")

                pdf_path = str(RAW_DIR / source["filename"])
                with st.spinner("Rendering PDF page..."):
                    img_bytes = render_pdf_page(
                        pdf_path, source["page"], source["content"]
                    )

                if img_bytes:
                    st.image(img_bytes, use_container_width=True)
                else:
                    st.warning(
                        f"Could not render page {source['page']} "
                        f"from {source['filename']}."
                    )

    elif not search_clicked:
        render_empty_state()
    elif search_clicked and not query.strip():
        st.warning("Please type your question.")


if __name__ == "__main__":
    main()
