import unittest

from src.char.hsin_electro_loop import (
    PHASE_CHISA_OPEN,
    PHASE_ROVER_FINAL,
    get_loop,
    is_hsin_electro_team,
    reset_loop,
    set_prefer,
    wants_must,
)


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


class ElectroLoopTest(unittest.TestCase):
    def team(self, form=-1):
        chars = [Char('Hsin'), Char('Chisa'), Char('Rover', form)]
        return Task(chars), chars

    def test_unknown_or_electric_rover_counts_as_this_team(self):
        task, chars = self.team(-1)
        self.assertTrue(is_hsin_electro_team(chars[0]))
        chars[2].ring_index = 1
        self.assertTrue(is_hsin_electro_team(chars[1]))

    def test_other_rover_forms_and_missing_teammates_do_not(self):
        task, chars = self.team(5)
        self.assertFalse(is_hsin_electro_team(chars[0]))
        chars[2].ring_index = 1
        task.chars = [chars[0], chars[2]]
        self.assertFalse(is_hsin_electro_team(chars[0]))

    def test_prefer_selects_only_the_named_teammate(self):
        task, (hsin, chisa, rover) = self.team(1)
        created = set_prefer(chisa, 'Rover', phase=PHASE_ROVER_FINAL)
        self.assertEqual(created['phase'], PHASE_ROVER_FINAL)
        self.assertTrue(wants_must(rover))
        self.assertFalse(wants_must(hsin))
        self.assertFalse(wants_must(chisa))

    def test_stale_prefer_is_ignored_when_the_team_stops_matching(self):
        task, chars = self.team(1)
        set_prefer(chars[1], 'Chisa', phase=PHASE_CHISA_OPEN)
        self.assertTrue(wants_must(chars[1]))
        chars[2].ring_index = 4
        self.assertFalse(wants_must(chars[1]))
        self.assertIsNone(get_loop(chars[0]))

    def test_reset_returns_to_chisa_open(self):
        task, chars = self.team(1)
        set_prefer(chars[0], 'Hsin', phase=PHASE_ROVER_FINAL)
        reset_loop(chars[2])
        self.assertEqual(task._hsin_electro_loop['phase'], PHASE_CHISA_OPEN)
        self.assertIsNone(task._hsin_electro_loop['prefer'])
        self.assertFalse(wants_must(chars[0]))


if __name__ == '__main__':
    unittest.main()
