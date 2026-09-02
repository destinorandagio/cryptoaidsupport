import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatMemberStatus
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from moderation import classify_message
from knowledge_engine import answer as knowledge_answer, detect_language
from acquisition_engine import assess, next_step

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("cryptoaid")
GROUP = os.getenv("TELEGRAM_GROUP", "@cryptoAIDsupporter")
CHANNEL = os.getenv("TELEGRAM_CHANNEL", "@cryptoaidsup")
OFFICIAL_LINKS = {
    "website": "https://cryptoaid.support",
    "bot": "https://t.me/CryptoAIDsupportBOT",
    "group": "https://t.me/cryptoAIDsupporter",
    "channel": "https://t.me/cryptoaidsup",
}

TEXT = {
 "en": {
  "welcome": "👋 Welcome to CryptoAID Support.\n\n🛡 Never share seed phrases, private keys, passwords or 2FA codes.\n\nAsk about CryptoAID, Web3 safety, scams, wallets, blockchain, dead dApps/tokens or recovery. If you describe a real incident, I can help structure the public evidence needed for a CryptoAID Case.",
  "help": "🆘 CryptoAID Support\n/about — What is CryptoAID?\n/services — Services\n/ask <question> — Ask CryptoAID\n/security — Security guide\n/scam — Scam safety\n/recovery — Recovery safety\n/case — Case pre-assessment\n/checklist — Scam emergency checklist\n/support — Get help\n/report — Report suspicious activity\n/links — Official links\n/language — Language",
  "security": "🛡 SECURITY FIRST\n• Never share seed/private keys.\n• Verify domains and usernames.\n• Treat unsolicited DMs as suspicious.\n• Read wallet signature requests before approving.\n• No legitimate CryptoAID admin needs your wallet secret.",
  "support": "🧭 Tell us what you need without posting passwords, seed phrases, private keys or sensitive credentials. If the knowledge base cannot answer safely, human review is recommended.",
  "report": "🚨 Report only public, non-secret evidence: username, public address/transaction hash, public URL and what happened. Never post credentials or seed phrases.",
  "checklist": "🧲 CRYPTO SCAM EMERGENCY CHECKLIST\n1. Stop signing transactions.\n2. Never share seed/private keys.\n3. Preserve public tx hashes, wallet/contract addresses and URLs.\n4. Record project/token/dApp name and what happened.\n5. Use /case to structure a CryptoAID pre-assessment.\n\nNo recovery outcome is guaranteed.",
  "case": "🧭 CRYPTOAID CASE PRE-ASSESSMENT\nReply with: project/token/dApp name; what happened; approximate date; chain; public transaction hash/address/contract/URL if available.\n\n⚠️ Never send seed phrases, private keys, passwords or 2FA codes. No recovery outcome is guaranteed."
 },
 "it": {
  "welcome": "👋 Benvenuto in CryptoAID Support.\n\n🛡 Non condividere mai seed phrase, chiavi private, password o codici 2FA.\n\nChiedimi di CryptoAID, sicurezza Web3, scam, wallet, blockchain, dApp/token morti o recovery. Se descrivi un incidente reale, posso aiutarti a strutturare le evidenze pubbliche necessarie per un Case CryptoAID.",
  "help": "🆘 Supporto CryptoAID\n/about — Cos'è CryptoAID?\n/services — Servizi\n/ask <domanda> — Chiedi a CryptoAID\n/security — Guida sicurezza\n/scam — Sicurezza scam\n/recovery — Recovery sicuro\n/case — Pre-assessment Case\n/checklist — Checklist emergenza scam\n/support — Assistenza\n/report — Segnala attività sospetta\n/links — Link ufficiali\n/language — Lingua",
  "security": "🛡 SECURITY FIRST\n• Non condividere seed/chiavi private.\n• Verifica domini e username.\n• Considera sospetti i DM non richiesti.\n• Leggi le richieste di firma del wallet prima di approvarle.\n• Nessun admin CryptoAID legittimo necessita dei segreti del tuo wallet.",
  "support": "🧭 Scrivi cosa ti serve senza pubblicare password, seed phrase, chiavi private o credenziali sensibili. Se la knowledge non può rispondere in sicurezza, è raccomandata la revisione umana.",
  "report": "🚨 Segnala solo prove pubbliche e non segrete: username, address/transaction hash pubblico, URL pubblico e descrizione. Mai credenziali o seed phrase.",
  "checklist": "🧲 CHECKLIST EMERGENZA CRYPTO SCAM\n1. Interrompi nuove firme/transazioni.\n2. Non condividere seed/chiavi private.\n3. Conserva tx hash, address wallet/contract e URL pubblici.\n4. Annota progetto/token/dApp e cosa è successo.\n5. Usa /case per strutturare il pre-assessment CryptoAID.\n\nNessun risultato di recovery è garantito.",
  "case": "🧭 PRE-ASSESSMENT CASE CRYPTOAID\nRispondi indicando: progetto/token/dApp; cosa è successo; data approssimativa; chain; transaction hash/address/contract/URL pubblici se disponibili.\n\n⚠️ Mai seed phrase, chiavi private, password o 2FA. Nessun risultato di recovery è garantito."
 }
}

def user_lang(update: Update) -> str:
    code = (update.effective_user.language_code or "en").lower() if update.effective_user else "en"
    return "it" if code.startswith("it") else "en"

def keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧲 Checklist", callback_data="checklist"), InlineKeyboardButton("🧭 Start Case", callback_data="case")],
        [InlineKeyboardButton("🛡 Security", callback_data="security"), InlineKeyboardButton("🆘 Support", callback_data="support")],
        [InlineKeyboardButton("🇮🇹 Italiano", callback_data="lang_it"), InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
    ])

async def send_key(update: Update, key: str, forced_lang=None):
    language = forced_lang or user_lang(update)
    await update.effective_message.reply_text(TEXT[language].get(key, TEXT[language]["help"]), reply_markup=keyboard() if key in {"welcome", "help"} else None)

async def start(update, context): await send_key(update, "welcome")
async def help_cmd(update, context): await send_key(update, "help")
async def security(update, context): await send_key(update, "security")
async def scam(update, context): await send_key(update, "security")
async def support(update, context): await send_key(update, "support")
async def report(update, context): await send_key(update, "report")
async def checklist(update, context): await send_key(update, "checklist")
async def case_cmd(update, context): await send_key(update, "case")

async def ask_text(update: Update, question: str):
    if not question.strip():
        await update.effective_message.reply_text("Ask a question after /ask. / Scrivi una domanda dopo /ask."); return
    language = detect_language(question)
    intent = assess(question, ["dm_reply"] if update.effective_chat.type == "private" else [])
    if intent.safety_risk:
        await update.effective_message.reply_text(next_step(intent, language)); return
    text, confidence, source = knowledge_answer(question, language)
    await update.effective_message.reply_text(text)
    if intent.case_intent:
        await update.effective_message.reply_text(next_step(intent, language))
    log.info("knowledge_answer source=%s confidence=%.2f stage=%s score=%d", source, confidence, intent.stage, intent.score)

async def ask_cmd(update, context): await ask_text(update, " ".join(context.args))
async def about(update, context): await ask_text(update, "Cos'è CryptoAID?" if user_lang(update)=="it" else "What is CryptoAID?")
async def services(update, context): await ask_text(update, "Quali servizi offre CryptoAID?" if user_lang(update)=="it" else "What services does CryptoAID provide?")
async def recovery(update, context): await ask_text(update, "Come funziona il recovery CryptoAID?" if user_lang(update)=="it" else "How does CryptoAID recovery work?")
async def links(update, context):
    lang=user_lang(update)
    title="🔗 Link ufficiali CryptoAID" if lang=="it" else "🔗 Official CryptoAID links"
    body=f"{title}\n🌐 {OFFICIAL_LINKS['website']}\n🤖 {OFFICIAL_LINKS['bot']}\n💬 {OFFICIAL_LINKS['group']}\n📢 {OFFICIAL_LINKS['channel']}"
    await update.effective_message.reply_text(body, disable_web_page_preview=True)
async def language(update, context): await update.effective_message.reply_text("Choose language / Scegli lingua", reply_markup=keyboard())

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); lang=user_lang(update)
    if q.data=="lang_it": await q.message.reply_text(TEXT["it"]["welcome"], reply_markup=keyboard())
    elif q.data=="lang_en": await q.message.reply_text(TEXT["en"]["welcome"], reply_markup=keyboard())
    elif q.data in ("security","support","checklist","case"): await q.message.reply_text(TEXT[lang][q.data])

async def new_members(update, context):
    for member in update.message.new_chat_members:
        if not member.is_bot: await update.message.reply_text(TEXT[user_lang(update)]["welcome"], reply_markup=keyboard())

async def conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_user: return
    text=update.message.text; result=classify_message(text)
    member=await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    is_admin=member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}
    if not is_admin and result["level"] >= 2:
        await update.message.reply_text("🚨 Suspicious content detected / Contenuto sospetto rilevato. Human admin review recommended. Never share wallet secrets." if result["level"]>=4 else "⚠️ Security warning / Avviso sicurezza: avoid suspicious promotions, secret requests and unsolicited links."); return
    intent=assess(text, ["dm_reply"] if update.effective_chat.type=="private" else [])
    if intent.safety_risk:
        await update.message.reply_text(next_step(intent, detect_language(text))); return
    bot_username=(context.bot.username or "CryptoAIDsupportBOT").lower()
    mentioned=f"@{bot_username}" in text.lower()
    replied=bool(update.message.reply_to_message and update.message.reply_to_message.from_user and update.message.reply_to_message.from_user.id==context.bot.id)
    question="?" in text or text.lower().startswith(("cos","come","cosa","quali","perché","perche","what","how","why","where","which","can "))
    if update.effective_chat.type=="private" or mentioned or replied or question or intent.case_intent:
        cleaned=text.replace(f"@{context.bot.username}","").strip() if context.bot.username else text
        await ask_text(update, cleaned)

def build_app():
    token=os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token: raise RuntimeError("TELEGRAM_BOT_TOKEN missing")
    app=Application.builder().token(token).build()
    commands={"start":start,"help":help_cmd,"about":about,"services":services,"ask":ask_cmd,"security":security,"scam":scam,"recovery":recovery,"case":case_cmd,"checklist":checklist,"support":support,"report":report,"links":links,"language":language,"rules":security,"status":help_cmd}
    for name,handler in commands.items(): app.add_handler(CommandHandler(name,handler))
    app.add_handler(CallbackQueryHandler(button)); app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS,new_members)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,conversation)); return app

if __name__=="__main__":
    log.info("Starting CryptoAID Support + Social Acquisition bot")
    build_app().run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)
