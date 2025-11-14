# Minimal __init__.py to avoid loading ALL evaluators
# Original file imports ALL evaluators which have heavy dependencies
# We only need utils.compare_urls for SetupController
# This prevents loading: chrome, docs, gimp, libreoffice, vlc, etc.

# Import lightweight basic OS evaluators that are commonly needed
from .basic_os import (
    check_gnome_favorite_apps,
    is_utc_0,
    check_text_enlarged,
    check_moved_jpgs,
    is_in_vm_clickboard
)

# If you need the full evaluators, use direct imports:
# from desktop_env.evaluators.metrics.chrome import ...
