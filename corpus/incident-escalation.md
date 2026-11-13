---
title: Incident Escalation Process
owner: Operations — Service Delivery
last_updated: 2026-10-12
doc_id: DOC-007
---

# Incident Escalation Process

## Severity levels

Severity 1 (SEV-1): a critical service is down for all users, or customer data is at risk. Severity 2 (SEV-2): a major feature is broken for many users, with a workaround available. Severity 3 (SEV-3): a minor issue affecting a small number of users. Severity 4 (SEV-4): a cosmetic issue or a question.

## Who to contact

For SEV-1, page the on-call engineer immediately using PagerDuty and open a SEV-1 ticket. Post in the #incidents channel with the service name and a one-line summary. For SEV-2, open a ticket and assign it to the owning team's on-call; no page is needed unless there is no response within 30 minutes. For SEV-3 and SEV-4, open a ticket in the normal queue.

## Response times

The on-call engineer must acknowledge a SEV-1 page within 15 minutes and a SEV-2 ticket within 30 minutes. SEV-3 tickets are acknowledged within 4 business hours and SEV-4 within 1 business day. If the on-call engineer does not respond in time, escalate to the on-call manager, whose contact details are in PagerDuty.

## After the incident

For every SEV-1 and SEV-2, the owning team writes a post-incident review within 5 business days. The review must include the timeline, the root cause, and at least one action item to prevent recurrence. Action items are tracked in the ticketing system and reviewed at the weekly operations meeting.
