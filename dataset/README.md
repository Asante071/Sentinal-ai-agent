# Dataset (Part C)
**File:** tickets_raw.csv (1,000 rows x 15 columns), the `tickets` table from the free sample of
"Help Desk Tickets (Synthetic)" by Mindweave Technologies.
**Source:** https://huggingface.co/datasets/mindweave/help-desk-tickets  (data/tickets.csv)
**Licence:** CC-BY-NC-4.0 (non-commercial use; fine for coursework). The dataset card describes the data as synthetic.
**Category key (categories.csv in the same repo):** 1 Access Management, 2 Laptop/Endpoint, 3 Network & VPN, 4 Email & Collaboration, 5 ERP/WMS, 6 Printers & Devices, 7 Security, 8 Telephony.
Run `python eda.py` to regenerate tickets_clean.csv, eda_summary.json and figures/.
_superseded_500_ticket_version/ holds an earlier 500-ticket file whose source could not be verified; it is not used.


## Temporal anomaly handling

The EDA script retains every source ticket and flags invalid event sequences in
`flag_time_anomaly`. Resolution-duration statistics and the resolution-time plot
exclude flagged records, including records where `resolved_at` precedes
`first_response_at`. Ticket status counts are calculated independently and are
not reduced by this duration filter.

## Reproduce the analysis

Run from this `dataset/` directory:

```bash
python eda.py
```

This regenerates `tickets_clean.csv`, `eda_summary.json`, `data_dictionary.csv`,
and the six figures in `figures/`.
