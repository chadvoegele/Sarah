package com.serexe.sarah

/** Display only. Journal due time remains wall-clock epoch; no timer is recreated on a tick. */
internal object TimerCountdown {
 fun remaining(dueMillis:Long,nowMillis:Long):String {
  if(dueMillis<=nowMillis) return "Due now"
  val delta=dueMillis-nowMillis
  val seconds=delta/1000 + if(delta%1000>0) 1 else 0
  val hours=seconds/3600
  val minutes=(seconds%3600)/60
  val secs=seconds%60
  return if(hours>0) "$hours:${minutes.toString().padStart(2,'0')}:${secs.toString().padStart(2,'0')}"
    else "${minutes.toString().padStart(2,'0')}:${secs.toString().padStart(2,'0')}"
 }
}
