import os

import requests


def send_f1_alert() -> dict:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    message = os.getenv(
        "TELEGRAM_MESSAGE",
        "🏎️ DESPIERTA!\nYa están en la vuelta de formación en Suzuka. ¡Prende la tele que largan ya!",
    )

    if not token or not chat_id:
        raise ValueError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID.")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }

    response = requests.post(url, json=payload, timeout=15)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    result = send_f1_alert()
    print(result)
