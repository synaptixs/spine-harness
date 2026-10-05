#!/usr/bin/env python3
"""Render the completed study in the supplied decision-report structure, without new model calls."""
from pathlib import Path
import argparse
import itertools
import json
import math
import statistics as st
import subprocess
import sys
from build_comparison_report import completed, sign_p, percentile
from model_report import model_section
from report_usage import summarize_usage


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results', type=Path, required=True)
    args = ap.parse_args()
    root = args.results.resolve()
    read = lambda p: json.loads(p.read_text())
    protocol = read(root/'PROTOCOL.json')
    model = protocol['model']
    tickets, repeats = protocol['tickets'], protocol['passes']
    sk = [read(p) for p in sorted((root/model).glob('speckit/*/summary.json'))]
    sp = [read(p) for p in sorted((root/model).glob('spine/pass*/*/summary.json'))]
    intake_rows = [d for p in (root/model).glob('intake/pass*.json') for d in read(p)]
    expected = {(t,n) for t in tickets for n in range(1,repeats+1)}
    for rows in (sk,sp,intake_rows):
        assert len(rows)==len(expected) and {(r['ticket'],r['pass']) for r in rows}==expected
    assert len(expected)==9 and len(tickets)==3 and repeats==3, 'This reference template describes the completed 3×3 study'
    assert all(completed(r) for r in sk)
    assert all(not r.get('aborted') and r['usage_complete'] for r in sp)
    intake = {(d['ticket'],d['pass']):d for d in intake_rows}
    sp_by = {(d['ticket'],d['pass']):d for d in sp}
    sc = lambda d: d['cost_usd']+intake[(d['ticket'],d['pass'])]['cost_usd']
    sk_cost=st.mean(d['total']['cost_usd'] for d in sk)
    sp_cost=st.mean(sc(d) for d in sp)
    sk_tokens=st.mean(d['total']['input']+d['total']['output'] for d in sk)
    sp_tokens=st.mean(d['prompt_tokens']+d['completion_tokens']+intake[(d['ticket'],d['pass'])]['prompt']+intake[(d['ticket'],d['pass'])]['completion'] for d in sp)
    ratio=sk_cost/sp_cost
    means=[]; paired_table=[]; quality=[]; sensitivity=[]
    for t in tickets:
        a=[d for d in sk if d['ticket']==t]; b=[d for d in sp if d['ticket']==t]
        x,y=st.mean(d['total']['cost_usd'] for d in a),st.mean(sc(d) for d in b)
        means.append((x,y))
        paired_table.append(f'| {t} | 3 | ${x:.4f} | ${y:.4f} | {x/y:.2f}× |')
        quality.append((sum(d['grading']['repo_gate_pass'] for d in a)/3,sum(d['repo_gate_pass'] for d in b)/3))
        clean=[d for d in a if not d.get('capacity_recovery')]
        sensitivity.append((st.mean(d['total']['cost_usd'] for d in clean),st.mean(sc(sp_by[(d['ticket'],d['pass'])]) for d in clean)))
    p=sign_p([x-y for x,y in means]); gp=sign_p([x-y for x,y in quality])
    resamples=[sum(means[i][0] for i in ids)/sum(means[i][1] for i in ids) for ids in itertools.product(range(3),repeat=3)]
    lo,hi=percentile(resamples,.025),percentile(resamples,.975)
    clean_ratio=st.mean(x for x,y in sensitivity)/st.mean(y for x,y in sensitivity)
    assert min(d['total']['cost_usd'] for d in sk)>max(sc(d) for d in sp)
    naive_mw=2/math.comb(18,9)
    # Keep a separately reproducible detailed measurement report.
    subprocess.run([sys.executable,str(Path(__file__).with_name('build_comparison_report.py')),'--results',str(root),'--model',model,'--output','MEASUREMENT_REPORT.md'],check=True)
    detail=(root/'MEASUREMENT_REPORT.md').read_text()
    def section(name):
        return detail.split('## '+name+'\n',1)[1].split('\n## ',1)[0].strip()
    metrics_table=section('Cost, tokens and elapsed time').split('\n\nSpine includes',1)[0]
    outcome_table=section('Outcomes')
    stage_rows=[]
    groups=[('Specify',('01-specify',)),('Clarify, including scripted answer',('02-clarify','02b-clarify-answer')),('Plan',('03-plan',)),('Checklist',('04-checklist',)),('Tasks',('05-tasks',)),('Analyze',('06-analyze',)),('Implement, including continuation/recovery',('07-implement','07b-implement-proceed','07c-capacity-resume')),('Converge',('08-converge',))]
    pre_cost=0
    for label,steps in groups:
        rows=[row for d in sk for row in d['rows'] if row['step'] in steps]
        cost=sum(d['cost_usd'] for d in rows)/9
        tokens=sum(d['input']+d['output'] for d in rows)/9
        stage_rows.append(f'| {label} | ${cost:.4f} | {tokens:,.0f} | {cost/sk_cost*100:.1f}% |')
        if label not in ('Implement, including continuation/recovery','Converge'):pre_cost+=cost
    fleet='\n'.join(f'| {n:,} | {n*48:,} | ${n*48*sk_cost:,.0f} | ${n*48*sp_cost:,.0f} |' for n in (500,1000,2000,5000,10000))
    cache_percent=sum(d['total']['cached'] for d in sk)/sum(d['total']['input'] for d in sk)*100
    stats={'model':model,'distinct_tickets':3,'pairs':9,'cost_ratio':ratio,'ticket_sign_test_p':p,'state_gate_ticket_sign_test_p':gp,'exploratory_ticket_bootstrap':[lo,hi],'excluded_recovery_pair_ratio':clean_ratio,'naive_independent_mann_whitney_p_not_primary':naive_mw,'naive_nine_pair_sign_p_not_primary':2/2**9,'six_unanimous_ticket_sign_p':2/2**6,'projection_features_per_developer_year':48}
    (root/'STATISTICAL_ANALYSIS.json').write_text(json.dumps(stats,indent=2)+'\n')
    body=f'''# spec-kit vs Spine + PKG — evaluated; broader claims provisional

**Status:** measurement complete, 2026-09-29. All 18 planned ticket-arm runs and nine separate intake measurements finished. No adoption or rejection decision is implied.  
**Subject:** spec-kit v1.0.11 versus Spine + PKG v3.52.0, using `{model}` with high reasoning through Codex subscription authentication.  
**How it was assessed:** three existing scenarios, three repeats per workflow, on the same target commit. All measurements below come from this study.  
**Scope of that measurement:** recorded API-equivalent cost, tokens, model responses, descriptive elapsed time, held-out tests, focused tests, lint/type checks, tracked-file changes, and the repository-count gate.  
**Statistical conclusion:** the observed cost ratio is **{ratio:.2f}×**, but the prespecified two-sided sign test across three distinct problems gives **p = {p:.2f}**, above 0.05. A general statistically significant cost advantage is not established by this design.  
**Reference format:** follows the supplied `spec-kit-integration-analysis-3.52.md` structure. Its historical measurements and architectural assertions are not pooled into this dataset.  
**Revisit condition:** expand to distinct problems and repositories under a prespecified analysis and a common acceptance definition.

---

## Spine + PKG, measured

Spine + PKG averaged **${sp_cost:.4f} API-equivalent cost**, **{sp_tokens:,.0f} tokens**, and **4 model responses** per measured attempt, including its separately measured intake. Spec-kit averaged **${sk_cost:.4f}**, **{sk_tokens:,.0f} tokens**, and **117.7 model responses**. The observed ratio is **{ratio:.2f}× on cost** and **{sk_tokens/sp_tokens:.2f}× on tokens**. Every spec-kit run cost more than every Spine run in this dataset.

Both workflows passed **9/9 held-out evaluations** and their focused tests, lint, formatting, and type checks. However, the repository-count gate passed in **5/9 spec-kit runs and 0/9 Spine runs**. The measurements support a substantial cost difference on these small tasks, alongside a maintenance-check advantage for spec-kit. They do not establish equal code quality or a universal winner.

All dollars are **API list-price equivalents, not subscription invoices**. These were Codex subscription runs with no API key. The total equivalent was **$35.68**, including the capacity-interrupted run and its same-model recovery.

## What the evidence means for an enterprise

The useful signal is that a constrained workflow can complete these existing scenarios with much less recorded model traffic. That warrants broader evaluation. It does not justify multiplying the result into a claimed enterprise saving without validating the task mix, acceptance criteria, human effort, maintenance costs, and actual commercial arrangement.

This experiment compares whole workflows. Spec-kit runs multiple conversational stages and can execute repository tools; Spine supplies deterministic design and makes narrowly scoped model calls. Tool access, prompts, context, validation work, and the knowledge graph vary together. The observed difference cannot be assigned specifically to the graph.

## The decision, in one paragraph

**Use this result as a promising benchmark finding and broaden the evaluation before making a general adoption decision.** Spine was much cheaper in these measurements, while spec-kit more often updated the repository's documented counts. Functional checks passed for both. Three distinct create-module problems on one repository provide too little independent problem coverage for a distribution-free claim of general superiority. The next study should prioritize new problems, use a common acceptance endpoint, and retain all failure and recovery costs.

## Why — the findings, in order of weight

### 1. The measured cost difference is large and consistent

The mean ratio is **{ratio:.2f}×**. Ticket-level mean ratios range from **{min(x/y for x,y in means):.2f}× to {max(x/y for x,y in means):.2f}×**. This is an observed effect size, not an estimate that is guaranteed to hold for a new repository or larger task.

### 2. Functional success does not distinguish the workflows here

All nine runs per workflow passed held-out tests. There is no observed difference on that endpoint. Nine successes on three repeated problems do not prove equal underlying quality, non-inferiority, or a 100% future success rate.

### 3. Repository maintenance changed the apparent winner

The gate used here is `scripts/state-numbers.py --check`: it checks documented repository counts. It is not the full test suite or a comprehensive merge-readiness gate. All nine Spine summaries record three inconsistent claims. Each of spec-kit's five gate passes coincided with a change to `docs/specs/STATE-OF-SPINE.md`.

### 4. A tracked-file edit is not automatically harmful

The harness fit score passed **1/9 spec-kit runs and 9/9 Spine runs**. Its rule penalizes modifications to any existing tracked file, including count maintenance and package exports. Those can be necessary integration edits. Report fit separately from held-out behavior and maintenance checks; do not label all such modifications defects.

### 5. Token volume and money answer different questions

Spec-kit used **{sk_tokens/sp_tokens:.2f}×** as many recorded tokens, but cost **{ratio:.2f}×** as much under the stated rates. **{cache_percent:.1f}% of its input tokens were cache reads.** Total tokens include repeated cached context, not that many unique words or lines of code. Model response counts also are not synonymous with tool-action counts.

### 6. The planning sequence is a substantial part of the treatment

The specification-through-analysis stages cost **${pre_cost:.4f} per run**, or **{pre_cost/sk_cost*100:.1f}%** of spec-kit's total, before the implementation stage. That is **{pre_cost/sp_cost:.2f}×** Spine's mean measured codegen-plus-separate-intake cost. This stage boundary is not an audit of the exact first code-writing action; stage totals describe the configured workflow.

### 7. The capacity interruption is retained, not discarded

One drift-Markdown implementation encountered a provider-capacity error. It resumed on the same model and thread; the failed responses and recovery overhead remain included. Excluding that entire paired observation gives **{clean_ratio:.2f}×** using equal-weight ticket means. The recovery does not account for most of the observed gap. This exclusion is a sensitivity check, not the primary result.

### 8. Elapsed time is descriptive

Mean recorded active wall time was **33.68 minutes for spec-kit** and **2.07 minutes for Spine plus separate intake**. Boundaries differ: spec-kit excludes initialization and independent harness grading, while Spine wraps benchmark execution and checks. Caches were not reset and workflow order was fixed. Recovery idle time is excluded. Do not present their quotient as a controlled end-to-end speedup.

### 9. Three distinct problems cannot establish the broad significance claim

The prespecified sign test averages each problem's three repeats before comparing workflows. All three cost differences favor Spine; **p = 2 × (1/2)³ = {p:.2f}**. That does not pass the conventional 0.05 threshold. It also does not mean there is no cost difference: this conservative test has coarse resolution and ignores its magnitude. The scenarios were selected, not randomly sampled, further limiting population claims.

### 10. What it would cost at fleet scale — arithmetic illustration only

**Per measured attempt:**

{metrics_table}

Spine includes matching ticket/pass intake cost, but the intake output was measured separately and was not fed into codegen. These are costs per completed attempt, not per fully accepted repository change. No cross-model repricing is included.

**Where spec-kit's money goes:** each row is total stage cost divided by all nine runs; optional continuations contribute zero to runs where they did not occur.

| Stage | Mean cost per run | Mean tokens per run | Share of total cost |
|---|---:|---:|---:|
{chr(10).join(stage_rows)}

**Per developer, if four benchmark-equivalent attempts were made per month:**

| Period | spec-kit API equivalent | Spine API equivalent |
|---|---:|---:|
| Month: 4 attempts | ${sk_cost*4:.2f} | ${sp_cost*4:.2f} |
| Year: 48 attempts | ${sk_cost*48:.2f} | ${sp_cost*48:.2f} |

**Annual arithmetic at 48 attempts per developer:**

| Developers | Assumed attempts/year | spec-kit API equivalent | Spine API equivalent |
|---|---:|---:|---:|
{fleet}

**How to read these tables:** multiply the unrounded measured means by an assumed volume. These are neither forecasts nor subscription bills. They exclude human review, infrastructure, setup, maintenance, task-mix changes, and acceptance-related rework. The study does not demonstrate enterprise savings or throughput at these scales.

## Where either workflow may be the better fit

In this dataset, Spine used less recorded model work; spec-kit repaired repository-count documentation more often. Greenfield work, long-running changes, compliance workflows, and enterprise integration were not tested. There is no measured basis here to declare a winner for those settings.

## The one idea worth taking anyway

**Make acceptance explicit and retain inspectable evidence.** Keep functional tests, static checks, scope changes, and repository maintenance visible as separate endpoints. A single pass/fail label would hide the opposing fit and maintenance-gate results in this study.

## What we are not claiming

- That the graph alone caused the cost difference; no graph-on/graph-off comparison was run here.
- That either workflow produces better code in general, or that matching test counts prove equivalence.
- That the reference's historical multi-model, grounding, precision, or design-A/B results were reproduced.
- That three scenarios establish a universal multiplier or statistically validated fleet savings.
- That the repository-count gate establishes full-suite success or merge readiness.

## Questions that come back

### Q1. “Are these numbers statistically significant?”

**Not under the prespecified test across distinct problems at the 0.05 threshold.** The cost comparison gives **p = {p:.2f}**. The maintenance-gate difference also points the same way across all three problems, favoring spec-kit, and its exploratory ticket-level sign test gives **p = {gp:.2f}**. Held-out results are tied. Large observed cost differences and weak breadth of inference can coexist.

### Q2. “Why did the reference report show much smaller p-values?”

It reports different runs and models. Its per-run tests treat run observations as independent, and its pooled sign test treats ticket–model pairs as independent. Repeated runs of one task, and the same task across multiple models, can share task-specific effects. Those small p-values cannot simply be transferred to this one-model, three-problem study. For generalization to new problems, three tickets remain three distinct problems.

### Q3. “Should we repeat these three problems more times?”

More repeats refine estimates of variability on these particular problems. They do not increase problem diversity. Prefer a broader, prospectively chosen set of **20–30 distinct scenarios across several repositories** as a practical planning range, with repeats used to characterize variability. This is not a power calculation or guarantee of significance. Choose meaningful cost and quality margins, then plan sample size against those targets.

### Q4. “Would tighter requirements or giving spec-kit the graph close the gap?”

Unknown. Neither intervention was randomized or tested here. Stage costs identify where resources went, but do not establish how much an intervention would save. A graph-on/graph-off ablation is needed to isolate that claim; a controlled requirements comparison is needed for the other.

### Q5. “Can the report be reproduced without another model run?”

Yes. The archive contains individual measurements, a sanitized per-response token ledger, source snapshots, and analysis scripts. Run the command in [RESULTS_QUICKSTART.md](RESULTS_QUICKSTART.md). This reconstructs both this report and the detailed measurement report without credentials or network access.

## What this research has not measured yet

Larger multi-file edits, bug fixes, API migrations, refactoring, multiple repositories and languages, human review time, downstream defect rates, common end-to-end acceptance, or a controlled graph ablation. The three current tasks all create small modules. Timing boundaries, fixed order, and agent-tool differences also limit causal interpretation.

## Revisit condition

Revisit the broad workflow recommendation after a preregistered, paired study on a more varied task set. Randomize workflow order, use common time and acceptance boundaries, retain all failures and retry costs, and evaluate both practical effect sizes and uncertainty. For quality equivalence, specify an equivalence or non-inferiority margin in advance; failure to find a difference is not enough.

## Appendix A: how the comparison was run

| Item | Configuration |
|---|---|
| Model / reasoning | `{model}` / high |
| Authentication | Codex subscription; no API key |
| Codex CLI | {protocol['codex_cli']} |
| spec-kit | {protocol['speckit_ref']} |
| Spine | {protocol['spine_ref']} |
| Target commit | `{protocol['target_commit']}` |
| Held-out suite | `{protocol['held_out_suite']}` |
| Design | 3 scenarios × 3 repeats × 2 workflows; 18 runs |
| Sequence | Fixed serial: spec-kit scenarios, Spine codegen, separate intake; repeat |
| Checklist policy | Explicit approval to proceed despite unchecked reviewer checklist items |
| Isolation | Fresh worktrees; nine distinct final planning directories |
| Deviation | One same-model/thread recovery after provider capacity error |

Temperature and requested output limits are not enforced identically to the original API experiment. The adapter uses validated JSON envelopes for Spine calls. Pilots, diagnostics, and this coordinating chat are excluded from benchmark accounting. The original executable snapshot and its hashes remain unchanged; the recovery is documented separately.

## Appendix B: paired scenario measurements

| Scenario | Repeats per workflow | spec-kit mean cost | Spine mean cost | Ratio |
|---|---:|---:|---:|---:|
{chr(10).join(paired_table)}

The overall cost ratio is the ratio of the equally weighted ticket means, not the arithmetic mean of these three ratios.

## Appendix C: outcomes and individual runs

{outcome_table}

{section('Individual outcomes')}

## Appendix D: workflow accounting

{section('Spec-kit stage costs')}

The optional-stage means above use observed stage executions as denominators. The grouped table in finding 10 instead divides by all nine runs; this explains why optional-stage means cannot be added directly to estimate average run cost. Spine's observed four responses comprise two codegen and two separate intake responses per ticket; this is not a measurement of every stage of a production deployment.

## Appendix E: tokens, provenance, and reproducibility

{section('Recorded tokens and cost')}

[Protocol](PROTOCOL.json) · [Statistical calculations](STATISTICAL_ANALYSIS.json) · [Detailed measurements](MEASUREMENT_REPORT.md) · [Portable response ledger](response-ledger.json) · [Recovery record](CAPACITY_RECOVERY.json).

The supplied historical report was used for organization and presentation, not as additional experimental observations. The results package excludes raw model conversations and credentials. Original local evidence retains the full sessions.

## Appendix F: how the statistics were calculated

### 1. What is the independent unit?

For the primary analysis, first average the three repeats within each ticket and workflow. Compare the three paired ticket means. This preserves pairing and avoids counting repeat runs as new problems. Independence across tickets and a relevant sampling population remain assumptions; one repository and a selected task set do not establish broad representativeness.

### 2. Is cost direction consistent? Exact paired sign test

**Question:** do ticket-level cost differences systematically favor one workflow? Under the null, each nonzero ticket difference is equally likely to have either sign, independently. All three favor Spine. The two-sided probability of three signs agreeing is **2/2³ = {p:.2f}**. This is the smallest possible two-sided sign-test p-value with three non-tied tickets, regardless of how large the ratios are. The null concerns direction of paired differences, not an exact cost ratio of 1. [Method: NIST sign test](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/signtest.htm).

A p-value is a tail probability under a specified null model and its assumptions. It is not the probability that the result is false, that the null is true, or that chance caused the observations. A large p-value does not establish equality. [Interpretation: American Statistical Association](https://www.amstat.org/docs/default-source/amstat-documents/p-valuestatement.pdf).

### 3. How large is the measured effect? Exploratory whole-ticket bootstrap

Resample the three paired ticket means together with replacement. Enumerate all **27 ordered samples** of size three; calculate the ratio of mean spec-kit cost to mean Spine cost for each. The linearly interpolated 2.5th and 97.5th percentiles are **{lo:.2f}–{hi:.2f}×**, around the observed **{ratio:.2f}×**.

With only three ticket clusters, this nominal 95% percentile interval is unstable and cannot reliably describe population uncertainty. It can only resample the observed favorable tickets, so it cannot represent different outcomes on unseen task types. Its exclusion of 1 does **not** override the primary test or justify an “at least {lo:.0f}× everywhere” claim. The bootstrap and sign test also target different summaries and use different assumptions.

### 4. Why not use the reference's per-run test as the headline?

Ignoring clustering, complete separation of nine costs per arm yields a two-sided rank-test tail probability of **2 / C(18,9) = {naive_mw:.8f}** under independent-sample assumptions. Counting the nine repeat pairs as independent signs yields **2/2⁹ = {2/2**9:.8f}**. These are illustrative calculations, not valid primary evidence about new problems in this clustered design. Mann–Whitney explicitly assumes independent samples. [SciPy method documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html).

### 5. Do the quality endpoints show a significant difference?

Held-out success is **9/9 versus 9/9**, leaving no observed discordance to distinguish the workflows. There is no evidence of superiority or equivalence from that tie. The repository-count gate favors spec-kit in the mean of each of the three tickets; the exploratory two-sided ticket sign test is **p = {gp:.2f}**. Report the observed **5/9 versus 0/9** difference, while keeping this endpoint's narrow definition visible. An unpaired test on 18 rows would discard both pairing and task clustering.

### 6. How much more evidence is needed?

Six independent, non-tied tickets all favoring one workflow would produce **2/2⁶ = 0.03125** in a two-sided sign test. That is only a mathematical minimum for that unanimous outcome, not an adequate sample-size or power recommendation. Do not keep adding convenient tasks until p drops below 0.05. Prespecify breadth, task selection, effect thresholds, stopping rules, and failure handling, then choose enough distinct problems to address those goals.

**What is established:** a large, consistently directed observed cost gap on the three tested scenarios, with matching held-out pass counts and different maintenance-gate outcomes. **What remains unestablished:** a general statistically significant advantage across software problems, quality equivalence, graph-specific causation, and enterprise savings.
'''
    inventory = [('spec-kit',model,sk),('Spine + PKG',model,sp),('Spine intake (separate)',model,intake_rows)]
    section = '\n'.join(model_section(protocol, inventory, summarize_usage(root)))
    body = body.replace('## Spine + PKG, measured', section + '\n## Spine + PKG, measured', 1)
    (root/'COMPARISON_REPORT.md').write_text(body)
    print(root/'COMPARISON_REPORT.md')

if __name__=='__main__':
    main()
