import time

from src.char.BaseChar import BaseChar, SwitchPriority

# UNISON_SHARED_BEGIN
# 心、鎖暝、守岸人各有一份，內容必須相同。三人互不 import。
UNISON_ATTR = '_hsin_unison'


def _unison_names(task):
    return {c.name for c in getattr(task, 'chars', []) or [] if c is not None}


def unison_team(char):
    """只有心、鎖暝、守岸人，且鎖暝不是主 C 設定，才走同奏。"""
    task = getattr(char, 'task', None)
    if task is None:
        return False
    config = getattr(task, 'char_config', None) or {}
    if config.get('Suoming DPS'):
        return False
    return {'Hsin', 'Suoming', 'ShoreKeeper'} <= _unison_names(task)


def unison_state(char):
    task = getattr(char, 'task', None)
    if task is None:
        return None
    state = getattr(task, UNISON_ATTR, None)
    if state is None:
        state = {'phase': 'shore', 'prefer': None}
        setattr(task, UNISON_ATTR, state)
    return state


def unison_wants(char):
    if not unison_team(char):
        return False
    state = unison_state(char)
    return bool(state and state.get('prefer') and state.get('prefer') == char.name)


def unison_advance(char, phase, prefer):
    state = unison_state(char)
    if state is None:
        return None
    state['phase'] = phase
    state['prefer'] = prefer
    return state


def unison_clear_prefer(char):
    task = getattr(char, 'task', None)
    state = getattr(task, UNISON_ATTR, None) if task is not None else None
    if isinstance(state, dict):
        state['prefer'] = None


def unison_owner(char):
    phase = (unison_state(char) or {}).get('phase') or 'shore'
    return {
        'shore': 'ShoreKeeper',
        'suoming_build': 'Suoming',
        'hsin_heavy': 'Hsin',
        'suoming_enhanced': 'Suoming',
        'hsin_finish': 'Hsin',
    }.get(phase, 'ShoreKeeper')


def reset_unison(char):
    task = getattr(char, 'task', None)
    if task is None or not unison_team(char):
        return
    setattr(task, UNISON_ATTR, {'phase': 'shore', 'prefer': None})
# UNISON_SHARED_END


class ShoreKeeper(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outrotime = -1
        self.dodge_count = 0
        self.attribute = 0
        self.check_f_on_switch = True

    def reset_state(self):
        super().reset_state()
        reset_unison(self)

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        self.decide_teammate()
        current_name = current_char.char_name if current_char else None
        if self.attribute == 2 and has_intro and current_name in {'Augusta', 'char_augusta'}:
            return SwitchPriority.MUST
        if unison_wants(self):
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    def skip_combat_check(self):
        return self.has_intro or self.flying()

    def decide_teammate(self):
        from src.char.Augusta import Augusta
        if self.attribute > 0:
            return
        if self.task.has_char(Augusta):
            self.attribute = 2
        else:
            self.attribute = 1

    def on_combat_end(self, chars):
        parent = getattr(super(), 'on_combat_end', None)
        result = parent(chars) if parent is not None else None
        unison_clear_prefer(self)
        return result

    def do_perform(self):
        if unison_team(self):
            return self._farm_perform()
        if self.has_intro:
            self.task.skip_combat_check = True
            try:
                self.logger.debug('ShoreKeeper wait intro animation')
                time.sleep(0.1)
                if not self.task.in_team_and_world():
                    self.task.wait_in_team_and_world(time_out=4, raise_if_not_found=False)
                else:
                    self.continues_normal_attack(1.2)
            finally:
                self.task.skip_combat_check = False
        self.click_echo(time_out=0)
        self.click_liberation()
        if not self._resonance_cast():
            self.heavy_click_forte(self.is_mouse_forte_full)
        self.switch_next_char()

    def _farm_perform(self):
        # 開場 AAAA、重擊、E、生骸，大招放最後。協奏打滿才切鎖暝。
        unison_clear_prefer(self)
        phase = (unison_state(self) or {}).get('phase') or 'shore'
        if phase != 'shore':
            return self._farm_yield()
        self._farm_clicks(4)
        self.heavy_click_forte(self.is_mouse_forte_full)
        self._resonance_cast()
        self.click_echo(time_out=0)
        self.click_liberation()
        if not self._attack_until(self.is_con_full):
            self.logger.info('ShoreKeeper farm: concerto not full, keep hitting')
            return None
        unison_advance(self, 'suoming_build', 'Suoming')
        self.logger.info('ShoreKeeper farm: concerto full, switch to Suoming')
        return self.switch_next_char()

    def _farm_yield(self):
        owner = unison_owner(self)
        if not self._attack_until(self.is_con_full):
            self.click()
            return None
        state = unison_state(self)
        if state is not None:
            state['prefer'] = owner
        return self.switch_next_char()

    def _farm_clicks(self, count):
        for _ in range(count):
            self.check_combat()
            self.click()
            self.sleep(0.05)

    def _attack_until(self, ready):
        deadline = time.time() + getattr(self, 'fill_timeout', 12)
        while time.time() < deadline:
            self.check_combat()
            if ready():
                return True
            self.click()
            self.sleep(0.02)
        return bool(ready())

    def _resonance_cast(self):
        result = self.click_resonance()
        if isinstance(result, (tuple, list)):
            return bool(result and result[0])
        return bool(result)

    def switch_next_char(self, *args, **kwargs):
        if self.is_con_full():
            self.outrotime = time.time()
            self.dodge_count = 5
        return super().switch_next_char(*args, **kwargs)

    def auto_dodge(self, condition):
        clicked = False
        if self.time_elapsed_accounting_for_freeze(self.outrotime) < 30 and self.dodge_count > 0:
            start = time.time()
            while time.time() - start < 1.5:
                if not condition():
                    break
                self.continues_right_click(0.05)
                self.sleep(0.05)
                clicked = True
                self.task.next_frame()
        if clicked:
            self.dodge_count -= 1
            self.logger.info('ShoreKeepers auto dodge success!')
        return clicked
