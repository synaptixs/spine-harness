# Experiment scope and reporting

The package supports ten built-in tasks and JSON extensions on one pinned Spine repository. Repeating a task measures variation on that task; it does not add independent problems. The two custom examples illustrate authoring, not broad coverage. Changing repository paths alone does not supply compatible setup, graders, or scope rules.

Before running, freeze task text, judges, target and workflow versions, model, reasoning effort, resource limits, retry/checklist policy, and outcome definitions. `EXPERIMENT.json` captures selected tasks, fingerprints, and run settings. Preserve the authored catalog alongside it. Fixed serial ordering in subscription mode is not randomized paired execution.

Use `report_results.py` for new experiments. It pairs by ticket and repeat, adds the matching separate intake measurement, and computes cost direction across distinct scenario means. It supports arbitrary catalog sizes; it does not enumerate an exponential bootstrap or pool repeated runs as independent problems. Its sign test assumes independent scenario signs, which similar tasks on one repository may not satisfy. Partial paired runs defer inference. A non-significant quality difference does not prove equivalence.

Report every attempted run, including pauses, capacity errors, timeouts, and manual recovery. Preserve failure costs even when they do not appear in completed-run averages. Usage is based on exported response records; missing interrupted exports remain unknown. Dollars are API list-price equivalents, not subscription invoices. The two workflow timing boundaries differ, and caches are not reset: do not promote descriptive wall times to a controlled end-to-end speed claim.

Functional success, own tests, scope fit, and the repository-count gate are distinct endpoints. The gate is not a comprehensive merge-readiness check. A documentation-count update or package export may be a reasonable change even when the inherited fit grader penalizes it. Full-suite execution done by an agent can vary between runs; the recorded common endpoints should be used for comparisons.

For broader claims, prioritize distinct realistic problems over more repeats: bug fixes, API changes, refactoring, and larger integration work, across multiple repositories with suitable adapters. A 20–30 problem study is a planning range, not a power guarantee. Specify meaningful cost and quality differences, choose a sampling and stopping plan, and account for task/repository clustering before collecting data. Do not add tasks selectively until p falls below 0.05. A graph-on/graph-off experiment is required to isolate the causal effect of the graph.

The completed earlier stock study used three scenarios and three repeats per workflow. Its large observed cost difference did not pass its three-ticket sign test (p=0.25). This release adds catalog and edit-detection capabilities; label new measurements with its package version instead of silently pooling them with the earlier experiment.

The legacy `summarize.py` is retained for historical compatibility. Its run-level statistics and fleet projections are not the primary analysis for a repeated-task experiment.

References:
- [NIST paired sign test](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/signtest.htm)
- [SciPy: independent samples assumption](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html)
- [ASA: interpreting p-values](https://www.amstat.org/docs/default-source/amstat-documents/p-valuestatement.pdf)
