# Implementation checklist

- [ ] Audit warehouse intent, upstream sender acceptance and existing recovery journal; define exact eligibility and migration exclusions.
- [ ] Implement durable per-source bounded receipts and fresh reconciliation via existing upstream helpers; preserve no-replay rules.
- [ ] Implement safe startup and reconnect restoration and completed/held outcomes, including stop/epoch fencing.
- [ ] Expose eligibility and reasons before launch and in web/native recovery views.
- [ ] Test simulated multi-shipment restart, in-transit and arrived cargo, ambiguous write, legacy jobs, changed stock, stop/reconnect, upstream parity; document live acceptance.
