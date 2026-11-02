"""右边栏的内容. 加一页手册或设置,就往 PAGES 里加一项:(标题, shop -> 文字)."""

from game import Bottle, Command, Furnace, Inside, Item, Offer, Shop, credits

GOODS = {
    "battery": "熔炉的能源,一节配一块矿石.",
    "bread": "当天卖得快的主食.",
    "eggs": "按个卖,别摔了.",
    "lighter": "小东西,利润薄.",
    "matches": "最便宜的东西,图个方便.",
    "noodles": "加班的人常来买.",
    "rice": "一袋很贵,卖掉一袋顶好几单.",
    "salt": "家家都要用,不愁卖.",
    "soap": "放不坏的日用品.",
    "tea": "价格高,收的时候看清要价.",
    "tissue": "便宜的日用品.",
    "umbrella": "下雨天才想起来的东西.",
    "ore": "放进熔炉,配一节电池炼成金属锭.",
    "ingot": "矿石炼出来的,比原料值钱.",
}

COMMANDS = {
    "deal": "结算. 客人买:把桌上他要的东西交给他. 客人卖:付钱收下标星的货.",
    "next": "送走当前客人,叫下一位进来.",
    "no": "送走客人,但不叫下一位. 店里空着,可以慢慢收拾桌子.",
    "close": "结束这一天,桌上的东西全部回库存.",
    "open": "开始新的一天.",
    "pay": "交房租. 房东每 7 天来一次,交了才走.",
}

OPERATIONS = """\
打字:搜索命令和物品
↑↓:移动光标,搜索时只在命中项间跳
←→:切换左右两栏
Enter:放上桌;桌上的东西和客人的货是选中
Esc:清空搜索和选中

选中一件后,再 Enter:
- 另一个瓶子:倒过去
- 熔炉:放进去
- 另一件东西:一起选中
- 它自己:放回库存"""

RECIPES = """\
熔炉

矿石 + 电池 = 金属锭

把矿石和电池选中,Enter 熔炉放进去,再 Enter 熔炉熔炼. 一次炼完所有能配对的.

产物留在炉里,移动光标到它上面 Enter 取出."""


def _describe_goods(thing: Item | Bottle | Furnace, shop: Shop) -> list[str]:
    if isinstance(thing, Bottle):
        inside = f"里面:{thing.liquid.name} {thing.ml}ml" if thing.liquid else "里面:空的"
        return [f"瓶子,容量 {thing.capacity}ml", inside, f"连瓶售价 {credits(thing.price)}"]
    if isinstance(thing, Furnace):
        names = ", ".join(item.name for item in thing.contents)
        return ["熔炉", f"里面:{names or '空的'}", '配方见"配方"页']
    return [thing.name, f"售价 {credits(thing.price)},库存 {shop.stock[thing.key]}", GOODS[thing.key]]


def describe(shop: Shop) -> str:
    entry = shop.current
    if entry is None:
        return "光标没有停在东西上."
    if isinstance(entry, Command):
        lines = [entry.name, COMMANDS[entry.key]]
    elif isinstance(entry, Offer):
        lines = [*_describe_goods(entry.item, shop), f"客人要价 {credits(entry.ask)}"]
    elif isinstance(entry, Inside):
        lines = [f"{entry.item.name},在熔炉里", GOODS[entry.item.key]]
    else:
        lines = _describe_goods(entry, shop)
    return "\n".join([*lines, "", f"Enter:{shop.enter_action}"])


PAGES = [
    ("说明", describe),
    ("操作", lambda shop: OPERATIONS),
    ("配方", lambda shop: RECIPES),
]
