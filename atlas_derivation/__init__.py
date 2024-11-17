try:
    import rucio
except (ImportError, ModuleNotFoundError):
    print("rucio is not installed, please run `lsetup rucio` or install it manually")
   
from .core.methods import *

clients = init_clients()