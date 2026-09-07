import os
import requests
from flask import Flask, request, jsonify

from setu.interactive import (
    INTERACTIVE_BODY_MAX,
    build_interactive_payload,
    build_text_payload,
    outbound_sends,
    parse_inbound_message,
)
from setu.orchestrator import handle_message
from setu.session import get_session

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
                        if not user_phone:
                            continue

                        user_text = parse_inbound_message(message)
                        if user_text:
                            print(
                                f"Incoming from {user_phone}: {user_text}",
                                flush=True,
                            )
                            bot_reply = handle_message(user_phone, user_text)
                            outbound = get_session(user_phone).get("outbound") or {}
                            send_whatsapp_reply(user_phone, bot_reply, outbound)
                        else:
                            message_type = message.get("type")
                            if message_type:
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


def _meta_url() -> str:
    return (
        f"https://graph.facebook.com/"
        f"{GRAPH_API_VERSION}/{PHONE_NUMBER_ID}/messages"
    )


def _meta_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def _post_meta(payload: dict) -> bool:
    try:
        response = requests.post(
            _meta_url(),
            json=payload,
            headers=_meta_headers(),
            timeout=20,
        )
        print(
            f"Meta send response: {response.status_code} {response.text}",
            flush=True,
        )
        if response.ok:
            return True
        print(
            f"Failed to send payload. Status: {response.status_code}",
            flush=True,
        )
        return False
    except requests.RequestException as exc:
        print(f"Error sending WhatsApp message: {exc}", flush=True)
        return False


def send_text_message(recipient_phone: str, message_text: str) -> bool:
    """Plain-text fallback (also used when interactive send is not possible)."""
    if not ACCESS_TOKEN:
        print("WHATSAPP_ACCESS_TOKEN is missing.", flush=True)
        return False
    if not PHONE_NUMBER_ID:
        print("WHATSAPP_PHONE_NUMBER_ID is missing.", flush=True)
        return False
    payload = build_text_payload(recipient_phone, message_text)
    ok = _post_meta(payload)
    if ok:
        print(f"Reply sent successfully to {recipient_phone}", flush=True)
    return ok


def send_whatsapp_reply(recipient_phone: str, message_text: str, outbound: dict | None = None) -> bool:
    """Send one or more WhatsApp messages (detail then What-next when flagged)."""
    if not ACCESS_TOKEN:
        print("WHATSAPP_ACCESS_TOKEN is missing.", flush=True)
        return False
    if not PHONE_NUMBER_ID:
        print("WHATSAPP_PHONE_NUMBER_ID is missing.", flush=True)
        return False

    ok = True
    for spec in outbound_sends(message_text, outbound):
        if not _send_one_whatsapp(recipient_phone, spec):
            ok = False
    return ok


def _send_one_whatsapp(recipient_phone: str, spec: dict) -> bool:
    options = spec.get("options") or []
    body = spec.get("body") or ""
    list_button = spec.get("list_button") or "Choose"
    short_body = spec.get("short_body") or ""

    if options:
        interactive_body = short_body or body
        if not short_body and len(body) > INTERACTIVE_BODY_MAX:
            send_text_message(recipient_phone, body)
            interactive_body = "Choose an option:"
        payload = build_interactive_payload(
            recipient_phone,
            interactive_body,
            options,
            list_button=list_button,
        )
        if payload and _post_meta(payload):
            print(
                f"Interactive reply sent to {recipient_phone} "
                f"({len(options)} options)",
                flush=True,
            )
            return True
        print(
            "Interactive send failed or not applicable; falling back to text.",
            flush=True,
        )
        return send_text_message(recipient_phone, body)

    return send_text_message(recipient_phone, body)


def send_whatsapp_message(recipient_phone, message_text):
    """Back-compat text send used by older call sites."""
    return send_text_message(recipient_phone, message_text)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
