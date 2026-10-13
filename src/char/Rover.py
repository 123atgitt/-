import time
from ok import Logger
from src.char.BaseChar import BaseChar, CharType, Elements, SwitchPriority
from src.char.hsin_electro_loop import (
    PHASE_ROVER_AXIS,
    PHASE_ROVER_FINAL,
    PHASE_HSIN,
    PHASE_CHISA_OPEN,
    consume_prefer,
    get_loop,
    is_hsin_electro_team,
    reset_loop,
    set_prefer,
    wants_must,
)

_ROVER_FORM_NAMES = {
    Elements.SPECTRO: 'Rover: Spectro',
    Elements.ELECTRIC: 'Rover: Electro',
    Elements.WIND: 'Rover: Aero',
    Elements.HAVOC: 'Rover: Havoc',
}


class Rover(BaseChar):
    def __init__(self, *args, **kwargs):
        self._last_known_form = -1
        super().__init__(*args, **kwargs)
        self.use_skyfall_severance = False
        self._bind_form_logger()

    def reset_state(self):
        if self.ring_index >= 0:
            self._last_known_form = self.ring_index
        self.ring_index = -1
        super().reset_state()
        self._bind_form_logger()
        reset_loop(self)

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if wants_must(self):
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    @property
    def display_name(self):
        return _ROVER_FORM_NAMES.get(self.ring_index, 'Rover')

    def get_char_type(self):
        form = self.ring_index if self.ring_index >= 0 else self._last_known_form
        # 首次识别前按辅助调度，上场仍重新确认形态。
        return CharType.SUB_DPS if form in (-1, Elements.ELECTRIC) else super().get_char_type()

    def __repr__(self):
        return self.display_name

    def _bind_form_logger(self):
        self.logger = Logger.get_logger(self.display_name)

    def _known_form(self):
        if hasattr(self.task, 'get_known_ring_index'):
            return self.task.get_known_ring_index(self)
        return self.ring_index

    def is_havoc_form(self):
        return self._known_form() == Elements.HAVOC

    def ensure_display_form(self):
        if self.ring_index >= 0:
            return
        if not self.is_current_char:
            return
        if hasattr(self.task, '_ensure_ring_index'):
            self.task._ensure_ring_index()
            self._bind_form_logger()

    def do_perform(self):
        self.init()
        if not self.has_intro:
            self.sleep(0.01)
        if self.ring_index == Elements.HAVOC:
            self.intro_motion_freeze_duration = 0.64
            self.logger.info('rover: form-dispatch ring=HAVOC routine=havoc')
            if self.perform_havoc_routine():
                return
        elif self.ring_index == Elements.SPECTRO:
            self.intro_motion_freeze_duration = 0.92
            self.logger.info('rover: form-dispatch ring=SPECTRO routine=spectro')
            self.perform_spectro_routine()
        elif self.ring_index == Elements.WIND:
            self.intro_motion_freeze_duration = 0.52
            self.logger.info('rover: form-dispatch ring=WIND routine=wind')
            self.perform_wind_routine()
        elif self.ring_index == Elements.ELECTRIC:
            self.logger.info('rover: form-dispatch ring=ELECTRIC routine=electric')
            self.perform_electric_routine()
        else:
            self.logger.info('rover: form-dispatch ring=UNKNOWN routine=basic')
            self.perform_basic_routine()
        self.switch_next_char()

    def init(self):
        previous_form = self.ring_index
        if hasattr(self.task, '_ensure_ring_index'):
            self.task._ensure_ring_index()
        if self.ring_index != previous_form:
            self._bind_form_logger()
            self.logger.info(
                f'rover: form-corrected previous={previous_form} current={self.ring_index}'
            )
            names = []
            for char in self.task.chars:
                if char is None:
                    continue
                name = getattr(char, 'display_name', char.name)
                names.append(self.task.tr(name) if getattr(self.task, '_app', None) is not None else name)
            self.task.info_set('Chars', ', '.join(names))
        if self.ring_index == Elements.WIND:
            self.init_wind()

    def electric_skill_ready(self):
        # 小E提示可能误匹配，须同时确认回路满格标记。
        return self.is_forte_full() and bool(self.is_e_forte_full())

    def perform_electric_routine(self):
        if not is_hsin_electro_team(self):
            self._perform_electric_routine_default()
            return
        consume_prefer(self)
        phase = (get_loop(self) or {}).get('phase')
        if phase == PHASE_ROVER_AXIS:
            self._electric_axis()
        elif phase == PHASE_ROVER_FINAL:
            self._electric_final()
        elif self._con_value() > 0.8:
            self.logger.info('rover: entered with concerto almost full, use final visit')
            self._electric_final()
        else:
            self.logger.info('rover: hand off to chisa without spending liberation or echo')
            set_prefer(self, 'Chisa', phase=PHASE_CHISA_OPEN)

    def _con_value(self):
        if self.is_con_full():
            return 1.0
        return self.get_current_con()

    def _electric_axis(self):
        """合軸只放大招。協奏被大招灌滿時不能切回千咲，否則電髓會給錯人。"""
        self.wait_down(click=False)
        if self._con_value() <= 0.55 and self.liberation_available():
            self.click_liberation(click_f=False)
        if self.is_con_full() or self._con_value() > 0.8:
            self.logger.info('rover: axis liberation filled concerto, fold into final visit')
            self._electric_final(skip_liberation=True)
            return
        self.logger.info('rover: axis liberation kept concerto open, return to chisa')
        set_prefer(self, 'Chisa', phase=PHASE_CHISA_SAW)

    def _electric_final(self, skip_liberation=False):
        """最後一次進場：聲骸、短按強化小招，協奏滿了才切給心月狐。"""
        self.wait_down(click=False)
        self.click_echo()
        if not skip_liberation:
            self.click_liberation(click_f=False)
        if not self.electric_skill_ready() and self.resonance_available():
            if self.click_resonance(send_click=False, time_out=1)[0]:
                self.sleep(0.1)
        start = time.time()
        while not self.electric_skill_ready() and self.time_elapsed_accounting_for_freeze(start) < 6:
            self.click()
            self.sleep(0.1)
        if self.electric_skill_ready():
            if not self.short_electric_skill():
                self.logger.info('rover: electric enhanced resonance not confirmed')
        else:
            self.logger.info('rover: electric forte not ready before final visit timeout')
        if not self.is_con_full():
            self.continues_normal_attack(4, until_con_full=True)
        if not self.is_con_full():
            self.logger.info('rover: final visit ended before concerto was full')
        set_prefer(self, 'Hsin', phase=PHASE_HSIN)

    def _perform_electric_routine_default(self):
        self.wait_down(click=False)
        self.click_echo()
        # Q后图标可能暂时变暗，让helper处理就绪重试，避免单帧判断漏放R。
        self.click_liberation(click_f=False)
        if not self.electric_skill_ready() and self.resonance_available():
            if self.click_resonance(send_click=False, time_out=1)[0]:
                self.sleep(0.1)
        start = time.time()
        duration = 8 if self.has_intro else 12
        while not self.electric_skill_ready() and self.time_elapsed_accounting_for_freeze(start) < duration:
            self.click()
            self.sleep(0.1)
        if not self.electric_skill_ready():
            self.logger.info('rover: electric forte not ready before rotation timeout')
            return
        if not self.short_electric_skill():
            self.logger.info('rover: electric enhanced resonance not confirmed, switch out')
            return
        if not self.is_con_full():
            self.click_liberation(click_f=False)
        if not self.is_con_full():
            self.continues_normal_attack(2, until_con_full=True)

    def short_electric_skill(self):
        # 强化E能在普通E冷却期间触发，不能用普通冷却拦截。
        for attempt in range(2):
            if not self.electric_skill_ready():
                return False
            start = time.time()
            self.send_resonance_key(down_time=0.05)
            # 回路在尾段消耗；过滤瞬间变暗，同时保留必要的动作保护。
            consumed = bool(self.task.wait_until(
                lambda: self.time_elapsed_accounting_for_freeze(start) >= 1.5
                        and not self.is_forte_full() and not self.is_e_forte_full(),
                time_out=2.6, settle_time=0.2, pre_action=self.check_combat))
            if consumed:
                self.record_resonance_use()
                return True
            self.logger.info(f'rover: electric enhanced resonance attempt {attempt + 1} not confirmed')
        return False

    def perform_spectro_routine(self):
        if self.has_intro:
            self.continues_normal_attack(1)
        self.wait_down()
        self.spectro_routine_aftertune_combo()
        self.click_echo(time_out=0)
        if self.is_forte_full():
            self.check_combat()
            if self.resonance_available() and self.click_resonance()[0]:
                self.continues_normal_attack(1.4)
                self.sleep(0.1)
        self.check_combat()
        if not self.click_liberation(send_click=True):
            self.click_resonance()

    def spectro_routine_aftertune_combo(self):
        self.heavy_attack()
        self.sleep(0.4)
        self.continues_normal_attack(0.7)

    def perform_havoc_routine(self):
        self.wait_down()
        self.heavy_click_forte(check_fun = self.is_mouse_forte_full)
        self.click_liberation(send_click=True)
        if self.click_resonance(send_click=True)[0]:
            return
        if not self.click_echo():
            self.click()
        self.continues_normal_attack(1.1 - self.time_elapsed_accounting_for_freeze(self.last_switch_time))

    def init_wind(self):
        from src.char.Cartethyia import Cartethyia
        from src.char.Phoebe import Phoebe
        self.use_skyfall_severance = bool(self.task.has_char(Cartethyia) and self.task.has_char(Phoebe))

    def perform_wind_routine(self):
        if not (self.has_intro and self.wind_routine_click_while_flying(2)):
            self.wind_routine_wait_down(check_forte_full=False)
            if self.resonance_available() and not self.is_forte_full():
                self.click_echo(time_out=0)
                start = time.time()
                flying = False
                while time.time() - start < 1:
                    self.send_resonance_key(interval=0.1)
                    self.task.next_frame()
                    self.click(interval=0.1)
                    if flying := self.wind_routine_flying():
                        break
                use_skyfall_severance = self.use_skyfall_severance
                if flying:
                    self.wind_routine_click_while_flying(1.6 if use_skyfall_severance else 1.74)
                if use_skyfall_severance and self.click_resonance(send_click=False)[0]:
                    self.wind_routine_click_while_flying(1)
        self.click_liberation(send_click=True)
        self.wind_routine_wait_down()

    def wind_routine_click_while_flying(self, duration, interval=0.1):
        start = time.time()
        while time.time() - start < duration:
            if not self.wind_routine_flying():
                return False
            self.click(interval=0.1)
            self.sleep(interval)
        return True

    def wind_routine_flying(self):
        if self.task.has_lavitator:
            return self.flying()
        elif self.current_resonance() > 0.15:
            return True

    def wind_routine_wait_down(self, check_forte_full=True):
        if self.wind_routine_flying():
            if self.task.has_lavitator:
                self.wait_down()
            else:
                self.task.wait_until(lambda: self.current_resonance() < 0.15,
                                     post_action=lambda: self.click(interval=0.1, after_sleep=0.01), time_out=2.5)
        if check_forte_full:
            self.sleep(0.03)
            if self.is_forte_full():
                self.send_resonance_key()
        else:
            self.sleep(0.01)
        return True

    def perform_basic_routine(self):
        if self.has_intro:
            self.continues_normal_attack(self.intro_motion_freeze_duration + 0.2)
        self.wait_down()
        self.click_echo()
        liber = self.click_liberation(send_click=True)
        res = self.click_resonance(send_click=True)[0]
        if not (liber or res):
            self.continues_normal_attack(1)