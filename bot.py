import os
import discord
import logging
import aiohttp
import io
from PIL import Image, ImageDraw, ImageFont
import textwrap
import json

from discord.ext import commands
from discord.ui import Button, View
from dotenv import load_dotenv
from agent_mistral import MistralAgent
from agent_openai import OpenAIAgent

from meme_leaderboard import MemeLeaderboard


PREFIX = "!"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("discord_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("discord_bot")

# Load the environment variables
load_dotenv()

# Create the bot with all intents
# The message content and members intent must be enabled in the Discord Developer Portal for the bot to work.
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Import the Mistral and OpenAI agent from the agent.py file
agent_mistral = MistralAgent()
agent_openai = OpenAIAgent()
meme_leaderboard = MemeLeaderboard()

# Get the token from the environment variables
token = os.getenv("DISCORD_TOKEN")


# Paginated leaderboard view
class MemeLeaderboardView(View):
    def __init__(self, ctx, memes, timeout=120):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.memes = memes
        self.current_page = 0
        self.total_pages = len(memes)
        self.message = None
        
        # Add buttons
        self.update_buttons()

    async def start(self):
        """Start the paginated view"""
        if not self.memes:
            return await self.ctx.send("No memes found!")
                
        embed = self.get_current_embed()
        self.message = await self.ctx.send(embed=embed, view=self)
        return self.message
    
    def update_buttons(self):
        """Update the buttons based on current page"""
        # Clear existing buttons
        self.clear_items()
        
        # Previous button
        prev_button = Button(
            style=discord.ButtonStyle.secondary,
            emoji="⬅️",
            custom_id="prev",
            disabled=(self.current_page == 0)
        )
        prev_button.callback = self.prev_callback
        self.add_item(prev_button)
        
        # Page indicator
        page_indicator = Button(
            style=discord.ButtonStyle.secondary,
            label=f"{self.current_page + 1}/{self.total_pages}",
            custom_id="page_indicator",
            disabled=True
        )
        self.add_item(page_indicator)
        
        # Next button
        next_button = Button(
            style=discord.ButtonStyle.secondary,
            emoji="➡️",
            custom_id="next",
            disabled=(self.current_page >= self.total_pages - 1)
        )
        next_button.callback = self.next_callback
        self.add_item(next_button)
    
    async def prev_callback(self, interaction):
        """Handle previous button click"""
        self.current_page = max(0, self.current_page - 1)
        
        # Update buttons and embed
        self.update_buttons()
        embed = self.get_current_embed()
        
        # Respond to the interaction
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def next_callback(self, interaction):
        """Handle next button click"""
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        
        # Update buttons and embed
        self.update_buttons()
        embed = self.get_current_embed()
        
        # Respond to the interaction
        await interaction.response.edit_message(embed=embed, view=self)
    
    def get_current_embed(self):
        """Create an embed for the current meme"""
        if not self.memes or self.current_page >= len(self.memes):
            # Return a default embed if something goes wrong
            return discord.Embed(
                title="No memes found",
                description="No memes to display",
                color=discord.Color.red()
            )
        
        meme = self.memes[self.current_page]
        
        # Calculate rank (using the original position in the list)
        rank = self.current_page + 1
        
        # Calculate net votes
        net_votes = meme["upvotes"] - meme["downvotes"]
        
        # Determine rank emoji
        if rank == 1:
            rank_emoji = "🥇"
        elif rank == 2:
            rank_emoji = "🥈"
        elif rank == 3:
            rank_emoji = "🥉"
        else:
            rank_emoji = f"{rank}."
        
        # Create link to original message
        meme_link = f"https://discord.com/channels/{self.ctx.guild.id}/{self.ctx.channel.id}/{meme['message_id']}"
        
        # Create embed with the title "Certified Funny™ Leaderboard"
        embed = discord.Embed(
            title=f"🏆 Certified Funny™ Leaderboard 🏆",
            description=f"{rank_emoji} Meme by {meme['author_name']}\n\n**Votes:** 👍 {meme['upvotes']} | 👎 {meme['downvotes']} | Net: {net_votes}\n\n[Jump to Original]({meme_link})",
            color=discord.Color.gold()
        )
        
        # Add the meme image
        if meme["embed_data"]["image_url"]:
            embed.set_image(url=meme["embed_data"]["image_url"])
        
        # Add the original meme title if available
        if meme["embed_data"]["title"]:
            embed.add_field(
                name="Original Title",
                value=meme["embed_data"]["title"],
                inline=False
            )
        
        # Add any fields from the original embed
        if meme["embed_data"].get("fields"):
            for field in meme["embed_data"]["fields"]:
                embed.add_field(
                    name=field["name"],
                    value=field["value"],
                    inline=field["inline"]
                )
        
        # Add pagination info to footer
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} • Use the buttons to navigate")
        
        return embed



# Helper function to add text to images
async def add_text_to_image(image_url, text):
    """
    Downloads an image from URL and adds text below the image with black text and reduced margins
    Returns a file-like object of the modified image
    """
    # Download the image
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            if response.status != 200:
                raise Exception(f"Failed to download image: {response.status}")
            image_data = await response.read()
    
    # Open the image with PIL
    original_image = Image.open(io.BytesIO(image_data))
    
    # Get original image dimensions
    original_width, original_height = original_image.size

    text = text.upper()
    
    # Try to load a good font
    try:
        # Adjust path to where you store the font
        font_path = os.path.join(os.path.dirname(__file__), "Impact.ttf")
        if os.path.exists(font_path):
            font = ImageFont.truetype(font_path, size=int(original_height/14))
        else:
            # Fallback to default font
            font = ImageFont.load_default()
    except:
        # Fallback to default font
        font = ImageFont.load_default()
    
    # Text wrapping
    max_width = int(original_width * 0.95)  # 95% of image width to reduce margins
    chars_per_line = 40  # Allow more characters per line
    
    try:
        # For newer Pillow versions
        avg_char_width = font.getbbox("A")[2]
        chars_per_line = max(1, int(max_width / avg_char_width))
    except:
        # Fallback for older Pillow versions or errors
        pass
    
    wrapped_text = textwrap.fill(text, width=chars_per_line)
    
    # Calculate text height
    try:
        # For newer Pillow versions
        text_bbox = ImageDraw.Draw(Image.new('RGB', (1, 1))).multiline_textbbox((0, 0), wrapped_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
    except:
        # Fallback for older Pillow versions
        text_width, text_height = ImageDraw.Draw(Image.new('RGB', (1, 1))).multiline_textsize(wrapped_text, font=font)
    
    # Calculate padding and new image dimensions - use smaller padding
    padding = int(original_height * 0.02)  # Reduced to 2% of image height as padding
    new_height = original_height + text_height + (padding * 2)  # Original + text height + padding above and below
    
    # Create a new larger canvas with extra space below
    new_image = Image.new('RGB', (original_width, new_height), (255, 255, 255))  # White background
    
    # Paste the original image at the top
    new_image.paste(original_image, (0, 0))
    
    # Create a draw object for the new image
    draw = ImageDraw.Draw(new_image)
    
    # Calculate position to center text in the new space below the image
    position = ((original_width - text_width) / 2, original_height + padding)
    
    # Draw text in black directly (no outline)
    try:
        # For newer Pillow versions
        draw.multiline_text(
            position,
            wrapped_text,
            font=font,
            fill=(0, 0, 0),  # Black text
            align="center"
        )
    except:
        # Fallback for older Pillow versions
        draw.multiline_text(
            position,
            wrapped_text,
            font=font,
            fill=(0, 0, 0),  # Black text
            align="center"
        )
    
    # Convert to bytes
    output = io.BytesIO()
    new_image.save(output, format="PNG")
    output.seek(0)
    
    return output

@bot.event
async def on_ready():
    """
    Called when the client is done preparing the data received from Discord.
    Prints message on terminal when bot successfully connects to discord.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_ready
    """
    logger.info(f"{bot.user} has connected to Discord!")


@bot.event
async def on_message(message: discord.Message):
    """
    Called when a message is sent in any channel the bot can see.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message
    """
    # Don't delete this line! It's necessary for the bot to process commands.
    await bot.process_commands(message)

    # Ignore messages from self or other bots to prevent infinite loops.
    if message.author.bot or message.content.startswith("!"):
        return
    
    # Add message to chat history
    agent_mistral.add_to_chat_history(message)
    logger.info(f"Added message from {message.author} to history: {message.content}")

    try:
        spontaneous_meme_decision, spontaneous_meme_reason = await agent_mistral.decide_spontaneous_meme()
        logger.info(f"Spontaneous meme decision: {spontaneous_meme_decision}, reason: {spontaneous_meme_reason}")

        if spontaneous_meme_decision:
            #Update leaderboard if message is funny
            agent_mistral.add_score_to_user(message.author.name)
            logger.info(f"Added humor point to {message.author.name} for meme-worthy message")
            await generate_spontaneous_meme(message)
    except Exception as e:
        logger.error(f"Error deciding spontaneous meme: {e}")

        
# Commands
# New command for generating memes based on chat history
@bot.command(name="generate", help="Generate a meme. Use !generate for chat history or !generate [your idea] for custom meme.")
async def generate_meme(ctx, *, user_input=None):
    """
    Generate a meme based on either:
    1. User provided input if specified
    2. Chat history in the current channel if no input is provided
    
    Args:
        ctx: The Discord context
        user_input: Optional - specific input for the meme
    """
    # Let the user know we're working on it
    if user_input:
        processing_msg = await ctx.send(f"Generating a meme based on your input: '{user_input}'...")
    else:
        processing_msg = await ctx.send("Generating a meme based on your conversation....")
    
    try:
        # Call Mistral agent to generate meme concept (text)
        if user_input:
            is_query_appropriate, reason = await agent_mistral.is_query_appropriate(user_input)
            if not is_query_appropriate:
                # First, delete the loading message
                await processing_msg.delete()

                # Then send a new message with the file and embed
                file = discord.File("fallback_error.png", filename="fallback_error.png")
                embed = discord.Embed(title="NUH UH", description=f"You sly dog, I can't generate a meme based on that", color=discord.Color.red())
                embed.set_footer(text=f"{reason}")
                embed.set_image(url="attachment://fallback_error.png")
                await ctx.send(file=file, embed=embed)
                return
            
            meme_concept = await agent_mistral.generate_meme_concept_from_input(user_input)
        else:
            meme_concept = await agent_mistral.generate_meme_concept_from_chat_history()
        
        # Call OpenAI agent (Dall-E) to generate meme image without text
        result = await agent_openai.generate_meme_from_concept(meme_concept)
        
        # Check if image generation failed due to content policy
        if result is None or not isinstance(result, dict):
            logger.warning(f"Content policy violation during meme generation: {result}")
            
            # Generate a humorous response
            humor_response = await agent_mistral.handle_content_policy_violation()
            await processing_msg.edit(content=humor_response)
            return
            
        # Extract image URL and text from result
        image_url = result["image_url"]
        meme_text = result["text"]
        
        # Check if we got a valid image URL
        if not image_url:
            await processing_msg.edit(content=f"Couldn't generate a meme. Please try again.")
            logger.error(f"No image URL returned for meme concept: {meme_concept}")
            return
        
        try:
            # Add text to the image using Pillow
            image_with_text = await add_text_to_image(image_url, meme_text)
            
            # Send the modified image as a file
            file = discord.File(fp=image_with_text, filename="meme.png")
            
            # Create an embed with the attached file - REMOVED TITLE
            embed = discord.Embed(color=discord.Color.blue())
            embed.set_image(url="attachment://meme.png")
            
            # Add info about whether this was from user input or chat history
            if user_input:
                embed.set_footer(text=f"Based on input from {ctx.author.display_name}")
            else:
                embed.set_footer(text=f"Based on chat history • Requested by {ctx.author.display_name}")
            
            # Send the meme
            meme_message = await ctx.send(file=file, embed=embed)

            # Extract the permanent CDN URL from the sent message's embed
            if meme_message.embeds and meme_message.embeds[0].image:
                permanent_url = meme_message.embeds[0].image.url
                logger.info(f"Permanent CDN URL: {permanent_url}")
                
                # Create a new embed with the permanent URL
                tracking_embed = discord.Embed(title=embed.title, description=embed.description, color=embed.color)
                tracking_embed.set_image(url=permanent_url)
                
                # Copy over footer and fields
                if embed.footer:
                    tracking_embed.set_footer(text=embed.footer.text, icon_url=embed.footer.icon_url)
                
                for field in embed.fields:
                    tracking_embed.add_field(name=field.name, value=field.value, inline=field.inline)
                
                # Track this embed with permanent URL
                meme_leaderboard.track_meme(meme_message, tracking_embed, ctx.author)
            else:
                # Fallback if no image found
                meme_leaderboard.track_meme(meme_message, embed, ctx.author)
                logger.warning(f"No image found in message {meme_message.id}, using original embed")

            # Set up the voting reactions
            await meme_leaderboard.setup_reactions(meme_message)
            
        except Exception as e:
            logger.error(f"Error adding text to image: {e}")
            
            # Fallback to sending the image without text overlay
            embed = discord.Embed(color=discord.Color.blue())
            embed.set_image(url=image_url)
            
            if user_input:
                embed.set_footer(text=f"Based on input from {ctx.author.display_name}")
            else:
                embed.set_footer(text=f"Based on chat history • Requested by {ctx.author.display_name}")
                
            # Add the caption as a field since we couldn't overlay it
            embed.add_field(name="Caption", value=meme_text, inline=False)
                    
            await ctx.send(embed=embed)
            
        # Delete the processing message
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Error generating meme: {e}")
        error_message = f"Sorry, I encountered an error while generating the meme. Let's try again later!"
        
        # For debugging, include error details
        if os.getenv("DEBUG", "False").lower() == "true":
            error_message += f"\n\nError details: {str(e)}"
            
        await processing_msg.edit(content=error_message)
        

# Function for spontaneous meme generation (called from on_message)
async def generate_spontaneous_meme(message):
    """
    Generate a spontaneous meme based on the chat history in the current channel.
    Similar to the command version but works with a message object instead of ctx.
    """
    # Let the user know we're working on it
    processing_msg = await message.channel.send("I've decided this conversation deserves a meme.......")
    
    try:
        # Call Mistral agent to generate meme concept (text)
        meme_concept = await agent_mistral.generate_meme_concept_from_chat_history()
        
        # Call OpenAI agent (Dall-E) to generate meme image without text
        result = await agent_openai.generate_meme_from_concept(meme_concept)
        
        # Check if image generation failed due to content policy
        if result is None or not isinstance(result, dict):
            logger.warning(f"Content policy violation during spontaneous meme generation: {result}")
            
            # Generate a humorous response
            humor_response = await agent_mistral.handle_content_policy_violation()
            await processing_msg.edit(content=humor_response)
            return
            
        # Extract image URL and text from result
        image_url = result["image_url"]
        meme_text = result["text"]
        
        # Check if we got a valid image URL
        if not image_url:
            await processing_msg.edit(content=f"I changed my mind about that meme. The timing wasn't right.")
            logger.error(f"No image URL returned for spontaneous meme concept: {meme_concept}")
            return
        
        try:
            # Add text to the image using Pillow
            image_with_text = await add_text_to_image(image_url, meme_text)
            
            # Send the modified image as a file
            file = discord.File(fp=image_with_text, filename="meme.png")
            
            # Create an embed with the attached file - REMOVED TITLE
            embed = discord.Embed(color=discord.Color.green())
            embed.set_image(url="attachment://meme.png")
            embed.set_footer(text=f"Generated spontaneously based on your conversation")
            
            # Send the meme
            meme_message = await ctx.send(file=file, embed=embed)

            # Extract the permanent CDN URL from the sent message's embed
            if meme_message.embeds and meme_message.embeds[0].image:
                permanent_url = meme_message.embeds[0].image.url
                logger.info(f"Permanent CDN URL: {permanent_url}")
                
                # Create a new embed with the permanent URL
                tracking_embed = discord.Embed(title=embed.title, description=embed.description, color=embed.color)
                tracking_embed.set_image(url=permanent_url)
                
                # Copy over footer and fields
                if embed.footer:
                    tracking_embed.set_footer(text=embed.footer.text, icon_url=embed.footer.icon_url)
                
                for field in embed.fields:
                    tracking_embed.add_field(name=field.name, value=field.value, inline=field.inline)
                
                # Track this embed with permanent URL
                meme_leaderboard.track_meme(meme_message, tracking_embed, message.author)
            else:
                # Fallback if no image found
                meme_leaderboard.track_meme(meme_message, embed, message.author)
                logger.warning(f"No image found in message {meme_message.id}, using original embed")

            # Set up the voting reactions
            await meme_leaderboard.setup_reactions(meme_message)
            
        except Exception as e:
            logger.error(f"Error adding text to image: {e}")
            
            # Fallback to sending the image without text overlay
            embed = discord.Embed(color=discord.Color.green())
            embed.set_image(url=image_url)
            embed.set_footer(text=f"Generated spontaneously based on your conversation")
            
            # Let the user know we had to fall back
            embed.add_field(name="Note", value="Couldn't add text directly to image. Caption shown separately.", inline=False)
            
            await message.channel.send(embed=embed)
            
        # Delete the processing message
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Error generating spontaneous meme: {e}")
        await processing_msg.edit(content=f"I was going to make a meme, but I got distracted. Maybe next time!")

# New command to have the bot react to the memes        
@bot.command(name="react", help="React to the latest message in the chat. Use optional sentiment type (happy, sad, angry, etc.)")
async def react_to_message(ctx, *args):
    """
    React to the latest message in the current channel.
    Optional argument for sentiment (e.g., happy, sad, angry, surprised).
    Usage: !react [sentiment]
    """
    sentiment = None
    if args:
        sentiment = " ".join(args)  # Join all sentiment descriptors, discord bot ignores command by default
    
    # Let the user know we're working on it
    processing_msg = await ctx.send("Generating a reaction to the latest message... 🤔")
    
    try:
        reaction = await agent_mistral.react_to_latest(sentiment)
        
        # Display the reaction - REMOVED TITLE
        embed = discord.Embed(color=discord.Color.green())
        embed.description = reaction
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        
        # Send the reaction
        await ctx.send(embed=embed)
        
        # Delete the processing message
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Error generating reaction: {e}")
        await processing_msg.edit(content=f"Sorry, I encountered an error while generating the reaction: {str(e)}")

# New command to search for a relevant meme
@bot.command(name="search", help="Search for a relevant meme.")
async def search_meme(ctx, *, query=None):
    """
    Search for a relevant meme based on a query.
    If no query is provided, the bot will search for a meme based on chat history context.
    """
    # Let the user know we're working on it
    if query:
        processing_msg = await ctx.send(f"Searching for a meme based on your input: '{query}'...")
    else:
        processing_msg = await ctx.send("Searching for a meme based on your conversation....")
        query = await agent_mistral.generate_keywords_from_chat_history()

    try:
        # Call the Mistral agent to search for memes
        result = await agent_mistral.search_memes(query)
        
        if not result["success"]:
            # Check if this is a content policy violation
            if "sorry" in result["error"].lower():
                # This is likely a rejected inappropriate query
                await processing_msg.edit(content=f"🚫 {result['error']}")
                
                # Log the rejected query
                logger.warning(f"Rejected meme search query from {ctx.author.name}: '{query}'")
                
                # React to the message with a warning emoji
                try:
                    await ctx.message.add_reaction("⚠️")
                except:
                    pass
            else:
                # This is some other error
                await processing_msg.edit(content=f"😕 {result['error']}")
            return
            
        # Get the single meme from the result
        meme = result["meme"]
        
        # Create an embed to display the meme - SIMPLIFIED VERSION
        embed = discord.Embed(
            title=f"Found Meme for '{query}'", 
            color=discord.Color.purple()
        )
        
        # Add the meme as the main image
        embed.set_image(url=meme["url"])
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        
        # Send the meme
        meme_message = await ctx.send(file=file, embed=embed)

        # Track the meme in the leaderboard
        meme_leaderboard.track_meme(meme_message, embed, ctx.author)

        # Set up the voting reactions
        await meme_leaderboard.setup_reactions(meme_message)
        
        # Delete the processing message
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Error searching for memes: {e}")
        await processing_msg.edit(content=f"Sorry, I encountered an error while searching for memes: {str(e)}")

@bot.command(name="leaderboard", help="Show the meme leaderboard. Use 'mystats' to see your stats, or 'reset' to reset all data (admin only).")
async def show_leaderboard(ctx, action=None):
    """
    Shows the meme leaderboard or user stats
    """
    # Handle reset command (admin only)
    if action and action.lower() == "reset":
        if ctx.message.author.guild_permissions.administrator:
            result = meme_leaderboard.reset_all_data()
            await ctx.send(f"🧹 {result}")
        else:
            await ctx.send("⚠️ Only administrators can reset the leaderboard.")
        return
    
    # Handle mystats command
    if action and action.lower() == "mystats":
        user_stats = meme_leaderboard.get_user_stats(ctx.author.id)
        
        # Create user stats embed
        embed = discord.Embed(
            title=f"Meme Stats for {ctx.author.display_name}",
            color=discord.Color.purple()
        )
        
        embed.add_field(name="📊 Memes Created", value=str(user_stats["memes_created"]), inline=True)
        embed.add_field(name="👍 Total Upvotes", value=str(user_stats["total_upvotes"]), inline=True)
        embed.add_field(name="👎 Total Downvotes", value=str(user_stats["total_downvotes"]), inline=True)
        embed.add_field(name="💯 Net Popularity", value=str(user_stats["net_popularity"]), inline=True)
        
        # Add most popular meme if available
        if user_stats["most_popular_meme"]:
            popular_meme = user_stats["most_popular_meme"]
            
            # Display the meme image directly in the embed
            if popular_meme["embed_data"]["image_url"]:
                embed.set_image(url=popular_meme["embed_data"]["image_url"])
                logger.info(f"Setting mystats image URL: {popular_meme['embed_data']['image_url']}")
            
            # Add a link to the original message
            meme_link = f"https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id}/{popular_meme['message_id']}"
            embed.add_field(
                name="🏆 Most Popular Meme", 
                value=f"👍 {popular_meme['upvotes']} | 👎 {popular_meme['downvotes']} | [View Original]({meme_link})",
                inline=False
            )
        
        embed.set_footer(text=f"Use {PREFIX}leaderboard to see the overall rankings")
        
        await ctx.send(embed=embed)
        return
    
    # Default: show paginated top memes
    top_memes = meme_leaderboard.get_top_memes(20)  # Get more memes for pagination
    
    if not top_memes:
        await ctx.send("No memes have been created yet! Use `!generate` to create one.")
        return
    
    # Add debug logging to inspect the memes data
    logger.info(f"Showing leaderboard with {len(top_memes)} memes")
    for i, meme in enumerate(top_memes[:3]):  # Log details of first 3 memes
        logger.info(f"Meme {i+1} - ID: {meme['message_id']}, Image URL: {meme['embed_data'].get('image_url', 'None')}")
    
    # Create and start the paginated view
    view = MemeLeaderboardView(ctx, top_memes)
    await view.start()

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    await meme_leaderboard.process_reaction(reaction, user, True)

@bot.event
async def on_reaction_remove(reaction, user):
    if user.bot:
        return
    await meme_leaderboard.process_reaction(reaction, user, False)









































# Add this debug command to your bot.py file to check the structure of stored memes
# This will help diagnose why images aren't showing up

@bot.command(name="debugmeme", help="Debug command to show meme data structure (admin only)")
async def debug_meme(ctx):
    """Admin command to display the data structure of stored memes for debugging"""
    # Get some memes to inspect
    top_memes = meme_leaderboard.get_top_memes(3)  # Just get a few
    
    if not top_memes:
        await ctx.send("No memes found in the database.")
        return
    
    # Create an embed with the diagnostic info
    embed = discord.Embed(
        title="Meme Data Structure Debug Info",
        description="Showing data for up to 3 memes",
        color=discord.Color.blue()
    )
    
    for i, meme in enumerate(top_memes):
        # Basic meme info
        meme_info = (
            f"ID: {meme['message_id']}\n"
            f"Author: {meme['author_name']}\n"
            f"Votes: 👍 {meme['upvotes']} | 👎 {meme['downvotes']}\n"
        )
        
        # Embed data diagnostics
        embed_data = meme.get('embed_data', {})
        image_url = embed_data.get('image_url', 'None')
        
        embed_info = (
            f"Title: {embed_data.get('title', 'None')}\n"
            f"Image URL: {image_url}\n"
            f"Fields count: {len(embed_data.get('fields', []))}"
        )
        
        embed.add_field(
            name=f"Meme #{i+1} Basic Info",
            value=meme_info,
            inline=False
        )
        
        embed.add_field(
            name=f"Meme #{i+1} Embed Data",
            value=embed_info,
            inline=False
        )
        
        # Try to display the image
        if i == 0 and image_url and image_url != 'None':
            embed.set_image(url=image_url)
    
    # Send the debug info
    await ctx.send(embed=embed)

# Add this to inspect the raw data file
@bot.command(name="inspectdata", help="Inspect the raw meme data file (admin only)")
async def inspect_data(ctx):
    """Admin command to display the raw meme data file contents"""
    
    # Check if the file exists
    if not os.path.exists(meme_leaderboard.memes_file):
        await ctx.send(f"No meme data file found at {meme_leaderboard.memes_file}")
        return
    
    # Read the raw file
    try:
        with open(meme_leaderboard.memes_file, 'r') as f:
            data = json.load(f)
        
        # Get the size and meme count
        file_size = os.path.getsize(meme_leaderboard.memes_file) / 1024  # KB
        meme_count = len(data.get("memes", {}))
        last_updated = data.get("last_updated", "Unknown")
        
        # Create an info message
        info = (
            f"**Meme Data File Info**\n"
            f"File: `{meme_leaderboard.memes_file}`\n"
            f"Size: {file_size:.2f} KB\n"
            f"Meme Count: {meme_count}\n"
            f"Last Updated: {last_updated}\n\n"
        )
        
        # Sample of meme IDs
        meme_ids = list(data.get("memes", {}).keys())[:5]  # First 5 meme IDs
        id_list = "\n".join(meme_ids) if meme_ids else "None"
        
        info += f"**Sample Meme IDs:**\n{id_list}"
        
        await ctx.send(info)
        
        # If there are memes, send the first meme's full data as a code block
        if meme_ids:
            first_meme_data = json.dumps(data["memes"][meme_ids[0]], indent=2)
            if len(first_meme_data) > 1900:  # Discord message limit
                first_meme_data = first_meme_data[:1900] + "..."
            
            await ctx.send(f"**First meme data structure:**\n```json\n{first_meme_data}\n```")
    
    except Exception as e:
        await ctx.send(f"Error reading meme data file: {str(e)}")











# Start the bot, connecting it to the gateway
bot.run(token)