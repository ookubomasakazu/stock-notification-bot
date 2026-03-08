import requests
import os

# token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
token = "w1FUg1i7gGcpWcQit9UO1F2e8UZ4JU//Y9Fdf9Xz0YY7TufHU+WoaJrlNK5/AFRP9CdZrKUekXIxAdx7ttS0AjmQ0WTw7WGObcYaPiPQqKAwHxVPt6seW2bmJRJwi1XC/kgVCK2PUz0WpWA1j6/+OAdB04t89/1O/w1cDnyilFU="
url = "https://api.line.me/v2/bot/followers/ids"

headers = {
    "Authorization": f"Bearer {token}"
}

r = requests.get(url, headers=headers)
print(r.text)