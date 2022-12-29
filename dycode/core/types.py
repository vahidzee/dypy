import typing as th
import types

# types
CallableFunctionDescriptorStr = th.Union[
    str, th.Dict[str, th.Any]
]  # either a function code (str), or a dict with a "code" key (str) and other keys (dict)
FunctionDescriptor = th.Union[
    th.Callable, CallableFunctionDescriptorStr
]  # either a function or a function descriptor (str, dict)
ContextType = th.Union[th.Dict[str, th.Any], types.ModuleType, th.Any]  # anything that we can get items from


# a singleton object to represent the absence of a value
class _NoValue:
    pass
