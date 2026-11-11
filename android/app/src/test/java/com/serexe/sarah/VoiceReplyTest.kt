package com.serexe.sarah

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class VoiceReplyTest {
 private fun reply(state:String="done")=JSONObject().put("id","t1").put("conversation","c1")
  .put("state",state).put("transcript","Set a timer or play music").put("detail","Plain agent answer")
  .put("audio",false).put("reply_expected",true)
 @Test fun onlySpeechTextAndNumericDiagnosticsCrossBoundary() {
  val source=reply("speaking").put("command",JSONObject().put("action","play"))
   .put("tools",JSONObject().put("clock",true)).put("actions",org.json.JSONArray().put("alarm"))
   .put("audio_chunks",JSONObject().put("count",2).put("url","https://untrusted.invalid"))
   .put("timings",JSONObject().put("stt_ms",12.5).put("route","direct_timer").put("token","secret"))
  val row=VoiceReply.read(source)
  assertEquals(setOf("id","conversation","state","transcript","detail","audio","reply_expected","audio_chunks","timings"),row.keySet())
  assertEquals("Set a timer or play music",row.getString("transcript"))
  assertEquals("Plain agent answer",row.getString("detail"))
  assertEquals(setOf("count"),row.getJSONObject("audio_chunks").keySet())
  assertEquals(setOf("stt_ms"),row.getJSONObject("timings").keySet())
  assertEquals(12.5,row.getJSONObject("timings").getDouble("stt_ms"),0.0)
  assertTrue(source.has("command")) // never mutate a caller's row
 }
 @Test fun realRelayEnvelopesMatchSharedPythonContract() {
  val fixtures=requireNotNull(javaClass.getResourceAsStream("/voice-relay.json")).use {
   JSONObject(it.bufferedReader().readText())
  }
  for(state in listOf("speaking","done","uncertain","cancelled")) {
   val source=fixtures.getJSONObject(state)
   val row=VoiceReply.read(source)
   assertEquals(state,row.getString("state"))
   for(key in listOf("id","conversation","detail","transcript","audio")) {
    assertEquals(source.get(key),row.get(key))
   }
   assertFalse(row.has("reply_expected"))
   assertFalse(ClarificationReply.valid(row,"synthetic-conversation","synthetic-turn","fresh","fresh"))
   if(state=="speaking") assertEquals(2,row.getJSONObject("audio_chunks").getInt("count"))
   else assertFalse(row.has("audio_chunks"))
  }
 }
 @Test fun legacyEnvelopesFailClosedIncludingStoredReceiptsAndMalformedValues() {
  for(key in listOf("phone_action","confirmation")) {
   for(state in listOf("speaking","done","error","uncertain")) {
    for(value in listOf(JSONObject().put("command",JSONObject().put("action","create").put("kind","timer"))
     .put("receipt",JSONObject().put("status","scheduled")),JSONObject(),false,"play music")) {
     assertThrows(VoiceReply.Unsupported::class.java) {VoiceReply.read(reply(state).put(key,value))}
    }
   }
   assertEquals("done",VoiceReply.read(reply().put(key,JSONObject.NULL)).getString("state"))
  }
 }
 @Test fun noActionStatesOrUnknownStatesCanBecomeReady() {
  for(state in listOf("confirming","acting","scheduled","", "new-action-state")) {
   assertThrows(VoiceReply.Unsupported::class.java) {VoiceReply.read(reply(state))}
  }
  for(state in listOf("transcribing","thinking","speaking","done","error","cancelled","uncertain")) {
   assertEquals(state,VoiceReply.read(reply(state)).getString("state"))
  }
 }
 @Test fun noReceiptOrConfirmationOperationsExistOnTransportOrController() {
  for(type in listOf(BridgePort::class.java,Bridge::class.java,SarahViewModel::class.java)) {
   assertFalse(type.declaredMethods.any {it.name in setOf("confirm","phoneReceipt","phoneReceiptCancellable","handlePhoneAction")})
  }
 }
}
