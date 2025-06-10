# Kairo Personal Assistant - Desktop Application

Kairo is a desktop application designed to be your personal assistant, helping you manage tasks, events, and interact with an AI for assistance.

## Features

*   **Dashboard**: Get a quick overview of your day, including upcoming events and pending tasks.
*   **Task Management**: Create, view, and complete tasks.
*   **Event Scheduling**: Add and view your events.
*   **AI Chat**: Interact with Kairo AI for help, information, or to trigger actions (e.g., task creation).
*   **User Settings**: Customize application preferences like theme (display only for now), working hours, and task archival settings.
*   **Local Data Storage**: All your data is stored locally in an SQLite database (`kairo_data.db`).

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
    *(Note: The `requirements.txt` file might need to be created or updated based on the final imports used in the project. Key dependencies identified are `requests` and `python-dateutil`.)*

## Running the Application

1.  **Ensure Ollama is Running**: If you plan to use the AI Chat feature, start your Ollama server and ensure the model is available.

2.  **Run the Main Application**:
    Execute the `main_app.py` script:
    ```bash
    python main_app.py
    ```

3.  **First Run - Database Initialization**:
    On the first run, the application will create and initialize an SQLite database file named `kairo_data.db` in the same directory as `main_app.py`. This file will store all your tasks, events, settings, etc.

## Using the Application

The application features a tabbed interface:

*   **Dashboard**: Shows your daily summary. Click "Refresh Dashboard" to update.
*   **Kairo AI Chat**: Type your message in the input field and press Enter or click "Send". Conversation history is loaded and saved.
*   **Tasks**:
    *   View existing tasks in the list.
    *   Add new tasks using the form and "Add Task" button.
    *   Select a task and click "Mark Complete".
    *   Click "Refresh" to reload the task list.
*   **Events**:
    *   View existing events.
    *   Add new events using the form and "Add Event" button.
    *   Click "Refresh Events" to reload.
*   **Settings**:
    *   View and modify your application preferences.
    *   Click "Save Settings" to apply changes.

## Project Structure

*   `main_app.py`: Main entry point for the Tkinter desktop application.
*   `database.py`: Handles SQLite database connection and schema.
*   `services.py`: Contains business logic for tasks, events, reports, etc.
*   `kairo_ai.py`: Manages interaction with the Ollama AI model and chat history.
*   `models.py`: Defines data structures for tasks and events.
*   `user_service.py`: Manages user identification.
*   `settings_service.py`: Manages application settings.
*   `adaptive_learning.py`: (Backend for future adaptive features, currently influences AI prompts and task completion logging).
*   `utils.py`: Utility functions.
*   `kairo_data.db`: SQLite database file (created on first run).
*   `requirements.txt`: Lists Python dependencies.

## Notes for Future Development

*   **Packaging**: Use tools like PyInstaller or cx_Freeze to package the application into a standalone executable.
*   **UI Enhancements**: Implement more sophisticated widgets (e.g., calendar for date picking), error handling, and visual themes.
*   **Full Feature Integration**: Integrate `SchedulingService` and `LearningService` into the UI.
*   **Requirements Update**: The `requirements.txt` needs to be finalized. Based on the current files, it should contain at least:
    ```
    requests
    python-dateutil
    ```
    (Tkinter is part of the standard Python library).
