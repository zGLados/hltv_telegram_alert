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
        self.application.add_handler(CommandHandler("favgames", self.favgames_command))
        self.application.add_handler(CommandHandler("setminstar", self.setminstar_command))
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
        from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeAllPrivateChats
        
        commands = [
            BotCommand("start", "Welcome message and overview"),
            BotCommand("today", "Show today's important matches"),
            BotCommand("favgames", "Show upcoming games for your favorite teams"),
            BotCommand("setminstar", "Set minimum star rating 1-5 (e.g., /setminstar 2)"),
            BotCommand("favorites", "Show your favorite teams"),
            BotCommand("add", "Add a favorite team"),
            BotCommand("remove", "Remove a favorite team"),
            BotCommand("help", "Show help and instructions"),
        ]
        
        # Set commands for all private chats (direct messages)
        await self.application.bot.set_my_commands(
            commands=commands,
            scope=BotCommandScopeAllPrivateChats()
        )
        
        # Also set default scope as fallback
        await self.application.bot.set_my_commands(
            commands=commands,
            scope=BotCommandScopeDefault()
        )
        
        logger.info("Bot commands updated successfully for all scopes")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /start Command"""
        welcome_text = (
            "🎮 <b>Welcome to the HLTV CS:GO Match Bot!</b>\n\n"
            "I keep you informed about the most important CS:GO matches of the day "
            "<b>Available Commands:</b>\n"
            "/today - Show today's important matches\n"
            "/favgames - Show upcoming games for your favorite teams\n"
            "/setminstar <number> - Set minimum star rating (1-5)\n"
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
            "/today - Shows today's important matches (based on your star rating)\n\n"
            "/favgames - Shows upcoming games for your favorite teams\n\n"
            "/setminstar &lt;number&gt; - Set minimum star rating (1-5)\n"
            "  Example: /setminstar 2\n\n"
            "/favorites - Shows your list of favorite teams\n\n"
            "/add - Add a new favorite team\n\n"
            "/remove - Remove a team from your favorites\n\n"
            "<b>Automatic Notifications:</b>\n"
            "• Daily summary at 09:00 (respects your star rating setting)\n"
            "• Notifications about your favorite teams' games\n\n"
            "Have fun! 🎯"
        )
        await update.message.reply_text(help_text, parse_mode='HTML')

    async def today_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /today Command - shows important matches today (based on user's min_stars setting)"""
        user_id = update.effective_user.id
        min_stars = db.get_min_stars(user_id)
        
        await update.message.reply_text(f"🔍 Searching for matches with {min_stars}+ stars...")
        
        today = datetime.now().date()
        
        # Get upcoming important matches
        upcoming_matches = scraper.get_todays_matches(min_stars=min_stars)
        upcoming_today = [m for m in upcoming_matches if m.time and m.time.date() == today]
        
        # Get today's results (filter for important ones)
        results = scraper.get_recent_results(hours=24)
        important_results = [r for r in results if r.stars >= min_stars]
        
        # Combine both
        all_important = []
        
        # Add finished matches
        for result in important_results:
            all_important.append({
                'match': result,
                'status': 'finished'
            })
        
        # Add upcoming matches
        for match in upcoming_today:
            all_important.append({
                'match': match,
                'status': 'upcoming'
            })
        
        if not all_important:
            await update.message.reply_text(
                f"No matches with {min_stars}+ stars found for today. 😔\n"
                f"Use /setminstar <number> to change the minimum rating."
            )
            return
        
        # Build message
        message = f"<b>⭐ Important Matches Today ({today.strftime('%d.%m.%Y')}):</b>\n"
        message += f"<i>Total: {len(all_important)} matches ({min_stars}+ stars)</i>\n\n"
        
        # Show finished matches first
        finished = [item for item in all_important if item['status'] == 'finished']
        upcoming = [item for item in all_important if item['status'] == 'upcoming']
        
        if finished:
            message += "<b>✅ Finished:</b>\n\n"
            for item in finished:
                result = item['match']
                message += f"{result.format_for_telegram()}\n\n"
        
        if upcoming:
            message += "<b>🕐 Upcoming:</b>\n\n"
            # Sort by time
            upcoming.sort(key=lambda x: x['match'].time if x['match'].time else datetime.max)
            for item in upcoming:
                match = item['match']
                message += f"{match.format_for_telegram()}\n\n"
        
        await update.message.reply_text(message, parse_mode='HTML', disable_web_page_preview=True)

    async def alltoday_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /alltoday Command - shows ALL matches for today (upcoming + finished)"""
        await update.message.reply_text("🔍 Searching for all matches today...")
        
        today = datetime.now().date()
        
        # Get upcoming matches
        upcoming_matches = scraper.get_todays_matches(min_stars=0, use_cache=True)
        upcoming_today = [m for m in upcoming_matches if m.time and m.time.date() == today]
        
        # Get today's results
        results = scraper.get_recent_results(hours=24)
        
        # Combine both lists
        all_matches = []
        
        # Add results first (mark them as finished)
        for result in results:
            all_matches.append({
                'match': result,
                'status': 'finished',
                'sort_key': 0  # Finished matches sort first
            })
        
        # Add upcoming matches
        for match in upcoming_today:
            all_matches.append({
                'match': match,
                'status': 'upcoming',
                'sort_key': match.time.timestamp() if match.time else float('inf')
            })
        
        if not all_matches:
            await update.message.reply_text(
                f"No matches found for today ({today.strftime('%d.%m.%Y')}). 😔"
            )
            return
        
        # Build message with grouping by star rating
        message = f"<b>🎮 All Matches Today ({today.strftime('%d.%m.%Y')}):</b>\n"
        message += f"<i>Total: {len(all_matches)} matches</i>\n\n"
        
        # Group by stars
        by_stars = {}
        for item in all_matches:
            match = item['match']
            stars = match.stars
            if stars not in by_stars:
                by_stars[stars] = {'finished': [], 'upcoming': []}
            by_stars[stars][item['status']].append(match)
        
        # Show in descending star order
        for stars in sorted(by_stars.keys(), reverse=True):
            stars_str = "☆" * stars if stars > 0 else "No rating"
            star_data = by_stars[stars]
            total_count = len(star_data['finished']) + len(star_data['upcoming'])
            
            message += f"<b>{stars_str} ({total_count} match{'es' if total_count != 1 else ''}):</b>\n\n"
            
            # Show finished matches first
            for result in star_data['finished'][:8]:
                message += f"{result.format_for_telegram()}\n\n"
            
            # Then show upcoming matches
            for match in star_data['upcoming'][:8]:
                message += f"{match.format_for_telegram()}\n\n"
            
            remaining = total_count - 16
            if remaining > 0:
                message += f"<i>... and {remaining} more</i>\n"
            message += "\n"
        
        await update.message.reply_text(message, parse_mode='HTML', disable_web_page_preview=True)

    async def setminstar_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /setminstar Command - set minimum star rating"""
        user_id = update.effective_user.id
        
        # Check if argument provided
        if not context.args or len(context.args) == 0:
            current_min = db.get_min_stars(user_id)
            await update.message.reply_text(
                f"Your current minimum star rating: {current_min}\n\n"
                f"Usage: /setminstar <number>\n"
                f"Example: /setminstar 2\n\n"
                f"Available ratings: 1-5 stars"
            )
            return
        
        # Parse the number
        try:
            min_stars = int(context.args[0])
            if min_stars < 1 or min_stars > 5:
                await update.message.reply_text(
                    "Please use a number between 1 and 5.\n"
                    "Example: /setminstar 2"
                )
                return
            
            db.set_min_stars(user_id, min_stars)
            await update.message.reply_text(
                f"✅ Minimum star rating set to {min_stars}!\n\n"
                f"You will now see matches with {min_stars}+ stars in /today and daily reminders."
            )
            
        except ValueError:
            await update.message.reply_text(
                "Please provide a valid number.\n"
                "Example: /setminstar 2"
            )

    async def favgames_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /favgames Command - shows upcoming games for favorite teams"""
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
            message += f"<b>{team}</b>\n"
            message += f"{match.format_for_telegram()}\n\n"
        
        await update.message.reply_text(message, parse_mode='HTML', disable_web_page_preview=True)

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
        """Send daily summary to all users (respecting their min_stars setting)"""
        logger.info("Sending daily summary at 9:00 AM...")
        
        # Send to all users who have set preferences or favorites
        users = db.get_all_users_with_favorites()
        
        for user_id in users:
            try:
                # Get user's min_stars setting
                min_stars = db.get_min_stars(user_id)
                
                # Get today's matches with user's min_stars
                matches = scraper.get_todays_matches(min_stars=min_stars)
                today = datetime.now().date()
                today_matches = [m for m in matches if m.time and m.time.date() == today]
                
                if not today_matches:
                    continue
                
                # Sort by stars (highest first), then by time
                today_matches.sort(key=lambda m: (-m.stars, m.time if m.time else datetime.max))
                
                message = f"<b>🌅 Good Morning! Today's Matches ({min_stars}+ stars):</b>\n\n"
                for match in today_matches[:15]:  # Max 15 matches
                    message += f"{match.format_for_telegram()}\n\n"
                
                await self.application.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
                logger.info(f"Sent daily summary to user {user_id}")
                
            except Exception as e:
                logger.error(f"Error sending daily summary to user {user_id}: {e}")

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
