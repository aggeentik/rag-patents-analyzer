## Problem Analysis

```
Analyze the attached Patents and propose the approach how to implement insights extraction? Requirements: customer needs to search the pieces of data in  patent (some examples attached) which are semantically close to user's request. Data inside the patents is highly fragmented, for example there might be a table, however description, explaining the metrics in this table  might be spread across the document. Additional complexity adds PDF itself (e.g. when text is split in 2 columns)  Customer is going to use the data from the patents to produce a steel. Possible approaches I am thinking about: 1/ Use of semantic search + BM25 2/ Knowledge graph to connect semantically close entities. Technical requirements: solution needs to be run locally including small LLMs for summarization and data chunks aggregations. Do not generate the code, just make a solution proposal with some diagrams. 
```

From the three patents, I've identified key challenges:

1. **Information Fragmentation**: Table metrics explained across multiple sections
2. **Multi-column PDF layouts**: Text extraction complexity
3. **Cross-references**: "As shown in Table 1", "According to Formula 2"
4. **Technical complexity**: Formulas, compositional ranges, process parameters
5. **Critical data types**: Chemical compositions (%, mass%), properties (MPa, T, W/kg), temperatures (°C), process steps

For steel production, users need to extract:
- Compositional requirements (Si: 2.5-10%, Cr: 1.5-20%, etc.)
- Processing parameters (annealing temperatures, cooling rates)
- Property targets (yield stress, magnetic flux density, core loss)
- Composition-property-process relationships

## Proposed Solution Architecture

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    PATENT PDF DOCUMENTS                      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              PHASE 1: DOCUMENT PROCESSING                    │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ Layout-Aware   │→ │  Structure   │→ │   Cross-Ref     │ │
│  │  PDF Parser    │  │  Detection   │  │   Resolver      │ │
│  └────────────────┘  └──────────────┘  └─────────────────┘ │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│         PHASE 2: KNOWLEDGE GRAPH CONSTRUCTION                │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ Entity         │→ │ Relationship │→ │  Graph          │ │
│  │ Extraction     │  │  Mapping     │  │  Database       │ │
│  └────────────────┘  └──────────────┘  └─────────────────┘ │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│          PHASE 3: SEMANTIC CHUNKING & ENRICHMENT            │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Context-Aware  │→ │  Metadata    │→ │   Graph-        │  │
│  │  Chunking      │  │  Addition    │  │   Enrichment    │  │
│  └────────────────┘  └──────────────┘  └─────────────────┘  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│            PHASE 4: INDEXING & STORAGE                      │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Vector         │  │    BM25      │  │   Structured    │  │
│  │ Embeddings     │  │    Index     │  │   Data Store    │  │
│  │ (FAISS)        │  │              │  │                 │  │
│  └────────────────┘  └──────────────┘  └─────────────────┘  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│         PHASE 5: QUERY PROCESSING & RETRIEVAL               │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Query          │→ │  Hybrid      │→ │   Graph         │  │
│  │ Understanding  │  │  Search      │  │   Traversal     │  │
│  └────────────────┘  └──────────────┘  └─────────────────┘  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│         PHASE 6: AGGREGATION & GENERATION                   │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Context        │→ │  Local LLM   │→ │   Structured    │  │
│  │ Assembly       │  │ Aggregation  │  │   Response      │  │
│  └────────────────┘  └──────────────┘  └─────────────────┘  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
                  USER RESPONSE
```

### Phase 1: Document Processing & Parsing

```
┌─────────────────────────────────────────────────────────────┐
│                    PDF EXTRACTION PIPELINE                   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Input: Multi-column PDF with tables, formulas       │  │
│  └────────────────┬─────────────────────────────────────┘  │
│                   │                                          │
│                   ▼                                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Layout-Aware Parser (pdfplumber/pypdfium2)          │  │
│  │  - Detect columns                                     │  │
│  │  - Preserve reading order                             │  │
│  │  - Extract coordinates                                │  │
│  └────────────────┬─────────────────────────────────────┘  │
│                   │                                          │
│                   ▼                                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Structure Detection                                  │  │
│  │  ├─ Headers/Sections (Background, Claims, Examples)  │  │
│  │  ├─ Tables (with structure preservation)             │  │
│  │  ├─ Formulas (math expressions)                       │  │
│  │  ├─ Figures & Captions                                │  │
│  │  └─ Cross-references                                  │  │
│  └────────────────┬─────────────────────────────────────┘  │
│                   │                                          │
│                   ▼                                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Structured Document Object                           │  │
│  │  {                                                    │  │
│  │    sections: [],                                      │  │
│  │    tables: [{caption, headers, rows, location}],     │  │
│  │    formulas: [{id, expression, context}],            │  │
│  │    figures: [{id, caption, location}],               │  │
│  │    cross_refs: [{source, target, type}]              │  │
│  │  }                                                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Key Components:**
- **Layout Analysis**: Identify multi-column layouts, table boundaries
- **Table Parser**: Extract tables with headers, preserve structure
- **Formula Detector**: Identify mathematical expressions using patterns
- **Reference Linker**: Map "Table 1", "Formula 2", "FIG. 3" to actual objects

### Phase 2: Knowledge Graph Construction

```
┌─────────────────────────────────────────────────────────────┐
│                   KNOWLEDGE GRAPH SCHEMA                     │
│                                                              │
│  ┌─────────────┐     CONTAINS     ┌─────────────┐          │
│  │  Chemical   │◄─────────────────┤ Composition │          │
│  │  Element    │                   │   Range     │          │
│  │ (Si, Cr,..) │     HAS_VALUE     └──────┬──────┘          │
│  └──────┬──────┘                          │                 │
│         │                                 │                 │
│         │ AFFECTS                         │ ACHIEVED_IN     │
│         │                                 │                 │
│         ▼                                 ▼                 │
│  ┌─────────────┐     MEASURED_IN  ┌─────────────┐          │
│  │  Property   │◄─────────────────┤   Sample/   │          │
│  │(yield stress│                   │  Example    │          │
│  │  core loss) │     SHOWN_IN      └──────┬──────┘          │
│  └──────┬──────┘◄────────────┐           │                 │
│         │                    │           │ HAS_DATA        │
│         │ REQUIRES           │           │                 │
│         │                    │           ▼                 │
│         ▼              ┌─────────────┐┌─────────────┐      │
│  ┌─────────────┐      │    Table    ││   Formula   │      │
│  │  Process    │      │             ││             │      │
│  │   Step      │      └─────────────┘└─────────────┘      │
│  │(annealing,  │                                           │
│  │  rolling)   │      DESCRIBED_IN                         │
│  └──────┬──────┘◄────────────┐                            │
│         │                    │                             │
│         │ HAS_PARAM          │                             │
│         │              ┌─────────────┐                     │
│         ▼              │    Text     │                     │
│  ┌─────────────┐      │   Section   │                     │
│  │ Temperature │      └─────────────┘                     │
│  │    Range    │                                           │
│  └─────────────┘                                           │
│                                                             │
│  Example Triples:                                          │
│  (Si, HAS_VALUE, "2.5% to 10%")                           │
│  (Si, AFFECTS, yield_stress)                               │
│  (yield_stress, MEASURED_IN, Table5_SampleE3)             │
│  (Table5_SampleE3, HAS_DATA, "730 MPa")                   │
│  (Table5_SampleE3, ACHIEVED_IN, annealing_process)       │
│  (annealing_process, HAS_PARAM, "900°C, 60 seconds")     │
│  (Formula1, CONSTRAINS, Si_content)                        │
└─────────────────────────────────────────────────────────────┘
```

**Entity Types:**
- **Chemical Elements**: Si, Cr, Mn, Al, Cu, Ti, Nb, Zr, V, N, C, S, etc.
- **Properties**: yield_stress, fracture_elongation, core_loss, magnetic_flux_density, resistivity
- **Processes**: hot_rolling, cold_rolling, annealing, pickling, finish_annealing
- **Process Parameters**: temperature_range, cooling_rate, time_duration, atmosphere
- **Compositional Ranges**: element ranges with constraints
- **Formulas**: Formula1, Formula2, etc. with their expressions
- **Tables**: Table1, Table2, etc. with their data
- **Samples/Examples**: Material symbols (Steel A, Steel B, Sample e1, etc.)
- **Figures**: FIG.1, FIG.2, etc.

**Relationship Types:**
- **CONTAINS**: Formula contains elements
- **HAS_VALUE**: Element has percentage value
- **AFFECTS**: Element/process affects property
- **REQUIRES**: Process requires parameter/condition
- **ACHIEVED_IN**: Property achieved in sample
- **MEASURED_IN**: Property measured in table
- **DESCRIBED_IN**: Entity described in text section
- **SHOWN_IN**: Relationship shown in figure
- **SATISFIES**: Composition satisfies formula
- **PART_OF**: Section part of document
- **REFERENCES**: Text references table/formula/figure

### Phase 3: Semantic Chunking Strategy

```
┌─────────────────────────────────────────────────────────────┐
│              CONTEXT-AWARE CHUNKING STRATEGY                 │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Type 1: Paragraph Chunks                          │    │
│  │  ─────────────────────────                         │    │
│  │  Original Text + Metadata + Graph Context          │    │
│  │                                                     │    │
│  │  {                                                  │    │
│  │    text: "Si is an element which decreases...",    │    │
│  │    metadata: {                                      │    │
│  │      section: "Embodiment 3",                       │    │
│  │      page: 14,                                      │    │
│  │      type: "paragraph"                              │    │
│  │    },                                               │    │
│  │    entities: [Si, core_loss],                       │    │
│  │    related_tables: [Table7],                        │    │
│  │    related_formulas: []                             │    │
│  │  }                                                  │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Type 2: Table Row Chunks                          │    │
│  │  ─────────────────────────                         │    │
│  │  Row + Headers + Caption + Surrounding Text        │    │
│  │                                                     │    │
│  │  {                                                  │    │
│  │    text: "Material c7: Si=2.1%, Cu=0.7%, Ni=1.4%,  │    │
│  │           yield_stress=700MPa, elongation=18%",    │    │
│  │    table_id: "Table7",                              │    │
│  │    caption: "Measured results of Si, Cu amounts...",│    │
│  │    metadata: {                                      │    │
│  │      section: "Embodiment 3",                       │    │
│  │      row_number: 7,                                 │    │
│  │      type: "table_row"                              │    │
│  │    },                                               │    │
│  │    entities: [Si, Cu, Ni, yield_stress, elongation],│    │
│  │    structured_data: {                               │    │
│  │      Si: 2.1, Cu: 0.7, Ni: 1.4,                    │    │
│  │      yield_stress: 700, elongation: 18             │    │
│  │    },                                               │    │
│  │    context_text: "In samples (Symbols c7 to c10)..." │    │
│  │  }                                                  │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Type 3: Formula Chunks                            │    │
│  │  ────────────────────────                          │    │
│  │  Formula + Explanation + Variable Definitions      │    │
│  │                                                     │    │
│  │  {                                                  │    │
│  │    text: "Formula (1): 2.0×10⁻⁴ ≤ [Nb]/93 + ...",  │    │
│  │    formula_id: "Formula1",                          │    │
│  │    variables: {                                     │    │
│  │      Nb: "Nb content (%)",                          │    │
│  │      Zr: "Zr content (%)", ...                     │    │
│  │    },                                               │    │
│  │    explanation: "Four elements of Nb, Zr, Ti, V... │    │
│  │                 suppress coarsening of crystal...", │    │
│  │    entities: [Nb, Zr, Ti, V],                       │    │
│  │    related_tables: [Table5, Table6],                │    │
│  │    type: "formula"                                  │    │
│  │  }                                                  │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Type 4: Process Step Chunks                       │    │
│  │  ─────────────────────────                         │    │
│  │  Complete Process Description                      │    │
│  │                                                     │    │
│  │  {                                                  │    │
│  │    text: "obtaining a hot-rolled sheet by hot      │    │
│  │           rolling the slab at 1150°C...",          │    │
│  │    process: "hot_rolling",                          │    │
│  │    parameters: {                                    │    │
│  │      temperature: "1150°C",                         │    │
│  │      duration: "60 minutes",                        │    │
│  │      output_thickness: "2.3 mm"                     │    │
│  │    },                                               │    │
│  │    next_step: "pickling",                           │    │
│  │    type: "process"                                  │    │
│  │  }                                                  │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

**Key Principles:**
1. **Preserve semantic units**: Don't split tables, formulas, or process descriptions
2. **Enrich with metadata**: Section, page, document type
3. **Add graph context**: Link to related entities in knowledge graph
4. **Include cross-references**: Automatically include referenced content
5. **Structure preservation**: For tables, maintain relational structure

### Phase 4: Hybrid Search Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HYBRID SEARCH SYSTEM                      │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              USER QUERY                              │  │
│  │  "What Si content for yield stress above 700 MPa?"  │  │
│  └────────────────┬─────────────────────────────────────┘  │
│                   │                                          │
│                   ▼                                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         QUERY ANALYSIS & DECOMPOSITION               │  │
│  │  - Extract entities: Si, yield_stress               │  │
│  │  - Extract constraints: yield_stress > 700 MPa      │  │
│  │  - Detect intent: compositional_query                │  │
│  │  - Generate sub-queries                              │  │
│  └────┬─────────────────────────────┬───────────────────┘  │
│       │                             │                       │
│       ▼                             ▼                       │
│  ┌──────────────────┐        ┌──────────────────┐          │
│  │  DENSE RETRIEVAL │        │ SPARSE RETRIEVAL │          │
│  │  (Semantic)      │        │     (BM25)       │          │
│  │                  │        │                  │          │
│  │  Embedding Model │        │  - Exact match   │          │
│  │  (MiniLM/BGE)    │        │  - Keywords      │          │
│  │  ↓               │        │  - Chemical      │          │
│  │  FAISS Index     │        │    formulas      │          │
│  │  ↓               │        │  - Numeric values│          │
│  │  Top-K chunks    │        │  ↓               │          │
│  │                  │        │  Top-K chunks    │          │
│  └────────┬─────────┘        └────────┬─────────┘          │
│           │                           │                     │
│           └──────────┬────────────────┘                     │
│                      ▼                                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           HYBRID FUSION (RRF or weighted)            │  │
│  │           Merged & Ranked Results                     │  │
│  └────────────────┬─────────────────────────────────────┘  │
│                   │                                          │
│                   ▼                                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │            GRAPH TRAVERSAL & EXPANSION               │  │
│  │  For each retrieved chunk:                           │  │
│  │  1. Identify entities in chunk                       │  │
│  │  2. Traverse graph to find related entities          │  │
│  │  3. Retrieve chunks for related entities             │  │
│  │  4. Apply filters (e.g., yield_stress > 700 MPa)    │  │
│  └────────────────┬─────────────────────────────────────┘  │
│                   │                                          │
│                   ▼                                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │          STRUCTURED QUERY EXECUTION                   │  │
│  │  - Query tables where yield_stress > 700            │  │
│  │  - Extract corresponding Si values                   │  │
│  │  - Find formulas constraining Si                     │  │
│  │  - Retrieve process conditions                       │  │
│  └────────────────┬─────────────────────────────────────┘  │
│                   │                                          │
│                   ▼                                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │             RE-RANKING & FILTERING                    │  │
│  │  - Relevance score                                    │  │
│  │  - Completeness score (has all needed context)       │  │
│  │  - Diversity (different aspects)                      │  │
│  │  - Recency (patent date)                              │  │
│  └────────────────┬─────────────────────────────────────┘  │
│                   │                                          │
│                   ▼                                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           CONTEXT ASSEMBLY                            │  │
│  │  - Group related chunks                               │  │
│  │  - Resolve references                                 │  │
│  │  - Order logically                                    │  │
│  │  - Include tables, formulas fully                     │  │
│  └────────────────┬─────────────────────────────────────┘  │
│                   │                                          │
│                   ▼                                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │        LLM AGGREGATION & SYNTHESIS                    │  │
│  │  Local LLM (Phi-3/Mistral-7B/Llama-3.2)             │  │
│  │  - Summarize findings                                 │  │
│  │  - Resolve conflicting information                    │  │
│  │  - Generate coherent response                         │  │
│  │  - Add citations                                      │  │
│  └────────────────┬─────────────────────────────────────┘  │
│                   │                                          │
│                   ▼                                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              STRUCTURED RESPONSE                      │  │
│  │  {                                                    │  │
│  │    answer: "Based on analysis of EP2278034...",      │  │
│  │    compositions: [{Si: 2.9-3.7%, Cr: ..., }],       │  │
│  │    properties: [{yield_stress: 730-880 MPa, ...}],  │  │
│  │    processes: [{annealing: "900-1000°C, 60s"}],     │  │
│  │    citations: ["Table 9", "Formula 1", ...]         │  │
│  │  }                                                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Phase 5: Query Processing Examples

```
┌─────────────────────────────────────────────────────────────┐
│            QUERY TYPE PROCESSING STRATEGIES                  │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Query Type 1: Compositional Search                │    │
│  │  ──────────────────────────────────────           │    │
│  │  Example: "What is the optimal Si content?"        │    │
│  │                                                     │    │
│  │  Processing:                                        │    │
│  │  1. Semantic search: "silicon content", "optimal"  │    │
│  │  2. Graph query: Find all (Si)-[HAS_VALUE]-(range) │    │
│  │  3. Retrieve: Claims sections, Formula constraints │    │
│  │  4. Retrieve: Tables with Si values & properties   │    │
│  │  5. Aggregate: Ranges, conditions, trade-offs      │    │
│  │                                                     │    │
│  │  Response Structure:                                │    │
│  │  - General range from claims (2.5-10%)             │    │
│  │  - Specific ranges for different properties        │    │
│  │  - Formula constraints (Formula 1, 2)              │    │
│  │  - Examples with achieved properties               │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Query Type 2: Property-Based Search               │    │
│  │  ───────────────────────────────────              │    │
│  │  Example: "How to achieve yield stress > 750 MPa?" │    │
│  │                                                     │    │
│  │  Processing:                                        │    │
│  │  1. Semantic search: "yield stress", "achieve"     │    │
│  │  2. Structured query: Filter tables WHERE          │    │
│  │     yield_stress > 750                              │    │
│  │  3. Graph traversal: For each matching sample:     │    │
│  │     - Get composition                               │    │
│  │     - Get process parameters                        │    │
│  │     - Get other properties                          │    │
│  │  4. Aggregate: Common patterns in compositions     │    │
│  │                                                     │    │
│  │  Response Structure:                                │    │
│  │  - Required compositional ranges                    │    │
│  │  - Critical process parameters                      │    │
│  │  - Trade-offs (elongation, etc.)                    │    │
│  │  - Specific examples from tables                    │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Query Type 3: Process Query                       │    │
│  │  ─────────────────────────                         │    │
│  │  Example: "What is the annealing process?"         │    │
│  │                                                     │    │
│  │  Processing:                                        │    │
│  │  1. Semantic search: "annealing", "process"        │    │
│  │  2. Graph query: Find (annealing)-[HAS_PARAM]-()   │    │
│  │  3. Retrieve: Method/claims sections               │    │
│  │  4. Retrieve: Examples with specific conditions    │    │
│  │  5. Aggregate: Standard process, variations        │    │
│  │                                                     │    │
│  │  Response Structure:                                │    │
│  │  - Process steps in order                           │    │
│  │  - Temperature ranges                               │    │
│  │  - Time durations                                   │    │
│  │  - Atmosphere conditions                            │    │
│  │  - Variations by composition                        │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Query Type 4: Relationship/Causal Query           │    │
│  │  ────────────────────────────────────             │    │
│  │  Example: "How does Cr affect magnetic properties?"│    │
│  │                                                     │    │
│  │  Processing:                                        │    │
│  │  1. Semantic search: "chromium", "magnetic"        │    │
│  │  2. Graph query: (Cr)-[AFFECTS]-(magnetic_property)│    │
│  │  3. Retrieve: Explanation paragraphs               │    │
│  │  4. Retrieve: Tables comparing different Cr levels │    │
│  │  5. Retrieve: Formulas with Cr                     │    │
│  │  6. Synthesize: Direct effects + indirect effects  │    │
│  │                                                     │    │
│  │  Response Structure:                                │    │
│  │  - Mechanism explanation                            │    │
│  │  - Quantitative relationships (from tables)        │    │
│  │  - Optimal ranges                                   │    │
│  │  - Interactions with other elements                │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Technical Implementation Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    TECHNOLOGY STACK                          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. PDF Processing Layer                             │  │
│  │     - pdfplumber (layout-aware extraction)           │  │
│  │     - tabula-py (table extraction backup)            │  │
│  │     - pypdfium2 (robust PDF rendering)               │  │
│  │     - Custom regex patterns (formula detection)      │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  2. Knowledge Graph Layer                            │  │
│  │     Option A: SQLite + NetworkX (lightweight)        │  │
│  │     Option B: DuckDB (analytical queries)            │  │
│  │     - Custom schema for entities & relationships     │  │
│  │     - Efficient graph traversal algorithms           │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  3. Embedding & Vector Search Layer                  │  │
│  │     - sentence-transformers (all-MiniLM-L6-v2 or     │  │
│  │       BAAI/bge-small-en-v1.5)                        │  │
│  │     - FAISS (vector index, CPU-optimized)            │  │
│  │     - ScaNN (alternative, Google's library)          │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  4. Sparse Retrieval Layer                           │  │
│  │     - rank-bm25 (Python BM25 implementation)         │  │
│  │     - Whoosh (pure Python search library)            │  │
│  │     - Custom inverted index for technical terms      │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  5. LLM Layer (Local, Quantized)                     │  │
│  │     Option A: Phi-3-mini (3.8B, 4-bit quantized)     │  │
│  │     Option B: Llama-3.2-3B-Instruct (4-bit)          │  │
│  │     Option C: Mistral-7B-Instruct (4-bit)            │  │
│  │     - llama.cpp or llama-cpp-python                  │  │
│  │     - GGUF format for efficient inference            │  │
│  │     - CPU or GPU execution                           │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  6. Orchestration Layer                              │  │
│  │     - FastAPI (REST API)                             │  │
│  │     - Celery (async task processing)                 │  │
│  │     - Redis (caching, task queue)                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  7. Storage Layer                                    │  │
│  │     - SQLite/DuckDB (structured data)                │  │
│  │     - JSON files (document structures)               │  │
│  │     - FAISS indices (vectors)                        │  │
│  │     - Pickle/Joblib (models, indices)                │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      END-TO-END ARCHITECTURE                 │
│                                                              │
│  ┌────────────────┐                                          │
│  │  Patent PDFs   │                                          │
│  └───────┬────────┘                                          │
│          │                                                   │
│          ▼                                                   │
│  ┌───────────────────────────────────────────────────┐      │
│  │         INGESTION PIPELINE (Offline)              │      │
│  │  ┌──────────────────────────────────────────┐    │      │
│  │  │  PDF Parser → Structure Detector          │    │      │
│  │  │      ↓            ↓            ↓         │    │      │
│  │  │   Tables      Formulas      Text        │    │      │
│  │  └──────────────────────────────────────────┘    │      │
│  │  ┌──────────────────────────────────────────┐    │      │
│  │  │  Entity Extraction → KG Construction     │    │      │
│  │  └──────────────────────────────────────────┘    │      │
│  │  ┌──────────────────────────────────────────┐    │      │
│  │  │  Chunking → Enrichment → Embedding       │    │      │
│  │  └──────────────────────────────────────────┘    │      │
│  └───────────────────────────────────────────────────┘      │
│          │                                                   │
│          ▼                                                   │
│  ┌───────────────────────────────────────────────────┐      │
│  │              STORAGE LAYER                        │      │
│  │  ┌─────────────┐  ┌──────────┐  ┌─────────────┐ │      │
│  │  │ Knowledge   │  │  Vector  │  │   BM25      │ │      │
│  │  │   Graph     │  │  Index   │  │   Index     │ │      │
│  │  │  (SQLite)   │  │ (FAISS)  │  │  (Whoosh)   │ │      │
│  │  └─────────────┘  └──────────┘  └─────────────┘ │      │
│  │  ┌─────────────────────────────────────────────┐ │      │
│  │  │     Structured Data (Tables, Formulas)      │ │      │
│  │  │              (DuckDB/SQLite)                │ │      │
│  │  └─────────────────────────────────────────────┘ │      │
│  └───────────────────────────────────────────────────┘      │
│          │                                                   │
│          ▼                                                   │
│  ┌───────────────────────────────────────────────────┐      │
│  │         QUERY PROCESSING (Online)                 │      │
│  │  ┌──────────────────────────────────────────┐    │      │
│  │  │  User Query → Query Analyzer             │    │      │
│  │  └──────────────────────────────────────────┘    │      │
│  │  ┌──────────────────────────────────────────┐    │      │
│  │  │  Multi-Stage Retrieval:                  │    │      │
│  │  │  1. Hybrid Search (BM25 + Dense)         │    │      │
│  │  │  2. Graph Expansion                      │    │      │
│  │  │  3. Structured Query                     │    │      │
│  │  │  4. Re-ranking                           │    │      │
│  │  └──────────────────────────────────────────┘    │      │
│  │  ┌──────────────────────────────────────────┐    │      │
│  │  │  Context Assembly & Aggregation          │    │      │
│  │  └──────────────────────────────────────────┘    │      │
│  │  ┌──────────────────────────────────────────┐    │      │
│  │  │  LLM Synthesis (Phi-3/Mistral/Llama)    │    │      │
│  │  └──────────────────────────────────────────┘    │      │
│  └───────────────────────────────────────────────────┘      │
│          │                                                   │
│          ▼                                                   │
│  ┌───────────────────────────────────────────────────┐      │
│  │          STRUCTURED RESPONSE                      │      │
│  │  - Answer text                                    │      │
│  │  - Compositional data                             │      │
│  │  - Process parameters                             │      │
│  │  - Property values                                │      │
│  │  - Citations (table/formula/section references)  │      │
│  └───────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Key Innovation: Cross-Reference Resolution

```
┌─────────────────────────────────────────────────────────────┐
│          CROSS-REFERENCE RESOLUTION MECHANISM                │
│                                                              │
│  Example: User asks about "optimal Si content"              │
│                                                              │
│  Retrieved chunk says:                                       │
│  "As shown in Table 7, Si content of 2.1-3.7% achieved      │
│   good properties when Formula 1 is satisfied."             │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Cross-Reference Resolver                          │    │
│  │  ─────────────────────────                         │    │
│  │  1. Detect references: "Table 7", "Formula 1"      │    │
│  │  2. Query KG: Find entities with id="Table7",      │    │
│  │              id="Formula1"                          │    │
│  │  3. Retrieve: Full table content, formula text     │    │
│  │  4. Get context: Table caption, formula explanation│    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  Enriched response includes:                                │
│  - Original text                                            │
│  - Table 7 (full data with headers)                        │
│  - Formula 1 (complete with variable definitions)          │
│  - Surrounding explanatory text                            │
│                                                             │
│  LLM then synthesizes:                                      │
│  "Based on EP2278034 Table 7, Si content of 2.1-3.7%       │
│   achieved yield stress of 700-880 MPa when Formula 1:     │
│   2.0×10⁻⁴ ≤ [Nb]/93+[Zr]/91+[Ti]/48+[V]/51              │
│   is satisfied. Specific examples:                          │
│   - Si=2.1%, Cu=0.7%, Ni=1.4% → 700 MPa (Sample c7)       │
│   - Si=3.5%, Cu=0.6%, Ni=1.7% → 720 MPa (Sample c12)      │
│   Processing: Finish annealing at 900-1000°C"              │
└─────────────────────────────────────────────────────────────┘
```

### Performance Optimization Strategies

```
┌─────────────────────────────────────────────────────────────┐
│             PERFORMANCE OPTIMIZATION STRATEGIES              │
│                                                              │
│  1. Caching Strategy                                         │
│     ┌────────────────────────────────────────────┐          │
│     │  - Cache common queries                    │          │
│     │  - Cache graph traversal results           │          │
│     │  - Cache LLM responses for similar queries │          │
│     │  - Cache table structures                  │          │
│     │  - TTL-based invalidation                  │          │
│     └────────────────────────────────────────────┘          │
│                                                             │
│  2. Indexing Optimization                                    │
│     ┌────────────────────────────────────────────┐          │
│     │  - Hierarchical indexing (by section type) │          │
│     │  - Separate indices for tables, formulas   │          │
│     │  - Compressed vectors (PQ, OPQ)            │          │
│     │  - Approximate search (HNSW, IVF)          │          │
│     └────────────────────────────────────────────┘          │
│                                                             │
│  3. Query Optimization                                       │
│     ┌────────────────────────────────────────────┐          │
│     │  - Early stopping for top-K results        │          │
│     │  - Parallel retrieval (BM25 + Dense)       │          │
│     │  - Lazy loading of full context            │          │
│     │  - Incremental graph traversal             │          │
│     └────────────────────────────────────────────┘          │
│                                                             │
│  4. LLM Optimization                                         │
│     ┌────────────────────────────────────────────┐          │
│     │  - 4-bit quantization (GGUF/GPTQ)          │          │
│     │  - Batch processing when possible          │          │
│     │  - Context length optimization             │          │
│     │  - Template-based generation for tables    │          │
│     │  - Speculative decoding                    │          │
│     └────────────────────────────────────────────┘          │
│                                                             │
│  5. Memory Management                                        │
│     ┌────────────────────────────────────────────┐          │
│     │  - Lazy loading of patent documents        │          │
│     │  - Streaming results                       │          │
│     │  - Chunk-level caching                     │          │
│     │  - Efficient serialization (msgpack)       │          │
│     └────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Roadmap

**Phase 1 (Weeks 1-2): Core Infrastructure**
- PDF parsing pipeline with layout awareness
- Document structure detection
- Basic entity extraction

**Phase 2 (Weeks 3-4): Knowledge Graph**
- KG schema design
- Entity & relationship extraction
- Graph database setup
- Cross-reference resolution

**Phase 3 (Weeks 5-6): Search Infrastructure**
- Semantic chunking implementation
- Vector embedding generation
- BM25 index creation
- Hybrid search fusion

**Phase 4 (Weeks 7-8): Query Processing**
- Query analyzer
- Multi-stage retrieval
- Graph traversal algorithms
- Context assembly

**Phase 5 (Weeks 9-10): LLM Integration**
- Local LLM setup (quantized)
- Prompt engineering
- Response generation
- Citation formatting

**Phase 6 (Weeks 11-12): Optimization & Testing**
- Performance tuning
- Caching implementation
- User testing
- Evaluation metrics

## Success Metrics

1. **Retrieval Quality**
   - Precision@5: >0.8
   - Recall@10: >0.7
   - MRR: >0.75

2. **Completeness**
   - Table inclusion rate: >90% when relevant
   - Formula resolution: >95%
   - Cross-reference accuracy: >90%

3. **Performance**
   - Query latency: <5 seconds (cold), <1 second (cached)
   - Indexing throughput: >10 pages/second

4. **Accuracy**
   - Numerical extraction accuracy: >95%
   - Compositional range accuracy: >95%

This solution combines semantic search, knowledge graphs, and local LLMs to handle the complex, fragmented structure of patent documents while enabling precise technical information retrieval for steel production.