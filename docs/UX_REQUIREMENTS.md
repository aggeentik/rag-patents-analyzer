Create a UI for Patent Search Demo: 

Requirements: 
    Minimum capabilities
            ●	Professional UI where a user can:
                ○	Browse or select among the provided patents.
                ○	Ask a natural-language question.
                ○	Receive an LLM-generated answer grounded in the patent content, with clear citations (patent ID/page/section).
            ●	No visible bugs; modern UX conventions (loading states, error messages, empty states).

Tech. stack:
    Streamlit

Possible layout:
┌─────────────────────────────────────────────────────────────┐
│  🔬 Patent Search Demo                              [logo]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Sidebar                                             │    │
│  │ ─────────                                           │    │
│  │ 📁 Patent Selection                                 │    │
│  │ ┌─────────────────────────────────┐                 │    │
│  │ │ ☑ EP2278034 - High-strength...  │                 │    │
│  │ │ ☑ EP1234567 - Steel sheet...    │                 │   │
│  │ │ ☐ EP9876543 - Manufacturing...  │                 │   │
│  │ └─────────────────────────────────┘                 │   │
│  │                                                      │   │
│  │ ⚙️ Search Settings                                   │   │
│  │ Results to retrieve: [━━━━●━━] 5                    │   │
│  │                                                      │   │
│  │ ▶ Advanced Settings                                  │   │
│  │   Keyword ◄━━━━●━━━━► Semantic                      │   │
│  │                                                      │   │
│  │ 📊 Stats                                             │   │
│  │ Patents loaded: 10                                   │   │
│  │ Total chunks: 523                                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Main Content Area                                    │   │
│  │ ─────────────────                                    │   │
│  │                                                      │   │
│  │ 💬 Ask a question about the patents:                │   │
│  │ ┌─────────────────────────────────────────────────┐ │   │
│  │ │ What Si content is needed for yield stress >700?│ │   │
│  │ └─────────────────────────────────────────────────┘ │   │
│  │                                    [🔍 Search]       │   │
│  │                                                      │   │
│  │ ═══════════════════════════════════════════════════ │   │
│  │                                                      │   │
│  │ 📝 Answer                                            │   │
│  │ ┌─────────────────────────────────────────────────┐ │   │
│  │ │ Based on the patent data, Si content of         │ │   │
│  │ │ 2.9-3.7% achieves yield stress above 700 MPa    │ │   │
│  │ │ [EP2278034, Examples, Page 18]...               │ │   │
│  │ └─────────────────────────────────────────────────┘ │   │
│  │                                                      │   │
│  │ 📚 Sources                                           │   │
│  │ ┌─────────────────────────────────────────────────┐ │   │
│  │ │ 1. EP2278034 | Examples | Page 18    score: 0.42│ │   │
│  │ │    "Table 7 shows Si=2.1%, yield=700MPa..."     │ │   │
│  │ │ ──────────────────────────────────────────────  │ │   │
│  │ │ 2. EP2278034 | Claims | Page 2       score: 0.38│ │   │
│  │ │    "Si content in range of 2.5% to 10%..."      │ │   │
│  │ └─────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘