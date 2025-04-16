from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
import os
from dotenv import load_dotenv
from openai import OpenAI
import sys

sys.stdout.reconfigure(line_buffering=True)
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
app = Flask(__name__)
CORS(app)

# 🔑 Берём session_id из тела запроса
def get_user_identifier():
    try:
        data = request.get_json(force=True)
        sid = data.get("session_id")
        if sid:
            print(f"→ Лимит по session_id: {sid}", file=sys.stdout, flush=True)
            return sid
        print("❌ session_id отсутствует", file=sys.stdout, flush=True)
        return "no-session"
    except:
        print("❌ Ошибка при чтении session_id", file=sys.stdout, flush=True)
        return "error"

# 💥 Блокируем запросы без session_id
@app.before_request
def reject_if_no_session_id():
    if request.path == "/ask" and request.method == "POST":
        try:
            data = request.get_json(force=True)
            sid = data.get("session_id")
            if not sid:
                return jsonify({"error": "session_id отсутствует"}), 403
        except:
            return jsonify({"error": "Ошибка в теле запроса"}), 403

# 🔒 Лимит
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
