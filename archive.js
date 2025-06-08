// archive.js

// These would ideally be shared from renderer.js or a global config.
// For this workaround, ensure they are accessible or redefine if necessary.
const API_BASE_URL = 'http://127.0.0.1:5000'; // Ensure this is consistent
const userId = "user123"; // Ensure this is consistent

async function fetchAndRenderArchivedTasks() {
    const archivedTasksListContainer = document.getElementById('archived-tasks-list-container');
    if (!archivedTasksListContainer) {
        // If the archive view isn't active, this container might not be found by this script
        // depending on when it runs relative to view switching.
        // console.log('Archived tasks list container not found (likely view not active).');
        return;
    }
    archivedTasksListContainer.innerHTML = '<p class="text-muted">Loading archived tasks...</p>';
    try {
        const response = await fetch(`${API_BASE_URL}/tasks/archived?user_id=${userId}`);
        if (!response.ok) {
            if (response.status === 404) {
                archivedTasksListContainer.innerHTML = '<p class="text-muted">No archived tasks found or feature not yet available.</p>';
                console.warn('Archived tasks endpoint not found or no data.');
                return;
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        renderArchivedTasks(data.archived_tasks || []);
    } catch (error) {
        console.error('Error fetching archived tasks:', error);
        archivedTasksListContainer.innerHTML = '<p class="text-error">Failed to load archived tasks.</p>';
    }
}

function renderArchivedTasks(tasks) {
    const archivedTasksListContainer = document.getElementById('archived-tasks-list-container');
    if (!archivedTasksListContainer) return; // Should exist if fetch was called

    archivedTasksListContainer.innerHTML = '';

    if (!tasks || tasks.length === 0) {
        archivedTasksListContainer.innerHTML = '<p class="text-muted">You have no archived tasks.</p>';
        return;
    }

    tasks.forEach(task => {
        const taskElement = document.createElement('div');
        taskElement.classList.add('card', 'task-item', 'archived-task-item');
        taskElement.dataset.taskId = task.task_id;

        const archivedDate = task.archived_at ? new Date(task.archived_at).toLocaleString() : 'N/A';
        const dueDate = task.due_datetime ? new Date(task.due_datetime).toLocaleString() : 'No due date';

        taskElement.innerHTML = `
            <div class="task-header">
                <h4 class="task-title">${task.title}</h4>
                <span class="task-priority priority-${task.priority}">${task.priority.toUpperCase()}</span>
            </div>
            <p class="task-meta">Originally Due: ${dueDate}</p>
            <p class="task-meta">Archived On: ${archivedDate}</p>
            <p class="task-status status-${task.status}">${task.status.replace(/-/g, ' ').toUpperCase()}</p>
            ${task.description ? `<p class="task-description">${task.description}</p>` : ''}
            <div class="task-actions">
                <span class="text-muted">Archived</span>
            </div>
        `;
        archivedTasksListContainer.appendChild(taskElement);
    });
}

// Alternative B: If modifying showView in renderer.js fails.
// This will be a fallback.
window.addEventListener('hashchange', function() {
    if (window.location.hash === '#archive') {
        console.log('Hash changed to #archive, attempting to load archived tasks.');
        fetchAndRenderArchivedTasks();
    }
});

// If renderer.js's showView is successfully modified, it will call fetchAndRenderArchivedTasks directly.
// If not, the hashchange listener above would be the fallback (uncommented if needed).
