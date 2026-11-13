# Help panel follow-up eval

147 runs (49 cases x 3). DECISIONS_ENABLED=1, context min 0.7, relevance min 0.5, search single/min/margin 0.8/0.5/0.12. Latency median 1.1s, max 42.1s.

## Verdicts

| verdict | runs |
|---|---|
| correct | 48 |
| WRONG | 33 |
| partial | 32 |
| missed | 15 |
| shown_options | 12 |
| options_wrong | 7 |

**WRONG = an FAQ was answered that does not answer the question. This is the number to drive to zero.**

## By group

| group | WRONG | correct | missed | options_wrong | partial | shown_options |
|---|---|---|---|---|---|---|
| A | 2 | 0 | 0 | 0 | 0 | 7 |
| C | 1 | 10 | 0 | 1 | 6 | 0 |
| F | 9 | 12 | 8 | 3 | 10 | 0 |
| M | 0 | 0 | 0 | 0 | 6 | 0 |
| N | 16 | 6 | 0 | 0 | 0 | 2 |
| O | 3 | 3 | 0 | 0 | 0 | 3 |
| S | 0 | 4 | 5 | 0 | 0 | 0 |
| T | 0 | 9 | 0 | 0 | 3 | 0 |
| V | 2 | 4 | 2 | 3 | 7 | 0 |

## Contextual classifier (DECISIONS_CONTEXT_MIN)

| DECISIONS_CONTEXT_MIN | follow-ups caught | self-contained left alone | accuracy |
|---|---|---|---|
| 0.3 | 84/99 | 33/39 | 0.85 |
| 0.4 | 81/99 | 33/39 | 0.83 |
| 0.5 | 78/99 | 33/39 | 0.80 |
| 0.6 | 78/99 | 33/39 | 0.80 |
| 0.7 (current) | 78/99 | 33/39 | 0.80 |
| 0.8 | 78/99 | 36/39 | 0.83 |
| 0.9 | 72/99 | 36/39 | 0.78 |

## Relevance check (DECISIONS_RELEVANT_MIN)

| DECISIONS_RELEVANT_MIN | expected FAQs kept | other FAQs kept | precision |
|---|---|---|---|
| 0.2 | 86/86 | 178 | 0.33 |
| 0.3 | 86/86 | 163 | 0.35 |
| 0.4 | 86/86 | 157 | 0.35 |
| 0.5 (current) | 86/86 | 151 | 0.36 |
| 0.6 | 86/86 | 132 | 0.39 |
| 0.7 | 86/86 | 117 | 0.42 |
| 0.8 | 83/86 | 88 | 0.49 |

## Cases

| case | verdict | outcome | ctx | understood as | searches (query: kept) |
|---|---|---|---|---|---|
| f01 | WRONG | answered FAQ_01 | 0.93 | How is my ability to work assessed for handicaptillæg (the SU disability supplement)? | How is my ability to work assessed for handicaptil: FAQ_01 |
| f01 | missed | no_match  | 0.93 | How is my ability to work assessed for the handicaptillæg application? | How is my ability to work assessed for the handica: - |
| f01 | WRONG | answered FAQ_P09 | 0.93 | How is my ability to work assessed in relation to my application for handicaptillæg? | How is my ability to work assessed in relation to : FAQ_P09 |
| f02 | correct | answered FAQ_P09 | 1.0 | Does unpaid volunteering count towards the work hours when applying for handicaptillæg? | Does unpaid volunteering count towards the work ho: FAQ_P09 |
| f02 | correct | answered FAQ_P09 | 1.0 | Does unpaid volunteering count towards the hours I plan to work alongside my studies? | Does unpaid volunteering count towards the hours I: FAQ_P09 |
| f02 | correct | answered FAQ_P09 | 1.0 | Does unpaid volunteering count towards the hours worked when applying for handicaptillæg? | Does unpaid volunteering count towards the hours w: FAQ_P09 |
| f03 | correct | answered FAQ_38 | 0.89 | How much am I allowed to earn while receiving handicaptillæg? | How much am I allowed to earn while receiving hand: FAQ_38 |
| f03 | partial | options FAQ_38,FAQ_P12 | 0.89 | How much money am I allowed to earn if I work besides my studies and still qualify for handicaptillæg? | How much money am I allowed to earn if I work besi: FAQ_38,FAQ_P12 |
| f03 | correct | answered FAQ_38 | 0.89 | How much am I allowed to earn while receiving the handicaptillæg? | How much am I allowed to earn while receiving the : FAQ_38 |
| f04 | missed | no_match  | 1.0 | Is there an age limit for the medical records I attach for my handicaptillæg application? | Is there an age limit for the medical records I at: - |
| f04 | missed | no_match  | 1.0 | Is there an age limit for medical records that I attach to my handicaptillæg application? | Is there an age limit for medical records that I a: - |
| f04 | missed | no_match  | 1.0 | Is there an age limit on the medical records I can attach for my handicaptillæg application? | Is there an age limit on the medical records I can: - |
| f05 | partial | options FAQ_25,FAQ_P05 | 1.0 | Is a note from my psychologist sufficient as medical documentation for my impairment when applying for handicaptillæg? | Is a note from my psychologist sufficient as medic: FAQ_25,FAQ_P05 |
| f05 | partial | options FAQ_25,FAQ_P05 | 1.0 | Is a note from my psychologist enough as medical documentation for the handicaptillæg application? | Is a note from my psychologist enough as medical d: FAQ_25,FAQ_P05 |
| f05 | partial | options FAQ_25,FAQ_P05 | 1.0 | Is a note from my psychologist enough as medical documentation for handicaptillæg application? | Is a note from my psychologist enough as medical d: FAQ_25,FAQ_P05 |
| f06 | correct | answered FAQ_P06 | 0.86 | Can I black out parts of my medical records before submitting them for the handicaptillæg application? | Can I black out parts of my medical records before: FAQ_P06 |
| f06 | correct | answered FAQ_P06 | 0.86 | Can I black out parts of medical records before attaching them to my handicaptillæg application? | Can I black out parts of medical records before at: FAQ_P06 |
| f06 | correct | answered FAQ_P06 | 0.86 | Can I black out parts of my medical records when submitting them for the SU disability supplement application? | Can I black out parts of my medical records when s: FAQ_P06 |
| f07 | correct | answered FAQ_37 | 0.96 | Can I get my time-limited handicaptillæg extended? | Can I get my time-limited handicaptillæg extended?: FAQ_37 |
| f07 | correct | answered FAQ_37 | 0.96 | Can I get my time-limited handicaptillæg extended? | Can I get my time-limited handicaptillæg extended?: FAQ_37 |
| f07 | partial | options FAQ_37,FAQ_36 | 0.96 | Can I get my time-limited handicap-stipend extended? | Can I get my time-limited handicap-stipend extende: FAQ_37,FAQ_36 |
| f08 | WRONG | answered FAQ_32 | 0.47 | - | and if they say no, can I appeal?: FAQ_41,FAQ_32,FAQ_42; Review and send demo application and if they say n: FAQ_32 |
| f08 | WRONG | answered FAQ_32 | 0.47 | - | and if they say no, can I appeal?: FAQ_41,FAQ_32,FAQ_42; Review and send demo application and if they say n: FAQ_32 |
| f08 | WRONG | answered FAQ_32 | 0.47 | - | and if they say no, can I appeal?: FAQ_41,FAQ_32,FAQ_42; Review and send demo application and if they say n: FAQ_32 |
| f09 | missed | no_match  | 0.96 | What happens if I am late submitting my application for handicaptillæg? | What happens if I am late submitting my applicatio: - |
| f09 | missed | no_match  | 0.96 | What happens if I am late submitting my application for the handicaptillæg? | What happens if I am late submitting my applicatio: - |
| f09 | missed | no_match  | 0.96 | What happens if I submit my handicaptillæg application late? | What happens if I submit my handicaptillæg applica: - |
| f10 | WRONG | answered FAQ_01 | 0.99 | Do I need to write a personal statement about my congenital impairment when applying for the SU disability supplement? | Do I need to write a personal statement about my c: FAQ_01 |
| f10 | options_wrong | options FAQ_P01,FAQ_03 | 0.99 | Should I write a personal statement about my congenital impairment when applying for the disability supplement? | Should I write a personal statement about my conge: FAQ_P01,FAQ_03 |
| f10 | correct | answered FAQ_P05 | 0.99 | Do I need to write a personal statement for my congenital impairment when applying for handicaptillæg? | Do I need to write a personal statement for my con: FAQ_P05 |
| f11 | WRONG | answered FAQ_03 | 0.98 | Can I apply for handicaptillæg if I have two types of functional impairments? | Can I apply for handicaptillæg if I have two types: FAQ_03 |
| f11 | options_wrong | options FAQ_03,FAQ_01 | 0.98 | Can I apply for the disability supplement if I have two different types of functional impairments? | Can I apply for the disability supplement if I hav: FAQ_03,FAQ_01 |
| f11 | WRONG | answered FAQ_03 | 0.98 | Can I select two types of functional impairments for my handicaptillæg application? | Can I select two types of functional impairments f: FAQ_03 |
| f12 | partial | options FAQ_08,FAQ_09,FAQ_01 | 0.97 | How long does an impairment need to have lasted to be considered permanent for the SU disability supplement? | How long does an impairment need to have lasted to: FAQ_08,FAQ_09,FAQ_01 |
| f12 | partial | options FAQ_09,FAQ_08,FAQ_33 | 0.97 | How long does an impairment need to have lasted to be considered permanent for the handicaptillæg? | How long does an impairment need to have lasted to: FAQ_09,FAQ_08,FAQ_33 |
| f12 | partial | options FAQ_09,FAQ_03 | 0.97 | How long does a condition need to have lasted to be considered permanent for the handicaptillæg? | How long does a condition need to have lasted to b: FAQ_09,FAQ_03 |
| f13 | options_wrong | options FAQ_03,FAQ_P05 | 0.95 | What should the medical records for handicaptillæg include or describe? | What should the medical records for handicaptillæg: FAQ_P05,FAQ_03 |
| f13 | WRONG | answered FAQ_P01 | 0.95 | What information should the medical records themselves include when applying for the SU disability supplement? | What information should the medical records themse: FAQ_P01 |
| f13 | missed | same_faq  | 0.95 | What details should the medical records include for the handicaptillæg application? | What details should the medical records include fo: FAQ_P05 |
| f14 | correct | answered FAQ_04 | 0.98 | Do I need to receive ordinary SU before I can get the handicaptillæg disability supplement? | Do I need to receive ordinary SU before I can get : FAQ_04 |
| f14 | partial | options FAQ_04,FAQ_01,FAQ_03 | 0.98 | Do I need to receive ordinary SU before I can get the disability supplement (handicaptillæg)? | Do I need to receive ordinary SU before I can get : FAQ_04,FAQ_03,FAQ_01 |
| f14 | partial | options FAQ_04,FAQ_01,FAQ_03 | 0.98 | Do I need to receive ordinary SU before I can get the disability supplement (handicaptillæg)? | Do I need to receive ordinary SU before I can get : FAQ_04,FAQ_03,FAQ_01 |
| n01 | correct | no_match  | 0.98 | Does the number of hours I worked before my studies matter for the handicaptillæg application? | Does the number of hours I worked before my studie: - |
| n01 | WRONG | answered FAQ_P09 | 0.98 | Does the number of hours I worked in the last three years matter for my handicaptillæg application? | Does the number of hours I worked in the last thre: FAQ_P09 |
| n01 | WRONG | answered FAQ_P09 | 0.98 | Does the number of hours I worked in the last three years matter for my application for handicaptillæg? | Does the number of hours I worked in the last thre: FAQ_P09 |
| n02 | shown_options | options FAQ_06,FAQ_01,FAQ_03 | 0.94 | Is the eligibility for handicaptillæg different for master's students compared to other students? | Is the eligibility for handicaptillæg different fo: FAQ_03,FAQ_01,FAQ_06 |
| n02 | correct | no_match  | 0.94 | Is the assessment of planned work while studying different for master's students when applying for handicaptillæg? | Is the assessment of planned work while studying d: - |
| n02 | shown_options | options FAQ_06,FAQ_03 | 0.94 | Is the rules for planning to work and qualifying for handicaptillæg different for master's students? | Is the rules for planning to work and qualifying f: FAQ_03,FAQ_06 |
| n03 | WRONG | answered FAQ_21 | 0.01 | Do the medical records I attach need to be translated into Danish? | do they have to be translated into Danish?: -; Attach medical records documenting each impairment: -; Do the medical records I attach need to be transla: FAQ_21 |
| n03 | correct | no_match  | 0.01 | Do medical records for the SU disability supplement need to be translated into Danish? | do they have to be translated into Danish?: -; Attach medical records documenting each impairment: -; Do medical records for the SU disability supplemen: - |
| n03 | WRONG | answered FAQ_P01 | 0.01 | Do medical records need to be translated into Danish for the SU disability supplement application? | do they have to be translated into Danish?: -; Attach medical records documenting each impairment: -; Do medical records need to be translated into Dani: FAQ_P01 |
| n04 | WRONG | answered FAQ_P08 | 0.93 | Will applying early for the handicaptillæg make the process go faster? | Will applying early for the handicaptillæg make th: FAQ_P08 |
| n04 | WRONG | answered FAQ_P08 | 0.93 | Will applying for the time-limited handicaptillæg early make the process faster? | Will applying for the time-limited handicaptillæg : FAQ_P08 |
| n04 | WRONG | answered FAQ_P08 | 0.93 | Will applying early make the processing of my handicaptillæg application faster? | Will applying early make the processing of my hand: FAQ_P08 |
| n05 | WRONG | answered FAQ_P08 | 0.0 | - | can I pay to have it processed faster?: FAQ_P08 |
| n05 | WRONG | answered FAQ_P08 | 0.0 | - | can I pay to have it processed faster?: FAQ_P08 |
| n05 | WRONG | answered FAQ_P08 | 0.0 | - | can I pay to have it processed faster?: FAQ_P08 |
| n06 | correct | no_match  | 0.31 | Will I receive a text message about my application in addition to emails? | will you also send me a text message?: -; What email address should we use to contact you ab: -; Will I receive a text message about my application: - |
| n06 | WRONG | answered FAQ_P02 | 0.31 | Will I also receive a text message about my application status? | will you also send me a text message?: -; What email address should we use to contact you ab: -; Will I also receive a text message about my applic: FAQ_P02 |
| n06 | correct | no_match  | 0.31 | Will I receive a text message to follow up on my SU disability supplement application? | will you also send me a text message?: -; What email address should we use to contact you ab: -; Will I receive a text message to follow up on my S: - |
| n07 | WRONG | answered FAQ_P05 | 0.03 | How many pages should my personal statement be when describing how my impairment affects my ability to work alongside my studies? | how many pages should it be?: -; Attach your personal statement describing how your: -; How many pages should my personal statement be whe: FAQ_P05 |
| n07 | WRONG | answered FAQ_P05 | 0.03 | How long should the personal statement be when describing how my impairment affects my ability to work alongside my studies? | how many pages should it be?: -; Attach your personal statement describing how your: -; How long should the personal statement be when des: FAQ_P05 |
| n07 | WRONG | answered FAQ_P05 | 0.03 | How many pages should my personal statement be when describing how my impairment affects my ability to work alongside my studies for the handicaptillæg application? | how many pages should it be?: -; Attach your personal statement describing how your: -; How many pages should my personal statement be whe: FAQ_P05 |
| n08 | WRONG | answered FAQ_15 | 0.96 | Does it count as paid work if I am paid in gift cards instead of money while studying? | Does it count as paid work if I am paid in gift ca: FAQ_15 |
| n08 | WRONG | answered FAQ_38 | 0.96 | If I get paid in gift cards instead of money for work alongside my studies, how does that affect my disability supplement application? | If I get paid in gift cards instead of money for w: FAQ_38 |
| n08 | correct | no_match  | 0.96 | Does it count as planned paid work if I am paid in gift cards instead of money? | Does it count as planned paid work if I am paid in: - |
| s01 | missed | no_match  | 0.93 | Will the Agency contact my previous employers as part of the assessment for the disability supplement? | Will the Agency contact my previous employers as p: - |
| s01 | correct | same_faq  | 0.93 | Will the Agency contact my old employers about my previous work when assessing my application? | Will the Agency contact my old employers about my : FAQ_17 |
| s01 | missed | no_match  | 0.93 | Will the Agency contact my previous employers as part of the assessment for the SU disability supplement? | Will the Agency contact my previous employers as p: - |
| s02 | missed | options FAQ_P01,FAQ_03 | 1.0 | Is a medical record from my GP sufficient as documentation for my handicap supplement application? | Is a medical record from my GP sufficient as docum: FAQ_P01,FAQ_03 |
| s02 | missed | options FAQ_P05,FAQ_25 | 1.0 | Is a record from my GP enough as medical documentation for my handicaptillæg application? | Is a record from my GP enough as medical documenta: FAQ_25,FAQ_P05 |
| s02 | missed | options FAQ_P05,FAQ_25 | 1.0 | Is a medical record from my GP alone enough documentation for my handicaptillæg application? | Is a medical record from my GP alone enough docume: FAQ_25,FAQ_P05 |
| s03 | correct | same_faq  | 1.0 | How early can I apply for the time-limited handicaptillæg? | How early can I apply for the time-limited handica: FAQ_37 |
| s03 | correct | same_faq  | 1.0 | How early can I apply for the time-limited handicaptillæg? | How early can I apply for the time-limited handica: FAQ_37 |
| s03 | correct | same_faq  | 1.0 | How early can I apply for the time-limited handicaptillæg? | How early can I apply for the time-limited handica: FAQ_37 |
| c01 | WRONG | answered FAQ_01 | 0.95 | Does work I did before my studies count against me for the SU disability supplement? | Does work I did before my studies count against me: FAQ_01 |
| c01 | options_wrong | options FAQ_01,FAQ_03 | 0.95 | Does the work I did before starting my studies affect my eligibility for the SU disability supplement? | Does the work I did before starting my studies aff: FAQ_03,FAQ_01 |
| c01 | correct | answered FAQ_17 | 0.95 | Does work I did before my studies count against me when applying for handicaptillæg? | Does work I did before my studies count against me: FAQ_17 |
| c02 | correct | answered FAQ_P06 | 0.01 | - | May I black out sensitive details in my medical re: FAQ_P06 |
| c02 | correct | answered FAQ_P06 | 0.01 | - | May I black out sensitive details in my medical re: FAQ_P06 |
| c02 | correct | answered FAQ_P06 | 0.01 | - | May I black out sensitive details in my medical re: FAQ_P06 |
| c03 | partial | options FAQ_P05,FAQ_07 | 0.73 | What should I include in my personal statement about how my impairment affects my ability to work during my studies? | What should I include in my personal statement abo: FAQ_P05,FAQ_07 |
| c03 | partial | options FAQ_15,FAQ_P05 | 0.73 | What should I include in my personal statement about how my impairment affects my ability to take paid work alongside my studies? | What should I include in my personal statement abo: FAQ_P05,FAQ_15 |
| c03 | partial | options FAQ_P05,FAQ_07 | 0.73 | What should I include in my personal statement to describe how my impairment affects my ability to work during my studies? | What should I include in my personal statement to : FAQ_P05,FAQ_07 |
| c04 | partial | options FAQ_16,FAQ_P09 | 0.0 | - | how many hours a week can I work and still get the: FAQ_16,FAQ_P09 |
| c04 | partial | options FAQ_16,FAQ_P09 | 0.0 | - | how many hours a week can I work and still get the: FAQ_16,FAQ_P09 |
| c04 | partial | options FAQ_16,FAQ_P09 | 0.0 | - | how many hours a week can I work and still get the: FAQ_16,FAQ_P09 |
| c05 | correct | answered FAQ_26 | 0.01 | - | I was born with my condition and only have old rec: FAQ_26 |
| c05 | correct | answered FAQ_26 | 0.01 | - | I was born with my condition and only have old rec: FAQ_26 |
| c05 | correct | answered FAQ_26 | 0.01 | - | I was born with my condition and only have old rec: FAQ_26 |
| c06 | correct | answered FAQ_P08 | 0.0 | - | how long does it take before I get a decision?: FAQ_P08 |
| c06 | correct | answered FAQ_P08 | 0.0 | - | how long does it take before I get a decision?: FAQ_P08 |
| c06 | correct | answered FAQ_P08 | 0.0 | - | how long does it take before I get a decision?: FAQ_P08 |
| t01 | correct | answered FAQ_P07 | 0.0 | - | Can someone else handle my application for me?: FAQ_P07; Did you have work in the last three years? Can som: FAQ_P07 |
| t01 | correct | answered FAQ_P07 | 0.0 | - | Can someone else handle my application for me?: FAQ_P07; Did you have work in the last three years? Can som: FAQ_P07 |
| t01 | correct | answered FAQ_P07 | 0.0 | - | Can someone else handle my application for me?: FAQ_P07; Did you have work in the last three years? Can som: FAQ_P07 |
| t02 | partial | options FAQ_03,FAQ_05b | 0.0 | - | Can I get handicaptillæg if I'm not a Danish citiz: FAQ_05b; Attach medical records documenting each impairment: FAQ_05b,FAQ_03 |
| t02 | partial | options FAQ_03,FAQ_05b | 0.0 | - | Can I get handicaptillæg if I'm not a Danish citiz: FAQ_05b; Attach medical records documenting each impairment: FAQ_05b,FAQ_03 |
| t02 | partial | options FAQ_03,FAQ_05b | 0.0 | - | Can I get handicaptillæg if I'm not a Danish citiz: FAQ_05b; Attach medical records documenting each impairment: FAQ_05b,FAQ_03 |
| t03 | correct | answered FAQ_P12 | 0.0 | - | Can I receive a scholarship while getting the supp: FAQ_P12; Do you plan to work besides your studies? Can I re: FAQ_P12 |
| t03 | correct | answered FAQ_P12 | 0.0 | - | Can I receive a scholarship while getting the supp: FAQ_P12; Do you plan to work besides your studies? Can I re: FAQ_P12 |
| t03 | correct | answered FAQ_P12 | 0.0 | - | Can I receive a scholarship while getting the supp: FAQ_P12; Do you plan to work besides your studies? Can I re: FAQ_P12 |
| t04 | correct | answered FAQ_34 | 0.0 | - | can I apply because of my child's disability?: FAQ_34; Attach your personal statement describing how your: FAQ_34 |
| t04 | correct | answered FAQ_34 | 0.0 | - | can I apply because of my child's disability?: FAQ_34; Attach your personal statement describing how your: FAQ_34 |
| t04 | correct | answered FAQ_34 | 0.0 | - | can I apply because of my child's disability?: FAQ_34; Attach your personal statement describing how your: FAQ_34 |
| v01 | partial | options FAQ_33,FAQ_08,FAQ_03 | 1.0 | What does it mean that my impairment must be per definition permanent already upon first manifestation for the handicaptillæg application? | What does it mean that my impairment must be per d: FAQ_08,FAQ_03,FAQ_33 |
| v01 | partial | options FAQ_08,FAQ_33,FAQ_07 | 1.0 | What does it mean if my impairment is per definition permanent already upon first manifestation? | What does it mean if my impairment is per definiti: FAQ_08,FAQ_33,FAQ_07 |
| v01 | partial | options FAQ_08,FAQ_33,FAQ_07 | 1.0 | What does it mean if my impairment is permanent by definition from the first time it appeared? | What does it mean if my impairment is permanent by: FAQ_08,FAQ_33,FAQ_07 |
| v02 | correct | answered FAQ_09 | 0.96 | What if my symptoms or effects from my disability have lasted less than a year for the SU handicaptillæg? | What if my symptoms or effects from my disability : FAQ_09 |
| v02 | partial | options FAQ_09,FAQ_08 | 0.96 | What if my symptoms or effects have not lasted for a full year yet? | What if my symptoms or effects have not lasted for: FAQ_09,FAQ_08 |
| v02 | options_wrong | options FAQ_01,FAQ_08 | 0.96 | What if my symptoms or effects have lasted less than a full year for the SU disability supplement? | What if my symptoms or effects have lasted less th: FAQ_08,FAQ_01 |
| v03 | options_wrong | options FAQ_01,FAQ_03 | 0.98 | How does my answer about planning to work alongside my studies affect my application for the SU disability supplement? | How does my answer about planning to work alongsid: FAQ_01,FAQ_03 |
| v03 | WRONG | answered FAQ_01 | 0.98 | How does my answer about planning to work besides my studies affect my application for the SU disability supplement? | How does my answer about planning to work besides : FAQ_01 |
| v03 | options_wrong | options FAQ_01,FAQ_P09 | 0.98 | How does my answer to whether I plan to work besides my studies affect my application for the SU disability supplement? | How does my answer to whether I plan to work besid: FAQ_01,FAQ_P09 |
| v04 | WRONG | answered FAQ_08 | 1.0 | What types of medical records count as documentation for my impairments when applying for the SU disability supplement? | What types of medical records count as documentati: FAQ_08 |
| v04 | missed | no_match  | 1.0 | What types of medical records count as documentation for the handicaptillæg application? | What types of medical records count as documentati: - |
| v04 | missed | no_match  | 1.0 | What types of medical records are accepted as documentation for impairments when applying for handicaptillæg? | What types of medical records are accepted as docu: - |
| v05 | partial | options FAQ_36,FAQ_37,FAQ_01 | 1.0 | What is a time-limited handicap-stipend (handicaptillæg)? | What is a time-limited handicap-stipend (handicapt: FAQ_36,FAQ_37,FAQ_01 |
| v05 | partial | options FAQ_36,FAQ_37,FAQ_02 | 1.0 | What is a time-limited handicap-stipend? | What is a time-limited handicap-stipend?: FAQ_36,FAQ_37,FAQ_02 |
| v05 | partial | options FAQ_36,FAQ_37,FAQ_01 | 1.0 | What is a time-limited handicap-stipend (handicaptillæg)? | What is a time-limited handicap-stipend (handicapt: FAQ_36,FAQ_37,FAQ_01 |
| v06 | correct | no_match  | 0.14 | Why am I being asked to agree to continue the demonstration using fictional information? | why are you asking me this?: -; Do you agree to continue this demonstration using : -; Why am I being asked to agree to continue the demo: - |
| v06 | correct | no_match  | 0.14 | Why am I being asked to agree to use fictional information in this demonstration? | why are you asking me this?: -; Do you agree to continue this demonstration using : -; Why am I being asked to agree to use fictional inf: - |
| v06 | correct | no_match  | 0.14 | Why do you ask if I agree to continue the demonstration using fictional information? | why are you asking me this?: -; Do you agree to continue this demonstration using : -; Why do you ask if I agree to continue the demonstr: - |
| a01 | shown_options | options FAQ_01,FAQ_03 | 0.14 | Does it matter that I worked for 4 years at a supermarket when applying for the SU disability supplement? | yes I worked 4 years at a supermarket: -; Did you have work in the last three years? yes I w: -; Does it matter that I worked for 4 years at a supe: FAQ_01,FAQ_03 |
| a01 | WRONG | answered FAQ_17 | 0.14 | Does work experience from four years ago count when applying for handicaptillæg if the question is about work in the last three years? | yes I worked 4 years at a supermarket: -; Did you have work in the last three years? yes I w: -; Does work experience from four years ago count whe: FAQ_17 |
| a01 | WRONG | answered FAQ_P01 | 0.14 | Does it matter if I worked 4 years at a supermarket when applying for the SU handicaptillæg and answering whether I had work in the last three years? | yes I worked 4 years at a supermarket: -; Did you have work in the last three years? yes I w: -; Does it matter if I worked 4 years at a supermarke: FAQ_P01 |
| a02 | shown_options | options FAQ_16,FAQ_P09 | 0.0 | - | about 10 hours a week: FAQ_P09,FAQ_16; How many hours did you work per week on average in: FAQ_P09,FAQ_16 |
| a02 | shown_options | options FAQ_16,FAQ_P09 | 0.0 | - | about 10 hours a week: FAQ_P09,FAQ_16; How many hours did you work per week on average in: FAQ_P09,FAQ_16 |
| a02 | shown_options | options FAQ_16,FAQ_P09 | 0.0 | - | about 10 hours a week: FAQ_P09,FAQ_16; How many hours did you work per week on average in: FAQ_P09,FAQ_16 |
| a03 | shown_options | options FAQ_08,FAQ_33,FAQ_07 | 0.0 | - | it's a physical impairment, I use a wheelchair: FAQ_07,FAQ_33,FAQ_08 |
| a03 | shown_options | options FAQ_08,FAQ_33,FAQ_07 | 0.0 | - | it's a physical impairment, I use a wheelchair: FAQ_07,FAQ_33,FAQ_08 |
| a03 | shown_options | options FAQ_08,FAQ_33,FAQ_07 | 0.0 | - | it's a physical impairment, I use a wheelchair: FAQ_07,FAQ_33,FAQ_08 |
| o01 | shown_options | options FAQ_03,FAQ_07,FAQ_11 | 0.12 | - | will I get the supplement with my condition?: FAQ_03,FAQ_02; What type of functional impairment do you have? Us: FAQ_03,FAQ_11,FAQ_07 |
| o01 | shown_options | options FAQ_03,FAQ_07,FAQ_11 | 0.12 | - | will I get the supplement with my condition?: FAQ_03,FAQ_02; What type of functional impairment do you have? Us: FAQ_03,FAQ_11,FAQ_07 |
| o01 | shown_options | options FAQ_03,FAQ_07,FAQ_11 | 0.12 | - | will I get the supplement with my condition?: FAQ_03,FAQ_02; What type of functional impairment do you have? Us: FAQ_03,FAQ_11,FAQ_07 |
| o02 | correct | no_match  | 0.0 | - | how do I apply for housing benefit?: -; Do you plan to work besides your studies? how do I: - |
| o02 | correct | no_match  | 0.0 | - | how do I apply for housing benefit?: -; Do you plan to work besides your studies? how do I: - |
| o02 | correct | no_match  | 0.0 | How do I apply for housing benefit while receiving the SU disability supplement? | how do I apply for housing benefit?: -; Do you plan to work besides your studies? how do I: -; How do I apply for housing benefit while receiving: - |
| o03 | WRONG | answered FAQ_P02 | 0.0 | What email address should I provide for contact about my handicaptillæg application? | what's the weather like in Copenhagen today?: -; What email address should we use to contact you ab: -; What email address should I provide for contact ab: FAQ_P02 |
| o03 | WRONG | answered FAQ_P02 | 0.0 | What email address can I use for contact about my handicaptillæg application? | what's the weather like in Copenhagen today?: -; What email address should we use to contact you ab: -; What email address can I use for contact about my : FAQ_P02 |
| o03 | WRONG | answered FAQ_P02 | 0.0 | What email address should I provide for contact about my handicaptillæg application? | what's the weather like in Copenhagen today?: -; What email address should we use to contact you ab: -; What email address should I provide for contact ab: FAQ_P02 |
| m01 | partial | options FAQ_38,FAQ_40,FAQ_P12 | 0.99 | What happens if I earn more than the allowed amount while receiving handicaptillæg? | What happens if I earn more than the allowed amoun: FAQ_38,FAQ_40,FAQ_P12 |
| m01 | partial | options FAQ_38,FAQ_40,FAQ_P12 | 0.99 | What happens if I earn more than the allowed income limit when receiving handicaptillæg? | What happens if I earn more than the allowed incom: FAQ_38,FAQ_40,FAQ_P12 |
| m01 | partial | options FAQ_38,FAQ_40,FAQ_P12 | 0.99 | What happens if I earn more than the allowed amount while receiving handicaptillæg? | What happens if I earn more than the allowed amoun: FAQ_38,FAQ_40,FAQ_P12 |
| m02 | partial | options FAQ_43,FAQ_22 | 0.0 | - | and will new documents I send with the appeal be l: FAQ_43,FAQ_22; Review and send demo application and will new docu: FAQ_43,FAQ_22 |
| m02 | partial | options FAQ_43,FAQ_22 | 0.0 | - | and will new documents I send with the appeal be l: FAQ_43,FAQ_22; Review and send demo application and will new docu: FAQ_43,FAQ_22 |
| m02 | partial | options FAQ_43,FAQ_22 | 0.0 | - | and will new documents I send with the appeal be l: FAQ_43,FAQ_22; Review and send demo application and will new docu: FAQ_43,FAQ_22 |

## Wrong answers

- f01: "and how is my ability to work assessed then?" answered with FAQ_01; expected {'answer': ['FAQ_15']}
- f01: "and how is my ability to work assessed then?" answered with FAQ_P09; expected {'answer': ['FAQ_15']}
- f08: "and if they say no, can I appeal?" answered with FAQ_32; expected {'answer': ['FAQ_41']}
- f08: "and if they say no, can I appeal?" answered with FAQ_32; expected {'answer': ['FAQ_41']}
- f08: "and if they say no, can I appeal?" answered with FAQ_32; expected {'answer': ['FAQ_41']}
- f10: "should I write a personal statement about it then?" answered with FAQ_01; expected {'answer': ['FAQ_P05']}
- f11: "what if I have two of them?" answered with FAQ_03; expected {'answer': ['FAQ_13']}
- f11: "what if I have two of them?" answered with FAQ_03; expected {'answer': ['FAQ_13']}
- f13: "okay, and what should the medical records themselves describe?" answered with FAQ_P01; expected {'answer': ['FAQ_23']}
- n01: "okay, but would the number of hours matter here?" answered with FAQ_P09; expected {'no_answer': True}
- n01: "okay, but would the number of hours matter here?" answered with FAQ_P09; expected {'no_answer': True}
- n03: "do they have to be translated into Danish?" answered with FAQ_21; expected {'no_answer': True}
- n03: "do they have to be translated into Danish?" answered with FAQ_P01; expected {'no_answer': True}
- n04: "will it go faster if I apply for it early?" answered with FAQ_P08; expected {'no_answer': True}
- n04: "will it go faster if I apply for it early?" answered with FAQ_P08; expected {'no_answer': True}
- n04: "will it go faster if I apply for it early?" answered with FAQ_P08; expected {'no_answer': True}
- n05: "can I pay to have it processed faster?" answered with FAQ_P08; expected {'no_answer': True}
- n05: "can I pay to have it processed faster?" answered with FAQ_P08; expected {'no_answer': True}
- n05: "can I pay to have it processed faster?" answered with FAQ_P08; expected {'no_answer': True}
- n06: "will you also send me a text message?" answered with FAQ_P02; expected {'no_answer': True}
- n07: "how many pages should it be?" answered with FAQ_P05; expected {'no_answer': True}
- n07: "how many pages should it be?" answered with FAQ_P05; expected {'no_answer': True}
- n07: "how many pages should it be?" answered with FAQ_P05; expected {'no_answer': True}
- n08: "what if they pay me in gift cards instead of money?" answered with FAQ_15; expected {'no_answer': True}
- n08: "what if they pay me in gift cards instead of money?" answered with FAQ_38; expected {'no_answer': True}
- c01: "Does work I did before my studies count against me?" answered with FAQ_01; expected {'answer': ['FAQ_17']}
- v03: "I'm not sure, how does my answer here affect the application?" answered with FAQ_01; expected {'answer': ['FAQ_16', 'FAQ_15']}
- v04: "what counts here?" answered with FAQ_08; expected {'answer': ['FAQ_21', 'FAQ_24']}
- a01: "yes I worked 4 years at a supermarket" answered with FAQ_17; expected {'no_answer': True}
- a01: "yes I worked 4 years at a supermarket" answered with FAQ_P01; expected {'no_answer': True}
- o03: "what's the weather like in Copenhagen today?" answered with FAQ_P02; expected {'no_answer': True}
- o03: "what's the weather like in Copenhagen today?" answered with FAQ_P02; expected {'no_answer': True}
- o03: "what's the weather like in Copenhagen today?" answered with FAQ_P02; expected {'no_answer': True}
