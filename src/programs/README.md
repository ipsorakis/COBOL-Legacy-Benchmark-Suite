# Programs

COBOL source for the Investment Portfolio Management System, grouped by execution layer. Each table lists the program, what it does (from its header comment), and the JCL that runs it, if any.

Online programs use `EXEC CICS`. Programs marked **DB2** contain `EXEC SQL` and need a DB2 precompile/bind step (see `../database/db2/PORTPLAN.sql`).

## `batch/`: batch processing and reporting

| Program | Purpose | Notes | JCL |
|---|---|---|---|
| `BCHCTL00` | Batch control processor: reads the control record, validates the process, checks dependencies, updates status | Several paragraphs are listed in the header as still to be implemented | none |
| `CKPRST` | Checkpoint/restart subroutine with `INIT`, `TAKE`, `COMMIT` and `RESTART` entry points over an indexed checkpoint file (`CKPTFILE`) | Called with `CHECKPOINT-CONTROL` and `RETURN-STATUS` | none |
| `HISTLD00` | Loads position history into DB2 | DB2 | none |
| `POSUPDT` | Position update | **Empty placeholder file** (1 byte) | none |
| `PRCSEQ00` | Process sequence manager: builds the run sequence and finds the next ready process | Several paragraphs are listed in the header as still to be implemented | none |
| `RCVPRC00` | Recovers failed batch processes | | none |
| `RPTAUD00` | Audit report: security trail, process audit, error summary, control checks | | `jcl/batch/RPTAUD.jcl` |
| `RPTPOS00` | Daily position report: position summary, transaction activity, exceptions, performance | | `jcl/batch/RPTPOS.jcl` |
| `RPTSTA00` | System statistics report: processing stats, resource use, trends | | `jcl/batch/RPTSTA.jcl` |
| `RTNANA00` | Analyses return codes across the system and reports trends and error patterns | DB2 | `jcl/RTNANA.jcl` |
| `RTNCDE00` | Standard return-code handler with an audit trail | DB2 | none |

## `common/`: shared subroutines

Called by other programs; they have no JCL of their own.

| Program | Purpose | Notes |
|---|---|---|
| `AUDPROC` | Writes audit trail records | Called by `PORTTRAN` |
| `ERRPROC` | Standard error processing; builds and writes error messages | Most-called subroutine in the suite |
| `DB2CONN` | DB2 connection manager | DB2 |
| `DB2CMT` | DB2 commit controller | DB2 |
| `DB2ERR` | DB2 SQL error handler | DB2 |
| `DB2STAT` | DB2 statistics collector | DB2 |

## `online/`: CICS online inquiry

Transaction `PINQ` starts `INQONLN` (see `../cics/PORTDFN.csd`). Screens are in `../maps/INQSET.bms`.

| Program | Purpose | Notes |
|---|---|---|
| `INQONLN` | Main inquiry handler: screen interaction and portfolio lookup | CICS entry point |
| `INQPORT` | Current portfolio positions (VSAM and DB2) | CICS, DB2 |
| `INQHIST` | Transaction history from DB2, with scrolling | CICS, DB2 |
| `SECMGR` | Validates CICS user credentials and DB2 authorization; keeps a security audit trail | CICS, DB2 |
| `CURSMGR` | Manages DB2 cursor lifecycle and array fetch | CICS, DB2 |
| `DB2ONLN` | Online DB2 connection pooling and reuse | CICS, DB2 |
| `DB2RECV` | DB2 failure recovery: retry and rollback | CICS, DB2 |
| `ERRHNDL` | Central online error handler; logs to DB2 `ERRLOG` | CICS, DB2. Written in free-format column layout, unlike the other programs |

## `portfolio/`: portfolio master maintenance

| Program | Purpose | JCL |
|---|---|---|
| `PORTMSTR` | CRUD operations on the portfolio master file | none |
| `PORTADD` | Creates portfolio records from an input file | `jcl/portfolio/PORTADD.jcl` |
| `PORTUPDT` | Updates existing portfolio records | `jcl/portfolio/PORTUPDT.jcl` |
| `PORTDEL` | Processes deletion requests | `jcl/portfolio/PORTDEL.jcl` |
| `PORTREAD` | Shows the read access patterns on the portfolio file | `jcl/portfolio/PORTREAD.jcl` |
| `PORTTRAN` | Portfolio transaction processing; saves the prior state and calls `AUDPROC` | none |
| `PORTVALD` | Validation subroutine (portfolio ID `PORT` + 4 digits, 10-digit account number) | none |
| `PORTTEST` | Generates portfolio test data | `jcl/portfolio/PORTTEST.jcl` |

## `test/`: test support

| Program | Purpose | JCL |
|---|---|---|
| `TSTGEN00` | Generates portfolio, transaction, error-condition and volume test data | `jcl/test/TSTGEN.jcl` |
| `TSTVAL00` | Runs test cases and validates results, error handling and performance | `jcl/test/TSTVAL.jcl` |

## `utility/`: maintenance and monitoring

| Program | Purpose | JCL |
|---|---|---|
| `UTLMNT00` | File maintenance: archiving, cleanup, VSAM reorg, space management | `jcl/utility/UTLMNT.jcl` |
| `UTLMON00` | System monitoring: resource use, metrics, thresholds, alerts | `jcl/utility/UTLMON.jcl` |
| `UTLVAL00` | Data validation: integrity, cross-reference, format and balance checks | `jcl/utility/UTLVAL.jcl` |

## Related

- Record layouts: [`../copybook/`](../copybook/README.md)
- Files and tables: [`../database/`](../database/README.md)
- Program skeletons: [`../templates/`](../templates/README.md)
