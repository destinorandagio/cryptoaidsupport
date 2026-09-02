import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatMemberStatus
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from moderation import classify_message
from knowledge_engine import answer as knowledge_answer, detect_language

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("cryptoaid")

GROUP = os.getenv("TELEGRAM_GROUP", "@cryptoAIDsupporter")
CHANNEL = os.getenv("TELEGRAM_CHANNEL", "@cryptoaidsup")

TEXT = {
 "en": {
  "welcome": "👋 Welcome to CryptoAID Support.\n\n🛡 Never share seed phrases, private keys, passwords or 2FA codes.\n\nAsk me a question about CryptoAID, Web3 safety, scams, wallets, blockchain or recovery. I answer from verified CryptoAID knowledge and escalate when I am not sure.",
  "help": "🆘 CryptoAID Support\n/about — What is CryptoAID?\n/services — Services\n/ask <question> — Ask CryptoAID\n/security — Security guide\n/scam — Scam safety\n/recovery — Recovery safety\n/support — Get help\n/report — Report suspicious activity\n/links — Official links\n/language — Language",
  "security": "🛡 SECURITY FIRST\n• Never share seed/private keys.\n• Verify domains and usernames.\n• Treat unsolicited DMs as suspicious.\n• Read wallet signature requests before approving.\n• No legitimate CryptoAID admin needs your wallet secret.",
  "support": "🧭 Tell us what you need without posting passwords, seed phrases, private keys or sensitive credentials. If the knowledge base cannot answer safely, the bot will recommend human admin review.",
  "report": "🚨 Report only public, non-secret evidence: username, public address/transaction hash, public URL and what happened. Never post credentials or seed phrases."
 },
 "it": {
  "welcome": "👋 Benvenuto in CryptoAID Support.\n\n🛡 Non condividere mai seed phrase, chiavi private, password o codici 2FA.\n\nFammi una domanda su CryptoAID, sicurezza Web3, scam, wallet, blockchain o recovery. Rispondo usando conoscenza CryptoAID verificata e faccio escalation quando non sono sicuro.",
  "help": "🆘 Supporto CryptoAID\n/about — Cos'è CryptoAID?\n/services — Servizi\n/ask <domanda> — Chiedi a CryptoAID\n/security — Guida sicurezza\n/scam — Sicurezza scam\n/recovery — Recovery sicuro\n/support — Assistenza\n/report — Segnala attività sospetta\n/links — Link ufficiali\n/language — Lingua",
  "security": "🛡 SECURITY FIRST\n• Non condividere seed/chiavi private.\n• Verifica domini e username.\n• Considera sospetti i DM non richiesti.\n• Leggi le richieste di firma del wallet prima di approvarle.\n• Nessun admin CryptoAID legittimo necessita dei segreti del tuo wallet.",
  "support": "🧭 Scrivi cosa ti serve senza pubblicare password, seed phrase, chiavi private o credenziali sensibili. Se la knowledge non può rispondere in sicurezza, il bot consiglierà la revisione di un admin umano.",
  "report": "🚨 Segnala solo prove pubbliche e non segrete: username, address/transaction hash pubblico, URL pubblico e descrizione. Mai credenziali o seed phrase."
 }
}


def user_lang(update: Update) -> str:
    code = (update.effective_user.language_code or "en").lower() if update.effective_user else "en"
    return "it" if code.startswith("it") else "en"


def keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛡 Security", callback_data="security"), InlineKeyboardButton("🆘 Support", callback_data="support")],
        [InlineKeyboardButton("🇮🇹 Italiano", callback_data="lang_it"), InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
    ])


async def send_key(update: Update, key: str, forced_lang=None):
    language = forced_lang or user_lang(update)
    await update.effective_message.reply_text(TEXT[language].get(key, TEXT[language]["help"]), reply_markup=keyboard() if key in {"welcome", "help"} else None)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_key(update, "welcome")
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_key(update, "help")
async def security(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_key(update, "security")
async def scam(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_key(update, "security")
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_key(update, "support")
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_key(update, "report")


async def ask_text(update: Update, question: str):
    if not question.strip():
        await update.effective_message.reply_text("Ask a question after /ask. / Scrivi una domanda dopo /ask.")
        return
    language = detect_language(question)
    text, confidence, source = knowledge_answer(question, language)
    await update.effective_message.reply_text(text)
    log.info("knowledge_answer source=%s confidence=%.2f", source, confidence)


async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ask_text(update, " ".join(context.args))


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ask_text(update, "Cos'è CryptoAID?" if user_lang(update) == "it" else "What is CryptoAID?")


async def services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ask_text(update, "Quali servizi offre CryptoAID?" if user_lang(update) == "it" else "What services does CryptoAID provide?")


async def recovery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ask_text(update, "Come funziona il recovery CryptoAID?" if user_lang(update) == "it" else "How does CryptoAID recovery work?")


async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ask_text(update, "Quali sono i link ufficiali CryptoAID?" if user_lang(update) == "it" else "What are the official CryptoAID links?")


async def language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("Choose language / Scegli lingua", reply_markup=keyboard())


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "lang_it": await q.message.reply_text(TEXT["it"]["welcome"])
    elif q.data == "lang_en": await q.message.reply_text(TEXT["en"]["welcome"])
    elif q.data in ("security", "support"): await q.message.reply_text(TEXT[user_lang(update)][q.data])


async def new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.is_bot: continue
        await update.message.reply_text(TEXT[user_lang(update)]["welcome"], reply_markup=keyboard())


async def conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_user:
        return
    text = update.message.text
    result = classify_message(text)
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    is_admin = member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}

    if not is_admin and result["level"] >= 2:
        if result["level"] >= 4:
            await update.message.reply_text("🚨 Suspicious content detected / Contenuto sospetto rilevato. Human admin review recommended. Never share wallet secrets.")
        else:
            await update.message.reply_text("⚠️ Security warning / Avviso sicurezza: avoid suspicious promotions, secret requests and unsolicited links.")
        return

    # In private chats, direct mentions/replies, or explicit questions, act as the CryptoAID knowledge assistant.
    bot_username = (context.bot.username or "CryptoAIDsupportBOT").lower()
    mentioned = f"@{bot_username}" in text.lower()
    replied_to_bot = bool(update.message.reply_to_message and update.message.reply_to_message.from_user and update.message.reply_to_message.from_user.id == context.bot.id)
    looks_like_question = "?" in text or text.lower().startswith(("cos", "come", "cosa", "quali", "perché", "perche", "what", "how", "why", "where", "which", "can "))
    if update.effective_chat.type == "private" or mentioned or replied_to_bot or looks_like_question:
        cleaned = text.replace(f"@{context.bot.username}", "").strip() if context.bot.username else text
        await ask_text(update, cleaned)


def build_app():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing")
    app = Application.builder().token(token).build()
    commands = {
        "start": start, "help": help_cmd, "about": about, "services": services, "ask": ask_cmd,
        "security": security, "scam": scam, "recovery": recovery, "support": support,
        "report": report, "links": links, "language": language, "rules": security, "status": help_cmd
    }
    for name, handler in commands.items():
        app.add_handler(CommandHandler(name, handler))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_members))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, conversation))
    return app


if __name__ == "__main__":
    log.info("Starting CryptoAID Support knowledge bot")
    build_app().run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)
