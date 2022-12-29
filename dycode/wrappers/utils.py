import functools


def make_inheritence_strict(cls: type, attribute_to_check: str):
    # when instantiating a class that inherits cls and the __init__ method is called
    # then the super() is called which redirects to the __init__ of the parent class
    # here, we should check if the child class is also decorated with @dynamize or not

    old_init = cls.__init__

    # keep signature
    @functools.wraps(old_init)
    def new_init(self, *args, **kwargs):

        # Check if the class is itself decorated with @dynamize or not
        if attribute_to_check not in self.__class__.__dict__:
            raise AttributeError(
                f"{cls.__name__} is a strict class and can only be inherited by classes with the same criteria:"
                "\ntry decorating the child class with @dycode.wrappers such as @dycode.wrappers.dynamize"
            )
        return old_init(self, *args, **kwargs)

    cls.__init__ = new_init

    return cls
