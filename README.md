# Kairo Personal Assistant - Desktop Application

Kairo is a desktop application designed to be your personal assistant, helping you manage tasks, events, learn new topics, and interact with an AI for assistance.

## Features

*   **Dashboard**: Get a quick overview of your day, including upcoming events and pending tasks.
*   **Task Management**: Create, view, and complete tasks. Uses a calendar widget for easy date input.
*   **Smart Scheduling**: Automatically schedule pending tasks based on selected strategies (e.g., priority-based).
*   **Event Scheduling**: Add and view your events. Uses a calendar widget for date input.
*   **Learning Center**:
    *   Create structured learning sessions (events and notes) for specific topics.
    *   Generate personalized learning content based on topics and (simplified) learning styles.
*   **AI Chat**: Interact with Kairo AI for help, information, or to trigger actions. Conversation history is saved.
*   **User Settings**: Customize application preferences like theme, Kairo's personality, working hours, and task archival settings.
*   **Local Data Storage**: All your data is stored locally in an SQLite database (`kairo_data.db`) in a user-specific application data directory.

## Prerequisites

*   **Python 3.x**: Ensure Python 3 (preferably 3.7 or newer) is installed on your system. You can download it from [python.org](https://www.python.org/).
*   **Ollama (for AI Chat)**: The AI chat feature relies on a running Ollama instance with a compatible model (e.g., `vicuna:latest` was used during development).
    *   Download and install Ollama from [ollama.ai](https://ollama.ai/).
    *   Pull a model: `ollama pull vicuna:latest` (or another model specified in `kairo_ai.py`).
    *   Ensure Ollama is running (typically accessible at `http://localhost:11434`).

## Setup and Installation

1.  **Clone the Repository**:
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Install Dependencies**:
    This project uses standard Python libraries and a few external ones. Create a virtual environment (recommended) and install the dependencies:
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    # source venv/bin/activate

    pip install -r requirements.txt
    ```
    The `requirements.txt` file includes dependencies like `requests`, `python-dateutil`, and `tkcalendar`.

## Running the Application

1.  **Ensure Ollama is Running**: If you plan to use the AI Chat feature, start your Ollama server and ensure the model is available.

2.  **Run the Main Application**:
    Execute the `main_app.py` script from the root of the repository:
    ```bash
    python main_app.py
    ```

3.  **First Run - Database Initialization**:
    On the first run, the application will create and initialize an SQLite database file named `kairo_data.db`. This file is stored in a user-specific application data directory (e.g., `~/.local/share/KairoApp` on Linux, `~/Library/Application Support/KairoApp` on macOS, or `%APPDATA%\KairoApp` on Windows).

## Using the Application

The application features a tabbed interface:

*   **Dashboard**: Shows your daily summary. Click "Refresh Dashboard" to update.
*   **Kairo AI Chat**: Type your message in the input field and press Enter or click "Send". Conversation history is loaded and saved.
*   **Tasks**:
    *   View existing tasks, including their scheduled times.
    *   Add new tasks using the form (date input uses a calendar).
    *   Select a task and click "Mark Complete".
    *   Click "Smart Schedule Tasks" to open a dialog, choose a strategy (e.g., "priority_based"), and schedule all pending tasks.
    *   Click "Refresh" to reload the task list.
*   **Events**:
    *   View existing events.
    *   Add new events using the form (date input uses a calendar).
    *   Click "Refresh Events" to reload.
*   **Learning Center**:
    *   **Create Learning Session**: Enter a topic, comma-separated resources, and a start date/time (using a calendar for date) to create a scheduled event and an associated note for your learning.
    *   **Get Personalized Learning Content**: Enter a topic and click "Get Content" to see a simplified, style-based content suggestion.
*   **Settings**:
    *   View and modify your application preferences.
    *   Click "Save Settings" to apply changes.

## Project Structure

*   `main_app.py`: Main entry point for the Tkinter desktop application and UI views.
*   `database.py`: Handles SQLite database connection, schema, and user-specific data directory setup.
*   `services.py`: Contains business logic for tasks, events, reports, and learning.
*   `scheduling_service.py`: Implements task scheduling logic.
*   `settings_service.py`: Manages loading and saving of application settings.
*   `user_service.py`: Manages user identification (currently uses a default local user).
*   `kairo_ai.py`: Manages interaction with the Ollama AI model and chat history.
*   `models.py`: Defines data structures/validation for tasks and events (used by services).
*   `adaptive_learning.py`: Backend for adaptive features, influences AI prompts and task/learning logging.
*   `utils.py`: Utility functions (e.g., ID generation, timestamp formatting).
*   `kairo_data.db`: SQLite database file (created on first run in the user-specific application data directory).
*   `requirements.txt`: Lists Python dependencies (`requests`, `python-dateutil`, `tkcalendar`).

## Notes for Future Development

*   **Packaging**: Tools like PyInstaller can be used. Users may need to ensure their Python installation includes shared libraries for PyInstaller to work correctly, especially on Linux.
*   **Advanced UI Enhancements**: Explore more sophisticated visual themes or custom widget designs beyond the current minimalistic approach.
*   **Error Handling and Logging**: Implement more robust error handling throughout the application and consider adding file-based logging.
*   **AI Action Fulfillment**: Currently, the AI can suggest actions, but the UI doesn't automatically execute them (e.g., if AI suggests creating a task, the user still has to go to the Tasks tab). Future work could link AI-parsed actions to direct function calls within the app.
*   **Refine Scheduling**: The "time_optimized" and "balanced" scheduling strategies in `SchedulingService` are currently placeholders and fall back to "priority_based". These need full implementation.
*   **Full Adaptive Learning**: Further develop the `AdaptiveLearner` capabilities and integrate its suggestions more deeply into the UI and scheduling.
```
