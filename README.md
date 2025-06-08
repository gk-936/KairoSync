# KairoSync - Your Personal Organizer

KairoSync is an intelligent personal organizer application designed to help you manage your tasks, courses, and events seamlessly. It features a chat interface powered by Kairo AI, allowing you to interact with your schedule and data conversationally. The application aims to provide a smart, intuitive way to stay organized and on top of your commitments.

## Features

KairoSync offers a range of features to help you stay organized:

*   **Dashboard:** Provides a quick overview of your activities, including total tasks, pending tasks, upcoming events, and active courses. It also shows a summary of recent activity.
*   **Task Management:** Allows users to add, view, and edit tasks. Tasks include details like title, description, due date/time, priority, and status.
*   **Event Management:** Manage your schedule by adding, viewing, and editing events with details such as title, description, start/end times, location, and attendees.
*   **Course Management:** Keep track of academic or other courses, including course name, description, instructor, schedule, and start/end dates.
*   **Kairo AI Chat:** An integrated conversational AI (Kairo) to assist with managing your schedule, adding items, and answering queries. Supports different response styles.
*   **New UI Theme (Frozen Glass & Zen Minimalist):** A modern, calming user interface featuring:
    *   Semi-transparent "frosted glass" effects on key UI elements.
    *   A minimalist aesthetic with a simplified color palette and clean typography.
    *   Improved visual consistency across the application.
*   **Archive Page:**
    *   "Deleted" tasks (or tasks intended for archiving) can be viewed on a separate Archive page.
    *   The archive page is accessible via the main navigation.
    *   _Note: Currently, tasks are not automatically moved to archive via a button click due to limitations in modifying existing UI logic. The "Delete" button still performs its original function if its backend logic is unchanged, or may lead to errors if the backend expects an archive operation._
*   **Theme Toggling:** Users can switch between light and dark visual themes.
*   **Cross-Platform:** Built with Electron, allowing it to run on multiple operating systems.

## Tech Stack

KairoSync is built using the following technologies:

*   **Frontend:**
    *   HTML5
    *   CSS3 (including custom theme `theme.css`)
    *   JavaScript (ES6+)
*   **Application Framework:**
    *   Electron (for cross-platform desktop application capabilities)
*   **Backend (assumed based on project structure and `main.js`):**
    *   Python
    *   Flask (common lightweight framework for Python backends)
*   **Database (assumed based on project files):**
    *   SQLite (e.g., `kairo_data.db`, `kairo_tasks.db`)
*   **Development Environment:**
    *   Node.js and npm (for managing Electron app dependencies and running scripts)

## Setup and Installation

To get KairoSync running on your local machine, follow these steps:

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd kairo-sync-project  # Or your project's directory name
    ```

2.  **Set up Python Backend:**
    *   Ensure you have Python 3.x installed.
    *   It's recommended to create a virtual environment:
        ```bash
        python -m venv venv
        ```
    *   Activate the virtual environment:
        *   On Windows:
            ```bash
            .\venv\Scripts\activate
            ```
        *   On macOS/Linux:
            ```bash
            source venv/bin/activate
            ```
    *   Install Python dependencies:
        *   _Note: A `requirements.txt` file is not currently present in the repository. You would typically install dependencies using `pip install -r requirements.txt`. For now, you might need to identify and install dependencies like Flask manually if not already globally available (e.g., `pip install Flask Flask-SQLAlchemy Flask-Cors`)._

3.  **Set up Frontend (Electron App):**
    *   Ensure you have Node.js and npm installed.
    *   Install Node.js dependencies:
        ```bash
        npm install
        ```

4.  **Run the Application:**
    *   The `main.js` file attempts to start the Python backend automatically.
    *   To start the Electron application (which in turn should try to start the Python backend):
        ```bash
        npm start
        ```
        (This command is typically defined in the `scripts` section of `package.json`. If it's not, you might need to run `electron .`)

5.  **Database Initialization (if needed):**
    *   The application uses SQLite databases (`.db` files). These might be created automatically by the backend on first run if they don't exist. If there are specific initialization scripts or steps for the database schema, they would be listed here. (No specific scripts have been identified so far).

## Known Issues / Current Limitations

*   **File Modification Challenges:** During recent development, persistent issues were encountered with the automated tools used for modifying core JavaScript files (like `renderer.js`). This has impacted the ability to implement certain features directly as planned.
*   **"Delete" vs. "Archive" Functionality:**
    *   The UI buttons for deleting tasks were not changed to "Archive" due to the file modification issues mentioned above. The original "Delete" buttons remain.
    *   The intended behavior was for these buttons to move tasks to the Archive page. Depending on the backend status, clicking "Delete" might perform an actual deletion or result in an error if the backend expects an archive operation.
*   **Auto-Archiving Not Implemented:** Settings and frontend logic for automatically archiving completed tasks after a certain period were not implemented due to their dependency on modifying `renderer.js`.
*   **Archive Page Access:** The Archive page is functional and accessible via the navigation sidebar. Its content is loaded using a `hashchange` event listener as a workaround, instead of being directly integrated into the main view-switching logic in `renderer.js`.
*   **Backend Endpoint Assumptions:** The frontend logic for archiving (had it been fully implemented for the button) and fetching archived tasks assumes specific backend endpoints (e.g., `PUT /tasks/{taskId}/archive` and `GET /tasks/archived`). These need to be implemented and aligned in the backend.
*   **Python Dependencies:** A formal `requirements.txt` for Python dependencies is not currently part of the repository. Setup instructions list common potential dependencies like Flask.
*   **Hardcoded API URL:** The `API_BASE_URL` in `renderer.js` (and `archive.js`) is hardcoded to `http://127.0.0.1:5000`. This might need to be made configurable for different environments.
*   **Python Path in `main.js`:** The path to the Python executable for the backend in `main.js` might be specific to a particular environment setup (`venv\Scripts\python.exe`) and may require adjustment on other systems or for different virtual environment configurations.

## Contributing

Contributions to KairoSync are welcome! If you have ideas for improvements, new features, or bug fixes, please feel free to:

1.  Fork the repository.
2.  Create a new branch for your feature or fix (`git checkout -b feature/your-feature-name`).
3.  Make your changes and commit them with clear messages.
4.  Push your changes to your fork (`git push origin feature/your-feature-name`).
5.  Submit a pull request to the main repository for review.

If you encounter any issues or have suggestions, please open an issue on the project's issue tracker.

## License

This project is currently under a placeholder license. Please refer to the `LICENSE` file in the repository for full details once it is added.

If no `LICENSE` file is present, the code is provided as-is, without any warranty, express or implied.
