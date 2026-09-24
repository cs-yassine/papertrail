# Phase 0.5 — Contradiction spike

> Go/no-go experiment for whether claim-level extraction + top-5 cosine candidate generation surfaces real contradictions. Throwaway code lives in `spike/` (gitignored); this file and its conclusion are the only committed output. The project owner draws the go/no-go conclusion by hand-labelling pairs below — this file does not.

## Paper list

| ArXiv ID | Resolved title | Topic | Required pair? | Abstract-only? |
|---|---|---|---|---|
| [2206.07682v2](https://arxiv.org/abs/2206.07682v2) | Emergent Abilities of Large Language Models | emergent_abilities | yes (emergence) | False |
| [2304.15004v2](https://arxiv.org/abs/2304.15004v2) | Are Emergent Abilities of Large Language Models a Mirage? | emergent_abilities | yes (emergence) | False |
| [2206.04615v3](https://arxiv.org/abs/2206.04615v3) | Beyond the Imitation Game: Quantifying and extrapolating the capabilities of language models | emergent_abilities | no (distractor) | False |
| [2203.15556v1](https://arxiv.org/abs/2203.15556v1) | Training Compute-Optimal Large Language Models | emergent_abilities | no (distractor) | False |
| [2001.08361v1](https://arxiv.org/abs/2001.08361v1) | Scaling Laws for Neural Language Models | emergent_abilities | no (distractor) | True |
| [2201.11903v6](https://arxiv.org/abs/2201.11903v6) | Chain-of-Thought Prompting Elicits Reasoning in Large Language Models | cot_faithfulness | yes (faithfulness) | False |
| [2305.04388v2](https://arxiv.org/abs/2305.04388v2) | Language Models Don't Always Say What They Think: Unfaithful Explanations in Chain-of-Thought Prompting | cot_faithfulness | yes (faithfulness) | False |
| [2307.13702v1](https://arxiv.org/abs/2307.13702v1) | Measuring Faithfulness in Chain-of-Thought Reasoning | cot_faithfulness | no (distractor) | False |
| [2205.11916v4](https://arxiv.org/abs/2205.11916v4) | Large Language Models are Zero-Shot Reasoners | cot_faithfulness | no (distractor) | False |
| [2203.11171v4](https://arxiv.org/abs/2203.11171v4) | Self-Consistency Improves Chain of Thought Reasoning in Language Models | cot_faithfulness | no (distractor) | False |

## Extraction prompt (verbatim — this is P2's starting point)

System message (spec §5.3, literal single-brace form for direct API use):

```
You extract atomic, self-contained claims from AI research papers.
A claim is a single assertion that stands alone without the surrounding text.
Rules:
- Each claim must be understandable without reading the paper
- Resolve pronouns and acronyms to their referents
- Include quantities and benchmark names when stated
- kind ∈ {finding, method, limitation, definition}
- Extract 3-10 claims. If the text contains none, return an empty list.
- Never invent claims not present in the text.

Respond with a JSON object of exactly this shape: {"claims": [{"text": "...", "kind": "finding|method|limitation|definition"}]}
```

Human message template: `Paper: {title}\n\nSection ({section}):\n{content}` — `section` was `"abstract and conclusion"` where a conclusion was fetched, else `"abstract only"`.

**Deviation from spec §5.3 for the spike, deliberately:** one extraction call per paper (abstract + conclusion concatenated as a single `content`), not one call per section. This is a budget/simplicity choice for the spike only — it is not a proposal for P2's per-section batching design.

## HEADLINE RESULT

For each known-contradicting pair: does a claim from paper A appear in paper B's *own* top-5 neighbours, and vice versa? Each claim's top-5 was computed against **all 71 claims from all 10 papers**, not just the pair partner — so the two directions are not guaranteed symmetric.

### `emergence`: Emergent Abilities of Large Language Models ↔ Are Emergent Abilities of Large Language Models a Mirage?

- **A→B**: `2206.07682v2::3` finds `2304.15004v2::0` in its own top-5, at **rank 1**, score **0.873**.
- **B→A**: `2304.15004v2::0` finds `2206.07682v2::3` in its own top-5, at **rank 1**, score **0.873**.

### `faithfulness`: Chain-of-Thought Prompting Elicits Reasoning in Large Language Models ↔ Language Models Don't Always Say What They Think: Unfaithful Explanations in Chain-of-Thought Prompting

- **A→B**: **no claim from paper A has any paper-B claim in its top-5.**
- **B→A**: `2305.04388v2::3` finds `2201.11903v6::2` in its own top-5, at **rank 1**, score **0.793**.

## Similarity score distribution

Across all 355 cross-paper top-5 entries (71 claims × up to 5 neighbours each, other-paper only):

| min | median | mean | p90 | max |
|---|---|---|---|---|
| 0.569 | 0.749 | 0.741 | 0.814 | 0.873 |

For reference, `LINK_MIN_SIM_CEILING` (the lowest cosine at which a real contradiction appeared) should be set once the pairs below are hand-labelled — **not** from this distribution alone, since this is the distribution of *all* top-5 entries, most of which are same-topic-but-not-contradicting.

## Token usage (real data for the P1 audit)

Totals across all 10 extraction calls: **7070 input, 4677 output (1989 of that reasoning), 11747 total tokens.** Well under the spike's ~80K budget. **Zero empty completions** — gpt-oss-120b at `reasoning_effort=low`, `max_completion_tokens=2000` returned usable content on every one of these 10 calls.

| ArXiv ID | prompt | completion | reasoning | finish_reason | claims |
|---|---|---|---|---|---|
| 2206.07682v2 | 512 | 358 | 172 | stop | 7 |
| 2304.15004v2 | 692 | 526 | 251 | stop | 8 |
| 2206.04615v3 | 679 | 438 | 222 | stop | 7 |
| 2203.15556v1 | 1103 | 376 | 9 | stop | 8 |
| 2001.08361v1 | 389 | 382 | 184 | stop | 7 |
| 2201.11903v6 | 507 | 468 | 223 | stop | 6 |
| 2305.04388v2 | 692 | 488 | 229 | stop | 5 |
| 2307.13702v1 | 736 | 491 | 255 | stop | 7 |
| 2205.11916v4 | 766 | 552 | 235 | stop | 6 |
| 2203.11171v4 | 994 | 598 | 209 | stop | 10 |

**Caveat this is not yet a P1-quality audit:** 10 calls, one model (`gpt-oss-120b`), one `reasoning_effort` (`low`), one prompt version, single abstract+conclusion sections (not the full per-section batching P2 will use). Real per-call sizes here are noticeably smaller than the spec's ~3-5K/call estimate — worth re-checking against real full-paper sections in the P1 audit rather than assuming this generalizes.

## All claims and their top-5 cross-paper neighbours

Organized by paper. Every claim's full top-5 is listed here so ~20 anchors can be hand-picked and labelled CONTRADICTS / SUPPORTS / NEITHER from a complete view, not a pre-filtered subset. Entries crossing into a **known-contradicting partner paper** are marked ⚠.

### Emergent Abilities of Large Language Models (`2206.07682v2`)

**`2206.07682v2::0`** [finding]: Scaling up language models predictably improves performance and sample efficiency on a wide range of downstream tasks.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2001.08361v1::5`: Larger language models are significantly more sample‑efficient than smaller ones. | 0.867 | Scaling Laws for Neural Language Models |
|  | `2201.11903v6::0`: Generating a chain of thought—a series of intermediate reasoning steps—significantly impro | 0.829 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2205.11916v4::5`: The strong performance of a single prompt across diverse tasks suggests that large languag | 0.805 | Large Language Models are Zero-Shot Reas |
|  | `2001.08361v1::0`: The cross-entropy loss of language models scales as a power-law with model size, dataset s | 0.793 | Scaling Laws for Neural Language Models |
|  | `2201.11903v6::3`: Prompting a 540 billion‑parameter language model with eight chain-of-thought exemplars ach | 0.789 | Chain-of-Thought Prompting Elicits Reaso |

**`2206.07682v2::1`** [definition]: An emergent ability is defined as a capability that is absent in smaller models but present in larger models.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
| ⚠ | `2304.15004v2::1`: The authors propose that apparent emergent abilities arise from the researcher’s choice of | 0.800 | Are Emergent Abilities of Large Language |
| ⚠ | `2304.15004v2::7`: Lack of public release of models and their outputs can hinder independent scientific inves | 0.782 | Are Emergent Abilities of Large Language |
| ⚠ | `2304.15004v2::6`: Emergent ability claims may be confounded by a failure to control for multiple comparisons | 0.766 | Are Emergent Abilities of Large Language |
| ⚠ | `2304.15004v2::0`: Recent work claims that large language models display emergent abilities that appear sharp | 0.748 | Are Emergent Abilities of Large Language |
| ⚠ | `2304.15004v2::4`: Two predictions about metric choices were made, tested, and confirmed in a meta‑analysis o | 0.722 | Are Emergent Abilities of Large Language |

**`2206.07682v2::2`** [finding]: Emergent abilities cannot be predicted simply by extrapolating the performance of smaller models.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
| ⚠ | `2304.15004v2::7`: Lack of public release of models and their outputs can hinder independent scientific inves | 0.828 | Are Emergent Abilities of Large Language |
| ⚠ | `2304.15004v2::6`: Emergent ability claims may be confounded by a failure to control for multiple comparisons | 0.810 | Are Emergent Abilities of Large Language |
| ⚠ | `2304.15004v2::1`: The authors propose that apparent emergent abilities arise from the researcher’s choice of | 0.782 | Are Emergent Abilities of Large Language |
| ⚠ | `2304.15004v2::0`: Recent work claims that large language models display emergent abilities that appear sharp | 0.762 | Are Emergent Abilities of Large Language |
| ⚠ | `2304.15004v2::4`: Two predictions about metric choices were made, tested, and confirmed in a meta‑analysis o | 0.738 | Are Emergent Abilities of Large Language |

**`2206.07682v2::3`** [finding]: The existence of emergent abilities implies that additional scaling could further expand the range of capabilities of language models.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
| ⚠ | `2304.15004v2::0`: Recent work claims that large language models display emergent abilities that appear sharp | 0.873 | Are Emergent Abilities of Large Language |
|  | `2201.11903v6::0`: Generating a chain of thought—a series of intermediate reasoning steps—significantly impro | 0.816 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2205.11916v4::5`: The strong performance of a single prompt across diverse tasks suggests that large languag | 0.811 | Large Language Models are Zero-Shot Reas |
| ⚠ | `2304.15004v2::1`: The authors propose that apparent emergent abilities arise from the researcher’s choice of | 0.797 | Are Emergent Abilities of Large Language |
|  | `2001.08361v1::5`: Larger language models are significantly more sample‑efficient than smaller ones. | 0.795 | Scaling Laws for Neural Language Models |

**`2206.07682v2::4`** [finding]: Meaningful performance of emergent abilities has only been observed at a certain computational scale so far.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
| ⚠ | `2304.15004v2::1`: The authors propose that apparent emergent abilities arise from the researcher’s choice of | 0.801 | Are Emergent Abilities of Large Language |
| ⚠ | `2304.15004v2::6`: Emergent ability claims may be confounded by a failure to control for multiple comparisons | 0.771 | Are Emergent Abilities of Large Language |
| ⚠ | `2304.15004v2::7`: Lack of public release of models and their outputs can hinder independent scientific inves | 0.771 | Are Emergent Abilities of Large Language |
| ⚠ | `2304.15004v2::0`: Recent work claims that large language models display emergent abilities that appear sharp | 0.771 | Are Emergent Abilities of Large Language |
| ⚠ | `2304.15004v2::3`: Three predictions about metric effects were made, tested, and confirmed on the InstructGPT | 0.754 | Are Emergent Abilities of Large Language |

**`2206.07682v2::5`** [finding]: Emergent abilities can span a variety of language model architectures, task types, and experimental scenarios.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
| ⚠ | `2304.15004v2::0`: Recent work claims that large language models display emergent abilities that appear sharp | 0.863 | Are Emergent Abilities of Large Language |
|  | `2205.11916v4::5`: The strong performance of a single prompt across diverse tasks suggests that large languag | 0.810 | Large Language Models are Zero-Shot Reas |
| ⚠ | `2304.15004v2::1`: The authors propose that apparent emergent abilities arise from the researcher’s choice of | 0.785 | Are Emergent Abilities of Large Language |
|  | `2201.11903v6::1`: Chain-of-thought prompting, which provides a few chain-of-thought demonstrations as exempl | 0.778 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.774 | Chain-of-Thought Prompting Elicits Reaso |

**`2206.07682v2::6`** [finding]: Emergent abilities are unpredictable in several ways and include emergent risks.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
| ⚠ | `2304.15004v2::6`: Emergent ability claims may be confounded by a failure to control for multiple comparisons | 0.732 | Are Emergent Abilities of Large Language |
|  | `2206.04615v3::3`: Tasks that exhibit breakthrough behavior at a critical scale often involve multiple steps  | 0.729 | Beyond the Imitation Game: Quantifying a |
| ⚠ | `2304.15004v2::1`: The authors propose that apparent emergent abilities arise from the researcher’s choice of | 0.729 | Are Emergent Abilities of Large Language |
| ⚠ | `2304.15004v2::0`: Recent work claims that large language models display emergent abilities that appear sharp | 0.728 | Are Emergent Abilities of Large Language |
| ⚠ | `2304.15004v2::2`: Nonlinear or discontinuous evaluation metrics produce apparent emergent abilities, while l | 0.715 | Are Emergent Abilities of Large Language |

### Are Emergent Abilities of Large Language Models a Mirage? (`2304.15004v2`)

**`2304.15004v2::0`** [finding]: Recent work claims that large language models display emergent abilities that appear sharply and unpredictably at certain model scales

| Label | Neighbour | Score | Paper |
|---|---|---|---|
| ⚠ | `2206.07682v2::3`: The existence of emergent abilities implies that additional scaling could further expand t | 0.873 | Emergent Abilities of Large Language Mod |
| ⚠ | `2206.07682v2::5`: Emergent abilities can span a variety of language model architectures, task types, and exp | 0.863 | Emergent Abilities of Large Language Mod |
|  | `2205.11916v4::5`: The strong performance of a single prompt across diverse tasks suggests that large languag | 0.843 | Large Language Models are Zero-Shot Reas |
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.794 | Chain-of-Thought Prompting Elicits Reaso |
| ⚠ | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.784 | Emergent Abilities of Large Language Mod |

**`2304.15004v2::1`** [definition]: The authors propose that apparent emergent abilities arise from the researcher’s choice of metric rather than fundamental changes in model behavior with scale

| Label | Neighbour | Score | Paper |
|---|---|---|---|
| ⚠ | `2206.07682v2::4`: Meaningful performance of emergent abilities has only been observed at a certain computati | 0.801 | Emergent Abilities of Large Language Mod |
| ⚠ | `2206.07682v2::1`: An emergent ability is defined as a capability that is absent in smaller models but presen | 0.800 | Emergent Abilities of Large Language Mod |
| ⚠ | `2206.07682v2::3`: The existence of emergent abilities implies that additional scaling could further expand t | 0.797 | Emergent Abilities of Large Language Mod |
| ⚠ | `2206.07682v2::5`: Emergent abilities can span a variety of language model architectures, task types, and exp | 0.785 | Emergent Abilities of Large Language Mod |
| ⚠ | `2206.07682v2::2`: Emergent abilities cannot be predicted simply by extrapolating the performance of smaller  | 0.782 | Emergent Abilities of Large Language Mod |

**`2304.15004v2::2`** [finding]: Nonlinear or discontinuous evaluation metrics produce apparent emergent abilities, while linear or continuous metrics yield smooth, predictable performance changes

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2206.04615v3::3`: Tasks that exhibit breakthrough behavior at a critical scale often involve multiple steps  | 0.761 | Beyond the Imitation Game: Quantifying a |
|  | `2206.04615v3::2`: Tasks that improve gradually and predictably commonly involve a large knowledge or memoriz | 0.733 | Beyond the Imitation Game: Quantifying a |
| ⚠ | `2206.07682v2::4`: Meaningful performance of emergent abilities has only been observed at a certain computati | 0.732 | Emergent Abilities of Large Language Mod |
|  | `2206.04615v3::1`: Performance is remarkably similar across model classes, though sparsity provides benefits | 0.719 | Beyond the Imitation Game: Quantifying a |
|  | `2206.04615v3::0`: Model performance and calibration both improve with scale, but are poor in absolute terms  | 0.719 | Beyond the Imitation Game: Quantifying a |

**`2304.15004v2::3`** [method]: Three predictions about metric effects were made, tested, and confirmed on the InstructGPT/GPT-3 family for tasks previously reported to have emergent abilities

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.809 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2206.04615v3::2`: Tasks that improve gradually and predictably commonly involve a large knowledge or memoriz | 0.790 | Beyond the Imitation Game: Quantifying a |
|  | `2205.11916v4::5`: The strong performance of a single prompt across diverse tasks suggests that large languag | 0.785 | Large Language Models are Zero-Shot Reas |
|  | `2206.04615v3::3`: Tasks that exhibit breakthrough behavior at a critical scale often involve multiple steps  | 0.770 | Beyond the Imitation Game: Quantifying a |
| ⚠ | `2206.07682v2::4`: Meaningful performance of emergent abilities has only been observed at a certain computati | 0.754 | Emergent Abilities of Large Language Mod |

**`2304.15004v2::4`** [method]: Two predictions about metric choices were made, tested, and confirmed in a meta‑analysis of emergent abilities on BIG‑Bench

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.789 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2206.04615v3::2`: Tasks that improve gradually and predictably commonly involve a large knowledge or memoriz | 0.767 | Beyond the Imitation Game: Quantifying a |
| ⚠ | `2206.07682v2::3`: The existence of emergent abilities implies that additional scaling could further expand t | 0.762 | Emergent Abilities of Large Language Mod |
|  | `2205.11916v4::5`: The strong performance of a single prompt across diverse tasks suggests that large languag | 0.758 | Large Language Models are Zero-Shot Reas |
|  | `2203.11171v4::2`: Self-consistency improves accuracy on the SVAMP arithmetic benchmark by 11.0% compared to  | 0.753 | Self-Consistency Improves Chain of Thoug |

**`2304.15004v2::5`** [method]: By selecting appropriate metrics, the authors were able to induce seemingly emergent abilities in multiple vision tasks across diverse deep networks

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2205.11916v4::5`: The strong performance of a single prompt across diverse tasks suggests that large languag | 0.777 | Large Language Models are Zero-Shot Reas |
| ⚠ | `2206.07682v2::5`: Emergent abilities can span a variety of language model architectures, task types, and exp | 0.766 | Emergent Abilities of Large Language Mod |
|  | `2206.04615v3::2`: Tasks that improve gradually and predictably commonly involve a large knowledge or memoriz | 0.763 | Beyond the Imitation Game: Quantifying a |
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.761 | Chain-of-Thought Prompting Elicits Reaso |
| ⚠ | `2206.07682v2::3`: The existence of emergent abilities implies that additional scaling could further expand t | 0.754 | Emergent Abilities of Large Language Mod |

**`2304.15004v2::6`** [limitation]: Emergent ability claims may be confounded by a failure to control for multiple comparisons, given the ~10^6 task‑metric‑model family triplets in BIG‑Bench

| Label | Neighbour | Score | Paper |
|---|---|---|---|
| ⚠ | `2206.07682v2::2`: Emergent abilities cannot be predicted simply by extrapolating the performance of smaller  | 0.810 | Emergent Abilities of Large Language Mod |
| ⚠ | `2206.07682v2::3`: The existence of emergent abilities implies that additional scaling could further expand t | 0.782 | Emergent Abilities of Large Language Mod |
|  | `2205.11916v4::5`: The strong performance of a single prompt across diverse tasks suggests that large languag | 0.776 | Large Language Models are Zero-Shot Reas |
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.775 | Chain-of-Thought Prompting Elicits Reaso |
| ⚠ | `2206.07682v2::4`: Meaningful performance of emergent abilities has only been observed at a certain computati | 0.771 | Emergent Abilities of Large Language Mod |

**`2304.15004v2::7`** [limitation]: Lack of public release of models and their outputs can hinder independent scientific investigation of emergent abilities

| Label | Neighbour | Score | Paper |
|---|---|---|---|
| ⚠ | `2206.07682v2::2`: Emergent abilities cannot be predicted simply by extrapolating the performance of smaller  | 0.828 | Emergent Abilities of Large Language Mod |
| ⚠ | `2206.07682v2::1`: An emergent ability is defined as a capability that is absent in smaller models but presen | 0.782 | Emergent Abilities of Large Language Mod |
| ⚠ | `2206.07682v2::4`: Meaningful performance of emergent abilities has only been observed at a certain computati | 0.771 | Emergent Abilities of Large Language Mod |
| ⚠ | `2206.07682v2::5`: Emergent abilities can span a variety of language model architectures, task types, and exp | 0.724 | Emergent Abilities of Large Language Mod |
| ⚠ | `2206.07682v2::3`: The existence of emergent abilities implies that additional scaling could further expand t | 0.701 | Emergent Abilities of Large Language Mod |

### Beyond the Imitation Game: Quantifying and extrapolating the capabilities of language models (`2206.04615v3`)

**`2206.04615v3::0`** [finding]: Model performance and calibration both improve with scale, but are poor in absolute terms and when compared with human expert raters

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2304.15004v2::1`: The authors propose that apparent emergent abilities arise from the researcher’s choice of | 0.747 | Are Emergent Abilities of Large Language |
|  | `2307.13702v1::5`: The degree of post‑hoc reasoning often shows inverse scaling, getting worse with increasin | 0.742 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.724 | Emergent Abilities of Large Language Mod |
|  | `2304.15004v2::2`: Nonlinear or discontinuous evaluation metrics produce apparent emergent abilities, while l | 0.719 | Are Emergent Abilities of Large Language |
|  | `2206.07682v2::4`: Meaningful performance of emergent abilities has only been observed at a certain computati | 0.715 | Emergent Abilities of Large Language Mod |

**`2206.04615v3::1`** [finding]: Performance is remarkably similar across model classes, though sparsity provides benefits

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2001.08361v1::2`: Simple equations accurately describe how overfitting depends on model size and dataset siz | 0.774 | Scaling Laws for Neural Language Models |
|  | `2001.08361v1::3`: Simple equations accurately describe how training speed depends on model size. | 0.773 | Scaling Laws for Neural Language Models |
|  | `2001.08361v1::5`: Larger language models are significantly more sample‑efficient than smaller ones. | 0.761 | Scaling Laws for Neural Language Models |
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.752 | Emergent Abilities of Large Language Mod |
|  | `2001.08361v1::6`: Compute‑efficient training is achieved by training very large models on a relatively modes | 0.722 | Scaling Laws for Neural Language Models |

**`2206.04615v3::2`** [finding]: Tasks that improve gradually and predictably commonly involve a large knowledge or memorization component

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.807 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2205.11916v4::5`: The strong performance of a single prompt across diverse tasks suggests that large languag | 0.806 | Large Language Models are Zero-Shot Reas |
|  | `2304.15004v2::3`: Three predictions about metric effects were made, tested, and confirmed on the InstructGPT | 0.790 | Are Emergent Abilities of Large Language |
|  | `2201.11903v6::0`: Generating a chain of thought—a series of intermediate reasoning steps—significantly impro | 0.789 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2304.15004v2::0`: Recent work claims that large language models display emergent abilities that appear sharp | 0.768 | Are Emergent Abilities of Large Language |

**`2206.04615v3::3`** [finding]: Tasks that exhibit breakthrough behavior at a critical scale often involve multiple steps or components, or brittle metrics

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2304.15004v2::3`: Three predictions about metric effects were made, tested, and confirmed on the InstructGPT | 0.770 | Are Emergent Abilities of Large Language |
|  | `2304.15004v2::2`: Nonlinear or discontinuous evaluation metrics produce apparent emergent abilities, while l | 0.761 | Are Emergent Abilities of Large Language |
|  | `2304.15004v2::1`: The authors propose that apparent emergent abilities arise from the researcher’s choice of | 0.745 | Are Emergent Abilities of Large Language |
|  | `2304.15004v2::4`: Two predictions about metric choices were made, tested, and confirmed in a meta‑analysis o | 0.733 | Are Emergent Abilities of Large Language |
|  | `2304.15004v2::6`: Emergent ability claims may be confounded by a failure to control for multiple comparisons | 0.732 | Are Emergent Abilities of Large Language |

**`2206.04615v3::4`** [finding]: Social bias typically increases with scale in settings with ambiguous context, but this can be improved with prompting

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2305.04388v2::3`: Chain-of-thought prompting is systematically unfaithful across three distinct bias types ( | 0.779 | Language Models Don't Always Say What Th |
|  | `2305.04388v2::2`: On a social-bias task, model explanations justify answers that align with stereotypes with | 0.752 | Language Models Don't Always Say What Th |
|  | `2305.04388v2::0`: Chain-of-thought (CoT) explanations can be heavily influenced by biasing features such as  | 0.714 | Language Models Don't Always Say What Th |
|  | `2304.15004v2::1`: The authors propose that apparent emergent abilities arise from the researcher’s choice of | 0.711 | Are Emergent Abilities of Large Language |
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.704 | Chain-of-Thought Prompting Elicits Reaso |

**`2206.04615v3::5`** [method]: The Beyond the Imitation Game benchmark (BIG-bench) currently consists of 204 tasks contributed by 450 authors across 132 institutions

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2304.15004v2::4`: Two predictions about metric choices were made, tested, and confirmed in a meta‑analysis o | 0.657 | Are Emergent Abilities of Large Language |
|  | `2304.15004v2::6`: Emergent ability claims may be confounded by a failure to control for multiple comparisons | 0.657 | Are Emergent Abilities of Large Language |
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.652 | Emergent Abilities of Large Language Mod |
|  | `2304.15004v2::5`: By selecting appropriate metrics, the authors were able to induce seemingly emergent abili | 0.640 | Are Emergent Abilities of Large Language |
|  | `2201.11903v6::3`: Prompting a 540 billion‑parameter language model with eight chain-of-thought exemplars ach | 0.628 | Chain-of-Thought Prompting Elicits Reaso |

**`2206.04615v3::6`** [method]: OpenAI GPT models, Google-internal dense transformer architectures, and Switch-style sparse transformers were evaluated on BIG-bench across model sizes ranging from millions to hundreds of billions of parameters

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2201.11903v6::3`: Prompting a 540 billion‑parameter language model with eight chain-of-thought exemplars ach | 0.753 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2304.15004v2::5`: By selecting appropriate metrics, the authors were able to induce seemingly emergent abili | 0.734 | Are Emergent Abilities of Large Language |
|  | `2001.08361v1::0`: The cross-entropy loss of language models scales as a power-law with model size, dataset s | 0.712 | Scaling Laws for Neural Language Models |
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.710 | Emergent Abilities of Large Language Mod |
|  | `2205.11916v4::0`: Adding the phrase "Let's think step by step" before each answer enables large language mod | 0.709 | Large Language Models are Zero-Shot Reas |

### Training Compute-Optimal Large Language Models (`2203.15556v1`)

**`2203.15556v1::0`** [finding]: Current large language models are significantly undertrained because model size has been increased without proportionally increasing the number of training tokens.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2001.08361v1::5`: Larger language models are significantly more sample‑efficient than smaller ones. | 0.778 | Scaling Laws for Neural Language Models |
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.747 | Emergent Abilities of Large Language Mod |
|  | `2304.15004v2::0`: Recent work claims that large language models display emergent abilities that appear sharp | 0.727 | Are Emergent Abilities of Large Language |
|  | `2206.07682v2::3`: The existence of emergent abilities implies that additional scaling could further expand t | 0.718 | Emergent Abilities of Large Language Mod |
|  | `2001.08361v1::0`: The cross-entropy loss of language models scales as a power-law with model size, dataset s | 0.717 | Scaling Laws for Neural Language Models |

**`2203.15556v1::1`** [method]: For compute-optimal training, model size and number of training tokens should be scaled equally: each doubling of model size requires a doubling of training tokens.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2001.08361v1::6`: Compute‑efficient training is achieved by training very large models on a relatively modes | 0.760 | Scaling Laws for Neural Language Models |
|  | `2001.08361v1::3`: Simple equations accurately describe how training speed depends on model size. | 0.757 | Scaling Laws for Neural Language Models |
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.746 | Emergent Abilities of Large Language Mod |
|  | `2001.08361v1::0`: The cross-entropy loss of language models scales as a power-law with model size, dataset s | 0.717 | Scaling Laws for Neural Language Models |
|  | `2001.08361v1::4`: These scaling relationships enable the determination of the optimal allocation of a fixed  | 0.714 | Scaling Laws for Neural Language Models |

**`2203.15556v1::2`** [finding]: The compute-optimal model Chinchilla, with 70 B parameters and four times more data than Gopher, uniformly and significantly outperforms Gopher (280 B), GPT‑3 (175 B), Jurassic‑1 (178 B), and Megatron‑Turing NLG (530 B) on a wide range of downstream tasks.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.712 | Emergent Abilities of Large Language Mod |
|  | `2001.08361v1::5`: Larger language models are significantly more sample‑efficient than smaller ones. | 0.712 | Scaling Laws for Neural Language Models |
|  | `2201.11903v6::3`: Prompting a 540 billion‑parameter language model with eight chain-of-thought exemplars ach | 0.710 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2206.04615v3::6`: OpenAI GPT models, Google-internal dense transformer architectures, and Switch-style spars | 0.707 | Beyond the Imitation Game: Quantifying a |
|  | `2205.11916v4::2`: Zero-shot-CoT significantly outperforms standard zero-shot performance on a range of reaso | 0.677 | Large Language Models are Zero-Shot Reas |

**`2203.15556v1::3`** [finding]: Chinchilla achieves a state‑of‑the‑art average accuracy of 67.5 % on the MMLU benchmark, a 7 % improvement over Gopher.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.590 | Emergent Abilities of Large Language Mod |
|  | `2203.11171v4::1`: Self-consistency improves accuracy on the GSM8K arithmetic benchmark by 17.9% compared to  | 0.589 | Self-Consistency Improves Chain of Thoug |
|  | `2203.11171v4::2`: Self-consistency improves accuracy on the SVAMP arithmetic benchmark by 11.0% compared to  | 0.585 | Self-Consistency Improves Chain of Thoug |
|  | `2201.11903v6::3`: Prompting a 540 billion‑parameter language model with eight chain-of-thought exemplars ach | 0.580 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2206.04615v3::1`: Performance is remarkably similar across model classes, though sparsity provides benefits | 0.579 | Beyond the Imitation Game: Quantifying a |

**`2203.15556v1::4`** [limitation]: The analysis assumes the efficient computational frontier follows a power‑law relationship between compute budget, model size, and number of training tokens, but observes concavity at high compute budgets, suggesting possible overestimation of optimal model size.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2001.08361v1::2`: Simple equations accurately describe how overfitting depends on model size and dataset siz | 0.771 | Scaling Laws for Neural Language Models |
|  | `2001.08361v1::4`: These scaling relationships enable the determination of the optimal allocation of a fixed  | 0.760 | Scaling Laws for Neural Language Models |
|  | `2001.08361v1::3`: Simple equations accurately describe how training speed depends on model size. | 0.749 | Scaling Laws for Neural Language Models |
|  | `2001.08361v1::6`: Compute‑efficient training is achieved by training very large models on a relatively modes | 0.743 | Scaling Laws for Neural Language Models |
|  | `2203.11171v4::8`: A limitation of self-consistency is increased computational cost, though using a small num | 0.742 | Self-Consistency Improves Chain of Thoug |

**`2203.15556v1::5`** [limitation]: Only two comparable large‑scale training runs (Chinchilla and Gopher) are available, limiting validation of the scaling predictions at intermediate scales.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2206.07682v2::2`: Emergent abilities cannot be predicted simply by extrapolating the performance of smaller  | 0.630 | Emergent Abilities of Large Language Mod |
|  | `2206.07682v2::4`: Meaningful performance of emergent abilities has only been observed at a certain computati | 0.617 | Emergent Abilities of Large Language Mod |
|  | `2001.08361v1::6`: Compute‑efficient training is achieved by training very large models on a relatively modes | 0.612 | Scaling Laws for Neural Language Models |
|  | `2206.07682v2::3`: The existence of emergent abilities implies that additional scaling could further expand t | 0.573 | Emergent Abilities of Large Language Mod |
|  | `2304.15004v2::7`: Lack of public release of models and their outputs can hinder independent scientific inves | 0.569 | Are Emergent Abilities of Large Language |

**`2203.15556v1::6`** [limitation]: All training runs in the study were conducted on less than one epoch of data, so results may not generalize to multi‑epoch training regimes.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2206.07682v2::2`: Emergent abilities cannot be predicted simply by extrapolating the performance of smaller  | 0.618 | Emergent Abilities of Large Language Mod |
|  | `2001.08361v1::6`: Compute‑efficient training is achieved by training very large models on a relatively modes | 0.601 | Scaling Laws for Neural Language Models |
|  | `2206.07682v2::4`: Meaningful performance of emergent abilities has only been observed at a certain computati | 0.594 | Emergent Abilities of Large Language Mod |
|  | `2001.08361v1::3`: Simple equations accurately describe how training speed depends on model size. | 0.587 | Scaling Laws for Neural Language Models |
|  | `2307.13702v1::3`: CoT's performance boost does not seem to come from CoT's added test-time compute alone or  | 0.573 | Measuring Faithfulness in Chain-of-Thoug |

**`2203.15556v1::7`** [limitation]: Training on trillions of tokens raises ethical and privacy concerns, including the presence of toxic language, biases, and private information in large web‑scraped datasets.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2001.08361v1::0`: The cross-entropy loss of language models scales as a power-law with model size, dataset s | 0.658 | Scaling Laws for Neural Language Models |
|  | `2203.11171v4::9`: Language models can sometimes generate incorrect or nonsensical reasoning paths, indicatin | 0.650 | Self-Consistency Improves Chain of Thoug |
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.633 | Emergent Abilities of Large Language Mod |
|  | `2001.08361v1::5`: Larger language models are significantly more sample‑efficient than smaller ones. | 0.620 | Scaling Laws for Neural Language Models |
|  | `2307.13702v1::6`: The authors introduce metrics for evaluating CoT faithfulness to facilitate increasing the | 0.609 | Measuring Faithfulness in Chain-of-Thoug |

### Scaling Laws for Neural Language Models (`2001.08361v1`)

**`2001.08361v1::0`** [finding]: The cross-entropy loss of language models scales as a power-law with model size, dataset size, and the amount of compute used for training, with trends spanning more than seven orders of magnitude.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.793 | Emergent Abilities of Large Language Mod |
|  | `2304.15004v2::0`: Recent work claims that large language models display emergent abilities that appear sharp | 0.767 | Are Emergent Abilities of Large Language |
|  | `2206.07682v2::3`: The existence of emergent abilities implies that additional scaling could further expand t | 0.752 | Emergent Abilities of Large Language Mod |
|  | `2203.15556v1::4`: The analysis assumes the efficient computational frontier follows a power‑law relationship | 0.732 | Training Compute-Optimal Large Language  |
|  | `2201.11903v6::4`: Chain‑of‑thought reasoning is an emergent property of model scale that allows sufficiently | 0.728 | Chain-of-Thought Prompting Elicits Reaso |

**`2001.08361v1::1`** [finding]: Within a wide range, architectural details such as network width or depth have minimal effects on loss scaling.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2203.11171v4::8`: A limitation of self-consistency is increased computational cost, though using a small num | 0.624 | Self-Consistency Improves Chain of Thoug |
|  | `2203.15556v1::4`: The analysis assumes the efficient computational frontier follows a power‑law relationship | 0.606 | Training Compute-Optimal Large Language  |
|  | `2206.04615v3::1`: Performance is remarkably similar across model classes, though sparsity provides benefits | 0.605 | Beyond the Imitation Game: Quantifying a |
|  | `2206.07682v2::4`: Meaningful performance of emergent abilities has only been observed at a certain computati | 0.594 | Emergent Abilities of Large Language Mod |
|  | `2203.15556v1::1`: For compute-optimal training, model size and number of training tokens should be scaled eq | 0.590 | Training Compute-Optimal Large Language  |

**`2001.08361v1::2`** [finding]: Simple equations accurately describe how overfitting depends on model size and dataset size.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2206.04615v3::1`: Performance is remarkably similar across model classes, though sparsity provides benefits | 0.774 | Beyond the Imitation Game: Quantifying a |
|  | `2203.15556v1::4`: The analysis assumes the efficient computational frontier follows a power‑law relationship | 0.771 | Training Compute-Optimal Large Language  |
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.704 | Emergent Abilities of Large Language Mod |
|  | `2203.15556v1::1`: For compute-optimal training, model size and number of training tokens should be scaled eq | 0.700 | Training Compute-Optimal Large Language  |
|  | `2206.04615v3::0`: Model performance and calibration both improve with scale, but are poor in absolute terms  | 0.689 | Beyond the Imitation Game: Quantifying a |

**`2001.08361v1::3`** [finding]: Simple equations accurately describe how training speed depends on model size.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2206.04615v3::1`: Performance is remarkably similar across model classes, though sparsity provides benefits | 0.773 | Beyond the Imitation Game: Quantifying a |
|  | `2203.15556v1::1`: For compute-optimal training, model size and number of training tokens should be scaled eq | 0.757 | Training Compute-Optimal Large Language  |
|  | `2203.15556v1::4`: The analysis assumes the efficient computational frontier follows a power‑law relationship | 0.749 | Training Compute-Optimal Large Language  |
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.720 | Emergent Abilities of Large Language Mod |
|  | `2205.11916v4::0`: Adding the phrase "Let's think step by step" before each answer enables large language mod | 0.697 | Large Language Models are Zero-Shot Reas |

**`2001.08361v1::4`** [method]: These scaling relationships enable the determination of the optimal allocation of a fixed compute budget.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2203.15556v1::4`: The analysis assumes the efficient computational frontier follows a power‑law relationship | 0.760 | Training Compute-Optimal Large Language  |
|  | `2203.15556v1::1`: For compute-optimal training, model size and number of training tokens should be scaled eq | 0.714 | Training Compute-Optimal Large Language  |
|  | `2203.11171v4::8`: A limitation of self-consistency is increased computational cost, though using a small num | 0.696 | Self-Consistency Improves Chain of Thoug |
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.643 | Emergent Abilities of Large Language Mod |
|  | `2206.07682v2::3`: The existence of emergent abilities implies that additional scaling could further expand t | 0.642 | Emergent Abilities of Large Language Mod |

**`2001.08361v1::5`** [finding]: Larger language models are significantly more sample‑efficient than smaller ones.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.867 | Emergent Abilities of Large Language Mod |
|  | `2206.07682v2::3`: The existence of emergent abilities implies that additional scaling could further expand t | 0.795 | Emergent Abilities of Large Language Mod |
|  | `2201.11903v6::0`: Generating a chain of thought—a series of intermediate reasoning steps—significantly impro | 0.781 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2203.15556v1::0`: Current large language models are significantly undertrained because model size has been i | 0.778 | Training Compute-Optimal Large Language  |
|  | `2304.15004v2::0`: Recent work claims that large language models display emergent abilities that appear sharp | 0.776 | Are Emergent Abilities of Large Language |

**`2001.08361v1::6`** [method]: Compute‑efficient training is achieved by training very large models on a relatively modest amount of data and stopping training well before convergence.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2203.15556v1::1`: For compute-optimal training, model size and number of training tokens should be scaled eq | 0.760 | Training Compute-Optimal Large Language  |
|  | `2203.15556v1::4`: The analysis assumes the efficient computational frontier follows a power‑law relationship | 0.743 | Training Compute-Optimal Large Language  |
|  | `2206.04615v3::1`: Performance is remarkably similar across model classes, though sparsity provides benefits | 0.722 | Beyond the Imitation Game: Quantifying a |
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.713 | Emergent Abilities of Large Language Mod |
|  | `2203.15556v1::0`: Current large language models are significantly undertrained because model size has been i | 0.703 | Training Compute-Optimal Large Language  |

### Chain-of-Thought Prompting Elicits Reasoning in Large Language Models (`2201.11903v6`)

**`2201.11903v6::0`** [finding]: Generating a chain of thought—a series of intermediate reasoning steps—significantly improves the ability of large language models to perform complex reasoning.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.829 | Emergent Abilities of Large Language Mod |
|  | `2307.13702v1::0`: Large language models (LLMs) perform better when they produce step-by-step, "Chain-of-Thou | 0.826 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2205.11916v4::0`: Adding the phrase "Let's think step by step" before each answer enables large language mod | 0.825 | Large Language Models are Zero-Shot Reas |
|  | `2206.07682v2::3`: The existence of emergent abilities implies that additional scaling could further expand t | 0.816 | Emergent Abilities of Large Language Mod |
|  | `2206.04615v3::2`: Tasks that improve gradually and predictably commonly involve a large knowledge or memoriz | 0.789 | Beyond the Imitation Game: Quantifying a |

**`2201.11903v6::1`** [method]: Chain-of-thought prompting, which provides a few chain-of-thought demonstrations as exemplars in the prompt, enables reasoning abilities to emerge naturally in sufficiently large language models.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2206.07682v2::3`: The existence of emergent abilities implies that additional scaling could further expand t | 0.793 | Emergent Abilities of Large Language Mod |
|  | `2205.11916v4::5`: The strong performance of a single prompt across diverse tasks suggests that large languag | 0.779 | Large Language Models are Zero-Shot Reas |
|  | `2206.07682v2::5`: Emergent abilities can span a variety of language model architectures, task types, and exp | 0.778 | Emergent Abilities of Large Language Mod |
|  | `2205.11916v4::4`: Zero-shot-CoT is a single zero‑shot prompt that elicits chain‑of‑thought reasoning from la | 0.777 | Large Language Models are Zero-Shot Reas |
|  | `2307.13702v1::0`: Large language models (LLMs) perform better when they produce step-by-step, "Chain-of-Thou | 0.768 | Measuring Faithfulness in Chain-of-Thoug |

**`2201.11903v6::2`** [finding]: Experiments on three large language models demonstrate that chain-of-thought prompting improves performance on arithmetic, commonsense, and symbolic reasoning tasks.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2205.11916v4::5`: The strong performance of a single prompt across diverse tasks suggests that large languag | 0.861 | Large Language Models are Zero-Shot Reas |
|  | `2307.13702v1::6`: The authors introduce metrics for evaluating CoT faithfulness to facilitate increasing the | 0.838 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2205.11916v4::4`: Zero-shot-CoT is a single zero‑shot prompt that elicits chain‑of‑thought reasoning from la | 0.823 | Large Language Models are Zero-Shot Reas |
|  | `2203.11171v4::4`: Self-consistency improves accuracy on the StrategyQA commonsense benchmark by 6.4% compare | 0.822 | Self-Consistency Improves Chain of Thoug |
|  | `2203.11171v4::2`: Self-consistency improves accuracy on the SVAMP arithmetic benchmark by 11.0% compared to  | 0.817 | Self-Consistency Improves Chain of Thoug |

**`2201.11903v6::3`** [finding]: Prompting a 540 billion‑parameter language model with eight chain-of-thought exemplars achieves state‑of‑the‑art accuracy on the GSM8K math word‑problem benchmark, surpassing a finetuned GPT‑3 model with a verifier.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.789 | Emergent Abilities of Large Language Mod |
|  | `2203.11171v4::1`: Self-consistency improves accuracy on the GSM8K arithmetic benchmark by 17.9% compared to  | 0.788 | Self-Consistency Improves Chain of Thoug |
|  | `2205.11916v4::0`: Adding the phrase "Let's think step by step" before each answer enables large language mod | 0.784 | Large Language Models are Zero-Shot Reas |
|  | `2206.04615v3::6`: OpenAI GPT models, Google-internal dense transformer architectures, and Switch-style spars | 0.753 | Beyond the Imitation Game: Quantifying a |
|  | `2203.11171v4::6`: Self-consistency yields significant accuracy gains across four large language models of va | 0.752 | Self-Consistency Improves Chain of Thoug |

**`2201.11903v6::4`** [definition]: Chain‑of‑thought reasoning is an emergent property of model scale that allows sufficiently large language models to solve reasoning tasks that otherwise exhibit flat scaling curves.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2307.13702v1::6`: The authors introduce metrics for evaluating CoT faithfulness to facilitate increasing the | 0.819 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2205.11916v4::4`: Zero-shot-CoT is a single zero‑shot prompt that elicits chain‑of‑thought reasoning from la | 0.795 | Large Language Models are Zero-Shot Reas |
|  | `2206.07682v2::3`: The existence of emergent abilities implies that additional scaling could further expand t | 0.784 | Emergent Abilities of Large Language Mod |
|  | `2205.11916v4::0`: Adding the phrase "Let's think step by step" before each answer enables large language mod | 0.781 | Large Language Models are Zero-Shot Reas |
|  | `2307.13702v1::0`: Large language models (LLMs) perform better when they produce step-by-step, "Chain-of-Thou | 0.777 | Measuring Faithfulness in Chain-of-Thoug |

**`2201.11903v6::5`** [definition]: Chain‑of‑thought prompting is presented as a simple and broadly applicable method for enhancing reasoning in language models.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2205.11916v4::4`: Zero-shot-CoT is a single zero‑shot prompt that elicits chain‑of‑thought reasoning from la | 0.847 | Large Language Models are Zero-Shot Reas |
|  | `2307.13702v1::6`: The authors introduce metrics for evaluating CoT faithfulness to facilitate increasing the | 0.823 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2205.11916v4::5`: The strong performance of a single prompt across diverse tasks suggests that large languag | 0.814 | Large Language Models are Zero-Shot Reas |
|  | `2205.11916v4::0`: Adding the phrase "Let's think step by step" before each answer enables large language mod | 0.807 | Large Language Models are Zero-Shot Reas |
|  | `2307.13702v1::0`: Large language models (LLMs) perform better when they produce step-by-step, "Chain-of-Thou | 0.780 | Measuring Faithfulness in Chain-of-Thoug |

### Language Models Don't Always Say What They Think: Unfaithful Explanations in Chain-of-Thought Prompting (`2305.04388v2`)

**`2305.04388v2::0`** [finding]: Chain-of-thought (CoT) explanations can be heavily influenced by biasing features such as reordering multiple-choice options to make the answer always "(A)", and models systematically fail to mention this bias in their explanations.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2307.13702v1::2`: Models show large variation across tasks in how strongly they condition on the CoT when pr | 0.732 | Measuring Faithfulness in Chain-of-Thoug |
| ⚠ | `2201.11903v6::4`: Chain‑of‑thought reasoning is an emergent property of model scale that allows sufficiently | 0.721 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2203.11171v4::9`: Language models can sometimes generate incorrect or nonsensical reasoning paths, indicatin | 0.717 | Self-Consistency Improves Chain of Thoug |
|  | `2206.04615v3::4`: Social bias typically increases with scale in settings with ambiguous context, but this ca | 0.714 | Beyond the Imitation Game: Quantifying a |
|  | `2307.13702v1::0`: Large language models (LLMs) perform better when they produce step-by-step, "Chain-of-Thou | 0.711 | Measuring Faithfulness in Chain-of-Thoug |

**`2305.04388v2::1`** [finding]: When models are biased toward incorrect answers, they frequently generate CoT explanations that rationalize those answers, causing accuracy to drop by up to 36% on a suite of 13 BIG-Bench Hard tasks tested with GPT-3.5 from OpenAI and Claude 1.0 from Anthropic.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2307.13702v1::2`: Models show large variation across tasks in how strongly they condition on the CoT when pr | 0.742 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2307.13702v1::4`: As models become larger and more capable, they produce less faithful reasoning on most tas | 0.735 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2307.13702v1::5`: The degree of post‑hoc reasoning often shows inverse scaling, getting worse with increasin | 0.714 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2203.11171v4::9`: Language models can sometimes generate incorrect or nonsensical reasoning paths, indicatin | 0.710 | Self-Consistency Improves Chain of Thoug |
|  | `2307.13702v1::0`: Large language models (LLMs) perform better when they produce step-by-step, "Chain-of-Thou | 0.678 | Measuring Faithfulness in Chain-of-Thoug |

**`2305.04388v2::2`** [finding]: On a social-bias task, model explanations justify answers that align with stereotypes without mentioning the influence of the social biases.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2206.04615v3::4`: Social bias typically increases with scale in settings with ambiguous context, but this ca | 0.752 | Beyond the Imitation Game: Quantifying a |
|  | `2203.11171v4::0`: Self-consistency is a decoding strategy that replaces the naive greedy decoding used in ch | 0.702 | Self-Consistency Improves Chain of Thoug |
| ⚠ | `2201.11903v6::4`: Chain‑of‑thought reasoning is an emergent property of model scale that allows sufficiently | 0.702 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2307.13702v1::1`: It is unclear whether the stated reasoning is a faithful explanation of the model's actual | 0.699 | Measuring Faithfulness in Chain-of-Thoug |
| ⚠ | `2201.11903v6::5`: Chain‑of‑thought prompting is presented as a simple and broadly applicable method for enha | 0.692 | Chain-of-Thought Prompting Elicits Reaso |

**`2305.04388v2::3`** [finding]: Chain-of-thought prompting is systematically unfaithful across three distinct bias types (social stereotypes, Answer is Always A, Suggested Answer), two prompting settings (zero-shot and few-shot), and two models (Claude 1.0 and GPT-3.5).

| Label | Neighbour | Score | Paper |
|---|---|---|---|
| ⚠ | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.793 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2205.11916v4::4`: Zero-shot-CoT is a single zero‑shot prompt that elicits chain‑of‑thought reasoning from la | 0.789 | Large Language Models are Zero-Shot Reas |
|  | `2206.04615v3::4`: Social bias typically increases with scale in settings with ambiguous context, but this ca | 0.779 | Beyond the Imitation Game: Quantifying a |
| ⚠ | `2201.11903v6::5`: Chain‑of‑thought prompting is presented as a simple and broadly applicable method for enha | 0.777 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2205.11916v4::5`: The strong performance of a single prompt across diverse tasks suggests that large languag | 0.763 | Large Language Models are Zero-Shot Reas |

**`2305.04388v2::4`** [limitation]: Improving the faithfulness of CoT explanations will require targeted measurement and improvement efforts, or alternatively abandoning CoT in favor of other explanation methods.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2307.13702v1::2`: Models show large variation across tasks in how strongly they condition on the CoT when pr | 0.660 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2307.13702v1::4`: As models become larger and more capable, they produce less faithful reasoning on most tas | 0.660 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2203.11171v4::9`: Language models can sometimes generate incorrect or nonsensical reasoning paths, indicatin | 0.653 | Self-Consistency Improves Chain of Thoug |
|  | `2307.13702v1::6`: The authors introduce metrics for evaluating CoT faithfulness to facilitate increasing the | 0.652 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2206.04615v3::4`: Social bias typically increases with scale in settings with ambiguous context, but this ca | 0.634 | Beyond the Imitation Game: Quantifying a |

### Measuring Faithfulness in Chain-of-Thought Reasoning (`2307.13702v1`)

**`2307.13702v1::0`** [finding]: Large language models (LLMs) perform better when they produce step-by-step, "Chain-of-Thought" (CoT) reasoning before answering a question.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2201.11903v6::0`: Generating a chain of thought—a series of intermediate reasoning steps—significantly impro | 0.826 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.803 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.780 | Emergent Abilities of Large Language Mod |
|  | `2201.11903v6::5`: Chain‑of‑thought prompting is presented as a simple and broadly applicable method for enha | 0.780 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2201.11903v6::4`: Chain‑of‑thought reasoning is an emergent property of model scale that allows sufficiently | 0.777 | Chain-of-Thought Prompting Elicits Reaso |

**`2307.13702v1::1`** [limitation]: It is unclear whether the stated reasoning is a faithful explanation of the model's actual reasoning process.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2305.04388v2::2`: On a social-bias task, model explanations justify answers that align with stereotypes with | 0.699 | Language Models Don't Always Say What Th |
|  | `2203.11171v4::9`: Language models can sometimes generate incorrect or nonsensical reasoning paths, indicatin | 0.697 | Self-Consistency Improves Chain of Thoug |
|  | `2304.15004v2::6`: Emergent ability claims may be confounded by a failure to control for multiple comparisons | 0.680 | Are Emergent Abilities of Large Language |
|  | `2201.11903v6::4`: Chain‑of‑thought reasoning is an emergent property of model scale that allows sufficiently | 0.669 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2305.04388v2::0`: Chain-of-thought (CoT) explanations can be heavily influenced by biasing features such as  | 0.665 | Language Models Don't Always Say What Th |

**`2307.13702v1::2`** [finding]: Models show large variation across tasks in how strongly they condition on the CoT when predicting their answer, sometimes relying heavily on the CoT and other times primarily ignoring it.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2305.04388v2::1`: When models are biased toward incorrect answers, they frequently generate CoT explanations | 0.742 | Language Models Don't Always Say What Th |
|  | `2305.04388v2::0`: Chain-of-thought (CoT) explanations can be heavily influenced by biasing features such as  | 0.732 | Language Models Don't Always Say What Th |
|  | `2304.15004v2::0`: Recent work claims that large language models display emergent abilities that appear sharp | 0.713 | Are Emergent Abilities of Large Language |
|  | `2206.04615v3::2`: Tasks that improve gradually and predictably commonly involve a large knowledge or memoriz | 0.706 | Beyond the Imitation Game: Quantifying a |
|  | `2206.04615v3::1`: Performance is remarkably similar across model classes, though sparsity provides benefits | 0.684 | Beyond the Imitation Game: Quantifying a |

**`2307.13702v1::3`** [finding]: CoT's performance boost does not seem to come from CoT's added test-time compute alone or from information encoded via the particular phrasing of the CoT.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2206.07682v2::4`: Meaningful performance of emergent abilities has only been observed at a certain computati | 0.653 | Emergent Abilities of Large Language Mod |
|  | `2205.11916v4::2`: Zero-shot-CoT significantly outperforms standard zero-shot performance on a range of reaso | 0.647 | Large Language Models are Zero-Shot Reas |
|  | `2304.15004v2::3`: Three predictions about metric effects were made, tested, and confirmed on the InstructGPT | 0.642 | Are Emergent Abilities of Large Language |
|  | `2305.04388v2::4`: Improving the faithfulness of CoT explanations will require targeted measurement and impro | 0.631 | Language Models Don't Always Say What Th |
|  | `2203.11171v4::2`: Self-consistency improves accuracy on the SVAMP arithmetic benchmark by 11.0% compared to  | 0.630 | Self-Consistency Improves Chain of Thoug |

**`2307.13702v1::4`** [finding]: As models become larger and more capable, they produce less faithful reasoning on most tasks studied.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2305.04388v2::1`: When models are biased toward incorrect answers, they frequently generate CoT explanations | 0.735 | Language Models Don't Always Say What Th |
|  | `2203.11171v4::9`: Language models can sometimes generate incorrect or nonsensical reasoning paths, indicatin | 0.735 | Self-Consistency Improves Chain of Thoug |
|  | `2304.15004v2::0`: Recent work claims that large language models display emergent abilities that appear sharp | 0.734 | Are Emergent Abilities of Large Language |
|  | `2206.04615v3::0`: Model performance and calibration both improve with scale, but are poor in absolute terms  | 0.712 | Beyond the Imitation Game: Quantifying a |
|  | `2001.08361v1::5`: Larger language models are significantly more sample‑efficient than smaller ones. | 0.709 | Scaling Laws for Neural Language Models |

**`2307.13702v1::5`** [finding]: The degree of post‑hoc reasoning often shows inverse scaling, getting worse with increasingly capable models.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2304.15004v2::0`: Recent work claims that large language models display emergent abilities that appear sharp | 0.742 | Are Emergent Abilities of Large Language |
|  | `2206.04615v3::0`: Model performance and calibration both improve with scale, but are poor in absolute terms  | 0.742 | Beyond the Imitation Game: Quantifying a |
|  | `2304.15004v2::6`: Emergent ability claims may be confounded by a failure to control for multiple comparisons | 0.736 | Are Emergent Abilities of Large Language |
|  | `2203.11171v4::9`: Language models can sometimes generate incorrect or nonsensical reasoning paths, indicatin | 0.730 | Self-Consistency Improves Chain of Thoug |
|  | `2304.15004v2::1`: The authors propose that apparent emergent abilities arise from the researcher’s choice of | 0.715 | Are Emergent Abilities of Large Language |

**`2307.13702v1::6`** [method]: The authors introduce metrics for evaluating CoT faithfulness to facilitate increasing the faithfulness of chain‑of‑thought reasoning.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.838 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2201.11903v6::5`: Chain‑of‑thought prompting is presented as a simple and broadly applicable method for enha | 0.823 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2201.11903v6::4`: Chain‑of‑thought reasoning is an emergent property of model scale that allows sufficiently | 0.819 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2205.11916v4::4`: Zero-shot-CoT is a single zero‑shot prompt that elicits chain‑of‑thought reasoning from la | 0.805 | Large Language Models are Zero-Shot Reas |
|  | `2201.11903v6::0`: Generating a chain of thought—a series of intermediate reasoning steps—significantly impro | 0.782 | Chain-of-Thought Prompting Elicits Reaso |

### Large Language Models are Zero-Shot Reasoners (`2205.11916v4`)

**`2205.11916v4::0`** [finding]: Adding the phrase "Let's think step by step" before each answer enables large language models to perform zero-shot reasoning, raising MultiArith accuracy from 17.7% to 78.7% with the InstructGPT model text-davinci-002

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2201.11903v6::0`: Generating a chain of thought—a series of intermediate reasoning steps—significantly impro | 0.825 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2201.11903v6::5`: Chain‑of‑thought prompting is presented as a simple and broadly applicable method for enha | 0.807 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.800 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.788 | Emergent Abilities of Large Language Mod |
|  | `2201.11903v6::3`: Prompting a 540 billion‑parameter language model with eight chain-of-thought exemplars ach | 0.784 | Chain-of-Thought Prompting Elicits Reaso |

**`2205.11916v4::1`** [finding]: The same zero-shot prompt increases GSM8K accuracy from 10.4% to 40.7% with text-davinci-002

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2203.11171v4::1`: Self-consistency improves accuracy on the GSM8K arithmetic benchmark by 17.9% compared to  | 0.722 | Self-Consistency Improves Chain of Thoug |
|  | `2203.11171v4::2`: Self-consistency improves accuracy on the SVAMP arithmetic benchmark by 11.0% compared to  | 0.651 | Self-Consistency Improves Chain of Thoug |
|  | `2201.11903v6::3`: Prompting a 540 billion‑parameter language model with eight chain-of-thought exemplars ach | 0.628 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2203.11171v4::6`: Self-consistency yields significant accuracy gains across four large language models of va | 0.626 | Self-Consistency Improves Chain of Thoug |
|  | `2206.04615v3::4`: Social bias typically increases with scale in settings with ambiguous context, but this ca | 0.610 | Beyond the Imitation Game: Quantifying a |

**`2205.11916v4::2`** [finding]: Zero-shot-CoT significantly outperforms standard zero-shot performance on a range of reasoning benchmarks—including MultiArith, GSM8K, AQUA‑RAT, SVAMP, Last Letter, Coin Flip, Date Understanding, and Tracking Shuffled Objects—without using any hand‑crafted few‑shot examples

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2203.11171v4::2`: Self-consistency improves accuracy on the SVAMP arithmetic benchmark by 11.0% compared to  | 0.756 | Self-Consistency Improves Chain of Thoug |
|  | `2307.13702v1::6`: The authors introduce metrics for evaluating CoT faithfulness to facilitate increasing the | 0.725 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.712 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2203.11171v4::1`: Self-consistency improves accuracy on the GSM8K arithmetic benchmark by 17.9% compared to  | 0.707 | Self-Consistency Improves Chain of Thoug |
|  | `2203.11171v4::3`: Self-consistency improves accuracy on the AQuA arithmetic benchmark by 12.2% compared to s | 0.702 | Self-Consistency Improves Chain of Thoug |

**`2205.11916v4::3`** [finding]: Similar magnitude improvements are observed when applying Zero-shot-CoT to the 540‑billion‑parameter PaLM model, indicating the method generalizes across off‑the‑shelf large models

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2206.04615v3::6`: OpenAI GPT models, Google-internal dense transformer architectures, and Switch-style spars | 0.707 | Beyond the Imitation Game: Quantifying a |
|  | `2206.04615v3::1`: Performance is remarkably similar across model classes, though sparsity provides benefits | 0.706 | Beyond the Imitation Game: Quantifying a |
|  | `2001.08361v1::2`: Simple equations accurately describe how overfitting depends on model size and dataset siz | 0.683 | Scaling Laws for Neural Language Models |
|  | `2203.11171v4::6`: Self-consistency yields significant accuracy gains across four large language models of va | 0.677 | Self-Consistency Improves Chain of Thoug |
|  | `2206.04615v3::0`: Model performance and calibration both improve with scale, but are poor in absolute terms  | 0.676 | Beyond the Imitation Game: Quantifying a |

**`2205.11916v4::4`** [method]: Zero-shot-CoT is a single zero‑shot prompt that elicits chain‑of‑thought reasoning from large language models across many tasks, contrasting with prior few‑shot (in‑context) approaches that require task‑specific exemplars

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2201.11903v6::5`: Chain‑of‑thought prompting is presented as a simple and broadly applicable method for enha | 0.847 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.823 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2307.13702v1::6`: The authors introduce metrics for evaluating CoT faithfulness to facilitate increasing the | 0.805 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2201.11903v6::4`: Chain‑of‑thought reasoning is an emergent property of model scale that allows sufficiently | 0.795 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2305.04388v2::3`: Chain-of-thought prompting is systematically unfaithful across three distinct bias types ( | 0.789 | Language Models Don't Always Say What Th |

**`2205.11916v4::5`** [finding]: The strong performance of a single prompt across diverse tasks suggests that large language models possess untapped zero‑shot, multi‑task cognitive capabilities that can be accessed through simple prompting

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.861 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2304.15004v2::0`: Recent work claims that large language models display emergent abilities that appear sharp | 0.843 | Are Emergent Abilities of Large Language |
|  | `2201.11903v6::5`: Chain‑of‑thought prompting is presented as a simple and broadly applicable method for enha | 0.814 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2206.07682v2::3`: The existence of emergent abilities implies that additional scaling could further expand t | 0.811 | Emergent Abilities of Large Language Mod |
|  | `2206.07682v2::5`: Emergent abilities can span a variety of language model architectures, task types, and exp | 0.810 | Emergent Abilities of Large Language Mod |

### Self-Consistency Improves Chain of Thought Reasoning in Language Models (`2203.11171v4`)

**`2203.11171v4::0`** [method]: Self-consistency is a decoding strategy that replaces the naive greedy decoding used in chain-of-thought prompting by sampling a diverse set of reasoning paths and selecting the most consistent answer through marginalization over the sampled paths.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2201.11903v6::5`: Chain‑of‑thought prompting is presented as a simple and broadly applicable method for enha | 0.779 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2201.11903v6::4`: Chain‑of‑thought reasoning is an emergent property of model scale that allows sufficiently | 0.768 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2307.13702v1::6`: The authors introduce metrics for evaluating CoT faithfulness to facilitate increasing the | 0.761 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.758 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2205.11916v4::4`: Zero-shot-CoT is a single zero‑shot prompt that elicits chain‑of‑thought reasoning from la | 0.732 | Large Language Models are Zero-Shot Reas |

**`2203.11171v4::1`** [finding]: Self-consistency improves accuracy on the GSM8K arithmetic benchmark by 17.9% compared to standard chain-of-thought prompting.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2201.11903v6::3`: Prompting a 540 billion‑parameter language model with eight chain-of-thought exemplars ach | 0.788 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.777 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2307.13702v1::6`: The authors introduce metrics for evaluating CoT faithfulness to facilitate increasing the | 0.726 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2205.11916v4::1`: The same zero-shot prompt increases GSM8K accuracy from 10.4% to 40.7% with text-davinci-0 | 0.722 | Large Language Models are Zero-Shot Reas |
|  | `2201.11903v6::5`: Chain‑of‑thought prompting is presented as a simple and broadly applicable method for enha | 0.716 | Chain-of-Thought Prompting Elicits Reaso |

**`2203.11171v4::2`** [finding]: Self-consistency improves accuracy on the SVAMP arithmetic benchmark by 11.0% compared to standard chain-of-thought prompting.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.817 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2205.11916v4::2`: Zero-shot-CoT significantly outperforms standard zero-shot performance on a range of reaso | 0.756 | Large Language Models are Zero-Shot Reas |
|  | `2304.15004v2::4`: Two predictions about metric choices were made, tested, and confirmed in a meta‑analysis o | 0.753 | Are Emergent Abilities of Large Language |
|  | `2307.13702v1::6`: The authors introduce metrics for evaluating CoT faithfulness to facilitate increasing the | 0.753 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2201.11903v6::5`: Chain‑of‑thought prompting is presented as a simple and broadly applicable method for enha | 0.749 | Chain-of-Thought Prompting Elicits Reaso |

**`2203.11171v4::3`** [finding]: Self-consistency improves accuracy on the AQuA arithmetic benchmark by 12.2% compared to standard chain-of-thought prompting.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.798 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2307.13702v1::6`: The authors introduce metrics for evaluating CoT faithfulness to facilitate increasing the | 0.744 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2201.11903v6::5`: Chain‑of‑thought prompting is presented as a simple and broadly applicable method for enha | 0.736 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2304.15004v2::4`: Two predictions about metric choices were made, tested, and confirmed in a meta‑analysis o | 0.722 | Are Emergent Abilities of Large Language |
|  | `2201.11903v6::0`: Generating a chain of thought—a series of intermediate reasoning steps—significantly impro | 0.716 | Chain-of-Thought Prompting Elicits Reaso |

**`2203.11171v4::4`** [finding]: Self-consistency improves accuracy on the StrategyQA commonsense benchmark by 6.4% compared to standard chain-of-thought prompting.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.822 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2201.11903v6::5`: Chain‑of‑thought prompting is presented as a simple and broadly applicable method for enha | 0.775 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2307.13702v1::6`: The authors introduce metrics for evaluating CoT faithfulness to facilitate increasing the | 0.767 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2201.11903v6::0`: Generating a chain of thought—a series of intermediate reasoning steps—significantly impro | 0.752 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2304.15004v2::4`: Two predictions about metric choices were made, tested, and confirmed in a meta‑analysis o | 0.731 | Are Emergent Abilities of Large Language |

**`2203.11171v4::5`** [finding]: Self-consistency improves accuracy on the ARC‑challenge benchmark by 3.9% compared to standard chain-of-thought prompting.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2201.11903v6::2`: Experiments on three large language models demonstrate that chain-of-thought prompting imp | 0.772 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2304.15004v2::3`: Three predictions about metric effects were made, tested, and confirmed on the InstructGPT | 0.739 | Are Emergent Abilities of Large Language |
|  | `2307.13702v1::6`: The authors introduce metrics for evaluating CoT faithfulness to facilitate increasing the | 0.736 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2304.15004v2::4`: Two predictions about metric choices were made, tested, and confirmed in a meta‑analysis o | 0.725 | Are Emergent Abilities of Large Language |
|  | `2201.11903v6::5`: Chain‑of‑thought prompting is presented as a simple and broadly applicable method for enha | 0.711 | Chain-of-Thought Prompting Elicits Reaso |

**`2203.11171v4::6`** [finding]: Self-consistency yields significant accuracy gains across four large language models of varying scales, including UL2, GPT‑3 (code‑davinci‑001 and code‑davinci‑002), LaMDA‑137B, and PaLM‑540B.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.764 | Emergent Abilities of Large Language Mod |
|  | `2201.11903v6::3`: Prompting a 540 billion‑parameter language model with eight chain-of-thought exemplars ach | 0.752 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2205.11916v4::0`: Adding the phrase "Let's think step by step" before each answer enables large language mod | 0.747 | Large Language Models are Zero-Shot Reas |
|  | `2001.08361v1::5`: Larger language models are significantly more sample‑efficient than smaller ones. | 0.743 | Scaling Laws for Neural Language Models |
|  | `2201.11903v6::0`: Generating a chain of thought—a series of intermediate reasoning steps—significantly impro | 0.741 | Chain-of-Thought Prompting Elicits Reaso |

**`2203.11171v4::7`** [finding]: Beyond accuracy, self-consistency provides useful rationales, uncertainty estimates, and improved calibration of language‑model outputs.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2206.07682v2::0`: Scaling up language models predictably improves performance and sample efficiency on a wid | 0.756 | Emergent Abilities of Large Language Mod |
|  | `2001.08361v1::5`: Larger language models are significantly more sample‑efficient than smaller ones. | 0.737 | Scaling Laws for Neural Language Models |
|  | `2206.07682v2::3`: The existence of emergent abilities implies that additional scaling could further expand t | 0.732 | Emergent Abilities of Large Language Mod |
|  | `2201.11903v6::0`: Generating a chain of thought—a series of intermediate reasoning steps—significantly impro | 0.731 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2205.11916v4::0`: Adding the phrase "Let's think step by step" before each answer enables large language mod | 0.724 | Large Language Models are Zero-Shot Reas |

**`2203.11171v4::8`** [limitation]: A limitation of self-consistency is increased computational cost, though using a small number of sampled paths (e.g., 5 or 10) captures most of the performance gains with limited overhead.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2203.15556v1::4`: The analysis assumes the efficient computational frontier follows a power‑law relationship | 0.742 | Training Compute-Optimal Large Language  |
|  | `2206.07682v2::4`: Meaningful performance of emergent abilities has only been observed at a certain computati | 0.712 | Emergent Abilities of Large Language Mod |
|  | `2001.08361v1::4`: These scaling relationships enable the determination of the optimal allocation of a fixed  | 0.696 | Scaling Laws for Neural Language Models |
|  | `2206.07682v2::3`: The existence of emergent abilities implies that additional scaling could further expand t | 0.682 | Emergent Abilities of Large Language Mod |
|  | `2206.04615v3::1`: Performance is remarkably similar across model classes, though sparsity provides benefits | 0.655 | Beyond the Imitation Game: Quantifying a |

**`2203.11171v4::9`** [limitation]: Language models can sometimes generate incorrect or nonsensical reasoning paths, indicating a need for better grounding of generated rationales.

| Label | Neighbour | Score | Paper |
|---|---|---|---|
|  | `2201.11903v6::0`: Generating a chain of thought—a series of intermediate reasoning steps—significantly impro | 0.761 | Chain-of-Thought Prompting Elicits Reaso |
|  | `2304.15004v2::0`: Recent work claims that large language models display emergent abilities that appear sharp | 0.756 | Are Emergent Abilities of Large Language |
|  | `2307.13702v1::4`: As models become larger and more capable, they produce less faithful reasoning on most tas | 0.735 | Measuring Faithfulness in Chain-of-Thoug |
|  | `2205.11916v4::0`: Adding the phrase "Let's think step by step" before each answer enables large language mod | 0.733 | Large Language Models are Zero-Shot Reas |
|  | `2201.11903v6::4`: Chain‑of‑thought reasoning is an emergent property of model scale that allows sufficiently | 0.731 | Chain-of-Thought Prompting Elicits Reaso |
