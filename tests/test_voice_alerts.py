import unittest
from blindspot.voice_alerts import speech_messages, voice_widget_html


class VoiceAlertTests(unittest.TestCase):
    def test_only_actionable_flags_spoken_and_deduplicated(self):
        flags = [
            {'kind': 'context', 'message': 'exercise'},
            {'kind': 'feed', 'message': 'CREW-03 sensor feed unavailable'},
            {'kind': 'feed', 'message': 'CREW-03 sensor feed unavailable'},
            {'kind': 'evidence', 'message': 'CREW-02 oxygen missing'},
            {'kind': 'trend', 'message': 'Habitat B carbon dioxide rising'},
        ]
        self.assertEqual(speech_messages(flags), [
            'Sensor feed unavailable: CREW-03 sensor feed unavailable',
            'Check sensor data: CREW-02 oxygen missing',
            'Cabin trend alert: Habitat B carbon dioxide rising',
        ])

    def test_widget_does_not_autospeak_without_opt_in(self):
        html = voice_widget_html([{'kind': 'feed', 'message': 'Feed gone'}])
        self.assertIn('speechSynthesis', html)
        self.assertIn('Enable spoken alerts', html)
        self.assertIn('speechEnabled', html)
        self.assertIn('localStorage', html)
        self.assertNotIn('eval(', html)

    def test_script_injection_is_escaped(self):
        html = voice_widget_html([{'kind': 'feed', 'message': '</script><script>alert(1)</script>'}])
        self.assertNotIn('</script><script>alert(1)</script>', html)

if __name__ == '__main__':
    unittest.main()

def test_total_sensor_outage_creates_critical_monitoring_flag():
    from blindspot.dashboard import dashboard_flags
    flags = dashboard_flags({'CREW-01': None, 'CREW-02': None, 'CREW-03': None},
                            {'Habitat A': None, 'Habitat B': None})
    assert any(flag['kind'] == 'critical' for flag in flags)
