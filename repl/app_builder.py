"""prompt_toolkit 组件工厂。

构建 REPL 的静态 UI 组件（TextArea、Layout、Application 等），
与工作流逻辑（KeyBindings、_handle_input）解耦。
"""

from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.completion import Completer


def create_input_field(completer: Completer | None = None) -> TextArea:
    """创建用户输入区域。"""
    return TextArea(
        text="",
        multiline=False,
        prompt="> ",
        history=InMemoryHistory(),
        completer=completer,
        style="class:input",
    )


def create_status_bar(default_text: str = "CutinAgent REPL — /help 查看命令") -> tuple[FormattedTextControl, dict]:
    """创建状态栏控件及其数据字典。

    Returns:
        (status_control, status_data): status_data 是可变字典，
        修改 status_data["text"] 后调用 app.invalidate() 即可刷新显示。
    """
    status_data = {"text": f"  {default_text}  "}

    def _get_status():
        return status_data["text"]

    return FormattedTextControl(_get_status), status_data


def create_root_container(input_field: TextArea, status_control: FormattedTextControl) -> HSplit:
    """构建 5 元素 HSplit 布局。

    布局结构（从上到下）：
        空白行 (height=1, char=" ")
        顶部分隔线 (height=1, char="─")
        输入区域 (TextArea)
        底部分隔线 (height=1, char="─")
        状态栏 (FormattedTextControl)
    """
    return HSplit([
        Window(height=1, char=" "),
        Window(height=1, char="─"),
        input_field,
        Window(height=1, char="─"),
        Window(content=status_control, height=1, style="class:status"),
    ])


def create_layout(root_container: HSplit, input_field: TextArea) -> Layout:
    """创建 Layout，聚焦输入区域。"""
    return Layout(root_container, focused_element=input_field)


def build_application(layout: Layout, keybindings) -> Application:
    """构建 prompt_toolkit Application（非全屏模式）。"""
    return Application(
        layout=layout,
        key_bindings=keybindings,
        full_screen=False,
        erase_when_done=True,
    )
