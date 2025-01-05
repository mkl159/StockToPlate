# Mon Bot Telegram (FR/EN/ES) avec Grocy et OpenAI

Ce projet contient un bot Telegram écrit en **Python 3 (v20+)** qui offre :
- Une gestion de convives (CSV).
- L'intégration de l'API Grocy (liste de produits, recherche par mot-clé ou code-barres).
- La génération de recettes via **OpenAI** (modèle `gpt-4o`).
- Un mode multi-langue (FR ou EN), réglé par la variable `LANGUAGE`.
- La possibilité d'ajouter/supprimer des quantités de produits directement depuis Telegram.

## Fonctionnalités principales
- **Recherche** de produits Grocy en tapant un mot ou un code-barres hors conversation.
- **Affichage** d'une liste numérotée, **sélection** d'un produit, **détails** (quantité, péremption, code-barres, photo).
- **Boutons** “Ajouter”, “Supprimer”, “Quitter” pour mettre à jour la quantité (fictivement, vous pouvez adapter l'API).
- **Gestion** de convives (ajout, suppression, modification).
- **Génération de recettes** avec mention explicite des produits en stock, priorisant ceux proches de la péremption, indiquant le temps de préparation, et signalant si un ingrédient manque ("il faudra l'acheter").
- **Emojis** et messages user-friendly.  
- **Menu principal** avec ReplyKeyboard (Créer/Supprimer convives, Générer Recette, Quitter).

## Installation

1. Cloner le dépôt :
   ```bash
   git clone https://github.com/votrepseudo/bot-telegram-grocy-openai.git
   cd bot-telegram-grocy-openai
   
2. Installer les dépendances :
   ```bash
   pip install python-telegram-bot==20.3 openai requests nest_asyncio

3. Éditer le fichier principal pour renseigner vos clés :
   ```bash
   TELEGRAM_BOT_TOKEN
   GROCY_API_KEY et GROCY_BASE_URL
   OPENAI_API_KEY et OPENAI_MODEL
   LANGUAGE = "FR" ou "EN" selon la langue souhaitée.

## Lancement
\```bash
python StockToPlate.py
\```

## Utilisation

- **Convives** : Ajouter, supprimer, modifier un convive.
- **Recherche Grocy** : Tapez un mot (ex: "sucre") ou un code-barres (ex: "1234567890123").
- **Générer Recette** : Choisir le nombre de convives, sélectionner les convives, saisir une note, et recevoir une recette d'OpenAI.










# #--------------------------------------------#
# My Telegram Bot (FR/EN) with Grocy and OpenAI

This project contains a Telegram bot written in **Python 3 (v20+)** that offers:
- Guest management (CSV).
- Integration with the Grocy API (product list, search by keyword or barcode).
- Recipe generation via **OpenAI** (model `gpt-4o`).
- Multi-language mode (FR or EN), set by the `LANGUAGE` variable.
- The ability to add/remove product quantities directly from Telegram.

## Main Features
- **Search** for Grocy products by typing a word or barcode outside of conversation.
- **Display** a numbered list, **select** a product, **details** (quantity, expiration, barcode, photo).
- **Buttons** “Add”, “Remove”, “Quit” to update the quantity (fictitiously, you can adapt the API).
- **Guest Management** (add, remove, modify).
- **Recipe Generation** with explicit mention of products in stock, prioritizing those near expiration, indicating preparation time, and signaling if an ingredient is missing ("it needs to be bought").
- **Emojis** and user-friendly messages.
- **Main Menu** with ReplyKeyboard (Create/Delete Guests, Generate Recipe, Quit).

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/votrepseudo/bot-telegram-grocy-openai.git
   cd bot-telegram-grocy-openai
2. Installer les dépendances :
   ```bash
   pip install python-telegram-bot==20.3 openai requests nest_asyncio

3. Éditer le fichier principal pour renseigner vos clés :
   ```bash
   TELEGRAM_BOT_TOKEN
   GROCY_API_KEY et GROCY_BASE_URL
   OPENAI_API_KEY et OPENAI_MODEL
   LANGUAGE = "FR" or "EN" as desired.

## Launch
\```bash
python StockToPlate.py
\```

## Usage

### Notes:
- **Code Blocks:** Ensure that the code blocks (enclosed by triple backticks ```bash) are properly formatted to display correctly on GitHub.
- **API Keys:** Replace the placeholder text (`TELEGRAM_BOT_TOKEN`, `GROCY_API_KEY`, etc.) with your actual API keys and configuration values in the main file of your project.
- **Script Name:** Make sure that `StockToPlate.py` is the correct name of your main script. If it's different, update it accordingly in the **Launch** section.

