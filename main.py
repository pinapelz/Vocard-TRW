"""MIT License

Copyright (c) 2023 - present Vocard Development

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import discord
import sys
import os
import aiohttp
import update
import logging
import voicelink
import function as func
import certifi

from discord.ext import commands
from ipc import IPCClient
from motor.motor_asyncio import AsyncIOMotorClient
from logging.handlers import TimedRotatingFileHandler
from addons import Settings
from constants import restaurant_triggers, banned_restaurants, exaroton_start_triggers, exaroton_status_triggers, SERVER_STATUS
import datetime

ca = certifi.where()

class Translator(discord.app_commands.Translator):
    async def load(self):
        func.logger.info("Loaded Translator")

    async def unload(self):
        func.logger.info("Unload Translator")

    async def translate(self, string: discord.app_commands.locale_str, locale: discord.Locale, context: discord.app_commands.TranslationContext):
        locale_key = str(locale)

        if locale_key in func.LOCAL_LANGS:
            translated_text = func.LOCAL_LANGS[locale_key].get(string.message)

            if translated_text is None:
                missing_translations = func.MISSING_TRANSLATOR.setdefault(locale_key, [])
                if string.message not in missing_translations:
                    missing_translations.append(string.message)

            return translated_text

        return None

class Vocard(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.ipc: IPCClient

    async def on_message(self, message: discord.Message, /) -> None:
        # Ignore messages from bots or DMs
        if message.author.bot or not message.guild:
            return

        # Check if the bot is directly mentioned
        if message.content.strip() == self.user.mention and not message.mention_everyone:
            prefix = await self.command_prefix(self, message)
            if not prefix:
                await message.channel.send("I don't have a bot prefix set.")
                return
            await message.channel.send(f"My prefix is `{prefix}`")
            return

        # Check for restaurant trigger words in any message
        content = message.content.lower()
        if any(trigger in content for trigger in restaurant_triggers):
            try:
                restaurant_cog = self.get_cog("Restaurant")
                if restaurant_cog:
                    recommendation = await restaurant_cog.get_random_restaurant_for_mention(message.guild.id)
                    if recommendation:
                        await message.channel.send(recommendation)
                    else:
                        await message.channel.send("I don't have any restaurants saved yet! Use `restaurantadd <name>,cuisine/tags,location` to add some recommendations.")
                else:
                    await message.channel.send("Restaurant feature is not available right now.")
            except Exception as e:
                func.logger.error(f"Error in restaurant mention handler: {e}")
                await message.channel.send("Sorry, I couldn't get a restaurant recommendation right now.")
            return

        if self.user in message.mentions:
            content_lower = message.content.lower()
            if any(trigger in content_lower for trigger in exaroton_start_triggers):
                try:
                    exaroton_cog = self.get_cog("Exaroton")
                    if exaroton_cog:
                        api_key = exaroton_cog.get_api_key()
                        if not api_key:
                            await message.reply("API key not configured in settings.json!")
                            return

                        exaroton_settings = await exaroton_cog.get_exaroton_settings(message.guild.id)
                        if exaroton_settings:
                            server_id = exaroton_settings.get("server_id", "")

                            if server_id:
                                result = await exaroton_cog.exaroton_api_request(f"/servers/{server_id}/start", api_key, method="POST")
                                if result.get("success", False):
                                    await message.reply("alright im booting it up. let me cook")
                                else:
                                    error_msg = result.get("error", "Unknown error")
                                    await message.reply(f"Failed to start server: {error_msg}. report this issue to central command")
                            else:
                                await message.reply("yeah u ducked up something, idk how to read this config. report this to central command")
                        else:
                            await message.reply("little brother. how can i start the server when u didn't even give me a server id. restarted mf")
                    else:
                        await message.channel.send("sorry diddly party cannot be started at the moment")
                except Exception as e:
                    func.logger.error(f"Error in Exaroton start handler: {e}")
                    await message.channel.send("sorry diddly party cannot be started at the moment")
                return

            # Check for Exaroton server status triggers with bot mention
            if any(trigger in content_lower for trigger in exaroton_status_triggers):
                try:
                    exaroton_cog = self.get_cog("Exaroton")
                    if exaroton_cog:
                        api_key = exaroton_cog.get_api_key()
                        if not api_key:
                            await message.reply("API key not configured in settings.json!")
                            return

                        exaroton_settings = await exaroton_cog.get_exaroton_settings(message.guild.id)
                        if exaroton_settings:
                            server_id = exaroton_settings.get("server_id", "")

                            if server_id:
                                result = await exaroton_cog.exaroton_api_request(f"/servers/{server_id}", api_key)
                                if result.get("success", False) and "data" in result:
                                    server_data = result["data"]
                                    status = server_data.get("status", -1)

                                    embed = discord.Embed(title="Server Status", color=discord.Color.green() if status == 1 else discord.Color.red())
                                    embed.add_field(name="Status", value=SERVER_STATUS.get(status, "UNKNOWN"), inline=True)

                                    if "name" in server_data:
                                        embed.add_field(name="Server", value=server_data["name"], inline=True)

                                    if "players" in server_data:
                                        players = server_data["players"]
                                        embed.add_field(name="Players", value=f"{players.get('count', 0)}/{players.get('max', 0)}", inline=True)

                                    await message.channel.send(embed=embed)
                                else:
                                    error_msg = result.get("error", "Unknown error")
                                    await message.channel.send(f"Failed to get server status: {error_msg}. very bad. report this to central command")
                            else:
                                await message.channel.send("Exaroton server is not configured properly!")
                        else:
                            await message.channel.send("smh. how u want me to tell u anything when u didn't even set the server")
                    else:
                        await message.channel.send("Exaroton feature is not available right now.")
                except Exception as e:
                    func.logger.error(f"Error in Exaroton status handler: {e}")
                    await message.channel.send("Sorry, I couldn't check the server status right now.")
                return

        content_lower = content.lower()
        for banned_restaurant, custom_response in banned_restaurants.items():
            if banned_restaurant in content_lower:
                try:
                    await message.author.timeout(discord.utils.utcnow() + datetime.timedelta(seconds=30), reason=f"Mentioned banned restaurant: {banned_restaurant}")
                except discord.Forbidden:
                    pass
                except Exception as e:
                    func.logger.error(f"Error timing out user: {e}")
                await message.channel.send(f"{message.author.mention} {custom_response}")
                return

        # Fetch guild settings and check if the mesage is in the music request channel
        settings = await func.get_settings(message.guild.id)
        if settings and (request_channel := settings.get("music_request_channel")):
            if message.channel.id == request_channel.get("text_channel_id"):
                ctx = await self.get_context(message)
                try:
                    cmd = self.get_command("play")
                    if message.content:
                        await cmd(ctx, query=message.content)

                    elif message.attachments:
                        for attachment in message.attachments:
                            await cmd(ctx, query=attachment.url)

                except Exception as e:
                    await func.send(ctx, str(e), ephemeral=True)

                finally:
                    await message.delete()

        await self.process_commands(message)

    async def connect_db(self) -> None:
        if not ((db_name := func.settings.mongodb_name) and (db_url := func.settings.mongodb_url)):
            raise Exception("MONGODB_NAME and MONGODB_URL can't not be empty in settings.json")

        try:
            func.MONGO_DB = AsyncIOMotorClient(host=db_url, tlscafile=ca)
            await func.MONGO_DB.server_info()
            func.logger.info(f"Successfully connected to [{db_name}] MongoDB!")

        except Exception as e:
            func.logger.error("Not able to connect MongoDB! Reason:", exc_info=e)
            exit()

        func.SETTINGS_DB = func.MONGO_DB[db_name]["Settings"]
        func.USERS_DB = func.MONGO_DB[db_name]["Users"]

    async def setup_hook(self) -> None:
        func.langs_setup()

        # Connecting to MongoDB
        await self.connect_db()

        # Set translator
        await self.tree.set_translator(Translator())

        # Loading all the module in `cogs` folder
        for module in os.listdir(func.ROOT_DIR + '/cogs'):
            if module.endswith('.py'):
                try:
                    await self.load_extension(f"cogs.{module[:-3]}")
                    func.logger.info(f"Loaded {module[:-3]}")
                except Exception as e:
                    func.logger.error(f"Something went wrong while loading {module[:-3]} cog.", exc_info=e)

        self.ipc = IPCClient(self, **func.settings.ipc_client)
        if func.settings.ipc_client.get("enable", False):
            try:
                await self.ipc.connect()
            except Exception as e:
                func.logger.error(f"Cannot connected to dashboard! - Reason: {e}")

        # Update version tracking
        if not func.settings.version or func.settings.version != update.__version__:
            await self.tree.sync()
            func.update_json("settings.json", new_data={"version": update.__version__})
            for locale_key, values in func.MISSING_TRANSLATOR.items():
                func.logger.warning(f'Missing translation for "{", ".join(values)}" in "{locale_key}"')

    async def on_ready(self):
        func.logger.info("------------------")
        func.logger.info(f"Logging As {self.user}")
        func.logger.info(f"Bot ID: {self.user.id}")
        func.logger.info("------------------")
        func.logger.info(f"Discord Version: {discord.__version__}")
        func.logger.info(f"Python Version: {sys.version}")
        func.logger.info("------------------")

        func.settings.client_id = self.user.id
        func.LOCAL_LANGS.clear()
        func.MISSING_TRANSLATOR.clear()

    async def on_command_error(self, ctx: commands.Context, exception, /) -> None:
        error = getattr(exception, 'original', exception)
        if ctx.interaction:
            error = getattr(error, 'original', error)

        if isinstance(error, (commands.CommandNotFound, aiohttp.client_exceptions.ClientOSError, discord.errors.NotFound)):
            return

        elif isinstance(error, (commands.CommandOnCooldown, commands.MissingPermissions, commands.RangeError, commands.BadArgument)):
            pass

        elif isinstance(error, (commands.MissingRequiredArgument, commands.MissingRequiredAttachment)):
            command = f"{ctx.prefix}" + (f"{ctx.command.parent.qualified_name} " if ctx.command.parent else "") + f"{ctx.command.name} {ctx.command.signature}"
            position = command.find(f"<{ctx.current_parameter.name}>") + 1
            description = f"**Correct Usage:**\n```{command}\n" + " " * position + "^" * len(ctx.current_parameter.name) + "```\n"
            if ctx.command.aliases:
                description += f"**Aliases:**\n`{', '.join([f'{ctx.prefix}{alias}' for alias in ctx.command.aliases])}`\n\n"
            description += f"**Description:**\n{ctx.command.help}\n\u200b"

            embed = discord.Embed(description=description, color=func.settings.embed_color)
            embed.set_footer(icon_url=ctx.me.display_avatar.url, text=f"More Help: {func.settings.invite_link}")
            return await ctx.reply(embed=embed)

        elif not issubclass(error.__class__, voicelink.VoicelinkException):
            error = await func.get_lang(ctx.guild.id, "unknownException") + func.settings.invite_link
            func.logger.error(f"An unexpected error occurred in the {ctx.command.name} command on the {ctx.guild.name}({ctx.guild.id}).", exc_info=exception)

        try:
            return await ctx.reply(error, ephemeral=True)
        except:
            pass

class CommandCheck(discord.app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        if interaction.type == discord.InteractionType.application_command:
            if not interaction.guild:
                await interaction.response.send_message("This command can only be used in guilds!")
                return False

            channel_perm = interaction.channel.permissions_for(interaction.guild.me)
            if not channel_perm.read_messages or not channel_perm.send_messages:
                await interaction.response.send_message("I don't have permission to read or send messages in this channel.")
                return False

        return True

async def get_prefix(bot: commands.Bot, message: discord.Message) -> str:
    settings = await func.get_settings(message.guild.id)
    prefix = settings.get("prefix", func.settings.bot_prefix)

    # Allow owner to use the bot without a prefix
    if prefix and not message.content.startswith(prefix) and (await bot.is_owner(message.author) or message.author.id in func.settings.bot_access_user):
        return ""

    return prefix

# Loading settings and logger
func.settings = Settings(func.open_json("settings.json"))

LOG_SETTINGS = func.settings.logging
if (LOG_FILE := LOG_SETTINGS.get("file", {})).get("enable", True):
    log_path = os.path.abspath(LOG_FILE.get("path", "./logs"))
    if not os.path.exists(log_path):
        os.makedirs(log_path)

    file_handler = TimedRotatingFileHandler(filename=f'{log_path}/vocard.log', encoding="utf-8", backupCount=LOG_SETTINGS.get("max-history", 30), when="d")
    file_handler.namer = lambda name: name.replace(".log", "") + ".log"
    file_handler.setFormatter(logging.Formatter('{asctime} [{levelname:<8}] {name}: {message}', '%Y-%m-%d %H:%M:%S', style='{'))
    logging.getLogger().addHandler(file_handler)

for log_name, log_level in LOG_SETTINGS.get("level", {}).items():
    _logger = logging.getLogger(log_name)
    _logger.setLevel(log_level)

# Setup the bot object
intents = discord.Intents.default()
intents.message_content = False if func.settings.bot_prefix is None else True
intents.members = func.settings.ipc_client.get("enable", False)
intents.voice_states = True

bot = Vocard(
    command_prefix=get_prefix,
    help_command=None,
    tree_cls=CommandCheck,
    chunk_guilds_at_startup=False,
    activity=discord.Activity(type=discord.ActivityType.listening, name="Starting..."),
    case_insensitive=True,
    intents=intents
)

if __name__ == "__main__":
    update.check_version(with_msg=True)
    bot.run(func.settings.token, root_logger=True)
