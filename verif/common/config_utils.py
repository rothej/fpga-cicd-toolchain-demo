# verif/common/config_utils.py

from pyuvm import ConfigDB


def _cfg(component, key, default=None):
    """ConfigDB.get() wrapper with optional default.

    Contract: call only from uvm_component subclasses (uvm_driver,
    uvm_monitor, uvm_scoreboard, uvm_env, uvm_agent, uvm_test).

    ConfigDB path resolution is component-hierarchy-based. Calling this
    from uvm_sequence.body() will always return *default* because a sequence
    is a uvm_object with no hierarchical component path, so the wildcard
    patterns set by test build_phase never match.

    For sequence parameterisation, set explicit typed attributes on the
    sequence instance before calling start():
        seq = MySeq("name")
        seq.count = 32
        await seq.start(sequencer)
    """
    try:
        return ConfigDB().get(component, "", key)
    except Exception:
        return default
