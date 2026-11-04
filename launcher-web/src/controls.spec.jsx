// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import ControlsHelp from './ControlsHelp';

afterEach(cleanup);
it('offers default controls without claiming remaps are detected', () => {
  render(<ControlsHelp />);
  const disclosure = screen.getByText('Game controls');
  expect(disclosure.tagName).toBe('SUMMARY');
  fireEvent.click(disclosure);
  expect(screen.getByText('A / confirm')).toBeTruthy();
  expect(screen.getByText('Z')).toBeTruthy();
  expect(screen.getByText(/remapped keys may be different/i)).toBeTruthy();
  expect(screen.getByText(/F11 toggles/)).toBeTruthy();
});
