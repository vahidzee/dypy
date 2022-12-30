import typing as th
import types
import sys
import inspect
from dycode.core.types import FunctionDescriptor
from dycode.core.functions import eval_function
import abc
from dycode.wrappers.utils import make_inheritence_strict

PREF_FOR_CONSTRUCTOR = "__dy__"


def dynamic_method(func: th.Callable, blend: th.Optional[bool] = None) -> th.Callable:
    """
    This function is a method decorator that tags the method with the attribute __is_dynamic_method__.
    This attribute is used by the class wrapper to identify the method as a dynamic method.
    The dynamic method can be implemented later on using code blocks.

    Parameters
    ----------
    func : th.Callable
        The method to be tagged
    blend : bool, optional
        If blend is set to True, then you can also reference the method using its name itself and a __dycode__ prefix
        is not necessarily needed anymore

    Returns
    -------
    th.Callable
        The tagged method
    """

    func.__is_dynamic_method__ = True
    func.__blend__ = blend
    return func


def implement_method(
    self,
    method_name: str,
    function_descriptor: FunctionDescriptor,
    function_of_interest: str = None,
    context: th.Any = None,
    dynamic_args: bool = False,
):
    cls = self.__class__
    if method_name not in cls.__dynamic_methods__:
        raise AttributeError(f"{method_name} is not a dynamic method of {cls.__name__}")

    fn = eval_function(
        function_descriptor,
        function_of_interest,
        context,
        dynamic_args,
    )

    setattr(self, method_name, types.MethodType(fn, self))


def implement_methods(self, **kwargs):
    for method_name, method_code in kwargs.items():
        implement_method(self, method_name, method_code)


def _dynamize_methods(cls: type, inheritence_strict: bool, blend: bool) -> type:
    """
    This function is a class decorator that wraps the class with a class wrapper.
    The input class will have some methods tagged with @dynamic_method
    and using the implement method, these functions can be implemented later on using code blocks.

    Parameters
    ----------
    cls : type
        The class to be wrapped
    blend : bool
        If set to true, then in the constructor of the class you do not need any prefix for the dynamic methods
        however, if there is an attribute in the class object that has the same name as the dynamic method it might
        cause problems. We typically advise using different names for methods, but in case you want to use the same
        name, then you can use the blend=False option and set __dy__ prefix in the constructor.

    Returns
    -------
    type
        The wrapped class
    """
    # Heavily influenced by dataclasses code
    if cls.__module__ in sys.modules:
        globals = sys.modules[cls.__module__].__dict__
    else:
        # Theoretically this can happen if someone writes
        # a custom string to cls.__module__.  In which case
        # such dataclass won't be fully introspectable
        # (w.r.t. typing.get_type_hints) but will still function
        # correctly.
        globals = {}

    # get allthe methods that are tagged with __is_dynamic_method__ and
    # add them to the class attribute __dynamic_methods__
    # For blending, if the method was specifically set to blend using the function
    # decorator, then add it to the __blended_dynamic_methods__ set and if it was specifically
    # set to not blend, then do not add it to the set
    # otherwise, check out the blend option of the class decorator
    dynamic_methods = set()
    blended_dynamic_methods = set()
    for name in dir(cls):
        value = getattr(cls, name)
        if getattr(value, "__is_dynamic_method__", False):
            dynamic_methods.add(name)

            # handle blending
            blend_spec = getattr(value, "__blend__", None)
            if blend_spec is None:
                blend_spec = blend

            # if it was blended specifically or blended in options add the name
            if blend_spec:
                blended_dynamic_methods.add(name)
    # handle inheritence, merge the dynamic methods of the parent classes
    for b in cls.__mro__[-1:0:-1]:
        # merge dynamic methods with parent
        dynamic_methods = dynamic_methods.union(
            getattr(b, "__dynamic_methods__", set())
        )
        # merge blended dynamic methods with parent
        blended_dynamic_methods = blended_dynamic_methods.union(
            getattr(b, "__blended_dynamic_methods__", set())
        )
    cls.__dynamic_methods__ = frozenset(dynamic_methods)
    cls.__blended_dynamic_methods__ = frozenset(blended_dynamic_methods)

    # add the implement_methods method to the class
    setattr(cls, "implement_methods", implement_methods)

    # 2. Define the new __init__ function for the new class
    init_before = cls.__init__

    # First define the new __init__ function without signature
    # and then add the signature
    def new_init(self, *args, **kwargs):

        # Implement the methods that are passed as keyword arguments
        delete_from_kwargs = []
        for name in kwargs:
            key_name = name
            if name.startswith(PREF_FOR_CONSTRUCTOR):
                # check if name starts with __dy__
                key_name = name[len(PREF_FOR_CONSTRUCTOR) :]
            else:
                if key_name not in cls.__blended_dynamic_methods__:
                    key_name = None

            if key_name in cls.__dynamic_methods__:
                # TODO: check whether there are any other context arguments
                implement_method(self, key_name, kwargs[name], context=globals)
                delete_from_kwargs.append(name)

        # Delete the arguments that were used to implement the methods
        for name in delete_from_kwargs:
            kwargs.pop(name)

        # call the parent __init__ method
        return init_before(self, *args, **kwargs)

    # Extend the signature of init_before to include implementations of
    # the dynamic methods and assign the new signature to the new __init__
    sig = inspect.Signature.from_callable(init_before)
    all_parameters = list(sig.parameters.values())
    # add all the __dy__ prefixed parameters to the signature
    for name in cls.__dynamic_methods__:
        new_param = inspect.Parameter(
            f"{PREF_FOR_CONSTRUCTOR}{name}",
            inspect.Parameter.KEYWORD_ONLY,
            default=None,
            annotation=th.Optional[FunctionDescriptor],
        )
        if new_param not in all_parameters:
            all_parameters.append(new_param)
        # all_parameters[f"{PREF_FOR_CONSTRUCTOR}{name}"] = new_param

    # add all the non prefixed parameters to the signature that are blended
    for name in cls.__blended_dynamic_methods__:
        if name in all_parameters:
            raise Exception(
                f"Cannot blend dynamic method with attribute of the same name: {name}\nConsider changing the method name!"
            )
        new_param = inspect.Parameter(
            name,
            inspect.Parameter.KEYWORD_ONLY,
            default=inspect.Parameter.empty,
            annotation=th.Optional[FunctionDescriptor],
        )
        if new_param not in all_parameters:
            all_parameters.append(new_param)

    # delete *args and **kwargs from all_parameters (TODO: not sure of this)
    all_parameters = [
        p for p in all_parameters if p.kind != inspect.Parameter.VAR_POSITIONAL
    ]

    all_parameters = [
        p for p in all_parameters if p.kind != inspect.Parameter.VAR_KEYWORD
    ]
    # replace the parameters with the extended version
    new_init.__signature__ = inspect.Signature(
        all_parameters, return_annotation=sig.return_annotation
    )

    # finally, setup as the new init function
    cls.__init__ = new_init

    # abc.update_abstractmethods(cls) # todo: support lower python versions

    if inheritence_strict:
        # if inheritence is set to strict then all the children of this class should also contain
        # the dynamic methods
        cls = make_inheritence_strict(cls, "__dynamic_methods__")

    return cls


def dynamize_methods(
    cls=None, /, *, inheritence_strict: bool = True, blend: bool = True
):
    """
    Dynamize the methods of a class that are tagged.

    This way, we can implement the methods in the constructor fast and easy.

    Parameters
    ----------
    cls : type
        The class to dynamize the methods of.
    blend : bool
        If True, then all the methods are assumed to have unique names and different from
        the attributes of the class, and then one can define them in the constructor easily.
        If False, then the methods should be prefixed while defining them in the constructor.
        -- However, if a particular method is tagged with a specific blend option, then this will
        overwrite the default blend option, meaning that for a class with blend=False, if a specific
        method has blend=True then in the constructor it should not be prefixed.

    Returns
    -------
    type
        The class with the dynamized methods.
    """

    def wrap(cls):
        return _dynamize_methods(
            cls, inheritence_strict=inheritence_strict, blend=blend
        )

    # If the class is not given as an argument return
    # a decorator that takes the class as an argument
    if cls is None:
        return wrap
    # If the class is given as an argument then return
    # the wrapped class
    return wrap(cls)
