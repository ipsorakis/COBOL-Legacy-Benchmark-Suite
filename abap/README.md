# ABAP migration (abapGit package `ZCLBS`)

abapGit-format SAP objects for the ABAP track of the CLBS migration. Import with
abapGit (starting folder `/src/`, prefix folder logic). Target release: ABAP 7.52+
(the unit tests use the ABAP SQL test double framework, available from 7.51).

Static check: `npx @abaplint/cli abaplint.json` (from this folder).

## Objects

| Object | Type | Source | Notes |
| --- | --- | --- | --- |
| `ZCLBS_HISTLD00` | Report (type 1) | `src/programs/batch/HISTLD00.cbl` | KAN-114. Position history load. |
| `ZCLBS_TRANHIST` | Transparent table | VSAM KSDS `TRANHIST` | Provisional, see below. |
| `ZCLBS_POSHIST` | Transparent table | `src/database/db2/POSHIST.sql` | Provisional, see below. |
| `ZCLBS_BCHCTL` | Transparent table | VSAM KSDS `BCHCTL` / `BCHCTL.cpy` | Provisional, see below. |

### Provisional Epic 1 tables

The Epic 1 DDIC tickets (KAN-132 / KAN-141 / KAN-147 / KAN-149) are still open, so
the three tables the report needs ship here as minimal definitions using
predefined types. Epic 1 can replace them with data elements and domains as long
as it keeps the field names below.

- `ZCLBS_TRANHIST`: the VSAM file moved into a table. The primary key is the
  KSDS record key `TH-KEY`: trans date, time, portfolio ID, sequence no. The data
  fields are the `TH-*` fields that HISTLD00 moves to POSHIST. HISTLD00 refers to
  `TH-*` names, but its `COPY HISTREC` defines `HIST-*` fields, so the COBOL
  does not compile as written. This layout is inferred from the moves.
- `ZCLBS_POSHIST`: a 1:1 copy of the DB2 table (`DATE` → `DATS`, `TIME` → `TIMS`,
  `TIMESTAMP` → `TIMESTAMPL`). Its secondary indexes and range partitioning
  are not included yet.
- `ZCLBS_BCHCTL`: the flat part of `BATCH-CONTROL-RECORD`, plus
  `RECORDS_READ` / `RECORDS_WRITTEN`. HISTLD00 writes these two fields, but
  `BCHCTL.cpy` does not define them. The `BCT-PREREQ-JOBS OCCURS 10` group is
  left out; KAN-149 should model it as a child table.

## ZCLBS_HISTLD00: mapping from HISTLD00

| COBOL | ABAP |
| --- | --- |
| `0000-MAIN` loop `UNTIL END-OF-FILE OR WS-ERROR-COUNT > 100` | `lcl_history_loader->run`, limit `P_MAXERR` (default 100) |
| `1100-OPEN-FILES`, `1200-CONNECT-DB2`, `3200`, `3300` | Not needed (DDIC tables on the default DB connection) |
| `1300-INIT-CHECKPOINTS`: READ/REWRITE BCHCTL key (`HISTLD00`, spaces) with status `A` | `UPDATE zclbs_bchctl SET status = 'A'` for key (`HISTLD00`, `P_PRCDT`, `P_SEQNO`), then commit |
| `2100-READ-HISTORY` (sequential KSDS read) | Keyset-paged `SELECT ... ORDER BY PRIMARY KEY` (package size 1000) |
| `2200-LOAD-TO-DB2` `INSERT INTO POSHIST` | `INSERT zclbs_poshist`. A duplicate key (`sy-subrc = 4`, SQLCODE -803) is skipped. `CX_SY_OPEN_SQL_DB` adds 1 to the error count and runs `DB2-ERROR-ROUTINE` |
| `2300-CHECK-COMMIT`, threshold 1000 | `COMMIT WORK` every `P_COMMIT` records read |
| `2310-UPDATE-CHECKPOINT` (VSAM REWRITE) | `UPDATE zclbs_bchctl` counters, committed on its own (the VSAM write was outside the DB2 unit of work) |
| `3100-FINAL-COMMIT` | Final `COMMIT WORK` and checkpoint |
| `3400-DISPLAY-STATS` (`DISPLAY`) | List output (spool) and job log message |
| `9000-ERROR-ROUTINE` / `CALL 'ERRPROC'` | `lif_error_handler` (list and job log), then `ROLLBACK WORK` |
| `MOVE WS-ERROR-COUNT TO RETURN-CODE` | `return_code` = error count. If it is above `P_MAXRC` (default 4, the JCL `RC <= 0004` condition), a background job ends with an `E` message so successor steps don't start |

### Behaviour kept for parity

These are faithful to the COBOL and may need a business decision:

- A missing control record is logged but does **not** stop the load or add to
  the return code. Each later checkpoint logs `Error updating checkpoint`.
- `DB2-ERROR-ROUTINE` rolls back every uncommitted insert since the last commit,
  but `records_written` is not reduced.
- The control record is never set to `D` (done) at the end. It stays `A`.
- No field validation. Records go to POSHIST unchanged.

### Deviations

- The POSHIST audit columns are filled in (`PROCESS_DATE/TIME` = `sy-datum/uzeit`,
  `PROGRAM_ID` = `HISTLD00`, `USER_ID` = `sy-uname`, `AUDIT_TIMESTAMP` = UTC).
  The COBOL leaves them as spaces after `INITIALIZE`, which DB2 rejects for
  `DATE`/`TIME` `NOT NULL` columns.
- ERRPROC wrote to the sequential `ERRLOG` file. Here errors go to the job log and
  spool through `lif_error_handler`, which Epic 6's central error service can replace.
