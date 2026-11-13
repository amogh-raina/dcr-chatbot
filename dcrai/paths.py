"""Single source of truth for where things live on disk.

Every module that reads or writes a file under the repository imports its location from here.
Moving a folder means changing one line in this file.

Environment overrides (all optional):
    INTERACTION_LOG_DIR   where per-interaction JSONL logs are written (default traces/interactions)
    RUNTIME_TRACE_DIR     where simulation snapshots and choice diagnostics are written (default traces/runtime)
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = ROOT / 'docs'
SOURCES = DOCS / 'sources'          # inputs the data build reads (guideline docx, practical FAQ md)
SPECS = DOCS / 'specs'

PROMPTS = ROOT / 'prompts'          # every model instruction, as text files (see prompts/README.md)

TRACES = ROOT / 'traces'
INTERACTION_LOGS = Path(os.getenv('INTERACTION_LOG_DIR') or TRACES / 'interactions')
RUNTIME_TRACES = Path(os.getenv('RUNTIME_TRACE_DIR') or TRACES / 'runtime')
REGISTRY_SNAPSHOTS = TRACES / 'registry'   # one <registry_version>.json per version (see dcrai/registry.py)

EVALS = ROOT / 'evals'
EVAL_CASES = EVALS / 'cases'        # inputs: labelled queries
EVAL_RUNS = EVALS / 'runs'          # outputs: cached scores and raw results
EVAL_REPORTS = EVALS / 'reports'    # outputs: readable reports

FAQ_DATA = ROOT / 'faq_search' / 'data'   # records and embeddings only
GRAPHS = ROOT / 'xml graphs'
