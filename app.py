from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from openai import OpenAI
import sys
from flask_limiter import Limiter

sys.stdout.reconfigure(line_buffering=True)
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
app = Flask(__name__)
CORS(app)

limiter = Limiter(key_func=lambda: request.get_json(force=True).get("session_id", "no-session"), app=app)

@app.before_request
def reject_invalid_token():
    if request.path in ["/ask", "/followup"] and request.method == "POST":
        try:
            data = request.get_json(force=True)
            if data.get("js_token") != "genuine-human":
                print("🛑 Бот без js_token — отклонено", flush=True)
                return jsonify({"error": "Bot detected — invalid token"}), 403
        except:
            return jsonify({"error": "Malformed request"}), 403

@app.route('/')
def index():
    return "Lazy GPT API is running. Use POST /ask or /followup."

# 🔒 Ограниченный маршрут: первый запрос
@app.route('/ask', methods=['POST'])
@limiter.limit("1 per minute", key_func=lambda: request.get_json(force=True).get("session_id", "no-session"))
def ask():
    return handle_request(request.get_json(), first=True)

# 🚪 Безлимитный маршрут: follow-up кнопки
@app.route('/followup', methods=['POST'])
def followup():
    return handle_request(request.get_json(), first=False)

# 🔁 Общая логика генерации ответа

def handle_request(data, first):
    user_input = data.get("prompt", "")
    action = data.get("action")

    if not user_input:
        return jsonify({"error": "No prompt provided"}), 400

    if action == "rephrase":
        system_prompt = "Перефразируй следующий текст, сделай его более ясным, но сохрани суть:"
    elif action == "personalize":
        system_prompt = "Сделай этот текст более личным и тёплым, обращённым к конкретному человеку:"
    elif action == "shakespeare":
        system_prompt = "Преобразуй этот текст в стиль Вильяма Шекспира:"
    else:
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
