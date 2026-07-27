import logging
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import store
from deploy import DeployError, deploy_zip, delete_project, stop_project

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("hosting-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
ALLOWED_USER_IDS = {
    int(x) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x.strip().isdigit()
}


def is_allowed(user_id: int) -> bool:
    return not ALLOWED_USER_IDS or user_id in ALLOWED_USER_IDS


def project_url(project: dict) -> str:
    if project["type"] == "static":
        return f"{PUBLIC_BASE_URL}/sites/{project['id']}/"
    return f"{PUBLIC_BASE_URL}/app/{project['id']}/"


def project_keyboard(project: dict) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🌐 Open", url=project_url(project), style="primary")],
        [
            InlineKeyboardButton("🔁 Redeploy", callback_data=f"redeploy_{project['id']}", style="success"),
            InlineKeyboardButton("⏹ Stop", callback_data=f"stop_{project['id']}", style="danger"),
        ],
        [InlineKeyboardButton("🗑 Delete", callback_data=f"delete_{project['id']}", style="danger")],
    ]
    return InlineKeyboardMarkup(rows)


def project_summary(p: dict) -> str:
    return (
        f"<b>{p['name']}</b>\n"
        f"Type: {p['type']}\n"
        f"Status: {p['status']}\n"
        f"URL: {project_url(p)}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("Sorry, you're not allowed to use this bot.")
        return
    await update.message.reply_text(
        "Zip file pathao (.zip) — automatically host hoye jabe.\n"
        "Static (HTML/CSS/JS), Node.js (package.json), r Java (Maven/Gradle) — shob support kore.\n\n"
        "/projects — tomar shob deployed project dekhte."
    )


async def list_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    projects = store.for_owner(update.effective_user.id)
    if not projects:
        await update.message.reply_text("Kono project deploy kora nai. Ekta .zip pathao.")
        return
    for p in projects:
        await update.message.reply_text(
            project_summary(p), parse_mode="HTML", reply_markup=project_keyboard(p)
        )


async def handle_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("Sorry, you're not allowed to use this bot.")
        return

    doc = update.message.document
    if not doc or not doc.file_name.lower().endswith(".zip"):
        await update.message.reply_text("Ekta .zip file pathao.")
        return

    redeploy_target = context.user_data.pop("redeploy_target", None)
    status_msg = await update.message.reply_text("⏳ Deploy hocche, wait koro...")

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / doc.file_name
        tg_file = await doc.get_file()
        await tg_file.download_to_drive(str(zip_path))

        project_name = doc.file_name.rsplit(".", 1)[0]
        try:
            project = deploy_zip(
                str(zip_path), project_name, user.id, existing_id=redeploy_target
            )
        except DeployError as e:
            await status_msg.edit_text(f"❌ Deploy failed:\n{str(e)[:500]}")
            return
        except Exception as e:
            log.exception("deploy crashed")
            await status_msg.edit_text(f"❌ Unexpected error: {e}")
            return

    await status_msg.edit_text(
        f"✅ Deployed!\n\n{project_summary(project)}",
        parse_mode="HTML",
        reply_markup=project_keyboard(project),
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, _, project_id = query.data.partition("_")

    project = store.get(project_id)
    if not project or project["owner_id"] != update.effective_user.id:
        await query.edit_message_text("Project not found (or it's not yours).")
        return

    if action == "stop":
        stop_project(project_id)
        project = store.get(project_id)
        await query.edit_message_text(
            project_summary(project), parse_mode="HTML", reply_markup=project_keyboard(project)
        )
    elif action == "delete":
        delete_project(project_id)
        await query.edit_message_text(f"🗑 Deleted \"{project['name']}\".")
    elif action == "redeploy":
        context.user_data["redeploy_target"] = project_id
        await query.message.reply_text(
            f"Notun .zip pathao \"{project['name']}\" redeploy korte."
        )


def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN missing in .env")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("projects", list_projects))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_zip))
    app.add_handler(CallbackQueryHandler(button_callback))

    log.info("Hosting bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
