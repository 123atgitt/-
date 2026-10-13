import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHAR_DIR = ROOT / 'src' / 'char'
CHAR_FILES = ('Hsin.py', 'Chisa.py', 'Rover.py')
BEGIN = '# ELECTRO_LOOP_SHARED_BEGIN\n'
END = '# ELECTRO_LOOP_SHARED_END\n'


def shared_block(name):
    text = (CHAR_DIR / name).read_text(encoding='utf-8')
    start = text.index(BEGIN) + len(BEGIN)
    end = text.index(END, start)
    return text[start:end]


def load_shared():
    namespace = {}
    exec(shared_block('Chisa.py'), namespace)
    return namespace


class ElectroLoopTest(unittest.TestCase):
    def setUp(self):
        self.ns = load_shared()

    def team(self, form=-1):
        chars = [Char('Hsin'), Char('Chisa'), Char('Rover', form)]
        return Task(chars), chars

    def test_three_scripts_share_one_block_and_do_not_import_it(self):
        blocks = [shared_block(name) for name in CHAR_FILES]
        self.assertEqual(blocks[0], blocks[1])
        self.assertEqual(blocks[0], blocks[2])
        for name in CHAR_FILES:
            text = (CHAR_DIR / name).read_text(encoding='utf-8')
            self.assertNotIn('src.char.hsin_electro_loop', text)
            self.assertNotIn('leave_if_not_owner', text)
            self.assertIn('PHASE_ROVER_AXIS', text)
            self.assertIn('PHASE_CHISA_SAW', text)

    def test_unknown_or_electric_rover_counts_as_this_team(self):
        task, chars = self.team(-1)
        self.assertTrue(self.ns['is_hsin_electro_team'](chars[0]))
        chars[2].ring_index = 1
        self.assertTrue(self.ns['is_hsin_electro_team'](chars[1]))

    def test_other_rover_forms_and_missing_teammates_do_not(self):
        task, chars = self.team(5)
        self.assertFalse(self.ns['is_hsin_electro_team'](chars[0]))
        chars[2].ring_index = 1
        task.chars = [chars[0], chars[2]]
        self.assertFalse(self.ns['is_hsin_electro_team'](chars[0]))

    def test_prefer_selects_only_the_next_character(self):
        task, (hsin, chisa, rover) = self.team(1)
        created = self.ns['set_prefer'](chisa, 'Rover')
        self.assertIs(created, task._hsin_electro_loop)
        self.assertTrue(self.ns['wants_must'](rover))
        self.assertFalse(self.ns['wants_must'](hsin))
        self.assertFalse(self.ns['wants_must'](chisa))
        self.ns['set_prefer'](rover, 'Hsin')
        self.assertTrue(self.ns['wants_must'](hsin))
        self.assertFalse(self.ns['wants_must'](rover))

    def test_stale_prefer_is_ignored_when_the_team_stops_matching(self):
        task, chars = self.team(1)
        self.ns['set_prefer'](chars[1], 'Chisa')
        self.assertTrue(self.ns['wants_must'](chars[1]))
        chars[2].ring_index = 4
        self.assertFalse(self.ns['wants_must'](chars[1]))
        self.assertIsNone(self.ns['get_loop'](chars[0]))

    def test_reset_clears_prefer(self):
        task, chars = self.team(1)
        self.ns['set_prefer'](chars[0], 'Hsin', phase=self.ns['PHASE_HSIN'])
        self.ns['reset_loop'](chars[2])
        self.assertIsNone(task._hsin_electro_loop['prefer'])
        self.assertEqual(task._hsin_electro_loop['phase'], self.ns['PHASE_CHISA_OPEN'])
        self.assertFalse(self.ns['wants_must'](chars[0]))

    def test_phase_follows_the_axis(self):
        task, (hsin, chisa, rover) = self.team(1)
        self.ns['set_prefer'](chisa, 'Rover', phase=self.ns['PHASE_ROVER_AXIS'])
        self.assertEqual(task._hsin_electro_loop['phase'], 'rover_axis')
        self.assertTrue(self.ns['wants_must'](rover))
        self.assertTrue(self.ns['axis_still_open'](FakeCon(0.2)))
        self.assertTrue(self.ns['axis_still_open'](FakeCon(0.8)))
        self.assertFalse(self.ns['axis_still_open'](FakeCon(0.81)))
        self.assertFalse(self.ns['axis_still_open'](FakeCon(1)))


class FakeCon:
    def __init__(self, value):
        self.current_con = 0
        self._value = value

    def is_con_full(self):
        return self._value >= 1

    def get_current_con(self):
        return self._value


class Char:
    def __init__(self, name, form=-1):
        self.name = name
        self.ring_index = form
        self._last_known_form = -1
        self.task = None


class Task:
    def __init__(self, chars):
        self.chars = chars
        for char in chars:
            char.task = self


if __name__ == '__main__':
    unittest.main()
