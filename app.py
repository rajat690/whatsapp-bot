import os
from flask import Flask, request, jsonify

app = Flask(__name__)

# Choose a strong secret password for verification
VERIFY_TOKEN = "my_super_secret_token_123" 
ACCESS_TOKEN = "EAAPveWiYYE0BSWleZANUvoPEuRZCB2KU63FeZCeeUvCvsum2fcto0FbfomyGZB0ZBbnjLbrmIKbMDgm42fsttkbOC9SsBUSxmnZB79OsR08rQZCje39Xkev1Yk7Wr3LFWieqbRVENb0ZAarHp41tiSmXMI04r1RZBOUEygvxViK3HobL4755I55b8loQfOMBHHRJEkmn4nWn5J5BJm2EYqRrMa4ZARUUMnFJxCmOBrYNXJSAs5ocgOFp9d0rIBvm3TNoFtNGKLwP3x1VDdBwiIUZBydyvBCYEQ1pVcNiAZDZD"
PHONE_NUMBER_ID = "1250032938200043"

@app.route("/webhook", methods=["GET"], strict_slashes=False)
def verify_webhook():
    """Handles the initial Meta verification handshake."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            return "Forbidden", 403
    return "Missing parameters", 400

@app.route("/webhook", methods=["POST"], strict_slashes=False)
def receive_message():
    """Handles incoming WhatsApp messages from users."""
    body = request.json
    print("Received WhatsApp JSON Payload:")
    print(body) # This prints the incoming user text message to your server logs
    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
