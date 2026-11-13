# DCR graph skill: install and use with an agent

The repository includes the complete **dcr-xml-builder** skill in
[`.agents/skills/dcr-xml-builder/`](../../.agents/skills/dcr-xml-builder/SKILL.md).
It covers graph creation, semantic explanation, XML review/repair, Robots, REST effects, marking and embedded DMN.
The XML validator uses Python's standard library; it needs no API key, MCP server or pip package.
Live Portal tests separately require access and private credentials, as in [deployment](DEPLOY.md).

## Codex

Open Codex in this checkout. Repository skills under `.agents/skills` are discovered automatically;
no user-wide installation is required. Invoke `$dcr-xml-builder` in a prompt. If the skill was added during
an existing chat and is not visible, start a new chat in the repository.
See [official Codex skill discovery documentation](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills).

To make the same skill available in other repositories, run from this checkout:

```sh
python scripts/install_dcr_skill.py --agent codex
```

This copies the complete bundle into `~/.agents/skills/dcr-xml-builder`.
An existing installation is left alone: compare/update it deliberately rather than merging versions.
Avoid installing duplicate copies with the same name in several discovery locations.

## Claude Code

`CLAUDE.md` imports `AGENTS.md`, which points Claude to the repository skill for graph work. Claude can read
the bundle directly. For native `/dcr-xml-builder` invocation, install a user copy:

```sh
python scripts/install_dcr_skill.py --agent claude
```

This copies it to `~/.claude/skills/dcr-xml-builder`. Alternatively install only for this checkout:

```sh
python scripts/install_dcr_skill.py --agent claude --scope repo
```

That destination is `.claude/skills/dcr-xml-builder` (local/ignored). Use `/dcr-xml-builder` in Claude Code.
See [Claude's skill locations](https://code.claude.com/docs/en/skills#choose-where-skills-load) and
[memory imports](https://code.claude.com/docs/en/memory#import-additional-files).

## Any other agent

There is no universal install command across agents. Give the agent this instruction:

> Read AGENTS.md and .agents/skills/dcr-xml-builder/SKILL.md. For DCR graph work follow that skill and
> load the referenced semantic, XML and REST material as needed. Work from the repository root. Preserve
> existing source graphs, generate a new output, run the bundled validator, and explain which behaviours
> were checked locally and which still require Portal simulation.

If an agent supports Agent Skills in a different directory, copy the entire folder, including `references/`,
`scripts/`, `assets/` and `agents/`. The helper accepts an exact destination directory:

```sh
python scripts/install_dcr_skill.py --dest /path/to/agent/skills/dcr-xml-builder
```

Do not copy only SKILL.md: its relative links and validator would be broken. The helper does not register
tools or grant permissions. Agents without skill discovery can still read and follow these files explicitly.

## Examples for this repository

**Explain:** Ask the agent to use the skill to explain
`xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml`: initial included/pending events,
`Session_Chat` versus `Session_Panel`, retrieval continuations, outcome table, and accepting states.
Have it cite event IDs and relations, and distinguish local evidence from Portal observations.

**Build:** Ask it to use `tools/clean_graph/` to regenerate a new credential-free graph from the Structured
source, preserve the source, and compare event/guard/marking changes. Normal rebuild command:

```sh
python tools/clean_graph/build_clean_graph.py
```

This writes the default NoEffect graph. For a scratch output, pass the builder's five positional paths
(`SRC OUT_EFFECT OUT_PLAIN DET_JSON RECORDS`); see its usage string and
[`build_clean_graph.py`](../../tools/clean_graph/build_clean_graph.py). Do not invent a `--output` option.

**Validate and debug locally:**

```sh
python .agents/skills/dcr-xml-builder/scripts/validate_dcr_xml.py "xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml"
python tools/clean_graph/simulate_clean_graph.py "xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml"
python -m unittest discover -s tests -t . -p test_outcome_table_graph.py
```

For REST/Robot failures load [the bundled API reference](../../.agents/skills/dcr-xml-builder/references/rest-simulation-api.md).
Check the new `/simulation/` engine, event role, quoted literal/continuation parameters, and both retrieval Robots.
For a wrong answer inspect the [trace](../../traces/README.md), selected FAQs and outcome row as well as the graph.
Structural validation alone does not prove business-rule correctness or successful Portal import.

Before installing, agents should show the target location and avoid replacing a pre-existing skill.
No installation is performed merely by reading this guide.
