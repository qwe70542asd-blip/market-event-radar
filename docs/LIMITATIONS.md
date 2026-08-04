# v11.4.6 Limitations and responses

| Limitation | Reason | Response |
|---|---|---|
| True foreign-broker holdings | Public branch data does not identify final clients or full positions | Show public institutional flow and branch concentration with a warning |
| Guaranteed second-level quotes | Free/public sources have latency and licensing limits | Mark update time; use official after-hours data and retained last-good payloads |
| Every ETF constituent every day | Managers publish in different formats and active ETFs may disclose later | Display source date and only publish verified holdings |
| Guaranteed parser stability | Official pages and APIs can change | Isolate sources, reject empty refreshes and retain the last successful payload |
| True generative AI without a secret | GitHub Pages cannot safely store model API keys | Use deterministic no-key classification now; allow an Actions secret later |
| Predicting market direction with certainty | News impact is conditional and expectation-dependent | Use impact, direction and confidence labels rather than certain predictions |
