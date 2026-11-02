# probably_typo

一个靠打字玩的杂货铺终端游戏. 输入框固定在屏幕中间, 命令和物品都靠搜索; 客人来买或来卖, 你在柜台后面用键盘做生意, 还能倒水分装, 用熔炉把矿石炼成金属锭.

游戏本体是 Python 写的 TUI ([Textual](https://github.com/Textualize/textual)), 浏览器里通过 [xterm.js](https://github.com/xtermjs/xterm.js) 直接进入, 方便发给别人玩.

## 运行

需要 [uv](https://github.com/astral-sh/uv).

```bash
uv run serve.py
```

会自动打开浏览器进入游戏 (http://127.0.0.1:8765/). 每个标签页是独立的一局. 不想自动打开浏览器就加 `--no-open`.

也可以直接在终端里玩:

```bash
uv run tui.py
```

## 怎么玩

| 按键 | 作用 |
|---|---|
| 打字 | 搜索命令和物品, 比如 `c` 会搜出 `close` 和 `cola` |
| ↑↓ | 移动光标; 搜索时只在命中项之间跳 |
| Enter | 库存的东西放上桌; 客人的货标星; 桌上的东西选中, 再 Enter 另一件就作用过去 |
| ←→ | 切换左边的游戏和右边的说明栏 |
| Esc | 清空搜索和选中 |

- 客人来买: 台词里带着英文名, 比如 `老板,拿个雨伞[umbrella].`, 搜出来放上桌, 再 `deal` 成交.
- 客人来卖: 在他的货上 Enter 标星, 再 `deal` 付钱收下.
- 液体只能装在瓶子里. 选中一个瓶子再 Enter 另一个瓶子, 就把里面的东西倒过去.
- 熔炉: 选中矿石和电池, Enter 熔炉放进去, 再 Enter 熔炉熔炼.
- `no` 送走客人后店里空着, 可以慢慢收拾桌子; `next` 叫下一位.
- 每 7 天开门, 第一个进来的是房东, 只能 `pay` 交 200 信用点, 钱不够就欠着.

## 代码

| 文件 | 内容 |
|---|---|
| `game.py` | 游戏规则, 不碰界面 |
| `tui.py` | Textual 界面 |
| `manual.py` | 右边栏的说明和手册页 |
| `serve.py` | 把 TUI 放进 pty, 经 WebSocket 接到浏览器 |
| `web/` | xterm.js 页面 |
| `test_tui.py` | 不开浏览器, 按键驱动真实界面并读屏幕的测试 |

跑测试, 加 `-v` 会把每一步的屏幕打印出来:

```bash
uv run test_tui.py -v
```

## 许可证

MIT, 见 [LICENSE](LICENSE). `web/vendor/` 里的 xterm.js 和 addon-fit 同为 MIT, 许可证见 [web/vendor/LICENSE-xterm](web/vendor/LICENSE-xterm).
