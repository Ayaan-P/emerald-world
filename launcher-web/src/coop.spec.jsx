// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import CoopGuide from './CoopGuide';

afterEach(cleanup);
it('explains consent, meeting, and safe completion of co-op', () => {
  render(<CoopGuide />);
  const summary = screen.getByText('How to play together');
  expect(summary.tagName).toBe('SUMMARY');
  fireEvent.click(summary);
  expect(screen.getByText(/friend must accept/)).toBeTruthy();
  expect(screen.getByText(/both players to return to the field/)).toBeTruthy();
  expect(screen.getByText(/only accept an invitation from someone you trust/i)).toBeTruthy();
});
