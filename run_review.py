import json
import os

from src.session_inventory import InfraiClient, PaymentEvent, secure_payment_review


def main() -> None:
    event = PaymentEvent("payment-001", "creator-42", 12500, "USD", "session-current")
    notifications = secure_payment_review(
        InfraiClient(), event, event.session_id, int(os.environ.get("RISK_SCORE", "85"))
    )
    print(json.dumps([item.__dict__ for item in notifications], indent=2))


if __name__ == "__main__":
    main()

