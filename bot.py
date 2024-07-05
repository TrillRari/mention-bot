import logging
import requests
import json
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# Remplace 'YOUR_TOKEN' par le token que tu as reçu de BotFather
TOKEN = '7322159641:AAHxfx7wxfJAFC6J1KJJEAlJWCo9ZNv_nNA'
OWNER_ID = 5691367640  # Remplacez par l'ID du propriétaire du bot
GROUPS_FILE = 'groups.json'

# Configurez le logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Charger les IDs de groupes et les membres depuis le fichier
def load_groups():
    try:
        with open(GROUPS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Sauvegarder les IDs de groupes et les membres dans le fichier
def save_groups(groups):
    with open(GROUPS_FILE, 'w') as f:
        json.dump(groups, f)

# Ajouter un groupe à la liste
def add_group(chat_id):
    groups = load_groups()
    if str(chat_id) not in groups:
        groups[str(chat_id)] = []
        save_groups(groups)

# Ajouter un membre au groupe
def add_member(chat_id, user):
    groups = load_groups()
    if str(chat_id) not in groups:
        groups[str(chat_id)] = []
    if user.id not in [member['id'] for member in groups[str(chat_id)]]:
        groups[str(chat_id)].append({'id': user.id, 'first_name': user.first_name})
        save_groups(groups)

# Nettoyer la commande '/broadcast' du texte
def clean_broadcast_command(text):
    command = "/broadcast"
    if text and text.startswith(command):
        return text[len(command):].strip()
    return text

# Commande pour démarrer le bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    add_group(update.message.chat_id)
    keyboard = [
        [InlineKeyboardButton("Menu", callback_data='menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        'Hello! Use the button below to interact with the bot.',
        reply_markup=reply_markup
    )

# Commande pour afficher les commandes disponibles
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "/start - Start the bot and add the group to the list\n"
        "/mention - Mention all members of the group (admins only)\n"
        "/solana - Shows the current price of Solana (SOL)\n"
        "/help - Shows this help message"
    )
    await update.message.reply_text(help_text)

# Enregistrer les membres qui envoient des messages
async def register_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    user = update.message.from_user
    add_member(chat_id, user)

# Vérifier si l'utilisateur est un admin
async def is_admin(chat_id, user_id, context) -> bool:
    try:
        chat_administrators = await context.bot.get_chat_administrators(chat_id)
        return any(admin.user.id == user_id for admin in chat_administrators)
    except Exception as e:
        logging.error(f"Error checking admin status: {e}")
        return False

# Commande pour afficher les administrateurs du groupe
async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    try:
        chat_administrators = await context.bot.get_chat_administrators(chat_id)
        admin_list = [f"{admin.user.id} - {admin.user.full_name}" for admin in chat_administrators]
        admin_text = "\n".join(admin_list) or "No administrators found."
        await update.message.reply_text(f"Administrators:\n{admin_text}")
    except Exception as e:
        logging.error(f"Error listing admins: {e}")
        await update.message.reply_text("Failed to list administrators.")

# Commande pour mentionner tous les membres du groupe
async def mention_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Vérifier si l'utilisateur est un admin (y compris anonymes)
    if not await is_admin(chat_id, user_id, context):
        await update.message.reply_text("You need to be an admin to use this command.")
        return

    groups = load_groups()
    if str(chat_id) in groups:
        members = groups[str(chat_id)]
        mentions = [f"[{member['first_name']}](tg://user?id={member['id']})" for member in members]

        mentions_per_message = 20  # Nombre de mentions par message
        messages = [', '.join(mentions[i:i + mentions_per_message]) for i in range(0, len(mentions), mentions_per_message)]

        for message in messages:
            await update.message.reply_text(message, parse_mode='Markdown')

# Fonction pour obtenir le prix actuel de Solana
def get_solana_price():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
    response = requests.get(url)
    data = response.json()
    return data['solana']['usd']

# Fonction pour répondre avec le prix de Solana
async def solana_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    price = get_solana_price()
    message = f"The current price of Solana (SOL) is ${price} USD."
    await update.message.reply_text(message)

# Fonction pour nettoyer la commande '/broadcast' du texte avant l'envoi
async def _broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return

    text = update.message.text
    text = clean_broadcast_command(text)
    
    # Si la commande est utilisée en réponse à un message
    if update.message.reply_to_message:
        reply_message = update.message.reply_to_message
        
        # Si le message en réponse contient une photo
        if reply_message.photo:
            photo = reply_message.photo[-1].file_id
            groups = load_groups()
            for chat_id in groups.keys():
                try:
                    await context.bot.send_photo(chat_id, photo=photo, caption=text)
                except Exception as e:
                    logging.error(f"Error sending photo to {chat_id}: {e}")
        elif reply_message.document:
            document = reply_message.document.file_id
            groups = load_groups()
            for chat_id in groups.keys():
                try:
                    await context.bot.send_document(chat_id, document=document, caption=text)
                except Exception as e:
                    logging.error(f"Error sending document to {chat_id}: {e}")
    
    # Gérer les images envoyées directement avec la commande
    elif update.message.photo:
        photo = update.message.photo[-1].file_id  # Prendre la meilleure qualité de photo
        caption = update.message.caption or ""  # Utiliser la légende de l'image, s'il y en a
        caption = clean_broadcast_command(caption)  # Nettoyer la légende de l'image

        groups = load_groups()
        for chat_id in groups.keys():
            try:
                await context.bot.send_photo(chat_id, photo=photo, caption=caption)
            except Exception as e:
                logging.error(f"Error sending photo to {chat_id}: {e}")

    # Gérer le texte
    elif text:
        groups = load_groups()
        for chat_id in groups.keys():
            try:
                await context.bot.send_message(chat_id, text=text)  # Pas de ParseMode ici
            except Exception as e:
                logging.error(f"Error sending message to {chat_id}: {e}")

    # Gérer les documents (comme PNG ou JPEG)
    elif update.message.document:
        document = update.message.document.file_id
        caption = update.message.caption or ""
        caption = clean_broadcast_command(caption)

        groups = load_groups()
        for chat_id in groups.keys():
            try:
                await context.bot.send_document(chat_id, document=document, caption=caption)
            except Exception as e:
                logging.error(f"Error sending document to {chat_id}: {e}")

# Gérer les interactions avec les boutons
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query.data == 'menu':
        keyboard = [
            [InlineKeyboardButton("Mention Members", callback_data='mention')],
            [InlineKeyboardButton("Solana Price", callback_data='solana')],
            [InlineKeyboardButton("Help", callback_data='help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            text="Choose a command:",
            reply_markup=reply_markup
        )

    elif query.data == 'mention':
        await query.message.reply_text("To mention all members, use the /mention command in the group.")

    elif query.data == 'solana':
        price = get_solana_price()
        await query.message.reply_text(f"The current price of Solana (SOL) is ${price} USD.")

    elif query.data == 'help':
        help_text = (
            "/start - Start the bot and add the group to the list\n"
            "/mention - Mention all members\n"
            "/solana - Get Solana price\n"
            "/help - Get help message"
        )
        await query.message.reply_text(help_text)

# Fonction principale
def main():
    # Créer l'application du bot
    application = Application.builder().token(TOKEN).build()

    # Ajouter des commandes
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("mention", "Mention all members"),
        BotCommand("solana", "Get Solana price"),
        BotCommand("help", "Get help message"),
        BotCommand("list_admins", "List all admins in the group")  # Ajout de la commande pour lister les admins
    ]

    # Définir les commandes disponibles pour le bot
    application.bot.set_my_commands(commands)

    # Ajouter les handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("mention", mention_all))
    application.add_handler(CommandHandler("solana", solana_price))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("broadcast", _broadcast))
    application.add_handler(CommandHandler("list_admins", list_admins))  # Ajout de la commande pour lister les admins
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, register_member))
    application.add_handler(MessageHandler(filters.PHOTO, _broadcast))
    application.add_handler(MessageHandler(filters.Document.ALL, _broadcast))
    application.add_handler(CallbackQueryHandler(button))

    # Exécuter le bot en mode polling
    application.run_polling()

if __name__ == '__main__':
    main()
