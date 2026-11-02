"""不开浏览器,直接按键驱动真实的 ShopApp 并读屏幕. 运行:uv run test_tui.py [-v]"""

import asyncio
import random
import sys

from game import (
    BEER, CATALOG, COLA, MILK, RENT, RENT_EVERY, WATER, Bottle, Command, Customer, Furnace, Item, Offer, Shop,
)
from tui import ShopApp

ITEMS = {item.key: item for item in CATALOG}
VERBOSE = "-v" in sys.argv
OFFERS = (Offer(ITEMS["soap"], 3), Offer(ITEMS["tea"], 21), Offer(ITEMS["rice"], 200))


def strips(app: ShopApp, selector: str) -> str:
    region = app.query_one(selector).region
    rows = app.screen._compositor.render_strips()
    return "\n".join(strip.crop(region.x, region.right).text.rstrip() for strip in rows)


def screen(app: ShopApp) -> str:
    return strips(app, "#left")


def side(app: ShopApp) -> str:
    return strips(app, "#side")


def above(app: ShopApp) -> str:
    return screen(app).split("╭")[0]


def below(app: ShopApp) -> str:
    return screen(app).split("╰")[1]


def show(app: ShopApp, title: str) -> None:
    if VERBOSE:
        rows = app.screen._compositor.render_strips()
        lines = [strip.text.rstrip() for strip in rows if strip.text.strip()]
        print(f"--- {title}\n" + "\n".join(lines) + "\n")


async def press(pilot, *keys: str) -> None:
    await pilot.press(*keys)
    await pilot.pause()


async def deal(pilot) -> None:
    """搜出 deal 命令再 enter."""
    await press(pilot, "d", "e", "a", "l", "enter")


async def start(app: ShopApp, pilot, customer: Customer | None) -> None:
    app.shop = Shop(random.Random(1))
    app.shop.customer = customer
    app.shop.stock.update(bread=2, salt=2, tea=1)
    app.shop.clear_query()
    app.draw()
    await pilot.pause()


def buyer() -> Customer:
    return Customer("阿姨", "来个面包.", wants=ITEMS["bread"])


def seller() -> Customer:
    return Customer("大爷", "收不收?", offers=OFFERS)


async def test_default_list_order() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, buyer())
        show(app, "默认列表")
        text = below(app)
        order = ["deal", "next", "no ", "close", "battery"]
        assert [text.index(w) for w in order] == sorted(text.index(w) for w in order), text
        assert "英文" not in text and "其他库存" not in text
        rows = text.splitlines()
        close = next(i for i, line in enumerate(rows) if "close" in line)
        assert rows[close + 1].strip() == "" and "battery" in rows[close + 2], rows  # 中间一个空行


async def test_search_filters_commands_and_items() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, buyer())
        await press(pilot, "c")
        show(app, "输入 c")
        text = below(app)
        assert "close" in text and "cola" in text and "deal" not in text
        await press(pilot, "backspace", "d")
        assert "deal" in below(app) and "cola" not in below(app)
        await press(pilot, "backspace", "z")
        assert "没有这个东西" in screen(app)


async def test_buy_flow_stock_to_table_to_customer() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, buyer())
        await press(pilot, "b", "r", "enter")
        show(app, "bread 上桌")
        assert app.shop.table == [ITEMS["bread"]] and app.shop.stock["bread"] == 1
        assert "桌面" in above(app) and "bread" in above(app)
        assert "deal        8点" in screen(app) and app.shop.money == 100
        await deal(pilot)
        show(app, "成交")
        assert app.shop.money == 108 and app.shop.stock["bread"] == 1
        assert app.shop.table == [] and app.shop.customer.name == "阿姨"
        assert "谢了" in screen(app) and "deal" not in screen(app)
        await press(pilot, "enter")  # 光标落在 next 上
        assert app.shop.customer.name != "阿姨"


async def test_enter_on_table_goes_back_to_stock() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, buyer())
        await press(pilot, "b", "r", "enter", "up")
        assert "> bread" in above(app)
        await press(pilot, "enter")
        show(app, "选中 bread")
        assert app.shop.selected == [ITEMS["bread"]] and ">*bread" in above(app)
        assert app.shop.stock["bread"] == 1
        await press(pilot, "enter")  # 对选中的自己再按一次才回库存
        assert app.shop.table == [] and app.shop.stock["bread"] == 2


async def test_escape_drops_selection() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, buyer())
        await press(pilot, "b", "r", "enter", "up", "enter", "escape")
        assert app.shop.selected == [] and app.shop.table == [ITEMS["bread"]]


async def test_wrong_item_stays_on_table() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, buyer())
        await deal(pilot)
        assert "先把东西放上桌" in screen(app)
        await press(pilot, "s", "a", "enter")
        await deal(pilot)
        show(app, "给错货")
        assert "这不是我要的" in screen(app)
        assert app.shop.money == 100 and app.shop.table == [ITEMS["salt"]]
        assert app.shop.customer.wants
        await press(pilot, "b", "r", "enter")
        await deal(pilot)  # 桌上多放别的不碍事
        assert app.shop.money == 108 and app.shop.table == [ITEMS["salt"]]


async def test_seller_goods_are_starred_then_paid() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, seller())
        shop = app.shop
        await deal(pilot)
        assert "先选中要收的货" in screen(app)
        await press(pilot, "enter")
        show(app, "标星一件")
        assert shop.starred == [OFFERS[0]] and shop.cursor == 0
        assert ">*soap" in above(app) and "桌面" not in above(app) and shop.table == []
        await press(pilot, "down", "enter")
        assert shop.starred == [OFFERS[0], OFFERS[1]] and "deal        24点" in screen(app)
        soap = shop.stock["soap"]
        await press(pilot, "up", "enter")  # 再按一次取消标星
        assert shop.starred == [OFFERS[1]] and shop.stock["soap"] == soap and shop.money == 100
        await press(pilot, "enter")
        await deal(pilot)
        show(app, "成交两件")
        assert shop.money == 76 and shop.stock["tea"] == 2 and shop.stock["soap"] == soap + 1
        assert shop.starred == [] and shop.customer.offers == OFFERS[2:]
        await press(pilot, "enter")
        await deal(pilot)
        assert "钱不够" in screen(app) and shop.money == 76 and shop.starred == [OFFERS[2]]
        assert ">*rice" in above(app)


async def test_seller_can_sell_a_filled_bottle() -> None:
    bottle = Bottle(750, BEER, 750)
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, Customer("大爷", "收不收?", offers=(Offer(bottle, 4),)))
        show(app, "收瓶子")
        assert "beer" in above(app) and "750ml" in above(app)
        await press(pilot, "enter")
        await deal(pilot)
        assert app.shop.money == 96 and bottle in app.shop.gear


async def test_unpaid_offer_leaves_with_customer_own_goods_stay() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, seller())
        soap = app.shop.stock["soap"]
        await press(pilot, "enter", "b", "r", "enter", "n", "e", "enter")
        assert app.shop.table == [ITEMS["bread"]] and app.shop.starred == []
        assert app.shop.stock["soap"] == soap and app.shop.money == 100


async def test_search_jumps_to_upper_and_still_lists_stock() -> None:
    offers = (Offer(ITEMS["soap"], 3), Offer(ITEMS["battery"], 4), Offer(ITEMS["bread"], 5))
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, Customer("大爷", "收不收?", offers=offers))
        await press(pilot, "b")
        show(app, "卖东西时输入 b")
        assert "> battery" in above(app)
        assert "battery" in below(app) and "bread" in below(app) and "soap" not in below(app)
        await press(pilot, "enter")
        assert app.shop.starred == [offers[1]] and app.shop.query == "" and app.shop.table == []
        await press(pilot, "b", "r")
        assert "> bread" in above(app)
        await press(pilot, "enter")
        await deal(pilot)
        assert app.shop.money == 91 and app.shop.customer.offers == offers[:1]
        await press(pilot, "z")
        assert "没有这个东西" in screen(app)
        await press(pilot, "backspace", "d")  # 上面没命中,落回下面第一条
        assert "> deal" in screen(app)


async def test_arrows_only_visit_candidates_while_searching() -> None:
    first, second = Bottle(750), Bottle(2000)  # 空瓶才叫 bottle
    offers = (Offer(first, 2), Offer(ITEMS["soap"], 3), Offer(second, 1))
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, Customer("大爷", "收不收?", offers=offers))
        await press(pilot, "b", "o")
        show(app, "卖东西时搜 bo")
        assert app.shop.cursor == 0
        await press(pilot, "down")  # 跳过没命中的 soap
        assert app.shop.cursor == 2
        await press(pilot, "down")
        show(app, "下键跳到下面")
        assert app.shop.cursor == 3 and "> bottle" in below(app)
        await press(pilot, "up", "up")
        assert app.shop.cursor == 0
        await press(pilot, "up")  # 到头就停
        assert app.shop.cursor == 0
        await press(pilot, "escape", "down")  # 搜索框空了,上下恢复逐行走
        assert app.shop.cursor == 1


async def test_search_keeps_commands_apart_from_goods() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, buyer())
        await press(pilot, "b")
        assert "close" not in below(app)
        await press(pilot, "backspace", "c")
        show(app, "搜 c")
        rows = below(app).splitlines()
        close = next(i for i, line in enumerate(rows) if "close" in line)
        assert rows[close + 1].strip() == "" and "cola" in rows[close + 2], rows


async def test_deal_by_typing() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, seller())
        await press(pilot, "enter", "d", "e", "enter")
        assert app.shop.money == 97 and app.shop.query == ""


async def test_table_columns_line_up() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 70)) as pilot:
        await start(app, pilot, buyer())
        await press(pilot, "b", "r", "enter")
        lines = screen(app).splitlines()
        columns = {next(line for line in lines if word in line).index(word) for word in ("bread", "salt")}
        assert len(columns) == 1, columns
        salt = next(line for line in lines if "salt" in line).split()
        assert salt == ["salt", "4点", "2", "盐"], salt


async def test_no_sends_customer_away_without_next() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, buyer())
        await press(pilot, "n", "o")
        assert "打发走" in screen(app) and "noodles" in screen(app)
        await press(pilot, "enter")
        show(app, "no 之后")
        assert "阿姨走了" in screen(app) and app.shop.customer is None
        assert "没有客人" in screen(app) and "deal" not in screen(app)
        await press(pilot, "n", "e", "enter")
        assert app.shop.customer is not None


async def landlord_day(app: ShopApp, pilot, money: int) -> None:
    await start(app, pilot, buyer())
    app.shop.day = RENT_EVERY - 1
    app.shop.money = money
    await press(pilot, "c", "l", "enter", "o", "enter")


async def test_landlord_comes_every_seventh_day_and_only_takes_rent() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await landlord_day(app, pilot, 300)
        show(app, "房东来收租")
        assert "房东" in screen(app) and f"交 {RENT} 信用点" in screen(app)
        assert [c.key for c in app.shop.results if isinstance(c, Command)] == ["pay"]
        await press(pilot, "n", "e", "x", "t", "enter")
        assert app.shop.customer.name == "房东"  # 不交不走
        await press(pilot, "escape", "p", "a", "y", "enter")
        show(app, "交完房租")
        assert app.shop.money == 100 and "交了房租" in screen(app)
        assert "pay" not in screen(app) and "next" in screen(app)
        await press(pilot, "n", "e", "x", "t", "enter")
        assert app.shop.customer.name != "房东"


async def test_rent_goes_into_debt_when_short() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await landlord_day(app, pilot, 50)
        await press(pilot, "p", "a", "enter")
        assert app.shop.money == 50 - RENT and "欠着 150 信用点" in screen(app)


async def test_filled_bottle_is_one_row_named_by_contents() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, buyer())
        await press(pilot, "c", "o", "l")
        show(app, "瓶装可乐")
        rows = [line for line in below(app).splitlines()[1:] if line.strip()]
        assert len(rows) == 1 and rows[0].split()[1:] == ["cola", "15点", "2000ml", "可乐", "容量", "2000ml"], rows


async def test_search_water_or_bottle_without_clutter() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, buyer())
        await press(pilot, "w", "a")
        show(app, "搜 water")
        rows = [line for line in below(app).splitlines()[1:] if line.strip()]
        assert len(rows) == 2 and all("water" in r for r in rows), rows
        assert rows[0].split()[-4:] == ["2000ml", "水", "容量", "2000ml"], rows
        assert rows[1].split()[-4:] == ["750ml", "水", "容量", "750ml"], rows
        await press(pilot, "escape", "b", "o", "t")
        show(app, "搜 bottle")
        rows = [line for line in below(app).splitlines()[1:] if line.strip()]
        assert [r[2:].split() for r in rows] == [  # 去掉行首的光标和选中标记
            ["bottle", "2点", "1", "空瓶", "容量", "2000ml"],
            ["bottle", "1点", "2", "空瓶", "容量", "750ml"],  # 两个 750ml 空瓶合成一行
        ], rows
        gear = len(app.shop.gear)
        await press(pilot, "down", "enter")  # 从合并的那行拿走一个
        assert len(app.shop.gear) == gear - 1 and app.shop.empty_bottles(750) == 1
        assert "空瓶  容量 750ml" in above(app)
        await press(pilot, "b", "o", "t")
        rows = [line for line in below(app).splitlines()[1:] if line.strip()]
        assert rows[1][2:].split()[:3] == ["bottle", "1点", "1"], rows
        await press(pilot, "escape", "水")
        assert len([line for line in below(app).splitlines()[1:] if line.strip()]) == 2
        app.shop.gear = [Bottle(750)]
        await press(pilot, "escape", "c", "o", "l")
        assert "没有这个东西" in screen(app)  # 没有瓶子装,就没有可乐


async def bottles_on_table(app: ShopApp, pilot) -> tuple[Bottle, Bottle]:
    """打发走客人,把 2000ml 的水和 750ml 的空瓶摆上桌."""
    await press(pilot, "n", "o", "enter")
    shop = app.shop
    big, small = shop.gear[0], shop.gear[6]
    assert (big.liquid, big.ml, small.liquid, small.capacity) == (WATER, 2000, None, 750)
    shop._put_on_table(big)
    shop._put_on_table(small)
    shop.clear_query()
    app.draw()
    await pilot.pause()
    return big, small


async def test_pour_by_selecting_source_then_target() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, buyer())
        big, small = await bottles_on_table(app, pilot)
        show(app, "两个瓶子上桌")
        await press(pilot, "up", "up", "enter")
        show(app, "选中大瓶")
        assert app.shop.selected == [big] and ">*water" in above(app)
        await press(pilot, "down", "enter")
        show(app, "倒过去")
        assert (big.ml, small.liquid, small.ml) == (1250, WATER, 750)
        assert "倒了 750ml 水" in screen(app) and app.shop.selected == []
        assert "> water" in above(app) and "750ml" in above(app)  # 光标留在目标上
        assert "1250ml" in above(app)
        app.shop.table = [small]
        app.shop.gear.append(big)
        app.shop.customer = Customer("大爷", "来个2000ml水.", wants=WATER, ml=2000)
        await deal(pilot)
        assert "这不是我要的" in screen(app) and app.shop.table == [small]
        app.shop.customer = Customer("大爷", "来个750ml水.", wants=WATER, ml=750)
        await deal(pilot)
        assert app.shop.money == 104 and app.shop.table == [] and small not in app.shop.gear


async def test_pour_works_with_customer_waiting() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, buyer())
        big, small = app.shop.gear[0], app.shop.gear[6]
        app.shop._put_on_table(big)
        app.shop._put_on_table(small)
        app.shop.clear_query()
        await press(pilot, "up", "up", "enter", "down", "enter")
        assert (big.ml, small.ml) == (1250, 750) and app.shop.customer.name == "阿姨"


async def test_bottle_on_table_returns_to_stock() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, buyer())
        big, small = await bottles_on_table(app, pilot)
        assert big not in app.shop.gear
        await press(pilot, "up", "up", "enter", "enter")
        assert app.shop.table == [small] and big in app.shop.gear


async def pour(app: ShopApp, pilot, source: Bottle, target: Bottle) -> None:
    app.shop.table = [source, target]
    app.shop.selected = [source]
    app.shop.cursor = 1
    await press(pilot, "enter")


async def test_pour_refuses_bad_moves() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, None)
        full = Bottle(2000, WATER, 2000)
        await pour(app, pilot, full, Bottle(750, WATER, 750))
        assert "满了" in screen(app) and full.ml == 2000
        await pour(app, pilot, Bottle(750), full)
        assert "空的" in screen(app)
        cola = Bottle(750, COLA, 100)
        await pour(app, pilot, cola, Bottle(2000, MILK, 100))
        assert "不能混" in screen(app) and cola.ml == 100
        drained = Bottle(750, MILK, 100)
        await pour(app, pilot, drained, Bottle(750))
        assert drained.liquid is None and drained.ml == 0  # 倒空后变回空瓶


async def furnace_on_table(app: ShopApp, pilot) -> Furnace:
    """桌上依次摆矿石, 电池, 熔炉."""
    shop = app.shop
    furnace = next(g for g in shop.gear if isinstance(g, Furnace))
    shop._put_on_table(ITEMS["ore"])
    shop._put_on_table(ITEMS["battery"])
    shop._put_on_table(furnace)
    shop.clear_query()
    app.draw()
    await pilot.pause()
    return furnace


async def test_furnace_load_smelt_and_take_out() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, None)
        shop = app.shop
        furnace = await furnace_on_table(app, pilot)
        show(app, "摆上桌")
        await press(pilot, "up", "up", "up", "enter", "down", "enter")
        show(app, "选中矿石和电池")
        assert shop.selected == [ITEMS["ore"], ITEMS["battery"]]
        assert "*" not in below(app)  # 库存里同名的东西不跟着标记
        await press(pilot, "down", "enter")
        show(app, "放进熔炉")
        assert shop.table == [furnace] and furnace.contents == [ITEMS["ore"], ITEMS["battery"]]
        assert "- ore" in above(app) and "- battery" in above(app) and "enter 熔炼" in above(app)
        table = above(app).splitlines()
        rows = [next(line for line in table if word in line) for word in ("furnace", "- ore", "- battery")]
        assert len({line.index(price) for line, price in zip(rows, ("50点", "6点", "10点"))}) == 1, rows  # 价格列对齐
        await press(pilot, "enter")
        show(app, "熔炼")
        assert furnace.contents == [ITEMS["ingot"]] and "炼出 1 块金属锭" in screen(app)
        await press(pilot, "down")
        assert ">" in above(app) and app.shop.upper[app.shop.cursor].item == ITEMS["ingot"]
        await press(pilot, "enter")
        show(app, "产物上桌")
        assert shop.table == [furnace, ITEMS["ingot"]] and furnace.contents == []
        await press(pilot, "up", "enter", "enter")
        assert shop.table == [furnace] and shop.stock["ingot"] == 1


async def test_smelting_needs_ore_and_battery() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, None)
        furnace = await furnace_on_table(app, pilot)
        furnace.contents = [ITEMS["ore"]]
        app.shop.table = [furnace]
        app.shop.clear_query()
        await press(pilot, "up", "up", "enter")
        assert "要有矿石和电池" in screen(app) and furnace.contents == [ITEMS["ore"]]


async def test_only_solids_go_into_furnace() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, None)
        furnace = next(g for g in app.shop.gear if isinstance(g, Furnace))
        bottle = app.shop.gear[0]
        app.shop.table = [bottle, furnace]
        app.shop.selected = [bottle]
        app.shop.cursor = 1
        await press(pilot, "enter")
        assert "只有固体" in screen(app) and furnace.contents == [] and bottle in app.shop.table


async def test_search_finds_things_inside_furnace() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, None)
        furnace = next(g for g in app.shop.gear if isinstance(g, Furnace))
        furnace.contents = [ITEMS["ingot"]]
        await press(pilot, "i", "n", "g")
        show(app, "搜 ingot")
        assert "furnace" in below(app) and "- ingot" in below(app)
        await press(pilot, "down", "enter")  # 炉子在库存里也能直接取出
        assert app.shop.table == [ITEMS["ingot"]] and furnace.contents == []


async def test_close_returns_table_to_stock_and_open() -> None:
    app = ShopApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await start(app, pilot, buyer())
        await press(pilot, "b", "r", "enter", "c", "l", "enter")
        show(app, "打烊")
        assert not app.shop.is_open and "打烊" in screen(app)
        assert app.shop.table == [] and app.shop.stock["bread"] == 2
        await press(pilot, "o", "enter")
        assert app.shop.is_open and "第 2 天" in screen(app)


async def test_long_list_scrolls_with_cursor() -> None:
    app = ShopApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await start(app, pilot, buyer())
        app.shop.stock.update({key: 3 for key in ITEMS})
        app.draw()
        await pilot.pause()
        assert "还有" in screen(app)
        await press(pilot, *["down"] * 25)
        show(app, "滚到底")
        assert "> water" in screen(app), screen(app)
        await press(pilot, *["up"] * 25)
        assert "> deal" in screen(app), screen(app)


async def test_box_stays_centered() -> None:
    for size in [(100, 30), (80, 24), (200, 60), (120, 25)]:
        app = ShopApp()
        async with app.run_test(size=size) as pilot:
            await start(app, pilot, seller())
            box = app.query_one("#box").region
            split = app.query_one("#split").region
            assert abs(box.y - (size[1] - box.bottom)) <= 1, size
            assert abs(split.x - (size[0] - split.right)) <= 1, size  # 左右两栏合起来居中
            await press(pilot, "c")
            assert app.query_one("#box").region == box, size


async def test_side_describes_what_is_under_the_cursor() -> None:
    app = ShopApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await start(app, pilot, buyer())
        show(app, "分栏:光标在 deal")
        assert "付钱收下标星的货" in side(app) and "Enter:成交" in side(app)
        await press(pilot, "b", "r")
        show(app, "分栏:光标在 bread")
        assert "面包" in side(app) and "Enter:放上桌" in side(app)
        await press(pilot, "enter", "up")
        assert "Enter:选中" in side(app)
        await press(pilot, "enter")
        assert "Enter:放回库存" in side(app)


async def test_side_tells_what_enter_does_on_bottles_and_furnace() -> None:
    app = ShopApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await start(app, pilot, None)
        shop = app.shop
        big, small = shop.gear[0], shop.gear[6]
        shop._put_on_table(big)
        shop._put_on_table(small)
        shop.clear_query()
        await press(pilot, "up", "up")
        assert "容量 2000ml" in side(app) and "水 2000ml" in side(app) and "Enter:选中" in side(app)
        await press(pilot, "enter", "down")
        assert "Enter:倒过来" in side(app)
        await press(pilot, "escape")
        shop.table = [ITEMS["ore"], next(g for g in shop.gear if isinstance(g, Furnace))]
        shop.gear = [g for g in shop.gear if not isinstance(g, Furnace)]
        shop.selected = [ITEMS["ore"]]
        shop.cursor = 1
        app.draw()
        await pilot.pause()
        assert "Enter:放进熔炉" in side(app)
        await press(pilot, "enter")
        assert "矿石" in side(app) and "放进熔炉" not in side(app)


async def test_side_explains_customer_offer() -> None:
    app = ShopApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await start(app, pilot, seller())
        assert "客人要价 3 信用点" in side(app) and "Enter:选中" in side(app)
        await press(pilot, "enter")
        assert app.shop.current == OFFERS[0] and "Enter:取消选中" in side(app)


async def test_every_row_can_be_described() -> None:
    app = ShopApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await start(app, pilot, buyer())
        furnace = next(g for g in app.shop.gear if isinstance(g, Furnace))
        furnace.contents = [ITEMS["ingot"]]
        app.draw()
        await pilot.pause()
        for _ in range(35):
            assert "Enter:" in side(app), side(app)
            await press(pilot, "down")


async def test_left_right_switches_panes_and_pages() -> None:
    app = ShopApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await start(app, pilot, buyer())
        cursor = app.shop.cursor
        await press(pilot, "right")
        assert app.side_active and "> 说明" in side(app)
        await press(pilot, "down")
        show(app, "右栏:操作页")
        assert "> 操作" in side(app) and "切换左右两栏" in side(app)
        assert app.shop.cursor == cursor  # 上下只动右边
        await press(pilot, "down", "down")
        assert "> 配方" in side(app) and "矿石 + 电池" in side(app)
        await press(pilot, "enter")  # 右边按 enter 不碰左边
        assert app.shop.table == [] and app.shop.customer.wants
        await press(pilot, "left")
        show(app, "回到左边")
        assert not app.side_active and app.page == 0 and "矿石 + 电池" not in side(app)
        assert "Enter:成交" in side(app)
        await press(pilot, "down")  # 右边重新跟着光标走
        assert app.shop.cursor == cursor + 1 and "下一个客户" in side(app)


async def test_side_is_vertically_centered_without_divider() -> None:
    app = ShopApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await start(app, pilot, buyer())
        heights = []
        for keys in ([], ["right", "down"]):  # 说明页短,操作页长
            await press(pilot, *keys)
            rows = side(app).splitlines()
            filled = [i for i, line in enumerate(rows) if line.strip()]
            middle = (filled[0] + filled[-1]) / 2
            assert abs(middle - (len(rows) - 1) / 2) <= 1, (middle, len(rows))
            heights.append(filled[-1] - filled[0])
        assert heights[1] > heights[0]  # 内容多了,往上下两边扩
        assert "│" not in strips(app, "#split").replace("│ ", "").split("╰")[-1]


async def test_buyer_line_shows_key_to_type() -> None:
    app = ShopApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.shop = Shop(random.Random(5))
        seen = set()
        for _ in range(40):
            customer = app.shop.customer
            if customer.wants:
                wants = customer.wants
                assert f"{wants.name}[{wants.key}]" in customer.line, customer.line
                if customer.ml:
                    assert f"{customer.ml}ml{wants.name}[{wants.key}]" in customer.line
                seen.add(bool(customer.ml))
            app.shop._next_customer()
        assert seen == {True, False}, seen  # 固体和液体都见过
        app.shop.customer = Customer("阿姨", "老板,拿个雨伞[umbrella].", wants=ITEMS["umbrella"])
        app.draw()
        await pilot.pause()
        show(app, "台词带英文名")
        assert '"老板,拿个雨伞[umbrella]."' in screen(app)


async def test_typing_on_side_goes_back_to_search() -> None:
    app = ShopApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await start(app, pilot, buyer())
        await press(pilot, "right", "b", "r")
        assert not app.side_active and app.shop.query == "br" and "bread" in below(app)


async def test_narrow_window_hides_side() -> None:
    app = ShopApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await start(app, pilot, buyer())
        await press(pilot, "right")
        assert not app.side_active and not app.query_one("#side").display
        cursor = app.shop.cursor
        await press(pilot, "down")
        assert app.shop.cursor == cursor + 1


async def test_small_window_shows_everything() -> None:
    for size in [(100, 30), (80, 24), (60, 20)]:
        app = ShopApp()
        async with app.run_test(size=size) as pilot:
            await start(app, pilot, seller())
            show(app, f"窗口 {size}")
            text = screen(app)
            for word in ("第 1 天", "大爷", "收不收", "soap", "tea", "rice", "deal", "next"):
                assert word in text, (size, word)


async def test_small_window_keeps_cursor_on_crowded_table() -> None:
    goods = tuple(Offer(Bottle(750, WATER, 750), 2) for _ in range(3))
    app = ShopApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await start(app, pilot, Customer("大爷", "收不收?", offers=goods))
        app.shop.table = [Bottle(750), Bottle(750), Bottle(2000)]  # 客人的货加上桌上的东西
        app.shop.clear_query()
        app.draw()
        await pilot.pause()
        show(app, "小窗口上面堆满")
        app.shop.cursor = len(app.shop.upper)
        for _ in range(6):
            await press(pilot, "up")
            assert ">" in above(app), screen(app)
            assert "大爷" in above(app) and "第 1 天" in above(app), screen(app)


async def test_random_input_never_breaks() -> None:
    app = ShopApp()
    rng = random.Random(3)
    keys = ["up", "down", "enter", "enter", "backspace", "escape", *"abcdeilmnorstuw"]
    async with app.run_test(size=(80, 24)) as pilot:
        for _ in range(300):
            await pilot.press(rng.choice(keys))
            shop = app.shop
            assert shop.money >= 0 and min(shop.stock.values()) >= 0
            gear = shop.gear + [t for t in shop.table if not isinstance(t, Item)]
            bottles = [g for g in gear if isinstance(g, Bottle)]
            assert all(0 <= b.ml <= b.capacity and bool(b.liquid) == bool(b.ml) for b in bottles)
            assert len(set(map(id, gear))) == len(gear)  # 同一件东西不会同时在两处
            assert all(s in shop.table for s in shop.selected), shop.selected
            assert all(o in shop.offers for o in shop.starred), shop.starred
            assert shop.cursor <= len(shop.upper) + len(shop.results), shop.cursor


async def main() -> None:
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    failed = 0
    for test in tests:
        try:
            await test()
            print(f"ok    {test.__name__}")
        except Exception as error:
            failed += 1
            print(f"FAIL  {test.__name__}: {error!r}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
