# Templates

Starting skeletons that encode the suite's coding standards. Copy one, rename `PROGRAM-ID`, and fill in the bracketed placeholders.

| Template | `PROGRAM-ID` | Use for |
|---|---|---|
| `program/standard-program.cbl` | `PROGNAME` | Any new program: standard header, maintenance log, constants and switches |
| `program/file-handling.cbl` | `FILEHNDL` | VSAM KSDS plus sequential input/output file patterns |
| `database/db2-handling.cbl` | `DB2HNDL` | DB2 access: SQLCA, table declaration, host variables, null indicators |
| `error/error-handling.cbl` | `ERRHANDL` | Standard return codes, error message structure, error tracking |

The `portfolio/` programs follow `standard-program.cbl` closely, so look there for filled-in examples.
