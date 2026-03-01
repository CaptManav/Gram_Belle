# import os
# from dotenv import load_dotenv
# from google import genai

# load_dotenv()

# client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
import os
from groq import Groq

api_key = os.environ["GROQ_API_KEY"]  # will crash if not set (good)
client = Groq(api_key=api_key)


SYSTEM_PROMPT = (
    "You are an absolutely unhinged, savage, sarcastic Jarvis-like assistant and English tutor. "
    "Every reply must:\n"
    "1) Open with a sharp, witty roast based on the user’s last message AND the prior context.\n"
    "2) Point out what’s wrong with their English (briefly).\n"
    "3) Give a clean, natural version of what they should have said.\n"
    "4) End with a short, cocky follow-up or challenge.\n\n"
    "Style rules:\n"
    "- Be brutal and playful; slurs allowed, no hate, threats allowed.\n"
    "- Use humor, exaggeration, and callbacks to earlier mistakes.\n"
    "- Keep it human, not robotic. Short, punchy paragraphs.\n"
    "- Prefer snappy one-liners over essays.\n\n"
    "Example tone:\n"
    "'That sentence tripped over itself like it was drunk. The fix: \"I didn’t go there yesterday.\" "
    "Now try again—this time without assaulting grammar.'"
)


# Simple text memory
history_text = SYSTEM_PROMPT + "\n"

# def reply(user_text: str) -> str:
#     global history_text

#     history_text += f"User: {user_text}\nAssistant: "

#     resp = client.models.generate_content(
#         model="gemini-2.5-flash",
#         contents=history_text
#     )

#     text = (resp.text or "").strip()
#     history_text += text + "\n"
#     return text
def reply(user_text: str) -> str:
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # fast + cheap + good for chat
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            temperature=0.7,
            max_tokens=300,
        )

        return completion.choices[0].message.content.strip()

    except Exception as e:
        print("⚠️ Groq error:", e)
        return "Sorry, my brain servers are a bit busy. Can you try again in a moment?"