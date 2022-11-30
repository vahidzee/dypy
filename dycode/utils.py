import os
import typing as th


def is_module(name: str) -> bool:
    """
    Check wether a name is a module in the current working directory.

    Args:
        name (str): The name of the module to check.

    Returns:
        bool: True if the name is a module, False otherwise.
    """
    route_steps = name.split(".")
    route_steps = route_steps[1:] if not route_steps[0] else route_steps  # .modulename.<...>
    return os.path.exists(os.path.join(*route_steps[:-1], f"{route_steps[-1]}.py"))


def is_package(name: str) -> bool:
    """
    Check wether a name is a package in the current working directory.

    Args:
        name (str): The name of the package to check.

    Returns:
        bool: True if the name is a package, False otherwise.
    """
    route_steps = name.split(".")
    route_steps = route_steps[1:] if not route_steps[0] else route_steps  # .modulename.<...>
    return os.path.exists(os.path.join(*route_steps, "__init__.py"))
