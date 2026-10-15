# JCL

Batch job streams. Each job runs a single program from `../programs/`.

| Folder / file | Jobs |
|---|---|
| [`batch/`](batch/README.md) | Reporting jobs |
| [`utility/`](utility/README.md) | Maintenance, monitoring and validation jobs |
| `portfolio/` | Portfolio master definition and maintenance (below) |
| `test/` | Test data generation and validation (below) |
| `RTNANA.jcl` | Runs `RTNANA00`, the return-code analysis |

## `portfolio/`

| Job | Runs | Purpose |
|---|---|---|
| `PORTDEF` | `IDCAMS` | Defines the portfolio master VSAM cluster. Run this first |
| `PORTTEST` | `PORTTEST` | Generates portfolio test data |
| `PORTADD` | `PORTADD` | Adds portfolios from an input file |
| `PORTREAD` | `PORTREAD` | Reads portfolio records |
| `PORTUPDT` | `PORTUPDT` | Updates portfolios |
| `PORTDEL` | `PORTDEL` | Deletes portfolios |

## `test/`

| Job | Runs | Purpose |
|---|---|---|
| `TSTGEN` | `TSTGEN00` | Generates test data |
| `TSTVAL` | `TSTVAL00` | Validates test results |

## Before submitting

The jobs use placeholder accounting info (`(ACCT)` or `(ACCT#)`) and dataset names (`PROD.*`). Change the `JOB` card, `STEPLIB`, and DSNs to match your site before you submit them. These programs have no JCL: `BCHCTL00`, `PRCSEQ00`, `RCVPRC00`, `HISTLD00`, `RTNCDE00` and `PORTMSTR`.
