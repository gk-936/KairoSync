import json
import requests
import datetime
import database # Added
from adaptive_learning import AdaptiveLearner

OLLAMA_URL = "http://localhost:11434/api/chat" # Consider making this configurable
OLLAMA_MODEL = "vicuna:latest" # Consider making this configurable

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
    """Retrieves conversation history for a user from the database."""
    db = database.get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        "SELECT sender, message FROM conversation_history WHERE user_id = ? ORDER BY timestamp ASC LIMIT ?",
        # Changed to ASC for chronological order, then will be reversed for display if needed
        (user_id, limit)
    )
    history_rows = cursor.fetchall()
    return [{"sender": row["sender"], "message": row["message"]} for row in history_rows]

def log_conversation_message(user_id, sender, message, parsed_action=None, context_flags=None):
    """Logs a message to the conversation history in the database."""
    db = database.get_db_connection()
    cursor = db.cursor()
    try:
        timestamp = datetime.datetime.now().isoformat()
        final_parsed_action = json.dumps(parsed_action) if parsed_action else None
        final_context_flags = json.dumps(context_flags) if context_flags else None

        cursor.execute(
            """INSERT INTO conversation_history
               (user_id, sender, message, parsed_action, context_flags, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, sender, message,
             final_parsed_action,
             final_context_flags,
             timestamp)
        )
        db.commit()
    except Exception as e:
        print(f"Error logging conversation message: {e}")

def get_kairo_response(user_id, user_message, conversation_history_list_of_dicts):
    """
    Get Kairo's response from AI.
    conversation_history_list_of_dicts: Expected format is a list of dicts,
                                         e.g., [{"sender": "user", "message": "Hi there"}]
                                         Should be in chronological order (oldest first).
    """
    learner = AdaptiveLearner(user_id)
    settings = learner.profile if hasattr(learner, 'profile') else {}

    # History for the prompt string (can be truncated differently than history for Ollama messages)
    # KAIRO_PROMPT expects a JSON string dump.
    # For the prompt, showing newest messages might be better, so reverse if it's chronological.
    prompt_history_display = list(reversed(conversation_history_list_of_dicts[-5:])) # last 5, newest first
    formatted_history_for_prompt = json.dumps(prompt_history_display)

    prompt_text = KAIRO_PROMPT.format(
        current_date=datetime.date.today().isoformat(),
        user_settings=json.dumps(settings),
        conversation_history=formatted_history_for_prompt
    )

    # For Ollama, messages should be in chronological order.
    messages_for_ollama = []
    for entry in conversation_history_list_of_dicts: # Assumes this list is already chronological
        role = "user" if entry["sender"].lower() == "user" else "assistant"
        if entry["sender"].lower() == "kairo": # Explicitly map "kairo" to assistant for Ollama
             role = "assistant"
        messages_for_ollama.append({"role": role, "content": entry["message"]})

    messages_for_ollama.append({"role": "user", "content": user_message}) # Current user message

    final_messages_payload = [
        {"role": "system", "content": prompt_text}
    ] + messages_for_ollama # Add the conversation context

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "messages": final_messages_payload, "stream": False},
            timeout=60
        )
        response.raise_for_status()
        ai_message_content = response.json().get("message", {}).get("content", "")
        return ai_message_content
    except requests.exceptions.Timeout:
        return "System error: The AI service timed out."
    except requests.exceptions.RequestException as e:
        return f"System error: AI service request failed ({type(e).__name__}). Check Ollama connection."
    except Exception as e:
        return f"System error: An unexpected error occurred ({type(e).__name__})."

def parse_ai_action(ai_response_text):
    try:
        parsed = json.loads(ai_response_text)
        if isinstance(parsed, dict) and "action" in parsed:
            return parsed
    except json.JSONDecodeError:
        pass
    return {"action": "conversation", "response": ai_response_text}
