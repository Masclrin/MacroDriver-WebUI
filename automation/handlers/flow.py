from automation.engine import _execute_flow
from automation.compiler import ExecNode
from automation.engine import ExecContext


def _handle_flow_start(node: ExecNode, ctx: ExecContext):
    _execute_flow(node.id, "next", ctx)


def _handle_flow_end(node: ExecNode, ctx: ExecContext):
    ctx.stop_event.set()
    ctx.task_pool.stop_all()


def register(handlers: dict):
    handlers["_handle_flow_start"] = _handle_flow_start
    handlers["_handle_flow_end"] = _handle_flow_end
