package com.serexe.sarah

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PhoneMediaTest {
 @Test fun localMediaActionsOnlyAndOwnerBinding() {
  assertEquals(setOf("play_local","pause","resume","stop","status","volume"),PhoneMedia.supportedActions)
  assertFalse(PhoneMedia.supportedActions.contains("play_radio"))
  val turn="00000000-0000-0000-0000-000000000001"
  val conversation="00000000-0000-0000-0000-000000000002"
  val envelope=JSONObject().put("turn",turn).put("conversation",conversation).put("nonce","a".repeat(64))
   .put("command",JSONObject().put("action","status").put("_phone_type","media"))
  assertEquals("$turn:${"a".repeat(64)}",PhoneScheduleCommand.requestKey(envelope,conversation,turn))
  assertThrows(Exception::class.java) {PhoneScheduleCommand.requestKey(envelope,"wrong",turn)}
  assertThrows(Exception::class.java) {PhoneScheduleCommand.requestKey(envelope,conversation,"wrong")}
 }
}
