import time

from src.char.BaseChar import BaseChar, CharType, SwitchPriority, get_default_buff_time
from src.char.hsin_electro_loop import (
    PHASE_CHISA_SAW,
    PHASE_ROVER_AXIS,
    PHASE_ROVER_FINAL,
    consume_prefer,
    get_loop,
    is_hsin_electro_team,
    reset_loop,
    set_prefer,
    wants_must,
)


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

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if wants_must(self):
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    def do_perform(self):
        if self.is_dps_config():
            return self.do_dps_perform()
        if is_hsin_electro_team(self):
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
            self.wait_intro(time_out=0.8, click=True)
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
        if self._con_value() > 0.75:
            self.logger.info('chisa: concerto already high, finish saw then outro')
            if self.is_forte_full():
                self.perform_forte()
            return self._outro_to_rover()
        if self.is_forte_full():
            started = self._start_chainsaw()
            if started == 'started' and self._con_value() <= 0.75:
                self.logger.info('chisa: chainsaw started below full concerto, axis into rover')
                set_prefer(self, 'Rover', phase=PHASE_ROVER_AXIS)
                return self.switch_next_char()
            if self._con_value() > 0.75:
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
        """按住小招直到強化小招吃掉回路。協奏快滿就停，避免合軸變成延奏。"""
        if self.flying():
            self.wait_down()
        if self._con_value() > 0.75:
            return 'full'
        key = self.get_resonance_key()
        self.task.send_key_down(key)
        start = time.time()
        try:
            while time.time() - start < 1.2:
                self.check_combat()
                if not self.is_forte_full():
                    return 'started'
                if self._con_value() > 0.75:
                    return 'full'
                self.task.next_frame()
                self.sleep(0.05, check_combat=False)
        finally:
            self.task.send_key_up(key)
        if not self.is_forte_full():
            return 'started'
        if self._con_value() > 0.75:
            return 'full'
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
