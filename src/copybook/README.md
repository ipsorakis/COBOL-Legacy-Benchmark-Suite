# Copybooks

Shared COBOL record layouts and constants, pulled in with `COPY <name>`. The "Used by" column lists the programs under `../programs/` and `../templates/` that copy each member.

## `common/`

| Copybook | Contents | Used by |
|---|---|---|
| `PORTFLIO` | Portfolio master record (`PORT-RECORD`) | PORTADD, PORTDEL, PORTREAD, PORTTEST, PORTUPDT, TSTGEN00 |
| `POSREC` | Position record (`POSITION-RECORD`) | INQPORT, RPTPOS00, UTLVAL00 |
| `TRNREC` | Transaction record (`TRANSACTION-RECORD`) | PORTTRAN, RPTPOS00, TSTGEN00, UTLVAL00 |
| `HISTREC` | History record (`HISTORY-RECORD`) | HISTLD00 |
| `AUDITLOG` | Audit trail record (`AUDIT-RECORD`) | AUDPROC, PORTTRAN, RPTAUD00 |
| `PORTVAL` | Validation return codes, error messages and constants | PORTVALD |
| `ERRHAND` | Batch error categories, return codes and message layout | ERRPROC and most batch, test and utility programs |
| `RTNCODE` | Return-code area | RPTAUD00, RPTPOS00, RPTSTA00, RTNCDE00, TSTGEN00, TSTVAL00, UTLMNT00, UTLMON00, UTLVAL00 |
| `RETHND` | Return-code handling and standard error codes | CKPRST |
| `COMMON` | System-wide return codes, status codes and transaction types | not copied by any program |

## `batch/`

| Copybook | Contents | Used by |
|---|---|---|
| `BCHCTL` | Batch control file record: job-level control and sequencing | BCHCTL00, HISTLD00, PRCSEQ00, RCVPRC00, RPTSTA00 |
| `BCHCON` | Batch control constants: status values, RC thresholds | BCHCTL00, HISTLD00, PRCSEQ00, RCVPRC00 |
| `PRCSEQ` | Process sequence record and standard sequences | PRCSEQ00, RCVPRC00 |
| `CKPRST` | Checkpoint control block and checkpoint VSAM record (pairs with `BCHCTL`) | CKPRST |

## `db2/`

| Copybook | Contents | Used by |
|---|---|---|
| `DBTBLS` | Host-variable layouts for `POSHIST` and `ERRLOG` | DB2ERR, HISTLD00 |
| `DBPROC` | Standard DB2 error-handling fields | DB2CMT, DB2CONN, DB2ERR, DB2STAT, HISTLD00 |
| `SQLCA` | SQL status codes | DB2CMT, DB2CONN, DB2ERR, DB2STAT, HISTLD00 |

## `online/`

| Copybook | Contents | Used by |
|---|---|---|
| `INQCOM` | Online inquiry COMMAREA | INQONLN, INQPORT, INQHIST |
| `ERRHND` | Online error-handling area | DB2ONLN, DB2RECV, ERRHNDL, INQONLN, SECMGR |
| `DB2REQ` | DB2 request area | DB2RECV |

## Notes

- Batch code uses `ERRHAND`; online code uses `ERRHND`. They are separate layouts with similar names.
- `copybook/batch/CKPRST.cpy` and `programs/batch/CKPRST.cbl` share a name, so check which one a build library resolves.
- The table above comes from a text search for `COPY <name>`. Programs that include the SQLCA with `EXEC SQL INCLUDE SQLCA` are not listed under `SQLCA`.
