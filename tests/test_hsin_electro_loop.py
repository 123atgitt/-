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
        task = Task(chars)
        return task, chars

    def test_three_scripts_share_one_block_and_do_not_import_it(self):
        blocks = [shared_block(name) for name in CHAR_FILES]
        self.assertEqual(blocks[0], blocks[1])
        self.assertEqual(blocks[0], blocks[2])
        for name in CHAR_FILES:
            text = (CHAR_DIR / name).read_text(encoding='utf-8')
            self.assertNotIn('src.char.hsin_electro_loop', text)

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

    def test_prefer_selects_only_the_named_teammate(self):
        task, (hsin, chisa, rover) = self.team(1)
        created = self.ns['set_prefer'](chisa, 'Rover', phase=self.ns['PHASE_ROVER_FINAL'])
        self.assertEqual(created['phase'], self.ns['PHASE_ROVER_FINAL'])
        self.assertIs(created, task._hsin_electro_loop)
        self.assertTrue(self.ns['wants_must'](rover))
        self.assertFalse(self.ns['wants_must'](hsin))
        self.assertFalse(self.ns['wants_must'](chisa))

    def test_stale_prefer_is_ignored_when_the_team_stops_matching(self):
        task, chars = self.team(1)
        self.ns['set_prefer'](chars[1], 'Chisa', phase=self.ns['PHASE_CHISA_OPEN'])
        self.assertTrue(self.ns['wants_must'](chars[1]))
        chars[2].ring_index = 4
        self.assertFalse(self.ns['wants_must'](chars[1]))
        self.assertIsNone(self.ns['get_loop'](chars[0]))

    def test_wrong_character_yields_the_field_back(self):
        task, (hsin, chisa, rover) = self.team(1)
        self.ns['set_prefer'](chisa, 'Rover', phase=self.ns['PHASE_ROVER_AXIS'])
        self.ns['consume_prefer'](rover)
        self.assertTrue(self.ns['leave_if_not_owner'](hsin))
        self.assertEqual(hsin.switched, 1)
        self.assertEqual(task._hsin_electro_loop['prefer'], 'Rover')
        self.assertFalse(self.ns['leave_if_not_owner'](rover))
        self.assertEqual(rover.switched, 0)

    def test_yield_stops_after_two_bounces(self):
        task, chars = self.team(1)
        self.ns['get_loop'](chars[0])['phase'] = self.ns['PHASE_HSIN']
        self.assertTrue(self.ns['leave_if_not_owner'](chars[1]))
        self.assertTrue(self.ns['leave_if_not_owner'](chars[1]))
        self.assertFalse(self.ns['leave_if_not_owner'](chars[1]))

    def test_reset_returns_to_chisa_open(self):
        task, chars = self.team(1)
        self.ns['set_prefer'](chars[0], 'Hsin', phase=self.ns['PHASE_ROVER_FINAL'])
        self.ns['reset_loop'](chars[2])
        self.assertEqual(task._hsin_electro_loop['phase'], self.ns['PHASE_CHISA_OPEN'])
        self.assertIsNone(task._hsin_electro_loop['prefer'])
        self.assertFalse(self.ns['wants_must'](chars[0]))


class Logger:
    def info(self, message):
        self.message = message


class Char:
    def __init__(self, name, form=-1):
        self.name = name
        self.ring_index = form
        self._last_known_form = -1
        self.task = None
        self.logger = Logger()
        self.switched = 0

    def switch_next_char(self):
        self.switched += 1


class Task:
    def __init__(self, chars):
        self.chars = chars
        for char in chars:
            char.task = self


if __name__ == '__main__':
    unittest.main()
