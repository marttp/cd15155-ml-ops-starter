# Task 2 registry evidence

Verified on 13 October 2026 using the course module-07 and module-11 patterns.
Evaluation uses the shared corrected FinBERT loader and immutable model revision.
All 1,629 DVC test samples were evaluated without changing the supplied threshold.

| Metric | Value |
| --- | --- |
| accuracy | 0.63842848 |
| f1_weighted | 0.59008130 |
| precision_weighted | 0.61110856 |
| recall_weighted | 0.63842848 |

MLflow experiment: finbert-evaluation. Run: `7c07fe666b40421b93891f4f057bf86b`.
Registered model: finbert. Version: 2. Alias: production.
Model revision: ec5ffa074fc00da4de8b28554a57aa1debf92508.
The run logs the test CSV checksum, sample count, model settings, classification
report, DVC lock, parameters, and full model artifacts.

Seven promotion tests passed, covering missing evaluations, invalid F1,
run/model lineage mismatch, numeric latest-version selection, and the threshold
boundary. A real rejection check temporarily set the threshold to 1.0, observed
the rejection message, and confirmed the production alias stayed unchanged;
the rubric threshold 0.56 was restored. Loading models:/finbert@production
returned positive with approximately 0.545465 confidence for the profits headline.

Evaluation runs are tagged separately from setup and monitoring. Promotion
requires the latest registered version to belong to the latest completed model
evaluation and to be ready. It fails rather than promoting a different version
using an unrelated score. These results demonstrate the assessment gate;
a 0.5901 weighted F1 does not establish broad financial-domain reliability.
