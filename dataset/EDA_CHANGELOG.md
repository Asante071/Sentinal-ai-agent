# EDA correction log

- Preserved all 1,000 source records.
- Kept all 899 resolved/closed status records in the status count.
- Flagged 21 resolved tickets with invalid event chronology.
- Excluded those 21 tickets from resolution-duration statistics and the
  resolution-time-by-priority figure.
- Regenerated `tickets_clean.csv`, `eda_summary.json`, `data_dictionary.csv`,
  and all six figures using `python eda.py`.

Corrected duration sample: 878 tickets.
Mean resolution time: 23.7 hours.
Median resolution time: 17.9 hours.
Median by priority: P1 2.1h, P2 5.0h, P3 14.8h, P4 44.2h.
IQR outliers: 0 under the script's 1.5×IQR rule.
