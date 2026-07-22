# RAG Validation Fixture — Photosynthesis (multi-chunk corpus)

This document exercises the full RAG pipeline with enough content to produce **multiple
indexed chunks** (default chunk size 400 tokens). Expected phrases are spread across
sections so **retrieve limit**, **rerank**, and **vector vs hybrid** can change benchmark
scores instead of always returning perfect coverage from a single chunk.

## Methods primer and study design

Plant physiology courses begin with experimental design, replication, and measurement error.
Students record leaf temperature, stomatal conductance, and ambient humidity when comparing
treatments across growth chambers. Statistical software fits mixed models to account for
block effects and random intercepts per plant individual. Peer review emphasizes transparent
reporting of sample sizes, exclusion criteria, and pre-registered hypotheses.

Instrument calibration spans quantum sensors, infrared gas analyzers, and chloroplast
fractionation protocols that do not by themselves demonstrate energy conversion outcomes.
Field notebooks should document soil moisture, photoperiod, and nutrient additions. Teaching
labs often pair microscopy with quantitative assays so learners connect structure and function
without assuming a single lecture captures the entire metabolic map.

Historical accounts describe early carbon-labeling experiments using radioactive tracers,
later replaced by stable isotope methods. Modern meta-analyses synthesize crop trial data
across climates to estimate yield sensitivity to elevated atmospheric CO2. Extension services
translate research summaries for growers choosing cultivars and irrigation schedules.

## Overview of autotrophic metabolism

Autotrophic organisms build reduced carbon from inorganic precursors. The overall balance
summarizes carbon dioxide and water forming carbohydrates while releasing oxygen. Learners
often contrast this anabolic pathway with respiratory catabolism, which releases stored
chemical bond energy for cellular maintenance, growth, and reproduction.

Organelle compartmentalization matters: outer membranes, inner membranes, and soluble stroma
each host distinct enzyme systems. Productivity metrics include grams of fixed carbon per
ground area per season, sometimes partitioned into above-ground and below-ground pools.
Satellite vegetation indices track canopy greenness yet remain indirect proxies for
photochemical performance in the field.

## Pigments and light capture

The green color of leaves comes from chlorophyll pigments embedded in thylakoid membranes.
Chlorophyll a and chlorophyll b absorb strongly in blue and red wavelengths while
reflecting green light. Accessory pigments such as carotenoids broaden the usable spectrum
and protect reaction centers from photo-oxidative damage during high irradiance.

When photons strike pigment molecules, electrons enter an excited state and feed the
photosynthetic electron transport chain. Laboratory chromatography separates pigment bands
on filter paper, a classic classroom demonstration useful for identifying composition.

## Light-dependent reactions

The light-dependent reactions occur on the thylakoid membranes inside chloroplasts. During
this stage, water molecules are split in photolysis, releasing oxygen as a byproduct into
the atmosphere. The light-dependent reactions generate ATP and NADPH, which are energy
carriers consumed in the next major phase of carbon fixation.

Cyclic and non-cyclic electron flow pathways adjust ATP/NADPH ratios to meet metabolic
demand. Photosystem II and Photosystem I work in series during non-cyclic photophosphorylation.
Environmental stressors such as drought or extreme temperatures can down-regulate these
reactions before Calvin cycle activity declines.

## Carbon fixation and the Calvin cycle

The Calvin cycle takes place in the chloroplast stroma and does not require light directly,
though it depends on ATP and NADPH produced earlier. Ribulose bisphosphate carboxylase,
often called RuBisCO, catalyzes the fixation of carbon dioxide into organic intermediates.
After several reduction steps, the cycle regenerates its starting material and net-produces
triose phosphates that are converted into glucose and other carbohydrates for growth.

Starch accumulates in chloroplasts when synthesis exceeds export demand. Sucrose transport
to sink tissues supports root development and fruit formation. Agricultural yields depend
partly on optimizing Calvin cycle flux under varying CO2 concentrations and temperature.

## Plant ecology and distractor context

Terrestrial ecosystems vary in leaf area index, soil nitrogen availability, and seasonal
phenology. Decomposers return mineral nutrients to the soil food web. Mycorrhizal fungi
extend root absorption surfaces for phosphorus and water. Comparative physiology courses
contrast wetland plants, CAM species, and C4 grasses with temperate C3 crops.

## Cellular respiration contrast

Cellular respiration oxidizes sugars in mitochondria to produce ATP for cellular work.
Glycolysis, the citric acid cycle, and oxidative phosphorylation constitute the major
phases. Respiration and autotrophic carbon fixation are complementary across the diel cycle.

## Validation markers

When retrieval works correctly, queries about photosynthesis energy conversion should
surface passages mentioning **chlorophyll** (pigments section), **light-dependent reactions**
(thylakoid section), and **glucose** (Calvin cycle section). With a low retrieve limit,
not all phrases may appear in the merged context — that is expected and should lower
phrase coverage in the benchmark dashboard.
