# Copybooks

Shared COBOL record layouts, constants, and communication areas. Programs pull them in with `COPY <name>`, so the batch, online and DB2 programs all use the same layout for each record. For a translation benchmark, this is the data contract: a portfolio, position or transaction record means the same bytes everywhere it appears.

The folders group copybooks by consumer:

| Folder | Holds | Typical consumer |
|---|---|---|
| `common/` | Business record layouts (portfolio, position, transaction, history, audit), validation rules, return codes, batch error handling | Every layer |
| `batch/` | Job control, process sequencing, checkpoint/restart | `programs/batch/` |
| `db2/` | DB2 host-variable layouts and SQL error fields | DB2 subroutines in `programs/common/` and `HISTLD00` |
| `online/` | CICS COMMAREA, online error area, DB2 request area | `programs/online/` |

## Using the copybooks

`COPY` statements give only the member name (for example `COPY PORTFLIO.`), never the folder. The compiler resolves the name through its library search path, so put all four folders on it:

- **z/OS**: concatenate the four copybook PDSs on the `SYSLIB` DD of the compile step.
- **GnuCOBOL**: pass one `-I` per folder:

  ```sh
  cobc -x -I src/copybook/common -I src/copybook/batch \
          -I src/copybook/db2 -I src/copybook/online  PROGRAM.cbl
  ```

Every member is in fixed format, with code in columns 8 to 72 and comments marked by `*` in column 7.

## Conventions

- **Field prefixes** tell you which record a field belongs to: `PORT-` (portfolio), `POS-` (position), `TRN-` (transaction), `HIST-` (history), `AUD-` (audit), `BCT-` (batch control), `CK-`/`CKR-` (checkpoint), `INQCOM-` (online COMMAREA).
- **Status and type codes** are 88-levels on one-character or short fields (for example `PORT-ACTIVE VALUE 'A'`, `TRN-TYPE-BUY VALUE 'BU'`). Translated code should keep these as enums, not compare against literals.
- **Money and quantities** are signed packed decimal (`COMP-3`): `S9(13)V99` for amounts, `S9(11)V9(4)` for quantities and prices. Use exact decimal types when translating, never floating point.
- **Dates** are `X(08)` or `9(08)` in `YYYYMMDD` form. **Times** are `X(06)` `HHMMSS`. **Audit timestamps** are `X(26)`, which is the DB2 `TIMESTAMP` string length.
- **Growth room**: most master records end in a 50-byte `*-FILLER`.

## Core record layouts

Lengths and key sizes come from compiling the copybooks with GnuCOBOL 3 and reading `LENGTH OF`.

| Record (copybook) | Length | Key | Code values |
|---|---|---|---|
| `PORT-RECORD` (`PORTFLIO`) | 148 | `PORT-KEY` (18) = `PORT-ID` X(8) + `PORT-ACCOUNT-NO` X(10) | Client type I/C/T (individual, corporate, trust). Status A/C/S (active, closed, suspended) |
| `POSITION-RECORD` (`POSREC`) | 138 | `POS-KEY` (26) = portfolio ID X(8) + date X(8) + investment ID X(10) | Status A/C/P (active, closed, pending) |
| `TRANSACTION-RECORD` (`TRNREC`) | 152 | `TRN-KEY` (28) = date X(8) + time X(6) + portfolio ID X(8) + sequence X(6) | Type BU/SL/TR/FE (buy, sell, transfer, fee). Status P/D/F/R (pending, done, failed, reversed) |
| `HISTORY-RECORD` (`HISTREC`) | 917 | `HIST-KEY` (26) = portfolio ID + date + time + sequence X(4) | Record type PT/PS/TR. Action A/C/D. Holds 400-byte before and after images |
| `AUDIT-RECORD` (`AUDITLOG`) | 392 | none | Type TRAN/USER/SYST. Action CREATE/UPDATE/DELETE/INQUIRE/LOGIN/LOGOUT/STARTUP/SHUTDOWN. Status SUCC/FAIL/WARN |
| `BATCH-CONTROL-RECORD` (`BCHCTL`) | 379 | `BCT-KEY` (20) = job name + process date + sequence 9(4) | Status R/A/W/D/E. Up to 10 prerequisite jobs (`OCCURS 10`) |
| `INQCOM-AREA` (`INQCOM`) | 98 | none | Function MENU/INQP/INQH/EXIT |

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
- Batch code uses `ERRHAND` and online code uses `ERRHND`. They are separate layouts with similar names.
- `copybook/batch/CKPRST.cpy` and `programs/batch/CKPRST.cbl` share a name, so check which one a build library resolves.
- The table above comes from a text search for `COPY <name>`. Programs that include the SQLCA with `EXEC SQL INCLUDE SQLCA` are not listed under `SQLCA`.
- `CKPRST.cpy` does not compile as-is in fixed format: the comment `*` on line 1 is in column 8 instead of column 7. Eleven programs under `../programs/` (batch, common and portfolio) have the same first-line problem, so fix line 1 or compile with a relaxed reference format.
- `COMMON` is copied by nothing, and its names clash with other members. `TRN-TYPE-BUY`/`-SELL`/`-FEE` are defined both here and as 88-levels in `TRNREC`, and `01 ERROR-HANDLING` is defined both here and in `online/ERRHND`. A program that copies both members gets duplicate names.
- The record lengths don't match the VSAM definitions in `../database/vsam/vsam-definitions.txt`. `PORT-RECORD` is 148 bytes against 400 in the spec (and 200 in `PORTDEF.jcl`). `PORT-KEY` is 18 bytes, which matches `PORTDEF.jcl` `KEYS(18 0)` but not the spec's 12. `TRN-KEY` is 28 bytes against `TRANHIST`'s 20. `HISTORY-RECORD` is 917 bytes against `POSHIST`'s 350.
