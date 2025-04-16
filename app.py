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

limiter = Limiter(key_func=lambda: request.get_json(force=True).get("session_id", "no-session"), app=app)

# In-memory session store (MVP-level)
sessions = {}

@app.before_request
def reject_invalid_token():
    if request.path in ["/ask", "/followup"] and request.method == "POST":
        try:
            data = request.get_json(force=True)
            if data.get("js_token") != "genuine-human":
                print("\U0001f6d1 Бот без js_token — отклонено", flush=True)
                return jsonify({"error": "Bot detected — invalid token"}), 403
        except:
            return jsonify({"error": "Malformed request"}), 403

@app.route('/')
def index():
    return "Lazy GPT API is running. Use POST /ask or /followup."

@app.route('/ask', methods=['POST'])
@limiter.limit("1 per minute", key_func=lambda: request.get_json(force=True).get("session_id", "no-session"))
def ask():
    return handle_request(request.get_json(), first=True)

@app.route('/followup', methods=['POST'])
def followup():
    return handle_request(request.get_json(), first=False)

@app.route("/confirm_payment", methods=["POST"])
def confirm_payment():
    session_id = request.json.get("session_id")
    if session_id in sessions:
        sessions[session_id]["payment_confirmed"] = True
        sessions[session_id]["paid_query_count"] = 0
        sessions[session_id]["current_payment_round"] = 1
        return jsonify({"status": "confirmed"})
    else:
        return jsonify({"error": "Session not found"}), 404

@app.route("/confirm_payment_round2", methods=["POST"])
def confirm_payment_round2():
    session_id = request.json.get("session_id")
    if session_id in sessions:
        sessions[session_id]["current_payment_round"] += 1
        sessions[session_id]["paid_query_count"] = 0
        return jsonify({"status": "confirmed_2nd_round"})
    else:
        return jsonify({"error": "Session not found"}), 404

def handle_request(data, first):
    session_id = data.get("session_id")
    user_input = data.get("prompt", "")
    action = data.get("action")

    if not session_id or not user_input:
        return jsonify({"error": "No session_id or prompt provided"}), 400

    if session_id not in sessions:
        sessions[session_id] = {
            "free_queries_used": 0,
            "payment_confirmed": False,
            "paid_query_count": 0,
            "current_payment_round": 0
        }

    session = sessions[session_id]

    if session["free_queries_used"] >= 2 and not session["payment_confirmed"]:
        return jsonify({
            "response": "Ваши бесплатные уточнения закончились.",
            "suggestions": [],
            "notice": "Бесплатные уточнения закончились.",
            "cta": {
                "text": "Продолжить за $0.99",
                "action": "show_payment_modal"
            },
            "status": "locked"
        })

    if session["payment_confirmed"] and session["paid_query_count"] >= 5:
        return jsonify({
            "response": "Вы использовали все уточнения после оплаты.",
            "suggestions": [],
            "notice": "Продолжить за $0.69",
            "cta": {
                "text": "Продолжить за $0.69",
                "action": "show_payment_modal_69"
            },
            "status": "locked_again"
        })

    if session["free_queries_used"] < 2:
        session["free_queries_used"] += 1
    elif session["payment_confirmed"]:
        session["paid_query_count"] += 1

    try:
        system_prompt = build_system_prompt(action, user_input)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
        )
        answer = response.choices[0].message.content

        suggestions = []
        if first and not action:
            followup_prompt = (
                "На основе следующего ответа предложи 3 follow-up действия в виде кнопок. "
                "Ответь только JSON-массивом без пояснений и без текста вокруг. Пример: [{\"label\": \"...\", \"action\": \"...\"}]\n\nОтвет:\n" + answer
            )

            followup = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Ты помощник, который помогает придумать follow-up действия."},
                    {"role": "user", "content": followup_prompt}
                ]
            )

            raw = followup.choices[0].message.content.strip()
            print("\U0001f501 Follow-up raw:", raw, flush=True)

            if "```" in raw:
                raw = raw.split("```")[-2].strip()

            try:
                suggestions = json.loads(raw)
            except:
                suggestions = []

        return jsonify({"response": answer, "suggestions": suggestions, "status": "free" if session["free_queries_used"] <= 2 else "paid"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def build_system_prompt(action, user_input):
    if action == "rephrase":
        return "Перефразируй следующий текст, сделай его более ясным, но сохрани суть:"
    elif action == "personalize":
        return "Сделай этот текст более личным и тёплым, обращённым к конкретному человеку:"
    elif action == "shakespeare":
        return "Преобразуй этот текст в стиль Вильяма Шекспира:"
    elif action and action.startswith("custom:"):
        custom_instruction = action.replace("custom:", "", 1).strip()
        return f"Преобразуй этот текст по следующему описанию: {custom_instruction}"
    else:
        return (
            "Ты — ленивый, но гениальный AI. Пользователь пишет всего одну фразу, "
            "и ты сразу создаешь идеальный, законченный, красиво оформленный ответ. "
            "Не задавай уточняющих вопросов. Просто выдай готовый результат.\n"
            f"Вот запрос: {user_input}"
        )

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
