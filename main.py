import logging, os, aiohttp
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, InlineQueryResultArticle, InputTextMessageContent, InputMediaPhoto
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes, InlineQueryHandler, ConversationHandler
from uuid import uuid4
from html import escape
from pymongo import MongoClient

load_dotenv()
BOT_TOKEN = os.environ['BOT_TOKEN']
GPTAPIKEY = os.getenv('GPTAPIKEY')
MCOG = MongoClient(os.getenv('MONGODB'))["luckbot"]["liveness"].find_one({"setting":"main"})

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /ping is issued."""
    print(context)
    await update.message.reply_text("Pong!🏓")


CHOICE, CHAT, IMAGE = range(3)
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks the user about their gender."""
    reply_keyboard = [["Chat", "Image"]]

    await update.message.reply_text(
        "Looking for Chat or Image?\n\n"
        "Send /cancel to stop",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="Chat or Image?"
        ),
    )
    return CHOICE

async def con_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the selected gender and asks for a photo."""
    user = update.message.from_user
    choice = update.message.text
    await update.message.reply_text(
        "Please send the prompt",
        reply_markup=ReplyKeyboardRemove(),
        quote=True
    )
    if choice == "Chat":
        return CHAT
    elif choice == "Image":
        return IMAGE        

async def con_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Call ChatGPT and ends the conversation."""
    user = update.message.from_user
    prompt = update.message.text
    if prompt == "":
        await update.message.reply_text("Input prompt directly behind commands", quote=True)
        return CHAT
    else:
        await update.message.reply_text( await chatgpt(prompt), quote=True)
        return ConversationHandler.END

async def con_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Call DALL E and ends the conversation."""
    user = update.message.from_user
    prompt = update.message.text
    if prompt == "":
        await update.message.reply_text("Input prompt directly behind commands", quote=True)
        return IMAGE
    else:
        output = await dallE(prompt)
        if type(output) == str:
            await update.message.reply_text(output)
        else:
            await update.message.reply_media_group(media=output, quote=True)
            return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text(
        "Alright, have a good day!", reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the inline query. This is run when you type: @botusername <query>"""
    query = update.inline_query.query

    if query == "":
        return

    results = [
        InlineQueryResultArticle(
            id=str(uuid4()),
            title="ChatGPT",
            input_message_content=InputTextMessageContent(await chatgpt(query)),
        )
    ]
    await update.inline_query.answer(results)

async def gpt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ Start ChatGPT API """
    cmd_len = update.message.entities[0].length
    prompt = update.message.text[cmd_len:]
    if prompt == "":
        await update.message.reply_text("Input prompt directly behind commands", quote=True)
    else:
        await update.message.reply_text( await chatgpt(prompt), quote=True)

async def image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ Start DALL E OpenAPI """
    cmd_len = update.message.entities[0].length
    prompt = update.message.text[cmd_len:]
    if prompt == "":
        await update.message.reply_text("Input prompt directly behind commands", quote=True)
    else:
        output = await dallE(prompt)
        if type(output) == str:
            await update.message.reply_text(output)
        else:
            await update.message.reply_media_group(media=output, quote=True)

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I didn't understand that command.")


async def dallE(prompt):
    async with aiohttp.ClientSession() as session:
        payload = {
        "prompt": prompt,
        "n": 2,
        "size": MCOG["chatgptsetting"]["imagesize"]
        }
        headers = {"Authorization": f"Bearer {GPTAPIKEY}"}
        async with session.post("https://api.openai.com/v1/images/generations", json=payload, headers=headers) as res:
            response = await res.json()
            print(response)
            if "error" in response:
                return response["error"]["message"]
            else:
                image1 = InputMediaPhoto(response["data"][0]["url"])
                image2 = InputMediaPhoto(response["data"][1]["url"])
                output = [image1,image2]
                return output
            
async def chatgpt(prompt):
    async with aiohttp.ClientSession() as session:
        payload = {
            "model": MCOG["chatgptsetting"]["model"],
            "prompt": prompt,
            "max_tokens": MCOG["chatgptsetting"]["max_token"],
            "temperature": MCOG["chatgptsetting"]["temperature"],
            "presence_penalty": MCOG["chatgptsetting"]["presence_penalty"],
            "frequency_penalty": MCOG["chatgptsetting"]["frequency_penalty"],
            "best_of": 1
        }
        headers = {"Authorization": f"Bearer {GPTAPIKEY}"}
        async with session.post("https://api.openai.com/v1/completions", json=payload, headers=headers) as res:
            response = await res.json()
            print(response)
            if "error" in response:
                return response["error"]["message"]
            else:
                reply = response["choices"][0]["text"]
                token = "Token Usage: " + str(response["usage"]["total_tokens"])
                return f"{reply}\n\n{token}"


if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).build()
     
    application.add_handler(CommandHandler('ping', ping))
    application.add_handler(CommandHandler("gpt", gpt))
    application.add_handler(CommandHandler("image", image))
    application.add_handler(InlineQueryHandler(inline_query))
    
    # Add conversation handler with the states
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("chat", chat)],
        states={
            CHOICE: [MessageHandler(filters.Regex("^(Chat|Image)$"), con_choice)],
            CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, con_chat)],
            IMAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, con_image)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)

    # Other handlers
    unknown_handler = MessageHandler(filters.COMMAND, unknown)
    application.add_handler(unknown_handler)

    application.run_polling()