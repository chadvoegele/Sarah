package com.serexe.sarah

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import org.json.JSONObject

/** Phone-owned catalog only. No filesystem path, arbitrary URL, cloud/DRM or model-selected URI. */
internal object PhoneMedia {
 val supportedActions=setOf("play_local","pause","resume","stop","status","volume")
 fun hasLibraryPermission(context:Context):Boolean = context.checkSelfPermission(
  if(Build.VERSION.SDK_INT>=33) Manifest.permission.READ_MEDIA_AUDIO else Manifest.permission.READ_EXTERNAL_STORAGE)==PackageManager.PERMISSION_GRANTED
 internal data class Song(val uri:Uri,val title:String,val artist:String)
 fun find(context:Context,query:String):List<Song> {
  require(query.length in 2..120 && query.none {it.isISOControl()})
  if(!hasLibraryPermission(context)) return emptyList()
  val collection=MediaStore.Audio.Media.EXTERNAL_CONTENT_URI
  val columns=arrayOf(MediaStore.Audio.Media._ID,MediaStore.Audio.Media.TITLE,MediaStore.Audio.Media.ARTIST)
  val matches=mutableListOf<Song>();val needle=query.lowercase(java.util.Locale.ROOT)
  context.contentResolver.query(collection,columns,"${MediaStore.Audio.Media.IS_MUSIC} != 0",null,
   "${MediaStore.Audio.Media.TITLE} ASC")?.use {cursor->
   val id=cursor.getColumnIndexOrThrow(MediaStore.Audio.Media._ID)
   val title=cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.TITLE)
   val artist=cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.ARTIST)
   var count=0
   while(cursor.moveToNext() && count++<5000) {
    val t=cursor.getString(title) ?: continue;val a=cursor.getString(artist) ?: ""
    if(t.lowercase(java.util.Locale.ROOT).contains(needle) || a.lowercase(java.util.Locale.ROOT).contains(needle)) {
     matches+=Song(android.content.ContentUris.withAppendedId(collection,cursor.getLong(id)),t,a)
     if(matches.size>12) break
    }
   }
  }
  return matches
 }
 fun execute(context:Context,envelope:JSONObject,conversation:String,turn:String):JSONObject {
  PhoneScheduleCommand.requestKey(envelope,conversation,turn)
  val cmd=envelope.getJSONObject("command")
  val result=try {
   val action=cmd.getString("action")
   if(action !in supportedActions) "Unsupported media action; nothing changed." to "denied"
   else when(action) {
    "play_local" -> {
     if(!hasLibraryPermission(context)) "Local music permission needed. In SARAH Settings, grant Music library access; no media opened." to "denied"
     else {
      val matches=find(context,cmd.getString("query"))
      when {
       matches.isEmpty() -> "No matching phone-local music found. No playback started." to "done"
       matches.size>1 -> "Multiple local matches: ${matches.take(5).joinToString("; ") {it.title+" by "+it.artist}}. Specify exact title; nothing played." to "done"
       else -> {val song=matches.single();send(context,PhoneMediaService.PLAY,song.uri.toString(),song.title)
        "Starting local ${song.title} by ${song.artist}; playback not yet confirmed." to "pending"}
      }
     }
    }
    "pause","resume","stop" -> {
     val action=cmd.getString("action")
     send(context,action,null,null)
     "${action.replaceFirstChar {it.uppercase()}} requested on this phone; check media notification for actual state." to "pending"
    }
    "status" -> "Phone media: ${PhoneMediaService.snapshot()}." to "done"
    "volume" -> {
     val percent=cmd.getInt("percent");require(percent in 0..100)
     send(context,"volume",null,null,percent)
     "Phone media volume change requested to $percent percent; check device output." to "pending"
    }
    else -> "Unsupported media action; nothing changed." to "denied"
   }
  } catch (_:Exception) {"Phone media unavailable or request invalid. No automatic retry of uncertain playback." to "uncertain"}
  return JSONObject().put("status",result.second).put("reply",result.first.take(1000))
 }
 private fun send(context:Context,action:String,uri:String?,title:String?,volume:Int=-1) {
  val i=Intent(context,PhoneMediaService::class.java).setAction(action)
  if(uri!=null) i.putExtra("uri",uri)
  if(title!=null) i.putExtra("title",title)
  if(volume>=0) i.putExtra("volume",volume)
  if(action==PhoneMediaService.PLAY) context.startForegroundService(i) else context.startService(i)
 }
}

internal object PhoneActionRouter {
 fun execute(context:Context,envelope:JSONObject,conversation:String,turn:String):JSONObject =
  if(envelope.getJSONObject("command").optString("_phone_type")=="media") PhoneMedia.execute(context,envelope,conversation,turn)
  else PhoneScheduleCommand.execute(context,envelope,conversation,turn)
}
