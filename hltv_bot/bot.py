"""HLTV Telegram bot: commands, scheduled jobs and startup.

Threading model: python-telegram-bot runs on an asyncio event loop. All HLTV
scraping is blocking (HTTP + rate-limit sleeps), so it is always executed via
`asyncio.to_thread` to keep the bot responsive. SQLite calls are fast and run
directly on the loop.
"""
import asyncio
import html
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Tuple

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeDefault, Update
from telegram.constants import MessageLimit, ParseMode
from telegram.error import Forbidden
from telegram.ext import (
    Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters,
)

from .config import (
    DAILY_SUMMARY_AT, DATABASE_PATH, INITIAL_DATABASE_PATH, MATCH_CACHE_FILE,
    MATCH_CACHE_SECONDS, MAX_TIME_LOOKUPS_PER_REFRESH, SNAPSHOT_TIME, TELEGRAM_BOT_TOKEN, TZ,
)
from .database import Database
from .scraper import HLTVScraper, Match

logger = logging.getLogger(__name__)

AWAITING_TEAM_NAME = 1
TODAY_WINDOW_HOURS = 24  # /today: results of the last and matches of the next N hours
MAX_SUMMARY_MATCHES = 15
SUMMARY_TIME_STR = DAILY_SUMMARY_AT.strftime('%H:%M')

COMMANDS = [
    ('start', 'Welcome message and overview'),
    ('help', 'Show help and instructions'),
    ('add', 'Add favorite team(s)'),
    ('remove', 'Remove favorite team(s)'),
    ('favorites', 'Show your favorite teams'),
    ('setminstar', 'Set minimum star rating 1-5 (e.g. /setminstar 2)'),
    ('today', 'Important matches of the last and next 24 hours'),
    ('favgames', 'Show the next game of each favorite team'),
    ('cancel', 'Cancel the current action'),
]

db = Database(DATABASE_PATH, INITIAL_DATABASE_PATH)
scraper = HLTVScraper(db, cache_file=MATCH_CACHE_FILE)


# --- Helpers ------------------------------------------------------------------------

def today_local():
    return datetime.now(TZ).date()


def is_today(match: Match) -> bool:
    local = match.local_time
    return local is not None and local.date() == today_local()


def starts_within(match: Match, hours: int) -> bool:
    """Live, or kick-off within the next `hours` (match list only holds unfinished matches)."""
    if match.is_live:
        return True
    return match.time is not None and match.time <= datetime.now(timezone.utc) + timedelta(hours=hours)


def by_time(match: Match):
    return match.time.timestamp() if match.time else float('inf')


def split_message(text: str, limit: int = MessageLimit.MAX_TEXT_LENGTH) -> List[str]:
    """Split at blank lines so no chunk exceeds Telegram's length limit.

    Each block is one formatted match, so HTML tags are never cut in half.
    """
    chunks, current = [], ''
    for block in text.split('\n\n'):
        candidate = f'{current}\n\n{block}' if current else block
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = block[:limit]
    if current:
        chunks.append(current)
    return chunks


async def reply_html(update: Update, text: str):
    for chunk in split_message(text):
        await update.message.reply_text(chunk, parse_mode=ParseMode.HTML,
                                        disable_web_page_preview=True)


def parse_team_list(text: str) -> List[str]:
    """Team names separated by commas and/or newlines."""
    return [t.strip() for line in text.splitlines() for t in line.split(',') if t.strip()]


def format_matches(matches: Iterable[Match]) -> str:
    return '\n\n'.join(m.format_for_telegram() for m in matches)


# --- Blocking data access (always called through asyncio.to_thread) ------------------

def fetch_window(min_stars: int, hours: int) -> Tuple[List[Match], List[Match]]:
    """(finished in the last `hours`, live + starting in the next `hours`)
    with at least `min_stars`."""
    upcoming = scraper.get_upcoming_matches(min_stars)
    scraper.resolve_times(upcoming)
    upcoming = sorted((m for m in upcoming if starts_within(m, hours)), key=by_time)

    results = scraper.get_recent_results(hours=hours)
    finished = [r for r in results if r.stars >= min_stars]
    return finished, upcoming


def fetch_next_games(teams: List[str]) -> Dict[str, Match]:
    """Next upcoming (or live) match for each team that has one."""
    matches = [m for m in scraper.get_upcoming_matches()
               if any(m.has_team(t) for t in teams)]
    scraper.resolve_times(matches)
    matches.sort(key=by_time)
    next_games = {}
    for team in teams:
        game = next((m for m in matches if m.has_team(team)), None)
        if game:
            next_games[team] = game
    return next_games


def fetch_summary_matches(favorite_teams: Iterable[str]) -> List[Match]:
    """All of today's matches that any daily summary could contain."""
    teams = set(favorite_teams)
    matches = [m for m in scraper.get_upcoming_matches()
               if m.stars >= 1 or any(m.has_team(t) for t in teams)]
    scraper.resolve_times(matches)
    return sorted((m for m in matches if is_today(m)), key=by_time)


def refresh_match_cache() -> bool:
    """Fetch the match list from HLTV (also rewrites the snapshot file).
    Returns False if HLTV couldn't be reached and the old data is kept."""
    before = scraper.matches_fetched_at
    matches = scraper.get_upcoming_matches(use_cache=False)
    if scraper.matches_fetched_at == before:
        logger.warning("Match refresh failed, keeping previous match list")
        return False
    important = [m for m in matches if m.stars >= 1]
    fetched = scraper.resolve_times(important, limit=MAX_TIME_LOOKUPS_PER_REFRESH)
    scraper.prune_time_cache()
    logger.info(f"Match cache refreshed: {len(matches)} matches, {len(important)} with stars, "
                f"{fetched} kick-off times looked up")
    return True


def daily_snapshot():
    """Daily fresh fetch of the match list; logs how many starred matches exist."""
    ok = refresh_match_cache()
    matches = scraper.get_upcoming_matches()
    per_star = Counter(m.stars for m in matches if m.stars >= 1)
    breakdown = ', '.join(f"{n}x {'☆' * stars}" for stars, n in sorted(per_star.items(), reverse=True))
    logger.info(f"Daily snapshot {'saved' if ok else 'FAILED (using previous data)'}: "
                f"{sum(per_star.values())} starred of {len(matches)} matches "
                f"({breakdown or 'none'}) -> {MATCH_CACHE_FILE}")


# --- Bot ----------------------------------------------------------------------------

class TelegramBot:
    def __init__(self):
        self.application = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .post_init(self.on_startup)
            .post_shutdown(self.on_shutdown)
            .build()
        )
        # Misfire grace: a job that starts a few minutes late (busy loop,
        # suspended host) still runs instead of being silently skipped.
        self.scheduler = AsyncIOScheduler(
            timezone=TZ, job_defaults={'misfire_grace_time': 300, 'coalesce': True},
        )
        self.setup_handlers()
        self.setup_jobs()

    def setup_handlers(self):
        app = self.application
        app.add_handler(CommandHandler('start', self.start_command))
        app.add_handler(CommandHandler('help', self.help_command))
        app.add_handler(CommandHandler('today', self.today_command))
        app.add_handler(CommandHandler('favgames', self.favgames_command))
        app.add_handler(CommandHandler('setminstar', self.setminstar_command))
        app.add_handler(CommandHandler('favorites', self.favorites_command))

        # /add and /remove accept names directly or ask for them in a follow-up message
        for command, entry, finish in (
            ('add', self.add_favorite_command, self.add_favorite_finish),
            ('remove', self.remove_favorite_command, self.remove_favorite_finish),
        ):
            app.add_handler(ConversationHandler(
                entry_points=[CommandHandler(command, entry)],
                states={AWAITING_TEAM_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, finish)
                ]},
                fallbacks=[CommandHandler('cancel', self.cancel)],
            ))
        app.add_handler(CommandHandler('cancel', self.cancel))
        app.add_error_handler(self.error_handler)

    def setup_jobs(self):
        s = self.scheduler
        s.add_job(self.send_daily_summary, CronTrigger(
            hour=DAILY_SUMMARY_AT.hour, minute=DAILY_SUMMARY_AT.minute), id='daily_summary')
        s.add_job(self.check_match_results, 'interval', minutes=30, id='check_results')
        s.add_job(self.refresh_match_cache, 'interval',
                  seconds=MATCH_CACHE_SECONDS, id='refresh_cache')
        s.add_job(self.load_teams, CronTrigger(hour=3, minute=0), id='daily_team_refresh')
        s.add_job(self.prune_notifications, CronTrigger(hour=4, minute=0), id='prune')
        snap_hour, snap_minute = map(int, SNAPSHOT_TIME.split(':'))
        s.add_job(self.daily_snapshot, CronTrigger(hour=snap_hour, minute=snap_minute),
                  id='daily_snapshot')

    async def on_startup(self, application: Application):
        """Runs once the event loop is up, before polling starts."""
        commands = [BotCommand(name, desc) for name, desc in COMMANDS]
        for scope in (BotCommandScopeAllPrivateChats(), BotCommandScopeDefault()):
            await application.bot.set_my_commands(commands=commands, scope=scope)
        logger.info("Bot commands registered")

        self.scheduler.start()
        # Warm caches in the background so the bot answers immediately
        self.scheduler.add_job(self.startup_warmup, id='startup_warmup')

    async def on_shutdown(self, application: Application):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error("Unhandled error while processing an update", exc_info=context.error)
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ Something went wrong. Please try again later.")

    # --- Commands -------------------------------------------------------------------

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        db.register_user(update.effective_user.id)
        await update.message.reply_text(
            "🎮 <b>Welcome to the HLTV CS2 Match Bot!</b>\n\n"
            "I keep you informed about the most important CS2 matches of the day.\n\n"
            "<b>Available Commands:</b>\n"
            "/today - Important matches of the last and next 24 hours\n"
            "/favgames - Show the next game of each favorite team\n"
            "/setminstar &lt;number&gt; - Set minimum star rating (1-5)\n"
            "/favorites - Show your favorite teams\n"
            "/add - Add favorite team(s)\n"
            "/remove - Remove favorite team(s)\n"
            "/help - Show help\n\n"
            f"Every day at {SUMMARY_TIME_STR} you'll get a summary of today's matches, "
            "and I'll message you when one of your favorite teams has finished a match!",
            parse_mode=ParseMode.HTML,
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "<b>🎮 HLTV CS2 Match Bot - Help</b>\n\n"
            "<b>Commands:</b>\n\n"
            "/add [team] - Add favorite team(s). Without a name I'll ask you; "
            "several teams can be separated by commas or new lines.\n\n"
            "/remove [team] - Remove favorite team(s)\n\n"
            "/favorites - Your favorite teams\n\n"
            "/setminstar &lt;number&gt; - Minimum HLTV star rating (1-5) for /today "
            "and the daily summary. Example: /setminstar 2\n\n"
            "/today - Results of the last 24 hours, live matches and matches of the "
            "next 24 hours with your star rating\n\n"
            "/favgames - The next game of each favorite team\n\n"
            "/cancel - Cancel the current action\n\n"
            "<b>Automatic Notifications:</b>\n"
            f"• Daily summary at {SUMMARY_TIME_STR} (your star rating + your teams' games)\n"
            "• A message when a favorite team has finished a match\n\n"
            "Have fun! 🎯",
            parse_mode=ParseMode.HTML,
        )

    async def today_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Matches with the user's minimum stars: results of the last 24 h,
        live matches and matches starting within the next 24 h."""
        min_stars = db.get_min_stars(update.effective_user.id)
        await update.message.reply_text(f"🔍 Searching for matches with {min_stars}+ stars...")

        hours = TODAY_WINDOW_HOURS
        finished, upcoming = await asyncio.to_thread(fetch_window, min_stars, hours)
        if not finished and not upcoming:
            await update.message.reply_text(
                f"No matches with {min_stars}+ stars in the last or next {hours} hours. 😔\n"
                "Use /setminstar <number> to change the minimum rating.")
            return

        live = [m for m in upcoming if m.is_live]
        upcoming = [m for m in upcoming if not m.is_live]
        parts = [
            f"<b>⭐ Important Matches (last &amp; next {hours}h):</b>\n"
            f"<i>Total: {len(finished) + len(live) + len(upcoming)} matches ({min_stars}+ stars)</i>"
        ]
        if finished:
            parts += ["<b>✅ Finished:</b>", format_matches(finished)]
        if live:
            parts += ["<b>🔴 Live:</b>", format_matches(live)]
        if upcoming:
            parts += [f"<b>🕐 Next {hours}h:</b>", format_matches(upcoming)]
        await reply_html(update, '\n\n'.join(parts))

    async def setminstar_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not context.args:
            await update.message.reply_text(
                f"Your current minimum star rating: {db.get_min_stars(user_id)}\n\n"
                "Usage: /setminstar <number>\nExample: /setminstar 2\n\n"
                "Available ratings: 1-5 stars")
            return

        try:
            min_stars = int(context.args[0])
        except ValueError:
            min_stars = 0
        if not 1 <= min_stars <= 5:
            await update.message.reply_text(
                "Please use a number between 1 and 5.\nExample: /setminstar 2")
            return

        db.set_min_stars(user_id, min_stars)
        await update.message.reply_text(
            f"✅ Minimum star rating set to {min_stars}!\n\n"
            f"You will now see matches with {min_stars}+ stars in /today and the daily summary.")

    async def favgames_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        favorites = db.get_favorites(update.effective_user.id)
        if not favorites:
            await update.message.reply_text(
                "You haven't added any favorite teams yet.\n"
                "Use /add to add a team and get notified about their games!")
            return

        await update.message.reply_text("🔍 Searching for upcoming games...")
        next_games = await asyncio.to_thread(fetch_next_games, favorites)
        if not next_games:
            await update.message.reply_text(
                "No upcoming games found for your favorite teams. 😔\n\n"
                "Your favorites: " + ", ".join(favorites))
            return

        blocks = ["<b>🎮 Upcoming Games for Your Favorites:</b>"]
        blocks += [f"<b>{html.escape(team)}</b>\n{match.format_for_telegram()}"
                   for team, match in next_games.items()]
        without = [t for t in favorites if t not in next_games]
        if without:
            blocks.append("<i>No upcoming games: " + html.escape(", ".join(without)) + "</i>")
        await reply_html(update, '\n\n'.join(blocks))

    async def favorites_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        favorites = db.get_favorites(update.effective_user.id)
        if not favorites:
            await update.message.reply_text(
                "You haven't added any favorite teams yet.\nUse /add to add a team!")
            return
        lines = [f"{i}. {html.escape(team)}" for i, team in enumerate(favorites, 1)]
        await reply_html(update, "<b>❤️ Your Favorite Teams:</b>\n\n" + "\n".join(lines))

    # --- /add and /remove ---------------------------------------------------------

    async def add_favorite_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if context.args:
            await self._add_teams(update, [' '.join(context.args)])
            return ConversationHandler.END
        await update.message.reply_text(
            "Please enter one or more team names (one per line or comma-separated):\n\n"
            "Examples:\n• FaZe, Navi, G2\n• BIG\n  Mouz\n  Vitality\n\n"
            "Or send /cancel to abort.")
        return AWAITING_TEAM_NAME

    async def add_favorite_finish(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._add_teams(update, parse_team_list(update.message.text))
        return ConversationHandler.END

    async def _add_teams(self, update: Update, names: List[str]):
        user_id = update.effective_user.id
        if not names:
            await update.message.reply_text("No team names provided.")
            return
        db.register_user(user_id)

        lines = []
        for name in names:
            found, canonical = scraper.search_team(name)
            if not found:
                hint = scraper.suggest_teams(name)
                line = f"❌ {html.escape(name)} - not found"
                if hint:
                    line += f" (did you mean: {html.escape(', '.join(hint))}?)"
                lines.append(line)
            elif db.add_favorite(user_id, canonical):
                lines.append(f"✅ {html.escape(canonical)} - added to favorites")
            else:
                lines.append(f"ℹ️ {html.escape(canonical)} - already in favorites")
        await reply_html(update, "<b>Results:</b>\n\n" + "\n".join(lines))

    async def remove_favorite_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if context.args:
            await self._remove_teams(update, [' '.join(context.args)])
            return ConversationHandler.END

        favorites = db.get_favorites(update.effective_user.id)
        if not favorites:
            await update.message.reply_text("You have no favorite teams to remove.")
            return ConversationHandler.END

        lines = [f"{i}. {html.escape(team)}" for i, team in enumerate(favorites, 1)]
        await reply_html(
            update,
            "Please enter one or more team names to remove (one per line or comma-separated):\n\n"
            "<b>Your favorite teams:</b>\n" + "\n".join(lines) + "\n\nOr send /cancel to abort.")
        return AWAITING_TEAM_NAME

    async def remove_favorite_finish(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._remove_teams(update, parse_team_list(update.message.text))
        return ConversationHandler.END

    async def _remove_teams(self, update: Update, names: List[str]):
        if not names:
            await update.message.reply_text("No team names provided.")
            return
        lines = []
        for name in names:
            removed = db.remove_favorite(update.effective_user.id, name)
            if removed:
                lines.append(f"✅ {html.escape(removed)} - removed from favorites")
            else:
                lines.append(f"❌ {html.escape(name)} - was not in favorites")
        await reply_html(update, "<b>Results:</b>\n\n" + "\n".join(lines))

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Action cancelled.")
        return ConversationHandler.END

    # --- Scheduled jobs ---------------------------------------------------------------

    async def _send(self, user_id: int, text: str) -> bool:
        """Send a (possibly long) HTML message to a user; False if it failed."""
        try:
            for chunk in split_message(text):
                await self.application.bot.send_message(
                    chat_id=user_id, text=chunk, parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True)
            return True
        except Forbidden:
            logger.info(f"User {user_id} has blocked the bot, skipping")
        except Exception as e:
            logger.error(f"Error sending message to user {user_id}: {e}")
        return False

    async def send_daily_summary(self):
        """Morning message: today's matches with the user's star rating, plus
        all of today's games of their favorite teams."""
        users = db.get_all_users()
        logger.info(f"Sending daily summary to {len(users)} users")
        favorites = {user_id: db.get_favorites(user_id) for user_id in users}
        all_teams = {t for teams in favorites.values() for t in teams}
        matches = await asyncio.to_thread(fetch_summary_matches, all_teams)

        for user_id in users:
            min_stars = db.get_min_stars(user_id)
            fav_games = [m for m in matches if any(m.has_team(t) for t in favorites[user_id])]
            important = [m for m in matches if m.stars >= min_stars and m not in fav_games]
            important.sort(key=lambda m: (-m.stars, by_time(m)))
            important = sorted(important[:MAX_SUMMARY_MATCHES], key=by_time)
            if not fav_games and not important:
                continue

            parts = [f"<b>🌅 Good Morning! Today's Matches ({today_local():%d.%m.%Y}):</b>"]
            if fav_games:
                parts += ["<b>❤️ Your Teams:</b>", format_matches(fav_games)]
            if important:
                parts += [f"<b>⭐ {min_stars}+ Stars:</b>", format_matches(important)]
            await self._send(user_id, '\n\n'.join(parts))

    async def check_match_results(self):
        """Notify users once when a favorite team's match has finished."""
        users = db.get_all_users_with_favorites()
        if not users:
            return
        # Look back a few hours so a missed run (HLTV blocked, restart) is caught up
        results = await asyncio.to_thread(scraper.get_recent_results, 6)

        for user_id in users:
            favorites = db.get_favorites(user_id)
            for result in results:
                team = next((t for t in favorites if result.has_team(t)), None)
                if not team or db.was_notification_sent(user_id, result.match_id, 'result'):
                    continue
                message = (f"🏁 <b>Match Finished!</b>\n\n{result.format_for_telegram()}\n\n"
                           f"Your favorite team: {html.escape(team)}")
                if await self._send(user_id, message):
                    db.mark_notification_sent(user_id, result.match_id, 'result')

    async def refresh_match_cache(self):
        await asyncio.to_thread(refresh_match_cache)

    async def daily_snapshot(self):
        await asyncio.to_thread(daily_snapshot)

    async def load_teams(self):
        teams = await asyncio.to_thread(scraper.refresh_teams)
        if teams:
            logger.info(f"Team list refreshed with {len(teams)} scraped teams")
        else:
            logger.warning("Team refresh found no teams (HLTV blocked?), keeping existing list")

    async def startup_warmup(self):
        # Match cache first: the team refresh reuses it for unranked teams
        await self.refresh_match_cache()
        await self.load_teams()

    async def prune_notifications(self):
        db.prune_notifications(days=30)

    def run(self):
        logger.info("Starting bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


def setup_logging():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
    )
    # httpx logs every Telegram long-poll request at INFO level
    logging.getLogger('httpx').setLevel(logging.WARNING)


def main():
    setup_logging()
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set! Please create a .env file.")
        raise SystemExit(1)
    TelegramBot().run()

