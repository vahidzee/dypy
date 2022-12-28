import typing as th
import sys
import inspect
import abc
from ..get_value import get_value as original_get_value
import types

INDICATOR_PREF = "__dy__"
_FIELDS = "__dycode_fields__"


def get_value(self, key: str, default: th.Any = None) -> th.Any:
    """
    This function is used to get the value of a dynamic field.

    Parameters
    ----------
    key : str
        The name of the dynamic field
    default : th.Any, optional
        The default value to be returned if the field is not found

    Returns
    -------
    th.Any
        The value of the dynamic field
    """
    cls = self.__class__
    if key not in getattr(cls, _FIELDS, {}):
        raise AttributeError(f"{key} is not a dynamic field of {cls.__name__}")
    return getattr(self, key, default)


def _dynamize_fields(
    cls, *, indicator_prefix: th.Optional[str] = None, eval: bool = True
) -> type:

    # all the class attributes starting with this indicator prefix will
    # be considered as dynamic attributes and they are instance attributes rather than class attributes
    # just like dataclasses
    indicator_prefix = indicator_prefix or INDICATOR_PREF
    full_indicator_prefix = f"_{cls.__name__}{indicator_prefix}"

    # A list of all the dynamic fields of the class
    # (key, value) : key is considered without the indicator prefix
    dynamic_fields = {}

    # Taken from dataclass code
    if cls.__module__ in sys.modules:
        globals = sys.modules[cls.__module__].__dict__
    else:
        # Theoretically this can happen if someone writes
        # a custom string to cls.__module__.  In which case
        # such dataclass won't be fully introspectable
        # (w.r.t. typing.get_type_hints) but will still function
        # correctly.
        globals = {}

    # create a dictionary where dynamic_fields[name] is mapped to (annotation, default)
    dynamic_fields = {}

    # Find our base classes in reverse MRO order, and exclude
    # ourselves.  In reversed order so that more derived classes
    # override earlier field definitions in base classes.
    has_dataclass_bases = False
    for b in cls.__mro__[-1:0:-1]:
        # Only process classes that have been processed by our
        # decorator.  That is, they have a _FIELDS attribute.
        base_fields = getattr(b, _FIELDS, None)
        if base_fields is not None:
            has_dataclass_bases = True
            for f in base_fields:
                # If the base class field is already defined in the
                # subclass, we'll override it.
                if f not in dynamic_fields:
                    dynamic_fields[f] = base_fields[f]

    # Now find fields in the class that start with the indicator_prefix
    # and exclude that prefix and put it in dynamic_fields
    cls_annotations = cls.__dict__.get("__annotations__", {})
    for name, value in cls.__dict__.items():
        if name.startswith(full_indicator_prefix):

            if value is None:
                raise AttributeError(
                    f"Field {name} should have an initial default value"
                )
            actual_name = name[len(full_indicator_prefix) :]

            annotation = str if eval else cls_annotations.get(name, None)
            # if annotation is set to None then get the annotation from default value
            if annotation is None:
                annotation = type(value)

            try:
                default_value = (
                    original_get_value(value, context=globals) if eval else value
                )
            except ImportError as e:
                default_value = value
                annotation = cls_annotations.get(name, None) or type(value)

            dynamic_fields[actual_name] = (annotation, default_value)

    # Remove all the fields starting with the indicator_prefix
    # from the class dictionary so that it can work seamlessly with other libraries

    for name in dynamic_fields.keys():
        delattr(cls, full_indicator_prefix + name)
        if (
            "__annotations__" in cls.__dict__
            and indicator_prefix + name in cls.__dict__["__annotations__"]
        ):
            cls.__dict__["__annotations__"].pop(indicator_prefix + name)

    # Add the dynamic_fields to the class dictionary
    setattr(cls, _FIELDS, dynamic_fields)

    # repurpose the init function so that one can pass in the dynamic field values
    # as keyword arguments
    prev_init = cls.__init__
    # 1. define a signature-less init function
    def new_init(self, *args, **kwargs):
        del_from_kwargs = []

        for name, value in kwargs.items():
            if name in dynamic_fields:
                del_from_kwargs.append((name, value))

        for name, _ in del_from_kwargs:
            kwargs.pop(name)

        prev_init(self, *args, **kwargs)

        for name, value in getattr(self.__class__, _FIELDS, {}).items():
            setattr(self, name, value[1])

        for name, value in del_from_kwargs:
            setattr(self, name, value)
        # init should return None by convention
        return None

    # 2. set the signature of the init function
    sig = inspect.Signature.from_callable(prev_init)
    all_parameters = list(sig.parameters.values())
    for name in dynamic_fields.keys():
        new_param = inspect.Parameter(
            name,
            inspect.Parameter.KEYWORD_ONLY,
            default=dynamic_fields[name][1],
            annotation=dynamic_fields[name][0],
        )
        all_parameters.append(new_param)

    new_init.__signature__ = inspect.Signature(
        all_parameters, return_annotation=sig.return_annotation
    )

    # 3. set the new init function
    cls.__init__ = new_init

    # Now implement the getvalue method
    setattr(cls, "get_value", get_value)

    abc.update_abstractmethods(cls)

    return cls


def dynamize_fields(
    cls=None, /, *, indicator_prefix: th.Optional[str] = None, eval=False
):
    """
    This function is a class decorator that wraps the class with a class wrapper.
    and using the implement attribute, these functions can be implemented later on using code blocks.

    Parameters
    ----------
    cls : type
        The class to be wrapped
    indicator_prefix : str, optional
        The prefix used to define the dynamic fields, by default it
        is set to INDICATOR_PREF
    eval : bool, optional
        If this is set to true, then the values of the dynamic fields will go through
        a get_value function which will evaluate the value of the dynamic field, by default True.

    Returns
    -------
    type
        The wrapped class that has a modified init function
        The init function can now take in the dynamic fields as keyword arguments
        and instantiate the class with the dynamic fields on the fly.
    """

    def wrap(cls):
        return _dynamize_fields(cls, indicator_prefix=indicator_prefix, eval=eval)

    # If the class is not given as an argument return
    # a decorator that takes the class as an argument
    if cls is None:
        return wrap
    # If the class is given as an argument then return
    # the wrapped class
    return wrap(cls)
