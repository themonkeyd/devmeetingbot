import json
import random
import os
from datetime import datetime
from pathlib import Path
import pytz
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ChatAction

# Configuration
TOKEN = os.getenv("TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID"))  # conversion en int
TIMEZONE = pytz.timezone(os.getenv("TIMEZONE"))  # maintenant Africa/Douala
DATA_FILE = os.getenv("DATA_FILE")

# Participants
PARTICIPANTS = ["Loic", "Harrison", "Marc", "Tanguy", "Ifeyi"]

# Calendrier mois
MOIS_FR = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
    7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre"
}

# Tour fixe 1 (nov-mars) et 2 (avr-août)
TOUR_1 = {11: "Tanguy", 12: "Harrison", 1: "Marc", 2: "Loic", 3: "Ifeyi"}
TOUR_2 = {4: "Ifeyi", 5: "Loic", 6: "Marc", 7: "Harrison", 8: "Tanguy"}


class MeetingManager:
    def __init__(self, data_file=DATA_FILE):
        self.data_file = data_file
        self.data = self.load_data()

    def load_data(self):
        if Path(self.data_file).exists():
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"history": {}, "random_tours": {}, "cycle_count": 0}

    def save_data(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_cycle_type(self, reference_month=None):
        """Détermine si c'est un cycle normal ou inversé"""
        if reference_month is None:
            reference_month = datetime.now(TIMEZONE).month
        
        # De novembre à août (mois 11 à 8), on alterne chaque 5 mois
        # Cycle 0 : nov-mars (normal)
        # Cycle 1 : avr-août (inversé)
        # Cycle 2 : sep-nov (normal)
        # etc...
        
        if reference_month >= 9:
            cycle_num = (reference_month - 9) // 5
        else:
            cycle_num = ((reference_month + 3) // 5)
        
        return "normal" if cycle_num % 2 == 0 else "inversé"

    def get_speaker_for_month(self, month):
        """Retourne le nom de la personne pour un mois donné"""
        if month in TOUR_1:
            return TOUR_1[month]
        if month in TOUR_2:
            return TOUR_2[month]
        # De septembre à décembre : aléatoire (avec cycle alternant)
        year = datetime.now().year
        key = f"{year}-{month}"
        if key not in self.data["random_tours"]:
            self.data["random_tours"][key] = random.choice(PARTICIPANTS)
            self.save_data()
        return self.data["random_tours"][key]

    def get_speaker_current_month(self):
        """Retourne le responsable du mois en cours"""
        return self.get_speaker_for_month(datetime.now(TIMEZONE).month)

    def get_next_speaker(self):
        """Retourne le prochain participant"""
        current_month = datetime.now(TIMEZONE).month
        next_month = current_month + 1 if current_month < 12 else 1
        return self.get_speaker_for_month(next_month)

    def get_planning(self):
        """Retourne le planning du cycle actuel"""
        planning = []
        current_month = datetime.now(TIMEZONE).month
        
        # Déterminer le cycle actuel
        if current_month >= 11 or current_month <= 3:
            months = [11, 12, 1, 2, 3]
            tour_dict = TOUR_1
            cycle_name = "ordre normal"
        elif current_month <= 8:
            months = [4, 5, 6, 7, 8]
            tour_dict = TOUR_2
            cycle_name = "ordre inversé"
        else:  # septembre à octobre
            months = [9, 10, 11, 12, 1]
            tour_dict = None
            cycle_name = "ordre normal (aléatoire jusqu'à nov)"

        for m in months:
            if tour_dict:
                speaker = tour_dict.get(m, "?")
            else:
                speaker = self.get_speaker_for_month(m)
            mois_name = MOIS_FR.get(m, "?")
            marker = " ← PROCHAIN" if m == (current_month + 1 if current_month < 12 else 1) else ""
            planning.append(f"  • {mois_name.capitalize():15} → {speaker}{marker}")
        
        return cycle_name, "\n".join(planning)

    def reset(self):
        """Réinitialise les données"""
        self.data = {"history": {}, "random_tours": {}, "cycle_count": 0}
        self.save_data()


# Initialiser le gestionnaire
manager = MeetingManager()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /start"""
    await update.message.reply_text(
        "🤖 *Bienvenue à la gestion des réunions mensuelles !*\n\n"
        "📋 *Commandes disponibles :*\n"
        "• `/mois` - Qui dirige la réunion ce mois-ci ?\n"
        "• `/prochain` - Qui dirige le mois prochain ?\n"
        "• `/planning` - Voir le planning complet du cycle actuel\n"
        "• `/reset` - Réinitialiser les données (admin)\n\n"
        "_Les cycles alternent entre ordre normal et inversé tous les 5 mois._",
        parse_mode="Markdown"
    )


async def mois(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /mois"""
    current_month = datetime.now(TIMEZONE).month
    speaker = manager.get_speaker_current_month()
    mois_name = MOIS_FR[current_month]
    
    await update.message.reply_text(
        f"📅 *Réunion du mois de {mois_name.capitalize()}*\n\n"
        f"👤 *Responsable : {speaker}*",
        parse_mode="Markdown"
    )


async def prochain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /prochain"""
    current_month = datetime.now(TIMEZONE).month
    next_month = current_month + 1 if current_month < 12 else 1
    speaker = manager.get_next_speaker()
    mois_name = MOIS_FR[next_month]
    
    await update.message.reply_text(
        f"🔜 *Prochaine réunion : {mois_name.capitalize()}*\n\n"
        f"👤 *Responsable : {speaker}*",
        parse_mode="Markdown"
    )


async def planning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /planning"""
    cycle_name, planning_text = manager.get_planning()
    
    await update.message.reply_text(
        f"🔁 *Cycle actuel : {cycle_name}*\n\n"
        f"{planning_text}",
        parse_mode="Markdown"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /reset"""
    manager.reset()
    await update.message.reply_text("✅ Données réinitialisées !")


async def monthly_announcement(context: ContextTypes.DEFAULT_TYPE):
    """Envoie l'annonce mensuelle"""
    current_month = datetime.now(TIMEZONE).month
    speaker = manager.get_speaker_for_month(current_month)
    mois_name = MOIS_FR[current_month]
    
    message = (
        f"📅 *Réunion du mois de {mois_name.capitalize()}*\n\n"
        f"👤 *Responsable : {speaker}*\n\n"
        "Utilisez `/planning` pour voir le calendrier complet."
    )
    
    try:
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=message,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Erreur lors de l'envoi du message : {e}")


async def setup_jobs(application: Application):
    """Configure les jobs planifiés"""
    job_queue = application.job_queue
    
    # Ajouter un job pour le 1er de chaque mois à 8h
    job_queue.run_monthly(
        monthly_announcement,
        when=8,  # 8h du matin (heure locale)
        day=1,
        name="monthly_meeting_announcement"
    )
    print("✅ Job mensuel configuré : 1er du mois à 08h00")


def main():
    """Lance le bot"""
    app = Application.builder().token(TOKEN).build()

    # Ajouter les commandes
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mois", mois))
    app.add_handler(CommandHandler("prochain", prochain))
    app.add_handler(CommandHandler("planning", planning))
    app.add_handler(CommandHandler("reset", reset))

    # Configurer les jobs
    app.post_init = setup_jobs

    # Lancer le bot
    print("🚀 Bot démarré...")
    app.run_polling()


if __name__ == "__main__":
    main()