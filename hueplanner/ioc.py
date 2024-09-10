# from __future__ import annotations

import inspect
from abc import abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from functools import wraps
from inspect import isclass, isfunction
from types import UnionType
from typing import (
    Any,
    Callable,
    Dict,
    Protocol,
    Tuple,
    Type,
    Union,
    get_args,
    get_origin,
    get_type_hints,
    runtime_checkable,
)

import structlog

logger = structlog.getLogger(__name__)


@dataclass(kw_only=True)
class _Signature:
    sig: inspect.Signature
    hints: dict[str, Any]
    target: Any


Constructable = Union[Callable[..., Any], Type[Any]]


class IocError(Exception):
    pass


class IocResolutionFailed(IocError):
    pass


@runtime_checkable
class Provider(Protocol):
    @abstractmethod
    def construct(self, resolution_context: "ResolutionContext") -> Any:
        pass


class Singleton(Provider):
    def __init__(self, instance: Any) -> None:
        if is_function_or_class(instance):
            raise IocError("Singleton entry should be initialized object, not function/class")
        self.instance = instance

    def construct(self, resolution_context: "ResolutionContext") -> Any:
        logger.debug("Singleton reused", instance=self.instance)
        return self.instance

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({repr(self.instance)})"


class Factory(Provider):
    def __init__(self, factory: Callable[..., Any], allow_inject: bool = True) -> None:
        self.factory = factory
        self.allow_inject = allow_inject
        if not is_function_or_class(factory):
            raise IocError(f"Factory entry should be function or class, not {type(factory)}")

        if not self.allow_inject and has_required_args(self.factory):
            raise IocError("Factory function should be injectable or not have required parameters")

    def construct(self, resolution_context: "ResolutionContext") -> Any:
        if self.allow_inject:
            instance = resolution_context.resolve(self.factory)
        else:
            instance = self.factory()
        logger.debug("Instance assembled with factory", factory=self.factory, instance=instance)
        return instance

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({repr(self.factory)})"


class SingletonFactory(Provider):
    _sentinel = object()

    def __init__(self, factory: Factory) -> None:
        self.factory = factory
        self._evaluated = self._sentinel

    def construct(self, resolution_context: "ResolutionContext") -> Any:
        if self._evaluated is not self._sentinel:
            logger.debug("Singleton reused", instance=self._evaluated)
            return self._evaluated
        self._evaluated = self.factory.construct(resolution_context)
        logger.debug("Instance assembled with factory", factory=self.factory, instance=self._evaluated)
        return self._evaluated

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({repr(self.factory)})"


class ResolutionContext:
    def __init__(
        self,
        ioc_container: "IOC",
        *,
        bypass_cache: bool = False,
        nullable_allowed: bool = True,
    ) -> None:
        self.ioc_container = ioc_container
        self.bypass_cache = bypass_cache
        self.nullable_allowed = nullable_allowed
        self._currently_resolving: set = set()
        self._resolution_cache: dict[Any, Any] = {}

    def resolve(self, target: Constructable) -> Any:
        if target in self._currently_resolving:
            raise RuntimeError(f"Detected recursive dependency resolution for {target}")

        if not self.bypass_cache and target in self._resolution_cache:
            return self._resolution_cache[target]

        self._currently_resolving.add(target)
        try:
            resolved = self.ioc_container._make(target, self)
            if not self.bypass_cache:
                self._resolution_cache[target] = resolved
            return resolved
        finally:
            self._currently_resolving.remove(target)


def is_function_or_class(variable):
    # Check if it's a function
    if isfunction(variable):
        return TabError  # It's a function
    # Check if it's a class
    if isclass(variable):
        return True  # It's a class
    return False  # It's neither a function nor a class


# Helper function to check if the type is a union with None, 3.11+ only
def is_optional_nullable(typ) -> bool:
    origin = get_origin(typ)

    # Handle both Union and new-style | unions (UnionType)
    if origin is Union or isinstance(typ, UnionType):
        return type(None) in get_args(typ)

    return False


# New helper function to extract the real type (excluding None)
def get_optional_real_type(typ):
    origin = get_origin(typ)

    # Handle both Union and new-style | unions (UnionType)
    if origin is Union or isinstance(typ, UnionType):
        # Filter out NoneType to get the real required type
        non_none_types = tuple(t for t in get_args(typ) if t is not type(None))
        if len(non_none_types) == 1:
            return non_none_types[0]  # Return the single real type
        else:
            raise ValueError(f"Unexpected union with more than one non-None type: {non_none_types}")

    return typ  # Return the original type if not a union


def has_required_args(factory: Constructable) -> bool:
    # Get the correct callable to inspect: if it's a class, inspect its __init__ method
    if inspect.isclass(factory):
        signature = inspect.signature(factory.__init__)
    else:
        signature = inspect.signature(factory)

    # Loop through the parameters in the signature
    for param in signature.parameters.values():
        # Skip 'self' and 'cls' for methods, since they are not considered arguments
        if param.name in ("self", "cls"):
            continue

        # Check if the parameter has no default value
        if param.default == inspect.Parameter.empty:
            return True

    # If no non-defaulted parameter is found, return False
    return False


def normalize_args(
    sig: inspect.Signature,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    override_args: tuple[Any, ...] | None = None,
    override_kwargs: dict[str, Any] | None = None,
):
    if override_args is None:
        override_args = tuple()
    if override_kwargs is None:
        override_kwargs = {}

    # Extract the function parameters from the signature
    params = sig.parameters

    # Index for positional args
    arg_idx = 0
    override_idx = 0

    # Prepare the final list of args and kwargs to pass
    final_args = []
    final_kwargs = {}

    # print(args, kwargs)
    # print(override_args, override_kwargs)

    # Iterate over the parameters in the function signature
    for param_name, param in params.items():
        # Handle positional and positional-or-keyword arguments
        if param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD):
            # Try to take from override_args first
            if override_idx < len(override_args):
                final_args.append(override_args[override_idx])
                override_idx += 1
            # If override_args is exhausted, take from args
            elif arg_idx < len(args):
                final_args.append(args[arg_idx])
                arg_idx += 1
            # Otherwise, use default values
            elif param.default != inspect.Parameter.empty:
                final_args.append(param.default)
            else:
                raise TypeError(f"Missing required positional argument: '{param_name}'")

        # Handle keyword-only arguments
        elif param.kind == param.KEYWORD_ONLY:
            # Check if the argument is provided in override_kwargs
            if param_name in override_kwargs:
                final_kwargs[param_name] = override_kwargs[param_name]
            # Otherwise, check if it's in the original kwargs
            elif param_name in kwargs:
                final_kwargs[param_name] = kwargs[param_name]
            # If there's a default value, use it
            elif param.default != inspect.Parameter.empty:
                final_kwargs[param_name] = param.default
            else:
                raise TypeError(f"Missing required keyword-only argument: '{param_name}'")

    # Bind the arguments using the final list of args and kwargs
    bound_args = sig.bind(*final_args, **final_kwargs)
    bound_args.apply_defaults()  # Apply defaults for any missing arguments
    # print(bound_args.args, bound_args.kwargs)
    return bound_args.args, bound_args.kwargs


class IOC:
    def __init__(self) -> None:
        self._registry: Dict[Type[Any], Provider] = {}

    def declare(self, dependency: Type[Any], declaration: Union[Provider, Callable[..., Any], object]) -> None:
        if isinstance(declaration, Provider):
            self._registry[dependency] = declaration

        elif isfunction(declaration) or isclass(declaration):
            self._registry[dependency] = Factory(declaration)

        elif isinstance(declaration, object):
            self._registry[dependency] = Singleton(declaration)
        else:
            raise TypeError("Declaration must be a Provider, callable, instance of class or class.")

    def auto_declare(self, obj: Callable[..., Any] | object) -> None:
        if isclass(obj):
            self._registry[obj] = Factory(obj)
            return

        if isfunction(obj):
            obj = Factory(obj)

        if isinstance(obj, Singleton):
            self._registry[type(obj.instance)] = obj
            return

        if isinstance(obj, (Factory, SingletonFactory)):
            rtype = get_type_hints(obj.factory).get("return")
            if rtype:
                self._registry[rtype] = obj
            else:
                raise IocError("Callable must have a return type hint to be auto-declared.")
            return

        if isinstance(obj, object):
            self._registry[type(obj)] = Singleton(obj)
            return

        raise IocError("Auto-declared entry must be a callable, instance of class or class.")

    def resolve(self, typ: Type[Any]):
        return self._resolve_dependency(typ, ResolutionContext(self))

    def make(self, target: Constructable, *args, **kwargs) -> Any:
        return self._make(target, ResolutionContext(self), args, kwargs)

    def _make(
        self,
        target: Constructable,
        resolution_context: ResolutionContext,
        extra_args: tuple[Any] | None = None,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> Any:
        if isclass(target):
            hints = get_type_hints(target.__init__, localns=locals(), globalns=globals())
        elif callable(target):
            hints = get_type_hints(target)
        else:
            raise IocError(f"Can't resolve type hints for {target!r} of type {type(target)!r}")

        signature = _Signature(
            sig=inspect.signature(target),
            hints=hints,
            target=target,
        )
        logger.debug("Starting resolution", signature=signature.sig)

        strict_resolve = True
        if extra_args or extra_kwargs:
            strict_resolve = False

        args_resolved, kwargs_resolved = self._resolve_full(
            signature, resolution_context, strict_resolve=strict_resolve
        )
        args, kwargs = normalize_args(
            signature.sig,
            args_resolved,
            kwargs_resolved,
            extra_args,
            extra_kwargs,
        )
        res = target(*args, **kwargs)
        logger.debug("Successfully resolved", signature=signature.sig, args=args, kwargs=kwargs)
        return res

    def _resolve_full(
        self,
        sign: _Signature,
        resolution_context: ResolutionContext,
        *,
        strict_resolve: bool = True,
    ) -> Tuple[tuple[Any], dict[str, Any]]:
        args, kwargs = self._extract_dependencies(sign)
        args_resolved = OrderedDict()
        kwargs_resolved = {}
        for arg_name, arg_type in args.items():
            try:
                args_resolved[arg_name] = self._resolve_dependency(arg_type, resolution_context)
            except IocResolutionFailed as ex:
                if strict_resolve:
                    raise IocResolutionFailed(f"Failed to make {sign.target!r}, cannot resolve {arg_name!r}: {str(ex)}")

        for kwarg_name, kwarg_type in kwargs.items():
            try:
                kwargs_resolved[kwarg_name] = self._resolve_dependency(kwarg_type, resolution_context)
            except IocResolutionFailed as ex:
                if strict_resolve:
                    raise IocResolutionFailed(f"Failed to make {sign.target!r}, cannot resolve {arg_name}: {str(ex)}")

        return tuple(args_resolved.values()), kwargs_resolved

    def _resolve_dependency(self, typ, context) -> Any:
        # Check if the type is optional (e.g., Foo | None)
        if is_optional := is_optional_nullable(typ):
            # Extract the real type (Foo in Foo | None)
            real_typ = get_optional_real_type(typ)
        else:
            real_typ = typ

        # Try to get the provider for the real type
        if (provider := self._registry.get(real_typ)) is None:
            # If it's optional and nullables are allowed in the context, return None
            if is_optional and context.nullable_allowed:
                return None
            raise IocResolutionFailed(f"no provider for dependency of type {real_typ!r}")

        return provider.construct(context)

    def _extract_dependencies(self, signature: _Signature):
        args = OrderedDict()
        kwargs = {}

        for name, param in signature.sig.parameters.items():
            if name == "self":
                continue  # Skip 'self' for class methods
            param_type = signature.hints.get(name, None)
            if param.default == inspect.Parameter.empty:
                args[name] = param_type
            else:
                kwargs[name] = param_type
        return args, kwargs

    # def _make_sign(self, target: Constructable) -> _Signature:
    #     if isclass(target):
    #         hints = get_type_hints(target.__init__, localns=locals(), globalns=globals())
    #     elif callable(target):
    #         hints = get_type_hints(target)
    #     else:
    #         raise IocError(f"Can't resolve type hints for {target!r} of type {type(target)!r}")

    #     return _Signature(
    #         sig=inspect.signature(target),
    #         hints=hints,
    #         target=target,
    #     )

    # def make_partial(self, target: Constructable) -> Callable[..., Any]:
    #     args, kwargs = self._resolve_full(
    #         self._make_sign(target), ResolutionContext(self), strict_resolve=False
    #     )

    #     # args, kwargs = normalize_args(inspect.signature(target), args, kwargs)
    #     return partial(target, *args, **kwargs)

    def inject(self, fn: Callable[..., Any]) -> Callable[..., Any]:

        @wraps(fn)
        def wrapper(*args, **kwargs) -> Any:
            return self.make(fn, *args, **kwargs)

        return wrapper
