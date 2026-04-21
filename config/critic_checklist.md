# Self-Critic Checklist

After generating results, the agent performs a self-critic pass using this checklist.
Every item must be answered YES or explained.  If any item is NO without
justification the run is marked **failed** and the finding is not published.

## Statistical Rigour
- [ ] Is the sample size stated and ≥ 30?
- [ ] Is the statistical test appropriate for the data distribution?
- [ ] Is the p-value reported and below the stated significance threshold?
- [ ] Are confidence intervals provided where applicable?
- [ ] Are multiple-comparison corrections applied if more than one test was run?

## Reproducibility
- [ ] Does `reproduce.sh` regenerate the same results from the raw data?
- [ ] Are all random seeds recorded?
- [ ] Are software versions pinned in the reproduce script?

## Data Integrity
- [ ] Is the dataset source URL or accession ID cited?
- [ ] Were any rows dropped?  If so, is the reason documented?
- [ ] Are units and scales stated for every numeric column used?

## Claim Quality
- [ ] Does the finding state a single, testable claim?
- [ ] Is the effect size reported alongside the p-value?
- [ ] Does the post.md distinguish correlation from causation?
- [ ] Are limitations listed?

## Artifact Completeness
- [ ] post.md exists and is non-empty?
- [ ] plot.png exists and renders correctly?
- [ ] raw_results.csv contains the data behind the claim?
- [ ] run_log.txt captures full stdout/stderr?
- [ ] reproduce.sh is executable and self-contained?
