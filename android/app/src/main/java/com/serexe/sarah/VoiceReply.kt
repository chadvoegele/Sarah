package com.serexe.sarah

import org.json.JSONObject

/** Speech-only wire boundary shared by visible, offscreen and read-only recovery paths. */
internal object VoiceReply {
 class Unsupported:IllegalArgumentException("Unsupported reply; use a voice-only ACP bridge")
 private val states=setOf("transcribing","thinking","speaking","done","error","cancelled","uncertain")
 fun read(row:JSONObject):JSONObject {
  if(!row.isNull("phone_action") || !row.isNull("confirmation") || row.optString("state") !in states) throw Unsupported()
  val out=JSONObject()
  for(key in listOf("id","conversation","state","transcript","detail","audio","reply_expected")) {
   if(row.has(key)) out.put(key,row.get(key))
  }
  row.optJSONObject("audio_chunks")?.let {chunks->
   out.put("audio_chunks",JSONObject().put("count",chunks.optInt("count",-1)))
  }
  row.optJSONObject("timings")?.let {timings->
   val safe=JSONObject()
   for(key in listOf("upload_read_ms","queue_ms","stt_ms","reply_ms","model_ms","tts_ms","server_ms")) {
    val value=timings.optDouble(key,Double.NaN)
    if(value.isFinite() && value>=0) safe.put(key,value)
   }
   out.put("timings",safe)
  }
  return out
 }
}
