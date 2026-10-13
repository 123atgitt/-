"""千咲、雷主、心月狐這一隊的輪次狀態。

ok-ww 的 switch_next_char() 不會切回上一個人，只會在優先級最高的隊友裡挑一個。
合軸要在協奏沒滿時切走、再切回來，所以這裡用 prefer 把目標抬到 MUST。
協奏滿了仍然是真正的延奏，但只會交給 prefer 指定的人。
"""

LOOP_ATTR = '_hsin_electro_loop'

PHASE_CHISA_OPEN = 'chisa_open'
PHASE_ROVER_AXIS = 'rover_axis'
PHASE_CHISA_SAW = 'chisa_saw'
PHASE_ROVER_FINAL = 'rover_final'
PHASE_HSIN = 'hsin'

# 與 BaseChar.Elements.ELECTRIC 相同，這裡不引入戰鬥基類。
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
