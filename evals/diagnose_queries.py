"""Why did a Help panel question find nothing? Shows the search scores and, optionally, the relevance check.

    python -m evals.diagnose_queries               # embedding scores and the API decision only
    python -m evals.diagnose_queries --relevance   # also the LLM relevance post-check (needs OPENAI_API_KEY)

For each case it searches three versions, as the application does: the typed words, "<field label> <message>"
(composed) and a hand-written standalone question (what a good rewrite would look like). It prints the top 3 FAQs
with scores, the decision the FAQ API would return with the current thresholds (FAQ_SINGLE_THRESHOLD,
FAQ_MIN_THRESHOLD, FAQ_MARGIN_THRESHOLD; defaults 0.80 / 0.50 / 0.12) and, with --relevance, which candidates the
relevance post-check keeps. A case fails at the search when the expected FAQ is not in the top 3 or the top score is
below the minimum; it fails at the relevance check when the search offers it and the check drops it.

Add cases to CASES. Nothing is sent to DCR; the messages are printed on your own console only.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# (field id, message, hand-written standalone question, expected FAQ id or None if no FAQ is known to answer it)
CASES = [
    ('Form0:Prev_work', 'what if I have prior work experience?',
     'Does work I did before my studies count against me?', 'FAQ_17'),
    ('Form0:Plan_work_studies', "if I won't work, would it be an issue?",
     'Is it a problem for my application if I do not plan to work alongside my studies?', None),
    ('Form0:Plan_work_studies', 'I am not sure, how does that decision affect the application?',
     'How does planning to work alongside my studies affect my application?', 'FAQ_16'),
    ('Form0:A5', 'what about describing my medical condition? like what do we have to talk about in the personal '
                 'statement?', 'What should I write about in my personal statement?', 'FAQ_P05'),
    ('Form0:Impairment_type', "What if my impairment is congenital and I don't have recent medical records?",
     "What if my impairment is congenital and I don't have recent medical records?", 'FAQ_26'),
]


def labels():
    """Field labels as the graph shows them (from the eval helper, which reads the clean graph)."""
    try:
        from evals.eval_composed import field_labels
        return field_labels()
    except Exception:   # noqa: BLE001 - fall back to the field id
        return {}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--relevance', action='store_true', help='also run the LLM relevance post-check')
    args = parser.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / '.env')
    except ImportError:
        pass
    from faq_search.api import decide
    from faq_search.retriever import get_retriever
    from dcrai.llm.openchat import Settings
    settings = Settings.from_env()
    retriever = get_retriever()
    names = labels()
    print(f'Thresholds: single>={settings.single:.2f} margin>={settings.margin:.2f} minimum>={settings.minimum:.2f}')
    if args.relevance:
        import dcrai.llm.retrieval_llm as llm
        print('DECISIONS_ENABLED in this environment:', os.getenv('DECISIONS_ENABLED') == '1', '(the app uses the decisions check only when this is True)')
    for field, message, rewrite, expected in CASES:
        label = names.get(field, field)
        print('\n' + '=' * 100)
        print(f'{field}: {label}\nmessage: {message}\nexpected: {expected or "(no FAQ known)"}')
        for how, query in (('typed', message), ('composed', f'{label} {message}'), ('rewrite', rewrite)):
            results = retriever.retrieve(query, top_k=3)
            decision = decide(results, settings)
            offered = (results[:1] if decision == 'single_match'
                       else [r for r in results if r.score >= settings.minimum] if decision == 'clarify_match'
                       else [])
            mark = 'OK ' if expected and any(r.id == expected for r in offered) else '-- '
            print(f'\n  [{mark}] {how:8} decision={decision}')
            for r in results:
                print(f'        {r.score:.3f}  {r.id:8} {r.canonical_question[:70]}'
                      + (f'   (matched variant: {r.matched_text[:50]})' if r.matched_kind == 'variant' else ''))
            if args.relevance and offered:
                found = [dict(id=r.id, question=r.canonical_question) for r in offered]
                # Both versions of the post-check: the app uses Decisions when DECISIONS_ENABLED=1, else Responses.
                for mode, check in (('responses', llm.relevant), ('decisions', llm.relevant_decisions)):
                    try:
                        kept = check(query, found)
                    except llm.LLMError as error:
                        kept = f'unavailable ({error})'
                    print(f'        relevance check ({mode}) keeps: {kept}')
    print()


if __name__ == '__main__':
    main()
