# v11.4.45 Limitations and responses

| Limitation | Reason | Response |
|---|---|---|
| True foreign-broker holdings | Public branch data does not identify final clients or full positions | Show public institutional flow; do not label branch trades as client holdings |
| Guaranteed second-level quotes | Free/public sources have latency and licensing limits | Mark update time and retain the last good payload |
| Every ETF constituent every day | Managers publish in different formats and third-party dates differ | Show source and holdings date; official/issuer data stays primary |
| Stable third-party HTML | Yahoo, MoneyDJ and HiStock may change pages or block requests | Isolate each channel, use small batches and preserve previous successful data |
| Exact EPS without weighted shares | Period-end shares are not the IAS 33 denominator | Use reported EPS or weighted-average shares; otherwise label the result as estimated |
| Article image availability | Publishers may omit images or block hotlinking | Use verified original images only; switch to compact text cards when unavailable |
| Guaranteed parser completeness | Official and media pages can change | Reject empty refreshes, expose source health and retain last-good data |
| Predicting market direction with certainty | News impact depends on expectations and valuation | Show impact/direction labels rather than certainty |

| 15 分鐘 K 線完整覆蓋 | 免費／官方來源的盤中粒度與可用性不一致 | 視為部署後非阻擋能力；缺資料時標示不可用或過期，不得偽造 K 棒 |
