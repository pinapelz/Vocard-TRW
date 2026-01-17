import discord
import aiohttp
import function as func
from discord.ext import commands
from discord import app_commands
from typing import Optional
from constants import SERVER_STATUS

class Exaroton(commands.Cog):
    """Exaroton server management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_api_key(self) -> Optional[str]:
        """Get the Exaroton API key from settings.json."""
        return func.settings.exaroton_api_key

    async def get_exaroton_settings(self, guild_id: int) -> Optional[dict]:
        """Get the Exaroton server settings for a guild."""
        settings = await func.get_settings(guild_id)
        return settings.get("exaroton_server")

    async def save_exaroton_settings(self, guild_id: int, exaroton_settings: dict) -> bool:
        """Save the Exaroton server settings for a guild."""
        try:
            result = await func.SETTINGS_DB.update_one(
                {"_id": guild_id},
                {"$set": {"exaroton_server": exaroton_settings}},
                upsert=True
            )

            if guild_id in func.SETTINGS_BUFFER:
                func.SETTINGS_BUFFER[guild_id]["exaroton_server"] = exaroton_settings
            else:
                func.SETTINGS_BUFFER[guild_id] = {"exaroton_server": exaroton_settings}

            return True
        except Exception as e:
            func.logger.error(f"Error saving Exaroton settings for guild {guild_id}: {e}")
            return False

    async def exaroton_api_request(self, endpoint: str, api_key: str, method: str = "GET", data: Optional[dict] = None) -> dict:
        """Make a request to the Exaroton API."""
        base_url = "https://api.exaroton.com/v1"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                if method == "GET":
                    async with session.get(f"{base_url}{endpoint}", headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            return {"success": False, "error": f"API returned status {response.status}"}
                elif method == "POST":
                    async with session.post(f"{base_url}{endpoint}", headers=headers, json=data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            return {"success": False, "error": f"API returned status {response.status}"}
                else:
                    return {"success": False, "error": f"Unsupported method: {method}"}
        except Exception as e:
            func.logger.error(f"Error making Exaroton API request: {e}")
            return {"success": False, "error": str(e)}

    @commands.hybrid_command(name="setexaroton", aliases=["exset", "setserver"])
    @app_commands.describe(server_id="Your Exaroton server ID")
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(func.cooldown_check, commands.BucketType.guild)
    async def set_server(self, ctx: commands.Context, server_id: str):
        """Set the Exaroton server ID for this Discord server."""
        if not ctx.guild:
            await func.send(ctx, "This command can only be used in a server!", ephemeral=True)
            return

        api_key = self.get_api_key()
        if not api_key:
            await func.send(ctx, "Exaroton API key is not configured in settings.json!", ephemeral=True)
            return

        exaroton_settings = {
            "server_id": server_id,
            "set_by": ctx.author.id
        }

        if await self.save_exaroton_settings(ctx.guild.id, exaroton_settings):
            await func.send(ctx, f"Exaroton server configured successfully! Server ID: `{server_id}`")
        else:
            await func.send(ctx, "Failed to save Exaroton settings.", ephemeral=True)

    @commands.hybrid_command(name="startserver", aliases=["start", "serverstart"])
    @commands.dynamic_cooldown(func.cooldown_check, commands.BucketType.guild)
    async def start_server(self, ctx: commands.Context):
        """Start the configured Exaroton server."""
        if not ctx.guild:
            await func.send(ctx, "This command can only be used in a server!", ephemeral=True)
            return

        await ctx.typing()

        api_key = self.get_api_key()
        if not api_key:
            await func.send(ctx, "Exaroton API key is not configured in settings.json!", ephemeral=True)
            return

        exaroton_settings = await self.get_exaroton_settings(ctx.guild.id)

        if not exaroton_settings:
            await func.send(ctx, "No Exaroton server configured. Use `setexaroton` command first.", ephemeral=True)
            return

        server_id = exaroton_settings.get("server_id", "")

        if not server_id:
            await func.send(ctx, "Invalid Exaroton configuration!", ephemeral=True)
            return

        result = await self.exaroton_api_request(f"/servers/{server_id}/start", api_key, method="POST")

        if result.get("success", False):
            await func.send(ctx, "alright i gotchu")
        else:
            error_msg = result.get("error", "Unknown error")
            await func.send(ctx, f"Failed to start server: {error_msg}", ephemeral=True)

    @commands.hybrid_command(name="serverstatus", aliases=["status", "checkserver"])
    @commands.dynamic_cooldown(func.cooldown_check, commands.BucketType.guild)
    async def check_status(self, ctx: commands.Context):
        """Check the status of the configured Exaroton server."""
        if not ctx.guild:
            await func.send(ctx, "This command can only be used in a server!", ephemeral=True)
            return

        await ctx.typing()

        api_key = self.get_api_key()
        if not api_key:
            await func.send(ctx, "Exaroton API key is not configured in settings.json!", ephemeral=True)
            return

        exaroton_settings = await self.get_exaroton_settings(ctx.guild.id)

        if not exaroton_settings:
            await func.send(ctx, "No Exaroton server configured. Use `setexaroton` command first.", ephemeral=True)
            return

        server_id = exaroton_settings.get("server_id", "")

        if not server_id:
            await func.send(ctx, "Invalid Exaroton configuration!", ephemeral=True)
            return

        result = await self.exaroton_api_request(f"/servers/{server_id}", api_key)

        if result.get("success", False) and "data" in result:
            server_data = result["data"]
            status = server_data.get("status", -1)

            embed = discord.Embed(
                title="Exaroton Server Status",
                color=discord.Color.green() if status == 1 else discord.Color.red()
            )
            embed.add_field(name="Status", value=SERVER_STATUS.get(status, "UNKNOWN"), inline=True)

            if "name" in server_data:
                embed.add_field(name="Server Name", value=server_data["name"], inline=True)

            if "address" in server_data:
                embed.add_field(name="Address", value=f"`{server_data['address']}`", inline=True)

            if "players" in server_data:
                players = server_data["players"]
                embed.add_field(name="Players", value=f"{players.get('count', 0)}/{players.get('max', 0)}", inline=True)

            await func.send(ctx, embed)
        else:
            error_msg = result.get("error", "Unknown error")
            await func.send(ctx, f"Failed to get server status: {error_msg}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Exaroton(bot))
