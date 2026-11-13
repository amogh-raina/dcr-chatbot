# prompts/base/

Layer 1 of the prompt hierarchy: immutable base rules shared by every call of one API.

| Name (`prompts.get(...)`) | File | Used by | Switch |
|---|---|---|---|
| `base/decisions` | `decisions.txt` | `retrieval_llm._decide`: prefixed (with one space) to the instructions of every Decisions question | `BASE_LAYER_DECISIONS=1` |

The switch is off by default. With it off, the Decisions request body is byte-identical to what it was before this file existed.
Turning it on changes model input, so it needs an eval run first (`python -m evals.eval_followups` with
`BASE_LAYER_DECISIONS=1` against the same run with `0`; see `docs/specs/02-registry-and-trace-record.md`, 4.1.3 and 5.5).
The wording is a proposal and has not been evaluated; its owner is Amogh.
The Responses path has no base layer yet.
