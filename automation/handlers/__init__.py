from automation.handlers.action import register as register_action
from automation.handlers.control import register as register_control
from automation.handlers.detection import register as register_detection
from automation.handlers.variable import register as register_variable
from automation.handlers.preset import register as register_preset
from automation.handlers.utility import register as register_utility
from automation.handlers.monitor import register as register_monitor
from automation.handlers.flow import register as register_flow

NODE_HANDLERS = {}


def register_all_handlers():
    register_action(NODE_HANDLERS)
    register_control(NODE_HANDLERS)
    register_detection(NODE_HANDLERS)
    register_variable(NODE_HANDLERS)
    register_preset(NODE_HANDLERS)
    register_utility(NODE_HANDLERS)
    register_monitor(NODE_HANDLERS)
    register_flow(NODE_HANDLERS)
