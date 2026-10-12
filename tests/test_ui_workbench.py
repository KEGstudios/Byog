"""Exercise the actual Lua menu using the published data, without game memory access.

Only the startup tail is replaced with a test adapter. No production test hooks.
"""
from pathlib import Path
import sys
import unittest
import zipfile

from lupa.luajit21 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import pack_addon


def published():
    with zipfile.ZipFile(ROOT / 'dist/BYOG-v2.0.0.zip') as z:
        source = pack_addon.read_archive(z.read('Addon/' + pack_addon.ARCHIVE_FILE))[0][1].decode()
    return source.split('local DATA = [==[\n', 1)[1].split(']==]', 1)[0]


ADAPTER = r'''
log = function() end
flush_log = function() end
pause = function() end
request_reload = function() end
menu_save = function() return true end
menu_settings_save = function() return true end
menu_trail.drawn = true
A = { game_window = function() if not UI.away then return 1 end end,
      game_in_front = function() return true end,
      mouse = function() return UI.mx, UI.my, UI.client_width or UI.width, UI.client_height or UI.height end,
      key_down = function(k) return UI.keys[k] or false end,
      now = function() return UI.now end }
local S = { World = { destroy_gui = function() end },
  Application = { back_buffer_size = function() return UI.width, UI.height end },
  Vector2 = function(x,y) return {x,y} end, Vector3 = function(x,y,z) return {x,y,z} end,
  Color = function(a,r,g,b) return {a,r,g,b} end, Gui = {} }
S.Gui.rect = function(gui,p,s,c) UI.rects[#UI.rects+1] = {p=p,s=s,c=c} end
S.Gui.text = function(gui,t,f,s,m,p,c) UI.texts[#UI.texts+1] = {t=t,s=s,p=p,c=c} end
menu.S, menu.gui, menu.font, menu.layers = S, 'gui', 'arial', true
menu.loaded, menu.open, menu.focus = true, true, 'stats'
menu.presets = {'Default','Friends'}
preset_name = 'Default'
config.sections_open = true
state.verdict = 'OK - no values changed'
parse_data()
return { menu=menu, config=config, items=ITEM_BY_NAME, ranges=RANGES,
  overrides=overrides, draw=menu_draw, input=menu_input, rows=menu_rows,
  bound=menu_bound, lists=menu_lists, current=menu_current,
  set=menu_set, settings_load=menu_settings_load,
  fake_settings=function(t) read_file=function() return t end end,
  use=function(category,name)
    local lists=menu_lists()
    for n,c in ipairs(MENU_CATEGORIES) do if c==category then menu.tab=n end end
    for n,it in ipairs(lists[category]) do
      if it.name==name then menu.item[category]=n; return it end
    end
  end }
'''


class MenuRig:
    def __init__(self, width=1920, height=1080):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('UI={width=%d,height=%d,now=10,mx=0,my=0,keys={},texts={},rects={}}' % (width,height))
        source = (ROOT / 'src/tuner/tuner.lua').read_text(encoding='utf-8')
        source = source.split('-- ---------------------------------------------------------------- startup',1)[0]
        source = source.replace('@@DATA@@',published()).replace('@@VERSION@@','2.0.0')
        self.api = self.lua.execute(source + ADAPTER)
        self.ui = self.lua.globals().UI
        self.menu = self.api.menu
        self.item = self.api.use('weapon','automatic_cannon')

    def draw(self):
        self.ui.texts = self.lua.table()
        self.ui.rects = self.lua.table()
        self.api.draw(self.ui.now)
        return '\n'.join(x.t for x in self.ui.texts.values())

    def press(self, vk):
        self.ui['keys'][vk]=True
        self.ui.now += .02
        self.api.input(self.ui.now)
        self.ui['keys'][vk]=False
        self.ui.now += .02
        self.api.input(self.ui.now)

    def click_text(self, label):
        self.draw()
        hit=next(x for x in self.ui.texts.values() if x.t == label)
        self.ui.mx, self.ui.my = hit.p[1]+3, self.ui.height-hit.p[2]-hit.s/2
        self.draw()
        self.ui['keys'][1]=True
        self.draw()
        self.ui['keys'][1]=False
        self.draw()
        self.api.input(self.ui.now)


class Workbench(unittest.TestCase):
    def test_text_only_fallback_marks_category_and_group(self):
        r=MenuRig()
        r.menu.layers=False
        rows,_=r.api.rows(r.item)
        r.menu.toggle(r.item,rows[1].key,True)
        text=r.draw()
        self.assertIn('> [+] DAMAGE',text)
        cat=next(t for t in r.ui.texts.values() if t.t=='Weapons')
        self.assertEqual((cat.c[2],cat.c[3],cat.c[4]),(255,214,0))

    def test_damage_explanation_is_in_inspector(self):
        r=MenuRig()
        _,stats=r.api.rows(r.item)
        for n,name in stats.items():
            if name=='damage': r.menu.stat[r.item]=n
        self.assertIn('Direct-hit damage',r.draw())

    def test_many_presets_keep_selected_row_visible(self):
        r=MenuRig()
        r.menu.page=2
        r.menu.presets=r.lua.table_from(['Profile%02d'%n for n in range(45)])
        r.menu.preset_row=45
        self.assertIn('Profile44',r.draw())

    def test_context_hints_during_capture_and_confirmation(self):
        r=MenuRig()
        r.menu.page=3
        r.press(0x0D)
        self.assertEqual(r.menu.mode,'capture')
        text=r.draw()
        self.assertIn('cancel',text)
        self.assertNotIn('\nclose\n',text)
        r.press(0x1B)
        r.menu.page=2
        r.menu.mode='confirm'
        r.menu.ask=r.lua.table_from({'name':'Default'})
        r.menu.bind.back='F8'
        text=r.draw()
        self.assertIn('F8',text)
        self.assertIn('cancel',text)

    def test_long_reassigned_keys_keep_footer_inside_panel(self):
        r=MenuRig()
        for action in ['up','down','left','right','column','page_up','page_down','fast','reset','search','accept','back','toggle']:
            r.menu.bind[action]='NUMPAD9'
        r.draw()
        for t in r.ui.texts.values():
            self.assertGreaterEqual(t.p[2],0)
            self.assertLessEqual(t.p[1]+len(t.t)*t.s*.62,r.ui.width)

    def test_donor_and_group_members_do_not_break_inspector(self):
        r=MenuRig()
        _,stats=r.api.rows(r.item)
        for n,name in stats.items():
            if name=='blast_from': r.menu.stat[r.item]=n
        self.assertIn('its own',r.draw())
        self.assertNotIn('Enter value',r.draw())
        r.menu.tab=11
        items,cat=r.api.current(r.api.lists())
        group=next(it for it in items.values() if it.members is not None)
        r.api.use(cat,group.name)
        self.assertIn('SELECTED GROUP',r.draw())
        rows,_=r.api.rows(group)
        r.menu.toggle(group,rows[1].key,False)
        self.assertIn('SELECTED PARAMETER',r.draw())

    def test_text_mode_clicks_do_not_change_pages(self):
        r=MenuRig()
        r.press(0x0D)
        self.assertEqual(r.menu.mode,'text')
        r.click_text('Presets')
        self.assertEqual(r.menu.page,1)

    def test_rebinding_through_keys_page_updates_hint(self):
        r=MenuRig()
        r.menu.page=3
        r.menu.key_row=14  # accept
        r.press(0x0D)
        r.press(0x77)  # F8
        self.assertEqual(r.api.bound('accept'),'F8')
        r.menu.page=1
        self.assertIn('F8',r.draw())
        r.press(0x2D)  # Insert alias must no longer accept.
        self.assertEqual(r.menu.mode,'list')
        r.press(0x77)
        self.assertEqual(r.menu.mode,'text')

    def test_inspector_uses_reassigned_keys(self):
        r=MenuRig()
        r.api.fake_settings('key.accept = F8\nkey.reset = F4\nkey.toggle = F2\nkey.fast = CTRL\nkey.column = F5\n')
        r.api.settings_load()
        text=r.draw()
        self.assertIn('SELECTED PARAMETER',text)
        self.assertIn('F8',text)
        self.assertIn('F4',text)
        self.assertIn('F2',text)
        self.assertIn('CTRL',text)
        self.assertNotIn('INSERT',text)
        self.assertNotIn('F9',text)
        r.press(0x77)  # F8 opens the actual value editor.
        self.assertEqual(r.menu.mode,'text')
        self.assertIn('F8',r.draw())

    def test_group_inspector_does_not_offer_numeric_edit(self):
        r=MenuRig()
        rows,_=r.api.rows(r.item)
        r.menu.toggle(r.item,rows[1].key,True)
        text=r.draw()
        self.assertIn('SELECTED GROUP',text)
        self.assertNotIn('Enter value',text)

    def test_wide_layout_stays_on_screen_at_different_aspects(self):
        for w,h in [(1920,1080),(2560,1440),(1280,1024),(1280,720),(3440,1440)]:
            with self.subTest(w=w,h=h):
                r=MenuRig(w,h)
                r.draw()
                for x in r.ui.rects.values():
                    self.assertGreaterEqual(x.p[1],0)
                    self.assertGreaterEqual(x.p[2],0)
                    self.assertLessEqual(x.p[1]+x.s[1],w+.01)
                    self.assertLessEqual(x.p[2]+x.s[2],h+.01)

    def test_difference_for_numeric_and_zero_default(self):
        r=MenuRig()
        r.api.overrides['weapon:automatic_cannon:damage']='400'
        text=r.draw()
        self.assertIn('+75',text)
        self.assertIn('MODIFIED VALUES',text)
        # Zero stock must never yield NaN/Inf percentage in the inspector.
        r.api.overrides['weapon:automatic_cannon:ap_bonus']='2'
        _,stats=r.api.rows(r.item)
        for n,s in stats.items():
            if s=='ap_bonus': r.menu.stat[r.item]=n
        text=r.draw().lower()
        self.assertNotIn('nan',text)
        self.assertNotIn('inf%',text)

    def test_click_category_and_value_after_layout_move(self):
        r=MenuRig()
        r.click_text('Throwables')
        self.assertEqual(r.menu.tab,2)
        r.api.use('weapon','automatic_cannon')
        r.menu.focus='stats'
        r.click_text('Enter value')
        self.assertEqual(r.menu.mode,'text')
        r.press(0x35)
        r.press(0x0D)
        self.assertEqual(r.menu.mode,'list')


class Icons(unittest.TestCase):
    def test_grouped_shovel_and_known_melee_get_matching_symbols(self):
        r=MenuRig()
        items,_=r.api.current(r.api.lists())
        shovel=next(it for it in items.values() if it.members is not None and 'Entrenchment' in it.name)
        self.assertEqual(r.menu.icon_name('weapon',shovel),'wiki_cqc_73_entrenchment_tool')
        self.assertEqual(r.menu.icon_name('weapon','stun_baton'),'wiki_cqc_30_stun_baton')
        self.assertEqual(r.menu.icon_name('weapon','melee_flag'),'wiki_cqc_1_one_true_flag')

    def test_weapon_families_have_distinct_silhouettes(self):
        r=MenuRig()
        self.assertIsNotNone(r.menu.icon_name,'icon resolver missing')
        expected={'automatic_cannon':'wiki_ac_8_autocannon','sniper_rifle':'wiki_apw_1_anti_materiel_rifle',
                  'assault_rifle':'wiki_ar_23_liberator','standard_pistol':'wiki_p_2_peacemaker',
                  'pump_shotgun':'wiki_sg_8_punisher','stun_spear':'wiki_cqc_19_stun_lance',
                  'crossbow_greyfax':'wiki_cb_9_exploding_crossbow','minigun':'wiki_m_1000_maxigun'}
        for name,art in expected.items():
            self.assertEqual(r.menu.icon_name('weapon',name),art)
        self.assertEqual(r.menu.icon_name('weapon','future_unknown_weapon'),'unknown_weapon')
        self.assertEqual(r.menu.icon_name('future_category','future_item'),'unknown_weapon')

    def test_icons_render_in_sidebar_and_library_with_bounded_draw_cost(self):
        r=MenuRig()
        r.draw()
        art=[x for x in r.ui.rects.values() if x.p[3]==902]
        self.assertGreater(len(art),50)
        self.assertLess(len(r.ui.rects),1000)
        self.assertTrue(any(80<=x.p[1]<110 for x in art),'no category icons')
        self.assertTrue(any(315<=x.p[1]<385 for x in art),'no weapon thumbnails')

    def test_scrolled_last_item_remains_visible(self):
        r=MenuRig()
        items,_=r.api.current(r.api.lists())
        r.menu.item['weapon']=len(items)
        text=r.draw()
        self.assertIn(str(len(items))+' of '+str(len(items)),text)
        # Every visible item must stay above the list footer, including the last.
        for t in r.ui.texts.values():
            if 315<=t.p[1]<670 and t.s==16:
                self.assertGreater(t.p[2],240)

    def test_click_on_thumbnail_selects_the_corresponding_item(self):
        r=MenuRig()
        r.menu.item['weapon']=1
        r.draw()
        # Second row's silhouette, not its text: the complete row is one hit area.
        r.ui.mx,r.ui.my=340,359
        r.draw()
        r.ui['keys'][1]=True
        r.draw()
        r.ui['keys'][1]=False
        r.draw()
        self.assertEqual(r.menu.item['weapon'],2)
        self.assertEqual(r.menu.focus,'items')

    def test_every_category_and_unknown_icon_can_render(self):
        r=MenuRig()
        for category,items in r.api.lists().items():
            self.assertIsNotNone(r.menu.icons[category])
            for entry in items.values():
                self.assertIsNotNone(r.menu.icons[r.menu.icon_name(category,entry.name)])
        r.menu.filter='this item does not exist'
        self.assertIn('No matching items',r.draw())

    def test_no_layer_fallback_does_not_draw_icons(self):
        r=MenuRig()
        r.menu.layers=False
        self.assertIn('AC-8 Autocannon',r.draw())
        self.assertEqual(len(r.ui.rects),0)

    def test_wiki_models_replace_guesses_and_unknowns_stay_unassigned(self):
        r=MenuRig()
        models=[r.menu.icon_name('weapon',n) for n in ('assault_rifle','plasma_rifle','faf_missile_launcher','stun_spear')]
        self.assertEqual(len(set(models)),4)
        self.assertTrue(all(n.startswith('wiki_') for n in models))
        self.assertEqual(r.menu.icon_name('weapon','laser_rifle_charge'),'unknown_weapon')
        self.assertEqual(r.menu.icon_name('weapon','revolver_pistol_long'),'unknown_weapon')
        self.assertEqual(r.menu.icon_name('shield','energy_shield_backpack'),'wiki_stratagem_shield_generator_pack')

    def test_worst_icon_windows_keep_existing_draw_budget(self):
        r=MenuRig()
        for category,items in r.api.lists().items():
            entries=list(items.values())
            costs=[len(r.menu.icons[r.menu.icon_name(category,e)]) for e in entries]
            start=max(range(len(entries)),key=lambda i:sum(costs[i:i+12]))
            r.api.use(category,entries[min(start+5,len(entries)-1)].name)
            r.draw()
            self.assertLess(len(r.ui.rects),1000,category)


class FactionEffects(unittest.TestCase):
    def test_factions_use_distinct_symbols_for_units_and_members(self):
        r=MenuRig()
        expected={'Hunter':'wiki_faction_terminid','Agitator':'wiki_faction_automaton',
                  'Voteless':'wiki_faction_illuminate','cha_observer':'wiki_faction_illuminate',
                  'cha_warrior_big_tier2':'wiki_faction_terminid','cyborg_siege_engine':'wiki_faction_automaton'}
        for name,icon in expected.items():
            self.assertEqual(r.menu.icon_name('enemy_weapon',name),icon)
        for item in r.api.lists()['enemy_weapon'].values():
            icon=r.menu.icon_name('enemy_weapon',item)
            self.assertIn(icon,set(expected.values()))
            if item.members:
                for member in item.members.values():
                    self.assertEqual(r.menu.icon_name('enemy_weapon',member),icon)

    def test_effect_groups_have_type_symbols_and_cover_members(self):
        r=MenuRig()
        for name,icon in {'Fire':'wiki_effect_fire','Gas':'wiki_effect_gas','Acid':'wiki_effect_acid',
                          'bleed':'wiki_effect_bleed','electric':'effect_electric',
                          'Stun':'effect_stun','Stim':'effect_heal'}.items():
            self.assertEqual(r.menu.icon_name('status',name),icon)
        for item in r.api.lists()['status'].values():
            icon=r.menu.icon_name('status',item)
            self.assertNotEqual(icon,'status')
            self.assertIsNotNone(r.menu.icons[icon])
            if item.members:
                for member in item.members.values():
                    self.assertEqual(r.menu.icon_name('status',member),icon)

    def test_unrecognized_future_entries_do_not_get_guessed_faction(self):
        r=MenuRig()
        self.assertEqual(r.menu.icon_name('enemy_weapon','unknown_robot_bug'),'enemy_weapon')
        self.assertEqual(r.menu.icon_name('status','future_fire_effect'),'status')


class SummaryRevision(unittest.TestCase):
    def test_grouped_changes_keep_owner_and_overflow_inside_summary(self):
        r=MenuRig()
        group=next(e for e in r.api.lists()['weapon'].values() if e.members)
        r.api.use('weapon',group.name)
        member=group.members[1]
        _,stats=r.api.rows(member)
        for name in list(stats.values())[:5]:
            r.api.overrides['weapon:'+member.name+':'+name]='4'
        text=r.draw()
        self.assertIn('MODIFIED VALUES',text)
        self.assertIn('+2 values',text)
        self.assertTrue(any((member.display or member.name)[:8] in t.t for t in r.ui.texts.values() if t.p[1]>1400))

    def test_changes_show_readable_before_after_and_delta(self):
        r=MenuRig()
        r.api.overrides['weapon:automatic_cannon:damage']='97725'
        r.draw()
        summary=[x.t for x in r.ui.texts.values() if x.p[1]>1400 and 195<x.p[2]<400]
        self.assertIn('325 -> 97,725',summary)
        self.assertIn('+97,400',summary)
        self.assertIn('1',summary)

    def test_summary_handles_zero_stock_and_negative_difference(self):
        r=MenuRig()
        r.api.overrides['weapon:automatic_cannon:damage']='0'
        r.api.overrides['weapon:automatic_cannon:ap_bonus']='4'
        text=r.draw()
        self.assertIn('325 -> 0',text)
        self.assertIn('-325',text)
        self.assertIn('0 -> 4',text)


class CursorRegression(unittest.TestCase):
    def move(self,r,x,y):
        r.ui.mx,r.ui.my=x,y
        r.draw()
        points=[v for v in r.ui.rects.values() if v.p[3]==904]
        if not points: return None
        p=points[-1]
        return round(p.p[1],5),round(r.ui.height-p.p[2]-p.s[2],5)

    def test_edge_to_center_reset_does_not_teleport_menu_pointer(self):
        for edge,after,expected in [((1880,540),(990,540),(1910,540)),
                                    ((40,540),(930,540),(10,540)),
                                    ((960,20),(960,525),(960,5)),
                                    ((960,1060),(960,555),(960,1075)),
                                    ((1880,1060),(990,555),(1910,1075))]:
            with self.subTest(edge=edge):
                r=MenuRig()
                self.move(r,960,540)
                self.assertEqual(self.move(r,*edge),edge)
                self.assertEqual(self.move(r,960,540),edge)
                self.assertEqual(self.move(r,*after),expected)

    def test_first_motion_from_corner_is_not_mistaken_for_reset(self):
        r=MenuRig()
        self.move(r,0,0)
        self.assertEqual(self.move(r,960,540),(960,540))

    def test_normal_motion_and_center_crossing_remain_absolute(self):
        r=MenuRig()
        self.move(r,960,540)
        for point in [(1100,600),(1600,500),(1200,530),(960,540),(30,200),(800,400)]:
            self.assertEqual(self.move(r,*point),point)

    def test_repeated_resets_clamp_and_reverse_immediately(self):
        r=MenuRig()
        self.move(r,960,540)
        self.move(r,1880,540)
        self.move(r,960,540)
        self.assertEqual(self.move(r,1880,540),(1919,540))
        self.assertEqual(self.move(r,960,540),(1919,540))
        self.assertEqual(self.move(r,950,540),(1909,540))

    def test_reopen_and_resize_discard_old_virtual_offset(self):
        r=MenuRig()
        self.move(r,960,540)
        self.move(r,1880,540)
        self.move(r,960,540)
        r.menu.width=None # real close clears width
        self.move(r,960,540)
        self.assertEqual(self.move(r,970,540),(970,540))
        r.ui.width,r.ui.height=1280,720
        self.move(r,640,360)
        self.assertEqual(self.move(r,650,360),(650,360))

    def test_corner_close_button_uses_virtual_not_windows_position(self):
        r=MenuRig()
        self.move(r,960,540)
        self.move(r,1800,100)
        self.move(r,960,540)
        self.assertEqual(self.move(r,970,550),(1810,110))
        r.ui['keys'][1]=True
        r.draw()
        self.assertFalse(r.menu.open)

    def test_focus_loss_hides_pointer_and_discards_offset(self):
        r=MenuRig()
        self.move(r,960,540)
        self.move(r,1880,540)
        self.move(r,960,540)
        r.ui.away=True
        r.ui['keys'][1]=True
        self.assertIsNone(self.move(r,400,350))
        r.ui.away=False
        self.assertIsNone(self.move(r,400,350))
        self.assertEqual(self.move(r,410,350),(410,350))
        self.assertTrue(r.menu.open)

    def test_client_pixels_are_scaled_to_back_buffer_after_warp(self):
        r=MenuRig()
        r.ui.client_width,r.ui.client_height=1280,720
        self.move(r,640,360)
        self.move(r,1240,360)
        self.assertEqual(self.move(r,640,360),(1860,540))
        self.assertEqual(self.move(r,650,360),(1875,540))


if __name__=='__main__': unittest.main()
