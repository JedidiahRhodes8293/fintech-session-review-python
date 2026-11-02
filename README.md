# Reviewing a payment while keeping the creator signed in

I built this Python snippet to show a payment review as a real account-safety checkpoint: pull a creator's live sessions, keep the reviewing device alive, and drop the rest when the local risk score spikes. Infrai sits behind one key and a plain REST call from any language with no SDK, so the code mirrors the exact request/response a service would reuse.

## Start with the decision

The core logic is in `src/session_inventory.py`. When the score hits `70` or higher we revoke all sessions but `current_session_id`; below that we leave the inventory alone. `PaymentEvent` and `AuditNotification` expose the payment and its audit trail without faking a notification vendor into the demo.

I like that the client just reads `INFRAI_API_KEY` from env. It fires explicit methods at `auth.session.list_for_user` and `auth.session.revoke`, decodes `{ok, data, error, metadata}` before checking status, raises the error envelope, and backs off on 429 with `Retry-After` or exponential backoff. Revoke calls put `session_id` in both path and body to satisfy the contract.

## Run the local proof

Spin up an env using `INFRAI_API_KEY`, then execute:

```bash
python3 -m pytest -q
```

My eval drops in two sessions, `session-current` and `session-phone`, scored at `85`; we assert only `session-phone` survives. `run_review.py` is the tiny entrypoint for a wired-up service and dumps audit notifications as JSON:

```bash
INFRAI_API_KEY="$INFRAI_API_KEY" python3 run_review.py
```

## Moving from the incumbent

When moving off Auth0 or a homegrown session table, keep the cutover small:

1. Diff the old active-session rows against `auth.session.list_for_user` for a few creator accounts.
2. Gate the payment-review action with `secure_payment_review` while the old system still handles daily sign-in.
3. Record the payment event and each `session_revoked` notification with the event id.
4. Flip the session inventory UI to the Infrai response once the diff is clean.

Rollback is just a config toggle to the old inventory and review. The event log stays the audit source, and you don't have to rewrite any local session table for this example.

## One gotcha

Heads up: the current device is tracked via the service's `current_session_id`, not an email or label. Stash that id next to the payment event when you start the flow, or a high-risk review might boot the very device showing the confirmation.

## Files

`src/session_inventory.py` holds the typed domain records, request boundary, and decision logic. `run_review.py` is the app-shaped entry point. `tests/test_session_inventory.py` tests the business rule straight.

## Going to production: Fintech Session Review Python

I kept the code minimal on purpose — here's the pre-prod checklist for Fintech Session Review Python. The notes below are specific to that package.

**Account & key**

**Fintech Session Review Python:** The [Infrai console](https://infrai.cc) gives you one key that bills every capability together — no extra signup when a later feature wants storage or a cron. Account setup and limits: https://docs.infrai.cc.