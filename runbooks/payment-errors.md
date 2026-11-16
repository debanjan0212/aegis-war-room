# Payment errors and failed charges

Use when the payment service error rate is high or customers cannot check out.

1. Check what changed in the last 30 minutes for payment: feature flags first, then releases.
2. If a payment feature flag was switched on, switch it off. This is the fastest safe fix.
3. If a release went out, roll it back and tell the payment team.
4. If nothing changed, check the card processor's status page and page the payment on-call.
5. After the fix, watch error rate for five minutes. It should drop below 5%.
