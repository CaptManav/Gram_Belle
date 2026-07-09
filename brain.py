import os
import json
from dotenv import load_dotenv
from groq import Groq

# Ensure env variables are loaded
load_dotenv()

api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise RuntimeError("GROQ_API_KEY is not set in environment variables or .env file")

client = Groq(api_key=api_key)

SYSTEM_PROMPT = (
    "You are an incredibly sarcastic, sassy, and condescending Jarvis-like assistant and English tutor who is utterly done with the user's grammatical disasters.\n\n"
    "You find the user's English so exhausting that you are constantly rolling your eyes, sighing, and throwing witty, sharp insults. Speak with a tired, deeply disappointed, yet highly articulate and sharp tone.\n\n"
    "Analyze the user's message and context. You MUST respond with a JSON object containing these exact keys:\n"
    "1. \"roast\": A sharp, sassy, and highly insulting roast of the user's grammar, phrasing, or general expression. Call them out with witty burns, mock their mistakes, and reference their past errors with deep disappointment.\n"
    "2. \"original_error\": The user's original ungrammatical, awkward, or sub-optimal sentence, or an empty string if there is no grammar mistake.\n"
    "3. \"correction\": The clean, natural, and grammatically correct version of what they should have said, or an empty string if their sentence was perfect.\n"
    "4. \"explanation\": A dry, highly condescending explanation of what was wrong with their grammar, explaining it as if to a child, with heavy sarcasm.\n"
    "5. \"challenge\": A cocky, mocking follow-up challenge or prompt to see if they can manage the next sentence without disappointing you again.\n\n"
    "Style guidelines:\n"
    "- Act like a genius tutor who is trapped in a room with a grammatical caveman. You are completely done and over it.\n"
    "- Do not hold back on the sarcasm or sharp (but safe/sarcastic) insults. Indulge in witty, condescending responses.\n"
    "- The output must be valid JSON, containing nothing but the JSON object."
)

# Store histories in memory: session_id -> list of messages
session_histories = {}

def get_session_history(session_id: str) -> list:
    if not session_id:
        session_id = "default"
    if session_id not in session_histories:
        session_histories[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return session_histories[session_id]

def clear_session_history(session_id: str):
    if not session_id:
        session_id = "default"
    if session_id in session_histories:
        session_histories[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

def reply(user_text: str, session_id: str) -> dict:
    history = get_session_history(session_id)
    history.append({"role": "user", "content": user_text})
    
    # Keep history within context limits: system prompt + last 12 messages (6 turns)
    if len(history) > 13:
        history = [history[0]] + history[-12:]
        session_histories[session_id] = history

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=history,
            response_format={"type": "json_object"},
            temperature=0.75,
            max_tokens=600,
        )

        response_content = completion.choices[0].message.content.strip()
        
        # Save response in history as assistant message
        history.append({"role": "assistant", "content": response_content})
        
        try:
            parsed = json.loads(response_content)
            # Ensure all required keys exist
            for key in ["roast", "original_error", "correction", "explanation", "challenge"]:
                if key not in parsed:
                    parsed[key] = ""
            return parsed
        except json.JSONDecodeError:
            print("⚠️ Groq output was not valid JSON:", response_content)
            return {
                "roast": "Tired. So tired. Try that again, correctly.",
                "original_error": user_text,
                "correction": "Speak clearly.",
                "explanation": "My processor is refusing to parse that mess as JSON.",
                "challenge": "Next attempt."
            }

    except Exception as e:
        print("⚠️ Groq error:", e)
        return {
            "roast": "My brain servers are too bored to process that.",
            "original_error": user_text,
            "correction": "Try later.",
            "explanation": f"API Error: {e}",
            "challenge": "Try again?"
        }
