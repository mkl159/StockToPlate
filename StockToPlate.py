#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bot Telegram en Python 3 (v20+) avec:
- Multi-langue (FR/EN/ES) via LANGUAGE.
- Gestion convives (CSV).
- Récupération du stock via GET /stock (Grocy).
- Recherche (fallback) par plusieurs mots ou code-barres (ordre indifférent).
- Affichage correct du code-barres (ou "Aucun code-barres" si vide).
- Génération de recette via OpenAI (gpt-4o), envoyant TOUT le stock.
- Émojis, code user-friendly, commentaire en français.
- drop_pending_updates=True pour ignorer l'historique.
"""

import logging
import csv
import os
import requests
import asyncio
import nest_asyncio

from typing import List, Dict

nest_asyncio.apply()  # Évite "event loop already running" dans certains environnements

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

# Librairie openai
import openai

# -------------------------------------------------------------------
# Paramètre de langue : "FR", "EN", ou "ES"
# -------------------------------------------------------------------
LANGUAGE = "FR"

TEXTS = {
    "FR": {
        "welcome": (
            "👋 Bienvenue ! Tapez un ou plusieurs mots/code-barres pour chercher dans Grocy (avec affichage du code-barres). "
            "Ou utilisez le menu ci-dessous."
        ),
        "start_menu_label": "Pour plus d'actions, tapez /start 🍽️",
        "no_stock_found": "⚠️ Impossible de récupérer Grocy...",
        "barcode_not_found": "Aucun produit ne correspond à",
        "product_updated": "✅ Produit mis à jour dans Grocy avec succès.",
        "product_to_list": "🛒 Produit ajouté (fictif) à la liste de courses.",
        "choose_quantity": "Quelle quantité voulez-vous ajouter ou retirer ?",
        "recipe_generation": "🤖 Je lance la génération de la recette !",
        "invalid_number": "Veuillez envoyer un numéro valide.",
        "invalid_choice": "Choix invalide. Réessayez ou /start pour annuler.",
        # convives
        "convive_added": "✅ Le convive {name} a été ajouté.",
        "convive_exists": "❌ Le convive '{name}' existe déjà.",
        "convive_removed": "✅ Le convive {name} a été supprimé.",
        "convive_notfound": "❌ Le convive '{name}' n'existe pas.",
        "convive_modified": "✅ La liste d'aliments non supportés pour {name} a été mise à jour.",
        # fallback
        "fallback_menu": "Tapez le numéro du produit ou /start pour annuler."
    },
    "EN": {
        "welcome": (
            "👋 Welcome! Type one or more words/barcodes to search in Grocy (barcodes displayed). "
            "Or use the menu below."
        ),
        "start_menu_label": "For more actions, type /start 🍽️",
        "no_stock_found": "⚠️ Unable to retrieve Grocy...",
        "barcode_not_found": "No product matches",
        "product_updated": "✅ Product successfully updated in Grocy.",
        "product_to_list": "🛒 Product (fictitiously) added to the shopping list.",
        "choose_quantity": "Which quantity do you want to add or remove?",
        "recipe_generation": "🤖 Generating the recipe now!",
        "invalid_number": "Please send a valid number.",
        "invalid_choice": "Invalid choice. Retry or /start to cancel.",
        # convives
        "convive_added": "✅ The guest {name} has been added.",
        "convive_exists": "❌ Guest '{name}' already exists.",
        "convive_removed": "✅ Guest {name} has been removed.",
        "convive_notfound": "❌ Guest '{name}' does not exist.",
        "convive_modified": "✅ The list of unsupported foods for {name} has been updated.",
        # fallback
        "fallback_menu": "Type the product number or /start to cancel."
    },
    "ES": {
        "welcome": (
            "👋 ¡Bienvenido! Escribe una o varias palabras/códigos de barras para buscar en Grocy (se mostrarán los códigos de barras). "
            "O usa el menú de abajo."
        ),
        "start_menu_label": "Para más acciones, escribe /start 🍽️",
        "no_stock_found": "⚠️ No se puede recuperar Grocy...",
        "barcode_not_found": "Ningún producto coincide con",
        "product_updated": "✅ Producto actualizado con éxito en Grocy.",
        "product_to_list": "🛒 Producto (ficticio) agregado a la lista de compras.",
        "choose_quantity": "¿Qué cantidad deseas añadir o quitar?",
        "recipe_generation": "🤖 ¡Generando la receta ahora!",
        "invalid_number": "Por favor, envía un número válido.",
        "invalid_choice": "Opción no válida. Reintenta o /start para cancelar.",
        # convives
        "convive_added": "✅ El comensal {name} ha sido agregado.",
        "convive_exists": "❌ El comensal '{name}' ya existe.",
        "convive_removed": "✅ El comensal {name} ha sido eliminado.",
        "convive_notfound": "❌ El comensal '{name}' no existe.",
        "convive_modified": "✅ Se ha actualizado la lista de alimentos no compatibles para {name}.",
        # fallback
        "fallback_menu": "Escribe el número del producto o /start para cancelar."
    }
}

# -------------------------------------------------------------------
# Vos tokens & clés
# -------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
GROCY_API_KEY = "GROCY_API_KEY"
GROCY_BASE_URL = "http://xxx.xxx.xxx.xxx:9283"

OPENAI_API_KEY = "OPENAI_API_KEY"
OPENAI_MODEL = "gpt-4o"

CONVIVES_CSV = "convives.csv"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Définitions des états => range(10)
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
    """Initialise le CSV si besoin."""
    if not os.path.exists(file_path):
        with open(file_path,'w', newline='', encoding='utf-8') as f:
            w= csv.writer(f)
            w.writerow(["name","aliments_non_supportes"])

def read_convives(file_path: str):
    conv=[]
    if os.path.exists(file_path):
        with open(file_path,'r', newline='', encoding='utf-8') as f:
            r= csv.DictReader(f)
            for row in r:
                conv.append({
                    "name": row["name"],
                    "aliments_non_supportes": row["aliments_non_supportes"]
                })
    return conv

def ajouter_convive(nom: str, file_path: str):
    c= read_convives(file_path)
    for x in c:
        if x["name"].lower()== nom.lower():
            return False, TEXTS[LANGUAGE]["convive_exists"].format(name=nom)
    c.append({"name":nom,"aliments_non_supportes":""})
    with open(file_path,'w', newline='', encoding='utf-8') as f:
        w= csv.DictWriter(f, fieldnames=["name","aliments_non_supportes"])
        w.writeheader()
        for cc in c:
            w.writerow(cc)
    return True, TEXTS[LANGUAGE]["convive_added"].format(name=nom)

def supprimer_convive(nom:str, file_path:str):
    c= read_convives(file_path)
    newc= [xx for xx in c if xx["name"].lower()!= nom.lower()]
    if len(newc)== len(c):
        return False, TEXTS[LANGUAGE]["convive_notfound"].format(name=nom)
    with open(file_path,'w', newline='', encoding='utf-8') as f:
        w= csv.DictWriter(f, fieldnames=["name","aliments_non_supportes"])
        w.writeheader()
        for cc in newc:
            w.writerow(cc)
    return True, TEXTS[LANGUAGE]["convive_removed"].format(name=nom)

def modifier_aliments_convive(nom:str, aliments:str, file_path:str):
    c= read_convives(file_path)
    found= False
    for cc in c:
        if cc["name"].lower()== nom.lower():
            cc["aliments_non_supportes"]= aliments
            found= True
            break
    if not found:
        return False, TEXTS[LANGUAGE]["convive_notfound"].format(name=nom)
    with open(file_path,'w', newline='', encoding='utf-8') as f:
        w= csv.DictWriter(f, fieldnames=["name","aliments_non_supportes"])
        w.writeheader()
        for x in c:
            w.writerow(x)
    return True, TEXTS[LANGUAGE]["convive_modified"].format(name=nom)

# -------------------------------------------------------------------
# Grocy
# -------------------------------------------------------------------
def get_grocy_stock():
    """Appel GET /stock pour récupérer tout le stock, code-barres inclus."""
    url= f"{GROCY_BASE_URL}/api/stock"
    headers= {
        "GROCY-API-KEY": GROCY_API_KEY,
        "Accept":"application/json"
    }
    try:
        r= requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data= r.json()
        results=[]
        for item in data:
            prod= item.get("product", {})
            barcodes= prod.get("barcodes", [])
            if not barcodes:
                barcodes= ["Aucun code-barres"]
            results.append({
                "product_id": item.get("product_id",""),
                "product_name": prod.get("name","Inconnu"),
                "amount": item.get("amount",0),
                "best_before_date": item.get("best_before_date","N/A"),
                "barcodes": barcodes,
                "picture_url": prod.get("picture_url", None)
            })
        return results
    except Exception as e:
        logger.error(f"Erreur get_grocy_stock: {e}")
        return []

def update_grocy_product(product_id:str, new_amount:float):
    """Appel POST /stock/products/{product_id}/inventory pour mettre à jour la quantité."""
    url= f"{GROCY_BASE_URL}/api/stock/products/{product_id}/inventory"
    headers= {
        "GROCY-API-KEY": GROCY_API_KEY,
        "Accept":"application/json",
        "Content-Type":"application/json"
    }
    payload= {"new_amount": new_amount}
    try:
        resp= requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        logger.info(f"[Grocy] Update product {product_id} => {new_amount}")
    except requests.HTTPError as e:
        logger.error(f"HTTPError update_grocy_product: {e}")
    except Exception as ex:
        logger.error(f"Erreur inattendue update_grocy_product: {ex}")

# -------------------------------------------------------------------
# openai
# -------------------------------------------------------------------
def call_openai_chatgpt(stock_data:list, convives:list, note:str, nb_convives:int)->str:
    """Construit le prompt avec TOUT le stock (incluant code-barres) et envoie à gpt-4o."""
    openai.api_key= OPENAI_API_KEY

    lines= ""
    for p in stock_data:
        bc_join= ", ".join(p["barcodes"])
        lines+= (
            f"- {p['product_name']} (Qté:{p['amount']}, Péremption:{p['best_before_date']}, "
            f"Code-barres:{bc_join})\n"
        )
    c_str= ", ".join(convives) if convives else "Aucun"

    prompt= f"""
Je veux une recette pour {nb_convives} convive(s) : {c_str}.

Voici tout le stock de produits (priorité à ceux qui périment vite), incluant code-barres :
{lines}

Note spéciale : {note}.

Exigences:
1) Mentionne si un ingrédient manque ("il faudra l'acheter").
2) Indique le temps de préparation total.
3) Donne l'estimation des calories, lipides, glucides avant la recette.
4) Utilise des émojis 🍅🥦🍽️
5) Explique clairement les étapes.
6) Mentionne explicitement le nom du produit si présent en stock.
"""
    try:
        rep= openai.ChatCompletion.create(
            model=OPENAI_MODEL,
            messages=[{"role":"user","content":prompt}],
            temperature=0.7
        )
        return rep["choices"][0]["message"]["content"]
    except openai.OpenAIError as e:
        logger.error(f"OpenAIError: {e}")
        return "❌ Erreur OpenAI."
    except Exception as ex:
        logger.error(f"Erreur inattendue openai: {ex}")
        return "❌ Erreur inattendue."

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
async def telegram_send_long_message(context: ContextTypes.DEFAULT_TYPE, chat_id:int, text:str):
    """Envoie un (ou plusieurs) messages si le texte dépasse 4096 caractères."""
    max_len=4000
    for i in range(0,len(text),max_len):
        part= text[i:i+max_len]
        await context.bot.send_message(chat_id=chat_id, text=part)

def get_main_menu():
    """Renvoie le clavier principal."""
    kb= [
        ["➕ Créer Utilisateur", "➖ Supprimer Utilisateur"],
        ["🔧 Modifier Convive", "🍽️ Générer Recette"],
        ["❌ Quitter"]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def match_all_words(product_name:str, barcodes:list, query_words:list)->bool:
    """
    Retourne True si TOUS les mots de query_words apparaissent
    soit dans product_name, soit dans un code-barres, sans ordre imposé.
    """
    pn_lower= product_name.lower()
    bc_lower= [b.lower() for b in barcodes]

    for w in query_words:
        if not ((w in pn_lower) or any(w in bc for bc in bc_lower)):
            return False
    return True

# -------------------------------------------------------------------
# fallback => recherche
# -------------------------------------------------------------------
async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query= update.message.text.strip()
    if not query:
        return await start_handler(update, context)

    stock= get_grocy_stock()
    if not stock:
        await update.message.reply_text(TEXTS[LANGUAGE]["no_stock_found"])
        return ConversationHandler.END

    # On sépare la requête en mots
    words= query.lower().split()
    found=[]
    for p in stock:
        if match_all_words(p["product_name"], p["barcodes"], words):
            found.append(p)

    if not found:
        msg= f"{TEXTS[LANGUAGE]['barcode_not_found']} '{query}'\n{TEXTS[LANGUAGE]['start_menu_label']}"
        await update.message.reply_text(msg)
        return ConversationHandler.END
    else:
        context.user_data["search_results"]= found
        # On affiche : Nom, Qté, Code-Barres
        listing= ""
        for i, pr in enumerate(found,1):
            bc_str= ", ".join(pr["barcodes"])
            listing+= (
                f"{i}) {pr['product_name']} "
                f"(Qté:{pr['amount']}, Code-Barres:{bc_str})\n"
            )
        listing+= "\n" + TEXTS[LANGUAGE]["fallback_menu"]
        await update.message.reply_text(listing)
        return SEARCH_GROCY_RESULTS

async def search_grocy_results_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c= update.message.text.strip()
    if not c.isdigit():
        await update.message.reply_text(TEXTS[LANGUAGE]["invalid_number"])
        return SEARCH_GROCY_RESULTS

    idx= int(c)-1
    results= context.user_data.get("search_results",[])
    if idx<0 or idx>= len(results):
        await update.message.reply_text("Numéro invalide.")
        return SEARCH_GROCY_RESULTS

    sel= results[idx]
    context.user_data["selected_product"]= sel
    bc_str= ", ".join(sel["barcodes"])
    detail= (
        f"**{sel['product_name']}**\n"
        f"Qté: {sel['amount']}\n"
        f"Date péremption: {sel['best_before_date']}\n"
        f"Code-Barres: {bc_str}\n\n"
        "👉 Choisissez : Ajouter / Supprimer / Liste / Quitter"
    )
    kb= [
        ["Ajouter","Supprimer","Liste"],
        ["Quitter"]
    ]
    await update.message.reply_text(detail, parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return SEARCH_GROCY_DETAIL

async def search_grocy_detail_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c= update.message.text.strip().lower()
    sel= context.user_data.get("selected_product",{})
    if c=="quitter":
        await update.message.reply_text(TEXTS[LANGUAGE]["start_menu_label"])
        return ConversationHandler.END
    if c=="liste":
        logger.info(f"[Fictif] Ajout liste => {sel.get('product_name','?')}")
        await update.message.reply_text(TEXTS[LANGUAGE]["product_to_list"])
        return ConversationHandler.END
    if c in ["ajouter","supprimer"]:
        context.user_data["action"]= c
        await update.message.reply_text(TEXTS[LANGUAGE]["choose_quantity"],
            reply_markup=ReplyKeyboardRemove())
        return SEARCH_GROCY_QUANTITY

    await update.message.reply_text(TEXTS[LANGUAGE]["invalid_choice"])
    return SEARCH_GROCY_DETAIL

async def search_grocy_quantity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qstr= update.message.text.strip()
    if not qstr.isdigit():
        await update.message.reply_text(TEXTS[LANGUAGE]["invalid_number"])
        return SEARCH_GROCY_QUANTITY

    qty= int(qstr)
    action= context.user_data.get("action","ajouter")
    sel= context.user_data.get("selected_product",{})
    old= sel["amount"]
    new_amt= old+ qty if action=="ajouter" else max(0, old- qty)
    # On met à jour Grocy
    update_grocy_product(sel["product_id"], new_amt)
    sel["amount"]= new_amt
    await update.message.reply_text(TEXTS[LANGUAGE]["product_updated"])
    return ConversationHandler.END

# -------------------------------------------------------------------
# /start
# -------------------------------------------------------------------
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg= TEXTS[LANGUAGE]["welcome"]
    await update.message.reply_text(welcome_msg, reply_markup=get_main_menu())
    return MAIN_MENU

# -------------------------------------------------------------------
# main_menu_handler
# -------------------------------------------------------------------
async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c= update.message.text.strip()
    if c== "➕ Créer Utilisateur":
        await update.message.reply_text("Nom du convive ?", 
            reply_markup=ReplyKeyboardRemove())
        return CREER_UTILISATEUR_STATE

    elif c== "➖ Supprimer Utilisateur":
        await update.message.reply_text("Nom du convive à supprimer ?",
            reply_markup=ReplyKeyboardRemove())
        return SUPPRIMER_UTILISATEUR_STATE

    elif c== "🔧 Modifier Convive":
        convs= read_convives(CONVIVES_CSV)
        if not convs:
            await update.message.reply_text("Aucun convive dans le CSV.",
                reply_markup=get_main_menu())
            return MAIN_MENU
        rec= "Liste convives:\n"
        for v in convs:
            rec+= f"- {v['name']} (Non supportés: {v['aliments_non_supportes']})\n"
        rec+= "\nEx: Bob gluten, lactose"
        await update.message.reply_text(rec, reply_markup=ReplyKeyboardRemove())
        return MODIFIER_UTILISATEUR_STATE

    elif c== "🍽️ Générer Recette":
        await update.message.reply_text("Combien de convives ?",
            reply_markup=ReplyKeyboardRemove())
        return GEN_RECETTE_NB_CONVIVES

    elif c== "❌ Quitter":
        await update.message.reply_text("Au revoir !", 
            reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    else:
        await update.message.reply_text(TEXTS[LANGUAGE]["invalid_choice"],
            reply_markup=get_main_menu())
        return MAIN_MENU

# -------------------------------------------------------------------
# convives states
# -------------------------------------------------------------------
async def creer_utilisateur_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nom= update.message.text.strip()
    ok,msg= ajouter_convive(nom, CONVIVES_CSV)
    await update.message.reply_text(msg, reply_markup=get_main_menu())
    return MAIN_MENU

async def supprimer_utilisateur_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nom= update.message.text.strip()
    ok,msg= supprimer_convive(nom, CONVIVES_CSV)
    await update.message.reply_text(msg, reply_markup=get_main_menu())
    return MAIN_MENU

async def modifier_utilisateur_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inp= update.message.text.strip()
    if " " not in inp:
        await update.message.reply_text("Format incorrect. Ex: Bob gluten, lactose.")
        return MODIFIER_UTILISATEUR_STATE
    parts= inp.split(" ",1)
    n= parts[0]
    a= parts[1].strip()
    ok,msg= modifier_aliments_convive(n,a, CONVIVES_CSV)
    await update.message.reply_text(msg, reply_markup=get_main_menu())
    return MAIN_MENU

# -------------------------------------------------------------------
# Génération recette
# -------------------------------------------------------------------
async def generer_nb_convives(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c= update.message.text.strip()
    if not c.isdigit():
        await update.message.reply_text("Entrez un nombre valide.",
            reply_markup=get_main_menu())
        return MAIN_MENU
    nb= int(c)
    context.user_data["nb_convives"]= nb

    convs= read_convives(CONVIVES_CSV)
    if not convs:
        await update.message.reply_text(
            "Aucun convive dans la base. Entrez la note :",
            reply_markup=ReplyKeyboardRemove()
        )
        return GEN_RECETTE_NOTE

    context.user_data["convives_list"]= [xx["name"] for xx in convs]
    context.user_data["convives_sel"]= []
    kb=[]
    for x in convs:
        kb.append([KeyboardButton(x["name"])])
    kb.append([KeyboardButton("Aucun"), KeyboardButton("fin")])
    await update.message.reply_text(
        f"Sélectionnez jusqu'à {nb} convive(s). Puis tapez 'fin'.",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return GEN_RECETTE_SEL_CONVIVES

async def generer_sel_convives(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t= update.message.text.strip().lower()
    sel= context.user_data.get("convives_sel", [])
    nb= context.user_data.get("nb_convives", 1)
    cl= context.user_data.get("convives_list", [])

    if t== "fin":
        await update.message.reply_text("Entrez la note (ex: 'Protéines'):",
            reply_markup=ReplyKeyboardRemove())
        return GEN_RECETTE_NOTE

    if t=="aucun":
        if not sel:
            await update.message.reply_text("Aucun convive sélectionné. Entrez la note :")
        else:
            await update.message.reply_text(f"Convives: {', '.join(sel)}. Entrez la note :")
        return GEN_RECETTE_NOTE

    if t in [xx.lower() for xx in cl]:
        real_name= [xx for xx in cl if xx.lower()== t][0]
        sel.append(real_name)
        cl.remove(real_name)
        context.user_data["convives_sel"]= sel
        context.user_data["convives_list"]= cl
        if len(sel)>= nb:
            await update.message.reply_text("Sélection complète. Entrez la note :",
                reply_markup=ReplyKeyboardRemove())
            return GEN_RECETTE_NOTE
        else:
            await update.message.reply_text(
                f"Convive '{real_name}' ajouté. Tapez 'fin' ou continuez."
            )
    else:
        await update.message.reply_text("Convive non trouvé. Réessayez ou 'fin'.")
    return GEN_RECETTE_SEL_CONVIVES

async def generer_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note= update.message.text.strip()
    context.user_data["note"]= note

    stock= get_grocy_stock()
    if not stock:
        await update.message.reply_text(TEXTS[LANGUAGE]["no_stock_found"])
        # renvoit le menu
    else:
        # Affichage partiel
        p= f"Exemple de votre stock (total {len(stock)} produits)\n"
        for s in stock[:5]:
            bc_join= ", ".join(s["barcodes"])
            p+= f"- {s['product_name']} (Qté:{s['amount']}, Code-Barres:{bc_join})\n"
        await update.message.reply_text(p)

    sel= context.user_data.get("convives_sel",[])
    nbC= context.user_data.get("nb_convives",1)
    await update.message.reply_text(TEXTS[LANGUAGE]["recipe_generation"])
    rep= call_openai_chatgpt(stock, sel, note, nbC)
    if rep:
        # Envoi en plusieurs morceaux si besoin
        await telegram_send_long_message(context, update.effective_chat.id, rep)
    else:
        await update.message.reply_text("❌ Pas de réponse ChatGPT.")

    await update.message.reply_text(TEXTS[LANGUAGE]["start_menu_label"])
    return MAIN_MENU

# -------------------------------------------------------------------
# conv_handler
# -------------------------------------------------------------------
conv_handler= ConversationHandler(
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
    # Initialise le CSV convives
    init_csv_file(CONVIVES_CSV)

    application= Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(conv_handler)

    logger.info("Bot en train de se lancer... ✅")

    # On ignore l'historique
    await application.run_polling(drop_pending_updates=True)

if __name__== "__main__":
    asyncio.run(main())
