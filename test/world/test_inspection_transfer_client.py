"""Shared admin exchange contract over a frozen bounded inspection."""
import unittest

from world import inspection_transfer


class InspectionExchangeTests(unittest.TestCase):
    def test_inspect_negotiates_and_reassembles_on_one_exchange(self):
        expected = dict(ok=True, state='x' * 70000)
        conn = {}
        calls = []

        def exchange(request):
            calls.append(request)
            if request['command'] == 'inspect':
                self.assertIs(request['chunked'], True)
                return inspection_transfer.begin(conn, expected)
            return inspection_transfer.next_chunk(conn, request)

        request = dict(command='inspect')
        actual = inspection_transfer.request(request, exchange)
        self.assertEqual(actual, expected)
        self.assertEqual(request, dict(command='inspect'))
        self.assertGreater(len(calls), 1)
        self.assertTrue(all(r['command'] == 'inspect_chunk' for r in calls[1:]))
        self.assertNotIn('inspection_transfer', conn)

    def test_small_inspection_and_noninspection_preserve_responses(self):
        for command in ('inspect', 'world_recall'):
            with self.subTest(command=command):
                response = dict(ok=False, error='authority refused')
                calls = []
                def exchange(request):
                    calls.append(request)
                    return response
                self.assertIs(inspection_transfer.request(dict(command=command), exchange), response)
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0].get('chunked'), True if command == 'inspect' else None)

    def test_changed_chunk_is_rejected_not_returned_as_success(self):
        conn = {}
        def exchange(request):
            if request['command'] == 'inspect':
                return inspection_transfer.begin(conn, dict(ok=True, state='x' * 70000))
            value = inspection_transfer.next_chunk(conn, request)
            value['digest'] = '0' * 64
            return value
        with self.assertRaisesRegex(ValueError, 'changed'):
            inspection_transfer.request(dict(command='inspect'), exchange)
