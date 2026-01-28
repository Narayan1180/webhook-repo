from flask import Flask, request
from datetime import datetime
from models import events_collection

from flask import Flask, jsonify
from pymongo import MongoClient
from datetime import datetime
from flask import render_template
import os


app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")



@app.route("/events", methods=["GET"])
def get_events():
    events = events_collection.find().sort("timestamp", -1).limit(10)

    response = []
    for e in events:
        response.append({
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
    data = request.json

    processed = {}

    if event_type == "push":
        processed = handle_push(data)

    elif event_type == "pull_request":
        processed = handle_pr(data)

    # Save only if we have something
    if processed:
        events_collection.insert_one(processed)

    return {"status": "received"}, 200

def handle_push(payload):
    try:
        return {
            "action_type": "push",
            "author": payload["pusher"]["name"],
            "from_branch": None,
            "to_branch": payload["ref"].split("/")[-1],
            "timestamp": payload["head_commit"]["timestamp"]
        }
    except:
        return {}

def handle_pr(payload):
    action = payload.get("action")

    # New PR created
    if action == "opened":
        pr = payload["pull_request"]
        return {
            "action_type": "pull_request",
            "author": pr["user"]["login"],
            "from_branch": pr["head"]["ref"],
            "to_branch": pr["base"]["ref"],
            "timestamp": pr["created_at"]
        }

    # PR merged
    elif action == "closed" and payload["pull_request"].get("merged"):
        pr = payload["pull_request"]
        return {
            "action_type": "merge",
            "author": pr["merged_by"]["login"],
            "from_branch": pr["head"]["ref"],
            "to_branch": pr["base"]["ref"],
            "timestamp": pr["merged_at"]
        }

    return {}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


