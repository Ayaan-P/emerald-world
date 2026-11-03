"""Coordinator unit tests, not native battle/trade acceptance tests."""
import unittest


def presence():
    return {'z': [1, 2, 4, 5, 0, 0, 1], 'a': [1, 2, 5, 5, 0, 0, 1]}


class LinkSessionsTests(unittest.TestCase):
    def test_offer_consent_both_ready_and_stable_order(self):
        from world.link_sessions import LinkSessions
        links = LinkSessions(clock=lambda: 0)
        p = presence()
        offered = links.offer('z', 'a', 'battle_single', p)
        self.assertEqual([e.recipient for e in offered.events], ['a', 'z'])
        self.assertEqual(offered.events[0].data['participants'], ('a', 'z'))
        self.assertEqual(offered.events[0].data['proposer'], 'z')
        self.assertEqual(offered.events[0].data['target'], 'a')
        accepted = links.accept('a', offered.session_id, p)
        self.assertEqual(accepted.events[0].data['state'], 'preparing')
        self.assertEqual(links.ready('z', offered.session_id, p).events, ())
        activated = links.ready('a', offered.session_id, p)
        self.assertEqual(activated.events[0].data['state'], 'active')
        self.assertEqual(activated.events[0].data['generation'], offered.generation)

    def assert_code(self, code, call):
        from world.link_sessions import LinkError
        with self.assertRaises(LinkError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_expiration_disconnect_release_locks_and_notify_both(self):
        from world.link_sessions import LinkSessions
        links = LinkSessions(clock=lambda: 0, consent_timeout=5)
        p = presence()
        old = links.offer('z', 'a', 'trade', p)
        new = links.offer('z', 'a', 'trade', p, now=5)
        self.assertGreater(new.generation, old.generation)
        self.assertEqual([e.data['reason'] for e in new.events[:2]], ['consent_timeout'] * 2)
        self.assert_code('unknown_session', lambda: links.accept('a', old.session_id, p, now=5))
        ended = links.disconnect('z', now=5)
        self.assertEqual([e.recipient for e in ended.events], ['a', 'z'])
        self.assertEqual(ended.events[0].data['reason'], 'disconnect')
        self.assertEqual(links.disconnect('z', now=5).events, ())
        self.assertTrue(links.offer('a', 'z', 'trade', p, now=5).session_id)

    def test_timeout_on_invalid_request_is_not_lost_and_clock_is_monotonic(self):
        from world.link_sessions import LinkSessions
        links = LinkSessions(clock=lambda: 10, consent_timeout=1)
        s = links.offer('z', 'a', 'trade', presence())
        error = self.assert_code('unknown_session', lambda: links.accept('a', s.session_id, presence(), now=11))
        self.assertEqual(len(error.events), 2)
        self.assert_code('clock_regressed', lambda: links.tick(now=10))
        for bad in (True, -1, float('nan'), float('inf'), '11'):
            self.assert_code('invalid_time', lambda: links.tick(now=bad))
        self.assertEqual(links.tick(now=11).events, ())

    def test_membership_kind_presence_and_capacity(self):
        from world.link_sessions import LinkSessions
        links = LinkSessions(clock=lambda: 0)
        p = presence()
        for actor in ('', True, 1, 'a b', 'a' * 65):
            self.assert_code('invalid_actor', lambda: links.offer(actor, 'a', 'trade', p))
        self.assert_code('self_offer', lambda: links.offer('a', 'a', 'trade', p))
        for kind in ('battle', 1, True, [], 'TRADE'):
            self.assert_code('invalid_kind', lambda: links.offer('a', 'z', kind, p))
        for index, value, code in ((0, 9, 'not_adjacent'), (2, 9, 'not_adjacent'), (6, 0, 'not_ready'), (6, True, 'invalid_presence')):
            bad = presence()
            bad['z'][index] = value
            self.assert_code(code, lambda: links.offer('a', 'z', 'trade', bad))
        s = links.offer('z', 'a', 'battle_double', p)
        self.assert_code('busy', lambda: links.offer('a', 'z', 'trade', p))
        self.assert_code('not_member', lambda: links.accept('other', s.session_id, p))
        self.assert_code('not_target', lambda: links.accept('z', s.session_id, p))
        p['a'][6] = 0
        self.assert_code('not_ready', lambda: links.accept('a', s.session_id, p))
        self.assertEqual(links.reject('a', s.session_id).events[0].data['reason'], 'rejected')
        p = presence()
        for i in range(8):
            a, b = 'x' + str(i), 'y' + str(i)
            p[a], p[b] = p['a'][:], p['z'][:]
            links.offer(a, b, 'trade', p)
        self.assert_code('capacity', lambda: links.offer('a', 'z', 'trade', p))

    def active(self, **options):
        from world.link_sessions import LinkSessions
        links = LinkSessions(clock=lambda: 0, **options)
        p = presence()
        s = links.offer('z', 'a', 'trade', p)
        links.accept('a', s.session_id, p)
        links.ready('z', s.session_id, p)
        links.ready('a', s.session_id, p)
        return links, s

    def test_transport_gates_ordered_frames_and_exact_duplicates(self):
        links, s = self.active()
        a, z = tuple(range(8)), (65535,) * 8
        submit = lambda actor, step, words: links.submit(actor, s.session_id, s.generation, step, words)
        self.assertEqual(submit('z', 0, z).events, ())
        self.assertEqual(submit('z', 0, list(z)).events, ())
        self.assert_code('conflicting_duplicate', lambda: submit('z', 0, a))
        self.assert_code('invalid_step', lambda: submit('a', 1, a))
        frame = submit('a', 0, a)
        self.assertEqual(len(frame.events), 2)
        self.assertEqual(frame.events[0].data['words'], (a, z))
        self.assertEqual(frame.events[0].data['step'], 0)
        self.assertEqual(submit('a', 0, a).events, ())
        self.assert_code('conflicting_duplicate', lambda: submit('a', 0, z))
        self.assertEqual(submit('a', 1, a).events, ())
        self.assertEqual(len(submit('z', 1, z).events), 2)
        self.assert_code('invalid_step', lambda: submit('a', 0, a))
        with self.assertRaises(TypeError):
            frame.events[0].data['step'] = 9

    def test_transport_rejects_invalid_envelopes_and_impersonation(self):
        links, s = self.active()
        def submit(actor='a', generation=None, step=0, words=None):
            return links.submit(actor, s.session_id, s.generation if generation is None else generation,
                                step, [0] * 8 if words is None else words)
        self.assert_code('not_member', lambda: submit(actor='A'))
        for generation in (True, '1', -1, s.generation + 1):
            self.assert_code('invalid_generation', lambda: submit(generation=generation))
        for step in (True, 0.0, -1, 4294967296, '0'):
            self.assert_code('invalid_step', lambda: submit(step=step))
        for words in ([0]*7, [0]*9, [True]*8, [65536]*8, [-1]*8, [0.0]*8, '00000000', iter([0]*8)):
            self.assert_code('invalid_commands', lambda: submit(words=words))
        links.close('a', s.session_id)
        other = links.offer('a', 'z', 'trade', presence())
        self.assertNotEqual(s.session_id, other.session_id)
        self.assert_code('unknown_session', lambda: submit())
        self.assert_code('invalid_state', lambda: links.submit('a', other.session_id, other.generation, 0, [0]*8))

    def test_active_timeout_cannot_be_kept_alive_by_duplicate_or_one_peer(self):
        links, s = self.active(step_timeout=3)
        links.submit('a', s.session_id, s.generation, 0, [0]*8, now=1)
        links.submit('a', s.session_id, s.generation, 0, [0]*8, now=2)
        expired = links.tick(now=3)
        self.assertEqual([e.data['reason'] for e in expired.events], ['step_timeout'] * 2)
        self.assertTrue(links.offer('a', 'z', 'trade', presence(), now=3).session_id)

    def test_step_limit_closes_without_wraparound(self):
        links, s = self.active(max_steps=1)
        links.submit('a', s.session_id, s.generation, 0, [0]*8)
        result = links.submit('z', s.session_id, s.generation, 0, [0]*8)
        self.assertEqual([e.data['type'] for e in result.events], ['frame', 'frame', 'closed', 'closed'])
        self.assertEqual(result.events[-1].data['reason'], 'step_limit')
        self.assert_code('unknown_session', lambda: links.submit('a', s.session_id, s.generation, 1, [0]*8))

    def test_readiness_cannot_be_forged_or_extended_and_live_presence_is_rechecked(self):
        from world.link_sessions import LinkSessions
        links = LinkSessions(clock=lambda: 0, consent_timeout=2)
        p = presence()
        s = links.offer('z', 'a', 'trade', p)
        self.assert_code('invalid_state', lambda: links.ready('a', s.session_id, p))
        self.assert_code('not_target', lambda: links.reject('z', s.session_id))
        links.accept('a', s.session_id, p)
        for operation in (links.ready,):
            self.assert_code('not_member', lambda: operation('outsider', s.session_id, p))
        self.assert_code('not_member', lambda: links.close('outsider', s.session_id))
        p['a'][2] += 1
        self.assert_code('not_adjacent', lambda: links.ready('a', s.session_id, p))
        p = presence()
        links.ready('a', s.session_id, p, now=1)
        links.ready('a', s.session_id, p, now=1.9)
        self.assertEqual(len(links.tick(now=2).events), 2)

    def test_long_stream_and_input_copies_have_no_replay_or_queue(self):
        links, s = self.active()
        words = [0] * 8
        links.submit('z', s.session_id, s.generation, 0, words)
        words[0] = 99
        frame = links.submit('a', s.session_id, s.generation, 0, [1] * 8)
        self.assertEqual(frame.events[0].data['words'][1], (0,) * 8)
        for step in range(1, 1001):
            self.assertEqual(links.submit('a', s.session_id, s.generation, step, [step] * 8).events, ())
            result = links.submit('z', s.session_id, s.generation, step, [step] * 8)
            self.assertEqual(len(result.events), 2)
            self.assertEqual(result.events[0].data['step'], step)
        self.assertEqual(len(links.close('z', s.session_id).events), 2)
        self.assertEqual(links.tick().events, ())

    def test_restart_namespace_and_mixed_presence_sequence_types(self):
        from world.link_sessions import LinkSessions
        p = presence()
        p['z'] = tuple(p['z'])
        a = LinkSessions(clock=lambda: 0).offer('a', 'z', 'trade', p)
        b = LinkSessions(clock=lambda: 0).offer('a', 'z', 'trade', p)
        self.assertNotEqual(a.session_id, b.session_id)

    def test_constructor_and_huge_numeric_inputs_are_explicit_errors(self):
        from world.link_sessions import LinkSessions, LinkError
        for bad in (True, 0, -1, 61, float('nan'), float('inf'), '5', 10**1000):
            with self.assertRaises(LinkError):
                LinkSessions(consent_timeout=bad)
            with self.assertRaises(LinkError):
                LinkSessions(step_timeout=bad)
        for bad in (True, 0, -1, 4294967297, 1.5):
            with self.assertRaises(LinkError):
                LinkSessions(max_steps=bad)
        links = LinkSessions(clock=lambda: 0)
        self.assert_code('invalid_time', lambda: links.tick(now=10**1000))

    def test_native_pair_can_clock_zero_rounds_before_host_advance(self):
        from world.link_sessions import LinkSessions
        links = LinkSessions(clock=lambda: 0)
        s = links.offer('a', 'z', 'battle_single', presence())
        links.accept('z', s.session_id, presence())
        links.open('a', s.session_id, 1, 0x2233)
        links.open('z', s.session_id, 1, 0x2233)
        for actor in ('a', 'z'):
            result = links.submit(actor, s.session_id, s.generation, 0, [0]*8, link_generation=1)
        self.assertEqual(result.events[0].data['step'], 0)
        self.assert_code('invalid_state', lambda: links.submit(
            'a', s.session_id, s.generation, 1, [1]*8, link_generation=1))
        self.assertEqual(links.advance('a', s.session_id, 1).events[0].data['type'], 'handshake')
        links.submit('a', s.session_id, s.generation, 1, [1]*8, link_generation=1)
        result = links.submit('z', s.session_id, s.generation, 1, [2]*8, link_generation=1)
        self.assertEqual(result.events[0].data['words'], ((1,)*8, (2,)*8))

    def test_native_open_handshake_reopen_preserves_consent_and_resets_round(self):
        from world.link_sessions import LinkSessions
        links = LinkSessions(clock=lambda: 0)
        s = links.offer('z', 'a', 'battle_single', presence())
        self.assert_code('invalid_state', lambda: links.open('a', s.session_id, 1, 0x2233))
        links.accept('a', s.session_id, presence())
        self.assertEqual(links.open('z', s.session_id, 1, 0x2233).events, ())
        self.assert_code('invalid_state', lambda: links.advance('a', s.session_id, 1))
        self.assert_code('link_type_mismatch', lambda: links.open('a', s.session_id, 1, 0x2244))
        pair = links.open('a', s.session_id, 1, 0x2233)
        self.assertEqual(pair.events[0].data['type'], 'pair')
        self.assertEqual(pair.events[0].data['words'], ((0,)*8, (0,)*8))
        self.assertEqual(links.open('a', s.session_id, 1, 0x2233).events, ())
        self.assert_code('not_host', lambda: links.advance('z', s.session_id, 1))
        def submit(actor, step, gen):
            return links.submit(actor, s.session_id, s.generation, step, [0]*8, link_generation=gen)
        self.assert_code('invalid_state', lambda: links.submit(
            'a', s.session_id, s.generation, 0, [1]*8, link_generation=1))
        self.assertEqual(links.advance('a', s.session_id, 1).events[0].data['type'], 'handshake')
        self.assertEqual(links.advance('a', s.session_id, 1).events, ())
        self.assert_code('invalid_link_generation', lambda: submit('a', 0, None))
        submit('a', 0, 1)
        self.assertEqual(submit('z', 0, 1).events[0].data['link_generation'], 1)
        closed = links.close_generation('z', s.session_id, 1)
        self.assertEqual(closed.events[0].data['type'], 'generation_closed')
        self.assert_code('busy', lambda: links.offer('a', 'z', 'trade', presence()))
        self.assertEqual(links.close_generation('a', s.session_id, 1).events, ())
        self.assert_code('invalid_link_generation', lambda: links.open('a', s.session_id, 1, 0x2233))
        links.open('a', s.session_id, 2, 0x2233)
        links.open('z', s.session_id, 2, 0x2233)
        self.assert_code('invalid_link_generation', lambda: links.advance('a', s.session_id, 1))
        links.advance('a', s.session_id, 2)
        self.assert_code('invalid_link_generation', lambda: submit('z', 0, 1))
        self.assertEqual(submit('z', 0, 2).events, ())
        self.assertEqual(submit('a', 0, 2).events[0].data['step'], 0)
        self.assertEqual(len(links.disconnect('a').events), 2)

    def test_native_generation_identity_validation_and_cross_session_advance(self):
        links, s = self.active()
        for gen in (True, 0, -1, 4294967296, '1'):
            self.assert_code('invalid_link_generation', lambda: links.open('a', s.session_id, gen, 1))
        for kind in (True, -1, 65536, '1'):
            self.assert_code('invalid_link_type', lambda: links.open('a', s.session_id, 1, kind))
        self.assert_code('not_member', lambda: links.open('outsider', s.session_id, 1, 1))
        self.assert_code('not_member', lambda: links.advance('outsider', s.session_id, 1))
        self.assert_code('not_member', lambda: links.close_generation('outsider', s.session_id, 1))
        links.open('a', s.session_id, 1, 1)
        self.assert_code('invalid_link_generation', lambda: links.open('z', s.session_id, 2, 1))
        self.assert_code('invalid_state', lambda: links.ready('z', s.session_id, presence()))

    def test_native_open_timeout_and_cross_session_advance(self):
        from world.link_sessions import LinkSessions
        links = LinkSessions(clock=lambda: 0, step_timeout=2)
        p = presence()
        p['c'], p['d'] = p['a'][:], p['z'][:]
        first = links.offer('a', 'z', 'trade', p)
        links.accept('z', first.session_id, p)
        other = links.offer('c', 'd', 'trade', p)
        links.accept('d', other.session_id, p)
        self.assert_code('not_member', lambda: links.advance('a', other.session_id, 1))
        p['a'][6] = p['z'][6] = 0
        links.open('a', first.session_id, 1, 1)
        links.open('a', first.session_id, 1, 1, now=1)
        timed_out = links.tick(now=2)
        self.assertEqual([e.data['reason'] for e in timed_out.events], ['step_timeout'] * 2)
        self.assertEqual(len(links.close('c', other.session_id, now=2).events), 2)


if __name__ == '__main__':
    unittest.main()
