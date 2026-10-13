import time

from src.char.BaseChar import BaseChar, CharType, SwitchPriority, get_default_buff_time

# ELECTRO_LOOP_SHARED_BEGIN
# 這一段在 Hsin.py、Chisa.py、Rover.py 必須逐字相同。
# 三個角色不互相 import，只共用 task._hsin_electro_loop。
# 一人一套打完再切下一人。不合軸。
LOOP_ATTR = '_hsin_electro_loop'

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
        loop = {'prefer': None}
        setattr(task, LOOP_ATTR, loop)
    return loop


def reset_loop(char):
    task = getattr(char, 'task', None)
    if task is None:
        return
    setattr(task, LOOP_ATTR, {'prefer': None})


def consume_prefer(char):
    loop = getattr(getattr(char, 'task', None), LOOP_ATTR, None)
    if loop is not None:
        loop['prefer'] = None


def set_prefer(char, name):
    loop = get_loop(char, create=True)
    if loop is None:
        return None
    loop['prefer'] = name
    return loop


def wants_must(char):
    if not is_hsin_electro_team(char):
        return False
    loop = getattr(getattr(char, 'task', None), LOOP_ATTR, None)
    return bool(loop and loop.get('prefer') == char.name)
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
        # 千咲在工廠裡是治療。滿協奏切走後程式會鎖 16 秒，下一輪就切不回她。
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
            return self.do_electro_support()
        return self.do_support_perform()

    def do_electro_support(self):
        """跟原本輔助迴圈一樣邊打邊放。電鋸打完、協奏滿了才切雷主。"""
        consume_prefer(self)
        if self.has_intro:
            self.continues_normal_attack(0.8)
        if self.flying() and not self.liberation_available() and not self.resonance_available():
            self.wait_down()
        self.click_echo(time_out=0)

        saw_done = False
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < 8:
            self.cycle_start()
            if saw_done and self.is_con_full():
                break
            if self.liberation_available():
                self.click_liberation(wait_if_cd_ready=0)
            elif not saw_done and self._enhanced_ready():
                if self.perform_forte():
                    saw_done = True
            elif not saw_done and self.resonance_available() and self.click_resonance(time_out=0)[0]:
                pass
            else:
                self.click()
            self.cycle_sleep()

        if not saw_done:
            self.logger.info('chisa: hold enhanced skill before swap')
            was_ready = self._enhanced_ready()
            if self.flying():
                self.wait_down()
            self.task.send_key(self.get_resonance_key(), down_time=1.2)
            # perform_forte 的判斷：按完回路還亮著，代表沒進電鋸，不接重擊。
            if was_ready and not self.is_forte_full():
                self.heavy_attack(3.5)
        if not self.is_con_full():
            self.continues_normal_attack(4, until_con_full=True)
        if not self.is_con_full():
            self.logger.info('chisa: set finished before concerto was full')
        set_prefer(self, 'Rover')
        return self.switch_next_char()

    def _enhanced_ready(self):
        return self.is_forte_full() or bool(self.is_e_forte_full())

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
