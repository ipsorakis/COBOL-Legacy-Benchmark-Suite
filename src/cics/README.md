# CICS resource definitions

`PORTDFN.csd` contains the DFHCSDUP input for the online inquiry, all in group `PORTGRP` with list `PORTLST`:

| Type | Name | Details |
|---|---|---|
| Transaction | `PINQ` | Program `INQONLN`, profile `DFHCICST` |
| Programs | `INQONLN`, `INQPORT`, `INQHIST`, `DB2ONLN`, `CURSMGR`, `DB2RECV`, `SECMGR` | COBOL, `EXECKEY(USER)`, non-resident |
| Mapset | `INQSET` | `../maps/INQSET.bms` |
| File | `POSFILE` | `PORTFOLIO.POSITION.VSAM`: read/browse/add, no update or delete |
| DB2ENTRY | `PORTDB2` | Plan `PORTPLAN`, `AUTHTYPE(USERID)` |
| DB2TRAN | `PINQ` | Routes `PINQ` to `PORTDB2` |

`ERRHNDL` (online error handler) is not defined here, so add a `DEFINE PROGRAM(ERRHNDL)` if it is linked to at runtime.

To install, run DFHCSDUP with this file as `SYSIN`, then `CEDA INSTALL LIST(PORTLST)` or `CEDA INSTALL GROUP(PORTGRP)`.
