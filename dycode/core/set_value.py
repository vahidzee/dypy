import typing as th
from .get_value import greedy_import_context


def set_value(name: str, value: th.Any, context: th.Optional[th.Any] = None):
    """
    Sets a value for variable "name" in the context "context", or in the global context if "context" is None.

    Args:
        name (str): The name of the variable to set.
        value (typing.Any): The value to set.

    Returns:
        None
    """
    var, name = greedy_import_context(name, upwards=True, level=1) if context is None else (context, name)
    for split in name.split(".")[:-1] if name else []:
        if isinstance(var, dict):
            var = var[split]
        elif isinstance(var, list):
            var = var[int(split)]
        else:
            var = getattr(var, split)
    if isinstance(var, dict):
        var[name.split(".")[-1]] = value
    else:
        setattr(var, name.split(".")[-1], value)
