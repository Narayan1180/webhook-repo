from flask import Flask, request, jsonify, render_template
from datetime import datetime
from models import events_collection
import os

app = Flask(__name__)

# ----------------- Date Helpers -----------------
def ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return str(n) + suffix


def format_utc_with_ordinal(ts):
    if not ts:
        return None

    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))

    day = ordinal(dt.day)
    month = dt.strftime("%B")
    year = dt.year
    time = dt.strftime("%I:%M %p")

    return f"{day} {month} {year} - {time} UTC"


# ----------------- Routes -----------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/events", methods=["GET"])
def get_events():
    events = (
        events_collection.find()
        .sort("timestamp_raw", -1)
        .limit(10)
    )

    response = []
    for e in events:
        response.append({
            #"request_id": e["request_id"],
            "event_type": e["action_type"],
            "author": e["author"],
            "from_branch": e.get("from_branch"),
            "to_branch": e.get("to_branch"),
            "timestamp": e["timestamp"]
        })

    return jsonify(response)


@app.route("/webhook", methods=["POST"])
def receive_webhook():
    event_type = request.headers.get("X-GitHub-Event")
    payload = request.json

    processed = {}

    if event_type == "push":
        processed = handle_push(payload)

    elif event_type == "pull_request":
        processed = handle_pr(payload)

    if processed:
        events_collection.insert_one(processed)

    return {"status": "received"}, 200


# ----------------- Event Handlers -----------------
def handle_push(payload):
    try:
        commit = payload.get("head_commit")
        if not commit:
            return {}

        ts = commit["timestamp"]

        return {
            "request_id": commit["id"],
            "action_type": "push",
            "author": payload["sender"]["login"],
            "from_branch": None,
            "to_branch": payload["ref"].split("/")[-1],
            "timestamp": format_utc_with_ordinal(ts),
            "timestamp_raw": datetime.fromisoformat(ts.replace("Z", "+00:00"))
        }
    except:
        return {}


def handle_pr(payload):
    pr = payload.get("pull_request")
    action = payload.get("action")

    if not pr:
        return {}

    # PR OPENED
    if action == "opened":
        ts = pr["created_at"]
        return {
            "request_id": pr["id"],
            "action_type": "pull_request",
            "author": pr["user"]["login"],
            "from_branch": pr["head"]["ref"],
            "to_branch": pr["base"]["ref"],
            "timestamp": format_utc_with_ordinal(ts),
            "timestamp_raw": datetime.fromisoformat(ts.replace("Z", "+00:00"))
        }

    # PR MERGED (ONLY IF ACTUALLY MERGED)
    if action == "closed" and pr.get("merged") and pr.get("merged_at"):
        ts = pr["merged_at"]
        return {
            "request_id": pr["id"],
            "action_type": "merge",
            "author": pr["merged_by"]["login"],
            "from_branch": pr["head"]["ref"],
            "to_branch": pr["base"]["ref"],
            "timestamp": format_utc_with_ordinal(ts),
            "timestamp_raw": datetime.fromisoformat(ts.replace("Z", "+00:00"))
        }

    return {}


# ----------------- Run Server -----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
