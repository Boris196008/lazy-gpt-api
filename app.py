from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded
import os
from dotenv import load_dotenv
from openai import OpenAI
import sys

sys.stdout.reconfigure(line_buffering=True)
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
app = Flask(__name__)
CORS(app, supports_credentials=True)

# 🛡️ Отказ от запросов без session_id
@app.before_request
def reject_if_no_session():
    if request.path == '/ask':
        if not request.cookies.get("session_id"):
            print("❌ Отклонено: нет session_id", file=sys.stdout, flush=True)
            return jsonify({"error": "Запрос без session_id запрещён."}), 403

# 🔑 Ключ лимита
def get_user_identifier():
    session_id = request.cookies.get("session_id")
    if session_id:
        print(f"→ Лимит по session_id: {session_id}", file=sys.stdout, flush=True)
        return session_id
    ip = get_remote_address()
    print(f"→ Лимит по IP: {ip}", file=sys.stdout, flush=True)
    return ip

limiter = Limiter(
    key_func=get_user_identifier,
    app=app,
    default_limits=["1 per minute"]
)

@app.errorhandler(RateLimitExceeded)
def handle_rate_limit(e):
    print("🚫 Ограничение сработало — 429", file=sys.stdout, flush=True)
    return jsonify({"error": "🚫 Лимит: не чаще 1 раза в минуту."}), 429

@app.route('/')
def index():
    return "Lazy GPT API is running. Use POST /ask."

@app.route('/ask', methods=['POST'])
@limiter.limit("1 per minute", key_func=get_user_identifier)
def ask():
    data = request.get_json()
    user_input = data.get("prompt", "")

    if not user_input:
        return jsonify({"error": "No prompt provided"}), 400

    system_prompt = (
        "Ты — ленивый, но гениальный AI. Пользователь пишет всего одну фразу, "
        "и ты сразу создаешь идеальный, законченный, красиво оформленный ответ. "
        "Не задавай уточняющих вопросов. Просто выдай готовый результат.\n"
        f"Вот запрос: {user_input}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
        )
        answer = response.choices[0].message.content
        return jsonify({"response": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
