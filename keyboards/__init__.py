from .user_kb import (
    no_access_kb, get_id_kb, main_menu_kb, exam_answer_kb,
    confirm_start_kb, confirm_finish_kb, back_to_menu_kb, results_kb,
    errors_nav_kb,
)
from .admin_kb import admin_panel_kb, admin_user_actions_kb, confirm_delete_kb

__all__ = [
    "no_access_kb", "get_id_kb", "main_menu_kb", "exam_answer_kb",
    "confirm_start_kb", "confirm_finish_kb", "back_to_menu_kb", "results_kb",
    "admin_panel_kb", "admin_user_actions_kb", "confirm_delete_kb",
]
