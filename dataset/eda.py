"""Part C: data quality, cleaning, feature engineering and EDA for the helpdesk ticket dataset.
Source: Mindweave 'Help Desk Tickets (Synthetic)' free sample, tickets.csv (1,000 tickets).  Run: python eda.py"""
import json, os, re
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

os.makedirs("figures", exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
C = "#2b5c8a"
CATS = {1: "Access Mgmt", 2: "Laptop/Endpoint", 3: "Network & VPN", 4: "Email & Collab", 5: "ERP/WMS", 6: "Printers & Devices", 7: "Security", 8: "Telephony"}
J = lambda x: json.loads(json.dumps(x, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
raw = pd.read_csv("tickets_raw.csv"); S = {}

# ---------- 1. Quality ----------
S["rows"], S["cols"] = raw.shape
S["missing"] = raw.isna().sum().to_dict()
S["duplicate_rows"] = int(raw.duplicated().sum()); S["duplicate_ids"] = int(raw.ticket_id.duplicated().sum())
S["distinct_summaries"] = int(raw.summary.nunique())
df = raw.copy()
for c in ("created_at", "first_response_at", "resolved_at"): df[c] = pd.to_datetime(df[c], format="mixed")
S["date_range"] = [str(df.created_at.min()), str(df.created_at.max())]
S["unresolved_missing_matches_status"] = bool((df.resolved_at.isna() == df.status.isin(["pending", "in_progress"])).all())
S["anomalies"] = {"resolved_before_first_response": int((df.resolved_at < df.first_response_at).sum()),
                  "first_response_before_created": int((df.first_response_at < df.created_at).sum()),
                  "resolved_before_created": int((df.resolved_at < df.created_at).sum())}
S["anomalous_tickets"] = int(((df.resolved_at < df.first_response_at) | (df.first_response_at < df.created_at) | (df.resolved_at < df.created_at)).sum())
for c in ("priority", "status", "channel"): S[f"{c}_counts"] = df[c].value_counts().to_dict()
S["escalated_pct"] = round(df.escalated.mean() * 100, 1); S["outage_related_n"] = int(df.outage_related.sum())
S["created_hour_range"] = [int(df.created_at.dt.hour.min()), int(df.created_at.dt.hour.max())]

# ---------- 2. Cleaning / transformation ----------
df["flag_time_anomaly"] = ((df.resolved_at < df.first_response_at) | (df.first_response_at < df.created_at) | (df.resolved_at < df.created_at)).astype(int)
df["resolution_hours"] = (df.resolved_at - df.created_at).dt.total_seconds() / 3600
# Retain all ticket rows, but exclude any invalid event sequence from duration metrics.
df.loc[df.flag_time_anomaly == 1, "resolution_hours"] = np.nan
df["first_response_hours"] = (df.first_response_at - df.created_at).dt.total_seconds() / 3600
df.loc[df.first_response_hours < 0, "first_response_hours"] = np.nan
df["is_resolved"] = df.status.isin(["resolved", "closed"]).astype(int)
df["category_label"] = df.category_id.map(CATS)

# ---------- 3. Feature engineering ----------
def topic(s):
    t = s.lower()
    if "service account" in t or ("outage" in t and "vpn" not in t): return "Other"
    if "vpn" in t: return "VPN"
    if "print" in t: return "Printer"
    if re.search(r"outlook|mailbox|\bemail|inbox|calendar|signature", t): return "Email"
    if re.search(r"password|sign in|sign-in", t): return "Account"
    if re.search(r"\bsso\b|single sign|\bmfa\b|\baccess\b|role request|conditional access|suspicious login", t): return "Access/Identity"
    return "Other"
df["topic"] = df.summary.map(topic)
IN_SCOPE = ["VPN", "Account", "Email", "Printer"]
df["in_scope"] = df.topic.isin(IN_SCOPE).astype(int)
df["created_week"] = df.created_at.dt.to_period("W").dt.start_time
df["created_weekday"] = df.created_at.dt.day_name(); df["created_hour"] = df.created_at.dt.hour
df.to_csv("tickets_clean.csv", index=False)

# ---------- 4. Analysis numbers ----------
S["topic_counts"] = df.topic.value_counts().to_dict(); S["topic_pct"] = (df.topic.value_counts(normalize=True) * 100).round(1).to_dict()
S["in_scope_n"] = int(df.in_scope.sum()); S["in_scope_pct"] = round(df.in_scope.mean() * 100, 1)
S["resolved_n"] = int(df.is_resolved.sum()); S["resolved_pct"] = round(df.is_resolved.mean() * 100, 1)
# Duration metrics use only resolved tickets with a valid event sequence.
S["resolution_duration_excluded_anomalies_n"] = int(((df.flag_time_anomaly == 1) & df.resolved_at.notna()).sum())
r = df.resolution_hours.dropna(); S["resolution_duration_valid_n"] = int(len(r))
q1, q3 = r.quantile([.25, .75]); iqr = q3 - q1
S["res_hours"] = {k: round(float(v), 1) for k, v in dict(mean=r.mean(), median=r.median(), std=r.std(), min=r.min(), max=r.max(), p90=r.quantile(.9)).items()}
S["res_hours"]["iqr_outliers"] = int(((r < q1 - 1.5 * iqr) | (r > q3 + 1.5 * iqr)).sum()); S["res_hours"]["n"] = int(len(r))
S["res_median_by_priority"] = df.groupby("priority").resolution_hours.median().round(1).to_dict()
S["frt_hours"] = {"mean": round(df.first_response_hours.mean(), 1), "median": round(df.first_response_hours.median(), 1)}
S["frt_median_by_priority"] = df.groupby("priority").first_response_hours.median().round(1).to_dict()
wk = df.groupby("created_week").size(); S["weekly"] = {"mean": round(wk.mean(), 1), "min": int(wk.min()), "max": int(wk.max()), "weeks": int(len(wk))}
S["p3_p4_n"] = int(df.priority.isin(["P3", "P4"]).sum())
S["escalated_pct_by_topic"] = (df.groupby("topic").escalated.mean() * 100).round(1).to_dict()
S["res_median_in_scope"] = round(df[df.in_scope == 1].resolution_hours.median(), 1)
S["in_scope_hours_share_pct"] = round(df[df.in_scope == 1].resolution_hours.sum() / df.resolution_hours.sum() * 100, 1)
# label quality: does category_id agree with what the ticket text says?
EXPECT = {"VPN": {3}, "Printer": {6}, "Email": {4}, "Account": {1}, "Access/Identity": {1, 7}}
chk = df[df.topic.isin(EXPECT)]
agree = chk.apply(lambda x: x.category_id in EXPECT[x.topic], axis=1)
S["label_check_n"] = int(len(chk)); S["label_agree_n"] = int(agree.sum()); S["label_agree_pct"] = round(agree.mean() * 100, 1)
S["label_agree_pct_by_topic"] = (agree.groupby(chk.topic).mean() * 100).round(1).to_dict()
json.dump(J(S), open("eda_summary.json", "w"), indent=2)

# ---------- 5. Figures ----------
def save(fig, n): fig.tight_layout(); fig.savefig(f"figures/{n}.png", dpi=200); plt.close(fig)
order = ["VPN", "Account", "Email", "Printer", "Access/Identity", "Other"]
tc = df.topic.value_counts().reindex(order)
fig, ax = plt.subplots(figsize=(5.2, 3)); ax.barh(order[::-1], tc.values[::-1], color=[C if t in IN_SCOPE else "#9aa5b1" for t in order[::-1]])
for i, v in enumerate(tc.values[::-1]): ax.text(v + 4, i, str(v), va="center", fontsize=8)
ax.set_title("Tickets by topic (from ticket text); blue = in scope"); save(fig, "fig1_topic")
ch = df.channel.value_counts(); fig, ax = plt.subplots(figsize=(5.2, 3)); ax.bar(ch.index, ch.values, color="#3d7a4f")
for i, v in enumerate(ch.values): ax.text(i, v + 4, str(v), ha="center", fontsize=8)
ax.set_title("Tickets by channel"); save(fig, "fig2_channel")
ct = pd.crosstab(df.topic, df.category_id).reindex(order)[list(CATS)]
fig, ax = plt.subplots(figsize=(6.6, 3.2)); ax.imshow(ct.values, cmap="Blues")
ax.set_xticks(range(8), [CATS[i] for i in CATS], rotation=30, ha="right", fontsize=8); ax.set_yticks(range(len(order)), order)
for i in range(ct.shape[0]):
    for j in range(ct.shape[1]): ax.text(j, i, ct.values[i, j], ha="center", va="center", fontsize=7)
ax.set_title("Ticket topic (from text) vs. category label"); save(fig, "fig3_label_vs_topic")
w = df.groupby("created_week").size(); fig, ax = plt.subplots(figsize=(5.2, 3)); ax.plot(w.index, w.values, marker="o", color=C, ms=3)
ax.set_title("Tickets created per week"); plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=7); save(fig, "fig4_weekly")
pr = ["P1", "P2", "P3", "P4"]; fig, ax = plt.subplots(figsize=(5.2, 3))
ax.boxplot([df[df.priority == p].resolution_hours.dropna() for p in pr], tick_labels=pr); ax.set_yscale("log"); ax.set_ylabel("hours (log scale)")
ax.set_title("Resolution time by priority"); save(fig, "fig5_resolution_by_priority")
es = df.groupby("topic").escalated.mean().reindex(order) * 100; fig, ax = plt.subplots(figsize=(5.2, 3)); ax.bar(order, es.values, color="#8a5a2b")
ax.set_ylabel("% escalated"); ax.set_title("Escalation rate by topic"); plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=8); save(fig, "fig6_escalation_by_topic")
print(json.dumps(J(S), indent=1)[:4500])

# ---------- 6. Data dictionary (types, values, missing counts measured from the data; meanings inferred from names and values) ----------
MEANING = {
 "ticket_id": ("integer", "Unique ticket number."),
 "created_at": ("datetime", "Date and time the ticket was opened."),
 "first_response_at": ("datetime", "Date and time of the first reply from a support agent."),
 "resolved_at": ("datetime", "Date and time the ticket was resolved. Blank while the ticket is pending or in progress."),
 "priority": ("category", "Urgency level. P1 appears most urgent: it has the shortest resolution times."),
 "status": ("category", "Current state of the ticket."),
 "channel": ("category", "How the ticket was raised."),
 "category_id": ("integer code", "Category code 1\u20138 (1 Access Mgmt, 2 Laptop/Endpoint, 3 Network & VPN, 4 Email & Collab, 5 ERP/WMS, 6 Printers & Devices, 7 Security, 8 Telephony). Unreliable: see Section 4.2."),
 "assigned_agent_id": ("integer code", "ID of the support agent assigned to the ticket."),
 "requester_department": ("category", "Department of the person who raised the ticket."),
 "affected_service": ("category", "Type of service affected."),
 "summary": ("text", "One-line description of the problem."),
 "description": ("text", "Longer description: the summary plus 'Reported by <name> from <department>'."),
 "escalated": ("boolean", "Whether the ticket was escalated."),
 "outage_related": ("boolean", "Whether the ticket relates to a service outage."),
}
rows_ = []
for c in raw.columns:
    typ, meaning = MEANING[c]; s = raw[c]; nu = s.nunique()
    if typ in ("category", "boolean"): vals = ", ".join(map(str, sorted(s.dropna().unique(), key=str)))
    elif typ == "integer code": vals = f"{s.min()} to {s.max()} ({nu} distinct)"
    elif typ == "integer": vals = f"{s.min()} to {s.max()}"
    elif typ == "datetime": vals = f"{str(s.dropna().min())[:10]} to {str(s.dropna().max())[:10]}"
    else: vals = f"{nu} distinct values"
    miss = int(s.isna().sum()); rows_.append({"column": c, "type": typ, "meaning": meaning, "observed_values": vals + (f"; {miss} missing" if miss else "")})
pd.DataFrame(rows_).to_csv("data_dictionary.csv", index=False)
