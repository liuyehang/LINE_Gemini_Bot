from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.models import StickerMessage, ImageMessage, VideoMessage, LocationMessage
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json

app = Flask(__name__)
load_dotenv()

# LINE bot 初始化（v2）
line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))

# 初始化 Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-1.5-flash")  # 推荐模型

# ====== Webhook 接收 LINE 讯息 ======
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


# ====== 处理文字讯息 ======
@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_msg = event.message.text
    user_id = event.source.user_id
    try:
        resp = model.generate_content(user_msg)
        reply = getattr(resp, 'text', 'AI 无法回应')
    except Exception as e:
        print("❌ Gemini 错误：", e)
        if "quota" in str(e).lower():
            reply = "❌ AI 配额已用完，请稍后再试"
        else:
            reply = "❌ AI 回覆失败，请稍后重试"

    # 回覆使用者
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

    # 储存历史对话
    save_history(user_id, user_msg, reply)



# 贴图讯息
@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="你传了一个贴图 🧸")
    )

# 图片讯息
@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="收到图片了 📷")
    )

# 影片讯息
@handler.add(MessageEvent, message=VideoMessage)
def handle_video(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="收到影片 🎥")
    )

# 位置讯息
@handler.add(MessageEvent, message=LocationMessage)
def handle_location(event):
    address = event.message.address or "（无法取得地址）"
    lat = event.message.latitude
    lng = event.message.longitude
    reply = f"你传了位置：{address}\n经纬度：({lat}, {lng})"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

# ====== 储存历史对话到 JSON ======
def save_history(user_id, question, answer):
    try:
        with open("history.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = []
    data.append({"user_id": user_id, "question": question, "answer": answer})
    with open("history.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ====== REST API：查看历史记录 ======
@app.route("/history", methods=["GET"])
def get_history():
    try:
        with open("history.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = []
    return jsonify(data)


# ====== REST API：清空历史记录 ======
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")

@app.route("/history", methods=["DELETE"])
def delete_history():
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            f.write("[]")
        return jsonify({"message": "历史记录已清除"})
    except Exception as e:
        return jsonify({"error": f"删除失败: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )


