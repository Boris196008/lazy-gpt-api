from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from openai import OpenAI

# Загрузка переменных окружения
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Инициализация Flask-приложения
app = Flask(__name__)
CORS(app)

# Корневой маршрут для проверки работоспособности
@app.route('/')
def index():
    return "Lazy GPT API is running. Use POST /ask."

# Основной маршрут /ask
@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    user_input = data.get("prompt", "")
    print("Получен запрос:", user_input)

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

# Запуск сервера (обязательно host=0.0.0.0 для Render)
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000)
