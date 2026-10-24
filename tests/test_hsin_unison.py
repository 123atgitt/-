import logging
import pathlib
import sys
import time
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHAR_DIR = ROOT / 'src' / 'char'
UNISON_FILES = ('Hsin.py', 'Suoming.py', 'ShoreKeeper.py')
BEGIN = '# UNISON_SHARED_BEGIN\n'
END = '# UNISON_SHARED_END\n'


def shared_block(name):
    text = (CHAR_DIR / name).read_text(encoding='utf-8')
    start = text.index(BEGIN) + len(BEGIN)
    end = text.index(END, start)
    return text[start:end]


def install_stubs():
    labels = types.ModuleType('src.Labels')

    class Labels:
        hsin_h1 = 'hsin_h1'
        hsin_h2 = 'hsin_h2'
        hsin_lib1 = 'hsin_lib1'
        hsin_lib2 = 'hsin_lib2'
        suoming_forte_e = 'suoming_forte_e'

    labels.Labels = Labels

    base = types.ModuleType('src.char.BaseChar')

    class SwitchPriority:
        MUST = 'must'
        NORMAL = 'normal'

    class CharType:
        MAIN_DPS = 'main'
        SUB_DPS = 'sub'

    def get_default_buff_time(char_type):
        return 12 if char_type == CharType.MAIN_DPS else 6

    class BaseChar:
        def __init__(self, *args, **kwargs):
            self.task = kwargs.get('task')
            self.name = self.__class__.__name__
            self.char_name = self.name
            self.has_intro = False
            self.logger = logging.getLogger(self.name)

        def reset_state(self):
            return None

        def on_combat_end(self, chars):
            self.combat_ended = chars
            return chars

        def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
            return SwitchPriority.NORMAL

        def switch_next_char(self, *args, **kwargs):
            return kwargs

        def check_combat(self):
            return None

        def sleep(self, _seconds):
            return None

        def click(self):
            return None

        def cycle_sleep(self):
            return None

        def time_elapsed_accounting_for_freeze(self, _start):
            return 0

        def liberation_available(self):
            return False

        def click_liberation(self, wait_if_cd_ready=0):
            return False

        def click_echo(self, time_out=0):
            return False

        def click_resonance(self, *args, **kwargs):
            return False

        def continues_normal_attack(self, duration=0, until_con_full=False):
            return None

        def is_con_full(self):
            return False

        def heavy_click_forte(self, *args, **kwargs):
            return None

        def is_mouse_forte_full(self):
            return False

        def flying(self):
            return False

    base.BaseChar = BaseChar
    base.SwitchPriority = SwitchPriority
    base.CharType = CharType
    base.get_default_buff_time = get_default_buff_time

    augusta = types.ModuleType('src.char.Augusta')

    class Augusta:
        pass

    augusta.Augusta = Augusta

    sys.modules['src.Labels'] = labels
    sys.modules['src.char.BaseChar'] = base
    sys.modules['src.char.Augusta'] = augusta
    return SwitchPriority


SWITCH = install_stubs()

from src.char.Hsin import Hsin  # noqa: E402
from src.char.ShoreKeeper import ShoreKeeper  # noqa: E402
from src.char.Suoming import Suoming  # noqa: E402


class Task:
    def __init__(self, config=None):
        self.chars = []
        self.char_config = {} if config is None else config
        self.skip_combat_check = False
        self.frames = 0

    def next_frame(self):
        self.frames += 1

    def has_char(self, _cls):
        return False

    def in_team_and_world(self):
        return True

    def wait_in_team_and_world(self, time_out=0, raise_if_not_found=False):
        return None

    def mouse_down(self):
        return None

    def mouse_up(self):
        return None


class Named:
    def __init__(self, name, ring_index=-1):
        self.name = name
        self.ring_index = ring_index
        self._last_known_form = -1
        self.task = None


def party(*chars, config=None):
    task = Task(config)
    task.chars = list(chars)
    for char in chars:
        char.task = task
    return task


class UnisonSharedTest(unittest.TestCase):
    def test_three_scripts_share_one_block_and_do_not_import_each_other(self):
        blocks = [shared_block(name) for name in UNISON_FILES]
        self.assertEqual(blocks[0], blocks[1])
        self.assertEqual(blocks[0], blocks[2])
        for name in UNISON_FILES:
            text = (CHAR_DIR / name).read_text(encoding='utf-8')
            self.assertNotIn('src.char.Hsin', text)
            self.assertNotIn('src.char.Suoming', text)
            self.assertNotIn('src.char.ShoreKeeper', text)
        for name in ('Chisa.py', 'Rover.py'):
            text = (CHAR_DIR / name).read_text(encoding='utf-8')
            self.assertNotIn('_hsin_unison', text)
            self.assertNotIn('UNISON_SHARED_BEGIN', text)

    def test_team_requires_all_three_and_support_suoming(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        self.assertTrue(unison_of(hsin))
        task.chars = [hsin, suo]
        self.assertFalse(unison_of(hsin))
        task.chars = [hsin, suo, shore]
        task.char_config['Suoming DPS'] = True
        self.assertFalse(unison_of(suo))

    def test_stale_prefer_is_ignored_when_the_team_stops_matching(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        from src.char.Hsin import unison_advance, unison_wants
        unison_advance(shore, 'hsin_r2', 'Hsin')
        self.assertTrue(unison_wants(hsin))
        task.char_config['Suoming DPS'] = True
        self.assertFalse(unison_wants(hsin))
        task.char_config.clear()
        task.chars = [hsin, shore]
        self.assertFalse(unison_wants(hsin))

    def test_reset_returns_the_chain_to_shorekeeper(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        from src.char.Hsin import unison_advance
        unison_advance(hsin, 'hsin_r2', 'Hsin')
        hsin.reset_state()
        self.assertEqual(task._hsin_unison, {'phase': 'shore', 'prefer': None})


class HsinUnisonTest(unittest.TestCase):
    def test_perform_calls_unison_before_the_electro_rotation(self):
        text = (CHAR_DIR / 'Hsin.py').read_text(encoding='utf-8')
        perform = text.split('def do_perform', 1)[1].split('def do_unison_perform', 1)[0]
        self.assertIn('not is_hsin_electro_team(self) and unison_team(self)', perform)
        self.assertLess(perform.index('do_unison_perform()'), perform.index('perform_everything()'))

    def test_electro_team_keeps_its_rotation_even_if_the_other_names_are_present(self):
        hsin = Hsin()
        called = []
        hsin.perform_everything = lambda: called.append('electro')
        hsin.do_unison_perform = lambda: called.append('unison')
        hsin.is_con_full = lambda: True
        hsin.switch_next_char = lambda *args, **kwargs: called.append('switch')
        party(hsin, Named('Chisa'), Named('Rover', 1), Named('Suoming'), Named('ShoreKeeper'))
        hsin.do_perform()
        self.assertEqual(called, ['electro', 'switch'])

    def test_unison_team_does_not_enter_the_electro_rotation(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        called = []
        hsin.perform_everything = lambda: called.append('electro')
        hsin.do_unison_perform = lambda: called.append('unison')
        party(hsin, suo, shore)
        hsin.do_perform()
        self.assertEqual(called, ['unison'])

    def test_wrong_phase_does_not_switch_before_concerto_is_full(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        switched = []
        hsin.fill_timeout = 0
        hsin.is_con_full = lambda: False
        hsin.switch_next_char = lambda *args, **kwargs: switched.append(kwargs) or kwargs
        self.assertIsNone(hsin.do_unison_perform())
        self.assertEqual(switched, [])
        self.assertEqual(task._hsin_unison['phase'], 'shore')

    def test_first_visit_is_enhanced_heavy_then_transform(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        from src.Labels import Labels
        from src.char.Hsin import unison_advance
        unison_advance(suo, 'hsin_heavy', 'Hsin')
        order = []
        hsin.heavy_available = lambda: 2
        hsin.handle_heavy = lambda heavy_type=0: order.append(('heavy', heavy_type)) or True
        hsin.is_con_full = lambda: False
        hsin.click_liberation = lambda wait_if_cd_ready=0: order.append('transform') or True
        hsin.switch_next_char = lambda *args, **kwargs: order.append(kwargs) or kwargs
        task.find_one = lambda name, threshold=0.7: name == Labels.hsin_lib1
        self.assertEqual(hsin.do_unison_perform(), {})
        self.assertEqual(order[:2], [('heavy', 2), 'transform'])
        self.assertEqual(order[-1], {})
        self.assertNotIn({'free_intro': True}, order)
        self.assertEqual(task._hsin_unison, {'phase': 'suoming_enhanced', 'prefer': 'Suoming'})

    def test_second_visit_does_four_attacks_heavy_and_ult_before_shorekeeper(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        from src.Labels import Labels
        from src.char.Hsin import unison_advance
        unison_advance(suo, 'hsin_finish', 'Hsin')
        order = []
        hsin.heavy_available = lambda: 2
        hsin.handle_heavy = lambda heavy_type=0: order.append(('heavy', heavy_type)) or True
        hsin.is_con_full = lambda: True
        hsin.click = lambda: order.append('A')
        hsin.click_liberation = lambda wait_if_cd_ready=0: order.append('ult') or True
        hsin.switch_next_char = lambda *args, **kwargs: order.append(kwargs) or kwargs
        task.find_one = lambda name, threshold=0.7: name == Labels.hsin_lib2
        hsin.do_unison_perform()
        self.assertEqual(order[:4], ['A', 'A', 'A', 'A'])
        self.assertIn(('heavy', 2), order)
        self.assertIn('ult', order)
        self.assertEqual(order[-1], {})
        self.assertLess(order.index(('heavy', 2)), order.index('ult'))
        self.assertEqual(task._hsin_unison, {'phase': 'shore', 'prefer': 'ShoreKeeper'})

    def test_second_visit_does_not_leave_before_the_ult(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        from src.char.Hsin import unison_advance
        unison_advance(suo, 'hsin_finish', 'Hsin')
        hsin.fill_timeout = 0
        hsin.heavy_available = lambda: 0
        hsin.is_con_full = lambda: True
        hsin.liberation_available = lambda: False
        hsin.click = lambda: None
        hsin.switch_next_char = lambda *args, **kwargs: kwargs
        task.find_one = lambda name, threshold=0.7: None
        self.assertIsNone(hsin.do_unison_perform())
        self.assertEqual(task._hsin_unison['phase'], 'hsin_finish')


class SuomingUnisonTest(unittest.TestCase):
    def test_dps_consumes_unison_and_does_not_set_the_chain(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore, config={'Suoming DPS': True})
        order = []
        suo.click_liberation = lambda wait_if_cd_ready=1: order.append('lib') or True
        suo.click_resonance = lambda **kwargs: order.append(('E', kwargs)) or True
        suo.perform_forte = lambda: order.append('forte')
        suo.click_echo = lambda time_out=0: order.append('echo')
        suo.switch_next_char = lambda *args, **kwargs: order.append(kwargs)
        suo.do_perform()
        self.assertEqual(order, ['lib', ('E', {'send_click': False, 'time_out': 1}), 'forte', {}])
        self.assertFalse(hasattr(task, '_hsin_unison'))

    def test_other_teams_still_pass_after_liberation(self):
        suo = Suoming()
        party(suo, Named('Verina'))
        order = []
        suo.click_liberation = lambda wait_if_cd_ready=1: True
        suo.click_echo = lambda time_out=0: order.append('echo')
        suo.switch_next_char = lambda *args, **kwargs: order.append(kwargs)
        suo.do_perform()
        self.assertEqual(order, ['echo', {'free_intro': True}])

    def test_first_visit_waits_for_ult_and_concerto_before_switching(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        from src.char.Suoming import unison_advance
        unison_advance(shore, 'suoming_build', 'Suoming')
        order = []
        suo.fill_timeout = 0
        suo.liberation_available = lambda: False
        suo.is_con_full = lambda: False
        suo.click = lambda: order.append('A')
        suo.switch_next_char = lambda *args, **kwargs: order.append(kwargs)
        self.assertIsNone(suo.do_perform())
        self.assertEqual(order, [])
        self.assertEqual(task._hsin_unison['phase'], 'suoming_build')

        suo.fill_timeout = 12
        suo.liberation_available = lambda: True
        suo.is_con_full = lambda: True
        suo.click_liberation = lambda wait_if_cd_ready=1: order.append('ult') or True
        suo.do_perform()
        self.assertEqual(order, ['ult', {}])
        self.assertNotIn({'free_intro': True}, order)
        self.assertEqual(
            task._hsin_unison,
            {'phase': 'hsin_heavy', 'prefer': 'Hsin', 'suoming_ult': True},
        )

    def test_ult_is_pressed_before_concerto_and_switch_waits(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        from src.char.Suoming import unison_advance
        unison_advance(shore, 'suoming_build', 'Suoming')
        order = []
        suo.fill_timeout = 0.05
        suo.liberation_available = lambda: True
        suo.is_con_full = lambda: False
        suo.click_liberation = lambda wait_if_cd_ready=1: order.append('ult') or True
        suo.click = lambda: order.append('A')
        suo.switch_next_char = lambda *args, **kwargs: order.append('switch')
        self.assertIsNone(suo.do_perform())
        self.assertIn('ult', order)
        self.assertNotIn('switch', order)
        self.assertEqual(task._hsin_unison['phase'], 'suoming_build')
        self.assertTrue(task._hsin_unison['suoming_ult'])

        order.clear()
        suo.fill_timeout = 12
        suo.liberation_available = lambda: False
        suo.is_con_full = lambda: True
        suo.click_liberation = lambda wait_if_cd_ready=1: order.append('ult-again') or False
        suo.switch_next_char = lambda *args, **kwargs: kwargs
        self.assertEqual(suo.do_perform(), {})
        self.assertNotIn('ult-again', order)
        self.assertEqual(task._hsin_unison['phase'], 'hsin_heavy')
        self.assertEqual(task._hsin_unison['prefer'], 'Hsin')

    def test_ult_is_pressed_when_the_ready_check_is_wrong(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        from src.char.Suoming import unison_advance
        unison_advance(shore, 'suoming_build', 'Suoming')
        calls = []
        suo.fill_timeout = 12
        suo.liberation_available = lambda: False
        suo.is_con_full = lambda: True

        def click_liberation(wait_if_cd_ready=0):
            calls.append(wait_if_cd_ready)
            return True

        suo.click_liberation = click_liberation
        suo.click = lambda: None
        suo.switch_next_char = lambda *args, **kwargs: kwargs
        self.assertEqual(suo.do_perform(), {})
        self.assertEqual(calls, [1])
        self.assertEqual(task._hsin_unison['phase'], 'hsin_heavy')

    def test_yellow_unison_switches_after_the_ult(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        from src.char.Suoming import unison_advance
        unison_advance(shore, 'suoming_build', 'Suoming')
        suo.fill_timeout = 12
        suo.liberation_available = lambda: True
        suo.is_con_full = lambda: False
        suo.click_liberation = lambda wait_if_cd_ready=1: True
        suo.click = lambda: None
        suo.switch_next_char = lambda *args, **kwargs: kwargs
        task.find_one = lambda name, threshold=0.7: name == 'yellow_unison'
        self.assertEqual(suo.do_perform(), {})
        self.assertEqual(task._hsin_unison['phase'], 'hsin_heavy')

    def test_second_visit_presses_a_lit_ult_without_skipping_the_combo(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        from src.char.Suoming import unison_advance
        unison_advance(hsin, 'suoming_enhanced', 'Suoming')
        order = []
        suo.forte_available = lambda: True
        suo.liberation_available = lambda: True
        suo.is_con_full = lambda: True
        suo.click_resonance = lambda **kwargs: order.append('enhanced-e')
        suo.click_liberation = lambda wait_if_cd_ready=1: order.append('ult') or True
        suo.click = lambda: order.append('A')
        suo.switch_next_char = lambda *args, **kwargs: order.append(kwargs) or kwargs
        self.assertEqual(suo.do_perform(), {})
        self.assertEqual(order[0], 'enhanced-e')
        self.assertEqual(order[1:9], ['A'] * 8)
        self.assertEqual(order[9], 'ult')
        self.assertEqual(order[-1], {})
        self.assertEqual(task._hsin_unison['phase'], 'hsin_finish')

    def test_second_visit_finishes_enhanced_basics_before_hsin(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        from src.char.Suoming import unison_advance
        unison_advance(hsin, 'suoming_enhanced', 'Suoming')
        order = []
        suo.forte_available = lambda: True
        suo.is_con_full = lambda: True
        suo.click_resonance = lambda **kwargs: order.append('enhanced-e')
        suo.click = lambda: order.append('A')
        suo.switch_next_char = lambda *args, **kwargs: order.append(kwargs) or kwargs
        self.assertEqual(suo.do_perform(), {})
        self.assertEqual(order[0], 'enhanced-e')
        self.assertEqual(order[1:9], ['A'] * 8)
        self.assertEqual(order[-1], {})
        self.assertEqual(task._hsin_unison, {'phase': 'hsin_finish', 'prefer': 'Hsin'})


class ShoreKeeperUnisonTest(unittest.TestCase):
    def test_augusta_must_wins_while_someone_else_holds_unison(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        party(hsin, suo, shore)
        from src.char.ShoreKeeper import unison_advance
        unison_advance(shore, 'hsin_r1', 'Hsin')
        shore.attribute = 2
        current = Named('Augusta')
        current.char_name = 'Augusta'
        self.assertEqual(
            shore.get_switch_priority(current, has_intro=True),
            SWITCH.MUST,
        )
        shore.attribute = 1
        self.assertEqual(
            shore.get_switch_priority(current, has_intro=True),
            SWITCH.NORMAL,
        )

    def test_unison_prefer_is_must_after_the_augusta_check(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        party(hsin, suo, shore)
        shore.attribute = 1
        self.assertEqual(shore.get_switch_priority(), SWITCH.NORMAL)
        from src.char.ShoreKeeper import unison_advance
        unison_advance(shore, 'suoming_arm', 'Suoming')
        self.assertEqual(shore.get_switch_priority(), SWITCH.NORMAL)
        self.assertEqual(suo.get_switch_priority(), SWITCH.MUST)
        suo.on_combat_end(['pickup'])
        self.assertEqual(suo.combat_ended, ['pickup'])
        self.assertIsNone(suo.task._hsin_unison['prefer'])
        self.assertEqual(suo.get_switch_priority(), SWITCH.NORMAL)

    def test_original_kit_names_suoming_and_still_heavies(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        order = []
        shore.liberation_available = lambda: False
        shore.click = lambda: order.append('A')
        shore.click_liberation = lambda *args, **kwargs: order.append('lib') or True
        shore.click_echo = lambda time_out=0: order.append('echo')
        shore.click_resonance = lambda *args, **kwargs: order.append('E') or (False, 0)
        shore.is_mouse_forte_full = lambda: True
        released = []
        task.mouse_down = lambda: order.append('heavy')
        task.mouse_up = lambda: released.append('up')
        shore.is_con_full = lambda: True
        switched = {}

        def switch(*args, **kwargs):
            switched.update(kwargs)
            order.append(kwargs)
            if shore.is_con_full():
                shore.outrotime = time.time()
                shore.dodge_count = 5
            return kwargs

        shore.switch_next_char = switch
        shore.do_perform()
        self.assertEqual(order, ['A', 'A', 'A', 'A', 'heavy', 'E', 'echo', 'lib', {}])
        self.assertEqual(released, ['up'])
        self.assertNotIn('free_intro', switched)
        self.assertEqual(task._hsin_unison, {'phase': 'suoming_build', 'prefer': 'Suoming'})
        self.assertEqual(shore.dodge_count, 5)

    def test_does_not_switch_before_concerto_is_full(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        order = []
        shore.fill_timeout = 0
        shore.is_con_full = lambda: False
        shore.click = lambda: order.append('A')
        shore.click_liberation = lambda *args, **kwargs: order.append('lib') or True
        shore.click_echo = lambda time_out=0: order.append('echo')
        shore.click_resonance = lambda *args, **kwargs: True
        shore.is_mouse_forte_full = lambda: False
        task.mouse_down = lambda: order.append('heavy')
        task.mouse_up = lambda: None
        shore.switch_next_char = lambda *args, **kwargs: order.append('switch')
        shore.do_perform()
        self.assertEqual(order, ['A', 'A', 'A', 'A', 'heavy', 'echo', 'lib'])
        self.assertEqual(task._hsin_unison['phase'], 'shore')

    def test_other_teams_still_switch_after_the_old_opener(self):
        shore = ShoreKeeper()
        party(shore, Named('Augusta'))
        order = []
        shore.click_resonance = lambda *args, **kwargs: True
        shore.switch_next_char = lambda *args, **kwargs: order.append('switch') or kwargs
        shore.do_perform()
        self.assertEqual(order, ['switch'])


def unison_of(char):
    from src.char.Hsin import unison_team
    return unison_team(char)


if __name__ == '__main__':
    unittest.main()
