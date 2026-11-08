package com.serexe.sarah

import org.junit.Assert.*
import org.junit.Test
import java.time.Instant
import java.util.concurrent.atomic.AtomicInteger

class LocalScheduleTest {
 private class Journal:ScheduleJournal {
  var data=byteArrayOf();var writes=0
  override fun load()=data.copyOf()
  override fun save(data:ByteArray) {this.data=data.copyOf();writes++}
 }
 private class Driver:ScheduleDriver {
  var enabled=true;var schedulingFails=false;var deliveryFails=false;var audible=false
  val scheduled=mutableListOf<ScheduleEntry>();val delivered=mutableListOf<ScheduleEntry>();val cancelled=mutableListOf<ScheduleEntry>()
  override fun available()=enabled
  override fun schedule(entry:ScheduleEntry) {if(schedulingFails) error("alarm manager failed");scheduled+=entry}
  override fun cancel(entry:ScheduleEntry) {cancelled+=entry;audible=false}
  override fun notify(entry:ScheduleEntry) {if(deliveryFails) error("notification failed");delivered+=entry;audible=true}
 }
 private val key="authenticated-turn-0001"
 private fun ledger(j:Journal,d:Driver,time:()->Long):LocalSchedule {
  val ids=AtomicInteger()
  return LocalSchedule(j,d,time,{"id-${ids.incrementAndGet()}-${System.nanoTime()}"})
 }
 @Test fun replayAndDurableRingingThenDismiss() {
  val j=Journal();val d=Driver();var now=1000L;val s=ledger(j,d,{now})
  val e=s.add(key,"timer","tea",5000)
  assertTrue(e.scheduled);assertEquals(e,s.add(key,"timer","tea",5000));assertEquals(1,d.scheduled.size)
  assertFalse(s.fire(e.id,5000));now=5001
  assertTrue(s.fire(e.id,5000));assertFalse(s.fire(e.id,5000));assertEquals(1,d.delivered.size)
  assertTrue(d.audible)
  assertEquals("ringing",s.list().single().state)
  s.reconcile();assertEquals(1,d.delivered.size)
  s.reconcile(recoverRinging=true);assertEquals(2,d.delivered.size)
  assertEquals(5000L,d.delivered.last().deliveredDue)
  assertTrue(s.dismiss(e.id,"authenticated-dismiss-1"));assertFalse(s.dismiss(e.id,"authenticated-dismiss-1"))
  assertFalse(d.audible);assertEquals(1,d.cancelled.size)
  assertTrue(s.list().isEmpty());assertEquals("fired",ScheduleCodec.decode(j.load()).first {it.id==e.id}.state)
 }
 @Test fun unavailablePermissionDoesNotAcceptAndCancelPersists() {
  val j=Journal();val d=Driver();var now=1000L;val s=ledger(j,d,{now})
  d.enabled=false
  try {s.add(key,"reminder","take medicine",5000);fail()} catch (_:IllegalStateException) {}
  assertEquals(0,j.writes)
  d.enabled=true;val e=s.add(key,"reminder","take medicine",5000)
  d.enabled=false;now=5001;assertFalse(s.fire(e.id,5000));assertTrue(s.cancel(e.id,"authenticated-cancel-1"))
  d.enabled=true;s.reconcile();assertFalse(s.fire(e.id,5000));assertTrue(s.list().isEmpty())
  assertEquals(1,d.cancelled.size)
 }
 @Test fun recurringAlarmDstAndStaleOccurrence() {
  val j=Journal();val d=Driver();val start=Instant.parse("2026-03-07T12:00:00Z").toEpochMilli()
  var now=start;val first=Instant.parse("2026-03-08T08:30:00Z").toEpochMilli()
  val s=ledger(j,d,{now});val e=s.add(key,"alarm","work",first,setOf(7),"02:30","America/Chicago")
  now=first+1;assertTrue(s.fire(e.id,first))
  assertEquals("ringing",s.list().single().state)
  assertTrue(s.dismiss(e.id,"authenticated-dismiss-1"))
  val next=s.list().single()
  assertEquals(Instant.parse("2026-03-15T07:30:00Z").toEpochMilli(),next.dueMillis)
  now=next.dueMillis+1;assertFalse(s.fire(e.id,first));assertTrue(s.fire(e.id,next.dueMillis))
  assertEquals(2,d.delivered.size)
 }
 @Test fun schedulerFailureReturnsAcceptedButPendingThenRecovers() {
  val j=Journal();val d=Driver();var now=1000L;d.schedulingFails=true
  val s=ledger(j,d,{now});val e=s.add(key,"timer","tea",5000)
  assertFalse(e.scheduled);assertEquals("active",s.list().single().state)
  d.schedulingFails=false;val restarted=ledger(j,d,{now});restarted.reconcile()
  assertTrue(restarted.list().single().scheduled)
  now=5001;restarted.reconcile();assertEquals(1,d.delivered.size)
 }
 @Test fun notificationCrashGapRecoverSameOccurrence() {
  val j=Journal();val d=Driver();var now=1000L;val s=ledger(j,d,{now})
  val e=s.add(key,"reminder","medicine",5000);now=5001;d.deliveryFails=true
  try {s.fire(e.id,5000);fail()} catch (_:IllegalStateException) {}
  assertEquals("delivering",ScheduleCodec.decode(j.load()).single().state)
  assertEquals(5000L,ScheduleCodec.decode(j.load()).single().deliveryDue)
  d.deliveryFails=false;val reopened=ledger(j,d,{now});reopened.reconcile()
  assertEquals(1,d.delivered.size);assertEquals("ringing",reopened.list().single().state)
  reopened.reconcile();assertEquals(1,d.delivered.size)
 }
 @Test fun extendAndSnoozeRetainOldRequestTombstones() {
  val j=Journal();val d=Driver();var now=1000L;val s=ledger(j,d,{now})
  val e=s.add(key,"timer","tea",5000)
  val ext=s.extend("authenticated-extend-1",e.id,2000)
  assertEquals(7000L,ext.dueMillis)
  assertEquals(2,ScheduleCodec.decode(j.load()).size)
  assertEquals(ext,s.extend("authenticated-extend-1",e.id,2000))
  try {s.add(key,"timer","tea",5000);fail("old key replay") } catch (_:IllegalStateException) {} catch (_:IllegalArgumentException) {}
  now=7001;s.fire(e.id,7000)
  val snooze=s.snooze("authenticated-snooze-1",e.id,600_000)
  assertEquals("active",snooze.state)
  assertEquals(3,ScheduleCodec.decode(j.load()).size)
 }
 @Test fun kindFilteredTimerCancellationDoesNotTouchOtherSchedule() {
  val j=Journal();val d=Driver();val s=ledger(j,d,{1000L})
  val first=s.add("authenticated-turn-0001","timer","first",5000)
  val alarm=s.add("authenticated-turn-0002","alarm","wake",6000)
  val second=s.add("authenticated-turn-0003","timer","second",7000)
  assertEquals(listOf(first.id,second.id),s.list("timer").map {it.id})
  assertEquals(3,s.list().size)
  val writes=j.writes
  assertFalse(s.cancel(alarm.id,"cancel-timer-only",kind="timer"))
  assertFalse(s.cancel(first.id,"cancel-wrong-kind",kind="alarm"))
  assertEquals(writes,j.writes)
  assertTrue(s.cancel(first.id,"cancel-first",kind="timer"))
  assertEquals(listOf(second.id),s.list("timer").map {it.id})
  assertEquals(setOf(alarm.id,second.id),s.list().map {it.id}.toSet())
  assertFalse(s.cancel(first.id,"cancel-first",kind="timer"))
  assertEquals("cancelled",ScheduleCodec.decode(j.load()).first {it.id==first.id}.state)
 }
 @Test fun corruptStateFailsClosed() {
  val j=Journal();val d=Driver();j.data="broken".toByteArray()
  try {ledger(j,d,{1000L}).reconcile();fail()} catch (_:Exception) {}
  assertTrue(d.scheduled.isEmpty())
 }
}
