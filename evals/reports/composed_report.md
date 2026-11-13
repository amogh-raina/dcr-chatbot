# Help-panel field questions: typed vs composed vs app

Thresholds: single 0.8, min 0.5, margin 0.12. 36 cases; the app used the composed search in 7.

| side | hit | top1 | single_wrong | none |
|---|---|---|---|---|
| typed | 30/36 | 25/36 | 0 | 0 |
| composed | 29/36 | 25/36 | 0 | 0 |
| app | 34/36 | 28/36 | 0 | 0 |

| id | target | message | typed | hit | top1 | composed | hit | top1 | app | hit | top1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| c01 | Form0:Plan_work_studies | what do I put here? | clarify FAQ_P01,FAQ_P05,FAQ_21 (0.595) | no | no | clarify FAQ_17,FAQ_19,FAQ_P05 (0.655) | no | no | clarify FAQ_17,FAQ_19,FAQ_P05 (0.655) [composed] | no | no |
| c02 | Form0:A16 | how many hours is too many? | clarify FAQ_P09,FAQ_16,FAQ_09 (0.675) | yes | no | clarify FAQ_16,FAQ_P09,FAQ_19 (0.787) | yes | yes | clarify FAQ_P09,FAQ_16,FAQ_09 (0.675) | yes | no |
| c03 | Form0:Impairment_definition | what does permanent mean here? | clarify FAQ_08,FAQ_09,FAQ_12 (0.690) | yes | yes | clarify FAQ_08,FAQ_33,FAQ_07 (0.885) | yes | yes | clarify FAQ_08,FAQ_09,FAQ_12 (0.690) | yes | yes |
| c04 | Form0:Impairment_definition | I'm not sure, what should I pick? | clarify FAQ_P01,FAQ_19,FAQ_P05 (0.542) | no | no | clarify FAQ_08,FAQ_33,FAQ_07 (0.871) | yes | yes | clarify FAQ_08,FAQ_33,FAQ_07 (0.871) [composed] | yes | yes |
| c05 | Form0:A14 | does it have to be exactly a year? | clarify FAQ_09,FAQ_P04,FAQ_08 (0.792) | yes | yes | single FAQ_09 (0.873) | yes | yes | clarify FAQ_09,FAQ_P04,FAQ_08 (0.792) | yes | yes |
| c06 | Form0:Impairment_type | what counts as congenital? | single FAQ_26 (0.804) | yes | yes | single FAQ_26 (0.853) | yes | yes | single FAQ_26 (0.804) | yes | yes |
| c07 | Form0:Time_limited | what is this? | clarify FAQ_02,FAQ_01,FAQ_11 (0.580) | no | no | clarify FAQ_36,FAQ_37,FAQ_02 (0.763) | yes | yes | clarify FAQ_36,FAQ_37,FAQ_02 (0.763) [composed] | yes | yes |
| c08 | Form0:A17 | why does that matter? | clarify FAQ_19,FAQ_07,FAQ_02 (0.593) | no | no | clarify FAQ_36,FAQ_37,FAQ_09 (0.737) | yes | no | clarify FAQ_36,FAQ_37,FAQ_09 (0.737) [composed] | yes | no |
| c09 | Form0:A1_1 | which month should I choose? | clarify FAQ_P08,FAQ_35,FAQ_P01 (0.589) | yes | no | clarify FAQ_P01,FAQ_03,FAQ_37 (0.791) | no | no | clarify FAQ_P08,FAQ_35,FAQ_P01 (0.589) | yes | no |
| c10 | Form0:A11 | what do I need to attach? | clarify FAQ_21,FAQ_P01,FAQ_37 (0.680) | yes | yes | clarify FAQ_21,FAQ_26,FAQ_23 (0.772) | yes | yes | clarify FAQ_21,FAQ_P01,FAQ_37 (0.680) | yes | yes |
| c11 | Form0:A11 | can I black out parts of it? | clarify FAQ_P06,FAQ_P01,FAQ_28 (0.649) | yes | yes | clarify FAQ_23,FAQ_21,FAQ_26 (0.683) | no | no | clarify FAQ_P06,FAQ_P01,FAQ_28 (0.649) | yes | yes |
| c12 | Form0:A5 | do I have to write this? | clarify FAQ_P05,FAQ_P04,FAQ_21 (0.710) | yes | yes | clarify FAQ_P05,FAQ_17,FAQ_07 (0.779) | yes | yes | clarify FAQ_P05,FAQ_P04,FAQ_21 (0.710) | yes | yes |
| c13 | Form0:A2 | what if I have more than one? | clarify FAQ_13,FAQ_P07,FAQ_14 (0.760) | yes | yes | clarify FAQ_13,FAQ_07,FAQ_33 (0.742) | yes | yes | clarify FAQ_13,FAQ_P07,FAQ_14 (0.760) | yes | yes |
| c14 | Form0:Prev_work | does a student job count? | clarify FAQ_17,FAQ_16,FAQ_15 (0.698) | yes | yes | clarify FAQ_17,FAQ_16,FAQ_15 (0.685) | yes | yes | clarify FAQ_17,FAQ_16,FAQ_15 (0.698) | yes | yes |
| c15 | Form0:A15 | what if it varied a lot? | clarify FAQ_11,FAQ_12,FAQ_39 (0.580) | no | no | clarify FAQ_16,FAQ_P09,FAQ_15 (0.732) | yes | yes | clarify FAQ_16,FAQ_P09,FAQ_15 (0.732) [composed] | yes | yes |
| c19 | Form0:A1_1 | can I choose a month in the past? | clarify FAQ_35,FAQ_P04,FAQ_P03 (0.538) | yes | yes | clarify FAQ_P01,FAQ_03,FAQ_41 (0.788) | no | no | clarify FAQ_35,FAQ_P04,FAQ_P03 (0.538) | yes | yes |
| c20 | Form0:A2 | my condition isn't on this list | clarify FAQ_18,FAQ_08,FAQ_33 (0.632) | yes | no | clarify FAQ_07,FAQ_33,FAQ_08 (0.710) | yes | no | clarify FAQ_18,FAQ_08,FAQ_33 (0.632) | yes | no |
| c21 | Form0:A2 | does ADHD count as mental? | clarify FAQ_08,FAQ_13,FAQ_25 (0.565) | yes | yes | clarify FAQ_08,FAQ_07,FAQ_13 (0.663) | yes | yes | clarify FAQ_08,FAQ_13,FAQ_25 (0.565) | yes | yes |
| c22 | Form0:Impairment_type | I got ill as a teenager, which one is that? | clarify FAQ_26,FAQ_08,FAQ_39 (0.624) | yes | yes | clarify FAQ_26,FAQ_34,FAQ_33 (0.793) | yes | yes | clarify FAQ_26,FAQ_08,FAQ_39 (0.624) | yes | yes |
| c23 | Form0:Impairment_type | I don't have recent records, is that a problem? | clarify FAQ_P04,FAQ_26,FAQ_18 (0.667) | yes | yes | single FAQ_26 (0.903) | yes | yes | clarify FAQ_P04,FAQ_26,FAQ_18 (0.667) | yes | yes |
| c24 | Form0:Impairment_definition | my doctor says it might get better | clarify FAQ_12,FAQ_23,FAQ_21 (0.612) | yes | yes | clarify FAQ_33,FAQ_08,FAQ_26 (0.791) | yes | yes | clarify FAQ_33,FAQ_08,FAQ_26 (0.791) [composed] | yes | yes |
| c25 | Form0:A14 | it has been 10 months, can I still apply? | clarify FAQ_32,FAQ_09,FAQ_12 (0.738) | yes | no | clarify FAQ_09,FAQ_32,FAQ_33 (0.778) | yes | yes | clarify FAQ_32,FAQ_09,FAQ_12 (0.738) | yes | no |
| c26 | Form0:Time_limited | how do I know if mine is time-limited? | clarify FAQ_36,FAQ_09,FAQ_37 (0.734) | yes | yes | clarify FAQ_36,FAQ_37,FAQ_P01 (0.742) | yes | yes | clarify FAQ_36,FAQ_09,FAQ_37 (0.734) | yes | yes |
| c27 | Form0:A17 | when can I apply for an extension? | single FAQ_37 (0.865) | yes | yes | clarify FAQ_37,FAQ_36,FAQ_42 (0.820) | yes | yes | single FAQ_37 (0.865) | yes | yes |
| c28 | Form0:Prev_work | I stopped working because of my illness | clarify FAQ_15,FAQ_39,FAQ_33 (0.629) | no | no | clarify FAQ_17,FAQ_15,FAQ_16 (0.608) | yes | yes | clarify FAQ_15,FAQ_39,FAQ_33 (0.629) | no | no |
| c29 | Form0:Prev_work | does unpaid volunteering count as work? | clarify FAQ_P09,FAQ_16,FAQ_15 (0.733) | yes | yes | clarify FAQ_P09,FAQ_15,FAQ_17 (0.701) | yes | yes | clarify FAQ_P09,FAQ_16,FAQ_15 (0.733) | yes | yes |
| c30 | Form0:A15 | should I count holiday jobs? | clarify FAQ_15,FAQ_16,FAQ_17 (0.595) | yes | yes | clarify FAQ_16,FAQ_P09,FAQ_15 (0.726) | yes | yes | clarify FAQ_15,FAQ_16,FAQ_17 (0.595) | yes | yes |
| c31 | Form0:Plan_work_studies | will I lose the supplement if I work? | clarify FAQ_16,FAQ_P10,FAQ_P09 (0.764) | yes | yes | clarify FAQ_16,FAQ_P09,FAQ_P10 (0.725) | yes | yes | clarify FAQ_16,FAQ_P10,FAQ_P09 (0.764) | yes | yes |
| c32 | Form0:A16 | what happens if I earn more than allowed? | clarify FAQ_40,FAQ_38,FAQ_39 (0.761) | yes | yes | clarify FAQ_16,FAQ_P09,FAQ_19 (0.768) | no | no | clarify FAQ_40,FAQ_38,FAQ_39 (0.761) | yes | yes |
| c33 | Form0:A16 | is 3 hours a week ok? | clarify FAQ_16,FAQ_P09,FAQ_15 (0.777) | yes | yes | clarify FAQ_16,FAQ_P09,FAQ_19 (0.788) | yes | yes | clarify FAQ_16,FAQ_P09,FAQ_15 (0.777) | yes | yes |
| c34 | Form0:A5 | what should the statement say? | clarify FAQ_23,FAQ_P05,FAQ_21 (0.695) | yes | no | clarify FAQ_P05,FAQ_15,FAQ_07 (0.724) | yes | yes | clarify FAQ_23,FAQ_P05,FAQ_21 (0.695) | yes | no |
| c35 | Form0:A11 | is a letter from my psychologist enough? | clarify FAQ_25,FAQ_24,FAQ_P05 (0.726) | yes | yes | clarify FAQ_21,FAQ_24,FAQ_26 (0.685) | no | no | clarify FAQ_25,FAQ_24,FAQ_P05 (0.726) | yes | yes |
| c36 | Form0:A11 | how old can the records be? | single FAQ_P04 (0.866) | yes | yes | clarify FAQ_26,FAQ_08,FAQ_P04 (0.762) | yes | no | single FAQ_P04 (0.866) | yes | yes |
| c37 | Form0:A11 | my doctor only wrote the diagnosis, is that ok? | clarify FAQ_24,FAQ_23,FAQ_21 (0.698) | yes | yes | clarify FAQ_21,FAQ_26,FAQ_24 (0.704) | yes | no | clarify FAQ_24,FAQ_23,FAQ_21 (0.698) | yes | yes |
| c38 | Form0:A10 | how long until I hear back? | single FAQ_P08 (0.805) | yes | yes | clarify FAQ_P02,FAQ_31,FAQ_P03 (0.756) | no | no | single FAQ_P08 (0.805) | yes | yes |
| c39 | Form0:A10 | what if they refuse me? | clarify FAQ_32,FAQ_33,FAQ_31 (0.731) | yes | yes | clarify FAQ_31,FAQ_32,FAQ_P02 (0.757) | yes | yes | clarify FAQ_31,FAQ_32,FAQ_P02 (0.757) [composed] | yes | yes |
