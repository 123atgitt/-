import time

from src.Labels import Labels
from src.char.BaseChar import BaseChar, SwitchPriority

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



class Hsin(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lib2_cast_this_turn: bool = False
        self.finisher_start: float | None = None
        self.finisher_e_sent: bool = False
        self.h2_completed: bool = False
        self.h2_guard_until: float = 0.0

    def reset_state(self):
        super().reset_state()
        reset_loop(self)

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if wants_must(self):
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    def do_get_switch_priority(self, current_char, has_intro, target_low_con=False):
        return self.get_switch_priority(current_char, has_intro, target_low_con)

    def skip_combat_check(self):
        if self.h2_guard_until and time.time() >= self.h2_guard_until:
            self.logger.info('Hsin H2 protection expired; resume combat checks')
            self.h2_guard_until = 0.0
        return self.h2_guard_until > 0

    def do_perform(self):
        self.lib2_cast_this_turn = False
        self.finisher_start = None
        self.finisher_e_sent = False
        self.h2_completed = False
        self.h2_guard_until = 0.0
        self._echo_used = False
        self._stage = 'open'
        self._stage_entered = time.time()
        consume_prefer(self)
        self.logger.debug(f'Hsin perform start: has_intro={self.has_intro}')
        try:
            self.perform_everything()
        finally:
            self.h2_guard_until = 0.0
        ensure_combat(self)
        if not self.is_con_full():
            self.continues_normal_attack(4, until_con_full=True)
        ensure_combat(self)
        # 下一輪要從千咲的變奏開始。其他隊伍沒有千咲時，這行不會改優先級。
        set_prefer(self, 'Chisa')
        self.logger.debug(f'Hsin switch_next_char start: lib2_cast={self.lib2_cast_this_turn}')
        self.switch_next_char()
        self.logger.debug('Hsin switch_next_char end')

    def _set_stage(self, stage):
        self._stage = stage
        self._stage_entered = time.time()

    def _rotation_timed_out(self, start):
        if self.finisher_start is None:
            return self.time_elapsed_accounting_for_freeze(start) >= 8
        return self.time_elapsed_accounting_for_freeze(self.finisher_start) >= 18

    def perform_everything(self):
        """轉相前不按小招。統御期間只在萬闕垂天圖示亮起時按大招。"""
        start = time.time()
        while not self._rotation_timed_out(start):
            if self._stage == 'done':
                return
            ensure_combat(self)
            self.cycle_start()
            finished = False
            if self._stage == 'open':
                self._open_step()
            elif self._stage == 'after_transform':
                self.click()
                self._set_stage('detonate')
            elif self._stage == 'detonate':
                self._detonate_step()
            elif self._stage == 'build_enhanced':
                self._build_enhanced_step()
            elif self._stage == 'dominion':
                finished = self._dominion_step()
            elif self._stage == 'finisher':
                finished = self._finisher_step()
            else:
                self.click()
            if finished or self.lib2_cast_this_turn:
                self._stage = 'done'
                return
            self.cycle_sleep()
        self.logger.info(
            f'Hsin rotation end: timeout stage={self._stage} lib2={self.lib2_cast_this_turn} '
            f'h2={self.h2_completed}'
        )

    def _open_step(self):
        if self.heavy_available() == 1:
            self.handle_heavy(1)
            return
        if not self._echo_used:
            self._echo_used = True
            self.click_echo(time_out=0)
            return
        if self._cast_marked_liberation(lib2=False):
            self._set_stage('after_transform')
            return
        self.click()

    def _detonate_step(self):
        # 強化小招已經取代小招時，沒有單獨的引爆鍵。
        if self.enhanced_e_ready():
            self.logger.info('Hsin detonation skipped: enhanced skill already replaced E')
            self._set_stage('build_enhanced')
            return
        if self.resonance_available():
            self.click_resonance(has_animation=False, send_click=False, time_out=0.45)
            self._set_stage('build_enhanced')
            return
        if time.time() - self._stage_entered > 1.2:
            self._set_stage('build_enhanced')
            return
        self.click()

    def _build_enhanced_step(self):
        # 圖示亮了就用原本的強化小招。沒亮就繼續普攻，不要空按。
        if self.enhanced_e_ready():
            if self.cast_enhanced_e():
                self._set_stage('dominion')
                return
            self.click()
            return
        if time.time() - self._stage_entered > 1.5:
            self.logger.info('Hsin enhanced E: press')
            self.send_resonance_key()
            self.record_resonance_use()
            self.finisher_e_sent = True
            self._set_stage('dominion')
            return
        self.click()

    def _dominion_step(self):
        if self.heavy_available() == 2:
            if self.handle_heavy(2):
                self._set_stage('finisher')
            return False
        # 先等強化重擊。圖示一直不來，才吃已經亮起的萬闕垂天。
        if time.time() - self._stage_entered > 3 and self._cast_marked_liberation(lib2=True):
            return True
        self.click()
        return False

    def _finisher_step(self):
        if self._cast_marked_liberation(lib2=True):
            return True
        self.click()
        return False

    def _cast_marked_liberation(self, lib2):
        label = Labels.hsin_lib2 if lib2 else Labels.hsin_lib1
        if not self.task.find_one(label, threshold=0.7):
            return False
        if not self.liberation_available():
            return False
        if not self.click_liberation(wait_if_cd_ready=0):
            return False
        if lib2:
            self.lib2_cast_this_turn = True
            self.h2_guard_until = 0.0
            self.logger.info('Hsin liberation: lib2 cast')
        elif self.finisher_start is None:
            self.finisher_start = time.time()
            self.logger.info('Hsin finisher start: R1 confirmed, duration=18')
        return True

    def enhanced_e_ready(self) -> bool:
        return bool(self.is_e_forte_full())

    def cast_enhanced_e(self) -> bool:
        self.logger.debug('Hsin enhanced E start')
        self.logger.info('Hsin enhanced E start: generic prompt ready')
        start = time.time()
        last_send = -1.0
        sends = 0
        gone_since = None
        while time.time() - start < 1.5:
            self.check_combat()
            now = time.time()
            if self.enhanced_e_ready():
                gone_since = None
                if now - last_send >= 0.25:
                    self.send_resonance_key()
                    last_send = now
                    sends += 1
                    self.logger.info(f'Hsin enhanced E key: send={sends}, elapsed={now - start:.3f}s')
            elif last_send >= 0:
                if gone_since is None:
                    gone_since = now
                elif now - gone_since >= 0.25:
                    self.finisher_e_sent = True
                    self.record_resonance_use()
                    self.logger.debug('Hsin enhanced E consumed; continue normal attacks')
                    self.logger.info(f'Hsin enhanced E result: confirmed=True, sends={sends}, '
                                     f'elapsed={time.time() - start:.3f}s')
                    return True
            self.task.next_frame()
        self.logger.debug('Hsin enhanced E not confirmed; retry when ready')
        self.logger.info(f'Hsin enhanced E result: confirmed=False, sends={sends}, '
                         f'elapsed={time.time() - start:.3f}s')
        return False

    def lib(self, after_heavy: bool = False) -> bool:
        # 沒有 lib1 / lib2 圖示就不按 R。統御裡的借相不是這兩個圖示。
        if after_heavy or self.task.find_one(Labels.hsin_lib2, threshold=0.7):
            return self._cast_marked_liberation(lib2=True)
        if self.finisher_start is None:
            return self._cast_marked_liberation(lib2=False)
        return False

    def heavy_available(self) -> int:
        if self.task.find_one(Labels.hsin_h2, threshold=0.7):
            return 2
        if self.task.find_one(Labels.hsin_h1, threshold=0.7):
            return 1
        return 0

    def heavy_wait_highlight_down(self, time_out: float, protect_animation: bool = False) -> bool:
        self.logger.debug(f'Hsin heavy hold start: timeout={time_out:.2f}')
        self.check_combat()
        self.task.mouse_down()
        if protect_animation:
            # H2 hides the HUD; let R2 take over before retargeting interrupts the animation.
            self.h2_guard_until = time.time() + 4
            self.logger.info('Hsin H2 protection start: at most 4s through R2 transition')
        try:
            confirmed = bool(self.task.wait_until(
                lambda: not self.heavy_available(), time_out=time_out,
                settle_time=0.25, pre_action=self.check_combat))
        except BaseException:
            self.h2_guard_until = 0.0
            raise
        finally:
            self.task.mouse_up()
            self.logger.debug('Hsin heavy hold: mouse released')
        if not confirmed:
            self.h2_guard_until = 0.0
        self.sleep(0.01)
        self.logger.debug(f'Hsin heavy hold end: indicator_disappeared={confirmed}')
        return confirmed

    def handle_heavy(self, heavy_type: int = 0) -> bool:
        self.logger.debug('Hsin heavy check start')
        heavy_type = heavy_type or self.heavy_available()
        if not heavy_type:
            self.logger.debug('Hsin heavy end: unavailable')
            return False
        # An already-started hold gets its full window, even near the rotation deadline.
        confirmed = self.heavy_wait_highlight_down(1.2, protect_animation=heavy_type == 2)
        self.logger.debug(f'Hsin heavy: type={heavy_type}, confirmed={confirmed}')
        if confirmed and heavy_type == 2:
            self.h2_completed = True
        return confirmed

    def wait_for_lib2(self, after_heavy: bool = False) -> bool:
        self.logger.debug(f'Hsin lib2 wait start: after_heavy={after_heavy}')
        confirmed = bool(self.task.wait_until(
            lambda: (after_heavy or bool(self.task.find_one(Labels.hsin_lib2, threshold=0.7)))
                    and self.lib(after_heavy=after_heavy) and self.lib2_cast_this_turn,
            time_out=1.5, pre_action=self.check_combat))
        self.logger.debug(f'Hsin lib2 wait end: cast={confirmed}, pending={self.h2_completed and not confirmed}')
        return confirmed
