package com.serexe.sarah

/** Monotonic one-shot window; service owns lifetime, not Activity visibility or closures. */
internal class ListenerWindow(private val startedAt:Long) {
 fun valid(now:Long):Boolean = now>=startedAt && now-startedAt<LIMIT_MS
 companion object {const val LIMIT_MS=120000L}
}
