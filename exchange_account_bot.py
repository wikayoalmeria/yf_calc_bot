import os
import json
import re
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters
)

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def get_user_file(user_id: int):
    return os.path.join(DATA_DIR, f"user_{user_id}.json")

def load_data(user_id: int):
    path = get_user_file(user_id)
    if not os.path.exists(path):
        return {
            "percent": 10.0,
            "rate": 1.48,
            "records": []
        }
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(user_id: int, data):
    with open(get_user_file(user_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── 命令全部正常保留 ───
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """💰 抽成&汇率换算机器人

⚙️ 设置：
/percent 10    → 设置抽成比例 10%
/rate 1.48     → 设置汇率 1 USD = 1.48 SGD

📝 记账：
+1000   → 收到1000新币，自动算扣成+换算

📊 查看/管理：
/settings  → 当前比例&汇率
/list      → 历史记录
/clear     → 清空所有记录
"""
    await update.message.reply_text(text)

async def set_percent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ 用法：/percent 10")
        return
    try:
        pct = float(context.args[0])
        if not (0 <= pct <= 100): raise ValueError
    except ValueError:
        await update.message.reply_text("❌ 请输入0-100之间的数字")
        return
    data = load_data(update.effective_user.id)
    data["percent"] = pct
    save_data(update.effective_user.id, data)
    await update.message.reply_text(f"✅ 抽成比例：{pct}%")

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ 用法：/rate 1.48")
        return
    try:
        rate = float(context.args[0])
        if rate <= 0: raise ValueError
    except ValueError:
        await update.message.reply_text("❌ 请输入正确汇率数字")
        return
    data = load_data(update.effective_user.id)
    data["rate"] = rate
    save_data(update.effective_user.id, data)
    await update.message.reply_text(f"✅ 汇率：1 USD = {rate} SGD")

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data(update.effective_user.id)
    await update.message.reply_text(
        f"⚙️ 当前设置\n"
        f"抽成：{data['percent']}%\n"
        f"汇率：1 USD = {data['rate']} SGD"
    )

async def list_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data(update.effective_user.id)
    records = data["records"]
    if not records:
        await update.message.reply_text("📭 暂无记录")
        return
    text = "📋 最近10条记录：\n"
    for i, r in enumerate(records[-10:], 1):
        text += f"{i}. {r['time']} | {r['original_sgd']:.2f} SGD → {r['payout_usd']:.2f} USD\n"
    await update.message.reply_text(text)

async def clear_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = {"percent": 10.0, "rate": 1.48, "records": []}
    save_data(user_id, data)
    await update.message.reply_text("🗑️ 已清空所有记录")

# ─── 核心：只认 +数字 / -数字，其他聊天一概不理 ───
async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # ✅ 严格匹配：必须是 +数字 或 -数字，其他全部忽略不回复
    if not re.fullmatch(r'[+-]\d+(\.\d+)?', text):
        return  # 直接退出，不回复任何内容

    try:
        amount_sgd = float(text)
    except ValueError:
        return

    user_id = update.effective_user.id
    data = load_data(user_id)
    pct = data["percent"]
    rate = data["rate"]

    commission_sgd = abs(amount_sgd) * pct / 100
    remaining_sgd = abs(amount_sgd) - commission_sgd
    amount_usd = remaining_sgd / rate

    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "original_sgd": amount_sgd,
        "percent": pct,
        "rate": rate,
        "commission_sgd": commission_sgd,
        "remaining_sgd": remaining_sgd,
        "payout_usd": amount_usd
    }
    data["records"].append(record)
    save_data(user_id, data)

    sign = "+" if amount_sgd > 0 else "-"
    res = f"""🧾 计算完成
━━━━━━━━━━━━━━
收到：{sign}{abs(amount_sgd):.2f} SGD
抽成 {pct}%：-{commission_sgd:.2f} SGD
剩余：{remaining_sgd:.2f} SGD
汇率：1 USD = {rate:.2f} SGD
💵 到手：{amount_usd:.2f} USD
━━━━━━━━━━━━━━"""
    await update.message.reply_text(res)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 所有命令 → 正常工作
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("percent", set_percent))
    app.add_handler(CommandHandler("rate", set_rate))
    app.add_handler(CommandHandler("settings", show_settings))
    app.add_handler(CommandHandler("list", list_records))
    app.add_handler(CommandHandler("clear", clear_data))

    # 纯文本消息 → 只响应 +数字/-数字，其余沉默
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount))

    print("✅ 换算机器人运行中...")
    app.run_polling()

if __name__ == "__main__":
    main()