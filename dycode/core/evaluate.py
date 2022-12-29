import typing as th
from .functions import dynamic_args_wrapper, eval_function
from .get_value import get_value
from .types import FunctionDescriptor, ContextType, _NoValue


def eval(
    expression: th.Union[str, FunctionDescriptor],
    context: th.Optional[ContextType] = None,
    strict: bool = True,
    function_of_interest: str = None,
    dynamic_args: bool = False,
) -> th.Any:
    """
    Evaluate variable lookup and function evaluations in a string expression.

    This function is the main entry point for the dycode package. It combines
    the functionality of the get_value and eval_function functions to allow
    for the evaluation of expressions that contain both variable lookups and
    function evaluations.

    Args:
        expression (str or FunctionDescriptor): The expression to evaluate.
        context (dict): The context to use for variable lookups.
        strict (bool): Whether to raise an error if a variable lookup fails.
        function_of_interest (str): The name of the function in the code-block to return.
        dynamic_args (bool): Whether to wrap the resulting function in a dynamic_args_wrapper.

    Returns:
        The result of the evaluation.

    Raises:
        ValueError: If the expression could not be evaluated (and strict is True).
    """
    value = _NoValue
    function_value = _NoValue
    value_error = None
    function_error = None

    try:
        value = get_value(expression, context=context, strict=True)
    except Exception as e:
        value_error = e

    try:
        function_value = eval_function(
            expression, function_of_interest=function_of_interest, context=context, dynamic_args=dynamic_args
        )
    except Exception as e:
        function_error = e

    if value is not _NoValue:
        if callable(value):
            return value if not dynamic_args else dynamic_args_wrapper(value)
        return value
    elif function_value is not _NoValue:
        return function_value

    if strict:
        # raise exception and include both errors
        raise ValueError(
            "Could not evaluate expression:\n%s \n\nValue error:\n%s. \n\nFunction error:\n%s"
            % (expression, value_error, function_error)
        )
    return None
