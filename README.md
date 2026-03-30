# notifications-f1

This project exposes a FastAPI webhook to process Telegram updates. When it receives a `"/start"` message, it saves or updates the user in Supabase and then sends a welcome message through Telegram.

## Does it write to Supabase using `supabase-py`?

Yes. Database writes are done with `supabase-py`, not with direct SQL and not with the database password.

The flow is here:

- [adapters.py](/mnt/c/Users/cyani/Documents/test/notifications-f1/supabase/functions/telegram-bot/adapters.py#L13) creates the client with `create_client(supabase_url, supabase_key)`.
- [adapters.py](/mnt/c/Users/cyani/Documents/test/notifications-f1/supabase/functions/telegram-bot/adapters.py#L16) persists with `self.client.table("users").upsert(...).execute()`.
- [entrypoints.py](/mnt/c/Users/cyani/Documents/test/notifications-f1/supabase/functions/telegram-bot/entrypoints.py#L39) exposes `POST /webhook`.
- [application.py](/mnt/c/Users/cyani/Documents/test/notifications-f1/supabase/functions/telegram-bot/application.py#L18) orchestrates the supported Telegram commands.

The `db password` is not used in this code. To run this app, the relevant variables are:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `TELEGRAM_TOKEN`

## Environment Variables

You can put them in a `.env` file at the project root:

```env
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_KEY=YOUR_SUPABASE_KEY
TELEGRAM_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
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

## What The Webhook Does

The `POST /webhook` endpoint expects a payload compatible with a Telegram update.

If it receives an update whose `message.text` is `"/start"`:

1. It rebuilds the Telegram `Update`.
2. It reads `user.id`, `user.first_name`, and `user.username`.
3. It performs an `upsert` into the `users` table.
4. It reads `welcome_msg` from `bot_settings`.
5. If that template includes a placeholder, it must use `{name}` because the code replaces that exact token.
6. It sends a welcome message through Telegram.

The bot now expects these keys to exist in `bot_settings`:

- `welcome_msg`
- `subscribe_ok`
- `unsubscribe_ok`

If any of them is missing when its command is executed, the request returns an error instead of using a hardcoded fallback message.

## `curl` To Test Writes In Supabase

This `curl` triggers the full `/start` flow:

```bash
curl -X POST http://127.0.0.1:8000/webhook \
  -H 'Content-Type: application/json' \
  -d '{
    "update_id": 999001,
    "message": {
      "message_id": 1,
      "date": 1711740000,
      "chat": {
        "id": 1568732224,
        "type": "private",
        "first_name": "John"
      },
      "from": {
        "id": 1568732224,
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

To test `/subscribe`, you can send the same payload and only change `text`:

```bash
curl -X POST http://127.0.0.1:8000/webhook \
  -H 'Content-Type: application/json' \
  -d '{
    "update_id": 999002,
    "message": {
      "message_id": 2,
      "date": 1711740001,
      "chat": {
        "id": 1568732224,
        "type": "private",
        "first_name": "John"
      },
      "from": {
        "id": 1568732224,
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

After `/subscribe`, the user's row should have `status: "active"`.

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
        "id": 1568732224,
        "type": "private",
        "first_name": "John"
      },
      "from": {
        "id": 1568732224,
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

After `/unsubscribe`, the user's row should have `status: "inactive"`.

## What Should Be Written

In the `users` table, you should end up with something equivalent to:

```json
{
  "user_id": 1568732224,
  "first_name": "John",
  "username": "john_doe",
  "status": "inactive"
}
```

The operation uses `upsert`, so if you send `/start` again for the same `user_id`, it updates the row instead of duplicating it.
If the row already exists, the current `status` is preserved, so repeated `/start` does not silently unsubscribe an active user.

## Verify The Row Through Supabase REST

You can query the table like this:

```bash
curl "$SUPABASE_URL/rest/v1/users?user_id=eq.1568732224&select=*" \
  -H "apikey: $SUPABASE_KEY" \
  -H "Authorization: Bearer $SUPABASE_KEY"
```

## Important Note About Errors

The flow writes to Supabase first and only then tries to send the Telegram message.

That means you may see an error response from the webhook if Telegram fails, while the row in `users` may already have been persisted.
