import os
import requests
from flask import Flask, request, jsonify

from setu.orchestrator import handle_message

app = Flask(__name__)

# Configure these in Render > Environment.
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
GRAPH_API_VERSION = os.environ.get("GRAPH_API_VERSION", "v23.0")


@app.route("/", methods=["GET"])
def health():
    """Simple health-check endpoint for Render."""
    return "WhatsApp bot is running", 200


@app.route("/webhook", methods=["GET"], strict_slashes=False)
def verify_webhook():
    """Handles Meta's webhook verification handshake."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("WEBHOOK_VERIFIED", flush=True)
        return challenge, 200

    print(
        f"Webhook verification failed. mode={mode}, "
        f"token_match={token == VERIFY_TOKEN}",
        flush=True,
    )
    return "Forbidden", 403


@app.route("/webhook", methods=["POST"], strict_slashes=False)
def receive_message():
    """Receives incoming WhatsApp webhook events from Meta."""
    body = request.get_json(silent=True)

    print("Received WhatsApp JSON Payload:", flush=True)
    print(body, flush=True)

    if not body:
        return jsonify({"status": "ignored", "reason": "empty payload"}), 200

    try:
        if body.get("object") == "whatsapp_business_account":
            for entry in body.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})

                    for message in value.get("messages", []):
                        user_phone = message.get("from")
                        message_type = message.get("type")

                        if not user_phone:
                            continue

                        user_text = None

                        if message_type == "text":
                            user_text = (
                                message.get("text", {})
                                .get("body", "")
                                .strip()
                            )
                        elif message_type == "interactive":
                            interactive = message.get("interactive", {})
                            itype = interactive.get("type")
                            if itype == "button_reply":
                                user_text = (
                                    interactive.get("button_reply", {})
                                    .get("title", "")
                                    .strip()
                                )
                            elif itype == "list_reply":
                                user_text = (
                                    interactive.get("list_reply", {})
                                    .get("title", "")
                                    .strip()
                                )

                        if user_text:
                            print(
                                f"Incoming from {user_phone}: {user_text}",
                                flush=True,
                            )
                            bot_reply = handle_message(user_phone, user_text)
                            send_whatsapp_message(user_phone, bot_reply)
                        elif message_type:
                            print(
                                f"Ignoring unsupported message type: "
                                f"{message_type}",
                                flush=True,
                            )

    except Exception as exc:
        # Keep the webhook acknowledged during debugging so Meta does not
        # repeatedly retry the same event.
        print(
            f"Error while processing webhook payload: {exc}",
            flush=True,
        )

    return jsonify({"status": "success"}), 200


def send_whatsapp_message(recipient_phone, message_text):
    """Sends a text reply through the WhatsApp Cloud API."""

    if not ACCESS_TOKEN:
        print("WHATSAPP_ACCESS_TOKEN is missing.", flush=True)
        return False

    if not PHONE_NUMBER_ID:
        print("WHATSAPP_PHONE_NUMBER_ID is missing.", flush=True)
        return False

    url = (
        f"https://graph.facebook.com/"
        f"{GRAPH_API_VERSION}/{PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    # WhatsApp text body max ~4096 chars
    if message_text and len(message_text) > 4000:
        message_text = message_text[:3990] + "…"

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_phone,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message_text,
        },
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=20,
        )

        print(
            f"Meta send response: "
            f"{response.status_code} {response.text}",
            flush=True,
        )

        if response.ok:
            print(
                f"Reply sent successfully to {recipient_phone}",
                flush=True,
            )
            return True

        print(
            f"Failed to send reply to {recipient_phone}. "
            f"Status: {response.status_code}",
            flush=True,
        )
        return False

    except requests.RequestException as exc:
        print(
            f"Error sending WhatsApp message: {exc}",
            flush=True,
        )
        return False


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
