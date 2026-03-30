# notifications-f1

This project exposes a FastAPI webhook to process Telegram updates and a protected wake-up endpoint for scheduled jobs.

Today the bot supports:

- registration with `/start`
- alert activation with `/subscribe`
- alert deactivation with `/unsubscribe`
- timezone selection with `/set_country`
- weekly digest delivery through `POST /wake-up`

## Does it write to Supabase using `supabase-py`?

Yes. Database writes are done with `supabase-py`, not with direct SQL and not with the database password.

The main flow is here:

- [adapters.py](/mnt/c/Users/cyani/Documents/test/notifications-f1/supabase/functions/telegram-bot/adapters.py) creates a shared Supabase client and exposes separate repositories for `users` and `bot_settings`.
- [adapters.py](/mnt/c/Users/cyani/Documents/test/notifications-f1/supabase/functions/telegram-bot/adapters.py) persists users with `supabase-py`.
- [adapters.py](/mnt/c/Users/cyani/Documents/test/notifications-f1/supabase/functions/telegram-bot/adapters.py) sends Telegram messages, inline keyboards, and callback answers.
- [entrypoints.py](/mnt/c/Users/cyani/Documents/test/notifications-f1/supabase/functions/telegram-bot/entrypoints.py) exposes `POST /webhook` and `POST /wake-up`.
- [application.py](/mnt/c/Users/cyani/Documents/test/notifications-f1/supabase/functions/telegram-bot/application.py) orchestrates the bot and wake-up use cases.

The `db password` is not used in this code. To run this app, the relevant variables are:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `TELEGRAM_TOKEN`
- `SECRET_TOKEN`

## Environment Variables

You can put them in a `.env` file at the project root:

```env
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_KEY=YOUR_SUPABASE_KEY
TELEGRAM_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
SECRET_TOKEN=YOUR_SECRET_BEARER_TOKEN
```

`load_dotenv()` runs at startup, so `uvicorn` will load these variables from `.env`.

## Run The App Locally

Create the virtual environment:

```bash
cd /mnt/c/Users/cyani/Documents/test/notifications-f1
python3 -m venv .venv
```

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt uvicorn==0.42.0
```

Start FastAPI:

```bash
uvicorn entrypoints:app --app-dir supabase/functions/telegram-bot --host 127.0.0.1 --port 8000 --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/
```

Expected response:

```json
{"status":"online","architecture":"hexagonal"}
```

If you prefer not to activate the environment, you can use explicit paths:

```bash
.venv/bin/python -m pip install -r requirements.txt uvicorn==0.42.0
.venv/bin/uvicorn entrypoints:app --app-dir supabase/functions/telegram-bot --host 127.0.0.1 --port 8000 --reload
```

## Webhook Flow

The `POST /webhook` endpoint expects a payload compatible with a Telegram update.

### `/start`

If the user does not exist yet:

1. The bot inserts the user into `users`.
2. The default timezone is stored as `UTC`.
3. It reads `welcome_msg` from `bot_settings`.
4. It replaces `{name}` with the Telegram `first_name`.
5. It sends that welcome text with an inline button: `🔔 Activar alertas`.

If the user already exists:

1. It reads `already_registered` from `bot_settings`.
2. It replaces `{name}` with `first_name`.
3. It replaces `{tz}` with the current timezone stored in `users.timezone`.
4. It sends a single informational message and does not restart onboarding.

### Subscribe onboarding

The inline button uses a Telegram callback. When the user presses it:

1. The bot answers the callback so Telegram stops showing the loading spinner.
2. It updates the user status to `active`.
3. It reads `subscribe_ok` from `bot_settings`.
4. It replaces `{name}` with `first_name`.
5. It edits the original message to show the confirmation text.

The bot also supports `/subscribe` as a normal command. In that case it updates `status` to `active` and sends the rendered `subscribe_ok` message.

### `/unsubscribe`

When the user sends `/unsubscribe`:

1. The bot updates `status` to `inactive`.
2. It reads `unsubscribe_ok` from `bot_settings`.
3. It sends the confirmation message.

### `/set_country`

When the user sends `/set_country`, the bot sends an inline country selector with:

- `🇨🇱 Chile`
- `🇦🇷 Argentina`
- `🇨🇴 Colombia`
- `🇪🇸 España`
- `🇺🇾 Uruguay`

When the user taps one of those buttons:

1. The bot maps the callback to a timezone.
2. It updates `users.timezone`.
3. It answers the callback so Telegram stops waiting.
4. It reads `timezone_confirmation_text` from `bot_settings`.
5. It replaces `{name}` with `first_name`.
6. It edits the original country-selector message with the confirmation text.

The bot now expects these keys to exist in `bot_settings`:

- `welcome_msg`
- `already_registered`
- `subscribe_ok`
- `unsubscribe_ok`
- `timezone_confirmation_text`
- `weekly_summary_msg`

If any of them is missing when its command is executed, the request returns an error instead of using a hardcoded fallback message.

## Example Webhook Payloads

This `curl` triggers `/start`:

```bash
curl -X POST http://127.0.0.1:8000/webhook \
  -H 'Content-Type: application/json' \
  -d '{
    "update_id": 999001,
    "message": {
      "message_id": 1,
      "date": 1711740000,
      "chat": {
        "id": "<YOUR_TELEGRAM_ID>",
        "type": "private",
        "first_name": "John"
      },
      "from": {
        "id": "<YOUR_TELEGRAM_ID>",
        "is_bot": false,
        "first_name": "John",
        "username": "john_doe"
      },
      "text": "/start"
    }
  }'
```

Expected response if the flow completes without errors:

```json
{"status":"ok"}
```

To test `/subscribe`, send the same payload and only change `text`:

```bash
curl -X POST http://127.0.0.1:8000/webhook \
  -H 'Content-Type: application/json' \
  -d '{
    "update_id": 999002,
    "message": {
      "message_id": 2,
      "date": 1711740001,
      "chat": {
        "id": "<YOUR_TELEGRAM_ID>",
        "type": "private",
        "first_name": "John"
      },
      "from": {
        "id": "<YOUR_TELEGRAM_ID>",
        "is_bot": false,
        "first_name": "John",
        "username": "john_doe"
      },
      "text": "/subscribe"
    }
  }'
```

Expected response:

```json
{"status":"ok"}
```

To test `/unsubscribe`, use this payload:

```bash
curl -X POST http://127.0.0.1:8000/webhook \
  -H 'Content-Type: application/json' \
  -d '{
    "update_id": 999003,
    "message": {
      "message_id": 3,
      "date": 1711740002,
      "chat": {
        "id": "<YOUR_TELEGRAM_ID>",
        "type": "private",
        "first_name": "John"
      },
      "from": {
        "id": "<YOUR_TELEGRAM_ID>",
        "is_bot": false,
        "first_name": "John",
        "username": "john_doe"
      },
      "text": "/unsubscribe"
    }
  }'
```

Expected response:

```json
{"status":"ok"}
```

To test a timezone callback, you can send a payload like this:

```json
{
  "update_id": 999010,
  "callback_query": {
    "id": "2053639717951473055",
    "from": {
      "id": 1568732224,
      "is_bot": false,
      "first_name": "John",
      "username": "john_doe"
    },
    "message": {
      "message_id": 19,
      "chat": {
        "id": 1568732224,
        "type": "private"
      },
      "text": "Elige tu pais para configurar la zona horaria:"
    },
    "data": "tz_cl"
  }
}
```

## What Should Be Written

In the `users` table, a registered row should look roughly like this:

```json
{
  "user_id": 1568732224,
  "first_name": "John",
  "username": "john_doe",
  "status": "inactive",
  "timezone": "UTC"
}
```

Important behavior:

- new users default to `timezone: "UTC"`
- repeated `/start` does not create duplicates
- if the row already exists, the current `status` and `timezone` are preserved
- `/subscribe` changes `status` to `"active"`
- `/unsubscribe` changes `status` to `"inactive"`
- `tz_*` callbacks update `timezone`

## Verify The Row Through Supabase REST

You can query the table like this:

```bash
curl "$SUPABASE_URL/rest/v1/users?user_id=eq.1568732224&select=*" \
  -H "apikey: $SUPABASE_KEY" \
  -H "Authorization: Bearer $SUPABASE_KEY"
```

## Wake Up Endpoint

The `POST /wake-up` endpoint is protected with a bearer token that must match `SECRET_TOKEN`.

It currently supports the `weekly_digest` trigger. When it receives that trigger:

1. It fetches the next upcoming session from OpenF1.
2. It resolves the session location from the meeting data.
3. It converts the session start time to Chile time.
4. It reads `weekly_summary_msg` from `bot_settings`.
5. It sends the rendered message to every user whose row in `users` has `status: "active"`.

The message template can use these placeholders:

- `{name}`
- `{location}`
- `{time}`
- `{session_name}`

You can trigger it manually with:

```bash
curl -X POST http://127.0.0.1:8000/wake-up \
  -H "Authorization: Bearer $SECRET_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"trigger_type":"weekly_digest"}'
```

If the bearer token is missing or invalid, the endpoint returns:

```json
{"detail":"Unauthorized"}
```

Example response when the digest is sent:

```json
{
  "status": "awake",
  "source": "OpenF1",
  "trigger_type": "weekly_digest",
  "next_session": {
    "name": "FORMULA 1 AUSTRALIAN GRAND PRIX 2026 - Practice 1",
    "location": "Melbourne",
    "utc_start": "2026-04-10T01:30:00Z",
    "chile_start": "2026-04-09 21:30 -04",
    "minutes_to_start": 15090
  },
  "action_taken": "weekly_digest_sent",
  "messages_sent": 2
}
```

## Notes

- The webhook ignores duplicate `update_id` values to reduce accidental double-processing.
- Telegram messages are sent as plain text by default, not Markdown, so templates from `bot_settings` do not need Markdown escaping.
