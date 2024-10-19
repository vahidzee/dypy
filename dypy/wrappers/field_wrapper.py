import typing as th
import sys
import inspect
import abc
from ..core.get_value import get_value as original_get_value
from ..core.types import ContextType
from .utils import make_inheritence_strict
import warnings

_FIELDS = "__dypy_fields__"
_DY_TYPE_SUFFIX = "_type"
_DY_CONSTRUCTOR_ARGS_SUFFIX = "_args"


class DynamicField:
    def __init__(
        self,
        value,
        /,
        *,
        eval: bool = False,
        prefer_modules: bool = False,
        strict: bool = True,
        context: th.Optional[ContextType] = None,
        # if is_class is True then it means that the evaluated thing is a class
        # type that can be instantiated
        is_class: bool = False,
        constructor_arguments: th.Optional[dict] = None,
        nullable: bool = False,
    ) -> None:
        self.nullable = nullable
        self.strict = strict
        self.prefer_modules = prefer_modules
        self.eval = eval
        self.context = context
        self.is_class = is_class

        if self.is_class:
            self.eval = True

        self.constructor_arguments = constructor_arguments or {}
        self._value = value

    def change_context(self, context: th.Optional[ContextType] = None):
        # TODO: might not be the best way to go
        if self.context is None:
            self.context = context

    @property
    def value(self):
        return (
            self._value
            if not self.eval
            else original_get_value(
                self._value, self.prefer_modules, self.strict, self.context
            )
        )

    def get_instance(self):
        if not self.is_class:
            raise TypeError("Cannot get instance of non-class field")
        return self.value(**self.constructor_arguments)


def field(
    default: th.Any,
    /,
    *,
    eval: bool = False,
    prefer_modules: bool = False,
    strict: bool = True,
    nullable: bool = False,
) -> DynamicField:
    return DynamicField(
        default,
        eval=eval,
        prefer_modules=prefer_modules,
        strict=strict,
        nullable=nullable,
    )


def composite(
    default: th.Optional[str],
    /,
    *,
    nullable: bool = False,
    **constructor_kwargs,
) -> DynamicField:
    return DynamicField(
        default,
        eval=True,
        is_class=True,
        constructor_arguments=constructor_kwargs,
        nullable=nullable,
    )


def get_dynamic_value(self, key: str, default: th.Any = None) -> th.Any:
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
    cls: type, indicator_prefix: th.Optional[str], inheritence_strict: bool = True
) -> type:

    # all the class attributes having the type DynamicField and starting with indicator_prefix
    # are considered as dynamic fields
    # and are instance attributes rather than class attributes, just like dataclasses
    indicator_prefix = indicator_prefix or ""
    full_indicator_prefix = f"{indicator_prefix}"

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
    for name, val in cls.__dict__.items():
        if isinstance(val, DynamicField) and name.startswith(full_indicator_prefix):

            if val is None:
                raise AttributeError(
                    f"Field {name} should have an initial default value"
                )

            if val.context:
                raise NotImplementedError(
                    "Context merging is not yet implemented in the field wrapper"
                )

            # Change the context to the class context
            # TODO: optimally, one should merge the context of the class and the field
            val.change_context(globals)

            # get the value in the field
            actual_name = name[len(full_indicator_prefix) :]

            annotation = cls_annotations.get(name, None)

            if val.is_class:
                if annotation is not None:
                    raise TypeError("Should not set annotation for class objects")
                dynamic_fields[actual_name] = (
                    val,
                    val.get_instance(),
                )

                dynamic_fields[f"{actual_name}{_DY_TYPE_SUFFIX}"] = (str, val._value)
                dynamic_fields[f"{actual_name}{_DY_CONSTRUCTOR_ARGS_SUFFIX}"] = (
                    dict,
                    val.constructor_arguments,
                )
            else:
                dynamic_fields[actual_name] = (annotation or type(val.value), val.value)

    # Remove all the fields starting with the indicator_prefix
    # from the class dictionary so that it can work seamlessly with other libraries

    for name in dynamic_fields.keys():
        if getattr(cls, full_indicator_prefix + name, None) is not None:
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

        def set_all_values():
            # set the default values of the dynamic fields
            for name, value in getattr(self.__class__, _FIELDS, {}).items():
                setattr(self, name, value[1])

            # write stuff that has been inputted in the init function
            names_with_dict = set()
            for name, value in del_from_kwargs:

                # works with both DynamicField and the actual value
                if isinstance(value, DynamicField):
                    # give a warning if the value is of DynamicField type

                    warnings.warn(
                        f"Passing a DynamicField object as a value to {name} is deprecated. "
                        f"Please use the value of the DynamicField object instead.",
                        DeprecationWarning,
                    )

                    if value.is_class:
                        value.change_context(globals)
                        setattr(self, name, value.get_instance())
                    else:
                        setattr(self, name, value.value)
                else:
                    if name + _DY_CONSTRUCTOR_ARGS_SUFFIX in getattr(
                        self.__class__, _FIELDS, {}
                    ) or name.endswith(_DY_CONSTRUCTOR_ARGS_SUFFIX):
                        # This is the name of a composite so handle composites
                        # handle construction
                        # TODO: implement this better
                        _name = (
                            name
                            if not name.endswith(_DY_CONSTRUCTOR_ARGS_SUFFIX)
                            else name[: -len(_DY_CONSTRUCTOR_ARGS_SUFFIX)]
                        )
                        names_with_dict.add(_name)
                    else:
                        setattr(self, name, value)

            del_from_kwargs_dict = dict(del_from_kwargs)

            # write the dynamic class values
            for name in names_with_dict:

                val = getattr(self.__class__, _FIELDS, {}).get(name, (None, None))[0]

                class_name = (
                    val._value
                    if name not in del_from_kwargs_dict
                    else del_from_kwargs_dict[name]
                )
                class_args = (
                    val.constructor_arguments
                    if name + _DY_CONSTRUCTOR_ARGS_SUFFIX not in del_from_kwargs_dict
                    else del_from_kwargs_dict[name + _DY_CONSTRUCTOR_ARGS_SUFFIX]
                )

                if class_name is None:
                    if val.nullable:
                        setattr(self, name, None)
                        continue
                    else:
                        raise TypeError(
                            f"Field {name} is not nullable but None given in constructor"
                        )

                # get the default constructor args

                if val and val._value == class_name:
                    constructor_args = val.constructor_arguments
                    # overwrite class_args with original
                    for k, v in class_args.items():
                        constructor_args[k] = v
                elif val:
                    constructor_args = class_args

                val = DynamicField(
                    class_name,
                    is_class=True,
                    context=globals,
                    constructor_arguments=constructor_args,
                )
                val.change_context(globals)
                setattr(self, name, val.get_instance())

        # First set all values for potential usage in the __init__
        set_all_values()
        # init should return None by convention
        ret = prev_init(self, *args, **kwargs)
        # TODO: check for changes: if something has been changed in the init function
        # then raise an error

        # Then re-write all the values in the __init__
        set_all_values()

        return ret

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
        if new_param not in all_parameters:
            all_parameters.append(new_param)

    # delete *args and **kwargs from all_parameters
    all_parameters = [
        p for p in all_parameters if p.kind != inspect.Parameter.VAR_POSITIONAL
    ]

    all_parameters = [
        p for p in all_parameters if p.kind != inspect.Parameter.VAR_KEYWORD
    ]

    new_init.__signature__ = inspect.Signature(
        all_parameters, return_annotation=sig.return_annotation
    )

    # 3. set the new init function
    cls.__init__ = new_init

    # Now implement the getvalue method
    setattr(cls, "get_dynamic_value", get_dynamic_value)

    # abc.update_abstractmethods(cls) # todo: handle lower python versions

    if inheritence_strict:
        # make the class inheritence strict so that every child class should have the _FIELDS attribute
        cls = make_inheritence_strict(cls, _FIELDS)

    return cls


def dynamize_fields(
    cls=None,
    /,
    *,
    indicator_prefix: th.Optional[str] = None,
    inheritence_strict: bool = True,
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
        return _dynamize_fields(
            cls,
            inheritence_strict=inheritence_strict,
            indicator_prefix=indicator_prefix,
        )

    # If the class is not given as an argument return
    # a decorator that takes the class as an argument
    if cls is None:
        return wrap
    # If the class is given as an argument then return
    # the wrapped class
    return wrap(cls)
