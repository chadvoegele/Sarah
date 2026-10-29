package com.serexe.sarah

/** Pure admission policy; all checks must pass after KWS recorder/native release. */
internal object OffscreenWakePolicy {
 fun admit(active:Boolean,unlocked:Boolean,audioIdle:Boolean,windowValid:Boolean,phase:String,paired:Boolean):Boolean =
  active && unlocked && audioIdle && windowValid && paired && phase in setOf("ready","done","error","cancelled")
}
