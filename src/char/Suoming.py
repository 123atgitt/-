import time

from src.Labels import Labels
from src.char.BaseChar import BaseChar, CharType, SwitchPriority, get_default_buff_time

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


class Suoming(BaseChar):
    FORTE_TIMEOUT = 15
    RESONANCE_HOLD_TIMEOUT = 6
    RESONANCE_READY_TIMEOUT = 8

    def is_dps_config(self):
        return bool(self.task and self.task.char_config.get('Suoming DPS', False))

    def get_char_type(self):
        return CharType.MAIN_DPS if self.is_dps_config() else CharType.SUB_DPS

    def get_buff_time(self):
        if self.is_dps_config():
            return get_default_buff_time(CharType.MAIN_DPS)
        return super().get_buff_time()

    def reset_state(self):
        super().reset_state()
        reset_unison(self)

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if unison_wants(self):
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    def on_combat_end(self, chars):
        parent = getattr(super(), 'on_combat_end', None)
        result = parent(chars) if parent is not None else None
        unison_clear_prefer(self)
        return result

    def do_perform(self):
        if not self.is_dps_config() and unison_team(self):
            return self._farm_perform()
        # Kit reference: https://ww.nanoka.cc/character/1312/
        if self.has_intro:
            self.continues_normal_attack(duration=1.6)
        liberated = self.click_liberation(wait_if_cd_ready=1)
        dps = self.is_dps_config()
        # Support passes Unison; DPS consumes it with Rift Cleaver for Seal Master.
        if liberated and not dps:
            self.click_echo(time_out=0)
            return self.switch_next_char(free_intro=True)

        if liberated or self.has_intro:
            if not liberated:
                self.click_echo(time_out=0)
            if dps:
                self.click_resonance(send_click=False, time_out=1)
            self.perform_forte()
        else:
            self.continues_normal_attack(1.1)
        self.switch_next_char()

    def _farm_perform(self):
        unison_clear_prefer(self)
        phase = (unison_state(self) or {}).get('phase') or 'shore'
        if phase == 'suoming_build':
            return self._farm_build()
        if phase == 'suoming_enhanced':
            return self._farm_enhanced()
        return self._farm_yield()

    def _farm_build(self):
        # 技能和普攻打到大招、協奏都滿，再開大切心。沒滿不切。
        self.logger.info('Suoming farm: skills until ult and concerto are full')
        deadline = time.time() + getattr(self, 'fill_timeout', 12)
        while time.time() < deadline:
            self.check_combat()
            if self.liberation_available() and self.is_con_full():
                break
            self._press_skill_or_attack()
            self.sleep(0.02)
        else:
            self.logger.info('Suoming farm: ult or concerto not full, keep hitting')
            return None
        if not self.click_liberation(wait_if_cd_ready=0):
            self.click()
            self.logger.info('Suoming farm: ult not cast, keep hitting')
            return None
        unison_advance(self, 'hsin_heavy', 'Hsin')
        self.logger.info('Suoming farm: ult cast, switch to Hsin')
        return self.switch_next_char()

    def _farm_enhanced(self):
        # 一直打到強化 E，強化普攻打完，協奏滿了才切心。
        self.logger.info('Suoming farm: attack until enhanced E')
        if not self._attack_until(self.forte_available):
            self.logger.info('Suoming farm: enhanced E not ready, keep hitting')
            return None
        self.click_resonance(send_click=True, time_out=0)
        self.logger.info('Suoming farm: enhanced basics')
        self._farm_clicks(8)
        if not self._attack_until(self.is_con_full):
            self.logger.info('Suoming farm: concerto not full, keep hitting')
            return None
        unison_advance(self, 'hsin_finish', 'Hsin')
        self.logger.info('Suoming farm: enhanced combo done, switch to Hsin')
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

    def _press_skill_or_attack(self):
        available = getattr(self, 'resonance_available', None)
        if callable(available) and available():
            self.click_resonance(send_click=True, time_out=0)
            return
        self.click()

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

    def forte_available(self):
        return bool(self.task.find_one(Labels.suoming_forte_e))

    def perform_forte(self):
        self.continues_click_until(self.forte_available, time_out=self.FORTE_TIMEOUT)
        self.hold_forte_resonance()

    def hold_forte_resonance(self):
        key = self.get_resonance_key()
        start = time.time()
        down = False
        try:
            self.check_combat()
            while (self.time_elapsed_accounting_for_freeze(start) < self.RESONANCE_HOLD_TIMEOUT
                   and self.forte_available()):
                if down:
                    self.task.send_key_up(key)
                    self.sleep(0.1)
                self.task.send_key_down(key)
                down = True
                self.sleep(2)
            self.sleep(3)
            self.task.wait_until(self.resonance_available, time_out=self.RESONANCE_READY_TIMEOUT,
                                 pre_action=self.check_combat)
        finally:
            self.task.send_key_up(key)
        self.click_echo()
        self.sleep(0.01)
