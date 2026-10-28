package com.serexe.sarah

import kotlinx.coroutines.*
import java.util.concurrent.CompletableFuture

/** Shared production boundary: cancellation is never a native-release acknowledgement. */
internal object CommandCleanup {
 // Establish command try/finally before Stop can cancel a queued Main dispatch.
 fun launchOwned(scope:CoroutineScope,body:suspend CoroutineScope.()->Unit):Job =
  scope.launch(start=CoroutineStart.UNDISPATCHED) {body()}
 suspend fun await(recording:Job?, captureReleased:()->Boolean,
                   playbackClosed:CompletableFuture<Boolean>, timeoutMs:Long=2500, preparing:Job?=null):Boolean =
  withContext(NonCancellable) {
   withTimeoutOrNull(timeoutMs) {
    recording?.join()
    preparing?.join()
    while(!playbackClosed.isDone) delay(10)
    captureReleased() && runCatching {playbackClosed.get()}.getOrDefault(false)
   } ?: false
  }
}

/** Application teardown is gated; OS destruction is an observation, never vetoable. */
internal class ServiceTeardown(private val invalidate:()->Unit,private val ready:()->Boolean,
                               private val teardown:()->Unit) {
 @Volatile var destroyed=false; private set
 @Volatile var stopped=false; private set
 private var finished=false
 fun stop() {stopped=true;invalidate()}
 fun destroyed() {destroyed=true;stop()}
 @Synchronized fun finish():Boolean {
  if(finished || !ready()) return false
  finished=true
  if(!destroyed) teardown()
  return true
 }
}
