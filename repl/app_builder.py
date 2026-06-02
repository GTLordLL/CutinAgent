"""prompt_toolkit 组件工厂。

构建 REPL 的静态 UI 组件（TextArea、Layout、Application 等），
与工作流逻辑（KeyBindings、_handle_input）解耦。
"""

from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit, Window, ConditionalContainer, Dimension
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.filters import Condition
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.history import History
from prompt_toolkit.completion import Completer

from repl.config_manager import get_config


class DialogueHistory(History):
    """从 current_dialogue 列表中提取用户消息作为输入历史。

    自动去重（连续重复消息合并），按时间顺序排列。
    """

    def __init__(self, state: dict):
        super().__init__()
        self.state = state

    def load_history_strings(self) -> list[str]:
        """返回历史输入列表（去重，最近的在最后）。"""
        seen = set()
        result = []
        for m in self.state.get("current_dialogue", []):
            if m.get("role") in ("user", "feedback"):
                content = m.get("content", "")
                if content and content not in seen:
                    seen.add(content)
                    result.append(content)
        return result

    def store_string(self, string: str) -> None:
        """存储由 main.py 的 append 操作负责，此处不重复。"""
        pass


def create_input_field(completer: Completer | None = None,
                       state: dict | None = None) -> TextArea:
    """创建多行用户输入区域。

    - multiline=True 支持换行和自动换行
    - 动态高度：BufferControl 自报内容高度，Dimension(min=1, max=10) 做上下限
    - dont_extend_height=True 确保不占用多余空间，内容减少时自动缩回
    - Escape+Enter 手动换行，Enter 提交（通过 keybindings 处理）
    - 使用 DialogueHistory 从 current_dialogue 提取历史输入
    """
    history = DialogueHistory(state) if state is not None else None

    cfg = get_config()
    ta = TextArea(
        text="",
        multiline=True,
        wrap_lines=True,
        dont_extend_height=True,
        height=Dimension(min=1, max=cfg["input_max_lines"]),
        prompt="> ",
        history=history,
        completer=completer,
        style="class:input",
    )
    # 历史导航状态：由 keybindings 中的 up/down 使用
    ta._state = state          # 指向 current_dialogue
    ta._hist_index = None      # None = 未在导航模式
    ta._hist_saved = ""        # 导航前保存的当前输入文本
    return ta


def create_top_status_bar() -> tuple[FormattedTextControl, dict]:
    """创建顶部状态栏控件（3行：空白 + 运行时动画 + 空白）。

    渲染时从 top_status_data["elapsed"] 确定性计算动画帧：
      - Spinner: "|/-\\" 每 100ms 切换
      - Dots:    ".  ", ".. ", "..." 每 ~333ms 切换
      - Color:   6 色渐变循环，每 1s 切换

    Returns:
        (top_status_control, top_status_data):
          top_status_data["label"] + ["elapsed"] 在执行期间被定时器更新。
    """
    top_status_data = {
        "runtime_text": "",   # 保留兼容
        "label": "",          # 节点名称（非空=运行中）
        "elapsed": 0.0,       # 当前已用秒数
    }

    _SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    _DOTS = ["   ", ".  ", ".. ", "..."]
    _COLORS = [
        "ansired", "ansiyellow", "ansigreen",
        "ansicyan", "ansimagenta", "ansiblue",
    ]

    def _fmt_elapsed(seconds: float) -> str:
        if seconds >= 60:
            m = int(seconds // 60)
            s = int(seconds % 60)
            return f"{m}m{s}s"
        return f"{seconds:.0f}s"

    def _get_top_status():
        label = top_status_data.get("label", "")
        if not label:
            return "\n\n"

        elapsed = top_status_data.get("elapsed", 0.0)

        # 确定性动画帧计算（不存 frame counter）
        spinner_char = _SPINNER[int(elapsed * 10) % len(_SPINNER)]  # 100ms/帧，盲文10帧
        dots_str = _DOTS[int(elapsed * 3) % 4]                      # ~333ms/帧
        color = _COLORS[(int(elapsed) // 5) % len(_COLORS)]          # 5s/帧

        line = f" {spinner_char} {label}{dots_str}  {_fmt_elapsed(elapsed)}"
        return [("", "\n"), (color, line), ("", "\n")]

    return FormattedTextControl(_get_top_status), top_status_data


def create_status_bar(default_text: str = "CutinAgent REPL — /help 查看命令") -> tuple[FormattedTextControl, dict]:
    """创建状态栏控件及其数据字典。

    Returns:
        (status_control, status_data): status_data 是可变字典，
        修改 status_data["text"] 后调用 app.invalidate() 即可刷新显示。
    """
    status_data = {"text": f"  {default_text}  ", "token_info": ""}

    def _get_status():
        line2 = status_data.get("token_info", "")
        if line2:
            return [("fg:ansigray", f"{status_data['text']}\n{line2}")]
        return [("fg:ansigray", status_data["text"])]

    return FormattedTextControl(_get_status), status_data


def create_root_container(input_field: TextArea, top_status_control: FormattedTextControl,
                         top_status_data: dict,
                         bottom_status_control: FormattedTextControl,
                         picker_control: FormattedTextControl = None,
                         picker_filter=None,
                         sop_picker_control: FormattedTextControl = None,
                         sop_picker_filter=None,
                         config_picker_control: FormattedTextControl = None,
                         config_picker_filter=None,
                         command_hint_control: FormattedTextControl = None,
                         command_hint_filter=None) -> HSplit:
    """构建 HSplit 布局，顶部状态栏动态高度。

    布局结构（从上到下）：
        顶部状态栏：有运行时 → height=3；无运行时 → height=1（空白）
        顶部分隔线 (height=1, char="─")
        输入区域 (TextArea)
        底部分隔线 (height=1, char="─")
        底部状态栏 (height=2) / 选择器 / 命令提示 (height=11)
    """
    has_runtime = Condition(lambda: bool(top_status_data.get("label", "")))

    has_picker = picker_control is not None and picker_filter is not None
    has_sop_picker = sop_picker_control is not None and sop_picker_filter is not None
    has_config_picker = config_picker_control is not None and config_picker_filter is not None
    has_command_hint = command_hint_control is not None and command_hint_filter is not None

    # 底部区域：正常状态栏与选择器/命令提示条件切换（互斥）
    if has_picker or has_sop_picker or has_config_picker or has_command_hint:
        # 构建 "任一覆盖层活跃" 的组合过滤器
        any_picker = None
        for f in [picker_filter, sop_picker_filter, config_picker_filter, command_hint_filter]:
            if f is not None:
                any_picker = f if any_picker is None else any_picker | f

        bottom_elements = [
            Window(height=1, char="─"),
            ConditionalContainer(
                content=Window(content=bottom_status_control, height=2, style="class:status"),
                filter=~any_picker,
            ),
        ]
        if has_picker:
            bottom_elements.append(
                ConditionalContainer(
                    content=Window(content=picker_control, height=8, style="class:status"),
                    filter=picker_filter,
                ),
            )
        if has_sop_picker:
            from repl.sop_picker import SOP_PICKER_HEIGHT
            bottom_elements.append(
                ConditionalContainer(
                    content=Window(content=sop_picker_control, height=SOP_PICKER_HEIGHT, style="class:status"),
                    filter=sop_picker_filter,
                ),
            )
        if has_config_picker:
            from repl.config_picker import CONFIG_PICKER_HEIGHT
            bottom_elements.append(
                ConditionalContainer(
                    content=Window(content=config_picker_control, height=CONFIG_PICKER_HEIGHT, style="class:status"),
                    filter=config_picker_filter,
                ),
            )
        if has_command_hint:
            from repl.command_hint import COMMAND_HINT_HEIGHT
            bottom_elements.append(
                ConditionalContainer(
                    content=Window(content=command_hint_control, height=COMMAND_HINT_HEIGHT, style="class:status"),
                    filter=command_hint_filter,
                ),
            )
    else:
        bottom_elements = [
            Window(height=1, char="─"),
            Window(content=bottom_status_control, height=2, style="class:status"),
        ]

    return HSplit([
        ConditionalContainer(
            content=Window(content=top_status_control, height=3, style="class:status"),
            filter=has_runtime,
        ),
        ConditionalContainer(
            content=Window(height=1, char=" "),
            filter=~has_runtime,
        ),
        Window(height=1, char="─"),
        input_field,
        *bottom_elements,
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
