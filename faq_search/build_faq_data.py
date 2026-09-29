#!/usr/bin/env python3
"""
build_faq_data.py -- Reconciles and builds faq_qa_records.json from the authoritative
guideline mapping in Question_upmapping_chatbot.docx (Vejledning nr 9577 af 25/06/2025).

This script:
1. Extracts canonical questions, sources, and answer text directly from Question_upmapping_chatbot.docx.
2. Decouples follow-up determinations ('hvis' exception branches), preserving them exclusively
   for the DCR process graph rather than embedding them into monolithic text answers.
3. Provides high-quality multilingual phrasing variants (3-5 per FAQ) for robust vector retrieval.
4. Categorizes records into the 5 core thematic topics.
5. Saves the clean records schema to faq_search/data/faq_qa_records.json.
"""
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
DOCX_PATH = PROJECT_ROOT / "Question_upmapping_chatbot.docx"
OUTPUT_PATH = HERE / "data" / "faq_qa_records.json"

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

# Curated answer text overrides for specific FAQs where docx text is fragmented or needs clean phrasing
CUSTOM_ANSWERS = {
    "25": (
        "As a starting point, a psychologist's statement cannot stand alone as medical documentation "
        "for your application. However, it can be included as part of the overall assessment if it is "
        "backed up by a statement from a psychiatric specialist or by other medical records."
    ),
    "42": (
        "The standard deadline for appealing a decision is 4 weeks from the day you received it. "
        "If you miss this deadline, the Appeals Board can in special, excusable cases disregard the delay "
        "up to six months after you received the decision. The Agency cannot make this exception for you; "
        "only the Appeals Board decides whether a delay is excusable."
    ),
    "43": (
        "No. An appeal against a refusal-to-process decision only examines whether the Agency was entitled "
        "to refuse the application in the first place, not your substantive entitlement to handicaptillæg. "
        "New medical documentation submitted with the appeal will not be assessed; to have new documentation "
        "considered, you must submit a new application."
    ),
}

# Curated Danish and English phrasing variants for each FAQ
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


def parse_raw_faqs(lines: list[str]) -> list[dict]:
    raw_faqs: list[dict] = []
    curr_sec = "Overall eligibility conditions"
    curr = None

    for line in lines:
        if line.startswith("## "):
            curr_sec = line[3:].strip()
        elif line.startswith("### FAQ"):
            if curr:
                raw_faqs.append(curr)
            m = re.match(r"### FAQ\s+(\d+[a-z]?):\s*(.*)", line)
            num = m.group(1) if m else str(len(raw_faqs) + 1)
            raw_title = m.group(2).strip() if m else line
            title = re.sub(r"\s*\[alternative.*\]", "", raw_title).strip()
            curr = {
                "num": num,
                "title": title,
                "topic": TOPIC_MAP.get(curr_sec, "eligibility_and_education"),
                "source": "",
                "pre_det_lines": [],
                "in_det": False,
            }
        elif curr:
            if line.startswith("**Source:**") or line.startswith("** Source"):
                src = re.sub(r"^\*\*\s*Source:?\s*", "", line).replace("**", "").strip()
                curr["source"] = src
            elif line.startswith("**Follow-up determination**"):
                curr["in_det"] = True
            elif not curr["in_det"]:
                curr["pre_det_lines"].append(line)

    if curr:
        raw_faqs.append(curr)
    return raw_faqs


def build():
    if not DOCX_PATH.exists():
        raise FileNotFoundError(f"Source DOCX not found at {DOCX_PATH}")

    lines = extract_paragraphs_from_docx(DOCX_PATH)
    raw_faqs = parse_raw_faqs(lines)

    final_records = []
    seen_ids = set()

    for r in raw_faqs:
        raw_num = r["num"]
        base_id = f"FAQ_{int(raw_num):02d}" if raw_num.isdigit() else f"FAQ_{raw_num}"
        if base_id in seen_ids:
            final_id = f"{base_id}b"
            key_num = f"{raw_num}b"
        else:
            final_id = base_id
            key_num = raw_num
        seen_ids.add(final_id)

        if raw_num in CUSTOM_ANSWERS:
            answer_text = CUSTOM_ANSWERS[raw_num]
        else:
            joined = "\n\n".join(r["pre_det_lines"]).strip()
            answer_text = joined if joined else "Please consult the official guidance for details on this condition."

        src = r["source"].strip()
        citation = f"Vejledning nr 9577, {src}" if src else "Vejledning nr 9577 af 25/06/2025"

        variants = DEFAULT_VARIANTS.get(key_num) or DEFAULT_VARIANTS.get(raw_num)
        if not variants:
            variants = [r["title"], f"How does {r['title'].lower()} work?", f"Rules regarding {r['title'].lower()}"]

        final_records.append({
            "id": final_id,
            "canonical_question": r["title"],
            "question_variants": variants,
            "answer_text": answer_text,
            "topic": r["topic"],
            "citation": citation,
            "availability": "suggested" if int(re.sub(r"\D", "", raw_num) or "99") <= 20 else "typed_only",
            "status": "reconciled_guideline",
            "gap_note": None,
            "dcr_note": None,
            "embedding": None,
            "updated_at": date.today().isoformat(),
        })

    out = {
        "schema_version": 3,
        "generated_at": date.today().isoformat(),
        "notes": {
            "description": "Reconciled authoritative FAQ knowledge base aligned with Vejledning nr 9577 af 25/06/2025 and Question_upmapping_chatbot.docx.",
            "determinations": "Follow-up determination logic ('hvis' rules) is decoupled from plain text blocks and modeled in the DCR process graph.",
            "embedding": "Computed by embed_faq_data.py and stored in companion faq_embeddings.npy.",
        },
        "topics": TOPICS_LIST,
        "records": final_records,
    }
    return out


if __name__ == "__main__":
    data = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Successfully generated {len(data['records'])} reconciled FAQ records to {OUTPUT_PATH}")
