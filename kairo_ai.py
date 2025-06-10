import json
import requests
import datetime
from adaptive_learning import AdaptiveLearner

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

def get_kairo_response(user_id, user_message, conversation_history):
    """Get Kairo's response from AI"""
    # Get user settings for personalization
    learner = AdaptiveLearner(user_id)
    settings = learner.profile
    
    # Prepare the enhanced prompt
    prompt = KAIRO_PROMPT.format(
        current_date=datetime.date.today().isoformat(),
        user_settings=json.dumps(settings),
        conversation_history=json.dumps(conversation_history)
    )
    
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_message}
    ]
    
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
            timeout=30
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
    except Exception as e:
        return f"System error: {str(e)}"

def parse_ai_action(ai_response):
    try:
        return json.loads(ai_response)
    except:
        return {"action": "conversation", "response": ai_response}