package com.serexe.sarah

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.net.Uri
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.media.RingtoneManager
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.speech.tts.TextToSpeech
import java.util.Locale

/** Bounded audible local alert. No network/model; no wake-microphone restart. */
class LocalAlertService:Service() {
 private val main=Handler(Looper.getMainLooper())
 private var activeId:String?=null
 private var player:MediaPlayer?=null
 private var tts:TextToSpeech?=null
 private var focus:AudioFocusRequest?=null
 private var leased=false
 private val manager by lazy {getSystemService(AudioManager::class.java)}
 override fun onBind(intent:Intent?):IBinder?=null
 override fun onStartCommand(intent:Intent?,flags:Int,startId:Int):Int {
  val id=intent?.getStringExtra("id")
  if(intent?.action==STOP) {
   if(id==activeId) {releaseAudio();stopForeground(STOP_FOREGROUND_REMOVE);stopSelf()}
   return START_NOT_STICKY
  }
  if(intent?.action!=START || id==null) {stopSelf();return START_NOT_STICKY}
  val due=intent.getLongExtra("due",0)
  val entry=runCatching {localSchedule(this).list().firstOrNull {it.id==id &&
   (it.deliveryDue==due || it.deliveredDue==due) && it.state in setOf("delivering","ringing")}}.getOrNull()
  if(entry==null) {stopSelf();return START_NOT_STICKY}
  val dismiss=PendingIntent.getBroadcast(this,0,Intent(this,LocalScheduleReceiver::class.java)
   .setAction(AndroidScheduleDriver.DISMISS)
   .setData(Uri.parse("sarah-schedule://dismiss/${Uri.encode(id)}/$due")),
   PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
  val notification=Notification.Builder(this,AndroidScheduleDriver.CHANNEL)
   .setSmallIcon(android.R.drawable.ic_lock_idle_alarm).setContentTitle("S.A.R.A.H alert sounding")
   .setVisibility(Notification.VISIBILITY_SECRET).setOngoing(true)
   .addAction(android.R.drawable.ic_menu_close_clear_cancel,"Dismiss alert",dismiss).build()
  try {startForeground(82991,notification)} catch (_:Exception) {stopSelf();return START_NOT_STICKY}
  releaseAudio();activeId=id;soundId=id
  val attr=AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build()
  try {
   val req=AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT).setAudioAttributes(attr)
    .setOnAudioFocusChangeListener({if(it<=0) releaseAudio()},main).build()
   focus=req
   if(manager.requestAudioFocus(req)==AudioManager.AUDIOFOCUS_REQUEST_GRANTED) {
    fun startWhenFree(attempt:Int) {
     if(activeId!=id) return
     if(!AudioArbiter.acquire(this)) {
      if(attempt<30) main.postDelayed({startWhenFree(attempt+1)},100L)
      return
     }
     leased=true
     try {
      val uri=RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
       ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
      if(uri!=null) {
       val p=MediaPlayer();player=p;p.setAudioAttributes(attr);p.setDataSource(this,uri)
       p.isLooping=true;p.setVolume(.25f,.25f);p.prepare();p.start()
      }
      val speech=if(entry.kind=="reminder") "Reminder: ${entry.title}" else "${entry.kind}: ${entry.title}"
      tts=TextToSpeech(this) {status-> main.post {
       if(status==TextToSpeech.SUCCESS && activeId==id) tts?.also {it.language=Locale.US;it.speak(speech,TextToSpeech.QUEUE_FLUSH,null,"alert-$due")}
      }}
     } catch (_:Exception) {releaseAudio()}
    }
    startWhenFree(0)
   } else releaseAudio()
  } catch (_:Exception) {releaseAudio()}
  main.postDelayed({if(activeId==id) {releaseAudio();stopForeground(STOP_FOREGROUND_REMOVE);stopSelf()}},120_000L)
  return START_NOT_STICKY
 }
 private fun releaseAudio() {
  runCatching {tts?.stop();tts?.shutdown()};tts=null
  runCatching {player?.stop()};runCatching {player?.release()};player=null
  runCatching {focus?.let {manager.abandonAudioFocusRequest(it)}};focus=null
  activeId=null
  soundId=null
  if(leased) {AudioArbiter.release(this);leased=false}
 }
 override fun onDestroy() {releaseAudio();super.onDestroy()}
 companion object {const val START="com.serexe.sarah.ALERT_START";const val STOP="com.serexe.sarah.ALERT_STOP";@Volatile var soundId:String?=null;private set}
}
