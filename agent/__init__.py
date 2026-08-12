"""Multi-step task planning and execution.

planner       -> decomposes a goal into steps
executor      -> runs them, recovering from failures
error_handler -> decides retry / skip / replan / abort
task_queue    -> priority queue with cancellation

Migrating toward the orchestrator described in docs/ARCHITECTURE.md §2, which
separates intent, planning, tool selection, execution, verification, and
response.
"""
