# Store the *version* that is currently in use
CURRENT_LOADED_VERSION = None
# Store the *module* that is currently in use
fdb = None

__VERSION__ = (0, 2, 1)
VERSION = "v" + ".".join([str(x) for x in __VERSION__])
