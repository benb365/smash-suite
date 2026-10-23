import assert from 'node:assert/strict';
import test from 'node:test';
import { defaultOptimizations, resolveOptimizations } from './optimizations.ts';

test('scene defaults enable three shared options and enable dynamic scan only for high view', () => {
  assert.deepEqual(defaultOptimizations('high'), {
    limit_fps: true, small_input: true, grayscale: true, dynamic_scan: true,
  });
  assert.deepEqual(defaultOptimizations('courtside'), {
    limit_fps: true, small_input: true, grayscale: true, dynamic_scan: false,
  });
  assert.deepEqual(defaultOptimizations('personal'), defaultOptimizations('courtside'));
});

test('resolving legacy or partial choices leaves stored data untouched', () => {
  const saved = { limit_fps: false };
  assert.deepEqual(resolveOptimizations('personal', saved), {
    limit_fps: false, small_input: true, grayscale: true, dynamic_scan: false,
  });
  assert.deepEqual(saved, { limit_fps: false });
});

test('camera choices are stored independently', () => {
  const storedByCamera = { high: { ...defaultOptimizations('high'), dynamic_scan: false } };
  assert.equal(resolveOptimizations('high', storedByCamera.high).dynamic_scan, false);
  assert.equal(resolveOptimizations('personal', storedByCamera.personal).dynamic_scan, false);
});

test('explicit false overrides every enabled default', () => {
  assert.deepEqual(resolveOptimizations('high', {
    limit_fps: false, small_input: false, grayscale: false, dynamic_scan: false,
  }), { limit_fps: false, small_input: false, grayscale: false, dynamic_scan: false });
});

test('stored scene choices override defaults while missing scenes use their own defaults', () => {
  const storedByCamera = { high: { ...defaultOptimizations('high'), dynamic_scan: false } };
  assert.deepEqual(resolveOptimizations('high', storedByCamera.high), {
    limit_fps: true, small_input: true, grayscale: true, dynamic_scan: false,
  });
  assert.deepEqual(resolveOptimizations('personal', storedByCamera.personal), defaultOptimizations('personal'));
});
