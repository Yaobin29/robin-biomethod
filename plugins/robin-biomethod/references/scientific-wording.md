# Scientific report wording

Apply humanizer-write in its scientific-writing mode before preparing the final report.
This portable, task-specific integration follows the humanizer-write scientific reference;
it does not require readers to install a global skill or a machine-specific registry.
Upstream pattern reference: https://github.com/blader/humanizer .

## Editing scope

Edit headings, table labels, explanatory sentences and presentation captions. Give each
heading a concrete scientific subject. Prefer conventional noun phrases to vague prompts.
Chinese and English editions should name the same subject, using sentence case in English.

| Avoid as a report label | Prefer |
| --- | --- |
| 尚未确定什么 / What remains unresolved | 待确认的参数与实验条件 / Parameters and conditions to confirm |
| 验证什么 / What it tests | 验证目的 / Validation objective |
| 检测什么 / What to measure | 检测指标 / Measurements |
| 完成后能明确什么 / What it can resolve | 拟解决的问题 / Uncertainties addressed |
| 候选方法如何形成 | 方法生成与修订记录 |
| 为什么相关 / Why relevant | 与本任务的相关性 / Relevance to this task |

Choose more specific labels when the contents warrant them, such as reagent amounts,
reaction conditions, purification settings or assay acceptance criteria. Do not relabel
all scientific uncertainties as missing parameters: some concern measurement specificity,
causal interpretation or transfer between systems. The combined heading covers both
parameters and experimental conditions without deleting those uncertainties.

## Scientific prose

- Start with the material, operation, measurement or evidence that the sentence describes.
- Remove repeated introductions, decorative subtitles and claims about the report's value.
- Replace vague or inflated phrases with the concrete observation or required action.
- Keep necessary contrasts that correct a real scientific confusion. Avoid stock rhetorical
  "not X, but Y" phrasing when a direct statement carries the same information.
- Do not add opinions, humor, authorial personality, first-person claims or novelty language.
- Distinguish reported results, proposed experiments and interpretations. Preserve the
  difference between incomplete evidence, a failed check and an unperformed experiment.
- Keep the title informative; do not promise validation, optimization or reproducibility
  when those outcomes have not been demonstrated.

## Preservation check

Never edit original scientific JSON, frozen task conditions, numerical values, units,
formulas, route identity, exact quotations, DOI/title text or execution receipts for style.
Retain scope, prerequisites, uncertainty and claim strength. Edit translation text only
when its meaning stays equivalent, then rerun source-hash, number and language checks.
Presentation captions remain separate from source data. Original stage records stay intact.

Do not run another model or restart the scientific workflow merely to polish wording.
The host performs the editorial pass; the renderer uses the stable labels above. Before
delivery, inspect the actual headings, table headers and disclosure summaries in both
languages for remaining vague questions or unnecessary instruction-like phrasing.
