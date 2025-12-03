import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import (
    TELEGRAM_BOT_TOKEN, TIMEZONE, DAILY_SUMMARY_TIME, 
    MIN_STARS_FOR_IMPORTANT, DATABASE_PATH
)
from database import Database
from hltv_scraper import HLTVScraper

# Logging konfigurieren
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation States
AWAITING_TEAM_NAME = 1

# Globale Instanzen
db = Database(DATABASE_PATH)
scraper = HLTVScraper()


class TelegramBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone(TIMEZONE))
        self.setup_handlers()
        self.setup_scheduler()

    def setup_handlers(self):
        """Registriere alle Command-Handler"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("today", self.today_command))
        self.application.add_handler(CommandHandler("alltoday", self.alltoday_command))
        self.application.add_handler(CommandHandler("games", self.games_command))
        self.application.add_handler(CommandHandler("favorites", self.favorites_command))
        
        # Conversation Handler for adding favorites
        add_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("add", self.add_favorite_command)],
            states={
                AWAITING_TEAM_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_favorite_finish)]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )
        self.application.add_handler(add_conv_handler)
        
        # Conversation Handler for removing favorites
        remove_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("remove", self.remove_favorite_command)],
            states={
                AWAITING_TEAM_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.remove_favorite_finish)]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )
        self.application.add_handler(remove_conv_handler)
        
        # Callback Query Handler
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

    def setup_scheduler(self):
        """Set up scheduled tasks"""
        # Daily summary
        hour, minute = map(int, DAILY_SUMMARY_TIME.split(':'))
        self.scheduler.add_job(
            self.send_daily_summary,
            CronTrigger(hour=hour, minute=minute),
            id='daily_summary'
        )
        
        # Check every 30 minutes for results of favorite matches
        self.scheduler.add_job(
            self.check_match_results,
            'interval',
            minutes=30,
            id='check_results'
        )
        
        # Refresh match cache every 30 minutes to ensure fresh data
        self.scheduler.add_job(
            self.refresh_match_cache,
            'interval',
            minutes=30,
            id='refresh_cache'
        )
        
        # Initial cache warmup
        self.scheduler.add_job(
            self.refresh_match_cache,
            'date',
            run_date=datetime.now() + timedelta(seconds=10),
            id='initial_cache_warmup'
        )
    
    async def setup_bot_commands(self):
        """Set bot commands via Telegram API"""
        from telegram import BotCommand
        
        commands = [
            BotCommand("start", "Welcome message and overview"),
            BotCommand("today", "Show today's important matches"),
            BotCommand("alltoday", "Show ALL matches for today"),
            BotCommand("games", "Show upcoming games for your favorite teams"),
            BotCommand("favorites", "Show your favorite teams"),
            BotCommand("add", "Add a favorite team"),
            BotCommand("remove", "Remove a favorite team"),
            BotCommand("help", "Show help and instructions"),
        ]
        
        await self.application.bot.set_my_commands(commands)
        logger.info("Bot commands updated successfully")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /start Command"""
        welcome_text = (
            "🎮 <b>Welcome to the HLTV CS:GO Match Bot!</b>\n\n"
            "I keep you informed about the most important CS:GO matches of the day "
            "<b>Available Commands:</b>\n"
            "/today - Show today's important matches\n"
            "/alltoday - Show ALL matches for today\n"
            "/games - Show upcoming games for your favorite teams\n"
            "/favorites - Show your favorite teams\n"
            "/add - Add a favorite team\n"
            "/remove - Remove a favorite team\n"
            "/help - Show this help\n\n"
            "You'll receive a daily summary at 09:00 with the most important matches "
            "and notifications about your favorite teams' games!"
        )
        await update.message.reply_text(welcome_text, parse_mode='HTML')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /help Command"""
        help_text = (
            "<b>🎮 HLTV CS:GO Match Bot - Help</b>\n\n"
            "<b>Commands:</b>\n\n"
            "/today - Shows all important matches for today\n\n"
            "/alltoday - Shows ALL matches for today (no star filter)\n\n"
            "/games - Shows upcoming games for your favorite teams\n\n"
            "/favorites - Shows your list of favorite teams\n\n"
            "/add - Add a new favorite team. You'll be notified about all games "
            "and results of this team\n\n"
            "/remove - Remove a team from your favorites\n\n"
            "<b>Automatic Notifications:</b>\n"
            "• Daily summary at 09:00\n"
            "• Notifications about your favorite teams' games\n"
            "• Results after match ends\n\n"
            "Have fun! 🎯"
        )
        await update.message.reply_text(help_text, parse_mode='HTML')

    async def today_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /today Command"""
        await update.message.reply_text("🔍 Searching for today's important matches...")
        
        matches = scraper.get_todays_matches(min_stars=MIN_STARS_FOR_IMPORTANT)
        
        if not matches:
            await update.message.reply_text(
                "No important matches found. 😔"
            )
            return
        
        # Filter to only show matches happening today
        today = datetime.now().date()
        today_matches = [m for m in matches if m.time and m.time.date() == today]
        
        if not today_matches:
            await update.message.reply_text(
                f"No important matches found for today ({today.strftime('%d.%m.%Y')}). 😔\n"
                f"There are {len(matches)} upcoming matches, but they are on other days."
            )
            return
        
        # Sort by time (soonest first), then by stars (most important first)
        today_matches.sort(key=lambda m: (m.time if m.time else datetime.max, -m.stars))
        
        message = f"<b>⭐ Important Matches Today ({today.strftime('%d.%m.%Y')}):</b>\n\n"
        for match in today_matches:
            stars = "⭐" * match.stars
            message += f"{stars}\n{match}\n\n"
        
        await update.message.reply_text(message, parse_mode='HTML')

    async def alltoday_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /alltoday Command - shows ALL matches for today"""
        await update.message.reply_text("🔍 Searching for all matches today...")
        
        # Get all matches (min_stars=0 means no filter)
        matches = scraper.get_todays_matches(min_stars=0, use_cache=True)
        
        if not matches:
            await update.message.reply_text(
                "No matches found. 😔"
            )
            return
        
        # Filter to only show matches happening today
        today = datetime.now().date()
        today_matches = [m for m in matches if m.time and m.time.date() == today]
        
        if not today_matches:
            await update.message.reply_text(
                f"No matches found for today ({today.strftime('%d.%m.%Y')}). 😔\n"
                f"There are {len(matches)} upcoming matches, but they are on other days."
            )
            return
        
        # Sort by time (soonest first), then by stars
        today_matches.sort(key=lambda m: (m.time if m.time else datetime.max, -m.stars))
        
        # Build message with grouping by star rating
        message = f"<b>🎮 All Matches Today ({today.strftime('%d.%m.%Y')}):</b>\n"
        message += f"<i>Total: {len(today_matches)} matches</i>\n\n"
        
        # Group by stars for better overview
        by_stars = {}
        for match in today_matches:
            if match.stars not in by_stars:
                by_stars[match.stars] = []
            by_stars[match.stars].append(match)
        
        # Show in descending star order
        for stars in sorted(by_stars.keys(), reverse=True):
            star_matches = by_stars[stars]
            stars_str = "⭐" * stars if stars > 0 else "◾"
            message += f"<b>{stars_str} {len(star_matches)} match{'es' if len(star_matches) != 1 else ''}:</b>\n"
            
            for match in star_matches[:10]:  # Limit to first 10 per category
                time_str = match.time.strftime('%H:%M') if match.time else 'TBA'
                message += f"{time_str} | {match.team1} vs {match.team2}\n"
            
            if len(star_matches) > 10:
                message += f"<i>... and {len(star_matches) - 10} more</i>\n"
            message += "\n"
        
        await update.message.reply_text(message, parse_mode='HTML')

    async def games_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /games Command - shows upcoming games for favorite teams"""
        user_id = update.effective_user.id
        favorites = db.get_favorites(user_id)
        
        if not favorites:
            await update.message.reply_text(
                "You haven't added any favorite teams yet.\n"
                "Use /add to add a team and get notified about their games!"
            )
            return
        
        await update.message.reply_text("🔍 Searching for upcoming games...")
        
        # Get all upcoming matches (HLTV shows only future matches)
        matches = scraper.get_todays_matches(min_stars=0)
        
        if not matches:
            await update.message.reply_text(
                "No upcoming matches found. 😔"
            )
            return
        
        # Find matches for each favorite team
        team_games = {}
        for team in favorites:
            team_matches = [m for m in matches if m.has_team(team)]
            if team_matches:
                # Sort by time and get the next match
                team_matches.sort(key=lambda m: m.time if m.time else datetime.max)
                team_games[team] = team_matches[0]
        
        if not team_games:
            await update.message.reply_text(
                "No upcoming games found for your favorite teams. 😔\n\n"
                "Your favorites: " + ", ".join(favorites)
            )
            return
        
        # Build message
        message = "<b>🎮 Upcoming Games for Your Favorites:</b>\n\n"
        for team, match in team_games.items():
            stars = "⭐" * match.stars if match.stars > 0 else ""
            message += f"<b>{team}</b>\n"
            message += f"{match}\n"
            if stars:
                message += f"{stars}\n"
            message += "\n"
        
        await update.message.reply_text(message, parse_mode='HTML')

    async def favorites_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /favorites Command"""
        user_id = update.effective_user.id
        favorites = db.get_favorites(user_id)
        
        if not favorites:
            await update.message.reply_text(
                "You haven't added any favorite teams yet.\n"
                "Use /add to add a team!"
            )
            return
        
        message = "<b>❤️ Your Favorite Teams:</b>\n\n"
        for i, team in enumerate(favorites, 1):
            message += f"{i}. {team}\n"
        
        await update.message.reply_text(message, parse_mode='HTML')

    async def add_favorite_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /add Command"""
        user_id = update.effective_user.id
        
        # Check if team name was provided as argument
        if context.args and len(context.args) > 0:
            team_name = ' '.join(context.args).strip()
            
            # Search for team on HLTV
            await update.message.reply_text(f"🔍 Searching for '{team_name}' on HLTV...")
            
            if not scraper.search_team(team_name):
                await update.message.reply_text(
                    f"❌ Team '{team_name}' not found on HLTV.\n\n"
                    "Please check the spelling or try a different name.\n"
                    "Examples: FaZe, Navi, G2, Vitality, BIG, Mouz"
                )
                return ConversationHandler.END
            
            if db.add_favorite(user_id, team_name):
                await update.message.reply_text(
                    f"✅ {team_name} has been added to your favorites!\n\n"
                    "You'll now be notified about all games and results of this team."
                )
            else:
                await update.message.reply_text(
                    f"❌ {team_name} is already in your favorites."
                )
            return ConversationHandler.END
        else:
            # Start conversation for bulk add
            await update.message.reply_text(
                "Please enter one or more team names (one per line or comma-separated):\n\n"
                "Examples:\n"
                "• FaZe, Navi, G2\n"
                "• BIG\n"
                "  Mouz\n"
                "  Vitality\n\n"
                "Or send /cancel to abort."
            )
            return AWAITING_TEAM_NAME

    async def add_favorite_finish(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Finish Adding Favorites (bulk or single)"""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        # Parse team names (support both comma-separated and newline-separated)
        team_names = []
        if ',' in text:
            team_names = [t.strip() for t in text.split(',') if t.strip()]
        else:
            team_names = [t.strip() for t in text.split('\n') if t.strip()]
        
        if not team_names:
            await update.message.reply_text("No team names provided.")
            return ConversationHandler.END
        
        results = []
        
        for team_name in team_names:
            # Search for team on HLTV
            if not scraper.search_team(team_name):
                results.append(f"❌ {team_name} - not found on HLTV")
                continue
            
            if db.add_favorite(user_id, team_name):
                results.append(f"✅ {team_name} - added to favorites")
            else:
                results.append(f"ℹ️ {team_name} - already in favorites")
        
        # Send summary
        message = "<b>Results:</b>\n\n" + "\n".join(results)
        await update.message.reply_text(message, parse_mode='HTML')
        
        return ConversationHandler.END

    async def remove_favorite_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /remove Command"""
        user_id = update.effective_user.id
        
        # Check if team name was provided as argument
        if context.args and len(context.args) > 0:
            team_name = ' '.join(context.args).strip()
            
            if db.remove_favorite(user_id, team_name):
                await update.message.reply_text(
                    f"✅ {team_name} has been removed from your favorites."
                )
            else:
                await update.message.reply_text(
                    f"❌ {team_name} was not in your favorites."
                )
            return ConversationHandler.END
        else:
            # Show current favorites and start conversation for bulk remove
            favorites = db.get_favorites(user_id)
            
            if not favorites:
                await update.message.reply_text(
                    "You have no favorite teams to remove."
                )
                return ConversationHandler.END
            
            message = "Please enter one or more team names to remove (one per line or comma-separated):\n\n"
            message += "<b>Your favorite teams:</b>\n"
            for i, team in enumerate(favorites, 1):
                message += f"{i}. {team}\n"
            message += "\nOr send /cancel to abort."
            
            await update.message.reply_text(message, parse_mode='HTML')
            return AWAITING_TEAM_NAME

    async def remove_favorite_finish(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Finish Removing Favorites (bulk or single)"""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        # Parse team names (support both comma-separated and newline-separated)
        team_names = []
        if ',' in text:
            team_names = [t.strip() for t in text.split(',') if t.strip()]
        else:
            team_names = [t.strip() for t in text.split('\n') if t.strip()]
        
        if not team_names:
            await update.message.reply_text("No team names provided.")
            return ConversationHandler.END
        
        results = []
        
        for team_name in team_names:
            if db.remove_favorite(user_id, team_name):
                results.append(f"✅ {team_name} - removed from favorites")
            else:
                results.append(f"❌ {team_name} - was not in favorites")
        
        # Send summary
        message = "<b>Results:</b>\n\n" + "\n".join(results)
        await update.message.reply_text(message, parse_mode='HTML')
        
        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /cancel Command"""
        await update.message.reply_text("Action cancelled.")
        return ConversationHandler.END

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for inline button callbacks"""
        query = update.callback_query
        await query.answer()

    async def send_daily_summary(self):
        """Send daily summary to all users with favorites"""
        logger.info("Sending daily summary...")
        
        matches = scraper.get_todays_matches(min_stars=MIN_STARS_FOR_IMPORTANT)
        
        if not matches:
            logger.info("No matches found for summary")
            return
        
        # Sort by stars
        matches.sort(key=lambda m: m.stars, reverse=True)
        
        message = "<b>🌅 Good Morning! Today's Matches:</b>\n\n"
        for match in matches:
            stars = "⭐" * match.stars
            message += f"{stars}\n{match}\n\n"
        
        # Sende an alle Benutzer mit Favoriten
        users = db.get_all_users_with_favorites()
        for user_id in users:
            try:
                await self.application.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Error sending to user {user_id}: {e}")

    async def check_match_results(self):
        """Check results of favorite team matches"""
        logger.info("Checking match results...")
        
        results = scraper.get_recent_results(hours=1)
        
        if not results:
            return
        
        # For each user with favorites
        users = db.get_all_users_with_favorites()
        for user_id in users:
            favorites = db.get_favorites(user_id)
            
            # Find matches with favorite teams
            for result in results:
                for team in favorites:
                    if result.has_team(team):
                        # Check if already sent
                        if not db.was_notification_sent(user_id, result.match_id, 'result'):
                            message = (
                                f"🏁 <b>Match Finished!</b>\n\n"
                                f"{result}\n\n"
                                f"Your favorite team: {team}"
                            )
                            try:
                                await self.application.bot.send_message(
                                    chat_id=user_id,
                                    text=message,
                                    parse_mode='HTML'
                                )
                                db.mark_notification_sent(user_id, result.match_id, 'result')
                            except Exception as e:
                                logger.error(f"Error sending to user {user_id}: {e}")
    
    async def refresh_match_cache(self):
        """Refresh the match cache and preload datetimes for important matches"""
        try:
            logger.info("Refreshing match cache...")
            # Force refresh by using use_cache=False
            matches = scraper.get_todays_matches(min_stars=0, use_cache=False)
            logger.info(f"Cache refreshed with {len(matches)} matches")
            
            # Preload datetimes for important matches (1+ stars) to ensure they're cached
            important_matches = [m for m in matches if m.stars >= 1]
            if important_matches:
                logger.info(f"Preloading datetimes for {len(important_matches)} important matches...")
                scraper.preload_match_datetimes(important_matches, max_matches=20)
                logger.info("Datetime preloading completed")
        except Exception as e:
            logger.error(f"Error refreshing match cache: {e}")

    def run(self):
        """Start the bot"""
        logger.info("Starting bot...")
        self.scheduler.start()
        
        # Set bot commands on startup
        import asyncio
        asyncio.get_event_loop().run_until_complete(self.setup_bot_commands())
        
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Main function"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set! Please create .env file.")
        return
    
    bot = TelegramBot()
    bot.run()


if __name__ == '__main__':
    main()
