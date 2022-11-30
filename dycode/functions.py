import importlib
import typing as th
import types
import inspect
import os
from .utils import is_module, is_package
import functools

# types
CallableFunctionDescriptorStr = th.Union[
    str, th.Dict[str, th.Any]
]  # either a function code (str), or a dict with a "code" key (str) and other keys (dict)
FunctionDescriptor = th.Union[
    th.Callable, CallableFunctionDescriptorStr
]  # either a function or a function descriptor (str, dict)

# registry for function evaluation
CONTEXT_REGISTRY = dict()


def register_context(context: th.Any, name: str = None):
    """
    Registers a context to be used in the dynamic code.

    Args:
        context (typing.Any): The context to register.
        name (str): The name of the context to register.

    Returns:
        None
    """
    if name is None:
        name = context.__name__
    CONTEXT_REGISTRY[name] = context


def dynamic_args_wrapper(function: th.Callable) -> th.Callable:
    """
    Wraps a function in a dynamic argument parser, that will try to call the function with the arguments it can, and ignore the rest.

    Args:
        function (typing.Callable): The function to wrap.

    Returns:
        typing.Callable: The wrapped function.
    """
    signature = inspect.signature(function)
    params = signature.parameters

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        call_kwargs = {name: kwargs[name] for name in params if name in kwargs}
        return function(*args, **call_kwargs)

    return wrapper


def generate_function(code_block, function: str) -> th.Callable[[th.Any], th.Any]:
    """
    Generates a function from a code block.

    Args:
        code_block (str): The code block to generate the function from.
        function (str): The name of the function (in the code block) to return.

    Returns:
        typing.Callable[[typing.Any], typing.Any]: The generated function.
    """
    context = dict()
    exec(code_block, dict(), context)
    return types.FunctionType(
        code=context[function].__code__,
        globals=context,
        name=function,
        argdefs=context[function].__defaults__,
    )


def eval_function(
    function_descriptor: th.Union[th.Callable, str, th.Dict[str, str]],
    function_of_interest: str = None,
    context: th.Any = None,
    dynamic_args: bool = False,
) -> th.Callable:
    """
    Processes a function descriptor (str, dict, callable) into a callable function.

    Function descriptors can be:
        - a function code (str): "lambda x: x + 1" or a callable function variable like "math.sin".
        - a function descriptor code block (str): "def function(x): return x + 1"
            If a code block is provided, the function_of_interest argument must be specified to indicate which
            function in the code block to return. (default: look for a function named "function")
        - a function descriptor dict (dict): a dictionary with the following keys:
            - "code": the function code (str) or a function descriptor code block (str).
            - "function_of_interest" (optional): the name of the function in the code block to return (str), overridden by
                the function_of_interest argument.
            - "context" (optional): the context to use when evaluating the function descriptor code block (str, dict, callable).
    Args:
        function_descriptor (typing.Union[typing.Callable, str, typing.Dict[str, str]]): The function description.
        function_of_interest (str): The name of the function to return.
            In case the function description is a code block, this is the name of the function of interest in that
            code block.

            For example, if the code block is:
            ```
            def function1():
                pass
            def function2():
                # do something (maybe use function1)
                pass
            ```
            and the function_of_interest is "function2", then the whole code block will be evaluated, and the function
            "function2" will be returned. By default, the function_of_interest is "function", Meaning that if the code
            is not a function itself (like lambda anonymous functions, or callable values like math.sin), eval_function
            will look for a function named "function" in the code block.

        context (typing.Any): The context to use when generating the function.
            For example, if the code block is: "math.sin", when evaluating the function descriptor, "math" module
            should be in the context. So context should be a dict with {"math": math}.
            This argument is optional, and if provided will be used to update (and add to) the DyCode context registry.

            You can use the register_context function to register a context, and then use it in every call to eval_function,
            without having to pass it as an argument.

            This might be useful if you want to use the same context in multiple calls to eval_function.

        dynamic_args (bool): If True, the function will be wrapped in a dynamic argument parser, that will try to call the
            function with the arguments it can, and ignore the rest.

            Useful for when a boilerplate function is expected to be called with a specific set of arguments, but the
            arguments are not known in advance, or are not always needed for the function to work.

    Returns:
        typing.Callable: The function.
    """
    # if function is callable or not a function descriptor, return it (it's already evaluated)
    if callable(function_descriptor) or not isinstance(function_descriptor, (str, dict)):
        results = function_descriptor
    else:
        try:
            # evaluate the function with the Registry as the context (first type of function descriptor)
            # if it's a function dict descriptor, merge Registry with function["context"] (if exists) and run the function
            # if it's a function code descriptor, run the function
            if isinstance(function_descriptor, dict):
                context = context or dict()
                context.update(CONTEXT_REGISTRY)
                context.update(function_descriptor.get("context", dict()))
                function_code = function_descriptor["code"]
            else:
                context = context or dict()
                context.update(CONTEXT_REGISTRY)
                function_code = function_descriptor

            results = eval(function_code, context)
        except SyntaxError:
            # second and third type of function descriptor (code block)
            assert function_of_interest is not None or (
                isinstance(function_descriptor, dict) and "function_of_interest" in function_descriptor
            ), "function_of_interest must be specified when using a code block as a function descriptor."
            results = generate_function(
                code_block=function_descriptor
                if isinstance(function_descriptor, str)
                else function_descriptor["code"],
                function=function_descriptor.get("function_of_interest", function_of_interest)
                if isinstance(function_descriptor, dict)
                else function_of_interest,
            )

    return dynamic_args_wrapper(results) if dynamic_args else results
