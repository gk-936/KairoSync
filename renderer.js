document.addEventListener('DOMContentLoaded', () => {
    try {
        const userId = "user123"; // This should be dynamically set based on user login
    const API_BASE_URL = 'http://127.0.0.1:5000'; // Define the base URL for your Flask backend

    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const chatSendButton = document.getElementById('chat-send-button');
    const loadingSpinner = document.getElementById('loading-spinner');
    const navItems = document.querySelectorAll('.nav-item');
    const contentViews = document.querySelectorAll('.content-view');
    const currentSectionTitle = document.getElementById('current-section-title');
    const themeToggleButton = document.getElementById('theme-toggle-button');
    const kairoStyleSelect = document.getElementById('kairo-style-select');

    // Dashboard elements
    const dashboardTotalTasks = document.getElementById('dashboard-total-tasks');
    const dashboardPendingTasks = document.getElementById('dashboard-pending-tasks');
    const dashboardUpcomingEvents = document.getElementById('dashboard-upcoming-events');
    const dashboardActiveCourses = document.getElementById('dashboard-active-courses');
    const dashboardRecentActivity = document.getElementById('dashboard-recent-activity');

    // Task elements
    const addTaskButton = document.getElementById('add-task-button');
    const newTaskTitle = document.getElementById('new-task-title');
    const newTaskDescription = document.getElementById('new-task-description');
    const newTaskDueDate = document.getElementById('new-task-due-date');
    const newTaskDueTime = document.getElementById('new-task-due-time');
    const newTaskPriority = document.getElementById('new-task-priority');
    const newTaskStatus = document.getElementById('new-task-status');
    const tasksListContainer = document.getElementById('tasks-list-container');

    // Event elements
    const addEventButton = document.getElementById('add-event-button');
    const newEventTitle = document.getElementById('new-event-title');
    const newEventDescription = document.getElementById('new-event-description');
    const newEventStartDate = document.getElementById('new-event-start-date');
    const newEventStartTime = document.getElementById('new-event-start-time');
    const newEventEndDate = document.getElementById('new-event-end-date');
    const newEventEndTime = document.getElementById('new-event-end-time');
    const newEventLocation = document.getElementById('new-event-location');
    const newEventAttendees = document.getElementById('new-event-attendees');
    const eventsListContainer = document.getElementById('events-list-container');

    // Course elements
    const addCourseButton = document.getElementById('add-course-button');
    const newCourseName = document.getElementById('new-course-name');
    const newCourseDescription = document.getElementById('new-course-description');
    const newCourseInstructor = document.getElementById('new-course-instructor');
    const newCourseSchedule = document.getElementById('new-course-schedule');
    const newCourseStartDate = document.getElementById('new-course-start-date');
    const newCourseEndDate = document.getElementById('new-course-end-date');
    const coursesListContainer = document.getElementById('courses-list-container');

    let currentKairoStyle = localStorage.getItem('kairo_style') || 'friendly';
    kairoStyleSelect.value = currentKairoStyle;

    // --- Utility Functions ---
    function addMessageToChat(sender, message) {
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('chat-message', sender);
        msgDiv.textContent = message;
        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight; // Scroll to bottom
    }

    function showLoadingSpinner() {
        loadingSpinner.classList.remove('hidden');
        chatSendButton.disabled = true;
        chatInput.disabled = true;
    }

    function hideLoadingSpinner() {
        loadingSpinner.classList.add('hidden');
        chatSendButton.disabled = false;
        chatInput.disabled = false;
        chatInput.focus();
    }

    function formatDateForInput(isoDateString) {
        if (!isoDateString) return '';
        try {
            const date = new Date(isoDateString);
            return date.toISOString().split('T')[0]; // YYYY-MM-DD
        } catch (e) {
            console.error("Error parsing date for input:", isoDateString, e);
            return '';
        }
    }

    function formatTimeForInput(isoDateString) {
        if (!isoDateString) return '';
        try {
            const date = new Date(isoDateString);
            return date.toTimeString().split(' ')[0].substring(0, 5); // HH:MM
        } catch (e) {
            console.error("Error parsing time for input:", isoDateString, e);
            return '';
        }
    }

    function getFormattedDateTime(dateInput, timeInput) {
        const date = dateInput.value;
        const time = timeInput.value;
        if (date && time) {
            return `${date}T${time}:00`; // YYYY-MM-DDTHH:MM:SS
        } else if (date) {
            return `${date}T23:59:59`; // End of day if only date is provided
        }
        return null;
    }

    function getFormattedDate(dateInput) {
        const date = dateInput.value;
        if (date) {
            return date; // YYYY-MM-DD
        }
        return null;
    }

    // --- Theme Toggling ---
    function applyTheme(theme) {
        document.body.classList.remove('light-theme', 'dark-theme');
        document.body.classList.add(`${theme}-theme`);
        localStorage.setItem('theme', theme);
    }

    const savedTheme = localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    applyTheme(savedTheme);

    if (themeToggleButton) {
        themeToggleButton.addEventListener('click', () => {
            const currentTheme = localStorage.getItem('theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            applyTheme(newTheme);
        });
    } else {
        console.error("Theme toggle button not found.");
    }

    // --- Navigation and View Switching ---
    function showView(viewId) {
        contentViews.forEach(view => view.classList.remove('active'));
        document.getElementById(`${viewId}-view`).classList.add('active');

        navItems.forEach(item => item.classList.remove('active'));
        document.querySelector(`a[href="#${viewId}"]`).classList.add('active');

        currentSectionTitle.textContent = viewId.charAt(0).toUpperCase() + viewId.slice(1);

        // Fetch data relevant to the view
        if (viewId === 'tasks') {
            fetchAndRenderTasks();
        } else if (viewId === 'events') {
            fetchAndRenderEvents();
        } else if (viewId === 'courses') {
            fetchAndRenderCourses();
        } else if (viewId === 'dashboard') {
            updateDashboard();
        }
    }

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const viewId = e.target.getAttribute('href').substring(1);
            showView(viewId);
        });
    });

    // Initialize to dashboard view
    showView('dashboard');

    // --- Data Fetching and Rendering ---

    async function fetchAndRenderTasks() {
        tasksListContainer.innerHTML = '<p class="text-muted">Loading tasks...</p>';
        try {
            const response = await fetch(`${API_BASE_URL}/tasks?user_id=${userId}`);
            if (!response.ok) {
                let errorMsg = `HTTP error! status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.error || errorData.message || errorMsg;
                } catch (e) { /* Ignore if error response is not JSON */ }
                throw new Error(errorMsg);
            }
            // Handle 204 No Content if applicable, though GET usually has content
            if (response.status === 204) {
                renderTasks([]); // Render empty if server says no content
                return;
            }
            const data = await response.json();
            renderTasks(data.tasks || []); // Ensure data.tasks is fallback to array
        } catch (error) {
            console.error('Error fetching tasks:', error);
            tasksListContainer.innerHTML = `<p class="text-error">Failed to load tasks: ${error.message}. Please ensure your backend server is running and accessible at ${API_BASE_URL}.</p>`;
        }
    }

    function renderTasks(tasks) {
        tasksListContainer.innerHTML = ''; // Clear previous tasks
        if (tasks.length === 0) {
            tasksListContainer.innerHTML = '<p class="text-muted">No tasks found. Add a new task above or chat with Kairo!</p>';
            return;
        }

        tasks.forEach(task => {
            const taskElement = document.createElement('div');
            taskElement.classList.add('card', 'task-item');
            taskElement.dataset.taskId = task.task_id; // Store task_id for updates/deletes

            const dueDate = task.due_datetime ? new Date(task.due_datetime).toLocaleString() : 'No due date';
            const descriptionSnippet = task.description ? ` - ${task.description.substring(0, 50)}${task.description.length > 50 ? '...' : ''}` : '';

            taskElement.innerHTML = `
                <div class="task-header">
                    <h4 class="task-title">${task.title}</h4>
                    <span class="task-priority priority-${task.priority}">${task.priority.toUpperCase()}</span>
                </div>
                <p class="task-meta">Due: ${dueDate}</p>
                <p class="task-status status-${task.status}">${task.status.replace(/-/g, ' ').toUpperCase()}</p>
                ${task.description ? `<p class="task-description">${task.description}</p>` : ''}
                ${task.tags ? `<p class="task-tags">Tags: ${task.tags}</p>` : ''}
                <div class="task-actions">
                    <button class="button-secondary edit-task-button" data-id="${task.task_id}">Edit</button>
                    <button class="button-danger delete-task-button" data-id="${task.task_id}">Delete</button>
                </div>
            `;
            tasksListContainer.appendChild(taskElement);
        });
        attachTaskEventListeners();
    }

    async function fetchAndRenderEvents() {
        eventsListContainer.innerHTML = '<p class="text-muted">Loading events...</p>';
        try {
            const response = await fetch(`${API_BASE_URL}/events?user_id=${userId}`);
            if (!response.ok) {
                let errorMsg = `HTTP error! status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.error || errorData.message || errorMsg;
                } catch (e) { /* Ignore if error response is not JSON */ }
                throw new Error(errorMsg);
            }
            if (response.status === 204) {
                renderEvents([]);
                return;
            }
            const data = await response.json();
            renderEvents(data.events || []);
        } catch (error) {
            console.error('Error fetching events:', error);
            eventsListContainer.innerHTML = `<p class="text-error">Failed to load events: ${error.message}. Please ensure your backend server is running and accessible at ${API_BASE_URL}.</p>`;
        }
    }

    function renderEvents(events) {
        eventsListContainer.innerHTML = ''; // Clear previous events
        if (events.length === 0) {
            eventsListContainer.innerHTML = '<p class="text-muted">No events found. Add a new event above or chat with Kairo!</p>';
            return;
        }

        events.forEach(event => {
            const eventElement = document.createElement('div');
            eventElement.classList.add('card', 'event-item');
            eventElement.dataset.eventId = event.event_id;

            const startDt = new Date(event.start_datetime).toLocaleString();
            const endDt = event.end_datetime ? new Date(event.end_datetime).toLocaleString() : 'N/A';

            eventElement.innerHTML = `
                <div class="event-header">
                    <h4 class="event-title">${event.title}</h4>
                </div>
                <p class="event-time">From: ${startDt}</p>
                <p class="event-time">To: ${endDt}</p>
                ${event.location ? `<p class="event-location">Location: ${event.location}</p>` : ''}
                ${event.description ? `<p class="event-description">${event.description}</p>` : ''}
                ${event.attendees ? `<p class="event-attendees">Attendees: ${event.attendees}</p>` : ''}
                <div class="event-actions">
                    <button class="button-secondary edit-event-button" data-id="${event.event_id}">Edit</button>
                    <button class="button-danger delete-event-button" data-id="${event.event_id}">Delete</button>
                </div>
            `;
            eventsListContainer.appendChild(eventElement);
        });
        attachEventEventListeners();
    }

    async function fetchAndRenderCourses() {
        coursesListContainer.innerHTML = '<p class="text-muted">Loading courses...</p>';
        try {
            const response = await fetch(`${API_BASE_URL}/courses?user_id=${userId}`);
            if (!response.ok) {
                let errorMsg = `HTTP error! status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.error || errorData.message || errorMsg;
                } catch (e) { /* Ignore if error response is not JSON */ }
                throw new Error(errorMsg);
            }
            if (response.status === 204) {
                renderCourses([]);
                return;
            }
            const data = await response.json();
            renderCourses(data.courses || []);
        } catch (error) {
            console.error('Error fetching courses:', error);
            coursesListContainer.innerHTML = `<p class="text-error">Failed to load courses: ${error.message}. Please ensure your backend server is running and accessible at ${API_BASE_URL}.</p>`;
        }
    }

    function renderCourses(courses) {
        coursesListContainer.innerHTML = ''; // Clear previous courses
        if (courses.length === 0) {
            coursesListContainer.innerHTML = '<p class="text-muted">No courses found. Add a new course above or chat with Kairo!</p>';
            return;
        }

        courses.forEach(course => {
            const courseElement = document.createElement('div');
            courseElement.classList.add('card', 'course-item');
            courseElement.dataset.courseId = course.course_id;

            const startDate = course.start_date ? new Date(course.start_date).toLocaleDateString() : 'N/A';
            const endDate = course.end_date ? new Date(course.end_date).toLocaleDateString() : 'N/A';

            courseElement.innerHTML = `
                <div class="course-header">
                    <h4 class="course-name">${course.name}</h4>
                </div>
                ${course.instructor ? `<p class="course-instructor">Instructor: ${course.instructor}</p>` : ''}
                ${course.schedule ? `<p class="course-schedule">Schedule: ${course.schedule}</p>` : ''}
                <p class="course-dates">Dates: ${startDate} - ${endDate}</p>
                ${course.description ? `<p class="course-description">${course.description}</p>` : ''}
                <div class="course-actions">
                    <button class="button-secondary edit-course-button" data-id="${course.course_id}">Edit</button>
                    <button class="button-danger delete-course-button" data-id="${course.course_id}">Delete</button>
                </div>
            `;
            coursesListContainer.appendChild(courseElement);
        });
        attachCourseEventListeners();
    }

    // --- Dashboard Updates ---
    async function updateDashboard() {
        try {
            const fetchPromises = [
                fetch(`${API_BASE_URL}/tasks?user_id=${userId}`),
                fetch(`${API_BASE_URL}/events?user_id=${userId}`),
                fetch(`${API_BASE_URL}/courses?user_id=${userId}`)
            ];
            const responses = await Promise.all(fetchPromises);

            for (const response of responses) {
                if (!response.ok) {
                    let errorMsg = `HTTP error! status: ${response.status}`;
                    try {
                        const errorData = await response.json();
                        errorMsg = errorData.error || errorData.message || errorMsg;
                    } catch (e) { /* Ignore */ }
                    throw new Error(`Failed to fetch one or more dashboard data components: ${errorMsg}`);
                }
            }

            const [tasksData, eventsData, coursesData] = await Promise.all(
                responses.map(res => res.status === 204 ? null : res.json()) // Handle 204 for .json()
            );
            // Ensure tasks, events, courses are arrays even if data is null (e.g. from 204)
            const tasks = (tasksData && tasksData.tasks) || [];
            const events = (eventsData && eventsData.events) || [];
            const courses = (coursesData && coursesData.courses) || [];

            const pendingTasks = tasks.filter(t => t.status === 'pending').length;
            const now = new Date();
            const upcomingEvents = events.filter(e => new Date(e.start_datetime) > now).length;
            const activeCourses = courses.filter(c =>
                (!c.start_date || new Date(c.start_date) <= now) &&
                (!c.end_date || new Date(c.end_date) >= now)
            ).length;

            dashboardTotalTasks.textContent = tasks.length;
            dashboardPendingTasks.textContent = pendingTasks;
            dashboardUpcomingEvents.textContent = upcomingEvents;
            dashboardActiveCourses.textContent = activeCourses;

            // Simple recent activity display (can be enhanced)
            dashboardRecentActivity.innerHTML = '';
            if (tasks.length > 0 || events.length > 0 || courses.length > 0) {
                const recentItems = [
                    ...tasks.map(t => ({ type: 'Task', title: t.title, date: t.updated_at || t.created_at })),
                    ...events.map(e => ({ type: 'Event', title: e.title, date: e.updated_at || e.created_at })),
                    ...courses.map(c => ({ type: 'Course', title: c.name, date: c.updated_at || c.created_at }))
                ].sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 5); // Get 5 most recent

                if (recentItems.length > 0) {
                    recentItems.forEach(item => {
                        const li = document.createElement('li');
                        // Ensure item.date is valid before creating a Date object
                        const dateString = item.date && !isNaN(new Date(item.date).getTime())
                                           ? new Date(item.date).toLocaleDateString()
                                           : "Date unknown";
                        li.textContent = `${dateString}: ${item.type} "${item.title}" updated.`;
                        dashboardRecentActivity.appendChild(li);
                    });
                } else {
                    dashboardRecentActivity.innerHTML = '<li>No recent activity.</li>';
                }
            } else {
                dashboardRecentActivity.innerHTML = '<li>No recent activity.</li>';
            }

        } catch (error) {
            console.error('Error updating dashboard:', error);
            dashboardRecentActivity.innerHTML = '<li class="text-error">Failed to load dashboard data. Please ensure your backend server is running and accessible at ' + API_BASE_URL + '.</li>';
        }
    }

    // Initial dashboard load
    updateDashboard();

    // --- Task Actions ---

    addTaskButton.addEventListener('click', async () => {
        const title = newTaskTitle.value.trim();
        if (!title) {
            alert('Task title cannot be empty.');
            return;
        }

        const dueDateTime = getFormattedDateTime(newTaskDueDate, newTaskDueTime);

        try {
            const response = await fetch(`${API_BASE_URL}/tasks`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    title: title,
                    description: newTaskDescription.value.trim(),
                    due_datetime: dueDateTime,
                    priority: newTaskPriority.value,
                    status: newTaskStatus.value
                })
            });
            if (!response.ok) {
                let errorMsg = `HTTP error! status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.error || errorData.message || errorMsg;
                } catch (e) { /* Ignore */ }
                throw new Error(errorMsg);
            }
            const result = await response.json();
            alert(result.message || 'Task added successfully!');
            newTaskTitle.value = '';
            newTaskDescription.value = '';
            newTaskDueDate.value = '';
            newTaskDueTime.value = '';
            newTaskPriority.value = 'medium';
            newTaskStatus.value = 'pending';
            fetchAndRenderTasks();
            updateDashboard();
        } catch (error) {
            console.error('Error adding task:', error);
            alert(`Error: ${error.message}. Please ensure your backend server is running and accessible at ${API_BASE_URL}.`);
        }
    });

    function attachTaskEventListeners() {
        document.querySelectorAll('.edit-task-button').forEach(button => {
            button.onclick = (e) => {
                const taskId = e.target.dataset.id;
                openTaskEditModal(taskId);
            };
        });

        document.querySelectorAll('.delete-task-button').forEach(button => {
            button.onclick = async (e) => {
                const taskId = e.target.dataset.id;
                if (confirm('Are you sure you want to delete this task?')) {
                    try {
                        const response = await fetch(`${API_BASE_URL}/tasks/${taskId}?user_id=${userId}`, {
                            method: 'DELETE'
                        });
                        if (!response.ok) {
                            let errorMsg = `HTTP error! status: ${response.status}`;
                            try {
                                const errorData = await response.json(); // Backend sends JSON error for DELETE failure
                                errorMsg = errorData.error || errorData.message || errorMsg;
                            } catch (e) { /* Ignore */ }
                            throw new Error(errorMsg);
                        }
                        // Backend sends JSON success message for DELETE
                        if (response.status !== 204) { // Check if there is content
                             const result = await response.json();
                             alert(result.message || 'Task deleted successfully!');
                        } else {
                            alert('Task deleted successfully!'); // For 204 No Content
                        }
                        fetchAndRenderTasks();
                        updateDashboard();
                    } catch (error) {
                        console.error('Error deleting task:', error);
                        alert(`Error: ${error.message}. Please ensure your backend server is running and accessible at ${API_BASE_URL}.`);
                    }
                }
            };
        });
    }

    async function openTaskEditModal(taskId) {
        try {
            const response = await fetch(`${API_BASE_URL}/tasks?user_id=${userId}`); // Use absolute URL
            const data = await response.json();
            const task = data.tasks.find(t => t.task_id === taskId);

            if (!task) {
                alert('Task not found.');
                return;
            }

            // Create and append a modal div
            const modal = document.createElement('div');
            modal.id = 'edit-task-modal';
            modal.classList.add('modal');
            modal.innerHTML = `
                <div class="modal-content">
                    <span class="close-button">&times;</span>
                    <h3>Edit Task: ${task.title}</h3>
                    <div class="form-group">
                        <label for="edit-task-title">Title</label>
                        <input type="text" id="edit-task-title" value="${task.title || ''}">
                    </div>
                    <div class="form-group">
                        <label for="edit-task-description">Description</label>
                        <textarea id="edit-task-description" rows="3">${task.description || ''}</textarea>
                    </div>
                    <div class="form-group-inline">
                        <div class="form-group">
                            <label for="edit-task-due-date">Due Date</label>
                            <input type="date" id="edit-task-due-date" value="${formatDateForInput(task.due_datetime)}">
                        </div>
                        <div class="form-group">
                            <label for="edit-task-due-time">Due Time</label>
                            <input type="time" id="edit-task-due-time" value="${formatTimeForInput(task.due_datetime)}">
                        </div>
                    </div>
                    <div class="form-group-inline">
                        <div class="form-group">
                            <label for="edit-task-priority">Priority</label>
                            <select id="edit-task-priority">
                                <option value="low" ${task.priority === 'low' ? 'selected' : ''}>Low</option>
                                <option value="medium" ${task.priority === 'medium' ? 'selected' : ''}>Medium</option>
                                <option value="high" ${task.priority === 'high' ? 'selected' : ''}>High</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="edit-task-status">Status</label>
                            <select id="edit-task-status">
                                <option value="pending" ${task.status === 'pending' ? 'selected' : ''}>Pending</option>
                                <option value="in-progress" ${task.status === 'in-progress' ? 'selected' : ''}>In Progress</option>
                                <option value="completed" ${task.status === 'completed' ? 'selected' : ''}>Completed</option>
                                <option value="cancelled" ${task.status === 'cancelled' ? 'selected' : ''}>Cancelled</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="edit-task-tags">Tags (comma-separated)</label>
                        <input type="text" id="edit-task-tags" value="${task.tags || ''}">
                    </div>
                    <button id="save-task-edit" class="button-primary">Save Changes</button>
                </div>
            `;
            document.body.appendChild(modal);

            modal.style.display = 'block';

            modal.querySelector('.close-button').onclick = () => {
                modal.style.display = 'none';
                modal.remove();
            };

            window.onclick = (event) => {
                if (event.target === modal) {
                    modal.style.display = 'none';
                    modal.remove();
                }
            };

            document.getElementById('save-task-edit').onclick = async () => {
                const updatedTitle = document.getElementById('edit-task-title').value.trim();
                if (!updatedTitle) {
                    alert('Task title cannot be empty.');
                    return;
                }

                const updatedDueDateTime = getFormattedDateTime(
                    document.getElementById('edit-task-due-date'),
                    document.getElementById('edit-task-due-time')
                );

                const updates = {
                    title: updatedTitle,
                    description: document.getElementById('edit-task-description').value.trim(),
                    due_datetime: updatedDueDateTime,
                    priority: document.getElementById('edit-task-priority').value,
                    status: document.getElementById('edit-task-status').value,
                    tags: document.getElementById('edit-task-tags').value.trim(),
                };

                try {
                    const response = await fetch(`${API_BASE_URL}/tasks/${taskId}?user_id=${userId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(updates)
                    });
                    if (!response.ok) {
                        let errorMsg = `HTTP error! status: ${response.status}`;
                        try {
                            const errorData = await response.json();
                            errorMsg = errorData.error || errorData.message || errorMsg;
                        } catch (e) { /* Ignore */ }
                        throw new Error(errorMsg);
                    }
                    const result = await response.json();
                    alert(result.message || 'Task updated successfully!');
                    modal.style.display = 'none';
                    modal.remove();
                    fetchAndRenderTasks(); // Refresh list
                    updateDashboard();
                } catch (error) {
                    console.error('Error updating task:', error);
                    alert(`Error: ${error.message}. Please ensure your backend server is running and accessible at ${API_BASE_URL}.`);
                }
            };

        } catch (error) {
            console.error('Error opening task edit modal:', error);
            alert('Could not load task details for editing. Please ensure your backend server is running and accessible at ' + API_BASE_URL + '.');
        }
    }

    // --- Event Actions ---

    addEventButton.addEventListener('click', async () => {
        const title = newEventTitle.value.trim();
        const startDateTime = getFormattedDateTime(newEventStartDate, newEventStartTime);

        if (!title || !startDateTime) {
            alert('Event title and start date/time are required.');
            return;
        }

        const endDateTime = getFormattedDateTime(newEventEndDate, newEventEndTime);

        try {
            const response = await fetch(`${API_BASE_URL}/events`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    title: title,
                    description: newEventDescription.value.trim(),
                    start_datetime: startDateTime,
                    end_datetime: endDateTime,
                    location: newEventLocation.value.trim(),
                    attendees: newEventAttendees.value.trim()
                })
            });
            if (!response.ok) {
                let errorMsg = `HTTP error! status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.error || errorData.message || errorMsg;
                } catch (e) { /* Ignore */ }
                throw new Error(errorMsg);
            }
            const result = await response.json();
            alert(result.message || 'Event added successfully!');
            newEventTitle.value = '';
            newEventDescription.value = '';
            newEventStartDate.value = '';
            newEventStartTime.value = '';
            newEventEndDate.value = '';
            newEventEndTime.value = '';
            newEventLocation.value = '';
            newEventAttendees.value = '';
            fetchAndRenderEvents();
            updateDashboard();
        } catch (error) {
            console.error('Error adding event:', error);
            alert(`Error: ${error.message}. Please ensure your backend server is running and accessible at ${API_BASE_URL}.`);
        }
    });

    function attachEventEventListeners() {
        document.querySelectorAll('.edit-event-button').forEach(button => {
            button.onclick = (e) => {
                const eventId = e.target.dataset.id;
                openEventEditModal(eventId);
            };
        });

        document.querySelectorAll('.delete-event-button').forEach(button => {
            button.onclick = async (e) => {
                const eventId = e.target.dataset.id;
                if (confirm('Are you sure you want to delete this event?')) {
                    try {
                        const response = await fetch(`${API_BASE_URL}/events/${eventId}?user_id=${userId}`, {
                            method: 'DELETE'
                        });
                        if (!response.ok) {
                            let errorMsg = `HTTP error! status: ${response.status}`;
                            try {
                                const errorData = await response.json(); // Backend sends JSON error for DELETE failure
                                errorMsg = errorData.error || errorData.message || errorMsg;
                            } catch (e) { /* Ignore */ }
                            throw new Error(errorMsg);
                        }
                        // Backend sends JSON success message for DELETE
                        if (response.status !== 204) { // Check if there is content
                             const result = await response.json();
                             alert(result.message || 'Event deleted successfully!');
                        } else {
                            alert('Event deleted successfully!'); // For 204 No Content
                        }
                        fetchAndRenderEvents();
                        updateDashboard();
                    } catch (error) {
                        console.error('Error deleting event:', error);
                        alert(`Error: ${error.message}. Please ensure your backend server is running and accessible at ${API_BASE_URL}.`);
                    }
                }
            };
        });
    }

    async function openEventEditModal(eventId) {
        try {
            const response = await fetch(`${API_BASE_URL}/events?user_id=${userId}`); // Use absolute URL
            const data = await response.json();
            const event = data.events.find(e => e.event_id === eventId);

            if (!event) {
                alert('Event not found.');
                return;
            }

            const modal = document.createElement('div');
            modal.id = 'edit-event-modal';
            modal.classList.add('modal');
            modal.innerHTML = `
                <div class="modal-content">
                    <span class="close-button">&times;</span>
                    <h3>Edit Event: ${event.title}</h3>
                    <div class="form-group">
                        <label for="edit-event-title">Title</label>
                        <input type="text" id="edit-event-title" value="${event.title || ''}">
                    </div>
                    <div class="form-group">
                        <label for="edit-event-description">Description</label>
                        <textarea id="edit-event-description" rows="3">${event.description || ''}</textarea>
                    </div>
                    <div class="form-group-inline">
                        <div class="form-group">
                            <label for="edit-event-start-date">Start Date</label>
                            <input type="date" id="edit-event-start-date" value="${formatDateForInput(event.start_datetime)}">
                        </div>
                        <div class="form-group">
                            <label for="edit-event-start-time">Start Time</label>
                            <input type="time" id="edit-event-start-time" value="${formatTimeForInput(event.start_datetime)}">
                        </div>
                    </div>
                    <div class="form-group-inline">
                        <div class="form-group">
                            <label for="edit-event-end-date">End Date</label>
                            <input type="date" id="edit-event-end-date" value="${formatDateForInput(event.end_datetime)}">
                        </div>
                        <div class="form-group">
                            <label for="edit-event-end-time">End Time</label>
                            <input type="time" id="edit-event-end-time" value="${formatTimeForInput(event.end_datetime)}">
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="edit-event-location">Location</label>
                        <input type="text" id="edit-event-location" value="${event.location || ''}">
                    </div>
                    <div class="form-group">
                        <label for="edit-event-attendees">Attendees (comma-separated emails)</label>
                        <input type="text" id="edit-event-attendees" value="${event.attendees || ''}">
                    </div>
                    <button id="save-event-edit" class="button-primary">Save Changes</button>
                </div>
            `;
            document.body.appendChild(modal);

            modal.style.display = 'block';

            modal.querySelector('.close-button').onclick = () => {
                modal.style.display = 'none';
                modal.remove();
            };

            window.onclick = (event) => {
                if (event.target === modal) {
                    modal.style.display = 'none';
                    modal.remove();
                }
            };

            document.getElementById('save-event-edit').onclick = async () => {
                const updatedTitle = document.getElementById('edit-event-title').value.trim();
                const updatedStartDateTime = getFormattedDateTime(
                    document.getElementById('edit-event-start-date'),
                    document.getElementById('edit-event-start-time')
                );

                if (!updatedTitle || !updatedStartDateTime) {
                    alert('Event title and start date/time cannot be empty.');
                    return;
                }

                const updatedEndDateTime = getFormattedDateTime(
                    document.getElementById('edit-event-end-date'),
                    document.getElementById('edit-event-end-time')
                );

                const updates = {
                    title: updatedTitle,
                    description: document.getElementById('edit-event-description').value.trim(),
                    start_datetime: updatedStartDateTime,
                    end_datetime: updatedEndDateTime,
                    location: document.getElementById('edit-event-location').value.trim(),
                    attendees: document.getElementById('edit-event-attendees').value.trim(),
                };

                try {
                    const response = await fetch(`${API_BASE_URL}/events/${eventId}?user_id=${userId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(updates)
                    });
                    if (!response.ok) {
                        let errorMsg = `HTTP error! status: ${response.status}`;
                        try {
                            const errorData = await response.json();
                            errorMsg = errorData.error || errorData.message || errorMsg;
                        } catch (e) { /* Ignore */ }
                        throw new Error(errorMsg);
                    }
                    const result = await response.json();
                    alert(result.message || 'Event updated successfully!');
                    modal.style.display = 'none';
                    modal.remove();
                    fetchAndRenderEvents(); // Refresh list
                    updateDashboard();
                } catch (error) {
                    console.error('Error updating event:', error);
                    alert(`Error: ${error.message}. Please ensure your backend server is running and accessible at ${API_BASE_URL}.`);
                }
            };

        } catch (error) {
            console.error('Error opening event edit modal:', error);
            alert('Could not load event details for editing. Please ensure your backend server is running and accessible at ' + API_BASE_URL + '.');
        }
    }

    // --- Course Actions ---

    addCourseButton.addEventListener('click', async () => {
        const name = newCourseName.value.trim();
        if (!name) {
            alert('Course name cannot be empty.');
            return;
        }

        const startDate = getFormattedDate(newCourseStartDate);
        const endDate = getFormattedDate(newCourseEndDate);

        try {
            const response = await fetch(`${API_BASE_URL}/courses`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    name: name,
                    description: newCourseDescription.value.trim(),
                    instructor: newCourseInstructor.value.trim(),
                    start_date: startDate,
                    end_date: endDate,
                    schedule: newCourseSchedule.value.trim()
                })
            });
            if (!response.ok) {
                let errorMsg = `HTTP error! status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.error || errorData.message || errorMsg;
                } catch (e) { /* Ignore */ }
                throw new Error(errorMsg);
            }
            const result = await response.json();
            alert(result.message || 'Course added successfully!');
            newCourseName.value = '';
            newCourseDescription.value = '';
            newCourseInstructor.value = '';
            newCourseSchedule.value = '';
            newCourseStartDate.value = '';
            newCourseEndDate.value = '';
            fetchAndRenderCourses();
            updateDashboard();
        } catch (error) {
            console.error('Error adding course:', error);
            alert(`Error: ${error.message}. Please ensure your backend server is running and accessible at ${API_BASE_URL}.`);
        }
    });

    function attachCourseEventListeners() {
        document.querySelectorAll('.edit-course-button').forEach(button => {
            button.onclick = (e) => {
                const courseId = e.target.dataset.id;
                openCourseEditModal(courseId);
            };
        });

        document.querySelectorAll('.delete-course-button').forEach(button => {
            button.onclick = async (e) => {
                const courseId = e.target.dataset.id;
                if (confirm('Are you sure you want to delete this course? This will not delete related tasks.')) {
                    try {
                        const response = await fetch(`${API_BASE_URL}/courses/${courseId}?user_id=${userId}`, {
                            method: 'DELETE'
                        });
                        if (!response.ok) {
                            let errorMsg = `HTTP error! status: ${response.status}`;
                            try {
                                const errorData = await response.json(); // Backend sends JSON error for DELETE failure
                                errorMsg = errorData.error || errorData.message || errorMsg;
                            } catch (e) { /* Ignore */ }
                            throw new Error(errorMsg);
                        }
                        // Backend sends JSON success message for DELETE
                        if (response.status !== 204) { // Check if there is content
                             const result = await response.json();
                             alert(result.message || 'Course deleted successfully!');
                        } else {
                            alert('Course deleted successfully!'); // For 204 No Content
                        }
                        fetchAndRenderCourses();
                        updateDashboard();
                    } catch (error) {
                        console.error('Error deleting course:', error);
                        alert(`Error: ${error.message}. Please ensure your backend server is running and accessible at ${API_BASE_URL}.`);
                    }
                }
            };
        });
    }

    async function openCourseEditModal(courseId) {
        try {
            const response = await fetch(`${API_BASE_URL}/courses?user_id=${userId}`); // Use absolute URL
            const data = await response.json();
            const course = data.courses.find(c => c.course_id === courseId);

            if (!course) {
                alert('Course not found.');
                return;
            }

            const modal = document.createElement('div');
            modal.id = 'edit-course-modal';
            modal.classList.add('modal');
            modal.innerHTML = `
                <div class="modal-content">
                    <span class="close-button">&times;</span>
                    <h3>Edit Course: ${course.name}</h3>
                    <div class="form-group">
                        <label for="edit-course-name">Course Name</label>
                        <input type="text" id="edit-course-name" value="${course.name || ''}">
                    </div>
                    <div class="form-group">
                        <label for="edit-course-description">Description</label>
                        <textarea id="edit-course-description" rows="3">${course.description || ''}</textarea>
                    </div>
                    <div class="form-group">
                        <label for="edit-course-instructor">Instructor</label>
                        <input type="text" id="edit-course-instructor" value="${course.instructor || ''}">
                    </div>
                    <div class="form-group">
                        <label for="edit-course-schedule">Schedule</label>
                        <input type="text" id="edit-course-schedule" value="${course.schedule || ''}">
                    </div>
                    <div class="form-group-inline">
                        <div class="form-group">
                            <label for="edit-course-start-date">Start Date</label>
                            <input type="date" id="edit-course-start-date" value="${formatDateForInput(course.start_date)}">
                        </div>
                        <div class="form-group">
                            <label for="edit-course-end-date">End Date</label>
                            <input type="date" id="edit-course-end-date" value="${formatDateForInput(course.end_date)}">
                        </div>
                    </div>
                    <button id="save-course-edit" class="button-primary">Save Changes</button>
                </div>
            `;
            document.body.appendChild(modal);

            modal.style.display = 'block';

            modal.querySelector('.close-button').onclick = () => {
                modal.style.display = 'none';
                modal.remove();
            };

            window.onclick = (event) => {
                if (event.target === modal) {
                    modal.style.display = 'none';
                    modal.remove();
                }
            };

            document.getElementById('save-course-edit').onclick = async () => {
                const updatedName = document.getElementById('edit-course-name').value.trim();
                if (!updatedName) {
                    alert('Course name cannot be empty.');
                    return;
                }

                const updatedStartDate = getFormattedDate(document.getElementById('edit-course-start-date'));
                const updatedEndDate = getFormattedDate(document.getElementById('edit-course-end-date'));

                const updates = {
                    name: updatedName,
                    description: document.getElementById('edit-course-description').value.trim(),
                    instructor: document.getElementById('edit-course-instructor').value.trim(),
                    schedule: document.getElementById('edit-course-schedule').value.trim(),
                    start_date: updatedStartDate,
                    end_date: updatedEndDate,
                };

                try {
                    const response = await fetch(`${API_BASE_URL}/courses/${courseId}?user_id=${userId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(updates)
                    });
                    if (!response.ok) {
                        let errorMsg = `HTTP error! status: ${response.status}`;
                        try {
                            const errorData = await response.json();
                            errorMsg = errorData.error || errorData.message || errorMsg;
                        } catch (e) { /* Ignore */ }
                        throw new Error(errorMsg);
                    }
                    const result = await response.json();
                    alert(result.message || 'Course updated successfully!');
                    modal.style.display = 'none';
                    modal.remove();
                    fetchAndRenderCourses(); // Refresh list
                    updateDashboard();
                } catch (error) {
                    console.error('Error updating course:', error);
                    alert(`Error: ${error.message}. Please ensure your backend server is running and accessible at ${API_BASE_URL}.`);
                }
            };

        } catch (error) {
            console.error('Error opening course edit modal:', error);
            alert('Could not load course details for editing. Please ensure your backend server is running and accessible at ' + API_BASE_URL + '.');
        }
    }


    // --- Kairo AI Chat Integration ---

    async function sendMessageToKairo() {
        const message = chatInput.value.trim();
        if (!message) return;

        addMessageToChat('user', message);
        chatInput.value = '';
        showLoadingSpinner();

        try {
            const response = await fetch(`${API_BASE_URL}/chat`, { // Now consistently using API_BASE_URL
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_id: userId,
                    message: message,
                    kairo_style: currentKairoStyle
                }),
            });

            if (!response.ok) {
                let errorMsg = `HTTP error! status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.error || errorData.message || errorMsg;
                } catch (e) { /* If error response isn't JSON, use the status code message */ }
                throw new Error(errorMsg);
            }

            const data = await response.json();
            addMessageToChat('kairo', data.response);

            // Update relevant views based on parsed_action
            if (data.parsed_action) {
                const actionType = data.parsed_action.action;
                if (actionType.includes('task')) {
                    fetchAndRenderTasks();
                    updateDashboard();
                }
                if (actionType.includes('event')) {
                    fetchAndRenderEvents();
                    updateDashboard();
                }
                if (actionType.includes('course')) {
                    fetchAndRenderCourses();
                    updateDashboard();
                }
            }
            // Always update dashboard after any action that might change counts
            updateDashboard();

        } catch (error) {
            console.error('Error communicating with Kairo AI:', error);
            addMessageToChat('kairo', `I'm sorry, I encountered an error: ${error.message}. Please try again. Ensure your backend server is running and accessible at ${API_BASE_URL}.`);
        } finally {
            hideLoadingSpinner();
        }
    }

    chatSendButton.addEventListener('click', sendMessageToKairo);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessageToKairo();
        }
    });

    // Kairo Style selection
    kairoStyleSelect.addEventListener('change', (e) => {
        currentKairoStyle = e.target.value;
        localStorage.setItem('kairo_style', currentKairoStyle);
        addMessageToChat('kairo', `My response style has been set to "${currentKairoStyle}".`);
    });
    } catch (e) {
        console.error("Critical error during initialization:", e);
        alert("A critical error occurred while initializing the application. Some features may not work. Please check the console for details.");
    }
});