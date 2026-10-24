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
        state = {'phase': 'shore', 'prefer': 'ShoreKeeper'}
        setattr(task, UNISON_ATTR, state)
    return state


def unison_wants(char):
    if not unison_team(char):
        return False
    state = unison_state(char)
    return bool(state and state.get('prefer') == char.name)


def unison_advance(char, phase, prefer):
    state = unison_state(char)
    if state is None:
        return None
    state['phase'] = phase
    state['prefer'] = prefer
    return state


def reset_unison(char):
    task = getattr(char, 'task', None)
    if task is None or not unison_team(char):
        return
    setattr(task, UNISON_ATTR, {'phase': 'shore', 'prefer': 'ShoreKeeper'})
# UNISON_SHARED_END


class ShoreKeeper(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outrotime = -1
        self.dodge_count = 0
        self.attribute = 0
        self.check_f_on_switch = True
        self._unison_realm_cast = False

    def reset_state(self):
        super().reset_state()
        self._unison_realm_cast = False
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

    def do_perform(self):
        if unison_team(self):
            return self.do_unison_perform()
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
        if not self.click_resonance():
            self.heavy_click_forte(self.is_mouse_forte_full)
        self.switch_next_char()

    def do_unison_perform(self):
        """同奏開場：領域要放成，協奏滿了才用真正的延奏切給鎖暝。"""
        phase = (unison_state(self) or {}).get('phase')
        self.logger.info(f'ShoreKeeper unison phase={phase}')
        if phase != 'shore':
            return self.switch_next_char()
        return self._unison_open()

    def _refresh(self):
        if hasattr(self.task, 'next_frame'):
            self.task.next_frame()
        self.check_combat()

    def _play_intro(self):
        if not self.has_intro:
            return
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

    def _unison_open(self):
        self._play_intro()
        self.click_echo(time_out=0)
        self._refresh()
        if not self._unison_realm_cast:
            if not self.liberation_available() or not self.click_liberation(wait_if_cd_ready=0):
                self.logger.info('ShoreKeeper unison: realm not ready, stay')
                return None
            self._unison_realm_cast = True
        if not self.click_resonance():
            self.heavy_click_forte(self.is_mouse_forte_full)
        if not self.is_con_full():
            self.continues_normal_attack(5, until_con_full=True)
        if not self.is_con_full():
            self.logger.info('ShoreKeeper unison: concerto not full, stay')
            return None
        self._unison_realm_cast = False
        unison_advance(self, 'suoming_arm', 'Suoming')
        self.logger.info('ShoreKeeper unison: realm ready, switch to Suoming')
        return self.switch_next_char()

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
