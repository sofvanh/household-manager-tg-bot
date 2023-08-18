import os
import requests
import logging
import time
from datetime import datetime

from fastapi import FastAPI, Request
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext, Application, ContextTypes
from deta import Deta

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
ALLOWED_USERNAMES = os.getenv("ALLOWED_USERNAMES").split(" ")

deta = Deta()
usersdb = deta.Base("users")
rewardsdb = deta.Base("rewards")
historydb = deta.Base("history")

# TODO Error handler for better logging
# TODO Add /help command
# TODO Make messages even friendlier

def is_allowed_user(username):
    return username in ALLOWED_USERNAMES

def user_exists(username):
    response = usersdb.fetch({"username": username})
    logging.warn(response.count)
    return response.count > 0

async def verify_user_exists(update):
    if not user_exists(update.message.from_user.username):
        await update.message.reply_text("You're not registered yet 😮 Send /register to register.")
        return False
    return True

async def record_action(username, action, points, description):
    currentTime = time.time()
    historydb.put({
        "username": username, 
        "action": action, 
        "points": points, 
        "description": description, 
        "time": currentTime
    })

async def greet_user(update, context):
    if not await verify_user_exists(update):
        return

    await update.message.reply_text(
        f"Hi {update.message.from_user.first_name} 😊 Here's a list of available commands.",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("/status")],
            [KeyboardButton("/addpoints")], 
            [KeyboardButton("/addreward")],
            [KeyboardButton("/redeem")],
            [KeyboardButton("/history")]],
            one_time_keyboard=True, 
            resize_keyboard=True
        )
    )

async def register(update, context):
    username = update.message.from_user.username

    if not is_allowed_user(username):
        await update.message.reply_text("Sorry, you're not allowed to register 😔")
        return
    
    response = usersdb.fetch({"username": username})
    if response.count > 0:
        await update.message.reply_text("You're already registered 😌")
        return
    
    name = update.message.from_user.first_name
    usersdb.put({"username": username, "name": name, "points": 0})
    await record_action(username, "register", 0, "Registered to the household")
    await update.message.reply_text(f"{name}, you're now registered to our household 😊 Your points start at 0.")

async def status(update, context):
    if not await verify_user_exists(update):
        return

    response = usersdb.fetch()
    message = "Here's the status of all users:\n"
    for user in response.items:
        message += f"{user['name']} - {user['points']} points\n"
    await update.message.reply_text(message)

async def showHistory(update, context):
    if not await verify_user_exists(update):
        return

    if len(context.args) == 0:
        message = "Here's your history.\nTo see the history of other users, use the following format: /history <username>\n\n"
        username = update.message.from_user.username
    else:
        message = "Here's the history of the user you requested.\n\n"
        username = context.args[0]
    
    response = historydb.fetch({"username": username})
    response.items.sort(key=lambda x: x['time'], reverse=True)

    if (response.count == 0):
        message += "No history found."
    else:
        for action in response.items:
            dt = datetime.fromtimestamp(action['time'])
            formatted_date = dt.strftime("%d/%m/%Y %H:%M:%S")
            message += f"{formatted_date} - {action['points']} points - {action['description']}\n"
    
    await update.message.reply_text(message)

async def add_points(update, context):
    if not await verify_user_exists(update):
        return

    if len(context.args) != 1:
        await update.message.reply_text("Please use the following format: /add_points <points>")
        return
    
    points = int(context.args[0])
    response = usersdb.fetch({"username": update.message.from_user.username})
    user = response.items[0]
    user["points"] += points
    usersdb.put(user)
    await record_action(user["username"], "add_points", user["points"], f"Added {points} points")
    await update.message.reply_text(f"Added {points} points to your account 🥳 You now have {user['points']} points.")

async def add_reward(update, context):
    if not await verify_user_exists(update):
        return

    if len(context.args) < 2:
        await update.message.reply_text("Please use the following format: /add_reward <reward_name> <cost>")
        return

    reward_name = " ".join(context.args[:-1])
    cost = int(context.args[-1])
    rewardsdb.put({"reward_name": reward_name, "cost": cost})
    await update.message.reply_text(f"Reward '{reward_name}' added with cost {cost} points.")

async def select_reward(update, context):
    if not await verify_user_exists(update):
        return
    
    rewards = rewardsdb.fetch()

    if rewards.count == 0:
        await update.message.reply_text("Reward shop is empty 🕸️")
    else:
        keyboard = [[InlineKeyboardButton(f"{reward['reward_name']} ({reward['cost']}p)", callback_data=reward["key"])] for reward in rewards.items]
        keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Please select a reward to redeem:", reply_markup=reply_markup)

async def button(update: Update, context) -> None:
    if not await user_exists(update.callback_query.from_user.username):
        return

    if update.callback_query.data == "cancel":
        await update.callback_query.edit_message_text("Cancelled")
        return
    
    response = rewardsdb.fetch({"key": update.callback_query.data})
    logging.warn(response)
    logging.warn(response.items)
    reward = response.items[0]
    await update.callback_query.edit_message_text(f"Are you sure you want to redeem '{reward['reward_name']}' for {reward['cost']} points?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Yes", callback_data=f"confirm_{reward['key']}"), InlineKeyboardButton("No", callback_data="cancel")]]))
    
async def confirm_redeem(update: Update, context) -> None:
    if not await user_exists(update.callback_query.from_user.username):
        return

    reward_key = update.callback_query.data.split("_")[1]
    rewards = rewardsdb.fetch({"key": reward_key})
    logging.warn(rewards)
    logging.warn(rewards.items)
    reward = rewards.items[0]
    user = usersdb.fetch({"username": update.callback_query.from_user.username}).items[0]
    if user["points"] < reward["cost"]:
        await update.callback_query.edit_message_text("You don't have enough points 😔")
        return

    user["points"] -= reward["cost"]
    usersdb.put(user)
    await record_action(user["username"], "redeem", user["points"], f"Redeemed '{reward['reward_name']}' for {reward['cost']} points")
    await update.callback_query.edit_message_text(f"Redeemed '{reward['reward_name']}' for {reward['cost']} points 🥳 You now have {user['points']} points.")


telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler('register', register))
telegram_app.add_handler(CommandHandler('status', status))
telegram_app.add_handler(CommandHandler('history', showHistory))
telegram_app.add_handler(CommandHandler('addpoints', add_points))
telegram_app.add_handler(CommandHandler('addreward', add_reward))
telegram_app.add_handler(CommandHandler('redeem', select_reward))
telegram_app.add_handler(CallbackQueryHandler(confirm_redeem, pattern=r"^confirm_"))
telegram_app.add_handler(CallbackQueryHandler(button))
telegram_app.add_handler(MessageHandler(filters.TEXT, greet_user))

app = FastAPI()

@app.post("/telegram")
async def telegram_webhook(req: Request):
    data = await req.json()
    logging.warn(data)
    async with telegram_app:
        await telegram_app.process_update(Update.de_json(data, telegram_app.bot))

@app.get("/set_webhook")
def url_setter():
    PROG_URL = os.getenv("DETA_SPACE_APP_HOSTNAME")
    set_url = f"{BOT_URL}/setWebHook?url=https://{PROG_URL}/telegram"
    res = requests.get(set_url)
    return res.json()
