"""Register all Telegram handlers on the application."""

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from src.handlers import commands, guided_add, ingress, reminders, text


def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", commands.start_command))
    app.add_handler(CommandHandler("help", commands.help_command))
    app.add_handler(CommandHandler("add", commands.add_command))
    app.add_handler(CommandHandler("addsupport", commands.addsupport_command))
    app.add_handler(CommandHandler("remind", reminders.remind_command))
    app.add_handler(CommandHandler("recent", commands.recent_command))
    app.add_handler(CommandHandler("undo", commands.undo_command))
    app.add_handler(CommandHandler("delete", commands.delete_command))
    app.add_handler(CallbackQueryHandler(reminders.handle_reminder_callback, pattern=r"^rm:"))
    app.add_handler(CallbackQueryHandler(guided_add.handle_guided_callback, pattern=r"^ga:"))
    app.add_handler(MessageHandler(filters.Document.ALL, ingress.handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, ingress.handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text.handle_text))
