# user_service.py
class UserService:
    _current_user_id = "local_user" # Default user ID

    @staticmethod
    def get_current_user_id():
        return UserService._current_user_id

    @staticmethod
    def set_current_user_id(user_id):
        # In a more complex app, this might involve login, profile loading, etc.
        UserService._current_user_id = user_id
