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
        # 變奏進來先接普攻和 E。協奏滿或同奏黃了就切心，不等大招。
        self.logger.info('Suoming farm: fill concerto with the combo, then Hsin')
        if self.has_intro:
            self.continues_normal_attack(0.4)
        self.click_echo(time_out=0)
        if not self._fight(lambda: self.is_con_full() or self._yellow_unison()):
            self.logger.info('Suoming farm: concerto not full, keep hitting')
            return None
        unison_advance(self, 'hsin_heavy', 'Hsin')
        self.logger.info('Suoming farm: concerto full, switch to Hsin')
        return self.switch_next_char()

    def _farm_enhanced(self):
        # 同奏進場會灌大招。亮了就開，開完心吃同奏。沒亮就繼續連段和閃避反擊把能量補滿。
        self.logger.info('Suoming farm: unison entry, ult, then Hsin')
        if self.has_intro:
            self.continues_normal_attack(0.3)
        self.click_echo(time_out=0)
        deadline = time.time() + getattr(self, 'fill_timeout', 8)
        next_ult = 0.0
        next_skill = 0.0
        while time.time() < deadline:
            self.check_combat()
            now = time.time()
            if now >= next_ult:
                next_ult = now + 0.45
                if self._cast_ult():
                    unison_advance(self, 'hsin_finish', 'Hsin')
                    self.logger.info('Suoming farm: ult cast, Hsin can unison in')
                    return self.switch_next_char()
            if now >= next_skill and (self._enhanced_ready() or self._resonance_ready()):
                next_skill = now + 0.4
                self.click_resonance(send_click=True, time_out=0)
            else:
                self._combo_and_dodge()
            self.sleep(0.02)
        self.logger.info('Suoming farm: ult not cast, keep hitting')
        return None

    def _farm_yield(self):
        owner = unison_owner(self)
        if not self._fight(lambda: self.is_con_full() or self._yellow_unison()):
            return None
        state = unison_state(self)
        if state is not None:
            state['prefer'] = owner
        return self.switch_next_char()

    def _fight(self, done):
        deadline = time.time() + getattr(self, 'fill_timeout', 8)
        next_skill = 0.0
        while time.time() < deadline:
            self.check_combat()
            if done():
                return True
            now = time.time()
            if now >= next_skill and (self._enhanced_ready() or self._resonance_ready()):
                next_skill = now + 0.4
                self.click_resonance(send_click=True, time_out=0)
            else:
                self._combo_and_dodge()
            self.sleep(0.02)
        return bool(done())

    def _combo_and_dodge(self):
        self.continues_normal_attack(0.35)
        if self.is_con_full() or self._yellow_unison():
            return
        right = getattr(self, 'continues_right_click', None)
        if callable(right):
            right(0.05)
        self.click()

    def _resonance_ready(self):
        available = getattr(self, 'resonance_available', None)
        return bool(callable(available) and available())

    def _enhanced_ready(self):
        find = getattr(self.task, 'find_one', None)
        if not callable(find):
            return False
        try:
            return bool(find(Labels.suoming_forte_e, threshold=0.7))
        except TypeError:
            return bool(find(Labels.suoming_forte_e))

    def _cast_ult(self):
        state = unison_state(self)
        if isinstance(state, dict) and state.get('suoming_ult'):
            return True
        # wait_if_cd_ready=0 常常立刻失敗，圖示亮著也不按。沿用原本開得動的按法。
        if not self.click_liberation(wait_if_cd_ready=1):
            return False
        if isinstance(state, dict):
            state['suoming_ult'] = True
        self.logger.info('Suoming farm: ult cast')
        self.sleep(0.35)
        return True

    def _yellow_unison(self):
        find = getattr(self.task, 'find_one', None)
        if not callable(find):
            return False
        for name in ('unison', 'yellow_unison'):
            try:
                if find(name, threshold=0.7):
                    return True
            except TypeError:
                return False
        return False

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
