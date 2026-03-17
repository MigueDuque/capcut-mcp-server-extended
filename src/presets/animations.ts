// Animation library for CapCut MCP Server.
// Animations are defined as sequences of relative keyframe steps.
// Use resolveKeyframes() to convert them into API-ready keyframe calls.

import { z } from 'zod';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface KeyframeStep {
  frame_offset: number;
  opacity?: number;
  // Offsets are relative to the final (resting) position of the element.
  // Units must match whatever coordinate system the keyframe API expects.
  position_y_offset?: number;
  position_x_offset?: number;
  scale?: number;
  rotation?: number;
}

export interface AnimationDefinition {
  name: string;
  description: string;
  frame_rate: number;
  keyframes: KeyframeStep[];
}

// Represents a single call to apiClient.addKeyframe for one property track.
export interface ResolvedKeyframeCall {
  property_type: string;
  times: number[];
  values: string[];
}

// ---------------------------------------------------------------------------
// Animation definitions
// ---------------------------------------------------------------------------

const popInUpper: AnimationDefinition = {
  name: 'popInUpper',
  description: 'Falls from slightly above its final position with fade in',
  frame_rate: 30,
  keyframes: [
    // Negative y_offset = below final position in CapCut keyframe space.
    // Element starts 0.15 units below its resting Y and slides UP into place.
    { frame_offset: 0, opacity: 0, position_y_offset: 0.15 },
    { frame_offset: 5, opacity: 1, position_y_offset: 0 },
  ],
};

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

export const ANIMATIONS: Record<string, AnimationDefinition> = {
  popInUpper,
};

export const AnimationNameSchema = z.enum(['popInUpper']);

export type AnimationName = z.infer<typeof AnimationNameSchema>;
export const ANIMATION_NAMES = AnimationNameSchema.options;

// ---------------------------------------------------------------------------
// Lookup helper
// ---------------------------------------------------------------------------

export function getAnimation(name: AnimationName): AnimationDefinition {
  return ANIMATIONS[name];
}

// ---------------------------------------------------------------------------
// resolveKeyframes
//
// Converts an AnimationDefinition into a list of ResolvedKeyframeCall objects
// ready to be sent to apiClient.addKeyframe.
//
// - frame_offset values are converted to seconds using `fps` (falls back to
//   animation.frame_rate if not provided).
// - position_*_offset values are added to finalPosition to produce absolute
//   positions. Units must be consistent with what the keyframe API expects.
// ---------------------------------------------------------------------------

export function resolveKeyframes(
  animation: AnimationDefinition,
  finalPosition: { x: number; y: number },
  fps?: number
): ResolvedKeyframeCall[] {
  const frameRate = fps ?? animation.frame_rate;

  // Accumulate per-property (times[], values[]) pairs.
  const props: Record<string, { times: number[]; values: string[] }> = {};

  function track(key: string): { times: number[]; values: string[] } {
    if (!props[key]) props[key] = { times: [], values: [] };
    return props[key];
  }

  for (const kf of animation.keyframes) {
    const time = kf.frame_offset / frameRate;

    if (kf.opacity !== undefined) {
      const t = track('alpha');
      t.times.push(time);
      t.values.push(String(kf.opacity));
    }

    if (kf.position_y_offset !== undefined) {
      const t = track('position_y');
      t.times.push(time);
      t.values.push(String(finalPosition.y + kf.position_y_offset));
    }

    if (kf.position_x_offset !== undefined) {
      const t = track('position_x');
      t.times.push(time);
      t.values.push(String(finalPosition.x + kf.position_x_offset));
    }

    if (kf.scale !== undefined) {
      const tx = track('scale_x');
      tx.times.push(time);
      tx.values.push(String(kf.scale));

      const ty = track('scale_y');
      ty.times.push(time);
      ty.values.push(String(kf.scale));
    }

    if (kf.rotation !== undefined) {
      const t = track('rotation');
      t.times.push(time);
      t.values.push(String(kf.rotation));
    }
  }

  return Object.entries(props).map(([property_type, data]) => ({
    property_type,
    times: data.times,
    values: data.values,
  }));
}