package com.serexe.sarah

import android.Manifest
import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.util.AtomicFile
import java.io.File
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties

/** Native owner; no bridge/network/model required after a command is accepted. */
internal class AndroidScheduleJournal(context:Context):ScheduleJournal {
 private val file=AtomicFile(File(context.filesDir,"local-schedules-v1.json"))
 private fun key():SecretKey {
  val ks=KeyStore.getInstance("AndroidKeyStore").apply {load(null)}
  (ks.getKey("sarah-schedules-v1",null) as? SecretKey)?.let {return it}
  return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore").apply {
   init(KeyGenParameterSpec.Builder("sarah-schedules-v1",KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
    .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setKeySize(256).build())
  }.generateKey()
 }
 override fun load():ByteArray {
  val raw=try {file.openRead().use {it.readBytes()}} catch (_:java.io.FileNotFoundException) {return byteArrayOf()}
  require(raw.size<=524288) {"Local schedule storage too large"}
  if(raw.firstOrNull()== '['.code.toByte()) {
   // Phase-1 plaintext migration: validate first, atomically replace with encrypted bytes.
   ScheduleCodec.decode(raw);save(raw);return raw
  }
  require(raw.size>28 && raw[0]==1.toByte()) {"Invalid encrypted schedule ledger"}
  val cipher=Cipher.getInstance("AES/GCM/NoPadding")
  cipher.init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,raw.copyOfRange(1,13)))
  return cipher.doFinal(raw.copyOfRange(13,raw.size))
 }
 override fun save(data:ByteArray) {
  val cipher=Cipher.getInstance("AES/GCM/NoPadding").apply {init(Cipher.ENCRYPT_MODE,key())}
  val encrypted=byteArrayOf(1)+cipher.iv+cipher.doFinal(data)
  val stream=file.startWrite()
  try {stream.write(encrypted);file.finishWrite(stream)} catch (e:Exception) {file.failWrite(stream);throw e}
 }
}

internal class AndroidScheduleDriver(private val context:Context):ScheduleDriver {
 private val alarms=context.getSystemService(AlarmManager::class.java)
 private val notifications=context.getSystemService(NotificationManager::class.java)
 private fun channel() {
  notifications.createNotificationChannel(NotificationChannel(CHANNEL,"Local schedules",NotificationManager.IMPORTANCE_HIGH))
 }
 override fun available():Boolean = try {
  channel()
  (Build.VERSION.SDK_INT<31 || alarms.canScheduleExactAlarms()) &&
   (Build.VERSION.SDK_INT<33 || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)==PackageManager.PERMISSION_GRANTED) &&
   notifications.areNotificationsEnabled() && notifications.getNotificationChannel(CHANNEL)?.importance!=NotificationManager.IMPORTANCE_NONE
 } catch (_:Exception) {false}
 private fun intent(entry:ScheduleEntry):Intent=Intent(context,LocalScheduleReceiver::class.java).setAction(ACTION)
  .setData(Uri.parse("sarah-schedule://local/${Uri.encode(entry.id)}/${entry.dueMillis}"))
 private fun pending(entry:ScheduleEntry,flags:Int):PendingIntent?=PendingIntent.getBroadcast(context,0,intent(entry),flags or PendingIntent.FLAG_IMMUTABLE)
 override fun schedule(entry:ScheduleEntry) {
  check(available()) {"Exact alarm or notification permission unavailable"}
  alarms.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,entry.dueMillis,pending(entry,PendingIntent.FLAG_UPDATE_CURRENT)!!)
 }
 override fun cancel(entry:ScheduleEntry) {
  pending(entry,PendingIntent.FLAG_NO_CREATE)?.let {alarms.cancel(it);it.cancel()}
  try {notifications.cancel(entry.id,0)} finally {
   // Notification actions may arrive while app is backgrounded. startService
   // can be denied there, leaving a foreground alarm sounding despite tombstone.
   if(LocalAlertService.soundId==entry.id) context.stopService(Intent(context,LocalAlertService::class.java))
  }
 }
 override fun notify(entry:ScheduleEntry) {
  val open=PendingIntent.getActivity(context,0,Intent(context,MainActivity::class.java),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
  val label=when(entry.kind) {"timer"->"Timer finished";"alarm"->"Alarm";else->"Reminder"}
  val occurrence=if(entry.deliveryDue!=0L) entry.deliveryDue else entry.deliveredDue
  val dismiss=PendingIntent.getBroadcast(context,0,Intent(context,LocalScheduleReceiver::class.java)
   .setAction(DISMISS).setData(Uri.parse("sarah-schedule://dismiss/${Uri.encode(entry.id)}/$occurrence")),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
  val snooze=PendingIntent.getBroadcast(context,0,Intent(context,LocalScheduleReceiver::class.java)
   .setAction(SNOOZE).setData(Uri.parse("sarah-schedule://snooze/${Uri.encode(entry.id)}/$occurrence")),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
  notifications.notify(entry.id,0,Notification.Builder(context,CHANNEL)
   .setSmallIcon(android.R.drawable.ic_lock_idle_alarm).setContentTitle(label).setContentText(entry.title)
   .setVisibility(Notification.VISIBILITY_SECRET).setContentIntent(open).setOngoing(true)
   .addAction(android.R.drawable.ic_menu_close_clear_cancel,"Dismiss",dismiss)
   .addAction(android.R.drawable.ic_media_pause,"Snooze 10 min",snooze).build())
  runCatching {context.startForegroundService(Intent(context,LocalAlertService::class.java)
   .setAction(LocalAlertService.START).putExtra("id",entry.id).putExtra("due",occurrence))}
 }
 companion object {
  const val ACTION="com.serexe.sarah.LOCAL_SCHEDULE_DUE"
  const val DISMISS="com.serexe.sarah.LOCAL_SCHEDULE_DISMISS"
  const val SNOOZE="com.serexe.sarah.LOCAL_SCHEDULE_SNOOZE"
  const val CHANNEL="sarah-local-schedules"
 }
}

/** One process-wide ledger lock; broadcasts and foreground commands cannot race file writes. */
internal object LocalScheduleOwner {
 @Volatile private var instance:LocalSchedule?=null
 fun get(context:Context):LocalSchedule=instance ?: synchronized(this) {
  instance ?: LocalSchedule(AndroidScheduleJournal(context.applicationContext),AndroidScheduleDriver(context.applicationContext))
   .also {instance=it}
 }
}

internal fun localSchedule(context:Context):LocalSchedule=LocalScheduleOwner.get(context)

class LocalScheduleReceiver:BroadcastReceiver() {
 override fun onReceive(context:Context,intent:Intent?) {
  val action=intent?.action ?: return
  if(action !in setOf(AndroidScheduleDriver.ACTION,AndroidScheduleDriver.DISMISS,AndroidScheduleDriver.SNOOZE)) return
  val uri=intent.data ?: return
  val host=when(action) {AndroidScheduleDriver.ACTION->"local";AndroidScheduleDriver.DISMISS->"dismiss";else->"snooze"}
  if(uri.scheme!="sarah-schedule" || uri.host!=host || uri.pathSegments.size!=2) return
  val due=uri.pathSegments[1].toLongOrNull() ?: return
  val id=uri.pathSegments[0]
  runCatching {
   val ledger=localSchedule(context)
   if(action==AndroidScheduleDriver.ACTION) ledger.fire(id,due)
   else if(ledger.list().any {it.id==id && it.state=="ringing" && it.deliveredDue==due}) {
    val changed=if(action==AndroidScheduleDriver.DISMISS) ledger.dismiss(id,"notification-dismiss-$id-$due")
     else ledger.snooze("notification-snooze-$id-$due",id,600_000L).let {true}
    if(changed) context.startService(Intent(context,LocalAlertService::class.java).setAction(LocalAlertService.STOP).putExtra("id",id))
   }
  }
 }
}

class LocalScheduleBootReceiver:BroadcastReceiver() {
 override fun onReceive(context:Context,intent:Intent?) {
  if(intent?.action !in setOf(Intent.ACTION_BOOT_COMPLETED,Intent.ACTION_TIME_CHANGED,Intent.ACTION_TIMEZONE_CHANGED)) return
  runCatching {localSchedule(context).reconcile(recoverRinging=true)}
 }
}
