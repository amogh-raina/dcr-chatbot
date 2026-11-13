#!/usr/bin/env python3
"""
build_faq_data.py -- Builds faq_search/data/faq_qa_records.json.

Sources:
1. Question_upmapping_chatbot.docx (Vejledning nr 9577 af 25/06/2025): the 43 guideline FAQs.
   The questions, source sections and answer text are read straight from the document.
2. SU_handicaptillaeg_FAQ_Expanded_Questions_Answers.md: 12 practical FAQs (how to apply, case
   status, documentation age, representatives, scholarships ...) that the guideline mapping does
   not cover. Their answers are read verbatim from that file; ids are FAQ_P01..FAQ_P12.

What the script does:
- Keeps follow-up determinations ('hvis' branches: the "Ask the applicant" question and its
  "If yes" / "If no" lines) OUT of the answers. They are modelled in the DCR graph. Only the
  number of determination questions is recorded, in dcr_note.
- Removes authoring leftovers from the docx (stray "Section N" headings, [FAQ: ...] blocks and
  [reference ...] notes). The questions inside [FAQ: ...] blocks become extra phrasing variants.
- Normalises citations to "Vejledning nr 9577, Section X".
- Attaches 3-5 English phrasing variants per record (Danish variants are added later).
- Validates the result and refuses to write the file if anything leaked or is missing.

Run from the repo root:  python faq_search/build_faq_data.py
Then recompute the vectors: python faq_search/embed_faq_data.py

Language edits: faq_search/answer_edits.json lists exact passages of answers to replace (grammar,
punctuation, British spelling, consistent terms, no em dashes) without changing what an answer says.
Each passage must occur exactly once, otherwise the build stops: the source text has changed and the
edit needs a look. The source documents themselves are not edited.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
DOCX_PATH = PROJECT_ROOT / "docs" / "sources" / "Question_upmapping_chatbot.docx"
PRACTICAL_MD_PATH = PROJECT_ROOT / "docs" / "sources" / "SU_handicaptillaeg_FAQ_Expanded_Questions_Answers.md"
OUTPUT_PATH = HERE / "data" / "faq_qa_records.json"
ANSWER_EDITS_PATH = HERE / "answer_edits.json"

SCHEMA_VERSION = 4
CITATION_PREFIX = "Vejledning nr 9577"
GUIDELINE_CITATION = f"{CITATION_PREFIX} af 25/06/2025"

TOPIC_MAP = {
    "Purpose and scope of the scheme": "eligibility_and_education",
    "Overall eligibility conditions": "eligibility_and_education",
    "Permanent impairment and severity": "impairment_and_work_capacity",
    "Ability to take paid work": "impairment_and_work_capacity",
    "Scope of impairments considered & excluded factors": "impairment_and_work_capacity",
    "Medical documentation": "medical_documentation",
    "Additional information gathering": "medical_documentation",
    "Refusal to process and denial": "applying_decisions_and_help",
    "Payment of the supplement": "payment_work_and_changes",
    "Income limits after an award": "payment_work_and_changes",
    "Appeals": "applying_decisions_and_help",
}

TOPICS_LIST = [
    {"id": "eligibility_and_education", "label": "Eligibility and qualifying education"},
    {"id": "impairment_and_work_capacity", "label": "Impairment and ability to work"},
    {"id": "medical_documentation", "label": "Medical documentation"},
    {"id": "applying_decisions_and_help", "label": "Applying, decisions and help"},
    {"id": "payment_work_and_changes", "label": "Payment, work and changes after approval"},
]

# Base answers for guideline FAQs whose docx entry has NO plain answer text: all of their content is
# inside the "Follow-up determination" block, which this script deliberately drops. The wording below
# is taken from that block, with the yes/no branching removed. They are marked drafted_needs_review
# so that someone with legal knowledge confirms them. A base answer is used only while the docx gives
# no answer text; if the docx gains one, the docx wins and the build stops until this entry is removed.
BASE_ANSWERS = {
    "25": (
        "As a starting point, a psychologist's statement cannot stand alone as your medical documentation. "
        "It can be included as part of the overall assessment of your application if it is backed up by a "
        "statement from a psychiatric specialist or by other medical documentation."
    ),
    "42": (
        "You have 4 weeks to submit your appeal to the Agency. If you miss the deadline, the Appeals Board "
        "can in some cases disregard it, up to six months after you received the decision, if the delay is "
        "excusable for special reasons. It is the Appeals Board, not the Agency, that decides whether the "
        "delay counts as excusable, so the Agency cannot make that call for you."
    ),
    "43": (
        "No. New medical documentation sent with an appeal against a refusal-to-process decision will not be "
        "taken into account in that appeal. Such an appeal only examines whether the Agency was entitled to "
        "refuse the application in the first place, not your substantive entitlement to handicaptillæg. "
        "To have new documentation considered, you would need to submit a new application instead."
    ),
}

# Curated English phrasing variants for each guideline FAQ (Danish variants are added later).
DEFAULT_VARIANTS = {
    "01": ["What is the disability supplement?", "Who can receive handicaptillæg?", "Can I get extra SU for a disability?", "What does the supplement cover?"],
    "02": ["Why does the handicap supplement exist?", "What is the purpose of handicaptillæg?", "Why do students get a disability grant?", "What is the idea behind the supplement?"],
    "03": ["What conditions must I meet to get the supplement?", "What are the requirements for handicaptillæg?", "How do I qualify for the disability supplement?", "What are the 3 main eligibility criteria?"],
    "04": ["Do I need to receive SU to get handicaptillæg?", "Can I get the supplement without receiving SU?", "Is the supplement tied to ordinary SU?", "Can I apply for handicaptillæg if I haven't applied for SU?"],
    "05": ["When am I eligible for ordinary SU?", "What are the general SU requirements?", "Can I get SU if I am under 18?", "Do I need to be study-active for SU?"],
    "05b": ["Can foreign citizens get handicaptillæg?", "I am not a Danish citizen, can I get the supplement?", "Can EU citizens receive handicaptillæg?", "What are the rules for non-Danish applicants?"],
    "06": ["Which education programmes qualify for the supplement?", "Can I get handicaptillæg at university or vocational school?", "Does my study programme qualify?", "Is EUD or higher education covered?"],
    "07": ["What does the Agency evaluate in my functional impairment?", "How is my disability assessed?", "What matters when assessing my impairment?", "How does the Agency look at functional limitation?"],
    "08": ["What counts as a permanent impairment?", "How does SU define permanent for disability?", "Must my condition be lifelong?", "What is the legal definition of permanent impairment?"],
    "09": ["How long must my condition have lasted to count as permanent?", "Is there a one-year waiting period for handicaptillæg?", "Can a non-permanent disease be treated as permanent?", "Does the condition need to have lasted one year?"],
    "11": ["How does the Agency assess the severity of my condition?", "What makes an impairment severe enough for the supplement?", "How is severity evaluated?", "What factors decide how severe my condition is?"],
    "12": ["How does ongoing medical treatment affect my case?", "Can I qualify if I am currently in treatment?", "What if my recovery is still uncertain during treatment?", "Does receiving treatment count against permanence?"],
    "13": ["What if I have more than one impairment?", "Can several conditions be combined in the assessment?", "Does the Agency look at multiple diagnoses together?", "Can multiple mild impairments qualify together?"],
    "14": ["Can I add another impairment while my case is being processed?", "Can I report a new diagnosis after submitting my application?", "What if a new condition arises during case handling?", "Can I supplement my application with another illness?"],
    "15": ["How is my ability to take paid work assessed?", "What is erhvervsevne in the disability supplement?", "How does the Agency evaluate my work capacity?", "What does limited ability to work mean?"],
    "16": ["How much student work counts against the supplement?", "Is there a weekly hours limit for working alongside study?", "Does working 5-6 hours a week disqualify me?", "How many hours can I work and still qualify?"],
    "17": ["Does my previous work history count against me?", "If I worked before my studies, does that disqualify me?", "How does past employment affect the assessment?", "Will previous student jobs hurt my chances?"],
    "18": ["Will the Agency consider an impairment I forgot to list?", "What if my medical records mention a condition I didn't list in the form?", "Does the Agency assess unlisted medical diagnoses?", "Will unmentioned conditions in my journal be evaluated?"],
    "19": ["What factors do not matter in the assessment?", "Does my financial situation or study pace matter?", "Do high grades or lack of jobs affect handicaptillæg?", "What is excluded from the disability assessment?"],
    "20": ["Does receiving SPS affect my handicaptillæg application?", "Can I get handicaptillæg if I already receive SPS?", "Is special educational support connected to the supplement?", "Does having SPS prove I qualify for handicaptillæg?"],
    "21": ["What medical documentation must I attach?", "What is the minimum documentation requirement under § 37?", "Which papers do I need to upload?", "What doctor's statement is required?"],
    "22": ["What other non-mandatory documentation is worth submitting?", "Can I submit SPS or municipal housing statements?", "What extra documents support my application?", "Should I submit documentation of earlier accommodations?"],
    "23": ["What should the medical documentation describe?", "What specific details must the doctor's statement include?", "What content must the medical records contain?", "What clinical details does the Agency look for?"],
    "24": ["What medical documents are not sufficient on their own?", "Can a prescription or diagnosis confirmation suffice?", "Why is a GP referral letter not enough?", "Which documents are rejected as insufficient?"],
    "25": ["Can a statement from a psychologist count on its own?", "Is a psychologist report enough for handicaptillæg?", "Do I need a psychiatrist or is a psychologist okay?", "Can a psychologist statement stand alone?"],
    "26": ["What if my impairment is congenital and I lack recent records?", "How do I document a childhood or congenital disability?", "What if my diagnosis was made many years ago?", "What documentation is needed for congenital conditions?"],
    "27": ["Can the Agency ask for more medical information?", "Why is the Agency requesting extra medical papers?", "Can the Agency contact a specialist or hospital?", "Can supplementary medical records be requested?"],
    "28": ["What if I cannot meet the deadline for extra information?", "Can I get an extension to submit medical documents?", "What happens if my doctor's appointment is after the deadline?", "How do I request more time to send medical papers?"],
    "29": ["Can the Agency request a medical certificate directly from my GP?", "Does the Agency contact my own doctor?", "Will my GP be asked to fill out an attestation?", "Do I pay if the Agency asks my doctor for a statement?"],
    "30": ["Can the Agency contact external specialists or AES?", "What is an advisory opinion from Arbejdsmarkedets Erhvervssikring?", "Can the Agency refer me to a specialist examination?", "Does the Agency cover specialist consultation costs?"],
    "31": ["When will my application be refused outright without assessment?", "What is an afvisning (refusal to process)?", "Why was my application rejected without being reviewed?", "When does an application fail the minimum documentation check?"],
    "32": ["Can I re-apply after being refused for documentation?", "What should I do if my application was refused?", "Can I submit a new application with proper medical papers?", "Is payment backdated if I reapply after a refusal?"],
    "33": ["Can I be denied if my condition is not permanent?", "What happens if my impairment is deemed temporary?", "Why was I denied for lack of permanence?", "Can temporary illness cause a denial?"],
    "34": ["Can I apply for handicaptillæg due to my child's disability?", "Can parents get the supplement for an ill or disabled child?", "Is there a disability supplement for student parents with disabled children?", "Does a child's impairment qualify the parent?"],
    "35": ["When does payment of handicaptillæg begin?", "How much is the disability supplement amount?", "From what date is the supplement paid?", "What are the monthly rates for higher education vs vocational?"],
    "36": ["What is a time-limited handicaptillæg award?", "Why was my supplement granted for a limited period only?", "What does tidsbegrænset mean for the disability supplement?", "How long does a time-limited grant last?"],
    "37": ["Can I get my time-limited handicaptillæg extended?", "How do I apply for an extension before my award expires?", "When should I apply for an extension of my supplement?", "What documentation is needed for an extension?"],
    "38": ["How does the supplement affect my allowed earnings (fribeløb)?", "What is the lower income allowance for handicaptillæg?", "How much money can I earn while getting the disability supplement?", "Does the supplement reduce my annual fribeløb?"],
    "39": ["What if I work more than expected or receive injury compensation?", "Do damage settlements or injury compensation affect the supplement?", "What if my health improves during my studies?", "Does accident compensation reduce my handicaptillæg?"],
    "40": ["How does the Agency check my annual income?", "What happens if I earn more than my reduced fribeløb?", "Can the Agency demand repayment of handicaptillæg?", "How is income verified with the Danish Tax Agency?"],
    "41": ["Can I appeal a decision about handicaptillæg?", "How do I appeal a rejection of the disability supplement?", "Where do I send an appeal for handicaptillæg?", "What is the Appeals Board (Ankenævnet) process?"],
    "42": ["What if I miss the 4-week deadline for appealing?", "Can I appeal after the 4-week deadline has passed?", "Can late appeals be accepted for special reasons?", "What happens if my appeal is sent too late?"],
    "43": ["Can new medical documentation be considered in an appeal?", "If I appeal a refusal, will new records be looked at?", "Can I submit new hospital papers with my appeal?", "Does an appeal against afvisning assess new evidence?"],
}

# Practical FAQs taken from SU_handicaptillaeg_FAQ_Expanded_Questions_Answers.md, keyed by the FAQ number
# used in that file (graph event FAQ_Answer_<n>). Question, answer text and availability are read from
# the file; the citation comes from the <purpose> field of SU_handicaptillaeg_FAQ_AnswerMatching_Expanded.xml.
PRACTICAL_SECTION_TOPIC = {
    "Eligibility and qualifying education": "eligibility_and_education",
    "Impairment and ability to work": "impairment_and_work_capacity",
    "Medical documentation": "medical_documentation",
    "Applying, decisions and help": "applying_decisions_and_help",
    "Payment, work and changes after approval": "payment_work_and_changes",
}

PRACTICAL_FAQS = {
    10: {
        "id": "FAQ_P01",
        "citation": "Guideline sections 3.5 and 4; SU.dk application FAQ.",
        "variants": ["Where do I submit an application for the disability supplement?", "What are the steps to apply for handicaptillæg in minSU?", "How can I apply for the handicap supplement?", "Which portal do I use to apply for handicaptillæg?"],
    },
    17: {
        "id": "FAQ_P02",
        "citation": "Current SU.dk case-status and contact guidance.",
        "variants": ["How do I check the status of my application?", "How can I contact SU about my handicaptillæg case?", "Where can I find out what is happening with my application?", "Who do I contact about my case?"],
    },
    19: {
        "id": "FAQ_P03",
        "citation": "English explanatory FAQ; content key BAS-06. Sources: SU FAQ, “Can an application be approved in advance?”",
        "variants": ["Can I find out beforehand whether I will qualify?", "Is there a pre-approval before I apply?", "Can SU tell me in advance if I am eligible?", "Can I get a binding answer before submitting an application?"],
    },
    28: {
        "id": "FAQ_P04",
        "citation": "English explanatory FAQ; content key DOC-03. Sources: GUIDE §4.1; SU documentation page, “Minimum documentation requirements”.",
        "variants": ["How old can my medical records be?", "Do my medical records need to be from this year?", "Are records older than three years accepted?", "Does the documentation have to be current?"],
    },
    34: {
        "id": "FAQ_P05",
        "citation": "English explanatory FAQ; content key DOC-14. Sources: SU FAQ and documentation page; GUIDE §§4.3 and 7.2.",
        "variants": ["Do I need to write a personal statement?", "What should I put in a personal statement for my application?", "Is a personal statement required for handicaptillæg?", "Is a personal statement part of the minimum documentation?"],
    },
    35: {
        "id": "FAQ_P06",
        "citation": "English explanatory FAQ; content key DOC-REDACT. Sources: SU documentation page, “Sådan skaffer du din dokumentation”.",
        "variants": ["Can I black out parts of my medical records before uploading?", "Is it allowed to cross out sensitive information in my records?", "What if my records contain details about other people or other diagnoses?", "Can I hide traumatic experiences described in my journal?"],
    },
    39: {
        "id": "FAQ_P07",
        "citation": "English explanatory FAQ; content key CASE-04. Sources: SU FAQ, “Can others help me contact the authority?”",
        "variants": ["Can someone apply on my behalf?", "How do I give someone power of attorney for my case?", "Can a relative or helper handle my application?", "Will the authority send letters to my representative?"],
    },
    40: {
        "id": "FAQ_P08",
        "citation": "English explanatory FAQ; content key CASE-02. Sources: SU status page; REPORT, “How long does it take?”",
        "variants": ["How long does it take to get a decision?", "What is the average processing time for handicaptillæg?", "When will I hear back on my application?", "How many months does case handling take?"],
    },
    42: {
        "id": "FAQ_P09",
        "citation": "English explanatory FAQ; content key PAY-05. Sources: SU FAQ, “May I perform voluntary work?”",
        "variants": ["Can I do unpaid volunteer work while receiving the supplement?", "Does voluntary work affect my handicaptillæg?", "Is volunteering allowed with the disability supplement?", "How many hours of voluntary work are allowed?"],
    },
    44: {
        "id": "FAQ_P10",
        "citation": "English explanatory FAQ; content key PAY-08. Sources: SU FAQ, “If I change education or resume after leave”.",
        "variants": ["Do I need to reapply if I switch study programme?", "What if I go from a bachelor's to a master's programme?", "Does the supplement continue after I return from leave?", "Must I apply again for handicaptillæg when I start a new programme?"],
    },
    45: {
        "id": "FAQ_P11",
        "citation": "English explanatory FAQ; content key PAY-09. Sources: SU FAQ, “If I move to a final loan”.",
        "variants": ["How do I get the supplement paid with a final loan (slutlån)?", "What should I do when my SU changes to a final loan?", "Is the disability supplement paid during the final loan period?", "Who do I contact to activate the supplement with my final loan?"],
    },
    46: {
        "id": "FAQ_P12",
        "citation": "English explanatory FAQ; content key PAY-SCHOLARSHIP. Sources: SU FAQ, “Kan jeg modtage legater, når jeg modtager handicaptillæg?”.",
        "variants": ["Do grants or scholarships affect my handicaptillæg?", "Does a scholarship count as income for the supplement?", "Can I apply to increase my income allowance because of a scholarship?", "Can I receive a grant from a foundation and the disability supplement?"],
    },
}

# The source answer for practical FAQ 17 says contact details "are not embedded in this graph". In this
# knowledge base the same sentence would be confusing, so it is reworded.
PRACTICAL_ANSWER_REPLACE = {
    17: ("so they are not embedded in this graph.", "so they are not stored in this chatbot."),
}
PRACTICAL_GAP_NOTES = {
    17: "Answer only points to SU.dk: no contact details or status link are stored. Confirm this is what the chatbot should say.",
}


FOLLOW_UP_MARKER = re.compile(r"^\*\*\s*Follow[\s-]*up\b", re.IGNORECASE)
DETERMINATION_ASK = re.compile(r"^>\s*\*\*\s*Ask the applicant", re.IGNORECASE)
DETERMINATION_BRANCH = re.compile(r"^-\s*\*\*\s*If\s+(yes|no)\b", re.IGNORECASE)
HEADING_ONLY = re.compile(r"^Section\s+\d+(\.\d+)*\.?$")
EDITOR_REFERENCE = re.compile(r"\s*\[reference[^\]]*\]", re.IGNORECASE)
LEAK_PATTERNS = [
    ("determination marker", re.compile(r"Ask the applicant|\*\*|Follow[\s-]*up (question|determination)", re.IGNORECASE)),
    ("if yes/no branch", re.compile(r"(^|\n)\s*-?\s*If (yes|no)\b", re.IGNORECASE)),
    ("authoring note", re.compile(r"\[FAQ:|\[reference|^\s*\]\s*$", re.IGNORECASE | re.MULTILINE)),
    ("stray heading", re.compile(r"(^|\n)Section \d+(\.\d+)*\.?\s*($|\n)")),
    ("em dash (add a language edit to answer_edits.json)", re.compile("\u2014")),
]


def extract_paragraphs_from_docx(docx_path: Path) -> list[str]:
    with zipfile.ZipFile(docx_path) as z:
        tree = ET.fromstring(z.read("word/document.xml"))
        namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        text: list[str] = []
        for p in tree.findall(".//w:p", namespaces):
            p_text = "".join([t.text for t in p.findall(".//w:t", namespaces) if t.text])
            if p_text.strip():
                text.append(p_text.strip())
        return text


def normalise_source(raw: str) -> str:
    """'** Source 6.3.**' -> 'Section 6.3'; 'Section 4.2' stays; '' stays ''."""
    s = raw.replace("**", "").strip()
    s = re.sub(r"^Source:?\s*", "", s, flags=re.IGNORECASE).strip().rstrip(".").strip()
    if re.match(r"^\d", s):
        s = f"Section {s}"
    return s


def parse_raw_faqs(lines: list[str]) -> list[dict]:
    raw_faqs: list[dict] = []
    curr_sec = "Overall eligibility conditions"
    curr = None
    in_faq_block = False

    for line in lines:
        if line.startswith("## "):
            curr_sec = line[3:].strip()
            in_faq_block = False
        elif line.startswith("### FAQ"):
            if curr:
                raw_faqs.append(curr)
            in_faq_block = False
            m = re.match(r"### FAQ\s+(\d+[a-z]?):\s*(.*)", line)
            if not m:
                raise ValueError(f"Cannot read FAQ number from heading: {line!r}")
            raw_title = m.group(2).strip()
            title = re.sub(r"\s*\[alternative.*\]", "", raw_title).strip()
            curr = {
                "num": m.group(1),
                "title": title,
                "topic": TOPIC_MAP.get(curr_sec, "eligibility_and_education"),
                "source": "",
                "answer_lines": [],
                "extra_questions": [],
                "determination_count": 0,
            }
        elif curr is None:
            continue  # preamble before the first FAQ
        elif in_faq_block:
            # Inside an authoring block "[FAQ: question / answer / FAQ: question / answer ... ]".
            if line.strip() == "]":
                in_faq_block = False
            elif line.startswith("FAQ:"):
                curr["extra_questions"].append(line[4:].strip())
        elif line.startswith("[FAQ:"):
            in_faq_block = True
            curr["extra_questions"].append(line[5:].strip())
        elif re.match(r"^\*\*\s*Source", line):
            curr["source"] = normalise_source(line)
        elif FOLLOW_UP_MARKER.match(line):
            continue
        elif DETERMINATION_ASK.match(line):
            curr["determination_count"] += 1
        elif DETERMINATION_BRANCH.match(line):
            continue
        elif HEADING_ONLY.match(line):
            continue
        else:
            cleaned = EDITOR_REFERENCE.sub("", line).strip()
            if cleaned:
                curr["answer_lines"].append(cleaned)

    if curr:
        raw_faqs.append(curr)
    return raw_faqs


def parse_practical_faqs(md_path: Path) -> dict[int, dict]:
    """Reads the practical FAQs listed in PRACTICAL_FAQS from the Expanded Q/A markdown file."""
    if not md_path.exists():
        raise FileNotFoundError(f"Practical FAQ source not found at {md_path}")
    md = md_path.read_text(encoding="utf-8")
    found: dict[int, dict] = {}
    section = ""
    for block in re.split(r"(?m)^(?=#{2,3} )", md):
        if block.startswith("## "):
            section = block[3:].splitlines()[0].strip()
            continue
        m = re.match(
            r"### FAQ (\d+): (.*?)\n\n\*\*Availability:\*\* (.*?)\s*\n\*\*Graph event:\*\* `(.*?)`\n\n(.*)",
            block, re.DOTALL)
        if not m or int(m.group(1)) not in PRACTICAL_FAQS:
            continue
        n = int(m.group(1))
        paragraphs = [re.sub(r"\s*\n\s*", " ", p).strip() for p in re.split(r"\n\s*\n", m.group(5).strip())]
        found[n] = {
            "question": m.group(2).strip(),
            "availability": "suggested" if m.group(3).startswith("Suggested") else "typed_only",
            "event": m.group(4),
            "section": section,
            "answer": "\n\n".join(p for p in paragraphs if p),
        }
    missing = sorted(set(PRACTICAL_FAQS) - set(found))
    if missing:
        raise ValueError(f"Practical FAQs not found in {md_path.name}: {missing}")
    return found


def distinct_variants(canonical: str, variants: list[str]) -> list[str]:
    """Drops blanks, repeats and the canonical question itself (case-insensitive), keeping order."""
    seen = {canonical.strip().casefold()}
    out: list[str] = []
    for v in variants:
        v = v.strip()
        if v and v.casefold() not in seen:
            seen.add(v.casefold())
            out.append(v)
    return out


def guideline_records(raw_faqs: list[dict]) -> list[dict]:
    records = []
    seen_ids: set[str] = set()
    for r in raw_faqs:
        raw_num = r["num"]
        base_id = f"FAQ_{int(raw_num):02d}" if raw_num.isdigit() else f"FAQ_{raw_num}"
        if base_id in seen_ids:  # the docx has a second "FAQ 05"
            final_id, key_num = f"{base_id}b", f"{raw_num}b"
        else:
            final_id, key_num = base_id, raw_num
        seen_ids.add(final_id)

        parsed_answer = "\n\n".join(r["answer_lines"]).strip()
        gap_notes: list[str] = []
        status = "reconciled_guideline"
        if parsed_answer:
            if raw_num in BASE_ANSWERS:
                raise ValueError(
                    f"{final_id}: the docx now has answer text, so BASE_ANSWERS[{raw_num!r}] is obsolete. Remove it.")
            answer_text = parsed_answer
        elif raw_num in BASE_ANSWERS:
            answer_text = BASE_ANSWERS[raw_num]
            status = "drafted_needs_review"
            gap_notes.append(
                "The docx has no plain answer for this FAQ (only the follow-up determination). "
                "This base answer was drafted from the determination text and needs review.")
        else:
            raise ValueError(f"{final_id}: no answer text in the docx and no BASE_ANSWERS entry.")

        if r["source"]:
            citation = f"{CITATION_PREFIX}, {r['source']}"
        else:
            citation = GUIDELINE_CITATION
            gap_notes.append("The docx gives no source section for this FAQ, so the citation is generic.")

        configured = DEFAULT_VARIANTS.get(key_num) or DEFAULT_VARIANTS.get(raw_num)
        if not configured:
            raise ValueError(f"{final_id}: no entry in DEFAULT_VARIANTS.")
        variants = distinct_variants(r["title"], configured + r["extra_questions"])

        dcr_note = None
        if r["determination_count"]:
            dcr_note = (f"The docx lists {r['determination_count']} follow-up determination question(s) for this FAQ. "
                        "They are modelled in the DCR graph, not stored in this record.")
        if raw_num == "33":
            note = ("The docx answer ended with a placeholder pointing to related questions on persistence "
                    "(likely FAQ_09 and FAQ_12). The placeholder was removed and the link is not resolved.")
            dcr_note = f"{dcr_note} {note}" if dcr_note else note

        records.append({
            "id": final_id,
            "canonical_question": r["title"],
            "question_variants": variants,
            "answer_text": answer_text,
            "topic": r["topic"],
            "citation": citation,
            "availability": "suggested" if int(re.sub(r"\D", "", raw_num) or "99") <= 20 else "typed_only",
            "status": status,
            "gap_note": " ".join(gap_notes) or None,
            "dcr_note": dcr_note,
            "embedding": None,
            "updated_at": date.today().isoformat(),
        })
    return records


def practical_records(md_path: Path) -> list[dict]:
    found = parse_practical_faqs(md_path)
    records = []
    for n, cfg in PRACTICAL_FAQS.items():
        item = found[n]
        answer = item["answer"]
        if n in PRACTICAL_ANSWER_REPLACE:
            old, new = PRACTICAL_ANSWER_REPLACE[n]
            if old not in answer:
                raise ValueError(f"{cfg['id']}: expected text not found for rewording: {old!r}")
            answer = answer.replace(old, new)
        topic = PRACTICAL_SECTION_TOPIC.get(item["section"])
        if not topic:
            raise ValueError(f"{cfg['id']}: unknown section {item['section']!r} in {md_path.name}")
        records.append({
            "id": cfg["id"],
            "canonical_question": item["question"],
            "question_variants": distinct_variants(item["question"], cfg["variants"]),
            "answer_text": answer,
            "topic": topic,
            "citation": cfg["citation"],
            "availability": item["availability"],
            "status": "practical_expanded_graph",
            "gap_note": PRACTICAL_GAP_NOTES.get(n),
            "dcr_note": (f"Practical FAQ from {md_path.name} (graph event {item['event']}). "
                         "Not part of the Vejledning mapping in the docx."),
            "embedding": None,
            "updated_at": date.today().isoformat(),
        })
    return records


def validate(records: list[dict]) -> None:
    """Raises ValueError listing every problem found, so a bad build is never written."""
    problems: list[str] = []
    ids = [r["id"] for r in records]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(f"duplicate id {dup}")
    topic_ids = {t["id"] for t in TOPICS_LIST}
    for r in records:
        rid = r["id"]
        answer = r["answer_text"]
        if len(answer.split()) < 15:
            problems.append(f"{rid}: answer is only {len(answer.split())} words")
        for label, pattern in LEAK_PATTERNS:
            if pattern.search(answer):
                problems.append(f"{rid}: answer contains {label}")
        if r["topic"] not in topic_ids:
            problems.append(f"{rid}: unknown topic {r['topic']!r}")
        if r["availability"] not in {"suggested", "typed_only"}:
            problems.append(f"{rid}: bad availability {r['availability']!r}")
        if not 3 <= len(r["question_variants"]) <= 8:
            problems.append(f"{rid}: {len(r['question_variants'])} variants (expected 3-8)")
        folded = [v.casefold() for v in [r["canonical_question"], *r["question_variants"]]]
        if len(set(folded)) != len(folded):
            problems.append(f"{rid}: canonical question and variants are not all distinct")
        if r["id"].startswith("FAQ_P"):
            continue
        if re.match(r"^Vejledning nr 9577, \d", r["citation"]):
            problems.append(f"{rid}: citation {r['citation']!r} lacks 'Section'")
    if problems:
        raise ValueError("FAQ data failed validation:\n  " + "\n  ".join(problems))


def build() -> dict:
    if not DOCX_PATH.exists():
        raise FileNotFoundError(f"Source DOCX not found at {DOCX_PATH}")

    raw_faqs = parse_raw_faqs(extract_paragraphs_from_docx(DOCX_PATH))
    unused = sorted(set(BASE_ANSWERS) - {r["num"] for r in raw_faqs})
    if unused:
        raise ValueError(f"BASE_ANSWERS has entries for FAQs not in the docx: {unused}")

    records = guideline_records(raw_faqs) + practical_records(PRACTICAL_MD_PATH)
    apply_answer_edits(records)
    validate(records)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": date.today().isoformat(),
        "notes": {
            "description": ("FAQ knowledge base: 43 guideline FAQs from Vejledning nr 9577 af 25/06/2025 "
                            "(Question_upmapping_chatbot.docx) plus 12 practical FAQs (ids FAQ_P01..FAQ_P12) "
                            "from SU_handicaptillaeg_FAQ_Expanded_Questions_Answers.md."),
            "determinations": ("Follow-up determination logic ('hvis' rules) is not stored here. "
                               "It is modelled in the DCR process graph."),
            "languages": "English only for now. Danish phrasing variants are to be added.",
            "status_values": {
                "reconciled_guideline": "Answer taken from the docx, with the language edits in answer_edits.json.",
                "drafted_needs_review": "No plain answer in the docx; base answer drafted from the determination text. Needs review.",
                "practical_expanded_graph": "Practical FAQ taken from the Expanded Q/A file, with the language edits in answer_edits.json.",
            },
            "embedding": "Computed by embed_faq_data.py and stored in companion faq_embeddings.npy.",
        },
        "topics": TOPICS_LIST,
        "records": records,
    }


def apply_answer_edits(records: list[dict], edits_path: Path = ANSWER_EDITS_PATH) -> None:
    """Applies the language edits in place. Raises ValueError listing every edit that does not fit."""
    edits = json.loads(edits_path.read_text(encoding="utf-8"))["edits"]
    by_id = {r["id"]: r for r in records}
    problems: list[str] = []
    for i, edit in enumerate(edits, 1):
        record = by_id.get(edit["id"])
        if record is None:
            problems.append(f"edit {i}: unknown id {edit['id']}")
            continue
        count = record["answer_text"].count(edit["old"])
        if count != 1:
            problems.append(f"edit {i} ({edit['id']}): passage found {count} times, expected once: {edit['old'][:60]!r}")
            continue
        record["answer_text"] = record["answer_text"].replace(edit["old"], edit["new"])
    if problems:
        raise ValueError(f"{edits_path.name} does not fit the source text:\n  " + "\n  ".join(problems))


if __name__ == "__main__":
    data = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(data['records'])} FAQ records to {OUTPUT_PATH}")
    print("Next: python faq_search/embed_faq_data.py")
