# Validation Results — Supplied Case Data

These values were produced after:
- normalising SKU case/spacing;
- standardising month values;
- removing duplicate transaction copies;
- merging the three `SWITCH` relationships;
- excluding inactive SKU1041 from the main analysis;
- applying the case rules in the specified order.

## Required outputs

| Measure | Result |
|---|---:|
| Red List items | 7 |
| No Action items | 13 |
| Push items | 18 |
| Total aged value of Push items | ₹163,841 |

## Required SKU checks

| SKU | Class | Reason |
|---|---|---|
| SKU1001 | No Action | Months to clear = 2.75, which is below 3. |
| SKU1006 | Push | Includes SWITCH partner SKU1003; combined months to clear = 3.98 and aged stock exists. |
| SKU1019 | Push | Includes SWITCH partner SKU1015; combined months to clear = 3.98 and aged stock exists. |

## SKU1005 first three customer targets

| Rank | Customer | Bucket | Six-month purchase value |
|---:|---|---|---:|
| 1 | C220 — Customer 220 | 1 — Bought Before | ₹665,004 |
| 2 | C224 — Customer 224 | 1 — Bought Before | ₹320,780 |
| 3 | C214 — Customer 214 | 2 — Similar Business | ₹574,001 |

## Top 10 Push items by aged value

1. SKU1005 — ₹31,280
2. SKU1034 — ₹20,315
3. SKU1020 — ₹18,360
4. SKU1019 — ₹12,600
5. SKU1029 — ₹9,605
6. SKU1006 — ₹9,150
7. SKU1033 — ₹8,220
8. SKU1014 — ₹7,650
9. SKU1009 — ₹7,480
10. SKU1038 — ₹7,320

## Data-quality findings

- 25 sales rows required SKU case/spacing normalisation.
- 117 sales rows required month-format normalisation.
- 6 duplicate transaction groups were found; 6 extra duplicate rows were removed.
- Customer C217 has no industry recorded.
- SKU1041 is inactive but holds 169 units of stock; it is excluded from the main analysis and shown as a warning.
- Three explicit SWITCH relationships were resolved:
  - SKU1003 → SKU1006
  - SKU1015 → SKU1019
  - SKU1030 → SKU1033
- Three alternate-item relationships have a non-SWITCH/blank flag and are not merged:
  - SKU1009 → B-Product 03 (25/case)
  - SKU1022 → D-Product 03 (25/case)
  - SKU1037 → F-Product 03 (24/case)
