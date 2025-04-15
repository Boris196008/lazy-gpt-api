from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded
import os
from dotenv import load_dotenv
from openai import OpenAI

# Загрузка .env (для локального запуска)
load_dotenv()

# Инициализация OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Flask-приложение
app = Flask(__name__)
CORS(app)

# Ограничение: 1 запрос в минуту на IP
limiter = Limiter(get_remote_address, app=app, default_limits=["1 per minute"])

# Обработчик превышения лимита
@app.errorhandler(RateLimitExceeded)
def handle_rate_limit(e):
    return jsonify({"error": "429 Too Many Requests: 1 per minute"}), 429

# Корневой маршрут (GET)
@app.route('/')
def index():
    return "Lazy GPT API is running. Use POST /ask."

# Основной маршрут (POST /ask)
@app.route('/ask', methods=['POST'])
@limiter.limit("1 per minute", key_func=lambda: request.cookies.get("session_id", request.remote_addr))
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

# Запуск (универсально — для Render и локально)
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
