import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- CONFIGURATION ---
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
            print("WEBHOOK_VERIFIED", flush=True)
            return challenge, 200
        else:
            return "Forbidden", 403
    return "Missing parameters", 400

@app.route("/webhook", methods=["POST"], strict_slashes=False)
def receive_message():
    """Handles incoming WhatsApp messages from users."""
    body = request.json
    
    # Real-time console tracking with flush=True
    print("Received WhatsApp JSON Payload:", flush=True)
    print(body, flush=True) 

    # Extract user message details and send response payload
    if body.get("object") and body.get("entry"):
        for entry in body["entry"]:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if "messages" in value:
                    for message in value["messages"]:
                        user_phone = message["from"]  
                        
                        if message.get("type") == "text":
                            user_text = message["text"]["body"]
                            
                            # Construct an automatic message reply string
                            bot_reply = f"🤖 Bot Prototype: I received your message: '{user_text}'!"
                            
                            # Execute outbound message transmission
                            send_whatsapp_message(user_phone, bot_reply)

    return jsonify({"status": "success"}), 200

def send_whatsapp_message(recipient_phone, message_text):
    """Sends a response back to the user via Meta's WhatsApp Cloud API."""
    # RECTIFIED: Explicitly structured forward slash endpoint string path
    url = f"https://facebook.com{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "text",
        "text": {
            "body": message_text
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"Reply sent successfully to {recipient_phone}", flush=True)
        else:
            print(f"Failed to send reply. Status: {response.status_code}, Response: {response.text}", flush=True)
    except Exception as e:
        print(f"An error occurred while sending message: {e}", flush=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
