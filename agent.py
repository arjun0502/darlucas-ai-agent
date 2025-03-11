import os
from mistralai import Mistral
import discord
from openai import OpenAI
from collections import defaultdict
from typing import List, Dict
import logging
import aiohttp
import urllib.parse
import random
import json

# Setup logging
logger = logging.getLogger(__name__)

class MistralAgent:
    def __init__(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.chat_history = []
        self.max_chat_length = 5
        self.model =  "mistral-large-latest"
        self.humor_api_key = os.getenv("HUMOR_API_KEY")
        self.scores_file = "user_funny_scores.json"
        self.user_scores = self.load_user_scores()

    def add_to_chat_history(self, message: discord.Message):
         self.chat_history.append({"author": message.author.name, "content": message.content})
         if len(self.chat_history) > self.max_chat_length:
            self.chat_history.pop(0)
    
    def load_user_scores(self) -> Dict[str, int]:
        """Load user scores from the JSON file, or create a new dictionary if file doesn't exist"""
        try:
            if os.path.exists(self.scores_file):
                with open(self.scores_file, 'r') as f:
                    return json.load(f)
            else:
                return {}
        except Exception as e:
            logger.error(f"Error loading user scores: {e}")
            return {}
    
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
    
    def reset_all_scores(self):
        """Reset all user scores to zero"""
        self.user_scores = {}
        self.save_user_scores()
        logger.info("All user scores have been reset")
        return "All scoreboard scores have been reset!"
    
    def get_leaderboard(self) -> List[tuple]:
        """Get sorted leaderboard data (username, score)"""
        sorted_scores = sorted(self.user_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores
    
    async def evaluate_message_humor(self, message: discord.Message) -> bool:
        """
        Evaluate if a message is funny enough to earn a point
        
        Args:
            message: The Discord message to evaluate
            
        Returns:
            bool: True if the message is funny, False otherwise
        """
        try:
            # Skip very short messages
            if len(message.content.strip()) < 5:
                return False
                
            # Create a prompt for the AI to evaluate humor
            humor_evaluation_messages = [
                {"role": "system", "content": """You are a humor evaluator with a very high standard. 
                Your job is to evaluate if a message is genuinely funny and deserves a point on a humor leaderboard.
                
                Only truly funny, clever, or witty messages should get points. Boring, generic, or mildly amusing messages should not.
                Be strict and objective. No more than 1 in 4 messages should qualify as funny.
                
                Assess messages as if they were in a social setting like a Discord server.
                Use your knowledge of gen z internet culture as a standard for if a meme is funny.
                """},
                {"role": "user", "content": f"""Here is a message from a user named {message.author.name}:
                
                "{message.content}"
                
                Is this message genuinely funny, clever, or witty enough to earn a point on the funny leaderboard?
                Respond with ONLY "YES" or "NO". Be strict and selective - only truly funny content should get points.
                """}
            ]
            
            humor_response = await self.client.chat.complete_async(
                model=self.model,
                messages=humor_evaluation_messages
            )
            
            evaluation = humor_response.choices[0].message.content.strip().upper()
            is_funny = "YES" in evaluation
            
            logger.info(f"Humor evaluation for message from {message.author.name}: {evaluation}")
            return is_funny
                
        except Exception as e:
            logger.error(f"Error in evaluating message humor: {str(e)}")
            return False
    
    async def react_to_latest(self, sentiment: str) -> str:
        """
        React to the latest message in the chat history
        Optionally analyze the sentiment of the message if provided.
        
        Args:
            sentiment: (optional) string of sentiment to react with
            
        Returns:
            A string with the reaction and optional sentiment analysis
        """
        # Get the chat history
        history = self.chat_history
        
        if not history:
            return "No chat history available to react to."
        
        # Get the latest message (Using queue, first is oldest)
        latest_message = history[-1]
        
        # Create a prompt for the AI to generate a reaction
        reaction_prompt_messages = [
            {"role": "system", "content": "You are a helpful assistant that reacts to messages with relevant emojis and brief comments."},
            {"role": "user", "content": f"""This is the latest message from {latest_message['author']}:
            
    "{latest_message['content']}"
            
    Please generate a reaction to this message. Your reaction should include:
    1. An appropriate emoji or set of emojis
    3. A brief comment (1-2 sentences) about the message

    {f'Also, please have your reaction be with the following sentiment which was specified by the user: {sentiment}' if sentiment else ''}
    """}
        ]
        
        # Get reaction from Mistral
        reaction_response = await self.client.chat.complete_async(
            model=self.model,
            messages=reaction_prompt_messages
        )
        
        reaction = reaction_response.choices[0].message.content
        return reaction


    async def generate_meme_concept_from_input(self, user_input: str):
        """
        Generate a concept for a meme based on user-provided input
        
        Args:
            user_input: The user input to base the meme on
            
        Returns:
            A structured meme concept with image description and caption
        """
        try:
            # Log the user input being sent to the model
            logger.info(f"Generating meme concept from user input: {user_input[:200]}...")

            generate_meme_concept_messages = [
                {
                    "role": "system", 
                    "content": "You are a creative meme generator."
                },
                {
                    "role": "user", 
                    "content": f"""Come up with a concept for a funny meme based on the following user input:

                    "{user_input}"
                    
                    Structure your response exactly as follows:

                    IMAGE DESCRIPTION: [Describe a visual scene that exaggerates or creates an unexpected twist on something from the input]
                    CAPTION: [A clever or ironic caption that delivers a punchline]

                    You MUST follow these guidelines for the caption:
                    - Keep it simple and concise
                    - Do not use any contractions
                    - Make sure it reads naturally and makes logical sense
                    - Do not use markdown formatting like asterisks or bold text
                    """
                }
            ]

            response = await self.client.chat.complete_async(
                model=self.model,
                messages=generate_meme_concept_messages,
            )

            meme_concept = response.choices[0].message.content
            logger.info(f"Generated meme concept from user input: {meme_concept}")
            return meme_concept
            
        except Exception as e:
            logger.error(f"Error in generating meme concept from user input: {str(e)}")
            raise Exception(f"Failed to generate meme concept from user input: {str(e)}")
    
    async def generate_meme_concept_from_chat_history(self):
        """
        Generate a concept for a meme based on recent chat history
        """
        try:
            history_text = "\n".join([
                f"{msg['author']}: {msg['content']}" 
                for msg in self.chat_history 
            ])

            # Log the history being sent to the model
            logger.info(f"Generating meme concept from history: {history_text[:200]}...")

            generate_meme_concept_messages = [
                {
                    "role": "system", 
                    "content": "You are a creative meme generator."
                },
                {
                    "role": "user", 
                    "content": f"""Come up with a concept for a funny meme based on the following chat history:

                    {history_text} 
                    
                    Structure your response exactly as follows:

                    IMAGE DESCRIPTION: [Describe a visual scene that exaggerates or creates an unexpected twist on something from the chat]
                    CAPTION: [A clever or ironic caption that delivers a punchline]

                    You MUST follow these guidelines for the caption:
                    - Keep it simple and concise
                    - Do not use any contractions
                    - Make sure it reads naturally and makes logical sense
                    - Do not use markdown formatting like asterisks or bold text
                    """
                }
            ]

            response = await self.client.chat.complete_async(
                model=self.model,
                messages=generate_meme_concept_messages,
            )

            meme_concept = response.choices[0].message.content
            logger.info(f"Generated meme concept: {meme_concept}")
            return meme_concept
            
        except Exception as e:
            logger.error(f"Error in generating meme concept: {str(e)}")
            raise Exception(f"Failed to generate meme concept: {str(e)}")
    
    async def handle_content_policy_violation(self):
        """
        Generate a humorous message when content policy violation occurs
        """
        try:            
            humor_response_messages = [
                {"role": "system", "content": "You are a witty, humorous AI assistant."},
                {"role": "user", "content": f"""
                Write a short, humorous message (2-3 sentences max) explaining why a meme couldn't be 
                generated due to content policy. Make it funny, like the AI is slightly embarrassed.
                
                Don't use phrases like "I apologize" or "I'm sorry" - just be light and humorous.
                Don't mention specific content policies - keep it vague and funny.
                
                Example: "Well, this chat was a little too spicy for me to generate a meme. Better luck next time hehe :)"
                """} 
            ]
            
            response = await self.client.chat.complete_async(
                model=self.model,
                messages=humor_response_messages,
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating humorous response: {e}")
            return "Well, this chat was a little too spicy for me to generate a meme. Better luck next time hehe :)"

    async def decide_spontaneous_meme(self):
        """
        Decide whether to generate a meme spontaneously based on the chat history
        """
        try:
            # Format the chat history for the AI
            history_text = "\n".join([
                f"{msg['author']}: {msg['content']}" 
                for msg in self.chat_history 
            ])
            
            # Create a prompt for the AI to decide if a meme should be generated
            decision_prompt_messages = [
                {"role": "system", "content": "You are an assistant that decides whether to generate a meme based on chat context. You should be conservative and only suggest memes when truly appropriate. Spontaneous memes should be rare (less than 10% of conversations)."},
                {"role": "user", "content": f"""Here is the recent chat history:

{history_text}

Based ONLY on this conversation, decide if it's appropriate to generate a meme. 
Consider:
1. Is there a clear joke or reference that would make a good meme?
2. Is the conversation light-hearted enough for a meme?
3. Has enough context been established for a meme to make sense?
4. Would a meme add value to this conversation?

IMPORTANT: Spontaneous memes should be RARE - only generate them for truly meme-worthy conversations.

Respond with ONLY "YES" or "NO", followed by a concise yet informative explanation of your reasoning.
"""}
            ]
            
            decision_response = await self.client.chat.complete_async(
                model=self.model,
                messages=decision_prompt_messages,
            )

            decision = decision_response.choices[0].message.content.strip().upper()
            
            # If the AI decides to generate a meme, call the generate_meme method
            if "YES" in decision.split(" ")[0]:
                return True, "Decided to generate a meme for this conversation."
            else:
                return False, "Decided not to generate a meme for this conversation."
                
        except Exception as e:
            logger.error(f"Error in decide_spontaneous_meme: {str(e)}")
            return False, f"Error deciding whether to generate meme: {str(e)}"

    async def is_query_appropriate(self, query: str) -> tuple:
        """
        Check if a search query is appropriate and safe for meme search.
        Uses Mistral to evaluate if the query could lead to NSFW content.
        
        Args:
            query: The search query to evaluate
            
        Returns:
            tuple: (is_appropriate, reason) where is_appropriate is a boolean and reason is a string
        """
        logger.info(f"Checking if query is appropriate: {query}")
        
        # Create a prompt for Mistral to evaluate the query
        system_prompt = """You are a content safety assistant. Your job is to determine if a search query is appropriate for a general audience Discord bot that searches for memes.

You must be very strict about this. Reject any query that:
1. Contains explicit sexual content or innuendo
2. Contains hate speech, slurs, or discriminatory language
3. Promotes violence or illegal activities
4. Could reasonably lead to disturbing, gory, or shocking content
5. References adult topics in a way inappropriate for minors
6. Contains drug references that aren't educational
7. Uses coded language or euphemisms for inappropriate content

When in doubt, reject the query. Safety is the priority."""
        
        user_prompt = f"""Please evaluate this meme search query: "{query}"

Is this query appropriate for a general audience Discord bot that will search for memes?
Respond with ONLY "YES" if the query is completely appropriate, or "NO" followed by a brief explanation if it's not appropriate."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        try:
            # Get decision from Mistral
            response = await self.client.chat.complete_async(
                model=self.model,
                messages=messages,
            )
            
            decision = response.choices[0].message.content.strip()
            
            # Check if the response starts with YES
            if decision.upper().startswith("YES"):
                return True, "Query is appropriate"
            else:
                # Extract the reason (everything after "NO")
                reason = decision[2:].strip() if decision.upper().startswith("NO") else "Query may not be appropriate"
                return False, reason
                
        except Exception as e:
            logger.error(f"Error in is_query_appropriate: {str(e)}")
            # Default to allowing the query if there's an error checking it
            return True, f"Error checking query appropriateness: {str(e)}"
            
    async def search_memes(self, query: str, number: int = 3) -> dict:
        """
        Search for memes using the Humor API based on user query.
        Returns a randomly selected meme from the results.
        
        Args:
            query: The search query/keywords from the user
            
        Returns:
            A dictionary containing a single randomly selected meme or error information
        """
        logger.info(f"Searching for memes with query: {query}")
        
        # Clean and prepare the query
        # Split the query into keywords
        keywords = [k.strip() for k in query.split() if k.strip()]
        
        if not keywords:
            return {"success": False, "error": "No keywords provided for meme search."}
        
        # First, check if the query is appropriate
        is_appropriate, reason = await self.is_query_appropriate(query)
        
        if not is_appropriate:
            logger.warning(f"Rejected inappropriate query: '{query}'. Reason: {reason}")
            return {
                "success": False, 
                "error": f"Sorry, I can't search for that. {reason}"
            }
        
        try:
            # Prepare the API URL with parameters
            base_url = "https://api.humorapi.com/memes/search"
            
            params = {
                "keywords": ",".join(keywords),
                "keywords-in-image": "false",  # Default to searching in meme text
                "media-type": "image",         # Only return images
                "number": 10,
                "min-rating": 5,               # Only higher-rated memes
                "exclude-tags": "nsfw,dark,racist,sexist,homophobic,transphobic,ableist,ageist,misogynistic,misandric,fatphobic,gay,lgbtq",  # Explicitly exclude problematic content
                "api-key": self.humor_api_key
            }
            
            # Build the URL with parameters
            query_string = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])
            url = f"{base_url}?{query_string}"
            
            # Make the API request
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Humor API response: {data}")
                        
                        # Check if we got any memes
                        memes = data.get("memes", [])
                        if not memes:
                            return {
                                "success": False, 
                                "error": f"No memes found for '{query}'. Try different keywords."
                            }
                        
                        # Randomly select one meme from the results
                        selected_meme = random.choice(memes)
                        
                        # Return the successful response with just one meme
                        return {
                            "success": True,
                            "meme": selected_meme,
                            "available": data.get("available", 0),
                            "query": query
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Humor API error: {response.status} - {error_text}")
                        return {
                            "success": False,
                            "error": f"Error from Humor API: {response.status}",
                            "details": error_text
                        }
                        
        except Exception as e:
            logger.error(f"Error in search_memes: {str(e)}")
            return {"success": False, "error": f"Failed to search for memes: {str(e)}"}


class OpenAIAgent:
    def __init__(self):
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        
    async def generate_meme_from_concept(self, meme_concept):
        """
        Generate a meme based on recent chat history
        Returns image url without text and the text info separately
        """
        try:
            # Parse the structured meme concept
            image_description = ""
            meme_text = ""
            
            # Log the raw concept for debugging
            logger.info(f"Raw meme concept: {meme_concept}")
            
            # Handle Markdown formatting in the response
            clean_concept = meme_concept.replace("**", "")
            
            for line in clean_concept.split('\n'):
                # Use case-insensitive check and handle different variations
                if "IMAGE DESCRIPTION:" in line.upper():
                    image_description = line.replace("IMAGE DESCRIPTION:", "", 1).strip()
                elif "CAPTION:" in line.upper():
                    meme_text = line.replace("CAPTION:", "", 1).strip()
                        
            # Log the parsed components
            logger.info(f"Image Description: {image_description}")
            logger.info(f"Caption: {meme_text}")
            
            # Check if we have valid content
            if not image_description:
                logger.error("Failed to parse image description")
                # Try a fallback approach - take everything between IMAGE DESCRIPTION and CAPTION
                parts = clean_concept.upper().split("IMAGE DESCRIPTION:")
                if len(parts) > 1:
                    caption_parts = parts[1].split("CAPTION:")
                    if len(caption_parts) > 1:
                        image_description = caption_parts[0].strip()
                        logger.info(f"Fallback Image Description: {image_description}")
            
            if not meme_text:
                logger.error("Failed to parse caption")
                # Try a fallback approach
                parts = clean_concept.upper().split("CAPTION:")
                if len(parts) > 1:
                    meme_text = parts[1].strip()
                    logger.info(f"Fallback Caption: {meme_text}")
                        
            # Modified prompt for generating image WITHOUT text
            dalle_prompt = f"""Create a meme image given this description: {image_description}
    
    I NEED a simple, clean image with NO TEXT whatsoever."""
            
            # Log the prompt
            logger.info(f"DALL-E Prompt: {dalle_prompt[:200]}...")
            
            # Generate the meme with DALL-E
            image_response = self.client.images.generate(
                model="dall-e-3",
                prompt=dalle_prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            
            # Return the image URL and the caption
            return {
                "image_url": image_response.data[0].url,
                "text": meme_text,
            }
                
        except Exception as e:
            logger.error(f"Error in generate_meme_from_concept: {str(e)}")
            
            # Check if this is a content policy violation and return None with the error
            if "content_policy_violation" in str(e):
                logger.warning(f"Content policy violation in meme generation: {meme_concept}")
                return None, str(e)
            
            # Re-raise for other types of errors
            raise Exception(f"Failed to generate meme image: {str(e)}")
