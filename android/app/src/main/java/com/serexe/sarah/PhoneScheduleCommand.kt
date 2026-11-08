package com.serexe.sarah

import android.content.Context
import org.json.JSONObject
import java.time.ZoneId

/** Only authenticated turn envelopes from Bridge.poll/lookup reach here. No text parsing. */
internal object PhoneScheduleCommand {
 fun requestKey(envelope:JSONObject,conversation:String,turn:String):String {
  require(Identity.valid(conversation) && Identity.valid(turn))
  require(envelope.getString("conversation")==conversation && envelope.getString("turn")==turn)
  val nonce=envelope.getString("nonce")
  require(nonce.matches(Regex("[0-9a-f]{64}")))
  envelope.getJSONObject("command")
  return "$turn:$nonce"
 }
 fun execute(context:Context,envelope:JSONObject,conversation:String,turn:String):JSONObject {
  val key=requestKey(envelope,conversation,turn)
  val command=envelope.getJSONObject("command")
  val schedule=localSchedule(context)
  val reply=try {
   when(command.getString("action")) {
    "create" -> {
     val kind=command.getString("kind")
     val days=command.optJSONArray("weekdays")?.let {a->(0 until a.length()).map {a.getInt(it)}.toSet()} ?: emptySet()
     val zone=command.optString("zone","");val local=command.optString("local_time","")
     if(days.isNotEmpty()) ZoneId.of(zone)
     val due=if(days.isEmpty()) command.getLong("due_ms") else LocalSchedule.nextWeekday(
      ScheduleEntry("","",kind,command.getString("title"),0,days,local,zone),System.currentTimeMillis())
     val e=schedule.add(key,kind,command.getString("title"),due,days,local,zone)
     if(e.state!="active") "Request already completed; no new alert." to "done"
     else if(!e.scheduled) "${e.kind} accepted but device scheduling pending. Check exact-alarm/notification permissions. ID ${e.id}." to "pending"
     else "${e.kind} scheduled: ${e.title}. ID ${e.id}." to "scheduled"
    }
    "list" -> {
     val kind=command.optString("kind","").takeIf {it.isNotEmpty()}
     val rows=schedule.list(kind).take(12)
     (if(rows.isEmpty()) if(kind=="timer") "No active timers." else "No active timers, alarms or reminders." else rows.joinToString("; ") {
      "${it.kind} ${it.title}, ID ${it.id}, due ${java.time.Instant.ofEpochMilli(it.dueMillis)}${if(it.state=="ringing") " ringing" else if(!it.scheduled) " scheduling pending" else ""}"
     }) to "done"
    }
    "cancel" -> (if(schedule.cancel(command.getString("id"),key,command.optString("kind","").takeIf {it.isNotEmpty()})) "Alert cancelled." else "Alert not active or request already handled.") to "done"
    "dismiss" -> (if(schedule.dismiss(command.getString("id"),key)) "Alert dismissed." else "Alert not ringing or request already handled.") to "done"
    "extend" -> schedule.extend(key,command.getString("id"),command.getLong("extra_ms")).let {
     "Timer extended. ID ${it.id}; ${if(it.scheduled) "scheduled" else "scheduling pending"}." to (if(it.scheduled) "scheduled" else "pending")
    }
    "snooze" -> schedule.snooze(key,command.getString("id"),command.getLong("extra_ms")).let {
     "Alert snoozed. ID ${it.id}; ${if(it.scheduled) "scheduled" else "scheduling pending"}." to (if(it.scheduled) "scheduled" else "pending")
    }
    else -> "Unsupported phone schedule action. Nothing changed." to "denied"
   }
  } catch (_:Exception) {"Phone schedule unavailable or request invalid. Check app and permissions; do not retry uncertain writes." to "uncertain"}
  return JSONObject().put("status",reply.second).put("reply",reply.first.take(1000))
 }
}
