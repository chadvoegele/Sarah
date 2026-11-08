package com.serexe.sarah

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PhoneScheduleCommandTest {
 @Test fun ownerTurnAndNonceRequiredForLocalMutation() {
  val envelope=JSONObject().put("conversation","owner-conversation").put("turn","turn-001")
   .put("nonce","a".repeat(64)).put("command",JSONObject().put("action","list"))
  assertEquals("turn-001:${"a".repeat(64)}",PhoneScheduleCommand.requestKey(envelope,"owner-conversation","turn-001"))
  for(bad in listOf(envelope.put("nonce","short"),JSONObject().put("conversation","other").put("turn","turn-001").put("nonce","a".repeat(64)).put("command",JSONObject()))) {
   try {PhoneScheduleCommand.requestKey(bad,"owner-conversation","turn-001");fail("foreign envelope accepted")} catch (_:Exception) {}
  }
 }
}
