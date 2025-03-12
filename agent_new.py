import os
import json
import logging
from typing import Dict, List, Optional
import discord
import random
from datetime import datetime, timedelta

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("meme_agent.log")
    ]
)

from mistralai import Mistral
from tools.generate import generate_meme
from tools.search import search_meme
from tools.leaderboard import leaderboard, generate_leaderboard_embed, process_command

logger = logging.getLogger("discord")

MISTRAL_MODEL = "mistral-large-latest"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

SYSTEM_PROMPT = """
You are an intelligent meme assistant designed to generate or find memes based on user requests. When a user messages you, analyze their request and determine which tool is most appropriate to use:

1. `search_meme`: Find an existing meme based on keywords
2. `generate_meme`: Create a new meme with a custom image and caption

## Tool Selection Guidelines

- Use `search_meme` when:
  - User is looking for a specific type of meme
  - Request mentions a well-known meme or meme format
  - Examples: "Get the spiderman meme", "Send the capybara meme"

- Use `generate_meme` when:
  - User wants a custom or new meme
  - User asks to "create," "make," or "generate" a meme
  - Request includes specific elements to combine in a novel way
  - Example: "Make a meme about my coding project failing" or "Create a funny meme about AI"

## Parameter Extraction Guidelines

### Context Determination:
- First, determine if the user's request contains specific content/keywords:
  - If the request includes specific topics (e.g., "about capybaras", "about cooking"), extract parameters directly from the request
  - If the request is generic (e.g., "Generate a meme", "Search for a funny meme"), extract parameters from recent conversation history

### For search_meme:
- If request contains specific keywords: Extract those keywords for the query
  - Example: "Find a meme about cats" → query: "cats"
- If request is generic: Review conversation history to determine relevant keywords
  - Example: Previous messages discussing job interviews, then "Show me a meme" → query: "job interview"
- Always focus on the subject matter and emotional tone
- Keep keywords concise and relevant

### For generate_meme:
- If request contains specific topics:
  - Create image description and caption based on those specific topics
  - Example: "Make a meme about slipping on bananas" → image and caption about slipping on bananas
- If request is generic:
  - Review conversation history to determine relevant topics and themes
  - Create image description and caption that reference those themes
  - Example: Previous messages discussing coding bugs, then "Make a funny meme" → image and caption about debugging
- Ensure the image and caption work together
- Keep captions brief, avoid contractions, and ensure they read naturally

{chat_history_context}
"""

class MemeAgent:
    def __init__(self):
        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.chat_history = []
        self.max_history_len = 10   
        self.user_scores = {}
        self.scores_file = "user_funny_scores.json"
        
        # Load existing user scores if the file exists
        self.load_user_scores()
        
        self.tools = [
            # {
            #     "type": "function",
            #     "function": {
            #         "name": "search_meme",
            #         "description": "retrieves meme from Humor API either based on user input or chat history",
            #         "parameters": {
            #             "type": "object",
            #             "properties": {
            #                 "query": 
            #                 {"type": "string", 
            #                  "description": "the search query/keywords from the user for Humor API"
            #                 }
            #             },
            #             "required": ["query"]
            #         }
            #     }
            # },
            {
                "type": "function",
                "function": {
                    "name": "generate_meme",
                    "description": "generates meme based on user input or chat history",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "image_description": 
                            {"type": "string", 
                             "description": "description of image to generate"
                             },
                            "caption": 
                            {"type": "string", 
                             "description": "caption to go along with meme"}
                        },
                        "required": ["image_description", "caption"]
                    }
                }
            },
            # {
            #     "type": "function",
            #     "function": {
            #         "name": "react",
            #         "description": "reacts to latest message with an appropriate emoji",
            #         "parameters": {
            #             "type": "object",
            #             "properties": {
            #                 "sentiment": {
            #                     "type": "string",
            #                     "enum": ["positive", "negative", "neutral"],
            #                     "description": "The sentiment of the reaction"
            #                 }
            #             },
            #             "required": ["sentiment"]
            #         }
            #     }
            # },
            {
                "type": "function",
                "function": {
                    "name": "leaderboard",
                    "description": "displays leaderboard of top memes or user stats",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string", 
                                "enum": ["leaderboard", "mystats"],
                                "description": "The leaderboard command to execute"
                            }
                        },
                        "required": ["command"]
                    }
                }
            },
        ]

        self.tools_to_functions = {
            #"search_meme": search_meme,
            "generate_meme": generate_meme,
            #"react": self.react_message,
            "leaderboard": self.show_leaderboard
        }
    
    def load_user_scores(self):
        """Load user scores from the JSON file if it exists"""
        try:
            if os.path.exists(self.scores_file):
                with open(self.scores_file, 'r') as f:
                    self.user_scores = json.load(f)
                logger.info(f"Loaded scores for {len(self.user_scores)} users")
        except Exception as e:
            logger.error(f"Error loading user scores: {e}")
            self.user_scores = {}
    
    def add_to_chat_history(self, message: discord.Message):
        """Add a message to the chat history"""
        self.chat_history.append({
            "author": message.author.name, 
            "content": message.content, 
            "timestamp": datetime.now().isoformat()
        })
        if len(self.chat_history) > self.max_history_len:
            self.chat_history.pop(0)
    
    def format_chat_history(self) -> str:
        """Format the chat history for inclusion in the system prompt"""
        if not self.chat_history:
            return "## Recent Chat History\nNo recent chat history available."
        
        formatted_history = "## Recent Chat History\n"
        for idx, msg in enumerate(self.chat_history):
            formatted_history += f"{idx+1}. {msg['author']}: {msg['content']}\n"
        
        return formatted_history
    
    def save_user_scores(self):
        """Save user scores to the JSON file"""
        try:
            with open(self.scores_file, 'w') as f:
                json.dump(self.user_scores, f)
        except Exception as e:
            logger.error(f"Error saving user scores: {e}")
    
    def add_score_to_user(self, username: str, points: int = 1):
        """Add points to a user's score"""
        if username not in self.user_scores:
            self.user_scores[username] = 0
        self.user_scores[username] += points
        self.save_user_scores()
        logger.info(f"Added {points} point(s) to {username}. New score: {self.user_scores[username]}")

    async def react_message(self, sentiment: str):
        """React to a message with an appropriate emoji"""
        emoji_map = {
            "positive": ["😂", "🤣", "👍", "❤️", "🔥", "👏", "😁"],
            "negative": ["😢", "👎", "😒", "😔", "🤔", "🙄"],
            "neutral": ["😐", "🤷", "👀", "👋", "🙂"]
        }
    
        # Choose a random emoji from the appropriate category
        emoji = random.choice(emoji_map.get(sentiment, emoji_map["neutral"]))
        
        embed = discord.Embed(description=emoji, color=discord.Color.blue())
        return embed

    async def show_leaderboard(self, command: str):
        """Show the leaderboard or user stats"""
        if command == "leaderboard":
            embed = await generate_leaderboard_embed()
            return embed
        elif command == "mystats":
            # This will be handled in the main function with the user ID available
            return discord.Embed(
                title="User Stats",
                description="Use !mystats in chat for your personal stats",
                color=discord.Color.blue()
            )

    async def handle_reaction(self, reaction: discord.Reaction, user: discord.User):
        """Handle a reaction added to a message"""
        if user.bot:
            return  # Ignore bot reactions

        # Check if the reaction is a thumb up or down
        emoji_name = reaction.emoji if isinstance(reaction.emoji, str) else reaction.emoji.name

        is_upvote = emoji_name == "👍"
        is_downvote = emoji_name == "👎"

        if not (is_upvote or is_downvote):
            return  # Not a vote reaction

        message_id = str(reaction.message.id)
        user_id = str(user.id)

        # Update the leaderboard with the vote
        if is_upvote or is_downvote:
            leaderboard.update_vote(message_id, user_id, is_upvote)

        logger.info(f"Handled reaction {emoji_name} by {user.name} on message {message_id}")

    async def handle_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        """Handle a reaction removed from a message"""
        if user.bot:
            return  # Ignore bot reactions

        # Check if the reaction is a thumb up or down
        emoji_name = reaction.emoji if isinstance(reaction.emoji, str) else reaction.emoji.name

        is_vote = emoji_name in ["👍", "👎"]

        if not is_vote:
            return  # Not a vote reaction

        message_id = str(reaction.message.id)
        user_id = str(user.id)

        # Remove the vote from the leaderboard
        leaderboard.remove_vote(message_id, user_id)

        logger.info(f"Handled reaction removal {emoji_name} by {user.name} on message {message_id}")

    async def register_meme(self, message: discord.Message, response_message: discord.Message):
        """Register a meme in the leaderboard database"""
        # Extract embed data if it exists
        if response_message.embeds:
            embed_data = {
                'title': response_message.embeds[0].title,
                'description': response_message.embeds[0].description,
                'color': response_message.embeds[0].color.value if response_message.embeds[0].color else None,
                'fields': [
                    {
                        'name': field.name,
                        'value': field.value,
                        'inline': field.inline
                    }
                    for field in response_message.embeds[0].fields
                ]
            }
            
            # Image URL is stored in the embed
            if response_message.embeds[0].image:
                embed_data['image_url'] = response_message.embeds[0].image.url
            
            # Add the meme to the leaderboard
            leaderboard.add_meme(
                message_id=str(response_message.id),
                author_id=str(message.author.id),
                author_name=message.author.name,
                embed_data=embed_data
            )
            
            logger.info(f"Registered meme with ID {response_message.id} by {message.author.name}")

    async def run(self, message: discord.Message):
        # Add the current message to chat history
        self.add_to_chat_history(message)
        
        # Format chat history for inclusion in system prompt
        chat_history_context = self.format_chat_history()
        
        # Apply chat history to system prompt
        system_prompt = SYSTEM_PROMPT.format(chat_history_context=chat_history_context)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Request: {message.content}\nOutput:",
            },
        ]

        try:
            logger.info(f"Processing message from {message.author.name}: '{message.content}'")
            logger.info(f"Using chat history context with {len(self.chat_history)} messages")
            
            # Send request to Mistral API
            logger.info(f"Sending request to Mistral API")
            tool_response = await self.client.chat.complete_async(
                model=MISTRAL_MODEL,
                messages=messages,
                tools=self.tools,
                tool_choice="any",
            )

            messages.append(tool_response.choices[0].message)
            
            # Check if tool_calls exists and is not empty
            if not tool_response.choices[0].message.tool_calls:
                logger.error("No tool calls in response")
                await message.reply("Sorry, I couldn't process that request. Please try again.")
                return

            tool_call = tool_response.choices[0].message.tool_calls[0]
            function_name = tool_call.function.name
            function_params = json.loads(tool_call.function.arguments)
            
            # Log the selected tool and parameters
            logger.info(f"Tool selected: {function_name}")
            logger.info(f"Tool parameters: {json.dumps(function_params, indent=2)}")
            
            if function_name not in self.tools_to_functions:
                logger.error(f"Unknown function: {function_name}")
                await message.reply(f"Sorry, I don't know how to {function_name}. Please try again.")
                return
            
            # Send loading message based on function name
            loading_text = (
            "Searching for a meme..." if function_name == "search_meme" else
            "Generating a meme..." if function_name == "generate_meme" else
            "Loading leaderboard..." if function_name == "leaderboard" else
            "Thinking..."
            )
            loading_message = await message.reply(loading_text)
            
            logger.info(f"Executing {function_name} with provided parameters")
            # Handle leaderboard command specially
            if function_name == "leaderboard" and function_params.get("command") == "mystats":
                # Add user_id parameter
                function_result = await process_command("mystats", str(message.author.id))
            else:
                function_result = await self.tools_to_functions[function_name](**function_params)

            if isinstance(function_result, tuple):
                embed, file = function_result
                logger.info(f"Sending response with file and embed to {message.author.name}")
                await loading_message.delete()  # Delete the loading message
                response_message = await message.reply(file=file, embed=embed)
            else:
                logger.info(f"Sending embed response to {message.author.name}")
                await loading_message.delete()  # Delete the loading message
                response_message = await message.reply(embed=function_result)

            # Then, register the meme and add reactions AFTER the message is created
            if function_name in ["search_meme", "generate_meme"]:
                await self.register_meme(message, response_message)
                # Add default reactions to make voting easier
                await response_message.add_reaction("👍")
                await response_message.add_reaction("👎")
            
            logger.info(f"Successfully processed request from {message.author.name}")
                
        except Exception as e:
            logger.error(f"Error in MemeAgent.run: {e}", exc_info=True)
            # If there was a loading message try to delete it
            try:
                if 'loading_message' in locals():
                    await loading_message.delete()
            except:
                pass
            await message.reply(f"Sorry, something went wrong: {str(e)}")