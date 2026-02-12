# Gold Standard RAG Evaluation Test Set
## Metallurgical Patent Corpus — 20 Needle-in-a-Haystack Questions

**Corpus:** 10 European Patent Applications covering non-oriented electrical steel sheets, hot-dip plating alloys, and high-strength magnetic steels.

**Purpose:** Stress-test a hybrid retrieval system (BM25 + Semantic + Knowledge Graph) by targeting exact formulas, buried table values, conceptual paraphrases, cross-entity links, and multi-document reasoning.

---

## Category 1: Keyword & Formula Precision (4 Questions)

These questions target unique identifiers, exact mathematical expressions, and boundary values that a semantic model may "blur" but a BM25 lexical model should retrieve precisely.

---

### Q1

**Question:** In patent EP 2 390 376, the parameter RTi is used to control the ratio of Ti to C and N. What is the exact mathematical expression for RTi, and what are its claimed lower and upper bounds?

**Expected Answer:** RTi = [Ti] / (4 × ([C] + [N])), where [Ti], [C], and [N] are contents in mass%. The lower bound is 1 and the upper bound is 10. More preferably, RTi ≥ 2 (more preferably ≥ 3) and RTi ≤ 9 (more preferably ≤ 7).

**Evidence:** EP2390376_A1, paragraphs [0010], [0018], [0019].

**Retrieval Type Tested:** Keyword — the exact token "RTi" and the formula string "[Ti]/(4×([C]+[N]))" are unique lexical anchors. A semantic model searching for "titanium ratio" might miss the precise formula.

---

### Q2

**Question:** EP 1 816 226 defines two simultaneous compositional constraints as [Formula 1] and [Formula 2] that must be satisfied for REM oxysulfide formation and TiN coprecipitation. Reproduce both formulas exactly.

**Expected Answer:**
- **Formula 1:** [REM]² × [O]² × [S] ≥ 1 × 10⁻¹⁵
- **Formula 2:** ([REM]² × [O]² × [S]) ÷ ([Ti] × [N]) ≥ 1 × 10⁻¹⁰

where [REM], [O], [S], [Ti], and [N] are mass% of the respective elements.

**Evidence:** EP1816226_A1, paragraphs [0030], [0066], and the Claims section (Claim 1).

**Retrieval Type Tested:** Keyword — the exact exponent notation "10⁻¹⁵" and "10⁻¹⁰" are highly specific tokens. Semantic search for "solubility product" will not distinguish between the two formulas.

---

### Q3

**Question:** In EP 2 278 034, the eddy current loss We10/400 is calculated using a dual frequency method. What is the exact calculation formula given in the patent for deriving We10/400 from two core loss measurements W1 and W2 at frequencies f1 and f2?

**Expected Answer:** We10/400 = (W2/f2 − W1/f1) / (f2 − f1) × 400 × 400. This is applied at a maximum magnetic flux density Bmax of 1.0 T.

**Evidence:** EP2278034_A1, paragraph [0065].

**Retrieval Type Tested:** Keyword — the exact token "We10/400" and the compound formula "(W2/f2-W1/f1)/(f2-f1)×400×400" are unique, non-paraphrasable lexical strings.

---

### Q4

**Question:** EP 2 679 695 defines a parameter Ti* to quantify the amount of Ti available for carbide formation. What is the formula for Ti*, and what are the two simultaneous inequality constraints (Formula (2)) that Ti* must satisfy?

**Expected Answer:** Ti* = Ti − 3.4[N%]. The constraints are: 0.008 ≤ Ti* < 1.2[C%].

**Evidence:** EP2679695_A1, paragraphs [0048] and Claims (Claim 1, Formula (2)).

**Retrieval Type Tested:** Keyword — "Ti*" is an unusual token (with asterisk) that a tokenizer may handle inconsistently. The compound inequality "0.008 ≤ Ti* < 1.2[C%]" is a precise lexical needle.

---

## Category 2: Tabular & Numerical Reasoning (4 Questions)

These questions require the model to locate data within tables, compare rows, and perform light numerical reasoning.

---

### Q5

**Question:** In Table 2 of EP 2 698 441, which material symbol achieves the highest yield stress while still being rated "GOOD" or "EXCELLENT" (i.e., not "POOR"), and what are its exact yield stress, fracture elongation, and core loss W10/400 values?

**Expected Answer:** Material symbol "n" (Ni: 2.5%, S: 0.009%) achieves a yield stress of 877 MPa, fracture elongation of 17%, and core loss W10/400 of 27.0 W/kg, rated "EXCELLENT."

**Evidence:** EP2698441_A1, Table 2 (continued), paragraph [0045].

**Retrieval Type Tested:** Table-Reasoning — requires scanning all rows of a multi-page table, filtering out "POOR" entries, and selecting the maximum yield stress.

---

### Q6

**Question:** In Table 1 of EP 2 698 441, material symbol "B" was tested at three different finish annealing temperatures (900°C, 950°C, 1000°C). At which temperature did it fail evaluation (rated "POOR"), and what was the specific failure reason?

**Expected Answer:** Material B failed at 1000°C finish annealing temperature, with evaluation "POOR" and reason "LOW FRACTURE ELONGATION" (fracture elongation of 9%).

**Evidence:** EP2698441_A1, Table 1, paragraph [0017].

**Retrieval Type Tested:** Table-Reasoning — requires cross-referencing temperature, evaluation status, and the remarks column within a single material across three rows.

---

### Q7

**Question:** In EP 2 278 034, Table 9, material symbol e11 has a Cu content of 1.5% and was soaked at 700°C. What was its recrystallization area ratio and why was it classified as a comparative example?

**Expected Answer:** Material e11 had a recrystallization area ratio of 0% (no recrystallization). It was classified as a comparative example because the soaking temperature of 700°C was below the Cu solid solution temperature calculated by Formula (4): 200 × 1.5 + 500 = 800°C.

**Evidence:** EP2278034_A1, Table 9, paragraphs [0068].

**Retrieval Type Tested:** Table-Reasoning — requires reading a specific cell value (0% recrystallization), then linking it to Formula (4) to understand the root cause.

---

### Q8

**Question:** In EP 2 679 695, Table 5, Steel Sample No. 18 has Si: 4.60% and a Formula (1) value of 454. What happened to this sample during processing, and why?

**Expected Answer:** Steel Sample No. 18 experienced sheet fracture during cold rolling and was therefore not subjected to subsequent evaluation. This is because the Formula (1) value of 454 exceeds the upper limit of 430 specified by the patent (300 ≤ 85[Si%] + 16[Mn%] + 40[Al%] + 490[P%] ≤ 430), indicating the steel was too hard/brittle for cold working.

**Evidence:** EP2679695_A1, Table 5, paragraph [0061], and Claims (Formula (1)).

**Retrieval Type Tested:** Table-Reasoning — requires noticing a missing data row (no magnetic/mechanical properties reported for No. 18) and connecting it to the prose explanation and the boundary condition of Formula (1).

---

## Category 3: Semantic & Conceptual (4 Questions)

These questions use synonyms and paraphrases not found in the original text to test semantic understanding.

---

### Q9

**Question:** One patent describes a mechanism where a rare earth compound with internal fractures serves as a preferential nucleation site for a titanium-nitrogen compound. Which patent describes this, and why are fractured inclusions more effective at immobilizing titanium than intact ones?

**Expected Answer:** EP 1 816 226. Fractured REM oxysulfides are more effective because: (1) their crack surfaces are not pre-covered by compounds like AlN that block TiN formation; (2) TiN preferentially coprecipitates on the freshly exposed fracture surfaces; and (3) fractures have larger numbers of TiN bonded in a stacked manner with TiN particles grown to larger sizes compared to unfractured surfaces. This fixes more Ti as TiN, preventing Ti from forming detrimental fine TiC during annealing.

**Evidence:** EP1816226_A1, paragraphs [0053]–[0058].

**Retrieval Type Tested:** Semantic — the question uses "nucleation site" (text says "coprecipitate"), "immobilizing titanium" (text says "fixing Ti"), and "internal fractures" (text says "cracks or fractures"). BM25 would not match these synonyms.

---

### Q10

**Question:** One patent addresses the problem where a specific metallic additive (used to suppress harmful precipitates) loses its effectiveness because it becomes trapped within manganese-sulfur compounds. Which patent describes this phenomenon, what is the additive, and what solution is proposed?

**Expected Answer:** EP 2 439 302. The additive is Bismuth (Bi). Bi is compositely precipitated in MnS, reducing the amount of Bi available to suppress Ti inclusions (TiN, TiS, TiC). The solution is to reduce free S to 0.005 mass% or less, either by direct desulfurization or by adding desulfurizing elements (REM and/or Ca) that form their own sulfides, thereby satisfying expression (3): [S] − 0.23[REM] − 0.4[Ca] ≤ 0.005.

**Evidence:** EP2439302_A1, paragraphs [0036]–[0042].

**Retrieval Type Tested:** Semantic — "trapped within manganese-sulfur compounds" paraphrases "compositely precipitated in MnS," and "loses its effectiveness" paraphrases "the amount of Bi exhibiting the function to reduce Ti inclusions is reduced."

---

### Q11

**Question:** One patent describes coating a base electrical steel with a thin layer of a specific nickel-iron alloy to align near-surface magnetic domains parallel to the sheet surface, thereby improving the magnetization response at low excitation levels. Which patent is this, what is the optimal alloy composition, and what film thickness range is effective?

**Expected Answer:** EP 2 316 980. The optimal alloy is Fe-78.5%Ni (permalloy composition), and the effective film thickness range is 0.1 µm to 0.6 µm. Below 0.1 µm, the relative permeability drops below 10,000. Above 0.6 µm, the effect saturates.

**Evidence:** EP2316980_A1, paragraphs [0013]–[0021], Table 2.

**Retrieval Type Tested:** Semantic — "align near-surface magnetic domains" paraphrases the text's "magnetic domains in the vicinity of a surface... are aligned in a direction parallel to the surface." "Low excitation levels" paraphrases "low magnetic field."

---

### Q12

**Question:** Which patent describes a method to improve directional magnetic properties by deliberately preserving an unrecrystallized worked texture from the hot rolling stage through the first cold rolling pass, and what specific processing constraint makes this possible?

**Expected Answer:** EP 2 602 335. The constraint is that the first cold rolling must be started without performing hot-rolled sheet annealing after hot rolling (i.e., maintaining the metallic structure from the finish rolling). Additionally, the hot rolling finish temperature must be 900°C or less (preferably 860°C or less). This preserves a high proportion of non-recrystallized rolled texture with {110}<001> orientation, which after intermediate annealing and a second cold rolling at 40–85% reduction, develops into crystal grains with the {110}<001> (Goss) orientation during finish annealing, improving rolling-direction magnetic properties.

**Evidence:** EP2602335_A1, paragraphs [0017], [0032]–[0035].

**Retrieval Type Tested:** Semantic — "deliberately preserving an unrecrystallized worked texture" paraphrases "start the first cold-rolling while maintaining a metallic structure of the steel strip at the end of the hot-rolling." "Directional magnetic properties" paraphrases "magnetic properties in the rolling direction."

---

## Category 4: Entity-Relationship / Knowledge Graph (4 Questions)

These questions test the ability to trace relationships between entities (elements, properties, processes, and formulas).

---

### Q13

**Question:** In EP 2 439 302, three numbered expressions govern the Bi-Ti-S system. Map each expression to the entities it constrains: which elements appear in each expression, and what property or outcome does each expression control?

**Expected Answer:**
- **Expression (1):** Contains [Ti] and [Bi]. Controls the boundary between successful suppression of Ti inclusions (TiN, TiS) and failure. Defines the minimum Bi content relative to Ti content.
- **Expression (2):** Contains [Ti] and [Bi]. A stricter subset of (1) that further reduces both Ti inclusions and metallic Bi inclusions, yielding even better crystal grain growth and magnetic properties.
- **Expression (3):** Contains [S], [REM], and [Ca]. Controls the amount of free sulfur. Ensures [S] − 0.23[REM] − 0.4[Ca] ≤ 0.005 mass%, preventing Bi from being compositely precipitated in MnS.

**Evidence:** EP2439302_A1, paragraphs [0009]–[0011], [0032], [0040]–[0042].

**Retrieval Type Tested:** Relational — requires traversing the link between three different expressions, the elements they constrain, and the downstream property each controls.

---

### Q14

**Question:** In EP 2 698 441, what is the chain of causal relationships linking the parameter [Mn]/[S] to the final product's mechanical and magnetic quality? Specifically, how does this ratio influence sulfide density, and how does sulfide density influence both yield stress and core loss?

**Expected Answer:** [Mn]/[S] controls the number density of MnS sulfide precipitates (circle-equivalent diameter 0.1–1.0 µm). When [Mn]/[S] > 50, sulfide density is too low → insufficient crystal grain growth suppression → low yield stress and low fracture elongation. When [Mn]/[S] < 10, sulfide density is too high → excessive suppression of crystal grain growth → core loss deteriorates significantly, recrystallization may be suppressed, and fracture elongation drops. The optimal range is 10 ≤ [Mn]/[S] ≤ 50, yielding sulfide density of 1.0×10⁴ to 1.0×10⁶ pieces/mm², which achieves ≥700 MPa yield stress, ≥10% fracture elongation, and acceptable core loss W10/400.

**Evidence:** EP2698441_A1, paragraphs [0031], [0035]–[0036].

**Retrieval Type Tested:** Relational — requires following a multi-hop causal chain: [Mn]/[S] → sulfide density → grain growth suppression → (yield stress, fracture elongation, core loss).

---

### Q15

**Question:** In EP 2 537 954, what role does Chromium (Cr) play at the alloy layer interface, and how does its presence in the alloy layer create a feedback loop that affects wrinkling of the plating surface?

**Expected Answer:** Cr in the plating bath partially concentrates in the alloy layer (between the steel substrate and plating layer) at a higher concentration than in the plating layer itself. From the alloy layer, Cr promotes the growth of the Si-Mg phase in the plating layer. This increases both the volume percentage of Si-Mg phase and the ratio of Mg in Si-Mg phase to total Mg weight. The Si-Mg phase, in turn, forms a solid-liquid mixed phase during solidification that decreases fluidity of the hot-dip plating metal, which inhibits wrinkle formation on the plating surface. Thus Cr → alloy layer enrichment → Si-Mg phase growth → fluidity decrease → wrinkle inhibition.

**Evidence:** EP2537954_A1, paragraphs [0081], [0085]–[0086].

**Retrieval Type Tested:** Relational — requires connecting entities (Cr → alloy layer → Si-Mg phase → fluidity → wrinkling) across multiple paragraphs.

---

### Q16

**Question:** According to EP 1 577 413, what specific type of precipitate is formed by adding Cr to Si-containing non-oriented electrical steel, and what is the approximate size of these precipitates as observed by SEM?

**Expected Answer:** Fine nitrides containing chromium (chromium nitrides) are formed, having a diameter of about several hundreds of nanometers, as observed by cross-sectional SEM imaging.

**Evidence:** EP1577413_A1, paragraph [0016].

**Retrieval Type Tested:** Relational — requires linking the entity "Cr addition" to the entity "fine chromium nitrides" and its measured property "several hundreds of nanometers."

---

## Category 5: Multi-Document Synthesis (4 Questions)

These questions require information from at least two different patents to construct a complete answer.

---

### Q17

**Question:** Both EP 2 390 376 and EP 2 679 695 deal with high-strength non-oriented electrical steel sheets that use titanium for strengthening. However, they define different parametric constraints on Ti content. Compare the two approaches: what parameter does each patent use to constrain Ti, and what are the fundamental differences in Ti content ranges and strengthening mechanisms between them?

**Expected Answer:**
- **EP 2 390 376** uses RTi = [Ti]/(4×([C]+[N])), constrained to 1 ≤ RTi ≤ 10. Ti content is preferably 0.1–0.3 mass% (high Ti). Strengthening comes from: (a) precipitation strengthening via Ti carbonitrides, (b) grain refining strengthening, and (c) solid-solution Ti orienting {111} surface texture during cold rolling. Targets tensile strength ≥900 MPa and W10/1000 ≤100 W/kg.
- **EP 2 679 695** uses Ti* = Ti − 3.4[N%], constrained to 0.008 ≤ Ti* < 1.2[C%], with an absolute Ti limit of ≤0.04 mass% (very low Ti). Strengthening comes from controlled precipitation of fine Ti carbides that inhibit grain growth during final annealing. Targets high tensile strength and fatigue limit strength with W10/400 as the iron loss metric.

The key difference: EP 2 390 376 uses ~10× more Ti and relies on a combination of precipitation + solid solution, while EP 2 679 695 uses trace-level Ti and controls it to be just enough for fine carbide precipitation without excess.

**Evidence:** EP2390376_A1 [0010], [0017]–[0019]; EP2679695_A1 [0048], Claims.

**Retrieval Type Tested:** Multi-Document Synthesis — requires retrieving and contrasting two different Ti control paradigms from different patents.

---

### Q18

**Question:** EP 1 816 226 and EP 2 439 302 both address the problem of harmful Ti inclusions degrading magnetic properties in non-oriented electrical steel after annealing. What are the two fundamentally different strategies they employ to neutralize titanium, and is there a compositional overlap (shared element) between them?

**Expected Answer:**
- **EP 1 816 226** strategy: Fix Ti as TiN by coprecipitating it on REM oxysulfide surfaces (especially at fracture sites). This requires REM, O, and S to satisfy Formula 1 ([REM]²×[O]²×[S] ≥ 1×10⁻¹⁵) and Formula 2 for TiN formation.
- **EP 2 439 302** strategy: Add Bi (bismuth) to the steel to directly suppress Ti inclusions (TiN, TiS, TiC). Bi acts to reduce Ti precipitate formation by a mechanism where Bi reduces the production of Ti inclusions.
- **Shared element:** REM appears in both. EP 1 816 226 uses REM as the primary Ti-fixing agent (via oxysulfides). EP 2 439 302 uses REM (and Ca) as a secondary desulfurization agent to prevent Bi from being trapped in MnS — but the primary Ti-neutralizing agent is Bi, not REM.

**Evidence:** EP1816226_A1 [0066]–[0070]; EP2439302_A1 [0008]–[0013], [0039], [0055].

**Retrieval Type Tested:** Multi-Document Synthesis — requires understanding two fundamentally different Ti-neutralization mechanisms and finding the shared REM entity with its different role in each patent.

---

### Q19

**Question:** Three patents — EP 2 698 441, EP 2 278 034, and EP 2 390 376 — all target high-strength non-oriented electrical steel with yield stress ≥700 MPa. Each uses a different primary strengthening mechanism. Identify the primary mechanism for each patent and the specific core loss metric each patent uses to evaluate magnetic performance.

**Expected Answer:**
- **EP 2 698 441:** Primary mechanism = Cu precipitation + MnS sulfide-controlled grain refinement. Core loss metric = W10/400 (1.0 T, 400 Hz). Also requires sulfide number density of 1.0×10⁴–1.0×10⁶ pieces/mm².
- **EP 2 278 034:** Primary mechanism = Cu precipitation strengthening combined with grain refinement via Nb/Zr/Ti/V carbonitrides. Core loss metric = eddy current loss We10/400 (derived from the dual-frequency method), constrained by Formula (3): We10/400 ≤ 70×t².
- **EP 2 390 376:** Primary mechanism = Ti carbonitride precipitation + Ti solid solution strengthening. Core loss metric = W10/1000 (1.0 T, 1000 Hz), targeting ≤100 W/kg.

**Evidence:** EP2698441_A1 [0017], [0029]–[0031]; EP2278034_A1 [0064]–[0065]; EP2390376_A1 [0009], [0017]–[0018], [0026].

**Retrieval Type Tested:** Multi-Document Synthesis — requires retrieving three distinct strengthening strategies and their associated loss metrics from three separate patents.

---

### Q20

**Question:** EP 2 316 980 uses a surface coating approach to improve magnetic properties, while EP 1 577 413 uses bulk alloying with Cr. Could these two approaches theoretically be combined on the same steel sheet? Identify any compositional contradictions between the base steel compositions used in their experiments that would prevent combination.

**Expected Answer:** Theoretically, the two approaches target different mechanisms and could be complementary (surface domain alignment vs. bulk nitride precipitation). However, there are compositional differences in the base steels:
- **EP 2 316 980** (Experiment 2) uses a base steel with Si: 4.5%, Al: 3.5% (very high Al), thickness 0.30 mm.
- **EP 1 577 413** (Table 1) uses steels with Si: ~2.9–3.3%, Al: 0.005% (extremely low Al), and Cr: 1.04–4.49%.

There is no fundamental compositional *contradiction* preventing combination, but the Al contents are vastly different: EP 2 316 980's high-Al base would need to also accommodate EP 1 577 413's requirement for Cr ≥ ~1% and very low Al (0.005%). If the Fe-Ni alloy film were applied to the Cr-containing steel of EP 1 577 413, the low Al content would be compatible. The key practical question is whether the Cr nitrides in the bulk steel interfere with the domain-aligning effect of the surface Fe-Ni film, which is not addressed by either patent.

**Evidence:** EP2316980_A1 [0053]; EP1577413_A1 Table 1, [0016].

**Retrieval Type Tested:** Multi-Document Synthesis — requires comparing base compositions across two patents and reasoning about compatibility at the boundary condition level.

---

## Summary Distribution

| Category | Questions | Retrieval Types |
|---|---|---|
| 1. Keyword & Formula Precision | Q1–Q4 | Keyword (BM25) |
| 2. Tabular & Numerical Reasoning | Q5–Q8 | Table-Reasoning |
| 3. Semantic & Conceptual | Q9–Q12 | Semantic |
| 4. Entity-Relationship / Knowledge Graph | Q13–Q16 | Relational |
| 5. Multi-Document Synthesis | Q17–Q20 | Multi-Document |

## Patent Coverage

| Patent | Questions Referencing It |
|---|---|
| EP 2 390 376 | Q1, Q17, Q19 |
| EP 1 816 226 | Q2, Q9, Q18 |
| EP 2 278 034 | Q3, Q7, Q19 |
| EP 2 679 695 | Q4, Q8, Q17 |
| EP 2 698 441 | Q5, Q6, Q14, Q19 |
| EP 2 439 302 | Q10, Q13, Q18 |
| EP 2 316 980 | Q11, Q20 |
| EP 2 602 335 | Q12 |
| EP 2 537 954 | Q15 |
| EP 1 577 413 | Q16, Q20 |
