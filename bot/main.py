import logging
import os
import re
from datetime import timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatMemberStatus
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from moderation import classify_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("cryptoaid")

GROUP = os.getenv("TELEGRAM_GROUP", "@cryptoAIDsupporter")
CHANNEL = os.getenv("TELEGRAM_CHANNEL", "@cryptoaidsup")

TEXT = {
 "en": {
  "welcome": "👋 Welcome to CryptoAID Support.\n\n🛡 Never share seed phrases, private keys, passwords or 2FA codes.\n\nI can help with CryptoAID, Web3 safety, scam awareness, wallets and support. Use /help or the buttons below.",
  "help": "🆘 CryptoAID Support\n/about — What is CryptoAID?\n/services — Services\n/security — Security guide\n/scam — Scam safety\n/recovery — Recovery safety\n/support — Get help\n/report — Report suspicious activity\n/links — Official links\n/language — Language",
  "about": "CryptoAID is a support, education and security-oriented ecosystem for crypto/Web3 users. This bot provides first-line community assistance and escalates uncertain or sensitive cases to human admins.",
  "security": "🛡 SECURITY FIRST\n• Never share seed/private keys.\n• Verify domains and usernames.\n• Treat unsolicited DMs as suspicious.\n• Read wallet signature requests before approving.\n• No legitimate CryptoAID admin needs your wallet secret.",
  "recovery": "🔎 Recovery safety: blockchain tracing may help investigate transactions, but tracing does not guarantee recovery. Never pay someone solely because they promise guaranteed recovery and never reveal wallet secrets.",
  "support": "🧭 Tell us what you need in this group without posting passwords, seed phrases, private keys or sensitive credentials. For uncertain or sensitive cases, a human admin should review the request.",
  "report": "🚨 To report suspicious activity, reply with public, non-secret evidence: username, public address/transaction hash, public URL and what happened. Never post credentials or seed phrases.",
 },
 "it": {
  "welcome": "👋 Benvenuto in CryptoAID Support.\n\n🛡 Non condividere mai seed phrase, chiavi private, password o codici 2FA.\n\nPosso aiutarti su CryptoAID, sicurezza Web3, scam, wallet e supporto. Usa /help o i pulsanti qui sotto.",
  "help": "🆘 Supporto CryptoAID\n/about — Cos'è CryptoAID?\n/services — Servizi\n/security — Guida sicurezza\n/scam — Sicurezza scam\n/recovery — Recovery sicuro\n/support — Assistenza\n/report — Segnala attività sospetta\n/links — Link ufficiali\n/language — Lingua",
  "about": "CryptoAID è un ecosistema orientato a supporto, educazione e sicurezza per utenti crypto/Web3. Il bot fornisce assistenza community di primo livello ed effettua escalation agli admin nei casi incerti o sensibili.",
  "security": "🛡 SECURITY FIRST\n• Non condividere seed/chiavi private.\n• Verifica domini e username.\n• Considera sospetti i DM non richiesti.\n• Leggi le richieste di firma del wallet prima di approvarle.\n• Nessun admin CryptoAID legittimo necessita dei segreti del tuo wallet.",
  "recovery": "🔎 Recovery sicuro: il tracing blockchain può aiutare a investigare transazioni, ma non garantisce il recupero. Diffida di chi promette recovery garantito e non rivelare mai segreti del wallet.",
  "support": "🧭 Scrivi nel gruppo cosa ti serve senza pubblicare password, seed phrase, chiavi private o credenziali sensibili. Per casi incerti o sensibili è prevista la revisione di un admin umano.",
  "report": "🚨 Per segnalare attività sospetta, invia solo prove pubbliche e non segrete: username, address/transaction hash pubblico, URL pubblico e descrizione. Mai credenziali o seed phrase.",
 }
}


def lang(update: Update) -> str:
    code = (update.effective_user.language_code or "en").lower() if update.effective_user else "en"
    return "it" if code.startswith("it") else "en"


def keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🛡 Security", callback_data="security"), InlineKeyboardButton("🆘 Support", callback_data="support")],[InlineKeyboardButton("🇮🇹 Italiano", callback_data="lang_it"), InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]])


async def send_key(update: Update, key: str, forced_lang=None):
    l = forced_lang or context_lang(update)
    await update.effective_message.reply_text(TEXT[l].get(key, TEXT[l]["help"]), reply_markup=keyboard() if key in {"welcome","help"} else None)


def context_lang(update: Update):
    return lang(update)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_key(update, "welcome")
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_key(update, "help")
async def about(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_key(update, "about")
async def security(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_key(update, "security")
async def scam(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_key(update, "security")
async def recovery(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_key(update, "recovery")
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_key(update, "support")
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_key(update, "report")

async def services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    l=context_lang(update); msg="🧰 CryptoAID: support, Web3 education, security awareness, scam reporting and recovery-oriented investigation guidance." if l=="en" else "🧰 CryptoAID: supporto, educazione Web3, sicurezza, segnalazioni scam e orientamento investigativo recovery."
    await update.effective_message.reply_text(msg)

async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("🔗 Official / Ufficiali\nWebsite: https://cryptoaid.support\nChannel: https://t.me/cryptoaidsup\nCommunity: https://t.me/cryptoAIDsupporter")

async def language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("Choose language / Scegli lingua", reply_markup=keyboard())

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    if q.data=="lang_it": await q.message.reply_text(TEXT["it"]["welcome"])
    elif q.data=="lang_en": await q.message.reply_text(TEXT["en"]["welcome"])
    elif q.data in ("security","support"): await q.message.reply_text(TEXT[context_lang(update)][q.data])

async def new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.is_bot: continue
        await update.message.reply_text(TEXT[context_lang(update)]["welcome"], reply_markup=keyboard())

async def moderate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_user: return
    result=classify_message(update.message.text)
    if result["level"] < 2: return
    member=await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    if member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}: return
    if result["level"] >= 4:
        await update.message.reply_text("🚨 Suspicious content detected / Contenuto sospetto rilevato. An admin review is recommended. Never share wallet secrets.")
    else:
        await update.message.reply_text("⚠️ Security warning / Avviso sicurezza: avoid suspicious promotions, secret requests and unsolicited links.")


def build_app():
    token=os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token: raise RuntimeError("TELEGRAM_BOT_TOKEN missing")
    app=Application.builder().token(token).build()
    commands={"start":start,"help":help_cmd,"about":about,"services":services,"security":security,"scam":scam,"recovery":recovery,"support":support,"report":report,"links":links,"language":language,"rules":security,"status":help_cmd}
    for name, handler in commands.items(): app.add_handler(CommandHandler(name, handler))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_members))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, moderate))
    return app

if __name__ == "__main__":
    log.info("Starting CryptoAID Support bot")
    build_app().run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)
