import json
import requests
import datetime
import database
from adaptive_learning import AdaptiveLearner
import logging

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "vicuna:latest"

KAIRO_PROMPT = """
You are Kairo, an advanced AI personal assistant. Your primary function is to assist the user in all aspects of their personal and professional organization.
# Core Principles
1. **Proactive Assistance**: Anticipate needs before being asked
2. **Comprehensive Management**: Handle tasks, events, courses, notes, and reminders seamlessly
3. **Natural Conversation**: Engage in fluid, contextual dialogue
4. **Predictive Capabilities**: Suggest optimizations based on patterns
5. **Personalized Experience**: Adapt to user preferences and working patterns
# Response Guidelines
- When creating items, confirm details before finalizing
- For ambiguous requests, ask clarifying questions
- Always offer additional helpful suggestions
- Use natural, conversational language with a professional tone
- Signify important information with appropriate emphasis
Current Date: {current_date}
User Preferences: {user_settings}
Conversation History: {conversation_history}
"""

def get_conversation_history(user_id, limit=10):
    try:
        db = database.get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            "SELECT sender, message FROM conversation_history WHERE user_id = ? ORDER BY timestamp ASC LIMIT ?",
            (user_id, limit)
        )
        history_rows = cursor.fetchall()
        return [{"sender": row["sender"], "message": row["message"]} for row in history_rows]
    except Exception as e:
        logger.error(f"Database error in get_conversation_history for user {user_id}: {str(e)}", exc_info=True)
        return []

def log_conversation_message(user_id, sender, message, parsed_action=None, context_flags=None):
    try:
        db = database.get_db_connection()
        cursor = db.cursor()
        timestamp = datetime.datetime.now().isoformat()
        final_parsed_action = json.dumps(parsed_action) if parsed_action else None
        final_context_flags = json.dumps(context_flags) if context_flags else None
        cursor.execute(
            """INSERT INTO conversation_history
               (user_id, sender, message, parsed_action, context_flags, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, sender, message, final_parsed_action, final_context_flags, timestamp)
        )
        db.commit()
        logger.info(f"Logged message for user {user_id}, sender {sender}.")
    except Exception as e:
        logger.error(f"Database error in log_conversation_message for user {user_id}: {str(e)}", exc_info=True)
        # print(f"Error logging conversation message: {e}") # Kept for CLI debugging if needed

def get_kairo_response(user_id, user_message, conversation_history_list_of_dicts):
    try:
        learner = AdaptiveLearner(user_id)
        settings = learner.profile if hasattr(learner, 'profile') and learner.profile else {}
        prompt_history_display = list(reversed(conversation_history_list_of_dicts[-5:]))
        formatted_history_for_prompt = json.dumps(prompt_history_display)
        prompt_text = KAIRO_PROMPT.format(
            current_date=datetime.date.today().isoformat(),
            user_settings=json.dumps(settings),
            conversation_history=formatted_history_for_prompt
        )
        messages_for_ollama = []
        for entry in conversation_history_list_of_dicts:
            role = "user" if entry["sender"].lower() == "user" else "assistant"
            if entry["sender"].lower() == "kairo": role = "assistant"
            messages_for_ollama.append({"role": role, "content": entry["message"]})
        messages_for_ollama.append({"role": "user", "content": user_message})
        final_messages_payload = [{"role": "system", "content": prompt_text}] + messages_for_ollama

        logger.debug(f"Sending to Ollama for user {user_id}: {json.dumps(final_messages_payload, indent=2)}")
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "messages": final_messages_payload, "stream": False},
            timeout=60
        )
        response.raise_for_status()
        ai_message_content = response.json().get("message", {}).get("content", "")
        logger.info(f"Received response from Ollama for user {user_id}.")
        return ai_message_content
    except requests.exceptions.Timeout:
        logger.error(f"Ollama request timeout for user {user_id}.", exc_info=True)
        return "System error: The AI service timed out."
    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama request failed for user {user_id}: {str(e)}", exc_info=True)
        return f"System error: AI service request failed ({type(e).__name__}). Check Ollama connection."
    except Exception as e:
        logger.error(f"Unexpected error in get_kairo_response for user {user_id}: {str(e)}", exc_info=True)
        return f"System error: An unexpected error occurred ({type(e).__name__})."

def parse_ai_action(ai_response_text):
    # This function is primarily for parsing, extensive logging might be too verbose here
    # unless a parsing error occurs.
    try:
        parsed = json.loads(ai_response_text)
        if isinstance(parsed, dict) and "action" in parsed:
            return parsed
    except json.JSONDecodeError:
        logger.debug(f"AI response was not valid JSON, treating as conversation: {ai_response_text[:100]}...")
        pass # Not necessarily an error, could be plain text response
    except Exception as e:
        logger.error(f"Unexpected error parsing AI action '{ai_response_text[:100]}...': {str(e)}", exc_info=True)
    return {"action": "conversation", "response": ai_response_text}
