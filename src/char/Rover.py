import time
from ok import Logger
from src.char.BaseChar import BaseChar, CharType, Elements, SwitchPriority

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


def ensure_combat(char):
    """先換新畫面再檢查。王死了會從這裡停，不會接著打空氣。"""
    task = getattr(char, 'task', None)
    if task is not None and hasattr(task, 'next_frame'):
        task.next_frame()
    char.check_combat()
# ELECTRO_LOOP_SHARED_END


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

    def do_get_switch_priority(self, current_char, has_intro, target_low_con=False):
        return self.get_switch_priority(current_char, has_intro, target_low_con)

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
        if is_hsin_electro_team(self):
            ensure_combat(self)
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
        self.wait_down(click=False)
        self.click_echo()
        self.click_liberation(click_f=False)
        # 強化小招圖示亮了就不要先點普通小招，也不要繼續普攻把這下拖過去。
        if not self._enhanced_prompt() and self.resonance_available():
            if self.click_resonance(send_click=False, time_out=0.6)[0]:
                self.sleep(0.1)
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < 4:
            if self._enhanced_prompt():
                break
            self.click()
            self.sleep(0.1)
            ensure_combat(self)
        self._press_short_enhanced()
        ensure_combat(self)
        if not self.is_con_full():
            self.click_liberation(click_f=False)
        ensure_combat(self)
        if not self.is_con_full():
            self.continues_normal_attack(4, until_con_full=True)
        if not self.is_con_full():
            self.logger.info('rover: set finished before concerto was full')
        set_prefer(self, 'Hsin')

    def _enhanced_prompt(self):
        # 畫面上的強化小招圖示即可。白條回路常常對不上，不能拿來擋這一下。
        return bool(self.is_e_forte_full()) or self.is_forte_full()

    def _press_short_enhanced(self):
        """圖示亮了立刻短按。長按會進臨界共鳴。"""
        self.send_resonance_key(down_time=0.05)
        self.record_resonance_use()
        self.sleep(0.12, check_combat=False)
        if self.is_e_forte_full():
            self.send_resonance_key(down_time=0.05)
            self.record_resonance_use()

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