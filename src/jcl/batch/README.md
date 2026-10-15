# Batch reporting JCL

| Job | Runs | Report |
|---|---|---|
| `RPTPOS.jcl` | `RPTPOS00` | Daily position report: positions, transaction activity, exceptions, performance |
| `RPTAUD.jcl` | `RPTAUD00` | System audit report: security trail, process audit, error summary |
| `RPTSTA.jcl` | `RPTSTA00` | System statistics report: processing stats, resource use, trends |

Program source is in `../../programs/batch/`.
