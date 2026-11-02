"""杂货铺的终端界面. 输入框固定在屏幕正中,上下两块各占一半."""

from rich.cells import cell_len
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from game import DEAL, Bottle, Command, Furnace, Inside, Item, Offer, Shop
from manual import PAGES

BG = "#14110f"
INK = "#e8dcc8"
DIM = "#8a7d6b"
ACCENT = "#e0a458"
WIDTH = 56
SIDE_WIDTH = 36
SPLIT_WIDTH = WIDTH + SIDE_WIDTH + 2  # 比这窄就收起右边栏

Line = tuple[int | None, Text]  # shop 光标下标(标题行和子行没有)和这一行的内容


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - cell_len(text))


def row(label: str, under_cursor: bool, picked: bool = False) -> Text:
    mark = "*" if picked else " "
    if under_cursor:
        return Text(pad(f">{mark}{label}", WIDTH), style=f"bold {BG} on {ACCENT}")
    return Text(f" {mark}{label}", style=ACCENT if picked else INK)


def title(text: str) -> Line:
    return (None, Text(f"  {text}", style=DIM))


def columns(key: str, price: str, stock: str, note: str) -> str:
    return f"{pad(key, 12)}{pad(price, 7)}{pad(stock, 12)}{note}"


def goods_label(entry: Item | Bottle | Furnace | Offer, shop: Shop) -> str:
    thing = entry.item if isinstance(entry, Offer) else entry
    if isinstance(thing, Bottle) and thing.liquid:
        # 价格连瓶子一起算,库存列是体积,容量写在说明里
        price, stock = thing.price, f"{thing.ml}ml"
        note = f"{thing.liquid.name}  容量 {thing.capacity}ml"
    elif isinstance(thing, Bottle):
        # 库存里一样大的空瓶合成一行,库存列是个数;桌上和客人手里的是单个
        count = shop.empty_bottles(thing.capacity) if thing in shop.gear else 1
        price, stock, note = thing.price, str(count), f"空瓶  容量 {thing.capacity}ml"
    elif isinstance(thing, Furnace):
        price, stock, note = thing.price, "1", f"{thing.name}  enter 熔炼" if thing.contents else thing.name
    else:
        price, stock, note = thing.price, str(shop.stock[thing.key]), thing.name
    if isinstance(entry, Offer):
        price, note = entry.ask, f"{note}  售价 ¥{thing.price}"
    return columns(thing.key, f"¥{price}", stock, note)


def goods_lines(entry: Item | Bottle | Furnace | Inside | Offer, index: int, shop: Shop) -> list[Line]:
    if isinstance(entry, Inside):
        item = entry.item
        return [(index, row(columns(f"  - {item.key}", f"¥{item.price}", "1", item.name), shop.cursor == index))]
    # 库存里同名的东西不算选中
    picked = index < len(shop.upper) and (entry in shop.selected or entry in shop.starred)
    return [(index, row(goods_label(entry, shop), shop.cursor == index, picked))]


def command_label(command: Command, shop: Shop) -> str:
    if command is DEAL:
        return columns(command.key, f"¥{shop.deal_total}", "", f"{command.name}  tab")
    return columns(command.key, "", "", command.name)


def upper_lines(shop: Shop) -> list[Line]:
    waiting = len(shop.offers)
    lines: list[Line] = []
    for i, entry in enumerate(shop.upper):
        if i == waiting:
            lines.append(title("桌面"))
        lines += goods_lines(entry, i, shop)
    return lines


def lower_lines(shop: Shop) -> list[Line]:
    start = len(shop.upper)
    results = shop.results
    if not results:
        return [title("没有这个东西")]
    lines: list[Line] = []
    for i, entry in enumerate(results):
        if isinstance(entry, Command):
            lines.append((start + i, row(command_label(entry, shop), shop.cursor == start + i)))
            continue
        if i and isinstance(results[i - 1], Command):
            lines.append((None, Text("")))  # 命令和物品之间空一行
        lines += goods_lines(entry, start + i, shop)
    return lines


class Rows(Static):
    """一列行. 放不下时只画光标附近的一段,reserved 是同一栏里别的东西占的行数."""

    def __init__(self, reserved: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.reserved = reserved
        self.first = 0

    def show(self, lines: list[Line]) -> None:
        self.update(Text("\n").join(text for _, text in self._window(lines)))

    def _window(self, lines: list[Line]) -> list[Line]:
        height = self.parent.size.height - self.reserved
        if height <= 1 or len(lines) <= height:
            self.first = 0
            return lines
        height -= 1  # 留一行写"还有多少项"
        cursor = self.app.shop.cursor
        at = next((i for i, (index, _) in enumerate(lines) if index == cursor), None)
        if at is not None:
            above = at - 1 if at and lines[at - 1][0] is None else at  # 标题跟着露出来
            below = at + 1 if at + 1 < len(lines) and lines[at + 1][0] is None else at  # 子行也是
            self.first = max(min(self.first, above), below - height + 1)
        self.first = min(self.first, len(lines) - height)
        rest = len(lines) - self.first - height
        more = Text(f"  ↓ 还有 {rest} 行" if rest else "", style=DIM)
        return lines[self.first : self.first + height] + [(None, more)]

    def on_resize(self) -> None:
        if not self.reserved:
            self.app.draw()


class ShopApp(App):
    ENABLE_COMMAND_PALETTE = False
    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (SPLIT_WIDTH, "-wide")]
    CSS = f"""
    Screen {{ align: center middle; background: {BG}; color: {INK}; }}
    #split {{ width: auto; height: 100%; }}
    #left {{ width: {WIDTH}; height: 100%; }}
    #side {{ width: {SIDE_WIDTH}; height: 100%; margin-left: 2; padding: 0 1; content-align: left middle; }}
    .-narrow #side {{ display: none; }}
    #above, #below {{ width: {WIDTH}; height: 1fr; }}
    #above {{ align-vertical: bottom; }}
    #status {{ dock: top; color: {DIM}; padding: 0 1; }}
    #note {{ color: {DIM}; padding: 0 1; }}
    #talk {{ padding: 0 1 1 1; }}
    #box {{ width: {WIDTH}; height: 3; border: round {ACCENT}; padding: 0 1; }}
    #results {{ height: 100%; }}
    """

    def __init__(self):
        super().__init__()
        self.shop = Shop()
        self.page = 0
        self.side_active = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="split"):
            with Vertical(id="left"):
                with Vertical(id="above"):
                    yield Static(id="status")
                    yield Static(id="note")
                    yield Static(id="talk")
                    yield Rows(reserved=5, id="upper")  # 状态, 提示各一行,对话三行
                yield Static(id="box")
                with Vertical(id="below"):
                    yield Rows(id="results")
            yield Static(id="side")

    def on_mount(self) -> None:
        self.draw()

    def on_key(self, event: events.Key) -> None:
        shop = self.shop
        if self.on_side_key(event.key):
            event.stop()
            event.prevent_default()
            self.draw()
            return
        if event.key == "up":
            shop.move(-1)
        elif event.key == "down":
            shop.move(1)
        elif event.key == "enter":
            shop.enter()
        elif event.key == "tab":
            shop.deal()
        elif event.key == "backspace":
            shop.backspace()
        elif event.key == "escape":
            shop.escape()
        elif event.is_printable and event.character:
            shop.type(event.character)
        else:
            return
        self.leave_side()  # 其余按键都是左边的事,打字也算
        event.stop()
        event.prevent_default()
        self.draw()

    def leave_side(self) -> None:
        """回到左边就回到说明页,让右边重新跟着光标走."""
        self.side_active = False
        self.page = 0

    def on_side_key(self, key: str) -> bool:
        if key == "right":
            self.side_active = self.size.width >= SPLIT_WIDTH
        elif key == "left":
            self.leave_side()
        elif self.side_active and key in ("up", "down"):
            step = 1 if key == "down" else -1
            self.page = max(0, min(len(PAGES) - 1, self.page + step))
        elif not (self.side_active and key == "enter"):
            return False
        return True

    def draw(self) -> None:
        shop = self.shop
        count = sum(shop.stock.values()) + len(shop.gear) + len(shop.table)
        self.query_one("#status", Static).update(f"第 {shop.day} 天   ¥{shop.money}   库存 {count} 件")
        self.query_one("#note", Static).update(Text(shop.note))

        talk = Text()
        if shop.customer:
            talk.append(f"{shop.customer.name}\n", style=f"bold {ACCENT}")
            talk.append(f'"{shop.customer.line}"', style=INK)
        else:
            talk.append("没有客人,可以摆弄桌上的东西." if shop.is_open else "打烊了.", style=DIM)
        self.query_one("#talk", Static).update(talk)

        self.query_one("#upper", Rows).show(upper_lines(shop))

        box = Text(shop.query, style=INK)
        box.append(" ", style=f"on {INK}")
        self.query_one("#box", Static).update(box)

        self.query_one("#results", Rows).show(lower_lines(shop))
        self.draw_side()

    def draw_side(self) -> None:
        side = Text()
        for i, (name, _) in enumerate(PAGES):
            mark = ">" if self.side_active and i == self.page else " "
            side.append(f"{mark} {name}\n", style=ACCENT if i == self.page else DIM)
        side.append("\n")
        side.append(PAGES[self.page][1](self.shop), style=INK)
        self.query_one("#side", Static).update(side)


if __name__ == "__main__":
    ShopApp().run(mouse=False)  # 不接管鼠标,xterm 里才能拖选复制
