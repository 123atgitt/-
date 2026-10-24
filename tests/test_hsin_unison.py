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
        self.assertEqual(task._hsin_unison, {'phase': 'shore', 'prefer': 'ShoreKeeper'})


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

    def test_r1_pass_is_immediate_and_a_miss_does_not_advance(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        from src.char.Hsin import unison_advance
        unison_advance(shore, 'hsin_r1', 'Hsin')
        switched = []
        hsin.switch_next_char = lambda *args, **kwargs: switched.append(kwargs) or kwargs
        hsin.heavy_available = lambda: 0
        hsin._cast_marked_liberation = lambda lib2=False: False
        hsin.time_elapsed_accounting_for_freeze = lambda _start: 100
        hsin.send_resonance_key = lambda: switched.append('E')
        self.assertIsNone(hsin._unison_arm())
        self.assertEqual(switched, [])
        self.assertEqual(task._hsin_unison['phase'], 'hsin_r1')

        hsin.time_elapsed_accounting_for_freeze = lambda _start: 0
        hsin._cast_marked_liberation = lambda lib2=False: not lib2
        result = hsin._unison_arm()
        self.assertEqual(result, {'free_intro': True})
        self.assertEqual(task._hsin_unison, {'phase': 'suoming_pass', 'prefer': 'Suoming'})
        self.assertNotIn('E', switched)

    def test_r2_holds_heavy_then_switches_without_skill_or_free_intro(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        from src.char.Hsin import unison_advance
        unison_advance(suo, 'hsin_r2', 'Hsin')
        seen = {'heavy': 0}
        order = []

        def heavy_available():
            seen['heavy'] += 1
            return 2 if seen['heavy'] == 1 else 0

        def handle_heavy(heavy_type=0):
            order.append(('heavy', heavy_type))
            hsin.h2_completed = heavy_type == 2
            return True

        hsin.heavy_available = heavy_available
        hsin.handle_heavy = handle_heavy
        hsin._cast_marked_liberation = lambda lib2=False: order.append(('lib', lib2)) or lib2
        hsin.switch_next_char = lambda *args, **kwargs: order.append(kwargs) or kwargs
        hsin.send_resonance_key = lambda: order.append('E')
        result = hsin._unison_finish()
        self.assertEqual(order, [('heavy', 2), ('lib', True), {}])
        self.assertEqual(result, {})
        self.assertEqual(task._hsin_unison, {'phase': 'shore', 'prefer': 'ShoreKeeper'})

    def test_r2_waits_through_the_heavy_animation_without_clicking(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        party(hsin, suo, shore)
        from src.char.Hsin import unison_advance
        unison_advance(suo, 'hsin_r2', 'Hsin')
        seen = {'heavy': 0}
        clicks = []

        def heavy_available():
            seen['heavy'] += 1
            return 2 if seen['heavy'] == 1 else 0

        def handle_heavy(heavy_type=0):
            hsin.h2_completed = True
            hsin.h2_guard_until = time.time() + 4
            return True

        calls = {'n': 0}

        def elapsed(_start):
            calls['n'] += 1
            return 100 if calls['n'] > 2 else 0

        hsin.heavy_available = heavy_available
        hsin.handle_heavy = handle_heavy
        hsin.time_elapsed_accounting_for_freeze = elapsed
        hsin._cast_marked_liberation = lambda lib2=False: False
        hsin.click = lambda: clicks.append('click')
        hsin.switch_next_char = lambda *args, **kwargs: kwargs
        self.assertIsNone(hsin._unison_finish())
        self.assertEqual(clicks, [])

    def test_r2_miss_stays_on_the_damage_visit(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        from src.char.Hsin import unison_advance
        unison_advance(suo, 'hsin_r2', 'Hsin')
        hsin.heavy_available = lambda: 0
        hsin._cast_marked_liberation = lambda lib2=False: False
        hsin.time_elapsed_accounting_for_freeze = lambda _start: 100
        hsin.switch_next_char = lambda *args, **kwargs: kwargs
        self.assertIsNone(hsin._unison_finish())
        self.assertEqual(task._hsin_unison['phase'], 'hsin_r2')


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

    def test_support_uses_the_original_cast_then_passes(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        from src.char.Suoming import unison_advance
        unison_advance(shore, 'suoming_arm', 'Suoming')
        order = []
        suo.has_intro = True
        suo.continues_normal_attack = lambda duration=0, until_con_full=False: order.append(('attack', duration))
        suo.click_echo = lambda time_out=0: order.append('echo')
        suo.click_resonance = lambda **kwargs: order.append('E')
        suo.click_liberation = lambda wait_if_cd_ready=1: False
        suo.perform_forte = lambda: order.append('forte')
        suo.switch_next_char = lambda *args, **kwargs: order.append(kwargs) or kwargs
        suo.do_perform()
        self.assertEqual(order, [('attack', 1.6), 'echo', 'forte', {}])
        self.assertNotIn('E', order)
        self.assertEqual(task._hsin_unison['phase'], 'suoming_arm')

        order.clear()
        suo.click_liberation = lambda wait_if_cd_ready=1: order.append(('lib', wait_if_cd_ready)) or True
        suo.do_perform()
        self.assertEqual(order, [('attack', 1.6), ('lib', 1), 'echo', {'free_intro': True}])
        self.assertEqual(task._hsin_unison, {'phase': 'hsin_r1', 'prefer': 'Hsin'})

    def test_second_pass_arms_the_damage_visit(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        from src.char.Suoming import unison_advance
        unison_advance(hsin, 'suoming_pass', 'Suoming')
        suo.click_liberation = lambda wait_if_cd_ready=1: True
        suo.switch_next_char = lambda *args, **kwargs: kwargs
        self.assertEqual(suo.do_perform(), {'free_intro': True})
        self.assertEqual(task._hsin_unison, {'phase': 'hsin_r2', 'prefer': 'Hsin'})
        self.assertEqual(suo.get_switch_priority(), SWITCH.NORMAL)


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
        self.assertEqual(shore.get_switch_priority(), SWITCH.MUST)
        from src.char.ShoreKeeper import unison_advance
        unison_advance(shore, 'suoming_arm', 'Suoming')
        self.assertEqual(shore.get_switch_priority(), SWITCH.NORMAL)
        self.assertEqual(suo.get_switch_priority(), SWITCH.MUST)

    def test_original_kit_names_suoming_and_still_heavies(self):
        hsin, suo, shore = Hsin(), Suoming(), ShoreKeeper()
        task = party(hsin, suo, shore)
        order = []
        shore.liberation_available = lambda: False
        shore.click_liberation = lambda *args, **kwargs: order.append('lib') or True
        shore.click_echo = lambda time_out=0: order.append('echo')
        shore.click_resonance = lambda *args, **kwargs: order.append('E') or (False, 0)
        shore.heavy_click_forte = lambda *args, **kwargs: order.append('heavy')
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
        self.assertEqual(order, ['echo', 'lib', 'E', 'heavy', {}])
        self.assertNotIn('free_intro', switched)
        self.assertEqual(task._hsin_unison, {'phase': 'suoming_arm', 'prefer': 'Suoming'})
        self.assertEqual(shore.dodge_count, 5)

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
