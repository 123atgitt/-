import time

from src.char.BaseChar import BaseChar, CharType, SwitchPriority, get_default_buff_time

# ELECTRO_LOOP_SHARED_BEGIN
# 這一段在 Hsin.py、Chisa.py、Rover.py 必須逐字相同。
# 三個角色不互相 import，只共用 task._hsin_electro_loop。
LOOP_ATTR = '_hsin_electro_loop'

PHASE_CHISA_OPEN = 'chisa_open'
PHASE_ROVER_AXIS = 'rover_axis'
PHASE_CHISA_SAW = 'chisa_saw'
PHASE_ROVER_FINAL = 'rover_final'
PHASE_HSIN = 'hsin'

_ELECTRIC = 1
_NON_ELECTRIC = (0, 2, 3, 4, 5)


def _chars(task):
    return [char for char in getattr(task, 'chars', []) or [] if char is not None]


def rover_form(rover):
    if hasattr(rover, '_known_form'):
        form = rover._known_form()
        if isinstance(form, int) and form >= 0:
            return form
    if getattr(rover, 'ring_index', -1) >= 0:
        return rover.ring_index
    return getattr(rover, '_last_known_form', -1)


def is_hsin_electro_team(char):
    """心月狐、千咲、電磁漂泊者同時在隊裡才走這條輪次。"""
    task = getattr(char, 'task', None)
    if task is None:
        return False
    by_name = {c.name: c for c in _chars(task)}
    if not {'Hsin', 'Chisa', 'Rover'} <= set(by_name):
        return False
    form = rover_form(by_name['Rover'])
    if form in _NON_ELECTRIC:
        return False
    return form in (-1, _ELECTRIC)


def get_loop(char, create=True):
    task = getattr(char, 'task', None)
    if task is None or not is_hsin_electro_team(char):
        return None
    loop = getattr(task, LOOP_ATTR, None)
    if loop is None and create:
        loop = {'phase': PHASE_CHISA_OPEN, 'prefer': None}
        setattr(task, LOOP_ATTR, loop)
    return loop


def reset_loop(char):
    task = getattr(char, 'task', None)
    if task is None:
        return
    setattr(task, LOOP_ATTR, {'phase': PHASE_CHISA_OPEN, 'prefer': None})


def consume_prefer(char):
    loop = getattr(getattr(char, 'task', None), LOOP_ATTR, None)
    if loop is not None:
        loop['prefer'] = None


def set_prefer(char, name, phase=None):
    loop = get_loop(char, create=True)
    if loop is None:
        return None
    loop['prefer'] = name
    if phase is not None:
        loop['phase'] = phase
    return loop


def wants_must(char):
    if not is_hsin_electro_team(char):
        return False
    loop = getattr(getattr(char, 'task', None), LOOP_ATTR, None)
    return bool(loop and loop.get('prefer') == char.name)


_PHASE_OWNER = {
    PHASE_CHISA_OPEN: 'Chisa',
    PHASE_CHISA_SAW: 'Chisa',
    PHASE_ROVER_AXIS: 'Rover',
    PHASE_ROVER_FINAL: 'Rover',
    PHASE_HSIN: 'Hsin',
}


def leave_if_not_owner(char):
    """上場的人不是這一步的主人時，立刻把場交回去。連跳兩次仍交不出去就停下。"""
    loop = get_loop(char)
    if loop is None:
        return False
    owner = _PHASE_OWNER.get(loop.get('phase'))
    if owner is None or owner == char.name:
        loop['bounces'] = 0
        return False
    bounces = loop.get('bounces', 0)
    if bounces >= 2:
        return False
    loop['bounces'] = bounces + 1
    char.logger.info(f'{char.name}: step {loop.get("phase")} belongs to {owner}')
    set_prefer(char, owner)
    char.switch_next_char()
    return True
# ELECTRO_LOOP_SHARED_END


class Chisa(BaseChar):
    SUPPORT_ACTION_DURATION = 1.2
    SUPPORT_LONG_ACTION_DURATION = 10.0
    INTRO_NORMAL_ATTACK_DURATION = 2.0

    def is_dps_config(self):
        return self.task and self.task.char_config.get("Chisa DPS")

    def get_char_type(self):
        if self.is_dps_config():
            return CharType.MAIN_DPS
        return super().get_char_type()

    def get_buff_time(self):
        if self.is_dps_config():
            return get_default_buff_time(CharType.MAIN_DPS)
        return super().get_buff_time()

    def reset_state(self):
        super().reset_state()
        reset_loop(self)

    def healer_full_con_switch_locked(self):
        # 千咲在工廠裡是治療。滿協奏切走後程式會鎖 16 秒不准回來，合軸和下一輪都會斷。
        if is_hsin_electro_team(self):
            return False
        return super().healer_full_con_switch_locked()

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if wants_must(self):
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    def do_get_switch_priority(self, current_char, has_intro, target_low_con=False):
        return self.get_switch_priority(current_char, has_intro, target_low_con)

    def do_perform(self):
        if self.is_dps_config():
            return self.do_dps_perform()
        if is_hsin_electro_team(self):
            if leave_if_not_owner(self):
                return
            return self.do_electro_support()
        return self.do_support_perform()

    def do_electro_support(self):
        """心月狐隊：聲骸、大招、小招，強化小招起手合軸，回來後電鋸協奏一滿就切。"""
        consume_prefer(self)
        phase = (get_loop(self) or {}).get('phase')
        if phase == PHASE_CHISA_SAW:
            return self._electro_saw_outro()
        return self._electro_opener()

    def _con_value(self):
        if self.is_con_full():
            return 1.0
        return self.get_current_con()

    def _electro_opener(self):
        if self.has_intro:
            self.wait_intro(time_out=0.6, click=False)
        elif self.flying():
            self.wait_down()
        self.click_echo(time_out=0)
        self.click_liberation(wait_if_cd_ready=0)
        if not self.is_forte_full() and self.resonance_available():
            self.click_resonance(time_out=0.5)
        start = time.time()
        while not self.is_forte_full() and time.time() - start < 4:
            self.click()
            self.sleep(0.1)
        # 進電鋸前協奏已經滿：合軸不成立，但電鋸仍要打完，延奏的 15 秒才從結尾起算。
        if self._con_value() > 0.8:
            self.logger.info('chisa: concerto already high, finish saw then outro')
            if self.is_forte_full():
                self.perform_forte()
            return self._outro_to_rover()
        if self.is_forte_full():
            started = self._start_chainsaw()
            if started == 'started' and self._con_value() <= 0.8:
                self.logger.info('chisa: chainsaw started below full concerto, axis into rover')
                set_prefer(self, 'Rover', phase=PHASE_ROVER_AXIS)
                return self.switch_next_char()
            if self._con_value() > 0.8:
                self.logger.info('chisa: chainsaw filled concerto, outro without returning later')
                return self._outro_to_rover()
        self.logger.info('chisa: chainsaw did not start, build concerto then outro')
        if not self._hold_attack_until_con_full(4.5):
            self.continues_normal_attack(3, until_con_full=True)
        return self._outro_to_rover()

    def _electro_saw_outro(self):
        """合軸切回來。背景電鋸若已把協奏灌滿，立刻延奏，不等落地。"""
        if not (self.is_con_full() or self._con_value() > 0.8):
            if not self._hold_attack_until_con_full(4.5):
                self.continues_normal_attack(3, until_con_full=True)
        return self._outro_to_rover()

    def _outro_to_rover(self):
        if not (self.is_con_full() or self._con_value() > 0.8):
            self.logger.info('chisa: leaving before concerto is full')
        set_prefer(self, 'Rover', phase=PHASE_ROVER_FINAL)
        return self.switch_next_char()

    def _start_chainsaw(self):
        """用和原本電鋸相同的按住小招。按完回路掉了、協奏還沒收滿，才是合軸。"""
        if self.flying():
            self.wait_down()
        if self._con_value() > 0.8:
            return 'full'
        self.task.send_key(self.get_resonance_key(), down_time=1.2)
        self.sleep(0.05)
        if self._con_value() > 0.8:
            return 'full'
        if not self.is_forte_full():
            return 'started'
        return 'failed'

    def _hold_attack_until_con_full(self, timeout):
        """電鋸強化普攻。協奏一滿就鬆開，不等落地。"""
        if self.flying():
            self.wait_down()
        self.task.mouse_down()
        start = time.time()
        try:
            while time.time() - start < timeout:
                self.check_combat()
                if self.is_con_full() or self._con_value() > 0.8:
                    return True
                self.task.next_frame()
                self.sleep(0.05, check_combat=False)
        finally:
            self.task.mouse_up()
        return self.is_con_full() or self._con_value() > 0.8

    def do_support_perform(self):
        needs_long_actions = self.has_intro and not self.has_buff()
        if self.has_intro:
            self.continues_normal_attack(self.INTRO_NORMAL_ATTACK_DURATION)

        duration = (self.SUPPORT_LONG_ACTION_DURATION
                    if needs_long_actions else self.SUPPORT_ACTION_DURATION)
        if self.flying() and not self.liberation_available() and not self.resonance_available():
            self.wait_down()
        self.click_echo(time_out=0)

        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < duration:
            self.cycle_start()
            if self.is_con_full():
                return self.switch_next_char()
            if self.liberation_available():
                self.click_liberation(wait_if_cd_ready=0)
            elif self.is_forte_full():
                if self.perform_forte():
                    break
            elif self.click_resonance(time_out=0)[0]:
                pass
            else:
                self.click()
            self.cycle_sleep()

        return self.switch_next_char()

    def do_dps_perform(self):
        timeout = 2.5
        self.check_f_on_switch = True
        if self.has_intro:
            self.continues_normal_attack(0.8)
            timeout = 2.3
        if self.flying() and not self.liberation_available() and not self.resonance_available():
            self.wait_down()
        self.click_echo()
        start = time.time()
        under_liber = False
        while time.time() - start < timeout:
            if time.time() - start < 0.5 and self.click_liberation():
                start = time.time()
                under_liber = True
                timeout = 10
                self.sleep(0.2)
            if time.time() - start < 0.5 and not self.is_forte_full() and self.click_resonance()[0]:
                start = time.time()
                if timeout != 10:
                    timeout = 1.7
            if (under_liber or self.is_dps_config()) and self.is_forte_full() and self.perform_forte():
                self.check_f_on_switch = False
                return self.switch_next_char()
            self.click()
            self.check_combat()
            self.task.next_frame()
        self.switch_next_char()

    def perform_forte(self):
        if self.flying():
            self.wait_down()
        self.task.send_key(self.get_resonance_key(), down_time=1.2)
        if self.is_forte_full():
            return False
        self.heavy_attack(3.5)
        return True
