# Database definitions

Physical data definitions for the two storage layers. VSAM holds the master and working files used by batch and online programs. DB2 holds history, logging and the relational portfolio model.

## `vsam/`

`vsam-definitions.txt` specifies the KSDS clusters (organization, record/key length, CI size, free space, share options, key structure):

| File | Record length | Key length | Key structure |
|---|---|---|---|
| `PORTMSTR` | 400 | 12 | Portfolio ID (8) + account type (2) + branch ID (2) |
| `TRANHIST` | 300 | 20 | Date (8) + time (6) + portfolio ID (8) + sequence (6) |
| `POSHIST` | 350 | 18 | see file |

The IDCAMS job that defines the portfolio master is `../jcl/portfolio/PORTDEF.jcl`.

## `db2/`

| File | Defines |
|---|---|
| `db2-definitions.sql` | `PORTFOLIO_MASTER`, `INVESTMENT_POSITIONS`, `TRANSACTION_HISTORY` (the latter two FK to `PORTFOLIO_MASTER`), their indexes, and views `ACTIVE_PORTFOLIOS` and `CURRENT_POSITIONS` |
| `POSHIST.sql` | Tablespace, table and two indexes for position history. PK `(ACCOUNT_NO, PORTFOLIO_ID, TRANS_DATE, TRANS_TIME)` |
| `ERRLOG.sql` | Tablespace, table and index for error logging. PK `(ERROR_TIMESTAMP, PROGRAM_ID)`. Written by `ERRHNDL` |
| `RTNCODES.sql` | Return-code log table and indexes. PK `(TIMESTAMP, PROGRAM_ID)` |
| `PORTPLAN.sql` | `BIND PLAN PORTPLAN` over package collection `PORTPKG`. CICS uses this plan through `DB2ENTRY(PORTDB2)` |

Host-variable layouts for these tables are in `../copybook/db2/DBTBLS.cpy`.

## Known inconsistencies

These definitions disagree with each other. If you need a single source of truth, decide which one wins first:

- `vsam-definitions.txt` gives `PORTMSTR` a 400-byte record and a 12-byte key. `PORTDEF.jcl` defines `PORTFOLIO.MASTER.FILE` with `RECORDSIZE(200 200)` and `KEYS(18 0)`. The `PORTFLIO` copybook record is 148 bytes with an 18-byte key, so the key agrees with `PORTDEF.jcl`.
- The CICS file `POSFILE` in `../cics/PORTDFN.csd` uses `RECORDSIZE(200)` and dataset `PORTFOLIO.POSITION.VSAM`, which does not appear in `vsam-definitions.txt`.
