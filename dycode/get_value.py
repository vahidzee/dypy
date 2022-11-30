import importlib
import typing as th
import types
import inspect
import os
from .utils import is_module, is_package

# types
ContextType = th.Union[th.Dict[str, th.Any], types.ModuleType, th.Any]  # anything that we can get items from


def importer(name) -> ContextType:
    """
    Imports a module or a package.
    The difference between this function and importlib.import_module is that
    this function can import packages from the current working directory as well.

    Args:
        name (str): The name of the module or package to import.

    Returns:
        types.ModuleType: The imported module or package.
    """
    try:
        # try importing as a module (using importlib from standard import mechanism)
        return __import__(name, globals=globals(), locals=locals())
    except:
        route_steps = name.split(".")
        route_steps = route_steps[1:] if not route_steps[0] else route_steps
        is_name_module, is_name_package = is_module(name), is_package(name)
        assert is_name_module or is_name_package
        file_path = os.path.join(*route_steps)
        if is_name_module:
            file_path = f"{file_path}.py"
        else:  # name is definitely a package (because of the assertion)
            file_path = os.path.join(file_path, "__init__.py")
        spec = importlib.util.spec_from_file_location(name, file_path)
        foo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(foo)
        return foo


def greedy_import_context(name: str, upwards: bool = False, level: int = 0) -> th.Tuple[th.Any, str]:
    """
    Greediely try importing a name, and return the first successful import, and
    the name of the variable we were able  to import.

    Args:
        name (str): The name of the variable to import.
        upwards (bool): If True, for "x.y.z", try importing "x."
            first, then "x.y." and then "x.y.z", and if False, try "x.y.z" first, then "x.y." and then "x.".
        level (int): level of the import. 0 means import the whole name, 1 means leaving out one level, etc.
            For example, when level=1, name="x.y.z", upwards=True, we will try importing "x.y".

    Returns:
        th.Tuple[th.Any, str]: The first successful import, and the name of the variable we were able to lookup.
    """
    module_hierarchy = name.split(".")
    imported_module = None
    for trial_index in range(
        1 if upwards else len(module_hierarchy) - level,
        (len(module_hierarchy) + 1 - level) if upwards else -1,
        1 if upwards else -1,
    ):
        try:
            imported_module = importer(".".join(module_hierarchy[:trial_index]))
            break
        except:
            pass
    return imported_module, ".".join(module_hierarchy[trial_index:])


def __get_value(name: str, strict: bool = True, upwards: bool = True, context: th.Optional[ContextType] = None):
    """
    Gets a value for variable "name" in the context "context", or in the global context if "context" is None.

    Args:
        name (str): The name of the variable to get.
        strict (bool): If True, raise an error if the variable is not found.
        upwards (bool): direction of the import, see greedy_import_context.
        context (typing.Any): The context to get the variable from.
    """

    var, name = greedy_import_context(name, upwards=upwards) if context is None else (context, name)
    for split in name.split(".") if name else []:
        if isinstance(var, dict):
            if split not in var:
                if strict:
                    raise KeyError('Invalid key "%s"' % name)
                else:
                    return None
            var = var[split]
        else:
            if not hasattr(var, split):
                if strict:
                    raise AttributeError("Invalid attribute %s" % name)
                else:
                    return None
            var = getattr(var, split)
    return var


def _get_value(name: str, prefer_modules: bool = False, strict: bool = True, context=None):

    results = []
    try:
        results.append(__get_value(name, upwards=True, strict=strict, context=context))
    except:
        pass
    try:
        results.append(__get_value(name, upwards=False, strict=strict, context=context))
    except:
        pass
    if not results:
        raise ImportError(name)
    if len(results) == 1:
        return results[0]

    # checking for successful lookup in non-strict config
    if not strict and results[0] is None and results[1] is not None:
        return results[1]
    elif not strict and results[0] is not None and results[1] is None:
        return results[0]

    # looking for modules
    if prefer_modules:
        return results[1] if inspect.ismodule(results[1]) else results[0]
    else:
        return results[0]


def get_value(
    name, prefer_modules: bool = False, strict: bool = True, context: th.Optional[ContextType] = None, num_trys=3
):
    """
    Lookup and retrieve a value defind by "name" in "context" (or in the global scope if "context" is None).

    Args:
        name (str): The name of the variable to retrieve.
        prefer_modules (bool): If True, prefer modules over other types of objects, in any intermidiate lookup step.
        strict (bool): If True, raise an error if the lookup fails. If False, return None if the lookup fails.
        context (typing.Any): The context to get the variable from. If None, get the variable from the global scope.
        num_trys (int):
            The number of times to try the lookup. If the lookup fails, try again. Sometimes, the lookup fails because
            changes in the global scope, or Python's import mechanism (PATH, etc.) are not yet reflected in the current
            scope. This is a naive workaround for this issue.

    Returns:
        typing.Any: The value of the variable.
    """
    for _ in range(num_trys - 1):
        try:
            return _get_value(name, strict=strict, prefer_modules=prefer_modules, context=context)
        except KeyError:
            pass
        except AttributeError:
            pass
        except ImportError:
            pass
    return _get_value(name, strict=strict, prefer_modules=prefer_modules, context=context)
