from repl.command_handler import dispatch_repl_command, ReplCompleter, REPL_COMMANDS, CmdSignal
from repl.state_manager import create_initial_state, reset_sop_state
from repl.session_manager import (
    create_session_dir,
    write_run_summary,
    save_session,
    load_session,
    list_sessions,
    delete_session,
    generate_session_id,
)
from repl.sop_runner import run_sop_graph
from repl.ui_renderer import (
    print_welcome,
    print_user_message,
    print_agent_message,
    print_command_result,
)
from repl.app_builder import (
    create_input_field,
    create_top_status_bar,
    create_status_bar,
    create_root_container,
    create_layout,
    build_application,
)
from repl.session_picker import (
    create_picker_state,
    get_picker_condition,
    create_picker_control,
    activate_picker,
    deactivate_picker,
    picker_move_up,
    picker_move_down,
    picker_page_left,
    picker_page_right,
    picker_select,
    picker_cancel,
)
from repl.llm_runner import run_llm_node, fmt_elapsed
from repl.compaction_controller import run_chat_compactor, try_auto_compact
from repl.session_controller import (
    save_current_if_dirty,
    restore_session_fields,
    handle_new_session,
    handle_show_picker,
    handle_load_session,
)
from repl.execution_controller import execute_sop_flow
from repl.keybindings import create_keybindings

__all__ = [
    "dispatch_repl_command",
    "ReplCompleter",
    "REPL_COMMANDS",
    "CmdSignal",
    "create_initial_state",
    "reset_sop_state",
    "create_session_dir",
    "write_run_summary",
    "save_session",
    "load_session",
    "list_sessions",
    "delete_session",
    "generate_session_id",
    "run_sop_graph",
    "print_welcome",
    "print_user_message",
    "print_agent_message",
    "print_command_result",
    "create_input_field",
    "create_top_status_bar",
    "create_status_bar",
    "create_root_container",
    "create_layout",
    "build_application",
    "create_picker_state",
    "get_picker_condition",
    "create_picker_control",
    "activate_picker",
    "deactivate_picker",
    "picker_move_up",
    "picker_move_down",
    "picker_page_left",
    "picker_page_right",
    "picker_select",
    "picker_cancel",
    "run_llm_node",
    "fmt_elapsed",
    "run_chat_compactor",
    "try_auto_compact",
    "save_current_if_dirty",
    "restore_session_fields",
    "handle_new_session",
    "handle_show_picker",
    "handle_load_session",
    "execute_sop_flow",
    "create_keybindings",
]

# 向后兼容别名 — main.py 迁移后可移除
_generate_session_id = generate_session_id
