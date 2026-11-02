"""杂货铺的规则. 不碰界面:tui.py 把 Shop 画出来,再把按键传进来."""

import random
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Item:
    key: str
    name: str
    price: int  # 液体是每 750ml 的价


@dataclass(frozen=True)
class Command:
    key: str
    name: str


@dataclass(eq=False)
class Bottle:
    """液体不单独存在,只装在瓶子里. 每个瓶子都是一件实物,哪怕长得一样."""

    capacity: int
    liquid: Item | None = None
    ml: int = 0

    @property
    def key(self) -> str:
        """装了东西就按里面的东西算,只有空瓶才叫 bottle."""
        return self.liquid.key if self.liquid else "bottle"

    @property
    def name(self) -> str:
        return f"{self.liquid.name} {self.capacity}ml瓶" if self.liquid else f"空瓶 {self.capacity}ml"

    @property
    def empty_price(self) -> int:
        return BOTTLE_PRICES[self.capacity]

    @property
    def contents_price(self) -> int:
        return round(self.liquid.price * self.ml / 750) if self.liquid else 0

    @property
    def price(self) -> int:
        return self.empty_price + self.contents_price


@dataclass(eq=False)
class Furnace:
    """机器也是容器,里面能放好几件固体,放进去的和炼出来的都能再拿出来."""

    contents: list[Item] = field(default_factory=list)
    key = "furnace"
    name = "熔炉"
    price = 50


@dataclass(frozen=True)
class Inside:
    """熔炉里的一件东西,在列表里单占一行."""

    machine: Furnace
    item: Item


@dataclass(frozen=True)
class Offer:
    item: Item | Bottle
    ask: int


@dataclass
class Customer:
    name: str
    line: str
    wants: Item | None = None  # 客人来买时才有,成交后清空
    ml: int = 0  # 要的是液体时,要多少
    offers: tuple[Offer, ...] = ()  # 客人来卖时才有,成交一件少一件
    rent: int = 0  # 房东来收租时才有,交了清零


CATALOG = [
    Item("battery", "电池", 10),
    Item("bread", "面包", 8),
    Item("eggs", "鸡蛋", 15),
    Item("lighter", "打火机", 3),
    Item("matches", "火柴", 1),
    Item("noodles", "泡面", 5),
    Item("rice", "大米", 40),
    Item("salt", "盐", 4),
    Item("soap", "肥皂", 6),
    Item("tea", "茶叶", 30),
    Item("tissue", "纸巾", 4),
    Item("umbrella", "雨伞", 25),
]

ORE = Item("ore", "矿石", 6)
INGOT = Item("ingot", "金属锭", 30)
BATTERY = CATALOG[0]
CATALOG += [ORE, INGOT]

WATER = Item("water", "水", 3)
COLA = Item("cola", "可乐", 5)
BEER = Item("beer", "啤酒", 8)
MILK = Item("milk", "牛奶", 7)
LIQUIDS = [WATER, COLA, BEER, MILK]

BOTTLE_PRICES = {750: 1, 2000: 2}


def credits(amount: int) -> str:
    """钱的写法. 表格里挤,只写"点",见 tui.py."""
    return f"{amount} 信用点"


DEAL = Command("deal", "成交")
NEXT = Command("next", "下一个客户")
NO = Command("no", "打发走")
CLOSE = Command("close", "关门")
OPEN = Command("open", "开门")
RENT = 200
RENT_EVERY = 7  # 每 7 天开门第一个进来的是房东
PAY = Command("pay", f"交 {credits(RENT)}")

NAMES = ["阿姨", "大爷", "小学生", "外卖员", "程序员", "保安", "隔壁老板"]
BUY_LINES = ["来个{}.", "有{}吗?我要一个.", "老板,拿个{}.", "急用,{}有没有?"]
SELL_LINES = ["我这儿有几样东西,你收不收?", "家里清出来的,便宜给你.", "收一件也行,看看?"]


def terms(thing: Item | Bottle | Furnace | Command) -> list[tuple[str, str]]:
    if isinstance(thing, Furnace):
        return [(thing.key, thing.name)] + [(i.key, i.name) for i in thing.contents]
    if not isinstance(thing, Bottle):
        return [(thing.key, thing.name)]
    if thing.liquid:
        return [(thing.liquid.key, thing.liquid.name)]
    return [("bottle", "空瓶")]


def expand(entries: list) -> list:
    """熔炉后面跟着它里面的每一件."""
    rows = []
    for entry in entries:
        rows.append(entry)
        if isinstance(entry, Furnace):
            rows += [Inside(entry, item) for item in entry.contents]
    return rows


def matches(entry: Item | Bottle | Furnace | Inside | Offer | Command, query: str) -> bool:
    target = entry.item if isinstance(entry, (Offer, Inside)) else entry
    return any(key.startswith(query) or query in name for key, name in terms(target))


class Shop:
    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.day = 1
        self.money = 100
        self.earned = 0
        self.spent = 0
        self.is_open = True
        self.stock = {item.key: self.rng.randint(0, 3) for item in CATALOG}
        self.stock.update({ORE.key: 3, BATTERY.key: 2, INGOT.key: 0})
        self.gear: list[Bottle | Furnace] = [
            Bottle(2000, WATER, 2000),
            Bottle(2000, COLA, 2000),
            Bottle(750, WATER, 750),
            Bottle(750, BEER, 750),
            Bottle(750, MILK, 750),
            Bottle(2000),
            Bottle(750),
            Bottle(750),
            Furnace(),
        ]
        self.customer: Customer | None = None
        self.table: list[Item | Bottle | Furnace] = []  # 自己的东西,客人买时成交看桌上有什么
        self.selected: list[Item | Bottle | Furnace] = []  # 桌上拿起来, 等着作用到下一件的东西
        self.starred: list[Offer] = []  # 客人的货里标了星, 成交时付钱收下
        self.note = ""
        self.query = ""
        self.cursor = 0  # upper + results 里的下标
        self._next_customer()

    # 光标在一条竖线上走:上面的物品接着下面的列表,输入框一直能打字,不占位置

    @property
    def offers(self) -> list[Offer]:
        return list(self.customer.offers) if self.customer else []

    @property
    def upper(self) -> list:
        return self.offers + expand(self.table)

    @property
    def results(self) -> list:
        query = self.query.strip().lower()
        if not query:
            solid = [i for i in CATALOG if self.stock[i.key]]
            goods = solid + self._stock_gear()
            return self._commands() + expand(sorted(goods, key=lambda g: g.key))
        commands = [c for c in self._commands() if matches(c, query)]
        goods = [g for g in CATALOG + self._stock_gear() if matches(g, query)]
        return sorted(commands, key=lambda c: c.key) + expand(sorted(goods, key=lambda g: g.key))

    def _stock_gear(self) -> list[Bottle | Furnace]:
        """库存里一样大的空瓶只列一行,拿的时候拿其中一个."""
        seen: set[int] = set()
        rows = []
        for thing in self.gear:
            if isinstance(thing, Bottle) and not thing.liquid:
                if thing.capacity in seen:
                    continue
                seen.add(thing.capacity)
            rows.append(thing)
        return rows

    def empty_bottles(self, capacity: int) -> int:
        return sum(1 for g in self.gear if isinstance(g, Bottle) and not g.liquid and g.capacity == capacity)

    @property
    def current(self) -> Item | Bottle | Furnace | Inside | Offer | Command | None:
        rows = self.upper + self.results
        return rows[self.cursor] if self.cursor < len(rows) else None

    @property
    def enter_action(self) -> str:
        """当前这一行按 enter 会发生什么,给右边的说明用."""
        entry = self.current
        if isinstance(entry, Inside):
            return "取出到桌上"
        if isinstance(entry, Offer):
            return "取消选中" if entry in self.starred else "选中"
        if isinstance(entry, Command):
            return entry.name
        return self._use_action(entry) if self.cursor < len(self.upper) else "放上桌"

    @property
    def trading(self) -> bool:
        return bool(self.customer and (self.customer.wants or self.customer.offers))

    @property
    def rent_due(self) -> bool:
        return bool(self.customer and self.customer.rent)

    @property
    def deal_total(self) -> int:
        if self.customer and self.customer.offers:
            return sum(offer.ask for offer in self.starred)
        wanted = self._wanted_on_table()
        return wanted.price if wanted else 0

    def type(self, char: str) -> None:
        if not char.isspace():
            self.query += char.lower()
            self._reset_cursor()

    def backspace(self) -> None:
        self.query = self.query[:-1]
        self._reset_cursor()

    def clear_query(self) -> None:
        self.query = ""
        self._reset_cursor()

    def escape(self) -> None:
        self.selected = []
        self.starred = []
        self.clear_query()

    def move(self, delta: int) -> None:
        upper = self.upper
        rows = self._upper_hits() + list(range(len(upper), len(upper) + len(self.results)))
        ahead = [i for i in rows if (i - self.cursor) * delta > 0]
        if ahead:
            self.cursor = min(ahead) if delta > 0 else max(ahead)

    def enter(self) -> None:
        """客人的货标星;库存的东西放上桌;桌上的东西先选中,再 enter 另一件就作用过去."""
        rows = self.upper + self.results
        if self.cursor >= len(rows):
            return
        picked = rows[self.cursor]
        on_table = self.cursor < len(self.upper)
        if isinstance(picked, Inside):
            self._take_out(picked)
        elif isinstance(picked, Offer):
            self.starred.remove(picked) if picked in self.starred else self.starred.append(picked)
            self.query = ""  # 光标留在这件货上
            return
        elif isinstance(picked, Command):
            self._run(picked)
        elif on_table:
            self._use(picked)
            return
        else:
            self._put_on_table(picked)
        self.clear_query()

    def deal(self) -> None:
        if self.rent_due:
            self._pay_rent()
        elif not self.trading:
            return
        elif self.customer.offers:
            self._buy_offers()
        else:
            self._sell_wanted()
        self.clear_query()

    def _use_action(self, target: Item | Bottle | Furnace) -> str:
        selected = self.selected
        if isinstance(target, Furnace) and selected and target not in selected:
            return "放进熔炉"
        if isinstance(target, Furnace) and target.contents and not selected:
            return "熔炼"
        if target in selected:
            return "取消选中" if len(selected) > 1 else "放回库存"
        if isinstance(target, Bottle) and len(selected) == 1 and isinstance(selected[0], Bottle):
            return "倒过来"
        return "选中"

    def _use(self, target: Item | Bottle | Furnace) -> None:
        self.note = ""
        action = self._use_action(target)
        if action == "放进熔炉":
            self._load(target)
        elif action == "熔炼":
            self._smelt(target)
        elif action == "取消选中":
            self.selected.remove(target)
        elif action == "放回库存":
            self.table.remove(target)
            self._put_back(target)
            self.selected = []
        elif action == "倒过来":
            self._pour(self.selected[0], target)
            self.selected = []
        else:
            self.selected.append(target)
        self.query = ""
        upper = self.upper
        if target in upper:
            self.cursor = upper.index(target)
        else:
            self._reset_cursor()

    def _pour(self, source: Bottle, target: Bottle) -> None:
        amount = min(source.ml, target.capacity - target.ml)
        if not source.ml:
            self.note = "倒出的瓶子是空的."
        elif target.liquid not in (None, source.liquid):
            self.note = "两种液体不能混."
        elif not amount:
            self.note = "接的瓶子满了."
        else:
            self.note = f"倒了 {amount}ml {source.liquid.name}."
            target.liquid = source.liquid
            target.ml += amount
            source.ml -= amount
            if not source.ml:
                source.liquid = None

    def _load(self, furnace: Furnace) -> None:
        solids = [thing for thing in self.selected if isinstance(thing, Item)]
        if len(solids) < len(self.selected):
            self.note = "只有固体能放进熔炉."
        for item in solids:
            self.table.remove(item)
            furnace.contents.append(item)
        self.selected = []

    def _smelt(self, furnace: Furnace) -> None:
        count = min(furnace.contents.count(ORE), furnace.contents.count(BATTERY))
        if not count:
            self.note = "要有矿石和电池才能熔炼."
            return
        for _ in range(count):
            furnace.contents.remove(ORE)
            furnace.contents.remove(BATTERY)
            furnace.contents.append(INGOT)
        self.note = f"炼出 {count} 块{INGOT.name}."

    def _take_out(self, inside: Inside) -> None:
        inside.machine.contents.remove(inside.item)
        self.table.append(inside.item)
        self.note = ""

    def _commands(self) -> list[Command]:
        if not self.is_open:
            return [OPEN]
        if not self.customer:
            return [NEXT, CLOSE]
        if self.rent_due:
            return [PAY]  # 房东不走,也不让关门
        return [DEAL, NEXT, NO, CLOSE] if self.trading else [NEXT, NO, CLOSE]

    def _upper_hits(self) -> list[int]:
        """上面能停的行:搜索时只有命中的才算备选."""
        upper = self.upper
        if not self.query:
            return list(range(len(upper)))
        return [i for i, entry in enumerate(upper) if matches(entry, self.query)]

    def _reset_cursor(self) -> None:
        upper = self.upper
        if self.query:
            # 搜到上面的物品就先落在上面,否则落在下面第一条结果
            self.cursor = next(iter(self._upper_hits()), len(upper))
        elif self.offers:
            self.cursor = 0
        else:
            self.cursor = len(upper)

    def _run(self, command: Command) -> None:
        if command in (DEAL, PAY):
            self.deal()
        elif command is NEXT:
            if self.customer:
                self.note = f"{self.customer.name}走了."
            self._next_customer()
        elif command is NO:
            self.note = f"{self.customer.name}走了."
            self.customer = None
            self.starred = []
        elif command is CLOSE:
            self._close()
        elif command is OPEN:
            self._open()

    def _close(self) -> None:
        self.is_open = False
        self.customer = None
        for thing in self.table:
            self._put_back(thing)
        self.table = []
        self.selected = []
        self.starred = []
        self.note = f"第 {self.day} 天打烊. 进账 {credits(self.earned)},支出 {credits(self.spent)}."

    def _open(self) -> None:
        self.day += 1
        self.earned = self.spent = 0
        self.is_open = True
        self.note = ""
        if self.day % RENT_EVERY:
            self._next_customer()
        else:
            self.customer = Customer("房东", f"七天到了. 租金 {credits(RENT)}.", rent=RENT)
            self.clear_query()

    def _put_on_table(self, thing: Item | Bottle | Furnace) -> None:
        if not self.is_open:
            self.note = "打烊了."
        elif not isinstance(thing, Item):
            self.note = ""
            self.gear.remove(thing)
            self.table.append(thing)
        elif self.stock[thing.key] == 0:
            self.note = f"{thing.name}没货了."
        else:
            self.note = ""
            self.stock[thing.key] -= 1
            self.table.append(thing)

    def _put_back(self, thing: Item | Bottle | Furnace) -> None:
        if isinstance(thing, Item):
            self.stock[thing.key] += 1
        else:
            self.gear.append(thing)

    def _satisfies(self, thing: Item | Bottle) -> bool:
        if isinstance(thing, Bottle):
            return thing.liquid == self.customer.wants and thing.ml == self.customer.ml
        return thing == self.customer.wants

    def _wanted_on_table(self) -> Item | Bottle | None:
        # 这里的 thing 可能是熔炉,但没人买熔炉,_satisfies 恒为假
        if not (self.customer and self.customer.wants):
            return None
        return next((thing for thing in self.table if self._satisfies(thing)), None)

    def _sell_wanted(self) -> None:
        thing = self._wanted_on_table()
        if thing:
            self.table.remove(thing)
            self.selected = [s for s in self.selected if s in self.table]
            self.money += thing.price
            self.earned += thing.price
            self.note = f"+{credits(thing.price)}"
            self.customer.wants = None
            self.customer.line = "谢了."
        elif self.table:
            self.note = f"{self.customer.name}:这不是我要的."
        else:
            self.note = "先把东西放上桌."

    def _buy_offers(self) -> None:
        offers = self.starred
        total = self.deal_total
        if not offers:
            self.note = "先选中要收的货."
            return
        if total > self.money:
            self.note = "钱不够."
            return
        self.money -= total
        self.spent += total
        for offer in offers:
            self._put_back(offer.item)
        self.starred = []
        self.customer.offers = tuple(o for o in self.customer.offers if o not in offers)
        self.customer.line = "谢了,剩下的还收吗?" if self.customer.offers else "谢了."
        self.note = f"-{credits(total)}  收下{', '.join(o.item.name for o in offers)}."

    def _pay_rent(self) -> None:
        rent = self.customer.rent
        self.money -= rent  # 钱不够也得交,先欠着
        self.spent += rent
        self.customer.rent = 0
        self.customer.line = "下个七天再来."
        paid = f"-{credits(rent)}  "
        self.note = paid + ("交了房租." if self.money >= 0 else f"钱不够,欠着 {credits(-self.money)}.")

    def _next_customer(self) -> None:
        self.starred = []  # 上一位的货跟人走,桌上自己的东西留着
        leaving = self.customer.name if self.customer else None
        name = self.rng.choice([n for n in NAMES if n != leaving])
        if self.rng.random() < 0.6:
            wants, ml = self._pick_wanted()
            # 带上英文名,玩家照着打就能搜到
            label = f"{ml}ml{wants.name}[{wants.key}]" if ml else f"{wants.name}[{wants.key}]"
            self.customer = Customer(name, self.rng.choice(BUY_LINES).format(label), wants=wants, ml=ml)
        else:
            # 要价可能比售价还高,收之前得看一眼
            offers = tuple(
                Offer(thing, max(1, round(thing.price * self.rng.uniform(0.4, 1.1))))
                for thing in self._pick_goods()
            )
            self.customer = Customer(name, self.rng.choice(SELL_LINES), offers=offers)
        self.clear_query()

    def _pick_wanted(self) -> tuple[Item, int]:
        in_stock = [item for item in CATALOG if self.stock[item.key]]
        in_stock += [t for t in self.table if isinstance(t, Item)]
        in_stock += [t.liquid for t in self.gear + self.table if isinstance(t, Bottle) and t.liquid]
        pool = in_stock if in_stock and self.rng.random() < 0.85 else CATALOG + LIQUIDS
        wanted = self.rng.choice(pool)
        return wanted, self.rng.choice(list(BOTTLE_PRICES)) if wanted in LIQUIDS else 0

    def _pick_goods(self) -> list[Item | Bottle]:
        goods: list[Item | Bottle] = []
        for item in self.rng.sample(CATALOG, 3):
            if self.rng.random() < 0.6:
                goods.append(item)
                continue
            capacity = self.rng.choice(list(BOTTLE_PRICES))
            liquid = self.rng.choice(LIQUIDS + [None])
            goods.append(Bottle(capacity, liquid, capacity if liquid else 0))
        return goods
