"""
Element Bounds Parser for Accessibility Tree

Parses element bounds from accessibility tree XML to:
1. Validate if a click hits an interactive element
2. Find nearby elements when a click misses
3. Suggest correct coordinates for target elements
"""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

# Namespace URIs for accessibility tree attributes
STATE_NS_UBUNTU = "https://accessibility.ubuntu.example.org/ns/state"
STATE_NS_WINDOWS = "https://accessibility.windows.example.org/ns/state"
COMPONENT_NS_UBUNTU = "https://accessibility.ubuntu.example.org/ns/component"
COMPONENT_NS_WINDOWS = "https://accessibility.windows.example.org/ns/component"
VALUE_NS_UBUNTU = "https://accessibility.ubuntu.example.org/ns/value"
VALUE_NS_WINDOWS = "https://accessibility.windows.example.org/ns/value"


@dataclass
class ElementBounds:
    """Represents an interactive UI element with its bounds."""
    tag: str
    name: str
    text: str
    x: int
    y: int
    width: int
    height: int

    @property
    def center_x(self) -> int:
        return self.x + self.width // 2

    @property
    def center_y(self) -> int:
        return self.y + self.height // 2

    @property
    def center(self) -> Tuple[int, int]:
        return (self.center_x, self.center_y)

    @property
    def bounds(self) -> Tuple[int, int, int, int]:
        """Returns (x1, y1, x2, y2) bounding box."""
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def contains(self, x: int, y: int) -> bool:
        """Check if point (x, y) is inside this element."""
        return (self.x <= x <= self.x + self.width and
                self.y <= y <= self.y + self.height)

    def distance_to(self, x: int, y: int) -> float:
        """Calculate distance from point to element center."""
        return ((x - self.center_x) ** 2 + (y - self.center_y) ** 2) ** 0.5

    def distance_to_edge(self, x: int, y: int) -> float:
        """Calculate distance from point to nearest edge of element."""
        # Clamp point to element bounds
        cx = max(self.x, min(x, self.x + self.width))
        cy = max(self.y, min(y, self.y + self.height))
        return ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5

    @property
    def display_name(self) -> str:
        """Human-readable element description."""
        if self.name:
            return f'{self.tag} "{self.name}"'
        elif self.text:
            text_preview = self.text[:30] + "..." if len(self.text) > 30 else self.text
            return f'{self.tag} "{text_preview}"'
        else:
            return self.tag

    def __str__(self) -> str:
        return f"{self.display_name} at ({self.x}, {self.y}) size {self.width}x{self.height}"


class ElementBoundsParser:
    """
    Parses accessibility tree XML and extracts element bounds.
    """

    # Interactive element types to track
    INTERACTIVE_TAGS = {
        "button", "push-button", "toggle-button",
        "link", "menu-item", "menu",
        "text-field", "textfield", "textbox", "entry", "searchbox", "textarea",
        "check-box", "checkbox", "radio-button",
        "combo-box", "combobox", "list-item",
        "tab", "tabelement", "tab-item",
        "slider", "scroll-bar", "scrollbar",
        "icon", "image",
        "label", "static", "text",
        "heading", "paragraph",
        "table-cell", "tree-item",
    }

    def __init__(self, platform: str = "ubuntu"):
        self.platform = platform
        if platform == "ubuntu":
            self.state_ns = STATE_NS_UBUNTU
            self.component_ns = COMPONENT_NS_UBUNTU
        else:
            self.state_ns = STATE_NS_WINDOWS
            self.component_ns = COMPONENT_NS_WINDOWS

    def parse(self, xml_string: str) -> List[ElementBounds]:
        """
        Parse accessibility tree XML and return list of interactive elements.
        """
        if not xml_string:
            return []

        try:
            root = ET.fromstring(xml_string)
        except ET.ParseError as e:
            logger.warning(f"Failed to parse accessibility tree XML: {e}")
            return []

        elements = []
        total_nodes = 0
        for node in root.iter():
            total_nodes += 1
            element = self._parse_node(node)
            if element:
                elements.append(element)

        logger.debug(f"[ElementBounds] Parsed {total_nodes} total nodes, found {len(elements)} interactive elements")
        if elements:
            # Log first few elements for debugging
            for i, elem in enumerate(elements[:3]):
                logger.debug(f"[ElementBounds]   Sample element {i+1}: {elem.display_name} at ({elem.center_x}, {elem.center_y})")
        return elements

    def _parse_node(self, node: ET.Element) -> Optional[ElementBounds]:
        """Parse a single node into ElementBounds if it's interactive."""
        tag = node.tag.lower()

        # Check if it's an interactive element type
        is_interactive = any(
            tag.endswith(t) or tag == t
            for t in self.INTERACTIVE_TAGS
        )
        if not is_interactive:
            return None

        # Check visibility and enabled state
        showing = node.get(f"{{{self.state_ns}}}showing", "false") == "true"
        visible = node.get(f"{{{self.state_ns}}}visible", "false") == "true"
        enabled = node.get(f"{{{self.state_ns}}}enabled", "false") == "true"

        if self.platform == "ubuntu":
            if not (showing and visible):
                return None
        else:  # windows
            if not visible:
                return None

        # Get coordinates and size
        coord_str = node.get(f"{{{self.component_ns}}}screencoord", "(-1, -1)")
        size_str = node.get(f"{{{self.component_ns}}}size", "(-1, -1)")

        try:
            coords = eval(coord_str)
            size = eval(size_str)
        except:
            return None

        if coords[0] < 0 or coords[1] < 0 or size[0] <= 0 or size[1] <= 0:
            return None

        # Get name and text
        name = node.get("name", "")
        text = node.text or ""

        return ElementBounds(
            tag=tag,
            name=name,
            text=text,
            x=coords[0],
            y=coords[1],
            width=size[0],
            height=size[1]
        )

    def find_element_at(self, elements: List[ElementBounds], x: int, y: int) -> Optional[ElementBounds]:
        """Find element that contains the given point."""
        for elem in elements:
            if elem.contains(x, y):
                logger.debug(f"[ElementBounds] Point ({x}, {y}) is INSIDE element: {elem.display_name}")
                return elem
        logger.debug(f"[ElementBounds] Point ({x}, {y}) is NOT inside any of {len(elements)} elements")
        return None

    def find_nearby_elements(
        self,
        elements: List[ElementBounds],
        x: int,
        y: int,
        max_distance: int = 100,
        limit: int = 5
    ) -> List[Tuple[ElementBounds, float]]:
        """
        Find elements near the given point, sorted by distance.

        Returns list of (element, distance) tuples.
        """
        nearby = []
        for elem in elements:
            dist = elem.distance_to_edge(x, y)
            if dist <= max_distance:
                nearby.append((elem, dist))

        # Sort by distance
        nearby.sort(key=lambda x: x[1])
        result = nearby[:limit]
        if result:
            logger.debug(f"[ElementBounds] Found {len(result)} elements within {max_distance}px of ({x}, {y})")
            for elem, dist in result[:3]:
                logger.debug(f"[ElementBounds]   - {elem.display_name} at ({elem.center_x}, {elem.center_y}), {int(dist)}px away")
        else:
            logger.debug(f"[ElementBounds] No elements found within {max_distance}px of ({x}, {y})")
        return result

    def find_clickable_elements(self, elements: List[ElementBounds]) -> List[ElementBounds]:
        """Filter to only elements that are typically clickable."""
        clickable_tags = {
            "button", "push-button", "toggle-button",
            "link", "menu-item", "menu",
            "check-box", "checkbox", "radio-button",
            "combo-box", "combobox", "list-item",
            "tab", "tabelement", "tab-item",
            "icon",
        }
        return [
            elem for elem in elements
            if any(elem.tag.endswith(t) or elem.tag == t for t in clickable_tags)
        ]


def generate_coordinate_guidance(
    elements: List[ElementBounds],
    click_x: int,
    click_y: int,
    max_distance: int = 150
) -> str:
    """
    Generate guidance message when a click misses its target.

    Args:
        elements: List of parsed elements from accessibility tree
        click_x, click_y: The attempted click coordinates
        max_distance: Maximum distance to search for nearby elements

    Returns:
        Guidance message string with nearby element suggestions
    """
    parser = ElementBoundsParser()

    # Check if click hit an element
    hit_element = parser.find_element_at(elements, click_x, click_y)
    if hit_element:
        return f"Your click at ({click_x}, {click_y}) hit: {hit_element.display_name}"

    # Find nearby elements
    nearby = parser.find_nearby_elements(elements, click_x, click_y, max_distance)

    if not nearby:
        return f"No interactive elements found near ({click_x}, {click_y}). Try scrolling or navigating to find the target."

    # Generate guidance
    lines = [
        f"Your click at ({click_x}, {click_y}) missed all interactive elements.",
        "",
        "Nearby clickable elements:"
    ]

    for elem, dist in nearby[:5]:
        center = elem.center
        lines.append(
            f"  - {elem.display_name}: click at ({center[0]}, {center[1]}) "
            f"[{int(dist)}px away]"
        )

    # Suggest the closest element
    if nearby:
        closest = nearby[0][0]
        lines.append("")
        lines.append(f"SUGGESTION: Try clicking at ({closest.center_x}, {closest.center_y}) "
                     f"for \"{closest.display_name}\"")

    return "\n".join(lines)


def validate_click_coordinates(
    a11y_tree_xml: str,
    click_x: int,
    click_y: int,
    platform: str = "ubuntu"
) -> Dict[str, Any]:
    """
    Validate click coordinates against accessibility tree.

    Args:
        a11y_tree_xml: Raw XML accessibility tree string
        click_x, click_y: The attempted click coordinates
        platform: "ubuntu" or "windows"

    Returns:
        Dict with:
        - valid: bool - whether click hits an element
        - hit_element: Optional element that was hit
        - nearby_elements: List of nearby elements if missed
        - guidance: String with suggestions
    """
    parser = ElementBoundsParser(platform=platform)
    elements = parser.parse(a11y_tree_xml)

    if not elements:
        return {
            "valid": False,
            "hit_element": None,
            "nearby_elements": [],
            "guidance": "Could not parse accessibility tree. Unable to validate coordinates."
        }

    hit = parser.find_element_at(elements, click_x, click_y)

    if hit:
        return {
            "valid": True,
            "hit_element": {
                "tag": hit.tag,
                "name": hit.name,
                "center": hit.center,
                "bounds": hit.bounds
            },
            "nearby_elements": [],
            "guidance": f"Click will hit: {hit.display_name}"
        }

    nearby = parser.find_nearby_elements(elements, click_x, click_y)
    guidance = generate_coordinate_guidance(elements, click_x, click_y)

    return {
        "valid": False,
        "hit_element": None,
        "nearby_elements": [
            {
                "tag": elem.tag,
                "name": elem.name,
                "center": elem.center,
                "distance": int(dist)
            }
            for elem, dist in nearby
        ],
        "guidance": guidance
    }
