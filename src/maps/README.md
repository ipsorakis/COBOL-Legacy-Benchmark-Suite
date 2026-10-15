# BMS maps

`INQSET.bms` is the only mapset. It defines the 3270 screens for the online portfolio inquiry, each 24x80:

| Map | Screen | Key fields |
|---|---|---|
| `MENMAP` | Main menu: 1 Position inquiry, 2 Transaction history, 3 Exit | `OPTION`, `ERRMSG` |
| `POSMAP` | Portfolio position inquiry | `ACCTIN` (input); `FUNDOUT`, `NAMEOUT`, `UNITOUT`, `COSTOUT`, `VALOUT`; PF3/PF7/PF8 |
| `HISMAP` | Transaction history inquiry | `HISAIN` (input) plus history rows |
| `ERRMAP` | Error display | |

The mapset is defined to CICS as `MAPSET(INQSET)` in `../cics/PORTDFN.csd`. `INQONLN` drives it, with `INQPORT` and `INQHIST` behind it (see `../programs/online/`).

To build it, assemble with your site's BMS procedure. That produces the physical map (load library) and the symbolic map copybook the online programs need.
