package com.serexe.sarah

import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime
import java.util.UUID

/** requestKey is server turn + nonce, not text selected by model. */
internal data class ScheduleEntry(
 val id:String, val requestKey:String, val kind:String, val title:String, val dueMillis:Long,
 val weekdays:Set<Int> = emptySet(), val localTime:String = "", val zone:String = "", val state:String="active",
 val deliveredDue:Long=0, val deliveryDue:Long=0, val scheduled:Boolean=false
)
internal object ScheduleCodec {
 fun encode(entries:List<ScheduleEntry>):ByteArray = JSONArray().also {array -> entries.forEach {e ->
  array.put(JSONObject().put("id",e.id).put("request",e.requestKey).put("kind",e.kind)
   .put("title",e.title).put("due",e.dueMillis).put("weekdays",JSONArray(e.weekdays.sorted()))
   .put("localTime",e.localTime).put("zone",e.zone).put("state",e.state)
   .put("deliveredDue",e.deliveredDue).put("deliveryDue",e.deliveryDue).put("scheduled",e.scheduled))
 }}.toString().toByteArray(Charsets.UTF_8)
 fun decode(data:ByteArray):List<ScheduleEntry> {
  if(data.isEmpty()) return emptyList()
  val array=JSONArray(String(data,Charsets.UTF_8))
  require(array.length()<=512) {"Too many local schedules"}
  return (0 until array.length()).map {i ->
   val o=array.getJSONObject(i);val days=o.getJSONArray("weekdays")
   ScheduleEntry(o.getString("id"),o.getString("request"),o.getString("kind"),
    o.getString("title"),o.getLong("due"),(0 until days.length()).map {days.getInt(it)}.toSet(),
    o.getString("localTime"),o.getString("zone"),o.optString("state","active"),
    o.optLong("deliveredDue"),o.optLong("deliveryDue"),o.optBoolean("scheduled"))
  }.also {entries -> require(entries.all {it.state in setOf("active","delivering","ringing","fired","cancelled")} &&
    entries.map {it.id}.toSet().size==entries.size &&
    entries.map {it.requestKey}.toSet().size==entries.size) {"Duplicate local schedule identity"}}
 }
}
internal interface ScheduleJournal { fun load():ByteArray; fun save(data:ByteArray) }
internal interface ScheduleDriver {
 fun available():Boolean
 fun schedule(entry:ScheduleEntry)
 fun cancel(entry:ScheduleEntry)
 /** Same occurrence/tag replaces prior notification on crash recovery. */
 fun notify(entry:ScheduleEntry)
}
/** Durable outbox. Delivery claimed before notify, acknowledged after; recovery retries same occurrence.
 * Notification identity is stable, so retries replace instead of stacking. Audio may replay after a
 * process death at the external side-effect boundary; never claim exactly-once physical sound. */
internal class LocalSchedule(private val journal:ScheduleJournal,private val driver:ScheduleDriver,
 private val now:()->Long=System::currentTimeMillis,private val newId:()->String={UUID.randomUUID().toString()}) {
 private fun entries()=ScheduleCodec.decode(journal.load())
 private fun save(entries:List<ScheduleEntry>)=journal.save(ScheduleCodec.encode(entries))
 @Synchronized fun list(kind:String?=null):List<ScheduleEntry> = entries().filter {
  it.state in setOf("active","delivering","ringing") && (kind==null || kind=="timer" && it.kind==kind)
 }
 @Synchronized fun add(requestKey:String,kind:String,title:String,dueMillis:Long,
  weekdays:Set<Int> = emptySet(),localTime:String="",zone:String=""):ScheduleEntry {
  require(requestKey.length in 8..128 && requestKey.none {it.isISOControl()}) {"Invalid request identity"}
  require(kind in setOf("timer","alarm","reminder"))
  require(title.length in 1..240 && title.none {it.isISOControl()})
  require(weekdays.isEmpty() || kind=="alarm" && weekdays.all {it in 1..7} &&
   localTime.isNotEmpty() && zone.isNotEmpty()) {"Invalid recurrence"}
  if(weekdays.isNotEmpty()) {LocalTime.parse(localTime);ZoneId.of(zone)}
  val prior=entries()
  prior.find {it.requestKey==requestKey}?.let {existing ->
   require(existing.kind==kind && existing.title==title && existing.dueMillis==dueMillis &&
    existing.weekdays==weekdays && existing.localTime==localTime && existing.zone==zone) {"Request identity conflict"}
   return existing // same authenticated turn: durable receipt, never repeat mutation
  }
  require(dueMillis>now()+999 && dueMillis<now()+366L*24*60*60*1000) {"Due time out of range"}
  check(prior.size<512) {"Too many local schedules; replay identities retained"}
  check(driver.available()) {"Exact alarm or notification permission unavailable; schedule not accepted"}
  val entry=ScheduleEntry(newId(),requestKey,kind,title,dueMillis,weekdays,localTime,zone)
  require(prior.none {it.id==entry.id}) {"Schedule identity collision"}
  save(prior+entry)
  return schedule(entry)
 }
 private fun schedule(entry:ScheduleEntry):ScheduleEntry {
  if(entry.scheduled) return entry
  return try {
   driver.schedule(entry)
   val prior=entries();val updated=entry.copy(scheduled=true)
   save(prior.map {if(it.id==entry.id && it.dueMillis==entry.dueMillis && it.state=="active") updated else it})
   updated
  } catch (_:Exception) {entry} // persisted acceptance, honest pending status
 }
 @Synchronized fun cancel(id:String,requestKey:String="local-cancel-$id",kind:String?=null):Boolean {
  if(kind!=null && kind!="timer") return false
  val prior=entries();if(prior.any {it.requestKey==requestKey}) return false
  val entry=prior.find {it.id==id && it.state in setOf("active","delivering","ringing") &&
   (kind==null || it.kind==kind)} ?: return false
  val tombstone=entry.copy(id=newId(),state="fired",title="[cancelled]")
  require(prior.size<511 && prior.none {it.id==tombstone.id})
  save(prior.map {if(it.id==id) it.copy(state="cancelled",requestKey=requestKey) else it}+tombstone)
  driver.cancel(entry);return true
 }
 @Synchronized fun dismiss(id:String,requestKey:String="local-dismiss-$id"):Boolean {
  val prior=entries();if(prior.any {it.requestKey==requestKey}) return false
  val entry=prior.find {it.id==id && it.state=="ringing"} ?: return false
  val tombstone=entry.copy(id=newId(),state="fired",title="[dismissed]")
  require(prior.size<511 && prior.none {it.id==tombstone.id})
  save(prior.map {if(it.id==id) it.copy(state=if(it.weekdays.isEmpty()) "fired" else "active",requestKey=requestKey) else it}+tombstone)
  driver.cancel(entry)
  if(entry.weekdays.isNotEmpty()) schedule(entries().first {it.id==id})
  return true
 }
 @Synchronized fun extend(requestKey:String,id:String,extraMillis:Long):ScheduleEntry {
  require(extraMillis in 1000..86_400_000)
  val prior=entries();prior.find {it.requestKey==requestKey}?.let {return it}
  val old=prior.find {it.id==id && it.state=="active" && it.kind=="timer"} ?: error("Timer unavailable")
  val due=Math.addExact(maxOf(now(),old.dueMillis),extraMillis)
  require(due<now()+366L*24*60*60*1000)
  val updated=old.copy(requestKey=requestKey,dueMillis=due,scheduled=false)
  val tombstone=old.copy(id=newId(),state="fired",title="[changed]")
  require(prior.size<511 && prior.none {it.id==tombstone.id})
  save(prior.map {if(it.id==id) updated else it}+tombstone);driver.cancel(old)
  return schedule(updated)
 }
 @Synchronized fun snooze(requestKey:String,id:String,millis:Long):ScheduleEntry {
  require(millis in 60_000..3_600_000)
  val prior=entries();prior.find {it.requestKey==requestKey}?.let {return it}
  val old=prior.find {it.id==id && it.state=="ringing"} ?: error("Alert not ringing")
  val updated=old.copy(requestKey=requestKey,dueMillis=now()+millis,state="active",scheduled=false)
  val tombstone=old.copy(id=newId(),state="fired",title="[snoozed]")
  require(prior.size<511 && prior.none {it.id==tombstone.id})
  save(prior.map {if(it.id==id) updated else it}+tombstone);driver.cancel(old)
  return schedule(updated)
 }
 @Synchronized fun fire(id:String,expectedDue:Long):Boolean {
  var prior=entries();var entry=prior.find {it.id==id && it.dueMillis==expectedDue && it.state in setOf("active","delivering")} ?: return false
  if(entry.dueMillis>now() || !driver.available()) return false
  if(entry.state=="active") {
   entry=entry.copy(state="delivering",deliveryDue=expectedDue)
   save(prior.map {if(it.id==id) entry else it})
  }
  driver.notify(entry) // failure leaves durable outbox; boot/app-entry retries
  prior=entries()
  val next=if(entry.weekdays.isEmpty()) entry.copy(state="ringing",deliveryDue=0,deliveredDue=expectedDue)
   else entry.copy(state="ringing",dueMillis=nextWeekday(entry,now()),deliveryDue=0,deliveredDue=expectedDue,scheduled=false)
  save(prior.map {if(it.id==id) next else it})
  return true
 }
 @Synchronized fun reconcile(recoverRinging:Boolean=false) {
  if(!driver.available()) return
  entries().forEach {entry -> runCatching {
   when(entry.state) {
    "ringing" -> if(recoverRinging) driver.notify(entry)
    "delivering" -> fire(entry.id,entry.deliveryDue)
    "active" -> if(entry.dueMillis<=now()) fire(entry.id,entry.dueMillis) else driver.schedule(entry).also {
     if(!entry.scheduled) save(entries().map {if(it.id==entry.id) it.copy(scheduled=true) else it})
    }
   }
  }}
 }
 companion object {
  fun nextWeekday(entry:ScheduleEntry,after:Long):Long {
   val zone=ZoneId.of(entry.zone);val time=LocalTime.parse(entry.localTime)
   val base=Instant.ofEpochMilli(after).atZone(zone)
   for(offset in 0..7) {
    val date=base.toLocalDate().plusDays(offset.toLong())
    if(date.dayOfWeek.value !in entry.weekdays) continue
    val candidate=ZonedDateTime.of(date,time,zone).toInstant().toEpochMilli()
    if(candidate>after) return candidate
   }
   error("No next weekday")
  }
 }
}
