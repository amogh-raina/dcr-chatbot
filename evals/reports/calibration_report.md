# Query prompt comparison

Threshold-free numbers first, then the best thresholds each setting reaches under the same caps (single_wrong <= 2.0%, oos single <= 0.0%).

| query prompt | top-1 accuracy | top-3 recall | in-scope top-1 p10 | off-scope top-1 p90 | separation |
|---|---|---|---|---|---|
| none |  89.5% | 100.0% | 0.657 | 0.766 | -0.109 |
| 'query' |  90.8% | 100.0% | 0.548 | 0.666 | -0.119 |

Separation is (in-scope top-1 p10) minus (off-scope top-1 p90). Positive means a score threshold can split the groups; larger is easier to tune.

| query prompt | best single / min / margin | useful | single correct | clarify hit | oos accepted |
|---|---|---|---|---|---|
| none | 0.76 / 0.42 / 0.06 |  75.0% |  51.3% |  47.4% |  90.0% |
| 'query' | 0.70 / 0.38 / 0.02 |  73.0% |  46.1% |  53.9% |  60.0% |
