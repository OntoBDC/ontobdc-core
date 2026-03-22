---
id: SPEC007
title: Terminal Wireframe Canvas and Overlay Rendering
status: Draft
---

# 1. Scope

This specification defines a terminal rendering subsystem focused on wireframe-style drawings and ANSI/Unicode art for OntoBDC CLI usage. The goal is deterministic, layered rendering with full control over glyph choice, allowing the system to “draw from data” (e.g., floor plans or simplified views) using composable drawing objects.

The MVP defined here is:

- A set of Drawing Objects (wireframe primitives) rendered line-by-line
- A Canvas compositor that overlays objects using space-transparent composition
- A glyph palette that improves visual smoothness (box drawing, diagonals, arrows)

This spec intentionally avoids interactive UI features (mouse, scrolling, widgets). Input handling, full-screen mode, and animation loops are out of scope for the MVP.

# 2. Definitions

- **Canvas**: an object responsible for composing multiple Drawing Objects into a final list of text lines.
- **Drawing Object**: any object that can produce its visual representation line-by-line (`get_line(n)`) and can be composed above a lower layer (`insert_above`).
- **Wireframe**: drawings composed of lines, corners, joints and arrows (e.g., rectangles + connectors).
- **Overlay**: composition where a character from the upper layer replaces the lower layer at the same position, unless that character is considered transparent (space).
- **Glyph**: a single character used for rendering (ASCII, Unicode box drawing, block elements, etc.).

# 3. Requirements

## 3.1 Functional Requirements

- The renderer must support N drawing objects layered in a deterministic order.
- Rendering must be deterministic for a given set of drawing objects and positions.
- Overlay must be “space-transparent” by default:
  - If the upper glyph is `" "` it does not replace the lower layer at that position.
  - Any non-space glyph replaces the lower layer.
- Each drawing object must support offsets:
  - Horizontal offset (`x_pos`) expressed as left margin spaces.
  - Vertical offset (`y_pos`) expressed as empty lines before content.

## 3.2 Non-Functional Requirements

- The system must work without internet or external services.
- The output must be stable across runs in the same terminal/font configuration.
- The system must be usable with plain `print()` (no full-screen requirement).

# 4. Rendering Model

## 4.1 Coordinate System

- Rendering is line-based.
- `line_number` is 1-based.
- `x_pos` is 0-based and is implemented via left margin spaces.
- `y_pos` is 0-based and is implemented by returning empty strings for lines before the object starts.

## 4.2 Canvas Construction

The Canvas computes:

- `width`: maximum `length` among drawing objects
- `height`: maximum `height` among drawing objects

Then it builds the final output from `line_number=1..height` by iterating drawing objects in insertion order and composing each object above the current line.

## 4.3 Overlay Composition

Overlay is defined by the algorithm:

1. Generate the upper layer for the current line.
2. If the lower layer is empty, return the upper layer.
3. For each position `pos`:
   - If `upper_layer[pos] != " "` then set `lower_layer[pos] = upper_layer[pos]`
4. Return the resulting line.

This provides layer composition with “transparent background” semantics and is the baseline approach for the MVP.

# 5. Wireframe Primitives

## 5.1 Rectangle

A Rectangle is defined by:

- `width`, `height`
- `x_pos`, `y_pos`

It must be able to render a top border, middle area, and bottom border.

## 5.2 Arrow (Connector)

An Arrow is a connector intended to join shapes. The MVP supports a diagonal arrow head rendered through a sequence of diagonal glyphs, with configurable height and offsets.

Rotation is out of scope for MVP unless explicitly implemented.

# 6. Glyph Palette

This section defines recommended glyphs to improve visual smoothness and make drawings look more “CAD-like” compared to ASCII `_`, `|`, `/`, and `\\`.

## 6.1 Box Drawing (Recommended)

Use Unicode box drawing:

- Horizontal: `─` (light), `━` (heavy)
- Vertical: `│` (light), `┃` (heavy)
- Corners: `┌ ┐ └ ┘` (light), `┏ ┓ ┗ ┛` (heavy)
- Joints: `├ ┤ ┬ ┴ ┼` (light), `┣ ┫ ┳ ┻ ╋` (heavy)

These glyphs produce the smoothest wireframes for rectangles and orthogonal lines.

## 6.2 Diagonals

Recommended diagonal glyphs:

- `╱` and `╲` instead of `/` and `\\`

They tend to appear cleaner and more uniform in many monospace fonts.

## 6.3 Block Elements (Optional, Higher Apparent Resolution)

For “ANSI art” or pseudo anti-aliasing:

- Half blocks: `▀` (upper), `▄` (lower)
- Full block: `█`
- Partial blocks: `▏▎▍▌▋▊▉`

These can simulate higher resolution by controlling foreground/background colors per cell.

## 6.4 Arrowheads and “More Open Than >”

If `>` looks too tight, consider:

- `›` (single right-pointing angle quotation mark)
- `»` (double right-pointing angle quotation mark)
- `❯` (heavy right-pointing angle quotation mark ornament)
- `➜` (heavy arrow, commonly used as prompt pointer)
- `→` (right arrow)
- `▸` / `▶` (triangle pointer)

For wireframes, `→` is the most neutral; for “prompt pointer” style, `➜` and `❯` are common.

# 7. Optional Enhancement: Junction Merging

The baseline overlay simply overwrites characters. For more realistic wireframes, an optional enhancement is to merge intersections:

- Example: overlaying `│` on `─` should yield `┼` rather than replacing one with the other.
- Similar merges exist for corners and T-junctions (`├ ┤ ┬ ┴`).

This is not required for MVP but is recommended if wireframes are used for floor plan-like visuals.

# 8. Example Output

Example conceptual composition:

- Rectangle frame using box drawing glyphs
- Arrow connector drawn above the rectangle and composed via space-transparent overlay

The output should be stable and should preserve lower-layer content wherever the upper-layer is a space.

# 9. Compatibility Notes

- Glyph appearance depends on terminal font and Unicode support.
- Some terminals may render heavy box characters slightly wider; choose one set consistently.
- If Unicode support is limited, fall back to ASCII:
  - `-`, `|`, `+`, `/`, `\\`, `>`, `<`

