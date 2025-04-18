from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from openai import OpenAI
import sys
from flask_limiter import Limiter
import json

sys.stdout.reconfigure(line_buffering=True)
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
app = Flask(__name__)
CORS(app)


def get_session_id():
    try:
        return request.get_json().get("session_id", "no-session")
    except:
        return "no-session"


limiter = Limiter(key_func=get_session_id, app=app)


@app.before_request
def reject_invalid_token():
    if request.path in ["/ask", "/followup"] and request.method == "POST":
        try:
            data = request.get_json()
            if data.get("js_token") != "genuine-human":
                print("\U0001f6a9 Бот без js_token — отклонено", flush=True)
                return jsonify({"error": "Bot detected — invalid token"}), 403
        except:
            return jsonify({"error": "Malformed request"}), 403


@app.route('/')
def index():
    return "Lazy GPT API is running. Use POST /ask or /followup."


@app.route('/ask', methods=['POST'])
@limiter.limit("1 per minute")
def ask():
    try:
        data = request.get_json()
        return handle_request(data, first=True)
    except:
        return jsonify({"error": "Invalid JSON"}), 400


@app.route('/followup', methods=['POST'])
def followup():
    try:
        data = request.get_json()
        return handle_request(data, first=False)
    except:
        return jsonify({"error": "Invalid JSON"}), 400


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
    elif isinstance(action, str) and action.startswith("custom:"):
        custom_instruction = action.replace("custom:", "", 1).strip()
        system_prompt = f"Преобразуй этот текст по следующему описанию: {custom_instruction}"
    else:
        system_prompt = (
            "Ты — гениальный помощник. Пользователь пишет всего одну фразу — ты сразу выдаёшь готовый, завершённый, красиво оформленный ответ. "
            "⚠️ Никогда не задавай уточняющих вопросов. "
            "Не пытайся вести диалог. Не используй фразы вроде \"Конечно!\" или \"Вот что я могу предложить\". "
            "Просто покажи результат — как будто ты уже понял всё правильно. "
            "Ответ должен быть структурирован, легко читаем и ощущаться как финальный. "
            "Стиль — краткий, умный, лаконичный."
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

        suggestions = []
        if not (isinstance(action, str) and (action.startswith("custom:") or action.startswith("http"))):
            followup_prompt = (
    "На основе следующего ответа предложи 3 follow-up действия, которые могли бы заинтересовать пользователя. "
    "Ты обязан выдать свежие и сфокусированные предложения — не повторяй предыдущий ответ. "
    "Если запрос касается еды — говори только про рестораны и гастрономию, а не маршруты. "

    "⚠️ Ответ строго в формате JSON-массива без текста вокруг. Пример: "
    "[{\"label\": \"...\", \"action\": \"...\"}] "
    "Никаких внешних ссылок: action не должен начинаться с http, содержать .com и т.п. "
    "Не предлагай кнопки вроде \"Спасибо\" или \"Завершить\" — только полезные действия."
)

            followup = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": followup_prompt},
                    {"role": "user", "content": answer}
                ]
            )

            raw = followup.choices[0].message.content.strip()
            print("\U0001f501 Follow-up raw:", raw, flush=True)

            if "```" in raw:
                parts = raw.split("```")
                if len(parts) >= 2:
                    raw = parts[1].strip()

            if raw.startswith("json"):
                raw = raw[4:].strip()

            print("\U0001f9fc Cleaned raw for JSON parsing:", repr(raw), flush=True)

            try:
                parsed = json.loads(raw)
                print("✅ Parsed follow-up JSON:", parsed, flush=True)
                if isinstance(parsed, list):
                    filtered = [
                        btn for btn in parsed
                        if isinstance(btn, dict)
                        and not any(btn.get("action", "").lower().startswith(prefix)
                                    for prefix in ("http://", "https://"))
                        and not any(s in btn.get("action", "").lower() for s in (".com", ".ru", ".org", ".net"))
                    ]
                    suggestions = filtered
                else:
                    print("⚠️ Parsed data is not a list", flush=True)
            except Exception as e:
                print(f"❌ JSON parse error: {e}", flush=True)

        return jsonify({"response": answer, "suggestions": suggestions})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
