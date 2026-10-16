import logging
import os
from decimal import Decimal

import discord
from discord.ext import tasks


logging.basicConfig(level=logging.INFO)
log = logging.getLogger("biggerz-wins")

INTERVAL_SECONDS = 17
BIGGERZ_URL = "https://biggerz.com"

# Données fictives réservées à la présentation client.
# La future intégration remplacera cette liste par les événements BiggerZ.
PREVIEW_WINS = [
    {"name": "Jonathan", "amount": "1.2", "currency": "ETH"},
    {"name": "Alex", "amount": "850", "currency": "USDT"},
    {"name": "Sarah", "amount": "0.035", "currency": "BTC"},
    {"name": "Lucas", "amount": "2.4", "currency": "ETH"},
    {"name": "Emma", "amount": "1250", "currency": "USDT"},
    {"name": "James", "amount": "12.5", "currency": "SOL"},
    {"name": "Oliver", "amount": "0.8", "currency": "ETH"},
    {"name": "Sophie", "amount": "320", "currency": "USDT"},
    {"name": "Nathan", "amount": "0.012", "currency": "BTC"},
    {"name": "Chloe", "amount": "5.75", "currency": "SOL"},
]


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing Railway variable: {name}")
    return value


def format_amount(value):
    amount = Decimal(value)
    if not amount.is_finite() or amount <= 0:
        raise ValueError("The win amount must be positive.")

    formatted = format(amount, ",f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")

    return formatted


def build_win_message(win):
    name = discord.utils.escape_markdown(win["name"])
    amount = format_amount(win["amount"])
    currency = win["currency"]

    embed = discord.Embed(
        title="🏆 BIGGERZ WIN",
        description=(
            f"**{name} just won!**\n\n"
            f"## 💰 {amount} {currency}\n\n"
            "[biggerz.com](https://biggerz.com)"
        ),
        color=0xF5C451,
    )

    # Facultatif : URL HTTPS publique directe vers le logo.
    logo_url = os.environ.get("LOGO_URL", "").strip()
    if logo_url:
        embed.set_thumbnail(url=logo_url)

    view = discord.ui.View()
    view.add_item(
        discord.ui.Button(
            label="Visit BiggerZ",
            style=discord.ButtonStyle.link,
            url=BIGGERZ_URL,
        )
    )

    return embed, view


class BiggerZWinsBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.none()
        intents.guilds = True

        super().__init__(
            intents=intents,
            allowed_mentions=discord.AllowedMentions.none(),
        )

        self.guild_id = int(required("DISCORD_GUILD_ID"))
        self.channel_id = int(required("WINS_CHANNEL_ID"))
        self.win_index = 0

        logo_url = os.environ.get("LOGO_URL", "").strip()
        if logo_url and not logo_url.startswith("https://"):
            raise RuntimeError("LOGO_URL must start with https://")

    async def setup_hook(self):
        # Démarré une seule fois, même si Discord se reconnecte.
        self.publish_wins.start()

    async def on_ready(self):
        log.info(
            "Connected. Preview messages scheduled every %s seconds.",
            INTERVAL_SECONDS,
        )

    async def send_win(self, win):
        channel = self.get_channel(self.channel_id)

        if channel is None:
            channel = await self.fetch_channel(self.channel_id)

        if not isinstance(channel, discord.TextChannel):
            raise RuntimeError(
                "WINS_CHANNEL_ID must point to a server text channel."
            )

        if channel.guild.id != self.guild_id:
            raise RuntimeError(
                "The target channel does not belong to DISCORD_GUILD_ID."
            )

        embed, view = build_win_message(win)

        await channel.send(
            embed=embed,
            view=view,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @tasks.loop(seconds=INTERVAL_SECONDS)
    async def publish_wins(self):
        if not self.is_ready():
            return

        win = PREVIEW_WINS[self.win_index % len(PREVIEW_WINS)]

        try:
            await self.send_win(win)
        except discord.Forbidden:
            log.error(
                "Cannot publish: check View Channel, Send Messages "
                "and Embed Links permissions."
            )
        except discord.NotFound:
            log.error(
                "Channel not found. Check WINS_CHANNEL_ID."
            )
        except discord.HTTPException as error:
            log.warning(
                "Discord request failed (HTTP %s). "
                "Will retry on the next scheduled run.",
                error.status,
            )
        except RuntimeError as error:
            log.error("%s", error)
            self.publish_wins.stop()
        else:
            self.win_index += 1
            log.info("Preview message published.")

    @publish_wins.before_loop
    async def before_publish_wins(self):
        await self.wait_until_ready()

    async def close(self):
        self.publish_wins.cancel()
        await super().close()


if __name__ == "__main__":
    token = required("DISCORD_TOKEN")
    bot = BiggerZWinsBot()
    bot.run(token, log_level=logging.WARNING)
