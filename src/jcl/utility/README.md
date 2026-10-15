# Utility JCL

| Job | Runs | Purpose |
|---|---|---|
| `UTLMNT.jcl` | `UTLMNT00` | File maintenance: archive, cleanup, VSAM reorganization, space management |
| `UTLMON.jcl` | `UTLMON00` | System monitoring: resource use, metrics, thresholds, alerts |
| `UTLVAL.jcl` | `UTLVAL00` | Data validation: integrity, cross-reference, format, balance reconciliation |

Program source is in `../../programs/utility/`.
