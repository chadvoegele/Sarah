package com.serexe.sarah

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.IntentFilter
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.media.MediaMetadata
import android.media.session.MediaSession
import android.media.session.PlaybackState
import android.net.Uri
import android.os.Handler
import android.os.IBinder
import android.os.Looper

/** Single phone-local playback owner. Commands never take arbitrary model-supplied stream URLs. */
class PhoneMediaService:Service() {
 private val main=Handler(Looper.getMainLooper())
 private val audio by lazy {getSystemService(AudioManager::class.java)}
 private val notifications by lazy {getSystemService(NotificationManager::class.java)}
 private val attrs=AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build()
 private var player:MediaPlayer?=null
 private var focus:AudioFocusRequest?=null
 private var owned=false
 private var title=""
 private var session:MediaSession?=null
 private var generation=0
 private val noisy=object:BroadcastReceiver() {
  override fun onReceive(context:Context?,intent:Intent?) {
   if(intent?.action==AudioManager.ACTION_AUDIO_BECOMING_NOISY) {stopPlayer();stopSelf()}
  }
 }
 override fun onBind(intent:Intent?):IBinder?=null
 override fun onCreate() {super.onCreate()
  registerReceiver(noisy,IntentFilter(AudioManager.ACTION_AUDIO_BECOMING_NOISY))
  notifications.createNotificationChannel(NotificationChannel(CHANNEL,"Phone music",NotificationManager.IMPORTANCE_LOW))
  session=MediaSession(this,"SARAH phone media").apply {
   setCallback(object:MediaSession.Callback() {
    override fun onPlay() {command("resume")}
    override fun onPause() {command("pause")}
    override fun onStop() {command("stop")}
   });isActive=true
  }
 }
 override fun onStartCommand(intent:Intent?,flags:Int,startId:Int):Int {
  val action=intent?.action ?: return START_NOT_STICKY
  if(action==PLAY) {
   val source=intent.getStringExtra("uri") ?: return START_NOT_STICKY
   val label=intent.getStringExtra("title")?.take(120) ?: "Phone media"
   // Reject even internal malformed intents; service is not exported. Local MediaStore only.
   val parsed=runCatching {Uri.parse(source)}.getOrNull()
   if(parsed==null || parsed.scheme!="content" || parsed.authority!="media" ||
    parsed.pathSegments.lastOrNull()?.toLongOrNull()==null) return START_NOT_STICKY
   stopPlayer();title=label
   startForeground(NOTIFICATION,notification("Starting"))
   if(!AudioArbiter.acquire(this)) {stopPlayer();stopSelf();return START_NOT_STICKY}
   owned=true
   val request=AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN).setAudioAttributes(attrs)
    .setOnAudioFocusChangeListener({change->
     if(change==AudioManager.AUDIOFOCUS_LOSS || change==AudioManager.AUDIOFOCUS_LOSS_TRANSIENT) {stopPlayer();stopSelf()}
     else if(change==AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK) pausePlayer()
    },main).build()
   focus=request
   if(audio.requestAudioFocus(request)!=AudioManager.AUDIOFOCUS_REQUEST_GRANTED) {stopPlayer();stopSelf();return START_NOT_STICKY}
   val token=++generation
   try {
    val p=MediaPlayer();player=p;p.setAudioAttributes(attrs)
    p.setDataSource(this,parsed)
    p.setOnPreparedListener {if(token==generation) {
     runCatching {it.start();update("Playing")}.onFailure {stopPlayer();stopSelf()}
    }}
    p.setOnCompletionListener {if(token==generation) {stopPlayer();stopSelf()}}
    p.setOnErrorListener {_,_,_->if(token==generation) {stopPlayer();stopSelf()};true}
    p.prepareAsync()
   } catch (_:Exception) {stopPlayer();stopSelf()}
  } else when(action) {
   "pause" -> pausePlayer()
   "resume" -> if(player!=null && !owned && AudioArbiter.acquire(this)) {
    owned=true
    val request=AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN).setAudioAttributes(attrs)
     .setOnAudioFocusChangeListener({if(it<=0) stopPlayer()},main).build()
    focus=request
    if(audio.requestAudioFocus(request)==AudioManager.AUDIOFOCUS_REQUEST_GRANTED) {
     runCatching {player?.start();update("Playing")}.onFailure {stopPlayer();stopSelf()}
    } else {stopPlayer();stopSelf()}
   }
   "stop" -> {stopPlayer();stopSelf()}
   "volume" -> {
    val pct=intent.getIntExtra("volume",-1)
    if(pct in 0..100 && player!=null) {val v=pct/100f;player?.setVolume(v,v);update("Volume $pct%")}
   }
  }
  return START_NOT_STICKY
 }
 private fun command(action:String) {startService(Intent(this,PhoneMediaService::class.java).setAction(action))}
 private fun pausePlayer() {runCatching {player?.pause()};releaseFocus();update("Paused")}
 private fun releaseFocus() {runCatching {focus?.let {audio.abandonAudioFocusRequest(it)}};focus=null
  if(owned) {AudioArbiter.release(this);owned=false}
 }
 private fun stopPlayer() {generation++;val p=player;player=null;runCatching {p?.reset()};runCatching {p?.release()};releaseFocus()
  current="Stopped";session?.setPlaybackState(PlaybackState.Builder().setState(PlaybackState.STATE_STOPPED,0,0f).build())
  stopForeground(STOP_FOREGROUND_REMOVE)
 }
 private fun update(state:String) {current="$state: $title"
  val code=when(state) {"Playing"->PlaybackState.STATE_PLAYING;"Paused"->PlaybackState.STATE_PAUSED;else->PlaybackState.STATE_BUFFERING}
  session?.setMetadata(MediaMetadata.Builder().putString(MediaMetadata.METADATA_KEY_TITLE,title).build())
  session?.setPlaybackState(PlaybackState.Builder().setActions(PlaybackState.ACTION_PLAY or PlaybackState.ACTION_PAUSE or PlaybackState.ACTION_STOP)
   .setState(code,PlaybackState.PLAYBACK_POSITION_UNKNOWN,if(code==PlaybackState.STATE_PLAYING) 1f else 0f).build())
  notifications.notify(NOTIFICATION,notification(state))
 }
 private fun notification(state:String):Notification {
  fun action(name:String,icon:Int):Notification.Action {
   val request=PendingIntent.getService(this,name.hashCode(),Intent(this,PhoneMediaService::class.java).setAction(name),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
   return Notification.Action.Builder(icon,name.replaceFirstChar {it.uppercase()},request).build()
  }
  val open=PendingIntent.getActivity(this,0,Intent(this,MainActivity::class.java),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
  return Notification.Builder(this,CHANNEL).setSmallIcon(android.R.drawable.ic_media_play)
   .setContentTitle(title.ifBlank {"SARAH phone media"}).setContentText(state).setContentIntent(open)
   .setOngoing(state=="Playing").setStyle(Notification.MediaStyle().setMediaSession(session?.sessionToken))
   .addAction(action(if(state=="Playing") "pause" else "resume",android.R.drawable.ic_media_pause))
   .addAction(action("stop",android.R.drawable.ic_menu_close_clear_cancel)).build()
 }
 override fun onDestroy() {unregisterReceiver(noisy);stopPlayer();session?.isActive=false;session?.release();session=null;super.onDestroy()}
 companion object {
  const val PLAY="com.serexe.sarah.PHONE_MEDIA_PLAY"
  const val CHANNEL="sarah-phone-media"
  const val NOTIFICATION=82993
  @Volatile private var current="Stopped"
  fun snapshot():String=current
 }
}
