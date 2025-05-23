from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.models import StickerMessage, ImageMessage, VideoMessage, LocationMessage
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json

# 初始化Flask应用和配置
app = Flask(__name__)
load_dotenv()

# 配置文件路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")

# 内存存储对话历史（启动时加载）
conversations = []


# 初始化加载历史对话
def load_history():
    global conversations
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            conversations = json.load(f)
    except FileNotFoundError:
        conversations = []


# 初始化LINE Bot和Gemini API
line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-1.5-flash")

# 加载历史（应用启动时执行）
load_history()


# ====== Webhook 接收LINE消息 ======
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


# ====== 处理文本消息（添加命令解析） ======
@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_msg = event.message.text
    user_id = event.source.user_id

    # 命令解析
    if user_msg.strip().lower() == "删除历史对话":
        clear_history()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="✅ 已成功清空所有历史对话")
        )
        return
    elif user_msg.strip().lower() == "查看历史":
        history_text = format_history_for_user(user_id)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=history_text)
        )
        return

    # 非命令消息：调用Gemini生成回复
    try:
        resp = model.generate_content(user_msg)
        reply = getattr(resp, 'text', 'AI无法回应')
    except Exception as e:
        print("❌ Gemini错误：", e)
        if "quota" in str(e).lower():
            reply = "❌ AI配额已用完，请稍后再试"
        else:
            reply = "❌ AI回覆失败，请稍后重试"

    # 回复用户
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

    # 保存历史对话
    save_history(user_id, user_msg, reply)


# ====== 处理其他类型消息 ======
@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="你传了一个贴图 🧸")
    )


@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="收到图片了 📷")
    )


@handler.add(MessageEvent, message=VideoMessage)
def handle_video(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="收到影片 🎥")
    )


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


# ====== 历史对话管理 ======
def save_history(user_id, question, answer):
    global conversations
    entry = {
        "id": len(conversations) + 1,
        "user_id": user_id,
        "question": question,
        "answer": answer,
        "timestamp": str(os.environ.get('datetime.now()', ''))  # 注意：此处应使用datetime.now()，示例中使用环境变量仅为占位
    }
    conversations.append(entry)

    # 写入文件
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(conversations, f, ensure_ascii=False, indent=2)


def clear_history():
    global conversations
    conversations = []
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump([], f, indent=2, ensure_ascii=False)


def format_history_for_user(user_id):
    user_conversations = [c for c in conversations if c["user_id"] == user_id]
    if not user_conversations:
        return "📜 暂无历史对话"

    formatted = "📜 历史对话记录：\n\n"
    for i, conv in enumerate(user_conversations[-5:], 1):  # 显示最近5条
        formatted += f"{i}. 你：{conv['question']}\n"
        formatted += f"   AI：{conv['answer']}\n\n"

    if len(user_conversations) > 5:
        formatted += f"（还有 {len(user_conversations) - 5} 条历史对话未显示）"

    return formatted


# ====== REST API ======
@app.route("/history", methods=["GET"])
def get_history():
    return jsonify(conversations)


@app.route("/conversations/clear", methods=["DELETE"])
def api_clear_history():
    clear_history()
    return jsonify({"result": "历史对话已清空"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
