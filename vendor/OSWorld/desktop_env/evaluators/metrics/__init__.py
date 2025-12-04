# Comprehensive metrics __init__.py
# Imports all evaluator functions needed for OSWorld task evaluation
# Uses graceful imports to handle missing dependencies

import logging
import importlib
logger = logging.getLogger(__name__)

def _safe_import(module_name, names):
    """Safely import names from a module, returning a dict of successful imports."""
    result = {}
    try:
        module = importlib.import_module(f".{module_name}", package=__name__)
        for name in names:
            if hasattr(module, name):
                result[name] = getattr(module, name)
            else:
                logger.debug(f"Function {name} not found in {module_name}")
    except ImportError as e:
        logger.warning(f"Could not import from {module_name}: {e}")
    except Exception as e:
        logger.warning(f"Error importing from {module_name}: {e}")
    return result

# Import each module and add to globals
_imports = {}

# Basic OS evaluators (lightweight, always available)
_imports.update(_safe_import("basic_os", [
    "check_gnome_favorite_apps",
    "is_utc_0",
    "check_text_enlarged",
    "check_moved_jpgs",
    "is_in_vm_clickboard",
]))

# Chrome evaluators
_imports.update(_safe_import("chrome", [
    "is_expected_active_tab",
    "is_expected_active_tab_approximate",
    "is_expected_url_pattern_match",
    "is_expected_tabs",
    "is_expected_bookmarks",
    "compare_pdfs",
    "is_cookie_deleted",
    "is_expected_search_query",
    "is_expected_installed_extensions",
    "check_history_deleted",
    "check_enabled_experiments",
    "compare_archive",
]))

# General evaluators (commonly used)
_imports.update(_safe_import("general", [
    "exact_match",
    "fuzzy_match",
    "check_include_exclude",
    "check_direct_json_object",
    "check_json",
    "check_list",
    "check_csv",
    "check_accessibility_tree",
    "run_sqlite3",
    "literal_match",
    "match_in_list",
    "is_in_list",
    "diff_text_file",
    "compare_python_pure_text",
    "file_contains",
    "fuzzy_place_math",
    "compare_time_in_speedtest_results",
]))

# Table evaluators (most commonly used - 71 tasks)
_imports.update(_safe_import("table", [
    "compare_table",
]))

# Slides/PowerPoint evaluators
_imports.update(_safe_import("slides", [
    "compare_pptx_files",
    "check_presenter_console_disable",
    "check_image_stretch_and_center",
    "check_slide_orientation_Portrait",
    "evaluate_presentation_fill_to_rgb_distance",
    "check_left_panel",
    "check_transition",
    "check_page_number_colors",
    "check_auto_saving_time",
]))

# Document evaluators
_imports.update(_safe_import("docs", [
    "compare_docx_files",
    "compare_docx_tables",
    "compare_docx_images",
    "compare_line_spacing",
    "compare_font_names",
    "compare_references",
    "compare_docx_files_and_ignore_new_lines",
    "compare_docx_lines",
    "compare_unique_train_records",
    "has_page_numbers_in_footers",
    "is_first_line_centered",
    "contains_page_break",
    "find_default_font",
    "check_tabstops",
    "evaluate_colored_words_in_tables",
    "check_highlighted_words",
    "evaluate_strike_through_last_paragraph",
    "check_italic_font_size_14",
]))

# VSCode evaluators
_imports.update(_safe_import("vscode", [
    "check_json_settings",
    "compare_text_file",
    "compare_config",
    "check_json_keybindings",
    "is_extension_installed",
]))

# VLC evaluators
_imports.update(_safe_import("vlc", [
    "is_vlc_playing",
    "is_vlc_recordings_folder",
    "is_vlc_fullscreen",
    "compare_images",
    "compare_audios",
    "compare_videos",
    "check_qt_bgcone",
    "check_qt_max_volume",
    "check_qt_minimal_view",
    "check_qt_slider_colours",
    "check_global_key_play_pause",
    "check_one_instance_when_started_from_file",
]))

# GIMP evaluators
_imports.update(_safe_import("gimp", [
    "compare_image_list",
    "check_brightness_decrease_and_structure_sim",
    "check_saturation_increase_and_structure_sim",
    "check_file_exists_and_structure_sim",
    "check_triangle_position",
    "check_structure_sim",
    "check_contrast_increase_and_structure_sim",
    "check_config_status",
    "check_palette_and_structure_sim",
    "check_textbox_on_leftside",
    "check_image_mirror",
    "check_green_background",
    "check_image_file_size",
]))

# Thunderbird evaluators
_imports.update(_safe_import("thunderbird", [
    "check_thunderbird_prefs",
    "check_thunderbird_filter",
    "check_thunderbird_folder",
]))

# PDF evaluators
_imports.update(_safe_import("pdf", [
    "check_pdf_pages",
]))

# Other evaluators
_imports.update(_safe_import("others", [
    "compare_epub",
    "check_mp3_meta",
]))

# LibreOffice evaluators
_imports.update(_safe_import("libreoffice", [
    "is_shortcut_on_desktop",
]))

# Utility functions
_imports.update(_safe_import("utils", [
    "compare_urls",
    "are_lists_equal",
]))

# Add all imports to module globals
globals().update(_imports)

# Clean up
del _imports
