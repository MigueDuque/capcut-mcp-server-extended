// Typography style system for CapCut MCP Server.
// Each style defines appearance (font, color, stroke, shadow) independently of
// position and timing — those are supplied at the call site.

import { z } from 'zod';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface StrokeStyle {
  enabled: boolean;
  color: string;
  thickness: number;
}

export interface ShadowStyle {
  enabled: boolean;
  color: string;
  opacity: number;
  blur: number;
  distance: number;
  angle: number;
}

export interface TypographyStyle {
  font: string;
  font_size: number;
  color: string;
  stroke: StrokeStyle;
  shadow: ShadowStyle;
}

// ---------------------------------------------------------------------------
// Style definitions
// ---------------------------------------------------------------------------

const defaultTypeWhite: TypographyStyle = {
  font: 'Poppins_Bold',
  font_size: 15,
  color: '#ecebeb',
  stroke: { enabled: true, color: '#000000', thickness: 40 },
  shadow: { enabled: true, color: '#000000', opacity: 0.25, blur: 23, distance: 10, angle: -70 },
};

const defaultTypeBlack: TypographyStyle = {
  font: 'Poppins_Bold',
  font_size: 15,
  color: '#000000',
  stroke: { enabled: false, color: '#000000', thickness: 0 },
  shadow: { enabled: false, color: '#000000', opacity: 0, blur: 0, distance: 0, angle: 0 },
};

const defaultTypeRed: TypographyStyle = {
  font: 'Poppins_Bold',
  font_size: 15,
  color: '#aa1a1a',
  stroke: { enabled: false, color: '#000000', thickness: 0 },
  shadow: { enabled: false, color: '#000000', opacity: 0, blur: 0, distance: 0, angle: 0 },
};

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

export const TYPOGRAPHY_STYLES: Record<string, TypographyStyle> = {
  defaultTypeWhite,
  defaultTypeBlack,
  defaultTypeRed,
};

export const TYPOGRAPHY_STYLE_NAMES = [
  'defaultTypeWhite',
  'defaultTypeBlack',
  'defaultTypeRed',
] as const;

export type TypographyStyleName = typeof TYPOGRAPHY_STYLE_NAMES[number];

export const TypographyStyleNameSchema = z.enum(
  [...TYPOGRAPHY_STYLE_NAMES] as [TypographyStyleName, ...TypographyStyleName[]]
);

// ---------------------------------------------------------------------------
// Lookup helper
// ---------------------------------------------------------------------------

export function getTypographyStyle(name: TypographyStyleName): TypographyStyle {
  return TYPOGRAPHY_STYLES[name];
2}