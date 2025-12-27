import discord
import random
import function as func

from discord.ext import commands
from discord import app_commands
from typing import List, Optional

class Restaurant(commands.Cog):
    """Restaurant recommendation system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_restaurants(self, guild_id: int) -> List[dict]:
        """Get the restaurant list for a guild."""
        settings = await func.get_settings(guild_id)
        return settings.get("restaurants", [])

    async def save_restaurants(self, guild_id: int, restaurants: List[dict]) -> bool:
        """Save the restaurant list for a guild."""
        try:
            # Update the database with upsert
            result = await func.SETTINGS_DB.update_one(
                {"_id": guild_id},
                {"$set": {"restaurants": restaurants}},
                upsert=True
            )

            # Update the buffer cache
            if guild_id in func.SETTINGS_BUFFER:
                func.SETTINGS_BUFFER[guild_id]["restaurants"] = restaurants
            else:
                func.SETTINGS_BUFFER[guild_id] = {"restaurants": restaurants}

            return True
        except Exception as e:
            func.logger.error(f"Error saving restaurants for guild {guild_id}: {e}")
            return False

    restaurant_group = app_commands.Group(name="restaurant", description="Manage restaurant recommendations")

    @restaurant_group.command(name="add", description="Add a restaurant to the recommendation list")
    @app_commands.describe(
        name="The name of the restaurant",
        cuisine="The type of cuisine (optional)",
        location="The location/address (optional)"
    )
    async def add_restaurant(
        self,
        interaction: discord.Interaction,
        name: str,
        cuisine: Optional[str] = None,
        location: Optional[str] = None
    ):
        """Add a restaurant to the guild's recommendation list."""
        restaurants = await self.get_restaurants(interaction.guild.id)

        # Check if restaurant already exists
        for restaurant in restaurants:
            if restaurant["name"].lower() == name.lower():
                await interaction.response.send_message(f"**{name}** is already in the restaurant list!", ephemeral=True)
                return

        # Create restaurant entry
        restaurant_entry = {
            "name": name,
            "added_by": interaction.user.id,
            "added_by_name": interaction.user.display_name
        }

        if cuisine:
            restaurant_entry["cuisine"] = cuisine
        if location:
            restaurant_entry["location"] = location

        restaurants.append(restaurant_entry)

        if await self.save_restaurants(interaction.guild.id, restaurants):
            embed = discord.Embed(
                title="Restaurant Added! 🍽️",
                description=f"**{name}** has been added to the restaurant list!",
                color=func.settings.embed_color
            )

            if cuisine:
                embed.add_field(name="Cuisine", value=cuisine, inline=True)
            if location:
                embed.add_field(name="Location", value=location, inline=True)

            embed.set_footer(text=f"Added by {interaction.user.display_name}")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("Failed to add restaurant. Please try again later.", ephemeral=True)

    @restaurant_group.command(name="remove", description="Remove a restaurant from the recommendation list")
    @app_commands.describe(name="The name of the restaurant to remove")
    async def remove_restaurant(self, interaction: discord.Interaction, name: str):
        """Remove a restaurant from the guild's recommendation list."""
        restaurants = await self.get_restaurants(interaction.guild.id)

        # Find and remove the restaurant
        restaurant_to_remove = None
        for i, restaurant in enumerate(restaurants):
            if restaurant["name"].lower() == name.lower():
                restaurant_to_remove = restaurants.pop(i)
                break

        if not restaurant_to_remove:
            await interaction.response.send_message(f"**{name}** was not found in the restaurant list!", ephemeral=True)
            return

        if await self.save_restaurants(interaction.guild.id, restaurants):
            embed = discord.Embed(
                title="Restaurant Removed! 🗑️",
                description=f"**{restaurant_to_remove['name']}** has been removed from the restaurant list!",
                color=func.settings.embed_color
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("Failed to remove restaurant. Please try again later.", ephemeral=True)

    @restaurant_group.command(name="list", description="Show all restaurants in the recommendation list")
    async def list_restaurants(self, interaction: discord.Interaction):
        """List all restaurants in the guild's recommendation list."""
        restaurants = await self.get_restaurants(interaction.guild.id)

        if not restaurants:
            await interaction.response.send_message("No restaurants have been added yet! Use `restaurantadd <name>,cuisine/tags,location` to add some.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Restaurant List 🍽️ ({len(restaurants)} restaurants)",
            color=func.settings.embed_color
        )

        # Group restaurants for better display
        restaurant_text = ""
        for i, restaurant in enumerate(restaurants, 1):
            restaurant_info = f"**{i}. {restaurant['name']}**"

            details = []
            if restaurant.get("cuisine"):
                details.append(f"*{restaurant['cuisine']}*")
            if restaurant.get("location"):
                details.append(f"📍 {restaurant['location']}")

            if details:
                restaurant_info += f" - {' | '.join(details)}"

            restaurant_info += f"\n*Added by {restaurant.get('added_by_name', 'Unknown')}*\n\n"

            # Check if adding this would exceed embed limit
            if len(restaurant_text + restaurant_info) > 4000:
                break

            restaurant_text += restaurant_info

        embed.description = restaurant_text
        await interaction.response.send_message(embed=embed)

    @restaurant_group.command(name="random", description="Get a random restaurant recommendation")
    async def random_restaurant(self, interaction: discord.Interaction):
        """Get a random restaurant recommendation from the guild's list."""
        restaurants = await self.get_restaurants(interaction.guild.id)

        if not restaurants:
            await interaction.response.send_message("No restaurants have been added yet! Use `restaurantadd <name>,cuisine/tags,location` to add some.", ephemeral=True)
            return

        recommendation_text = await self.get_random_restaurant_for_mention(interaction.guild.id)
        if recommendation_text:
            await interaction.response.send_message(recommendation_text)
        else:
            await interaction.response.send_message("No restaurants have been added yet! Use `restaurantadd <name>,cuisine/tags,location` to add some.", ephemeral=True)

    @restaurant_group.command(name="clear", description="Clear all restaurants from the list")
    async def clear_restaurants(self, interaction: discord.Interaction):
        """Clear all restaurants from the guild's recommendation list."""
        # Check if user has manage guild permissions
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("You need the 'Manage Server' permission to clear the restaurant list!", ephemeral=True)
            return

        restaurants = await self.get_restaurants(interaction.guild.id)

        if not restaurants:
            await interaction.response.send_message("The restaurant list is already empty!", ephemeral=True)
            return

        outer_self = self

        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30.0)

            @discord.ui.button(label="Yes, Clear All", style=discord.ButtonStyle.danger)
            async def confirm(self, interaction_inner: discord.Interaction, button: discord.ui.Button):
                if await outer_self.save_restaurants(interaction.guild.id, []):
                    embed = discord.Embed(
                        title="Restaurant List Cleared! 🗑️",
                        description=f"All {len(restaurants)} restaurants have been removed from the list.",
                        color=func.settings.embed_color
                    )
                    await interaction_inner.response.edit_message(embed=embed, view=None)
                else:
                    await interaction_inner.response.edit_message(content="Failed to clear restaurants. Please try again later.", embed=None, view=None)

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction_inner: discord.Interaction, button: discord.ui.Button):
                await interaction_inner.response.edit_message(content="Cancelled clearing restaurant list.", embed=None, view=None)

        embed = discord.Embed(
            title="⚠️ Confirm Clear All Restaurants",
            description=f"Are you sure you want to remove all {len(restaurants)} restaurants from the list?\n\n**This action cannot be undone!**",
            color=discord.Color.orange()
        )

        view = ConfirmView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def get_random_restaurant_for_mention(self, guild_id: int) -> Optional[str]:
        """Get a random restaurant name for mention responses."""
        restaurants = await self.get_restaurants(guild_id)
        if not restaurants:
            return None

        restaurant = random.choice(restaurants)
        name = restaurant['name']
        cuisine = restaurant.get('cuisine')
        location = restaurant.get('location')

        cuisine_text = cuisine if cuisine else "idk what cuisine they cook"
        location_text = location if location else "idk where tf it is"

        return f"Go to **{name}** - {cuisine_text} - {location_text}"

    async def get_restaurants_by_keyword(self, guild_id: int, keyword: str) -> List[dict]:
        """Get restaurants that match a specific keyword in their cuisine."""
        restaurants = await self.get_restaurants(guild_id)
        if not restaurants:
            return []

        keyword_lower = keyword.lower()
        matching_restaurants = []

        for restaurant in restaurants:
            cuisine = restaurant.get('cuisine', '').lower()
            if keyword_lower in cuisine:
                matching_restaurants.append(restaurant)

        return matching_restaurants

    async def get_random_restaurant_with_keyword(self, guild_id: int, keyword: str) -> Optional[str]:
        """Get a random restaurant recommendation that matches a keyword."""
        matching_restaurants = await self.get_restaurants_by_keyword(guild_id, keyword)
        if not matching_restaurants:
            return None

        restaurant = random.choice(matching_restaurants)
        name = restaurant['name']
        cuisine = restaurant.get('cuisine')
        location = restaurant.get('location')

        # Use fallback text for missing information
        cuisine_text = cuisine if cuisine else "idk what cuisine they cook"
        location_text = location if location else "idk where tf it is"

        return f"Go to **{name}** - {cuisine_text} - {location_text}"


    @remove_restaurant.autocomplete("name")
    async def restaurant_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for restaurant names."""
        restaurants = await self.get_restaurants(interaction.guild.id)
        choices = []

        for restaurant in restaurants:
            if current.lower() in restaurant["name"].lower():
                choices.append(app_commands.Choice(name=restaurant["name"], value=restaurant["name"]))
                if len(choices) >= 25:  # Discord limit
                    break

        return choices

    @commands.hybrid_command(name="addrestaurant", aliases=func.get_aliases("addrestaurant"))
    @app_commands.describe(input="Restaurant info: name, cuisine (optional), location (optional)")
    @commands.dynamic_cooldown(func.cooldown_check, commands.BucketType.guild)
    async def add_restaurant_prefix(self, ctx: commands.Context, *, input: str):
        """Add a restaurant using prefix command. Format: name, cuisine, location"""
        parts = [part.strip() for part in input.split(',')]

        if not parts or not parts[0]:
            await func.send(ctx, "Please provide at least a restaurant name. Format: `name, cuisine, location`", ephemeral=True)
            return

        name = parts[0]
        cuisine = parts[1] if len(parts) > 1 and parts[1] else None
        location = parts[2] if len(parts) > 2 and parts[2] else None

        restaurants = await self.get_restaurants(ctx.guild.id)

        # Check if restaurant already exists
        for restaurant in restaurants:
            if restaurant["name"].lower() == name.lower():
                await func.send(ctx, f"**{name}** is already in the restaurant list!", ephemeral=True)
                return

        # Create restaurant entry
        restaurant_entry = {
            "name": name,
            "added_by": ctx.author.id,
            "added_by_name": ctx.author.display_name
        }

        if cuisine:
            restaurant_entry["cuisine"] = cuisine
        if location:
            restaurant_entry["location"] = location

        restaurants.append(restaurant_entry)

        if await self.save_restaurants(ctx.guild.id, restaurants):
            embed = discord.Embed(
                title="Restaurant Added! 🍽️",
                description=f"**{name}** has been added to the restaurant list!",
                color=func.settings.embed_color
            )

            if cuisine:
                embed.add_field(name="Cuisine", value=cuisine, inline=True)
            if location:
                embed.add_field(name="Location", value=location, inline=True)

            embed.set_footer(text=f"Added by {ctx.author.display_name}")
            await func.send(ctx, embed)
        else:
            await func.send(ctx, "Failed to add restaurant. Please try again later.", ephemeral=True)

    @commands.hybrid_command(name="removerestaurant", aliases=func.get_aliases("removerestaurant"))
    @app_commands.describe(name="The name of the restaurant to remove")
    @commands.dynamic_cooldown(func.cooldown_check, commands.BucketType.guild)
    async def remove_restaurant_prefix(self, ctx: commands.Context, *, name: str):
        """Remove a restaurant from the guild's recommendation list."""
        restaurants = await self.get_restaurants(ctx.guild.id)

        # Find and remove the restaurant
        restaurant_to_remove = None
        for i, restaurant in enumerate(restaurants):
            if restaurant["name"].lower() == name.lower():
                restaurant_to_remove = restaurants.pop(i)
                break

        if not restaurant_to_remove:
            await func.send(ctx, f"**{name}** was not found in the restaurant list!", ephemeral=True)
            return

        if await self.save_restaurants(ctx.guild.id, restaurants):
            embed = discord.Embed(
                title="Restaurant Removed! 🗑️",
                description=f"**{restaurant_to_remove['name']}** has been removed from the restaurant list!",
                color=func.settings.embed_color
            )
            await func.send(ctx, embed)
        else:
            await func.send(ctx, "Failed to remove restaurant. Please try again later.", ephemeral=True)

    @commands.hybrid_command(name="listrestaurants", aliases=func.get_aliases("listrestaurants"))
    @commands.dynamic_cooldown(func.cooldown_check, commands.BucketType.guild)
    async def list_restaurants_prefix(self, ctx: commands.Context):
        """Show all restaurants in the recommendation list."""
        restaurants = await self.get_restaurants(ctx.guild.id)

        if not restaurants:
            await func.send(ctx, "No restaurants have been added yet! Use `addrestaurant` to add some.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Restaurant List 🍽️ ({len(restaurants)} restaurants)",
            color=func.settings.embed_color
        )

        # Group restaurants for better display
        restaurant_text = ""
        for i, restaurant in enumerate(restaurants, 1):
            restaurant_info = f"**{i}. {restaurant['name']}**"

            details = []
            if restaurant.get("cuisine"):
                details.append(f"*{restaurant['cuisine']}*")
            if restaurant.get("location"):
                details.append(f"📍 {restaurant['location']}")

            if details:
                restaurant_info += f" - {' | '.join(details)}"

            restaurant_info += f"\n*Added by {restaurant.get('added_by_name', 'Unknown')}*\n\n"

            # Check if adding this would exceed embed limit
            if len(restaurant_text + restaurant_info) > 4000:
                break

            restaurant_text += restaurant_info

        embed.description = restaurant_text
        await func.send(ctx, embed)

    @commands.hybrid_command(name="randomrestaurant", aliases=func.get_aliases("randomrestaurant"))
    @commands.dynamic_cooldown(func.cooldown_check, commands.BucketType.guild)
    async def random_restaurant_prefix(self, ctx: commands.Context):
        """Get a random restaurant recommendation from the guild's list."""
        restaurants = await self.get_restaurants(ctx.guild.id)

        if not restaurants:
            await func.send(ctx, "No restaurants have been added yet! Use `addrestaurant` to add some.", ephemeral=True)
            return

        recommendation_text = await self.get_random_restaurant_for_mention(ctx.guild.id)
        if recommendation_text:
            await func.send(ctx, recommendation_text)
        else:
            await func.send(ctx, "No restaurants have been added yet! Use `addrestaurant` to add some.", ephemeral=True)

    @commands.hybrid_command(name="findrestaurant", aliases=func.get_aliases("findrestaurant"))
    @app_commands.describe(keyword="Keyword to search for (e.g. 'halal', 'vegan')")
    @commands.dynamic_cooldown(func.cooldown_check, commands.BucketType.guild)
    async def find_restaurant_by_keyword(self, ctx: commands.Context, *, keyword: str):
        """Find restaurants with a specific keyword in their cuisine."""
        matching_restaurants = await self.get_restaurants_by_keyword(ctx.guild.id, keyword.strip())

        if not matching_restaurants:
            await func.send(ctx, f"No restaurants found with keyword '{keyword}'.", ephemeral=True)
            return

        if len(matching_restaurants) == 1:
            restaurant = matching_restaurants[0]
            name = restaurant['name']
            cuisine = restaurant.get('cuisine')
            location = restaurant.get('location')

            cuisine_text = cuisine if cuisine else "idk what cuisine they cook"
            location_text = location if location else "idk where tf it is"

            await func.send(ctx, f"Go to **{name}** - {cuisine_text} - {location_text}")
        else:
            # Multiple matches, pick random
            recommendation_text = await self.get_random_restaurant_with_keyword(ctx.guild.id, keyword)
            if recommendation_text:
                await func.send(ctx, recommendation_text)
            else:
                await func.send(ctx, f"No restaurants found with keyword '{keyword}'.", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Restaurant(bot))
