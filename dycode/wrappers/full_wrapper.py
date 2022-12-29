from dycode.wrappers.field_wrapper import _dynamize_fields
from dycode.wrappers.method_wrapper import _dynamize_methods
import typing as th

# Merge the signature of all the wrappers into one signature that acts upon the class
def _dynamize(
    cls,
    inheritence_strict: bool,
    blend: bool,
    indicator_prefix: th.Optional[str],
):
    ret_cls = cls
    ret_cls = _dynamize_fields(
        ret_cls,
        inheritence_strict=inheritence_strict,
        indicator_prefix=indicator_prefix,
    )
    ret_cls = _dynamize_methods(
        ret_cls, inheritence_strict=inheritence_strict, blend=blend
    )
    return ret_cls


def dynamize(
    cls=None,
    /,
    *,
    inheritence_strict: bool = True,
    blend: bool = True,
    indicator_prefix: th.Optional[str] = None,
):
    def wrap(cls):
        return _dynamize(cls, inheritence_strict, blend, indicator_prefix)

    if cls is None:
        return wrap

    return wrap(cls)
