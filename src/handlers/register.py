"""Register all Telegram handlers on the application."""

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from src.handlers import commands, ingress, text


def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", commands.start_command))
    app.add_handler(CommandHandler("help", commands.help_command))
    app.add_handler(CommandHandler("add", commands.add_command))
    app.add_handler(CommandHandler("recent", commands.recent_command))
    app.add_handler(CommandHandler("undo", commands.undo_command))
    app.add_handler(CommandHandler("delete", commands.delete_command))
    app.add_handler(CommandHandler("pending", commands.pending_command))
    app.add_handler(MessageHandler(filters.Document.ALL, ingress.handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, ingress.handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text.handle_text))
