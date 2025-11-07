"""Extension system for custom types and command-line argument handling.

This module provides RustyBT's extension mechanism, allowing users to:
1. Register custom implementations of extensible interfaces
2. Pass configuration via command-line arguments in key=value format
3. Organize extension arguments in hierarchical namespaces

The extension system consists of two main components:

Extension Arguments (Namespace):
    Hierarchical namespace for passing custom arguments to extensions via CLI.
    Arguments use dot notation: --extension-arg key.subkey=value

Extension Registry (Registry):
    Factory pattern for registering and loading custom implementations of
    extensible base classes (e.g., custom data loaders, slippage models).

Key Classes:
    Namespace: Hierarchical attribute container for extension arguments
    Registry: Manages factories for a specific extensible interface

Public API:
    Namespace Creation:
        - create_args: Build namespace tree from CLI arguments
        - parse_extension_arg: Parse individual key=value arguments

    Registry Management:
        - create_registry / @extensible: Mark interface as extensible
        - register: Register factory for an interface
        - load: Instantiate registered factory by name
        - unregister: Remove registered factory
        - clear: Remove all registered factories
        - get_registry: Get Registry for an interface

Examples:
    Extension arguments:
        >>> # Command line: --extension-arg my.config.host=localhost
        >>> root = Namespace()
        >>> create_args(['my.config.host=localhost'], root)
        >>> root.my.config.host
        'localhost'

    Extension registry:
        >>> @extensible
        ... class DataLoader:
        ...     '''Base class for data loaders'''
        ...     pass
        >>>
        >>> @register(DataLoader, 'csv')
        ... def make_csv_loader():
        ...     return CSVDataLoader()
        >>>
        >>> loader = load(DataLoader, 'csv')

    Full workflow:
        >>> from rustybt.extensions import extensible, register, load
        >>>
        >>> @extensible
        ... class SlippageModel:
        ...     pass
        >>>
        >>> class FixedSlippage(SlippageModel):
        ...     def __init__(self, spread=0.01):
        ...         self.spread = spread
        >>>
        >>> @register(SlippageModel, 'fixed')
        ... def make_fixed_slippage():
        ...     return FixedSlippage()
        >>>
        >>> model = load(SlippageModel, 'fixed')

Architecture:
    Registry Pattern:
        - Interfaces marked with @extensible decorator
        - Factories registered with @register decorator
        - Instances created via load() function
        - One Registry per extensible interface

    Namespace Pattern:
        - Dot-separated keys create attribute chains
        - Safe for both reading and assignment
        - Used for passing config to extensions

Note:
    This system is inspired by setuptools entry points but is lighter-weight
    and doesn't require package installation.
"""
import re

from toolz import curry


def create_args(args, root):
    """Build hierarchical namespace from command-line argument strings.

    Parses a list of key=value or key.namespace.subkey=value argument strings
    and constructs a nested Namespace object tree. Dot-separated keys create
    nested attribute chains.

    Args:
        args (list[str]): List of argument strings in key=value format.
            Keys can use dot notation for nested namespaces.
        root (Namespace): The root Namespace object to populate.

    Raises:
        ValueError: If any argument is not in valid key=value format.
        ValueError: If there are conflicting assignments at same namespace level.

    Examples:
        >>> root = Namespace()
        >>> create_args(['host=localhost', 'db.name=trading', 'db.port=5432'], root)
        >>> root.host
        'localhost'
        >>> root.db.name
        'trading'
        >>> root.db.port
        '5432'

        Conflicting assignments:
            >>> root = Namespace()
            >>> create_args(['a.b.c=1', 'a.b=2'], root)  # Error!
            ValueError: Conflicting assignments at namespace level 'b'

    Note:
        - Arguments are processed in sorted order by key length
        - All values are stored as strings
        - Later assignments to same key overwrite earlier ones
    """
    extension_args: dict[str, str] = {}

    for arg in args:
        parse_extension_arg(arg, extension_args)

    for name in sorted(extension_args, key=len):
        path = name.split(".")
        update_namespace(root, path, extension_args[name])


def parse_extension_arg(arg, arg_dict):
    """Parse a single extension argument into a dictionary.

    Validates and extracts the key and value from an argument string in
    key=value format. Keys must be valid Python identifiers and can use
    dot notation for nested namespaces.

    Args:
        arg (str): Argument string in key=value or key.sub.key=value format.
        arg_dict (dict): Dictionary to store the parsed key-value pair.

    Raises:
        ValueError: If argument is not in valid key=value format or if
            the key is not a valid identifier.

    Examples:
        >>> args = {}
        >>> parse_extension_arg('host=localhost', args)
        >>> args
        {'host': 'localhost'}

        >>> args = {}
        >>> parse_extension_arg('db.config.url=postgres://...', args)
        >>> args
        {'db.config.url': 'postgres://...'}

        Invalid formats:
            >>> parse_extension_arg('no_equals_sign', {})
            ValueError: invalid extension argument 'no_equals_sign', ...

            >>> parse_extension_arg('123invalid=value', {})
            ValueError: invalid extension argument '123invalid=value', ...

    Note:
        - Keys must start with a letter or underscore
        - Keys can contain letters, numbers, underscores, and dots
        - Values can be any string (including empty strings)
    """
    match = re.match(r"^(([^\d\W]\w*)(\.[^\d\W]\w*)*)=(.*)$", arg)
    if match is None:
        raise ValueError(f"invalid extension argument '{arg}', must be in key=value form")

    name = match.group(1)
    value = match.group(4)
    arg_dict[name] = value


def update_namespace(namespace, path, name):
    """Recursively build nested Namespace tree from dotted path.

    Creates or updates a chain of Namespace objects based on a dot-separated
    path, setting the final value at the leaf level. Intermediate Namespace
    objects are created as needed.

    Args:
        namespace (Namespace): The current namespace object to update.
        path (list[str]): List of attribute names forming the path.
        name (str): The value to assign at the final path element.

    Raises:
        ValueError: If an intermediate path element is already assigned a
            string value (conflict between leaf and branch).

    Examples:
        >>> ns = Namespace()
        >>> update_namespace(ns, ['db', 'host'], 'localhost')
        >>> ns.db.host
        'localhost'

        >>> update_namespace(ns, ['db', 'port'], '5432')
        >>> ns.db.port
        '5432'
        >>> ns.db.host  # Still exists
        'localhost'

        Conflict example:
            >>> ns = Namespace()
            >>> update_namespace(ns, ['config'], 'value')  # config='value'
            >>> update_namespace(ns, ['config', 'sub'], 'x')  # Error!
            ValueError: Conflicting assignments at namespace level 'config'

    Note:
        - Recursively processes path elements from left to right
        - Creates intermediate Namespace objects as needed
        - Final path element gets the string value
    """
    if len(path) == 1:
        setattr(namespace, path[0], name)
    else:
        if hasattr(namespace, path[0]):
            if isinstance(getattr(namespace, path[0]), str):
                raise ValueError(f"Conflicting assignments at namespace level '{path[0]}'")
        else:
            a = Namespace()
            setattr(namespace, path[0], a)

        update_namespace(getattr(namespace, path[0]), path[1:], name)


class Namespace:
    """Empty namespace object for storing hierarchical extension arguments.

    A simple placeholder class used to create nested attribute structures
    for extension configuration. Attributes can be dynamically added without
    prior declaration.

    Examples:
        >>> ns = Namespace()
        >>> ns.host = 'localhost'
        >>> ns.db = Namespace()
        >>> ns.db.port = 5432
        >>> ns.db.port
        5432

        Used by create_args:
            >>> root = Namespace()
            >>> create_args(['api.key=secret', 'api.timeout=30'], root)
            >>> root.api.key
            'secret'
            >>> root.api.timeout
            '30'

    Note:
        This is a minimal class with no special behavior. It simply provides
        a clean namespace for dynamic attribute assignment.
    """


class Registry:
    """Manages factory registration and loading for an extensible interface.

    A Registry instance manages all factory functions that create instances
    of custom implementations for a specific extensible base class. Each
    extensible interface gets its own Registry instance.

    The Registry implements the factory pattern: instead of storing class
    references directly, it stores factory functions (or classes) that
    create instances when called with no arguments.

    Args:
        interface (type): The base class/interface this registry manages.

    Attributes:
        interface (type): The base class for this registry.
        _factories (dict): Maps factory names to factory callables.

    Examples:
        Creating and using a registry:
            >>> registry = Registry(SlippageModel)
            >>> registry.register('fixed', lambda: FixedSlippage(0.01))
            >>> model = registry.load('fixed')

        Using as decorator:
            >>> @registry.register('variable')
            ... def make_variable_slippage():
            ...     return VariableSlippage()

        Checking registration:
            >>> registry.is_registered('fixed')
            True
            >>> registry.is_registered('nonexistent')
            False

    Note:
        - Typically accessed via module-level functions (register, load, etc.)
        - One Registry per extensible interface
        - Factories must be zero-argument callables
    """

    def __init__(self, interface):
        """Initialize registry for an extensible interface.

        Args:
            interface (type): The base class this registry manages.
        """
        self.interface = interface
        self._factories = {}

    def load(self, name):
        """Construct an instance from a registered factory.

        Calls the factory function registered under the given name and
        returns the result. The factory must be a zero-argument callable.

        Args:
            name (str): Name of the registered factory to instantiate.

        Returns:
            An instance created by the registered factory.

        Raises:
            ValueError: If no factory is registered under the given name.

        Examples:
            >>> registry = Registry(DataLoader)
            >>> registry.register('csv', CSVLoader)
            >>> loader = registry.load('csv')
        """
        try:
            return self._factories[name]()
        except KeyError as exc:
            raise ValueError(
                f"no {self.interface.__name__} factory registered under name {name!r}, options are: {sorted(self._factories)!r}",
            ) from exc

    def is_registered(self, name):
        """Check whether a factory is registered under the given name.

        Args:
            name (str): Factory name to check.

        Returns:
            bool: True if factory is registered, False otherwise.

        Examples:
            >>> if registry.is_registered('custom_loader'):
            ...     loader = registry.load('custom_loader')
        """
        return name in self._factories

    @curry
    def register(self, name, factory):
        """Register a factory function for this interface.

        Stores a factory callable under the given name. The factory will be
        called with no arguments when load() is called.

        Args:
            name (str): Name to register the factory under.
            factory (callable): Zero-argument callable that creates instances.

        Returns:
            callable: The factory (for use as decorator).

        Raises:
            ValueError: If a factory is already registered under this name.

        Examples:
            As a decorator:
                >>> @registry.register('json')
                ... class JSONLoader:
                ...     pass

            Direct call:
                >>> registry.register('xml', lambda: XMLLoader())

        Note:
            This method is curried, so it can be used as both a decorator
            and a regular function.
        """
        if self.is_registered(name):
            raise ValueError(
                f"{self.interface.__name__} factory with name {name!r} is already registered"
            )

        self._factories[name] = factory

        return factory

    def unregister(self, name):
        """Remove a registered factory.

        Args:
            name (str): Name of the factory to remove.

        Raises:
            ValueError: If no factory is registered under this name.

        Examples:
            >>> registry.unregister('old_loader')
        """
        try:
            del self._factories[name]
        except KeyError as exc:
            raise ValueError(
                f"{self.interface.__name__} factory {name!r} was not already registered"
            ) from exc

    def clear(self):
        """Remove all registered factories.

        Examples:
            >>> registry.clear()  # Remove all factories
            >>> registry.is_registered('anything')
            False
        """
        self._factories.clear()


# Public wrapper methods for Registry:


def get_registry(interface):
    """Get the Registry instance for an extensible interface.

    Retrieves the Registry that manages factory registration for the
    specified extensible base class.

    Args:
        interface (type): The extensible base class (marked with @extensible).

    Returns:
        Registry: The registry managing factories for this interface.

    Raises:
        ValueError: If the interface has not been marked as extensible.

    Examples:
        >>> @extensible
        ... class MyInterface:
        ...     pass
        >>> registry = get_registry(MyInterface)
        >>> registry.is_registered('some_impl')
        False
    """
    try:
        return custom_types[interface]
    except KeyError as exc:
        raise ValueError("class specified is not an extendable type") from exc


def load(interface, name):
    """Load an instance of a registered factory.

    Creates and returns an instance by calling the factory function
    registered under the given name for the specified interface.

    Args:
        interface (type): The extensible base class.
        name (str): The registered factory name.

    Returns:
        An instance created by the registered factory.

    Raises:
        ValueError: If interface is not extensible or name is not registered.

    Examples:
        >>> @extensible
        ... class DataLoader:
        ...     pass
        >>>
        >>> @register(DataLoader, 'csv')
        ... class CSVLoader(DataLoader):
        ...     pass
        >>>
        >>> loader = load(DataLoader, 'csv')
        >>> isinstance(loader, CSVLoader)
        True
    """
    return get_registry(interface).load(name)


@curry
def register(interface, name, custom_class):
    """Register a factory for an extensible interface.

    Registers a factory (typically a class) that creates instances of
    custom implementations. The factory will be callable with no arguments.

    Args:
        interface (type): The extensible base class.
        name (str): Name to register the factory under.
        custom_class (callable): Factory function or class to register.
            Must be callable with no arguments.

    Returns:
        callable: The registered factory (for use as decorator).

    Raises:
        ValueError: If interface is not extensible or name already registered.

    Examples:
        As a decorator:
            >>> @register(DataLoader, 'json')
            ... class JSONLoader(DataLoader):
            ...     pass

        Direct registration:
            >>> register(DataLoader, 'xml', XMLLoader)

        With factory function:
            >>> @register(DataLoader, 'custom')
            ... def make_custom_loader():
            ...     return CustomLoader(config='special')

    Note:
        This function is curried, enabling both decorator and functional usage.
    """
    return get_registry(interface).register(name, custom_class)


def unregister(interface, name):
    """Remove a registered factory.

    Unregisters the factory with the given name from the specified interface.

    Args:
        interface (type): The extensible base class.
        name (str): Name of the factory to unregister.

    Raises:
        ValueError: If interface is not extensible or name not registered.

    Examples:
        >>> unregister(DataLoader, 'old_impl')
    """
    get_registry(interface).unregister(name)


def clear(interface):
    """Remove all registered factories for an interface.

    Clears all factory registrations for the specified extensible interface.
    Useful for testing or resetting to a clean state.

    Args:
        interface (type): The extensible base class to clear.

    Raises:
        ValueError: If interface is not extensible.

    Examples:
        >>> clear(DataLoader)  # Remove all registered loaders
    """
    get_registry(interface).clear()


def create_registry(interface):
    """Mark a class as extensible and create its registry.

    Decorator that marks a base class as extensible and creates a Registry
    to manage factory registration for that interface. Use this on abstract
    base classes that should support custom implementations.

    Args:
        interface (type): The base class to make extensible.

    Returns:
        type: The interface class (unmodified, for use as decorator).

    Raises:
        ValueError: If the interface already has a registry.

    Examples:
        >>> @create_registry
        ... class SlippageModel:
        ...     '''Base class for slippage models'''
        ...     pass

        Alternative syntax:
            >>> class CommissionModel:
            ...     pass
            >>> create_registry(CommissionModel)

        Now can register implementations:
            >>> @register(SlippageModel, 'fixed')
            ... class FixedSlippage(SlippageModel):
            ...     pass

    Note:
        The @extensible decorator is an alias for this function.
    """
    if interface in custom_types:
        raise ValueError("there is already a Registry instance for the specified type")
    custom_types[interface] = Registry(interface)
    return interface


extensible = create_registry

# A global dictionary for storing instances of Registry:
custom_types: dict[type, Registry] = {}
