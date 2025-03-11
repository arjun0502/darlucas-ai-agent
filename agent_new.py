import os
import json
import logging
from typing import Dict
import discord

from mistralai import Mistral
from tools.generate import generate_meme
from tools.search import search_meme

logger = logging.getLogger("discord")

MISTRAL_MODEL = "mistral-large-latest"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

### TO DO: Modify system prompt to specify how to choose tools (provide examples) and generate parameters for each function
SYSTEM_PROMPT = """
You are a helpful meme generator.
Given a user's request, use your tools to fulfill the request.
"""

class MemeAgent:
    def __init__(self):
        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.chat_history = []
        self.max_history_len = 10   
        self.user_scores = {}
        self.scores_file = "user_funny_scores.json"
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_meme",
                    "description": "retrieves meme from Humor API based on user input or chat history",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": ""},
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_meme",
                    "description": "generates meme based on user input or chat history",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meme_concept": {"type": "string", "description": ""}
                        }
                    },
                    "required": ["meme_concept"]
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "react",
                    "description": "reacts to latest message",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sentiment": {"type": "string"}
                        }
                    },
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "leaderboard",
                    "description": "generates leaderboard",
                    "parameters": {},
                }
            },
        ]

        self.tools_to_functions = {
            "search_meme": search_meme,
            "generate_meme": generate_meme,
            # "react": react,
            # "leaderboard": leaderboard
        }

    
    def add_to_chat_history(self, message: discord.Message):
         self.chat_history.append({"author": message.author.name, "content": message.content})
         if len(self.chat_history) > self.max_history_len:
            self.chat_history.pop(0)
    
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

    async def run(self, message: discord.Message):
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Request: {message.content}\nOutput:",
            },
        ]

        tool_response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
            tools=self.tools,
            tool_choice="any",
        )

        messages.append(tool_response.choices[0].message)

        tool_call = tool_response.choices[0].message.tool_calls[0]
        function_name = tool_call.function.name
        function_params = json.loads(tool_call.function.arguments)
        function_result = self.tools_to_functions[function_name](**function_params)

        ## TO DO: How to generate meme spontaneously 

        ## TO DO: ONCE WE GET THE EMBED, HOW DO WE RENDER IT? DO WE JUST WHAT WE ARE DOING BELOW??? 
        if isinstance(function_result, tuple):
            file, embed = function_result
            await message.reply(file=file,embed=embed)
        else:
            await message.reply(embed=function_result)