# LINE Gemini Chatbot

这是一个使用 Flask 构建的 LINE 聊天机器人，集成 Google Gemini API，具备以下功能：

- ✅ 支援 LINE Webhook 回调
- ✅ 连接 Gemini API 进行智能问答
- ✅ 聊天纪录储存与 REST API 查询
- ✅ Flask + Ngrok 本地联机

## 功能说明

- `/callback`：LINE Webhook 回传接口
- `/history`：
  - `GET`：取得聊天纪录
  - `DELETE`：清空聊天纪录

## 安装方式

```bash
pip install -r requirements.txt
