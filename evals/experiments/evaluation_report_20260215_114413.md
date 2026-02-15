# RAGAS Evaluation Report

**Evaluation Date:** 2026-02-15T11:49:13.819334

**Total Questions:** 12

## RAGAS Metrics

| Metric | Score |
|--------|-------|
| faithfulness | 0.9155 |
| answer_relevancy | 0.8619 |
| context_precision | 0.7663 |
| context_recall | 0.9444 |

## Category Statistics

| Category | Questions | Avg Contexts | BM25 | Semantic | Graph |
|----------|-----------|--------------|------|----------|-------|
| single_hop_specific_query_synthesizer | 4 | 10.0 | 9.8 | 8.2 | 2.0 |
| multi_hop_abstract_query_synthesizer | 4 | 10.0 | 8.2 | 7.8 | 5.8 |
| multi_hop_specific_query_synthesizer | 4 | 10.0 | 9.0 | 9.0 | 4.5 |

## Retriever Contribution Analysis

Total retrievals: 257

| Retriever | Contributions | Percentage |
|-----------|---------------|------------|
| BM25 | 108 | 42.0% |
| Semantic | 100 | 38.9% |
| Graph | 49 | 19.1% |

## Question-by-Question Results

### G1: single_hop_specific_query_synthesizer

**Retrieval Type:** hybrid

**Question:** What is the specified range for N content in the high-strength non-oriented electrical steel sheet?

**Retriever Stats:** BM25=9, Semantic=4, Graph=8

**Ground Truth:**
```
The N content is specified as not less than 0.002% nor more than 0.05% by mass....
```

**Generated Answer:**
```
The specified range for N content in the high-strength non-oriented electrical steel sheet is not less than 0.002% nor more than 0.05% by mass% [Source 1]. This range is also confirmed in the preamble, which states N: not less than 0.002% nor more than 0.05% [Source 5]. Additionally, the manufacturing method for this steel sheet specifies the same N content range of not less than 0.002% nor more than 0.05% by mass% [Source 7]. No other N content ranges are specified for this particular high-stre...
```

---

### G2: multi_hop_abstract_query_synthesizer

**Retrieval Type:** hybrid

**Question:** How does the material composition analysis of invention examples compare to comparative examples in terms of yield stress and eddy current loss, based on the provided tables and embodiment results?

**Retriever Stats:** BM25=6, Semantic=7, Graph=10

**Ground Truth:**
```
Material composition analysis across the provided tables and embodiment results shows that invention examples generally achieve higher yield stress and lower eddy current loss compared to comparative examples. For instance, in Table 5 and Table 6, invention examples with optimized contents of C, N, Nb, Zr, Ti, and V consistently exhibit yield stress values in the range of 750–900 MPa and eddy current loss We10/400 values around 7.0–8.0 W/kg. In contrast, comparative examples often fall outside t...
```

**Generated Answer:**
```
Invention examples (c7, c8, c9, c10) have Si content of 2.1% and yield stress values ranging from 700 MPa to 760 MPa, with eddy current loss We10/400*2 values between 4.1 and 9.2 W/kg [Source 1]. Comparative examples (c1 to c6) show lower Si content (data not available in sources for most, except c3 with 1.8%), yield stress values from 540 MPa to 690 MPa, and eddy current loss We10/400*2 values from 4.3 to 6.2 W/kg [Source 1]. The invention examples consistently exhibit higher yield stress compa...
```

---

### G3: multi_hop_specific_query_synthesizer

**Retrieval Type:** hybrid

**Question:** How does increasing Si content affect the yield stress and eddy current loss in the invention examples of electrical steels, based on the data from Table 5 and Table 7?

**Retriever Stats:** BM25=6, Semantic=10, Graph=5

**Ground Truth:**
```
Based on the data from Table 5 (<1-hop>) and Table 7 (<2-hop>), increasing the Si content in the invention examples of electrical steels leads to higher yield stress and lower eddy current loss. In Table 7, as the Si content increases from 2.1% to 3.9% and 4.1%, the yield stress rises from 700 MPa (c7, 2.1% Si) to 900 MPa (c20, 3.9% Si) and 820 MPa (c21, 4.1% Si). Simultaneously, the eddy current loss decreases from 4.3 W/kg (c7, 2.1% Si) to 2.8 W/kg (c20, 3.9% Si) and 2.6 W/kg (c21, 4.1% Si). T...
```

**Generated Answer:**
```
In the invention examples from Table 5 and Table 7, increasing the Si content from 2.1% to 3.9% results in higher yield stress values and lower eddy current loss values [Source 8], [Source 6], [Source 7]. Specifically, at Si = 2.1%, yield stress ranges from 610 MPa to 760 MPa and eddy current loss ranges from 4.1 W/kg to 4.3 W/kg [Source 8]. At Si = 3.5%, yield stress increases to 710–810 MPa and eddy current loss decreases to 3.2–3.3 W/kg [Source 6], [Source 7]. At Si = 3.9%, yield stress furth...
```

---

### G4: single_hop_specific_query_synthesizer

**Retrieval Type:** hybrid

**Question:** Wht is the imprtance of a rotor in the cntxt of non-orinted electrial steel shets for high-speed rotary machnes, and how does the invntion adress the techncal problms associted with it?

**Retriever Stats:** BM25=10, Semantic=9, Graph=0

**Ground Truth:**
```
The present invention relates to a non-oriented electrical steel sheet suitable for a rotor of a high-speed rotary machine. The invention aims to provide a non-oriented electrical steel sheet that can be manufactured easily while achieving high tensile strength and low high-frequency core loss....
```

**Generated Answer:**
```
The rotor in high-speed rotary machines is subjected to extremely large stress due to centrifugal force, which is proportional to the rotation radius and the square of the rotation speed, making high tensile strength in the non-oriented electrical steel sheet essential for reliable operation [Source 4]. The invention addresses these technical problems by providing a non-oriented electrical steel sheet with a tensile strength of 900 MPa or more, enabling sufficient high-speed rotation of the roto...
```

---

### G5: multi_hop_abstract_query_synthesizer

**Retrieval Type:** hybrid

**Question:** How does grain refining strengthening contribute to achieving high tensile strength in non-oriented electrical steel sheets, and what role does the appropriate Ti content and RTi value play in this process?

**Retriever Stats:** BM25=9, Semantic=9, Graph=4

**Ground Truth:**
```
Grain refining strengthening contributes to achieving high tensile strength in non-oriented electrical steel sheets by increasing the tension of the steel through the formation of fine precipitates, specifically Ti carbonitride, which results from the reaction of Ti with C and N. The appropriate Ti content and RTi value are crucial for this process. According to the context, Ti enhances tension by precipitation strengthening and grain refining strengthening. The RTi value, defined as [Ti]/(4x([C...
```

**Generated Answer:**
```
Grain refining strengthening contributes to achieving high tensile strength in non-oriented electrical steel sheets by refining the crystal grains, which increases the tension of the steel sheet [Source 1]. Ti plays a crucial role in this process by reacting with C and N to form fine Ti carbonitride precipitates, which promote both precipitation strengthening and grain refining strengthening [Source 1]. The appropriate Ti content, quantified by the RTi value ([Ti]/(4×([C]+[N]))), ensures that su...
```

---

### G6: multi_hop_specific_query_synthesizer

**Retrieval Type:** hybrid

**Question:** Howw does the additon of Si, Al, Ni, and Mn in the non-orientd electrical steel shet contribute to low high-frequncy core loss, and why is this important for rotors of high-speed rotary machines as described in the invention?

**Retriever Stats:** BM25=10, Semantic=10, Graph=1

**Ground Truth:**
```
The additon of Si, Al, Ni, and Mn in the non-oriented electrical steel sheet contributes to low high-frequency core loss by increasing the electrical resistance of the steel, which reduces eddy current loss. Si and Al both reduce high-frequency core loss by raising electrical resistance, while Ni and Mn also help by increasing resistance and further improving tension through solid solution strengthening and grain refining. Maintaining the proper content ranges for these elements ensures that the...
```

**Generated Answer:**
```
The addition of Si, Al, Ni, and Mn to non-oriented electrical steel sheet contributes to low high-frequency core loss by increasing the electrical resistance of the steel, which reduces eddy current loss and thus suppresses core loss at high frequencies [Source 7] [Source 8] [Source 9]. Si is particularly effective, as it achieves higher tensile strength, higher fatigue strength, and lower iron loss in a balanced manner, with a preferred content of 3.0% or more and an upper limit of 5.0% to avoi...
```

---

### G7: single_hop_specific_query_synthesizer

**Retrieval Type:** hybrid

**Question:** What is the significance of the rolling direction in improving magnetic properties of non-oriented electrical steel sheets?

**Retriever Stats:** BM25=10, Semantic=10, Graph=0

**Ground Truth:**
```
The rolling direction is significant because the present invention aims to improve magnetic properties in that direction for non-oriented electrical steel sheets....
```

**Generated Answer:**
```
The significance of the rolling direction in improving magnetic properties of non-oriented electrical steel sheets is that favorable magnetic properties in the rolling direction are sometimes required for applications such as divided iron cores of rotary machines and iron cores of medium or small sized transformers, where magnetic fluxes mainly flow in orthogonal directions and the rolling direction is set to the direction with the largest influence of magnetic flux flow [Source 3]. The present ...
```

---

### G8: multi_hop_abstract_query_synthesizer

**Retrieval Type:** hybrid

**Question:** How they improve magnetic properties in rolling direction for non-oriented electrical steel sheet, and why old ways not enough?

**Retriever Stats:** BM25=10, Semantic=10, Graph=0

**Ground Truth:**
```
They improve magnetic properties in rolling direction for non-oriented electrical steel sheet by adjusting contents of Si, Al, Mn, and other elements, controlling hot-rolling finish temperature, and using specific cold-rolling and annealing steps. Old ways not enough because just increasing Si and Al can lower saturation magnetic flux density, which is bad for making electric equipment smaller and more efficient. So, new method uses right mix of elements and process steps to get better magnetic ...
```

**Generated Answer:**
```
Magnetic properties in the rolling direction of non-oriented electrical steel sheet are significantly improved by appropriately combining the finish temperature in hot-rolling (900°C or less) and the rolling reduction in the second cold-rolling (not less than 40% nor more than 85%) [Source 1]. Additionally, the inclusion of elements such as Sn, Cu, or Cr further enhances magnetic properties in the rolling direction and suppresses iron loss, as demonstrated by comparative examples [Source 6]; [So...
```

---

### G9: multi_hop_specific_query_synthesizer

**Retrieval Type:** hybrid

**Question:** How does the presence of Sn in the steel slab composition affect the magnetic flux density B50 and iron loss W10/400, based on the experimental results for conditions 12, 13, and 15?

**Retriever Stats:** BM25=10, Semantic=6, Graph=9

**Ground Truth:**
```
The presence of Sn in the steel slab composition can be observed in conditions 12, 13, and 15. According to the data, condition 12 contains 0.07% Sn, condition 13 contains 0.08% Sn, and condition 15 contains 0.07% Sn. The magnetic flux density B50 for these conditions is 1.69 T (condition 12), 1.77 T (condition 13), and 1.70 T (condition 15). The iron loss W10/400 for these conditions is 15.6 W/kg (condition 12), 13.1 W/kg (condition 13), and 15.7 W/kg (condition 15). This indicates that with th...
```

**Generated Answer:**
```
In the experimental results for conditions 12, 13, and 15, the presence of Sn in the steel slab composition at amounts exceeding 0.010% led to the occurrence of scabs, as observed in condition 15, but also resulted in a high magnetic flux density B50 [Source 6]. Specifically, condition 15, which had Sn exceeding 0.010%, showed a B50 value of 1.70 T and an iron loss W10/400 of 15.7 W/kg [Source 5]. In contrast, conditions 12 and 13, with lower or unspecified Sn content, exhibited B50 values of 1....
```

---

### G10: single_hop_specific_query_synthesizer

**Retrieval Type:** hybrid

**Question:** How you use vacuum melting furnace for make steel billet in experiment, what steps you do after, and what you measure after all that?

**Retriever Stats:** BM25=10, Semantic=10, Graph=0

**Ground Truth:**
```
In the experiment, steels with specified compositions were melted in a vacuum melting furnace in a laboratory, and a steel billet (slab) was made from each of the steels. After that, each steel billet was heated at 1100°C for 60 minutes and subjected to hot rolling to obtain hot-rolled sheets with a thickness of 2.0 mm. These hot-rolled sheets were then annealed at 1050°C for one minute, pickled, and cold rolled once to produce cold-rolled sheets with a thickness of 0.35 mm. Subsequently, the co...
```

**Generated Answer:**
```
To make a steel billet in an experiment, steel compositions are melted in a vacuum melting furnace in a laboratory [Source 1][Source 2][Source 3][Source 4][Source 5][Source 6][Source 7][Source 8][Source 9][Source 10]. After melting, the steel is cast into billets (slabs), which are then heated (e.g., at 1100°C for 60 minutes) and subjected to hot rolling to obtain hot-rolled sheets of specified thickness (e.g., 2.0 mm) [Source 1][Source 2][Source 3][Source 4][Source 5][Source 6][Source 7][Source...
```

---

### G11: multi_hop_abstract_query_synthesizer

**Retrieval Type:** hybrid

**Question:** What is the high-strength non-oriented electrical steel sheet described in the patent documentation, and how do the claims and international search report relate to its composition and inventive step?

**Retriever Stats:** BM25=8, Semantic=5, Graph=9

**Ground Truth:**
```
The high-strength non-oriented electrical steel sheet described in the patent documentation contains, in mass%, C: 0.010% or less; Si: 2.0% to 4.0%; Mn: 0.05% to 0.50%; Al: 0.2% to 3.0%; N: 0.005% or less; S: 0.005% to 0.030%; Cu: 0.5% to 3.0%, with the balance being Fe and inevitable impurities. It also specifies a certain number of sulfide pieces per mm2 and allows for additional elements like Ni and others in small amounts. The patent documentation, as shown in the international search report...
```

**Generated Answer:**
```
The high-strength non-oriented electrical steel sheet described in the patent documentation is characterized by a composition containing, by mass%, C: not less than 0.002% nor more than 0.05%, Si: not less than 2.0% nor more than 4.0%, Mn: not less than 0.05% nor more than 1.0%, N: not less than 0.002% nor more than 0.05%, Cu: not less than 0.5% nor more than 3.0%, Al: 3.0% or less, with the balance being Fe and inevitable impurities, and may further contain Ni: not less than 0.5% nor more than ...
```

---

### G12: multi_hop_specific_query_synthesizer

**Retrieval Type:** hybrid

**Question:** How do variations in the [Mn]/[S] ratio and the temperature of finish annealing affect the number density of sulfide and the resulting core loss and mechanical properties in non-oriented electrical steel sheet?

**Retriever Stats:** BM25=10, Semantic=10, Graph=3

**Ground Truth:**
```
Variations in the [Mn]/[S] ratio and the temperature of finish annealing significantly impact the number density of sulfide, which in turn affects the core loss and mechanical properties of non-oriented electrical steel sheet. When the [Mn]/[S] ratio is between 10 and 50, good properties are generally obtained. However, increasing the finish annealing temperature (e.g., to 1000°C) causes sulfide to coarsen, reducing its number density and leading to lower fracture elongation due to insufficient ...
```

**Generated Answer:**
```
Variations in the [Mn]/[S] ratio and the temperature of finish annealing significantly affect the number density of sulfide and the resulting core loss and mechanical properties in non-oriented electrical steel sheet [Source 2]. When the [Mn]/[S] ratio is not less than 10 nor more than 50, good properties are obtained; however, increasing the finish annealing temperature (e.g., to 1000°C) causes sulfide to coarsen, decreases the number density of sulfide, and lowers fracture elongation, as cryst...
```

---

