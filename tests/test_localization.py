"""Display-only tests using the shipped catalog; no research files or game process needed.

Run: python -m unittest tests.test_localization -v (requires lupa.luajit21).
All file I/O, keyboard input and Gui calls below are private in-memory fixtures.
"""
from pathlib import Path
import re
import struct
import unittest
import zipfile

from lupa.luajit21 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'src/tuner/tuner.lua').read_text(encoding='utf-8')


def shipped_source():
    version = (ROOT / 'src/tuner/version.txt').read_text().strip()
    with zipfile.ZipFile(ROOT / 'dist' / ('BYOG-v%s.zip' % version)) as archive:
        data = archive.read('Addon/9ba626afa44a3aa3.patch_0')
    count = struct.unpack_from('<I', data, 8)[0]
    for index in range(count):
        row = 104 + index * 80
        name, kind, offset = struct.unpack_from('<3Q', data, row)
        if name == 0x9337AA4DB4A8A256:
            length, version = struct.unpack_from('<II', data, offset)
            assert kind == 0xA14E8DFA2CD117E2 and version == 2
            return data[offset + 8:offset + 8 + length].decode('utf-8')
    raise AssertionError('BYOG entry not found in the shipped ZIP')


SHIPPED = shipped_source()
DATA = re.search(r'local DATA = \[==\[\n(.*?)\]==\]', SHIPPED, re.S).group(1)

FIXTURE = r'''
local files, draws, down = {}, {}, {}
local WIDTH, HEIGHT, NOW = 1920, 1080, 1
local function pause() end
local function log() end
local function flush_log() end
local function trim(v) return (v:gsub('^%s+', ''):gsub('%s+$', '')) end
local function ensure_out_dir() return 'private' end
local function write_file(name, value) files[name] = value; return true end
local function read_file(name) return files[name] end
local function request_reload() end
local function same_value(_, a, b) return a == b end
local io = {open = function(name)
    local handle = {}
    function handle:write(value) files[name] = value end
    function handle:close() end
    return handle
end}
local config = {menu_key = 'F9', menu_vk = 0x78, sections_open = true, requests = {}}
local overrides, preset_name = {}, 'Default'
local state = {verdict = 'OK - no changes configured'}
local MOD = {version = '2.0.0'}
local A = {key_down = function(vk) return down[vk] or false end,
    now = function() return NOW end, game_window = function() return nil end,
    game_in_front = function() return true end, mkdir = function() return true end,
    list = function() return {'Default.txt'} end}
local S = {Application = {}, World = {}, Gui = {}}
S.Vector2 = function(x,y) return {x=x,y=y} end
S.Vector3 = function(x,y,z) return {x=x,y=y,z=z} end
S.Color = function(a,r,g,b) return {a=a,r=r,g=g,b=b} end
S.Application.back_buffer_size = function() return WIDTH,HEIGHT end
S.Application.main_world = function() return {} end
S.Application.can_get = function(kind,name)
    return kind == 'runtime_font' and name == 'content/fonts/fallback'
        or kind == 'material' and name == 'content/fonts/runtime_font'
end
S.World.create_screen_gui = function() return {} end
S.Gui.rect = function() end
S.Gui.text = function(gui,text,font,size,material,pos,color)
    draws[#draws+1] = {text=text,x=pos.x,y=pos.y,z=pos.z,size=size,font=font,material=material,
        red=color.r,green=color.g,blue=color.b}
end
stingray = S
'''

EXPORT = r'''
parse_data()
menu.S, menu.gui, menu.font, menu.layers = S, {}, 'debug', true
menu.zh_font = {font='content/fonts/fallback', material='content/fonts/runtime_font'}
menu.presets, menu.block = {'Default'}, false
return {menu=menu, items=ITEMS, by_name=ITEM_BY_NAME, ranges=RANGES, overrides=overrides,
    config=config, state=state, files=files, ui=MENU_ZH, labels=MENU_LABEL, statuses=MENU_STATUS,
    groups=MENU_GROUP_OF, categories=MENU_CATEGORIES, category_names=MENU_CATEGORY_NAME,
    category_tags=MENU_CATEGORY_TAG, actions=MENU_ACTIONS, pages=MENU_PAGES,
    L=L, label=menu_label, heading=menu_heading, cells=menu_cells, clip=menu_clip,
    lists=menu_lists, current=menu_current, rows=menu_rows, set=menu_set, change=menu_change,
    preset_text=preset_text, preset_parse=preset_parse, save=menu_save, load=menu_load,
    start=menu_start, language_input=menu_language_input, settings_save=menu_settings_save,
    key_bound=menu_bound,
    render=function(width,height)
        WIDTH, HEIGHT = width or WIDTH, height or HEIGHT
        menu.width, menu.height = nil,nil
        draws = {}
        menu_draw(NOW)
        return draws
    end,
    press=function(key)
        NOW = NOW + 0.1; down[KEY_VK[key]] = true; menu_input(NOW); menu_draw(NOW)
        NOW = NOW + 0.1; down[KEY_VK[key]] = nil; menu_input(NOW)
    end,
    set_font_available=function(available)
        S.Application.can_get = function() return available end
    end}
'''


def fixture(language='zh', source=SOURCE):
    lua = LuaRuntime(unpack_returned_tuples=True)
    generated = source[source.index('local BUILDS ='):source.index('-- ---------------------------------------------------------------- build gate')]
    numbers = source[source.index('local function show('):source.index('-- ---------------------------------------------------------------- windows api')]
    menus = source[source.index('local SETTINGS_FILE,'):source.index('-- once per frame')]
    program = FIXTURE + '\nlocal DATA = [==[' + DATA + ']==]\n' + generated + numbers + menus + EXPORT
    api = lua.execute(program)
    api.menu.lang = language
    api.menu.lang_saved = language
    return lua, api


def rows(table):
    return [value for _, value in table.items()]


class Localization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lua, cls.api = fixture()

    def test_full_addon_compiles_on_luajit(self):
        # The complete chunk is close to LuaJIT's 200-local limit; a helper-only compile misses that.
        LuaRuntime().compile(SOURCE.replace('@@VERSION@@', '2.0.0').replace('@@DATA@@', DATA))

    def test_ui_labels_groups_and_search_tags_are_translated(self):
        api = self.api
        for text in rows(api.labels) + rows(api.pages) + rows(api.category_names) + rows(api.category_tags):
            self.assertRegex(api.L(text), r'[\u3400-\u9fff]', text)
        for _, group in api.groups.items():
            self.assertRegex(api.L(group[1]), r'[\u3400-\u9fff]', group[1])
        for action in rows(api.actions):
            self.assertRegex(api.L(action[3]), r'[\u3400-\u9fff]', action[3])

    def test_format_placeholders_are_preserved(self):
        for english, chinese in self.api.ui.items():
            tokens = lambda value: re.findall(r'%(?:\d+\$)?[sdifg]', value)
            self.assertEqual(tokens(english), tokens(chinese), english)

    def test_every_catalog_name_and_stat_has_a_readable_label(self):
        api = self.api
        for item in rows(api['items']):
            for text in (item.display or item.name, item.group, item.section):
                if not text:
                    continue
                translated = api.menu.name(text)
                # A caliber alone is already a useful numeric label, not an untranslated word.
                if not re.fullmatch(r'\d+(?:[,.]\d+)?(?:mm|g)?', text):
                    self.assertRegex(translated, r'[\u3400-\u9fff]', text)
            for stat in rows(item.stat_order):
                self.assertRegex(api.label(stat), r'[\u3400-\u9fff]', stat)
        for text in rows(api.statuses):
            self.assertRegex(api.menu.name(text), r'[\u3400-\u9fff]', text)

    def test_official_names_and_unidentified_ids(self):
        translate = self.api.menu.name
        self.assertEqual(translate('AR-23 Liberator'), 'AR-23 解放者')
        self.assertEqual(translate('R-63 Diligence'), 'R-63 勤勉')
        self.assertEqual(translate('weapon_abcdef12'), '未识别武器 abcdef12')
        self.assertEqual(translate('armor_deadbeef'), '未识别护甲 deadbeef')
        self.assertEqual(translate('Damage row 269: -1 / -1, AP 0'), '伤害数据 269: -1 / -1, 穿甲 0')
        self.assertEqual(translate('health 70, armor 0, 6 parts [body_12345678]'),
                         '生命 70, 护甲 0, 部件 6 [body_12345678]')
        self.assertEqual(translate('A future item'), 'A future item')

    def test_utf8_clipping_does_not_split_characters(self):
        api = self.api
        for sample in ('中文字符测试ABCDE', '未识别效果 deadbeef', '射击模式 (1 自动/2 单发/3 点射)', '🔧中文'):
            for cells in range(0, 40):
                clipped = api.clip(sample, cells)
                self.assertLessEqual(api.cells(clipped), cells)
                self.assertTrue(sample.startswith(clipped))

    def test_verdicts_and_warnings_keep_the_numbers(self):
        messages = [
            'WAITING', 'WAITING - checking the game build (nothing written yet)',
            'REFUSED - this game build is not one this version was verified on; nothing was written',
            "DISABLED - enabled = false in config.txt; all values are the game's own",
            "OK - 12 values applied, 2 weapons on their own bullet, 3 magazines switched to the weapons' own values, 4 explosions of their own",
            'PARTIAL - 12 values applied, 3 waiting for their table, 1 failed, 2 config lines rejected',
            'mags_start 20 is above mags_max 10: the game starts with 10. Set mags_max as well',
            'rounds_max 1500 is above 1023: the game starts with 1500, but a resupply fills up to 1023 at most',
            'charges 1500 is above 1023: the game starts with 1500, but a resupply fills up to 1023 at most',
            'part leg_left has 100000 health and passes 50% of its damage on, the main health is 1000: the vehicle is destroyed before this part breaks. Raise health, lower part_leg_left_to_main, or use all_health to scale everything together',
        ]
        for message in messages:
            translated = self.api.menu.message(message)
            self.assertRegex(translated, r'[\u3400-\u9fff]', message)
            self.assertEqual(re.findall(r'\d+', message), re.findall(r'\d+', translated), message)

    def test_display_changes_do_not_change_order_search_or_saved_identifiers(self):
        saved, orders, found = [], [], []
        for language in ('en', 'zh'):
            lua, api = fixture(language)
            listing = api.lists()
            orders.append({category: [item.name for item in rows(listing[category])] for category in rows(api.categories)})
            api.menu.filter = 'liberator'
            hits, category = api.current(listing)
            found.append([hits[index].name for index in range(1, len(hits) + 1)])
            weapon = api.by_name['weapon:assault_rifle']
            original = weapon.stats.rpm.field.stock
            api.set(weapon, 'rpm', original + 10, 1)
            api.change(weapon, 'rpm', 1, False, 2)
            self.assertTrue(api.save())
            saved.append(api.files['presets\\Default.txt'])
            values = api.preset_parse(saved[-1])
            self.assertIn('weapon:assault_rifle:rpm', list(values.keys()))
            self.assertEqual(api.key_bound('accept'), 'ENTER')
        self.assertEqual(orders[0], orders[1])
        self.assertEqual(found[0], found[1])
        self.assertTrue(found[1])
        self.assertEqual(saved[0], saved[1])
        self.assertIn('[weapon: assault_rifle]', saved[1])

    def test_all_pages_and_categories_render_at_four_resolutions(self):
        for width, height in ((1280,720), (1920,1080), (2560,1440), (3440,1440)):
            lua, api = fixture()
            for page in range(1, 5):
                api.menu.page = page
                for tab in range(1, 14) if page == 1 else (1,):
                    api.menu.tab = tab
                    output = rows(api.render(width, height))
                    self.assertTrue(output)
                    for draw in output:
                        self.assertGreaterEqual(draw.x, 0)
                        self.assertGreaterEqual(draw.y, 0)
                        self.assertLess(draw.x, width)
                        self.assertLess(draw.y, height)
                        self.assertEqual(draw.font, 'content/fonts/fallback')
                        self.assertEqual(draw.material, 'content/fonts/runtime_font')

    def test_english_rendering_matches_shipped_version(self):
        _, before = fixture('en', SHIPPED)
        _, after = fixture('en')
        for page in range(1, 5):
            before.menu.page = after.menu.page = page
            for tab in range(1, 14) if page == 1 else (1,):
                before.menu.tab = after.menu.tab = tab
                a = [dict(draw.items()) for draw in rows(before.render())]
                b = [dict(draw.items()) for draw in rows(after.render())]
                self.assertEqual(a, b, (page, tab))

    def test_font_gate_and_failed_font_guard_are_unchanged(self):
        for available, failed in ((False, False), (True, True), (True, False)):
            lua, api = fixture()
            api.menu.zh_font = None
            api.menu.zh_asked = None
            api.menu.zh_failed = failed
            api.set_font_available(available)
            self.assertTrue(api.start())
            self.assertEqual(api.menu.lang, 'zh' if available and not failed else 'en')

    def test_language_switch_keeps_the_delayed_font_confirmation(self):
        _, api = fixture('en')
        api.menu.page, api.menu.lang_row = 4, 2
        api.press('ENTER')
        self.assertEqual(api.menu.lang, 'zh')
        self.assertIn('language = en', api.files['private\\settings.txt'])
        self.assertIn('chinese_trying = true', api.files['private\\settings.txt'])
        for _ in range(60):
            api.render()
        self.assertIn('language = zh', api.files['private\\settings.txt'])
        self.assertNotIn('chinese_trying', api.files['private\\settings.txt'])
        api.menu.lang_row = 1
        api.press('ENTER')
        self.assertEqual(api.menu.lang, 'en')

    def test_translated_key_names_do_not_change_saved_bindings(self):
        _, api = fixture()
        api.menu.page, api.menu.key_row = 3, 1
        api.press('ENTER')
        self.assertEqual(api.menu.mode, 'capture')
        api.press('F8')
        self.assertEqual(api.key_bound('toggle'), 'F8')
        self.assertIn('key.toggle = F8', api.files['private\\settings.txt'])
        self.assertEqual(api.key_bound('up'), 'UP')
        self.assertEqual(api.menu.key_name('UP'), '上')

    def test_search_results_use_chinese_names_and_category_tags(self):
        _, api = fixture()
        api.menu.filter = 'sentry'
        text = '\n'.join(draw.text for draw in rows(api.render()))
        self.assertIn('[战备武器]', text)
        self.assertNotIn('[strat. weapon]', text)
        self.assertNotIn('Gatling Sentry', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
