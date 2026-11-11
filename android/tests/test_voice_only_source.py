"""Source-contract audit, not JVM, acoustic or device validation. No external services."""
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ANDROID = Path(__file__).resolve().parents[1]
SOURCE = ANDROID / "app/src/main/java/com/serexe/sarah"
NAME = "{http://schemas.android.com/apk/res/android}name"


def read(name):
    return (SOURCE / name).read_text()


class VoiceOnlySourceTest(unittest.TestCase):
    def test_manifest_has_only_voice_permissions_and_services(self):
        manifest = ET.parse(ANDROID / "app/src/main/AndroidManifest.xml").getroot()
        self.assertEqual(
            {node.attrib[NAME].removeprefix("android.permission.") for node in manifest.findall("uses-permission")},
            {"INTERNET", "RECORD_AUDIO", "FOREGROUND_SERVICE", "FOREGROUND_SERVICE_MICROPHONE",
             "WAKE_LOCK", "VIBRATE", "POST_NOTIFICATIONS"},
        )
        app = manifest.find("application")
        self.assertEqual([], app.findall("receiver"))
        self.assertEqual(
            {node.attrib[NAME] for node in app.findall("service")},
            {".HeySarahListenerService", ".SarahVoiceInteractionService", ".SarahSessionService", ".SarahRecognitionService"},
        )
        for attribute in ("usesCleartextTraffic", "allowBackup", "fullBackupContent"):
            self.assertEqual("false", app.attrib[NAME.removesuffix("name") + attribute])

    def test_device_action_code_and_model_backends_are_absent(self):
        forbidden = r"\b(PhoneActionRouter|PhoneMedia|PhoneMediaService|LocalSchedule|LocalAlertService|AndroidSchedule|ScheduleEntry|TimerCountdown|AlarmManager|MediaStore|MediaSession|PhoneScheduleCommand|ProcessBuilder)\b|direct_timer|/confirmation|phone-receipt"
        for path in SOURCE.glob("*.kt"):
            with self.subTest(path=path.name):
                self.assertNotRegex(path.read_text(), forbidden)
        ports = read("Ports.kt")
        self.assertNotRegex(ports, r"fun\s+(confirm|phoneReceipt)")
        self.assertNotRegex(read("SarahViewModel.kt"), r"fun\s+(confirm|handlePhoneAction)")
        for name in ("LocalScheduleTest.kt", "PhoneScheduleCommandTest.kt", "PhoneMediaTest.kt", "TimerCountdownTest.kt"):
            self.assertFalse((ANDROID / "app/src/test/java/com/serexe/sarah" / name).exists())

    def test_transport_exposes_only_generic_voice_routes(self):
        routes = set(re.findall(r'"(/v1/[^"\n]*)"', read("Bridge.kt")))
        self.assertEqual(
            {"/v1/", "/v1/health", "/v1/diagnostics", "/v1/conversations", "/v1/turns",
             "/v1/requests/$request", "/v1/turns/$turn", "/v1/turns/$turn/audio",
             "/v1/turns/$turn/audio/$seq", "/v1/turns/$turn/cancel"}, routes,
        )
        self.assertNotIn('X-Clarification-Parent', read("Bridge.kt"))
        for marker in ('followRedirects(false)', 'followSslRedirects(false)',
                       'retryOnConnectionFailure(false)', 'override fun isOneShot()=true',
                       'cert.checkValidity()', 'X-Audio-Chunks', 'sentence-mp3-v1',
                       'Idempotency-Key', 'Authorization', 'X-Conversation'):
            self.assertIn(marker, read("Bridge.kt"))

    def test_all_presented_replies_use_shared_speech_boundary(self):
        vm = read("SarahViewModel.kt")
        offscreen = read("OffscreenCommand.kt")
        for marker in ('VoiceReply.read(bridge!!.pollChunks(', 'VoiceReply.read(bridge!!.lookup(',
                       'VoiceReply.read(bridge!!.cancel(', 'VoiceReply.read(remote!!.cancel('):
            self.assertIn(marker, vm)
        self.assertIn('VoiceReply.read(bridge.pollCancellable(', offscreen)
        self.assertIn('!row.isNull("phone_action")', read("VoiceReply.kt"))
        self.assertIn('!row.isNull("confirmation")', read("VoiceReply.kt"))
        # The only production mentions of legacy envelopes are rejection at the boundary.
        for path in SOURCE.glob("*.kt"):
            if path.name != "VoiceReply.kt":
                self.assertNotRegex(path.read_text(), r'"(phone_action|confirmation|phoneActionKey|phoneActionReceipt)"')
        recovery = vm.split(" fun checkExisting()", 1)[1].split(" fun recoverApprovedLocalRequest()", 1)[0]
        self.assertNotRegex(recovery, r'bridge!!\.(submit|create|audio|audioChunk|cancel)\(')
        self.assertIn('state.put("request",request)', offscreen)
        self.assertLess(offscreen.index('vault.save(state)', offscreen.index('state.put("request",request)')),
                        offscreen.index('bridge.submitCancellable('))

    def test_wake_capture_playback_and_both_ui_variants_remain(self):
        for name in ("Capture.kt", "Playback.kt", "AudioSafety.kt", "CommandEndpoint.kt",
                     "CommandTeardown.kt", "HeySarahKeywordEngine.kt", "HeySarahListenerService.kt",
                     "ListenerModelWarmup.kt", "OffscreenSafety.kt", "Vault.kt"):
            self.assertTrue((SOURCE / name).is_file(), name)
        service = read("HeySarahListenerService.kt")
        for marker in ('ServiceRearmPolicy.allowed(', 'owner.cleanupComplete', 'listenerCleanup.complete',
                       'prewarmed.take()', 'NotificationAvailability.allowed(this)', 'fun stop(context:Context)'):
            self.assertIn(marker, service)
        self.assertIn('CommandCleanup.await(', read("OffscreenCommand.kt"))
        ui = read("MainActivity.kt")
        for marker in ('if(locked()) {finish();return}', 'listenerConsent', 'ListenerPermissionFlow.confirmed(',
                       'CompanionWaveform(ui.phase,vm', 'val caption=ui.responseText', 'vm.playbackPositionMs()', 'History'):
            self.assertIn(marker, ui)
        gradle = (ANDROID / "app/build.gradle.kts").read_text()
        for marker in ('create("phone")', 'create("lenovo")', 'arm64-v8a', 'armeabi-v7a'):
            self.assertIn(marker, gradle)
        self.assertIn('AES/GCM/NoPadding', read("Vault.kt"))
        self.assertIn('file.finishWrite(out)', read("Vault.kt"))
        self.assertIn('No plaintext fallback', read("Vault.kt"))


if __name__ == "__main__":
    unittest.main()
