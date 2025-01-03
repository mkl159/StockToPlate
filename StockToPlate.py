#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bot Telegram en Python 3 (v20+) avec:
- Multi-langue (FR/EN) via variable LANGUAGE.
- Gestion convives (CSV).
- Intégration Grocy (liste produits).
- Recherche Grocy par mot-clé ou code-barres (liste numérotée, sélection, détail).
- Mise à jour (fictive) de la quantité : Ajouter/Supprimer.
- Génération recette via OpenAI (gpt-4o), mentionnant si l'ingrédient est en stock,
  indiquant le temps de préparation, priorisant les ingrédients proches de la péremption,
  et signalant si un ingrédient est manquant ("il faudra l'acheter").
- Emojis et messages user-friendly.
- Code commenté en français.
"""

import logging
import csv
import os
import requests
import asyncio
import nest_asyncio
import datetime
from typing import List, Dict

nest_asyncio.apply()

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
import openai

# -------------------------------------------------------------------
# Variable de langue : "FR" ou "EN"
# -------------------------------------------------------------------
LANGUAGE = "FR"

TEXTS = {
    "FR": {
        "welcome": "👋 Bienvenue dans votre bot ! Choisissez une option ci-dessous.\nTapez un mot ou un code-barres pour chercher dans Grocy.",
        "start_menu_label": "Pour générer des recettes ou chercher des recettes archivées, tapez /start 🍽️",
        "no_stock_found": "⚠️ Impossible de récupérer Grocy. On va continuer quand même...",
        "barcode_not_found": "Pas de produit correspondant à",
        "select_action": "Choisissez une action.",
        "choose_quantity": "Quelle quantité ?",
        "product_updated": "✅ Produit mis à jour avec succès.",
        "quit_msg": "Ok, tapez /start pour revenir au menu.",
        "invalid_number": "Veuillez envoyer un numéro. Ou /start pour annuler.",
        "invalid_choice": "Choix invalide. Envoyez Ajouter, Supprimer ou Quitter.",
        "quantity_enter_digit": "Veuillez envoyer un chiffre.",
        "recipe_generation": "🤖 Je lance la génération de recette !"
    },
    "EN": {
        "welcome": "👋 Welcome to your bot! Choose an option below.\nType a word or a barcode to search in Grocy.",
        "start_menu_label": "To generate recipes or search archived recipes, type /start 🍽️",
        "no_stock_found": "⚠️ Could not get Grocy. Let's continue anyway...",
        "barcode_not_found": "No product found for",
        "select_action": "Choose an action.",
        "choose_quantity": "Which quantity?",
        "product_updated": "✅ Product updated successfully.",
        "quit_msg": "Ok, type /start to return to the menu.",
        "invalid_number": "Please send a number or /start to cancel.",
        "invalid_choice": "Invalid choice. Send Add, Remove or Quit.",
        "quantity_enter_digit": "Please send a digit.",
        "recipe_generation": "🤖 Generating recipe now!"
    }
}

# -------------------------------------------------------------------
# Clés / Tokens
# -------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"

GROCY_API_KEY = "GROCY_API_KEY"
GROCY_BASE_URL = "http://xxx.xxx.xx.xxx:9283"

OPENAI_API_KEY = "sk-proj-OPENAI_API_KEY"
OPENAI_MODEL = "gpt-4o"

CONVIVES_CSV = "convives.csv"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# États (ConversationHandler)
# -------------------------------------------------------------------
(
    MAIN_MENU,
    CREER_UTILISATEUR_STATE,
    SUPPRIMER_UTILISATEUR_STATE,
    MODIFIER_UTILISATEUR_STATE,
    GEN_RECETTE_NB_CONVIVES,
    GEN_RECETTE_SEL_CONVIVES,
    GEN_RECETTE_NOTE,
    SEARCH_GROCY_RESULTS,
    SEARCH_GROCY_DETAIL,
    SEARCH_GROCY_QUANTITY
) = range(10)


# -------------------------------------------------------------------
# Fonctions CSV convives
# -------------------------------------------------------------------
def init_csv_file(file_path: str):
    if not os.path.exists(file_path):
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["name", "aliments_non_supportes"])

def read_convives(file_path: str):
    convives_list = []
    if os.path.exists(file_path):
        with open(file_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                convives_list.append({
                    "name": row["name"],
                    "aliments_non_supportes": row["aliments_non_supportes"]
                })
    return convives_list

def write_convives(file_path: str, convives_data: list):
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["name", "aliments_non_supportes"])
        writer.writeheader()
        for c in convives_data:
            writer.writerow({
                "name": c["name"],
                "aliments_non_supportes": c["aliments_non_supportes"]
            })

def ajouter_convive(nom: str, file_path: str):
    convives_list = read_convives(file_path)
    for c in convives_list:
        if c["name"].lower() == nom.lower():
            return False, f"❌ Le convive '{nom}' existe déjà."
    convives_list.append({"name": nom, "aliments_non_supportes": ""})
    write_convives(file_path, convives_list)
    return True, f"✅ Le convive '{nom}' a été ajouté avec succès."

def supprimer_convive(nom: str, file_path: str):
    convives_list = read_convives(file_path)
    new_list = [c for c in convives_list if c["name"].lower() != nom.lower()]
    if len(new_list) == len(convives_list):
        return False, f"❌ Le convive '{nom}' n'existe pas."
    write_convives(file_path, new_list)
    return True, f"✅ Le convive '{nom}' a été supprimé."

def modifier_aliments_convive(nom: str, aliments: str, file_path: str):
    convives_list = read_convives(file_path)
    found = False
    for c in convives_list:
        if c["name"].lower() == nom.lower():
            c["aliments_non_supportes"] = aliments
            found = True
            break
    if not found:
        return False, f"❌ Le convive '{nom}' n'existe pas."
    write_convives(file_path, convives_list)
    return True, f"✅ La liste d'aliments non supportés pour '{nom}' a été mise à jour."

# -------------------------------------------------------------------
# Grocy
# -------------------------------------------------------------------
def get_grocy_stock():
    url = f"{GROCY_BASE_URL}/api/stock"
    headers = {
        "GROCY-API-KEY": GROCY_API_KEY,
        "Accept": "application/json"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data:
            product = item.get("product", {})
            barcodes = product.get("barcodes", [])
            pic = product.get("picture_url", None)
            results.append({
                "product_id": item.get("product_id", ""),
                "product_name": product.get("name", "Inconnu"),
                "amount": item.get("amount", 0),
                "best_before_date": item.get("best_before_date", "N/A"),
                "barcodes": barcodes,
                "picture_url": pic
            })
        return results
    except Exception as e:
        logger.error(f"Erreur Grocy : {e}")
        return []

def update_grocy_product(product_id: str, new_amount: float):
    """
    Met à jour la quantité dans Grocy pour le produit product_id
    en faisant un POST réel vers l'endpoint d'inventaire.
    """
    url = f"{GROCY_BASE_URL}/api/stock/products/{product_id}/inventory"
    headers = {
        "GROCY-API-KEY": GROCY_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    payload = {
        "new_amount": new_amount,
        # "location_id": 1,  # si vous voulez préciser un emplacement
        # "spoiled": False,  # si nécessaire
        # d'autres champs facultatifs selon votre version Grocy
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()  # lèvera une HTTPError si code >= 400
        logger.info(f"Quantité mise à jour dans Grocy : product_id={product_id}, new_amount={new_amount}")
    except requests.HTTPError as e:
        logger.error(f"HTTPError lors de la mise à jour Grocy: {e}")
    except Exception as ex:
        logger.error(f"Erreur inattendue update_grocy_product: {ex}")


# -------------------------------------------------------------------
# OpenAI
# -------------------------------------------------------------------
def call_openai_chatgpt(stock_data: list, convives: list, note: str, nb_convives: int) -> str:
    openai.api_key = OPENAI_API_KEY

    # On construit la liste
    ingredients_str = ""
    for item in stock_data:
        ingredients_str += (
            f"- {item['product_name']} (Qté: {item['amount']}, "
            f"Péremption: {item['best_before_date']})\n"
        )
    convives_str = ", ".join(convives) if convives else "Aucun"

    # On insiste sur le temps de prép, mention manquants, etc.
    user_prompt = f"""
Je veux une recette à {nb_convives} convive(s) : {convives_str}.

Voici la liste des ingrédients disponibles (priorité à ceux qui périment vite) :
{ingredients_str}

Note spéciale : {note}.

Exigences :
1) Mentionne si un ingrédient manque ("il faudra l'acheter").
2) Indique le temps de préparation total.
3) Donne l'estimation des calories, lipides, glucides avant la recette.
4) Utilise des émojis 🍅🥦🍽️
5) Explique clairement les étapes.
6) Mentionne explicitement le nom exact du produit si présent en stock.
"""

    try:
        resp = openai.ChatCompletion.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.7
        )
        return resp["choices"][0]["message"]["content"]
    except openai.OpenAIError as e:
        logger.error(f"Erreur OpenAI : {e}")
        return "❌ Erreur OpenAI."
    except Exception as ex:
        logger.error(f"Erreur inattendue : {ex}")
        return f"❌ Erreur inattendue : {ex}"

# -------------------------------------------------------------------
# Helpers envoi message
# -------------------------------------------------------------------
async def telegram_send_long_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str):
    max_length = 4000
    for idx in range(0, len(text), max_length):
        part = text[idx:idx+max_length]
        await context.bot.send_message(chat_id=chat_id, text=part)

# -------------------------------------------------------------------
# Menu principal
# -------------------------------------------------------------------
def get_main_menu():
    keyboard = [
        ["➕ Créer Utilisateur", "➖ Supprimer Utilisateur"],
        ["🔧 Modifier Convive", "🍽️ Générer Recette"],
        ["❌ Quitter"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# -------------------------------------------------------------------
# fallback_handler
# Recherche par mot ou code-barres
# -------------------------------------------------------------------
async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        # on redirige vers /start
        return await start_handler(update, context)

    stock = get_grocy_stock()
    if not stock:
        await update.message.reply_text(TEXTS[LANGUAGE]["no_stock_found"])
        return ConversationHandler.END

    found = []
    for p in stock:
        # check code-barres
        if any(query in b for b in p["barcodes"]):
            found.append(p)
        # ou check product_name
        elif query.lower() in p["product_name"].lower():
            found.append(p)

    if not found:
        msg = f"{TEXTS[LANGUAGE]['barcode_not_found']} '{query}'\n{TEXTS[LANGUAGE]['start_menu_label']}"
        await update.message.reply_text(msg)
        return ConversationHandler.END

    context.user_data["search_results"] = found

    msg = "🧐 Produits trouvés :\n"
    for i, prod in enumerate(found, start=1):
        msg += f"{i}) {prod['product_name']} (Qté: {prod['amount']})\n"
    msg += f"\nEnvoyez le numéro du produit pour voir le détail.\n{TEXTS[LANGUAGE]['start_menu_label']}"
    await update.message.reply_text(msg)
    return SEARCH_GROCY_RESULTS

async def search_grocy_results_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    if not choice.isdigit():
        await update.message.reply_text(TEXTS[LANGUAGE]["invalid_number"])
        return SEARCH_GROCY_RESULTS

    idx = int(choice) - 1
    results = context.user_data.get("search_results", [])
    if idx < 0 or idx >= len(results):
        await update.message.reply_text("Numéro invalide.")
        return SEARCH_GROCY_RESULTS

    selected = results[idx]
    context.user_data["selected_product"] = selected
    # On affiche détail
    text_detail = (
        f"**{selected['product_name']}**\n"
        f"Qté: {selected['amount']}\n"
        f"Date péremption: {selected['best_before_date']}\n"
        f"Code-barres: {','.join(selected['barcodes'])}\n"
    )
    if selected.get("picture_url"):
        text_detail += f"[Photo]({selected['picture_url']})\n"
    text_detail += f"\n{TEXTS[LANGUAGE]['select_action']}\n"

    keyboard = [
        ["Ajouter", "Supprimer"],
        ["Quitter"]
    ]
    await update.message.reply_text(text_detail, parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return SEARCH_GROCY_DETAIL

async def search_grocy_detail_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip().lower()
    if choice == "quitter":
        await update.message.reply_text(TEXTS[LANGUAGE]["quit_msg"])
        return ConversationHandler.END

    if choice in ["ajouter", "supprimer"]:
        context.user_data["action"] = choice
        await update.message.reply_text(TEXTS[LANGUAGE]["choose_quantity"],
            reply_markup=ReplyKeyboardRemove())
        return SEARCH_GROCY_QUANTITY

    await update.message.reply_text(TEXTS[LANGUAGE]["invalid_choice"])
    return SEARCH_GROCY_DETAIL

async def search_grocy_quantity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qstr = update.message.text.strip()
    if not qstr.isdigit():
        await update.message.reply_text(TEXTS[LANGUAGE]["quantity_enter_digit"])
        return SEARCH_GROCY_QUANTITY

    qty = int(qstr)
    action = context.user_data.get("action", "ajouter")
    selected = context.user_data.get("selected_product")
    if not selected:
        await update.message.reply_text("Erreur: pas de produit sélectionné.")
        return ConversationHandler.END

    current_amt = selected["amount"]
    if action == "ajouter":
        new_amount = current_amt + qty
    else:
        new_amount = max(0, current_amt - qty)

    update_grocy_product(selected["product_id"], new_amount)
    selected["amount"] = new_amount

    await update.message.reply_text(TEXTS[LANGUAGE]["product_updated"])
    await update.message.reply_text(TEXTS[LANGUAGE]["start_menu_label"])
    return ConversationHandler.END

# -------------------------------------------------------------------
# start_handler
# -------------------------------------------------------------------
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = TEXTS[LANGUAGE]["welcome"]
    await update.message.reply_text(
        text=text,
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )
    return MAIN_MENU

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    if choice == "➕ Créer Utilisateur":
        await update.message.reply_text(
            "Veuillez entrer **le nom** du convive à créer :",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        return CREER_UTILISATEUR_STATE

    elif choice == "➖ Supprimer Utilisateur":
        await update.message.reply_text(
            "Veuillez entrer **le nom** du convive à supprimer :",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        return SUPPRIMER_UTILISATEUR_STATE

    elif choice == "🔧 Modifier Convive":
        # On récupère la liste, etc.
        convives_list = read_convives(CONVIVES_CSV)
        if not convives_list:
            await update.message.reply_text(
                "Aucun convive dans la base. Retour au menu principal.",
                parse_mode="Markdown",
                reply_markup=get_main_menu()
            )
            return MAIN_MENU

        recap = "🔧 **Liste des convives existants** :\n\n"
        for c in convives_list:
            alim = c["aliments_non_supportes"] or "Aucun"
            recap += f"- **{c['name']}** (non supportés : {alim})\n"
        recap += (
            "\nVeuillez entrer le **nom** du convive puis la liste d'aliments non supportés,\n"
            "séparés par une virgule.\nEx: `Bob gluten, lactose`"
        )
        await update.message.reply_text(
            recap,
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        return MODIFIER_UTILISATEUR_STATE

    elif choice == "🍽️ Générer Recette":
        await update.message.reply_text(
            "Combien de convives participeront au repas ? 🍽️\nVeuillez indiquer un nombre (chiffre).",
            reply_markup=ReplyKeyboardRemove()
        )
        return GEN_RECETTE_NB_CONVIVES

    elif choice == "❌ Quitter":
        await update.message.reply_text(
            "Merci d'avoir utilisé le bot. Au revoir !",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    else:
        await update.message.reply_text(
            "Choix invalide. Merci de cliquer sur un bouton du menu ci-dessous :",
            parse_mode="Markdown",
            reply_markup=get_main_menu()
        )
        return MAIN_MENU

# -------------------------------------------------------------------
# Création / Suppression / Modification convives
# -------------------------------------------------------------------
async def creer_utilisateur_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nom = update.message.text.strip()
    success, msg = ajouter_convive(nom, CONVIVES_CSV)
    await update.message.reply_text(msg, reply_markup=get_main_menu())
    return MAIN_MENU

async def supprimer_utilisateur_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nom = update.message.text.strip()
    success, msg = supprimer_convive(nom, CONVIVES_CSV)
    await update.message.reply_text(msg, reply_markup=get_main_menu())
    return MAIN_MENU

async def modifier_utilisateur_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    if " " not in user_input:
        await update.message.reply_text(
            "Format incorrect. Réessayez (ex : `Bob gluten, lactose`).",
            parse_mode="Markdown"
        )
        return MODIFIER_UTILISATEUR_STATE

    parts = user_input.split(" ", 1)
    nom_convive = parts[0]
    aliments = parts[1].strip()

    success, msg = modifier_aliments_convive(nom_convive, aliments, CONVIVES_CSV)
    await update.message.reply_text(msg, reply_markup=get_main_menu())
    return MAIN_MENU

# -------------------------------------------------------------------
# Générer Recette
# -------------------------------------------------------------------
async def generer_nb_convives(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if not txt.isdigit():
        await update.message.reply_text(
            "Veuillez entrer un **nombre valide**. Retour au menu principal.",
            parse_mode="Markdown",
            reply_markup=get_main_menu()
        )
        return MAIN_MENU

    nb = int(txt)
    context.user_data["nombre_convives"] = nb

    convives_list = read_convives(CONVIVES_CSV)
    if not convives_list:
        await update.message.reply_text(
            "Aucun convive connu. Saisissez la note pour ce repas :",
            reply_markup=ReplyKeyboardRemove()
        )
        return GEN_RECETTE_NOTE

    context.user_data["convives_list_remaining"] = [c["name"] for c in convives_list]
    context.user_data["convives_selectionnes"] = []

    # On propose un petit clavier
    kb = []
    for c in convives_list:
        kb.append([KeyboardButton(c["name"])])
    kb.append([KeyboardButton("Aucun"), KeyboardButton("fin")])

    await update.message.reply_text(
        f"Nous avons {len(convives_list)} convives possibles.\n"
        f"Sélectionnez jusqu'à {nb} convive(s). Ensuite, tapez 'fin'.",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return GEN_RECETTE_SEL_CONVIVES

async def generer_sel_convives(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip().lower()
    selected = context.user_data.get("convives_selectionnes", [])
    nb = context.user_data.get("nombre_convives", 1)
    convives_list_remaining = context.user_data.get("convives_list_remaining", [])

    if t == "fin":
        await update.message.reply_text(
            "Fin de sélection. Entrez la note (un mot, ex: 'Protéine' ou 'Végétarien') :",
            reply_markup=ReplyKeyboardRemove()
        )
        return GEN_RECETTE_NOTE

    if t == "aucun":
        if not selected:
            await update.message.reply_text("Aucun convive sélectionné. Entrez la note :")
        else:
            await update.message.reply_text(
                f"Convives déjà sélectionnés : {', '.join(selected)}.\nFin. Entrez la note :"
            )
        return GEN_RECETTE_NOTE

    # Sinon, on ajoute
    # On retire la casse, on compare convives_list_remaining
    if t in [x.lower() for x in convives_list_remaining]:
        # On retrouve le vrai nom
        for c in convives_list_remaining:
            if c.lower() == t:
                selected.append(c)
                convives_list_remaining.remove(c)
                break
        context.user_data["convives_selectionnes"] = selected
        context.user_data["convives_list_remaining"] = convives_list_remaining

        if len(selected) >= nb:
            await update.message.reply_text(
                f"Vous avez atteint {nb} convive(s). Entrez la note :",
                reply_markup=ReplyKeyboardRemove()
            )
            return GEN_RECETTE_NOTE
        else:
            await update.message.reply_text(
                f"Convive '{t}' ajouté. Choisissez-en d'autres ou tapez 'fin'."
            )
    else:
        await update.message.reply_text(
            f"Convive '{t}' n'est pas disponible. Réessayez ou tapez 'fin'."
        )

    return GEN_RECETTE_SEL_CONVIVES

async def generer_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = update.message.text.strip()
    context.user_data["note"] = note

    # On récupère le stock
    stock_data = get_grocy_stock()
    if not stock_data:
        await update.message.reply_text(TEXTS[LANGUAGE]["no_stock_found"])
    else:
        # On en affiche quelques-uns
        preview = "📦 **Quelques produits Grocy** :\n"
        for it in stock_data[:5]:
            preview += (
                f"- {it['product_name']} (Qté: {it['amount']}, "
                f"Péremption: {it['best_before_date']})\n"
            )
        await update.message.reply_text(preview, parse_mode="Markdown")

    selected_convives = context.user_data.get("convives_selectionnes", [])
    nb = context.user_data.get("nombre_convives", 1)

    await update.message.reply_text(TEXTS[LANGUAGE]["recipe_generation"])

    # Appel openai
    r = call_openai_chatgpt(
        stock_data=stock_data or [],
        convives=selected_convives,
        note=note,
        nb_convives=nb
    )
    if r:
        await telegram_send_long_message(context, update.effective_chat.id, r)
        # Rappel
        await update.message.reply_text(TEXTS[LANGUAGE]["start_menu_label"])
    else:
        await update.message.reply_text("❌ Pas de réponse ChatGPT.")

    await update.message.reply_text("👉 Sélection terminée ! Retour au menu principal.",
        reply_markup=get_main_menu())
    return MAIN_MENU

# -------------------------------------------------------------------
# Construction du conv_handler
# -------------------------------------------------------------------
conv_handler = ConversationHandler(
    entry_points=[
        MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_handler),
        CommandHandler("start", start_handler)
    ],
    states={
        MAIN_MENU: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler)
        ],
        CREER_UTILISATEUR_STATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, creer_utilisateur_state)
        ],
        SUPPRIMER_UTILISATEUR_STATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, supprimer_utilisateur_state)
        ],
        MODIFIER_UTILISATEUR_STATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, modifier_utilisateur_state)
        ],
        GEN_RECETTE_NB_CONVIVES: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, generer_nb_convives)
        ],
        GEN_RECETTE_SEL_CONVIVES: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, generer_sel_convives)
        ],
        GEN_RECETTE_NOTE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, generer_note)
        ],
        SEARCH_GROCY_RESULTS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, search_grocy_results_handler)
        ],
        SEARCH_GROCY_DETAIL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, search_grocy_detail_handler)
        ],
        SEARCH_GROCY_QUANTITY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, search_grocy_quantity_handler)
        ]
    },
    fallbacks=[CommandHandler("start", start_handler)]
)

# -------------------------------------------------------------------
# main
# -------------------------------------------------------------------
async def main():
    # init CSV
    init_csv_file(CONVIVES_CSV)
    # si on veut des archives de recettes => init un autre csv si besoin
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(conv_handler)

    logger.info("Bot démarré... ✅")
    await application.run_polling()

# -------------------------------------------------------------------
# Lancement
# -------------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
