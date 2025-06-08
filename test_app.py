import pytest
import requests
import json
import uuid
import datetime
import re

BASE_URL = "http://localhost:5000" # Assuming Flask app runs on port 5000
# It's good practice to clean up the database before/after tests,
# but for now, we'll rely on unique IDs and specific user_ids for isolation.

USER_ID_1 = "test_user_1"
USER_ID_2 = "test_user_2"

def generate_unique_id(prefix="item"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

def create_task_for_testing(user_id, title="Test Task for Update/Delete", due_date=None, priority="medium", status="pending", description=None):
    """Helper function to create a task and return its ID."""
    if description is None:
        description = "A task created specifically for testing PUT/DELETE."

    task_data = {
        "user_id": user_id,
        "title": title,
        "description": description,
        "due_date": due_date if due_date else (datetime.datetime.now() + datetime.timedelta(days=7)).isoformat(),
        "priority": priority,
        "status": status
    }
    response = requests.post(f"{BASE_URL}/tasks", json=task_data)
    response.raise_for_status() # Raise an exception for HTTP errors
    assert response.status_code == 201
    return response.json()["task_id"]

# --- Tests for POST /tasks (from previous steps, ensure they still pass) ---
def test_add_task_valid_data():
    task_data = {
        "user_id": USER_ID_1,
        "title": "Test Task - Valid",
        "description": "This is a test task.",
        "due_date": "2024-12-31T23:59:59",
        "priority": "high",
        "status": "pending"
    }
    response = requests.post(f"{BASE_URL}/tasks", json=task_data)
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["user_id"] == USER_ID_1
    assert response_data["title"] == "Test Task - Valid"
    assert "task_id" in response_data

def test_add_task_missing_title():
    task_data = {"user_id": USER_ID_1, "description": "Missing title"}
    response = requests.post(f"{BASE_URL}/tasks", json=task_data)
    assert response.status_code == 400
    assert "title is required" in response.json()["error"].lower()

def test_add_task_missing_user_id():
    task_data = {"title": "Missing user_id", "description": "A task."}
    response = requests.post(f"{BASE_URL}/tasks", json=task_data)
    assert response.status_code == 400
    assert "user id is required" in response.json()["error"].lower()

def test_add_task_invalid_priority():
    task_data = {
        "user_id": USER_ID_1,
        "title": "Invalid Priority Task",
        "priority": "urgent" # Invalid
    }
    response = requests.post(f"{BASE_URL}/tasks", json=task_data)
    assert response.status_code == 400
    # Corrected assertion to match app.py
    assert "invalid priority" in response.json()["error"].lower()


def test_add_task_invalid_status():
    task_data = {
        "user_id": USER_ID_1,
        "title": "Invalid Status Task",
        "status": "underway" # Invalid
    }
    response = requests.post(f"{BASE_URL}/tasks", json=task_data)
    assert response.status_code == 400
    # Corrected assertion to match app.py
    assert "invalid status" in response.json()["error"].lower()


def test_add_task_invalid_date_format():
    task_data = {
        "user_id": USER_ID_1,
        "title": "Invalid Date Format Task",
        "due_date": "31-12-2024" # Invalid format
    }
    response = requests.post(f"{BASE_URL}/tasks", json=task_data)
    assert response.status_code == 400
    assert "invalid due_date format" in response.json()["error"].lower()

def test_add_task_date_only_format_post():
    """Test if providing only a date (YYYY-MM-DD) for due_date is handled correctly in POST."""
    task_data = {
        "user_id": USER_ID_1,
        "title": "Date Only Task POST",
        "due_date": "2025-01-15"
    }
    response = requests.post(f"{BASE_URL}/tasks", json=task_data)
    assert response.status_code == 201
    response_data = response.json()
    # app.py's add_task_route now normalizes YYYY-MM-DD to YYYY-MM-DDTHH:MM:SS (end of day)
    assert response_data["due_date"] == "2025-01-15T23:59:59"


# --- Tests for PUT /tasks/<task_id> ---

def test_update_task_valid_full_update():
    task_id = create_task_for_testing(USER_ID_1, title="Original Title for Full Update")
    update_data = {
        "title": "Updated Title",
        "description": "Updated description.",
        "due_date": (datetime.datetime.now() + datetime.timedelta(days=10)).isoformat(),
        "priority": "high",
        "status": "in-progress"
    }
    response = requests.put(f"{BASE_URL}/tasks/{task_id}?user_id={USER_ID_1}", json=update_data)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["message"] == "Task updated successfully"
    updated_task = response_data["task"]
    assert updated_task["title"] == "Updated Title"
    assert updated_task["description"] == "Updated description."
    assert updated_task["priority"] == "high"
    assert updated_task["status"] == "in-progress"
    # Ensure due_date is compared correctly, considering potential microsecond differences if not handled.
    # Storing as ISO string and comparing ISO strings should be fine.
    assert datetime.datetime.fromisoformat(updated_task["due_date"]).replace(microsecond=0) == datetime.datetime.fromisoformat(update_data["due_date"]).replace(microsecond=0)


    # Verify by fetching the task
    get_response = requests.get(f"{BASE_URL}/tasks/{task_id}?user_id={USER_ID_1}")
    assert get_response.status_code == 200
    fetched_task = get_response.json()
    assert fetched_task["title"] == "Updated Title"
    assert fetched_task["status"] == "in-progress"

def test_update_task_partial_update_title():
    task_id = create_task_for_testing(USER_ID_1, title="Original Title for Partial Update")
    update_data = {"title": "Partially Updated Title"}
    response = requests.put(f"{BASE_URL}/tasks/{task_id}?user_id={USER_ID_1}", json=update_data)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["task"]["title"] == "Partially Updated Title"

    get_response = requests.get(f"{BASE_URL}/tasks/{task_id}?user_id={USER_ID_1}")
    assert get_response.json()["title"] == "Partially Updated Title"

def test_update_task_date_only_format_put():
    task_id = create_task_for_testing(USER_ID_1, title="Task for Date Only Update PUT")
    update_data = {"due_date": "2025-08-20"} # YYYY-MM-DD format
    response = requests.put(f"{BASE_URL}/tasks/{task_id}?user_id={USER_ID_1}", json=update_data)
    assert response.status_code == 200
    response_data = response.json()["task"]
    # update_task_in_db (via get_iso_datetime) converts YYYY-MM-DD to YYYY-MM-DDTHH:MM:SS (end of day)
    assert response_data["due_date"] == "2025-08-20T23:59:59"

def test_update_task_non_existent():
    non_existent_task_id = "task_" + uuid.uuid4().hex[:8]
    update_data = {"title": "Attempt to update non-existent task"}
    response = requests.put(f"{BASE_URL}/tasks/{non_existent_task_id}?user_id={USER_ID_1}", json=update_data)
    assert response.status_code == 404
    assert "task not found or access denied" in response.json()["error"].lower()

def test_update_task_wrong_user():
    task_id_user1 = create_task_for_testing(USER_ID_1, title="User1's Task")
    update_data = {"title": "Attempted Update by User2"}
    response = requests.put(f"{BASE_URL}/tasks/{task_id_user1}?user_id={USER_ID_2}", json=update_data)
    assert response.status_code == 404
    assert "task not found or access denied" in response.json()["error"].lower()

    get_response = requests.get(f"{BASE_URL}/tasks/{task_id_user1}?user_id={USER_ID_1}")
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "User1's Task"


def test_update_task_invalid_priority():
    task_id = create_task_for_testing(USER_ID_1)
    update_data = {"priority": "extremely_high"}
    response = requests.put(f"{BASE_URL}/tasks/{task_id}?user_id={USER_ID_1}", json=update_data)
    assert response.status_code == 400
    assert "invalid priority" in response.json()["error"].lower() # Corrected to match app.py

def test_update_task_invalid_status():
    task_id = create_task_for_testing(USER_ID_1)
    update_data = {"status": "stuck"}
    response = requests.put(f"{BASE_URL}/tasks/{task_id}?user_id={USER_ID_1}", json=update_data)
    assert response.status_code == 400
    assert "invalid status" in response.json()["error"].lower() # Corrected to match app.py

def test_update_task_invalid_date_format():
    task_id = create_task_for_testing(USER_ID_1)
    update_data = {"due_date": "tomorrow morning"}
    response = requests.put(f"{BASE_URL}/tasks/{task_id}?user_id={USER_ID_1}", json=update_data)
    assert response.status_code == 400
    assert "invalid due_date format" in response.json()["error"].lower()

def test_update_task_no_user_id_in_query():
    task_id = create_task_for_testing(USER_ID_1)
    update_data = {"title": "No User ID in Query"}
    response = requests.put(f"{BASE_URL}/tasks/{task_id}", json=update_data)
    assert response.status_code == 400
    assert "user id is required as query parameter" in response.json()["error"].lower()

def test_update_task_no_changes():
    original_title = "Task with No Changes"
    original_due_date_str = "2024-10-15T10:00:00"
    original_description = "This is the original description."

    task_id = create_task_for_testing(
        USER_ID_1,
        title=original_title,
        due_date=original_due_date_str,
        description=original_description,
        priority="medium",
        status="pending"
    )

    get_response = requests.get(f"{BASE_URL}/tasks/{task_id}?user_id={USER_ID_1}")
    assert get_response.status_code == 200
    task_as_is = get_response.json()

    update_data_no_change = {
        "title": task_as_is["title"],
        "description": task_as_is.get("description"),
        "due_date": task_as_is.get("due_date"),
        "priority": task_as_is.get("priority"),
        "status": task_as_is.get("status")
    }
    update_data_no_change = {k: v for k, v in update_data_no_change.items() if v is not None}

    response = requests.put(f"{BASE_URL}/tasks/{task_id}?user_id={USER_ID_1}", json=update_data_no_change)
    assert response.status_code == 200
    response_data = response.json()
    # If data (even identical data) is provided, updated_at WILL change, so a successful update message is expected.
    # The "no changes were made" message is for when the input `data` to PUT is empty of updatable fields.
    assert "task updated successfully" in response_data["message"].lower()

    final_get_response = requests.get(f"{BASE_URL}/tasks/{task_id}?user_id={USER_ID_1}")
    assert final_get_response.status_code == 200
    final_task_data = final_get_response.json()

    assert final_task_data["title"] == task_as_is["title"]
    assert final_task_data.get("description") == task_as_is.get("description")
    assert final_task_data.get("due_date") == task_as_is.get("due_date")
    assert final_task_data.get("priority") == task_as_is.get("priority")
    assert final_task_data.get("status") == task_as_is.get("status")


# --- Tests for DELETE /tasks/<task_id> ---

def test_delete_task_valid():
    task_id = create_task_for_testing(USER_ID_1, title="Task to be Deleted")

    get_response_before_delete = requests.get(f"{BASE_URL}/tasks/{task_id}?user_id={USER_ID_1}")
    assert get_response_before_delete.status_code == 200

    delete_response = requests.delete(f"{BASE_URL}/tasks/{task_id}?user_id={USER_ID_1}")
    assert delete_response.status_code == 200
    assert "task deleted successfully" in delete_response.json()["message"].lower()

    get_response_after_delete = requests.get(f"{BASE_URL}/tasks/{task_id}?user_id={USER_ID_1}")
    assert get_response_after_delete.status_code == 404
    assert "task not found" in get_response_after_delete.json()["error"].lower()

def test_delete_task_non_existent():
    non_existent_task_id = "task_" + uuid.uuid4().hex[:8]
    response = requests.delete(f"{BASE_URL}/tasks/{non_existent_task_id}?user_id={USER_ID_1}")
    assert response.status_code == 404
    assert "task not found or access denied" in response.json()["error"].lower()

def test_delete_task_wrong_user():
    task_id_user1 = create_task_for_testing(USER_ID_1, title="User1's Task for Delete Test")

    delete_response = requests.delete(f"{BASE_URL}/tasks/{task_id_user1}?user_id={USER_ID_2}")
    assert delete_response.status_code == 404
    assert "task not found or access denied" in delete_response.json()["error"].lower()

    get_response = requests.get(f"{BASE_URL}/tasks/{task_id_user1}?user_id={USER_ID_1}")
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "User1's Task for Delete Test"

def test_delete_task_no_user_id_in_query():
    task_id = create_task_for_testing(USER_ID_1)
    response = requests.delete(f"{BASE_URL}/tasks/{task_id}")
    assert response.status_code == 400
    assert "user id is required as query parameter" in response.json()["error"].lower()

# To run these tests:
# 1. Ensure your Flask app (app.py) is running (e.g., python app.py).
# 2. Install pytest and requests: pip install pytest requests
# 3. Run from terminal: pytest test_app.py
