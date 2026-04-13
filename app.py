import os
import json
import requests
from flask import Flask, request, Response
from openai import OpenAI

app = Flask(__name__)

# إعدادات البيئة (سيتم استبدالها بالقيم الحقيقية من قبل المستخدم)
FB_VERIFY_TOKEN = os.environ.get('FB_VERIFY_TOKEN', 'my_secret_verify_token')
FB_PAGE_ACCESS_TOKEN = os.environ.get('FB_PAGE_ACCESS_TOKEN', '')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# تهيئة عميل OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# قاموس لتخزين سياق المحادثة البسيط (اختياري)
user_sessions = {}

def get_openai_response(sender_id, user_message):
    """الحصول على رد من OpenAI بناءً على رسالة المستخدم مع سياق بسيط"""
    try:
        # استرجاع سياق المستخدم أو إنشاء سياق جديد
        if sender_id not in user_sessions:
            user_sessions[sender_id] = [
                {"role": "system", "content": "أنت مساعد ذكي لبوت فيسبوك ماسنجر، ترد باللغة العربية بأسلوب مهذب ومفيد."}
            ]
        
        # إضافة رسالة المستخدم للسياق
        user_sessions[sender_id].append({"role": "user", "content": user_message})
        
        # الحفاظ على آخر 10 رسائل فقط لتوفير التكاليف والسياق
        if len(user_sessions[sender_id]) > 11:
            user_sessions[sender_id] = [user_sessions[sender_id][0]] + user_sessions[sender_id][-10:]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=user_sessions[sender_id]
        )
        
        ai_message = response.choices[0].message.content
        
        # إضافة رد الذكاء الاصطناعي للسياق
        user_sessions[sender_id].append({"role": "assistant", "content": ai_message})
        
        return ai_message
    except Exception as e:
        print(f"Error calling OpenAI: {e}")
        return "عذراً، واجهت مشكلة في معالجة طلبك حالياً."

def send_messenger_message(recipient_id, message_text):
    """إرسال رسالة إلى المستخدم عبر Facebook Send API"""
    params = {
        "access_token": FB_PAGE_ACCESS_TOKEN
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    })
    r = requests.post("https://graph.facebook.com/v19.0/me/messages", params=params, headers=headers, data=data)
    if r.status_code != 200:
        print(f"Error sending message: {r.status_code} - {r.text}")

@app.route('/webhook', methods=['GET'])
def verify():
    """التحقق من الـ Webhook من قبل فيسبوك"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == FB_VERIFY_TOKEN:
        print("WEBHOOK_VERIFIED")
        return Response(challenge, status=200)
    else:
        return Response("Verification failed", status=403)

@app.route('/webhook', methods=['POST'])
def webhook():
    """استقبال الرسائل ومعالجتها"""
    data = request.get_json()
    print(f"Received webhook data: {json.dumps(data, indent=2)}")

    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                if messaging_event.get("message"):
                    sender_id = messaging_event["sender"]["id"]
                    recipient_id = messaging_event["recipient"]["id"]
                    message_text = messaging_event["message"].get("text")

                    if message_text:
                        print(f"Received message from {sender_id}: {message_text}")
                        # الحصول على رد من OpenAI
                        ai_response = get_openai_response(sender_id, message_text)
                        # إرسال الرد للمستخدم
                        send_messenger_message(sender_id, ai_response)

    return Response("EVENT_RECEIVED", status=200)

@app.route('/', methods=['GET'])
def index():
    return "Facebook Messenger Bot is running!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
