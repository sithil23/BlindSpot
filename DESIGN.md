---
version: alpha
name: BLINDSPOT
description: A calm mission-workbench for inspecting measurement evidence before performance.
colors:
  primary: '#2153a0'
  background: '#eef3f8'
  surface: '#ffffff'
  text: '#172b45'
  muted: '#52657a'
  success: '#007b81'
  warning: '#a15a00'
  border: '#ccd7e4'
typography:
  sans:
    fontFamily: 'system-ui, sans-serif'
  display:
    fontFamily: 'Trebuchet MS, system-ui, sans-serif'
  mono:
    fontFamily: 'ui-monospace, monospace'
rounded:
  DEFAULT: '0.625rem'
spacing:
  section-gap: '1.5rem'
  page-max: '76rem'
components:
  button: {}
  card: {}
  evidence-strip: {}
---

# BLINDSPOT design system

## Overview
The reference is a flight-test measurement worksheet, with soft instrument-blue surfaces,
navy typography and a continuous evidence strip. Audience: the two-person Space Apps team,
demonstration viewers, and prototype evaluators. Product register; English UI; no Japan-market
or Japanese-language requirement. Desktop local Python is primary; narrow screens remain readable.
The signature is a trace whose missing sections remain visible, directly above the interpretation.
Avoid hospital urgency, risk gauges, space wallpaper, decorative orbit graphics, and NASA branding.

## Token ownership and runtime mapping
The concrete runtime owner is `blindspot/assets/theme.css` (`--bs-*` variables).
This document mirrors that owner. `.streamlit/config.toml` adapts primary/background/surface/text
for Streamlit-native widgets. SVG charts use those same CSS variables with explicit fallback tokens
from `theme.css` read by `ui.py`. `tests/test_ui.py` checks this mapping. Change all in one change.

## Colors
Use background for the page, surface for cards, text for content, muted for captions, primary for
actions, success for usable evidence, warning for missing evidence. Every state also has text.
Light theme only; forced-colors uses system colors. No clinical severity semantics.

## Typography
Display uses a restrained Trebuchet heading, body the operating system sans, and data captions
system monospace. Body 16px, line-height 1.5; main title 34px, section title 24px. No external fonts.
Numeric values use tabular figures. Sentence case labels, uppercase only for the short wordmark.

## Layout and shapes
Natural document scrolling; max width 76rem; 1.5rem vertical rhythm; 10px rounded panels.
Columns stack on narrow screens. Tables have their own horizontal overflow. No fixed page height.
Cards use a 1px border, no shadow. No ornamental gradients, blurs or elevated glass panels.

## Components and states
Streamlit owns native buttons, inputs, alerts, tabs, expanders, radio groups and downloads.
Actions have text labels, focus outlines, hover/pressed states and disabled states. Use inline
persistent feedback rather than expiring toasts. The same result renderer serves camera and lab.
Charts have a title/description and adjacent text counts, durations, coverage and gap measures.
History is 10 records per page; previous/next are disabled at boundaries.
No destructive action, modal, password input, date picker or single-select dropdown is provided.
All controls have explicit labels. Radio groups use Streamlit's native accessible owner.

## Motion, feedback and stability
No decorative motion. Capture displays a fixed preview region and determinate elapsed progress;
setup uses a labelled spinner. Reduced-motion overrides animations/transitions. Errors preserve
completed results and show recovery instructions. Raw media is never persisted.

## Do / don't
- Show evidence before interpretation and preserve gaps.
- Separate synthetic demonstrations from real personal history.
- Do not label a prototype quality pass as medical fitness.
- Do not communicate reliability solely through color.
