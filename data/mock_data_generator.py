"""
Generates synthetic feedback data so the project can be built, tested,
and demoed without needing a live feedback stream.

Doesn't call any AI or DB — pure Python, so it runs instantly and free.
Tags every row with a source (app_review / tweet / support_ticket) and
seeds a deliberate spike of near-identical complaints so the anomaly
detector has something real to catch.

Run directly: python -m data.mock_data_generator
"""
import random
import csv
import datetime
import os
import sys

SOURCES = ["app_review", "tweet", "support_ticket"]

# Templates grouped loosely by intended category, so the generated
# data has enough real signal for the AI classifier to work with.
BUG_TEMPLATES = [
    "App crashes every time I try to open my cart",
    "Checkout page freezes on the payment step",
    "Getting a blank screen after I update the app",
    "Search results don't load, just an infinite spinner",
    "The order tracking page shows an error 500",
    "App logs me out randomly every few minutes",
]

PAYMENT_SPIKE_TEMPLATES = [
    "UPI payment failed at checkout, money got deducted though",
    "PhonePe failed on checkout, tried three times",
    "Payment gateway timed out during checkout with UPI",
    "checkout failed, UPI transaction shows failed but amount debited",
    "Can't complete checkout, UPI keeps failing on the payment step",
]

FEATURE_TEMPLATES = [
    "Would be great if I could save multiple addresses",
    "Please add a dark mode option",
    "Wish there was a way to filter by seller rating",
    "Can you add a 'buy again' button on past orders",
    "Would love wishlist sharing with friends",
]

COMPLAINT_TEMPLATES = [
    "Delivery was 5 days late with no notification",
    "Customer support took forever to respond to my ticket",
    "Product arrived damaged and refund process is so slow",
    "The new cart redesign is confusing, hard to find things",
    "Too many notifications, feels spammy",
]

PRAISE_TEMPLATES = [
    "Love how fast delivery was this time!",
    "Great app, super easy to use",
    "Customer service resolved my issue in minutes, impressed",
    "The new UI looks clean and modern",
]

SPAM_TEMPLATES = [
    "Check out my channel for free followers!!!",
    "asdkjaslkdj random text here",
    "Win a free iPhone click here www.notreal.example",
]

NOISE_PREFIXES = ["", "Ugh. ", "Seriously, ", "So annoyed. ", "FYI - ", "Update: "]
NOISE_SUFFIXES = ["", " Fix this please.", " !!!", " <br>", " 😡", " 🙄", " https://example.com/ref123"]


def _rand_timestamp(base: datetime.datetime, spread_hours: int) -> datetime.datetime:
    offset_minutes = random.randint(0, spread_hours * 60)
    return base + datetime.timedelta(minutes=offset_minutes)


def _make_row(text: str, source: str, timestamp: datetime.datetime) -> dict:
    noisy_text = f"{random.choice(NOISE_PREFIXES)}{text}{random.choice(NOISE_SUFFIXES)}"
    return {
        "source": source,
        "raw_text": noisy_text,
        "created_at": timestamp.isoformat(),
    }


def generate_mock_data(
    n_general: int = 350,
    n_spike: int = 22,
    spike_window_minutes: int = 45,
    seed: int | None = 42,
) -> list[dict]:
    """Returns a list of dicts: {source, raw_text, created_at}.

    n_general: number of ordinary feedback rows spread over the past week
    n_spike: number of near-identical payment-failure complaints clustered
             together in a short window, to trigger the anomaly detector
    """
    if seed is not None:
        random.seed(seed)

    rows = []
    now = datetime.datetime.now(datetime.timezone.utc)
    week_ago = now - datetime.timedelta(days=7)

    template_pool = (
        [(t, "Bug") for t in BUG_TEMPLATES]
        + [(t, "Feature Request") for t in FEATURE_TEMPLATES]
        + [(t, "Complaint") for t in COMPLAINT_TEMPLATES]
        + [(t, "Praise") for t in PRAISE_TEMPLATES]
        + [(t, "Spam") for t in SPAM_TEMPLATES]
    )

    # General background feedback, spread randomly over the last week
    for _ in range(n_general):
        text, _label = random.choice(template_pool)
        source = random.choice(SOURCES)
        timestamp = week_ago + datetime.timedelta(
            minutes=random.randint(0, 7 * 24 * 60)
        )
        rows.append(_make_row(text, source, timestamp))

    # Seeded spike: many similar payment-failure reports clustered in a
    # short recent window, so the anomaly detector has something to catch.
    spike_start = now - datetime.timedelta(hours=2)
    for _ in range(n_spike):
        text = random.choice(PAYMENT_SPIKE_TEMPLATES)
        source = random.choice(SOURCES)
        timestamp = _rand_timestamp(spike_start, spike_window_minutes // 60 or 1)
        rows.append(_make_row(text, source, timestamp))

    rows.sort(key=lambda r: r["created_at"])
    return rows


def save_to_csv(rows: list[dict], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "raw_text", "created_at"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    output_path = os.path.join(os.path.dirname(__file__), "sample_feedback.csv")
    data = generate_mock_data()
    save_to_csv(data, output_path)
    print(f"Generated {len(data)} rows -> {output_path}")
    sys.exit(0)
