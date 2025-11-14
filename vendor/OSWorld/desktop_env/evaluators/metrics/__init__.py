# Minimal __init__.py to avoid loading ALL evaluators
# Original file imports ALL evaluators which have heavy dependencies
# We only need utils.compare_urls for SetupController
# This prevents loading: chrome, docs, gimp, libreoffice, vlc, etc.

# If you need the full evaluators, use direct imports:
# from desktop_env.evaluators.metrics.chrome import ...
